from __future__ import annotations

import json
from json import JSONDecodeError
import re
from typing import Any

from scripts.intent import QueryPlan
from scripts.llm_client import LlmClient, LlmError


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

template 参数约束：
- employee_basic params: employee_name 或 employee_id 必填；field 必填且只能是 department/email/level/hire_date/status/name。
- employee_manager params: employee_name 或 employee_id 必填。
- department_members params: department 必填；status 可选，员工状态优先使用 active/resigned；“离职”映射为 resigned。
- employee_projects params: employee_name 或 employee_id 必填；status 可选，项目状态优先使用 active/planning/completed/on_hold。
- department_projects params: department 可选；status 可选，优先使用 active/planning/completed/on_hold，支持单个状态或状态数组。
- project_members params: project_id 或 project_name 必填。
- attendance_stats params: employee_name 或 employee_id 必填；status 必填；date_range 可选，格式 {"start":"YYYY-MM-DD","end":"YYYY-MM-DD"}。
- performance_summary params: employee_name 或 employee_id 必填；year/quarter 可选；quarter 优先输出 1-4 的整数。
- department_performance_summary params: department 或 employee_name 必填；year 必填；scope 可选。
- promotion_eligibility params: employee_name 或 employee_id 必填；from_level/to_level 可选。
- kb_search params: query 必填，topic 可选。
- recent_events params: query/date_range/department/status 可选；未给 status 时默认查询 active/planning 项目；“暂停/paused”映射为 on_hold。
- unknown params: reason 可选。

字段映射示例：
- “张三的部门是什么？” -> {"source_type":"db","template":"employee_basic","params":{"employee_name":"张三","field":"department"},"output_mode":"summary"}
- “李四的上级是谁？” -> {"source_type":"db","template":"employee_manager","params":{"employee_name":"李四"},"output_mode":"summary"}
- “PRJ-001 有哪些成员？” -> {"source_type":"db","template":"project_members","params":{"project_id":"PRJ-001"},"output_mode":"list"}
- “张三 2 月迟到几次？” -> {"source_type":"db","template":"attendance_stats","params":{"employee_name":"张三","status":"late","date_range":{"start":"2026-02-01","end":"2026-02-28"}},"output_mode":"count"}
- “张三 2025 Q2 绩效如何？” -> {"source_type":"db","template":"performance_summary","params":{"employee_name":"张三","year":2025,"quarter":2},"output_mode":"summary"}
- “年假怎么计算？” -> {"source_type":"kb","template":"kb_search","params":{"query":"年假怎么计算"},"output_mode":"summary"}

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

    try:
        data: dict[str, Any] = json.loads(stripped)
    except JSONDecodeError as exc:
        raise LlmError(f"无效 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise LlmError("无效 JSON：顶层结构必须是 object")
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
