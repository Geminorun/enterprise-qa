from __future__ import annotations

from datetime import date
import json
import re
from typing import Protocol

from scripts.intent import Evidence, QueryPlan
from scripts.levels import infer_promotion_levels
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
    return "会议纪要要点：\n" + "\n".join(f"- {item}" for item in summaries) + f"\n\n{_source_block(evidences)}"


def _format_recent_events(evidences: list[Evidence]) -> str:
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
        lines = [f"- {item.data['project_id']} {item.data['name']}：{item.data.get('status', '未知状态')}" for item in project_evidences]
        sections.append("相关项目：\n" + "\n".join(lines))
    if not sections:
        sections = [item.content for item in evidences]
    return "\n\n".join(sections) + f"\n\n{_source_block(evidences)}"


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


def _full_years_between(start: object, end: date) -> int | None:
    if not isinstance(start, str):
        return None
    try:
        start_date = date.fromisoformat(start)
    except ValueError:
        return None
    years = end.year - start_date.year
    if (end.month, end.day) < (start_date.month, start_date.day):
        years -= 1
    return max(years, 0)


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


def _s_count_latest_year(reviews: list[dict]) -> int:
    years = [int(item["year"]) for item in reviews if "year" in item]
    if not years:
        return 0
    latest_year = max(years)
    return sum(1 for item in reviews if int(item.get("year", 0)) == latest_year and item.get("grade") == "S")


def _count_lead_projects(projects: dict) -> int:
    rows = projects.get("projects", [])
    if not isinstance(rows, list):
        return 0
    return sum(1 for item in rows if item.get("role") == "lead")


def _grade_at_least(grade: object, minimum: str) -> bool:
    order = {"D": 0, "C": 1, "B": 2, "A": 3, "S": 4}
    return order.get(str(grade), -1) >= order[minimum]


def _has_consecutive_grade(reviews: list[dict], minimum: str, required_count: int) -> bool:
    best_run = 0
    current_run = 0
    previous_index: int | None = None
    for review in sorted(reviews, key=lambda item: (item.get("year", 0), item.get("quarter", 0))):
        try:
            quarter_index = int(review["year"]) * 4 + int(review["quarter"])
        except (KeyError, TypeError, ValueError):
            continue
        if _grade_at_least(review.get("grade"), minimum):
            current_run = current_run + 1 if previous_index is not None and quarter_index == previous_index + 1 else 1
            best_run = max(best_run, current_run)
        else:
            current_run = 0
        previous_index = quarter_index
    return best_run >= required_count


