# Thinking 模式配置说明

## 背景

DeepSeek V4 系列支持 thinking 与 non-thinking 两种运行方式。企业问答 Skill 的常见问题多是结构化查询规划、数据库读取和知识库检索，通常不需要长链路推理。为了降低简单问题的响应延迟，当前默认关闭 thinking。

## 配置项

可以在 `config.yaml` 中配置：

```yaml
llm:
  timeout_seconds: 20
  answer_polish: true
  thinking_enabled: false
```

也可以使用环境变量覆盖：

```bash
export ENTERPRISE_QA_THINKING_ENABLED="false"
```

Windows PowerShell：

```powershell
[Environment]::SetEnvironmentVariable("ENTERPRISE_QA_THINKING_ENABLED", "false", "User")
```

环境变量优先级高于 `config.yaml`。

## Provider 行为

- DeepSeek 官方接口：`thinking_enabled=false` 时发送 `thinking: {"type": "disabled"}`；为 `true` 时发送 `thinking: {"type": "enabled"}`。
- SiliconFlow 接口：发送 `enable_thinking: false` 或 `enable_thinking: true`。
- 其他 OpenAI-compatible provider：不额外发送 thinking 字段，避免传入不兼容参数。

## 推荐设置

- 面试演示、普通企业问答、员工/项目/考勤/绩效查询：保持 `thinking_enabled: false`。
- 需要更复杂的制度解释、模糊问题拆解或长文本综合时，可以临时改为 `true`。
- 若开启 `answer_polish: true`，一次请求可能包含查询规划和回答润色两次 LLM 调用；对速度敏感时可同时设置 `answer_polish: false`。

## 验证

修改配置后，可运行：

```bash
python -X utf8 scripts/cli.py "张三的部门是什么？"
```

输出应包含正常中文和来源，例如：

```text
张三的department是 研发部。

> 来源：employees 表 (employee_id: EMP-001)
```

如需确认配置读取结果，可运行：

```bash
python -X utf8 -c "from scripts.config import load_config; c=load_config(); print(c.thinking_enabled)"
```
