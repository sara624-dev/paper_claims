"""data/ のスキーマ検証 + 参照整合性チェック。

/paper-import スキルの書き込み後と CI から実行する。エラーがあれば一覧を表示して
exit 1 で終了する。スキーマ定義は app/models.py（単一の真実）に従う。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError

from app import config
from app.models import (
    CLAIM_ID_RE,
    SYMMETRIC_RELATION_TYPES,
    Paper,
    Question,
    QuestionLink,
    Relation,
    Topic,
)


def _fmt_validation_error(prefix: str, e: ValidationError) -> list[str]:
    return [f"{prefix}: {'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()]


def validate() -> list[str]:
    """全チェックを実行してエラーメッセージ一覧を返す（空なら合格）。"""
    errors: list[str] = []
    papers: list[Paper] = []
    relations: list[Relation] = []
    topics: list[Topic] = []

    # --- topics.json ---
    topics_raw = _read(config.topics_file(), {"topics": []}, errors)
    for i, raw in enumerate(topics_raw.get("topics", [])):
        try:
            topics.append(Topic.model_validate(raw))
        except ValidationError as e:
            errors += _fmt_validation_error(f"topics.json[{i}]", e)
    topic_ids = {t.id for t in topics}
    if len(topic_ids) != len(topics):
        errors.append("topics.json: topic id が重複している")

    # --- papers/*.json ---
    papers_dir = config.papers_dir()
    for path in sorted(papers_dir.glob("*.json")) if papers_dir.is_dir() else []:
        raw = _read(path, None, errors)
        if raw is None:
            continue
        try:
            paper = Paper.model_validate(raw)
        except ValidationError as e:
            errors += _fmt_validation_error(path.name, e)
            continue
        papers.append(paper)
        if path.stem != paper.id:
            errors.append(f"{path.name}: ファイル名と paper id が一致しない（{paper.id}）")
        for topic in paper.topics:
            if topic not in topic_ids:
                errors.append(f"{paper.id}: 未定義トピック {topic}（topics.json に追加すること）")
        for claim in paper.claims:
            m = CLAIM_ID_RE.match(claim.id)
            if m and m.group("paper_id") != paper.id:
                errors.append(f"{paper.id}: claim {claim.id} の接頭辞が paper id と一致しない")

    # claim ID の全体一意性
    claim_ids: set[str] = set()
    for paper in papers:
        for claim in paper.claims:
            if claim.id in claim_ids:
                errors.append(f"claim id が重複: {claim.id}")
            claim_ids.add(claim.id)

    # --- relations.json ---
    relations_raw = _read(config.relations_file(), {"relations": []}, errors)
    for i, raw in enumerate(relations_raw.get("relations", [])):
        try:
            relations.append(Relation.model_validate(raw))
        except ValidationError as e:
            errors += _fmt_validation_error(f"relations.json[{i}]", e)

    rel_ids: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()
    for rel in relations:
        if rel.id in rel_ids:
            errors.append(f"relation id が重複: {rel.id}")
        rel_ids.add(rel.id)
        for endpoint in (rel.from_id, rel.to_id):
            if endpoint not in claim_ids:
                errors.append(f"{rel.id}: 存在しない claim を参照している: {endpoint}")
        if rel.from_id == rel.to_id:
            errors.append(f"{rel.id}: 自己参照関係は不可")
        edge = (rel.from_id, rel.to_id, rel.type)
        if edge in seen_edges:
            errors.append(f"{rel.id}: 同一 (from, to, type) の関係が重複")
        seen_edges.add(edge)
        if rel.type in SYMMETRIC_RELATION_TYPES and rel.from_id > rel.to_id:
            errors.append(
                f"{rel.id}: {rel.type} は対称関係のため from < to（辞書順）に正規化すること"
            )

    # --- questions.json ---
    questions: list[Question] = []
    questions_raw = _read(config.questions_file(), {"questions": []}, errors)
    for i, raw in enumerate(questions_raw.get("questions", [])):
        try:
            questions.append(Question.model_validate(raw))
        except ValidationError as e:
            errors += _fmt_validation_error(f"questions.json[{i}]", e)
    question_by_id = {q.id: q for q in questions}
    if len(question_by_id) != len(questions):
        errors.append("questions.json: question id が重複している")
    for q in questions:
        for topic in q.topics:
            if topic not in topic_ids:
                errors.append(f"{q.id}: 未定義トピック {topic}（topics.json に追加すること）")

    # --- question_links.json ---
    links: list[QuestionLink] = []
    links_raw = _read(config.question_links_file(), {"question_links": []}, errors)
    for i, raw in enumerate(links_raw.get("question_links", [])):
        try:
            links.append(QuestionLink.model_validate(raw))
        except ValidationError as e:
            errors += _fmt_validation_error(f"question_links.json[{i}]", e)

    link_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    for link in links:
        if link.id in link_ids:
            errors.append(f"link id が重複: {link.id}")
        link_ids.add(link.id)
        if link.claim_id not in claim_ids:
            errors.append(f"{link.id}: 存在しない claim を参照している: {link.claim_id}")
        question = question_by_id.get(link.question_id)
        if question is None:
            errors.append(f"{link.id}: 存在しない question を参照している: {link.question_id}")
        elif question.type == "closed" and link.stance is None:
            errors.append(f"{link.id}: 判定型の問い {question.id} へのリンクは stance 必須")
        elif question.type == "open" and link.stance is not None:
            errors.append(f"{link.id}: 記述型の問い {question.id} へのリンクに stance は不可")
        pair = (link.question_id, link.claim_id)
        if pair in seen_pairs:
            errors.append(f"{link.id}: 同一 (question, claim) のリンクが重複")
        seen_pairs.add(pair)

    return errors


def _read(path: Path, default: object, errors: list[str]) -> object:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as e:
        errors.append(f"{path.name}: JSON parse error: {e}")
        return default


def main() -> int:
    errors = validate()
    if errors:
        print(f"NG: {len(errors)} 件のエラー")
        for msg in errors:
            print(f"  - {msg}")
        return 1
    print("OK: data/ はスキーマ・参照整合性ともに問題なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
