"""Task B2 (atomize -> assign-owners history-sedimentation pipeline),
reworked by Task F2 into an EVENT-GROUPED pipeline with thorough
multi-agent owners and no `narrator` fallback.

Per chunk: (1) a roster call for state only, (2) one atomize call breaking
the chunk into EVENT GROUPS of complete, self-contained, source-language
fragments (no pronouns, no chapter-heading/marker prefixes, no authorial
framing, <=64 tokens each), (3) one or more assign calls (batched at
<=20 fragments per call) attributing each fragment to EVERY role id that
would plausibly know/be aware of it (participants, witnesses, the
location(s), any carrier -- over-inclusion preferred). Fragments with no
resolvable owner fall back to the chunk's roster-derived location id(s);
if that's empty too, the fragment is dropped (never deposited ownerless,
never attributed to a reserved `narrator` id -- that fallback is gone).
Each event's deposited fragments are linked together via
`SharedMemory.link_group` so they end up mutually affiliated. story_time is
no longer threaded into deposits -- only story_order anchors them.

No real API calls anywhere -- FakeLLM (scripted per-call, routed on the
distinguishing marker text baked into each new prompt) + the async fake
embed throughout.
"""

import copy
import json
import uuid

import pytest

from society.history_extract import (
    NARRATOR_ID,
    _chunk_location_ids,
    _is_background_exposition_fragment,
    _is_heading_or_marker_fragment,
    _RegistryResolvers,
    _ensure_narrator_role,
    _process_chunk_atomic,
    _run_sediment_pass_atomic,
    extract_history,
)
from society.ltm import SharedMemory
from society.textlen import count_tokens
from tests.helpers import FakeLLM, afake_embed

REGISTRY = {
    "characters": [
        {"id": "alice", "name": "甲", "aliases": [], "profile": ""},
        {"id": "bob", "name": "乙", "aliases": [], "profile": ""},
    ],
    "locations": [{"id": "loc1", "name": "集市", "aliases": [], "profile": ""}],
    "carriers": [],
}


def _registry() -> dict:
    return copy.deepcopy(REGISTRY)


def _new_shared(llm) -> SharedMemory:
    # Matches extract_history's real sedimentation config (Task F2 change #6).
    return SharedMemory(afake_embed, llm, collection_name=f"t_{uuid.uuid4().hex[:8]}", max_tokens=64)


def _chunk(text: str, flat_idx: int = 0, title: str | None = "第一回") -> dict:
    return {"text": text, "title": title, "flat_idx": flat_idx}


ROSTER_RESPONSE = json.dumps(
    {
        "characters": ["alice", "bob"],
        "state_updates": [{"id": "alice", "location": "loc1", "alive": True}],
        "story_time": "t1",
    },
    ensure_ascii=False,
)

ROSTER_RESPONSE_NO_LOCATION = json.dumps(
    {"characters": [], "state_updates": [], "story_time": "t1"}, ensure_ascii=False
)


def _routed_fake(atomize_response: str, assign_response: str, roster_response: str = ROSTER_RESPONSE):
    def fake(prompt, system=None):
        if "[atomize]" in prompt:
            return atomize_response
        if "[assign]" in prompt:
            return assign_response
        if "出场" in prompt:
            return roster_response
        return "[]"

    return fake


# ----------------------------------------------------------------------
# 1. _process_chunk_atomic: events parsed, multi-owner, location fallback
#    (no narrator ever).
# ----------------------------------------------------------------------


async def test_process_chunk_atomic_events_multi_owner_and_location_fallback():
    registry = _registry()
    resolvers = _RegistryResolvers(registry)
    warnings: list[str] = []

    # One event with two fragments (alice alone, then alice+bob), a second
    # event with one fragment that gets NO owner from assign -> falls back
    # to the chunk's roster location (loc1), never to narrator. Per-event
    # assign (Task F2.1) means these two events get TWO separate assign
    # calls, each seeing only its own fragment(s) -- route the fake by
    # content rather than a single flat response.
    atomize_response = json.dumps(
        [
            ["alice went to the market", "alice and bob met at the market"],
            ["the market stalls were being packed up for the night"],
        ],
        ensure_ascii=False,
    )

    def fake(prompt, system=None):
        if "[atomize]" in prompt:
            return atomize_response
        if "[assign]" in prompt:
            if "alice went to the market" in prompt:
                return json.dumps([["alice"], ["alice", "bob"]], ensure_ascii=False)
            return json.dumps([[]], ensure_ascii=False)
        if "出场" in prompt:
            return ROSTER_RESPONSE
        return "[]"

    llm = FakeLLM(fn=fake)

    result = await _process_chunk_atomic(llm, _chunk("正文"), registry, resolvers, "", warnings)

    assert result["flat_idx"] == 0
    assert result["state_updates"] == [{"id": "alice", "location": "loc1", "alive": True}]
    assert "story_time" not in result

    events = result["events"]
    assert len(events) == 2
    assert events[0][0] == ("alice went to the market", ["alice"])
    assert events[0][1][0] == "alice and bob met at the market"
    assert sorted(events[0][1][1]) == ["alice", "bob"]
    # Location fallback -- NOT narrator.
    assert events[1] == [("the market stalls were being packed up for the night", ["loc1"])]

    assert not any("narrator" in w.lower() for w in warnings)
    assert any("falling back to chunk location" in w for w in warnings)


