import cv2, numpy as np, subprocess, sys, json
path=sys.argv[1]; maxlag=float(sys.argv[2]) if len(sys.argv)>2 else 30
FPS=24; W,H=360,640
raw=subprocess.run(["ffmpeg","-v","error","-i",path,"-vf",f"fps={FPS},scale={W}:{H}","-pix_fmt","gray","-f","rawvideo","-"],capture_output=True,check=True).stdout
fr=np.frombuffer(raw,np.uint8).reshape(-1,H,W)
casc=cv2.CascadeClassifier(cv2.data.haarcascades+"haarcascade_frontalface_default.xml")
box=None; mot=[]; prev=None; det=0
for i,f in enumerate(fr):
    if i%2==0:
        d=casc.detectMultiScale(f,1.1,5,minSize=(70,70))
        if len(d):
            b=max(d,key=lambda r:r[2]*r[3]).astype(float); box=b if box is None else 0.6*box+0.4*b; det+=1
    if box is None: mot.append(0.0); continue
    x,y,w,h=box
    roi=cv2.resize(f[int(y+0.62*h):int(min(H,y+1.05*h)),int(x+0.25*w):int(x+0.75*w)],(64,32)).astype(np.float32)
    mot.append(0.0 if prev is None else float(np.mean(np.abs(roi-prev)))); prev=roi
mot=np.array(mot)
x=np.frombuffer(subprocess.run(["ffmpeg","-v","error","-i",path,"-vn","-ac","1","-ar","16000","-f","s16le","-"],capture_output=True,check=True).stdout,np.int16).astype(np.float32)/32768
hop=16000//FPS
env=np.log(np.array([np.sqrt(np.mean(x[k*hop:(k+1)*hop]**2)+1e-9) for k in range(len(x)//hop)]))
n=min(len(env),len(mot)); env=env[:n]; mot=mot[:n]
def sm(v,k): return np.convolve(v,np.ones(k)/k,mode="same")
def z(v): v=v-v.mean(); s=v.std(); return v/s if s>0 else v
print(f"frames {n}, face detections {det}/{n//2}")
L=int(maxlag*FPS); out={}
for k,label in [(3,"fine"),(12,"coarse")]:
    A=z(sm(env,k)); V=z(sm(mot,k)); res=[]
    for lag in range(-L,L+1):   # video at t vs audio at t+lag ; lag>0 => VIDEO EARLY by lag
        a=V[max(0,-lag):n-max(0,lag)]; b=A[max(0,lag):n-max(0,-lag)]
        res.append(float(np.mean(a*b)) if len(a)>FPS*20 else np.nan)
    res=np.array(res); o=np.argsort(-np.nan_to_num(res,nan=-9)); top=[]
    for t in o:
        if all(abs(t-u)>FPS for u in top): top.append(t)
        if len(top)==4: break
    print(f"{label:6s} " + "  ".join(f"lag {(t-L)/FPS:+6.2f}s r={res[t]:.3f}" for t in top) + f" | r@0={res[L]:.3f}, median {np.nanmedian(res):.3f}")
    out[label]=res.tolist()
json.dump(out,open(path+".lagscan.json","w"))
