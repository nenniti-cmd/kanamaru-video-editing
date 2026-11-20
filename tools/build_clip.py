#!/usr/bin/env python3
"""Build a vertical clip from one raw source + an edit spec (JSON).

Sync strategy (fixes the drift seen when parts are cut separately and
stream-copied together):
  * the source is decoded ONCE; video is put on a constant 24 fps grid
    (frames picked by index, restamped N/24) and audio is put on its
    sample-count timeline and resampled to 48 kHz, so one video frame is
    exactly 2000 audio samples;
  * every segment is cut with trim (frame index) and atrim (sample index)
    from the SAME timeline, so audio and video segments have identical
    durations;
  * segments are joined with the concat FILTER (not the concat demuxer),
    so no per-part AAC priming/padding can accumulate.
Captions are burned in with libass from an ASS file generated from the
spec (caption times are given in source time and mapped to output time).

usage: build_clip.py SPEC.json SRC.mp4 OUT.mp4 [--ass-only] [--max-mb 9.5] [--use-ass FILE.ass]
"""
import json, subprocess, sys, re, os

FPS = 24
SR = 48000
SPF = SR // FPS  # samples per frame = 2000


def fr(t):
    return int(round(t * FPS))


def ts(t):
    t = max(0.0, t)
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def plain_len(text):
    return max(len(re.sub(r"\{[^}]*\}", "", ln)) for ln in text.split("\\N"))


