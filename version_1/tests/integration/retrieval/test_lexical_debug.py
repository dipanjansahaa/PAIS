from sqlalchemy import func, select

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.user import User
from tests.evaluation.retrieval_dataset import EVALUATION_DOCUMENTS


async def test_debug_postgres_fts(db_session):
    # Create evaluation data
    for item in EVALUATION_DOCUMENTS:
        user = User(
            email=None,
            display_name=f"Debug User - {item['title']}",
        )

        db_session.add(user)
        await db_session.flush()

        document = Document(
            user_id=user.id,
            title=item["title"],
            source_type="text",
            content_hash=f"debug-{item['title']}",
            raw_text=item["content"],
        )

        db_session.add(document)
        await db_session.flush()

        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=0,
            content=item["content"],
            token_count=None,
            chunk_metadata={"source": "lexical-debug"},
        )

        db_session.add(chunk)

    await db_session.flush()

    query = "How are database connections managed asynchronously?"

    document_text = func.to_tsvector(
        "english",
        DocumentChunk.content,
    )

    query_text = func.plainto_tsquery(
        "english",
        query,
    )

    statement = select(
        DocumentChunk.content,
        document_text.label("tsvector"),
        query_text.label("tsquery"),
        document_text.op("@@")(query_text).label("matches"),
        func.ts_rank_cd(
            document_text,
            query_text,
        ).label("rank"),
    )

    result = await db_session.execute(statement)

    print("\n=== PostgreSQL FTS DEBUG ===")

    for content, tsvector, tsquery, matches, rank in result:
        print("\nCONTENT:")
        print(content)

        print("TSVECTOR:")
        print(tsvector)

        print("TSQUERY:")
        print(tsquery)

        print("MATCHES:")
        print(matches)

        print("RANK:")
        print(rank)

    print("\n=== END DEBUG ===")