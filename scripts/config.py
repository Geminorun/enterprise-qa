from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class LlmProviderConfig:
    name: str
    api_key: str
    base_url: str
    model: str


@dataclass(frozen=True)
class AppConfig:
    database_path: Path
    knowledge_path: Path
    current_date: str
    timezone: str
    timeout_seconds: int
    answer_polish: bool
    providers: list[LlmProviderConfig]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def load_config() -> AppConfig:
    providers = [
        LlmProviderConfig(
            name="deepseek",
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        ),
        LlmProviderConfig(
            name="siliconflow",
            api_key=os.getenv("SILICONFLOW_API_KEY", ""),
            base_url=os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
            model=os.getenv("SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V3"),
        ),
    ]
    return AppConfig(
        database_path=Path(os.getenv("ENTERPRISE_QA_DB_PATH", "data/enterprise.db")),
        knowledge_path=Path(os.getenv("ENTERPRISE_QA_KB_PATH", "data/knowledge")),
        current_date=os.getenv("ENTERPRISE_QA_CURRENT_DATE", "2026-03-27"),
        timezone=os.getenv("ENTERPRISE_QA_TIMEZONE", "Asia/Shanghai"),
        timeout_seconds=int(os.getenv("ENTERPRISE_QA_LLM_TIMEOUT", "20")),
        answer_polish=_env_bool("ENTERPRISE_QA_ANSWER_POLISH", True),
        providers=providers,
    )
