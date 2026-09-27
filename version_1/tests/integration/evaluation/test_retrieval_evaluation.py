from __future__ import annotations

import pytest

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.user import User
from app.embeddings.factory import get_embedding_provider
from app.evaluation.runner import RetrievalEvaluator
from app.evaluation.runner import (
    RetrievalEvaluationResult,
    RetrievalEvaluator,
)
from app.reranking.service import RerankingService
from app.retrieval.fusion import RRFFusion
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.lexical import LexicalRetriever
from app.retrieval.vector import VectorRetriever
from app.retrieval.reranked import RerankedRetriever
from tests.evaluation.retrieval_cases import build_retrieval_cases
from tests.evaluation.retrieval_dataset import EVALUATION_DOCUMENTS
from app.reranking.providers.local import LocalCrossEncoderReranker

# DIAGNOSTIC_MODE = True
DIAGNOSTIC_MODE = False

@pytest.fixture
def evaluation_embedding_provider():
    return get_embedding_provider()


@pytest.fixture
def evaluation_vector_retriever(evaluation_embedding_provider):
    return VectorRetriever(
        embedding_provider=evaluation_embedding_provider,
    )


@pytest.fixture
def evaluation_lexical_retriever():
    return LexicalRetriever()


@pytest.fixture
def evaluation_hybrid_retriever(evaluation_embedding_provider):
    return HybridRetriever(
        vector_retriever=VectorRetriever(
            embedding_provider=evaluation_embedding_provider,
        ),
        lexical_retriever=LexicalRetriever(),
        fusion=RRFFusion(k=60),
    )


@pytest.fixture
def evaluation_reranking_service():
    return RerankingService(
        reranker=LocalCrossEncoderReranker()
    )


@pytest.fixture
def evaluation_reranked_retriever(
    evaluation_hybrid_retriever,
    evaluation_reranking_service,
):
    return RerankedRetriever(
        base_retriever=evaluation_hybrid_retriever,
        reranking_service=evaluation_reranking_service,
        candidate_k=20,
    )


async def create_evaluation_documents(
    db_session,
    embedding_provider,
):
    chunks_by_case = {}

    for item in EVALUATION_DOCUMENTS:
        document_identifier = item["title"].lower().replace(" ", "-")

        user = User(
            email=f"{document_identifier}@evaluation.local",
            display_name=f"Evaluation User {item['title']}",
        )
        db_session.add(user)
        await db_session.flush()

        document = Document(
            user_id=user.id,
            title=item["title"],
            source_type="evaluation",
            file_name=f"{document_identifier}.txt",
            mime_type="text/plain",
            content_hash=f"evaluation-{document_identifier}",
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
            token_count=len(item["content"].split()),
            chunk_metadata={
                "evaluation_title": item["title"],
                "relevant_case": item["relevant_case"],
            },
            embedding=embeddings[0],
        )

        db_session.add(chunk)
        await db_session.flush()

        if item["relevant_case"] is not None:
            chunks_by_case[item["relevant_case"]] = chunk

    return chunks_by_case


def print_evaluation_results(
    results: dict[str, RetrievalEvaluationResult],
    *,
    k: int,
) -> None:
    print()
    print(f"Evaluation Cases = 15")
    print(f"K = {k}")
    print()
    print(
        f"{'Retriever':<30}"
        f"{'Recall@5':>12}"
        f"{'MRR':>12}"
        f"{'NDCG@5':>12}"
    )
    print("-" * 66)

    for name, result in results.items():
        print(
            f"{name:<30}"
            f"{result.recall_at_k:>12.4f}"
            f"{result.mrr:>12.4f}"
            f"{result.ndcg_at_k:>12.4f}"
        )


