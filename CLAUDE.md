# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要

**論脈 RONMYAKU** — 論文の主張（クレーム）を複数論文横断で管理・紐付け・グラフ可視化するアプリ。
論文（主に arXiv）からクレームを抽出し、根拠・実験条件と紐づけて保存。論文間で 支持 / 反証 / 同一 / 拡張 の関係を張り、トピックごとの研究状況（コンセンサス・係争点）を一望する。

- **取り込み（抽出・照合・紐付け）は Claude Code の `/paper-import` スキルが行う**（`.claude/skills/paper-import/SKILL.md`）
- **問いの登録・遡及マッピングは `/paper-question`**（`.claude/skills/paper-question/SKILL.md`）。以降の取り込みで答えとなる主張が自動でリンクされる
- **Web UI は閲覧専用**（FastAPI + JSONファイル + Cytoscape.js、ビルドレス）。書き込みエンドポイントは持たない
- Raspberry Pi 上で常時稼働、認証なし LAN 利用（ポート **8124**）。iPhone ファースト

このリポジトリのルートが作業対象ディレクトリ。アプリ本体は `app/`、データは `data/`。

## よく使うコマンド

実行は **uv**。

| 目的 | コマンド |
|------|----------|
| 依存導入 | `uv sync` |
| 起動 | `uv run uvicorn app.main:app --host 0.0.0.0 --port 8124` |
| データ検証 | `uv run python scripts/validate.py` |
| インデックス再生成 | `uv run python scripts/build_index.py` |
| lint / format | `uv run ruff check .` / `uv run ruff format .` |
| 型チェック | `uv run mypy app` |
| テスト | `uv run pytest -q` |
| 一括チェック | `bash scripts/check.sh` |

データ保存先は環境変数 `PAPER_CLAIMS_DATA_DIR` で上書きできる（テスト分離）。

## アーキテクチャ

- **`app/models.py`（単一の真実）** — Paper / Claim / Evidence / Relation / Topic の Pydantic モデルと全 enum（`CLAIM_KINDS` / `RELATION_TYPES` / `CONFIDENCES`）・日本語ラベル。**選択肢を変えるときはここを直す**（validate.py・API・テンプレ・スキルが全部ここに従う）
- **`app/storage.py`** — 読み取り専用ローダ。mtime シグネチャのキャッシュを持ち、Claude Code が外部からファイルを編集してもサーバ再起動なしで反映される。壊れたファイルは読み飛ばして `errors` に記録
- **`app/graph.py`** — papers + relations → Cytoscape.js elements 変換。ノード色は paper id のハッシュ色相
- **`app/main.py`** — 全ルート（read-only GET のみ）。API 6本 + 画面4枚（`/` 脈図, `/papers`, `/papers/{id}`, `/claims/{id}`）
- **`scripts/validate.py`** — スキーマ + 参照整合性チェック（スキルの手順8と CI が使う）。エラー時 exit 1
- フロントは Jinja2 + 素の JS（`app/static/app.js`）。Cytoscape.js は `app/static/vendor/` にベンダリング済み（CDN 非依存）

## 規約

- 型ヒント必須 + 日本語 Google スタイル docstring 必須。ruff（`pydocstyle=google`）+ mypy（`disallow_untyped_defs`）
- **Web アプリに書き込み機能を足さない**（設計上の決定）。データ変更は必ず `/paper-import` かユーザーの手編集 + validate.py
- データ変更後は必ず `scripts/build_index.py` → `scripts/validate.py` を実行する
- **台帳（relations / question_links）への書き込みは直列に行う**。連番が「既存最大+1」方式のため並行書き込みは ID 競合する（並行取り込みは論文ファイル作成までに留める）

## データの削除・修正の手順

- クレーム・論文を削除すると relations / question_links がダングリングする。**削除 → `validate.py` 実行 → 列挙されたダングリング関係・リンクを削除 → `build_index.py`** の順で掃除する
- ID の**欠番は再利用しない**（rel / ql / claim いずれも。過去の参照履歴と混線するため）
- データは取り込み単位で git コミットされているので、壊れたら `git log data/` から巻き戻せる
- ID 空間の上限: claim = c99/論文、question = q-99、relation/link = 9999。個人利用では当面問題ないが、超える場合は `app/models.py` の正規表現と既存データの一括変換が必要

## 最重要: JSON スキーマ（Claude 連携仕様の本体）

クレームの抽出・照合・紐付けは Web UI ではなく **Claude Code がこの JSON を直接読み書き**して行う。実例は `tests/fixtures/data/` にある。

