from __future__ import annotations

import json
import re
from typing import Protocol

from scripts.date_utils import as_date, full_years_between
from scripts.evidence_formatter import sources, source_block
from scripts.intent import Evidence, QueryPlan
from scripts.llm_client import LlmClient, LlmError
from scripts.performance_formatter import format_department_performance, format_performance_summary
from scripts.project_formatter import format_project_collection, format_project_section
from scripts.promotion_rules_engine import format_promotion_answer


class ChatClient(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> str:
        ...


def _append_verified_sources(answer: str, evidences: list[Evidence]) -> str:
    body_lines = [line for line in answer.strip().splitlines() if not line.strip().startswith("> 来源：")]
    body = "\n".join(body_lines).strip()
    return f"{body}\n\n{source_block(evidences)}" if body else source_block(evidences)


def _clean_markdown_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^#{1,6}\s*", "", line)
    line = re.sub(r"^\s*[-*]\s*", "", line)
    line = line.replace("**", "").replace("`", "")
    if line.startswith("|") and line.endswith("|"):
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        line = " / ".join(cell for cell in cells if cell and set(cell) != {"-"})
    return line.strip()


def _is_table_data_line(line: str) -> bool:
    if not (line.startswith("|") and line.endswith("|")):
        return False
    cells = [cell.strip() for cell in line.strip("|").split("|")]
    if not cells or all(set(cell) <= {"-"} for cell in cells if cell):
        return False
    header_cells = {"决议", "说明", "负责人", "事项", "时间"}
    return not set(cells) <= header_cells


def _summarize_meeting_note(content: str) -> str:
    important_terms = ("ReMe", "智能问答", "AI 实验室", "技术委员会", "调薪", "期权", "晋升", "决议", "后续行动")
    structured_sections = ("决议事项", "后续行动")
    lines: list[str] = []
    in_structured_section = False
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped == "---" or set(stripped.replace("|", "").strip()) <= {"-"}:
            continue
        if stripped.startswith("#"):
            heading = _clean_markdown_line(stripped)
            in_structured_section = any(term in heading for term in structured_sections)
            line = heading
        else:
            line = _clean_markdown_line(stripped)
        if not line or set(line.replace(" ", "")) <= {"-"}:
            continue
        if len(lines) < 8 or any(term in line for term in important_terms) or (in_structured_section and _is_table_data_line(stripped)):
            if line not in lines:
                lines.append(line)
    if not lines:
        return content.strip()
    title = lines[0]
    details = "；".join(lines[1:])
    return f"{title}：{details}" if details else title


def _format_meeting_notes_answer(evidences: list[Evidence]) -> str:
    selected: dict[str, Evidence] = {}
    for evidence in evidences:
        if "meeting_notes/" not in evidence.source and "meeting_notes/" not in str(evidence.locator):
            continue
        key = evidence.locator or evidence.source
        current = selected.get(key)
        if current is None or evidence.data.get("recall") == "file":
            selected[key] = evidence
    summaries = [_summarize_meeting_note(item.content) for item in selected.values()]
    if not summaries:
        summaries = [item.content for item in evidences]
    return "会议纪要要点：\n" + "\n".join(f"- {item}" for item in summaries) + f"\n\n{source_block(evidences)}"


def _format_recent_events(question: str, plan: QueryPlan, evidences: list[Evidence]) -> str:
    meeting_evidences = [
        item for item in evidences if "meeting_notes/" in item.source or "meeting_notes/" in str(item.locator)
    ]
    project_evidences = [
        item for item in evidences if item.source.startswith("projects 表") and "project_id" in item.data
    ]
    sections: list[str] = []
    if meeting_evidences:
        meeting_answer = _format_meeting_notes_answer(meeting_evidences).split("> 来源：", 1)[0].strip()
        sections.append(meeting_answer)
    if project_evidences:
        sections.append(format_project_section(question, plan, project_evidences))
    if not sections:
        sections = [item.content for item in evidences]
    return "\n\n".join(sections) + f"\n\n{source_block(evidences)}"


def _employee_status_label(status: object) -> str:
    labels = {"active": "在职", "on_leave": "休假", "resigned": "离职"}
    return labels.get(str(status), str(status))


def _format_employee_manager(evidences: list[Evidence]) -> str:
    data = evidences[0].data
    employee_name = data.get("name", "该员工")
    manager_name = data.get("manager_name") or "未记录"
    manager_email = data.get("manager_email")
    if manager_email:
        return f"{employee_name}的直属上级是 {manager_name}，邮箱是 {manager_email}。\n\n{source_block(evidences)}"
    return f"{employee_name}的直属上级是 {manager_name}。\n\n{source_block(evidences)}"


def _format_attendance_policy_check(evidences: list[Evidence]) -> str:
    attendance = next((item for item in evidences if item.source == "attendance 表 + employees 表"), evidences[0])
    data = attendance.data
    name = data.get("name", "该员工")
    count = int(data.get("count") or 0)
    start = data.get("start")
    end = data.get("end")
    status = data.get("status")
    if status != "late":
        return (
            f"{name}在 {start} 至 {end} 的{status}记录为 {count} 次；"
            "当前仅支持对迟到扣款规则做确定性判断。"
            f"\n\n{source_block(evidences)}"
        )
    if count <= 3:
        result = f"未超过扣款线，月累计迟到 {count} 次属于 3 次以内，不扣款，口头提醒。"
    elif count <= 6:
        result = f"已超过扣款线，月累计迟到 {count} 次落在 4-6 次扣款档，每次扣款 50 元。"
    else:
        result = f"已超过扣款线，月累计迟到 {count} 次达到 7 次以上，视为旷工 1 天并通报批评。"
    return f"{name}在 {start} 至 {end} 迟到 {count} 次，{result}\n\n{source_block(evidences)}"


def _format_leave_entitlement_check(evidences: list[Evidence], current_date: str | None) -> str:
    employee = next((item for item in evidences if item.source == "employees 表"), None)
    if employee is None:
        return f"未找到该员工的入职日期，无法判定年假资格。\n\n{source_block(evidences)}"
    data = employee.data
    name = data.get("name", "该员工")
    hire_date = data.get("hire_date")
    leave_type = data.get("leave_type", "年假")
    today = as_date(current_date)
    full_years = full_years_between(hire_date, today)
    if leave_type != "年假":
        return f"{name}的{leave_type}资格当前没有专用判定规则。\n\n{source_block(evidences)}"
    if full_years is None:
        return f"{name}的入职日期不可解析，无法判定年假资格。\n\n{source_block(evidences)}"
    if full_years < 1:
        return (
            f"{name}入职日期是 {hire_date}，截至 {today.isoformat()} 未满 1 年，"
            "按年假制度没有年假。"
            f"\n\n{source_block(evidences)}"
        )
    days = min(15, 5 + full_years - 1)
    return (
        f"{name}入职日期是 {hire_date}，截至 {today.isoformat()} 已满 1 年，"
        f"按年假制度有年假，当前可按约 {days} 天估算。"
        f"\n\n{source_block(evidences)}"
    )


def format_fallback_answer(
    question: str,
    plan: QueryPlan,
    evidences: list[Evidence],
    *,
    current_date: str | None = None,
) -> str:
    if plan.template == "unknown" and plan.needs_clarification and plan.clarification_question:
        return plan.clarification_question
    if not evidences:
        return "我没有在当前数据源中找到相关信息，因此不能确认答案。"

    if plan.template == "employee_basic":
        field = str(plan.params.get("field", ""))
        data = evidences[0].data
        value = data.get(field)
        name = data.get("name", plan.params.get("employee_name", "该员工"))
        return f"{name}的{field}是 {value}。\n\n> 来源：{sources(evidences)}"

    if plan.template == "employee_manager":
        return _format_employee_manager(evidences)

    if plan.template == "department_members":
        data = evidences[0].data
        names = "、".join(item["name"] for item in data.get("members", []))
        label = _employee_status_label(data.get("status", "active"))
        return f"{data['department']}有 {data['count']} 名{label}员工：{names}。\n\n> 来源：{sources(evidences)}"

    if plan.template == "attendance_stats":
        data = evidences[0].data
        return f"查询时间范围内，匹配的考勤记录共有 {data['count']} 次。\n\n> 来源：{sources(evidences)}"

    if plan.template == "attendance_policy_check":
        return _format_attendance_policy_check(evidences)

    if plan.template == "leave_entitlement_check":
        return _format_leave_entitlement_check(evidences, current_date)

    if plan.template == "promotion_eligibility":
        return format_promotion_answer(plan, evidences, current_date)

    if plan.template == "department_performance_summary":
        return format_department_performance(evidences)

    if plan.template == "performance_summary":
        return format_performance_summary(plan, evidences)

    if plan.template == "recent_events":
        return _format_recent_events(question, plan, evidences)

    if plan.template in {"employee_projects", "department_projects", "project_members"}:
        return format_project_collection(question, plan, evidences)

    if plan.template == "kb_search":
        if any("meeting_notes/" in item.source or "meeting_notes/" in str(item.locator) for item in evidences):
            return _format_meeting_notes_answer(evidences)
        lines = [item.content for item in evidences]
        return "\n".join(lines) + f"\n\n> 来源：{sources(evidences)}"

    if any("meeting_notes/" in item.source or "meeting_notes/" in str(item.locator) for item in evidences):
        return _format_meeting_notes_answer(evidences)

    lines = [evidence.content for evidence in evidences]
    return "\n".join(lines) + f"\n\n> 来源：{sources(evidences)}"


def polish_answer(client: ChatClient, question: str, plan: QueryPlan, evidences: list[Evidence]) -> str:
    evidence_payload = [
        {"kind": item.kind, "source": item.source, "locator": item.locator, "content": item.content, "data": item.data}
        for item in evidences
    ]
    prompt = (
        "你是企业问答助手。只能使用 Evidence 中的事实回答，不得添加未给出的事实。"
        "答案必须自然、简洁，并保留来源。"
    )
    return client.chat(
        [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {"question": question, "plan": plan.__dict__, "evidence": evidence_payload},
                    ensure_ascii=False,
                ),
            },
        ]
    )


def build_answer(
    question: str,
    plan: QueryPlan,
    evidences: list[Evidence],
    *,
    client: LlmClient | None,
    answer_polish: bool,
    current_date: str | None = None,
) -> str:
    if plan.template in {
        "promotion_eligibility",
        "department_performance_summary",
        "attendance_policy_check",
        "leave_entitlement_check",
        "recent_events",
        "performance_summary",
        "employee_projects",
        "department_projects",
        "project_members",
    }:
        return format_fallback_answer(question, plan, evidences, current_date=current_date)

    if client is not None and answer_polish and evidences:
        try:
            polished = polish_answer(client, question, plan, evidences).strip()
            if polished:
                return _append_verified_sources(polished, evidences)
        except LlmError:
            pass
    return format_fallback_answer(question, plan, evidences, current_date=current_date)
