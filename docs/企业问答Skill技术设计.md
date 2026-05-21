# 企业问答 Skill 技术设计

## 1. 目标

构建一个用于企业问答的 Claude Code Skill。该 Skill 通过组合以下信息源回答自然语言问题：

- SQLite 表中的结构化数据：`employees`、`projects`、`project_members`、`attendance`、`performance_reviews`。
- 知识库目录下 Markdown 文档中的非结构化知识。
- 通过 DeepSeek 兼容 API 完成的 LLM 问题理解与答案润色。

实现语言使用 Python。LLM 不生成 SQL，只生成受控的 `QueryPlan`；Python 负责校验计划，并执行参数化查询模板。

## 2. 已确认决策

- Skill 类型：Claude Code Skill。
- 运行技术栈：Python。
- 发布形态：GitHub 仓库根目录即 Skill 目录，clone 到 `~/.claude/skills/enterprise-qa` 后可被 Claude Code 发现。
- 脚本布局：Python 文件直接放在 `scripts/` 下，不再额外套包目录。
- 主 LLM：DeepSeek 官方 OpenAI-compatible API。
- 备用 LLM：SiliconFlow 托管的 DeepSeek，使用 OpenAI-compatible API。
- LLM 职责：只负责查询规划和答案润色。
- SQL 职责：由 Python 控制，使用参数化、白名单查询模板。
- 答案策略：默认启用 LLM 基于 Evidence 润色答案；润色失败时使用 Python formatter 兜底。
- 运行时依赖：尽量只使用 Python 标准库；`requirements.txt` 优先只放开发和测试依赖。
- 发布内容：最终 GitHub 仓库包含 `AGENTS.md`，用于约束后续仓库维护行为。
- 测试策略：单元测试中 mock LLM 返回，不真实调用外部 API。

## 3. 高层流程

```text
用户问题
  ->
Skill 入口
  ->
LLM planner 生成 QueryPlan JSON
  ->
PlanValidator 检查模板、参数、字段、数据源类型和安全性
  ->
查询执行器运行 DB 模板和/或 KB 检索
  ->
生成 Evidence 证据对象
  ->
答案引擎要求 LLM 只基于 Evidence 润色答案
  ->
如果润色失败，Python formatter 兜底
  ->
输出最终答案和来源
```

核心安全边界位于“规划”和“执行”之间。LLM 可以选择受支持的模板并填充参数，但不能选择任意表、任意 join、任意字段或 SQL 文本。

## 4. 目录布局

```text
enterprise-qa/
+-- SKILL.md
+-- scripts/
    +-- cli.py
    +-- init_db.py
    +-- config.py
    +-- llm_client.py
    +-- intent.py
    +-- planner.py
    +-- validator.py
    +-- query_templates.py
    +-- knowledge_index.py
    +-- answer_engine.py
    +-- context.py
+-- data/
    +-- enterprise.db
    +-- schema.sql
    +-- seed_data.sql
    +-- knowledge/
        +-- hr_policies.md
        +-- promotion_rules.md
        +-- tech_docs.md
        +-- finance_rules.md
        +-- faq.md
        +-- meeting_notes/
+-- config.yaml.example
+-- requirements.txt
+-- docs/
    +-- 企业问答Skill技术设计.md
+-- README.md
+-- AGENTS.md

tests/
+-- test_planner.py
+-- test_validator.py
+-- test_query_templates.py
+-- test_knowledge_index.py
+-- test_answer_engine.py
+-- test_cli_cases.py
```

职责说明：

