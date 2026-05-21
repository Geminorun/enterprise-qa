# 企业问答 Skill

这是一个 Claude Code Skill，用于回答企业员工、项目、考勤、绩效、制度、报销、FAQ 和会议纪要相关问题。

## 安装

```bash
git clone "$ENTERPRISE_QA_REPO_URL" ~/.claude/skills/enterprise-qa
```

Windows:

```powershell
git clone $env:ENTERPRISE_QA_REPO_URL $env:USERPROFILE\.claude\skills\enterprise-qa
```

## 配置

至少配置一个 LLM provider：

```bash
export DEEPSEEK_API_KEY="..."
export SILICONFLOW_API_KEY="..."
```

默认数据文件已经包含在 `data/` 下。

## 运行

```bash
python scripts/cli.py "张三的部门是什么？"
python scripts/cli.py "年假怎么计算？"
python scripts/cli.py "王五符合 P5 晋升 P6 条件吗？"
```

## 自测

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```
