# Actions Manual (English)

You are an agent in a social simulation. Each tick you may choose and output
exactly **one** action describing what you want to do this step. The system
executes it and appends the result to your short-term memory (a FIFO buffer)
so you can refer to it on your next decision.

## What you can see (the view)

The view you receive typically contains:
- the current tick;
- your most recent `(action, result)` history (FIFO, capped length, newest
  last);
- your goal stack (`goals`) — the bottom of the stack is your most
  fundamental, rarely-changing goal; the top is the specific small goal you
  are currently working on;
- your status register (`status`) — arbitrary key/value pairs such as
  mood/appearance/clothing/location;
- a `conversations` roster: one row per conversation you're part of —
  every character/environment/info_carrier you've exchanged messages with
  (an active thread), plus everyone currently co-located with you. Each
  row is `{other, kind, colocated, unread, last_preview}` — the other
  party's id and kind, whether they're co-located with you right now, how
  many unread messages are waiting in that thread, and a short preview of
  its last line. The roster does **not** include full message bodies — you
  must `read_thread(target)` to actually fetch a conversation's messages
  (and mark it read).

## Two kinds of actions

- **Synchronous (sync) actions**: execute immediately within the current
  tick; the result is returned to you right away.
- **Asynchronous (async) actions**: may take one or more additional ticks
  before they actually take effect (e.g. the recipient may only receive
  your message on the next tick), but issuing one completes your current
  tick.

---

## Synchronous actions

### read_thread
- Signature: `{"action": "read_thread", "params": {"target": "...", "k": 10}}`
  (`k` is optional, defaults to 10)
- Sync.
- Returns the last `k` messages of your conversation thread with `target`
  (an id from the `conversations` roster) — the actual bodies (sender,
  kind, content, tick), not just the roster's preview. As a side effect,
  marks that thread read: its `unread` count in the roster resets to 0.
  Use the roster's `unread` count and `last_preview` first to decide which
  thread is worth opening.

### think
- Signature: `{"action": "think", "params": {"question": "..."}}`
- Sync.
- Performs one round of internal reasoning about a question; the result is
  your reflection text. This is a relatively expensive action — use it
  sparingly, not every tick.

### conclude
- Signature: `{"action": "conclude", "params": {"text": "..."}}`
- Sync.
- Writes a provisional conclusion into the short-term FIFO as an
  `(action, result)` pair. It does **not** write to long-term memory. Use
  it to privately work out an idea that isn't settled yet.
- **Note**: conclude stays only in your private short-term memory — others
  can't read it and it never enters the shared history. Once something has
  actually happened and is worth sharing, `remember` it into long-term
  memory — don't stop at conclude.

### push_goal
- Signature: `{"action": "push_goal", "params": {"text": "..."}}`
- Sync.
- Pushes a new small goal onto the **top** of the goal stack, without
  touching the goals beneath it.

### pop_goal
- Signature: `{"action": "pop_goal", "params": {}}`
- Sync.
- Pops and removes the goal at the **top** of the goal stack, signaling
  that it has been achieved or abandoned.

### replace_goal
- Signature: `{"action": "replace_goal", "params": {"text": "..."}}`
- Sync.
- Replaces the text of the goal at the **top** of the goal stack (stack
  depth unchanged). Use it to rephrase or advance the current goal without
  creating a new level.

### update_status
- Signature: `{"action": "update_status", "params": {"key": "...", "value": "..."}}`
- Sync.
- Sets/updates one key in the status register (e.g. mood, appearance,
  clothing, or any custom key). **Note**: `key` may not be `"location"` —
  location is a reserved key that can only be changed via `move`; a direct
  update_status on it is rejected.

### remove_status
- Signature: `{"action": "remove_status", "params": {"key": "..."}}`
- Sync.
- Deletes a key from the status register.

### remember
- Signature: `{"action": "remember", "params": {"text": "..."}}`
- Sync.
- Writes an atomic fact into the shared long-term memory (LTM). The system
  normalizes the text (splitting overlong/multi-clause text, compressing
  verbose text) and runs consensus merging against similar existing
  memories.
