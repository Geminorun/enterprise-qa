import pytest

from scripts.intent import QueryPlan
from scripts.validator import PlanValidationError, validate_plan


def test_validate_employee_projects_plan():
    plan = QueryPlan(
        source_type="db",
        template="employee_projects",
        params={"employee_name": "张三"},
        output_mode="list",
    )

    validated = validate_plan(plan)

    assert validated.template == "employee_projects"


def test_rejects_unknown_template():
    plan = QueryPlan(
        source_type="db",
        template="free_sql",
        params={},
        output_mode="list",
    )

    with pytest.raises(PlanValidationError, match="不支持的查询模板"):
        validate_plan(plan)


def test_rejects_sql_like_question_param():
    plan = QueryPlan(
        source_type="db",
        template="employee_basic",
        params={"employee_name": "SELECT * FROM users", "field": "department"},
        output_mode="summary",
    )

    with pytest.raises(PlanValidationError, match="疑似不安全输入"):
        validate_plan(plan)


def test_rejects_disallowed_employee_field():
    plan = QueryPlan(
        source_type="db",
        template="employee_basic",
        params={"employee_name": "张三", "field": "teacher"},
        output_mode="summary",
    )

    with pytest.raises(PlanValidationError, match="不支持的员工字段"):
        validate_plan(plan)


def test_rejects_employee_template_without_employee_locator():
    plan = QueryPlan(
        source_type="db",
        template="employee_projects",
        params={},
        output_mode="list",
    )

    with pytest.raises(PlanValidationError, match="缺少必要定位参数"):
        validate_plan(plan)


def test_rejects_project_members_without_project_locator():
    plan = QueryPlan(
        source_type="db",
        template="project_members",
        params={},
        output_mode="list",
    )

    with pytest.raises(PlanValidationError, match="缺少必要定位参数"):
        validate_plan(plan)


def test_accepts_department_projects_without_department():
    plan = QueryPlan(
        source_type="db",
        template="department_projects",
        params={"status": ["active", "planning"]},
        output_mode="list",
    )

    validated = validate_plan(plan)

    assert validated.params["status"] == ["active", "planning"]


def test_normalizes_project_status_aliases():
    plan = QueryPlan(
        source_type="db",
        template="department_projects",
        params={"department": "产品部", "status": "paused"},
        output_mode="list",
    )

    validated = validate_plan(plan)

    assert validated.params["status"] == "on_hold"


def test_accepts_promotion_eligibility_with_employee_id():
    plan = QueryPlan(
        source_type="db",
        template="promotion_eligibility",
        params={"employee_id": "EMP-003", "from_level": "P5", "to_level": "P6"},
        output_mode="summary",
    )

    validated = validate_plan(plan)

    assert validated.params["employee_id"] == "EMP-003"


def test_normalizes_performance_summary_quarter_text():
    plan = QueryPlan(
        source_type="db",
        template="performance_summary",
        params={"employee_name": "张三", "year": 2025, "quarter": "Q2"},
        output_mode="summary",
    )

    validated = validate_plan(plan)

    assert validated.params["quarter"] == 2


def test_rejects_invalid_performance_summary_quarter():
    plan = QueryPlan(
        source_type="db",
        template="performance_summary",
        params={"employee_name": "张三", "year": 2025, "quarter": "Q5"},
        output_mode="summary",
    )

    with pytest.raises(PlanValidationError, match="不支持的季度"):
        validate_plan(plan)
