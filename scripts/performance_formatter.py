from __future__ import annotations

from scripts.evidence_formatter import source_block
from scripts.intent import Evidence, QueryPlan


def format_department_performance(evidences: list[Evidence]) -> str:
    data = evidences[0].data
    department = data.get("department", "该部门")
    year = data.get("year", "该年度")
    average = data.get("department_average")
    members = data.get("members", [])
    counted_members = [item for item in members if int(item.get("review_count") or 0) > 0]
    record_count = sum(int(item.get("review_count") or 0) for item in counted_members)
    return (
        f"{department} {year} 年部门平均 KPI 为 {average}，"
        f"基于 {len(counted_members)} 名员工的 {record_count} 条绩效记录汇总。"
        "这是由个人绩效记录汇总得到的结果，不是独立部门绩效表。"
        f"\n\n{source_block(evidences)}"
    )


def format_performance_summary(plan: QueryPlan, evidences: list[Evidence]) -> str:
    if not evidences:
        return "我没有在当前数据源中找到相关绩效记录，因此不能确认答案。"
    if plan.params.get("year") is not None and plan.params.get("quarter") is None:
        values = [float(item.data["kpi_score"]) for item in evidences if item.data.get("kpi_score") is not None]
        if values:
            average = round(sum(values) / len(values), 2)
            name = evidences[0].data.get("name", plan.params.get("employee_name", "该员工"))
            year = plan.params["year"]
            details = "；".join(
                f"Q{item.data['quarter']} {item.data['kpi_score']}（{item.data.get('grade')}）"
                for item in evidences
            )
            return f"{name} {year} 年平均 KPI 为 {average}。季度明细：{details}。\n\n{source_block(evidences)}"
    lines = [evidence.content for evidence in evidences]
    return "\n".join(lines) + f"\n\n{source_block(evidences)}"
