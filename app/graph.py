"""papers + relations から Cytoscape.js の elements 形式を組み立てる。

レイアウトはドメイン構造をそのまま使う: 論文 = compound 親ノード（カラム、左から
時系列順）、クレーム = 親の中に縦に積むカード。座標計算はフロント（preset layout）。
"""

from __future__ import annotations

import zlib
from typing import Any

from .models import Paper
from .storage import Vault


def paper_hue(paper_id: str) -> int:
    """論文 ID から安定した色相（0-359）を返す。同じ論文の要素は同色になる。"""
    return zlib.crc32(paper_id.encode("utf-8")) % 360


def _short(text: str, limit: int = 48) -> str:
    """グラフノードのラベル用にテキストを切り詰める。"""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _paper_short(paper: Paper) -> str:
    """カラム見出し用の短い論文表記（筆頭著者姓 + 年）を返す。"""
    first_author = paper.authors[0].split()[-1] if paper.authors else paper.id
    return f"{first_author}+{' ' + str(paper.year) if paper.year else ''}"


def build_elements(vault: Vault, topic: str | None = None) -> dict[str, Any]:
    """Cytoscape.js に渡す elements とメタ情報を返す。

    Args:
        vault: 読み込み済みデータ。
        topic: 指定時はそのトピックを持つ論文のクレームに絞る。

    Returns:
        ``{"elements": {"nodes": [...], "edges": [...]}, "meta": {...}}``。
        nodes には論文（compound 親、``order`` = 時系列カラム位置）とクレーム
        （``parent`` + ``seq`` = カラム内の行位置）の両方が入る。
    """
    papers = vault.papers if topic is None else [p for p in vault.papers if topic in p.topics]
    # 左から時系列（年 → 取り込み日 → id）でカラムを並べる
    papers = sorted(papers, key=lambda p: (p.year or 9999, p.imported_at, p.id))

    nodes: list[dict[str, Any]] = []
    claim_count = 0
    claim_ids: set[str] = set()
    for order, paper in enumerate(papers):
        hue = paper_hue(paper.id)
        nodes.append(
            {
                "data": {
                    "id": paper.id,
                    "label": _paper_short(paper),
                    "title": paper.title,
                    "hue": hue,
                    "order": order,
                }
            }
        )
        for seq, claim in enumerate(paper.claims):
            claim_count += 1
            claim_ids.add(claim.id)
            nodes.append(
                {
                    "data": {
                        "id": claim.id,
                        "parent": paper.id,
                        "label": _short(claim.summary_ja),
                        "summary": claim.summary_ja,
                        "paper_id": paper.id,
                        "paper_title": paper.title,
                        "kind": claim.kind,
                        "confidence": claim.confidence,
                        "order": order,
                        "seq": seq,
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
            "node_count": claim_count,
            "edge_count": len(edges),
            "paper_count": len(papers),
        },
    }
