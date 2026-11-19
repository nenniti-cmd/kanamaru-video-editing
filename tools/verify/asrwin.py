import sys, wave, numpy as np
from faster_whisper import WhisperModel
m = WhisperModel(sys.argv[1], device="cpu", compute_type="int8", cpu_threads=4)
w = wave.open(sys.argv[2]); sr = w.getframerate()
x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
for arg in sys.argv[3:]:
    a, b = map(float, arg.split(":"))
    seg = x[int(a * sr):int(b * sr)]
    segs, _ = m.transcribe(seg, language="ja", word_timestamps=True, beam_size=5, vad_filter=False, condition_on_previous_text=False)
    out = []
    for s in segs:
        out += [f"{wd.word.strip()}[{a+wd.start:.2f}-{a+wd.end:.2f}]" for wd in s.words]
    print(f"[{a}-{b}] " + " ".join(out), flush=True)
