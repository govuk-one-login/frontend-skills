"""Unit tests for the shared lib (hashing determinism + manifest round-trip)."""

from __future__ import annotations

import json

from evals.lib import (
    hash_bytes,
    hash_file,
    hash_skill,
    hash_fixture,
    build_manifest_entry,
    read_manifest,
    write_manifest,
    upsert_entry,
)
from evals.lib.manifest import empty_manifest


def test_hash_bytes_is_stable():
    assert hash_bytes(b"abc") == hash_bytes(b"abc")
    assert hash_bytes(b"abc") != hash_bytes(b"abd")


def test_hash_file_matches_bytes(tmp_path):
    p = tmp_path / "f.txt"
    p.write_bytes(b"hello")
    assert hash_file(p) == hash_bytes(b"hello")


def test_hash_tree_is_order_independent_and_content_sensitive(tmp_path):
    d = tmp_path / "tree"
    (d / "sub").mkdir(parents=True)
    (d / "a.txt").write_text("a")
    (d / "sub" / "b.txt").write_text("b")
    h1 = hash_fixture(d)

    # Rewriting the same content yields the same hash.
    (d / "a.txt").write_text("a")
    assert hash_fixture(d) == h1

    # Changing content changes the hash.
    (d / "a.txt").write_text("a-changed")
    assert hash_fixture(d) != h1


def test_hash_skill_reads_whole_directory(tmp_path):
    s = tmp_path / "my-skill"
    s.mkdir()
    (s / "SKILL.md").write_text("---\nname: my-skill\ndescription: x\n---\nbody")
    h1 = hash_skill(s)
    (s / "references").mkdir()
    (s / "references" / "r.md").write_text("ref")
    assert hash_skill(s) != h1  # adding a referenced file changes the hash


def test_manifest_roundtrip_and_upsert(tmp_path):
    path = tmp_path / "manifest.json"
    m = empty_manifest()
    e1 = build_manifest_entry(
        concern="application",
        skill="s",
        case_id="c1",
        skill_hash="sh",
        case_hash="ch",
        fixture_hash="fh",
    )
    upsert_entry(m, e1)
    write_manifest(m, path)

    loaded = read_manifest(path)
    assert loaded["version"] == 2
    assert loaded["algorithm"] == "sha256"
    assert len(loaded["entries"]) == 1

    # Upsert with the same key replaces rather than duplicates.
    e1b = build_manifest_entry(
        concern="application", skill="s", case_id="c1",
        skill_hash="sh2", case_hash="ch2", fixture_hash="fh2",
    )
    upsert_entry(loaded, e1b)
    assert len(loaded["entries"]) == 1
    assert loaded["entries"][0]["skill_hash"] == "sh2"

    # A different concern/case is a distinct entry.
    e2 = build_manifest_entry(concern="content", skill="s", skill_hash="sh")
    upsert_entry(loaded, e2)
    assert len(loaded["entries"]) == 2


def test_manifest_write_is_sorted_and_deterministic(tmp_path):
    path = tmp_path / "m.json"
    m = empty_manifest()
    upsert_entry(m, build_manifest_entry(concern="content", skill="z", skill_hash="1"))
    upsert_entry(m, build_manifest_entry(concern="application", skill="a", case_id="c", skill_hash="2"))
    write_manifest(m, path)
    first = path.read_text()
    # Rewrite the same logical manifest and confirm byte-identical output.
    m2 = read_manifest(path)
    write_manifest(m2, path)
    assert path.read_text() == first
    entries = json.loads(first)["entries"]
    # application < content by concern sort.
    assert entries[0]["concern"] == "application"
