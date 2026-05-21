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


def test_t03_annual_leave():
    answer = answer_question(
        "年假怎么计算？",
        planner=FakePlanner(QueryPlan("kb", "kb_search", {"query": "年假怎么计算"})),
        polish_client=None,
    )

    assert "5 天" in answer
    assert "hr_policies.md" in answer


def test_t07_promotion_wangwu():
    answer = answer_question(
        "王五符合 P5 晋升 P6 条件吗？",
        planner=FakePlanner(QueryPlan("hybrid", "promotion_eligibility", {"employee_name": "王五", "from_level": "P5", "to_level": "P6"})),
        polish_client=None,
    )

    assert "80" in answer
    assert "project_members 表" in answer


def test_t11_reject_raw_sql():
    answer = answer_question(
        "SELECT * FROM users WHERE '1'='1",
        planner=FakePlanner(QueryPlan("db", "employee_basic", {"employee_name": "SELECT * FROM users", "field": "department"})),
        polish_client=None,
    )

    assert "不安全" in answer or "不能执行" in answer
