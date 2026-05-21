from __future__ import annotations

from datetime import date
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


def _source_block(evidences: list[Evidence]) -> str:
    return f"> 来源：{_sources(evidences)}"


def _append_verified_sources(answer: str, evidences: list[Evidence]) -> str:
    body_lines = [line for line in answer.strip().splitlines() if not line.strip().startswith("> 来源：")]
    body = "\n".join(body_lines).strip()
    return f"{body}\n\n{_source_block(evidences)}" if body else _source_block(evidences)


def _as_date(value: str | None) -> date:
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return date.today()


def _years_between(start: object, end: date) -> float | None:
    if not isinstance(start, str):
        return None
    try:
        start_date = date.fromisoformat(start)
    except ValueError:
        return None
    return round((end - start_date).days / 365.25, 1)


def _has_consecutive_kpi(reviews: list[dict], threshold: float, required_count: int) -> bool:
    best_run = 0
    current_run = 0
    previous_index: int | None = None
    for review in sorted(reviews, key=lambda item: (item.get("year", 0), item.get("quarter", 0))):
        try:
            quarter_index = int(review["year"]) * 4 + int(review["quarter"])
            kpi_score = float(review["kpi_score"])
        except (KeyError, TypeError, ValueError):
            continue
        if kpi_score >= threshold:
            current_run = current_run + 1 if previous_index is not None and quarter_index == previous_index + 1 else 1
            best_run = max(best_run, current_run)
        else:
            current_run = 0
        previous_index = quarter_index
    return best_run >= required_count


def _latest_annual_average(reviews: list[dict], fallback: object) -> float | None:
    by_year: dict[int, list[float]] = {}
    for review in reviews:
        try:
            by_year.setdefault(int(review["year"]), []).append(float(review["kpi_score"]))
        except (KeyError, TypeError, ValueError):
            continue
    if by_year:
        latest_year = max(by_year)
        values = by_year[latest_year]
        return round(sum(values) / len(values), 2)
    try:
        return float(fallback)
    except (TypeError, ValueError):
        return None


def _format_promotion_answer(plan: QueryPlan, evidences: list[Evidence], current_date: str | None) -> str:
    combined = {item.source: item.data for item in evidences}
    employee = combined.get("employees 表", {})
    reviews = combined.get("performance_reviews 表", {})
    projects = combined.get("project_members 表", {})
    name = str(employee.get("name", plan.params.get("employee_name", "该员工")))
    current_level = str(employee.get("level", "未知职级"))
    from_level = str(plan.params.get("from_level", current_level))
    to_level = str(plan.params.get("to_level", "目标职级"))

    failures: list[str] = []
    unknowns: list[str] = []
    checks: list[str] = []

    if current_level == to_level:
        failures.append(f"当前职级已是 {to_level}")
        checks.append(f"- 职级：不满足，当前职级已是 {to_level}，不是 {from_level} 候选人。")
    elif current_level != from_level:
        failures.append(f"当前职级是 {current_level}，不是 {from_level}")
        checks.append(f"- 职级：不满足，当前职级是 {current_level}，不是 {from_level}。")
    else:
        checks.append(f"- 职级：满足，当前职级是 {current_level}。")

    years = _years_between(employee.get("hire_date"), _as_date(current_date))
    if years is None:
        unknowns.append("缺少可解析的入职日期")
        checks.append("- 工作年限：待确认，缺少可解析的入职日期。")
    elif years >= 1:
        checks.append(f"- 工作年限：满足，入职约 {years} 年，要求入职满 1 年。")
    else:
        failures.append("入职未满 1 年")
        checks.append(f"- 工作年限：不满足，入职约 {years} 年，要求入职满 1 年。")

    review_details = reviews.get("reviews", [])
    review_list = review_details if isinstance(review_details, list) else []
    annual_average = _latest_annual_average(review_list, reviews.get("average_kpi"))
    consecutive_ok = _has_consecutive_kpi(review_list, 85, 2)
    annual_ok = annual_average is not None and annual_average >= 85
    if consecutive_ok or annual_ok:
        detail = f"年度平均 KPI {annual_average}" if annual_average is not None else "连续季度达标"
        checks.append(f"- 绩效要求：满足，{detail}，规则要求连续 2 季度 KPI≥85 或年度平均≥85。")
    else:
        failures.append("绩效未达到 P5→P6 要求")
        detail = f"当前平均 KPI {annual_average}" if annual_average is not None else "缺少 KPI 记录"
        checks.append(f"- 绩效要求：不满足，{detail}，规则要求连续 2 季度 KPI≥85 或年度平均≥85。")

    project_count = int(projects.get("project_count") or 0)
    if project_count >= 3:
        checks.append(f"- 项目经验：满足，主导/核心参与数为 {project_count}，规则要求主导或核心参与≥3 个。")
    else:
        failures.append("主导/核心参与项目不足 3 个")
        checks.append(f"- 项目经验：不满足，主导/核心参与数为 {project_count}，规则要求主导或核心参与≥3 个。")

    unknowns.append("当前数据源未提供 P0/P1 事故记录")
    checks.append("- 事故记录：待确认，当前数据源未提供 P0/P1 事故记录。")

    if failures:
        result = "不符合"
        reason = "；".join(failures)
    elif unknowns:
        result = "当前证据不足以确认完全符合"
        reason = "；".join(unknowns)
    else:
        result = "符合"
        reason = "已满足全部可判定条件"

    return (
        f"{name}目前{result} {from_level} 晋升 {to_level} 条件：{reason}。\n"
        "逐项判断：\n"
        + "\n".join(checks)
        + f"\n\n{_source_block(evidences)}"
    )


def _format_department_performance(evidences: list[Evidence]) -> str:
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
        f"\n\n{_source_block(evidences)}"
    )


def format_fallback_answer(
    question: str,
    plan: QueryPlan,
    evidences: list[Evidence],
    *,
    current_date: str | None = None,
) -> str:
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

    if plan.template == "promotion_eligibility":
        return _format_promotion_answer(plan, evidences, current_date)

    if plan.template == "department_performance_summary":
        return _format_department_performance(evidences)

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
    current_date: str | None = None,
) -> str:
    if plan.template in {"promotion_eligibility", "department_performance_summary"}:
        return format_fallback_answer(question, plan, evidences, current_date=current_date)

    if client is not None and answer_polish and evidences:
        try:
            polished = polish_answer(client, question, plan, evidences).strip()
            if polished:
                return _append_verified_sources(polished, evidences)
        except LlmError:
            pass
    return format_fallback_answer(question, plan, evidences, current_date=current_date)
