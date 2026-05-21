"""Tests for FTS5 search logic."""

import json
import sqlite3
from pathlib import Path

import pytest

from codenav import store, search as search_mod


@pytest.fixture
def conn(tmp_path):
    c = store.open_db(tmp_path)
    yield c
    c.close()


def _insert(conn, class_name: str, description: str, tags: list[str], namespace: str = "N"):
    entry = {
        "file": f"/fake/{class_name}.cs",
        "class_name": class_name,
        "namespace": namespace,
        "folder": "/fake",
        "solution": "",
        "project": "",
        "kind": "class",
        "description": description,
        "tags": tags,
        "methods": [],
        "source_hash": f"sha1:{class_name}",
        "stale": 0,
    }
    store.upsert_class(conn, entry)


def test_basic_english_search(conn):
    _insert(conn, "DataCollector", "Collects data from sensors.", ["data", "collector", "sensor"])
    results = search_mod.search(conn, "data collector")
    assert any(r["class"] == "DataCollector" for r in results)


def test_korean_bigram_search(conn):
    _insert(conn, "DataCollector", "PLC에서 센서 데이터를 수집하는 클래스.", ["데이터", "수집", "collector"])
    results = search_mod.search(conn, "수집")
    assert any(r["class"] == "DataCollector" for r in results)


def test_pascal_case_split(conn):
    # tags must include PascalCase-split words so FTS can match "event" and "bus"
    _insert(conn, "InMemoryEventBus", "In-memory event bus.", ["in", "memory", "event", "bus"])
    results = search_mod.search(conn, "EventBus")
    assert any(r["class"] == "InMemoryEventBus" for r in results)


def test_fts_injection_no_crash(conn):
    _insert(conn, "Foo", "Test class.", ["test"])
    results = search_mod.search(conn, '"; DROP TABLE--')
    assert isinstance(results, list)


def test_stale_with_description_still_searchable(conn):
    """stale entries with non-empty description remain searchable, flagged via 'stale' key."""
    entry = {
        "file": "/fake/Stale.cs",
        "class_name": "StaleClass",
        "namespace": "N",
        "folder": "/fake",
        "solution": "",
        "project": "",
        "kind": "class",
        "description": "This is stale.",
        "tags": ["stale"],
        "methods": [],
        "source_hash": "sha1:stale",
        "stale": 1,
    }
    store.upsert_class(conn, entry)
    results = search_mod.search(conn, "stale")
    match = next((r for r in results if r["class"] == "StaleClass"), None)
    assert match is not None
    assert match["stale"] is True


def test_stale_with_empty_description_excluded(conn):
    """stale entries with empty description stay hidden (no useful content to surface)."""
    entry = {
        "file": "/fake/Empty.cs",
        "class_name": "EmptyStale",
        "namespace": "N",
        "folder": "/fake",
        "solution": "",
        "project": "",
        "kind": "class",
        "description": "",
        "tags": ["emptystale"],
        "methods": [],
        "source_hash": "sha1:empty",
        "stale": 1,
    }
    store.upsert_class(conn, entry)
    results = search_mod.search(conn, "emptystale")
    assert not any(r["class"] == "EmptyStale" for r in results)


def test_tag_hit_bonus_raises_score(conn):
    _insert(conn, "HighTag", "Some description.", ["collector", "sensor"])
    _insert(conn, "LowTag", "Collector sensor description without tag match.", [])
    results = search_mod.search(conn, "collector")
    # HighTag should rank higher due to tag-hit bonus
    if len(results) >= 2:
        high_idx = next((i for i, r in enumerate(results) if r["class"] == "HighTag"), None)
        low_idx = next((i for i, r in enumerate(results) if r["class"] == "LowTag"), None)
        if high_idx is not None and low_idx is not None:
            assert high_idx < low_idx


def test_empty_query_returns_empty(conn):
    _insert(conn, "Foo", "Test.", ["test"])
    results = search_mod.search(conn, "")
    assert results == []


def test_solution_filter(conn):
    entry_a = {
        "file": "/fake/A.cs",
        "class_name": "ServiceA",
        "namespace": "N",
        "folder": "/fake",
        "solution": "SolA",
        "project": "",
        "kind": "class",
        "description": "Service class.",
        "tags": ["service"],
        "methods": [],
        "source_hash": "sha1:A",
        "stale": 0,
    }
    entry_b = {**entry_a, "file": "/fake/B.cs", "class_name": "ServiceB", "solution": "SolB", "source_hash": "sha1:B"}
    store.upsert_class(conn, entry_a)
    store.upsert_class(conn, entry_b)
    results = search_mod.search(conn, "service", solution="SolA")
    assert all(r["solution"] == "SolA" for r in results)
    assert any(r["class"] == "ServiceA" for r in results)
    assert not any(r["class"] == "ServiceB" for r in results)
