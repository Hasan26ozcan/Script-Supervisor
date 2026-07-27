from pathlib import Path

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
            store.add(PreferencePair(brief=f"brief-{i}", candidate_a="a", candidate_b="b", winner="a"))

        all_prefs = store.all()
        assert len(all_prefs) == 5
        assert [p.brief for p in all_prefs] == [f"brief-{i}" for i in range(5)]


def test_migrate_from_jsonl(tmp_path):
    jsonl_path = tmp_path / "prefs.jsonl"
    jsonl_path.write_text(
        "{\"brief\": \"b\", \"candidate_a\": \"a1\", \"candidate_b\": \"a2\", \"winner\": \"a\"}\n",
        encoding="utf-8",
    )

    database_url = f"sqlite:///{tmp_path / 'test_migrate.db'}"
    with PreferenceStore(database_url=database_url) as store:
        assert store.migrate_from_jsonl(jsonl_path) == 1
        assert len(store.all()) == 1
