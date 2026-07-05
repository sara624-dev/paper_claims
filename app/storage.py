"""JSON ストレージ層（Web アプリからは読み取り専用）。

書き込みは Claude Code（/paper-import スキル）が直接ファイルを編集して行うため、
このモジュールは読み取りと mtime ベースのキャッシュのみを持つ。外部からファイルが
更新されるとシグネチャが変わり、サーバ再起動なしで次のリクエストから反映される。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from . import config
from .models import Paper, Question, QuestionLink, Relation, Topic


def _read_json(path: Path, default: Any) -> Any:
    """JSON を読み込み、失敗時は ``default`` を返す。"""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, OSError):
        return default


def _data_signature() -> tuple:
    """データディレクトリの更新シグネチャを返す。

    papers/ 配下の (ファイル名, mtime) 一覧と relations.json / topics.json の
    mtime を束ねたタプル。どれかが変わればキャッシュを破棄する。
    """
    papers = config.papers_dir()
    entries: list[tuple[str, float]] = []
    if papers.is_dir():
        entries = sorted(
            (p.name, p.stat().st_mtime) for p in papers.iterdir() if p.suffix == ".json"
        )

    def _mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    return (
        str(config.DATA_DIR),
        tuple(entries),
        _mtime(config.relations_file()),
        _mtime(config.topics_file()),
        _mtime(config.questions_file()),
        _mtime(config.question_links_file()),
    )


@dataclass
class Vault:
    """読み込み済みデータ一式。壊れた/不正なファイルは読み飛ばし errors に記録する。"""

    papers: list[Paper] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    topics: list[Topic] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    question_links: list[QuestionLink] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def paper_by_id(self, paper_id: str) -> Paper | None:
        """ID で論文を引く。"""
        return next((p for p in self.papers if p.id == paper_id), None)

    def claim_paper(self, claim_id: str) -> Paper | None:
        """クレーム ID から所属論文を引く。"""
        return next((p for p in self.papers if any(c.id == claim_id for c in p.claims)), None)

    def question_by_id(self, question_id: str) -> Question | None:
        """ID で問いを引く。"""
        return next((q for q in self.questions if q.id == question_id), None)

    def links_for_question(self, question_id: str) -> list[QuestionLink]:
        """問いに紐づくリンク一覧を返す。"""
        return [link for link in self.question_links if link.question_id == question_id]

    def links_for_claim(self, claim_id: str) -> list[QuestionLink]:
        """クレームに紐づくリンク一覧を返す。"""
        return [link for link in self.question_links if link.claim_id == claim_id]


def _load_vault() -> Vault:
    """data/ から全データを読み込む（不正データは errors に積んで読み飛ばす）。"""
    vault = Vault()

    papers_dir = config.papers_dir()
    if papers_dir.is_dir():
        for path in sorted(papers_dir.glob("*.json")):
            raw = _read_json(path, None)
            if raw is None:
                vault.errors.append(f"{path.name}: JSON として読めない")
                continue
            try:
                paper = Paper.model_validate(raw)
            except ValidationError as e:
                vault.errors.append(f"{path.name}: {e.errors()[0]['msg']}")
                continue
            vault.papers.append(paper)
    # 新しい論文が上に来るように取り込み日降順
    vault.papers.sort(key=lambda p: p.imported_at, reverse=True)

    for raw in _read_json(config.relations_file(), {"relations": []}).get("relations", []):
        try:
            vault.relations.append(Relation.model_validate(raw))
        except ValidationError as e:
            vault.errors.append(f"relations.json: {e.errors()[0]['msg']}")

    for raw in _read_json(config.topics_file(), {"topics": []}).get("topics", []):
        try:
            vault.topics.append(Topic.model_validate(raw))
        except ValidationError as e:
            vault.errors.append(f"topics.json: {e.errors()[0]['msg']}")

    for raw in _read_json(config.questions_file(), {"questions": []}).get("questions", []):
        try:
            vault.questions.append(Question.model_validate(raw))
        except ValidationError as e:
            vault.errors.append(f"questions.json: {e.errors()[0]['msg']}")

    for raw in _read_json(config.question_links_file(), {"question_links": []}).get(
        "question_links", []
    ):
        try:
            vault.question_links.append(QuestionLink.model_validate(raw))
        except ValidationError as e:
            vault.errors.append(f"question_links.json: {e.errors()[0]['msg']}")

    return vault


_cache: tuple[tuple, Vault] | None = None


def load_vault() -> Vault:
    """全データを返す（シグネチャが変わっていなければキャッシュを返す）。"""
    global _cache
    sig = _data_signature()
    if _cache is not None and _cache[0] == sig:
        return _cache[1]
    vault = _load_vault()
    _cache = (sig, vault)
    return vault