@pytest.mark.asyncio
async def test_retrieval_benchmark_comparison(
    db_session,
    evaluation_embedding_provider,
    evaluation_vector_retriever,
    evaluation_lexical_retriever,
    evaluation_hybrid_retriever,
    evaluation_reranked_retriever,
):
    chunks_by_case = await create_evaluation_documents(
        db_session,
        evaluation_embedding_provider,
    )

    cases = build_retrieval_cases(
        database_chunk_id=chunks_by_case["database"].id,
        deployment_chunk_id=chunks_by_case["deployment"].id,
        meeting_decision_chunk_id=chunks_by_case["meeting_decision"].id,
        authentication_chunk_id=chunks_by_case["authentication"].id,
        error_handling_chunk_id=chunks_by_case["error_handling"].id,
        background_processing_chunk_id=chunks_by_case[
            "background_processing"
        ].id,
        chunking_chunk_id=chunks_by_case["chunking"].id,
        semantic_search_chunk_id=chunks_by_case["semantic_search"].id,
        lexical_search_chunk_id=chunks_by_case["lexical_search"].id,
        hybrid_retrieval_chunk_id=chunks_by_case[
            "hybrid_retrieval"
        ].id,
        retrieval_evaluation_chunk_id=chunks_by_case[
            "retrieval_evaluation"
        ].id,
        readiness_chunk_id=chunks_by_case["readiness"].id,
        connection_pool_chunk_id=chunks_by_case[
            "connection_pool"
        ].id,
        observability_chunk_id=chunks_by_case["observability"].id,
        configuration_chunk_id=chunks_by_case["configuration"].id,
    )

    k = 5

    vector_evaluator = RetrievalEvaluator(
        retriever=evaluation_vector_retriever,
    )

    lexical_evaluator = RetrievalEvaluator(
        retriever=evaluation_lexical_retriever,
    )

    hybrid_evaluator = RetrievalEvaluator(
        retriever=evaluation_hybrid_retriever,
    )

    reranked_evaluator = RetrievalEvaluator(
        retriever=evaluation_reranked_retriever,
    )

    vector_result = await vector_evaluator.evaluate(
        session=db_session,
        cases=cases,
        k=k,
    )

    lexical_result = await lexical_evaluator.evaluate(
        session=db_session,
        cases=cases,
        k=k,
    )

    hybrid_result = await hybrid_evaluator.evaluate(
        session=db_session,
        cases=cases,
        k=k,
    )

    reranked_result = await reranked_evaluator.evaluate(
        session=db_session,
        cases=cases,
        k=k,
    )

    if DIAGNOSTIC_MODE:
        for case_number, case in enumerate(cases, start=1):
            hybrid_candidates = await evaluation_hybrid_retriever.search(
                session=db_session,
                query=case.query,
                top_k=20,
            )

            reranked_results = await evaluation_reranked_retriever.search(
                session=db_session,
                query=case.query,
                top_k=k,
            )

            print()
            print("=" * 100)
            print(f"CASE {case_number}")
            print("=" * 100)
            print(f"Query: {case.query}")

            print()
            print("Relevant Documents:")

            for relevant_chunk_id, relevance_score in case.relevance.items():
                matching_result = next(
                    (
                        result
                        for result in hybrid_candidates
                        if result.chunk_id == relevant_chunk_id
                    ),
                    None,
                )

                if matching_result is not None:
                    print(
                        f"  - {matching_result.content}"
                        f" [relevance={relevance_score}]"
                    )
                else:
                    print(
                        f"  - chunk_id={relevant_chunk_id}"
                        f" [relevance={relevance_score}]"
                    )

            print()
            print("Top 10 Hybrid + RRF Candidates:")
            print("-" * 100)

            for rank, result in enumerate(hybrid_candidates[:10], start=1):
                relevant_marker = (
                    " <-- RELEVANT"
                    if result.chunk_id in case.relevance
                    else ""
                )

                print(
                    f"{rank:>2}. "
                    f"score={result.similarity:.6f} | "
                    f"{result.content}"
                    f"{relevant_marker}"
                )

            print()
            print("Top 5 Cross-Encoder Results:")
            print("-" * 100)

            for rank, result in enumerate(reranked_results, start=1):
                relevant_marker = (
                    " <-- RELEVANT"
                    if result.chunk_id in case.relevance
                    else ""
                )

                print(
                    f"{rank:>2}. "
                    f"score={result.similarity:.6f} | "
                    f"{result.content}"
                    f"{relevant_marker}"
                )

    results = {
        "Vector": vector_result,
        "Lexical": lexical_result,
        "Hybrid + RRF": hybrid_result,
        "Hybrid + RRF + Cross-Encoder": reranked_result,
    }

    print_evaluation_results(
        results,
        k=k,
    )

    assert len(results) == 4

    for result in results.values():
        assert 0.0 <= result.recall_at_k <= 1.0
        assert 0.0 <= result.mrr <= 1.0
        assert 0.0 <= result.ndcg_at_k <= 1.0