"""data/ ディレクトリの骨組みを初期化する（初回セットアップ用）。

data/ は git 管理外（個人の研究データのため）。clone 直後にこれを実行して
空の台帳一式を作る。既存ファイルは上書きしない（冪等）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config

LEDGERS = {
    "topics.json": {"topics": []},
    "relations.json": {"relations": []},
    "questions.json": {"questions": []},
    "question_links.json": {"question_links": []},
    "problems.json": {"problems": []},
}


def main() -> int:
    for sub in ("papers", "pdfs"):
        (config.DATA_DIR / sub).mkdir(parents=True, exist_ok=True)
    for name, empty in LEDGERS.items():
        path = config.DATA_DIR / name
        if not path.exists():
            path.write_text(
                json.dumps(empty, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(f"created: {path}")
        else:
            print(f"exists:  {path}（変更なし）")
    (config.DATA_DIR / "claims_index.jsonl").touch()
    (config.DATA_DIR / "challenges_index.jsonl").touch()
    print(
        "OK: data/ を初期化した。バックアップしたい場合は data/ を私有 git リポジトリ化することを推奨"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
