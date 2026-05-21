# 企业问答 Skill V2 全量测试报告

测试日期：2026-05-21
被测分支：`main`
测试对象：Claude Code Skill `enterprise-qa`
测试方式：真实调用当前 LLM 生成 QueryPlan，经 validator、受控查询执行器和本地 formatter 输出答案。

## 1. 测试配置

| 项目 | 值 |
|---|---|
| `thinking_enabled` | `False` |
| `answer_polish` | `False` |
| `timeout_seconds` | `50` |
| 当前日期 | `2026-03-27` |
| 时区 | `Asia/Shanghai` |
| 数据库 | `data\enterprise.db` |
| 知识库 | `data\knowledge` |

运行前显式设置：

```powershell
$env:ENTERPRISE_QA_THINKING_ENABLED='false'
$env:ENTERPRISE_QA_ANSWER_POLISH='false'
$env:ENTERPRISE_QA_LLM_TIMEOUT='50'
python -X utf8 scripts/run_v2_full_test.py
```

## 2. 总体结论

本轮共执行 49 条用例，总耗时约 306.19s，平均 6.25s/题。

- 自动关键词判定通过：45
- 自动关键词判定未通过：4
- 人工复核后通过：46
- 人工复核后未通过：3

| 分类 | 用例数 | 通过 | 未通过 |
|---|---:|---:|---:|
| V2刁钻 | 20 | 17 | 3 |
| 上次报错回归 | 10 | 10 | 0 |
| 官方必过 | 12 | 12 | 0 |
| 官方追加 | 7 | 7 | 0 |

## 3. 失败与风险清单

人工复核后，T11 属于自动检查词过窄导致的误报：它路由到 `unknown`，没有 evidence，没有执行 SQL，并要求用户改成业务查询，符合“拦截 SQL 注入”的预期。

剩余 3 个真实缺口：

- **B08 李四 2025 年平均 KPI 是多少？**：缺少：93.25；路由 `performance_summary`。
- **B10 PRJ-005 为什么暂停？**：未命中任一：没有 / 未提供 / 不能确认 / 无法确认；路由 `recent_events`。
- **B12 active 项目有多少个？**：缺少：2；路由 `department_projects`。

## 4. 用例总表

| ID | 分类 | 问题 | 刁钻点/考察点 | 预期 | 路由 | 结果 | 耗时 |
|---|---|---|---|---|---|---|---:|
| T01 | 官方必过 | 张三的部门是什么？ | 基础 DB 查询 | 研发部 | `employee_basic` | 通过 | 7.01s |
| T02 | 官方必过 | 李四的上级是谁？ | 员工自关联查询 | CEO / EMP-000 | `employee_manager` | 通过 | 7.49s |
| T03 | 官方必过 | 年假怎么计算？ | KB 制度检索 | 满 1 年 5 天，每年 +1，上限 15 天 | `kb_search` | 通过 | 6.90s |
| T04 | 官方必过 | 迟到几次扣钱？ | KB 制度检索 | 4-6 次开始扣，50 元/次 | `kb_search` | 通过 | 8.41s |
| T05 | 官方必过 | 张三负责哪些项目？ | 员工项目关联查询 | PRJ-001、PRJ-002、PRJ-003、PRJ-004 及角色 | `employee_projects` | 通过 | 8.66s |
| T06 | 官方必过 | 研发部有多少人？ | 部门人数统计 | 4 人 | `department_members` | 通过 | 7.14s |
| T07 | 官方必过 | 王五符合 P5 晋升 P6 条件吗？ | DB + KB 混合判断 | 不符合，KPI 80<85，项目数 1<3 | `promotion_eligibility` | 通过 | 7.13s |
| T08 | 官方必过 | 张三 2 月迟到几次？ | 时间范围考勤查询 | 2 次 | `attendance_stats` | 通过 | 5.88s |
| T09 | 官方必过 | 查一下 EMP-999 | 不存在员工边界 | 明确告知无此员工 | `employee_basic` | 通过 | 5.68s |
| T10 | 官方必过 | 最近有什么事？ | 模糊时间和事件查询 | 追问澄清或返回最近会议/项目 | `recent_events` | 通过 | 5.90s |
| T11 | 官方必过 | SELECT * FROM users WHERE '1'='1 | 安全边界 | 拦截 SQL 注入 | `unknown` | 人工通过（自动误报） | 6.04s |
| T12 | 官方必过 | xyzabc123 怎么报销 | 无匹配 KB 查询 | 告知无相关信息，不编造 | `kb_search` | 通过 | 5.92s |
| A01 | 官方追加 | 李四的邮箱是什么？ | 同模板换字段 | lisi@company.com | `employee_basic` | 通过 | 5.69s |
| A02 | 官方追加 | 产品部有多少人？ | 同模板换部门 | 3 人 | `department_members` | 通过 | 5.73s |
| A03 | 官方追加 | 钱七符合晋升条件吗？ | 默认晋升级别推断 | 不符合 | `promotion_eligibility` | 通过 | 5.81s |
| A04 | 官方追加 | 差旅费报销标准是什么？ | KB 财务制度 | 机票、酒店、餐补等标准 | `kb_search` | 通过 | 5.93s |
| A05 | 官方追加 | 3 月全员大会说了什么？ | 会议纪要召回 | 营收、目标、ReMe、AI 实验室、调薪等 | `kb_search` | 通过 | 6.68s |
| A06 | 官方追加 | 张三 2025 年绩效如何？ | 绩效多记录查询 | Q1-Q4 KPI 或平均 89.25 | `performance_summary` | 通过 | 5.74s |
| A07 | 官方追加 | 有哪些在研项目？ | 项目状态筛选 | PRJ-001、PRJ-003 | `department_projects` | 通过 | 5.88s |
| R01 | 上次报错回归 | 3 月全员大会说了什么？ | 曾只命中标题块 | 会议纪要完整召回 | `kb_search` | 通过 | 5.67s |
| R02 | 上次报错回归 | 张三 P6 晋升 P7 可以吗？ | 曾错误套用晋升口径 | 不能套用 P5→P6 规则 | `promotion_eligibility` | 通过 | 5.84s |
| R03 | 上次报错回归 | 王五上个月迟到超过扣款线了吗？ | 考勤 + 制度混合判断 | 2 月迟到 5 次，超过扣款线，每次 50 元 | `attendance_policy_check` | 通过 | 6.92s |
| R04 | 上次报错回归 | CEO 的邮箱是多少？ | 特殊员工名实体识别 | ceo@company.com | `employee_basic` | 通过 | 5.62s |
| R05 | 上次报错回归 | 入职未满一年的吴十有年假吗？ | 用户前提需核实 | 查询入职日期后判定无年假 | `leave_entitlement_check` | 通过 | 6.84s |
| R06 | 上次报错回归 | 张三的直属上级的邮箱是多少？ | 两跳上级联系方式 | ceo@company.com | `employee_manager` | 通过 | 5.62s |
| R07 | 上次报错回归 | 技术同步会说下周启动什么？ | 会议纪要决议项 | 下周启动代码重构 | `kb_search` | 通过 | 5.83s |
| R08 | 上次报错回归 | EMP-999 符合晋升条件吗？ | 不存在员工 + 混合模板 | 明确无此员工/无法确认 | `promotion_eligibility` | 通过 | 5.89s |
| R09 | 上次报错回归 | 最近有什么事？ | recent_events 聚合 | 最近会议或 active/planning 项目 | `recent_events` | 通过 | 5.87s |
| R10 | 上次报错回归 | 张三 2 月迟到几次？ | 考勤统计稳定性 | 2 次 | `attendance_stats` | 通过 | 5.92s |
| B01 | V2刁钻 | 张三所在部门的 2025 年绩效如何？ | 涉及张三本人、部门反查、绩效汇总，且没有独立部门绩效表 | 研发部平均 KPI，说明由个人绩效汇总 | `department_performance_summary` | 通过 | 5.88s |
| B02 | V2刁钻 | 张三的老师是谁？ | 老师字段不存在，考察是否幻觉 | 不编造老师实体，澄清或说明无数据 | `unknown` | 通过 | 6.09s |
| B03 | V2刁钻 | 研发部有哪些在研和规划中的项目？ | 部门关联 + 多状态过滤 | PRJ-001、PRJ-002、PRJ-003 | `department_projects` | 通过 | 5.97s |
| B04 | V2刁钻 | 产品部有什么暂停项目？ | 中文状态别名到 on_hold | PRJ-005 官网改版 | `department_projects` | 通过 | 5.77s |
| B05 | V2刁钻 | 张三有哪些已完成项目？ | 员工项目 + completed 状态 | 仅 PRJ-004 | `employee_projects` | 通过 | 5.89s |
| B06 | V2刁钻 | 王五 2025 Q1 绩效如何？ | 员工存在但季度记录不存在 | 明确无 Q1 记录 | `performance_summary` | 通过 | 6.89s |
| B07 | V2刁钻 | 钱七符合 P5 晋升 P6 条件吗？ | 接近阈值，不能只看入职年限 | 不符合 | `promotion_eligibility` | 通过 | 6.11s |
| B08 | V2刁钻 | 李四 2025 年平均 KPI 是多少？ | 四季度聚合平均 | 93.25 | `performance_summary` | 未通过 | 6.82s |
| B09 | V2刁钻 | 谁是 PRJ-001 的负责人？ | 项目 lead 到员工名 | 张三 | `project_members` | 通过 | 5.61s |
| B10 | V2刁钻 | PRJ-005 为什么暂停？ | 区别状态和原因 | 状态有记录但原因未提供，不能编造 | `recent_events` | 未通过 | 5.71s |
| B11 | V2刁钻 | 今年有调薪计划吗？ | 会议 Q&A 召回 | 4 月启动，预算 15% | `kb_search` | 通过 | 5.85s |
| B12 | V2刁钻 | active 项目有多少个？ | 英文状态枚举 + 统计 | 2 个 | `department_projects` | 未通过 | 5.66s |
| B13 | V2刁钻 | 市场部有哪些在研项目？ | 空结果 + 状态过滤 | 无 active 项目，不能返回暂停项目 | `department_projects` | 通过 | 5.86s |
| B14 | V2刁钻 | ReMe 记忆框架有哪些成员，谁是 lead？ | 项目名 + 成员角色 | 张三 lead，李四 core，钱七 contributor | `project_members` | 通过 | 5.82s |
| B15 | V2刁钻 | 研发部有哪些离职员工？ | 员工状态过滤不应默认 active | 离职员工 | `department_members` | 通过 | 7.04s |
| B16 | V2刁钻 | 张三有哪些在研项目？ | 员工项目 + active 状态 | PRJ-001、PRJ-003 | `employee_projects` | 通过 | 5.85s |
| B17 | V2刁钻 | 请问旷工规则是什么？ | KB 制度局部检索 | 迟到 7 次以上视为旷工 1 天 | `kb_search` | 通过 | 5.71s |
| B18 | V2刁钻 | 试用期多久？ | FAQ 检索 | 3-6 个月 | `kb_search` | 通过 | 6.87s |
| B19 | V2刁钻 | 周九参与了哪些项目？ | 员工项目查询，非张三/李四 | PRJ-003 lead | `employee_projects` | 通过 | 5.90s |
| B20 | V2刁钻 | 产品部 2025 年绩效怎么样？ | 部门绩效统计可能不存在，需说明汇总口径 | 基于个人绩效汇总，不是独立部门绩效表 | `department_performance_summary` | 通过 | 7.25s |

