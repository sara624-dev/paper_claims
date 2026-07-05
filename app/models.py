"""ドメインモデルと選択肢の単一の真実。

JSON に保存される構造はここで決まる。kind / relation type / confidence の
選択肢を変えるときはここを直す（validate.py・API・スキルが全部ここに従う）。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ===== 選択肢（enum）=====

# クレーム種別: 実験的 / 理論的 / 見解・主観
CLAIM_KINDS = ("experimental", "theoretical", "opinion")

# 関係種別: from が to を 支持 / 反証 / 同一主張 / 拡張 する
RELATION_TYPES = ("supports", "contradicts", "same_as", "extends")

# same_as のみ対称関係 → from < to（辞書順）に正規化して保存する
SYMMETRIC_RELATION_TYPES = ("same_as",)

# 信頼度（kb の frontmatter 慣習に合わせる）
CONFIDENCES = ("high", "medium", "low")

# 論文ソース種別
PAPER_SOURCES = ("arxiv", "pdf")

# 表示用の日本語ラベル（テンプレート・フロント JS の両方がここに従う）
RELATION_LABELS_JA = {
    "supports": "支持",
    "contradicts": "反証",
    "same_as": "同一主張",
    "extends": "拡張",
}
KIND_LABELS_JA = {"experimental": "実験的", "theoretical": "理論的", "opinion": "見解"}
CONFIDENCE_LABELS_JA = {"high": "高", "medium": "中", "low": "低"}

# ===== ID 形式 =====

PAPER_ID_RE = re.compile(r"^(arxiv-[0-9]{4}\.[0-9]{4,5}|pdf-[a-z0-9][a-z0-9-]*)$")
CLAIM_ID_RE = re.compile(r"^(?P<paper_id>.+)-c(?P<seq>[0-9]{2})$")
RELATION_ID_RE = re.compile(r"^rel-[0-9]{4}$")
TOPIC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

JST = timezone(timedelta(hours=9))


def now_iso() -> str:
    """現在時刻（JST）を秒精度の ISO 文字列で返す。"""
    return datetime.now(JST).isoformat(timespec="seconds")


# ===== モデル =====


class Metric(BaseModel):
    """クレームを裏付ける数値結果（ベースライン込み）。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    value: str
    baseline: str = ""


class Evidence(BaseModel):
    """クレームの根拠（実験条件・データセット・数値・出典箇所）。"""

    model_config = ConfigDict(extra="forbid")

    conditions: str = ""
    datasets: list[str] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    section: str  # 出典セクション（プロベナンス原則により必須）
    pages: str = ""

    @field_validator("section")
    @classmethod
    def _section_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("evidence.section は必須（出典箇所のないクレームは保存しない）")
        return v


class Claim(BaseModel):
    """論文が主張していること1件。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    summary_ja: str
    quote: str  # 原文引用（プロベナンス原則により必須）
    kind: str
    evidence: Evidence
    confidence: str
    confidence_note: str = ""
    created_at: str

    @field_validator("id")
    @classmethod
    def _valid_id(cls, v: str) -> str:
        if not CLAIM_ID_RE.match(v):
            raise ValueError(f"claim id が <paper_id>-cNN 形式でない: {v}")
        return v

    @field_validator("summary_ja", "quote")
    @classmethod
    def _not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("summary_ja / quote は必須")
        return v

    @field_validator("kind")
    @classmethod
    def _valid_kind(cls, v: str) -> str:
        if v not in CLAIM_KINDS:
            raise ValueError(f"kind は {CLAIM_KINDS} のいずれか: {v}")
        return v

    @field_validator("confidence")
    @classmethod
    def _valid_confidence(cls, v: str) -> str:
        if v not in CONFIDENCES:
            raise ValueError(f"confidence は {CONFIDENCES} のいずれか: {v}")
        return v


class Paper(BaseModel):
    """論文1件（メタデータ + その論文のクレーム）。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    source: str
    arxiv_id: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str = ""
    url: str = ""
    abstract: str = ""
    topics: list[str] = Field(default_factory=list)
    imported_at: str
    notes: str = ""
    claims: list[Claim] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _valid_id(cls, v: str) -> str:
        if not PAPER_ID_RE.match(v):
            raise ValueError(f"paper id が arxiv-NNNN.NNNNN / pdf-<slug> 形式でない: {v}")
        return v

    @field_validator("source")
    @classmethod
    def _valid_source(cls, v: str) -> str:
        if v not in PAPER_SOURCES:
            raise ValueError(f"source は {PAPER_SOURCES} のいずれか: {v}")
        return v

    @field_validator("title")
    @classmethod
    def _title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title は必須")
        return v


class Relation(BaseModel):
    """クレーム間の関係1件。向きは「from が to を支持/反証/拡張する」。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    from_id: str = Field(alias="from")
    to_id: str = Field(alias="to")
    type: str
    rationale_ja: str  # 関係判断の根拠（実験条件の差異など）。必須
    confidence: str
    created_at: str

    @field_validator("id")
    @classmethod
    def _valid_id(cls, v: str) -> str:
        if not RELATION_ID_RE.match(v):
            raise ValueError(f"relation id が rel-NNNN 形式でない: {v}")
        return v

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in RELATION_TYPES:
            raise ValueError(f"type は {RELATION_TYPES} のいずれか: {v}")
        return v

    @field_validator("rationale_ja")
    @classmethod
    def _rationale_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("rationale_ja は必須（判断根拠のない関係は保存しない）")
        return v

    @field_validator("confidence")
    @classmethod
    def _valid_confidence(cls, v: str) -> str:
        if v not in CONFIDENCES:
            raise ValueError(f"confidence は {CONFIDENCES} のいずれか: {v}")
        return v


class Topic(BaseModel):
    """クレーム・論文を横断グルーピングするトピック。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    name_ja: str
    description: str = ""
    created_at: str

    @field_validator("id")
    @classmethod
    def _valid_id(cls, v: str) -> str:
        if not TOPIC_ID_RE.match(v):
            raise ValueError(f"topic id が kebab-case slug でない: {v}")
        return v
