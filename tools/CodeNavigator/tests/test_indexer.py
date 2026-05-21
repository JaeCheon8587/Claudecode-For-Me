"""Tests for AI indexer logic."""

import os

import pytest

from codenav import indexer


def test_mock_fail_returns_none(monkeypatch):
    monkeypatch.setenv(indexer._MOCK_ENV, "fail")
    result = indexer._call_claude("Class: Foo\nNamespace: N")
    assert result is None


def test_no_claude_exe_returns_none(monkeypatch):
    monkeypatch.setenv(indexer._MOCK_ENV, "")
    monkeypatch.setattr(indexer, "_claude_exe", lambda: None)
    result = indexer._call_claude("Class: Foo")
    assert result is None


def test_enrich_entries_mock_fail(monkeypatch):
    monkeypatch.setenv(indexer._MOCK_ENV, "fail")
    entries = [
        {"class_name": "Foo", "namespace": "N", "methods": [], "file": "foo.cs"},
        {"class_name": "Bar", "namespace": "N", "methods": [], "file": "bar.cs"},
    ]
    result, call_count = indexer.enrich_entries(entries)
    assert call_count == 2
    assert all(e.get("_ai_failed") for e in result)
    assert all("description" not in e or e["description"] == "" for e in result)


def test_enrich_entries_skips_existing_description(monkeypatch):
    monkeypatch.setenv(indexer._MOCK_ENV, "fail")
    entries = [
        {"class_name": "Foo", "namespace": "N", "methods": [], "file": "foo.cs",
         "description": "Already described."},
    ]
    result, call_count = indexer.enrich_entries(entries)
    assert call_count == 0
    assert result[0]["description"] == "Already described."


def test_tags_type_validation(monkeypatch):
    """If AI returns tags as a string instead of list, it should be wrapped in a list."""
    def fake_call(class_info, retries=1):
        return {"description": "A class.", "tags": "tag1, tag2"}

    monkeypatch.setattr(indexer, "_call_claude", fake_call)
    entries = [{"class_name": "Foo", "namespace": "N", "methods": [], "file": "foo.cs"}]
    result, _ = indexer.enrich_entries(entries)
    assert isinstance(result[0]["tags"], list)
