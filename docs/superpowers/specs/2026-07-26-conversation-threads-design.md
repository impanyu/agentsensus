# Kernel-held per-interlocutor conversation threads — Design

Date: 2026-07-26
Status: approved (brainstorming)
Repo: agentsensus
Scope: **Effort B** — the messaging-layer redesign. Effort A (boundary-state placement) already landed.

## Problem / motivation

Today each agent owns a single FIFO `inbox` (`STM.inbox`, an `asyncio.Queue`); the view exposes only `inbox_size` + an `inbox_head` preview; `pop_message`/`peek_inbox` consume it. This flat queue:
- has no per-interlocutor structure — an agent can't see "my conversation with X",
- gates `say` on co-location, so an agent can only ever talk to whoever it happens to be co-located with (which, combined with imperfect placement, forced canonically-implausible groupings),
- has no notion of distance/latency — remote communication is impossible except as an instant `broadcast`.

We want a messaging model where each agent maintains, in the kernel, a conversation thread with every other party it talks to (like email/WeChat), can talk to co-located agents instantly and remote agents via delayed "letters," and where all interaction records (including with locations and readable carriers) are unified into these threads.

## Decisions (locked in brainstorming)

| topic | decision |
|---|---|
| Storage | The inbox moves to the **kernel** as per-interlocutor **conversation threads**; `STM.inbox` is removed. |
| View | **Email-style roster**: a compact conversation list, NOT full histories inline. |
| Roster scope | **Active conversations (≥1 message) + currently co-located reachable agents.** Remote never-contacted parties are not listed; you write to them by id. |
| Read | A new **`read_thread(target)`** action returns a thread's messages and marks it read. Replaces `pop_message`/`peek_inbox`. |
| Send | **`say` and `broadcast` MERGE into one `say`**: `say(targets?, content, wake?)`. `targets` optional, **default = all co-located characters**; **delay = worldmap distance per target** (co-located → 0 / instant, remote → distance ticks, like a letter); **wakes recipients** (`wake` default True). `broadcast` is removed. |
| Delay | **worldmap distance** between sender's and each recipient's location at send time (same distances `move` uses); unroutable → `default_distance`. Recipient moving mid-flight is delivered per send-time distance (no chasing). |
| Locations & readables | `observe` / `act_on(env)` / `read(carrier)` keep their exact current synchronous semantics, but each interaction is **logged as a message into the agent's thread with that env/carrier** — unifying all interaction history into threads. |

## Architecture

### New: `society/conversations.py`
- `class Thread`: ordered `list[Message]` (or lightweight message records), an `unread: int`, and a `meta` cache `{kind, colocated}` refreshed at view time. Methods: `append(msg)`, `mark_read() -> None`, `recent(k) -> list`, `to_dict()/from_dict()` for persistence.
- `class ConversationStore`: `{agent_id: {other_id: Thread}}`. Methods:
  - `record(owner, other, msg, *, unread_delta=1)` — append `msg` to `owner`'s thread with `other`, bump unread.
  - `roster(owner, colocated_ids, agents) -> list[dict]` — build the view roster: every active thread `{other, kind, colocated, unread, last_preview}`, plus co-located reachable agents not yet threaded (`unread=0`). Sorted deterministically (unread desc, then id).
  - `read(owner, other, k) -> list[dict]` — the last-k messages of the thread, marking it read.
  - `export()/restore()` for checkpointing.

The kernel holds one `ConversationStore` (`self.conversations`) and no longer relies on `STM.inbox`.

### Message routing
A `say` (the unified send) from `sender` to each `target`:
1. compute `delay = 0 if same location else worldmap.distance(sender_loc, target_loc)` (unroutable → `default_distance`);
2. enqueue a pending delivery `{msg, recipient: target, deliver_at: tick + delay}`;
3. On the tick where `deliver_at <= tick`: `conversations.record(target, sender, msg)` (recipient's thread, unread+1) AND `conversations.record(sender, target, msg, unread_delta=0)` (sender's own copy, already "read"); if `msg.wake`, clear the recipient's `waiting_until`.

Co-located targets (`delay=0`) deliver next tick — identical timing to today's `say`. Default `targets` (omitted) = all currently co-located characters.

