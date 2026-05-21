from __future__ import annotations

import re
from typing import Any

from scripts.intent import QueryPlan


class PlanValidationError(ValueError):
    pass


SAFE_TEMPLATES: dict[str, set[str]] = {
    "employee_basic": {"employee_name", "employee_id", "field"},
    "employee_manager": {"employee_name", "employee_id"},
    "department_members": {"department", "status"},
    "employee_projects": {"employee_name", "employee_id", "status"},
    "department_projects": {"department", "status"},
    "project_members": {"project_id", "project_name"},
    "attendance_stats": {"employee_name", "employee_id", "date_range", "status"},
    "performance_summary": {"employee_name", "employee_id", "year", "quarter"},
    "department_performance_summary": {"employee_name", "department", "year", "scope"},
    "promotion_eligibility": {"employee_name", "employee_id", "from_level", "to_level"},
    "kb_search": {"query", "topic"},
    "recent_events": {"query", "date_range"},
    "unknown": {"reason"},
}

REQUIRED_PARAMS: dict[str, set[str]] = {
    "employee_basic": {"field"},
    "employee_manager": set(),
    "department_members": {"department"},
    "employee_projects": set(),
    "department_projects": set(),
    "project_members": set(),
    "attendance_stats": {"status"},
    "performance_summary": set(),
    "department_performance_summary": {"year"},
    "promotion_eligibility": {"employee_name"},
    "kb_search": {"query"},
    "recent_events": set(),
    "unknown": set(),
}

EMPLOYEE_FIELDS = {"department", "email", "level", "hire_date", "status", "name"}
UNSAFE_PATTERN = re.compile(
    r"\b(select|insert|update|delete|drop|alter|create|pragma|union)\b|--|;|'='|'1'='1",
    re.IGNORECASE,
)


def _contains_unsafe_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(UNSAFE_PATTERN.search(value))
    if isinstance(value, dict):
        return any(_contains_unsafe_value(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_unsafe_value(item) for item in value)
    return False


def validate_plan(plan: QueryPlan) -> QueryPlan:
    if plan.template not in SAFE_TEMPLATES:
        raise PlanValidationError(f"不支持的查询模板：{plan.template}")

    allowed = SAFE_TEMPLATES[plan.template]
    unexpected = set(plan.params) - allowed
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise PlanValidationError(f"查询参数不被允许：{names}")

    missing = REQUIRED_PARAMS[plan.template] - set(plan.params)
    if missing:
        names = ", ".join(sorted(missing))
        raise PlanValidationError(f"缺少必要参数：{names}")

    if _contains_unsafe_value(plan.params):
        raise PlanValidationError("疑似不安全输入，已拒绝执行")

    if plan.template == "employee_basic":
        field = plan.params.get("field")
        if field not in EMPLOYEE_FIELDS:
            raise PlanValidationError(f"不支持的员工字段：{field}")

    return plan
