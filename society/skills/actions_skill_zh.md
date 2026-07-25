# Actions 使用说明书(中文版)

你是社会模拟中的一个智能体(agent)。每一个 tick,你只能选择并输出**一个** action,
用来描述你这一步要做什么。系统会执行这个 action,并把结果放进你的短期记忆
(FIFO 缓存)里,供你下一次决策时参考。

## 你能看到什么(view)

你收到的 view 里通常包含:
- 当前 tick;
- 最近若干条 `(action, result)` 历史(FIFO,最多若干条,越靠后越新);
- 你的目标栈(goals,栈底是最根本、最不会变的目标,栈顶是你当前正在处理的具体小目标);
- 你的状态寄存器(status,比如 mood/appearance/clothing/location 等任意键值);
- 你的消息队列深度,以及队首消息的预览(发送者、类型),但**不包含**消息正文——
  正文要用 `pop_message` 才能取到。

## Action 分为两类

- **同步(sync)action**: 本 tick 内立即执行完毕,结果当场返回给你。
- **异步(async)action**: 可能要跨越多个 tick 才真正送达/生效(比如对方要下一
  tick 才能收到你的话),但你发出这个 action 之后,当前 tick 就算完成了。

---

## 同步 action 列表

### pop_message
- 签名: `{"action": "pop_message", "params": {}}`
- 同步。
- 作用: 从你的消息队列中取出并**移除**队首的一条消息,结果里包含这条消息的完整
  内容(sender、kind、content、tick_sent 等)。如果队列为空,结果会标明"无消息"。

### peek_inbox
- 签名: `{"action": "peek_inbox", "params": {}}`
- 同步。
- 作用: 只**查看**队列深度和队首消息的预览(发送者/类型),不取出、不移除。用来
  判断"值不值得现在处理这条消息"。

### think
- 签名: `{"action": "think", "params": {"question": "..."}}`
- 同步。
- 作用: 针对一个问题进行一次内部推理/自问自答,结果是你对这个问题的思考文本。
  这是相对"昂贵"的 action,请节制使用,不要每个 tick 都 think。

### conclude
- 签名: `{"action": "conclude", "params": {"text": "..."}}`
- 同步。
- 作用: 把一句阶段性结论写入短期记忆的 FIFO 里(作为一条 `(action, result)`),
  但**不会**写入长期记忆。用于把想法先沉淀下来,确认稳定之后再考虑 `remember`。

### push_goal
- 签名: `{"action": "push_goal", "params": {"text": "..."}}`
- 同步。
- 作用: 在目标栈**栈顶**压入一个新的小目标,不改变更底层的目标。

### pop_goal
- 签名: `{"action": "pop_goal", "params": {}}`
- 同步。
- 作用: 弹出并移除目标栈**栈顶**的目标,表示该目标已经达成或已放弃。

### replace_goal
- 签名: `{"action": "replace_goal", "params": {"text": "..."}}`
- 同步。
- 作用: 用新文本替换目标栈**栈顶**的目标(栈深不变),用于对当前目标的措辞调整
  或推进,而不产生新的层级。

### update_status
- 签名: `{"action": "update_status", "params": {"key": "...", "value": "..."}}`
- 同步。
- 作用: 写入/更新状态寄存器里的一个键值(例如 mood、appearance、clothing 或任意
  自定义键)。**注意**: `key` 不能是 `"location"`——location 是保留键,只能通过
  `move` 修改,直接 update_status 会被拒绝。

### remove_status
- 签名: `{"action": "remove_status", "params": {"key": "..."}}`
- 同步。
- 作用: 从状态寄存器中删除某个键。

### remember
- 签名: `{"action": "remember", "params": {"text": "..."}}`
- 同步。
- 作用: 把一条原子事实写入共享长期记忆(LTM)。系统会对文本做规范化(过长/多义
  会被拆解或压缩)并做共识合并(与已有相似记忆判断是否等价)。**使用前应先用
  `recall` 查重**,避免反复记录同一件事。

### recall
- 签名: `{"action": "recall", "params": {"query": "..."}}`
- 同步。
- 作用: 按语义相似度从共享长期记忆中检索相关条目,返回若干候选文本。既可以用来
  查重,也可以用来获取背景知识、回忆过去发生的事。

### forget
- 签名: `{"action": "forget", "params": {"memory_id": "..."}}`
- 同步。
- 作用: 把**你自己**从这条记忆的 owners 中移除。只有当 owners 变空时,这条记忆
  才会被真正物理删除(如果别人仍然持有这条记忆,它会被保留)。