# ----------------------------------------------------------------------
# 2. Heading/authorial-framing fragments are dropped even if the model
#    emits them despite the prompt telling it not to.
# ----------------------------------------------------------------------


def test_is_heading_or_marker_fragment_detects_chapter_heading_and_bare_marker():
    assert _is_heading_or_marker_fragment("第一回 甲乙初遇")
    assert _is_heading_or_marker_fragment("第一百回 尾声")
    assert _is_heading_or_marker_fragment("【建安五年】")
    assert not _is_heading_or_marker_fragment("甲与乙在集市相遇")
    assert not _is_heading_or_marker_fragment("【建安五年】关羽挂印封金离开曹营")  # not a BARE marker


async def test_heading_fragment_in_event_dropped_no_such_memory():
    registry = _registry()
    resolvers = _RegistryResolvers(registry)
    warnings: list[str] = []

    atomize_response = json.dumps(
        [["第一回 甲乙初遇", "甲与乙在集市相遇"]], ensure_ascii=False
    )
    assign_response = json.dumps([["alice"]], ensure_ascii=False)
    llm = FakeLLM(fn=_routed_fake(atomize_response, assign_response))

    result = await _process_chunk_atomic(llm, _chunk("正文"), registry, resolvers, "", warnings)

    events = result["events"]
    assert len(events) == 1
    assert events[0] == [("甲与乙在集市相遇", ["alice"])]
    all_texts = [f for ev in events for f, _ in ev]
    assert "第一回 甲乙初遇" not in all_texts
    assert any("heading/marker fragment" in w for w in warnings)


# ----------------------------------------------------------------------
# 3. End-to-end via _run_sediment_pass_atomic: NO narrator role ever
#    created/used; deposits land with the right owners.
# ----------------------------------------------------------------------


async def test_run_sediment_pass_atomic_deposits_with_owners_no_narrator():
    registry = _registry()

    atomize_response = json.dumps(
        [["alice bought bread", "alice and bob argued over bread"]], ensure_ascii=False
    )
    assign_response = json.dumps([["alice"], ["alice", "bob"]], ensure_ascii=False)
    llm = FakeLLM(fn=_routed_fake(atomize_response, assign_response))
    shared = _new_shared(llm)
    warnings: list[str] = []

    state = await _run_sediment_pass_atomic(llm, shared, [_chunk("正文")], registry, "", warnings)

    # Registry is NOT mutated with a narrator/catch-all role any more.
    assert not any(loc.get("id") == NARRATOR_ID for loc in registry["locations"])

    entries = shared.all_entries()
    assert len(entries) == 2
    by_text = {e["text"]: e for e in entries}
    assert by_text["alice bought bread"]["owners"] == ["alice"]
    assert sorted(by_text["alice and bob argued over bread"]["owners"]) == ["alice", "bob"]
    assert all(NARRATOR_ID not in e["owners"] for e in entries)

    assert state["alice"]["location"] == "loc1"
    assert warnings == []


# ----------------------------------------------------------------------
# 4. EVENT AFFILIATION: fragments in the same event are affiliated with
#    each other; fragments in different events are not.
# ----------------------------------------------------------------------


async def test_event_affiliation_links_same_event_not_cross_event():
    registry = _registry()

    atomize_response = json.dumps(
        [["event A fragment one", "event A fragment two"], ["event B fragment one"]],
        ensure_ascii=False,
    )

    # Per-event assign (Task F2.1): two events -> two separate assign calls,
    # each seeing only its own fragment(s) -- route the fake by content.
    def fake(prompt, system=None):
        if "[atomize]" in prompt:
            return atomize_response
        if "[assign]" in prompt:
            if "event A fragment one" in prompt:
                return json.dumps([["alice"], ["bob"]], ensure_ascii=False)
            return json.dumps([["alice"]], ensure_ascii=False)
        if "出场" in prompt:
            return ROSTER_RESPONSE
        return "[]"

    llm = FakeLLM(fn=fake)
    shared = _new_shared(llm)
    warnings: list[str] = []

    await _run_sediment_pass_atomic(llm, shared, [_chunk("正文")], registry, "", warnings)

    entries = shared.all_entries()
    by_text = {e["text"]: e for e in entries}
    a1 = by_text["event A fragment one"]
    a2 = by_text["event A fragment two"]
    b1 = by_text["event B fragment one"]

    assert a2["id"] in shared.get_affiliations(a1["id"])
    assert a1["id"] in shared.get_affiliations(a2["id"])

    # Different event -> not affiliated with either A fragment.
    assert b1["id"] not in shared.get_affiliations(a1["id"])
    assert b1["id"] not in shared.get_affiliations(a2["id"])
    assert shared.get_affiliations(b1["id"]) == []


