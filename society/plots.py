"""English-labelled case-study plots (Deliverable 3).

The paper is in English even though a simulation (e.g. Three Kingdoms) runs
in Chinese, so every figure built from a run's `SharedMemory` export must
carry English titles/axis labels and English (or id-fallback) agent names,
never the source-language ones baked into the run.

All functions take LTM export/`all_entries()`-shaped entries (each at least
{"id", "text", "owners", ...}) plus an optional {agent_id: display_name}
map, and write a PNG via matplotlib's non-interactive Agg backend (no
display, no network).
"""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402


def _display_name(agent_id: str, agent_names: dict | None) -> str:
    agent_names = agent_names or {}
    return agent_names.get(agent_id) or agent_id


def _agent_ids(entries: list[dict], agent_names: dict | None) -> list[str]:
    """Deterministic (sorted) union of every agent id that owns >=1 entry,
    plus any id explicitly present in `agent_names` (so an agent with zero
    entries still gets a row/column/bar)."""
    ids: set[str] = set(agent_names or {})
    for e in entries:
        ids.update(e.get("owners", []) or [])
    return sorted(ids)


def shared_memory_matrix(entries: list[dict], agent_names: dict | None, out_path: str) -> str:
    """Write an agent x agent shared-memory heatmap.

    M[i][i] = agent i's entry count (entries i owns, alone or jointly).
    M[i][j] (i != j) = number of entries jointly owned by i and j.
    """
    agent_ids = _agent_ids(entries, agent_names)
    n = len(agent_ids)
    index = {aid: i for i, aid in enumerate(agent_ids)}
    matrix = [[0] * n for _ in range(n)]

    for e in entries:
        owners = sorted(set(e.get("owners", []) or []))
        for a in owners:
            i = index.get(a)
            if i is not None:
                matrix[i][i] += 1
        for x in range(len(owners)):
            for y in range(x + 1, len(owners)):
                i, j = index[owners[x]], index[owners[y]]
                matrix[i][j] += 1
                matrix[j][i] += 1

    labels = [_display_name(aid, agent_names) for aid in agent_ids]

    fig, ax = plt.subplots(figsize=(max(4, n * 0.6 + 1), max(4, n * 0.6 + 1)))
    im = ax.imshow(matrix, cmap="viridis")
    ax.set_title("Shared-memory matrix")
    ax.set_xlabel("Agent")
    ax.set_ylabel("Agent")
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels)
    for i in range(n):
        for j in range(n):
            ax.text(j, i, str(matrix[i][j]), ha="center", va="center", color="white", fontsize=8)
    fig.colorbar(im, ax=ax, label="Entry count")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def memory_per_character_bar(
    entries: list[dict], agent_names: dict | None, out_path: str
) -> str:
    """Write a bar chart of each agent's total entry count."""
    agent_ids = _agent_ids(entries, agent_names)
    counts = {aid: 0 for aid in agent_ids}
    for e in entries:
        for a in e.get("owners", []) or []:
            if a in counts:
                counts[a] += 1

    labels = [_display_name(aid, agent_names) for aid in agent_ids]
    values = [counts[aid] for aid in agent_ids]

    fig, ax = plt.subplots(figsize=(max(4, len(agent_ids) * 0.6 + 1), 4))
    ax.bar(labels, values, color="steelblue")
    ax.set_title("Memory entries per character")
    ax.set_xlabel("Agent")
    ax.set_ylabel("Entry count")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def consensus_pairs_bar(entries: list[dict], agent_names: dict | None, out_path: str) -> str:
    """Write a bar chart of jointly-owned ("consensus") entry counts per
    agent pair, sorted descending (ties broken by pair label) for a
    deterministic plot; pairs with zero shared entries are omitted."""
    agent_ids = _agent_ids(entries, agent_names)
    pair_counts: dict[tuple[str, str], int] = {}
    for e in entries:
        owners = sorted(set(e.get("owners", []) or []) & set(agent_ids))
        for x in range(len(owners)):
            for y in range(x + 1, len(owners)):
                key = (owners[x], owners[y])
                pair_counts[key] = pair_counts.get(key, 0) + 1

    pairs = sorted(pair_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    labels = [
        f"{_display_name(a, agent_names)}–{_display_name(b, agent_names)}"
        for (a, b), _ in pairs
    ]
    values = [count for _, count in pairs]

    fig, ax = plt.subplots(figsize=(max(4, len(labels) * 0.6 + 1), 4))
    if labels:
        ax.bar(labels, values, color="darkorange")
    ax.set_title("Consensus (jointly-owned) memory pairs")
    ax.set_xlabel("Agent pair")
    ax.set_ylabel("Shared entry count")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path
