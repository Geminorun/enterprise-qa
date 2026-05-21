from pathlib import Path

import pytest


@pytest.fixture
def db_path() -> Path:
    return Path("data/enterprise.db")


@pytest.fixture
def kb_path() -> Path:
    return Path("data/knowledge")
