"""Shared test fixtures for Maestro."""

from __future__ import annotations

import pathlib

import aiosqlite
import pytest


@pytest.fixture
def tmp_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Return a temporary directory for test artifacts."""
    return tmp_path


@pytest.fixture
def config_dict() -> dict:
    """Return a minimal valid Maestro configuration dictionary."""
    return {
        "project": {
            "name": "test-project",
            "root": "/tmp/maestro-test",
        },
        "daemon": {
            "poll_seconds": 5,
            "pid_file": "/tmp/maestro-test/maestro.pid",
        },
        "concurrency": {
            "max_tasks": 4,
        },
        "budget": {
            "max_cost_usd": 10.0,
        },
        "agent": {
            "model": "test-model",
            "provider": "test",
        },
        "logging": {
            "level": "DEBUG",
            "dir": "/tmp/maestro-test/logs",
        },
    }


@pytest.fixture
async def db_path(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a temporary SQLite database with the Maestro schema applied.

    If schema.sql does not yet exist (created in a later task), a minimal
    placeholder schema is used so that early tests can still run.
    """
    db_file = tmp_path / "maestro.db"
    schema_file = (
        pathlib.Path(__file__).resolve().parent.parent
        / "src"
        / "maestro"
        / "schema.sql"
    )

    if schema_file.exists():
        schema_sql = schema_file.read_text()
    else:
        # Placeholder until schema.sql is created in Task 4
        schema_sql = """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """

    async with aiosqlite.connect(str(db_file)) as db:
        await db.executescript(schema_sql)
        await db.commit()

    return db_file
