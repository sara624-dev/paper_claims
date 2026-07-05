# 論脈 RONMYAKU — MVP 実装計画

計画本体: `/home/vscode/.claude/plans/cheeky-bouncing-snail.md`（承認済み）

## Step 1: スキャフォールド
- [x] ディレクトリ作成・git init
- [x] pyproject.toml（tansu流用: uv / ruff / mypy / pytest）
- [x] scripts/check.sh
- [x] .gitignore（data/pdfs/ 除外）
- [ ] README.md / CLAUDE.md（JSONスキーマ表込み）
- [ ] uv sync

## Step 2: データ層
- [ ] app/config.py（PAPER_CLAIMS_DATA_DIR 上書き対応）
- [ ] app/models.py（Paper / Claim / Evidence / Relation / Topic + enum の単一の真実）
- [ ] app/storage.py（読み取り専用ローダ + mtimeキャッシュ）
- [ ] scripts/validate.py（スキーマ + 参照整合性、エラー時 exit 1）
- [ ] scripts/build_index.py（claims_index.jsonl 再生成）
- [ ] tests/fixtures（論文2・クレーム4・関係3）+ test_storage / test_validate
- [ ] data/ 初期ファイル（topics.json / relations.json / claims_index.jsonl / pdfs/.gitkeep）

## Step 3: API（read-only）
- [ ] app/graph.py（Cytoscape elements 変換）
- [ ] app/main.py（/api/topics, /api/papers, /api/papers/{id}, /api/claims, /api/claims/{id}, /api/graph）
- [ ] tests/test_api.py（httpx + フィクスチャ差し替え）

## Step 4: フロントエンド（ビルドレス）
- [ ] cytoscape.min.js ベンダリング（npm pack cytoscape@3.34.0）
- [ ] templates: base / graph / papers / paper_detail / claim_detail
- [ ] static: app.js / styles.css（モバイルファースト、ボトムシート）
- [ ] エッジ色分け: supports=緑 / contradicts=赤 / same_as=青破線 / extends=グレー点線

## Step 5: スキル
- [ ] .claude/skills/paper-import/SKILL.md

## Step 6: 仕上げ
- [ ] paper-claims.service（ポート8124、ホスト適用手順をREADMEへ）
- [ ] /workspace/CLAUDE.md のプロジェクト一覧に追記
- [ ] git commit

## 検証
- [ ] bash scripts/check.sh 通過
- [ ] E2E: CoTトリオ（2201.11903 / 2203.11171 / 2310.01798）取り込み → グラフで緑/赤エッジ確認

## Review
（完了時に記入）
