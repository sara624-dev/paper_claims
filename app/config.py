"""パスと定数の集中管理。"""

from __future__ import annotations

import os
from pathlib import Path

# プロジェクトルート（app/ の一つ上）
BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent

# データ保存先。環境変数 PAPER_CLAIMS_DATA_DIR で上書き可能（テスト分離・運用での移動に利用）。
DATA_DIR = (
    Path(os.environ["PAPER_CLAIMS_DATA_DIR"])
    if os.environ.get("PAPER_CLAIMS_DATA_DIR")
    else BASE_DIR / "data"
)


def papers_dir() -> Path:
    """論文JSONの格納ディレクトリを返す。"""
    return DATA_DIR / "papers"


def relations_file() -> Path:
    """関係台帳ファイルのパスを返す。"""
    return DATA_DIR / "relations.json"


def topics_file() -> Path:
    """トピック台帳ファイルのパスを返す。"""
    return DATA_DIR / "topics.json"


def claims_index_file() -> Path:
    """クレーム照合用インデックス（派生物）のパスを返す。"""
    return DATA_DIR / "claims_index.jsonl"


TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

# グラフ表示: ノード数がこれを超えたら cose レイアウトを諦めて concentric に切り替える
GRAPH_COSE_NODE_LIMIT = 500