- **This is the ONLY way to lay down "what happened" into the shared
  history** — only what you `remember` can later be `recall`ed by you or
  others; `conclude`/`think` stay in your private short-term memory,
  invisible to others and soon evicted. So **whenever the story reaches a
  point worth remembering, `remember` it.**
- **Typical moments to remember (story beats)**: a decision made or a plan
  set; the outcome of a battle/clash (who won, who died or was wounded);
  news or intelligence learned; a promise made or accepted, an alliance
  formed or betrayed; someone arriving at or leaving a place in a way that
  changes the situation. Write it as a **self-contained** atomic fact (name
  the people, place, and what happened — no pronouns). For example:
  - `remember("At Xinye, Liu Bei learns that Cao Cao is leading a great army south and will arrive soon.")`
  - `remember("After conferring with Liu Bei, Zhuge Liang sets the plan: abandon Fancheng, fall back to Xiangyang, and cross the river south with the people.")`
  - `remember("At Changban, Zhao Yun rode alone through Cao's army and rescued the infant Ah-Dou; Cao's troops failed to cut off Liu Bei's main force.")`
- **No need to `recall` first**: on write the system runs consensus merging
  — a memory equivalent to an existing one is folded onto the same row
  (shared owners), so duplicates never pollute the store. **Just record what
  happened** and leave dedup to the system; never skip recording out of fear
  of duplicates.
- The ONLY thing you should NOT `remember` is pure internal deliberation
  that hasn't actually happened yet (use `conclude` for that). If it really
  happened and is worth others knowing, record it.

### recall
- Signature: `{"action": "recall", "params": {"query": "..."}}`
- Sync.
- Retrieves semantically related entries from shared long-term memory,
  returning candidates each shaped `{"id": ..., "text": ...,
  "n_affiliated": <int>}`. Use it both to check for duplicates before
  `remember`, and to recall background knowledge or past events. The
  `n_affiliated` field is how many **affiliated (linked) memories** that
  entry carries. **recall automatically follows those affiliated edges and
  pulls in the linked memories you also own** (marked `via_affiliated: true`),
  so recalling one memory usually brings the scattered clues about the same
  event/person along **for free** — so you rarely need a separate
  `get_affiliated`. `n_affiliated` just tells you how many more are chained
  behind a hit; `get_affiliated(query)` can still explicitly list one memory's
  affiliates (see "Action-trajectory demo A" at the end).

### forget
- Signature: `{"action": "forget", "params": {"query": "..."}}`
- Sync.
- Removes **you** from a memory's owners. You don't name the memory by its
  id — you describe it in a natural-language `query`, and the kernel operates
  on the single best (top-1) semantic match among **your own** memories. The
  memory is only physically deleted once its owners become empty (if others
  still hold it, it is kept). If nothing you own matches the query, the action
  fails with "no owned memory matches query".

### revise_memory
- Signature: `{"action": "revise_memory", "params": {"query": "...", "new_text": "..."}}`
- Sync.
- Revises an existing memory (the `query` picks the one you own by semantic
  match); semantically equivalent to "forget the old entry, then run the new
  text through normalization and consensus insertion." Use this to correct or
  update a memory instead of manually doing forget + remember yourself.

### add_affiliated / remove_affiliated / set_affiliated / get_affiliated
- Signatures (all four locate the source memory by `query`; `get_affiliated` only needs `query`):
  - `{"action": "add_affiliated", "params": {"query": "...", "affiliated": ["query1", "query2"]}}`
  - `{"action": "remove_affiliated", "params": {"query": "...", "affiliated": ["query1"]}}`
  - `{"action": "set_affiliated", "params": {"query": "...", "affiliated": ["query1"]}}`
  - `{"action": "get_affiliated", "params": {"query": "..."}}`
