# 論脈 RONMYAKU

論文の主張（クレーム）を複数論文横断で管理・紐付け・グラフ可視化する個人用アプリ。

論文（主に arXiv）を Claude Code の `/paper-import` で取り込むと、クレームが根拠・実験条件つきで抽出され、既存クレームとの関係（支持 / 反証 / 同一 / 拡張）が張られる。Web UI（脈図）でトピックごとの研究状況——どこにコンセンサスがあり、どこが係争中か——を一望できる。

- ストレージは JSON ファイル + git（DB なし）。スキーマは `CLAUDE.md` を参照
- Web UI は閲覧専用・認証なし（LAN 内利用前提）・iPhone ファースト
- グラフ描画は Cytoscape.js（`app/static/vendor/` にベンダリング済み・CDN 非依存）

## 使い方

### 論文を取り込む（Claude Code）

```
/paper-import https://arxiv.org/abs/2201.11903 cot-reasoning
/paper-import 2310.01798          # トピック省略時は既存から自動選択 or 対話で決定
/paper-import ~/papers/foo.pdf    # ローカル PDF も可
```

### 見る（Web UI）

| URL | 内容 |
|-----|------|
| `/` | 脈図（クレームグラフ）。トピック切替、ノードタップで詳細シート |
| `/papers` | 論文一覧（トピック・テキストで絞り込み） |
| `/papers/{id}` | 論文詳細（クレーム一覧） |
| `/claims/{id}` | クレーム詳細（根拠・関係・「脈図で見る」） |

エッジの色: 緑=支持 / 赤=反証 / 青破線=同一 / 灰点線=拡張。ノードの形: 楕円=実験的 / 菱形=理論的 / 角丸=見解。ノード色は論文ごと。

## 開発

```bash
uv sync                                                    # 依存導入
uv run uvicorn app.main:app --host 0.0.0.0 --port 8124     # 起動
bash scripts/check.sh                                      # lint / 型 / テスト / データ検証
```

## 常駐化（Raspberry Pi ホスト側で実行）

このリポジトリはコンテナ内 `/workspace/paper_claims` = ホスト `/home/YOUR_USER/workspace/paper_claims`。
systemd unit はホスト側で適用する:

```bash
sudo cp paper-claims.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now paper-claims.service
```

LAN 内から `http://<PiのIP>:8124/` で開ける。

> **注意**: 論文データの追加・編集は再起動なしで反映される（mtimeキャッシュ）が、
> **コード（`app/` 配下）を変更した場合は `sudo systemctl restart paper-claims` が必要**。
> 反映漏れがあると「新しいJS × 古いAPI」の食い違いで表示が壊れることがある。

## データ運用

- `data/` は git 管理（`data/pdfs/` のみ除外）。論文の取り込み単位でコミットされる
- 手編集した場合は `uv run python scripts/build_index.py && uv run python scripts/validate.py` を必ず実行
- 検証データを壊した場合も git で戻せる
