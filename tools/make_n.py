#!/usr/bin/env python3
"""Build a clip in the approved layout "N" (dusty-pink card) from a short CONTENT file.

usage: make_n.py CONTENT.json SRC.mp4 OUT.mp4 [--template templates/layout_N.json] [--ass-only]

CONTENT.json holds only what changes per clip:
  title           : metadata title (also used in the report)
  title_top       : small yellow line above the main title (hook / question)
  title_main      : big white title line
  source          : free-form info about the recording (kept in the spec)
  card_crop_y     : (optional) first source row of the card crop, in 720x1280 source pixels (default 0 = top)
  end_text        : (optional) text of the end pill (default from the template: 17LIVEで配信中)
  segments        : [{name, in, out, voff?, captions:[{s,e,text}], comments:[{s,e,text}]}]
                    times are SOURCE seconds on the 1/24 grid (same rules as build_clip.py).
                    captions = her words (white, on a cushion inside the card).
                    comments = viewer comments, original text, no user names (slide-in bubble).
                    While she reads a comment aloud, show only the comment bubble, not a caption.
  Emphasis: wrap a word in [[ ]] -> yellow in captions, deep pink in comment bubbles.

Steps: writes OUT_base.spec.json (full build_clip spec) -> build_clip --ass-only -> ass_bubbles (template args)
-> build_clip --use-ass. Output: 1080x1920, 24 fps, H.264 + AAC 48 kHz, -14 LUFS.
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def emph(text, on, off):
    return re.sub(r"\[\[(.+?)\]\]", lambda m: "{\\c&H%s&}%s{\\c&H%s&}" % (on, m.group(1), off), text)


def video_filter(T, crop_y):
    c, b = T["card"], T["background"]
    sw, sh, ch = c["src_w"], c["src_h"], c["src_crop_h"]
    crop_y = max(0, min(int(crop_y), sh - ch))
    W, H, R = c["w"], c["h"], c["radius"]
    (r0, g0, b0), (r1, g1, b1) = b["top_rgb"], b["bottom_rgb"]
    ox, oy = b["shadow_offset"]
    mask = (f"color=black:s={W}x{H}:r=24:d=1,format=gray,geq=lum='clip(({R}.5-hypot(max(max({R}-X\\,X-({W - 1}-{R}))\\,0)\\,"
            f"max(max({R}-Y\\,Y-({H - 1}-{R}))\\,0)))*255\\,0\\,255)',loop=loop=-1:size=1")
    bg = (f"color=black:s=1080x1920:r=24:d=1,format=gbrp,geq=r='{r0}-{r0 - r1}*Y/1919':g='{g0}-{g0 - g1}*Y/1919':"
          f"b='{b0}-{b0 - b1}*Y/1919',format=yuv420p,drawbox=x={c['x'] + ox}:y={c['y'] + oy}:w={W}:h={H}:"
          f"color=black@{b['shadow']}:t=fill,gblur=sigma={b['shadow_blur']},loop=loop=-1:size=1")
    # the canvas is derived from the source frames so output timing follows the source (no 1-frame lag);
    # the static background is laid over it, then the card.
    return (f"scale={sw}:{sh}:flags=lanczos,setsar=1,split[srcA][srcB];"
            f"[srcA]crop={sw}:{ch}:0:{crop_y},scale={W}:{H}:flags=lanczos,setsar=1,format=yuva420p[fgv];"
            f"{mask}[mask];[fgv][mask]alphamerge[card];{bg}[bg];"
            f"[srcB]scale=1080:1920,setsar=1,drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill[canvas];"
            f"[canvas][bg]overlay=0:0:eof_action=repeat[base];[base][card]overlay={c['x']}:{c['y']},format=yuv420p,setsar=1")


def frame_overlay(T):
    c = T["card"]; W, H, R = c["w"], c["h"], c["radius"]; k = 16
    path = (f"m {R} 0 l {W - R} 0 b {W - k} 0 {W} {k} {W} {R} l {W} {H - R} b {W} {H - k} {W - k} {H} {W - R} {H} "
            f"l {R} {H} b {k} {H} 0 {H - k} 0 {H - R} l 0 {R} b 0 {k} {k} 0 {R} 0")
    return {"s": 0, "e": None, "style": "Frame", "layer": 3,
            "text": "{\\an7\\pos(%d,%d)\\bord%d\\shad0\\1a&HFF&\\3a&H%s&\\3c&H%s&\\p1}%s{\\p0}"
                    % (c["x"], c["y"], c["border_px"], c["border_alpha"], c["border_bgr"], path)}


def build_spec(C, T):
    t, e = T["title"], T["emphasis"]
    title = ("{\\fs%d\\c&H%s&}%s\\N{\\fs%d\\c&H%s&}%s"
             % (t["top_fs"], t["top_bgr"], C["title_top"], t["main_fs"], t["main_bgr"], C["title_main"])) \
        if C.get("title_top") else "{\\fs%d\\c&H%s&}%s" % (t["main_fs"], t["main_bgr"], C["title_main"])
    segs = []
    for s in C["segments"]:
        seg = {k: v for k, v in s.items() if k not in ("captions", "comments")}
        seg["captions"] = [{"s": c["s"], "e": c["e"], "style": "Sub",
                            "text": emph(c["text"], e["sub_bgr"], e["sub_base_bgr"])} for c in s.get("captions", [])]
        seg["labels"] = [{"s": c["s"], "e": c["e"], "style": "Label", "layer": 1,
                          "text": "コメント「%s」" % emph(c["text"], e["comment_bgr"], e["comment_base_bgr"])}
                         for c in s.get("comments", [])]
        segs.append(seg)
    end = T["end"]
    return {
        "title": C["title"], "source": C.get("source", {}), "layout": {"id": "N", "template": "templates/layout_N.json"},
        "playres": T["playres"], "crf": T["crf"], "end_fade": T["end_fade"], "max_line_chars": T["max_line_chars"],
        "styles": T["styles"], "video_filter": video_filter(T, C.get("card_crop_y", 0)),
        "segments": segs,
        "overlays": [frame_overlay(T),
                     {"s": 0, "e": None, "style": "Title", "layer": 5, "text": title},
                     {"s": -end["seconds"], "e": None, "style": "End", "layer": 6, "text": C.get("end_text", end["text"])}],
    }


def main():
    content, src, out = sys.argv[1:4]
    T = json.load(open(arg("--template", os.path.join(ROOT, "templates", "layout_N.json")), encoding="utf-8"))
    C = json.load(open(content, encoding="utf-8"))
    base = os.path.splitext(out)[0]
    spec_path = base + ".spec.json"
    json.dump(build_spec(C, T), open(spec_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    py = sys.executable
    subprocess.run([py, os.path.join(HERE, "build_clip.py"), spec_path, src, out, "--ass-only"], check=True)
    subprocess.run([py, os.path.join(HERE, "ass_bubbles.py"), base + ".ass", base + "_b.ass"] + T["bubbles_args"], check=True)
    if "--ass-only" in sys.argv:
        return
    subprocess.run([py, os.path.join(HERE, "build_clip.py"), spec_path, src, out, "--use-ass", base + "_b.ass"], check=True)


if __name__ == "__main__":
    main()
