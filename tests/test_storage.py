"""storage（読み取り + mtime キャッシュ）のテスト。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from app import storage


def test_load_vault(data_dir: Path) -> None:
    vault = storage.load_vault()
    assert len(vault.papers) == 2
    assert sum(len(p.claims) for p in vault.papers) == 4
    assert len(vault.relations) == 3
    assert len(vault.topics) == 2
    assert vault.errors == []
    # 取り込み日降順
    assert vault.papers[0].id == "arxiv-2102.00002"


def test_paper_and_claim_lookup(data_dir: Path) -> None:
    vault = storage.load_vault()
    assert vault.paper_by_id("arxiv-2101.00001") is not None
    assert vault.paper_by_id("arxiv-9999.99999") is None
    paper = vault.claim_paper("arxiv-2102.00002-c02")
    assert paper is not None and paper.id == "arxiv-2102.00002"


def test_cache_invalidation_on_file_change(data_dir: Path) -> None:
    vault1 = storage.load_vault()
    assert storage.load_vault() is vault1  # 変更がなければ同一オブジェクト

    # 論文ファイルを外部から更新（Claude Code が編集するのと同じ経路）
    path = data_dir / "papers" / "arxiv-2101.00001.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["notes"] = "updated"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 10))

    vault2 = storage.load_vault()
    assert vault2 is not vault1
    paper = vault2.paper_by_id("arxiv-2101.00001")
    assert paper is not None and paper.notes == "updated"


def test_broken_file_is_skipped_with_error(data_dir: Path) -> None:
    (data_dir / "papers" / "arxiv-2103.00003.json").write_text("{broken", encoding="utf-8")
    vault = storage.load_vault()
    assert len(vault.papers) == 2  # 壊れたファイルは読み飛ばす
    assert any("arxiv-2103.00003" in e for e in vault.errors)
