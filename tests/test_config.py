from pathlib import Path

from scripts.config import load_config


def test_load_config_uses_default_paths(monkeypatch):
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
    monkeypatch.setenv("ENTERPRISE_QA_DB_PATH", str(db_path))
    monkeypatch.setenv("ENTERPRISE_QA_KB_PATH", str(kb_path))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")

    config = load_config()

    assert config.database_path == db_path
    assert config.knowledge_path == kb_path
    assert config.providers[0].api_key == "deepseek-key"
