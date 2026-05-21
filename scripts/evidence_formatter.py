from __future__ import annotations

from scripts.intent import Evidence


def sources(evidences: list[Evidence]) -> str:
    parts: list[str] = []
    for evidence in evidences:
        locator = f" ({evidence.locator})" if evidence.locator else ""
        parts.append(f"{evidence.source}{locator}")
    return " + ".join(dict.fromkeys(parts))


def source_block(evidences: list[Evidence]) -> str:
    return f"> 来源：{sources(evidences)}"
