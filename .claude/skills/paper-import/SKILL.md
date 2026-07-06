---
name: paper-import
description: >
  arXiv URL / arXiv ID / PDFパスから論文を取り込み、主張（クレーム）を抽出し、
  既存クレームと照合して supports / contradicts / same_as / extends の関係を判定し、
  data/ に保存する。「この論文を取り込んで」「論文を登録して」「arXivのURLを読み込んで」
  「PDFからクレームを抽出して」など、論脈（paper_claims）への論文追加の依頼で必ず使う。
  arXiv URL が会話に出てきて取り込み文脈であれば明示依頼がなくても検討すること。
argument-hint: "<arXiv URL | arXiv ID | PDFパス> [topic-id] [タグ カンマ区切り（任意・省略時は対話で決定）]"
allowed-tools: Read, Write, Edit, Glob, Grep, AskUserQuestion, Bash(curl *), Bash(ls *), Bash(uv run *), Bash(git *), Bash(date *), Bash(pdftotext *), WebFetch
---

# paper-import

論文1本を取り込み、クレーム抽出 → 既存クレームとの照合 → 関係judgment → 保存 → 検証まで行うワークフロー。
作業ディレクトリは `/workspace/paper_claims/`。データスキーマの正は `app/models.py`（詳細表は `CLAUDE.md`）。

**IMPORTANT: 台帳への書き込みは直列に行うこと。** rel / ql の連番は「既存最大+1」方式のため、
複数の取り込みを並行実行すると ID が競合し relations.json / question_links.json で更新が失われる。
複数論文を並行処理する場合は、**論文ファイル（`data/papers/*.json`）の作成までを並行**とし、
関係・問いリンクの judgment と書き込みは全論文の抽出完了後に1プロセスでまとめて行う。

## 手順

### 1. 引数解析と重複チェック

- `$ARGUMENTS` から入力を判別する:
  - arXiv URL（`arxiv.org/abs/2201.11903v3` 等）/ 素の arXiv ID → バージョンサフィックス `vN` を落とし、`paper_id = arxiv-<ID>` とする
  - ローカル PDF パス → タイトルから英小文字ケバブケースの slug を作り `paper_id = pdf-<slug>` とする
- `data/papers/<paper_id>.json` が既に存在する場合は**中断してユーザーに報告**する（更新は明示指示があった場合のみ）。

**追補モード**: 「〜の観点でクレームを追補して」のように取り込み済み論文への追加を明示指示された場合は、
PDF を指定観点で再読し、既存クレームと重複しない新規クレームを続き連番で追加する
（quote / section 必須）。連番は**既存最大+1**。クレームを削除した場合の欠番は**再利用しない**
（関係・リンクが旧IDを参照していた履歴と混線するため）。追補後は手順6〜9（照合・問い判定・検証）を新規クレームに対して実施し、
`uv run python scripts/verify_quotes.py <paper_id>` も実行する。
初回取り込みの3〜10件はダイジェストであり、取りこぼしはこの追補と /paper-question の
問い駆動再読（手順2.5）で回復する二段構えの設計。

### 2. メタデータ取得（arXiv の場合）

```bash
curl -s "http://export.arxiv.org/api/query?id_list=<arxiv_id>"
```

Atom XML から title / authors / summary(abstract) / published(→year) を抽出する。
venue は arXiv API にはないため、本文中に "Accepted at ..." 等の記載があれば拾う（なければ空文字）。

### 3. PDF 取得と読解

```bash
curl -sL "https://arxiv.org/pdf/<arxiv_id>" -o data/pdfs/<paper_id>.pdf
```

PDF は `pdftotext`（poppler-utils）でテキスト化して読む。**この環境（Pi コンテナ）では Read ツールの PDF レンダリングが使えないことが確認済み**:

```bash
pdftotext data/pdfs/<paper_id>.pdf - | head -c 30000   # 分割して読む
```

`pdftotext` が無ければ `apt-get install -y poppler-utils` で導入する。
優先順: **Abstract / Introduction（貢献の列挙）→ 実験・結果（数値・条件）→ Conclusion / Limitations（限界の自己申告）**。付録は数値の裏取りが必要な場合のみ。行またぎのハイフネーションは復元して転記してよい。

### 4. クレーム抽出

1論文あたり **3〜10件**。以下の品質基準を厳守する:

- **「この論文自身が主張していること」のみ**。関連研究の紹介・引用文献の主張・自明な一般論は抽出しない
- 優先度: 主要な貢献主張 > 数値付きの実験結果 > 明確な限界・否定的知見（Limitations は係争点の種になるため重要）
- 各クレームに必須:
  - `summary_ja`: 条件を含む一文の和文サマリ（「〜の条件下で〜」まで書く。単なる「手法Xは有効」は不可）
  - `quote`: **原文そのままの引用**（言い換え禁止。PDF から正確に転記）
  - `context_ja`: **引用周辺の文脈の補足（2〜4文）**。引用の前後が何を論じているか・指示語（this/it/the task 等）が指すもの・成立の前提条件を再構成する。summary_ja の言い換えは不可。
    **quote 断片だけでは関係judgmentもユーザーの理解もミスリードされる**ため、文脈は抽出時（PDF全文が見えている唯一の機会）に固定する
  - `evidence.section`: 出典セクション番号（必須）。`pages` も可能な限り
  - `kind`: experimental（実験結果）/ theoretical（証明・理論）/ opinion（著者の見解・展望）
  - `confidence`: high（複数データセット・複数モデルで一貫）/ medium（単一設定のみ）/ low（予備的・n小）。判定理由を `confidence_note` に書く
- 数値結果は `evidence.metrics` に **baseline 込み**で記録する（改善幅が関係judgmentの材料になる）
- claim id は `<paper_id>-c01` から連番

### 4.5 課題の抽出

「この論文は何を解こうとしているのか」を **1〜2件**（最大3件）抽出し、paper JSON の `challenges` に入れる:

- **論文が自ら取り組むと明言している課題のみ**（一般的な背景説明・関連研究が挙げる課題は不可）。
  Abstract / Introduction の課題宣言文（"However, ..." "remains a challenge" "has not proved sufficient" 等）を探す
- `summary_ja` は「何が問題で、なぜ既存手法では足りないか」まで含む一文
- `quote`（原文そのまま・捏造厳禁）+ `section` 必須。verify_quotes の機械検証対象
- `context_ja` 必須（2〜4文）: 課題宣言の前後の議論・指示語の解決・課題のスコープを補足する（クレームと同じ原則）
- id は `<paper_id>-ch01` から連番、`problem_id` はこの時点では null

### 5. トピック決定

1. 引数で topic-id 指定があればそれを使う
2. なければ `data/topics.json` の既存トピックから内容に合うものを選ぶ
3. 合うものがなければ AskUserQuestion で新規トピック名を確認し、`topics.json` に追記する（id は英小文字ケバブケース）

### 5.5 タグ付け（照合スコープの決定 — **タグはユーザーが決める**）

論文の**2〜5個**の細粒度タグ（英語 kebab-case。例: `self-correction`, `chain-of-thought`, `math-reasoning`）は
**ユーザー自身が付与する**。タグは照合スコープを決めるレバーであり、ユーザーの分類眼を反映させる（設計上の決定）。
スキルが勝手に確定してはならない。

1. 引数・会話でタグが指定されていればそれを使う（確認不要）
2. 指定がなければ、既存語彙を取得した上で:

   ```bash
   uv run python -c "import json,glob; print(sorted({t for f in glob.glob('data/papers/*.json') for t in json.load(open(f)).get('tags',[])}))"
   ```

   論文内容に合う候補（**既存語彙からの再利用を優先**し、必要な場合のみ新規案を1〜2個混ぜる）を
   AskUserQuestion（multiSelect）で提示し、ユーザーに選択・追加してもらう
3. 表記ゆれ厳禁: 類義の既存タグがあるのに新規案を出さない（例: `self-refinement` を提案せず既存の `self-correction` を出す）

トピックが「棚」ならタグは「主題の索引」で、手順6の照合はタグが重なる論文のクレームに絞られる。

### 6. 既存クレームとの照合と関係judgment

```bash
uv run python scripts/build_index.py   # 照合前に必ずインデックスを最新化する（手動編集・追補後の鮮度ずれ対策）
grep '<topic-id>' data/claims_index.jsonl | grep -e '<tag1>' -e '<tag2>' -e '<tag3>'
```

で**同一トピック かつ タグが1つ以上重なる**既存クレーム候補を取得する（全く主題の異なる論文
まで照合するのは無駄なため、タグでスコープを絞る）。候補が0〜数件しかない場合のみ、
トピック全体の一行サマリを流し読みして明白な見落としがないか確認してよい。
サマリを読んで関連しそうな候補があれば、**その候補が属する論文ファイルだけ** Read して詳細を比較し、関係を判定する。
**インデックスの一行サマリだけで判定してはならない** — 必ず候補クレームの `quote`・`context_ja`・`evidence`
（実験条件・数値）まで読み、文脈を踏まえて判定すること（断片比較はミスリードを生む）:

| type | 判定基準 |
|------|---------|
| `supports` | 別の実験・データで同方向の結論を裏付けている（追試成功・一般化の確認） |
| `contradicts` | 同等の条件で逆方向の結果、または主張の一般性を崩す反例を示している |
| `same_as` | 実質的に同一の主張（from < to の辞書順に正規化すること） |
| `extends` | 主張を前提として、適用範囲の拡大・機構の説明・改良を加えている |

- `rationale_ja` に**判断根拠を必ず書く**。特に「実験条件のどこが同じでどこが違うか」を明記（contradicts では条件差こそが情報）
- **確信の持てない関係は作らない**（偽リンクより欠落を許容）。迷ったら relation の `confidence: low` ではなく「作らない」を選ぶ
- 関係の向きは「from が to を 支持/反証/拡張 する」= 新しい論文が from になるのが通常
- `contradicts` は論理的には対称（脈図では両端矢印で描画）。from は「対立を提起した側」の来歴として記録する。相互支持は supports を両方向に2本張ってよい

### 6.3 共有課題の照合（同じ課題に向き合う論文の紐付け）

```bash
grep '<topic-id>' data/challenges_index.jsonl | grep -e '<tag1>' -e '<tag2>'
```

で既存論文の課題とタグスコープ内で突き合わせ、**実質同じ課題に向き合っている**ものがあれば:

1. 既存側に `problem_id` があれば → 新論文の challenge をその problem に紐付ける提案
2. どちらも未紐付けなら → `data/problems.json` への新規 problem（`prob-NN`・name_ja）作成と双方の紐付けを提案

いずれも **AskUserQuestion でユーザーに確認してから**書き込む（課題の同一性判定はユーザーの分類眼に委ねる。
タグと同じ思想）。**確認を求める前に、比較対象の課題それぞれの summary_ja・quote・context_ja を
チャットで並べて提示すること**（断片だけ見せて選ばせるのはミスリードを生むため不可）。
承認されたら problems.json 追記 + 該当論文の `challenges[].problem_id` を更新。
確信が持てない・ユーザーが否認した場合は紐付けない。

### 6.5 オープンな問いへの回答性判定

`data/questions.json` を読み、**`status` が `open` の問い**のうちこの論文のトピックに合致するものについて、
新規クレームごとに「この問いに直接答えるか」を判定する（settled / archived の問いは判定しない —
問い数が増えても取り込みコストが膨らまないためのライフサイクル制御）。答えるものは
`data/question_links.json` に追記:

- `answer_ja` 必須（このクレームが問いに与える答え・一文）
- `stance` は判定型（closed）の問いのみ: `affirms` / `denies` / `qualifies`。記述型（open）では省略
- `rationale_ja` 必須。**確信の持てないリンクは作らない**（関係judgmentと同じ原則）
- id は `ql-NNNN`（既存最大+1）

### 7. 書き込み

1. `data/papers/<paper_id>.json` を新規作成（challenges / claims 込み。スキーマは CLAUDE.md の表・`tests/fixtures/data/` の実例に従う。`imported_at` は `TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00`）
2. 関係があれば `data/relations.json` に Edit で追記（`rel-NNNN` は既存最大値+1）
3. 問いへのリンクがあれば `data/question_links.json` に追記（手順6.5）
4. 共有課題の承認があれば `data/problems.json` 追記 + 該当論文の `problem_id` 更新（手順6.3）
5. 新規トピックは `data/topics.json` に追記

### 8. 検証（必須・スキップ不可）

```bash
uv run python scripts/build_index.py && uv run python scripts/validate.py
uv run python scripts/verify_quotes.py <paper_id>   # quote が PDF 本文に実在するかの機械検証
```

エラーが出たら自分で修正して再実行する。通るまで完了としない。
verify_quotes が NG のクレームは**捏造引用の疑い**なので、PDF を読み直して quote を原文どおりに直すこと（要約・言い換えは不可）。

### 9. コミット

```bash
git add data/ && git commit -m "import: <paper_id> <短いタイトル>（クレームN件・関係M件）"
```

### 10. 報告

- 論文タイトル・抽出クレーム数（kind別）・作成した関係数（type別、相手論文名つき）
- 問いへのリンクを作成した場合はその内訳（問い×answer_ja）
- グラフ URL: `http://<Piホスト>:8124/?topic=<topic-id>`
- 判断に迷って**作らなかった**関係・リンク候補があれば、その旨を一言添える（ユーザーが手で判断できるように）

## 品質基準（要約）

- クレームは「一望したとき研究状況が読める」粒度。多すぎ（些末な数値の羅列）も少なすぎ（貢献1件のみ）も不可
- quote と section のないクレームは保存しない（プロベナンス原則）
- 関係の過剰生成をしない。contradicts は条件差の分析なしに付けない
- validate.py が通らない状態で終了しない
