from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any

from scripts.intent import Evidence, QueryPlan


EMPLOYEE_BASIC_FIELDS = {"department", "email", "level", "hire_date", "status", "name"}


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _employee_filter(params: dict[str, Any]) -> tuple[str, str]:
    if "employee_id" in params:
        return "e.employee_id = ?", str(params["employee_id"])
    return "e.name = ?", str(params["employee_name"])


def execute_db_plan(db_path: Path, plan: QueryPlan) -> list[Evidence]:
    with _connect(db_path) as conn:
        if plan.template == "employee_basic":
            return _employee_basic(conn, plan)
        if plan.template == "employee_manager":
            return _employee_manager(conn, plan)
        if plan.template == "department_members":
            return _department_members(conn, plan)
        if plan.template == "employee_projects":
            return _employee_projects(conn, plan)
        if plan.template == "department_projects":
            return _department_projects(conn, plan)
        if plan.template == "project_members":
            return _project_members(conn, plan)
        if plan.template == "attendance_stats":
            return _attendance_stats(conn, plan)
        if plan.template == "performance_summary":
            return _performance_summary(conn, plan)
        if plan.template == "department_performance_summary":
            return _department_performance_summary(conn, plan)
        if plan.template == "promotion_eligibility":
            return _promotion_facts(conn, plan)
    return []


def _employee_basic(conn: sqlite3.Connection, plan: QueryPlan) -> list[Evidence]:
    field = str(plan.params["field"])
    if field not in EMPLOYEE_BASIC_FIELDS:
        return []

    condition, value = _employee_filter(plan.params)
    row = conn.execute(
        f"SELECT employee_id, name, {field} FROM employees e WHERE {condition} AND e.status = 'active'",
        (value,),
    ).fetchone()
    if row is None:
        return []
    return [
        Evidence(
            kind="db",
            source="employees 表",
            locator=f"employee_id: {row['employee_id']}",
            content=f"{row['name']} 的 {field} 是 {row[field]}",
            data=dict(row),
        )
    ]


def _employee_manager(conn: sqlite3.Connection, plan: QueryPlan) -> list[Evidence]:
    condition, value = _employee_filter(plan.params)
    row = conn.execute(
        f"""
        SELECT e.employee_id, e.name, m.employee_id AS manager_id, m.name AS manager_name
        FROM employees e
        LEFT JOIN employees m ON m.employee_id = e.manager_id
        WHERE {condition} AND e.status = 'active'
        """,
        (value,),
    ).fetchone()
    if row is None:
        return []
    return [
        Evidence(
            kind="db",
            source="employees 表",
            locator=f"employee_id: {row['employee_id']}",
            content=f"{row['name']} 的直属上级是 {row['manager_name']}",
            data=dict(row),
        )
    ]


def _department_members(conn: sqlite3.Connection, plan: QueryPlan) -> list[Evidence]:
    department = str(plan.params["department"])
    status = str(plan.params.get("status", "active"))
    rows = conn.execute(
        """
        SELECT employee_id, name, department, level
        FROM employees
        WHERE department = ? AND status = ?
        ORDER BY employee_id
        """,
        (department, status),
    ).fetchall()
    return [
        Evidence(
            kind="db",
            source="employees 表",
            locator=f"department: {department}, status: {status}",
            content=f"{department} {status} 员工 {len(rows)} 人",
            data={"department": department, "status": status, "count": len(rows), "members": [dict(row) for row in rows]},
        )
    ]


def _employee_projects(conn: sqlite3.Connection, plan: QueryPlan) -> list[Evidence]:
    condition, value = _employee_filter(plan.params)
    status = plan.params.get("status")
    status_clause = "AND p.status = ?" if status else ""
    args: tuple[Any, ...] = (value, status) if status else (value,)
    rows = conn.execute(
        f"""
        SELECT e.employee_id, e.name AS employee_name, p.project_id, p.name, p.status, pm.role, pm.join_date
        FROM employees e
        JOIN project_members pm ON pm.employee_id = e.employee_id
        JOIN projects p ON p.project_id = pm.project_id
        WHERE {condition} AND e.status = 'active' {status_clause}
        ORDER BY p.project_id
        """,
        args,
    ).fetchall()
    return [
        Evidence(
            kind="db",
            source="projects 表 + project_members 表",
            locator=f"project_id: {row['project_id']}",
            content=f"{row['employee_name']} 参与 {row['project_id']} {row['name']}，角色 {row['role']}",
            data=dict(row),
        )
        for row in rows
    ]


