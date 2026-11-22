# C 無人編集の手順書（Mの編集タスクの合図で起動したセッション用）

- 対応タスク：P1-C-OPS-COMMAND-20261121-01（本人承認 2026-11-22「作って」）
- このセッションは、人間が見ていない。質問しない。本人への通知は「blocked」か「失敗」のときだけ1回。
- 作業の範囲は、正本タスクの approved_scope と本人の承認原文だけ。発行者の名前だけで承認とみなさない。
- 公開・再投稿・削除・認証変更・範囲外の編集・Mの生素材の上書きはしない。秘密の値（窓口のURL・キー、トークン）は、ログ・正本・出力に書かない。

## 0. 準備（約3〜6分）
1. ツール一式を取得：Driveで、タイトルが `C編集ツール一式_` で始まる最新の tar.gz を探し、download_file_content で取得して `/tmp/cedit/kit` に展開。以降のコマンドはそのフォルダで実行。
2. `bash tools/cedit/setup.sh`（ffmpeg・日本語フォント・Python部品の確認と導入）。
3. 以降の `tools/cedit/*.py` と `tools/verify/*.py` は、**`/tmp/cedit/venv/bin/python`** で実行する（システムの python3 には numpy などが入っていない）。`tools/make_n.py`・`tools/build_clip.py`・`tools/ass_bubbles.py`・`tools/drive_relay/drive_relay.py` はどちらでもよい。

## 1. 受領と検証
1. 合図の task_file_id の正本を読む。必須項目（task_id、source_request_id、group_id/clip_id、対象版、created_by、approval_evidence＝本人の決定原文、approved_scope、入力URL、depends_on、dedupe_key、status）と、承認の原文があるかを確認。
   - 不足 → 作業しない。完了フォルダに `REPORT_<task_id>_C_blocked.md` を作り、不足項目を書いて、本人に1回通知して終了。
2. 重複確認：完了フォルダに `REPORT_<task_id>_C` で始まるファイルがある、または正本（Googleドキュメントの場合）に「C結果」の記入がある → 何もせず終了。
3. 正本がGoogleドキュメントなら「C受領（日時）」を追記し、作業中フォルダへ移す。.md など編集できない形式なら、移動だけ行う（移動できなければそのまま）。

## 2. 下ごしらえ（素材ごと）
1. 素材の取得：入力URLのファイルIDで `curl -sSL -o raw.mp4 "https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t"`。HTMLが返ったら（リンク共有でない）blocked。MD5を記録。
2. `/tmp/cedit/venv/bin/python tools/cedit/analyze.py raw.mp4 a_<名前>` を実行（文字起こし2種・無音区間・同期・コマ一覧）。
3. `sync.txt` で同期を確認。r が 0.15 以上の区間で ±0.05秒を超えるずれがあれば、区間ごとに `voff` を指定する（`templates/README_layout_N.md` の「音と同期」）。迷う場合は作業を止めず、未確認事項として報告に書く。
4. `tile_XX.png` を画像として見て、他人のプロフィール画面・名前・子どもの顔などが映る秒を確認する。映る区間は使わないか、`"blur": true` にする。

## 3. 構成を決める（ここが品質の中心）
読むもの：正本の「本人コメント原文」「狙い」、`asr_large.txt`、`asr_kotoba.txt`、`quiet.txt`、コマ一覧。手本：`clips/` の内容ファイル（`kabe_C02.json`、`sushi_C02.json`、`beer_C02.json`、`n1119_A_C03.json`、`n1119_B_C01.json`）。
- 尺は30〜60秒。冒頭0〜3秒に、初見でも分かる一番強い一言（フック）を置く。最後は言い切り・笑いなど自然な終わりで切る（言葉の途中で切らない）。
- 区間の in/out は、`quiet.txt` の無音の中に置き、1/24秒単位に丸める（`round(t*24)/24`）。
- 字幕は本人の発言だけ。1行16文字まで・2行まで。聞き取りは2種の文字起こしで照合し、割れた語は `tools/verify/asr_short.py` で短く区切って聞き直す。確定できない語は報告に「未確認」と書く。強調は `[[語]]`（黄色）。
- 吹き出し（視聴者コメント）は、本人が読み上げたコメントか話の中身に関わるコメントだけ。ほめ言葉・簡単な同調（すごい・上手い・まじかよ・乾杯 等）は出さない。投稿者名は出さない。絵文字は省く。コメントの記録がなければ吹き出しは使わない。
- 他のライバー・視聴者・家族の名前は字幕に出さない。名前を言っている区間は使わない。投げ銭のお願い・金額の強調は入れない。順位や結果を断定しない。
- タイトル：`title_top`（黄色・小）＝フックや状況、`title_main`（白・大）＝本題。12文字前後。誇張しない。
- 内容ファイルを `clips/<task_id>_<名前>.json` として書く（形式は `tools/make_n.py` の説明どおり）。

## 4. 書き出しと検証
1. `/tmp/cedit/venv/bin/python tools/cedit/finish.py clips/<…>.json a_<名前>/src.mkv out/<名前>.mp4`
2. `<名前>.check.txt` を確認：デコードエラー0、−14 LUFS前後、安全範囲（上端252px以上・下端1497px以下）、音ズレ（0ms以外はカット境界・ぼかし・寄せの区間だけ）。`_sheet.png` を画像として見て、文字の重なり・はみ出し・映ってはいけないものがないか確認。
3. 問題があれば内容ファイルを直して書き出し直す（最大3回）。直らなければ未確認事項として報告。

## 5. 納品
1. 窓口のURLとキーを、本人のマイドライブの「C窓口URL_共有禁止.txt」（1CORMeUxfqpE91cqj94TX45q4OZuVdtx2）と「C窓口キー_共有禁止.txt」（14t8fwvhn6vEiKVEHiMDSzsZ7llYlx7sB）から読み、環境変数 `DRIVE_RELAY_URL` / `DRIVE_RELAY_KEY` にだけ入れる（表示・保存しない）。
2. `python3 -I tools/drive_relay/drive_relay.py upload out/<名前>.mp4 <正本が指定する納品先フォルダID> --name "<分かりやすい名前>_C版01_雛形Nv2.mp4"` → md5_match が true であることを確認。
3. 字幕 `out/<名前>_b.ass` も同じフォルダへ（Driveの create_file）。

## 6. 結果の記録（新しいREPORTは1件だけ）
完了フォルダに `REPORT_<task_id>_C_<JSTのYYYYMMDD-HHMM>.md` を作る（正本がGoogleドキュメントなら、そこへの追記でもよい）。書くこと：
- 素材（ファイルID・MD5）、各動画のURL・尺・MD5/サイズ、構成（素材の秒・元録画の秒・内容）、タイトル、字幕の照合方法
- 検証結果（check.txt の要点）、映り込み・名前の扱い、未確認事項（耳で聞いていないこと、聞き取りが割れた語、実機表示 等）
- 「無人セッションで作成。Cの作業セッションによる確認は未実施」の一文
最後に正本を完了フォルダへ移す（移せない形式ならそのまま）。本人への通知はしない（Mが納品を検知して本人に試写を案内する）。
