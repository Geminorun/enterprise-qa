from scripts.config import LlmProviderConfig
from scripts.intent import QueryPlan
from scripts.llm_client import LlmClient, LlmError
from scripts.planner import PLAN_PROMPT, parse_plan_json

import pytest


class FakeTransport:
    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def post_json(self, url, headers, payload, timeout):
        self.calls += 1
        return {"choices": [{"message": {"content": self.response}}]}


def test_parse_plan_json_strips_code_fence():
    content = """```json
{"source_type":"db","template":"employee_projects","params":{"employee_name":"张三"},"output_mode":"list"}
```"""

    plan = parse_plan_json(content)

    assert plan == QueryPlan("db", "employee_projects", {"employee_name": "张三"}, "list")


def test_parse_plan_json_wraps_invalid_json():
    with pytest.raises(LlmError, match="无效 JSON"):
        parse_plan_json("我会先解释一下，然后再给 JSON")


def test_plan_prompt_includes_template_parameter_contracts():
    assert "employee_basic params" in PLAN_PROMPT
    assert "employee_name 或 employee_id" in PLAN_PROMPT
    assert "project_members params" in PLAN_PROMPT
    assert "示例" in PLAN_PROMPT


def test_llm_client_uses_first_available_provider():
    transport = FakeTransport('{"source_type":"kb","template":"kb_search","params":{"query":"年假"},"output_mode":"summary"}')
    client = LlmClient(
        [
            LlmProviderConfig("deepseek", "key", "https://api.deepseek.com", "deepseek-chat"),
        ],
        timeout_seconds=5,
        transport=transport,
    )

    content = client.chat([{"role": "user", "content": "年假怎么计算"}])

    assert '"kb_search"' in content
    assert transport.calls == 1
