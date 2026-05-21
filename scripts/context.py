from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.intent import QueryPlan


def load_context(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_context(path: Path | None, plan: QueryPlan) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"last_template": plan.template, "last_params": plan.params}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
