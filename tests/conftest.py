"""テスト共通フィクスチャ。"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app import config, storage

FIXTURES_DATA = Path(__file__).parent / "fixtures" / "data"


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """フィクスチャデータを tmp にコピーして DATA_DIR を差し替える。"""
    dst = tmp_path / "data"
    shutil.copytree(FIXTURES_DATA, dst)
    monkeypatch.setattr(config, "DATA_DIR", dst)
    storage._cache = None
    return dst
