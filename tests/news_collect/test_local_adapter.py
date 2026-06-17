import yaml

from news_collect.adapters.local import LocalAdapter
from news_collect.state import SourceState


def _make_notes(tmp_path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "a.md").write_text("# A\n\nalpha", encoding="utf-8")
    (notes / "b.md").write_text("# B\n\nbeta", encoding="utf-8")
    return notes


def test_discover_finds_markdown_with_path_hash_keys(tmp_path):
    notes = _make_notes(tmp_path)
    adapter = LocalAdapter(paths=[str(notes)], vault=tmp_path / "vault", now="2026-06-14T09:00:00+02:00")
    refs = adapter.discover(SourceState(), fresh=False)
    assert len(refs) == 2
    assert all("#" in r.key for r in refs)
    assert all(r.source == "local" for r in refs)


def test_fetch_writes_files_to_vault(tmp_path):
    notes = _make_notes(tmp_path)
    vault = tmp_path / "vault"
    adapter = LocalAdapter(paths=[str(notes)], vault=vault, now="2026-06-14T09:00:00+02:00")
    refs = adapter.discover(SourceState(), fresh=False)
    result = adapter.fetch(refs)
    assert result.status == "ok"
    out = list((vault / "News" / "local").glob("*.md"))
    assert len(out) == 2
    text = out[0].read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---\n")[1])
    assert fm["source"] == "local"
    assert "source_path" in fm


def test_fetch_merges_existing_frontmatter_instead_of_nesting(tmp_path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "vid.md").write_text(
        "---\n"
        "title: Real Title\n"
        "source: https://example.com/v.mp4\n"
        "duration: '12:25'\n"
        "date: '2026-06-16'\n"
        "transcript_source: whisper:base\n"
        "---\n\n# Real Title\n\nbody text\n",
        encoding="utf-8",
    )
    vault = tmp_path / "vault"
    adapter = LocalAdapter(paths=[str(notes)], vault=vault, now="2026-06-17T11:00:00+02:00")
    result = adapter.fetch(adapter.discover(SourceState(), fresh=False))
    assert result.status == "ok"

    text = list((vault / "News" / "local").glob("*.md"))[0].read_text(encoding="utf-8")
    # Exactly one frontmatter block: a single closing "\n---\n" fence.
    assert text.count("\n---\n") == 1
    parts = text.split("---\n")
    fm = yaml.safe_load(parts[1])
    body = "---\n".join(parts[2:])

    assert fm["source"] == "local"                      # collector source preserved
    assert fm["title"] == "Real Title"                  # inner title wins over stem
    assert fm["url"] == "https://example.com/v.mp4"     # inner source -> url
    assert fm["date"] == "2026-06-16"                   # inner metadata carried up
    assert fm["duration"] == "12:25"
    assert fm["transcript_source"] == "whisper:base"
    assert fm["source_path"].endswith("vid.md")
    assert "title: Real Title" not in body              # inner frontmatter not duplicated in body
    assert "# Real Title" in body


def test_refs_for_expands_dirs_for_ingest(tmp_path):
    notes = _make_notes(tmp_path)
    adapter = LocalAdapter(paths=[], vault=tmp_path / "vault", now="t")
    refs = adapter.refs_for([str(notes)])
    assert len(refs) == 2
