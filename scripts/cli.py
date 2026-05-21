from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Callable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.answer_engine import build_answer
from scripts.config import load_config
from scripts.context import load_context, save_context
from scripts.intent import Evidence, QueryPlan
from scripts.knowledge_index import search_knowledge
from scripts.llm_client import LlmClient, LlmError
from scripts.planner import plan_question
from scripts.query_templates import execute_db_plan
from scripts.validator import PlanValidationError, validate_plan


Planner = Callable[[str, dict], QueryPlan]


def _execute_plan(plan: QueryPlan, db_path: Path, kb_path: Path) -> list[Evidence]:
    if plan.template == "unknown":
        return []
    if plan.source_type == "kb" or plan.template == "kb_search":
        return search_knowledge(kb_path, str(plan.params.get("query", plan.params.get("topic", ""))))
    if plan.template == "attendance_policy_check":
        policy_topic = str(plan.params.get("policy_topic", "迟到规则"))
        return execute_db_plan(db_path, plan) + search_knowledge(kb_path, policy_topic)
    if plan.template == "leave_entitlement_check":
        leave_type = str(plan.params.get("leave_type", "年假"))
        return execute_db_plan(db_path, plan) + search_knowledge(kb_path, f"{leave_type} 制度")
    if plan.template == "promotion_eligibility":
        from_level = str(plan.params.get("from_level", "P5"))
        to_level = str(plan.params.get("to_level", "P6"))
        return execute_db_plan(db_path, plan) + search_knowledge(kb_path, f"{from_level} 晋升 {to_level} 条件")
    if plan.template == "recent_events":
        meeting_notes_path = kb_path / "meeting_notes"
        notes_root = meeting_notes_path if meeting_notes_path.exists() else kb_path
        kb = search_knowledge(notes_root, str(plan.params.get("query", "最近 会议 项目")))
        if notes_root != kb_path:
            kb = [
                Evidence(
                    kind=item.kind,
                    source=f"meeting_notes/{item.source}",
                    locator=f"meeting_notes/{item.locator}" if item.locator else None,
                    content=item.content,
                    data=item.data,
                )
                for item in kb
            ]
        project_params: dict[str, object] = {"status": plan.params.get("status", ["active", "planning"])}
        if "department" in plan.params:
            project_params["department"] = plan.params["department"]
        projects = execute_db_plan(db_path, QueryPlan("db", "department_projects", project_params))
        return kb + projects
    return execute_db_plan(db_path, plan)


def answer_question(
    question: str,
    *,
    planner: Planner | None = None,
    polish_client: LlmClient | None = None,
    context_path: Path | None = None,
) -> str:
    config = load_config()
    context = load_context(context_path)
    llm_client = polish_client
    if planner is None:
        llm_client = LlmClient(config.providers, timeout_seconds=config.timeout_seconds)
        planner = lambda user_question, ctx: plan_question(llm_client, user_question, ctx)

    try:
        plan = validate_plan(planner(question, context))
    except PlanValidationError as exc:
        return f"我不能执行这个查询：{exc}"
    except LlmError as exc:
        return f"我不能生成查询计划：LLM provider 不可用。{exc}"

    if plan.needs_clarification and plan.clarification_question:
        return plan.clarification_question

    evidences = _execute_plan(plan, config.database_path, config.knowledge_path)
    save_context(context_path, plan)
    return build_answer(
        question,
        plan,
        evidences,
        client=llm_client,
        answer_polish=config.answer_polish,
        current_date=config.current_date,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Enterprise QA Skill CLI")
    parser.add_argument("question")
    parser.add_argument("--context", type=Path, default=None)
    args = parser.parse_args()
    print(answer_question(args.question, context_path=args.context))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
