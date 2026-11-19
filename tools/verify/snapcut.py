"""Snap candidate cut points to the quietest frame boundary nearby.

usage: snapcut.py WAV16k  t1:lo:hi [t2:lo:hi ...]
For each candidate, searches [lo,hi] for the frame boundary (k/24 s) whose
surrounding 80 ms has the lowest RMS, and prints a 10 ms dB profile.
"""
import sys, wave
import numpy as np

w = wave.open(sys.argv[1]); sr = w.getframerate()
x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
hop = sr // 100
env = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2) + 1e-10) for i in range(0, len(x) - hop, hop)])
db = 20 * np.log10(env)
noise = np.percentile(db, 10)
print(f"noise floor (p10) {noise:.1f} dB, speech p90 {np.percentile(db, 90):.1f} dB")
for arg in sys.argv[2:]:
    name, lo, hi = arg.split(":")
    lo, hi = float(lo), float(hi)
    best = None
    k0, k1 = int(np.ceil(lo * 24)), int(np.floor(hi * 24))
    for k in range(k0, k1 + 1):
        t = k / 24
        i = int(t * 100)
        seg = db[max(0, i - 4):i + 4]
        v = float(np.max(seg))
        if best is None or v < best[1]:
            best = (t, v)
    t, v = best
    i = int(t * 100)
    prof = " ".join(f"{d:.0f}" for d in db[max(0, i - 30):i + 31:3])
    print(f"{name}: snap {t:.4f}s (frame {round(t*24)})  max80ms={v:.1f}dB  [{lo}-{hi}]\n   profile(-0.3s..+0.3s step30ms): {prof}")
