import sys, wave, numpy as np
from faster_whisper import WhisperModel
m = WhisperModel(sys.argv[1], device="cpu", compute_type="int8", cpu_threads=4)
for p in sys.argv[2:]:
    w=wave.open(p); x=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32)/32768
    for bs,temp in [(5,0.0),(1,0.4),(1,0.8)]:
        segs,_=m.transcribe(x,language="ja",beam_size=bs,temperature=temp,vad_filter=False,condition_on_previous_text=False)
        print(p, bs, temp, " / ".join(s.text for s in segs), flush=True)
