---
name: paper-question
description: >
  論脈（paper_claims）に「問い」を登録し、既存クレームを遡及スキャンして
  答えとなる主張をマッピングする。「問いを立てたい」「この問いを登録して」
  「〜は〜か？という問いを追加して」「リサーチクエスチョンを管理したい」など、
  問いの登録・整理の依頼で必ず使う。以降の /paper-import では取り込みのたびに
  オープンな問いへの回答性が自動判定される。
argument-hint: "\"<問い>\" [topic-id]"
allowed-tools: Read, Write, Edit, Glob, Grep, AskUserQuestion, Bash(ls *), Bash(uv run *), Bash(git *), Bash(date *)
---

# paper-question

問いを登録し、既存クレームから答えを遡及マッピングするワークフロー。
作業ディレクトリは `/workspace/paper_claims/`。スキーマの正は `app/models.py`（詳細表は `CLAUDE.md`）。

## 問いの設計原則

- **type を判定する**: yes/no で答えられる問い = `closed`（判定型）、what/how/どの条件で = `open`（記述型）。曖昧なら AskUserQuestion で確認
- 問いは**クレームが直接答えられる粒度**にする。「LLMはすごいか」のような漠然とした問いは、登録前にユーザーと分割・具体化の相談をする
- topic は必須（1件以上）。既存 topic に合うものがなければユーザーに確認して `topics.json` へ追加

## 手順

### 1. 登録

- `data/questions.json` に追記。id は `q-NN`（既存最大+1、2桁）
- `created_at` は `TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00`

### 2. 遡及マッピング

```bash
grep '<topic-id>' data/claims_index.jsonl
```

で対象トピックの既存クレームを取得し、候補が属する論文ファイルを Read して詳細を確認の上、
**その問いに直接答えるクレームだけ**を `data/question_links.json` に追記する:

- id は `ql-NNNN`（既存最大+1）
- `answer_ja` 必須: 「このクレームがこの問いに与える答え」を一文で（判定型でも「外部FBなしでは修正できない」のように内容を書く。「はい/いいえ」だけは不可）
- `stance`: **判定型のみ** `affirms`（肯定の証拠）/ `denies`（否定の証拠）/ `qualifies`（条件付き・部分的）。記述型では省略（null）
- `rationale_ja` 必須: なぜこのクレームがこの問いに答えると判断したか
- **確信の持てないリンクは作らない**（偽リンクより欠落を許容）。周辺的に関連するだけのクレームはリンクしない

### 2.5 抽出漏れの回復（問い駆動の再読）

遡及マッピングは**抽出済みクレームしか見えない**。初回取り込みは3〜10件のダイジェストなので、
問いに答える内容が論文にあってもクレーム化されていない可能性がある。そこで:

1. 対象トピックの取り込み済み論文の title / abstract / notes を確認し、
   「クレームには答えが無いが、この論文は問いに答えていそう」なものを挙げる
2. 該当があればその論文の PDF（`data/pdfs/`）を**問いの観点で再読**し、
   答えとなる主張が見つかれば既存クレームの続き連番（`<paper_id>-c<次番>`）で追補する
   （quote / section 必須。追補後に `uv run python scripts/verify_quotes.py <paper_id>` を実行）
3. 追補したクレームを手順2と同様にリンクする

該当論文が多い場合は全再読せず、有望な2〜3本に絞ってユーザーに報告する。

### 3. 検証（必須・スキップ不可）

```bash
uv run python scripts/validate.py
```

エラーは自分で修正して再実行。stance⇔type の整合・参照整合性・重複が機械チェックされる。

### 4. コミットと報告

```bash
git add data/ && git commit -m "question: <q-NN> <問いの短縮形>（リンクN件）" && git push origin main
```

報告内容:
- 登録した問い（id・type）とリンク数（判定型なら stance 別の内訳）
- ダッシュボード URL: `http://<Piホスト>:8124/questions`、問いレンズ: `http://<Piホスト>:8124/?question=<q-NN>`
- リンクを見送った微妙な候補があればその旨（ユーザーが手で判断できるように）
