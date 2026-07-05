"""scripts/validate.py（スキーマ + 参照整合性）のテスト。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

validate_path = Path(__file__).parent.parent / "scripts" / "validate.py"
spec = importlib.util.spec_from_file_location("validate", validate_path)
assert spec and spec.loader
validate_mod = importlib.util.module_from_spec(spec)
sys.modules["validate"] = validate_mod
spec.loader.exec_module(validate_mod)


def _relations(data_dir: Path) -> dict:
    return json.loads((data_dir / "relations.json").read_text(encoding="utf-8"))


def _write_relations(data_dir: Path, raw: dict) -> None:
    (data_dir / "relations.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")


def test_fixture_data_is_valid(data_dir: Path) -> None:
    assert validate_mod.validate() == []


def test_detects_dangling_relation(data_dir: Path) -> None:
    raw = _relations(data_dir)
    raw["relations"][0]["to"] = "arxiv-9999.99999-c01"
    _write_relations(data_dir, raw)
    errors = validate_mod.validate()
    assert any("存在しない claim" in e for e in errors)


def test_detects_self_reference_and_duplicate_edge(data_dir: Path) -> None:
    raw = _relations(data_dir)
    raw["relations"][0]["to"] = raw["relations"][0]["from"]
    raw["relations"].append(dict(raw["relations"][1], id="rel-0009"))
    _write_relations(data_dir, raw)
    errors = validate_mod.validate()
    assert any("自己参照" in e for e in errors)
    assert any("重複" in e for e in errors)


def test_detects_unnormalized_same_as(data_dir: Path) -> None:
    raw = _relations(data_dir)
    same_as = raw["relations"][2]
    same_as["from"], same_as["to"] = same_as["to"], same_as["from"]
    _write_relations(data_dir, raw)
    errors = validate_mod.validate()
    assert any("正規化" in e for e in errors)


def test_detects_unknown_topic(data_dir: Path) -> None:
    path = data_dir / "papers" / "arxiv-2101.00001.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["topics"] = ["no-such-topic"]
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    errors = validate_mod.validate()
    assert any("未定義トピック" in e for e in errors)


def test_detects_bad_enum(data_dir: Path) -> None:
    # スキーマ違反（不正な kind）はファイル単位で弾かれる
    path = data_dir / "papers" / "arxiv-2101.00001.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["claims"][0]["kind"] = "vibes"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    errors = validate_mod.validate()
    assert any("kind" in e for e in errors)


def test_detects_duplicate_claim_id(data_dir: Path) -> None:
    src = data_dir / "papers" / "arxiv-2101.00001.json"
    raw = json.loads(src.read_text(encoding="utf-8"))
    raw["id"] = "arxiv-2104.00004"
    raw["arxiv_id"] = "2104.00004"
    # claims の id を書き換え忘れた（接頭辞不一致 + 重複）ケース
    (data_dir / "papers" / "arxiv-2104.00004.json").write_text(
        json.dumps(raw, ensure_ascii=False), encoding="utf-8"
    )
    errors = validate_mod.validate()
    assert any("接頭辞" in e for e in errors)
    assert any("claim id が重複" in e for e in errors)


def test_detects_missing_rationale(data_dir: Path) -> None:
    raw = _relations(data_dir)
    raw["relations"][0]["rationale_ja"] = " "
    _write_relations(data_dir, raw)
    errors = validate_mod.validate()
    assert any("rationale_ja" in e for e in errors)
