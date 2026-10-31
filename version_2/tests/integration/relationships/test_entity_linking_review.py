from __future__ import annotations

from uuid import uuid4

import pytest
from app.database.models.commitment import Commitment, CommitmentSource
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.knowledge_relationship import (
    KnowledgeRelationship,
    KnowledgeRelationshipSource,
)
from app.database.models.person import Person
from app.database.models.user import User
from app.relationships.graph_builder import KnowledgeGraphConstructionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_exact_commitment_owner_creates_edge_with_provenance(
    db_session: AsyncSession,
):
    user = User(
        email=f"commitment-linking-{uuid4()}@example.com",
        display_name="Commitment Linking Integration User",
    )
    db_session.add(user)
    await db_session.flush()

    person = Person(
        user_id=user.id,
        name="Grace Hopper",
        email="grace.hopper@example.com",
    )
    document = Document(
        user_id=user.id,
        title="Commitment owner evidence",
        source_type="notes",
        content_hash=f"commitment-linking-{uuid4()}",
        raw_text="Grace owns the release review commitment.",
    )
    db_session.add_all([person, document])
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="Grace owns the release review commitment.",
        embedding=[1.0] + [0.0] * 383,
    )
    db_session.add(chunk)
    await db_session.flush()

    commitment = Commitment(
        user_id=user.id,
        description="Complete the release review",
        owner=" GRACE.HOPPER@EXAMPLE.COM ",
        status="open",
    )
    db_session.add(commitment)
    await db_session.flush()

    db_session.add(
        CommitmentSource(
            commitment_id=commitment.id,
            chunk_id=chunk.id,
        )
    )
    await db_session.flush()

    result = await KnowledgeGraphConstructionService().construct_for_user(
        db_session,
        user_id=user.id,
    )
    await db_session.flush()

    assert result.person_links_matched == 1
    assert result.person_links_ambiguous == 0
    assert result.person_links_unmatched == 0

    edge = await db_session.scalar(
        select(KnowledgeRelationship).where(
            KnowledgeRelationship.user_id == user.id,
            KnowledgeRelationship.source_type == "commitment",
            KnowledgeRelationship.source_id == commitment.id,
            KnowledgeRelationship.relationship_type == "assigned_to",
            KnowledgeRelationship.target_type == "person",
            KnowledgeRelationship.target_id == person.id,
        )
    )
    assert edge is not None

    provenance = await db_session.scalar(
        select(KnowledgeRelationshipSource).where(
            KnowledgeRelationshipSource.relationship_id == edge.id,
            KnowledgeRelationshipSource.chunk_id == chunk.id,
        )
    )
    assert provenance is not None


@pytest.mark.asyncio
async def test_owner_reference_cannot_link_to_another_users_person(
    db_session: AsyncSession,
):
    owner = User(
        email=f"entity-owner-{uuid4()}@example.com",
        display_name="Entity Owner",
    )
    other_user = User(
        email=f"entity-other-{uuid4()}@example.com",
        display_name="Other User",
    )
    db_session.add_all([owner, other_user])
    await db_session.flush()

    foreign_person = Person(
        user_id=other_user.id,
        name="Private Person",
        email="private.person@example.com",
    )
    db_session.add(foreign_person)
    await db_session.flush()

    commitment = Commitment(
        user_id=owner.id,
        description="Review a private item",
        owner="private.person@example.com",
        status="open",
    )
    db_session.add(commitment)
    await db_session.flush()

    result = await KnowledgeGraphConstructionService().construct_for_user(
        db_session,
        user_id=owner.id,
    )
    await db_session.flush()

    assert result.person_links_matched == 0
    assert result.person_links_ambiguous == 0
    assert result.person_links_unmatched == 1

    edge = await db_session.scalar(
        select(KnowledgeRelationship).where(
            KnowledgeRelationship.user_id == owner.id,
            KnowledgeRelationship.source_type == "commitment",
            KnowledgeRelationship.source_id == commitment.id,
            KnowledgeRelationship.relationship_type == "assigned_to",
        )
    )
    assert edge is None
