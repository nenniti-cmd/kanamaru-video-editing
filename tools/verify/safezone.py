import sys, subprocess, numpy as np
ass, dur = sys.argv[1], float(sys.argv[2])
W, H = 1080, 1920
f = ass.replace("\\", "/").replace(":", "\\:")
raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=black:s={W}x{H}:d={dur}:r=2",
                      "-vf", f"ass='{f}'", "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W)
top_min = H; bot_max = 0; right_max_low = 0; left_min_low = W
for i, g in enumerate(fr):
    m = g > 60
    up, low = m[:H // 2], m[H // 2:]
    if up.any():
        ys = np.where(up.any(1))[0]; top_min = min(top_min, ys[0])
    if low.any():
        ys = np.where(low.any(1))[0] + H // 2; bot_max = max(bot_max, ys[-1])
        xs = np.where(low.any(0))[0]; right_max_low = max(right_max_low, xs[-1]); left_min_low = min(left_min_low, xs[0])
print(f"frames {len(fr)} | top-most text y={top_min} (need >= {int(H*0.07)}) | bottom-most text y={bot_max} (need <= {int(H*0.78)}) "
      f"| lower-half text x range {left_min_low}..{right_max_low} (right buttons ~x>930)")
