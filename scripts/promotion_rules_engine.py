from __future__ import annotations

from scripts.date_utils import as_date, years_between
from scripts.evidence_formatter import source_block
from scripts.intent import Evidence, QueryPlan
from scripts.levels import infer_promotion_levels


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


def _missing_performance() -> tuple[str, str]:
    return "待确认", "当前数据源没有连续季度绩效记录。"


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
    years = years_between(employee.get("hire_date"), as_date(current_date))

    if (from_level, to_level) == ("P4", "P5"):
        low_grades = [item.get("grade") for item in review_rows if item.get("grade") in {"C", "D"}]
        if not review_rows:
            performance_status, performance_detail = _missing_performance()
        else:
            performance_status = "满足" if _has_consecutive_grade(review_rows, "B", 2) and not low_grades else "不满足"
            performance_detail = "绩效记录未出现 C/D。" if not low_grades else f"存在 {', '.join(str(item) for item in low_grades)} 评价。"
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
                performance_status,
                performance_detail,
            ),
            ("学习任务", "完成导师指定任务", "待确认", "当前数据源未提供导师学习任务完成情况。"),
        ]

    if (from_level, to_level) == ("P5", "P6"):
        consecutive_ok = _has_consecutive_kpi(review_rows, 85, 2)
        annual_ok = annual_average is not None and annual_average >= 85
        performance_status, performance_detail = (
            _missing_performance()
            if not review_rows
            else ("满足" if consecutive_ok or annual_ok else "不满足", f"年度平均 KPI {annual_average}。")
        )
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
                performance_status,
                performance_detail,
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
        performance_status, performance_detail = (
            _missing_performance()
            if not review_rows
            else (
                "满足" if kpi_ok else "不满足",
                f"当前年度平均 KPI {annual_average}，最新年度 S 评价 {_s_count_latest_year(review_rows)} 个。",
            )
        )
        return [
            ("工作年限", "P6 满 2 年", "待确认", "当前数据源没有职级生效日期，不能确认 P6 任职时长。"),
            (
                "绩效要求",
                "连续 4 季度 KPI≥90 或年度 2 个 S",
                performance_status,
                performance_detail,
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
        performance_status, performance_detail = (
            _missing_performance()
            if not review_rows
            else ("满足" if s_count >= 2 else "待确认", f"最新年度 S 评价 {s_count} 个。")
        )
        return [
            ("工作年限", "P7 满 3 年", "待确认", "当前数据源没有职级生效日期，不能确认 P7 任职时长。"),
            ("绩效要求", "年度绩效至少 2 个 S 或连续 2 年 A 以上", performance_status, performance_detail),
            ("业务贡献", "显著业务贡献，营收/效率提升≥30%", "待确认", "当前数据源未提供业务贡献量化记录。"),
            ("影响力", "团队培养/技术分享，培养 2 名以上骨干", "待确认", "当前数据源未提供团队培养记录。"),
        ]

    return [("规则覆盖", f"{from_level} 晋升 {to_level}", "待确认", "当前规则表未覆盖该晋升级别。")]


def format_promotion_answer(plan: QueryPlan, evidences: list[Evidence], current_date: str | None) -> str:
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
        checks.append(f"- {name_}：{status}，规则要求：{requirement}；{detail}")
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
        + f"\n\n{source_block(evidences)}"
    )
