from pathlib import Path

from scripts.intent import QueryPlan
from scripts.query_templates import execute_db_plan


DB_PATH = Path("data/enterprise.db")


def test_employee_basic_department():
    evidence = execute_db_plan(
        DB_PATH,
        QueryPlan("db", "employee_basic", {"employee_name": "张三", "field": "department"}),
    )

    assert evidence[0].data["department"] == "研发部"
    assert "employees 表" in evidence[0].source


def test_employee_manager():
    evidence = execute_db_plan(DB_PATH, QueryPlan("db", "employee_manager", {"employee_name": "李四"}))

    assert evidence[0].data["manager_name"] == "CEO"


def test_employee_projects():
    evidence = execute_db_plan(DB_PATH, QueryPlan("db", "employee_projects", {"employee_name": "张三"}))
    project_ids = {item.data["project_id"] for item in evidence}

    assert project_ids == {"PRJ-001", "PRJ-002", "PRJ-003", "PRJ-004"}


def test_employee_projects_filters_by_project_status():
    evidence = execute_db_plan(DB_PATH, QueryPlan("db", "employee_projects", {"employee_name": "张三", "status": "active"}))
    project_ids = {item.data["project_id"] for item in evidence}

    assert project_ids == {"PRJ-001", "PRJ-003"}


def test_employee_projects_filters_by_project_status_list():
    evidence = execute_db_plan(
        DB_PATH,
        QueryPlan("db", "employee_projects", {"employee_name": "张三", "status": ["active", "planning"]}),
    )
    project_ids = {item.data["project_id"] for item in evidence}

    assert project_ids == {"PRJ-001", "PRJ-002", "PRJ-003"}


def test_department_members_filters_by_employee_status():
    evidence = execute_db_plan(DB_PATH, QueryPlan("db", "department_members", {"department": "研发部", "status": "resigned"}))
    members = evidence[0].data["members"]

    assert evidence[0].data["count"] == 1
    assert members[0]["name"] == "离职员工"


def test_project_members():
    evidence = execute_db_plan(DB_PATH, QueryPlan("db", "project_members", {"project_id": "PRJ-001"}))
    names = {item.data["employee_name"] for item in evidence}

    assert names == {"张三", "李四", "钱七"}


def test_attendance_stats():
    evidence = execute_db_plan(
        DB_PATH,
        QueryPlan(
            "db",
            "attendance_stats",
            {
                "employee_name": "张三",
                "status": "late",
                "date_range": {"start": "2026-02-01", "end": "2026-02-28"},
            },
            "count",
        ),
    )

    assert evidence[0].data["count"] == 2


def test_promotion_facts_for_wangwu():
    evidence = execute_db_plan(
        DB_PATH,
        QueryPlan("hybrid", "promotion_eligibility", {"employee_name": "王五", "from_level": "P5", "to_level": "P6"}),
    )
    combined = {item.source: item.data for item in evidence}

    assert combined["employees 表"]["level"] == "P5"
    assert combined["performance_reviews 表"]["average_kpi"] == 80.0
    assert combined["project_members 表"]["project_count"] == 1


def test_promotion_facts_include_review_details():
    evidence = execute_db_plan(
        DB_PATH,
        QueryPlan("hybrid", "promotion_eligibility", {"employee_name": "张三", "from_level": "P5", "to_level": "P6"}),
    )
    combined = {item.source: item.data for item in evidence}

    assert [item["quarter"] for item in combined["performance_reviews 表"]["reviews"]] == [1, 2, 3, 4]


def test_promotion_facts_count_only_lead_or_core_projects():
    evidence = execute_db_plan(
        DB_PATH,
        QueryPlan("hybrid", "promotion_eligibility", {"employee_name": "钱七", "from_level": "P5", "to_level": "P6"}),
    )
    combined = {item.source: item.data for item in evidence}

    assert combined["project_members 表"]["project_count"] == 0
    assert all(item["role"] in {"lead", "core"} for item in combined["project_members 表"]["projects"])


def test_performance_summary_filters_by_quarter():
    evidence = execute_db_plan(
        DB_PATH,
        QueryPlan("db", "performance_summary", {"employee_name": "张三", "year": 2025, "quarter": 2}),
    )

    assert [item.data["quarter"] for item in evidence] == [2]
    assert evidence[0].data["kpi_score"] == 92


def test_department_projects_can_return_active_and_planning_projects_without_department():
    evidence = execute_db_plan(DB_PATH, QueryPlan("db", "department_projects", {"status": ["active", "planning"]}))
    project_ids = {item.data["project_id"] for item in evidence}

    assert project_ids == {"PRJ-001", "PRJ-002", "PRJ-003"}
