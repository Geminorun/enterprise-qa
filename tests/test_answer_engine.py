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


def test_promotion_answer_checks_p6_to_p7_rules():
    plan = QueryPlan("hybrid", "promotion_eligibility", {"employee_name": "张三", "from_level": "P6", "to_level": "P7"})
    evidences = [
        Evidence("db", "employees 表", "张三 当前职级 P6", "employee_id: EMP-001", {"name": "张三", "level": "P6", "hire_date": "2023-06-15"}),
        Evidence(
            "db",
            "performance_reviews 表",
            "张三 平均 KPI 89.25",
            "employee_id: EMP-001",
            {
                "average_kpi": 89.25,
                "review_count": 4,
                "reviews": [
                    {"year": 2025, "quarter": 1, "kpi_score": 88, "grade": "A"},
                    {"year": 2025, "quarter": 2, "kpi_score": 92, "grade": "A"},
                    {"year": 2025, "quarter": 3, "kpi_score": 87, "grade": "A"},
                    {"year": 2025, "quarter": 4, "kpi_score": 90, "grade": "A"},
                ],
            },
        ),
        Evidence(
            "db",
            "project_members 表",
            "张三 主导/核心参与项目数 3",
            "employee_id: EMP-001",
            {
                "project_count": 3,
                "projects": [
                    {"project_id": "PRJ-001", "role": "lead"},
                    {"project_id": "PRJ-002", "role": "core"},
                    {"project_id": "PRJ-004", "role": "lead"},
                ],
            },
        ),
        Evidence("kb", "promotion_rules.md section P6 → P7", "P6 晋升 P7 条件", "promotion_rules.md", {}),
    ]

    answer = format_fallback_answer("张三符合晋升条件吗？", plan, evidences)

    assert "P6 晋升 P7" in answer
    assert "P6 满 2 年" in answer
    assert "连续 4 季度 KPI≥90" in answer
    assert "主导项目≥2 个" in answer
    assert "技术突破/专利/论文" in answer
    assert "暂不支持自动判定" not in answer


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


def test_department_members_answer_uses_resigned_status_label():
    plan = QueryPlan("db", "department_members", {"department": "研发部", "status": "resigned"})
    evidence = [
        Evidence(
            "db",
            "employees 表",
            "研发部 resigned 员工 1 人",
            "department: 研发部, status: resigned",
            {"department": "研发部", "status": "resigned", "count": 1, "members": [{"name": "离职员工"}]},
        )
    ]

    answer = format_fallback_answer("研发部有哪些离职员工？", plan, evidence)

    assert "研发部有 1 名离职员工：离职员工" in answer
    assert "在职员工" not in answer


def test_department_members_answer_uses_on_leave_status_label():
    plan = QueryPlan("db", "department_members", {"department": "研发部", "status": "on_leave"})
    evidence = [
        Evidence(
            "db",
            "employees 表",
            "研发部 on_leave 员工 0 人",
            "department: 研发部, status: on_leave",
            {"department": "研发部", "status": "on_leave", "count": 0, "members": []},
        )
    ]

    answer = format_fallback_answer("研发部有哪些休假员工？", plan, evidence)

    assert "研发部有 0 名休假员工" in answer
    assert "on_leave 员工" not in answer


def test_build_answer_appends_verified_sources_after_polish():
    plan = QueryPlan("db", "employee_basic", {"employee_name": "张三", "field": "department"})
    evidence = [
        Evidence(
            "db",
            "employees 表",
            "张三的部门是研发部",
            "employee_id: EMP-001",
            {"name": "张三", "department": "研发部"},
        )
    ]

    answer = build_answer(
        "张三的部门是什么？",
        plan,
        evidence,
        client=FakeClient("张三属于研发部。\n\n> 来源：员工信息表"),
        answer_polish=True,
    )

    assert answer.endswith("> 来源：employees 表 (employee_id: EMP-001)")


def test_performance_summary_uses_deterministic_average_when_polish_enabled():
    plan = QueryPlan("db", "performance_summary", {"employee_name": "李四", "year": 2025})
    evidence = [
        Evidence("db", "performance_reviews 表 + employees 表", "2025 Q1 KPI 95 grade S", "employee_id: EMP-002", {"name": "李四", "year": 2025, "quarter": 1, "kpi_score": 95, "grade": "S"}),
        Evidence("db", "performance_reviews 表 + employees 表", "2025 Q2 KPI 93 grade S", "employee_id: EMP-002", {"name": "李四", "year": 2025, "quarter": 2, "kpi_score": 93, "grade": "S"}),
        Evidence("db", "performance_reviews 表 + employees 表", "2025 Q3 KPI 91 grade A", "employee_id: EMP-002", {"name": "李四", "year": 2025, "quarter": 3, "kpi_score": 91, "grade": "A"}),
        Evidence("db", "performance_reviews 表 + employees 表", "2025 Q4 KPI 94 grade S", "employee_id: EMP-002", {"name": "李四", "year": 2025, "quarter": 4, "kpi_score": 94, "grade": "S"}),
    ]

    answer = build_answer(
        "李四 2025 年平均 KPI 是多少？",
        plan,
        evidence,
        client=FakeClient("李四 2025 年绩效不错。\n\n> 来源：绩效表"),
        answer_polish=True,
    )

    body = answer.split("> 来源：", 1)[0]
    assert "平均 KPI 为 93.25" in body
    assert "Q1 95" in body


def test_department_projects_count_uses_deterministic_formatter_when_polish_enabled():
    plan = QueryPlan("db", "department_projects", {"status": "active"}, "count")
    evidence = [
        Evidence("db", "projects 表 + project_members 表 + employees 表", "PRJ-001 ReMe 记忆框架", "project_id: PRJ-001", {"project_id": "PRJ-001", "name": "ReMe 记忆框架", "status": "active"}),
        Evidence("db", "projects 表 + project_members 表 + employees 表", "PRJ-003 移动端 App", "project_id: PRJ-003", {"project_id": "PRJ-003", "name": "移动端 App", "status": "active"}),
    ]

    answer = build_answer(
        "active 项目有多少个？",
        plan,
        evidence,
        client=FakeClient("active 项目包括若干项目。\n\n> 来源：项目表"),
        answer_polish=True,
    )

    body = answer.split("> 来源：", 1)[0]
    assert "2 个项目" in body
    assert "PRJ-001" in body


def test_recent_events_uses_deterministic_formatter_when_polish_enabled():
    plan = QueryPlan("hybrid", "recent_events", {"query": "最近 会议 项目"})
    evidence = [
        Evidence(
            "kb",
            "meeting_notes/2026-03-15-tech-sync.md file",
            "# 2026 年 3 月技术同步会纪要\n\n## 决议事项\n| 决议 | 说明 | 负责人 |\n| 代码重构 | 下周启动，为期 2 周 | 张三 |",
            "meeting_notes/2026-03-15-tech-sync.md",
            {"recall": "file"},
        ),
        Evidence(
            "db",
            "projects 表 + project_members 表 + employees 表",
            "PRJ-001 ReMe 记忆框架",
            "project_id: PRJ-001",
            {"project_id": "PRJ-001", "name": "ReMe 记忆框架", "status": "active"},
        ),
    ]

    answer = build_answer(
        "最近有什么事？",
        plan,
        evidence,
        client=FakeClient("最近主要是技术同步会。\n\n> 来源：meeting_notes/2026-03-15-tech-sync.md"),
        answer_polish=True,
    )

    body = answer.split("> 来源：", 1)[0]
    assert "代码重构" in body
    assert "PRJ-001" in body
