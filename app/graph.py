"""papers + relations から Cytoscape.js の elements 形式を組み立てる。"""

from __future__ import annotations

import zlib
from typing import Any

from . import config
from .storage import Vault


def paper_hue(paper_id: str) -> int:
    """論文 ID から安定した色相（0-359）を返す。同じ論文のクレームは同色になる。"""
    return zlib.crc32(paper_id.encode("utf-8")) % 360


def _short(text: str, limit: int = 34) -> str:
    """グラフノードのラベル用にテキストを切り詰める。"""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_elements(vault: Vault, topic: str | None = None) -> dict[str, Any]:
    """Cytoscape.js に渡す elements とメタ情報を返す。

    Args:
        vault: 読み込み済みデータ。
        topic: 指定時はそのトピックを持つ論文のクレームに絞る。

    Returns:
        ``{"elements": {"nodes": [...], "edges": [...]}, "meta": {...}}``
    """
    papers = vault.papers if topic is None else [p for p in vault.papers if topic in p.topics]

    nodes = []
    claim_ids: set[str] = set()
    for paper in papers:
        hue = paper_hue(paper.id)
        first_author = paper.authors[0].split()[-1] if paper.authors else paper.id
        paper_short = f"{first_author}{' ' + str(paper.year) if paper.year else ''}"
        for claim in paper.claims:
            claim_ids.add(claim.id)
            nodes.append(
                {
                    "data": {
                        "id": claim.id,
                        "label": _short(claim.summary_ja),
                        "summary": claim.summary_ja,
                        "paper_id": paper.id,
                        "paper_title": paper.title,
                        "paper_short": paper_short,
                        "kind": claim.kind,
                        "confidence": claim.confidence,
                        "hue": hue,
                    }
                }
            )

    edges = [
        {
            "data": {
                "id": rel.id,
                "source": rel.from_id,
                "target": rel.to_id,
                "type": rel.type,
                "rationale": rel.rationale_ja,
                "confidence": rel.confidence,
            }
        }
        for rel in vault.relations
        if rel.from_id in claim_ids and rel.to_id in claim_ids
    ]

    return {
        "elements": {"nodes": nodes, "edges": edges},
        "meta": {
            "topic": topic,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "paper_count": len(papers),
            "layout": "cose" if len(nodes) <= config.GRAPH_COSE_NODE_LIMIT else "concentric",
        },
    }
