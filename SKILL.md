---
name: enterprise-qa
description: Use this skill to answer enterprise employee, project, attendance, performance, policy, reimbursement, FAQ, and meeting-note questions using the bundled SQLite database and Markdown knowledge base. The skill routes natural-language questions through a DeepSeek-compatible QueryPlan, validates the plan, executes safe local queries, and returns cited answers.
---

# Enterprise QA

Use this skill when the user asks enterprise work-related questions such as:

- "张三的部门是什么？"
- "李四的上级是谁？"
- "年假怎么计算？"
- "王五符合 P5 晋升 P6 条件吗？"
- "最近有什么事？"

## Run

From this skill directory, run:

```bash
python scripts/cli.py "张三的部门是什么？"
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

## Safety

- The LLM never writes SQL.
- The LLM only returns a structured `QueryPlan`.
- Python validates the plan and runs parameterized SQLite queries.
- Answers must include sources or clearly explain missing information.
