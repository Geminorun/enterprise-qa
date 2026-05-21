from scripts.context import load_context, save_context
from scripts.intent import QueryPlan


def test_save_and_load_context(tmp_path):
    path = tmp_path / "context.json"
    plan = QueryPlan("hybrid", "promotion_eligibility", {"employee_name": "王五", "from_level": "P5", "to_level": "P6"})

    save_context(path, plan)
    context = load_context(path)

    assert context["last_template"] == "promotion_eligibility"
    assert context["last_params"]["employee_name"] == "王五"
