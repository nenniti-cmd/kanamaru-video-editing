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

## 締切時の暫定一覧（Z の集約が開催から3時間を過ぎても見当たらないとき）
- M は新しい常駐処理を増やさず、**既存の定期巡回**で次の条件をすべて満たしたときに、C へ1回だけ合図を送る。
  1. その group_id について、M が C へ独立提案の合図を送ってから3時間以上たっている（開催時刻 = その送信時刻）
  2. タイトルに group_id と「集約」または「見比べ」を含むファイル（Z の正式集約）がない
  3. 同じ group_id で締切の合図をまだ送っていない（dedupe_id = `<group_id>-deadline`）
- 合図の本文：
```json
{"mode":"deadline_live","group_id":"…","dedupe_id":"<group_id>-deadline",
 "meeting_opened_at":"YYYY-MM-DD HH:MM JST","meeting_doc_id":"会議正本のID（あれば）"}
```
- C は Z の集約がまだないことを自分でも確かめてから、提出済みの回答を原文のまま並べた `C暫定一覧_<group_id>` を受付に作り、ロックし、本人に1回だけ通知する。要約・評価・順位付けはしない。Z の集約がすでにあれば何もしない（`z_done_skipped`）。
- 3時間の精度は、M の巡回間隔で決まる（1時間おきの巡回なら最大で約1時間遅れる）。実際の遅れは試験で測って記録する。
- 試験では `"mode":"deadline_test"` にする（一覧の名前に `TEST_` が付き、通知はしない）。

## 回答ファイルの名前の決まり（M・Z へのお願い）
暫定一覧を作るとき、C はタイトルで回答を探す。M・Z の回答と Z の集約は、次の名前に揃えてもらえると確実に見つけられる。
- 独立回答：`M独立提案_<group_id>_v1`、`C独立提案_<group_id>_v1`、`Z独立提案_<group_id>_v1`
- Z の正式集約：`Z集約_<group_id>`
- 揃っていない場合も、タイトルに group_id と「独立提案」または「独立回答」が入っていれば探せる。

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