def _department_projects(conn: sqlite3.Connection, plan: QueryPlan) -> list[Evidence]:
    department = plan.params.get("department")
    status = plan.params.get("status")
    filters = ["e.status = 'active'"]
    args: list[Any] = []
    if department:
        filters.append("e.department = ?")
        args.append(str(department))
    if status:
        if isinstance(status, (list, tuple, set)):
            statuses = [str(item) for item in status]
        else:
            statuses = [str(status)]
        placeholders = ", ".join("?" for _ in statuses)
        filters.append(f"p.status IN ({placeholders})")
        args.extend(statuses)
    rows = conn.execute(
        f"""
        SELECT DISTINCT p.project_id, p.name, p.status
        FROM employees e
        JOIN project_members pm ON pm.employee_id = e.employee_id
        JOIN projects p ON p.project_id = pm.project_id
        WHERE {" AND ".join(filters)}
        ORDER BY p.project_id
        """,
        tuple(args),
    ).fetchall()
    return [
        Evidence(
            kind="db",
            source="projects 表 + project_members 表 + employees 表",
            content=f"{row['project_id']} {row['name']}",
            locator=f"project_id: {row['project_id']}",
            data=dict(row),
        )
        for row in rows
    ]


def _project_members(conn: sqlite3.Connection, plan: QueryPlan) -> list[Evidence]:
    if "project_id" in plan.params:
        condition = "p.project_id = ?"
        value = str(plan.params["project_id"])
    else:
        condition = "p.name = ?"
        value = str(plan.params["project_name"])

    rows = conn.execute(
        f"""
        SELECT p.project_id, p.name AS project_name, p.status, e.employee_id, e.name AS employee_name,
               e.department, pm.role, pm.join_date
        FROM projects p
        JOIN project_members pm ON pm.project_id = p.project_id
        JOIN employees e ON e.employee_id = pm.employee_id
        WHERE {condition} AND e.status = 'active'
        ORDER BY pm.role = 'lead' DESC, e.employee_id
        """,
        (value,),
    ).fetchall()
    return [
        Evidence(
            kind="db",
            source="projects 表 + project_members 表 + employees 表",
            content=f"{row['project_id']} {row['project_name']} 成员 {row['employee_name']}，角色 {row['role']}",
            locator=f"project_id: {row['project_id']}, employee_id: {row['employee_id']}",
            data=dict(row),
        )
        for row in rows
    ]


def _attendance_stats(conn: sqlite3.Connection, plan: QueryPlan) -> list[Evidence]:
    condition, value = _employee_filter(plan.params)
    date_range = plan.params.get("date_range", {})
    start = str(date_range.get("start", "2026-02-01"))
    end = str(date_range.get("end", "2026-02-28"))
    status = str(plan.params["status"])
    row = conn.execute(
        f"""
        SELECT e.employee_id, e.name, COUNT(a.id) AS count
        FROM employees e
        LEFT JOIN attendance a ON a.employee_id = e.employee_id
        WHERE {condition} AND a.status = ? AND a.date BETWEEN ? AND ?
        GROUP BY e.employee_id, e.name
        """,
        (value, status, start, end),
    ).fetchone()
    count = 0 if row is None else row["count"]
    name = str(plan.params.get("employee_name", plan.params.get("employee_id", "")))
    return [
        Evidence(
            kind="db",
            source="attendance 表 + employees 表",
            content=f"{name} 在 {start} 至 {end} 的 {status} 次数为 {count}",
            locator=None,
            data={"count": count, "start": start, "end": end, "status": status},
        )
    ]


