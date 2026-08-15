"""Pytest configuration — fixtures available to all tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repository root."""
    return Path(__file__).parent.parent
