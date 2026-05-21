from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import time
from typing import Any

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.answer_engine import build_answer
from scripts.cli import _execute_plan
from scripts.config import load_config
from scripts.intent import Evidence, QueryPlan
from scripts.llm_client import LlmClient, LlmError
from scripts.planner import plan_question
from scripts.validator import PlanValidationError, validate_plan


@dataclass(frozen=True)
class TestCase:
    group: str
    case_id: str
    question: str
    expected: str
    difficulty: str
    must_contain: list[str] = field(default_factory=list)
    any_contains: list[list[str]] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)


TestCase.__test__ = False


@dataclass(frozen=True)
class CaseResult:
    case: TestCase
    status: str
    reason: str
    elapsed_seconds: float
    raw_plan: QueryPlan | None
    validated_plan: QueryPlan | None
    evidences: list[Evidence]
    answer: str
    error: str | None


def _cases() -> list[TestCase]:
    official = [
        TestCase("官方必过", "T01", "张三的部门是什么？", "研发部", "基础 DB 查询", ["研发部"]),
        TestCase("官方必过", "T02", "李四的上级是谁？", "CEO / EMP-000", "员工自关联查询", ["CEO"]),
        TestCase("官方必过", "T03", "年假怎么计算？", "满 1 年 5 天，每年 +1，上限 15 天", "KB 制度检索", ["5 天", "15 天"]),
        TestCase("官方必过", "T04", "迟到几次扣钱？", "4-6 次开始扣，50 元/次", "KB 制度检索", ["50"], [["4-6", "4 到 6", "4至6"]]),
        TestCase(
            "官方必过",
            "T05",
            "张三负责哪些项目？",
            "PRJ-001、PRJ-002、PRJ-003、PRJ-004 及角色",
            "员工项目关联查询",
            ["PRJ-001", "PRJ-002", "PRJ-003", "PRJ-004"],
        ),
        TestCase("官方必过", "T06", "研发部有多少人？", "4 人", "部门人数统计", ["4"]),
        TestCase(
            "官方必过",
            "T07",
            "王五符合 P5 晋升 P6 条件吗？",
            "不符合，KPI 80<85，项目数 1<3",
            "DB + KB 混合判断",
            ["不符合"],
            [["80", "KPI"], ["1", "项目"]],
        ),
        TestCase("官方必过", "T08", "张三 2 月迟到几次？", "2 次", "时间范围考勤查询", ["2"]),
        TestCase(
            "官方必过",
            "T09",
            "查一下 EMP-999",
            "明确告知无此员工",
            "不存在员工边界",
            [],
            [["没有", "未找到", "不能确认", "无法确认"]],
            ["Traceback", "ValidationError"],
        ),
        TestCase(
            "官方必过",
            "T10",
            "最近有什么事？",
            "追问澄清或返回最近会议/项目",
            "模糊时间和事件查询",
            [],
            [["会议", "项目", "请问", "澄清"]],
        ),
        TestCase(
            "官方必过",
            "T11",
            "SELECT * FROM users WHERE '1'='1",
            "拦截 SQL 注入",
            "安全边界",
            [],
            [["不能", "拒绝", "自然语言", "不安全", "SQL语句", "业务查询"]],
            ["users 表"],
        ),
        TestCase(
            "官方必过",
            "T12",
            "xyzabc123 怎么报销",
            "告知无相关信息，不编造",
            "无匹配 KB 查询",
            [],
            [["没有", "未找到", "不能确认", "无法确认"]],
        ),
    ]
    additions = [
        TestCase("官方追加", "A01", "李四的邮箱是什么？", "lisi@company.com", "同模板换字段", ["lisi@company.com"]),
        TestCase("官方追加", "A02", "产品部有多少人？", "3 人", "同模板换部门", ["3"]),
        TestCase("官方追加", "A03", "钱七符合晋升条件吗？", "不符合", "默认晋升级别推断", ["不符合"]),
        TestCase("官方追加", "A04", "差旅费报销标准是什么？", "机票、酒店、餐补等标准", "KB 财务制度", ["机票", "酒店", "餐补"]),
        TestCase(
            "官方追加",
            "A05",
            "3 月全员大会说了什么？",
            "营收、目标、ReMe、AI 实验室、调薪等",
            "会议纪要召回",
            [],
            [["营收", "150%"], ["ReMe", "智能问答"], ["调薪", "15%"]],
        ),
        TestCase(
            "官方追加",
            "A06",
            "张三 2025 年绩效如何？",
            "Q1-Q4 KPI 或平均 89.25",
            "绩效多记录查询",
            [],
            [["88", "89.25", "92", "90"]],
        ),
        TestCase("官方追加", "A07", "有哪些在研项目？", "PRJ-001、PRJ-003", "项目状态筛选", ["PRJ-001", "PRJ-003"]),
    ]
    regressions = [
        TestCase(
            "上次报错回归",
            "R01",
            "3 月全员大会说了什么？",
            "会议纪要完整召回",
            "曾只命中标题块",
            [],
            [["营收", "150%"], ["ReMe", "AI 实验室"], ["调薪", "15%"]],
        ),
        TestCase(
            "上次报错回归",
            "R02",
            "张三 P6 晋升 P7 可以吗？",
            "不能套用 P5→P6 规则",
            "曾错误套用晋升口径",
            [],
            [["暂不支持", "不输出符合/不符合", "P6 晋升 P7"]],
            ["符合 P5 晋升 P6", "主导或核心参与≥3"],
        ),
        TestCase(
            "上次报错回归",
            "R03",
            "王五上个月迟到超过扣款线了吗？",
            "2 月迟到 5 次，超过扣款线，每次 50 元",
            "考勤 + 制度混合判断",
            ["王五", "5", "50"],
            [["超过", "扣款"]],
        ),
        TestCase(
            "上次报错回归",
            "R04",
            "CEO 的邮箱是多少？",
            "ceo@company.com",
            "特殊员工名实体识别",
            ["ceo@company.com"],
        ),
        TestCase(
            "上次报错回归",
            "R05",
            "入职未满一年的吴十有年假吗？",
            "查询入职日期后判定无年假",
            "用户前提需核实",
            ["吴十", "2025-07-01"],
            [["未满 1 年", "没有年假", "无年假"]],
        ),
        TestCase(
            "上次报错回归",
            "R06",
            "张三的直属上级的邮箱是多少？",
            "ceo@company.com",
            "两跳上级联系方式",
            ["CEO", "ceo@company.com"],
        ),
        TestCase(
            "上次报错回归",
            "R07",
            "技术同步会说下周启动什么？",
            "下周启动代码重构",
            "会议纪要决议项",
            ["代码重构"],
        ),
        TestCase(
            "上次报错回归",
            "R08",
            "EMP-999 符合晋升条件吗？",
            "明确无此员工/无法确认",
            "不存在员工 + 混合模板",
            [],
            [["没有", "未找到", "不能确认", "无法确认"]],
        ),
        TestCase(
            "上次报错回归",
            "R09",
            "最近有什么事？",
            "最近会议或 active/planning 项目",
            "recent_events 聚合",
            [],
            [["会议", "项目", "PRJ-001", "PRJ-002"]],
        ),
        TestCase("上次报错回归", "R10", "张三 2 月迟到几次？", "2 次", "考勤统计稳定性", ["2"]),
    ]
    tricky = [
        TestCase(
            "V2刁钻",
            "B01",
            "张三所在部门的 2025 年绩效如何？",
            "研发部平均 KPI，说明由个人绩效汇总",
            "涉及张三本人、部门反查、绩效汇总，且没有独立部门绩效表",
            ["研发部", "KPI"],
            [["89", "个人绩效", "汇总"]],
        ),
        TestCase(
            "V2刁钻",
            "B02",
            "张三的老师是谁？",
            "不编造老师实体，澄清或说明无数据",
            "老师字段不存在，考察是否幻觉",
            [],
            [["没有", "未找到", "不能确认", "请问", "澄清", "老师"]],
        ),
        TestCase("V2刁钻", "B03", "研发部有哪些在研和规划中的项目？", "PRJ-001、PRJ-002、PRJ-003", "部门关联 + 多状态过滤", ["PRJ-001", "PRJ-002", "PRJ-003"]),
        TestCase("V2刁钻", "B04", "产品部有什么暂停项目？", "PRJ-005 官网改版", "中文状态别名到 on_hold", ["PRJ-005"]),
        TestCase("V2刁钻", "B05", "张三有哪些已完成项目？", "仅 PRJ-004", "员工项目 + completed 状态", ["PRJ-004"], [], ["PRJ-001", "PRJ-002", "PRJ-003"]),
        TestCase(
            "V2刁钻",
            "B06",
            "王五 2025 Q1 绩效如何？",
            "明确无 Q1 记录",
            "员工存在但季度记录不存在",
            [],
            [["没有", "未找到", "不能确认", "无相关"]],
        ),
        TestCase("V2刁钻", "B07", "钱七符合 P5 晋升 P6 条件吗？", "不符合", "接近阈值，不能只看入职年限", ["不符合"]),
        TestCase("V2刁钻", "B08", "李四 2025 年平均 KPI 是多少？", "93.25", "四季度聚合平均", ["93.25"]),
        TestCase("V2刁钻", "B09", "谁是 PRJ-001 的负责人？", "张三", "项目 lead 到员工名", ["张三"]),
        TestCase(
            "V2刁钻",
            "B10",
            "PRJ-005 为什么暂停？",
            "状态有记录但原因未提供，不能编造",
            "区别状态和原因",
            [],
            [["没有", "未提供", "不能确认", "无法确认"]],
        ),
        TestCase("V2刁钻", "B11", "今年有调薪计划吗？", "4 月启动，预算 15%", "会议 Q&A 召回", ["4 月", "15"]),
        TestCase("V2刁钻", "B12", "active 项目有多少个？", "2 个", "英文状态枚举 + 统计", ["2"]),
        TestCase(
            "V2刁钻",
            "B13",
            "市场部有哪些在研项目？",
            "无 active 项目，不能返回暂停项目",
            "空结果 + 状态过滤",
            [],
            [["没有", "未找到", "无相关"]],
            ["PRJ-005"],
        ),
        TestCase("V2刁钻", "B14", "ReMe 记忆框架有哪些成员，谁是 lead？", "张三 lead，李四 core，钱七 contributor", "项目名 + 成员角色", ["张三", "李四", "钱七", "lead"]),
        TestCase("V2刁钻", "B15", "研发部有哪些离职员工？", "离职员工", "员工状态过滤不应默认 active", ["离职员工"]),
        TestCase("V2刁钻", "B16", "张三有哪些在研项目？", "PRJ-001、PRJ-003", "员工项目 + active 状态", ["PRJ-001", "PRJ-003"]),
        TestCase("V2刁钻", "B17", "请问旷工规则是什么？", "迟到 7 次以上视为旷工 1 天", "KB 制度局部检索", ["7", "旷工"]),
        TestCase("V2刁钻", "B18", "试用期多久？", "3-6 个月", "FAQ 检索", [], [["3-6", "3 到 6", "3 至 6"]]),
        TestCase("V2刁钻", "B19", "周九参与了哪些项目？", "PRJ-003 lead", "员工项目查询，非张三/李四", ["PRJ-003", "lead"]),
        TestCase(
            "V2刁钻",
            "B20",
            "产品部 2025 年绩效怎么样？",
            "基于个人绩效汇总，不是独立部门绩效表",
            "部门绩效统计可能不存在，需说明汇总口径",
            ["产品部", "KPI"],
            [["88", "个人绩效", "汇总"]],
        ),
    ]
    return official + additions + regressions + tricky


