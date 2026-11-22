#!/usr/bin/env bash
# 無人の編集セッション用の準備。何度実行してもよい。
# usage: bash tools/cedit/setup.sh   （リポジトリ／ツール一式の最上位で実行）
set -euo pipefail
W=${CEDIT_WORK:-/tmp/cedit}
mkdir -p "$W"
command -v ffmpeg >/dev/null || { sudo -n apt-get update -qq && sudo -n apt-get install -y -qq ffmpeg; } || apt-get install -y -qq ffmpeg
if ! fc-list | grep -q "Noto Sans CJK JP"; then
  { apt-get update -qq && apt-get install -y -qq fonts-noto-cjk; } || { sudo -n apt-get update -qq && sudo -n apt-get install -y -qq fonts-noto-cjk; } || true
  fc-cache -f >/dev/null 2>&1 || true
fi
fc-list | grep -q "Noto Sans CJK JP" || { echo "ERROR: 日本語フォント（Noto Sans CJK JP）が入っていません"; exit 1; }
if [ ! -x "$W/venv/bin/python" ]; then
  python3 -m venv "$W/venv"
  "$W/venv/bin/pip" install -q --disable-pip-version-check faster-whisper "opencv-python-headless<5" numpy
fi
ffmpeg -version | head -1
fc-list | grep -c "Noto Sans CJK JP" | sed 's/^/Noto Sans CJK JP fonts: /'
"$W/venv/bin/python" -c "import faster_whisper, cv2, numpy; print('python libs ok')"
echo "setup done: $W"
