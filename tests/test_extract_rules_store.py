import pytest

from maestro.store import Store


@pytest.fixture
async def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    await s.init_db()
    return s


@pytest.mark.asyncio
async def test_create_and_get_rule(store):
    await store.create_extract_rule(
        task_type="create_post",
        asset_type="post",
        title_field="content.text",
        tags_from=["content.hashtag"],
    )
    rule = await store.get_extract_rule("create_post")
    assert rule is not None
    assert rule["asset_type"] == "post"
    assert rule["title_field"] == "content.text"


@pytest.mark.asyncio
async def test_list_rules(store):
    await store.create_extract_rule(
        task_type="post",
        asset_type="post",
    )
    await store.create_extract_rule(
        task_type="engage",
        asset_type="engage",
    )
    rules = await store.list_extract_rules()
    assert len(rules) == 2


@pytest.mark.asyncio
async def test_list_all_rules(store):
    await store.create_extract_rule(task_type="t1", asset_type="x")
    await store.create_extract_rule(task_type="t2", asset_type="y")
    rules = await store.list_extract_rules()
    assert len(rules) == 2


@pytest.mark.asyncio
async def test_delete_rule(store):
    await store.create_extract_rule(task_type="t", asset_type="a")
    await store.delete_extract_rule("t")
    assert await store.get_extract_rule("t") is None


@pytest.mark.asyncio
async def test_upsert_rule(store):
    await store.create_extract_rule(
        task_type="t",
        asset_type="a",
        title_field="old",
    )
    await store.create_extract_rule(
        task_type="t",
        asset_type="a",
        title_field="new",
    )
    rule = await store.get_extract_rule("t")
    assert rule["title_field"] == "new"