def _plan_to_dict(plan: QueryPlan | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    return {
        "source_type": plan.source_type,
        "template": plan.template,
        "params": plan.params,
        "output_mode": plan.output_mode,
        "needs_clarification": plan.needs_clarification,
        "clarification_question": plan.clarification_question,
    }


def _evidence_to_dict(evidence: Evidence) -> dict[str, Any]:
    return {
        "kind": evidence.kind,
        "source": evidence.source,
        "locator": evidence.locator,
        "content": evidence.content,
        "data": evidence.data,
    }


def _evaluate(case: TestCase, result_text: str) -> tuple[str, str]:
    missing = [token for token in case.must_contain if token not in result_text]
    missing_any = [
        " / ".join(group)
        for group in case.any_contains
        if group and not any(token in result_text for token in group)
    ]
    forbidden = [token for token in case.must_not_contain if token in result_text]
    if missing or missing_any or forbidden:
        parts = []
        if missing:
            parts.append("缺少：" + "、".join(missing))
        if missing_any:
            parts.append("未命中任一：" + "；".join(missing_any))
        if forbidden:
            parts.append("出现禁用词：" + "、".join(forbidden))
        return "未通过", "；".join(parts)
    return "通过", "命中预期要点"


def _run_case(case: TestCase, client: LlmClient, config: Any) -> CaseResult:
    started = time.perf_counter()
    raw_plan: QueryPlan | None = None
    validated_plan: QueryPlan | None = None
    evidences: list[Evidence] = []
    answer = ""
    error: str | None = None
    try:
        raw_plan = plan_question(client, case.question, {})
        validated_plan = validate_plan(raw_plan)
        if validated_plan.template == "unknown" and validated_plan.needs_clarification:
            answer = validated_plan.clarification_question or "需要进一步澄清问题。"
        else:
            evidences = _execute_plan(validated_plan, config.database_path, config.knowledge_path)
            answer = build_answer(
                case.question,
                validated_plan,
                evidences,
                client=client,
                answer_polish=config.answer_polish,
                current_date=config.current_date,
            )
    except PlanValidationError as exc:
        error = f"PlanValidationError: {exc}"
        answer = f"我不能执行这个查询：{exc}"
    except LlmError as exc:
        error = f"LlmError: {exc}"
        answer = f"我不能生成查询计划：{exc}"
    except Exception as exc:  # pragma: no cover - test report should capture unexpected runtime failures.
        error = f"{type(exc).__name__}: {exc}"
        answer = f"运行异常：{error}"
    elapsed = round(time.perf_counter() - started, 2)
    check_text = "\n".join(
        [
            answer,
            json.dumps(_plan_to_dict(validated_plan or raw_plan), ensure_ascii=False),
            json.dumps([_evidence_to_dict(item) for item in evidences], ensure_ascii=False),
            error or "",
        ]
    )
    status, reason = _evaluate(case, check_text)
    return CaseResult(case, status, reason, elapsed, raw_plan, validated_plan, evidences, answer, error)


def _status_summary(results: list[CaseResult]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for result in results:
        summary[result.status] = summary.get(result.status, 0) + 1
    return summary


def _group_summary(results: list[CaseResult]) -> list[str]:
    groups = sorted(dict.fromkeys(result.case.group for result in results))
    lines = ["| 分类 | 用例数 | 通过 | 未通过 |", "|---|---:|---:|---:|"]
    for group in groups:
        group_results = [result for result in results if result.case.group == group]
        passed = sum(1 for result in group_results if result.status == "通过")
        failed = len(group_results) - passed
        lines.append(f"| {group} | {len(group_results)} | {passed} | {failed} |")
    return lines


def _failure_lines(results: list[CaseResult]) -> list[str]:
    failed = [result for result in results if result.status != "通过"]
    if not failed:
        return ["本轮自动判定未发现失败用例。"]
    lines: list[str] = []
    for result in failed:
        route = result.validated_plan.template if result.validated_plan else (result.raw_plan.template if result.raw_plan else "无")
        lines.append(
            f"- **{result.case.case_id} {result.case.question}**：{result.reason}；路由 `{route}`。"
        )
    return lines


def _case_table(results: list[CaseResult]) -> list[str]:
    lines = [
        "| ID | 分类 | 问题 | 刁钻点/考察点 | 预期 | 路由 | 结果 | 耗时 |",
        "|---|---|---|---|---|---|---|---:|",
    ]
    for result in results:
        route = result.validated_plan.template if result.validated_plan else (result.raw_plan.template if result.raw_plan else "无")
        lines.append(
            f"| {result.case.case_id} | {result.case.group} | {result.case.question} | "
            f"{result.case.difficulty} | {result.case.expected} | `{route}` | "
            f"{result.status} | {result.elapsed_seconds:.2f}s |"
        )
    return lines


def _details(results: list[CaseResult]) -> list[str]:
    lines: list[str] = []
    for result in results:
        lines.append(f"### {result.case.case_id} {result.case.question}")
        lines.append("")
        lines.append(f"- 分类：{result.case.group}")
        lines.append(f"- 刁钻点/考察点：{result.case.difficulty}")
        lines.append(f"- 预期：{result.case.expected}")
        lines.append(f"- 自动判定：{result.status}，{result.reason}")
        lines.append(f"- 耗时：{result.elapsed_seconds:.2f}s")
        lines.append(f"- 原始计划：`{json.dumps(_plan_to_dict(result.raw_plan), ensure_ascii=False)}`")
        lines.append(f"- 校验后计划：`{json.dumps(_plan_to_dict(result.validated_plan), ensure_ascii=False)}`")
        if result.error:
            lines.append(f"- 错误：`{result.error}`")
        sources = [
            f"{item.source} ({item.locator})" if item.locator else item.source
            for item in result.evidences
        ]
        lines.append(f"- 来源：{'; '.join(dict.fromkeys(sources)) if sources else '无'}")
        lines.append("")
        lines.append("实际回答：")
        lines.append("")
        lines.append("```text")
        lines.append(result.answer.strip())
        lines.append("```")
        lines.append("")
    return lines


def _recommendations(results: list[CaseResult]) -> list[str]:
    failed_ids = {result.case.case_id for result in results if result.status != "通过"}
    suggestions: list[str] = [
        "以下内容按代码 Review 标准整理，供修复时逐项处理。修复原则：不要为了单个测试问题写一对一特判，应把能力收敛到规则引擎、受控模板、查询执行器或 formatter 的通用逻辑中。",
        "",
        "### [P1] 晋升规则引擎只实现了 P5→P6，其他晋升级别被直接拒判",
        "",
        "- 位置：`scripts/answer_engine.py:195`",
        "- 现象：`_format_promotion_answer` 中只允许 `(from_level, to_level) == (\"P5\", \"P6\")` 进入自动判定，其他晋升级别直接返回“暂不支持自动判定”。",
        "- 影响：当用户问“张三符合晋升条件吗？”时，张三当前职级是 P6，系统只能拒判 P6→P7；同时证据中又可能召回“张三破格晋升 P6→P7”的会议纪要，最终回答会显得割裂。这个问题不是文案问题，而是晋升规则能力边界过窄。",
        "- 建议：将 `promotion_rules.md` 中的 P4→P5、P5→P6、P6→P7、P7→P8 规则结构化为规则表或 checker map，按 `from_level/to_level` 选择对应规则。若某些条件无法由当前数据源判定，也应完整列出目标晋升级别的全部条件，并标明“已满足 / 不满足 / 待确认”，而不是只写 P5→P6。P6→P7 至少应覆盖：P6 满 2 年、连续 4 季度 KPI≥90、主导项目≥2、有技术突破或专利/论文。破格晋升会议纪要可以作为补充事实，但不能替代规则判断。",
        "",
    ]
    if {"A05", "R01", "B11"} & failed_ids:
        suggestions.extend(
            [
                "### [P1] 会议纪要召回仍不稳定",
                "",
                "- 位置：`scripts/knowledge_index.py`、`scripts/answer_engine.py`",
                "- 影响：命中文档标题时可能缺少 Q&A 和议程正文，导致会议类问题回答不完整。",
                "- 建议：继续加固文件级召回，标题命中后带出相邻章节或短文档全文摘要。",
                "",
            ]
        )
    if {"T09", "R08"} & failed_ids:
        suggestions.extend(
            [
                "### [P1] 员工概览查询缺少空结果兜底",
                "",
                "- 位置：`scripts/validator.py`、`scripts/answer_engine.py`",
                "- 影响：不存在员工可能返回校验错误或不友好的空结果。",
                "- 建议：保留员工概览默认字段兜底，并确保不存在员工返回“未找到/无法确认”。",
                "",
            ]
        )
    if {"R02"} & failed_ids:
        suggestions.extend(
            [
                "### [P1] 非 P5→P6 晋升判断存在套用规则风险",
                "",
                "- 位置：`scripts/answer_engine.py`",
                "- 影响：P6→P7 等晋升问题可能被错误套用 P5→P6 规则。",
                "- 建议：按晋升级别选择规则；未实现时完整列出规则和待确认项，禁止套用错误口径。",
                "",
            ]
        )
    if {"R03"} & failed_ids:
        suggestions.extend(
            [
                "### [P1] 考勤制度混合模板识别不稳定",
                "",
                "- 位置：`scripts/planner.py`、`scripts/answer_engine.py`",
                "- 影响：“上个月 + 扣款线”问题可能被路由为普通考勤统计或 unknown。",
                "- 建议：稳定使用 `attendance_policy_check`，并同时输出考勤次数和制度判断。",
                "",
            ]
        )
    if {"R06"} & failed_ids:
        suggestions.extend(
            [
                "### [P2] 上级联系方式两跳查询输出不完整",
                "",
                "- 位置：`scripts/query_templates.py`、`scripts/answer_engine.py`",
                "- 影响：能找到直属上级，但可能缺少上级邮箱。",
                "- 建议：继续由 `employee_manager` 返回 `manager_email`，并在 formatter 中直接输出。",
                "",
            ]
        )
    if {"B10"} & failed_ids:
        suggestions.extend(
            [
                "### [P2] 项目暂停原因缺失时没有明确说明“原因未提供”",
                "",
                "- 位置：`scripts/answer_engine.py:99`",
                "- 失败用例：B10 `PRJ-005 为什么暂停？`",
                "- 影响：用户可能误以为项目名称或状态就是暂停原因。",
                "- 建议：当问题询问原因，但 evidence 只有状态字段、没有 reason/cause 字段时，明确输出“当前数据源未提供暂停原因，因此不能确认为什么暂停”。",
                "",
            ]
        )
    if {"B08"} & failed_ids:
        suggestions.extend(
            [
                "### [P2] 年度绩效查询没有处理“平均 KPI”聚合口径",
                "",
                "- 位置：`scripts/query_templates.py:285`、`scripts/answer_engine.py:409`",
                "- 失败用例：B08 `李四 2025 年平均 KPI 是多少？`",
                "- 影响：用户问聚合结果，系统只返回季度明细，答案不完整。",
                "- 建议：让 `performance_summary` 支持聚合输出；当 `output_mode=count/summary` 或问题包含“平均 KPI”时，计算并输出平均值，同时保留季度明细和来源。",
                "",
            ]
        )
    if {"B12"} & failed_ids:
        suggestions.extend(
            [
                "### [P2] `output_mode=count` 没有被列表类项目查询尊重",
                "",
                "- 位置：`scripts/query_templates.py:161`、`scripts/answer_engine.py:409`",
                "- 失败用例：B12 `active 项目有多少个？`",
                "- 影响：路由和查询正确，但最终答案层丢失用户真正问的数量。",
                "- 建议：在项目列表类 formatter 中统一处理 `output_mode=count`：先输出数量，再按需附带项目清单。",
                "",
            ]
        )
    return suggestions


def _write_outputs(results: list[CaseResult], config: Any) -> None:
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    report_path = docs_dir / "企业问答Skill-V2全量测试报告.md"
    json_path = docs_dir / "企业问答Skill-V2全量测试结果.json"
    summary = _status_summary(results)
    total = len(results)
    passed = summary.get("通过", 0)
    failed = total - passed
    total_seconds = round(sum(result.elapsed_seconds for result in results), 2)

    report: list[str] = [
        "# 企业问答 Skill V2 全量测试报告",
        "",
        "测试日期：2026-05-21",
        "被测分支：`main`",
        "测试对象：Claude Code Skill `enterprise-qa`",
        "测试方式：真实调用当前 LLM 生成 QueryPlan，经 validator、受控查询执行器和本地 formatter 输出答案。",
        "",
        "## 1. 测试配置",
        "",
        "| 项目 | 值 |",
        "|---|---|",
        f"| `thinking_enabled` | `{config.thinking_enabled}` |",
        f"| `answer_polish` | `{config.answer_polish}` |",
        f"| `timeout_seconds` | `{config.timeout_seconds}` |",
        f"| 当前日期 | `{config.current_date}` |",
        f"| 时区 | `{config.timezone}` |",
        f"| 数据库 | `{config.database_path}` |",
        f"| 知识库 | `{config.knowledge_path}` |",
        "",
        "运行前显式设置：",
        "",
        "```powershell",
        "$env:ENTERPRISE_QA_THINKING_ENABLED='false'",
        "$env:ENTERPRISE_QA_ANSWER_POLISH='false'",
        "$env:ENTERPRISE_QA_LLM_TIMEOUT='50'",
        "python -X utf8 scripts/run_v2_full_test.py",
        "```",
        "",
        "## 2. 总体结论",
        "",
        f"本轮共执行 {total} 条用例，总耗时约 {total_seconds:.2f}s，平均 {total_seconds / total:.2f}s/题。",
        "",
        f"- 通过：{passed}",
        f"- 未通过：{failed}",
        "",
        *_group_summary(results),
        "",
        "## 3. 失败与风险清单",
        "",
        *_failure_lines(results),
        "",
        "## 4. 用例总表",
        "",
        *_case_table(results),
        "",
        "## 5. Review 诊断",
        "",
        *_recommendations(results),
        "",
        "## 6. 逐题明细",
        "",
        *_details(results),
    ]

    report_path.write_text("\n".join(report), encoding="utf-8")
    json_payload = [
        {
            "group": result.case.group,
            "case_id": result.case.case_id,
            "question": result.case.question,
            "expected": result.case.expected,
            "difficulty": result.case.difficulty,
            "status": result.status,
            "reason": result.reason,
            "elapsed_seconds": result.elapsed_seconds,
            "raw_plan": _plan_to_dict(result.raw_plan),
            "validated_plan": _plan_to_dict(result.validated_plan),
            "evidences": [_evidence_to_dict(item) for item in result.evidences],
            "answer": result.answer,
            "error": result.error,
        }
        for result in results
    ]
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"写入报告：{report_path}")
    print(f"写入明细：{json_path}")


def main() -> int:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    config = load_config()
    client = LlmClient(
        config.providers,
        timeout_seconds=config.timeout_seconds,
        thinking_enabled=config.thinking_enabled,
    )
    results: list[CaseResult] = []
    cases = _cases()
    for index, case in enumerate(cases, start=1):
        result = _run_case(case, client, config)
        results.append(result)
        print(
            json.dumps(
                {
                    "index": index,
                    "total": len(cases),
                    "group": case.group,
                    "case_id": case.case_id,
                    "status": result.status,
                    "elapsed_seconds": result.elapsed_seconds,
                    "question": case.question,
                    "reason": result.reason,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    _write_outputs(results, config)
    failed = sum(1 for result in results if result.status != "通过")
    print(f"V2 全量测试完成：{len(results) - failed}/{len(results)} 通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
