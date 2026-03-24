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
        workspace="sns-threads", task_type="create_post",
        asset_type="post", title_field="content.text",
        tags_from=["content.hashtag"],
    )
    rule = await store.get_extract_rule("sns-threads", "create_post")
    assert rule is not None
    assert rule["asset_type"] == "post"
    assert rule["title_field"] == "content.text"

@pytest.mark.asyncio
async def test_list_rules(store):
    await store.create_extract_rule(
        workspace="sns", task_type="post", asset_type="post",
    )
    await store.create_extract_rule(
        workspace="sns", task_type="engage", asset_type="engage",
    )
    rules = await store.list_extract_rules()
    assert len(rules) == 2

@pytest.mark.asyncio
async def test_list_rules_by_workspace(store):
    await store.create_extract_rule(workspace="a", task_type="t", asset_type="x")
    await store.create_extract_rule(workspace="b", task_type="t", asset_type="y")
    rules = await store.list_extract_rules(workspace="a")
    assert len(rules) == 1

@pytest.mark.asyncio
async def test_delete_rule(store):
    await store.create_extract_rule(workspace="w", task_type="t", asset_type="a")
    await store.delete_extract_rule("w", "t")
    assert await store.get_extract_rule("w", "t") is None

@pytest.mark.asyncio
async def test_upsert_rule(store):
    await store.create_extract_rule(
        workspace="w", task_type="t", asset_type="a", title_field="old",
    )
    await store.create_extract_rule(
        workspace="w", task_type="t", asset_type="a", title_field="new",
    )
    rule = await store.get_extract_rule("w", "t")
    assert rule["title_field"] == "new"