### revise_memory
- 签名: `{"action": "revise_memory", "params": {"memory_id": "...", "new_text": "..."}}`
- 同步。
- 作用: 修订一条已有记忆,语义上等价于"先对旧条目做一次 forget,再让新文本走一遍
  规范化与共识插入流程"。用它来更正错误或过时的记忆,而不要自己手动拆成
  forget + remember 两步。

### add_affiliated / remove_affiliated / set_affiliated / get_affiliated
- 签名(四个动作参数形状一致,`get_affiliated` 只需要 `memory_id`):
  - `{"action": "add_affiliated", "params": {"memory_id": "...", "affiliated": ["..."]}}`
  - `{"action": "remove_affiliated", "params": {"memory_id": "...", "affiliated": ["..."]}}`
  - `{"action": "set_affiliated", "params": {"memory_id": "...", "affiliated": ["..."]}}`
  - `{"action": "get_affiliated", "params": {"memory_id": "..."}}`
- 同步。不调用 LLM。
- 作用: 每条长期记忆都有一个"关联记忆"数组(`affiliated`),用来把同一事件/同一
  话题下相关的多条记忆链接起来,方便日后一并回忆。这四个动作分别是对这个数组的
  增(`add_affiliated`)、删(`remove_affiliated`)、整体替换(`set_affiliated`,
  用新数组整体覆盖旧数组)、查(`get_affiliated`,返回
  `[{"id": "...", "text": "..."}, ...]`,把每个关联 id 解析成对应记忆的正文;
  如果某个关联 id 指向的记忆已经不存在,会被静默跳过,不报错)。
  **只能操作你自己拥有(owners 包含你)的记忆**——`memory_id` 不属于你时,四个动作
  都会失败并返回"not an owner of ..."错误。

### observe
- 签名: `{"action": "observe", "params": {"target": "..."}}`
- 同步。
- 作用: 直接返回目标 agent 的公开 status(character/environment/info_carrier
  三种 agent 通用同一种返回形状:`{"kind": "...", "status": {...},
  "occupants": [...]}`,`occupants` 只在目标是 environment 时出现),**不包含
  任何记忆内容**。可见性规则与之前一致:character 目标必须与你同处一地(且未
  archived);info_carrier 目标必须可读(同处一地,或 portable 且被你持有);
  environment 目标按现有规则始终可观察。想了解目标"知道什么"/"记得什么",要用
  `say`(character)或 `read`(info_carrier)去问,而不是 `observe`。

### read
- 签名: `{"action": "read", "params": {"target": "...", "query": "..."}}`
- 异步。
- 作用: 向一份可读文书(info_carrier,如书籍/信件/日记)发起带 query 的询问。
  这是异步的:你的 `read` 只是把这条询问投递进该文书自己的收件箱,文书本身
  (也是一个有 LLM brain 的 agent)会在它自己的回合里,根据自己的记忆(即文书
  内容,由沉淀/`remember`写入其长期记忆)作答,再用 `say` 把答案发回给你——不
  是本次 action 立即返回结果。只对 info_carrier 类型的目标有效;目标必须与你
  同处一地,或者是可携带(portable)且正被你持有。

### move
- 签名: `{"action": "move", "params": {"destination": "..."}}`
- 同步发起,但会产生"在途"效果。
- 作用: 校验 destination 是一个 environment 且与你当前位置连通,校验通过后你会
  在本 tick**离开**当前环境(原环境的在场索引移除你),随后进入"在途"状态若干个
  tick(这段时间你不会被调度、也不能执行任何 action)。到达目的地后,你会收到一条
  "已到达"系统消息把你唤醒,同时 `status.location` 会自动更新为新环境。

### wait
- 签名: `{"action": "wait", "params": {"timeout_ticks": N}}`(`timeout_ticks` 可选)
- 同步发起,但会产生"休眠"效果。
- 作用: 带 `timeout_ticks=N` 时,你会休眠 N 个 tick 后自动醒来(即使没有任何消息);
  不带这个参数时,等价于**永久休眠**,直到收到一条 `wake=true` 的消息才会被唤醒
  ——**唤醒消息总能打断等待**,不论是定时等待还是永久等待。注意:`wake=false` 的
  消息(见 `broadcast`)不会打断 `wait`,它会安静地留在你的收件箱里,等你因为其他
  原因醒来后再去看。

### noop
- 签名: `{"action": "noop", "params": {}}`
- 同步。
- 作用: 空操作。一般由框架在你的输出解析失败等异常情况下自动使用;你也可以在
  确实无事可做时主动选择它。

