from app.database.models.decision import Decision, DecisionSource


def test_decision_table_metadata() -> None:
    assert Decision.__tablename__ == "decisions"

    assert Decision.__table__.c.user_id.nullable is False
    assert Decision.__table__.c.project_id.nullable is True
    assert Decision.__table__.c.title.nullable is False
    assert Decision.__table__.c.description.nullable is False
    assert Decision.__table__.c.decision_date.nullable is True

    assert (
        Decision.__table__.c.status.server_default.arg
        == "active"
    )


def test_decision_source_has_composite_primary_key() -> None:
    primary_key_columns = [
        column.name
        for column in DecisionSource.__table__.primary_key
    ]

    assert primary_key_columns == [
        "decision_id",
        "chunk_id",
    ]


def test_decision_foreign_keys_have_expected_delete_actions() -> None:
    decision_fks = {
        fk.target_fullname: fk.ondelete
        for column in Decision.__table__.columns
        for fk in column.foreign_keys
    }

    source_fks = {
        fk.target_fullname: fk.ondelete
        for column in DecisionSource.__table__.columns
        for fk in column.foreign_keys
    }

    assert decision_fks["users.id"] == "CASCADE"
    assert decision_fks["projects.id"] == "SET NULL"

    assert source_fks["decisions.id"] == "CASCADE"
    assert source_fks["document_chunks.id"] == "CASCADE"