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


def test_refs_for_expands_dirs_for_ingest(tmp_path):
    notes = _make_notes(tmp_path)
    adapter = LocalAdapter(paths=[], vault=tmp_path / "vault", now="t")
    refs = adapter.refs_for([str(notes)])
    assert len(refs) == 2
