import asyncio

from app.database.models.user import User
from app.database.session import AsyncSessionFactory
from sqlalchemy import select

SUBJECT = "dev-user-local-001"

async def main():
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(User).where(User.auth_subject == SUBJECT)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                auth_subject=SUBJECT,
                display_name="Local Development User",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            print(f"Created development user: {user.id}")
        else:
            print(f"Development user already exists: {user.id}")

asyncio.run(main())