# ----------------------------------------------------------------------
# 5. THOROUGH OWNERS: a fragment naming 3 entities (2 characters + 1
#    location) gets all 3 as owners.
# ----------------------------------------------------------------------


async def test_thorough_owners_fragment_naming_three_entities():
    registry = _registry()

    atomize_response = json.dumps(
        [["alice and bob met at loc1 and discussed the letter"]], ensure_ascii=False
    )
    assign_response = json.dumps([["alice", "bob", "loc1"]], ensure_ascii=False)
    llm = FakeLLM(fn=_routed_fake(atomize_response, assign_response))
    shared = _new_shared(llm)
    warnings: list[str] = []

    await _run_sediment_pass_atomic(llm, shared, [_chunk("正文")], registry, "", warnings)

    entries = shared.all_entries()
    assert len(entries) == 1
    assert sorted(entries[0]["owners"]) == ["alice", "bob", "loc1"]


# ----------------------------------------------------------------------
# 6. No story_time is stored on deposited memories any more -- only
#    story_order.
# ----------------------------------------------------------------------


async def test_no_story_time_stored_only_story_order():
    registry = _registry()
    atomize_response = json.dumps([["alice did something notable"]], ensure_ascii=False)
    assign_response = json.dumps([["alice"]], ensure_ascii=False)
    llm = FakeLLM(fn=_routed_fake(atomize_response, assign_response))
    shared = _new_shared(llm)
    warnings: list[str] = []

    await _run_sediment_pass_atomic(llm, shared, [_chunk("正文", title="第一回")], registry, "", warnings)

    entries = shared.all_entries()
    assert len(entries) == 1
    meta = entries[0]["meta"]
    assert meta["story_order"] == 0
    assert "story_time" not in meta


# ----------------------------------------------------------------------
# 7. Token cap 64 respected.
# ----------------------------------------------------------------------


async def test_overlength_fragment_truncated_to_64_tokens():
    registry = _registry()
    long_fragment = "word " * 120
    assert count_tokens(long_fragment) > 64

    atomize_response = json.dumps([[long_fragment]], ensure_ascii=False)
    assign_response = json.dumps([["alice"]], ensure_ascii=False)
    llm = FakeLLM(fn=_routed_fake(atomize_response, assign_response))
    shared = _new_shared(llm)
    warnings: list[str] = []

    await _run_sediment_pass_atomic(llm, shared, [_chunk("正文")], registry, "", warnings)

    entries = shared.all_entries()
    assert len(entries) == 1
    assert count_tokens(entries[0]["text"]) <= 64
    assert entries[0]["text"] != long_fragment.strip()


# ----------------------------------------------------------------------
# 8. Assign batching: a chunk with >20 fragments issues multiple assign
#    calls.
# ----------------------------------------------------------------------


async def test_assign_batches_at_most_20_fragments_per_call():
    registry = _registry()
    n_fragments = 25
    fragments = [f"fragment number {i}" for i in range(n_fragments)]
    atomize_response = json.dumps([fragments], ensure_ascii=False)  # one big event

    assign_call_batches: list[int] = []

    def fake(prompt, system=None):
        if "[atomize]" in prompt:
            return atomize_response
        if "[assign]" in prompt:
            # Count how many fragments were listed in THIS assign call by
            # counting numbered lines "N: ..." in the prompt.
            frag_block = prompt.split("Fragments:\n", 1)[1]
            batch_len = len([ln for ln in frag_block.splitlines() if ln.strip()])
            assign_call_batches.append(batch_len)
            return json.dumps([["alice"] for _ in range(batch_len)], ensure_ascii=False)
        if "出场" in prompt:
            return ROSTER_RESPONSE
        return "[]"

    llm = FakeLLM(fn=fake)
    shared = _new_shared(llm)
    warnings: list[str] = []

    await _run_sediment_pass_atomic(llm, shared, [_chunk("正文")], registry, "", warnings)

    assert len(assign_call_batches) == 2
    assert assign_call_batches == [20, 5]

    assign_calls = [c for c in llm.calls if "[assign]" in c[1]]
    assert len(assign_calls) == 2

    entries = shared.all_entries()
    assert len(entries) == n_fragments


# ----------------------------------------------------------------------
# 9. No-owner fragment falls back to the chunk location; truly ownerless
#    (no location either) is dropped with a warning.
# ----------------------------------------------------------------------


