"""Mouth-openness vs speech-envelope cross-correlation (inherent lip-sync check).
Positive best lag = audio LATER than mouth movement.
usage: lipsync.py VIDEO [start end]"""
import sys, subprocess
import numpy as np, cv2

path = sys.argv[1]
ss = ["-ss", sys.argv[2], "-to", sys.argv[3]] if len(sys.argv) > 3 else []
FPS = 24; W, H = 540, 960
raw = subprocess.run(["ffmpeg", "-v", "error", *ss, "-i", path, "-vf", f"fps={FPS},scale={W}:{H}", "-pix_fmt", "gray",
                      "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W)
casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
box = None; feats = []
for i, f in enumerate(fr):
    if i % 2 == 0:
        d = casc.detectMultiScale(f, 1.1, 6, minSize=(150, 150))
        if len(d):
            b = max(d, key=lambda r: r[2] * r[3]).astype(float)
            box = b if box is None else 0.7 * box + 0.3 * b
    if box is None:
        feats.append((np.nan, np.nan)); continue
    x, y, w, h = box
    roi = f[int(y + 0.68 * h):int(min(H, y + 1.02 * h)), int(x + 0.3 * w):int(x + 0.7 * w)].astype(np.float32)
    if roi.size == 0:
        feats.append((np.nan, np.nan)); continue
    roi = cv2.GaussianBlur(roi, (5, 5), 0)
    thr = np.percentile(roi, 50) - 25
    dark = float(np.mean(roi < thr))                          # open mouth -> dark cavity
    vgrad = float(np.mean(np.abs(np.diff(roi, axis=0))))      # lip edges
    feats.append((dark, vgrad))
feats = np.array(feats)
aud = subprocess.run(["ffmpeg", "-v", "error", *ss, "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
x = np.frombuffer(aud, np.int16).astype(np.float32) / 32768
hop = 16000 // FPS
env = np.array([np.sqrt(np.mean(x[k * hop:(k + 1) * hop] ** 2) + 1e-9) for k in range(len(x) // hop)])
env = np.log(env)
n = min(len(env), len(feats))


def z(v):
    v = np.nan_to_num(v - np.nanmean(v)); s = v.std(); return v / s if s > 0 else v


def smooth(v, k=3):
    return np.convolve(v, np.ones(k) / k, mode="same")


E = z(smooth(env[:n]))
for name, col in (("dark", 0), ("vgrad", 1)):
    M = z(smooth(feats[:n, col]))
    res = []
    for lag in range(-12, 13):  # +-500 ms
        a = M[max(0, -lag):n - max(0, lag)]
        b = E[max(0, lag):n - max(0, -lag)]
        res.append(float(np.mean(a * b)))
    res = np.array(res); k = int(res.argmax())
    curve = " ".join(f"{(l)*1000/FPS:+.0f}:{r:.2f}" for l, r in zip(range(-12, 13), res) if l % 2 == 0)
    print(f"{name:5s} best lag {(k-12)*1000/FPS:+.0f} ms  r={res[k]:.3f}  (r at 0 = {res[12]:.3f})  valid={np.mean(~np.isnan(feats[:n,col])):.2f}")
    print("      curve:", curve)
