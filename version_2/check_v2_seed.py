import asyncio

from app.database.models.commitment import Commitment
from app.database.models.decision import Decision
from app.database.models.person import Person
from app.database.models.project import Project
from app.database.models.risk import Risk
from app.database.models.task import Task
from app.database.models.user import User
from app.database.session import AsyncSessionFactory
from sqlalchemy import func, select


async def main():
    async with AsyncSessionFactory() as session:
        user = await session.scalar(
            select(User).where(
                User.auth_subject == "dev-user-local-001"
            )
        )

        if user is None:
            print("V2_USER_NOT_FOUND")
            return

        print(f"V2_USER_ID: {user.id}")
        print(f"V2_USER_NAME: {user.display_name}")

        for model in (Project, Task, Commitment, Decision, Person, Risk):
            count = await session.scalar(
                select(func.count()).select_from(model).where(
                    model.user_id == user.id
                )
            )
            print(f"{model.__name__}: {count}")

asyncio.run(main())
