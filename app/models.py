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

# 問いの型: closed = 判定型（yes/no）/ open = 記述型（what/how）
QUESTION_TYPES = ("closed", "open")

# 問いのライフサイクル。取り込み時の回答性判定は open のみが対象
QUESTION_STATUSES = ("open", "settled", "archived")

# 問いへの立場（判定型の問いのみ。記述型は answer_ja が答えそのもの）
STANCES = ("affirms", "denies", "qualifies")

# 表示用の日本語ラベル（テンプレート・フロント JS の両方がここに従う）
RELATION_LABELS_JA = {
    "supports": "支持",
    "contradicts": "反証",
    "same_as": "同一主張",
    "extends": "拡張",
}
KIND_LABELS_JA = {"experimental": "実験的", "theoretical": "理論的", "opinion": "見解"}
CONFIDENCE_LABELS_JA = {"high": "高", "medium": "中", "low": "低"}
QUESTION_TYPE_LABELS_JA = {"closed": "判定型", "open": "記述型"}
STANCE_LABELS_JA = {"affirms": "肯定", "denies": "否定", "qualifies": "条件付き"}
QUESTION_STATUS_LABELS_JA = {"open": "探究中", "settled": "決着", "archived": "保留"}

# ===== ID 形式 =====

PAPER_ID_RE = re.compile(r"^(arxiv-[0-9]{4}\.[0-9]{4,5}|pdf-[a-z0-9][a-z0-9-]*)$")
CLAIM_ID_RE = re.compile(r"^(?P<paper_id>.+)-c(?P<seq>[0-9]{2})$")
RELATION_ID_RE = re.compile(r"^rel-[0-9]{4}$")
TOPIC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
QUESTION_ID_RE = re.compile(r"^q-[0-9]{2}$")
QUESTION_LINK_ID_RE = re.compile(r"^ql-[0-9]{4}$")

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
    tags: list[str] = Field(default_factory=list)  # 照合スコープ用の細粒度タグ（kebab-case）
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

    @field_validator("tags")
    @classmethod
    def _valid_tags(cls, v: list[str]) -> list[str]:
        for tag in v:
            if not TOPIC_ID_RE.match(tag):
                raise ValueError(f"tag が kebab-case slug でない: {tag}")
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


class Question(BaseModel):
    """ユーザーが立てた問い。クレームが answer_ja 付きでマッピングされる。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    text_ja: str
    type: str  # closed（判定型）/ open（記述型）
    status: str = "open"  # open（探究中）/ settled（決着）/ archived（保留）
    topics: list[str] = Field(default_factory=list)
    notes: str = ""
    created_at: str

    @field_validator("id")
    @classmethod
    def _valid_id(cls, v: str) -> str:
        if not QUESTION_ID_RE.match(v):
            raise ValueError(f"question id が q-NN 形式でない: {v}")
        return v

    @field_validator("text_ja")
    @classmethod
    def _text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text_ja は必須")
        return v

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in QUESTION_TYPES:
            raise ValueError(f"type は {QUESTION_TYPES} のいずれか: {v}")
        return v

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        if v not in QUESTION_STATUSES:
            raise ValueError(f"status は {QUESTION_STATUSES} のいずれか: {v}")
        return v

    @field_validator("topics")
    @classmethod
    def _topics_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("topics は1件以上必須（取り込み時の照合スコープに使う）")
        return v


class QuestionLink(BaseModel):
    """問い↔クレームのリンク。answer_ja =「このクレームが問いに与える答え」。

    stance は判定型（closed）の問いのみ持つ（validate.py が問いの type と突き合わせる）。
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    question_id: str
    claim_id: str
    answer_ja: str
    stance: str | None = None
    rationale_ja: str  # なぜこのクレームがこの問いに答えると判断したか。必須
    confidence: str
    created_at: str

    @field_validator("id")
    @classmethod
    def _valid_id(cls, v: str) -> str:
        if not QUESTION_LINK_ID_RE.match(v):
            raise ValueError(f"question link id が ql-NNNN 形式でない: {v}")
        return v

    @field_validator("answer_ja", "rationale_ja")
    @classmethod
    def _not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("answer_ja / rationale_ja は必須")
        return v

    @field_validator("stance")
    @classmethod
    def _valid_stance(cls, v: str | None) -> str | None:
        if v is not None and v not in STANCES:
            raise ValueError(f"stance は {STANCES} のいずれか（または省略）: {v}")
        return v

    @field_validator("confidence")
    @classmethod
    def _valid_confidence(cls, v: str) -> str:
        if v not in CONFIDENCES:
            raise ValueError(f"confidence は {CONFIDENCES} のいずれか: {v}")
        return v