def _promotion_checks(
    from_level: str,
    to_level: str,
    employee: dict,
    reviews: dict,
    projects: dict,
    current_date: str | None,
) -> list[tuple[str, str, str, str]]:
    review_list = reviews.get("reviews", [])
    review_rows = review_list if isinstance(review_list, list) else []
    annual_average = _latest_annual_average(review_rows, reviews.get("average_kpi"))
    project_count = int(projects.get("project_count") or 0)
    lead_count = _count_lead_projects(projects)
    years = _years_between(employee.get("hire_date"), _as_date(current_date))

    if (from_level, to_level) == ("P4", "P5"):
        low_grades = [item.get("grade") for item in review_rows if item.get("grade") in {"C", "D"}]
        return [
            (
                "工作年限",
                "入职满 6 个月",
                "满足" if years is not None and years >= 0.5 else "不满足" if years is not None else "待确认",
                f"入职约 {years} 年。" if years is not None else "缺少可解析的入职日期。",
            ),
            (
                "绩效要求",
                "连续 2 季度≥B 且无 C/D 评价",
                "满足" if _has_consecutive_grade(review_rows, "B", 2) and not low_grades else "不满足",
                "绩效记录未出现 C/D。" if not low_grades else f"存在 {', '.join(str(item) for item in low_grades)} 评价。",
            ),
            ("学习任务", "完成导师指定任务", "待确认", "当前数据源未提供导师学习任务完成情况。"),
        ]

    if (from_level, to_level) == ("P5", "P6"):
        consecutive_ok = _has_consecutive_kpi(review_rows, 85, 2)
        annual_ok = annual_average is not None and annual_average >= 85
        return [
            (
                "工作年限",
                "入职满 1 年，或 P5 满 2 年",
                "满足" if years is not None and years >= 1 else "不满足" if years is not None else "待确认",
                f"入职约 {years} 年。" if years is not None else "缺少可解析的入职日期。",
            ),
            (
                "绩效要求",
                "连续 2 季度 KPI≥85 或年度平均≥85",
                "满足" if consecutive_ok or annual_ok else "不满足",
                f"年度平均 KPI {annual_average}。",
            ),
            (
                "项目经验",
                "主导或核心参与≥3 个",
                "满足" if project_count >= 3 else "不满足",
                f"主导/核心参与数为 {project_count}。",
            ),
            ("事故记录", "无重大事故（P0/P1）", "待确认", "当前数据源未提供 P0/P1 事故记录。"),
        ]

    if (from_level, to_level) == ("P6", "P7"):
        kpi_ok = _has_consecutive_kpi(review_rows, 90, 4) or _s_count_latest_year(review_rows) >= 2
        return [
            ("工作年限", "P6 满 2 年", "待确认", "当前数据源没有职级生效日期，不能确认 P6 任职时长。"),
            (
                "绩效要求",
                "连续 4 季度 KPI≥90 或年度 2 个 S",
                "满足" if kpi_ok else "不满足",
                f"当前年度平均 KPI {annual_average}，最新年度 S 评价 {_s_count_latest_year(review_rows)} 个。",
            ),
            (
                "项目经验",
                "主导项目≥2 个",
                "满足" if lead_count >= 2 else "不满足",
                f"主导项目数为 {lead_count}。",
            ),
            ("技术贡献", "技术突破/专利/论文至少 1 项", "待确认", "当前数据源未提供技术突破、专利或论文记录。"),
        ]

    if (from_level, to_level) == ("P7", "P8"):
        s_count = _s_count_latest_year(review_rows)
        return [
            ("工作年限", "P7 满 3 年", "待确认", "当前数据源没有职级生效日期，不能确认 P7 任职时长。"),
            ("绩效要求", "年度绩效至少 2 个 S 或连续 2 年 A 以上", "满足" if s_count >= 2 else "待确认", f"最新年度 S 评价 {s_count} 个。"),
            ("业务贡献", "显著业务贡献，营收/效率提升≥30%", "待确认", "当前数据源未提供业务贡献量化记录。"),
            ("影响力", "团队培养/技术分享，培养 2 名以上骨干", "待确认", "当前数据源未提供团队培养记录。"),
        ]

    return [("规则覆盖", f"{from_level} 晋升 {to_level}", "待确认", "当前规则表未覆盖该晋升级别。")]


def _format_promotion_answer(plan: QueryPlan, evidences: list[Evidence], current_date: str | None) -> str:
    combined = {item.source: item.data for item in evidences}
    employee = combined.get("employees 表", {})
    reviews = combined.get("performance_reviews 表", {})
    projects = combined.get("project_members 表", {})
    name = str(employee.get("name", plan.params.get("employee_name", "该员工")))
    current_level = str(employee.get("level", "未知职级"))
    from_level, to_level = infer_promotion_levels(plan.params, current_level)
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

    for name_, requirement, status, detail in _promotion_checks(from_level, to_level, employee, reviews, projects, current_date):
        checks.append(f"- {name_}：{status}，规则要求{requirement}；{detail}")
        if status == "不满足":
            failures.append(f"{name_}不满足")
        elif status == "待确认":
            unknowns.append(f"{name_}待确认")

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


def _format_performance_summary(plan: QueryPlan, evidences: list[Evidence]) -> str:
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
            return f"{name} {year} 年平均 KPI 为 {average}。季度明细：{details}。\n\n{_source_block(evidences)}"
    lines = [evidence.content for evidence in evidences]
    return "\n".join(lines) + f"\n\n{_source_block(evidences)}"


def _employee_status_label(status: object) -> str:
    labels = {"active": "在职", "on_leave": "休假", "resigned": "离职"}
    return labels.get(str(status), str(status))


def _format_employee_manager(evidences: list[Evidence]) -> str:
    data = evidences[0].data
    employee_name = data.get("name", "该员工")
    manager_name = data.get("manager_name") or "未记录"
    manager_email = data.get("manager_email")
    if manager_email:
        return f"{employee_name}的直属上级是 {manager_name}，邮箱是 {manager_email}。\n\n{_source_block(evidences)}"
    return f"{employee_name}的直属上级是 {manager_name}。\n\n{_source_block(evidences)}"


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
            f"\n\n{_source_block(evidences)}"
        )
    if count <= 3:
        result = f"未超过扣款线，月累计迟到 {count} 次属于 3 次以内，不扣款，口头提醒。"
    elif count <= 6:
        result = f"已超过扣款线，月累计迟到 {count} 次落在 4-6 次扣款档，每次扣款 50 元。"
    else:
        result = f"已超过扣款线，月累计迟到 {count} 次达到 7 次以上，视为旷工 1 天并通报批评。"
    return f"{name}在 {start} 至 {end} 迟到 {count} 次，{result}\n\n{_source_block(evidences)}"


