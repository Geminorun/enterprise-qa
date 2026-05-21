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


def test_search_meeting_notes_recalls_adjacent_sections():
    evidence = search_knowledge(KB_PATH, "3 月全员大会说了什么")
    content = "\n".join(item.content for item in evidence)

    assert "营收" in content
    assert "ReMe 记忆框架 2.0" in content
    assert "年度调薪" in content
    assert any("meeting_notes/2026-03-01-allhands.md" in item.source for item in evidence)


def test_search_unknown_returns_empty():
    evidence = search_knowledge(KB_PATH, "xyzabc123 怎么报销")

    assert evidence == []