## 5. Review 诊断

以下内容按代码 Review 标准整理，供修复时逐项处理。修复原则：不要为了单个测试问题写一对一特判，应把能力收敛到规则引擎、受控模板、查询执行器或 formatter 的通用逻辑中。

### [P1] 晋升规则引擎只实现了 P5→P6，其他晋升级别被直接拒判

- 位置：`scripts/answer_engine.py:195`
- 现象：`_format_promotion_answer` 中只允许 `(from_level, to_level) == ("P5", "P6")` 进入自动判定，其他晋升级别直接返回“暂不支持自动判定”。
- 影响：当用户问“张三符合晋升条件吗？”时，张三当前职级是 P6，系统只能拒判 P6→P7；同时证据中又可能召回“张三破格晋升 P6→P7”的会议纪要，最终回答会显得割裂。这个问题不是文案问题，而是晋升规则能力边界过窄。
- 建议：将 `promotion_rules.md` 中的 P4→P5、P5→P6、P6→P7、P7→P8 规则结构化为规则表或 checker map，按 `from_level/to_level` 选择对应规则。若某些条件无法由当前数据源判定，也应完整列出目标晋升级别的全部条件，并标明“已满足 / 不满足 / 待确认”，而不是只写 P5→P6。P6→P7 至少应覆盖：P6 满 2 年、连续 4 季度 KPI≥90、主导项目≥2、有技术突破或专利/论文。破格晋升会议纪要可以作为补充事实，但不能替代规则判断。

### [P2] 年度绩效查询没有处理“平均 KPI”聚合口径

- 位置：`scripts/query_templates.py:285`、`scripts/answer_engine.py:409`
- 失败用例：B08 `李四 2025 年平均 KPI 是多少？`
- 现象：查询已经拿到了李四 2025 年四个季度 KPI：95、93、91、94，但 fallback formatter 只是逐条输出明细，没有计算并回答平均值 93.25。
- 影响：用户问的是聚合结果，系统返回原始明细，答案不完整。
- 建议：让 `performance_summary` 支持聚合输出。可在执行层返回 `average_kpi`，或在 formatter 中根据 evidence 计算年度平均值；当 `output_mode=count/summary` 或问题包含“平均 KPI”时，优先输出平均值，同时保留季度明细和来源。

### [P2] 项目暂停原因缺失时没有明确说明“原因未提供”

- 位置：`scripts/answer_engine.py:99`
- 失败用例：B10 `PRJ-005 为什么暂停？`
- 现象：系统返回 `PRJ-005 官网改版：on_hold`，只说明项目处于暂停状态，没有回答“为什么”，也没有提示数据源不含暂停原因。
- 影响：用户可能误以为“官网改版”就是暂停原因，存在事实误导风险。
- 建议：当问题询问原因，但 evidence 只有状态字段、没有 reason/cause 字段时，formatter 应明确输出“当前数据源只记录该项目状态为 on_hold，未提供暂停原因，因此不能确认为什么暂停”。不要把项目名称或状态解释成原因。

### [P2] `output_mode=count` 没有被列表类项目查询尊重

- 位置：`scripts/query_templates.py:161`、`scripts/answer_engine.py:409`
- 失败用例：B12 `active 项目有多少个？`
- 现象：LLM 正确生成了 `department_projects` + `output_mode=count`，执行层也返回了 PRJ-001、PRJ-003 两条 evidence，但 formatter 只列出两个项目，没有回答“2 个”。
- 影响：路由和查询都正确，最终答案层丢失用户真正问的数量。
- 建议：在项目列表类 formatter 中统一处理 `output_mode=count`：先输出数量，再按需附带项目清单。这个能力应覆盖 `department_projects`、`employee_projects`、`project_members` 等列表型模板。

## 6. 逐题明细

### T01 张三的部门是什么？

- 分类：官方必过
- 刁钻点/考察点：基础 DB 查询
- 预期：研发部
- 自动判定：通过，命中预期要点
- 耗时：7.01s
- 原始计划：`{"source_type": "db", "template": "employee_basic", "params": {"employee_name": "张三", "field": "department"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "employee_basic", "params": {"employee_name": "张三", "field": "department"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 (employee_id: EMP-001)

实际回答：

```text
张三的department是 研发部。

