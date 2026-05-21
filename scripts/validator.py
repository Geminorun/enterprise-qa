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
    "recent_events": {"query", "date_range", "department", "status"},
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
    "promotion_eligibility": set(),
    "kb_search": {"query"},
    "recent_events": set(),
    "unknown": set(),
}

REQUIRED_ANY_PARAMS: dict[str, tuple[str, ...]] = {
    "employee_basic": ("employee_name", "employee_id"),
    "employee_manager": ("employee_name", "employee_id"),
    "employee_projects": ("employee_name", "employee_id"),
    "attendance_stats": ("employee_name", "employee_id"),
    "performance_summary": ("employee_name", "employee_id"),
    "promotion_eligibility": ("employee_name", "employee_id"),
    "department_performance_summary": ("employee_name", "department"),
    "project_members": ("project_id", "project_name"),
}

EMPLOYEE_FIELDS = {"department", "email", "level", "hire_date", "status", "name"}
PROJECT_STATUS_TEMPLATES = {"department_projects", "employee_projects", "recent_events"}
PROJECT_STATUS_ALIASES = {
    "active": "active",
    "在研": "active",
    "进行中": "active",
    "進行中": "active",
    "planning": "planning",
    "规划": "planning",
    "規劃": "planning",
    "计划": "planning",
    "計劃": "planning",
    "planned": "planning",
    "completed": "completed",
    "完成": "completed",
    "已完成": "completed",
    "done": "completed",
    "on_hold": "on_hold",
    "onhold": "on_hold",
    "on-hold": "on_hold",
    "on hold": "on_hold",
    "paused": "on_hold",
    "pause": "on_hold",
    "暂停": "on_hold",
    "暫停": "on_hold",
    "搁置": "on_hold",
    "擱置": "on_hold",
}
QUARTER_ALIASES = {
    "q1": 1,
    "1": 1,
    "第一季度": 1,
    "一季度": 1,
    "第1季度": 1,
    "q2": 2,
    "2": 2,
    "第二季度": 2,
    "二季度": 2,
    "第2季度": 2,
    "q3": 3,
    "3": 3,
    "第三季度": 3,
    "三季度": 3,
    "第3季度": 3,
    "q4": 4,
    "4": 4,
    "第四季度": 4,
    "四季度": 4,
    "第4季度": 4,
}
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


def _normalize_quarter(value: Any) -> int:
    if isinstance(value, int):
        quarter = value
    elif isinstance(value, str):
        key = value.strip().lower().replace(" ", "")
        quarter = QUARTER_ALIASES.get(key)
        if quarter is None:
            match = re.fullmatch(r"q?([1-4])", key)
            quarter = int(match.group(1)) if match else None
    else:
        quarter = None

    if quarter not in {1, 2, 3, 4}:
        raise PlanValidationError(f"不支持的季度：{value}")
    return quarter


def _normalize_project_status(value: Any) -> str | list[str]:
    if isinstance(value, (list, tuple, set)):
        return [_normalize_project_status_item(item) for item in value]
    return _normalize_project_status_item(value)


def _normalize_project_status_item(value: Any) -> str:
    if not isinstance(value, str):
        raise PlanValidationError(f"不支持的项目状态：{value}")
    key = value.strip().lower().replace("_", " ")
    normalized = PROJECT_STATUS_ALIASES.get(key)
    if normalized is None:
        raise PlanValidationError(f"不支持的项目状态：{value}")
    return normalized


def _normalize_params(plan: QueryPlan) -> dict[str, Any]:
    params = dict(plan.params)
    if plan.template == "performance_summary" and "quarter" in params:
        params["quarter"] = _normalize_quarter(params["quarter"])
    if plan.template in PROJECT_STATUS_TEMPLATES and "status" in params:
        params["status"] = _normalize_project_status(params["status"])
    return params


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

    required_any = REQUIRED_ANY_PARAMS.get(plan.template, ())
    if required_any and not any(name in plan.params for name in required_any):
        names = " 或 ".join(required_any)
        raise PlanValidationError(f"缺少必要定位参数：{names}")

    if _contains_unsafe_value(plan.params):
        raise PlanValidationError("疑似不安全输入，已拒绝执行")

    params = _normalize_params(plan)

    if plan.template == "employee_basic":
        field = params.get("field")
        if field not in EMPLOYEE_FIELDS:
            raise PlanValidationError(f"不支持的员工字段：{field}")

    if params != plan.params:
        return QueryPlan(
            source_type=plan.source_type,
            template=plan.template,
            params=params,
            output_mode=plan.output_mode,
            needs_clarification=plan.needs_clarification,
            clarification_question=plan.clarification_question,
        )
    return plan
