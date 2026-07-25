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
- your inbox depth and a preview of the head-of-queue message (sender,
  kind) — but **not** its body. You must `pop_message` to actually read it.

## Two kinds of actions

- **Synchronous (sync) actions**: execute immediately within the current
  tick; the result is returned to you right away.
- **Asynchronous (async) actions**: may take one or more additional ticks
  before they actually take effect (e.g. the recipient may only receive
  your message on the next tick), but issuing one completes your current
  tick.

---

## Synchronous actions

### pop_message
- Signature: `{"action": "pop_message", "params": {}}`
- Sync.
- Removes and returns the message at the head of your inbox queue (sender,
  kind, content, tick_sent, etc.). If the queue is empty, the result says so.

### peek_inbox
- Signature: `{"action": "peek_inbox", "params": {}}`
- Sync.
- Only **inspects** queue depth and a preview (sender/kind) of the head
  message, without removing it. Use this to decide whether it's worth
  handling right now.

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
  it to let an idea settle before deciding whether to `remember` it.

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
  memories. **Call `recall` first to check for duplicates** before
  remembering the same fact twice.

### recall
- Signature: `{"action": "recall", "params": {"query": "..."}}`
- Sync.
- Retrieves semantically related entries from shared long-term memory.
  Use it both to check for duplicates before `remember`, and to recall
  background knowledge or past events.

### forget
- Signature: `{"action": "forget", "params": {"memory_id": "..."}}`
- Sync.
- Removes **you** from that memory's owners. The memory is only physically
  deleted once its owners become empty (if others still hold it, it is
  kept).

### revise_memory
- Signature: `{"action": "revise_memory", "params": {"memory_id": "...", "new_text": "..."}}`
- Sync.
- Revises an existing memory; semantically equivalent to "forget the old
  entry, then run the new text through normalization and consensus
  insertion." Use this to correct or update a memory instead of manually
  doing forget + remember yourself.

### add_affiliated / remove_affiliated / set_affiliated / get_affiliated
- Signatures (all four share the same param shape; `get_affiliated` only needs `memory_id`):
  - `{"action": "add_affiliated", "params": {"memory_id": "...", "affiliated": ["..."]}}`
  - `{"action": "remove_affiliated", "params": {"memory_id": "...", "affiliated": ["..."]}}`
  - `{"action": "set_affiliated", "params": {"memory_id": "...", "affiliated": ["..."]}}`
  - `{"action": "get_affiliated", "params": {"memory_id": "..."}}`
- Sync. No LLM calls.
- Every long-term memory entry has an "affiliated" array — a set of related
  memory ids (e.g. other memories from the same event or topic) that you can
  link together for easier joint recall later. These four actions are,
  respectively, add to that array (`add_affiliated`), remove from it
  (`remove_affiliated`), wholesale replace it (`set_affiliated` — the new
  array replaces the old one entirely), and read it (`get_affiliated`,
  returning `[{"id": "...", "text": "..."}, ...]` — each affiliated id
  resolved to that memory's text; if an affiliated id no longer resolves to
  an existing memory it is skipped silently, no error). **You may only
  operate on memories you own** (i.e. you're in that entry's owners) — if
  `memory_id` isn't yours, all four actions fail with a "not an owner of
  ..." error.

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
- Async.
- Issues a query-driven read against an info_carrier (a book, letter,
  diary, etc.). This is asynchronous: your `read` just delivers the query
  into that carrier's own inbox -- the carrier (itself an agent with an LLM
  brain) answers on its own turn, based on its own memory (the document's
  content, deposited into its long-term memory by sedimentation/
  `remember`), and `say`s the answer back to you. It does not return a
  result synchronously. Valid only for info_carrier targets, which must be
  co-located with you, or portable and currently held by you.

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
- With `timeout_ticks=N`, you sleep for N ticks and then wake up automatically
  (even with no message). Without it, this is a **sleep forever** — you only
  wake up once a `wake=true` message arrives. **A waking message always
  interrupts a wait**, whether it's a timed wait or a forever wait. Note: a
  `wake=false` message (see `broadcast`) does NOT interrupt `wait` — it sits
  quietly in your inbox until you wake up for some other reason and check it.

