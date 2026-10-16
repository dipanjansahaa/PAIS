"""Seed realistic development data for the PAIS Daily Intelligence UI."""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.database.models.commitment import Commitment
from app.database.models.decision import Decision
from app.database.models.person import Person
from app.database.models.project import Project
from app.database.models.risk import Risk
from app.database.models.task import Task
from app.database.models.user import User
from app.database.session import AsyncSessionFactory


DEV_AUTH_SUBJECT = "dev-user-local-001"
TIMEZONE_NAME = "Asia/Kolkata"


def local_to_database_utc(
    value: datetime,
    timezone_name: str,
) -> datetime:
    """Convert a timezone-aware local datetime to naive UTC for the database."""

    zone = ZoneInfo(timezone_name)

    local_value = value.replace(tzinfo=zone)

    return local_value.astimezone(timezone.utc).replace(tzinfo=None)


async def get_or_create_project(
    session,
    *,
    user: User,
) -> Project:
    result = await session.scalar(
        select(Project).where(
            Project.user_id == user.id,
            Project.name == "PAIS V1 Frontend",
        )
    )

    if result is not None:
        return result

    project = Project(
        user_id=user.id,
        name="PAIS V1 Frontend",
    )

    session.add(project)
    await session.flush()

    return project


async def get_or_create_commitment(
    session,
    *,
    user: User,
    project: Project,
    deadline_at: datetime,
) -> Commitment:
    description = (
        "Complete the PAIS V1 frontend milestone before starting D7."
    )

    result = await session.scalar(
        select(Commitment).where(
            Commitment.user_id == user.id,
            Commitment.description == description,
        )
    )

    if result is not None:
        result.project_id = project.id
        result.owner = user.display_name
        result.deadline_at = deadline_at
        result.status = "open"
        return result

    commitment = Commitment(
        user_id=user.id,
        project_id=project.id,
        description=description,
        owner=user.display_name,
        deadline_at=deadline_at,
        status="open",
    )

    session.add(commitment)
    await session.flush()

    return commitment


async def get_or_create_task(
    session,
    *,
    user: User,
    project: Project,
    commitment: Commitment,
    description: str,
    priority: str,
    due_at: datetime,
) -> Task:
    result = await session.scalar(
        select(Task).where(
            Task.user_id == user.id,
            Task.description == description,
        )
    )

    if result is not None:
        result.project_id = project.id
        result.commitment_id = commitment.id
        result.owner = user.display_name
        result.priority = priority
        result.due_at = due_at
        result.status = "open"
        return result

    task = Task(
        user_id=user.id,
        project_id=project.id,
        commitment_id=commitment.id,
        description=description,
        owner=user.display_name,
        due_at=due_at,
        priority=priority,
        status="open",
    )

    session.add(task)
    await session.flush()

    return task


async def get_or_create_decision(
    session,
    *,
    user: User,
    project: Project,
    decision_date,
) -> Decision:
    title = "Use React and TypeScript for the PAIS frontend"

    result = await session.scalar(
        select(Decision).where(
            Decision.user_id == user.id,
            Decision.title == title,
        )
    )

    if result is not None:
        result.project_id = project.id
        result.description = (
            "Keep the frontend aligned with the existing PAIS "
            "production-oriented architecture."
        )
        result.decision_date = decision_date
        result.status = "active"
        return result

    decision = Decision(
        user_id=user.id,
        project_id=project.id,
        title=title,
        description=(
            "Keep the frontend aligned with the existing PAIS "
            "production-oriented architecture."
        ),
        decision_date=decision_date,
        status="active",
    )

    session.add(decision)
    await session.flush()

    return decision


async def get_or_create_person(
    session,
    *,
    user: User,
) -> Person:
    name = "PAIS Project Stakeholder"

    result = await session.scalar(
        select(Person).where(
            Person.user_id == user.id,
            Person.name == name,
        )
    )

    if result is not None:
        return result

    person = Person(
        user_id=user.id,
        name=name,
    )

    session.add(person)
    await session.flush()

    return person


