#!/usr/bin/env python3
"""無人の編集セッション用：生素材1本を下ごしらえして、構成を決めるための材料を作る。

usage: python3 tools/cedit/analyze.py RAW.mp4 OUTDIR [--asr large,kotoba] [--max-sec 400]
出力（OUTDIR）:
  src.mkv          720x1280・24fps CFR・PCM 48kHz の作業用ファイル（雛形の入力。秒は生素材と同じ）
  aud16.wav        音声（16kHz mono）
  asr_large.json   Whisper large-v3 の単語タイムスタンプつき文字起こし
  asr_large.txt    同・読みやすい形（「開始-終了 本文」と「単語@秒」）
  asr_kotoba.txt   kotoba-whisper v2.0（12秒ごと）の文字起こし（聞き取りの照合用）
  quiet.txt        無音（-34dB以下、0.15秒以上）の区間＝カット点の候補
  sync.txt         口の動きと声の強さの相互相関（映像が早い秒数。±0.05秒以内なら正常）
  tile_XX.png      1秒ごとのコマを並べた一覧（20列。行=20秒。左上が0秒）。画面に映るもの（他人のプロフィール等）の確認用
"""
import json, os, subprocess, sys, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
W = os.environ.get("CEDIT_WORK", "/tmp/cedit")
PY = os.path.join(W, "venv", "bin", "python")


def run(cmd, **kw):
    print("+", " ".join(cmd) if isinstance(cmd, list) else cmd, flush=True)
    return subprocess.run(cmd, check=True, **kw)


def hf_snapshot(repo):
    # faster-whisper downloads only the files it needs when given the repo id (snapshot_download of the
    # whole kotoba repo also pulls large extra files). Xet transfer is blocked in this network.
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    return repo


def main():
    raw, out = sys.argv[1], sys.argv[2]
    asr = (sys.argv[sys.argv.index("--asr") + 1] if "--asr" in sys.argv else "large,kotoba").split(",")
    os.makedirs(out, exist_ok=True)
    src = os.path.join(out, "src.mkv")
    run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-map", "0:v:0", "-map", "0:a:0",
         "-vf", "scale=720:1280:flags=lanczos,setsar=1", "-r", "24", "-fps_mode", "cfr",
         "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-pix_fmt", "yuv420p",
         "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", src])
    wav = os.path.join(out, "aud16.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", wav])
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                               capture_output=True, text=True).stdout.strip())

    # quiet gaps (cut candidates)
    w = wave.open(wav); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    hop = 800
    db = 20 * np.log10(np.sqrt(np.array([np.mean(x[i * hop:(i + 1) * hop] ** 2) for i in range(len(x) // hop)])) + 1e-9)
    runs, cur = [], None
    for i, v in enumerate(db):
        t = i * 0.05
        if v < -34:
            cur = t if cur is None else cur
        else:
            if cur is not None and t - cur >= 0.15:
                runs.append(f"{cur:.2f}-{t:.2f}")
            cur = None
    open(os.path.join(out, "quiet.txt"), "w").write("無音（-34dB以下・0.15秒以上）:\n" + "\n".join(runs) + "\n")

    # sync: windowed lag of mouth motion vs audio
    wins = [[a, min(a + 60, dur - 1)] for a in range(2, int(dur) - 20, 60)] or [[1, dur - 1]]
    r = subprocess.run([PY, "-I", os.path.join(ROOT, "tools", "verify", "lagwin.py"), src, "-1", "1", json.dumps(wins)],
                       capture_output=True, text=True)
    open(os.path.join(out, "sync.txt"), "w").write(
        "映像が音声より早い秒数（正なら映像が早い）。r が 0.15 未満の区間は信頼度が低い。\n" + r.stdout + r.stderr[-2000:])

    # frame tiles (1 fps, 20 x 20 per tile)
    tdir = os.path.join(out, "frames"); os.makedirs(tdir, exist_ok=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", "fps=1,scale=90:160", "-f", "image2", os.path.join(tdir, "f_%04d.png")])
    n = len([f for f in os.listdir(tdir) if f.endswith(".png")])
    for k in range(0, n, 400):
        files = sorted(os.listdir(tdir))[k:k + 400]
        lst = os.path.join(out, f"tile_{k // 400:02d}.txt")
        open(lst, "w").write("".join(f"file '{os.path.join(tdir, f)}'\n" for f in files))
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-vf", "tile=20x20",
             "-frames:v", "1", os.path.join(out, f"tile_{k // 400:02d}.png")])

    # ASR
    if "large" in asr:
        m = hf_snapshot("Systran/faster-whisper-large-v3")
        run([PY, "-I", os.path.join(ROOT, "tools", "verify", "asr.py"), m, os.path.join(out, "asr_large.json"), wav],
            stdout=open(os.path.join(out, "asr_large.log"), "w"), stderr=subprocess.STDOUT)
        d = list(json.load(open(os.path.join(out, "asr_large.json"))).values())[0]
        with open(os.path.join(out, "asr_large.txt"), "w") as f:
            for s in d:
                f.write(f"{s['start']:7.2f}-{s['end']:7.2f} {s['text'].strip()}\n")
                f.write("    " + " ".join(f"{wd[2].strip()}@{wd[0]:.2f}" for wd in s["words"]) + "\n")
    if "kotoba" in asr:
        m = hf_snapshot("kotoba-tech/kotoba-whisper-v2.0-faster")
        wins = [f"{a}:{min(a + 12, dur)}" for a in range(0, int(dur), 12)]
        run([PY, "-I", os.path.join(ROOT, "tools", "verify", "asrwin_text.py"), m, wav] + wins,
            stdout=open(os.path.join(out, "asr_kotoba.txt"), "w"), stderr=subprocess.DEVNULL)
    print("analyze done:", out, f"duration {dur:.1f}s")


if __name__ == "__main__":
    main()
