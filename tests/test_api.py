"""API（read-only）のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(data_dir: Path) -> TestClient:
    return TestClient(app)


def test_topics(client: TestClient) -> None:
    res = client.get("/api/topics")
    assert res.status_code == 200
    topics = {t["id"]: t for t in res.json()["topics"]}
    assert topics["cot-reasoning"]["paper_count"] == 2
    assert topics["cot-reasoning"]["claim_count"] == 4
    assert topics["self-correction"]["paper_count"] == 1


def test_papers_list_and_filter(client: TestClient) -> None:
    assert len(client.get("/api/papers").json()["papers"]) == 2
    filtered = client.get("/api/papers", params={"topic": "self-correction"}).json()["papers"]
    assert [p["id"] for p in filtered] == ["arxiv-2102.00002"]


def test_paper_detail(client: TestClient) -> None:
    res = client.get("/api/papers/arxiv-2101.00001")
    assert res.status_code == 200
    assert len(res.json()["claims"]) == 2
    assert client.get("/api/papers/arxiv-9999.99999").status_code == 404


def test_claims_search(client: TestClient) -> None:
    assert len(client.get("/api/claims").json()["claims"]) == 4
    hits = client.get("/api/claims", params={"q": "自己修正"}).json()["claims"]
    assert {c["id"] for c in hits} == {"arxiv-2101.00001-c02", "arxiv-2102.00002-c02"}
    hits = client.get("/api/claims", params={"topic": "self-correction", "q": "悪化"}).json()[
        "claims"
    ]
    assert [c["id"] for c in hits] == ["arxiv-2102.00002-c02"]


def test_claim_detail_joins_relations(client: TestClient) -> None:
    res = client.get("/api/claims/arxiv-2101.00001-c02")
    assert res.status_code == 200
    body = res.json()
    assert body["paper"]["id"] == "arxiv-2101.00001"
    assert len(body["relations"]) == 1
    rel = body["relations"][0]
    assert rel["type"] == "contradicts"
    assert rel["direction"] == "in"  # 相手（from）がこのクレームを反証している
    assert rel["other"]["claim_id"] == "arxiv-2102.00002-c02"
    assert rel["other"]["paper_title"].startswith("Self-Correction")


def test_graph_full_and_topic_filter(client: TestClient) -> None:
    body = client.get("/api/graph").json()
    assert body["meta"]["node_count"] == 4
    assert body["meta"]["edge_count"] == 3
    assert body["meta"]["layout"] == "cose"
    edge_types = {e["data"]["type"] for e in body["elements"]["edges"]}
    assert edge_types == {"supports", "contradicts", "same_as"}

    # self-correction トピックは論文1本のみ → 相手側クレームが範囲外の関係は落ちる
    body = client.get("/api/graph", params={"topic": "self-correction"}).json()
    assert body["meta"]["node_count"] == 2
    assert body["meta"]["edge_count"] == 0


def test_pages_render(client: TestClient) -> None:
    for path in (
        "/",
        "/?topic=cot-reasoning",
        "/papers",
        "/papers/arxiv-2101.00001",
        "/claims/arxiv-2102.00002-c02",
    ):
        res = client.get(path)
        assert res.status_code == 200, path
        assert "論脈" in res.text
    assert client.get("/claims/arxiv-9999.99999-c01").status_code == 404
