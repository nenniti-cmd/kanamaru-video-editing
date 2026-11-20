#!/usr/bin/env python3
"""Post-process an ASS file: turn Label / End events into rounded "bubbles".
usage: ass_bubbles.py IN.ass OUT.ass [--y 505] [--end-y 520]
Label events become: a pale rounded pill (drawing) + a small pink "コメント" tag + the comment text.
End events become a small pill with the text. Width is estimated from the text length (CJK ~1em)."""
import re, sys
src, dst = sys.argv[1], sys.argv[2]
LY = int(sys.argv[sys.argv.index("--y") + 1]) if "--y" in sys.argv else 505
EY = int(sys.argv[sys.argv.index("--end-y") + 1]) if "--end-y" in sys.argv else 520
FS = 36

def pill(cx, cy, w, h, color_bgr, alpha="10"):
    r = h // 2
    x0, y0 = cx - w // 2, cy - h // 2
    k = int(r * 0.55)
    path = (f"m {r} 0 l {w - r} 0 b {w - r + k} 0 {w} {r - k} {w} {r} b {w} {r + k} {w - r + k} {h} {w - r} {h} "
            f"l {r} {h} b {r - k} {h} 0 {r + k} 0 {r} b 0 {r - k} {r - k} 0 {r} 0")
    return rf"{{\an7\pos({x0},{y0})\bord0\shad0\1c&H{color_bgr}&\1a&H{alpha}&\p1}}{path}{{\p0}}"

def text_width(s, fs):
    s = re.sub(r"\{[^}]*\}", "", s)
    return int(sum(fs if ord(c) > 0x2E7F else fs * 0.55 for c in s))

out = []
for line in open(src, encoding="utf-8"):
    m = re.match(r"Dialogue: (\d+),([^,]*),([^,]*),(Label|End),([^,]*),(\d+),(\d+),(\d+),([^,]*),(.*)$", line.rstrip("\n"))
    if not m:
        out.append(line.rstrip("\n")); continue
    layer, a, b, style, name, ml, mr, mv, eff, text = m.groups()
    if style == "Label":
        body = text.replace("コメント「", "「", 1) if text.startswith("コメント「") else text
        tag = "コメント"
        if body == "視聴者コメントを読み上げ":
            tag, body = "コメント読み上げ", ""
        tw = text_width(tag, FS - 8) + (text_width(body, FS) + 18 if body else 0)
        w, h, cy = tw + 64, 64, LY
        out.append(f"Dialogue: 6,{a},{b},Label,,0,0,0,,{pill(540, cy, w, h, 'EAE0F6', '10')}")
        txt = (rf"{{\an5\pos(540,{cy})\bord0\shad0}}{{\fs{FS-8}\c&H9A5ED8&}}{tag}" +
               (rf"{{\fs{FS}\c&H312838&}}  {body}" if body else ""))
        out.append(f"Dialogue: 7,{a},{b},Label,,0,0,0,,{txt}")
    else:  # End
        w, h = text_width(text, 34) + 60, 56
        out.append(f"Dialogue: 6,{a},{b},End,,0,0,0,,{pill(540, EY, w, h, 'EAE0F6', '10')}")
        out.append(f"Dialogue: 7,{a},{b},End,,0,0,0,,{{\\an5\\pos(540,{EY})\\bord0\\shad0}}{text}")
open(dst, "w", encoding="utf-8").write("\n".join(out) + "\n")
print("bubbles written:", dst)
