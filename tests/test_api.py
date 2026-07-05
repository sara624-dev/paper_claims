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
    assert body["meta"]["node_count"] == 4  # クレームのみ（論文の親ノードは含まない）
    assert body["meta"]["edge_count"] == 3
    edge_types = {e["data"]["type"] for e in body["elements"]["edges"]}
    assert edge_types == {"supports", "contradicts", "same_as"}
    # 論文 = compound 親ノード、クレームは parent と時系列カラム位置を持つ
    nodes = body["elements"]["nodes"]
    parents = [n["data"] for n in nodes if "parent" not in n["data"]]
    claims = [n["data"] for n in nodes if "parent" in n["data"]]
    assert len(parents) == 2 and len(claims) == 4
    assert {p["order"] for p in parents} == {0, 1}
    assert all("seq" in c for c in claims)

    # self-correction トピックは論文1本のみ → 相手側クレームが範囲外の関係は落ちる
    body = client.get("/api/graph", params={"topic": "self-correction"}).json()
    assert body["meta"]["node_count"] == 2
    assert body["meta"]["edge_count"] == 0


def test_questions_list_and_detail(client: TestClient) -> None:
    body = client.get("/api/questions").json()
    q1 = next(q for q in body["questions"] if q["id"] == "q-01")
    assert q1["type"] == "closed"
    assert q1["link_count"] == 2
    assert q1["stance_counts"] == {"affirms": 2, "denies": 0, "qualifies": 0}

    detail = client.get("/api/questions/q-02").json()
    assert len(detail["links"]) == 1
    link = detail["links"][0]
    assert link["stance"] is None
    assert link["claim_id"] == "arxiv-2102.00002-c02"
    assert link["paper_title"].startswith("Self-Correction")
    assert client.get("/api/questions/q-99").status_code == 404


def test_graph_question_lens(client: TestClient) -> None:
    body = client.get("/api/graph", params={"question": "q-01"}).json()
    assert body["meta"]["node_count"] == 2  # リンクされたクレームのみ
    assert body["meta"]["paper_count"] == 2
    claims = [n["data"] for n in body["elements"]["nodes"] if "parent" in n["data"]]
    assert all(c["stance"] == "affirms" and c["answer"] for c in claims)
    # 両端がレンズ内にある関係だけ残る（c01同士の supports / same_as）
    assert body["meta"]["edge_count"] == 2


def test_claim_detail_includes_questions(client: TestClient) -> None:
    body = client.get("/api/claims/arxiv-2102.00002-c02").json()
    assert len(body["questions"]) == 1
    assert body["questions"][0]["question_id"] == "q-02"
    assert body["questions"][0]["stance"] is None


def test_pages_render(client: TestClient) -> None:
    for path in (
        "/",
        "/?topic=cot-reasoning",
        "/?question=q-01",
        "/questions",
        "/papers",
        "/papers/arxiv-2101.00001",
        "/claims/arxiv-2102.00002-c02",
    ):
        res = client.get(path)
        assert res.status_code == 200, path
        assert "論脈" in res.text
    assert client.get("/claims/arxiv-9999.99999-c01").status_code == 404
