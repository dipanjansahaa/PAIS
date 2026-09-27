from __future__ import annotations

import pytest

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.user import User
from app.embeddings.factory import get_embedding_provider
from app.evaluation.cases import RetrievalEvaluationCase
from app.evaluation.runner import (
    RetrievalEvaluationResult,
    RetrievalEvaluator,
)
from app.retrieval.fusion import RRFFusion
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.lexical import LexicalRetriever
from app.retrieval.vector import VectorRetriever
from tests.evaluation.retrieval_cases import build_retrieval_cases
from tests.evaluation.retrieval_dataset import EVALUATION_DOCUMENTS


@pytest.fixture
def evaluation_embedding_provider():
    return get_embedding_provider()


@pytest.fixture
def evaluation_vector_retriever(
    evaluation_embedding_provider,
) -> VectorRetriever:
    return VectorRetriever(
        embedding_provider=evaluation_embedding_provider,
    )


@pytest.fixture
def evaluation_lexical_retriever() -> LexicalRetriever:
    return LexicalRetriever()


@pytest.fixture
def evaluation_hybrid_retriever(
    evaluation_embedding_provider,
) -> HybridRetriever:
    return HybridRetriever(
        vector_retriever=VectorRetriever(
            embedding_provider=evaluation_embedding_provider,
        ),
        lexical_retriever=LexicalRetriever(),
        fusion=RRFFusion(k=60),
    )


async def create_evaluation_documents(
    db_session,
    embedding_provider,
) -> dict[str, DocumentChunk]:
    chunks_by_case: dict[str, DocumentChunk] = {}

    for item in EVALUATION_DOCUMENTS:
        user = User(
            email=None,
            display_name=f"Evaluation User - {item['title']}",
        )

        db_session.add(user)
        await db_session.flush()

        document = Document(
            user_id=user.id,
            title=item["title"],
            source_type="text",
            content_hash=f"evaluation-{item['title']}",
            raw_text=item["content"],
        )

        db_session.add(document)
        await db_session.flush()

        embeddings = await embedding_provider.embed_documents(
            [item["content"]]
        )

        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=0,
            content=item["content"],
            token_count=None,
            chunk_metadata={"source": "retrieval-evaluation"},
            embedding=embeddings[0],
        )

        db_session.add(chunk)
        await db_session.flush()

        relevant_case = item["relevant_case"]

        if relevant_case is not None:
            chunks_by_case[relevant_case] = chunk

    return chunks_by_case


async def evaluate_retriever(
    retriever,
    db_session,
    cases: list[RetrievalEvaluationCase],
    *,
    k: int = 5,
) -> RetrievalEvaluationResult:
    evaluator = RetrievalEvaluator(
        retriever=retriever,
    )

    return await evaluator.evaluate(
        session=db_session,
        cases=cases,
        k=k,
    )


def print_evaluation_results(
    *,
    vector_result: RetrievalEvaluationResult,
    lexical_result: RetrievalEvaluationResult,
    hybrid_result: RetrievalEvaluationResult,
    k: int,
) -> None:
    print()
    print("Retrieval Evaluation")
    print("====================")
    print()
    print(f"Evaluation Cases = 15")
    print(f"K = {k}")
    print()

    print(
        f"{'Retriever':<20}"
        f"{f'Recall@{k}':>12}"
        f"{'MRR':>12}"
        f"{f'NDCG@{k}':>12}"
    )

    print("-" * 56)

    print(
        f"{'Vector':<20}"
        f"{vector_result.recall_at_k:>12.4f}"
        f"{vector_result.mrr:>12.4f}"
        f"{vector_result.ndcg_at_k:>12.4f}"
    )

    print(
        f"{'Lexical':<20}"
        f"{lexical_result.recall_at_k:>12.4f}"
        f"{lexical_result.mrr:>12.4f}"
        f"{lexical_result.ndcg_at_k:>12.4f}"
    )

    print(
        f"{'Hybrid + RRF':<20}"
        f"{hybrid_result.recall_at_k:>12.4f}"
        f"{hybrid_result.mrr:>12.4f}"
        f"{hybrid_result.ndcg_at_k:>12.4f}"
    )

    print()


def assert_valid_metrics(
    result: RetrievalEvaluationResult,
) -> None:
    assert 0.0 <= result.recall_at_k <= 1.0
    assert 0.0 <= result.mrr <= 1.0
    assert 0.0 <= result.ndcg_at_k <= 1.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retrieval_evaluation(
    db_session,
    evaluation_embedding_provider,
    evaluation_vector_retriever,
    evaluation_lexical_retriever,
    evaluation_hybrid_retriever,
):
    chunks = await create_evaluation_documents(
        db_session,
        evaluation_embedding_provider,
    )

    cases = build_retrieval_cases(
        database_chunk_id=chunks["database"].id,
        deployment_chunk_id=chunks["deployment"].id,
        meeting_decision_chunk_id=chunks["meeting_decision"].id,
        authentication_chunk_id=chunks["authentication"].id,
        error_handling_chunk_id=chunks["error_handling"].id,
        background_processing_chunk_id=chunks["background_processing"].id,
        chunking_chunk_id=chunks["chunking"].id,
        semantic_search_chunk_id=chunks["semantic_search"].id,
        lexical_search_chunk_id=chunks["lexical_search"].id,
        hybrid_retrieval_chunk_id=chunks["hybrid_retrieval"].id,
        retrieval_evaluation_chunk_id=chunks["retrieval_evaluation"].id,
        readiness_chunk_id=chunks["readiness"].id,
        connection_pool_chunk_id=chunks["connection_pool"].id,
        observability_chunk_id=chunks["observability"].id,
        configuration_chunk_id=chunks["configuration"].id,
    )

    assert len(cases) == 15

    k = 5

    vector_result = await evaluate_retriever(
        evaluation_vector_retriever,
        db_session,
        cases,
        k=k,
    )

    lexical_result = await evaluate_retriever(
        evaluation_lexical_retriever,
        db_session,
        cases,
        k=k,
    )

    hybrid_result = await evaluate_retriever(
        evaluation_hybrid_retriever,
        db_session,
        cases,
        k=k,
    )

    print_evaluation_results(
        vector_result=vector_result,
        lexical_result=lexical_result,
        hybrid_result=hybrid_result,
        k=k,
    )

    assert_valid_metrics(vector_result)
    assert_valid_metrics(lexical_result)
    assert_valid_metrics(hybrid_result)