- `SKILL.md`：告诉 Claude Code 何时使用该 Skill，以及如何调用 Python 入口。
- `scripts/`：存放 Skill 的 Python 执行脚本，所有脚本直接放在该目录下。
- `cli.py`：命令行入口；接收问题和可选上下文文件路径。
- `init_db.py`：根据 `data/schema.sql` 和 `data/seed_data.sql` 初始化或重建 `data/enterprise.db`。
- `config.py`：从环境变量和可选 YAML 配置中加载配置。
- `llm_client.py`：OpenAI-compatible 聊天客户端，支持 provider fallback。
- `intent.py`：定义 `QueryPlan`、`Evidence` 和结果对象，可使用 dataclass 或 Pydantic model。
- `planner.py`：调用 LLM，将自然语言转换为 `QueryPlan`。
- `validator.py`：校验计划模板、参数、数据源类型、可用字段和危险输入。
- `query_templates.py`：集中维护参数化 SQLite 查询模板。
- `knowledge_index.py`：索引并检索相关 Markdown 分块。
- `answer_engine.py`：融合证据，调用 LLM 润色答案，并在失败时回退到确定性格式化。
- `context.py`：保存轻量的最近对话上下文，用于追问问题。
- `data/`：随 Skill 一起发布的运行数据，包含开箱可用的 `enterprise.db`、建表脚本、种子数据和知识库。
- `tests/`：pytest 测试，验证查询模板、校验器、知识库检索和公开问答案例。
- `docs/`：开发和交付文档，后续技术方案、实施计划和验收说明继续放在这里。
- `README.md`：面向使用者的安装、配置和运行说明。
- `AGENTS.md`：本仓库开发维护规范，随最终 GitHub 仓库一起发布。

## 5. 配置

配置可以来自环境变量，也可以来自 `config.yaml`。

示例：

```yaml
database:
  type: sqlite
  path: ./data/enterprise.db

knowledge_base:
  root_path: ./data/knowledge
  index_type: bm25

llm:
  timeout_seconds: 20
  providers:
    - name: deepseek
      api_key: ${DEEPSEEK_API_KEY}
      base_url: https://api.deepseek.com
      model: deepseek-chat
    - name: siliconflow
      api_key: ${SILICONFLOW_API_KEY}
      base_url: https://api.siliconflow.cn/v1
      model: deepseek-ai/DeepSeek-V3

timezone: Asia/Shanghai
current_date: 2026-03-27
```

Provider 行为：

- 按配置顺序依次尝试 providers。
- 如果某个 provider 缺少 API key，则跳过。
- 遇到超时、网络错误、限流或 provider 返回无效响应时触发 fallback。
- 测试中 mock LLM client，不需要真实 API key。

## 6. QueryPlan 模型

LLM 返回严格 JSON。校验器会拒绝格式错误的计划。

```json
{
  "source_type": "db",
  "template": "employee_projects",
  "params": {
    "employee_name": "张三"
  },
  "output_mode": "list",
  "needs_clarification": false,
  "clarification_question": null
}
```

字段说明：

- `source_type`：`db`、`kb`、`hybrid` 或 `unknown`。
- `template`：一个受支持的模板名称。
- `params`：特定模板所需参数。
- `output_mode`：`summary`、`list`、`count` 或 `table`。
- `needs_clarification`：当问题过于模糊时为 true。
- `clarification_question`：需要澄清时展示给用户的追问。

LLM prompt 包含：

- 数据库 schema 摘要。
- 知识库文档列表。
- 受支持模板名称和参数 schema。
- 当前日期：2026-03-27。
- 明确指令：绝不输出 SQL。
- 明确指令：遇到不支持或不确定问题时使用 `unknown` 或 `needs_clarification`。

## 7. 支持的查询模板

初始模板白名单：