async def test_no_owner_fragment_falls_back_to_chunk_location():
    registry = _registry()
    atomize_response = json.dumps([["something happened near the market"]], ensure_ascii=False)
    assign_response = json.dumps([[]], ensure_ascii=False)  # empty owner list from assign
    llm = FakeLLM(fn=_routed_fake(atomize_response, assign_response, roster_response=ROSTER_RESPONSE))
    shared = _new_shared(llm)
    warnings: list[str] = []

    await _run_sediment_pass_atomic(llm, shared, [_chunk("正文")], registry, "", warnings)

    entries = shared.all_entries()
    assert len(entries) == 1
    assert entries[0]["owners"] == ["loc1"]
    assert NARRATOR_ID not in entries[0]["owners"]
    assert any("falling back to chunk location" in w for w in warnings)


async def test_truly_ownerless_fragment_dropped_with_warning():
    registry = _registry()
    atomize_response = json.dumps([["something happened with no clear owner"]], ensure_ascii=False)
    assign_response = json.dumps([[]], ensure_ascii=False)
    llm = FakeLLM(
        fn=_routed_fake(atomize_response, assign_response, roster_response=ROSTER_RESPONSE_NO_LOCATION)
    )
    shared = _new_shared(llm)
    warnings: list[str] = []

    await _run_sediment_pass_atomic(llm, shared, [_chunk("正文")], registry, "", warnings)

    entries = shared.all_entries()
    assert entries == []
    assert any(
        "had no owner and no chunk location to fall back to; dropped" in w for w in warnings
    )
    assert not any(NARRATOR_ID in w for w in warnings)


def test_ensure_narrator_role_still_defined_but_never_auto_invoked():
    """`_ensure_narrator_role` is kept defined (Task F2 change #1 says: leave
    the helper for any other caller that still wants it) but the atomic
    pipeline itself never calls it any more -- see the narrator-absence
    assertions throughout this file."""
    registry = _registry()
    assert _ensure_narrator_role(registry) is True
    assert any(loc["id"] == NARRATOR_ID for loc in registry["locations"])
    assert _ensure_narrator_role(registry) is False  # idempotent, no duplicate


def test_chunk_location_ids_helper_dedupes_in_first_seen_order():
    registry = {
        "characters": [{"id": "a", "name": "甲", "aliases": []}],
        "locations": [
            {"id": "loc1", "name": "集市", "aliases": []},
            {"id": "loc2", "name": "皇宫", "aliases": []},
        ],
        "carriers": [],
    }
    resolvers = _RegistryResolvers(registry)
    state_updates = [
        {"id": "a", "location": "loc2", "alive": True},
        {"id": "a", "location": "loc1", "alive": True},
        {"id": "a", "location": "loc2", "alive": True},
    ]
    assert _chunk_location_ids(state_updates, resolvers) == ["loc2", "loc1"]
    assert _chunk_location_ids([], resolvers) == []


# ----------------------------------------------------------------------
# 10. Two chunks: deposits stay in story order (flat_idx*1000+i), even
#     though the read-only LLM phase is gathered concurrently across
#     chunks.
# ----------------------------------------------------------------------


async def test_two_chunks_deposit_order_matches_story_order():
    registry = _registry()

    def fake(prompt, system=None):
        if "[atomize]" in prompt:
            if "ALPHA" in prompt:
                return json.dumps([["alpha fragment one", "alpha fragment two"]], ensure_ascii=False)
            return json.dumps([["beta fragment one"]], ensure_ascii=False)
        if "[assign]" in prompt:
            if "alpha fragment one" in prompt:
                return json.dumps([["alice"], ["bob"]], ensure_ascii=False)
            return json.dumps([["alice"]], ensure_ascii=False)
        if "出场" in prompt:
            return json.dumps(
                {"characters": [], "state_updates": [], "story_time": None}, ensure_ascii=False
            )
        return "[]"

    llm = FakeLLM(fn=fake)
    shared = _new_shared(llm)
    warnings: list[str] = []

    chunks = [_chunk("ALPHA chunk text", flat_idx=0, title=None), _chunk("BETA chunk text", flat_idx=1, title=None)]
    await _run_sediment_pass_atomic(llm, shared, chunks, registry, "", warnings)

    entries = sorted(shared.all_entries(), key=lambda e: e["meta"]["story_order"])
    assert [e["meta"]["story_order"] for e in entries] == [0, 1, 1000]
    assert [e["text"] for e in entries] == [
        "alpha fragment one",
        "alpha fragment two",
        "beta fragment one",
    ]
    assert warnings == []


# ----------------------------------------------------------------------
# 11. Language passthrough: English atomize output is stored verbatim (no
#     forced translation) -- the pipeline just passes text through.
# ----------------------------------------------------------------------


