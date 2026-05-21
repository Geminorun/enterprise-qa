from scripts.answer_engine import build_answer, format_fallback_answer, polish_answer
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


def test_promotion_answer_rejects_employee_already_at_target_level():
    plan = QueryPlan("hybrid", "promotion_eligibility", {"employee_name": "张三", "from_level": "P5", "to_level": "P6"})
    evidences = [
        Evidence("db", "employees 表", "张三 当前职级 P6", "employee_id: EMP-001", {"name": "张三", "level": "P6", "hire_date": "2023-06-15"}),
        Evidence("db", "performance_reviews 表", "张三 平均 KPI 89.25", "employee_id: EMP-001", {"average_kpi": 89.25, "review_count": 4}),
        Evidence("db", "project_members 表", "张三 项目数 4", "employee_id: EMP-001", {"project_count": 4}),
        Evidence("kb", "promotion_rules.md section P5 → P6", "P5 晋升 P6 条件", "promotion_rules.md", {}),
    ]

    answer = format_fallback_answer("那张三呢？", plan, evidences)

    assert "不符合" in answer
    assert "当前职级已是 P6" in answer
    assert "工作年限" in answer
    assert "绩效要求" in answer
    assert "项目经验" in answer
    assert "promotion_rules.md" in answer


def test_department_performance_answer_includes_aggregate_metrics():
    plan = QueryPlan("db", "department_performance_summary", {"employee_name": "张三", "year": 2025})
    evidence = [
        Evidence(
            "db",
            "employees 表 + performance_reviews 表",
            "研发部 2025 年绩效基于个人记录汇总",
            "department: 研发部, year: 2025",
            {
                "department": "研发部",
                "year": 2025,
                "department_average": 89.5,
                "members": [
                    {"employee_id": "EMP-001", "name": "张三", "average_kpi": 89.25, "review_count": 4},
                    {"employee_id": "EMP-005", "name": "钱七", "average_kpi": 84.67, "review_count": 3},
                ],
            },
        )
    ]

    answer = format_fallback_answer("张三部门的 2025 年绩效如何？", plan, evidence)

    assert "研发部 2025 年部门平均 KPI 为 89.5" in answer
    assert "2 名员工" in answer
    assert "7 条绩效记录" in answer
    assert "个人绩效记录汇总" in answer


def test_build_answer_appends_verified_sources_after_polish():
    plan = QueryPlan("db", "performance_summary", {"employee_name": "张三", "year": 2025, "quarter": 2})
    evidence = [
        Evidence(
            "db",
            "performance_reviews 表 + employees 表",
            "2025 Q2 KPI 92 grade A",
            "employee_id: EMP-001",
            {"name": "张三", "year": 2025, "quarter": 2, "kpi_score": 92, "grade": "A"},
        )
    ]

    answer = build_answer(
        "张三 2025 Q2 绩效如何？",
        plan,
        evidence,
        client=FakeClient("张三 2025 Q2 KPI 为 92，评级 A。\n\n> 来源：绩效评估表"),
        answer_polish=True,
    )

    assert answer.endswith("> 来源：performance_reviews 表 + employees 表 (employee_id: EMP-001)")