`observe`/`act_on`/`read` additionally call `conversations.record(actor, target_env_or_carrier, <a synthetic interaction message>, unread_delta=0)` so the actor's thread with that place/carrier logs what it did/observed/read. These stay synchronous and unchanged in their return values.

### View
`_build_agent_view` drops `inbox_size`/`inbox_head` and adds:
- `conversations`: `conversations.roster(agent.id, colocated_ids, self.agents)`.
Everything else (`colocated`, `known_locations`, `goal_hint`, `remember_hint`) unchanged.

### Actions (delta to the catalog)
- **REMOVE** `broadcast`, `pop_message`, `peek_inbox`.
- **CHANGE** `say`: `{targets?: list[str], content: str, wake?: bool}` — targets optional (default local-all), wake default True, per-target distance delay, no co-location gate (remote allowed). `gesture` stays as the non-verbal twin with identical routing.
- **ADD** `read_thread`: `{target: str, k?: int}` → returns `[{sender, kind, content, tick}]` (last k, default e.g. 10) and marks that thread read.

### Eligibility / awake model
Unchanged. `is_eligible` still keys on `waiting_until`/archived/transit/kind. A delivered `wake=True` message clears `waiting_until` in the delivery step (as `deliver_pending` does today).

### Persistence
Checkpoint `self.conversations.export()`; restore on resume. Remove `STM.inbox` from the checkpoint schema. (`society/persistence.py` — its `SharedMemory`-hardcoding is out of scope here; only the inbox→conversations swap.)

## Data flow

```
say(targets?, content, wake?)  (default targets = co-located characters)
   │  per target: delay = 0 (co-located) | worldmap.distance (remote)
   ▼
pending delivery {msg, recipient, deliver_at = tick + delay}
   │  each tick: due messages ->
   ▼
conversations.record(recipient, sender, msg)  (unread+1; wake clears waiting_until)
conversations.record(sender, recipient, msg)  (own copy, read)
   │
   ▼
view["conversations"] = roster(active threads + co-located)  ── agent picks a thread
   │
read_thread(target, k) -> last-k messages, marks read
```

## Testing

- **Unified say**: co-located target → delivered next tick (delay 0), appears in BOTH sender's and recipient's thread, recipient unread+1 & woken; omitted `targets` → all co-located characters receive it.
- **Remote delay**: a target at distance d → not delivered until tick+d, then appears in the thread; a nearer target arrives sooner (distance-ordered); unroutable pair → `default_distance`.
- **Recipient moves mid-flight**: delivered on the original send-time schedule (no chasing), to the recipient's thread.
- **read_thread**: returns last-k messages of the named thread and sets its unread to 0; a thread with no messages → empty list.
- **Roster**: lists active threads (unread + preview) and co-located-but-unthreaded agents; excludes remote never-contacted parties; deterministic order.
- **Locations/readables**: `act_on`/`read`/`observe` return values unchanged AND log a message into the actor's thread with that env/carrier.
- **Removed actions**: `broadcast`/`pop_message`/`peek_inbox` are gone from the catalog/validator; scenarios' kickoff and tests updated to the new `say`/`read_thread`.
- **Persistence**: conversations round-trip through export/restore; a restored kernel resumes with the same threads/unread.
- **Skill docs**: `actions_skill_{zh,en}.md` updated — one `say` (local instant / remote letter), `read_thread`, the roster in the view; `broadcast`/`pop_message`/`peek_inbox` removed.

## Risks / open points

- **Broad blast radius**: touches kernel messaging, STM (inbox removal), the view, the action catalog + validator, skill docs, persistence, and existing tests/scenarios that use `broadcast`/`pop_message`. Sequenced in the plan so the store lands first, then routing, then the action/view swap, then doc/scenario cleanup.
- **N² threads**: threads are created lazily (only on first message), and the roster shows only active + co-located, so storage and context stay bounded even at 187 agents.
- **Default-targets semantics**: `say` with omitted `targets` = all co-located characters at send time; if none are co-located, it's a no-op that still records nothing (or errors — pick no-op, logged).
- **Wake noise**: `say` wakes recipients by default; a large remote letter with `wake=True` wakes many on arrival. Agents may pass `wake=False`. Acceptable per the "唤醒接收方" decision.