async def test_english_fragments_stored_verbatim_no_translation():
    registry = _registry()
    english_fragment = "Napoleon crossed the river at dawn."
    atomize_response = json.dumps([[english_fragment]], ensure_ascii=False)
    assign_response = json.dumps([["alice"]], ensure_ascii=False)
    llm = FakeLLM(fn=_routed_fake(atomize_response, assign_response))
    shared = _new_shared(llm)
    warnings: list[str] = []

    await _run_sediment_pass_atomic(llm, shared, [_chunk("Some English source text.")], registry, "", warnings)

    entries = shared.all_entries()
    assert len(entries) == 1
    assert entries[0]["text"] == english_fragment


# ----------------------------------------------------------------------
# 12. Assign length-mismatch and unknown-owner-id degrade gracefully
#     (falling back to chunk location, never to narrator).
# ----------------------------------------------------------------------


async def test_assign_length_mismatch_pads_defensively_falls_back_to_location():
    registry = _registry()
    atomize_response = json.dumps(
        [["fragment one", "fragment two", "fragment three"]], ensure_ascii=False
    )
    # Only ONE owner list for THREE fragments.
    assign_response = json.dumps([["alice"]], ensure_ascii=False)
    llm = FakeLLM(fn=_routed_fake(atomize_response, assign_response))
    shared = _new_shared(llm)
    warnings: list[str] = []

    await _run_sediment_pass_atomic(llm, shared, [_chunk("正文")], registry, "", warnings)

    entries = shared.all_entries()
    assert len(entries) == 3
    by_text = {e["text"]: e for e in entries}
    assert by_text["fragment one"]["owners"] == ["alice"]
    # Padded fragments fall back to the chunk location (loc1), not narrator.
    assert by_text["fragment two"]["owners"] == ["loc1"]
    assert by_text["fragment three"]["owners"] == ["loc1"]
    assert any("padding/truncating" in w for w in warnings)
    assert not any(NARRATOR_ID in w for w in warnings)


async def test_assign_unknown_owner_id_dropped_falls_back_to_location():
    registry = _registry()
    atomize_response = json.dumps([["fragment with a bogus owner"]], ensure_ascii=False)
    assign_response = json.dumps([["ghost_id"]], ensure_ascii=False)
    llm = FakeLLM(fn=_routed_fake(atomize_response, assign_response))
    shared = _new_shared(llm)
    warnings: list[str] = []

    await _run_sediment_pass_atomic(llm, shared, [_chunk("正文")], registry, "", warnings)

    entries = shared.all_entries()
    assert len(entries) == 1
    # Unknown ref dropped -> no valid owners left -> chunk-location fallback.
    assert entries[0]["owners"] == ["loc1"]
    assert any("unknown id" in w and "ghost_id" in w for w in warnings)


async def test_assign_call_invalid_json_falls_back_to_location_for_whole_chunk():
    registry = _registry()
    atomize_response = json.dumps([["fragment one", "fragment two"]], ensure_ascii=False)
    assign_response = "not json at all"
    llm = FakeLLM(fn=_routed_fake(atomize_response, assign_response))
    shared = _new_shared(llm)
    warnings: list[str] = []

    await _run_sediment_pass_atomic(llm, shared, [_chunk("正文")], registry, "", warnings)

    entries = shared.all_entries()
    assert len(entries) == 2
    assert all(e["owners"] == ["loc1"] for e in entries)
    assert any("assign pass failed" in w for w in warnings)


# ----------------------------------------------------------------------
# 12b. Task F2.1 fix #2 -- PER-EVENT assign: group-ref resolution needs
# whole-scene context, and two events issue two separate assign calls each
# seeing only their own fragments.
# ----------------------------------------------------------------------

SANGUO_REGISTRY = {
    "characters": [
        {"id": "liubei", "name": "刘备", "aliases": [], "profile": ""},
        {"id": "guanyu", "name": "关羽", "aliases": [], "profile": ""},
        {"id": "zhangfei", "name": "张飞", "aliases": [], "profile": ""},
    ],
    "locations": [{"id": "taoyuan", "name": "桃园", "aliases": [], "profile": ""}],
    "carriers": [],
}


