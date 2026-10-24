import uuid

from app.database.base import Base
from app.database.models.memory import Memory, MemorySource
from app.database.models.user import User
from sqlalchemy import inspect


def test_memory_table_definition() -> None:
    table = Memory.__table__

    assert table.name == "memories"

    for column in (
        "id",
        "user_id",
        "memory_type",
        "content",
        "normalized_content",
        "status",
        "confidence",
        "valid_from",
        "valid_until",
        "last_confirmed_at",
        "supersedes_id",
        "created_at",
        "updated_at",
    ):
        assert column in table.c

    assert table.c.id.primary_key
    assert not table.c.user_id.nullable
    assert not table.c.memory_type.nullable
    assert not table.c.content.nullable
    assert not table.c.status.nullable


def test_memory_source_table_definition() -> None:
    table = MemorySource.__table__

    assert table.name == "memory_sources"

    for column in (
        "id",
        "memory_id",
        "source_kind",
        "document_id",
        "chunk_id",
        "source_reference",
        "evidence_text",
        "created_at",
    ):
        assert column in table.c

    assert table.c.id.primary_key
    assert not table.c.memory_id.nullable
    assert not table.c.source_kind.nullable
    assert table.c.document_id.nullable
    assert table.c.chunk_id.nullable


def test_memory_status_default() -> None:
    column = Memory.__table__.c.status

    assert column.default is not None
    assert column.default.arg == "active"
    assert column.server_default is not None


def test_memory_relationships() -> None:
    assert Memory.user.property.back_populates == "memories"
    assert User.memories.property.back_populates == "user"
    assert Memory.sources.property.back_populates == "memory"
    assert MemorySource.memory.property.back_populates == "sources"


def test_memory_supports_supersession() -> None:
    previous_id = uuid.uuid4()

    memory = Memory(
        user_id=uuid.uuid4(),
        memory_type="preference",
        content="Prefers Python for scripting.",
        supersedes_id=previous_id,
    )

    assert memory.supersedes_id == previous_id


def test_memory_source_can_reference_a_document_chunk() -> None:
    memory_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    source = MemorySource(
        memory_id=memory_id,
        source_kind="document_extracted",
        document_id=document_id,
        chunk_id=chunk_id,
        evidence_text="The user prefers Python.",
    )

    assert source.memory_id == memory_id
    assert source.document_id == document_id
    assert source.chunk_id == chunk_id


def test_memory_models_are_registered_with_metadata() -> None:
    assert "memories" in Base.metadata.tables
    assert "memory_sources" in Base.metadata.tables


def test_memory_constraints_are_defined() -> None:
    constraints = {
        constraint.name
        for constraint in inspect(Memory).local_table.constraints
    }

    assert "ck_memories_memory_type" in constraints
    assert "ck_memories_status" in constraints
    assert "ck_memories_confidence_range" in constraints
    assert "ck_memories_validity_range" in constraints