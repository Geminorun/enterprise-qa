from __future__ import annotations

from scripts.evidence_formatter import source_block
from scripts.intent import Evidence, QueryPlan


REASON_INTENTS = {"reason_query", "reason", "why"}


def is_reason_query(question: str, plan: QueryPlan | None = None) -> bool:
    if plan is not None:
        intent = str(plan.params.get("intent", "")).strip().lower()
        if intent in REASON_INTENTS:
            return True
    return any(word in question for word in ("为什么", "原因", "为何", "why"))


def project_missing_reason_lines(evidences: list[Evidence]) -> list[str]:
    return [
        f"- {item.data.get('project_id')} {item.data.get('name') or item.data.get('project_name')} 当前状态为 {item.data.get('status')}，"
        "当前数据源未提供暂停原因，因此不能确认为什么暂停。"
        for item in evidences
        if item.data.get("status") == "on_hold"
    ]


def format_project_section(question: str, plan: QueryPlan, evidences: list[Evidence]) -> str:
    reason_lines = project_missing_reason_lines(evidences) if is_reason_query(question, plan) else []
    lines = reason_lines or [
        f"- {item.data['project_id']} {item.data['name']}：{item.data.get('status', '未知状态')}"
        for item in evidences
    ]
    return "相关项目：\n" + "\n".join(lines)


def format_project_collection(question: str, plan: QueryPlan, evidences: list[Evidence]) -> str:
    if not evidences:
        return "我没有在当前数据源中找到相关项目信息，因此不能确认答案。"
    if is_reason_query(question, plan) and any(item.data.get("status") == "on_hold" for item in evidences):
        lines = project_missing_reason_lines(evidences)
        return "\n".join(lines) + f"\n\n{source_block(evidences)}"

    if plan.output_mode == "count":
        noun = "个项目" if plan.template != "project_members" else "名成员"
        header = f"共找到 {len(evidences)} {noun}。"
    else:
        header = "相关项目如下：" if plan.template != "project_members" else "相关成员如下："

    if plan.template == "employee_projects":
        lines = [f"- {item.data['project_id']} {item.data['name']}：{item.data['role']}" for item in evidences]
    elif plan.template == "project_members":
        lines = [f"- {item.data['employee_id']} {item.data['employee_name']}：{item.data['role']}" for item in evidences]
    else:
        lines = [f"- {item.data['project_id']} {item.data['name']}：{item.data.get('status', '未知状态')}" for item in evidences]
    return header + "\n" + "\n".join(lines) + f"\n\n{source_block(evidences)}"
