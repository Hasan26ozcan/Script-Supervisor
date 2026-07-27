from pathlib import Path

from app.preference_store import PreferenceStore
from training.generate_fake_preferences import build_fake_preferences, main as generate_fake_main


def test_build_fake_preferences_has_20_entries():
    prefs = build_fake_preferences()
    assert len(prefs) == 20
    assert prefs[0].rater == "rater_01"
    assert prefs[-1].rater == "rater_20"


def test_generated_preferences_file_can_be_loaded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HARNESS_DATABASE_URL", f"sqlite:///{tmp_path / 'fake_prefs.db'}")
    generate_fake_main()
    path = Path("data/preferences.jsonl")
    assert path.exists()

    with PreferenceStore(database_url=f"sqlite:///{tmp_path / 'fake_prefs.db'}") as store:
        prefs = store.all()
        assert len(prefs) == 20
        assert prefs[0].prompt.startswith("Brief:")
        assert prefs[0].candidate_a
        assert prefs[0].candidate_b