> 来源：employees 表 (employee_id: EMP-001)
```

### T02 李四的上级是谁？

- 分类：官方必过
- 刁钻点/考察点：员工自关联查询
- 预期：CEO / EMP-000
- 自动判定：通过，命中预期要点
- 耗时：7.49s
- 原始计划：`{"source_type": "db", "template": "employee_manager", "params": {"employee_name": "李四"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "employee_manager", "params": {"employee_name": "李四"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 (employee_id: EMP-002)

实际回答：

```text
李四的直属上级是 CEO，邮箱是 ceo@company.com。

> 来源：employees 表 (employee_id: EMP-002)
```

### T03 年假怎么计算？

- 分类：官方必过
- 刁钻点/考察点：KB 制度检索
- 预期：满 1 年 5 天，每年 +1，上限 15 天
- 自动判定：通过，命中预期要点
- 耗时：6.90s
- 原始计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "年假怎么计算"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "年假怎么计算"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：faq.md section Q: 年假怎么算？ (faq.md); finance_rules.md section 差旅费标准 (finance_rules.md); hr_policies.md section 请假类型 (hr_policies.md)

实际回答：

```text
**A**: 入职满 1 年享 5 天年假，每增加 1 年 +1 天，上限 15 天。
- 年假有效期：自然年
- 未休年假：可折算工资或结转下年（最多 5 天）
| 项目 | 标准 | 说明 |
|------|------|------|
| 机票 | 经济舱 | 提前 7 天预订，特殊情况需审批 |
| 高铁 | 二等座 | - |
| 酒店 | 一线城市≤500 元/天 | 北京、上海、广州、深圳 |
| 酒店 | 其他城市≤300 元/天 | - |
| 餐补 | 出差 100 元/天 | 按自然日计算 |
| 市内交通 | 实报实销 | 优先公共交通 |
| 类型 | 薪资 | 天数 | 说明 |
|------|------|------|------|
| 年假 | 全薪 | 5 天起 | 入职满 1 年享 5 天，每增 1 年 +1 天，上限 15 天 |
| 病假 | 全薪 | 3 天/年 | 需提供医院证明 |
| 事假 | 无薪 | - | 需提前 2 工作日申请 |
| 婚假 | 全薪 | 10 天 | 凭结婚证申请 |
| 产假 | 全薪 | 98 天 | 符合国家规定 |
| 陪产假 | 全薪 | 15 天 | 男方享受 |
| 丧假 | 全薪 | 3-5 天 | 直系亲属去世 |

> 来源：faq.md section Q: 年假怎么算？ (faq.md) + finance_rules.md section 差旅费标准 (finance_rules.md) + hr_policies.md section 请假类型 (hr_policies.md)
```

### T04 迟到几次扣钱？

- 分类：官方必过
- 刁钻点/考察点：KB 制度检索
- 预期：4-6 次开始扣，50 元/次
- 自动判定：通过，命中预期要点
- 耗时：8.41s
- 原始计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "迟到几次扣钱", "topic": "迟到规则"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "迟到几次扣钱", "topic": "迟到规则"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：hr_policies.md section 迟到规则 (hr_policies.md); hr_policies.md section 工作时间 (hr_policies.md)

实际回答：

```text
| 月累计迟到次数 | 处理方式 |
|--------------|---------|
| 3 次以内 | 不扣款，口头提醒 |
| 4-6 次 | 每次扣款 50 元 |
| 7 次以上 | 视为旷工 1 天，通报批评 |
**迟到定义**：晚于 9:30 到岗视为迟到（弹性时间最晚边界）
- **标准工作时间**：9:00-18:00，午休 12:00-13:00
- **弹性范围**：早到早走，核心时段 10:00-16:00 必须在岗
- **打卡要求**：每日需打卡两次（上班、下班）

> 来源：hr_policies.md section 迟到规则 (hr_policies.md) + hr_policies.md section 工作时间 (hr_policies.md)
```

### T05 张三负责哪些项目？

- 分类：官方必过
- 刁钻点/考察点：员工项目关联查询
- 预期：PRJ-001、PRJ-002、PRJ-003、PRJ-004 及角色
- 自动判定：通过，命中预期要点
- 耗时：8.66s
- 原始计划：`{"source_type": "db", "template": "employee_projects", "params": {"employee_name": "张三"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "employee_projects", "params": {"employee_name": "张三"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 来源：projects 表 + project_members 表 (project_id: PRJ-001); projects 表 + project_members 表 (project_id: PRJ-002); projects 表 + project_members 表 (project_id: PRJ-003); projects 表 + project_members 表 (project_id: PRJ-004)

实际回答：

```text
相关项目如下：
- PRJ-001 ReMe 记忆框架：lead
- PRJ-002 智能问答系统：core
- PRJ-003 移动端 App：contributor
- PRJ-004 数据分析平台：lead

> 来源：projects 表 + project_members 表 (project_id: PRJ-001) + projects 表 + project_members 表 (project_id: PRJ-002) + projects 表 + project_members 表 (project_id: PRJ-003) + projects 表 + project_members 表 (project_id: PRJ-004)
```

### T06 研发部有多少人？

- 分类：官方必过
- 刁钻点/考察点：部门人数统计
- 预期：4 人
- 自动判定：通过，命中预期要点
- 耗时：7.14s
- 原始计划：`{"source_type": "db", "template": "department_members", "params": {"department": "研发部", "status": "active"}, "output_mode": "count", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "department_members", "params": {"department": "研发部", "status": "active"}, "output_mode": "count", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 (department: 研发部, status: active)

实际回答：

```text
研发部有 4 名在职员工：张三、李四、钱七、周九。

> 来源：employees 表 (department: 研发部, status: active)
```

### T07 王五符合 P5 晋升 P6 条件吗？

- 分类：官方必过
- 刁钻点/考察点：DB + KB 混合判断
- 预期：不符合，KPI 80<85，项目数 1<3
- 自动判定：通过，命中预期要点
- 耗时：7.13s
- 原始计划：`{"source_type": "hybrid", "template": "promotion_eligibility", "params": {"employee_name": "王五", "from_level": "P5", "to_level": "P6"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "hybrid", "template": "promotion_eligibility", "params": {"employee_name": "王五", "from_level": "P5", "to_level": "P6"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 (employee_id: EMP-003); performance_reviews 表 (employee_id: EMP-003); project_members 表 (employee_id: EMP-003); promotion_rules.md section 破格晋升 (promotion_rules.md); meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md); meeting_notes/2026-03-01-allhands.md section 人事任命 (meeting_notes/2026-03-01-allhands.md)

实际回答：

```text
王五目前不符合 P5 晋升 P6 条件：绩效未达到 P5→P6 要求；主导/核心参与项目不足 3 个。
逐项判断：
- 职级：满足，当前职级是 P5。
- 工作年限：满足，入职约 2.2 年，要求入职满 1 年。
- 绩效要求：不满足，当前平均 KPI 80.0，规则要求连续 2 季度 KPI≥85 或年度平均≥85。
- 项目经验：不满足，主导/核心参与数为 1，规则要求主导或核心参与≥3 个。
- 事故记录：待确认，当前数据源未提供 P0/P1 事故记录。

> 来源：employees 表 (employee_id: EMP-003) + performance_reviews 表 (employee_id: EMP-003) + project_members 表 (employee_id: EMP-003) + promotion_rules.md section 破格晋升 (promotion_rules.md) + meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md) + meeting_notes/2026-03-01-allhands.md section 人事任命 (meeting_notes/2026-03-01-allhands.md)
```

### T08 张三 2 月迟到几次？

- 分类：官方必过
- 刁钻点/考察点：时间范围考勤查询
- 预期：2 次
- 自动判定：通过，命中预期要点
- 耗时：5.88s
- 原始计划：`{"source_type": "db", "template": "attendance_stats", "params": {"employee_name": "张三", "status": "late", "date_range": {"start": "2026-02-01", "end": "2026-02-28"}}, "output_mode": "count", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "attendance_stats", "params": {"employee_name": "张三", "status": "late", "date_range": {"start": "2026-02-01", "end": "2026-02-28"}}, "output_mode": "count", "needs_clarification": false, "clarification_question": null}`
- 来源：attendance 表 + employees 表

实际回答：

```text
查询时间范围内，匹配的考勤记录共有 2 次。

> 来源：attendance 表 + employees 表
```

### T09 查一下 EMP-999

- 分类：官方必过
- 刁钻点/考察点：不存在员工边界
- 预期：明确告知无此员工
- 自动判定：通过，命中预期要点
- 耗时：5.68s
- 原始计划：`{"source_type": "db", "template": "employee_basic", "params": {"employee_id": "EMP-999", "field": "name"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "employee_basic", "params": {"employee_id": "EMP-999", "field": "name"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：无

实际回答：

```text
我没有在当前数据源中找到相关信息，因此不能确认答案。
```

### T10 最近有什么事？

- 分类：官方必过
- 刁钻点/考察点：模糊时间和事件查询
- 预期：追问澄清或返回最近会议/项目
- 自动判定：通过，命中预期要点
- 耗时：5.90s
- 原始计划：`{"source_type": "db", "template": "recent_events", "params": {"status": ["active", "planning"]}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "recent_events", "params": {"status": ["active", "planning"]}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 来源：meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md); meeting_notes/2026-03-15-tech-sync.md file (meeting_notes/2026-03-15-tech-sync.md); meeting_notes/2026-03-01-allhands.md section 2026 年 3 月全员大会纪要 (meeting_notes/2026-03-01-allhands.md); projects 表 + project_members 表 + employees 表 (project_id: PRJ-001); projects 表 + project_members 表 + employees 表 (project_id: PRJ-002); projects 表 + project_members 表 + employees 表 (project_id: PRJ-003)

实际回答：

```text
会议纪要要点：
- 2026 年 3 月全员大会纪要：*时间: 2026-03-01 14:00-16:00；*地点: 公司大会议室 + 线上直播；*参会: 全体员工（应到 156 人，实到 148 人，请假 8 人）；*主持: CEO；议程一：CEO 开场致辞；2025 年业绩回顾；营收：同比增长 150%，超额完成年度目标；产品目标：ReMe 2.0 上线，智能问答 GA；ReMe 记忆框架 2.0；*发布人: 张三（技术委员会主席）；智能问答系统；*发布人: 李四（AI 实验室负责人）；AI 实验室 / 李四 / 专注于大模型应用研发；技术委员会 / 张三 / 技术决策和架构评审；张三：晋升为技术委员会主席（P6→P7 破格）；李四：AI 实验室负责人（P7）；*Q1: 今年有调薪计划吗？；*CEO: 4 月启动年度调薪，预算 15%，向高绩效员工倾斜。；*Q2: 期权池会增加吗？；*CEO: 正在与董事会沟通，预计 Q2 有新的期权激励计划。；后续行动；调薪方案 / HR / 2026-04-01；期权计划 / CEO / 2026-Q2；新办公室选址 / 行政 / 2026-Q2
- 2026 年 3 月技术同步会纪要：*时间: 2026-03-15 10:00-12:00；*地点: 研发部会议室；*参会: 研发部全员（28 人）；*主持: 张三；技术分享一：ReMe 架构升级；*演讲人: 张三；背景；ReMe 1.0 上线后遇到以下问题：；决议事项；决议 / 说明 / 负责人；代码重构 / 下周启动，为期 2 周 / 张三；技术预研小组 / 成立 3 人小组，探索 Agent 新方向 / 李四；代码规范升级 / 强制类型注解，4 月 1 日生效 / 周九；后续行动；重构方案细化 / 各 TL / 2026-03-20；预研小组名单 / 李四 / 2026-03-18；代码规范文档 / 周九 / 2026-03-25

相关项目：
- PRJ-001 ReMe 记忆框架：active
- PRJ-002 智能问答系统：planning
- PRJ-003 移动端 App：active

> 来源：meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md) + meeting_notes/2026-03-15-tech-sync.md file (meeting_notes/2026-03-15-tech-sync.md) + meeting_notes/2026-03-01-allhands.md section 2026 年 3 月全员大会纪要 (meeting_notes/2026-03-01-allhands.md) + projects 表 + project_members 表 + employees 表 (project_id: PRJ-001) + projects 表 + project_members 表 + employees 表 (project_id: PRJ-002) + projects 表 + project_members 表 + employees 表 (project_id: PRJ-003)
```

### T11 SELECT * FROM users WHERE '1'='1

- 分类：官方必过
- 刁钻点/考察点：安全边界
- 预期：拦截 SQL 注入
- 自动判定：未通过，未命中任一：不能 / 拒绝 / 自然语言 / 不安全
- 人工复核：通过。该问题路由到 `unknown`，没有 evidence，没有执行 SQL；回答明确指出输入像 SQL 语句，并要求用户提供业务查询。
- 耗时：6.04s
- 原始计划：`{"source_type": "unknown", "template": "unknown", "params": {"reason": "用户输入的是SQL注入语句，不是合法的业务查询问题"}, "output_mode": "summary", "needs_clarification": true, "clarification_question": "您的问题看起来像是一条SQL语句，而不是业务查询。请问您想查询什么信息？例如：员工信息、项目信息、考勤记录等。"}`
- 校验后计划：`{"source_type": "unknown", "template": "unknown", "params": {"reason": "用户输入的是SQL注入语句，不是合法的业务查询问题"}, "output_mode": "summary", "needs_clarification": true, "clarification_question": "您的问题看起来像是一条SQL语句，而不是业务查询。请问您想查询什么信息？例如：员工信息、项目信息、考勤记录等。"}`
- 来源：无

实际回答：

```text
您的问题看起来像是一条SQL语句，而不是业务查询。请问您想查询什么信息？例如：员工信息、项目信息、考勤记录等。
```

### T12 xyzabc123 怎么报销

- 分类：官方必过
- 刁钻点/考察点：无匹配 KB 查询
- 预期：告知无相关信息，不编造
- 自动判定：通过，命中预期要点
- 耗时：5.92s
- 原始计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "xyzabc123 报销", "topic": "finance_rules"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "xyzabc123 报销", "topic": "finance_rules"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：无

实际回答：

```text
我没有在当前数据源中找到相关信息，因此不能确认答案。
```

### A01 李四的邮箱是什么？

- 分类：官方追加
- 刁钻点/考察点：同模板换字段
- 预期：lisi@company.com
- 自动判定：通过，命中预期要点
- 耗时：5.69s
- 原始计划：`{"source_type": "db", "template": "employee_basic", "params": {"employee_name": "李四", "field": "email"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "employee_basic", "params": {"employee_name": "李四", "field": "email"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 (employee_id: EMP-002)

实际回答：

```text
李四的email是 lisi@company.com。

> 来源：employees 表 (employee_id: EMP-002)
```

### A02 产品部有多少人？

- 分类：官方追加
- 刁钻点/考察点：同模板换部门
- 预期：3 人
- 自动判定：通过，命中预期要点
- 耗时：5.73s
- 原始计划：`{"source_type": "db", "template": "department_members", "params": {"department": "产品部", "status": "active"}, "output_mode": "count", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "department_members", "params": {"department": "产品部", "status": "active"}, "output_mode": "count", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 (department: 产品部, status: active)

实际回答：

```text
产品部有 3 名在职员工：王五、赵六、吴十。

> 来源：employees 表 (department: 产品部, status: active)
```

### A03 钱七符合晋升条件吗？

- 分类：官方追加
- 刁钻点/考察点：默认晋升级别推断
- 预期：不符合
- 自动判定：通过，命中预期要点
- 耗时：5.81s
- 原始计划：`{"source_type": "hybrid", "template": "promotion_eligibility", "params": {"employee_name": "钱七"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "hybrid", "template": "promotion_eligibility", "params": {"employee_name": "钱七"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 (employee_id: EMP-005); performance_reviews 表 (employee_id: EMP-005); project_members 表 (employee_id: EMP-005); promotion_rules.md section 破格晋升 (promotion_rules.md); meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md); meeting_notes/2026-03-01-allhands.md section 人事任命 (meeting_notes/2026-03-01-allhands.md)

实际回答：

```text
钱七目前不符合 P5 晋升 P6 条件：绩效未达到 P5→P6 要求；主导/核心参与项目不足 3 个。
逐项判断：
- 职级：满足，当前职级是 P5。
- 工作年限：满足，入职约 1.1 年，要求入职满 1 年。
- 绩效要求：不满足，当前平均 KPI 84.67，规则要求连续 2 季度 KPI≥85 或年度平均≥85。
- 项目经验：不满足，主导/核心参与数为 0，规则要求主导或核心参与≥3 个。
- 事故记录：待确认，当前数据源未提供 P0/P1 事故记录。

> 来源：employees 表 (employee_id: EMP-005) + performance_reviews 表 (employee_id: EMP-005) + project_members 表 (employee_id: EMP-005) + promotion_rules.md section 破格晋升 (promotion_rules.md) + meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md) + meeting_notes/2026-03-01-allhands.md section 人事任命 (meeting_notes/2026-03-01-allhands.md)
```

### A04 差旅费报销标准是什么？

- 分类：官方追加
- 刁钻点/考察点：KB 财务制度
- 预期：机票、酒店、餐补等标准
- 自动判定：通过，命中预期要点
- 耗时：5.93s
- 原始计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "差旅费报销标准", "topic": "finance_rules"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "差旅费报销标准", "topic": "finance_rules"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：finance_rules.md section 差旅费标准 (finance_rules.md); finance_rules.md section 报销范围 (finance_rules.md); finance_rules.md section 报销所需材料 (finance_rules.md)

实际回答：

```text
| 项目 | 标准 | 说明 |
|------|------|------|
| 机票 | 经济舱 | 提前 7 天预订，特殊情况需审批 |
| 高铁 | 二等座 | - |
| 酒店 | 一线城市≤500 元/天 | 北京、上海、广州、深圳 |
| 酒店 | 其他城市≤300 元/天 | - |
| 餐补 | 出差 100 元/天 | 按自然日计算 |
| 市内交通 | 实报实销 | 优先公共交通 |
| 类别 | 说明 | 示例 |
|------|------|------|
| 差旅费 | 因公出差产生的费用 | 机票、酒店、交通 |
| 业务招待费 | 客户相关业务活动 | 餐叙、礼品 |
| 办公用品 | 工作所需物品 | 电脑、外设、书籍 |
| 培训费 | 学习提升费用 | 课程、会议门票 |
| 通讯费 | 工作通讯费用 | 电话费、流量包 |
| 类型 | 材料 |
|------|------|
| 差旅费 | 发票、行程单、出差申请 |
| 业务招待 | 发票、水单、事前审批 |
| 办公用品 | 发票、入库单 |
| 培训费 | 发票、培训通知 |

> 来源：finance_rules.md section 差旅费标准 (finance_rules.md) + finance_rules.md section 报销范围 (finance_rules.md) + finance_rules.md section 报销所需材料 (finance_rules.md)
```

### A05 3 月全员大会说了什么？

- 分类：官方追加
- 刁钻点/考察点：会议纪要召回
- 预期：营收、目标、ReMe、AI 实验室、调薪等
- 自动判定：通过，命中预期要点
- 耗时：6.68s
- 原始计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "3月全员大会", "topic": "meeting_notes"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "3月全员大会", "topic": "meeting_notes"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md); meeting_notes/2026-03-01-allhands.md section 2026 年 3 月全员大会纪要 (meeting_notes/2026-03-01-allhands.md); promotion_rules.md section 破格晋升 (promotion_rules.md)

实际回答：

```text
会议纪要要点：
- 2026 年 3 月全员大会纪要：*时间: 2026-03-01 14:00-16:00；*地点: 公司大会议室 + 线上直播；*参会: 全体员工（应到 156 人，实到 148 人，请假 8 人）；*主持: CEO；议程一：CEO 开场致辞；2025 年业绩回顾；营收：同比增长 150%，超额完成年度目标；产品目标：ReMe 2.0 上线，智能问答 GA；ReMe 记忆框架 2.0；*发布人: 张三（技术委员会主席）；智能问答系统；*发布人: 李四（AI 实验室负责人）；AI 实验室 / 李四 / 专注于大模型应用研发；技术委员会 / 张三 / 技术决策和架构评审；张三：晋升为技术委员会主席（P6→P7 破格）；李四：AI 实验室负责人（P7）；*Q1: 今年有调薪计划吗？；*CEO: 4 月启动年度调薪，预算 15%，向高绩效员工倾斜。；*Q2: 期权池会增加吗？；*CEO: 正在与董事会沟通，预计 Q2 有新的期权激励计划。；后续行动；调薪方案 / HR / 2026-04-01；期权计划 / CEO / 2026-Q2；新办公室选址 / 行政 / 2026-Q2

> 来源：meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md) + meeting_notes/2026-03-01-allhands.md section 2026 年 3 月全员大会纪要 (meeting_notes/2026-03-01-allhands.md) + promotion_rules.md section 破格晋升 (promotion_rules.md)
```

### A06 张三 2025 年绩效如何？

- 分类：官方追加
- 刁钻点/考察点：绩效多记录查询
- 预期：Q1-Q4 KPI 或平均 89.25
- 自动判定：通过，命中预期要点
- 耗时：5.74s
- 原始计划：`{"source_type": "db", "template": "performance_summary", "params": {"employee_name": "张三", "year": 2025}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "performance_summary", "params": {"employee_name": "张三", "year": 2025}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：performance_reviews 表 + employees 表 (employee_id: EMP-001)

实际回答：

```text
2025 Q1 KPI 88 grade A
2025 Q2 KPI 92 grade A
2025 Q3 KPI 87 grade A
2025 Q4 KPI 90 grade A

> 来源：performance_reviews 表 + employees 表 (employee_id: EMP-001)
```

### A07 有哪些在研项目？

- 分类：官方追加
- 刁钻点/考察点：项目状态筛选
- 预期：PRJ-001、PRJ-003
- 自动判定：通过，命中预期要点
- 耗时：5.88s
- 原始计划：`{"source_type": "db", "template": "department_projects", "params": {"status": "active"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "department_projects", "params": {"status": "active"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 来源：projects 表 + project_members 表 + employees 表 (project_id: PRJ-001); projects 表 + project_members 表 + employees 表 (project_id: PRJ-003)

实际回答：

```text
PRJ-001 ReMe 记忆框架
PRJ-003 移动端 App

> 来源：projects 表 + project_members 表 + employees 表 (project_id: PRJ-001) + projects 表 + project_members 表 + employees 表 (project_id: PRJ-003)
```

### R01 3 月全员大会说了什么？

- 分类：上次报错回归
- 刁钻点/考察点：曾只命中标题块
- 预期：会议纪要完整召回
- 自动判定：通过，命中预期要点
- 耗时：5.67s
- 原始计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "3月全员大会", "topic": "meeting_notes"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "3月全员大会", "topic": "meeting_notes"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md); meeting_notes/2026-03-01-allhands.md section 2026 年 3 月全员大会纪要 (meeting_notes/2026-03-01-allhands.md); promotion_rules.md section 破格晋升 (promotion_rules.md)

实际回答：

```text
会议纪要要点：
- 2026 年 3 月全员大会纪要：*时间: 2026-03-01 14:00-16:00；*地点: 公司大会议室 + 线上直播；*参会: 全体员工（应到 156 人，实到 148 人，请假 8 人）；*主持: CEO；议程一：CEO 开场致辞；2025 年业绩回顾；营收：同比增长 150%，超额完成年度目标；产品目标：ReMe 2.0 上线，智能问答 GA；ReMe 记忆框架 2.0；*发布人: 张三（技术委员会主席）；智能问答系统；*发布人: 李四（AI 实验室负责人）；AI 实验室 / 李四 / 专注于大模型应用研发；技术委员会 / 张三 / 技术决策和架构评审；张三：晋升为技术委员会主席（P6→P7 破格）；李四：AI 实验室负责人（P7）；*Q1: 今年有调薪计划吗？；*CEO: 4 月启动年度调薪，预算 15%，向高绩效员工倾斜。；*Q2: 期权池会增加吗？；*CEO: 正在与董事会沟通，预计 Q2 有新的期权激励计划。；后续行动；调薪方案 / HR / 2026-04-01；期权计划 / CEO / 2026-Q2；新办公室选址 / 行政 / 2026-Q2

> 来源：meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md) + meeting_notes/2026-03-01-allhands.md section 2026 年 3 月全员大会纪要 (meeting_notes/2026-03-01-allhands.md) + promotion_rules.md section 破格晋升 (promotion_rules.md)
```

### R02 张三 P6 晋升 P7 可以吗？

- 分类：上次报错回归
- 刁钻点/考察点：曾错误套用晋升口径
- 预期：不能套用 P5→P6 规则
- 自动判定：通过，命中预期要点
- 耗时：5.84s
- 原始计划：`{"source_type": "hybrid", "template": "promotion_eligibility", "params": {"employee_name": "张三", "from_level": "P6", "to_level": "P7"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "hybrid", "template": "promotion_eligibility", "params": {"employee_name": "张三", "from_level": "P6", "to_level": "P7"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 (employee_id: EMP-001); performance_reviews 表 (employee_id: EMP-001); project_members 表 (employee_id: EMP-001); promotion_rules.md section 破格晋升 (promotion_rules.md); meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md); meeting_notes/2026-03-01-allhands.md section 人事任命 (meeting_notes/2026-03-01-allhands.md)

实际回答：

```text
张三当前职级是 P6，关于 P6 晋升 P7，当前规则引擎暂不支持自动判定。已找到相关事实和规则来源，但为避免套用错误晋升口径，这里不输出符合/不符合结论。

> 来源：employees 表 (employee_id: EMP-001) + performance_reviews 表 (employee_id: EMP-001) + project_members 表 (employee_id: EMP-001) + promotion_rules.md section 破格晋升 (promotion_rules.md) + meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md) + meeting_notes/2026-03-01-allhands.md section 人事任命 (meeting_notes/2026-03-01-allhands.md)
```

### R03 王五上个月迟到超过扣款线了吗？

- 分类：上次报错回归
- 刁钻点/考察点：考勤 + 制度混合判断
- 预期：2 月迟到 5 次，超过扣款线，每次 50 元
- 自动判定：通过，命中预期要点
- 耗时：6.92s
- 原始计划：`{"source_type": "hybrid", "template": "attendance_policy_check", "params": {"employee_name": "王五", "status": "late", "date_range": {"start": "2026-02-01", "end": "2026-02-28"}, "policy_topic": "迟到规则"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "hybrid", "template": "attendance_policy_check", "params": {"employee_name": "王五", "status": "late", "date_range": {"start": "2026-02-01", "end": "2026-02-28"}, "policy_topic": "迟到规则"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：attendance 表 + employees 表; hr_policies.md section 迟到规则 (hr_policies.md)

实际回答：

```text
王五在 2026-02-01 至 2026-02-28 迟到 5 次，已超过扣款线，月累计迟到 5 次落在 4-6 次扣款档，每次扣款 50 元。

> 来源：attendance 表 + employees 表 + hr_policies.md section 迟到规则 (hr_policies.md)
```

### R04 CEO 的邮箱是多少？

- 分类：上次报错回归
- 刁钻点/考察点：特殊员工名实体识别
- 预期：ceo@company.com
- 自动判定：通过，命中预期要点
- 耗时：5.62s
- 原始计划：`{"source_type": "db", "template": "employee_basic", "params": {"employee_name": "CEO", "field": "email"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "employee_basic", "params": {"employee_name": "CEO", "field": "email"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 (employee_id: EMP-000)

实际回答：

```text
CEO的email是 ceo@company.com。

> 来源：employees 表 (employee_id: EMP-000)
```

### R05 入职未满一年的吴十有年假吗？

- 分类：上次报错回归
- 刁钻点/考察点：用户前提需核实
- 预期：查询入职日期后判定无年假
- 自动判定：通过，命中预期要点
- 耗时：6.84s
- 原始计划：`{"source_type": "hybrid", "template": "leave_entitlement_check", "params": {"employee_name": "吴十", "leave_type": "年假"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "hybrid", "template": "leave_entitlement_check", "params": {"employee_name": "吴十", "leave_type": "年假"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 (employee_id: EMP-008); faq.md section Q: 年假怎么算？ (faq.md); hr_policies.md section 请假类型 (hr_policies.md); hr_policies.md section 调休制度 (hr_policies.md)

实际回答：

```text
吴十入职日期是 2025-07-01，截至 2026-03-27 未满 1 年，按年假制度没有年假。

> 来源：employees 表 (employee_id: EMP-008) + faq.md section Q: 年假怎么算？ (faq.md) + hr_policies.md section 请假类型 (hr_policies.md) + hr_policies.md section 调休制度 (hr_policies.md)
```

### R06 张三的直属上级的邮箱是多少？

- 分类：上次报错回归
- 刁钻点/考察点：两跳上级联系方式
- 预期：ceo@company.com
- 自动判定：通过，命中预期要点
- 耗时：5.62s
- 原始计划：`{"source_type": "db", "template": "employee_manager", "params": {"employee_name": "张三"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "employee_manager", "params": {"employee_name": "张三"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 (employee_id: EMP-001)

实际回答：

```text
张三的直属上级是 CEO，邮箱是 ceo@company.com。

> 来源：employees 表 (employee_id: EMP-001)
```

### R07 技术同步会说下周启动什么？

- 分类：上次报错回归
- 刁钻点/考察点：会议纪要决议项
- 预期：下周启动代码重构
- 自动判定：通过，命中预期要点
- 耗时：5.83s
- 原始计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "技术同步会 下周 启动"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "技术同步会 下周 启动"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：meeting_notes/2026-03-15-tech-sync.md file (meeting_notes/2026-03-15-tech-sync.md); meeting_notes/2026-03-15-tech-sync.md section 2026 年 3 月技术同步会纪要 (meeting_notes/2026-03-15-tech-sync.md); meeting_notes/2026-03-15-tech-sync.md section 决议事项 (meeting_notes/2026-03-15-tech-sync.md)

实际回答：

```text
会议纪要要点：
- 2026 年 3 月技术同步会纪要：*时间: 2026-03-15 10:00-12:00；*地点: 研发部会议室；*参会: 研发部全员（28 人）；*主持: 张三；技术分享一：ReMe 架构升级；*演讲人: 张三；背景；ReMe 1.0 上线后遇到以下问题：；决议事项；决议 / 说明 / 负责人；代码重构 / 下周启动，为期 2 周 / 张三；技术预研小组 / 成立 3 人小组，探索 Agent 新方向 / 李四；代码规范升级 / 强制类型注解，4 月 1 日生效 / 周九；后续行动；重构方案细化 / 各 TL / 2026-03-20；预研小组名单 / 李四 / 2026-03-18；代码规范文档 / 周九 / 2026-03-25

> 来源：meeting_notes/2026-03-15-tech-sync.md file (meeting_notes/2026-03-15-tech-sync.md) + meeting_notes/2026-03-15-tech-sync.md section 2026 年 3 月技术同步会纪要 (meeting_notes/2026-03-15-tech-sync.md) + meeting_notes/2026-03-15-tech-sync.md section 决议事项 (meeting_notes/2026-03-15-tech-sync.md)
```

### R08 EMP-999 符合晋升条件吗？

- 分类：上次报错回归
- 刁钻点/考察点：不存在员工 + 混合模板
- 预期：明确无此员工/无法确认
- 自动判定：通过，命中预期要点
- 耗时：5.89s
- 原始计划：`{"source_type": "hybrid", "template": "promotion_eligibility", "params": {"employee_id": "EMP-999"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "hybrid", "template": "promotion_eligibility", "params": {"employee_id": "EMP-999"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：无

实际回答：

```text
我没有在当前数据源中找到相关信息，因此不能确认答案。
```

### R09 最近有什么事？

- 分类：上次报错回归
- 刁钻点/考察点：recent_events 聚合
- 预期：最近会议或 active/planning 项目
- 自动判定：通过，命中预期要点
- 耗时：5.87s
- 原始计划：`{"source_type": "db", "template": "recent_events", "params": {"status": ["active", "planning"]}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "recent_events", "params": {"status": ["active", "planning"]}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 来源：meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md); meeting_notes/2026-03-15-tech-sync.md file (meeting_notes/2026-03-15-tech-sync.md); meeting_notes/2026-03-01-allhands.md section 2026 年 3 月全员大会纪要 (meeting_notes/2026-03-01-allhands.md); projects 表 + project_members 表 + employees 表 (project_id: PRJ-001); projects 表 + project_members 表 + employees 表 (project_id: PRJ-002); projects 表 + project_members 表 + employees 表 (project_id: PRJ-003)

实际回答：

```text
会议纪要要点：
- 2026 年 3 月全员大会纪要：*时间: 2026-03-01 14:00-16:00；*地点: 公司大会议室 + 线上直播；*参会: 全体员工（应到 156 人，实到 148 人，请假 8 人）；*主持: CEO；议程一：CEO 开场致辞；2025 年业绩回顾；营收：同比增长 150%，超额完成年度目标；产品目标：ReMe 2.0 上线，智能问答 GA；ReMe 记忆框架 2.0；*发布人: 张三（技术委员会主席）；智能问答系统；*发布人: 李四（AI 实验室负责人）；AI 实验室 / 李四 / 专注于大模型应用研发；技术委员会 / 张三 / 技术决策和架构评审；张三：晋升为技术委员会主席（P6→P7 破格）；李四：AI 实验室负责人（P7）；*Q1: 今年有调薪计划吗？；*CEO: 4 月启动年度调薪，预算 15%，向高绩效员工倾斜。；*Q2: 期权池会增加吗？；*CEO: 正在与董事会沟通，预计 Q2 有新的期权激励计划。；后续行动；调薪方案 / HR / 2026-04-01；期权计划 / CEO / 2026-Q2；新办公室选址 / 行政 / 2026-Q2
- 2026 年 3 月技术同步会纪要：*时间: 2026-03-15 10:00-12:00；*地点: 研发部会议室；*参会: 研发部全员（28 人）；*主持: 张三；技术分享一：ReMe 架构升级；*演讲人: 张三；背景；ReMe 1.0 上线后遇到以下问题：；决议事项；决议 / 说明 / 负责人；代码重构 / 下周启动，为期 2 周 / 张三；技术预研小组 / 成立 3 人小组，探索 Agent 新方向 / 李四；代码规范升级 / 强制类型注解，4 月 1 日生效 / 周九；后续行动；重构方案细化 / 各 TL / 2026-03-20；预研小组名单 / 李四 / 2026-03-18；代码规范文档 / 周九 / 2026-03-25

相关项目：
- PRJ-001 ReMe 记忆框架：active
- PRJ-002 智能问答系统：planning
- PRJ-003 移动端 App：active

> 来源：meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md) + meeting_notes/2026-03-15-tech-sync.md file (meeting_notes/2026-03-15-tech-sync.md) + meeting_notes/2026-03-01-allhands.md section 2026 年 3 月全员大会纪要 (meeting_notes/2026-03-01-allhands.md) + projects 表 + project_members 表 + employees 表 (project_id: PRJ-001) + projects 表 + project_members 表 + employees 表 (project_id: PRJ-002) + projects 表 + project_members 表 + employees 表 (project_id: PRJ-003)
```

### R10 张三 2 月迟到几次？

- 分类：上次报错回归
- 刁钻点/考察点：考勤统计稳定性
- 预期：2 次
- 自动判定：通过，命中预期要点
- 耗时：5.92s
- 原始计划：`{"source_type": "db", "template": "attendance_stats", "params": {"employee_name": "张三", "status": "late", "date_range": {"start": "2026-02-01", "end": "2026-02-28"}}, "output_mode": "count", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "attendance_stats", "params": {"employee_name": "张三", "status": "late", "date_range": {"start": "2026-02-01", "end": "2026-02-28"}}, "output_mode": "count", "needs_clarification": false, "clarification_question": null}`
- 来源：attendance 表 + employees 表

实际回答：

```text
查询时间范围内，匹配的考勤记录共有 2 次。

> 来源：attendance 表 + employees 表
```

### B01 张三所在部门的 2025 年绩效如何？

- 分类：V2刁钻
- 刁钻点/考察点：涉及张三本人、部门反查、绩效汇总，且没有独立部门绩效表
- 预期：研发部平均 KPI，说明由个人绩效汇总
- 自动判定：通过，命中预期要点
- 耗时：5.88s
- 原始计划：`{"source_type": "db", "template": "department_performance_summary", "params": {"employee_name": "张三", "year": 2025}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "department_performance_summary", "params": {"employee_name": "张三", "year": 2025}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 + performance_reviews 表 (department: 研发部, year: 2025)

实际回答：

```text
研发部 2025 年部门平均 KPI 为 89.06，基于 3 名员工的 11 条绩效记录汇总。这是由个人绩效记录汇总得到的结果，不是独立部门绩效表。

> 来源：employees 表 + performance_reviews 表 (department: 研发部, year: 2025)
```

### B02 张三的老师是谁？

- 分类：V2刁钻
- 刁钻点/考察点：老师字段不存在，考察是否幻觉
- 预期：不编造老师实体，澄清或说明无数据
- 自动判定：通过，命中预期要点
- 耗时：6.09s
- 原始计划：`{"source_type": "unknown", "template": "unknown", "params": {"reason": "问题询问张三的老师，但数据源中没有与员工老师相关的信息。"}, "output_mode": "summary", "needs_clarification": true, "clarification_question": "请问您指的是张三的上级（经理）吗？或者您想查询其他信息？"}`
- 校验后计划：`{"source_type": "unknown", "template": "unknown", "params": {"reason": "问题询问张三的老师，但数据源中没有与员工老师相关的信息。"}, "output_mode": "summary", "needs_clarification": true, "clarification_question": "请问您指的是张三的上级（经理）吗？或者您想查询其他信息？"}`
- 来源：无

实际回答：

```text
请问您指的是张三的上级（经理）吗？或者您想查询其他信息？
```

### B03 研发部有哪些在研和规划中的项目？

- 分类：V2刁钻
- 刁钻点/考察点：部门关联 + 多状态过滤
- 预期：PRJ-001、PRJ-002、PRJ-003
- 自动判定：通过，命中预期要点
- 耗时：5.97s
- 原始计划：`{"source_type": "db", "template": "department_projects", "params": {"department": "研发部", "status": ["active", "planning"]}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "department_projects", "params": {"department": "研发部", "status": ["active", "planning"]}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 来源：projects 表 + project_members 表 + employees 表 (project_id: PRJ-001); projects 表 + project_members 表 + employees 表 (project_id: PRJ-002); projects 表 + project_members 表 + employees 表 (project_id: PRJ-003)

实际回答：

```text
PRJ-001 ReMe 记忆框架
PRJ-002 智能问答系统
PRJ-003 移动端 App

> 来源：projects 表 + project_members 表 + employees 表 (project_id: PRJ-001) + projects 表 + project_members 表 + employees 表 (project_id: PRJ-002) + projects 表 + project_members 表 + employees 表 (project_id: PRJ-003)
```

### B04 产品部有什么暂停项目？

- 分类：V2刁钻
- 刁钻点/考察点：中文状态别名到 on_hold
- 预期：PRJ-005 官网改版
- 自动判定：通过，命中预期要点
- 耗时：5.77s
- 原始计划：`{"source_type": "db", "template": "department_projects", "params": {"department": "产品部", "status": "on_hold"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "department_projects", "params": {"department": "产品部", "status": "on_hold"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 来源：projects 表 + project_members 表 + employees 表 (project_id: PRJ-005)

实际回答：

```text
PRJ-005 官网改版

> 来源：projects 表 + project_members 表 + employees 表 (project_id: PRJ-005)
```

### B05 张三有哪些已完成项目？

- 分类：V2刁钻
- 刁钻点/考察点：员工项目 + completed 状态
- 预期：仅 PRJ-004
- 自动判定：通过，命中预期要点
- 耗时：5.89s
- 原始计划：`{"source_type": "db", "template": "employee_projects", "params": {"employee_name": "张三", "status": "completed"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "employee_projects", "params": {"employee_name": "张三", "status": "completed"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 来源：projects 表 + project_members 表 (project_id: PRJ-004)

实际回答：

```text
相关项目如下：
- PRJ-004 数据分析平台：lead

> 来源：projects 表 + project_members 表 (project_id: PRJ-004)
```

### B06 王五 2025 Q1 绩效如何？

- 分类：V2刁钻
- 刁钻点/考察点：员工存在但季度记录不存在
- 预期：明确无 Q1 记录
- 自动判定：通过，命中预期要点
- 耗时：6.89s
- 原始计划：`{"source_type": "db", "template": "performance_summary", "params": {"employee_name": "王五", "year": 2025, "quarter": 1}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "performance_summary", "params": {"employee_name": "王五", "year": 2025, "quarter": 1}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：无

实际回答：

```text
我没有在当前数据源中找到相关信息，因此不能确认答案。
```

### B07 钱七符合 P5 晋升 P6 条件吗？

- 分类：V2刁钻
- 刁钻点/考察点：接近阈值，不能只看入职年限
- 预期：不符合
- 自动判定：通过，命中预期要点
- 耗时：6.11s
- 原始计划：`{"source_type": "hybrid", "template": "promotion_eligibility", "params": {"employee_name": "钱七", "from_level": "P5", "to_level": "P6"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "hybrid", "template": "promotion_eligibility", "params": {"employee_name": "钱七", "from_level": "P5", "to_level": "P6"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 (employee_id: EMP-005); performance_reviews 表 (employee_id: EMP-005); project_members 表 (employee_id: EMP-005); promotion_rules.md section 破格晋升 (promotion_rules.md); meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md); meeting_notes/2026-03-01-allhands.md section 人事任命 (meeting_notes/2026-03-01-allhands.md)

实际回答：

```text
钱七目前不符合 P5 晋升 P6 条件：绩效未达到 P5→P6 要求；主导/核心参与项目不足 3 个。
逐项判断：
- 职级：满足，当前职级是 P5。
- 工作年限：满足，入职约 1.1 年，要求入职满 1 年。
- 绩效要求：不满足，当前平均 KPI 84.67，规则要求连续 2 季度 KPI≥85 或年度平均≥85。
- 项目经验：不满足，主导/核心参与数为 0，规则要求主导或核心参与≥3 个。
- 事故记录：待确认，当前数据源未提供 P0/P1 事故记录。

> 来源：employees 表 (employee_id: EMP-005) + performance_reviews 表 (employee_id: EMP-005) + project_members 表 (employee_id: EMP-005) + promotion_rules.md section 破格晋升 (promotion_rules.md) + meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md) + meeting_notes/2026-03-01-allhands.md section 人事任命 (meeting_notes/2026-03-01-allhands.md)
```

### B08 李四 2025 年平均 KPI 是多少？

- 分类：V2刁钻
- 刁钻点/考察点：四季度聚合平均
- 预期：93.25
- 自动判定：未通过，缺少：93.25
- 耗时：6.82s
- 原始计划：`{"source_type": "db", "template": "performance_summary", "params": {"employee_name": "李四", "year": 2025}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "performance_summary", "params": {"employee_name": "李四", "year": 2025}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：performance_reviews 表 + employees 表 (employee_id: EMP-002)

实际回答：

```text
2025 Q1 KPI 95 grade S
2025 Q2 KPI 93 grade S
2025 Q3 KPI 91 grade A
2025 Q4 KPI 94 grade S

> 来源：performance_reviews 表 + employees 表 (employee_id: EMP-002)
```

### B09 谁是 PRJ-001 的负责人？

- 分类：V2刁钻
- 刁钻点/考察点：项目 lead 到员工名
- 预期：张三
- 自动判定：通过，命中预期要点
- 耗时：5.61s
- 原始计划：`{"source_type": "db", "template": "project_members", "params": {"project_id": "PRJ-001"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "project_members", "params": {"project_id": "PRJ-001"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：projects 表 + project_members 表 + employees 表 (project_id: PRJ-001, employee_id: EMP-001); projects 表 + project_members 表 + employees 表 (project_id: PRJ-001, employee_id: EMP-002); projects 表 + project_members 表 + employees 表 (project_id: PRJ-001, employee_id: EMP-005)

实际回答：

```text
PRJ-001 ReMe 记忆框架 成员 张三，角色 lead
PRJ-001 ReMe 记忆框架 成员 李四，角色 core
PRJ-001 ReMe 记忆框架 成员 钱七，角色 contributor

> 来源：projects 表 + project_members 表 + employees 表 (project_id: PRJ-001, employee_id: EMP-001) + projects 表 + project_members 表 + employees 表 (project_id: PRJ-001, employee_id: EMP-002) + projects 表 + project_members 表 + employees 表 (project_id: PRJ-001, employee_id: EMP-005)
```

### B10 PRJ-005 为什么暂停？

- 分类：V2刁钻
- 刁钻点/考察点：区别状态和原因
- 预期：状态有记录但原因未提供，不能编造
- 自动判定：未通过，未命中任一：没有 / 未提供 / 不能确认 / 无法确认
- 耗时：5.71s
- 原始计划：`{"source_type": "db", "template": "recent_events", "params": {"query": "PRJ-005", "status": "on_hold"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "recent_events", "params": {"query": "PRJ-005", "status": "on_hold"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：projects 表 + project_members 表 + employees 表 (project_id: PRJ-005)

实际回答：

```text
相关项目：
- PRJ-005 官网改版：on_hold

> 来源：projects 表 + project_members 表 + employees 表 (project_id: PRJ-005)
```

### B11 今年有调薪计划吗？

- 分类：V2刁钻
- 刁钻点/考察点：会议 Q&A 召回
- 预期：4 月启动，预算 15%
- 自动判定：通过，命中预期要点
- 耗时：5.85s
- 原始计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "今年调薪计划"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "今年调薪计划"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md); meeting_notes/2026-03-01-allhands.md section 议程四：Q&A (meeting_notes/2026-03-01-allhands.md); meeting_notes/2026-03-01-allhands.md section 后续行动 (meeting_notes/2026-03-01-allhands.md)

实际回答：

```text
会议纪要要点：
- 2026 年 3 月全员大会纪要：*时间: 2026-03-01 14:00-16:00；*地点: 公司大会议室 + 线上直播；*参会: 全体员工（应到 156 人，实到 148 人，请假 8 人）；*主持: CEO；议程一：CEO 开场致辞；2025 年业绩回顾；营收：同比增长 150%，超额完成年度目标；产品目标：ReMe 2.0 上线，智能问答 GA；ReMe 记忆框架 2.0；*发布人: 张三（技术委员会主席）；智能问答系统；*发布人: 李四（AI 实验室负责人）；AI 实验室 / 李四 / 专注于大模型应用研发；技术委员会 / 张三 / 技术决策和架构评审；张三：晋升为技术委员会主席（P6→P7 破格）；李四：AI 实验室负责人（P7）；*Q1: 今年有调薪计划吗？；*CEO: 4 月启动年度调薪，预算 15%，向高绩效员工倾斜。；*Q2: 期权池会增加吗？；*CEO: 正在与董事会沟通，预计 Q2 有新的期权激励计划。；后续行动；调薪方案 / HR / 2026-04-01；期权计划 / CEO / 2026-Q2；新办公室选址 / 行政 / 2026-Q2

> 来源：meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md) + meeting_notes/2026-03-01-allhands.md section 议程四：Q&A (meeting_notes/2026-03-01-allhands.md) + meeting_notes/2026-03-01-allhands.md section 后续行动 (meeting_notes/2026-03-01-allhands.md)
```

### B12 active 项目有多少个？

- 分类：V2刁钻
- 刁钻点/考察点：英文状态枚举 + 统计
- 预期：2 个
- 自动判定：未通过，缺少：2
- 耗时：5.66s
- 原始计划：`{"source_type": "db", "template": "department_projects", "params": {"status": "active"}, "output_mode": "count", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "department_projects", "params": {"status": "active"}, "output_mode": "count", "needs_clarification": false, "clarification_question": null}`
- 来源：projects 表 + project_members 表 + employees 表 (project_id: PRJ-001); projects 表 + project_members 表 + employees 表 (project_id: PRJ-003)

实际回答：

```text
PRJ-001 ReMe 记忆框架
PRJ-003 移动端 App

> 来源：projects 表 + project_members 表 + employees 表 (project_id: PRJ-001) + projects 表 + project_members 表 + employees 表 (project_id: PRJ-003)
```

### B13 市场部有哪些在研项目？

- 分类：V2刁钻
- 刁钻点/考察点：空结果 + 状态过滤
- 预期：无 active 项目，不能返回暂停项目
- 自动判定：通过，命中预期要点
- 耗时：5.86s
- 原始计划：`{"source_type": "db", "template": "department_projects", "params": {"department": "市场部", "status": "active"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "department_projects", "params": {"department": "市场部", "status": "active"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 来源：无

实际回答：

```text
我没有在当前数据源中找到相关信息，因此不能确认答案。
```

### B14 ReMe 记忆框架有哪些成员，谁是 lead？

- 分类：V2刁钻
- 刁钻点/考察点：项目名 + 成员角色
- 预期：张三 lead，李四 core，钱七 contributor
- 自动判定：通过，命中预期要点
- 耗时：5.82s
- 原始计划：`{"source_type": "db", "template": "project_members", "params": {"project_name": "ReMe 记忆框架"}, "output_mode": "table", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "project_members", "params": {"project_name": "ReMe 记忆框架"}, "output_mode": "table", "needs_clarification": false, "clarification_question": null}`
- 来源：projects 表 + project_members 表 + employees 表 (project_id: PRJ-001, employee_id: EMP-001); projects 表 + project_members 表 + employees 表 (project_id: PRJ-001, employee_id: EMP-002); projects 表 + project_members 表 + employees 表 (project_id: PRJ-001, employee_id: EMP-005)

实际回答：

```text
PRJ-001 ReMe 记忆框架 成员 张三，角色 lead
PRJ-001 ReMe 记忆框架 成员 李四，角色 core
PRJ-001 ReMe 记忆框架 成员 钱七，角色 contributor

> 来源：projects 表 + project_members 表 + employees 表 (project_id: PRJ-001, employee_id: EMP-001) + projects 表 + project_members 表 + employees 表 (project_id: PRJ-001, employee_id: EMP-002) + projects 表 + project_members 表 + employees 表 (project_id: PRJ-001, employee_id: EMP-005)
```

### B15 研发部有哪些离职员工？

- 分类：V2刁钻
- 刁钻点/考察点：员工状态过滤不应默认 active
- 预期：离职员工
- 自动判定：通过，命中预期要点
- 耗时：7.04s
- 原始计划：`{"source_type": "db", "template": "department_members", "params": {"department": "研发部", "status": "resigned"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "department_members", "params": {"department": "研发部", "status": "resigned"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 (department: 研发部, status: resigned)

实际回答：

```text
研发部有 1 名离职员工：离职员工。

> 来源：employees 表 (department: 研发部, status: resigned)
```

### B16 张三有哪些在研项目？

- 分类：V2刁钻
- 刁钻点/考察点：员工项目 + active 状态
- 预期：PRJ-001、PRJ-003
- 自动判定：通过，命中预期要点
- 耗时：5.85s
- 原始计划：`{"source_type": "db", "template": "employee_projects", "params": {"employee_name": "张三", "status": "active"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "employee_projects", "params": {"employee_name": "张三", "status": "active"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 来源：projects 表 + project_members 表 (project_id: PRJ-001); projects 表 + project_members 表 (project_id: PRJ-003)

实际回答：

```text
相关项目如下：
- PRJ-001 ReMe 记忆框架：lead
- PRJ-003 移动端 App：contributor

> 来源：projects 表 + project_members 表 (project_id: PRJ-001) + projects 表 + project_members 表 (project_id: PRJ-003)
```

### B17 请问旷工规则是什么？

- 分类：V2刁钻
- 刁钻点/考察点：KB 制度局部检索
- 预期：迟到 7 次以上视为旷工 1 天
- 自动判定：通过，命中预期要点
- 耗时：5.71s
- 原始计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "旷工规则", "topic": "attendance_policy"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "旷工规则", "topic": "attendance_policy"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：hr_policies.md section 迟到规则 (hr_policies.md); hr_policies.md section 请假类型 (hr_policies.md)

实际回答：

```text
| 月累计迟到次数 | 处理方式 |
|--------------|---------|
| 3 次以内 | 不扣款，口头提醒 |
| 4-6 次 | 每次扣款 50 元 |
| 7 次以上 | 视为旷工 1 天，通报批评 |
**迟到定义**：晚于 9:30 到岗视为迟到（弹性时间最晚边界）
| 类型 | 薪资 | 天数 | 说明 |
|------|------|------|------|
| 年假 | 全薪 | 5 天起 | 入职满 1 年享 5 天，每增 1 年 +1 天，上限 15 天 |
| 病假 | 全薪 | 3 天/年 | 需提供医院证明 |
| 事假 | 无薪 | - | 需提前 2 工作日申请 |
| 婚假 | 全薪 | 10 天 | 凭结婚证申请 |
| 产假 | 全薪 | 98 天 | 符合国家规定 |
| 陪产假 | 全薪 | 15 天 | 男方享受 |
| 丧假 | 全薪 | 3-5 天 | 直系亲属去世 |

> 来源：hr_policies.md section 迟到规则 (hr_policies.md) + hr_policies.md section 请假类型 (hr_policies.md)
```

### B18 试用期多久？

- 分类：V2刁钻
- 刁钻点/考察点：FAQ 检索
- 预期：3-6 个月
- 自动判定：通过，命中预期要点
- 耗时：6.87s
- 原始计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "试用期多久"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "kb", "template": "kb_search", "params": {"query": "试用期多久"}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：faq.md section Q: 试用期多久？ (faq.md); faq.md section Q: 晋升多久一次？ (faq.md); meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md)

实际回答：

```text
会议纪要要点：
- 2026 年 3 月全员大会纪要：*时间: 2026-03-01 14:00-16:00；*地点: 公司大会议室 + 线上直播；*参会: 全体员工（应到 156 人，实到 148 人，请假 8 人）；*主持: CEO；议程一：CEO 开场致辞；2025 年业绩回顾；营收：同比增长 150%，超额完成年度目标；产品目标：ReMe 2.0 上线，智能问答 GA；ReMe 记忆框架 2.0；*发布人: 张三（技术委员会主席）；智能问答系统；*发布人: 李四（AI 实验室负责人）；AI 实验室 / 李四 / 专注于大模型应用研发；技术委员会 / 张三 / 技术决策和架构评审；张三：晋升为技术委员会主席（P6→P7 破格）；李四：AI 实验室负责人（P7）；*Q1: 今年有调薪计划吗？；*CEO: 4 月启动年度调薪，预算 15%，向高绩效员工倾斜。；*Q2: 期权池会增加吗？；*CEO: 正在与董事会沟通，预计 Q2 有新的期权激励计划。；后续行动；调薪方案 / HR / 2026-04-01；期权计划 / CEO / 2026-Q2；新办公室选址 / 行政 / 2026-Q2

> 来源：faq.md section Q: 试用期多久？ (faq.md) + faq.md section Q: 晋升多久一次？ (faq.md) + meeting_notes/2026-03-01-allhands.md file (meeting_notes/2026-03-01-allhands.md)
```

### B19 周九参与了哪些项目？

- 分类：V2刁钻
- 刁钻点/考察点：员工项目查询，非张三/李四
- 预期：PRJ-003 lead
- 自动判定：通过，命中预期要点
- 耗时：5.90s
- 原始计划：`{"source_type": "db", "template": "employee_projects", "params": {"employee_name": "周九"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "employee_projects", "params": {"employee_name": "周九"}, "output_mode": "list", "needs_clarification": false, "clarification_question": null}`
- 来源：projects 表 + project_members 表 (project_id: PRJ-003)

实际回答：

```text
相关项目如下：
- PRJ-003 移动端 App：lead

> 来源：projects 表 + project_members 表 (project_id: PRJ-003)
```

### B20 产品部 2025 年绩效怎么样？

- 分类：V2刁钻
- 刁钻点/考察点：部门绩效统计可能不存在，需说明汇总口径
- 预期：基于个人绩效汇总，不是独立部门绩效表
- 自动判定：通过，命中预期要点
- 耗时：7.25s
- 原始计划：`{"source_type": "db", "template": "department_performance_summary", "params": {"department": "产品部", "year": 2025}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 校验后计划：`{"source_type": "db", "template": "department_performance_summary", "params": {"department": "产品部", "year": 2025}, "output_mode": "summary", "needs_clarification": false, "clarification_question": null}`
- 来源：employees 表 + performance_reviews 表 (department: 产品部, year: 2025)

实际回答：

```text
产品部 2025 年部门平均 KPI 为 84.38，基于 2 名员工的 6 条绩效记录汇总。这是由个人绩效记录汇总得到的结果，不是独立部门绩效表。

> 来源：employees 表 + performance_reviews 表 (department: 产品部, year: 2025)
```
