import uuid

from sqlalchemy import inspect

from app.database.base import Base
from app.database.models.knowledge_relationship import (
    KNOWLEDGE_ENTITY_TYPES,
    KNOWLEDGE_RELATIONSHIP_TYPES,
    KnowledgeRelationship,
    KnowledgeRelationshipSource,
)
from app.database.models.user import User


def test_knowledge_relationship_table_definition() -> None:
    table = KnowledgeRelationship.__table__

    assert table.name == "knowledge_relationships"
    assert table.c.id.primary_key
    assert not table.c.user_id.nullable
    assert not table.c.source_type.nullable
    assert not table.c.source_id.nullable
    assert not table.c.relationship_type.nullable
    assert not table.c.target_type.nullable
    assert not table.c.target_id.nullable
    assert not table.c.created_at.nullable
    assert not table.c.updated_at.nullable


def test_knowledge_relationship_supports_typed_directed_edges() -> None:
    source_id = uuid.uuid4()
    target_id = uuid.uuid4()
    user_id = uuid.uuid4()

    edge = KnowledgeRelationship(
        user_id=user_id,
        source_type="decision",
        source_id=source_id,
        relationship_type="affects",
        target_type="project",
        target_id=target_id,
    )

    assert edge.user_id == user_id
    assert edge.source_type == "decision"
    assert edge.source_id == source_id
    assert edge.relationship_type == "affects"
    assert edge.target_type == "project"
    assert edge.target_id == target_id


def test_supported_entity_and_relationship_types_are_explicit() -> None:
    assert KNOWLEDGE_ENTITY_TYPES == (
        "project",
        "person",
        "task",
        "commitment",
        "decision",
        "risk",
        "document",
        "memory",
    )
    assert "depends_on" in KNOWLEDGE_RELATIONSHIP_TYPES
    assert "derived_from" in KNOWLEDGE_RELATIONSHIP_TYPES


def test_relationship_constraints_and_indexes_are_defined() -> None:
    table = KnowledgeRelationship.__table__

    constraint_names = {
        constraint.name for constraint in table.constraints if constraint.name
    }
    index_names = {index.name for index in table.indexes}

    assert "ck_knowledge_relationships_source_type" in constraint_names
    assert "ck_knowledge_relationships_target_type" in constraint_names
    assert "ck_knowledge_relationships_relationship_type" in constraint_names
    assert "ck_knowledge_relationships_no_self_reference" in constraint_names
    assert "uq_knowledge_relationships_directed_edge" in constraint_names

    assert "ix_knowledge_relationships_source" in index_names
    assert "ix_knowledge_relationships_target" in index_names
    assert "ix_knowledge_relationships_type" in index_names


def test_relationship_provenance_uses_composite_primary_key() -> None:
    table = KnowledgeRelationshipSource.__table__

    assert table.name == "knowledge_relationship_sources"
    assert list(table.primary_key.columns.keys()) == [
        "relationship_id",
        "chunk_id",
    ]

    assert next(
        iter(table.c.relationship_id.foreign_keys)
    ).target_fullname == "knowledge_relationships.id"

    assert next(
        iter(table.c.chunk_id.foreign_keys)
    ).target_fullname == "document_chunks.id"


def test_relationship_model_is_registered_with_metadata() -> None:
    assert "knowledge_relationships" in Base.metadata.tables
    assert "knowledge_relationship_sources" in Base.metadata.tables


def test_user_relationship_is_configured() -> None:
    user_relationship = inspect(User).relationships.knowledge_relationships
    relationship_user = inspect(KnowledgeRelationship).relationships.user

    assert user_relationship.back_populates == "user"
    assert relationship_user.back_populates == "knowledge_relationships"
    assert user_relationship.uselist is True
    assert relationship_user.uselist is False


def test_relationship_sources_are_configured() -> None:
    assert (
        inspect(KnowledgeRelationship).relationships.sources.back_populates
        == "knowledge_relationship"
    )

    assert (
        inspect(KnowledgeRelationshipSource)
        .relationships.knowledge_relationship.back_populates
        == "sources"
    )