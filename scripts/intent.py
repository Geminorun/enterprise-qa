from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


SourceType = Literal["db", "kb", "hybrid", "unknown"]
OutputMode = Literal["summary", "list", "count", "table"]


@dataclass(frozen=True)
class QueryPlan:
    source_type: SourceType
    template: str
    params: dict[str, Any] = field(default_factory=dict)
    output_mode: OutputMode = "summary"
    needs_clarification: bool = False
    clarification_question: str | None = None


@dataclass(frozen=True)
class Evidence:
    kind: Literal["db", "kb", "system"]
    source: str
    content: str
    locator: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    evidences: list[Evidence]
    used_llm_polish: bool