- Sync. No LLM calls.
- Every long-term memory entry has an "affiliated" array — a set of related
  memories (e.g. other memories from the same event or topic) that you can
  link together for easier joint recall later. **No raw memory ids appear
  here**: `query` describes the **source memory** in words and the kernel
  resolves it to the top-1 match among your own memories; `affiliated` is a
  **list of queries**, each of which is likewise resolved to one memory you
  own — the link targets to attach or detach. These four actions are,
  respectively, add to that array (`add_affiliated` — **APPENDS**, unioning
  the resolved targets into the existing affiliated set), remove from it
  (`remove_affiliated`), wholesale replace it (`set_affiliated` — **REPLACES**
  the whole set with the resolved new set), and read it (`get_affiliated`,
  returning `[{"id": "...", "text": "..."}, ...]` — each of the source
  memory's affiliates resolved to its text, but **only the affiliated
  memories YOU also own are returned**; any you don't own are skipped
  silently). Because a `query` only ever resolves over **your own** memories,
  you can only operate on memories you own — there's no separate ownership
  error to worry about; a query that matches nothing you own just fails with
  "no owned memory matches query".
- **Automatic affiliation on split (NEW)**: when a `remember` gets split into
  multiple atomic memories (a compound event), the system **automatically**
  makes those pieces mutually affiliated. So for pieces of one event you
  usually **don't** need to call `add_affiliated` yourself — just `remember`
  the compound sentence and the links are built for you. Reserve manual
  `add_affiliated` for linking memories you recorded **separately** that turn
  out to be about the same event/person.

### observe
- Signature: `{"action": "observe", "params": {"target": "..."}}`
- Sync.
- Directly returns the target agent's public status. The shape is uniform
  across all three agent kinds -- character/environment/info_carrier --:
  `{"kind": "...", "status": {...}, "occupants": [...]}`, where
  `occupants` is present only when the target is an environment.
  **No memory content is ever included.** Visibility rules are unchanged: a
  character target must be co-located with you (and not archived); an
  info_carrier target must be readable (co-located, or portable and
  currently held by you); an environment target is always observable per
  today's rules. To learn what a target *knows*/*remembers*, ask it via
  `say` (character) or `read` (info_carrier) instead of `observe`.

### read
- Signature: `{"action": "read", "params": {"target": "...", "query": "..."}}`
- Sync.
- Issues a query-driven read against an info_carrier (a book, letter,
  diary, etc.) or an environment. environment/info_carrier are both
  passive, function-driven agents (no brain turn of their own, never
  scheduled), so this **returns a result immediately, in the same tick**:
  the kernel directly retrieves the target's own long-term memories
  (deposited by sedimentation/`remember`/`act_on`) relevant to `query` and
  returns `[{"id": "...", "text": "..."}, ...]` -- no message delivery, no
  LLM call involved. Valid for an info_carrier target (must be co-located
  with you, or portable and currently held by you) or an environment
  target (must be co-located with you).

### act_on
- Signature: `{"action": "act_on", "params": {"targets": ["..."], "content": "..."}}`
  — `targets` must be a list containing **exactly one** element: the id of
  the `environment` agent you are currently at.
- Sync.
- Applies an action to the `environment` you are currently at (e.g.
  pushing a door, lighting a fire, rummaging through a drawer). An
  environment is a passive, function-driven agent (no brain turn of its
  own, never scheduled), so this **takes effect and returns a result
  immediately, in the same tick**: the kernel deposits `content` as a
  memory owned by that environment (so the place "remembers" what
  happened there), retrievable afterward via `read`. No message is ever
  sent, and no LLM is ever called for this.

### move
- Signature: `{"action": "move", "params": {"destination": "..."}}`
- Sync to issue, but has an "in-transit" effect.
- Validates that `destination` is an environment connected to your current
  location. On success you **leave** your current environment this tick
  (removed from its presence index), then spend a number of ticks
  "in-transit" (not scheduled, cannot act). On arrival you receive an
  "arrived" system message that wakes you up, and `status.location` is
  updated automatically to the new environment.

