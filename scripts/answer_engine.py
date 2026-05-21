from __future__ import annotations

import json
from typing import Protocol

from scripts.intent import Evidence, QueryPlan
from scripts.llm_client import LlmClient, LlmError


class ChatClient(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> str:
        ...


def _sources(evidences: list[Evidence]) -> str:
    parts: list[str] = []
    for evidence in evidences:
        locator = f" ({evidence.locator})" if evidence.locator else ""
        parts.append(f"{evidence.source}{locator}")
    return " + ".join(dict.fromkeys(parts))


def format_fallback_answer(question: str, plan: QueryPlan, evidences: list[Evidence]) -> str:
    if plan.needs_clarification and plan.clarification_question:
        return plan.clarification_question
    if not evidences:
        return "我没有在当前数据源中找到相关信息，因此不能确认答案。"

    if plan.template == "employee_basic":
        field = str(plan.params.get("field", ""))
        data = evidences[0].data
        value = data.get(field)
        name = data.get("name", plan.params.get("employee_name", "该员工"))
        return f"{name}的{field}是 {value}。\n\n> 来源：{_sources(evidences)}"

    if plan.template == "department_members":
        data = evidences[0].data
        names = "、".join(item["name"] for item in data.get("members", []))
        return f"{data['department']}有 {data['count']} 名在职员工：{names}。\n\n> 来源：{_sources(evidences)}"

    if plan.template == "attendance_stats":
        data = evidences[0].data
        return f"查询时间范围内，匹配的考勤记录共有 {data['count']} 次。\n\n> 来源：{_sources(evidences)}"

    if plan.template == "employee_projects":
        lines = [f"- {item.data['project_id']} {item.data['name']}：{item.data['role']}" for item in evidences]
        return "相关项目如下：\n" + "\n".join(lines) + f"\n\n> 来源：{_sources(evidences)}"

    if plan.template == "kb_search":
        lines = [item.content for item in evidences]
        return "\n".join(lines) + f"\n\n> 来源：{_sources(evidences)}"

    lines = [evidence.content for evidence in evidences]
    return "\n".join(lines) + f"\n\n> 来源：{_sources(evidences)}"


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
) -> str:
    if client is not None and answer_polish and evidences:
        try:
            polished = polish_answer(client, question, plan, evidences).strip()
            if polished and "来源" in polished:
                return polished
        except LlmError:
            pass
    return format_fallback_answer(question, plan, evidences)