### `data/papers/<paper_id>.json` — 論文1件 = 1ファイル

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `id` | str | `arxiv-<ID>`（例 `arxiv-2201.11903`、バージョンなし）or `pdf-<slug>`。ファイル名と一致必須 |
| `source` | str | `arxiv` / `pdf` |
| `arxiv_id` | str \| null | arXiv ID（非arXivは null） |
| `title` / `authors` / `year` / `venue` / `url` / `abstract` | — | 論文メタデータ（venue 不明なら `""`） |
| `topics` | list[str] | topic id の配列。**topics.json に定義済みであること** |
| `imported_at` | str | ISO 時刻（JST、秒精度） |
| `notes` | str | 自由メモ |
| `claims` | list | 下記 Claim の配列 |

### Claim（papers ファイル内）

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `id` | str | `<paper_id>-cNN`（2桁連番）。全体で一意 |
| `summary_ja` | str | 条件を含む一文の和文サマリ（必須） |
| `quote` | str | **原文そのままの引用**（必須・言い換え禁止） |
| `kind` | str | `experimental` / `theoretical` / `opinion` |
| `evidence.conditions` | str | 実験条件（モデル・設定など） |
| `evidence.datasets` | list[str] | データセット名 |
| `evidence.metrics` | list | `{name, value, baseline}`（baseline 込みで記録） |
| `evidence.section` | str | 出典セクション（**必須**・プロベナンス原則） |
| `evidence.pages` | str | 該当ページ（例 `"4-6"`） |
| `confidence` | str | `high` / `medium` / `low` |
| `confidence_note` | str | 確度の判定理由 |
| `created_at` | str | ISO 時刻（JST） |

### `data/relations.json` — `{"relations": [...]}`

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `id` | str | `rel-NNNN`（4桁連番、既存最大+1） |
| `from` / `to` | str | claim id。向きは「**from が to を 支持/反証/拡張 する**」 |
| `type` | str | `supports` / `contradicts` / `same_as` / `extends`。**same_as は from < to（辞書順）に正規化** |

方向の意味論:
- `supports` / `extends` は本質的に非対称（証拠の提供・積み上げ）。**相互支持**は両方向に2本張って表現する（合法）
- `contradicts` は**論理的には対称**（両立しない）。脈図では両端矢印で描かれる。from/to は「**対立を提起した側 → された側**」（通常は後発論文が from）という来歴として保持する
- `same_as` は対称のため正規化・無矢印破線
| `rationale_ja` | str | 判断根拠（実験条件の差異を明記・必須） |
| `confidence` | str | `high` / `medium` / `low` |
| `created_at` | str | ISO 時刻（JST) |

制約: 自己参照禁止・同一 (from, to, type) の重複禁止・両端の claim が実在すること。

### `data/topics.json` — `{"topics": [...]}`

`{id（kebab-case slug）, name_ja, description, created_at}`。論文→トピック対応は paper 側の `topics` に持つ。

### `data/questions.json` — `{"questions": [...]}` ユーザーが立てた問い

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `id` | str | `q-NN`（2桁連番） |
| `text_ja` | str | 問いの文面（必須） |
| `type` | str | `closed`（判定型 = yes/no）/ `open`（記述型 = what/how） |
| `topics` | list[str] | 対象トピック（1件以上必須。取り込み時の照合スコープ） |
| `notes` / `created_at` | str | メモ / ISO 時刻（JST） |

### `data/question_links.json` — `{"question_links": [...]}` 問い↔クレーム

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `id` | str | `ql-NNNN`（4桁連番） |
| `question_id` / `claim_id` | str | 実在する問い / クレームを指すこと |
| `answer_ja` | str | **このクレームが問いに与える答え**（必須・一文。「はい」だけは不可） |
| `stance` | str \| null | **判定型のみ**: `affirms`（肯定）/ `denies`（否定）/ `qualifies`（条件付き）。記述型では null |
| `rationale_ja` | str | 判断根拠（必須） |
| `confidence` / `created_at` | str | `high`/`medium`/`low` / ISO 時刻（JST） |

制約: 同一 (question, claim) の重複禁止。stance の有無は問いの type と整合すること（validate.py が強制）。
記述型の「回答候補のクラスタ」は別台帳を持たず、リンクされたクレーム間の既存関係（supports / same_as / contradicts）から導出する（設計上の決定）。

### `data/claims_index.jsonl` — 派生インデックス（手編集禁止）

1クレーム=1行 `{id, topics, kind, summary_ja, paper_title}`。照合時に grep で候補を絞るためのもの。`scripts/build_index.py` で再生成。

## 関連ドキュメント

- `tasks/todo.md` — 実装計画とチェックリスト
- `.claude/skills/paper-import/SKILL.md` — 取り込みワークフローの本体（抽出粒度・関係判定基準）
- `README.md` — 運用手順（常駐化・データのバックアップ）
