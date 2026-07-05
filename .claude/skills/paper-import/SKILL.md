---
name: paper-import
description: >
  arXiv URL / arXiv ID / PDFパスから論文を取り込み、主張（クレーム）を抽出し、
  既存クレームと照合して supports / contradicts / same_as / extends の関係を判定し、
  data/ に保存する。「この論文を取り込んで」「論文を登録して」「arXivのURLを読み込んで」
  「PDFからクレームを抽出して」など、論脈（paper_claims）への論文追加の依頼で必ず使う。
  arXiv URL が会話に出てきて取り込み文脈であれば明示依頼がなくても検討すること。
argument-hint: "<arXiv URL | arXiv ID | PDFパス> [topic-id]"
allowed-tools: Read, Write, Edit, Glob, Grep, AskUserQuestion, Bash(curl *), Bash(ls *), Bash(uv run *), Bash(git *), Bash(date *), Bash(pdftotext *), WebFetch
---

# paper-import

論文1本を取り込み、クレーム抽出 → 既存クレームとの照合 → 関係judgment → 保存 → 検証まで行うワークフロー。
作業ディレクトリは `/workspace/paper_claims/`。データスキーマの正は `app/models.py`（詳細表は `CLAUDE.md`）。

## 手順

### 1. 引数解析と重複チェック

- `$ARGUMENTS` から入力を判別する:
  - arXiv URL（`arxiv.org/abs/2201.11903v3` 等）/ 素の arXiv ID → バージョンサフィックス `vN` を落とし、`paper_id = arxiv-<ID>` とする
  - ローカル PDF パス → タイトルから英小文字ケバブケースの slug を作り `paper_id = pdf-<slug>` とする
- `data/papers/<paper_id>.json` が既に存在する場合は**中断してユーザーに報告**する（更新は明示指示があった場合のみ）。

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
  - `evidence.section`: 出典セクション番号（必須）。`pages` も可能な限り
  - `kind`: experimental（実験結果）/ theoretical（証明・理論）/ opinion（著者の見解・展望）
  - `confidence`: high（複数データセット・複数モデルで一貫）/ medium（単一設定のみ）/ low（予備的・n小）。判定理由を `confidence_note` に書く
- 数値結果は `evidence.metrics` に **baseline 込み**で記録する（改善幅が関係judgmentの材料になる）
- claim id は `<paper_id>-c01` から連番

### 5. トピック決定

1. 引数で topic-id 指定があればそれを使う
2. なければ `data/topics.json` の既存トピックから内容に合うものを選ぶ
3. 合うものがなければ AskUserQuestion で新規トピック名を確認し、`topics.json` に追記する（id は英小文字ケバブケース）

### 6. 既存クレームとの照合と関係judgment

```bash
grep '<topic-id>' data/claims_index.jsonl
```

で同一トピックの既存クレーム候補を取得（インデックスが無い/古い場合は先に `uv run python scripts/build_index.py`）。
サマリを読んで関連しそうな候補があれば、**その候補が属する論文ファイルだけ** Read して詳細（実験条件・数値）を比較し、関係を判定する:

| type | 判定基準 |
|------|---------|
| `supports` | 別の実験・データで同方向の結論を裏付けている（追試成功・一般化の確認） |
| `contradicts` | 同等の条件で逆方向の結果、または主張の一般性を崩す反例を示している |
| `same_as` | 実質的に同一の主張（from < to の辞書順に正規化すること） |
| `extends` | 主張を前提として、適用範囲の拡大・機構の説明・改良を加えている |

- `rationale_ja` に**判断根拠を必ず書く**。特に「実験条件のどこが同じでどこが違うか」を明記（contradicts では条件差こそが情報）
- **確信の持てない関係は作らない**（偽リンクより欠落を許容）。迷ったら relation の `confidence: low` ではなく「作らない」を選ぶ
- 関係の向きは「from が to を 支持/反証/拡張 する」= 新しい論文が from になるのが通常

### 7. 書き込み

1. `data/papers/<paper_id>.json` を新規作成（スキーマは CLAUDE.md の表・`tests/fixtures/data/` の実例に従う。`imported_at` は `TZ=Asia/Tokyo date +%Y-%m-%dT%H:%M:%S+09:00`）
2. 関係があれば `data/relations.json` に Edit で追記（`rel-NNNN` は既存最大値+1）
3. 新規トピックは `data/topics.json` に追記

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
- グラフ URL: `http://<Piホスト>:8124/?topic=<topic-id>`
- 判断に迷って**作らなかった**関係候補があれば、その旨を一言添える（ユーザーが手で判断できるように）

## 品質基準（要約）

- クレームは「一望したとき研究状況が読める」粒度。多すぎ（些末な数値の羅列）も少なすぎ（貢献1件のみ）も不可
- quote と section のないクレームは保存しない（プロベナンス原則）
- 関係の過剰生成をしない。contradicts は条件差の分析なしに付けない
- validate.py が通らない状態で終了しない
