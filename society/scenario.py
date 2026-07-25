import json
import os
import uuid

import yaml

from society.actions import Message
from society.agent import Agent
from society.baselines import make_memory
from society.brains import LLMBrain, RetrievalBrain, RuleBrain
from society.kernel import Kernel
from society.metrics import Metrics
from society.stm import STM
from society.worldmap import WorldMap

_BRAIN_KINDS = {"llm", "rule", "retrieval"}


def load_scenario(path: str) -> dict:
    """Load and validate a scenario YAML file.

    Raises ValueError on:
      - an agent missing "id" or "kind"
      - duplicate agent ids
      - an unknown "brain" value
      - a "private_status_keys" field that isn't a list of strings
      - a character/info_carrier whose initial status.location does not
        reference an environment agent defined in the file
      - a map edge endpoint that isn't a defined environment id
      - a top-level "ltm_file" that doesn't exist relative to the
        scenario file's directory

    Stores the scenario file's directory under cfg["_dir"] so that
    build_society can resolve relative paths (e.g. info_carrier corpus
    files, ltm_file) against the scenario file rather than the process cwd.
    """
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    agents = cfg.get("agents", [])
    seen_ids = set()
    env_ids = set()

    for a in agents:
        if "id" not in a:
            raise ValueError("agent missing required 'id' field")
        if "kind" not in a:
            raise ValueError(f"agent {a['id']!r} missing required 'kind' field")

        aid = a["id"]
        if aid in seen_ids:
            raise ValueError(f"duplicate agent id: {aid}")
        seen_ids.add(aid)

        brain = a.get("brain")
        if brain not in _BRAIN_KINDS:
            raise ValueError(f"agent {aid!r}: unknown brain {brain!r}")

        private_keys = a.get("private_status_keys")
        if private_keys is not None:
            if not isinstance(private_keys, list) or not all(
                isinstance(k, str) for k in private_keys
            ):
                raise ValueError(
                    f"agent {aid!r}: private_status_keys must be a list of strings"
                )

        name = a.get("name")
        if name is not None and not isinstance(name, str):
            raise ValueError(f"agent {aid!r}: name must be a string")

        archived = a.get("archived")
        if archived is not None and not isinstance(archived, bool):
            raise ValueError(f"agent {aid!r}: archived must be a bool")

        if a["kind"] == "environment":
            env_ids.add(aid)

    for a in agents:
        if a["kind"] in ("character", "info_carrier"):
            loc = (a.get("status") or {}).get("location")
            if loc is not None and loc not in env_ids:
                raise ValueError(
                    f"agent {a['id']!r}: initial location {loc!r} is not an "
                    "environment agent defined in this scenario"
                )

    map_cfg = cfg.get("map") or {}
    for edge in map_cfg.get("edges", []):
        a_id, b_id = edge[0], edge[1]
        if a_id not in env_ids or b_id not in env_ids:
            raise ValueError(
                f"map edge {edge!r} references an id that isn't an environment agent"
            )

    cfg["_dir"] = os.path.dirname(os.path.abspath(path))

    ltm_file = cfg.get("ltm_file")
    if ltm_file is not None:
        full_ltm_path = os.path.join(cfg["_dir"], ltm_file)
        if not os.path.isfile(full_ltm_path):
            raise ValueError(f"ltm_file not found: {full_ltm_path!r}")

    return cfg


# Task S2 (unified-agent architecture): kind-specific system-prompt
# preamble prepended to an environment/info_carrier agent's profile
# whenever it ends up with an LLMBrain, so the LLM understands its role is
# different from a character's even though the brain/STM machinery is now
# identical across all three kinds. Picked by the scenario's "language".
_ENV_PREAMBLE = {
    "zh": (
        "你是一个地点/环境 agent,代表模拟世界中的一处场所本身,而不是一个角色。"
        "回应到访者对你发起的询问与动作(act_on),用 update_status 维护自身状态"
        "(例如天气、门是否开着、桌上有什么),用 recall 查询发生在你这里的记忆。"
    ),
    "en": (
        "You are a location/environment agent -- you represent a place in "
        "the simulated world itself, not a character. Respond to visitors' "
        "act_on requests directed at you, use update_status to maintain "
        "your own state (e.g. weather, whether a door is open, what's on a "
        "table), and use recall to search memories that happened here."
    ),
}
_CARRIER_PREAMBLE = {
    "zh": (
        "你是一份文书/信息载体(信件、日记、公告等),代表这份文档本身,而不是一个角色。"
        "如实根据你的记忆(即文书内容)回答别人对你发起的 read 询问,不得虚构内容。"
    ),
    "en": (
        "You are a document/information carrier (a letter, diary, notice, "
        "etc.) -- you represent the document itself, not a character. "
        "Truthfully answer read queries directed at you based on your own "
        "memory (i.e. the document's content); never fabricate content."
    ),
}


