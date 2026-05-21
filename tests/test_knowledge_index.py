from pathlib import Path

from scripts.knowledge_index import search_knowledge


KB_PATH = Path("data/knowledge")


def test_search_annual_leave():
    evidence = search_knowledge(KB_PATH, "年假怎么计算")

    assert evidence
    assert any("5 天" in item.content for item in evidence)
    assert any("hr_policies.md" in item.source for item in evidence)


def test_search_reimbursement():
    evidence = search_knowledge(KB_PATH, "差旅费报销标准")

    assert evidence
    assert any("finance_rules.md" in item.source for item in evidence)


def test_search_unknown_returns_empty():
    evidence = search_knowledge(KB_PATH, "xyzabc123 怎么报销")

    assert evidence == []
