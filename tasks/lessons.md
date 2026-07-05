# Lessons — 論脈 RONMYAKU

## 2026-07-05 MVP 構築時

### PDF 読解は pdftotext を使う
- **事象**: この環境（Pi コンテナ）では Claude Code の Read ツールによる PDF レンダリングが使えない
- **対応**: `pdftotext`（poppler-utils）でテキスト化して読む。SKILL.md 手順3に反映済み
- **ルール**: PDF 処理を含むスキルを書くときは、Read の PDF 対応を前提にせず pdftotext を第一選択にする

### 関係（relation）は「実在する反証」だけを張る
- **事象**: E2E 検証で CoT / Self-Consistency / Cannot-Self-Correct の3本を取り込んだが、この組み合わせには真の contradicts が存在しなかった（Huang 2310.01798 の反証対象は Reflexion / Self-Refine 等の未収載論文）
- **対応**: 無理に赤エッジを作らず、反証対象の Self-Refine（2303.17651）を追加取り込みして実在の係争関係で検証した
- **ルール**: 「グラフに全種類のエッジを出したい」という検証都合でデータを歪めない。contradicts が無いのはそれ自体が正しい研究状況の反映。反証関係を見たければ反証している論文を取り込む

### arXiv API はまれに別論文を返すことがある
- **事象**: `export.arxiv.org/api/query?id_list=` が一度、別 ID の論文メタデータを返した（サブエージェント報告）
- **ルール**: メタデータ取得後、PDF 1ページ目のタイトルと一致することを必ず確認する
