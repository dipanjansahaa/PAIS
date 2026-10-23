import asyncio
from sqlalchemy import select
from app.database.session import AsyncSessionFactory
from app.database.models.user import User

async def main():
    async with AsyncSessionFactory() as session:
        users = (await session.scalars(
            select(User).where(
                User.auth_subject == "dev-user-local-001"
            )
        )).all()

        for user in users:
            print(f"ID: {user.id}")
            print(f"Name: {user.display_name}")
            print(f"Auth subject: {user.auth_subject}")
            print("---")

asyncio.run(main())
