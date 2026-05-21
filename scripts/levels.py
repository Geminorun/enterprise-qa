from __future__ import annotations

from typing import Any


LEVEL_SEQUENCE = ("P4", "P5", "P6", "P7", "P8", "P9", "P10")


def next_level(level: str) -> str | None:
    try:
        index = LEVEL_SEQUENCE.index(level)
    except ValueError:
        return None
    next_index = index + 1
    return LEVEL_SEQUENCE[next_index] if next_index < len(LEVEL_SEQUENCE) else None


def infer_promotion_levels(params: dict[str, Any], current_level: object) -> tuple[str, str]:
    from_level = str(params.get("from_level") or current_level or "未知职级")
    to_level = str(params.get("to_level") or next_level(from_level) or "目标职级")
    return from_level, to_level
