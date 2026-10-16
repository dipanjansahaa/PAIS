from sqlalchemy import inspect

from app.database.base import Base
from app.database.models.project import Project
from app.database.models.user import User


def test_user_table_definition() -> None:
    assert User.__tablename__ == "users"

    columns = inspect(User).columns

    assert columns.id.primary_key
    assert columns.email.unique
    assert not columns.display_name.nullable
    assert not columns.created_at.nullable
    assert not columns.updated_at.nullable


def test_project_table_definition() -> None:
    assert Project.__tablename__ == "projects"

    columns = inspect(Project).columns

    assert columns.id.primary_key
    assert not columns.user_id.nullable
    assert not columns.name.nullable
    assert columns.description.nullable
    assert not columns.status.nullable
    assert not columns.created_at.nullable
    assert not columns.updated_at.nullable


def test_user_project_relationships() -> None:
    user_relationship = inspect(User).relationships.projects
    project_relationship = inspect(Project).relationships.user

    assert user_relationship.back_populates == "user"
    assert project_relationship.back_populates == "projects"
    assert project_relationship.uselist is False


def test_models_registered_with_metadata() -> None:
    assert "users" in Base.metadata.tables
    assert "projects" in Base.metadata.tables