from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.lexical import LexicalRetriever
from app.retrieval.models import RetrievalResult
from app.retrieval.vector import VectorRetriever
from app.retrieval.fusion import RRFFusion
from app.retrieval.models import RetrievalResult


# class HybridRetriever:
#     """Retrieve candidates using both vector and lexical search."""

#     def __init__(
#         self,
#         vector_retriever: VectorRetriever,
#         lexical_retriever: LexicalRetriever,
#     ) -> None:
#         self.vector_retriever = vector_retriever
#         self.lexical_retriever = lexical_retriever

#     async def search(
#         self,
#         session: AsyncSession,
#         query: str,
#         top_k: int = 5,
#         project_id: uuid.UUID | None = None,
#         document_id: uuid.UUID | None = None,
#         source_type: str | None = None,
#     ) -> list[RetrievalResult]:
#         if not query.strip():
#             raise ValueError("Query must not be empty.")

#         if top_k <= 0:
#             raise ValueError("top_k must be greater than zero.")

#         vector_results = await self.vector_retriever.search(
#             session=session,
#             query=query,
#             top_k=top_k,
#             project_id=project_id,
#             document_id=document_id,
#             source_type=source_type,
#         )

#         lexical_results = await self.lexical_retriever.search(
#             session=session,
#             query=query,
#             top_k=top_k,
#             project_id=project_id,
#             document_id=document_id,
#             source_type=source_type,
#         )

#         combined_results: list[RetrievalResult] = []
#         seen_chunk_ids: set[uuid.UUID] = set()

#         for result in vector_results + lexical_results:
#             if result.chunk_id in seen_chunk_ids:
#                 continue

#             seen_chunk_ids.add(result.chunk_id)
#             combined_results.append(result)

#         return combined_results[:top_k]


class HybridRetriever:
    def __init__(
        self,
        vector_retriever,
        lexical_retriever,
        fusion: RRFFusion | None = None,
    ):
        self.vector_retriever = vector_retriever
        self.lexical_retriever = lexical_retriever
        self.fusion = fusion or RRFFusion()

    async def search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 5,
        project_id: UUID | None = None,
        document_id: UUID | None = None,
        source_type: str | None = None,
    ) -> list[RetrievalResult]:
        if not query.strip():
            raise ValueError("Query must not be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        vector_results = await self.vector_retriever.search(
            session=session,
            query=query,
            top_k=top_k,
            project_id=project_id,
            document_id=document_id,
            source_type=source_type,
        )

        lexical_results = await self.lexical_retriever.search(
            session=session,
            query=query,
            top_k=top_k,
            project_id=project_id,
            document_id=document_id,
            source_type=source_type,
        )

        return self.fusion.fuse(
            result_lists=[
                vector_results,
                lexical_results,
            ],
            top_k=top_k,
        )