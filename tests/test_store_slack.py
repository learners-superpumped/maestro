import pytest

from maestro.store import Store


@pytest.fixture
async def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    await s.init_db()
    return s


@pytest.mark.asyncio
async def test_create_and_get_slack_thread(store):
    entry = await store.create_slack_thread(
        channel_id="C123",
        thread_ts="1234567890.000100",
        conversation_id="conv-1",
        user_id="U001",
    )
    assert entry["slack_channel_id"] == "C123"
    assert entry["slack_thread_ts"] == "1234567890.000100"
    assert entry["conversation_id"] == "conv-1"
    assert entry["slack_user_id"] == "U001"
    assert entry["progress_msg_ts"] is None
    assert entry["created_at"] is not None

    fetched = await store.get_slack_thread("C123", "1234567890.000100")
    assert fetched is not None
    assert fetched["slack_channel_id"] == "C123"
    assert fetched["slack_thread_ts"] == "1234567890.000100"
    assert fetched["conversation_id"] == "conv-1"
    assert fetched["slack_user_id"] == "U001"
    assert fetched["progress_msg_ts"] is None


@pytest.mark.asyncio
async def test_get_slack_thread_by_conversation(store):
    await store.create_slack_thread(
        channel_id="C456",
        thread_ts="9999999999.000200",
        conversation_id="conv-2",
        user_id="U002",
    )

    fetched = await store.get_slack_thread_by_conversation("conv-2")
    assert fetched is not None
    assert fetched["slack_channel_id"] == "C456"
    assert fetched["slack_thread_ts"] == "9999999999.000200"
    assert fetched["conversation_id"] == "conv-2"
    assert fetched["slack_user_id"] == "U002"


@pytest.mark.asyncio
async def test_get_slack_thread_not_found(store):
    result = await store.get_slack_thread("C_MISSING", "0000000000.000000")
    assert result is None

    result = await store.get_slack_thread_by_conversation("conv-nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_update_progress_msg_ts(store):
    await store.create_slack_thread(
        channel_id="C789",
        thread_ts="1111111111.000300",
        conversation_id="conv-3",
        user_id="U003",
    )

    await store.update_slack_thread_progress(
        channel_id="C789",
        thread_ts="1111111111.000300",
        progress_msg_ts="1111111111.000400",
    )

    fetched = await store.get_slack_thread("C789", "1111111111.000300")
    assert fetched is not None
    assert fetched["progress_msg_ts"] == "1111111111.000400"


@pytest.mark.asyncio
async def test_list_all_slack_threads(store):
    initial = await store.list_slack_threads()
    assert initial == []

    await store.create_slack_thread("CA", "1000000000.000001", "conv-a", "UA")
    await store.create_slack_thread("CB", "2000000000.000002", "conv-b", "UB")
    await store.create_slack_thread("CC", "3000000000.000003", "conv-c", "UC")

    threads = await store.list_slack_threads()
    assert len(threads) == 3
    conversation_ids = {t["conversation_id"] for t in threads}
    assert conversation_ids == {"conv-a", "conv-b", "conv-c"}