def _format_leave_entitlement_check(evidences: list[Evidence], current_date: str | None) -> str:
    employee = next((item for item in evidences if item.source == "employees 表"), None)
    if employee is None:
        return f"未找到该员工的入职日期，无法判定年假资格。\n\n{_source_block(evidences)}"
    data = employee.data
    name = data.get("name", "该员工")
    hire_date = data.get("hire_date")
    leave_type = data.get("leave_type", "年假")
    today = _as_date(current_date)
    full_years = _full_years_between(hire_date, today)
    if leave_type != "年假":
        return f"{name}的{leave_type}资格当前没有专用判定规则。\n\n{_source_block(evidences)}"
    if full_years is None:
        return f"{name}的入职日期不可解析，无法判定年假资格。\n\n{_source_block(evidences)}"
    if full_years < 1:
        return (
            f"{name}入职日期是 {hire_date}，截至 {today.isoformat()} 未满 1 年，"
            "按年假制度没有年假。"
            f"\n\n{_source_block(evidences)}"
        )
    days = min(15, 5 + full_years - 1)
    return (
        f"{name}入职日期是 {hire_date}，截至 {today.isoformat()} 已满 1 年，"
        f"按年假制度有年假，当前可按约 {days} 天估算。"
        f"\n\n{_source_block(evidences)}"
    )


def _format_project_collection(question: str, plan: QueryPlan, evidences: list[Evidence]) -> str:
    if not evidences:
        return "我没有在当前数据源中找到相关项目信息，因此不能确认答案。"
    asks_reason = any(word in question for word in ("为什么", "原因")) or "PRJ-" in question
    if asks_reason and any(item.data.get("status") == "on_hold" for item in evidences):
        lines = [
            f"{item.data.get('project_id')} {item.data.get('name')} 当前状态为 {item.data.get('status')}，"
            "当前数据源未提供暂停原因，因此不能确认为什么暂停。"
            for item in evidences
        ]
        return "\n".join(lines) + f"\n\n{_source_block(evidences)}"

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
    return header + "\n" + "\n".join(lines) + f"\n\n{_source_block(evidences)}"


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
        return f"{name}的{field}是 {value}。\n\n> 来源：{_sources(evidences)}"

    if plan.template == "employee_manager":
        return _format_employee_manager(evidences)

    if plan.template == "department_members":
        data = evidences[0].data
        names = "、".join(item["name"] for item in data.get("members", []))
        label = _employee_status_label(data.get("status", "active"))
        return f"{data['department']}有 {data['count']} 名{label}员工：{names}。\n\n> 来源：{_sources(evidences)}"

    if plan.template == "attendance_stats":
        data = evidences[0].data
        return f"查询时间范围内，匹配的考勤记录共有 {data['count']} 次。\n\n> 来源：{_sources(evidences)}"

    if plan.template == "attendance_policy_check":
        return _format_attendance_policy_check(evidences)

    if plan.template == "leave_entitlement_check":
        return _format_leave_entitlement_check(evidences, current_date)

    if plan.template == "promotion_eligibility":
        return _format_promotion_answer(plan, evidences, current_date)

    if plan.template == "department_performance_summary":
        return _format_department_performance(evidences)

    if plan.template == "performance_summary":
        return _format_performance_summary(plan, evidences)

    if plan.template == "recent_events":
        return _format_recent_events(evidences)

    if plan.template in {"employee_projects", "department_projects", "project_members"}:
        return _format_project_collection(question, plan, evidences)

    if plan.template == "kb_search":
        if any("meeting_notes/" in item.source or "meeting_notes/" in str(item.locator) for item in evidences):
            return _format_meeting_notes_answer(evidences)
        lines = [item.content for item in evidences]
        return "\n".join(lines) + f"\n\n> 来源：{_sources(evidences)}"

    if any("meeting_notes/" in item.source or "meeting_notes/" in str(item.locator) for item in evidences):
        return _format_meeting_notes_answer(evidences)

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
