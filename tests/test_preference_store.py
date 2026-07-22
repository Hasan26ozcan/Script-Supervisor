from app.preference_store import PreferenceStore
from app.schemas import PreferencePair


def test_add_and_read_back(tmp_path):
    store = PreferenceStore(path=tmp_path / "prefs.jsonl")
    pref = PreferencePair(brief="b", candidate_a="a1", candidate_b="a2", winner="a")
    store.add(pref)

    all_prefs = store.all()
    assert len(all_prefs) == 1
    assert all_prefs[0].pair_id == pref.pair_id
    assert all_prefs[0].winner == "a"


def test_all_returns_empty_list_when_file_missing(tmp_path):
    store = PreferenceStore(path=tmp_path / "does_not_exist.jsonl")
    assert store.all() == []


def test_append_only_preserves_order(tmp_path):
    store = PreferenceStore(path=tmp_path / "prefs.jsonl")
    for i in range(5):
        store.add(PreferencePair(brief=f"brief-{i}", candidate_a="a", candidate_b="b", winner="a"))

    all_prefs = store.all()
    assert len(all_prefs) == 5
    assert [p.brief for p in all_prefs] == [f"brief-{i}" for i in range(5)]


def test_skips_blank_lines(tmp_path):
    path = tmp_path / "prefs.jsonl"
    store = PreferenceStore(path=path)
    store.add(PreferencePair(brief="b", candidate_a="a1", candidate_b="a2", winner="tie"))
    # simulate a stray blank line landing in the file (e.g. from a crashed write)
    with path.open("a") as f:
        f.write("\n")
    assert len(store.all()) == 1