### wait
- Signature: `{"action": "wait", "params": {"timeout_ticks": N}}` (`timeout_ticks` is optional)
- Sync to issue, but has a "sleeping" effect.
- You are **awake by default** — even with an empty goal stack, you get
  scheduled every tick; an empty goal stack does not put you to sleep on
  its own. `wait` is **the only way you choose to sleep**: with
  `timeout_ticks=N`, you sleep for N ticks and then wake up automatically
  (even with no message). Without it, this is a **sleep forever** — you only
  wake up once a `wake=true` message arrives. **A waking message always
  interrupts a wait**, whether it's a timed wait or a forever wait. Note: a
  `wake=false` message (see `say`/`gesture`) does NOT interrupt `wait` — it
  sits quietly in its thread (bumping that row's `unread` count in the
  `conversations` roster) until you wake up for some other reason and go
  `read_thread` it. **If you genuinely have nothing to do, `wait`** — otherwise you'll
  keep spinning, getting rescheduled and re-deciding every tick for nothing.

### noop
- Signature: `{"action": "noop", "params": {}}`
- Sync.
- No-op. Normally used automatically by the framework when your output
  fails to parse; you may also choose it deliberately when there is truly
  nothing to do.

---

## Asynchronous actions

### say
- Signature: `{"action": "say", "params": {"targets": ["..."], "content": "...", "wake": true}}`
  — `targets` is **optional**; `wake` is optional, defaults to `true`.
- Async.
- Sends a spoken message. If you **omit `targets`** (or pass an empty
  list), it defaults to **everyone currently co-located with you** — a
  bare `say` just speaks to the room. You can instead pass an explicit list
  of target ids, mixing co-located and remote ones freely: a co-located
  target receives it on the next tick, exactly as before; a **remote**
  target (anywhere else in the world) instead receives it as a
  distance-delayed "letter" — delivery is deferred by an amount
  proportional to the worldmap distance between you and them, arriving
  once that much in-world travel time has passed, not on the very next
  tick.
- `wake` defaults to `true`, actively waking the recipient(s). Pass
  `"wake": false` for a quiet aside that doesn't interrupt them — it still
  gets delivered and still bumps the `unread` count of that conversation's
  row in their `conversations` roster, they just won't be woken by it
  until they check for some other reason.
- If `targets` is omitted (or empty) and nobody is currently co-located
  with you, this is a harmless no-op (`{"delivered": 0}`), not an error —
  there is simply no room to speak to.
- Every explicit target must exist and not be archived, or the whole call
  fails with the offending id(s) named in the error (no partial delivery).

### gesture
- Signature: `{"action": "gesture", "params": {"targets": ["..."], "content": "...", "wake": true}}`
  — same optional `targets`/`wake` shape as `say`.
- Async.
- Shows a non-verbal action/expression/gesture. Mechanically identical to
  `say` in every respect (targets optional and defaulting to co-located,
  remote targets distance-delayed, `wake` defaulting to `true`, no-op when
  you're alone) — the only difference is that the content is non-verbal.

---

## Six typical pipelines

### 1. Message handling (check the roster → push_goal FIRST → read_thread → act → pop_goal)
**Critical order: `push_goal` before `read_thread`.** The view's
`conversations` roster already gives you, for every conversation you're
part of, an `unread` count and a `last_preview` of its last line -- you
can decide "is this thread worth handling now" from that alone, without
opening it. If you `read_thread` first while your goal stack happens to be
empty, there is a window -- before you get around to `push_goal` -- where
you're judged goalless and stop being scheduled starting next tick; the
thread's `unread` count has already been reset to 0 by the read (nothing
is lost from the thread itself, but you may never get scheduled again to
notice it needed a reply). The correct order is:
1. Scan the `conversations` roster for rows with `unread > 0`, and use
   `last_preview` (and `kind`/`other`) to judge whether it's worth handling
   now;
2. **`push_goal` first**, based on that preview, pushing a corresponding
   small goal (e.g. "reply to alice's message") -- the thread's `unread`
   count is untouched at this point (nothing is lost), and you stay awake
   because you now have a goal;
3. Only then `read_thread(target)` to actually fetch the messages --
   the content `last_preview` couldn't fully show you is visible now (this
   also marks the thread read);
