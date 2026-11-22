#!/usr/bin/env python3
"""無人の編集セッション用：内容ファイル（clips/*.json の形式）から雛形N v2で書き出し、検証まで行う。

usage: python3 tools/cedit/finish.py CONTENT.json SRC.mkv OUT.mp4
出力: OUT.mp4、OUT_b.ass（字幕）、OUT.check.txt（検証結果）、OUT_sheet.png（8コマの一覧）
検証: フレーム数・デコードエラー・音量（LUFS）・0.6秒以上の映像停止・0.7秒以上の無音・
      文字の安全範囲（上端252px以上／下端1497px以下／右930px付近にかからない）・
      音ズレ（カード部分を元素材と照合。0ms以外の区間はカットをまたぐ区間・ぼかし・寄せの区間だけのはず）
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
W = os.environ.get("CEDIT_WORK", "/tmp/cedit")
PY = os.path.join(W, "venv", "bin", "python")


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()


def main():
    content, src, out = sys.argv[1:4]
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_n.py"), content, src, out], check=True)
    base = os.path.splitext(out)[0]
    T = json.load(open(os.path.join(ROOT, "templates", "layout_N.json"), encoding="utf-8"))
    c = T["card"]
    lines = []
    dur = float(sh(f"ffprobe -v error -show_entries format=duration -of csv=p=0 '{out}'"))
    lines.append(f"duration {dur:.2f}s")
    lines.append("frames " + sh(f"ffprobe -v error -select_streams v -count_packets -show_entries stream=nb_read_packets -of csv=p=0 '{out}'"))
    lines.append("decode_errors " + sh(f"ffmpeg -v error -i '{out}' -f null - 2>&1 | wc -l"))
    lines.append("loudness " + sh(f"ffmpeg -hide_banner -i '{out}' -af ebur128=peak=true -f null - 2>&1 | grep -E '^\\s+(I|Peak):' | tr -s ' ' | tr '\\n' ' '"))
    lines.append("freezes>=0.6s " + sh(f"ffmpeg -hide_banner -i '{out}' -vf freezedetect=n=0.003:d=0.6 -map 0:v -f null - 2>&1 | grep -E 'freeze_(start|end)' | sed 's/.*freezedetect[^]]*] //' | tr '\\n' ' '"))
    lines.append("silences>=0.7s " + sh(f"ffmpeg -hide_banner -i '{out}' -af silencedetect=n=-40dB:d=0.7 -f null - 2>&1 | grep -E 'silence_(start|end)' | sed 's/.*silencedetect[^]]*] //' | tr '\\n' ' '"))
    sh(f"grep -v ',Frame,' '{base}_b.ass' > '{base}_text.ass'")
    lines.append("safezone " + sh(f"'{PY}' -I '{ROOT}/tools/verify/safezone.py' '{base}_text.ass' {dur:.1f} | tail -1") +
                 "  ※v2の基準：上端>=252（TikTok）、下端<=1497")
    # sync against source (card area)
    sh(f"ffmpeg -v error -y -i '{out}' -vf 'crop={c['w']}:{c['h']}:{c['x']}:{c['y']},scale=720:1040' -c:v libx264 -preset veryfast -crf 16 -c:a copy '{base}_card.mp4'")
    sh(f"ffmpeg -v error -y -i '{src}' -vf 'crop=720:1040:0:0' -c:v libx264 -preset veryfast -crf 16 -c:a aac -b:a 192k '{base}_rawcrop.mp4'")
    al = sh(f"'{PY}' -I '{ROOT}/tools/verify/srcalign.py' '{base}_rawcrop.mp4' '{base}_card.mp4' --band 0.30 0.85 --json '{base}_align.json'")
    al_lines = al.splitlines()
    lines.append("sync " + (al_lines[0] if al_lines else "(no output)"))
    bad = [l for l in al_lines[1:] if "A-V=   +0.0ms" not in l and "A-V=   -0.0ms" not in l]
    lines.append(f"sync_nonzero_windows {len(bad)}（カットをまたぐ区間・ぼかし・寄せの区間なら問題なし）")
    lines += ["  " + l for l in bad[:30]]
    # contact sheet
    ts = [round(dur * (i + 0.5) / 8, 2) for i in range(8)]
    for i, t in enumerate(ts):
        sh(f"ffmpeg -v error -y -ss {t} -i '{out}' -frames:v 1 -vf scale=270:480 '{base}_s{i}.png'")
    sh("ffmpeg -v error -y " + " ".join(f"-i '{base}_s{i}.png'" for i in range(8)) + f" -filter_complex hstack=8 '{base}_sheet.png'")
    lines.append(f"sheet {base}_sheet.png （秒: {ts}）")
    lines.append("audio_md5 " + sh(f"ffmpeg -v error -i '{out}' -vn -f s16le - | md5sum | cut -c1-12"))
    lines.append("file_md5 " + sh(f"md5sum '{out}' | cut -c1-32") + "  size " + str(os.path.getsize(out)))
    txt = "\n".join(lines)
    open(base + ".check.txt", "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
