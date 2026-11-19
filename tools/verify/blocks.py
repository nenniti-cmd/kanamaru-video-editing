import sys, wave, numpy as np
w = wave.open(sys.argv[1]); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)/32768
hop = 160; db = 20*np.log10(np.array([np.sqrt(np.mean(x[i:i+hop]**2)+1e-10) for i in range(0, len(x)-hop, hop)]))
for arg in sys.argv[2:]:
    a, b = map(float, arg.split(":"))
    on = db[int(a*100):int(b*100)] > -32
    blocks = []; i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and (on[j] or (j+15 < len(on) and on[j:j+15].any())): j += 1
            blocks.append((a+i/100, a+j/100)); i = j
        else: i += 1
    print(f"[{a:.3f}-{b:.3f}] " + "  ".join(f"{s:.2f}-{e:.2f}" for s, e in blocks if e-s > 0.05))
