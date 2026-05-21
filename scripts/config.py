from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any


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


def _expand_env(value: str) -> str:
    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", lambda match: os.getenv(match.group(1), ""), value)


def _parse_scalar(value: str) -> Any:
    expanded = _expand_env(value.strip().strip("\"'"))
    lowered = expanded.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if expanded.isdigit():
        return int(expanded)
    return expanded


def _load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    data: dict[str, Any] = {}
    section: str | None = None
    current_provider: dict[str, Any] | None = None
    in_providers = False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0:
            key, _, value = line.partition(":")
            section = key
            in_providers = False
            current_provider = None
            if value.strip():
                data[key] = _parse_scalar(value)
            else:
                data.setdefault(key, [] if key == "providers" else {})
            continue

        if section == "llm" and line == "providers:":
            data.setdefault("llm", {})["providers"] = []
            in_providers = True
            current_provider = None
            continue

        if section == "llm" and in_providers:
            if line.startswith("- "):
                current_provider = {}
                data.setdefault("llm", {}).setdefault("providers", []).append(current_provider)
                line = line[2:]
            if current_provider is not None and ":" in line:
                key, _, value = line.partition(":")
                current_provider[key.strip()] = _parse_scalar(value)
            continue

        if section:
            key, _, value = line.partition(":")
            target = data.setdefault(section, {})
            if isinstance(target, dict):
                target[key.strip()] = _parse_scalar(value)

    return data


def _default_providers() -> list[LlmProviderConfig]:
    return [
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


def _yaml_providers(config: dict[str, Any]) -> list[LlmProviderConfig] | None:
    providers = config.get("llm", {}).get("providers")
    if not isinstance(providers, list):
        return None
    return [
        LlmProviderConfig(
            name=str(item.get("name", "")),
            api_key=str(item.get("api_key", "")),
            base_url=str(item.get("base_url", "")),
            model=str(item.get("model", "")),
        )
        for item in providers
        if isinstance(item, dict)
    ]


def _with_provider_env_overrides(provider: LlmProviderConfig) -> LlmProviderConfig:
    prefix = provider.name.upper()
    return LlmProviderConfig(
        name=provider.name,
        api_key=os.getenv(f"{prefix}_API_KEY", provider.api_key),
        base_url=os.getenv(f"{prefix}_BASE_URL", provider.base_url),
        model=os.getenv(f"{prefix}_MODEL", provider.model),
    )


def load_config(config_path: Path | None = None) -> AppConfig:
    yaml_path = config_path or Path(os.getenv("ENTERPRISE_QA_CONFIG_PATH", "config.yaml"))
    yaml_config = _load_yaml_config(yaml_path)
    yaml_database = yaml_config.get("database", {})
    yaml_kb = yaml_config.get("knowledge_base", {})
    yaml_llm = yaml_config.get("llm", {})
    providers = [_with_provider_env_overrides(provider) for provider in (_yaml_providers(yaml_config) or _default_providers())]

    return AppConfig(
        database_path=Path(os.getenv("ENTERPRISE_QA_DB_PATH", str(yaml_database.get("path", "data/enterprise.db")))),
        knowledge_path=Path(os.getenv("ENTERPRISE_QA_KB_PATH", str(yaml_kb.get("root_path", "data/knowledge")))),
        current_date=os.getenv("ENTERPRISE_QA_CURRENT_DATE", str(yaml_config.get("current_date", "2026-03-27"))),
        timezone=os.getenv("ENTERPRISE_QA_TIMEZONE", str(yaml_config.get("timezone", "Asia/Shanghai"))),
        timeout_seconds=int(os.getenv("ENTERPRISE_QA_LLM_TIMEOUT", str(yaml_llm.get("timeout_seconds", "20")))),
        answer_polish=_env_bool("ENTERPRISE_QA_ANSWER_POLISH", bool(yaml_llm.get("answer_polish", True))),
        providers=providers,
    )