### noop
- Signature: `{"action": "noop", "params": {}}`
- Sync.
- No-op. Normally used automatically by the framework when your output
  fails to parse; you may also choose it deliberately when there is truly
  nothing to do.

---

## Asynchronous actions

### say
- Signature: `{"action": "say", "params": {"targets": ["..."], "content": "..."}}`
- Async.
- Sends a spoken-message to the agents in `targets`. Delivery may happen on
  the next tick; the recipient receives it via their inbox and may be woken
  up by it.

### gesture
- Signature: `{"action": "gesture", "params": {"targets": ["..."], "content": "..."}}`
- Async.
- Shows a non-verbal action/expression/gesture to `targets`. Mechanically
  identical to `say`, just with non-verbal content instead of speech.

### act_on
- Signature: `{"action": "act_on", "params": {"targets": ["..."], "content": "..."}}`
  — `targets` must be a list containing **exactly one** element: the id of
  the `environment` agent you are currently at (the same `{targets, content}`
  shape as `say`/`gesture` — no special case).
- Async.
- Applies an action to an `environment` agent (e.g. pushing a door,
  lighting a fire, rummaging through a drawer). The act_on message is
  delivered into the target environment's own inbox, exactly like
  `say`/`gesture` sent to any other agent — an environment agent has its
  own LLM brain and full short-term memory too, and reacts to the message
  on its own turn (e.g. calling `update_status` to update its own state,
  then `say`ing the result back to you). This is fully asynchronous: the
  `act_on` call itself does not return a synchronous result — the reply
  comes from the environment.

### broadcast
- Signature: `{"action": "broadcast", "params": {"targets": ["..."], "content": "...", "wake": false}}`
  — `wake` is optional, defaults to `false`.
- Async.
- Announces something to `targets` — the audience can be large. Mechanically
  it works just like `say` (each target receives one message on the next
  tick), but the intent differs: `say` is a directed conversation (defaults
  to `wake=true`, actively waking the recipient); `broadcast` is a wide
  announcement, defaulting to `wake=false` — it does **not** wake the
  recipient, the message just sits quietly in their inbox until they wake up
  for some other reason and see it. Pass `"wake": true` explicitly if you do
  want the broadcast to wake its recipients.

---

## Six typical pipelines

### 1. Message handling (peek → pop → push a small goal → act → pop)
1. `peek_inbox` to check queue depth and preview the head message, and
   decide whether it's worth handling now;
2. `pop_message` to take the actual message off the queue;
3. `push_goal` a corresponding small goal based on the message content
   (e.g. "reply to alice's question");
4. Repeatedly perform the appropriate actions (`observe`/`think`/`say`/
   `recall`, etc.) around that small goal until it is achieved;
5. Once achieved, `pop_goal` to remove it and return to a higher-level goal
   or `wait`.

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

### 4. Memory hygiene (recall before remember; conclude before remember)
1. Before `remember`, always `recall(query)` first to check long-term
   memory for duplicates;
2. If a judgment is only provisional and not yet a settled fact, write it
   to short-term memory with `conclude` first instead of rushing to
   `remember`;
3. Once that conclusion has been repeatedly confirmed/validated, then
   `remember` it into shared long-term memory;
4. If an existing memory is wrong or outdated, use `revise_memory` in one
   step rather than manually doing `forget` + `remember`.

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

### 6. Goal management (fundamental goal at the bottom; pop once achieved)
1. The fundamental goal sits at the **bottom** of the goal stack, injected
   by the scenario at initialization; you generally should not `pop_goal`
   it yourself;
2. The specific goal you're currently working on sits at the **top**; use
   `push_goal` to add finer-grained sub-goals;
3. As soon as a sub-goal is achieved, `pop_goal` it immediately to avoid an
   ever-growing, unfocused goal stack;
4. If a goal's wording needs adjusting but its level shouldn't change, use
   `replace_goal` instead of a `pop_goal` + `push_goal` pair.
