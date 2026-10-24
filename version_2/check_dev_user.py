import asyncio

from app.database.models.user import User
from app.database.session import AsyncSessionFactory
from sqlalchemy import select


async def main():
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(User.id, User.display_name, User.auth_subject)
            .where(User.auth_subject == "dev-user-local-001")
        )
        rows = result.all()
        print(rows if rows else "NO_MATCHING_USER")

asyncio.run(main())
