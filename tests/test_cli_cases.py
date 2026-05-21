import subprocess
import sys

from scripts.cli import answer_question
from scripts.intent import QueryPlan


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
    assert "project_members 表" in answer


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
        planner=FakePlanner(QueryPlan("db", "employee_basic", {"employee_id": "EMP-999", "field": "name"})),
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
    assert "PRJ-001" in answer


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


def test_answer_question_reports_missing_llm_provider(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)

    answer = answer_question("张三的部门是什么？")

    assert "LLM" in answer
    assert "不能生成查询计划" in answer
