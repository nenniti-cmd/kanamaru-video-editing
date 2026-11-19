"""Measure editing-induced A/V offset of an edited clip against its raw source.

For every frame of EDIT, find the best-matching frame of SRC (image match on a
band of the picture that avoids burned-in captions) -> video source time.
For every audio window of EDIT, find its position in SRC audio by normalized
cross-correlation -> audio source time.
offset = audio_src_time - video_src_time at the same edit time.
  > 0 : audio is AHEAD of the picture (sound plays before the mouth moves)
  < 0 : audio LAGS the picture
usage: srcalign.py SRC EDIT [--json OUT] [--band 0.22 0.80]
"""
import sys, json, subprocess, argparse
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("edit")
ap.add_argument("--band", nargs=2, type=float, default=[0.22, 0.80])
ap.add_argument("--json")
ap.add_argument("--awin", type=float, default=0.5)
a = ap.parse_args()

TW, TH = 36, 64


def pts(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "frame=pts_time",
                          "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.split()
    return np.array([float(v.strip(",")) for v in out if v.strip(",") and v.strip(",") != "N/A"])


def thumbs(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-fps_mode", "passthrough", "-vf",
                          f"scale={TW}:{TH}:flags=area", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    t = np.frombuffer(raw, np.uint8).reshape(-1, TH, TW).astype(np.float32)
    y0, y1 = int(a.band[0] * TH), int(a.band[1] * TH)
    t = t[:, y0:y1, :].reshape(len(t), -1)
    t = t - t.mean(1, keepdims=True)
    t /= (np.linalg.norm(t, axis=1, keepdims=True) + 1e-6)
    return t


def audio(path, sr=8000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


sp, ep = pts(a.src), pts(a.edit)
st, et = thumbs(a.src), thumbs(a.edit)
n = min(len(et), len(ep)); st = st[:len(sp)]
sim = et[:n] @ st.T                      # cosine similarity edit x src
j = sim.argmax(1)
vmatch = sim[np.arange(n), j]
vsrc = sp[j]                             # source time shown at each edit frame
voff = vsrc - ep[:n]

SR = 8000
sa, ea = audio(a.src, SR), audio(a.edit, SR)
W = int(a.awin * SR)
F = 1 << int(np.ceil(np.log2(len(sa) + W)))
SA = np.fft.rfft(sa, F)
csum = np.concatenate([[0], np.cumsum(sa.astype(np.float64) ** 2)])
rows = []
for k in range(0, len(ea) - W, W // 2):
    w = ea[k:k + W]
    if np.sqrt(np.mean(w ** 2)) < 0.003:        # skip silence
        continue
    c = np.fft.irfft(SA * np.conj(np.fft.rfft(w, F)), F)[:len(sa) - W]
    energy = np.sqrt(csum[W:W + len(c)] - csum[:len(c)]) * np.linalg.norm(w) + 1e-9
    nc = c / energy
    p = int(nc.argmax())
    t_edit = (k + W / 2) / SR
    a_src = (p + W / 2) / SR
    a_off = a_src - t_edit
    i = int(np.clip(np.searchsorted(ep[:n], t_edit), 0, n - 1))
    # video offset: median over the frames covered by this audio window (robust)
    lo = max(0, i - int(a.awin * 12)); hi = min(n, i + int(a.awin * 12) + 1)
    v_off = float(np.median(voff[lo:hi]))
    rows.append({"t": round(t_edit, 3), "audio_ncc": round(float(nc[p]), 3), "a_off": round(a_off, 4),
                 "v_off": round(v_off, 4), "av_ms": round((a_off - v_off) * 1000, 1),
                 "vmatch": round(float(np.median(vmatch[lo:hi])), 3)})

good = [r for r in rows if r["audio_ncc"] > 0.6 and r["vmatch"] > 0.95]
av = np.array([r["av_ms"] for r in good]) if good else np.array([np.nan])
summary = {"windows": len(rows), "reliable": len(good), "median_ms": float(np.median(av)),
           "p05_ms": float(np.percentile(av, 5)), "p95_ms": float(np.percentile(av, 95)),
           "max_abs_ms": float(np.max(np.abs(av))), "video_frame_step_ms": 1000 / 24}
print(json.dumps(summary))
for r in rows:
    flag = "" if r in good else "  (low-confidence)"
    print(f"t={r['t']:7.2f}  src_audio={r['t']+r['a_off']:7.2f} src_video={r['t']+r['v_off']:7.2f}  "
          f"A-V={r['av_ms']:+7.1f}ms  ncc={r['audio_ncc']:.2f} vm={r['vmatch']:.3f}{flag}")
if a.json:
    json.dump({"summary": summary, "rows": rows}, open(a.json, "w"), indent=1)
