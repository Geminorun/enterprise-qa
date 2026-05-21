import subprocess
import sys

from scripts.cli import answer_question
from scripts.intent import QueryPlan
from scripts.llm_client import LlmError


class FakePlanner:
    def __init__(self, plan: QueryPlan):
        self.plan = plan

    def __call__(self, question, context):
        return self.plan


def test_t01_zhangsan_department():
    answer = answer_question(
        "张三的部门是什么？",
        planner=FakePlanner(QueryPlan("db", "employee_basic", {"employee_name": "张三", "field": "department"})),
        polish_client=None,
    )

    assert "研发部" in answer
    assert "来源" in answer


def test_t02_lisi_manager():
    answer = answer_question(
        "李四的上级是谁？",
        planner=FakePlanner(QueryPlan("db", "employee_manager", {"employee_name": "李四"})),
        polish_client=None,
    )

    assert "CEO" in answer


def test_t03_annual_leave():
    answer = answer_question(
        "年假怎么计算？",
        planner=FakePlanner(QueryPlan("kb", "kb_search", {"query": "年假怎么计算"})),
        polish_client=None,
    )

    assert "5 天" in answer
    assert "hr_policies.md" in answer


def test_t04_late_penalty():
    answer = answer_question(
        "迟到几次扣钱？",
        planner=FakePlanner(QueryPlan("kb", "kb_search", {"query": "迟到几次扣钱"})),
        polish_client=None,
    )

    assert "4-6" in answer
    assert "50" in answer


def test_t05_zhangsan_projects():
    answer = answer_question(
        "张三负责哪些项目？",
        planner=FakePlanner(QueryPlan("db", "employee_projects", {"employee_name": "张三"})),
        polish_client=None,
    )

    assert "PRJ-001" in answer
    assert "PRJ-004" in answer


def test_t06_rd_count():
    answer = answer_question(
        "研发部有多少人？",
        planner=FakePlanner(QueryPlan("db", "department_members", {"department": "研发部"}, "count")),
        polish_client=None,
    )

    assert "4" in answer


def test_t07_promotion_wangwu():
    answer = answer_question(
        "王五符合 P5 晋升 P6 条件吗？",
        planner=FakePlanner(QueryPlan("hybrid", "promotion_eligibility", {"employee_name": "王五", "from_level": "P5", "to_level": "P6"})),
        polish_client=None,
    )

    assert "80" in answer
    assert "不符合" in answer
    assert "project_members 表" in answer


def test_promotion_template_loads_rules_when_planned_as_db():
    answer = answer_question(
        "王五符合 P5 晋升 P6 条件吗？",
        planner=FakePlanner(QueryPlan("db", "promotion_eligibility", {"employee_name": "王五", "from_level": "P5", "to_level": "P6"})),
        polish_client=None,
    )

    assert "不符合" in answer
    assert "promotion_rules.md" in answer


def test_t08_zhangsan_late_count():
    answer = answer_question(
        "张三 2 月迟到几次？",
        planner=FakePlanner(
            QueryPlan(
                "db",
                "attendance_stats",
                {
                    "employee_name": "张三",
                    "status": "late",
                    "date_range": {"start": "2026-02-01", "end": "2026-02-28"},
                },
                "count",
            )
        ),
        polish_client=None,
    )

    assert "2" in answer


def test_t09_missing_employee():
    answer = answer_question(
        "查一下 EMP-999",
        planner=FakePlanner(QueryPlan("db", "employee_basic", {"employee_id": "EMP-999"})),
        polish_client=None,
    )

    assert "没有" in answer or "未找到" in answer


def test_t10_recent_events():
    answer = answer_question(
        "最近有什么事？",
        planner=FakePlanner(QueryPlan("hybrid", "recent_events", {"query": "最近 会议 项目"})),
        polish_client=None,
    )

    assert "会议" in answer or "项目" in answer
    assert "meeting_notes" in answer
    assert "PRJ-001" in answer
    assert "PRJ-002" in answer


def test_recent_events_runs_by_template_when_planned_as_db():
    answer = answer_question(
        "最近有什么事？",
        planner=FakePlanner(QueryPlan("db", "recent_events", {"query": "最近 会议 项目"})),
        polish_client=None,
    )

    assert "meeting_notes" in answer
    assert "PRJ-001" in answer
    assert "PRJ-002" in answer


def test_promotion_p6_to_p7_does_not_use_p5_to_p6_rules():
    answer = answer_question(
        "张三 P6 晋升 P7 可以吗？",
        planner=FakePlanner(QueryPlan("hybrid", "promotion_eligibility", {"employee_name": "张三", "from_level": "P6", "to_level": "P7"})),
        polish_client=None,
    )

    assert "暂不支持自动判定" in answer
    assert "promotion_rules.md" in answer
    assert "KPI≥85" not in answer
    assert "主导或核心参与≥3" not in answer


def test_department_projects_normalizes_paused_status():
    answer = answer_question(
        "产品部有什么暂停项目？",
        planner=FakePlanner(QueryPlan("db", "department_projects", {"department": "产品部", "status": "paused"})),
        polish_client=None,
    )

    assert "PRJ-005" in answer
    assert "官网改版" in answer


def test_employee_projects_filters_active_status():
    answer = answer_question(
        "张三有哪些在研项目？",
        planner=FakePlanner(QueryPlan("db", "employee_projects", {"employee_name": "张三", "status": "在研"})),
        polish_client=None,
    )

    assert "PRJ-001" in answer
    assert "PRJ-003" in answer
    assert "PRJ-002" not in answer
    assert "PRJ-004" not in answer


def test_department_members_filters_resigned_status():
    answer = answer_question(
        "研发部有哪些离职员工？",
        planner=FakePlanner(QueryPlan("db", "department_members", {"department": "研发部", "status": "离职"})),
        polish_client=None,
    )

    assert "离职员工" in answer


def test_t11_reject_raw_sql():
    answer = answer_question(
        "SELECT * FROM users WHERE '1'='1",
        planner=FakePlanner(QueryPlan("db", "employee_basic", {"employee_name": "SELECT * FROM users", "field": "department"})),
        polish_client=None,
    )

    assert "不安全" in answer or "不能执行" in answer


def test_t12_unknown_reimbursement():
    answer = answer_question(
        "xyzabc123 怎么报销",
        planner=FakePlanner(QueryPlan("kb", "kb_search", {"query": "xyzabc123 怎么报销"})),
        polish_client=None,
    )

    assert "没有" in answer or "未找到" in answer


def test_cli_script_help_runs_from_repo_root():
    result = subprocess.run(
        [sys.executable, "scripts/cli.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Enterprise QA Skill CLI" in result.stdout


def test_answer_question_reports_missing_llm_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("ENTERPRISE_QA_CONFIG_PATH", str(tmp_path / "missing-config.yaml"))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)

    answer = answer_question("张三的部门是什么？")

    assert "LLM" in answer
    assert "不能生成查询计划" in answer


class BadPlanner:
    def __call__(self, question, context):
        raise LlmError("无效 JSON：Expecting value")


def test_answer_question_reports_invalid_planner_json():
    answer = answer_question("张三的部门是什么？", planner=BadPlanner())

    assert "不能生成查询计划" in answer
    assert "无效 JSON" in answer