def _performance_summary(conn: sqlite3.Connection, plan: QueryPlan) -> list[Evidence]:
    condition, value = _employee_filter(plan.params)
    year = plan.params.get("year")
    quarter = plan.params.get("quarter")
    filters = []
    args: list[Any] = [value]
    if year is not None:
        filters.append("AND pr.year = ?")
        args.append(year)
    if quarter is not None:
        filters.append("AND pr.quarter = ?")
        args.append(quarter)
    rows = conn.execute(
        f"""
        SELECT e.employee_id, e.name, pr.year, pr.quarter, pr.kpi_score, pr.grade
        FROM employees e
        JOIN performance_reviews pr ON pr.employee_id = e.employee_id
        WHERE {condition} {" ".join(filters)}
        ORDER BY pr.year, pr.quarter
        """,
        tuple(args),
    ).fetchall()
    return [
        Evidence(
            kind="db",
            source="performance_reviews 表 + employees 表",
            content=f"{row['year']} Q{row['quarter']} KPI {row['kpi_score']} grade {row['grade']}",
            locator=f"employee_id: {row['employee_id']}",
            data=dict(row),
        )
        for row in rows
    ]


def _department_performance_summary(conn: sqlite3.Connection, plan: QueryPlan) -> list[Evidence]:
    year = int(plan.params["year"])
    department = plan.params.get("department")
    if not department:
        row = conn.execute(
            "SELECT department FROM employees WHERE name = ? AND status = 'active'",
            (plan.params["employee_name"],),
        ).fetchone()
        if row is None:
            return []
        department = row["department"]

    rows = conn.execute(
        """
        SELECT e.employee_id, e.name, AVG(pr.kpi_score) AS average_kpi, COUNT(pr.id) AS review_count
        FROM employees e
        LEFT JOIN performance_reviews pr ON pr.employee_id = e.employee_id AND pr.year = ?
        WHERE e.department = ? AND e.status = 'active'
        GROUP BY e.employee_id, e.name
        ORDER BY e.employee_id
        """,
        (year, department),
    ).fetchall()
    values = [row["average_kpi"] for row in rows if row["average_kpi"] is not None]
    department_average = round(sum(values) / len(values), 2) if values else None
    return [
        Evidence(
            kind="db",
            source="employees 表 + performance_reviews 表",
            locator=f"department: {department}, year: {year}",
            content=f"{department} {year} 年绩效基于个人记录汇总",
            data={
                "department": department,
                "year": year,
                "department_average": department_average,
                "members": [dict(row) for row in rows],
            },
        )
    ]


def _promotion_facts(conn: sqlite3.Connection, plan: QueryPlan) -> list[Evidence]:
    if "employee_id" in plan.params:
        condition = "employee_id = ?"
        value = str(plan.params["employee_id"])
    else:
        condition = "name = ?"
        value = str(plan.params["employee_name"])
    employee = conn.execute(
        f"SELECT employee_id, name, level, hire_date FROM employees WHERE {condition} AND status = 'active'",
        (value,),
    ).fetchone()
    if employee is None:
        return []

    review_summary = conn.execute(
        "SELECT AVG(kpi_score) AS average_kpi, COUNT(id) AS review_count FROM performance_reviews WHERE employee_id = ?",
        (employee["employee_id"],),
    ).fetchone()
    review_rows = conn.execute(
        """
        SELECT year, quarter, kpi_score, grade
        FROM performance_reviews
        WHERE employee_id = ?
        ORDER BY year, quarter
        """,
        (employee["employee_id"],),
    ).fetchall()
    project_rows = conn.execute(
        """
        SELECT p.project_id, p.name, p.status, pm.role, pm.join_date
        FROM project_members pm
        JOIN projects p ON p.project_id = pm.project_id
        WHERE pm.employee_id = ? AND pm.role IN ('lead', 'core')
        ORDER BY p.project_id
        """,
        (employee["employee_id"],),
    ).fetchall()
    return [
        Evidence(
            kind="db",
            source="employees 表",
            content=f"{employee['name']} 当前职级 {employee['level']}",
            locator=f"employee_id: {employee['employee_id']}",
            data=dict(employee),
        ),
        Evidence(
            kind="db",
            source="performance_reviews 表",
            content=f"{employee['name']} 平均 KPI {review_summary['average_kpi']}",
            locator=f"employee_id: {employee['employee_id']}",
            data={**dict(review_summary), "reviews": [dict(row) for row in review_rows]},
        ),
        Evidence(
            kind="db",
            source="project_members 表",
            content=f"{employee['name']} 主导/核心参与项目数 {len(project_rows)}",
            locator=f"employee_id: {employee['employee_id']}",
            data={"project_count": len(project_rows), "projects": [dict(row) for row in project_rows]},
        ),
    ]