| 模板 | 数据源 | 用途 |
|---|---|---|
| `employee_basic` | DB | 查询员工字段，例如部门、邮箱、职级、入职日期、状态 |
| `employee_manager` | DB | 查询员工直属上级，并解析为员工姓名 |
| `department_members` | DB | 按部门统计或列出在职员工 |
| `employee_projects` | DB | 查询员工参与的项目及角色 |
| `department_projects` | DB | 查询某部门或全量员工参与的项目，可按状态过滤 |
| `project_members` | DB | 查询某项目成员 |
| `attendance_stats` | DB | 按员工和时间范围统计考勤 |
| `performance_summary` | DB | 按年份或季度查询员工绩效 |
| `department_performance_summary` | DB | 基于个人绩效记录汇总部门层面的绩效情况 |
| `promotion_eligibility` | Hybrid | 结合晋升规则、员工绩效和项目事实判断晋升资格 |
| `kb_search` | KB | 查询制度、财务、FAQ、技术文档和会议纪要 |
| `recent_events` | Hybrid | 查询最近会议纪要和 active/planning 项目事实 |
| `unknown` | None | 不支持或不安全的问题 |

这是“受控泛化”：系统支持常见员工、部门、项目、考勤、绩效和制度问题，但不会变成任意 SQL agent。

## 8. QueryPlan 校验

`PlanValidator` 负责强制执行：

- 模板必须在白名单内。
- 必填参数必须存在。
- 参数类型必须匹配模板 schema。
- `performance_summary.quarter` 会把 `Q1`、`Q2`、`第一季度`、`第二季度` 等表达归一化为 `1-4`，非法季度会被拒绝。
- 项目类 `status` 会把 `暂停`、`paused`、`on hold`、`on_hold` 归一化为 `on_hold`，并统一 `在研/进行中/active`、`规划/planning`、`完成/completed` 等表达。
- 日期范围必须有效且有边界。
- 字段名必须来自白名单。
- 不直接暴露 `manager_id` 等原始敏感字段；上级类答案需要解析成人名。
- 疑似 SQL 注入输入在执行前拒绝。
- 不支持的计划转换为清晰拒绝或澄清问题。

示例：

问题：

```text
SELECT * FROM users WHERE '1'='1
```

结果：

```text
我不能执行原始 SQL 或疑似注入内容。请用自然语言描述你想查询的信息。
```

问题：

```text
张三的老师是谁？
```

行为：

- LLM 可能尝试使用 `employee_basic`，并给出字段 `teacher`。
- Validator 会拒绝 `teacher`，因为它不是允许的员工字段。
- KB 检索也找不到可靠的老师或导师分配记录。
- 答案说明当前数据源不包含该信息。

## 9. 数据库查询执行

所有 DB 访问都使用 SQLite 参数绑定。

示例模板行为：

### `employee_projects`

输入：

```json
{
  "employee_name": "张三"
}
```

SQL 形态：

```sql
SELECT p.project_id, p.name, p.status, pm.role, pm.join_date
FROM employees e
JOIN project_members pm ON pm.employee_id = e.employee_id
JOIN projects p ON p.project_id = pm.project_id
WHERE e.name = ? AND e.status = 'active'
ORDER BY p.project_id
```

参数：

```text
["张三"]
```

代码不会把用户输入拼接进 SQL。

### `department_projects`

输入选项：

```json
{
  "department": "研发部",
  "status": "active"
}
```

或：

```json
{
  "status": ["active", "planning"]
}
```

当未提供 `department` 时，查询所有在职员工参与的项目；`recent_events` 默认使用 `active/planning` 状态集合，避免把“最近有什么事”固定到单一部门。项目状态进入 SQL 前会归一化到数据库枚举，例如 `paused` 会转换为 `on_hold`。

### `department_performance_summary`

输入选项：

```json
{
  "employee_name": "张三",
  "year": 2025,
  "scope": "employee_department"
}
```

或：

```json
{
  "department": "研发部",
  "year": 2025
}
```

执行步骤：

1. 如果提供 `employee_name`，先解析该员工所在部门。
2. 查询该部门的在职员工。
3. 查询这些员工在指定年份的绩效记录。
4. 计算个人平均 KPI、等级分布，以及基于已有记录的部门平均值。
5. 明确说明该结果是由个人绩效记录汇总而来，因为不存在单独的部门绩效表。

该模板可以处理这类问题：

```text
张三部门的 2025 年绩效如何？
```

