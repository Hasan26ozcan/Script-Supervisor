"""Unit tests for Mem0Store internals (app/mem0.py)."""

import pytest

from app.mem0 import Mem0Store
from app.schemas import ComparisonPair, MemoryEntry


@pytest.fixture
def store(tmp_path):
    p = tmp_path / "mem0.jsonl"
    return Mem0Store(path=p)


class TestAddEntry:
    def test_add_creates_entry_with_defaults(self, store):
        pair = ComparisonPair(
            pair_id="p1",
            source="test",
            brief="A scene.",
            candidate_a="Shot A",
            candidate_b="Shot B",
        )
        entry = store.add_entry(pair, "a")

        assert entry.source_pair_id == "p1"
        assert entry.source == "test"
        assert entry.brief == "A scene."
        assert entry.expected_winner == "a"
        assert entry.status == "active"
        assert entry.effectiveness_score == 1.0

    def test_add_entry_is_persisted_to_disk(self, store):
        pair = ComparisonPair(
            pair_id="p2", source="api", brief="Brief.", candidate_a="A", candidate_b="B"
        )
        store.add_entry(pair, "b")

        assert store.path.exists()
        lines = store.path.read_text().strip().splitlines()
        assert len(lines) == 1
        import json

        data = json.loads(lines[0])
        assert data["source_pair_id"] == "p2"

    def test_add_entry_assigns_unique_ids(self, store):
        pair = ComparisonPair(
            pair_id="p3", source="test", brief="Brief.", candidate_a="A", candidate_b="B"
        )
        e1 = store.add_entry(pair, "a")
        e2 = store.add_entry(pair, "b")
        assert e1.entry_id != e2.entry_id


class TestFindStaleEntries:
    def test_find_stale_empty_store(self, store):
        assert store.find_stale_entries() == []

    def test_find_stale_returns_only_stale(self, store):
        pair = ComparisonPair(
            pair_id="p4", source="test", brief="Brief.", candidate_a="A", candidate_b="B"
        )
        store.add_entry(pair, "a")

        # Mark the entry as stale directly
        entry_id = list(store.entries.keys())[0]
        store.mark_stale(entry_id)

        stale = store.find_stale_entries()
        assert len(stale) == 1
        assert stale[0].status == "stale"

    def test_find_stale_filters_active(self, store):
        pair = ComparisonPair(
            pair_id="p5", source="test", brief="Brief.", candidate_a="A", candidate_b="B"
        )
        store.add_entry(pair, "a")
        stale = store.find_stale_entries()
        assert stale == []


class TestMarkStale:
    def test_mark_stale_changes_status(self, store):
        pair = ComparisonPair(
            pair_id="p6", source="test", brief="Brief.", candidate_a="A", candidate_b="B"
        )
        store.add_entry(pair, "a")
        entry_id = list(store.entries.keys())[0]

        assert store.entries[entry_id].status == "active"
        store.mark_stale(entry_id, replacement="new_pair_id")
        assert store.entries[entry_id].status == "stale"
        assert store.entries[entry_id].replacement_suggestion == "new_pair_id"

    def test_mark_stale_without_replacement(self, store):
        pair = ComparisonPair(
            pair_id="p7", source="test", brief="Brief.", candidate_a="A", candidate_b="B"
        )
        store.add_entry(pair, "a")
        entry_id = list(store.entries.keys())[0]
        store.mark_stale(entry_id)
        assert store.entries[entry_id].replacement_suggestion is None


class TestReplaceEntry:
    def test_replace_entry_marks_old_as_replaced(self, store):
        pair = ComparisonPair(
            pair_id="p8", source="test", brief="Brief.", candidate_a="A", candidate_b="B"
        )
        store.add_entry(pair, "a")
        old_id = list(store.entries.keys())[0]

        new_entry = MemoryEntry(
            source_pair_id="p8",
            source="test",
            brief="Brief.",
            prompt="Brief: Brief.\n\nShot list:\n",
            candidate_a="A-new",
            candidate_b="B-new",
            expected_winner="b",
        )
        store.replace_entry(old_id, new_entry)

        assert store.entries[old_id].status == "replaced"
        assert store.entries[new_entry.entry_id].status == "active"

    def test_replace_entry_preserves_new_entry(self, store):
        pair = ComparisonPair(
            pair_id="p9", source="test", brief="Brief.", candidate_a="A", candidate_b="B"
        )
        store.add_entry(pair, "a")
        old_id = list(store.entries.keys())[0]

        new_entry = MemoryEntry(
            source_pair_id="p9",
            source="test",
            brief="Brief.",
            prompt="Brief: Brief.\n\nShot list:\n",
            candidate_a="A-updated",
            candidate_b="B-updated",
            expected_winner="a",
        )
        store.replace_entry(old_id, new_entry)

        assert store.entries[new_entry.entry_id].candidate_a == "A-updated"


class TestLoadEntries:
    def test_load_existing_file_populates_entries(self, tmp_path):

        p = tmp_path / "mem0.jsonl"
        entry = MemoryEntry(
            source_pair_id="p10",
            source="test",
            brief="Brief.",
            prompt="Brief: Brief.\n\nShot list:\n",
            candidate_a="A",
            candidate_b="B",
            expected_winner="a",
        )
        p.write_text(entry.model_dump_json() + "\n", encoding="utf-8")

        store = Mem0Store(path=p)
        assert len(store.entries) == 1
        assert store.entries[entry.entry_id].brief == "Brief."

    def test_load_missing_file_creates_empty_store(self, tmp_path):
        store = Mem0Store(path=tmp_path / "nonexistent.jsonl")
        assert store.entries == {}

    def test_load_skips_blank_lines(self, tmp_path):

        p = tmp_path / "mem0.jsonl"
        entry = MemoryEntry(
            source_pair_id="p11",
            source="test",
            brief="Brief.",
            prompt="Brief: Brief.\n\nShot list:\n",
            candidate_a="A",
            candidate_b="B",
            expected_winner="a",
        )
        p.write_text(
            entry.model_dump_json() + "\n\n\n",
            encoding="utf-8",
        )

        store = Mem0Store(path=p)
        assert len(store.entries) == 1


class TestSavePersists:
    def test_save_writes_all_entries(self, store):
        pair = ComparisonPair(
            pair_id="p12", source="test", brief="Brief.", candidate_a="A", candidate_b="B"
        )
        store.add_entry(pair, "a")

        # Create a new store from the same file to verify persistence
        store2 = Mem0Store(path=store.path)
        assert len(store2.entries) == 1

    def test_save_overwrites_file(self, store):
        pair = ComparisonPair(
            pair_id="p13", source="test", brief="Brief.", candidate_a="A", candidate_b="B"
        )
        store.add_entry(pair, "a")
        # Adding again will replace (same pair_id would overwrite in dict)
        # Instead, add a second entry and verify both are saved
        pair2 = ComparisonPair(
            pair_id="p14", source="test", brief="Brief 2.", candidate_a="C", candidate_b="D"
        )
        store.add_entry(pair2, "b")

        store2 = Mem0Store(path=store.path)
        assert len(store2.entries) == 2
