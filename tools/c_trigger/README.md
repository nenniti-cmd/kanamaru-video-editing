# C 配信完成トリガー（M → C の自動起動）

対応タスク：P1-C-CLIP-CANDIDATE-TRIGGER-20261120-01

## 構成
- Claude Code のスケジュールタスク「C 配信完成トリガー受信・独立提案」（`trig_01JYonfMiJQNAQ4rUvuJXvZW`）
  - 定時実行なし。合図があったときだけ起動する
  - 起動のたびに新しいクラウドセッションを作る（環境：kanamaru-video-editing）
  - 指示文：`routine_prompt.md`（このフォルダ）
- 外部からの起動：Anthropic のタスク起動API（ベータ）
  - `POST https://api.anthropic.com/v1/claude_code/routines/<trigger_id>/fire`
  - ヘッダー：`Authorization: Bearer <token>`、`anthropic-beta: experimental-cc-routine-2026-04-01`、`anthropic-version: 2023-06-01`、`Content-Type: application/json`
  - 本文：`{"text": "<下のJSONを文字列にしたもの>"}`
  - 応答：`{"type":"routine_fire","claude_code_session_id":"…","claude_code_session_url":"…"}` → Mはこのセッションのidを受領の証拠として記録する
- トークンとtrigger_idは、本人のマイドライブ直下の非公開ファイル「C起動トークン_共有禁止.txt」にだけ置く（共通文書、タスク、チャットに書かない）。

## M が送る本文（text の中身）
```json
{"mode":"live","group_id":"recording-group-YYYYMMDD-HHMMSS","dedupe_id":"<group_id>-v1",
 "policy_version":"Ver.N (YYYY-MM-DD)","m_submitted":true,
 "sessions":[{"recording_id":"…","folder_id":"…","transcript_id":"…","summary_id":"…"}],
 "gaps":"欠落の説明（なければ none）"}
```
- 試験では `"mode":"test"` にする（成果物の名前に `TEST_` が付き、本番の回答と混ざらない）。

## C の出力（Z が拾うもの）
- 回答：タスク置き場／受付の Googleドキュメント `C独立提案_<group_id>_v1`（試験は `TEST_` 付き）。提出後に Drive のロック（readOnly）をかける。
  - 冒頭の判定キー：group_id / candidate_set_version / submitted_at / policy_version / trigger_dedupe_id / mode / M・Z未閲覧の宣言 / 読んだ資料ID / 対応タスクID
- ログ：タスク置き場／作業中の `C起動ログ_<group_id>_<時刻>`（result = submitted / duplicate_skipped / blocked / failed）
- Z の探し方：Drive でタイトルに `C独立提案_<group_id>` を含むファイルを検索する。

## 二重防止
- C は起動するたびに、同じタイトルの回答があるかをタイトルだけで確認する。あれば何も作らずに `duplicate_skipped` のログを残して終了する。
- M も、送信済みの dedupe_id を記録して再送しない（再送しても C 側で止まる）。

## 失敗時
- 資料が読めない → `blocked`（回答は作らない）。M が資料を直したあと、同じ本文で再送すればよい。
- 起動 API が失敗（応答が routine_fire でない） → M は未達として記録し、再送は最大3回まで（間隔15分）。それでも失敗なら本人に報告する。
- Drive コネクタのない状態で起動した → `failed / no_drive_connector`（何も作らない）。

## 費用
- 追加の契約や課金はない。起動1回ごとに、本人の Claude プランの使用枠を消費する（クラウドの実行環境は別料金なし）。
- 起動APIは1時間あたり100回までなどの上限がある（ベータ版のため仕様が変わる可能性あり）。
