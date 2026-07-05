# 論脈 RONMYAKU — MVP 実装計画

計画本体: `/home/vscode/.claude/plans/cheeky-bouncing-snail.md`（承認済み）

## Step 1: スキャフォールド
- [x] ディレクトリ作成・git init
- [x] pyproject.toml（tansu流用: uv / ruff / mypy / pytest）
- [x] scripts/check.sh
- [x] .gitignore（data/pdfs/ 除外）
- [x] README.md / CLAUDE.md（JSONスキーマ表込み）
- [x] uv sync

## Step 2: データ層
- [x] app/config.py（PAPER_CLAIMS_DATA_DIR 上書き対応）
- [x] app/models.py（Paper / Claim / Evidence / Relation / Topic + enum の単一の真実）
- [x] app/storage.py（読み取り専用ローダ + mtimeキャッシュ）
- [x] scripts/validate.py（スキーマ + 参照整合性、エラー時 exit 1）
- [x] scripts/build_index.py（claims_index.jsonl 再生成）
- [x] tests/fixtures（論文2・クレーム4・関係3）+ test_storage / test_validate
- [x] data/ 初期ファイル

## Step 3: API（read-only）
- [x] app/graph.py（Cytoscape elements 変換）
- [x] app/main.py（6 APIエンドポイント + 画面4枚）
- [x] tests/test_api.py（httpx + フィクスチャ差し替え）

## Step 4: フロントエンド（ビルドレス）
- [x] cytoscape.min.js ベンダリング（3.34.0, 425KB）
- [x] templates: base / graph / papers / paper_detail / claim_detail
- [x] static: app.js / styles.css（モバイルファースト、ボトムシート、墨×銀鼠デザイン）
- [x] エッジ色分け: supports=緑 / contradicts=赤 / same_as=青破線 / extends=グレー点線

## Step 5: スキル
- [x] .claude/skills/paper-import/SKILL.md
- [x] 環境知見の反映（Read の PDF レンダリング不可 → pdftotext を使う）

## Step 6: 仕上げ
- [x] paper-claims.service（ポート8124、ホスト適用手順をREADMEへ）
- [x] /workspace/CLAUDE.md のプロジェクト一覧・ルーティングに追記
- [x] git commit（アプリ本体）

## 検証
- [x] bash scripts/check.sh 通過（ruff / mypy / pytest 19件 / validate）
- [x] フィクスチャデータで全ページ・API・静的配信 200 確認
- [x] E2E: 実論文の取り込み
  - [x] 2201.11903 CoT Prompting（クレーム7件）
  - [x] 2203.11171 Self-Consistency（クレーム7件）
  - [x] 2310.01798 Cannot Self-Correct（クレーム7件）
  - [x] 2303.17651 Self-Refine（反証エッジ検証用に追加）
  - [x] 関係judgment（extends / supports / contradicts）→ validate 通過
  - [x] グラフAPIで全エッジ種別の出力確認
- [x] データのコミット

## Review

- **成果**: 計画どおり MVP 完成。実論文4本・クレーム28件・関係7件（supports 4 / contradicts 2 / extends 1）が入った状態で全チェック通過。サーバ再起動なしのデータ反映（mtimeキャッシュ）も実証
- **計画からの逸脱（改善）**:
  - E2E 検証で当初の3本トリオでは真の contradicts が存在しないと判明（Huang の反証対象 Self-Refine が未収載のため）→ 偽リンクを作らず 2303.17651 を4本目として追加取り込みし、実在する反証関係で検証
  - この環境では Read ツールの PDF レンダリングが使えない → pdftotext 方式に SKILL.md を修正
- **教訓**: tasks/lessons.md を参照
