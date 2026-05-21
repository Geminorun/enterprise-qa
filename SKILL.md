---
name: enterprise-qa
description: Use when answering enterprise work questions about employees, departments, projects, attendance, performance, promotion, leave, reimbursement, policies, FAQ, or meeting notes from the bundled SQLite database and Markdown knowledge base.
---

# Enterprise QA

Use this skill when the user asks enterprise work-related questions that should be answered from the bundled database and knowledge base.

Good fits include:

- "张三的部门是什么？"
- "李四的上级是谁？"
- "张三的直属上级的邮箱是多少？"
- "查一下 EMP-999"
- "年假怎么计算？"
- "入职未满一年的吴十有年假吗？"
- "王五上个月迟到超过扣款线了吗？"
- "王五符合 P5 晋升 P6 条件吗？"
- "3 月全员大会说了什么？"
- "最近有什么事？"

This skill can query:

- Employee, department, manager, and contact facts.
- Project membership, roles, project status, and department project relations.
- Attendance counts and supported attendance-policy checks.
- Individual performance and supported promotion checks.
- Leave, reimbursement, HR, technical, FAQ, and meeting-note knowledge.

## Run

From this skill directory, run:

```bash
python -X utf8 scripts/cli.py "张三的部门是什么？"
```

More examples:

```bash
python -X utf8 scripts/cli.py "张三的直属上级的邮箱是多少？"
python -X utf8 scripts/cli.py "王五上个月迟到超过扣款线了吗？"
python -X utf8 scripts/cli.py "入职未满一年的吴十有年假吗？"
python -X utf8 scripts/cli.py "3 月全员大会说了什么？"
```

## Configuration

Prefer environment variables:

```bash
export DEEPSEEK_API_KEY="..."
export SILICONFLOW_API_KEY="..."
```

The default data paths are:

- Database: `data/enterprise.db`
- Knowledge base: `data/knowledge`

Runtime behavior can also be configured in `config.yaml` or environment variables. Do not commit real API keys.
Use `python -X utf8` on Windows or mixed shell environments so Chinese output is encoded consistently.

## Safety

- The LLM never writes SQL.
- The LLM only returns a structured `QueryPlan`.
- Python validates the plan and runs parameterized SQLite queries.
- Answers must include sources or clearly explain missing information.

## Boundaries

- The system should not answer from unsupported fields or invent missing facts.
- SQL-like input must be rejected or converted to a safe natural-language request.
- Promotion auto-judgment is currently deterministic for P5 to P6. Other promotion levels should return facts and rule sources without forcing a supported/unsupported conclusion unless explicitly implemented.
- Language is fuzzy. Unknown or unsupported requests should return a clear limitation or ask for clarification instead of guessing.