---

## 异步 action 列表

### say
- 签名: `{"action": "say", "params": {"targets": ["..."], "content": "..."}}`
- 异步。
- 作用: 向 `targets` 列表中的对象发送一条对话消息。实际送达可能要等到下一个
  tick,对方通过自己的消息队列收到这条消息,并可能因此被唤醒。

### gesture
- 签名: `{"action": "gesture", "params": {"targets": ["..."], "content": "..."}}`
- 异步。
- 作用: 向 `targets` 展示一个非语言的动作/表情/姿态,机制与 `say` 完全相同,只是
  内容语义是动作而非言语。

### act_on
- 签名: `{"action": "act_on", "params": {"targets": ["..."], "content": "..."}}`
  ——`targets` 必须是**恰好包含一个**元素的列表,元素是你当前所在的那个
  environment 类 agent 的 id(和 `say`/`gesture` 用同一套 `{targets, content}`
  形状,没有特例)。
- 异步。
- 作用: 对一个 environment 类 agent 施加一个动作(例如推门、点火、翻找抽屉)。
  这条 act_on 消息会被投递进目标环境自己的收件箱,和 `say`/`gesture` 发给任何
  其他 agent 完全一样——环境 agent 自己也有 LLM brain 和完整短期记忆,会在它
  自己的回合里对这条消息作出反应(例如用 `update_status` 更新自身状态,再
  `say` 把结果回复给你)。这是纯异步的:发起 `act_on` 的这次 action 不会同步
  拿到结果,结果要等环境自己回复。

### broadcast
- 签名: `{"action": "broadcast", "params": {"targets": ["..."], "content": "...", "wake": false}}`
  ——`wake` 可选,默认 `false`。
- 异步。
- 作用: 向 `targets` 广而告之——受众可以很多,机制上和 `say` 一样(每个目标下一
  tick 收到一条消息),但语义不同:`say` 是定向交谈(默认 `wake=true`,会主动
  唤醒对方);`broadcast` 是大范围周知,默认 `wake=false`——**不会**吵醒对方,
  消息只是安静地躺进对方的收件箱,等对方下次因为别的原因醒来时自然会看到。如果
  确实需要广播也能唤醒对方,显式传 `"wake": true`。

---

## 六种典型 pipeline

### 1. 消息处理(push_goal 先行 → pop → 执行 → pop_goal)
**关键顺序:先 `push_goal`,再 `pop_message`。** view 里的 `inbox_head` 已经给出了
队首消息的预览(发送者、类型),不需要 pop 就能据此判断"这是一条什么消息、值不值得
处理"。如果先 `pop_message` 取出消息,而当时目标栈恰好是空的,你会在**还没来得及
push_goal** 的这个间隙里被判定为无目标、下一 tick 起就不再被调度——消息已经被你
取走并清空了收件箱,永远没有机会再补上这个目标了。正确顺序是:
1. 观察 `inbox_head`(和/或先 `peek_inbox`)预览队首消息的发送者与类型,判断值不
   值得现在处理;
