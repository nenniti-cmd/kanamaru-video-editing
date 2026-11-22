# Mが編集タスクを起票したときの、Cへの合図（案A）

- 対応タスク：P1-C-OPS-COMMAND-20261121-01（本人承認 2026-11-21「案aでおけです」）
- 合図先：スケジュールタスク「C 編集タスク受信（Mの正式起票→この作業セッション）」
  - trigger_id：`trig_01Jn3NbyA96L9e2VW1N2nwkH`
  - 2026-11-22 実測：APIで送った合図は、毎回**新しいセッション**を立ち上げる（Cの作業セッションには届かない）。
    新しいセッションには Drive 接続・編集の道具がなく、Cの作業セッションへ連絡する手段（fire_trigger・SendMessage）も使えないことを試験で確認した。
  - 現在の動き（暫定）：合図を受けた新しいセッションが、**本人のスマホにお知らせを1回送る**（「Cの作業チャットで『<task_id> はじめて』と送ってください」）。
    本人のひと言で、Cの作業セッションが正本を検証して編集する。Mの送り方・トークンは変更なし。
  - 完全自動にするには、合図を受けた新しいセッション自身が編集まで行う方式（Drive接続の追加、道具一式の準備）が必要。本人の判断待ち。
- トークン：本人のマイドライブ直下の非公開文書「C編集起動トークン_共有禁止」（1行目 trigger_id、2行目 トークン）。値はタスク・ログ・チャットに書かない。

## いつ送るか
本人の承認済みの編集・修正について、M が受付に正本タスクを1件作った直後に1回だけ。正本には次をそろえる：
task_id、source_request_id、group_id / clip_id、対象版、created_by、approval_evidence（本人の決定原文とURL）、approved_scope、入力URL、depends_on、dedupe_key、status。

## 送り方
```
POST https://api.anthropic.com/v1/claude_code/routines/trig_01Jn3NbyA96L9e2VW1N2nwkH/fire
Authorization: Bearer <C編集起動トークン>
anthropic-version: 2023-06-01
anthropic-beta: experimental-cc-routine-2026-04-01
Content-Type: application/json

{"text": "{\"mode\":\"edit\",\"task_id\":\"P1-…\",\"task_file_id\":\"<受付の正本のDrive ID>\",\"dedupe_key\":\"<正本と同じ値>\"}"}
```
- 本文に指示文を書かない（C は ID だけを使い、作業の範囲は正本の承認証跡で判断する）。
- 同じ dedupe_key で再送しても、C は二重に作業しない。失敗時の再送は最大3回・15分間隔。

## C が返すもの
- 正本タスクを 受付 → 作業中 → 完了 へ移し、同じ正本に「C受領」「結果（動画URL・MD5/サイズ・検証・未確認事項）」を追記する。新しい REPORT ファイルは作らない。
- 項目不足・承認証跡なしのときは作業せず、正本に「C：blocked（不足項目）」と追記する。
- 公開・再投稿・削除・範囲外の編集はしない。

## 注意
- この合図は C の作業セッションに届く。セッションのコンテナが作り直された直後は、道具の準備に数分かかることがある。
- 独立提案・締切の合図（trig_01JYonfMiJQNAQ4rUvuJXvZW、README.md）とは別物。会議の開始だけでは編集の合図を送らない。

## 疎通確認（ping）
- 本文 `{"mode":"ping","task_id":"PING-<日時>","task_file_id":"","dedupe_key":"ping-<日時>"}` を送ると、中継→作業セッションまで届いたかを確認できる。
  作業セッションは何も作らず、C移行タスク（P1-C-OPS-COMMAND-20261121-01）の正本に受信時刻を1行だけ追記する。
