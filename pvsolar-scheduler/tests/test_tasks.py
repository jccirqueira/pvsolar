import pytest
from src.core.config import TaskConfig, TaskPriority, TaskStatus, TaskType
from src.tasks.task import Task, TaskRegistry, TaskResult


class TestTaskResult:
    def test_create(self):
        r = TaskResult("t1", TaskStatus.COMPLETED, output={"key": "val"})
        assert r.task_id == "t1"
        assert r.status == TaskStatus.COMPLETED
        assert r.output == {"key": "val"}

    def test_to_dict(self):
        r = TaskResult("t1", TaskStatus.FAILED, error="timeout")
        d = r.to_dict()
        assert d["task_id"] == "t1"
        assert d["status"] == "failed"
        assert d["error"] == "timeout"


class TestTask:
    def test_create(self):
        cfg = TaskConfig(id="t1", name="Test Task")
        task = Task(cfg)
        assert task.config.id == "t1"
        assert task.status == TaskStatus.PENDING
        assert task.run_count == 0

    def test_to_dict(self):
        cfg = TaskConfig(id="t1", name="Test", task_type=TaskType.DATA_SYNC)
        task = Task(cfg)
        d = task.to_dict()
        assert d["id"] == "t1"
        assert d["task_type"] == "data_sync"
        assert d["status"] == "pending"


class TestTaskRegistry:
    def test_add_task(self):
        reg = TaskRegistry()
        cfg = TaskConfig(id="t1", name="Task 1")
        task = reg.add_task(cfg)
        assert task.config.id == "t1"

    def test_add_auto_id(self):
        reg = TaskRegistry()
        task = reg.add_task(TaskConfig(name="Auto"))
        assert len(task.config.id) == 8

    def test_get_task(self):
        reg = TaskRegistry()
        reg.add_task(TaskConfig(id="t1", name="T"))
        task = reg.get_task("t1")
        assert task is not None
        assert task.config.name == "T"

    def test_get_nonexistent(self):
        reg = TaskRegistry()
        assert reg.get_task("nope") is None

    def test_list_tasks(self):
        reg = TaskRegistry()
        reg.add_task(TaskConfig(id="t1", name="A"))
        reg.add_task(TaskConfig(id="t2", name="B"))
        assert len(reg.list_tasks()) == 2

    def test_remove_task(self):
        reg = TaskRegistry()
        reg.add_task(TaskConfig(id="t1", name="T"))
        assert reg.remove_task("t1") is True
        assert reg.get_task("t1") is None

    def test_remove_nonexistent(self):
        reg = TaskRegistry()
        assert reg.remove_task("nope") is False

    def test_update_task(self):
        reg = TaskRegistry()
        reg.add_task(TaskConfig(id="t1", name="Old"))
        task = reg.update_task("t1", name="New")
        assert task is not None
        assert task.config.name == "New"

    def test_update_nonexistent(self):
        reg = TaskRegistry()
        assert reg.update_task("nope", name="X") is None

    def test_register_handler(self):
        reg = TaskRegistry()
        async def handler(cfg):
            return {"ok": True}
        reg.register_handler("custom", handler)
        assert reg.get_handler("custom") is not None

    def test_get_handler_none(self):
        reg = TaskRegistry()
        assert reg.get_handler("nonexistent") is None

    def test_statistics(self):
        reg = TaskRegistry()
        reg.add_task(TaskConfig(id="t1", name="A", enabled=True))
        reg.add_task(TaskConfig(id="t2", name="B", enabled=False))
        stats = reg.get_statistics()
        assert stats["total"] == 2
        assert stats["enabled"] == 1
        assert stats["disabled"] == 1