同时不会伪造不存在的部门绩效记录。

## 10. 知识库检索

知识库是 Markdown。系统不应为了回答单个问题而盲目 dump 整个文件。

索引方式：

- 递归扫描配置知识库路径下的 Markdown 文件。
- 按标题和短段落切分。
- 保存分块文本、文件路径和标题路径。
- 使用 BM25 或轻量关键词匹配为分块打分。
- 返回超过阈值的 top matches。

Evidence 示例：

```json
{
  "source_type": "kb",
  "source": "hr_policies.md §请假类型",
  "content": "年假：入职满 1 年享 5 天，每增 1 年 +1 天，上限 15 天"
}
```

对于无匹配问题，例如：

```text
xyzabc123 怎么报销
```

系统返回没有找到相关制度信息，并且不编造答案。

## 11. Evidence 模型

所有查询结果在生成答案前都会转换为 Evidence。

```json
{
  "kind": "db",
  "source": "employees 表",
  "locator": "employee_id: EMP-001",
  "data": {
    "name": "张三",
    "department": "研发部"
  }
}
```

Evidence 规则：

- 除澄清或不支持请求外，最终答案至少引用一个来源。
- 混合答案需要同时引用 DB 和 KB 来源。
- 衍生统计需要引用源表，并说明推导方式。
- 信息缺失时，在有帮助的情况下说明检查过哪些来源。

## 12. 答案生成

答案引擎有两条路径：

1. 优先路径：LLM 润色。
2. 兜底路径：确定性的 Python formatter。

LLM 润色 prompt：

- 只接收用户问题、已校验计划和 Evidence。
- 不得添加 Evidence 中不存在的事实。
- 必须包含来自 Evidence 的来源引用。
- 必须清晰说明缺失信息。
- 除非表格有帮助，否则避免直接 dump 原始数据。

如果润色 LLM 失败、超时或返回无效内容，Python formatter 生成简洁答案。

晋升判断示例：

```text
王五目前不符合 P5→P6 晋升条件。

| 条件 | 要求 | 王五情况 | 结果 |
|---|---|---|---|
| 入职年限 | 满 1 年 | 已满 2 年 | 通过 |
| KPI | 连续 2 季度 KPI≥85 | 2025 Q3=78，Q4=82 | 不通过 |
| 项目参与 | 主导或核心参与项目≥3 个 | 1 个：PRJ-005 core | 不通过 |

> 来源：promotion_rules.md §P5→P6 + employees 表 + performance_reviews 表 + project_members 表
```

## 13. 多轮上下文

Skill 支持轻量追问。

保存的上下文：

```json
{
  "last_template": "promotion_eligibility",
  "last_params": {
    "employee_name": "王五",
    "from_level": "P5",
    "to_level": "P6"
  },
  "last_focus": "promotion"
}
```

示例：

```text
User: 王五符合 P5 晋升 P6 条件吗？
Assistant: ...
User: 那张三呢？
```

规划器可以推断：

```json
{
  "template": "promotion_eligibility",
  "params": {
    "employee_name": "张三",
    "from_level": "P5",
    "to_level": "P6"
  }
}
```

推断出的计划仍然必须经过 `PlanValidator`。上下文不会带来额外权限。

## 14. 歧义处理

系统需要区分“不支持的问题”和“有歧义但可回答的问题”。

示例：

```text
张三部门的 2025 年绩效如何？
```

优先行为：

- 理解为张三所在部门的部门绩效汇总。
- 说明结果来自个人绩效记录汇总，而不是官方部门绩效表。

如果置信度低：

```text
你是想看张三本人的 2025 年绩效，还是张三所在部门的 2025 年绩效汇总？
```

示例：

```text
最近有什么事？
```

行为：

- 可以询问用户指的是会议、项目还是公司动态。
- 也可以返回最近会议纪要和 active/planning 项目，并说明“最近”是相对 2026-03-27 理解的。

## 15. 错误处理

