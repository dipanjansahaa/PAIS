import asyncio

from app.database.models.user import User
from app.database.session import AsyncSessionFactory
from sqlalchemy import select


async def main():
    async with AsyncSessionFactory() as session:
        users = (await session.scalars(select(User))).all()

        for user in users:
            print(f"ID: {user.id}")
            print(f"Name: {user.display_name}")
            print(f"Auth subject: {user.auth_subject}")
            print("---")

asyncio.run(main())