def _with_preamble(preamble_map: dict, language: str, profile: str) -> str:
    preamble = preamble_map.get(language, preamble_map["en"])
    return f"{preamble}\n\n{profile}" if profile else preamble


def _make_brain(a: dict, *, llm, language: str, scenario_dir: str):
    """Builds the brain for one scenario agent entry.

    Task S2 (unified-agent architecture): environment/info_carrier agents
    now get an LLMBrain in the sim path, exactly like characters. The
    legacy `brain: rule` (environments) / `brain: retrieval` (info
    carriers) yaml values from before this design -- still present in
    existing scenario files -- are mapped to LLMBrain whenever the agent
    kind is environment/info_carrier AND a real llm client is configured
    (llm is not None): there's no longer a meaningful distinction between
    "rule" and "llm" for these kinds going forward, so the legacy value is
    just read as "give this agent an LLM brain". `brain: retrieval`'s
    `corpus:` field is ignored in this path -- a carrier's LLMBrain answers
    `read` queries by recalling its own LTM (the document chains deposited
    by history sedimentation), not by keyword-matching a fixed corpus file.

    `brain: rule` stays available as an explicit opt-in, still producing a
    RuleBrain, for any agent kind when either (a) the agent kind is
    "character" (character scripting is untouched by this task), or (b) no
    real llm is configured (llm is None) -- e.g. a scenario built without
    an LLM client, where an env/carrier LLMBrain could never safely
    decide(). Likewise `brain: retrieval` without a real llm still falls
    back to the legacy RetrievalBrain(corpus_text), reading `corpus:` as
    before. `brain: llm` is unconditional, for every agent kind, exactly
    as before.
    """
    kind_name = a["brain"]
    agent_kind = a["kind"]

    use_llm = kind_name == "llm" or (
        kind_name in ("rule", "retrieval")
        and agent_kind in ("environment", "info_carrier")
        and llm is not None
    )
    if use_llm:
        profile = a.get("profile", "")
        if agent_kind == "environment":
            profile = _with_preamble(_ENV_PREAMBLE, language, profile)
        elif agent_kind == "info_carrier":
            profile = _with_preamble(_CARRIER_PREAMBLE, language, profile)
        return LLMBrain(llm, profile=profile, language=language)

    if kind_name == "rule":
        return RuleBrain()

    # retrieval, falling back to the legacy corpus-backed RetrievalBrain
    # (agent kind not environment/info_carrier, or no real llm configured).
    corpus_text = ""
    corpus_path = a.get("corpus")
    if corpus_path:
        full_path = os.path.join(scenario_dir, corpus_path)
        with open(full_path, "r", encoding="utf-8") as f:
            corpus_text = f.read()
    return RetrievalBrain(corpus_text)


def build_agents_and_map(cfg: dict, *, llm, embed_fn=None) -> tuple[dict, "WorldMap", dict, list]:
    """Build the agents dict + WorldMap from a loaded scenario dict.

    This is the brain/agent-construction core shared by `build_society`
    (fresh run) and `society.persistence.restore_society` (resume from a
    checkpoint) -- kept in exactly one place so the two paths can never
    drift apart on how a scenario's agents/brains/map are constructed.

    `embed_fn` (the same async embedding function used for SharedMemory)
    is threaded into each agent's STM as `cache_embed_fn`, so the STM
    cache's "relevance"/"hybrid" eviction strategies (config knobs
    `cache_strategy`/`cache_alpha` in `defaults`) have an embedder to
    score with. It's optional (None) since it's only required when a
    non-"fifo" cache_strategy is configured.

    Returns (agents, worldmap, defaults, seed_specs) where `defaults` is
    the resolved `cfg["defaults"]` dict and `seed_specs` is the
    `[(agent_id, [seed_memory_texts]), ...]` list -- callers that must NOT
    replay seed memories (i.e. resume) simply ignore `seed_specs`.
    """
    defaults = cfg.get("defaults", {}) or {}
    language = cfg.get("language", "zh")
    scenario_dir = cfg.get("_dir", ".")

    fifo_size = defaults.get("fifo_size", 20)
    distance = defaults.get("distance", 20)
    cache_strategy = defaults.get("cache_strategy", "fifo")
    cache_alpha = defaults.get("cache_alpha", 0.5)

    agents: dict[str, Agent] = {}
    env_ids = []
    seed_specs = []  # (agent_id, [texts])

    for a in cfg.get("agents", []):
        brain = _make_brain(a, llm=llm, language=language, scenario_dir=scenario_dir)
        stm = STM(
            fifo_size=fifo_size,
            status=a.get("status"),
            private_keys=set(a["private_status_keys"]) if a.get("private_status_keys") else None,
            goals=a.get("goals"),
            cache_strategy=cache_strategy,
            cache_alpha=cache_alpha,
            cache_embed_fn=embed_fn,
        )
        agent = Agent(
            a["id"],
            a["kind"],
            brain,
            stm,
            portable=a.get("portable", False),
            holder=a.get("holder"),
            profile=a.get("profile", ""),
            name=a.get("name"),
            archived=a.get("archived", False),
        )
        agents[a["id"]] = agent
        if a["kind"] == "environment":
            env_ids.append(a["id"])
        if a.get("seed_memories"):
            seed_specs.append((a["id"], a["seed_memories"]))

    map_cfg = cfg.get("map") or {}
    edges = [tuple(e) for e in map_cfg.get("edges", [])]
    worldmap = WorldMap(
        env_ids,
        edges=edges,
        default_distance=map_cfg.get("default_distance", distance),
    )

    return agents, worldmap, defaults, seed_specs


