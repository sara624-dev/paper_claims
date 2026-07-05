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

## 機能拡張: 問い駆動マッピング（2026-07-05 承認済み設計）

設計: 問い type = closed(判定型) | open(記述型)。QuestionLink は answer_ja 必須、
stance（肯定/否定/条件付き）は判定型のみ。記述型の回答クラスタは既存のクレーム間関係から導出。

- [x] models.py: Question / QuestionLink + enum（QUESTION_TYPES / STANCES）
- [x] config.py / storage.py: questions.json / question_links.json の読み込み
- [x] validate.py: 参照整合性 + stance⇔type 整合 + 重複リンク検出
- [x] graph.py: 問いレンズ（linked claims のみ + stance をノードに付与）
- [x] main.py: /api/questions, /api/questions/{id}, /api/graph?question=, /questions ページ
- [x] templates/app.js: 問いダッシュボード、脈図の問いバナー + stance枠色、シート/詳細に「答える問い」
- [x] スキル: /paper-question 新設、/paper-import に手順6.5（問いへの回答性判定）
- [x] CLAUDE.md スキーマ表更新
- [x] tests: fixtures + storage/validate/api（計26件）
- [x] E2E: 実データで問い2件（q-01判定型: 否定3/条件付き2、q-02記述型: 答え2件）登録・スクリーンショット確認
- [x] commit & push
- 併せて完了: quote機械検証 scripts/verify_quotes.py（28件全照合OK）、GitHub私有リポ https://github.com/sara624-dev/paper_claims

## Review

- **成果**: 計画どおり MVP 完成。実論文4本・クレーム28件・関係7件（supports 4 / contradicts 2 / extends 1）が入った状態で全チェック通過。サーバ再起動なしのデータ反映（mtimeキャッシュ）も実証
- **計画からの逸脱（改善）**:
  - E2E 検証で当初の3本トリオでは真の contradicts が存在しないと判明（Huang の反証対象 Self-Refine が未収載のため）→ 偽リンクを作らず 2303.17651 を4本目として追加取り込みし、実在する反証関係で検証
  - この環境では Read ツールの PDF レンダリングが使えない → pdftotext 方式に SKILL.md を修正
- **教訓**: tasks/lessons.md を参照