需要处理的情况：

- 缺少 DB 路径。
- DB 连接失败。
- 缺少 KB 路径。
- 查询结果为空。
- 缺少 LLM API key。
- LLM 超时或返回无效 JSON。
- 所有 LLM providers 均失败。
- 不支持的查询模板。
- 不安全输入或原始 SQL。

错误信息应该清晰、面向用户。正常答案中不应展示内部 traceback。

## 16. 测试覆盖

必测公开用例：

| ID | 问题 | 预期行为 |
|---|---|---|
| T01 | 张三的部门是什么？ | 研发部 |
| T02 | 李四的上级是谁？ | CEO |
| T03 | 年假怎么计算？ | 满 1 年 5 天，每年 +1，上限 15 天 |
| T04 | 迟到几次扣钱？ | 4-6 次开始扣，50 元/次 |
| T05 | 张三负责哪些项目？ | 4 个项目及角色正确 |
| T06 | 研发部有多少人？ | 4 名在职员工 |
| T07 | 王五符合 P5 晋升 P6 条件吗？ | 不符合，KPI 和项目数不满足 |
| T08 | 张三 2 月迟到几次？ | 2 次 |
| T09 | 查一下 EMP-999 | 友好提示无此员工 |
| T10 | 最近有什么事？ | 追问澄清，或返回最近会议/项目 |
| T11 | SELECT * FROM users WHERE '1'='1 | 拒绝不安全的 SQL-like 输入 |
| T12 | xyzabc123 怎么报销 | 无相关信息，不编造 |

追加测试：

- 李四的邮箱是什么？
- 产品部有多少人？
- 钱七符合晋升条件吗？
- 差旅费报销标准是什么？
- 3 月全员大会说了什么？
- 张三 2025 年绩效如何？
- 有哪些在研项目？
- 张三的老师是谁？
- 张三部门的 2025 年绩效如何？
- 多轮：先问“王五符合晋升条件吗？”，再问“那张三呢？”

覆盖率目标：

- 核心模块行覆盖率至少达到 80%。
- 查询模板和 validator 需要重点单元测试。
- CLI smoke test 使用 mock planner 输出，避免外部调用。

## 17. 实施顺序

1. 创建 Skill 骨架和配置加载。
2. 根据提供的 schema 和 seed data 初始化 SQLite 数据库。
3. 实现 `QueryPlan`、`Evidence` 和 validator。
4. 实现公开 DB 用例所需查询模板。
5. 实现 Markdown 索引和 KB 检索。
6. 实现 DeepSeek/SiliconFlow LLM client。
7. 实现 planner prompt 和严格 JSON 解析。
8. 实现带 LLM 润色和 Python fallback 的 answer engine。
9. 实现轻量上下文处理。
10. 为 T01-T12 和追加样例添加测试。
11. 在 `SKILL.md` 中添加使用说明。

## 18. 设计边界

该 Skill 有意不支持任意自然语言转 SQL。

它支持：

- 公开测试用例。
- 通过替换员工、部门、年份、项目或制度主题来支持同类问题。
- 围绕员工、项目、考勤和绩效的一组受控安全 join。
- 清晰的未知和不支持问题处理。

它不会尝试回答无限复杂的分析问题，例如：

```text
迟到次数最多的人绩效如何，再列出他参与过预算最高的项目？
```

对于这类多跳问题，系统应要求用户拆分请求，或返回当前不支持该查询类型。

这个边界是有意设计的：企业数据访问应该先做到安全、可解释、可测试，再追求更宽的覆盖范围。

## 19. 实现状态

当前实现遵循本设计：

- 仓库根目录即 Skill 目录。
- `scripts/` 使用扁平 Python 文件布局。
- 运行时优先使用标准库。
- 查询规划使用单次 LLM 调用。
- 答案默认启用 LLM 润色，失败时 Python formatter 兜底。
- 测试中 mock LLM，不真实调用外部 API。
