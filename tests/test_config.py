from pathlib import Path

from scripts.config import load_config


def test_load_config_uses_default_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("ENTERPRISE_QA_CONFIG_PATH", str(tmp_path / "missing-config.yaml"))
    monkeypatch.delenv("ENTERPRISE_QA_DB_PATH", raising=False)
    monkeypatch.delenv("ENTERPRISE_QA_KB_PATH", raising=False)

    config = load_config()

    assert config.database_path == Path("data/enterprise.db")
    assert config.knowledge_path == Path("data/knowledge")
    assert config.current_date == "2026-03-27"
    assert config.answer_polish is True


def test_load_config_reads_env_overrides(monkeypatch, tmp_path):
    db_path = tmp_path / "custom.db"
    kb_path = tmp_path / "kb"
    monkeypatch.setenv("ENTERPRISE_QA_CONFIG_PATH", str(tmp_path / "missing-config.yaml"))
    monkeypatch.setenv("ENTERPRISE_QA_DB_PATH", str(db_path))
    monkeypatch.setenv("ENTERPRISE_QA_KB_PATH", str(kb_path))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")

    config = load_config()

    assert config.database_path == db_path
    assert config.knowledge_path == kb_path
    assert config.providers[0].api_key == "deepseek-key"


def test_load_config_reads_yaml_file(monkeypatch, tmp_path):
    db_path = tmp_path / "from-yaml.db"
    kb_path = tmp_path / "knowledge"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
database:
  path: {db_path}
knowledge_base:
  root_path: {kb_path}
llm:
  timeout_seconds: 7
  answer_polish: false
  providers:
    - name: local
      api_key: yaml-key
      base_url: https://llm.example.test/v1
      model: local-model
timezone: Asia/Hong_Kong
current_date: 2026-05-21
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.delenv("ENTERPRISE_QA_DB_PATH", raising=False)
    monkeypatch.delenv("ENTERPRISE_QA_KB_PATH", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)

    config = load_config(config_path)

    assert config.database_path == db_path
    assert config.knowledge_path == kb_path
    assert config.timeout_seconds == 7
    assert config.answer_polish is False
    assert config.timezone == "Asia/Hong_Kong"
    assert config.current_date == "2026-05-21"
    assert config.providers == [
        type(config.providers[0])("local", "yaml-key", "https://llm.example.test/v1", "local-model")
    ]
