"""Make a labelled strip of mouth crops around a bilabial speech onset.
usage: lipstrip.py VIDEO T_APPROX OUT.png [search=0.35]
Finds the strongest audio-energy rise within +-search s of T_APPROX (10 ms
resolution), then shows frames -6..+3 relative to the frame containing that
onset, with the audio RMS of each frame period drawn as a bar."""
import sys, subprocess
import numpy as np, cv2

path, t0, outp = sys.argv[1], float(sys.argv[2]), sys.argv[3]
srch = float(sys.argv[4]) if len(sys.argv) > 4 else 0.35
FPS = 24
aud = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
x = np.frombuffer(aud, np.int16).astype(np.float32) / 32768
h = 160
db = 20 * np.log10(np.array([np.sqrt(np.mean(x[i:i + h] ** 2) + 1e-10) for i in range(0, len(x) - h, h)]))
lo, hi = int((t0 - srch) * 100), int((t0 + srch) * 100)
rise = db[lo + 3:hi + 3] - db[lo:hi]
k = lo + int(np.argmax(rise)) + 2
onset = k / 100
of = int(onset * FPS)
frames = []
for d in range(-6, 4):
    t = (of + d) / FPS
    img = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.4f}", "-i", path, "-frames:v", "1", "-f", "image2pipe",
                          "-vcodec", "png", "-"], capture_output=True, check=True).stdout
    frames.append((d, t, cv2.imdecode(np.frombuffer(img, np.uint8), cv2.IMREAD_COLOR)))
g = cv2.cvtColor(frames[6][2], cv2.COLOR_BGR2GRAY)
casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
fc = casc.detectMultiScale(g, 1.1, 6, minSize=(150, 150))
if len(fc):
    fx, fy, fw, fh = max(fc, key=lambda r: r[2] * r[3])
    box = (int(fx + 0.15 * fw), int(fy + 0.55 * fh), int(fx + 0.85 * fw), int(fy + 1.15 * fh))
else:
    box = (200, 520, 520, 760)
tiles = []
for d, t, im in frames:
    c = cv2.resize(im[box[1]:box[3], box[0]:box[2]], (220, 190))
    a0, a1 = int(t * 100), int((t + 1 / FPS) * 100)
    lvl = float(np.max(db[a0:a1 + 1]))
    bar = int(np.clip((lvl + 50) / 45, 0, 1) * 200)
    pad = np.full((70, 220, 3), 255, np.uint8)
    cv2.rectangle(pad, (10, 50), (10 + bar, 64), (0, 0, 200) if t + 1 / FPS > onset >= t else (90, 90, 90), -1)
    cv2.putText(pad, f"{d:+d}f {t:.3f}s", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    cv2.putText(pad, f"{lvl:.0f}dB", (150, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    tiles.append(np.vstack([c, pad]))
strip = np.hstack(tiles)
cv2.putText(strip, "", (0, 0), 0, 1, 0)
cv2.imwrite(outp, strip)
print(f"onset {onset:.2f}s (frame {of}, frame starts {of/FPS:.3f}s); red bar = frame containing onset")