async def test_group_ref_fragment_resolved_via_whole_event_context():
    """The real 桃园结义 failure this task fixes: a fragment that still says
    "三人结为兄弟" (an unresolved group reference) must be assignable to
    liubei/guanyu/zhangfei because the assign call for its event receives
    ALL of that event's fragments together (Task F2.1 fix #2) -- including
    the sibling fragment that actually names the three. The fake assign
    function below only returns the correct owners if BOTH fragments are
    present in the same call's Fragments list, proving per-event context is
    actually passed rather than each fragment being assigned in isolation."""
    registry = copy.deepcopy(SANGUO_REGISTRY)
    resolvers = _RegistryResolvers(registry)
    warnings: list[str] = []

    atomize_response = json.dumps(
        [["刘备、关羽、张飞在桃园相遇", "三人结为兄弟"]], ensure_ascii=False
    )
    assign_calls: list[str] = []

    def fake(prompt, system=None):
        if "[atomize]" in prompt:
            return atomize_response
        if "[assign]" in prompt:
            assign_calls.append(prompt)
            # Only resolvable if the call sees BOTH sibling fragments.
            if "刘备、关羽、张飞在桃园相遇" in prompt and "三人结为兄弟" in prompt:
                return json.dumps(
                    [["liubei", "guanyu", "zhangfei"], ["liubei", "guanyu", "zhangfei"]],
                    ensure_ascii=False,
                )
            return json.dumps([[], []], ensure_ascii=False)
        if "出场" in prompt:
            return ROSTER_RESPONSE_NO_LOCATION
        return "[]"

    llm = FakeLLM(fn=fake)
    result = await _process_chunk_atomic(llm, _chunk("正文"), registry, resolvers, "", warnings)

    assert len(assign_calls) == 1  # one event -> one assign call
    events = result["events"]
    assert len(events) == 1
    owners_by_text = {f: o for f, o in events[0]}
    assert sorted(owners_by_text["三人结为兄弟"]) == ["guanyu", "liubei", "zhangfei"]
    assert sorted(owners_by_text["刘备、关羽、张飞在桃园相遇"]) == ["guanyu", "liubei", "zhangfei"]


async def test_two_events_issue_two_separate_assign_calls_each_own_fragments():
    """Per-event assign restructure: TWO events -> TWO assign calls, and
    each call's Fragments section contains ONLY that event's own
    fragments (never a sibling event's)."""
    registry = _registry()
    resolvers = _RegistryResolvers(registry)
    warnings: list[str] = []

    atomize_response = json.dumps(
        [["alpha event fragment"], ["beta event fragment one", "beta event fragment two"]],
        ensure_ascii=False,
    )
    assign_calls: list[str] = []

    def fake(prompt, system=None):
        if "[atomize]" in prompt:
            return atomize_response
        if "[assign]" in prompt:
            assign_calls.append(prompt)
            if "alpha event fragment" in prompt:
                return json.dumps([["alice"]], ensure_ascii=False)
            return json.dumps([["alice"], ["bob"]], ensure_ascii=False)
        if "出场" in prompt:
            return ROSTER_RESPONSE
        return "[]"

    llm = FakeLLM(fn=fake)
    result = await _process_chunk_atomic(llm, _chunk("正文"), registry, resolvers, "", warnings)

    assert len(assign_calls) == 2
    alpha_call = next(c for c in assign_calls if "alpha event fragment" in c)
    beta_call = next(c for c in assign_calls if "beta event fragment one" in c)
    # Each call's Fragments list is scoped to its own event only.
    assert "beta event fragment" not in alpha_call.split("Fragments:\n", 1)[1]
    assert "alpha event fragment" not in beta_call.split("Fragments:\n", 1)[1]

    events = result["events"]
    assert len(events) == 2
    assert events[0] == [("alpha event fragment", ["alice"])]
    assert dict(events[1]) == {"beta event fragment one": ["alice"], "beta event fragment two": ["bob"]}


# ----------------------------------------------------------------------
# 12c. Task F2.1 fix #1 (code-side heuristic half) -- background/authorial
# exposition is dropped like a heading/marker, without over-dropping a
# concrete event that merely mentions a dynasty.
# ----------------------------------------------------------------------


def test_is_background_exposition_fragment_detects_recap_not_concrete_mention():
    assert _is_background_exposition_fragment("周末七国分争,至於秦并六国,一统天下")
    assert _is_background_exposition_fragment("汉朝自高祖刘邦斩白蛇起义一统天下")
    assert _is_background_exposition_fragment("话说天下大势,分久必合,合久必分")
    # A concrete event that merely mentions a dynasty/era must NOT be dropped.
    assert not _is_background_exposition_fragment("刘备,西汉中山靖王刘胜之后,生于涿郡")
    assert not _is_background_exposition_fragment("关羽在桃园与刘备张飞结拜")


async def test_background_exposition_fragment_dropped_concrete_event_kept():
    registry = _registry()
    resolvers = _RegistryResolvers(registry)
    warnings: list[str] = []

    atomize_response = json.dumps(
        [["汉朝自高祖刘邦斩白蛇起义一统天下", "alice met bob at the market"]],
        ensure_ascii=False,
    )
    assign_response = json.dumps([["alice", "bob"]], ensure_ascii=False)
    llm = FakeLLM(fn=_routed_fake(atomize_response, assign_response))

    result = await _process_chunk_atomic(llm, _chunk("正文"), registry, resolvers, "", warnings)

    events = result["events"]
    assert len(events) == 1
    all_texts = [f for ev in events for f, _ in ev]
    assert "汉朝自高祖刘邦斩白蛇起义一统天下" not in all_texts
    assert "alice met bob at the market" in all_texts
    assert any("background-exposition fragment" in w for w in warnings)