4. Repeatedly perform the appropriate actions (`observe`/`think`/`say`/
   `recall`, etc.) around the goal pushed in step 2 until it is achieved;
5. Only once it is achieved, `pop_goal` to remove it and return to a
   higher-level goal or `wait` -- don't pop it early, before it's actually
   done.

### 2. Socializing (observe environment → pick targets → say/gesture → wait)
1. `observe` your current environment to get the set of present agents and
   the environment's public status;
2. Pick the `targets` you want to interact with from those present;
3. `say` or `gesture` toward `targets`;
4. `wait` for a reply — you'll be woken automatically when their response
   arrives on a later tick.
   Action target parameters must use the agent's id (given in the view's
   `colocated`/`known_locations`), not a character's display name in prose
   (the kernel can resolve some aliases, but id is authoritative).

### 3. Moving (observe → move → wait to arrive → observe)
1. `observe` your current environment to confirm your location and which
   neighboring environments you can reach;
2. `move(destination)` to set off;
3. From this tick you are in-transit — you cannot and need not act, just
   wait for the "arrived" system message to wake you;
4. On arrival, `observe` the new environment to learn its status and who
   is present.

### 4. Memory sedimentation (remember plot beats **on the spot**; don't hoard, don't dedup)
1. **Whenever a real plot beat happens, `remember` it on the very tick it
   happens** — a decision or plan made, the outcome of a clash, news heard,
   a promise given, a death or departure. **Do not** defer it to "wait until
   it's validated": defer it and no one can ever recall it. The system puts a
   `remember_hint` field in your view when you've just taken part in
   memorable developments — when you see it, seriously consider `remember`.
2. **No need to `recall` first to check for duplicates**: the system
   consensus-merges duplicates on write. Skipping a record out of fear of
   duplication is the most common and most harmful mistake — over-record if
   in doubt; the system will dedup for you.
3. `conclude`/`think` are only for your own scratch reasoning; they stay in
   private short-term memory that nobody else sees, and they **cannot
   substitute** for `remember`. Anything you want shared must be `remember`ed.
4. If an existing memory is wrong or outdated, use `revise_memory` in one
   step rather than manually doing `forget` + `remember`.

**Worked example — a typical `remember` trajectory across one storyline**
(one action per tick; a single matter moving from "learned" to "decided" to
"acted" to "consequence" is the most common `remember` trajectory):
- **Learned**: `read_thread` / `say` / `read` brings you a new piece of news
  → record on the spot: `remember("<who> learns that <what>.")`
- **Decided**: after conferring or deciding alone, you settle on a plan
  → `remember("<who> (after conferring with <whom>) decides to <do what>.")`
- **Acted**: `say` / `gesture` / `act_on` / `move` carries it out and
  changes the situation → `remember("<who> did <what>, causing <direct result>.")`
- **Consequence**: a clash resolves, or someone arrives / leaves / dies
  → `remember("Outcome of <clash or event>: <who won/lost, who left, who died>.")`

When you see `remember_hint`, you are usually standing on one of these beats:
look back over your last few `say`s and the messages you received, pick out
**the one thing that actually happened**, record it as a self-contained fact
(name people and place, no pronouns), then get on with your goal.

### 5. Bootstrap reflection (recall → observe → conclude → push_goal fundamental → push_goal current)
Applies when your goal stack is empty (you'll see a `goal_hint` field in your
view) — typical of a "history sedimentation" start (in a sequel simulation,
living characters start with no preset goals and must figure out what to do
next themselves).
1. `recall` your own past (e.g. query on your name/notable events) to
   remember who you are and what you've been through;
2. `observe` your current environment to learn where you are, who's around,
   and what's happening;
3. `conclude` a judgment that synthesizes "who I am + what my situation is
   right now" and write it to short-term memory;
4. `push_goal` a fundamental goal (based on step 3's judgment — the most
   basic thing you want out of this life/phase);