async def get_or_create_risk(
    session,
    *,
    user: User,
) -> Risk:
    title = "Frontend and backend contract drift"

    result = await session.scalar(
        select(Risk).where(
            Risk.user_id == user.id,
            Risk.title == title,
        )
    )

    if result is not None:
        return result

    risk = Risk(
        user_id=user.id,
        title=title,
    )

    session.add(risk)
    await session.flush()

    return risk


async def seed() -> None:
    zone = ZoneInfo(TIMEZONE_NAME)

    local_now = datetime.now(zone)
    local_today = local_now.date()
    local_tomorrow = local_today + timedelta(days=1)

    now_utc = local_now.astimezone(timezone.utc).replace(tzinfo=None)

    today_morning = local_to_database_utc(
        datetime.combine(local_today, time(10, 0)),
        TIMEZONE_NAME,
    )

    today_afternoon = local_to_database_utc(
        datetime.combine(local_today, time(15, 0)),
        TIMEZONE_NAME,
    )

    today_evening = local_to_database_utc(
        datetime.combine(local_today, time(18, 0)),
        TIMEZONE_NAME,
    )

    tomorrow_morning = local_to_database_utc(
        datetime.combine(local_tomorrow, time(11, 0)),
        TIMEZONE_NAME,
    )

    async with AsyncSessionFactory() as session:
        user = await session.scalar(
            select(User).where(
                User.auth_subject == DEV_AUTH_SUBJECT,
            )
        )

        if user is None:
            raise RuntimeError(
                "Development user was not found. "
                f"Expected User.auth_subject={DEV_AUTH_SUBJECT!r}."
            )

        project = await get_or_create_project(
            session,
            user=user,
        )

        commitment = await get_or_create_commitment(
            session,
            user=user,
            project=project,
            deadline_at=today_evening,
        )

        await get_or_create_task(
            session,
            user=user,
            project=project,
            commitment=commitment,
            description="Finish Daily Intelligence frontend validation",
            priority="high",
            due_at=today_morning,
        )

        await get_or_create_task(
            session,
            user=user,
            project=project,
            commitment=commitment,
            description="Prepare the PAIS V1 D7 implementation plan",
            priority="medium",
            due_at=today_afternoon,
        )

        await get_or_create_task(
            session,
            user=user,
            project=project,
            commitment=commitment,
            description="Review PAIS frontend responsive behavior",
            priority="normal",
            due_at=tomorrow_morning,
        )

        await get_or_create_decision(
            session,
            user=user,
            project=project,
            decision_date=local_today,
        )

        await get_or_create_person(
            session,
            user=user,
        )

        await get_or_create_risk(
            session,
            user=user,
        )

        # Make all seeded entities appear as recent changes for today's
        # Daily Intelligence window.
        project.updated_at = now_utc
        commitment.updated_at = now_utc

        for task in (
            await session.scalars(
                select(Task).where(
                    Task.user_id == user.id,
                    Task.project_id == project.id,
                )
            )
        ).all():
            task.updated_at = now_utc

        decision = await session.scalar(
            select(Decision).where(
                Decision.user_id == user.id,
                Decision.title
                == "Use React and TypeScript for the PAIS frontend",
            )
        )
        if decision is not None:
            decision.updated_at = now_utc

        person = await session.scalar(
            select(Person).where(
                Person.user_id == user.id,
                Person.name == "PAIS Project Stakeholder",
            )
        )
        if person is not None:
            person.updated_at = now_utc

        risk = await session.scalar(
            select(Risk).where(
                Risk.user_id == user.id,
                Risk.title == "Frontend and backend contract drift",
            )
        )
        if risk is not None:
            risk.updated_at = now_utc

        await session.commit()

        print("Daily demo seed completed.")
        print(f"User:       {user.display_name} ({user.id})")
        print(f"Project:    {project.name}")
        print(f"Local day:  {local_today}")
        print(f"Timezone:   {TIMEZONE_NAME}")
        print("Seeded:")
        print("  - 3 open tasks")
        print("  - 1 open commitment")
        print("  - 1 recent decision")
        print("  - 1 project")
        print("  - 1 person")
        print("  - 1 risk")


if __name__ == "__main__":
    asyncio.run(seed())