2. **先 `push_goal`**,根据这个预览压入一个对应的小目标(例如"回复 alice 的
   消息")——此时消息还留在收件箱里,不会丢,你也因为有目标而保持清醒;
3. 然后 `pop_message` 取出消息正文,`peek_inbox` 时看不到的实际内容现在才能看到;
4. 围绕第 2 步压入的这个小目标反复执行合适的 action(`observe`/`think`/`say`/
   `recall` 等),直到目标达成;
5. 目标达成后才 `pop_goal` 弹出这个小目标,回到更上层的目标或 `wait`——不要在
   目标达成之前提前弹出。

### 2. 社交(observe环境 → 选targets → say/gesture → wait)
1. `observe` 当前所在的环境,获取在场者集合与环境公开状态;
2. 从在场者中选出要互动的 `targets`;
3. `say` 或 `gesture` 向 `targets` 表达;
4. `wait` 等待对方回应——下一 tick 对方的回复消息到达时,你会被自动唤醒。
   action 参数中的目标必须用 agent 的 id(view 的 colocated/known_locations 里给出),不要用人物的中文名字(内核可解析部分别名,但以 id 为准)。

### 3. 移动(observe → move → 等到达 → observe)
1. `observe` 当前环境,确认当前位置以及与之连通的相邻环境;
2. `move(destination)` 发起移动;
3. 本 tick 起进入"在途"状态,不需要也不能继续执行 action,静静等待"已到达"的
   系统消息把你唤醒;
4. 到达后 `observe` 新环境,了解新环境的状态与在场者。

### 4. 记忆卫生(remember前先recall查重;conclude先于remember)
1. 在 `remember` 之前,先用 `recall(query)` 查一遍长期记忆,避免录入重复事实;
2. 如果只是阶段性判断、尚未确定为稳定事实,先用 `conclude` 把结论写进短期记忆
   FIFO 里沉淀,而不要急着 `remember`;
3. 等这个结论被反复验证或明确认可之后,再 `remember` 把它写入共享长期记忆;
4. 如果发现旧记忆有误或过时,用 `revise_memory` 一步到位修订,而不要自己手动
   拆成 `forget` + `remember` 两步。

### 5. 开局自省(recall → observe → conclude → push_goal根本 → push_goal当前)
适用场景:你的目标栈为空(view 里会看到 `goal_hint` 字段)——常见于"历史沉淀"式
开局(后传模拟中,活着的角色不预设目标,需要自己想清楚接下来要做什么)。
1. `recall` 关于自己的过去(例如查询自己的名字/经历关键词),回忆你是谁、
   经历过什么;
2. `observe` 当前所在环境,了解你现在身处何地、周围有谁、发生了什么;
3. `conclude` 把"我是谁 + 我现在的处境是什么"综合成一句阶段性判断,写入
   短期记忆;
4. `push_goal` 设立一个根本目标(fundamental,基于第 3 步的判断,决定你这一生
   /这一阶段最根本想做的事);
5. `push_goal` 再设立一个当前的小目标(具体到眼下这一步该做什么),然后按其他
   pipeline(消息处理/社交/移动等)继续推进。

### 6. 目标生命周期(空栈 → push_goal → 持续推进 → 子目标/replace_goal → 达成才pop)
1. 根本目标(fundamental)在目标栈**栈底**,由场景在初始化时注入,一般不应该
   被你自己 `pop_goal` 掉;
2. 当前要执行的具体目标在**栈顶**,用 `push_goal` 添加更细粒度的子目标;
3. 子目标一旦真正达成(或确认无法/不必再推进而主动放弃),才 `pop_goal`,避免
   目标栈无限增长、决策失焦——但也不要为了"清空"而在事情没完时提前 pop;
4. 如果目标的表述需要调整但层级不需要变化,用 `replace_goal` 而不是先
   `pop_goal` 再 `push_goal`;
5. **只要还有未完成的事,就至少保留一个目标**——续写故事天然就有未完成的事
   (下一句对话没说、对方的反应还没等到、一个决定还没做),所以几乎不会出现
   "目标已经彻底完成、可以让栈空着"的时刻;宁可把目标改写得更具体,也不要
   直接清空。

**完整实例(从空栈开始,跨越多个 tick)**:
- tick 0(目标栈为空,view 里出现 `goal_hint`):`recall("自己的经历")` 回忆
  身世 → `observe` 当前环境 → `conclude("我刚从…回来,现在在…,尚不清楚…")` →
  `push_goal("弄清楚发生了什么")`(根本目标)→ `push_goal("找 alice 打听情况")`
  (当前目标)。
- tick 1:`observe` 环境找到 alice 在场 → `say(targets=["alice"], "你知道…
  发生了什么吗?")` → `wait`(等待 alice 回复,目标栈保持非空,所以下一次因为
  回复消息到达而被唤醒,而不是永久休眠)。
- tick 2:alice 的回复消息到达并唤醒你 → 先 `push_goal("回应 alice 的消息")`
  (根据 `inbox_head` 预览,遵循上面 pipeline 1 的顺序)→ `pop_message` 读到正文
  → 发现事情比预期复杂,`replace_goal("查证 alice 说的这件事是否属实")`(措辞
  调整,栈深不变)→ `remember("alice 说…")` 把关键信息存入长期记忆。
- tick 3-4:围绕"查证"这个目标继续 `observe`/`recall`/`say` 若干轮,每次都
  确认目标栈非空(因此保持清醒),直到得到确凿结论。
- tick 5:结论确认后,`conclude` 写入短期记忆,`pop_goal` 弹出"查证…"这个
  子目标(已达成),回到栈底的"弄清楚发生了什么"——如果这个根本目标也已经通过
  查证结果得到满足,可以继续 `push_goal` 一个新的当前目标(例如"把结果告诉
  某人"),而不是让栈见底;只有当根本目标本身也彻底了结、且确实没有下一步可做
  时,才考虑连根本目标一起 `pop_goal`。
