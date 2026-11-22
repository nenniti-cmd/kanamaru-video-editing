# windowed lag between mouth motion and audio envelope; lag>0 => video EARLY by lag seconds
import cv2, numpy as np, subprocess, sys, json
path=sys.argv[1]; lo,hi=float(sys.argv[2]),float(sys.argv[3]); wins=json.loads(sys.argv[4])
FPS=24; W,H=360,640
raw=subprocess.run(["ffmpeg","-v","error","-i",path,"-vf",f"scale={W}:{H}","-pix_fmt","gray","-f","rawvideo","-"],capture_output=True,check=True).stdout
fr=np.frombuffer(raw,np.uint8).reshape(-1,H,W)
casc=cv2.CascadeClassifier(cv2.data.haarcascades+"haarcascade_frontalface_default.xml")
box=None; mot=[]; prev=None
for i,f in enumerate(fr):
    if i%2==0:
        d=casc.detectMultiScale(f,1.1,5,minSize=(70,70))
        if len(d):
            b=max(d,key=lambda r:r[2]*r[3]).astype(float); box=b if box is None else 0.6*box+0.4*b
    if box is None: mot.append(0.0); continue
    x,y,w,h=box
    roi=cv2.resize(f[int(y+0.62*h):int(min(H,y+1.05*h)),int(x+0.25*w):int(x+0.75*w)],(64,32)).astype(np.float32)
    mot.append(0.0 if prev is None else float(np.mean(np.abs(roi-prev)))); prev=roi
mot=np.array(mot)
x=np.frombuffer(subprocess.run(["ffmpeg","-v","error","-i",path,"-vn","-ac","1","-ar","16000","-f","s16le","-"],capture_output=True,check=True).stdout,np.int16).astype(np.float32)/32768
hop=16000//FPS
env=np.log(np.array([np.sqrt(np.mean(x[k*hop:(k+1)*hop]**2)+1e-9) for k in range(len(x)//hop)]))
def sm(v,k): return np.convolve(v,np.ones(k)/k,mode="same")
def z(v): v=v-v.mean(); s=v.std(); return v/s if s>0 else v
A=sm(env,3); V=sm(mot,3)
for a0,a1 in wins:   # audio-time window (seconds in file)
    i0,i1=int(a0*FPS),int(a1*FPS); best=[]
    for lagf in range(int(lo*FPS),int(hi*FPS)+1):
        j0,j1=i0-lagf,i1-lagf          # video frames showing that audio = earlier in file
        if j0<0: continue
        c=float(np.mean(z(A[i0:i1])*z(V[j0:j1]))); best.append((c,lagf/FPS))
    best.sort(reverse=True)
    print(f"audio {a0:6.1f}-{a1:6.1f}: best lag {best[0][1]:.3f}s (r={best[0][0]:.2f})  2nd {best[1][1]:.3f} ({best[1][0]:.2f})  top5 {[b[1] for b in best[:5]]}")
