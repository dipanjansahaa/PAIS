from app.evaluation.cases import RetrievalEvaluationCase


def build_retrieval_cases(
    *,
    database_chunk_id,
    deployment_chunk_id,
    meeting_decision_chunk_id,
    authentication_chunk_id,
    error_handling_chunk_id,
    background_processing_chunk_id,
    chunking_chunk_id,
    semantic_search_chunk_id,
    lexical_search_chunk_id,
    hybrid_retrieval_chunk_id,
    retrieval_evaluation_chunk_id,
    readiness_chunk_id,
    connection_pool_chunk_id,
    observability_chunk_id,
    configuration_chunk_id,
):
    return [
        RetrievalEvaluationCase(
            query="PostgreSQL relational database persistent application data",
            relevant_ids={database_chunk_id},
            relevance={database_chunk_id: 3},
        ),

        RetrievalEvaluationCase(
            query="Docker containers production container image deployment",
            relevant_ids={deployment_chunk_id},
            relevance={deployment_chunk_id: 3},
        ),

        RetrievalEvaluationCase(
            query="PostgreSQL full-text search tsvector ts_rank_cd",
            relevant_ids={lexical_search_chunk_id},
            relevance={lexical_search_chunk_id: 3},
        ),

        RetrievalEvaluationCase(
            query="Recall MRR NDCG retrieval quality metrics",
            relevant_ids={retrieval_evaluation_chunk_id},
            relevance={retrieval_evaluation_chunk_id: 3},
        ),

        RetrievalEvaluationCase(
            query="Where does the system keep information that must survive restarts?",
            relevant_ids={database_chunk_id},
            relevance={database_chunk_id: 3},
        ),

        RetrievalEvaluationCase(
            query="What mechanism packages the service so it can be run consistently in production?",
            relevant_ids={deployment_chunk_id},
            relevance={deployment_chunk_id: 3},
        ),

        RetrievalEvaluationCase(
            query="How does the system discover passages that discuss similar ideas rather than identical words?",
            relevant_ids={semantic_search_chunk_id},
            relevance={semantic_search_chunk_id: 3},
        ),

        RetrievalEvaluationCase(
            query="How does the application process work that would be too slow to perform during an API request?",
            relevant_ids={background_processing_chunk_id},
            relevance={background_processing_chunk_id: 3},
        ),

        RetrievalEvaluationCase(
            query="How does the system search?",
            relevant_ids={
                semantic_search_chunk_id,
                lexical_search_chunk_id,
                hybrid_retrieval_chunk_id,
            },
            relevance={
                semantic_search_chunk_id: 3,
                lexical_search_chunk_id: 3,
                hybrid_retrieval_chunk_id: 3,
            },
        ),

        RetrievalEvaluationCase(
            query="How are database operations handled?",
            relevant_ids={
                database_chunk_id,
                connection_pool_chunk_id,
                readiness_chunk_id,
            },
            relevance={
                database_chunk_id: 3,
                connection_pool_chunk_id: 2,
                readiness_chunk_id: 2,
            },
        ),

        RetrievalEvaluationCase(
            query="How does the application check that services are working?",
            relevant_ids={
                readiness_chunk_id,
                observability_chunk_id,
            },
            relevance={
                readiness_chunk_id: 3,
                observability_chunk_id: 2,
            },
        ),

        RetrievalEvaluationCase(
            query="What search approach combines semantic similarity with PostgreSQL keyword matching?",
            relevant_ids={hybrid_retrieval_chunk_id},
            relevance={hybrid_retrieval_chunk_id: 3},
        ),

        RetrievalEvaluationCase(
            query="How are API failures reported with enough information to trace a request?",
            relevant_ids={
                error_handling_chunk_id,
                observability_chunk_id,
            },
            relevance={
                error_handling_chunk_id: 3,
                observability_chunk_id: 2,
            },
        ),

        RetrievalEvaluationCase(
            query="How are large documents broken into pieces before semantic indexing?",
            relevant_ids={
                chunking_chunk_id,
                semantic_search_chunk_id,
            },
            relevance={
                chunking_chunk_id: 3,
                semantic_search_chunk_id: 2,
            },
        ),

        RetrievalEvaluationCase(
            query="How does the system protect API endpoints using authenticated requests?",
            relevant_ids={authentication_chunk_id},
            relevance={authentication_chunk_id: 3},
        ),
    ]