async def build_society(
    cfg: dict,
    *,
    llm,
    embed_fn,
    event_log,
    out_dir=None,
    metrics_interval=None,
    memory_kind: str = "consensus",
) -> Kernel:
    """Build a fully-wired Kernel from a loaded scenario dict.

    Creates all agents (brain selected per agent's "brain" field), a
    WorldMap from cfg["map"], a shared-memory backend, and a Metrics
    instance. Kickoff messages are queued with tick_sent=-1 before the
    kernel is returned so they are already pending on kernel.send()
    (visible to recipients once the caller calls kernel.run(), per the
    tick-0 delivery semantics in Kernel.run()).

    `memory_kind` (Task S3) selects the shared-memory backend via
    `society.baselines.make_memory` -- one of "consensus" (default;
    `society.ltm.SharedMemory`, today's behavior, unchanged),
    "generative_agents", "g_memory", "collaborative". This is the ONLY
    thing that changes across a Task-S3 experiment run; everything else
    (agents, brains, map, kernel scheduling) is identical regardless of
    backend.

    If cfg has a top-level "ltm_file" (path relative to the scenario
    file's directory, validated to exist by load_scenario), the memory
    backend is populated via `shared.restore()` from that holographic
    dump instead -- seed_memories are NOT replayed in that case, since the
    ltm_file already reflects (a superset of) their effect. Otherwise each
    agent's seed_memories are seeded as before. All 4 backends implement
    `restore()`, including on a dump that carries multi-owner ("consensus")
    entries -- see `society.baselines.GenerativeAgentsMemory.restore` for
    the one backend whose restore needed a fix for this (per-owner rows).
    """
    agents, worldmap, defaults, seed_specs = build_agents_and_map(cfg, llm=llm, embed_fn=embed_fn)

    memory_max_tokens = defaults.get(
        "memory_max_tokens", defaults.get("memory_max_chars", 50)
    )
    stats_interval = defaults.get("stats_interval", 10)

    shared = make_memory(memory_kind, embed_fn, llm=llm, max_tokens=memory_max_tokens)

    interval = metrics_interval if metrics_interval is not None else stats_interval
    metrics = Metrics(agents, shared, out_dir, interval=interval)

    kernel = Kernel(
        agents,
        worldmap,
        event_log,
        shared_memory=shared,
        llm=llm,
        metrics=metrics,
        config={
            "language": cfg.get("language", "zh"),
            "wake_all_characters": defaults.get("wake_all_characters", False),
        },
    )
    kernel.scenario_cfg = cfg

    ltm_file = cfg.get("ltm_file")
    if ltm_file is not None:
        ltm_path = os.path.join(cfg.get("_dir", "."), ltm_file)
        with open(ltm_path, "r", encoding="utf-8") as f:
            await shared.restore(json.load(f))
    else:
        for agent_id, texts in seed_specs:
            for text in texts:
                await shared.remember(agent_id, text, tick=0, source="scenario_seed")

    for kick in cfg.get("kickoff", []):
        msg = Message(
            id=str(uuid.uuid4()),
            sender="scenario",
            recipients=list(kick["to"]),
            kind=kick["kind"],
            content=kick["content"],
            tick_sent=-1,
        )
        kernel.send(msg)

    return kernel
