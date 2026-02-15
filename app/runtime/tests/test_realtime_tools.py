"""Tests for the realtime tools module -- TaskStore and handlers."""

from __future__ import annotations

import asyncio
import json

import pytest

from app.runtime.realtime.tools import (
    ALL_REALTIME_TOOL_SCHEMAS,
    TaskStatus,
    TaskStore,
    handle_check_agent_task,
    handle_invoke_agent,
    handle_invoke_agent_async,
)


class TestTaskStore:
    def test_create(self) -> None:
        store = TaskStore()
        task = store.create("Do something")
        assert task.prompt == "Do something"
        assert task.status == TaskStatus.PENDING

    def test_get(self) -> None:
        store = TaskStore()
        task = store.create("X")
        found = store.get(task.id)
        assert found is not None
        assert found.id == task.id

    def test_get_nonexistent(self) -> None:
        store = TaskStore()
        assert store.get("nope") is None

    def test_complete(self) -> None:
        store = TaskStore()
        task = store.create("X")
        store.complete(task.id, "done!")
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "done!"
        assert task.completed_at is not None

    def test_fail(self) -> None:
        store = TaskStore()
        task = store.create("X")
        store.fail(task.id, "oops")
        assert task.status == TaskStatus.FAILED
        assert task.error == "oops"
        assert task.completed_at is not None

    def test_complete_nonexistent(self) -> None:
        store = TaskStore()
        store.complete("nope", "result")

    def test_fail_nonexistent(self) -> None:
        store = TaskStore()
        store.fail("nope", "error")


class TestTaskStatus:
    def test_values(self) -> None:
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"


class TestSchemas:
    def test_all_schemas_present(self) -> None:
        assert len(ALL_REALTIME_TOOL_SCHEMAS) == 3
        names = {s["name"] for s in ALL_REALTIME_TOOL_SCHEMAS}
        assert "invoke_agent" in names
        assert "invoke_agent_async" in names
        assert "check_agent_task" in names

    def test_schema_structure(self) -> None:
        for schema in ALL_REALTIME_TOOL_SCHEMAS:
            assert schema["type"] == "function"
            assert "name" in schema
            assert "description" in schema
            assert "parameters" in schema


@pytest.mark.asyncio
class TestHandleInvokeAgent:
    async def test_empty_prompt(self) -> None:
        result = await handle_invoke_agent({}, agent=None)
        assert "Error" in result or "no prompt" in result

    async def test_success(self) -> None:
        class FakeAgent:
            async def send(self, prompt: str) -> str:
                return f"Response to: {prompt}"

        result = await handle_invoke_agent({"prompt": "hello"}, agent=FakeAgent())
        assert "Response to: hello" in result

    async def test_agent_returns_none(self) -> None:
        class FakeAgent:
            async def send(self, prompt: str) -> str | None:
                return None

        result = await handle_invoke_agent({"prompt": "hello"}, agent=FakeAgent())
        assert "no response" in result.lower()

    async def test_agent_exception(self) -> None:
        class FakeAgent:
            async def send(self, prompt: str) -> str:
                raise RuntimeError("broke")

        result = await handle_invoke_agent({"prompt": "hello"}, agent=FakeAgent())
        assert "Error" in result


@pytest.mark.asyncio
class TestHandleCheckAgentTask:
    async def test_no_task_id(self) -> None:
        result = await handle_check_agent_task({})
        data = json.loads(result)
        assert "error" in data

    async def test_not_found(self) -> None:
        result = await handle_check_agent_task({"task_id": "missing"})
        data = json.loads(result)
        assert "error" in data
