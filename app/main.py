"""FastAPI アプリ本体（閲覧専用）。

書き込み系エンドポイントは一切持たない。データの追加・編集は Claude Code の
/paper-import スキルがファイルを直接書く（CLAUDE.md のスキーマ表が連携仕様）。
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config, graph, storage
from .models import (
    CONFIDENCE_LABELS_JA,
    KIND_LABELS_JA,
    QUESTION_STATUS_LABELS_JA,
    QUESTION_TYPE_LABELS_JA,
    RELATION_LABELS_JA,
    STANCE_LABELS_JA,
    STANCES,
    Claim,
    Paper,
    Question,
)

app = FastAPI(title="論脈 RONMYAKU")
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))
templates.env.globals.update(
    RELATION_LABELS=RELATION_LABELS_JA,
    KIND_LABELS=KIND_LABELS_JA,
    CONFIDENCE_LABELS=CONFIDENCE_LABELS_JA,
    QUESTION_TYPE_LABELS=QUESTION_TYPE_LABELS_JA,
    QUESTION_STATUS_LABELS=QUESTION_STATUS_LABELS_JA,
    STANCE_LABELS=STANCE_LABELS_JA,
    paper_hue=graph.paper_hue,
)


def _json_for_script(obj: object) -> str:
    r"""``<script>`` へ安全に埋め込める JSON 文字列を返す。

    ``</script>`` 等によるブレイクアウト（格納型 XSS）を防ぐため ``< > &`` を
    ``\uXXXX`` へ置換する。JSON.parse の往復結果は不変。
    """
    return (
        json.dumps(obj, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _paper_summary(paper: Paper) -> dict[str, Any]:
    """一覧表示用の論文サマリ dict を返す。"""
    return {
        "id": paper.id,
        "title": paper.title,
        "authors": paper.authors,
        "year": paper.year,
        "venue": paper.venue,
        "url": paper.url,
        "topics": paper.topics,
        "tags": paper.tags,
        "claim_count": len(paper.claims),
        "challenge_head": paper.challenges[0].summary_ja if paper.challenges else "",
        "imported_at": paper.imported_at,
    }


def _problem_summary(vault: storage.Vault, problem_id: str) -> dict[str, Any] | None:
    """共有課題のサマリ（向き合う論文一覧つき）を返す。"""
    problem = vault.problem_by_id(problem_id)
    if problem is None:
        return None
    entries = [
        {
            "paper_id": paper.id,
            "paper_title": paper.title,
            "year": paper.year,
            "challenge_id": ch.id,
            "summary_ja": ch.summary_ja,
        }
        for paper, ch in vault.challenges_for_problem(problem_id)
    ]
    entries.sort(key=lambda x: (x["year"] or 9999, x["paper_id"]))
    return {**problem.model_dump(), "entries": entries}


def _claim_relations(vault: storage.Vault, claim_id: str) -> list[dict[str, Any]]:
    """クレームを端点とする関係一覧を、相手側クレーム・論文情報を join して返す。"""
    result = []
    for rel in vault.relations:
        if claim_id not in (rel.from_id, rel.to_id):
            continue
        other_id = rel.to_id if rel.from_id == claim_id else rel.from_id
        other_paper = vault.claim_paper(other_id)
        other_claim = None
        if other_paper is not None:
            other_claim = next((c for c in other_paper.claims if c.id == other_id), None)
        result.append(
            {
                "id": rel.id,
                "type": rel.type,
                "direction": "out" if rel.from_id == claim_id else "in",
                "rationale_ja": rel.rationale_ja,
                "confidence": rel.confidence,
                "other": {
                    "claim_id": other_id,
                    "summary_ja": other_claim.summary_ja if other_claim else "(不明)",
                    "paper_id": other_paper.id if other_paper else "",
                    "paper_title": other_paper.title if other_paper else "",
                },
            }
        )
    return result


def _find_claim(vault: storage.Vault, claim_id: str) -> tuple[Paper, Claim]:
    """クレーム ID から (論文, クレーム) を引く。見つからなければ 404。"""
    paper = vault.claim_paper(claim_id)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"claim not found: {claim_id}")
    claim = next(c for c in paper.claims if c.id == claim_id)
    return paper, claim


def _question_summary(vault: storage.Vault, question: Question) -> dict[str, Any]:
    """一覧表示用の問いサマリ（stance 集計つき）を返す。"""
    links = vault.links_for_question(question.id)
    return {
        **question.model_dump(),
        "link_count": len(links),
        "stance_counts": {s: sum(1 for x in links if x.stance == s) for s in STANCES},
    }


def _question_links_joined(vault: storage.Vault, question_id: str) -> list[dict[str, Any]]:
    """問いのリンク一覧を、クレーム・論文情報を join して時系列順で返す。"""
    result = []
    for link in vault.links_for_question(question_id):
        paper = vault.claim_paper(link.claim_id)
        claim = None
        if paper is not None:
            claim = next((c for c in paper.claims if c.id == link.claim_id), None)
        result.append(
            {
                **link.model_dump(),
                "claim_summary": claim.summary_ja if claim else "(不明)",
                "paper_id": paper.id if paper else "",
                "paper_title": paper.title if paper else "",
                "year": paper.year if paper else None,
            }
        )
    result.sort(key=lambda x: (x["year"] or 9999, x["claim_id"]))
    return result


def _claim_questions(vault: storage.Vault, claim_id: str) -> list[dict[str, Any]]:
    """クレームが答えている問いの一覧（answer_ja / stance つき）を返す。"""
    result = []
    for link in vault.links_for_claim(claim_id):
        question = vault.question_by_id(link.question_id)
        if question is None:
            continue
        result.append(
            {
                "question_id": question.id,
                "text_ja": question.text_ja,
                "type": question.type,
                "answer_ja": link.answer_ja,
                "stance": link.stance,
                "rationale_ja": link.rationale_ja,
            }
        )
    return result


# ===== API（すべて read-only GET）=====


@app.get("/api/topics")
def api_topics() -> dict[str, Any]:
    """トピック一覧（論文数・クレーム数つき）。"""
    vault = storage.load_vault()
    topics = []
    for topic in vault.topics:
        papers = [p for p in vault.papers if topic.id in p.topics]
        topics.append(
            {
                **topic.model_dump(),
                "paper_count": len(papers),
                "claim_count": sum(len(p.claims) for p in papers),
            }
        )
    return {"topics": topics}


@app.get("/api/papers")
def api_papers(topic: str | None = None) -> dict[str, Any]:
    """論文一覧。``?topic=`` で絞り込み。"""
    vault = storage.load_vault()
    papers = vault.papers if topic is None else [p for p in vault.papers if topic in p.topics]
    return {"papers": [_paper_summary(p) for p in papers]}


@app.get("/api/papers/{paper_id}")
def api_paper_detail(paper_id: str) -> dict[str, Any]:
    """論文詳細（全クレーム込み）。"""
    vault = storage.load_vault()
    paper = vault.paper_by_id(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"paper not found: {paper_id}")
    return paper.model_dump()


@app.get("/api/claims")
def api_claims(
    topic: str | None = None, kind: str | None = None, q: str | None = None
) -> dict[str, Any]:
    """クレーム横断検索。``?topic=&kind=&q=``（q は summary_ja / quote の部分一致）。"""
    vault = storage.load_vault()
    results = []
    needle = q.lower() if q else None
    for paper in vault.papers:
        if topic is not None and topic not in paper.topics:
            continue
        for claim in paper.claims:
            if kind is not None and claim.kind != kind:
                continue
            if (
                needle
                and needle not in claim.summary_ja.lower()
                and needle not in claim.quote.lower()
            ):
                continue
            results.append(
                {
                    **claim.model_dump(),
                    "paper_id": paper.id,
                    "paper_title": paper.title,
                    "topics": paper.topics,
                }
            )
    return {"claims": results}


@app.get("/api/claims/{claim_id}")
def api_claim_detail(claim_id: str) -> dict[str, Any]:
    """クレーム詳細 + 関係一覧（相手側クレーム・論文を join 済み）+ 答える問い。"""
    vault = storage.load_vault()
    paper, claim = _find_claim(vault, claim_id)
    return {
        **claim.model_dump(),
        "paper": _paper_summary(paper),
        "relations": _claim_relations(vault, claim_id),
        "questions": _claim_questions(vault, claim_id),
    }


@app.get("/api/graph")
def api_graph(topic: str | None = None, question: str | None = None) -> dict[str, Any]:
    """Cytoscape.js elements 形式のグラフデータ。``?topic=`` / ``?question=`` で絞り込み。"""
    vault = storage.load_vault()
    return graph.build_elements(vault, topic, question)


@app.get("/api/problems")
def api_problems() -> dict[str, Any]:
    """共有課題一覧（向き合う論文つき）。"""
    vault = storage.load_vault()
    problems = [_problem_summary(vault, p.id) for p in vault.problems]
    return {"problems": [p for p in problems if p is not None]}


@app.get("/api/questions")
def api_questions() -> dict[str, Any]:
    """問い一覧（stance 集計つき）。"""
    vault = storage.load_vault()
    return {"questions": [_question_summary(vault, q) for q in vault.questions]}


@app.get("/api/questions/{question_id}")
def api_question_detail(question_id: str) -> dict[str, Any]:
    """問い詳細 + リンク一覧（クレーム・論文を join 済み・時系列順）。"""
    vault = storage.load_vault()
    question = vault.question_by_id(question_id)
    if question is None:
        raise HTTPException(status_code=404, detail=f"question not found: {question_id}")
    return {
        **_question_summary(vault, question),
        "links": _question_links_joined(vault, question_id),
    }


# ===== 画面 =====


@app.get("/", response_class=HTMLResponse)
def page_graph(
    request: Request, topic: str | None = None, question: str | None = None
) -> HTMLResponse:
    """メイン: クレームグラフビュー（トピック絞り込み / 問いレンズ）。"""
    vault = storage.load_vault()
    initial_topic = topic if any(t.id == topic for t in vault.topics) else None
    lens_question = vault.question_by_id(question) if question else None
    return templates.TemplateResponse(
        request,
        "graph.html",
        {
            "nav": "graph",
            "topics": vault.topics,
            "initial_topic": initial_topic,
            "lens_question": lens_question,
            "bootstrap_json": _json_for_script(
                {
                    "initialTopic": initial_topic,
                    "questionId": lens_question.id if lens_question else None,
                    "relationLabels": RELATION_LABELS_JA,
                    "kindLabels": KIND_LABELS_JA,
                    "confidenceLabels": CONFIDENCE_LABELS_JA,
                    "stanceLabels": STANCE_LABELS_JA,
                }
            ),
            "data_errors": vault.errors,
        },
    )


@app.get("/questions", response_class=HTMLResponse)
def page_questions(request: Request) -> HTMLResponse:
    """問いダッシュボード（探究中を先頭に表示）。"""
    vault = storage.load_vault()
    status_order = {"open": 0, "settled": 1, "archived": 2}
    ordered = sorted(vault.questions, key=lambda q: (status_order.get(q.status, 9), q.id))
    questions = [
        {**_question_summary(vault, q), "links": _question_links_joined(vault, q.id)}
        for q in ordered
    ]
    return templates.TemplateResponse(
        request, "questions.html", {"nav": "questions", "questions": questions}
    )


@app.get("/papers", response_class=HTMLResponse)
def page_papers(request: Request, topic: str | None = None) -> HTMLResponse:
    """論文一覧。"""
    vault = storage.load_vault()
    papers = vault.papers if topic is None else [p for p in vault.papers if topic in p.topics]
    return templates.TemplateResponse(
        request,
        "papers.html",
        {
            "nav": "papers",
            "topics": vault.topics,
            "current_topic": topic,
            "papers": [_paper_summary(p) for p in papers],
        },
    )


@app.get("/papers/{paper_id}", response_class=HTMLResponse)
def page_paper_detail(request: Request, paper_id: str) -> HTMLResponse:
    """論文詳細（課題・クレーム一覧つき）。"""
    vault = storage.load_vault()
    paper = vault.paper_by_id(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"paper not found: {paper_id}")
    claim_relations = {c.id: _claim_relations(vault, c.id) for c in paper.claims}
    # 各課題の「同じ課題に向き合う他の論文」
    challenge_mates: dict[str, dict[str, Any]] = {}
    for ch in paper.challenges:
        if ch.problem_id is None:
            continue
        summary = _problem_summary(vault, ch.problem_id)
        if summary is None:
            continue
        summary["entries"] = [e for e in summary["entries"] if e["paper_id"] != paper.id]
        challenge_mates[ch.id] = summary
    return templates.TemplateResponse(
        request,
        "paper_detail.html",
        {
            "nav": "papers",
            "paper": paper,
            "claim_relations": claim_relations,
            "challenge_mates": challenge_mates,
        },
    )


@app.get("/problems", response_class=HTMLResponse)
def page_problems(request: Request) -> HTMLResponse:
    """共有課題の一覧（どの課題に誰が挑んでいるか）。"""
    vault = storage.load_vault()
    problems = [_problem_summary(vault, p.id) for p in vault.problems]
    return templates.TemplateResponse(
        request,
        "problems.html",
        {"nav": "problems", "problems": [p for p in problems if p is not None]},
    )


@app.get("/claims/{claim_id}", response_class=HTMLResponse)
def page_claim_detail(request: Request, claim_id: str) -> HTMLResponse:
    """クレーム詳細のパーマリンク。"""
    vault = storage.load_vault()
    paper, claim = _find_claim(vault, claim_id)
    return templates.TemplateResponse(
        request,
        "claim_detail.html",
        {
            "nav": "papers",
            "paper": paper,
            "claim": claim,
            "relations": _claim_relations(vault, claim_id),
            "questions": _claim_questions(vault, claim_id),
        },
    )