# ----------------------------------------------------------------------
# 12d. Task F2.1 fix #3 -- EVENT-LOCAL fallback: an ownerless fragment
# prefers its OWN event's sibling-resolved location over the chunk's
# roster location (or any other chunk location), and only falls through to
# the chunk-wide location when its own event named none.
# ----------------------------------------------------------------------

MULTI_LOC_REGISTRY = {
    "characters": [{"id": "alice", "name": "甲", "aliases": [], "profile": ""}],
    "locations": [
        {"id": "loc1", "name": "集市", "aliases": [], "profile": ""},
        {"id": "loc2", "name": "皇宫", "aliases": [], "profile": ""},
        {"id": "loc3", "name": "校场", "aliases": [], "profile": ""},
        {"id": "loc4", "name": "驿站", "aliases": [], "profile": ""},
        {"id": "loc5", "name": "桃园", "aliases": [], "profile": ""},
    ],
    "carriers": [],
}


async def test_ownerless_fragment_prefers_own_event_location_over_chunk_locations():
    """Mirrors the real 桃园结义 failure: the chunk's roster references
    SEVERAL locations (loc1..loc4, like the real daxingshan/guangzong/
    luoyang/yingchuan bug), but this fragment's own EVENT resolved a
    sibling fragment to loc5 -- the ownerless fragment must get loc5 only,
    never the unrelated chunk-wide locations."""
    registry = copy.deepcopy(MULTI_LOC_REGISTRY)
    resolvers = _RegistryResolvers(registry)
    warnings: list[str] = []

    roster_response = json.dumps(
        {
            "characters": [],
            "state_updates": [
                {"id": "alice", "location": "loc1", "alive": True},
                {"id": "alice", "location": "loc2", "alive": True},
                {"id": "alice", "location": "loc3", "alive": True},
                {"id": "alice", "location": "loc4", "alive": True},
            ],
            "story_time": "t1",
        },
        ensure_ascii=False,
    )
    atomize_response = json.dumps(
        [["something happened at loc5", "a related but unowned happening at loc5"]],
        ensure_ascii=False,
    )
    assign_response = json.dumps([["loc5"], []], ensure_ascii=False)
    llm = FakeLLM(fn=_routed_fake(atomize_response, assign_response, roster_response=roster_response))

    result = await _process_chunk_atomic(llm, _chunk("正文"), registry, resolvers, "", warnings)

    events = result["events"]
    assert len(events) == 1
    owners_by_text = dict(events[0])
    assert owners_by_text["a related but unowned happening at loc5"] == ["loc5"]
    assert any("falling back to this event's own location" in w for w in warnings)
    assert not any("falling back to chunk location" in w for w in warnings)


async def test_ownerless_fragment_falls_through_to_chunk_location_when_event_has_none():
    """When the fragment's own event named NO location at all, fallback
    goes to the chunk's roster-derived location(s) -- the second-priority
    source, unchanged from Task F2."""
    registry = copy.deepcopy(MULTI_LOC_REGISTRY)
    resolvers = _RegistryResolvers(registry)
    warnings: list[str] = []

    roster_response = json.dumps(
        {
            "characters": [],
            "state_updates": [{"id": "alice", "location": "loc1", "alive": True}],
            "story_time": "t1",
        },
        ensure_ascii=False,
    )
    # Neither fragment in this event resolves to any location.
    atomize_response = json.dumps(
        [["alice did something", "something else happened with no owner"]], ensure_ascii=False
    )
    assign_response = json.dumps([["alice"], []], ensure_ascii=False)
    llm = FakeLLM(fn=_routed_fake(atomize_response, assign_response, roster_response=roster_response))

    result = await _process_chunk_atomic(llm, _chunk("正文"), registry, resolvers, "", warnings)

    events = result["events"]
    owners_by_text = dict(events[0])
    assert owners_by_text["something else happened with no owner"] == ["loc1"]
    assert any("falling back to chunk location" in w for w in warnings)


# ----------------------------------------------------------------------
# 13. Atomize failure skips the chunk's memories but keeps roster state.
# ----------------------------------------------------------------------


async def test_atomize_failure_skips_memories_but_keeps_roster_state():
    registry = _registry()

    def fake(prompt, system=None):
        if "出场" in prompt:
            return ROSTER_RESPONSE
        if "[atomize]" in prompt:
            return "not json at all"
        return "[]"

    llm = FakeLLM(fn=fake)
    shared = _new_shared(llm)
    warnings: list[str] = []

    state = await _run_sediment_pass_atomic(llm, shared, [_chunk("正文")], registry, "", warnings)

    assert shared.all_entries() == []
    assert state["alice"]["location"] == "loc1"
    assert any("atomize pass failed" in w for w in warnings)


