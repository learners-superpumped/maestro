import pytest
from maestro.store import Store

@pytest.fixture
async def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    await s.init_db()
    return s

@pytest.mark.asyncio
async def test_schedule_last_run_roundtrip(store):
    assert await store.get_schedule_last_run("test-sched") is None
    await store.set_schedule_last_run("test-sched", "2026-03-23T09:00:00Z")
    assert await store.get_schedule_last_run("test-sched") == "2026-03-23T09:00:00Z"

@pytest.mark.asyncio
async def test_schedule_last_run_upsert(store):
    await store.set_schedule_last_run("s1", "2026-03-23T09:00:00Z")
    await store.set_schedule_last_run("s1", "2026-03-23T10:00:00Z")
    assert await store.get_schedule_last_run("s1") == "2026-03-23T10:00:00Z"

@pytest.mark.asyncio
async def test_scheduler_state_roundtrip(store):
    assert await store.get_scheduler_state("last_tick") is None
    await store.set_scheduler_state("last_tick", "2026-03-23T09:00:00Z")
    assert await store.get_scheduler_state("last_tick") == "2026-03-23T09:00:00Z"

@pytest.mark.asyncio
async def test_increment_review_count(store):
    from maestro.models import Task
    task = Task(id="t1", type="test", workspace="ws", title="T", instruction="I")
    await store.create_task(task)
    t = await store.get_task("t1")
    assert t.review_count == 0
    await store.increment_review_count("t1")
    t = await store.get_task("t1")
    assert t.review_count == 1

@pytest.mark.asyncio
async def test_list_children(store):
    from maestro.models import Task
    parent = Task(id="p1", type="t", workspace="ws", title="Parent", instruction="I")
    child1 = Task(id="c1", type="t", workspace="ws", title="Child1", instruction="I", parent_task_id="p1")
    child2 = Task(id="c2", type="t", workspace="ws", title="Child2", instruction="I", parent_task_id="p1")
    other = Task(id="o1", type="t", workspace="ws", title="Other", instruction="I")
    await store.create_task(parent)
    await store.create_task(child1)
    await store.create_task(child2)
    await store.create_task(other)

    children = await store.list_children("p1")
    assert len(children) == 2
    assert {c.id for c in children} == {"c1", "c2"}

@pytest.mark.asyncio
async def test_list_children_empty(store):
    from maestro.models import Task
    task = Task(id="lone", type="t", workspace="ws", title="T", instruction="I")
    await store.create_task(task)
    children = await store.list_children("lone")
    assert len(children) == 0

@pytest.mark.asyncio
async def test_find_root_task_id(store):
    from maestro.models import Task
    t1 = Task(id="r1", type="t", workspace="ws", title="Root", instruction="I")
    t2 = Task(id="r2", type="t", workspace="ws", title="Child", instruction="I", parent_task_id="r1")
    t3 = Task(id="r3", type="t", workspace="ws", title="Grandchild", instruction="I", parent_task_id="r2")
    await store.create_task(t1)
    await store.create_task(t2)
    await store.create_task(t3)

    assert await store.find_root_task_id("r3") == "r1"
    assert await store.find_root_task_id("r2") == "r1"
    assert await store.find_root_task_id("r1") == "r1"

@pytest.mark.asyncio
async def test_get_task_tree(store):
    from maestro.models import Task
    t1 = Task(id="tr1", type="t", workspace="ws", title="Root", instruction="I")
    t2 = Task(id="tr2", type="t", workspace="ws", title="Child", instruction="I", parent_task_id="tr1")
    t3 = Task(id="tr3", type="t", workspace="ws", title="Grandchild", instruction="I", parent_task_id="tr2")
    unrelated = Task(id="tr4", type="t", workspace="ws", title="Unrelated", instruction="I")
    await store.create_task(t1)
    await store.create_task(t2)
    await store.create_task(t3)
    await store.create_task(unrelated)

    tree = await store.get_task_tree("tr1")
    assert len(tree) == 3
    assert {t.id for t in tree} == {"tr1", "tr2", "tr3"}
