import pytest
import pytest_asyncio

from maestro.models import Task, TaskStatus
from maestro.store import Store


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = Store(db_path)
    await s.init_db()
    return s


@pytest.mark.asyncio
async def test_save_and_get_slack_notification(store):
    task = Task(
        id="t1",
        type="test",
        title="Test",
        instruction="do it",
        agent="default",
        status=TaskStatus.PENDING,
    )
    await store.create_task(task)
    await store.save_task_slack_notification("t1", "C123", "1234567890.123456")
    row = await store.get_task_slack_notification("t1")
    assert row == ("C123", "1234567890.123456")


@pytest.mark.asyncio
async def test_get_slack_notification_missing(store):
    task = Task(
        id="t2",
        type="test",
        title="Test2",
        instruction="do it",
        agent="default",
        status=TaskStatus.PENDING,
    )
    await store.create_task(task)
    row = await store.get_task_slack_notification("t2")
    assert row is None


@pytest.mark.asyncio
async def test_migration_idempotent(store):
    # calling init_db twice should not raise
    await store.init_db()
    row = await store.get_task_slack_notification("nonexistent")
    assert row is None
