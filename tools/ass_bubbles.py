#!/usr/bin/env python3
"""Post-process an ASS file: turn Label / End events into rounded "bubbles".
usage: ass_bubbles.py IN.ass OUT.ass [--y 505] [--end-y 520]
Label events become: a pale rounded pill (drawing) + a small pink "コメント" tag + the comment text.
End events become a small pill with the text. Width is estimated from the text length (CJK ~1em)."""
import re, sys
src, dst = sys.argv[1], sys.argv[2]
LY = int(sys.argv[sys.argv.index("--y") + 1]) if "--y" in sys.argv else 505
EY = int(sys.argv[sys.argv.index("--end-y") + 1]) if "--end-y" in sys.argv else 520
FS = 50
SLIDE = "--slide-left" in sys.argv
SUBBOX = "--sub-box" in sys.argv     # one rounded cushion behind all lines of a subtitle (instead of per-line boxes)
SUB_FS = int(sys.argv[sys.argv.index("--sub-fs") + 1]) if "--sub-fs" in sys.argv else 64
SUB_BOTTOM = int(sys.argv[sys.argv.index("--sub-bottom") + 1]) if "--sub-bottom" in sys.argv else 1470   # bubble enters from off-screen left and overlaps the card
SX0 = int(sys.argv[sys.argv.index("--x0") + 1]) if "--x0" in sys.argv else 40

def pill(cx, cy, w, h, color_bgr, alpha="10"):
    r = h // 2
    x0, y0 = cx - w // 2, cy - h // 2
    k = int(r * 0.55)
    path = (f"m {r} 0 l {w - r} 0 b {w - r + k} 0 {w} {r - k} {w} {r} b {w} {r + k} {w - r + k} {h} {w - r} {h} "
            f"l {r} {h} b {r - k} {h} 0 {r + k} 0 {r} b 0 {r - k} {r - k} 0 {r} 0")
    return rf"{{\an7\pos({x0},{y0})\bord0\shad0\1c&H{color_bgr}&\1a&H{alpha}&\p1}}{path}{{\p0}}"

def text_width(s, fs):
    s = re.sub(r"\{[^}]*\}", "", s)
    em = fs / 1.448          # Noto Sans CJK: ASS font size = ascent+descent = 1.448 em (measured)
    return int(sum(em if ord(c) > 0x2E7F else em * 0.55 for c in s))

out = []
for line in open(src, encoding="utf-8"):
    ms = re.match(r"Dialogue: (\d+),([^,]*),([^,]*),Sub,([^,]*),(\d+),(\d+),(\d+),([^,]*),(.*)$", line.rstrip("\n"))
    if SUBBOX and ms:
        a, b, text = ms.group(2), ms.group(3), ms.group(9)
        lines = text.split("\\N")
        # measured: line pitch = font size; glyph ink height ~0.66*fs; ink bottom = SUB_BOTTOM
        w = max(text_width(l, SUB_FS) for l in lines) + 64
        ink_h = int(SUB_FS * 0.66) + SUB_FS * (len(lines) - 1)
        pad = 22
        h = ink_h + 2 * pad
        x0, y0 = 540 - w // 2, SUB_BOTTOM - ink_h - pad
        r, k = 22, 12
        path = (f"m {r} 0 l {w - r} 0 b {w - r + k} 0 {w} {r - k} {w} {r} l {w} {h - r} b {w} {h - r + k} {w - r + k} {h} {w - r} {h} "
                f"l {r} {h} b {r - k} {h} 0 {h - r + k} 0 {h - r} l 0 {r} b 0 {r - k} {r - k} 0 {r} 0")
        out.append(f"Dialogue: 0,{a},{b},Sub,,0,0,0,,{{\\an7\\pos({x0},{y0})\\bord0\\shad0\\1c&H1E1418&\\1a&H50&\\p1}}{path}{{\\p0}}")
        out.append(line.rstrip("\n").replace("Dialogue: 0,", "Dialogue: 1,", 1))
        continue
    m = re.match(r"Dialogue: (\d+),([^,]*),([^,]*),(Label|End),([^,]*),(\d+),(\d+),(\d+),([^,]*),(.*)$", line.rstrip("\n"))
    if not m:
        out.append(line.rstrip("\n")); continue
    layer, a, b, style, name, ml, mr, mv, eff, text = m.groups()
    if style == "Label" and SLIDE:
        body = text.replace("コメント「", "「", 1) if text.startswith("コメント「") else text
        tag = "コメント"
        if body == "視聴者コメントを読み上げ":
            tag, body = "コメント読み上げ", ""
        fs = FS + 4
        tw = text_width(tag, fs - 10) + (text_width(body, fs) + 20 if body else 0)
        h = 84; w = tw + 110; cy = LY; x0 = SX0; y0 = cy - h // 2
        r = h // 2; k = int(r * 0.55)
        path = (f"m {r} 0 l {w - r} 0 b {w - r + k} 0 {w} {r - k} {w} {r} b {w} {r + k} {w - r + k} {h} {w - r} {h} "
                f"l {r} {h} b {r - k} {h} 0 {r + k} 0 {r} b 0 {r - k} {r - k} 0 {r} 0")
        mv = lambda x, y: rf"\move({x - w - 80},{y},{x},{y},0,250)"
        # soft shadow, pill, avatar dot, text
        out.append(f"Dialogue: 5,{a},{b},Label,,0,0,0,,{{\\an7{mv(x0 + 6, y0 + 10)}\\bord0\\shad0\\blur6\\1c&H000000&\\1a&H90&\\p1}}{path}{{\\p0}}")
        out.append(f"Dialogue: 6,{a},{b},Label,,0,0,0,,{{\\an7{mv(x0, y0)}\\bord0\\shad0\\1c&HEFE6F8&\\1a&H08&\\p1}}{path}{{\\p0}}")
        d = 46; dot = f"m {d//2} 0 b {d} 0 {d} {d} {d//2} {d} b 0 {d} 0 0 {d//2} 0"
        out.append(f"Dialogue: 7,{a},{b},Label,,0,0,0,,{{\\an7{mv(x0 + 16, cy - d // 2)}\\bord0\\shad0\\1c&HA67BE0&\\p1}}{dot}{{\\p0}}")
        txt = (rf"{{\an4{mv(x0 + 76, cy)}\bord0\shad0}}{{\fs{fs-10}\c&H9A5ED8&}}{tag}" +
               (rf"{{\fs{fs}\c&H312838&}}  {body}" if body else ""))
        out.append(f"Dialogue: 8,{a},{b},Label,,0,0,0,,{txt}")
        continue
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
