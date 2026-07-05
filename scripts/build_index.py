"""claims_index.jsonl（クレーム照合用の派生インデックス）を再生成する。

/paper-import スキルが「既存クレームとの照合」で grep するための 1クレーム=1行 の
JSONL。data/papers/*.json から常に再生成できる派生物であり、手編集しない。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.storage import load_vault


def main() -> int:
    vault = load_vault()
    if vault.errors:
        print("WARN: 読み飛ばしたデータがある（scripts/validate.py で確認すること）")
        for msg in vault.errors:
            print(f"  - {msg}")

    lines = []
    for paper in sorted(vault.papers, key=lambda p: p.id):
        for claim in paper.claims:
            lines.append(
                json.dumps(
                    {
                        "id": claim.id,
                        "topics": paper.topics,
                        "tags": paper.tags,
                        "kind": claim.kind,
                        "summary_ja": claim.summary_ja,
                        "paper_title": paper.title,
                    },
                    ensure_ascii=False,
                )
            )

    out = config.claims_index_file()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"OK: {out} を再生成（{len(lines)} クレーム）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
