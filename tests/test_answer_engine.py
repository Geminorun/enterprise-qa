from scripts.answer_engine import format_fallback_answer, polish_answer
from scripts.intent import Evidence, QueryPlan


class FakeClient:
    def __init__(self, content: str):
        self.content = content

    def chat(self, messages):
        return self.content


def test_fallback_employee_basic_answer():
    plan = QueryPlan("db", "employee_basic", {"employee_name": "张三", "field": "department"})
    evidence = [
        Evidence(
            "db",
            "employees 表",
            "张三的 department 是研发部",
            "employee_id: EMP-001",
            {"name": "张三", "department": "研发部"},
        )
    ]

    answer = format_fallback_answer("张三的部门是什么？", plan, evidence)

    assert "研发部" in answer
    assert "来源" in answer
    assert "employees 表" in answer


def test_polish_answer_uses_llm_content():
    plan = QueryPlan("db", "employee_basic", {"employee_name": "张三", "field": "department"})
    evidence = [
        Evidence(
            "db",
            "employees 表",
            "张三的部门是研发部",
            "employee_id: EMP-001",
            {"department": "研发部"},
        )
    ]

    answer = polish_answer(
        FakeClient("张三属于研发部。\n\n> 来源：employees 表 (employee_id: EMP-001)"),
        "张三的部门是什么？",
        plan,
        evidence,
    )

    assert "张三属于研发部" in answer
