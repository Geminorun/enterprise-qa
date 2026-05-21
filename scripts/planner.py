from __future__ import annotations

import json
import re
from typing import Any

from scripts.intent import QueryPlan
from scripts.llm_client import LlmClient


PLAN_PROMPT = """你是企业问答系统的查询规划器。你只能输出 JSON，不能输出 SQL。

数据源摘要：
- employees(employee_id, name, department, level, hire_date, manager_id, email, status)
- projects(project_id, name, lead_id, status, start_date, end_date, budget)
- project_members(project_id, employee_id, role, join_date)
- attendance(id, employee_id, date, status)
- performance_reviews(id, employee_id, year, quarter, kpi_score, grade)
- knowledge Markdown: hr_policies, promotion_rules, tech_docs, finance_rules, faq, meeting_notes

可选 template:
employee_basic, employee_manager, department_members, employee_projects, department_projects,
project_members, attendance_stats, performance_summary, department_performance_summary,
promotion_eligibility, kb_search, recent_events, unknown

输出字段：
source_type: db | kb | hybrid | unknown
template: 上方 template 之一
params: JSON object
output_mode: summary | list | count | table
needs_clarification: boolean
clarification_question: string or null

当前日期：2026-03-27。遇到“上个月”按 2026-02 计算。
"""


def parse_plan_json(content: str) -> QueryPlan:
    stripped = content.strip()
    match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
    if match:
        stripped = match.group(1).strip()

    data: dict[str, Any] = json.loads(stripped)
    return QueryPlan(
        source_type=data.get("source_type", "unknown"),
        template=data.get("template", "unknown"),
        params=data.get("params", {}),
        output_mode=data.get("output_mode", "summary"),
        needs_clarification=bool(data.get("needs_clarification", False)),
        clarification_question=data.get("clarification_question"),
    )


def plan_question(client: LlmClient, question: str, context: dict[str, Any] | None = None) -> QueryPlan:
    context_text = json.dumps(context or {}, ensure_ascii=False)
    content = client.chat(
        [
            {"role": "system", "content": PLAN_PROMPT},
            {"role": "user", "content": f"上下文：{context_text}\n问题：{question}"},
        ]
    )
    return parse_plan_json(content)
