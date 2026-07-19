from society.plots import (
    consensus_pairs_bar,
    memory_per_character_bar,
    shared_memory_matrix,
)

ENTRIES = [
    {"id": "e1", "text": "a", "owners": ["liubei"]},
    {"id": "e2", "text": "b", "owners": ["guanyu", "zhangfei"]},
    {"id": "e3", "text": "c", "owners": ["liubei", "guanyu"]},
]

AGENT_NAMES = {"liubei": "Liu Bei", "guanyu": "Guan Yu", "zhangfei": "Zhang Fei"}


def test_shared_memory_matrix_writes_png(tmp_path):
    out = tmp_path / "matrix.png"
    result = shared_memory_matrix(ENTRIES, AGENT_NAMES, str(out))
    assert result == str(out)
    assert out.exists() and out.stat().st_size > 0


def test_memory_per_character_bar_writes_png(tmp_path):
    out = tmp_path / "bar.png"
    result = memory_per_character_bar(ENTRIES, AGENT_NAMES, str(out))
    assert result == str(out)
    assert out.exists() and out.stat().st_size > 0


def test_consensus_pairs_bar_writes_png(tmp_path):
    out = tmp_path / "pairs.png"
    result = consensus_pairs_bar(ENTRIES, AGENT_NAMES, str(out))
    assert result == str(out)
    assert out.exists() and out.stat().st_size > 0


def test_shared_memory_matrix_falls_back_to_id_without_display_name(tmp_path):
    out = tmp_path / "matrix_fallback.png"
    shared_memory_matrix(ENTRIES, None, str(out))
    assert out.exists() and out.stat().st_size > 0


def test_no_shared_entries_still_writes_png(tmp_path):
    out = tmp_path / "pairs_empty.png"
    entries = [{"id": "e1", "text": "a", "owners": ["liubei"]}]
    consensus_pairs_bar(entries, AGENT_NAMES, str(out))
    assert out.exists() and out.stat().st_size > 0