# ----------------------------------------------------------------------
# 14. Roster failure still proceeds with atomize/assign (state
#     best-effort); no story_time fallback to store any more.
# ----------------------------------------------------------------------


async def test_roster_failure_still_proceeds_with_atomize_assign():
    registry = _registry()

    def fake(prompt, system=None):
        if "出场" in prompt:
            return "not json at all"
        if "[atomize]" in prompt:
            return json.dumps([["alice did something"]], ensure_ascii=False)
        if "[assign]" in prompt:
            return json.dumps([["alice"]], ensure_ascii=False)
        return "[]"

    llm = FakeLLM(fn=fake)
    shared = _new_shared(llm)
    warnings: list[str] = []

    state = await _run_sediment_pass_atomic(
        llm, shared, [_chunk("正文", title="第一回")], registry, "", warnings
    )

    entries = shared.all_entries()
    assert len(entries) == 1
    assert entries[0]["text"] == "alice did something"
    assert "story_time" not in entries[0]["meta"]
    # No state_updates were recorded (roster failed) -> empty state table.
    assert state == {}
    assert any("roster" in w and "chunk 0" in w for w in warnings)


# ----------------------------------------------------------------------
# 15. registry_only gate still returns after Pass 1, with the new atomic
#     default -- Pass 2 (and hence atomize/assign) never runs.
# ----------------------------------------------------------------------


SUMMARY_RESPONSE = json.dumps(
    {"summary": "s", "characters": ["甲"], "locations": ["集市"]}, ensure_ascii=False
)
REGISTRY_RESPONSE = json.dumps(REGISTRY, ensure_ascii=False)


async def test_registry_only_gate_with_default_atomic_detail(tmp_path):
    def fake(prompt, system=None):
        if "摘要" in prompt:
            return SUMMARY_RESPONSE
        if "注册表" in prompt:
            return REGISTRY_RESPONSE
        raise AssertionError(f"Pass 2 must not run under registry_only: {prompt[:50]!r}")

    llm = FakeLLM(fn=fake)
    out = str(tmp_path / "out.yaml")

    result = await extract_history(
        "正文" * 50, llm, out, embed_fn=afake_embed, chunk_chars=200, registry_only=True
    )

    assert result["registry"]["characters"][0]["id"] == "alice"
    # No narrator role injected -- that only ever happened inside Pass 2's
    # atomic sedimentation, which never runs under registry_only.
    assert not any(loc.get("id") == NARRATOR_ID for loc in result["registry"]["locations"])
    import os

    assert os.path.exists(out + ".registry.json")


# ----------------------------------------------------------------------
# 16. Full extract_history pipeline with the DEFAULT detail (no detail=
#     kwarg passed) exercises the atomic path end-to-end and proves no
#     per-character (沉淀/补漏) extraction call, and no narrator role,
#     remains in it.
# ----------------------------------------------------------------------


async def test_extract_history_default_detail_is_atomic_end_to_end(tmp_path):
    text = ("甲乙" * 90) + ("乙甲" * 85)
    assert 300 < len(text) < 400  # chunk_chars=200 below forces exactly 2 chunks

    kickoff_response = json.dumps(
        [{"to": ["alice"], "kind": "system", "content": "start"}], ensure_ascii=False
    )

    def make_fake():
        def fake(prompt, system=None):
            if "摘要" in prompt:
                return SUMMARY_RESPONSE
            if "注册表" in prompt:
                return REGISTRY_RESPONSE
            if "出场" in prompt:
                return ROSTER_RESPONSE
            if "[atomize]" in prompt:
                return json.dumps([["alice and bob crossed paths"]], ensure_ascii=False)
            if "[assign]" in prompt:
                return json.dumps([["alice", "bob"]], ensure_ascii=False)
            if "起始" in prompt:
                return kickoff_response
            if "Which existing candidate" in prompt:
                return "0"
            return "[]"

        return fake

    llm = FakeLLM(fn=make_fake())
    out = str(tmp_path / "out.yaml")

    cfg = await extract_history(text, llm, out, embed_fn=afake_embed, chunk_chars=200)

    # No detail= was passed -- this exercises the new default end-to-end.
    for _, prompt, _ in llm.calls:
        assert "沉淀" not in prompt
        assert "补漏" not in prompt

    import os

    assert os.path.exists(out)
    assert os.path.exists(out + ".ltm.json")

    agent_ids = {a["id"] for a in cfg["agents"]}
    # Narrator role is GONE -- Task F2 change #1.
    assert NARRATOR_ID not in agent_ids