def main():
    spec_path, src, out = sys.argv[1:4]
    ass_only = "--ass-only" in sys.argv
    max_mb = float(sys.argv[sys.argv.index("--max-mb") + 1]) if "--max-mb" in sys.argv else None
    use_ass = sys.argv[sys.argv.index("--use-ass") + 1] if "--use-ass" in sys.argv else None  # pre-processed ASS (e.g. bubbles)
    spec = json.load(open(spec_path, encoding="utf-8"))
    segs = spec["segments"]

    # ---- timeline mapping -------------------------------------------------
    t_out = 0.0
    events = []
    for i, s in enumerate(segs):
        f0, f1 = fr(s["in"]), fr(s["out"])
        assert abs(f0 / FPS - s["in"]) < 1e-3 and abs(f1 / FPS - s["out"]) < 1e-3, f"segment {i} not frame aligned"
        k = int(s.get("speed", 1))          # integer speed-up (e.g. 3 = 3x); frames are kept 1-in-k
        assert k >= 1 and (f1 - f0) % k == 0, f"segment {i}: length in frames must be a multiple of speed {k}"
        s["_f0"], s["_f1"], s["_t0"], s["_k"] = f0, f1, t_out, k
        dur = (f1 - f0) / FPS / k
        for c in s.get("captions", []) + s.get("labels", []):
            a = (max(c["s"], s["in"]) - s["in"]) / k + t_out
            b = (min(c["e"], s["out"]) - s["in"]) / k + t_out
            if b - a < 0.15:
                continue
            style = c.get("style", "Sub")
            if style == "Sub" and plain_len(c["text"]) > spec.get("max_line_chars", 12):
                print(f"WARN long caption line ({plain_len(c['text'])}): {c['text']}", file=sys.stderr)
            events.append((a, b, style, c["text"], c.get("layer", 0)))
        t_out += dur
    total = t_out
    for g in spec.get("overlays", []):
        a = g["s"] if g["s"] >= 0 else total + g["s"]
        b = total if g.get("e") is None else (g["e"] if g["e"] >= 0 else total + g["e"])
        events.append((a, b, g["style"], g["text"], g.get("layer", 5)))

    # ---- ASS -----------------------------------------------------------------
    ass_path = os.path.splitext(out)[0] + ".ass"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("[Script Info]\n")
        pw, ph = spec.get("playres", [720, 1280])
        f.write(f"Title: {spec['title']}\nScriptType: v4.00+\nPlayResX: {pw}\nPlayResY: {ph}\n"
                "ScaledBorderAndShadow: yes\nWrapStyle: 2\nYCbCr Matrix: TV.709\n\n")
        f.write("[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
                "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                "Alignment, MarginL, MarginR, MarginV, Encoding\n")
        for st in spec["styles"]:
            f.write("Style: " + st + "\n")
        f.write("\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for a, b, style, text, layer in sorted(events):
            f.write(f"Dialogue: {layer},{ts(a)},{ts(b)},{style},,0,0,0,,{text}\n")
    print(f"ASS written: {ass_path}  (total {total:.3f}s, {len(segs)} segments)")
    if use_ass:
        ass_path = use_ass
        print(f"using ASS: {ass_path}")
    if ass_only:
        return

    # ---- filtergraph -------------------------------------------------------
    n = len(segs)
    # Video: frames are selected by INDEX (trim start_frame/end_frame count decoded
    # frames) and re-stamped N/24, so container timestamp jitter cannot drop or
    # duplicate a frame. Audio: timestamps are replaced by the decoded sample count
    # before resampling, so atrim cuts by sample position, not by jittery packet pts.
    # spec["video_filter"] lets a layout scale/crop/pad the picture (e.g. a title band); default fills 720x1280
    vf = spec.get("video_filter", "scale=720:1280:flags=lanczos,setsar=1")
    fc = [f"[0:v]{vf},split={n}" + "".join(f"[v{i}]" for i in range(n)),
          f"[0:a]asetpts=N/SR/TB,aresample={SR},asetpts=N/SR/TB,aformat=channel_layouts=stereo,asplit={n}"
          + "".join(f"[a{i}]" for i in range(n))]
    fade = spec.get("seam_fade", 0.012)
    for i, s in enumerate(segs):
        k = s["_k"]
        nf = (s["_f1"] - s["_f0"]) // k     # output frames of this segment
        dur = nf / FPS
        # optional per-segment video offset (seconds, on the 1/24 grid after rounding): the picture for audio
        # time t is taken from t + voff. Used for recordings whose video track is shifted against the audio
        # (e.g. voff = -16.2 when the video is 16.2 s early).
        dv = int(round(s.get("voff", 0.0) * FPS))
        assert s["_f0"] + dv >= 0, f"segment {i}: voff reaches before the start of the source"
        step = f",framestep={k}" if k > 1 else ""
        fc.append(f"[v{i}]trim=start_frame={s['_f0'] + dv}:end_frame={s['_f1'] + dv}{step},setpts=N/({FPS}*TB)[vs{i}]")
        tempo = ""
        if k > 1:   # atempo (max 2.0 per stage), then pad/trim to exactly nf*SPF samples so A/V stay locked
            r, parts = float(k), []
            while r > 2.0:
                parts.append("atempo=2.0"); r /= 2.0
            parts.append(f"atempo={r:.6f}")
            tempo = "," + ",".join(parts) + f",aresample={SR},apad,atrim=end_sample={nf * SPF},asetpts=N/SR/TB"
        mute = ",volume=0" if s.get("mute") else ""
        fc.append(f"[a{i}]atrim=start_sample={s['_f0'] * SPF}:end_sample={s['_f1'] * SPF},asetpts=PTS-STARTPTS{tempo}{mute},"
                  f"afade=t=in:d={fade},afade=t=out:st={dur - fade:.4f}:d={fade}[as{i}]")
    fc.append("".join(f"[vs{i}][as{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac]")
    endfade = spec.get("end_fade", 0.25)
    assf = ass_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    fc.append(f"[vc]ass='{assf}',fade=t=out:st={total - endfade:.4f}:d={endfade}[vo]")
    afinal = f"afade=t=out:st={total - endfade:.4f}:d={endfade}"

    # pass 1: loudness measurement on the edited audio
    g1 = ";".join(fc[:-1]) + f";[vc]nullsink;[ac]{afinal},loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[ao]"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-filter_complex", g1, "-map", "[ao]",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        sys.exit("loudnorm measurement failed:\n" + r.stderr[-2000:])
    L = json.loads(m.group(0))
    print("loudness measured:", {k: L[k] for k in ("input_i", "input_tp", "input_lra", "input_thresh")})
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={L['input_i']}:measured_TP={L['input_tp']}:"
          f"measured_LRA={L['input_lra']}:measured_thresh={L['input_thresh']}:offset={L['target_offset']}:linear=true")
    g2 = ";".join(fc) + f";[ac]{afinal},{ln},aresample={SR}[ao]"
    base = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src, "-filter_complex", g2,
            "-map", "[vo]", "-map", "[ao]", "-r", str(FPS), "-fps_mode", "cfr",
            "-c:v", "libx264", "-preset", "slow", "-profile:v", "high", "-pix_fmt", "yuv420p", "-g", "48"]
    tail = ["-c:a", "aac", "-b:a", "128k" if max_mb else "160k", "-ar", str(SR),
            "-movflags", "+faststart", "-metadata", f"title={spec['title']}", out]
    if max_mb:
        # size-capped delivery (e.g. Drive connector 10 MB limit): 2-pass ABR
        vk = int((max_mb * 8 * 1024 * 1024 / (total + 0.2) - 128000 - 30000) / 1000)
        print(f"2-pass target video bitrate {vk} kb/s for <= {max_mb} MB")
        plog = os.path.splitext(out)[0] + ".x264pass"
        subprocess.run(base + ["-b:v", f"{vk}k", "-pass", "1", "-passlogfile", plog, "-an", "-f", "null", "-"], check=True)
        subprocess.run(base + ["-b:v", f"{vk}k", "-pass", "2", "-passlogfile", plog] + tail, check=True)
    else:
        subprocess.run(base + ["-crf", str(spec.get("crf", 21))] + tail, check=True)
    json.dump({"total": total, "segments": [{"in": s["in"], "out": s["out"], "out_start": round(s["_t0"], 4),
               "frames": (s["_f1"] - s["_f0"]) // s["_k"], "speed": s["_k"]} for s in segs], "loudnorm_pass1": L},
              open(os.path.splitext(out)[0] + ".timeline.json", "w"), indent=1, ensure_ascii=False)
    print("done:", out)


if __name__ == "__main__":
    main()