5. `push_goal` a current small goal (concretely, what to do right now), then
   keep going with the other pipelines (message handling / socializing /
   moving / etc.).

### 6. Goal lifecycle (empty stack → push_goal → keep pursuing → sub-goal/replace_goal → pop only once achieved)
1. The fundamental goal sits at the **bottom** of the goal stack, injected
   by the scenario at initialization; you generally should not `pop_goal`
   it yourself;
2. The specific goal you're currently working on sits at the **top**; use
   `push_goal` to add finer-grained sub-goals;
3. Only `pop_goal` a sub-goal once it is truly achieved (or you have
   genuinely decided to abandon it because it can't/needn't be pursued
   further) -- this avoids an ever-growing, unfocused goal stack, but don't
   pop early just to "clear the stack" while things are still unfinished;
4. If a goal's wording needs adjusting but its level shouldn't change, use
   `replace_goal` instead of a `pop_goal` + `push_goal` pair;
5. **Keep at least one goal on the stack as long as you have unfinished
   business** -- continuing a story always has unfinished business (an
   unsaid next line, a reply you're waiting on, a decision not yet made),
   so there is almost never a moment where a goal is so completely done
   that the stack can be left empty; rewrite the goal to be more specific
   rather than popping it away.

**Worked example (starting from an empty stack, spanning several ticks)**:
- Tick 0 (goal stack empty, view shows `goal_hint`): `recall("my own
  history")` to remember your background → `observe` the current
  environment → `conclude("I just came back from..., I'm now at..., I
  don't yet know...")` → `push_goal("figure out what happened")`
  (fundamental goal) → `push_goal("find alice and ask her")` (current
  goal).
- Tick 1: `observe` the environment, find alice present → `say(targets=
  ["alice"], "do you know what happened with...?")` → `wait` (waiting for
  alice's reply -- the goal stack stays non-empty, so you'll be woken next
  by her reply message arriving, not left to sleep forever).
- Tick 2: alice's reply arrives and wakes you → **first** `push_goal("respond
  to alice's message")` (based on the `conversations` roster's
  `last_preview` for alice, following pipeline 1's order above) →
  `read_thread(target="alice")` to read the body → it turns out
  to be more complicated than expected, so `replace_goal("verify what alice
  said is actually true")` (a wording change, same stack depth) →
  `remember("alice said...")` to store the key fact in long-term memory.
- Ticks 3-4: keep pursuing the "verify" goal with several more rounds of
  `observe`/`recall`/`say`, each time confirming the goal stack is
  non-empty (so you stay awake), until you reach a solid conclusion.
- Tick 5: once confirmed, `conclude` it into short-term memory, `pop_goal`
  the "verify..." sub-goal (achieved), back down to the fundamental "figure
  out what happened" goal at the bottom -- if that fundamental goal has now
  also been satisfied by the verification result, keep going with a new
  `push_goal` for a current goal (e.g. "tell someone the result") instead of
  letting the stack bottom out; only consider popping the fundamental goal
  too once it is genuinely settled and there is truly nothing left to do
  next.

---

## Action-trajectory demos (supplement: getting the neglected actions moving)

Each demo below is a short trajectory (**one action per tick**, strung
together with `→`), with a concrete Three-Kingdoms example plus a "when to
use it." They specifically show off the actions that are easy to overlook
yet quite useful.

### A. Investigation chain (affiliated memories surface automatically) — `recall` (auto-expands) → act on it
`recall("Xu Shu")` → the result has the direct hit `{text:"Xu Shu goes over to
Cao Cao's camp", n_affiliated:2}` **and automatically brings in its affiliated
memories that you also own** (marked `via_affiliated:true`, e.g. "Xu Shu's
mother is held hostage by Cao Cao", "On departure Xu Shu recommends Zhuge Liang
to Liu Bei") → the scattered clues are **woven together in one recall** → then
act on it with `push_goal("seek out Zhuge Liang at Longzhong")` / `say` / `act_on`.
- **To explicitly list one memory's affiliates**: `get_affiliated("Xu Shu goes
  over to Cao Cao's camp")` (by query) → returns that memory's affiliates you
  also own. (Usually unnecessary — recall already pulled the one-hop neighbours.)
- **Manual linking (rare)**: to chain two memories you recorded **separately**
  that turn out to be the same event/person, use `add_affiliated("description of
  one", ["description of the other"])` (both ends by query, **appends**). Pieces
  split out of one compound `remember` are auto-linked, so you don't do those.

### B. Environment-interaction chain (act on your environment and leave a trace) — `observe` → `act_on` → `remember`
`observe("xuchang_wuku")` to see what's in the armory → `act_on(targets=
["xuchang_wuku"], content="take inventory of the armory, tallying the
blades, spears, and armor")` to act on the environment (pushing a door,
rifling case files, lighting a beacon, checking a granary all work the same
way) → `remember("At the Xuchang armory, Yu Jin took inventory of the
weapons and found the armor short by three hundred suits.")`.
- **When to use**: when you want to **physically change or inspect the
  environment you're in** (rather than talk to a person). `act_on` deposits
  `content` as a memory owned by that environment, so the place henceforth
  "remembers" what happened and it can be `read` later; don't forget to also
  `remember` a memory of your own to lay the outcome into the shared history.

### C. Reading documents / reading people (retrieve content the target holds) — `read` → `remember` → `push_goal`/`say`
Encountering a messenger / document / someone present → `read(target=
"secret_letter", query="Cai Mao Zhang Yun treachery")` to retrieve the
info_carrier's (the secret letter's) own memories/content → `remember("In
Zhou Yu's tent Jiang Gan stole a secret letter claiming Cai Mao and Zhang
Yun mean to hand over the northern naval camp.")` → then act on it with
`push_goal("hurry back north to report to Cao Cao")` or `say` to pass it on.
- **When to use**: when the key information is **written in a document, or
  held inside a present target's memory**, and `observe` only shows public
  status, not content, use `read(target, query)` to read a document
  (info_carrier) or environment with a question in hand. To ask a character
  what it *knows*, still use `say`.

