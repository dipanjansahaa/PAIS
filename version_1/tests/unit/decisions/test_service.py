from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.decisions.service import DecisionService
from app.intelligence.models import DecisionCandidate, IntelligenceSource


def _candidate(*chunk_ids):
    return DecisionCandidate(
        title="Database choice",
        description="Use PostgreSQL",
        decision_date=datetime(
            2026,
            9,
            30,
            tzinfo=timezone.utc,
        ),
        sources=[
            IntelligenceSource(chunk_id=chunk_id)
            for chunk_id in chunk_ids
        ],
    )


def _session(*, scalar_result=None, source_ids=None):
    session = MagicMock()

    session.scalar = AsyncMock(
        return_value=scalar_result,
    )

    scalars_result = MagicMock()
    scalars_result.all.return_value = list(
        source_ids or []
    )

    session.scalars = AsyncMock(
        return_value=scalars_result,
    )

    session.flush = AsyncMock()

    return session


@pytest.mark.asyncio
async def test_create_decision_from_candidate() -> None:
    user_id = uuid4()
    chunk_id = uuid4()

    session = _session(
        scalar_result=uuid4(),
        source_ids=[chunk_id],
    )

    decision = await DecisionService().create_from_candidate(
        session,
        user_id=user_id,
        candidate=_candidate(chunk_id),
    )

    assert decision.user_id == user_id
    assert decision.title == "Database choice"
    assert decision.description == "Use PostgreSQL"
    assert decision.decision_date is not None

    assert session.add.call_count == 1
    assert session.add_all.call_count == 1
    assert session.flush.await_count == 2


@pytest.mark.asyncio
async def test_create_decision_with_multiple_sources() -> None:
    chunk_a = uuid4()
    chunk_b = uuid4()

    session = _session(
        source_ids=[chunk_a, chunk_b],
    )

    await DecisionService().create_from_candidate(
        session,
        user_id=uuid4(),
        candidate=_candidate(
            chunk_a,
            chunk_b,
        ),
    )

    sources = session.add_all.call_args.args[0]

    assert [
        source.chunk_id
        for source in sources
    ] == [
        chunk_a,
        chunk_b,
    ]


@pytest.mark.asyncio
async def test_create_decision_deduplicates_source_chunks() -> None:
    chunk_id = uuid4()

    session = _session(
        source_ids=[chunk_id],
    )

    await DecisionService().create_from_candidate(
        session,
        user_id=uuid4(),
        candidate=_candidate(
            chunk_id,
            chunk_id,
        ),
    )

    sources = session.add_all.call_args.args[0]

    assert len(sources) == 1
    assert sources[0].chunk_id == chunk_id


@pytest.mark.asyncio
async def test_create_decision_rejects_foreign_project() -> None:
    session = _session(
        scalar_result=None,
    )

    with pytest.raises(
        ValueError,
        match="Project does not belong to the user",
    ):
        await DecisionService().create_from_candidate(
            session,
            user_id=uuid4(),
            candidate=_candidate(uuid4()),
            project_id=uuid4(),
        )

    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_decision_rejects_foreign_source_chunk() -> None:
    chunk_id = uuid4()

    session = _session(
        source_ids=[],
    )

    with pytest.raises(
        ValueError,
        match="One or more source chunks do not belong to the user",
    ):
        await DecisionService().create_from_candidate(
            session,
            user_id=uuid4(),
            candidate=_candidate(chunk_id),
        )

    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_decision_rejects_missing_sources() -> None:
    session = _session()

    with pytest.raises(
        ValueError,
        match="Decision must contain at least one source chunk",
    ):
        await DecisionService._validate_source_chunks(
            session,
            user_id=uuid4(),
            chunk_ids=[],
        )