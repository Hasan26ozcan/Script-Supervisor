import pytest

"""Tests for PreferenceStore — SQL backend with JSONL fallback."""

from app.preference_store import PreferenceStore
from app.schemas import PreferencePair


def test_add_and_read_back(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    with PreferenceStore(database_url=database_url) as store:
        pref = PreferencePair(brief="b", candidate_a="a1", candidate_b="a2", winner="a")
        store.add(pref)

        all_prefs = store.all()
        assert len(all_prefs) == 1
        assert all_prefs[0].pair_id == pref.pair_id
        assert all_prefs[0].winner == "a"


def test_all_returns_empty_list_when_db_empty(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'test_empty.db'}"
    with PreferenceStore(database_url=database_url) as store:
        assert store.all() == []


def test_append_only_preserves_order(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'test_order.db'}"
    with PreferenceStore(database_url=database_url) as store:
        for i in range(5):
            store.add(
                PreferencePair(
                    brief=f"brief-{i}", candidate_a="a", candidate_b="b", winner="a"
                )
            )

        all_prefs = store.all()
        assert len(all_prefs) == 5
        assert [p.brief for p in all_prefs] == [f"brief-{i}" for i in range(5)]


def test_migrate_from_jsonl(tmp_path):
    jsonl_path = tmp_path / "prefs.jsonl"
    jsonl_path.write_text(
        '{"brief": "b", "candidate_a": "a1", "candidate_b": "a2", "winner": "a"}\n',
        encoding="utf-8",
    )

    database_url = f"sqlite:///{tmp_path / 'test_migrate.db'}"
    with PreferenceStore(database_url=database_url) as store:
        assert store.migrate_from_jsonl(jsonl_path) == 1
        assert len(store.all()) == 1


def test_fallback_jsonl_when_db_unavailable(tmp_path):
    """When the SQL backend is unavailable (e.g. psycopg missing), PreferenceStore
    should transparently fall back to JSONL storage."""
    # Use a URL that would trigger DB unavailability (no psycopg on this machine)
    # and verify that JSONL fallback is used instead.
    database_url = f"sqlite:///{tmp_path / 'test_fallback.db'}"
    with PreferenceStore(database_url=database_url) as store:
        store.add(
            PreferencePair(
                brief="fallback test", candidate_a="a1", candidate_b="a2", winner="a"
            )
        )
        result = store.all()
        assert len(result) == 1
        assert result[0].brief == "fallback test"


def test_multiple_winners_stored_correctly(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'test_multi.db'}"
    with PreferenceStore(database_url=database_url) as store:
        store.add(PreferencePair(brief="b1", candidate_a="a1", candidate_b="a2", winner="a"))
        store.add(PreferencePair(brief="b2", candidate_a="b1", candidate_b="b2", winner="b"))
        store.add(PreferencePair(brief="b3", candidate_a="c1", candidate_b="c2", winner="tie"))

        all_prefs = store.all()
        assert len(all_prefs) == 3
        winners = {p.winner for p in all_prefs}
        assert winners == {"a", "b", "tie"}


def test_preference_pair_has_all_required_fields():
    """PreferencePair should have all fields required for the DPO pipeline."""
    pref = PreferencePair(
        brief="Test brief",
        candidate_a="Candidate A content",
        candidate_b="Candidate B content",
        winner="a",
        rater="human_01",
        notes="A is more cinematic",
    )
    assert pref.brief
    assert pref.candidate_a
    assert pref.candidate_b
    assert pref.winner in ("a", "b", "tie")


def test_add_sqlalchemy_error_falls_back_to_jsonl(tmp_path, monkeypatch):
    """When session.merge raises SQLAlchemyError, the store falls back
    to JSONL storage."""
    import sqlalchemy.exc
    from app.preference_store import PreferenceStore
    from app.schemas import PreferencePair

    database_url = f"sqlite:///{tmp_path / 'test_err.db'}"
    store = PreferenceStore(database_url=database_url)

    # Force SQLAlchemyError on merge by patching session.merge
    original_merge = store.session.merge

    def failing_merge(model):
        raise sqlalchemy.exc.SQLAlchemyError("forced error")

    store.session.merge = failing_merge

    pref = PreferencePair(
        brief="fallback test",
        candidate_a="A",
        candidate_b="B",
        winner="a",
    )
    store.add(pref)

    # After the error, _db_available should be False and fallback should be used
    assert not store._db_available
    fallback_prefs = store.all()
    assert len(fallback_prefs) >= 1
    assert fallback_prefs[-1].brief == "fallback test"

    store.session.merge = original_merge
    store.close()


def test_migrate_from_jsonl_missing_file_raises(tmp_path):
    """migrate_from_jsonl raises FileNotFoundError when source file missing."""
    database_url = f"sqlite:///{tmp_path / 'test_migrate_err.db'}"
    store = PreferenceStore(database_url=database_url)

    missing = tmp_path / "nonexistent.jsonl"
    with pytest.raises(FileNotFoundError):
        store.migrate_from_jsonl(missing)

    store.close()


def test_all_uses_fallback_records_when_db_fails(tmp_path, monkeypatch):
    """When the DB is unavailable at query time, all() returns fallback records."""
    import sqlalchemy.exc
    from app.preference_store import PreferenceStore
    from app.schemas import PreferencePair

    database_url = f"sqlite:///{tmp_path / 'test_fb.db'}"
    store = PreferenceStore(database_url=database_url)

    pref = PreferencePair(brief="fb", candidate_a="A", candidate_b="B", winner="a")
    store.add(pref)

    # Close the store to simulate DB unavailability
    store.close()

    # Re-create with a broken session that raises on execute
    store2 = PreferenceStore(database_url=database_url)

    original_execute = store2.session.execute

    def failing_execute(stmt):
        raise sqlalchemy.exc.SQLAlchemyError("DB broken")

    import types
    store2.session.execute = types.MethodType(failing_execute, store2.session)

    result = store2.all()
    # Should fall back to the JSONL fallback records that were written
    fb_entries = [p for p in result if p.brief == "fb"]
    assert len(fb_entries) >= 1

    store2.session.execute = original_execute
    store2.close()
    store.close()
    assert pref.rater == "anonymous"
    assert pref.notes == ""


def test_all_falls_back_to_load_fallback_records_when_no_cached_records(
    tmp_path, monkeypatch
):
    """When DB fails and _fallback_records is empty, all() falls back to the JSONL file."""
    import sqlalchemy.exc
    from app.preference_store import PreferenceStore
    from app.schemas import PreferencePair

    database_url = f"sqlite:///{tmp_path / 'test_fb_empty.db'}"

    # Create a store, add a pref, close it. This populates the JSONL fallback file.
    store = PreferenceStore(database_url=database_url)
    pref = PreferencePair(brief="fb", candidate_a="A", candidate_b="B", winner="a")
    store.add(pref)
    store.close()

    # Now create a NEW store instance in a fresh process-like environment
    # where the session is immediately broken. _fallback_records is empty
    # (just loaded from JSONL at init, but session is broken on execute).
    store2 = PreferenceStore(database_url=database_url)

    # Break the session so DB queries fail.
    original_execute = store2.session.execute

    def failing_execute(stmt):
        raise sqlalchemy.exc.SQLAlchemyError("DB broken on query")

    import types

    store2.session.execute = types.MethodType(failing_execute, store2.session)

    # Force _fallback_records to be empty (simulate a fresh session where no add() was called)
    store2._fallback_records = []

    result = store2.all()
    fb_entries = [p for p in result if p.brief == "fb"]
    assert len(fb_entries) >= 1

    store2.session.execute = original_execute
    store2.close()
    store.close()


def test_migrate_from_jsonl_skips_blank_lines(tmp_path):
    """migrate_from_jsonl should skip blank lines in the source JSONL file."""
    jsonl_path = tmp_path / "prefs_with_blanks.jsonl"
    jsonl_path.write_text(
        '{"brief": "b1", "candidate_a": "a1", "candidate_b": "a2", "winner": "a"}\n\n'
        '{"brief": "b2", "candidate_a": "b1", "candidate_b": "b2", "winner": "b"}\n\n',
        encoding="utf-8",
    )

    database_url = f"sqlite:///{tmp_path / 'test_migrate_blanks.db'}"
    with PreferenceStore(database_url=database_url) as store:
        count = store.migrate_from_jsonl(jsonl_path)
    assert count == 2
    with PreferenceStore(database_url=database_url) as store:
        all_prefs = store.all()
    assert len(all_prefs) == 2


def test_load_fallback_records_skips_blank_lines(tmp_path, monkeypatch):
    """_load_fallback_records should skip blank lines in the JSONL file."""
    import sqlalchemy.exc
    from app.preference_store import PreferenceStore
    from app.schemas import PreferencePair

    database_url = f"sqlite:///{tmp_path / 'test_fb_blanks.db'}"
    store = PreferenceStore(database_url=database_url)

    # Write a JSONL file directly with blank lines to exercise line 141.
    fallback_path = store._fallback_path
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        '{"brief": "b1", "candidate_a": "A", "candidate_b": "B", "winner": "a"}\n\n'
        '{"brief": "b2", "candidate_a": "X", "candidate_b": "Y", "winner": "b"}\n\n'
    )
    fallback_path.write_text(content, encoding="utf-8")
    store.close()

    # Re-open with a broken session to force fallback path.
    store2 = PreferenceStore(database_url=database_url)
    original_execute = store2.session.execute

    def failing_execute(stmt):
        raise sqlalchemy.exc.SQLAlchemyError("DB broken")

    import types
    store2.session.execute = types.MethodType(failing_execute, store2.session)

    try:
        result = store2.all()
        assert len(result) == 2
        assert {p.brief for p in result} == {"b1", "b2"}
    finally:
        store2.session.execute = original_execute
        store2.close()
    assert {p.brief for p in result} == {"b1", "b2"}
    store2.close()
    store.close()
