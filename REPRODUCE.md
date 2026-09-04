# Reproducing the method

This is the end-to-end path from a clone to a rebuilt paper. It reproduces the
*method*, not the numbers: every stage calls an LLM, so a fresh run of a world
will differ in its particulars from the one reported. What should reproduce is
the shape of the result — consensus writing the fewest entries, being the only
backend whose memories become shared, and the sharing rate rising with the
horizon.

The repository carries the method and the paper, not the data: nothing a run
produces — stores, checkpoints, event logs, statistics, scored results,
generated figures — is committed. Steps 1 through 5 below regenerate all of
it into `runs/`, and step 6 builds the paper from what they wrote, so run
them in order rather than expecting `build_paper_academic.py` to work on a
bare clone. `README.md` covers the framework itself (config, scenario format,
checkpointing, architecture); this file covers only the experiments.

## 0. Setup

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
cp config.json.example config.json     # fill in api_key
```

Every experiment script below takes `config_path="config_flash.json"`, which is
gitignored because ours holds a key. Either create it as a copy of your
`config.json`, or edit the script's `config_path`. The reported runs used
`gpt-5-mini` for chat and `text-embedding-3-small` for embeddings.

## 1. Sediment the worlds

Turns each source text into a scenario: a cast, a map, information carriers,
and a memory store seeded with what the characters would already know.

```bash
venv/bin/python -m experiments.sediment_all
```

Reads `scenarios/sources/*.txt` (tracked) and writes `scenarios/<world>.yaml`,
`.registry.json` and `.ltm.json` — the last is the seeded store, several
hundred MB of embeddings, which is why it is not in the repo. The sedimented
spans are chapters 1–40 for both novels, Acts I–III for Hamlet, and the
timeline through 2024-04 for Russia–Ukraine; the rest of each work is held out
as the reference the continuation is scored against.

`scenarios/<world>.sim.yaml` (tracked) is the simulation scenario built from
that: cast selection is `experiments.select_cast`, carrier placement is
`experiments.place_carriers`. Both are already applied in the tracked files,
so this step only needs rerunning if you change the cast or the corpus.

## 2. Run the four backends

One invocation per backend, four backends per world:

```bash
for m in consensus generative_agents g_memory collaborative; do
  venv/bin/python -m experiments.run_hl20 $m       # Hamlet, rounds 0-19
done
```

Longer horizons resume from the previous stage's final checkpoint rather than
starting over, which is how the reported 40- and 80-round runs were produced:

```bash
venv/bin/python -m experiments.resume_hl30 consensus   # -> runs/hl30_consensus
venv/bin/python -m experiments.resume_hl40 consensus   # -> runs/hl40_consensus
```

The per-world launchers are `run_hl20` / `run_rc10` for the first stage and
`resume_*` for each later one; `experiments/run_sim.py` is the function they
all call, and takes the two ablation knobs (`consensus_merge`,
`cache_strategy`) directly.

A run writes `events.jsonl` (the record everything else is computed from),
`ltm_final.json` (the store with embeddings), `checkpoints/` (resumable state)
and `result.json` (footprint and cost).

## 3. Structure statistics

```bash
venv/bin/python -m experiments.prep_hl40_paper
```

Concatenates the stages into `runs/hl40full_consensus/`, writes
`runs/paper_stats_hl40.json` (entries, sharing, linking, merge depth, growth,
latency, the three-layer relation numbers) and the growth/latency figures.
One `prep_<stage>_paper.py` per world-horizon.

## 4. Continuation quality

```bash
RUN_REPEAT=3 venv/bin/python -m experiments.score_all hamlet
venv/bin/python -m experiments.quality_figs hamlet
```

Renders one screenplay per backend, scores grounding, trajectory and narrative
from it and goal pursuit from the event log, three times each, into
`runs/results_hl40.json`. `METRICS=goal` scores only goal pursuit and merges it
into an existing results file.

## 5. Ablation

```bash
venv/bin/python experiments/run_ablation_cell.py on fifo 40        # as published
venv/bin/python experiments/run_ablation_cell.py on relevance 40
venv/bin/python experiments/run_ablation_cell.py on hybrid 40
venv/bin/python experiments/run_ablation_cell.py off fifo 40       # merge disabled
ABLATION_REPEAT=3 venv/bin/python -m experiments.score_ablation
venv/bin/python -m experiments.ablation_fig
```

One factor at a time from the published configuration, consensus backend on
Three Kingdoms. Unlike §5.3, all four metrics here read the event log directly,
so no renderer sits between a cell and its score.

## 6. Case-study graphs and the paper

```bash
venv/bin/python experiments/export_graph_json.py runs/hl40full_consensus
venv/bin/python experiments/case_study_trilayer.py runs/hl40full_consensus
venv/bin/python -m experiments.translate_case_study runs/hl40full_consensus
venv/bin/python -m experiments.appendix_screenplays hamlet
venv/bin/python -m experiments.scene_grid_fig
venv/bin/python -m experiments.review_stats
venv/bin/python -m experiments.build_paper_academic     # -> docs/index.html
```

`review_stats.py` needs no LLM: it recomputes what auto-expansion returns,
what the keep-shorter merge rule discards, and how far the quality metrics sit
from their ceiling, straight from the event logs and final stores.

`build_paper_academic.py` reads what steps 1&ndash;5 wrote into `runs/` and
emits the whole paper as one self-contained HTML file — every figure, table
and number inlined. It needs those steps to have run for the worlds it
reports; `docs/index.html` in the repository is the built result for our runs.

Two appendix tables are counted by reading whole event logs. If you have run
the worlds, the logs are there and are used directly. If you are rebuilding
from a partial set, cache the counts once and the builder will fall back to
them:

```bash
venv/bin/python -m experiments.cache_derived   # -> runs/derived_tables.json
```

Logs take precedence over the cache, so your rerun always reports its own
numbers.

## Costs

Measured on the reported runs, `gpt-5-mini`, 32-way concurrency:

| stage | wall-clock | tokens |
|---|---|---|
| Hamlet, 20 rounds, one backend | 6–19 min | 1.6–3.0 M |
| Three Kingdoms, 20 rounds, one backend | ~45 min | ~15 M |
| Russia–Ukraine, 20 rounds, one backend | ~60 min | ~19 M |
| sedimentation, one world | hours | tens of M |
| scoring one world, four backends, 3 repeats | ~40 min | — |

A full four-world, four-backend replication at the reported horizons is on the
order of a few hundred million tokens. Hamlet at 40 rounds is the cheapest
entry point and shows every structural effect the paper reports.
