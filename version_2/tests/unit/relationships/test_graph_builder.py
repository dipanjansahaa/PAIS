from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.relationships.graph_builder import KnowledgeGraphConstructionService


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _ExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Session:
    def __init__(self, scalar_batches, execute_rows):
        self._scalar_batches = list(scalar_batches)
        self._execute_rows = execute_rows
        self.flush = AsyncMock()

    async def scalars(self, _statement):
        return _ScalarResult(self._scalar_batches.pop(0))

    async def execute(self, _statement):
        return _ExecuteResult(self._execute_rows)


@pytest.mark.asyncio
async def test_constructs_only_explicit_user_owned_associations_and_sources():
    user_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    task_id = uuid4()
    commitment_id = uuid4()
    decision_id = uuid4()
    newer_memory_id = uuid4()
    older_memory_id = uuid4()
    foreign_project_id = uuid4()
    chunk_ids = [uuid4(), uuid4(), uuid4(), uuid4(), uuid4()]

    project = SimpleNamespace(id=project_id, user_id=user_id)
    document = SimpleNamespace(id=document_id, user_id=user_id, project_id=project_id)
    task = SimpleNamespace(
        id=task_id,
        user_id=user_id,
        project_id=foreign_project_id,  # not in the user's project set
        commitment_id=commitment_id,
        owner=None,
    )
    commitment = SimpleNamespace(
        id=commitment_id, user_id=user_id, project_id=project_id, owner=None
    )
    decision = SimpleNamespace(id=decision_id, user_id=user_id, project_id=project_id)
    newer_memory = SimpleNamespace(
        id=newer_memory_id, user_id=user_id, supersedes_id=older_memory_id
    )
    older_memory = SimpleNamespace(id=older_memory_id, user_id=user_id, supersedes_id=None)

    task_source = SimpleNamespace(task_id=task_id, chunk_id=chunk_ids[1])
    commitment_source = SimpleNamespace(commitment_id=commitment_id, chunk_id=chunk_ids[2])
    decision_source = SimpleNamespace(decision_id=decision_id, chunk_id=chunk_ids[3])
    memory_source = SimpleNamespace(memory_id=newer_memory_id, chunk_id=chunk_ids[4])

    session = _Session(
        scalar_batches=[
            [project],
            [document],
            [task],
            [commitment],
            [decision],
            [newer_memory, older_memory],
            [],  # user-owned people
            [task_source],
            [commitment_source],
            [decision_source],
            [memory_source],
        ],
        execute_rows=[(document_id, chunk_ids[0])],
    )

    relationship_service = SimpleNamespace(
        create_relationship=AsyncMock(),
        add_sources=AsyncMock(),
    )
    generated_relationship_ids = [uuid4() for _ in range(5)]
    relationship_service.create_relationship.side_effect = [
        SimpleNamespace(id=value) for value in generated_relationship_ids
    ]

    service = KnowledgeGraphConstructionService(relationship_service=relationship_service)
    result = await service.construct_for_user(session, user_id=user_id)

    assert result.relationships_processed == 5
    assert result.provenance_links_processed == 6
    assert relationship_service.create_relationship.await_count == 5
    assert relationship_service.add_sources.await_count == 5
    session.flush.assert_awaited_once()

    calls = relationship_service.create_relationship.await_args_list
    edges = [
        (
            call.kwargs["source_type"],
            call.kwargs["source_id"],
            call.kwargs["relationship_type"],
            call.kwargs["target_type"],
            call.kwargs["target_id"],
        )
        for call in calls
    ]
    assert edges == [
        ("document", document_id, "belongs_to", "project", project_id),
        ("commitment", commitment_id, "fulfills", "task", task_id),
        ("commitment", commitment_id, "belongs_to", "project", project_id),
        ("decision", decision_id, "belongs_to", "project", project_id),
        ("memory", newer_memory_id, "supersedes", "memory", older_memory_id),
    ]

    source_calls = relationship_service.add_sources.await_args_list
    assert source_calls[0].kwargs["chunk_ids"] == [chunk_ids[0]]
    assert source_calls[1].kwargs["chunk_ids"] == [chunk_ids[2], chunk_ids[1]]
    assert source_calls[2].kwargs["chunk_ids"] == [chunk_ids[2]]
    assert source_calls[3].kwargs["chunk_ids"] == [chunk_ids[3]]
    assert source_calls[4].kwargs["chunk_ids"] == [chunk_ids[4]]


@pytest.mark.asyncio
async def test_does_not_create_edges_without_explicit_associations():
    user_id = uuid4()
    session = _Session(
        scalar_batches=[[], [], [], [], [], [], [], [], [], [], []],
        execute_rows=[],
    )
    relationship_service = SimpleNamespace(
        create_relationship=AsyncMock(),
        add_sources=AsyncMock(),
    )

    result = await KnowledgeGraphConstructionService(
        relationship_service=relationship_service
    ).construct_for_user(session, user_id=user_id)

    assert result.relationships_processed == 0
    assert result.provenance_links_processed == 0
    relationship_service.create_relationship.assert_not_awaited()
    relationship_service.add_sources.assert_not_awaited()
    session.flush.assert_awaited_once()