### D. Status upkeep (update it when it changes, remove it when it clears) — `update_status` / `remove_status`
Something that changes you happens (wounded / disguised / donning enemy
armor / a swing of mood) → `update_status(key="injury", value="right arm
struck by one of Cao's poisoned arrows")` (the key can also be mood /
appearance / clothing / any custom key, but **not** the reserved key
`location`) → once Hua Tuo scrapes the bone clean and the wound heals →
`remove_status(key="injury")` to drop that status.
- **When to use**: whenever you take on a state that will keep affecting
  later interactions, `update_status` to record it (others see it when they
  `observe` you); once the state clears, `remove_status` it — don't leave a
  stale status hanging around.

### E. Goal close-out (pop when achieved, replace when obsolete; don't let the goal stack grow stale) — `pop_goal` / `replace_goal`
The goal stack, bottom to top, is `[root goal, …, current sub-goal]`
(bottom = most fundamental goal, top = current sub-goal).
- **Pop when achieved**: the top sub-goal is done → `pop_goal()` to drop it
  and return to the goal above. E.g. with the stack `[restore the Han,
  ally with Wu against Cao, persuade Sun Quan into an alliance]`, once the
  Red Cliffs pact is sealed → `pop_goal()` drops "persuade Sun Quan into an
  alliance" and returns to "ally with Wu against Cao."
- **Replace when obsolete**: a goal has become impossible or meaningless
  (e.g. the person you meant to persuade has died) → `replace_goal` in
  place. E.g. the top goal is "take Nan Commandery through Zhou Yu's help,"
  but Zhou Yu has died → `replace_goal("work with Lu Su instead to keep the
  Sun-Liu alliance intact")` (stack depth unchanged).
- **When to use**: agents tend to only `push` and never close out, so the
  goal stack piles up stale and decisions lose focus. `pop_goal` a sub-goal
  the moment it's truly achieved; `replace_goal` a goal that's obsolete or
  impossible — but in both cases don't act early while things are still
  unfinished.
