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
- 一份 `conversations`("会话花名册"):你所参与的每一段会话各占一行——包括你
  已经互通过消息的每一个 character/environment/info_carrier(活跃会话线程),
  以及当前与你同处一地的所有对象。每一行形如
  `{other, kind, colocated, unread, last_preview}`——对方的 id 与类型、对方
  当前是否与你同处一地、该会话里有多少条未读消息、以及最后一条消息的简短预览。
  这份花名册里**不包含**完整消息正文——要读取某段会话的实际内容,得用
  `read_thread(target)`(同时会把该会话标记为已读)。

## Action 分为两类

- **同步(sync)action**: 本 tick 内立即执行完毕,结果当场返回给你。
- **异步(async)action**: 可能要跨越多个 tick 才真正送达/生效(比如对方要下一
  tick 才能收到你的话),但你发出这个 action 之后,当前 tick 就算完成了。

---

## 同步 action 列表

### read_thread
- 签名: `{"action": "read_thread", "params": {"target": "...", "k": 10}}`
  (`k` 可选,默认为 10)
- 同步。
- 作用: 返回你与 `target`(`conversations` 花名册里的某个 id)之间会话线程的
  最近 `k` 条记录——是实际的消息正文(sender、kind、content、tick),不只是花名册
  里的那句预览。作为副作用,会把该会话标记为已读:花名册里对应行的 `unread`
  归零。建议先看花名册的 `unread` 和 `last_preview` 再决定值不值得打开哪个会话。

### think
- 签名: `{"action": "think", "params": {"question": "..."}}`
- 同步。
- 作用: 针对一个问题进行一次内部推理/自问自答,结果是你对这个问题的思考文本。
  这是相对"昂贵"的 action,请节制使用,不要每个 tick 都 think。

### conclude
- 签名: `{"action": "conclude", "params": {"text": "..."}}`
- 同步。
- 作用: 把一句阶段性结论写入短期记忆的 FIFO 里(作为一条 `(action, result)`),
  但**不会**写入长期记忆。用于把还不确定的想法先私下捋一捋。
- **注意**:conclude 只留在你私有的短期记忆里,别人读不到、也不进共同历史。一旦某件事
  真的发生了、值得让大家共享,就要用 `remember` 正式写入长期记忆——不要停在 conclude。

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
  会被拆解或压缩)并做共识合并(与已有相似记忆判断是否等价)。
- **这是把"发生过的事"沉淀进共同历史的唯一方式**——只有 `remember` 写入的东西,
  日后你和别人才 `recall` 得到;`conclude`/`think` 只留在你私有的短期记忆里,别人看不到,
  过一会儿也会被挤出。所以**每当剧情推进到一个值得记住的节点,就要 `remember` 它**。
- **该 remember 的典型时刻(剧情节点)**:做出一个决定、定下一条计策;一场战斗/交锋
  的结果(谁胜谁负、谁死谁伤);听到或得知一条消息/情报;许下或接受一个承诺、结成或
  背弃一个盟约;某人到达/离开某地这类改变格局的事。把它写成一句**自足**的原子事实
  (写清人物、地点、发生了什么,别用代词)。举例:
  - `remember("刘备在新野得知:曹操亲率大军南下,不日将至。")`
  - `remember("诸葛亮与刘备商议后定策:弃樊城、走襄阳,携民渡江南撤。")`
  - `remember("长坂坡一战,赵云单骑救出阿斗,曹军未能截下刘备主力。")`
- **不必先 recall 查重**:系统在写入时会自动做共识合并——与已有等价的记忆会被并到
  同一条上(共享 owner),重复不会污染记忆库。所以**你只管把发生的事记下来**,把"会不
  会重复"交给系统,不要因为担心重复而不记。
- 唯一**不该** remember 的是:还停在你脑子里、并未真正发生的纯内心盘算(那用
  `conclude`)。只要是真发生了、且值得让别人知道的,就记。

### recall
- 签名: `{"action": "recall", "params": {"query": "..."}}`
- 同步。
- 作用: 按语义相似度从共享长期记忆中检索相关条目,返回若干候选,每条形如
  `{"id": ..., "text": ..., "n_affiliated": <int>}`。既可以用来查重,也可以用来
  获取背景知识、回忆过去发生的事。其中 `n_affiliated` 表示该条记忆挂着多少条
  **关联记忆**。**recall 会自动顺关联边,把你也拥有的关联记忆一并带出来**(这些
  条目标 `via_affiliated: true`)——所以你 recall 一条,同一事件/人物的散落线索
  通常就**自动到手了**,不必再单独 `get_affiliated`(见文末"动作轨迹示范 A")。

### forget
- 签名: `{"action": "forget", "params": {"query": "..."}}`
- 同步。
- 作用: 把**你自己**从一条记忆的 owners 中移除。你不用记忆的 id 来指定它——而是
  用一句自然语言 `query` 描述你指的是哪条记忆,内核会在**你自己拥有的**记忆里取
  语义最相近的那一条(top-1)来操作。只有当 owners 变空时,这条记忆才会被真正物理
  删除(如果别人仍然持有这条记忆,它会被保留)。若没有任何你拥有的记忆匹配该
  query,动作会失败并返回"no owned memory matches query"。

### revise_memory
- 签名: `{"action": "revise_memory", "params": {"query": "...", "new_text": "..."}}`
- 同步。
- 作用: 修订一条已有记忆(用 `query` 语义命中你自己拥有的那一条),语义上等价于
  "先对旧条目做一次 forget,再让新文本走一遍规范化与共识插入流程"。用它来更正错误
  或过时的记忆,而不要自己手动拆成 forget + remember 两步。

### add_affiliated / remove_affiliated / set_affiliated / get_affiliated
- 签名(四个动作都用 `query` 定位源记忆,`get_affiliated` 只需要 `query`):
  - `{"action": "add_affiliated", "params": {"query": "...", "affiliated": ["query1", "query2"]}}`
  - `{"action": "remove_affiliated", "params": {"query": "...", "affiliated": ["query1"]}}`
  - `{"action": "set_affiliated", "params": {"query": "...", "affiliated": ["query1"]}}`
  - `{"action": "get_affiliated", "params": {"query": "..."}}`
- 同步。不调用 LLM。
- 作用: 每条长期记忆都有一个"关联记忆"数组(`affiliated`),用来把同一事件/同一
  话题下相关的多条记忆链接起来,方便日后一并回忆。这里**不出现任何原始记忆 id**:
  `query` 用一句话描述**源记忆**,内核在你自己拥有的记忆里取 top-1 命中它;
  `affiliated` 是一个**查询列表**,列表里每一条 query 同样各自解析成你拥有的一条
  记忆,作为要挂上/取下的链接目标。这四个动作分别是对源记忆的关联数组做增
  (`add_affiliated`,**追加**——把解析出的目标并入现有关联集合)、删
  (`remove_affiliated`)、整体替换(`set_affiliated`,**替换**——用解析出的新集合
  整体覆盖旧集合)、查(`get_affiliated`,返回 `[{"id": "...", "text": "..."}, ...]`,
  把源记忆的每个关联解析成正文——但**只返回你也拥有的那些关联记忆**,你不拥有的
  会被静默跳过)。因为 `query` 只在**你自己拥有的**记忆上解析,所以你天然只能操作
  自己的记忆,不存在单独的归属错误;若没有任何你拥有的记忆匹配某个 query,该动作
  失败并返回"no owned memory matches query"。
- **拆分时自动挂链(新)**:当一条 `remember` 被拆成多条原子记忆(复合事件)时,
  系统会**自动**把这些碎片互相设为关联。所以对同一件事的多个碎片,你通常**不必**
  自己再 `add_affiliated`——直接 `remember` 那句复合句,链就替你建好了。手动
  `add_affiliated` 留给这种情况:你**分开**记下的几条记忆,事后发现其实说的是
  同一事件/同一人,再手动把它们挂到一起。

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
- 同步。
- 作用: 向一份可读文书(info_carrier,如书籍/信件/日记)或一个 environment
  发起带 query 的询问。environment/info_carrier 都是被动的、纯函数式的
  agent(没有自己的 brain 回合,永远不会被调度),所以这**本 tick 内立即返回
  结果**:内核直接检索目标自己拥有的长期记忆(由沉淀/`remember`/`act_on`
  写入)中与 query 相关的条目,返回 `[{"id": "...", "text": "..."}, ...]`,
  不经过任何消息投递或 LLM 调用。目标必须是 info_carrier(需与你同处一地,
  或可携带且正被你持有)或 environment(需与你同处一地)。

### act_on
- 签名: `{"action": "act_on", "params": {"targets": ["..."], "content": "..."}}`
  ——`targets` 必须是**恰好包含一个**元素的列表,元素是你当前所在的那个
  environment 类 agent 的 id。
- 同步。
- 作用: 对你当前所在的 environment 施加一个动作(例如推门、点火、翻找抽屉)。
  environment 是被动的、纯函数式的 agent(没有自己的 brain 回合,永远不会被
  调度),所以这**本 tick 内立即生效并返回结果**:内核把 `content` 作为一条
  由该 environment 拥有的长期记忆存下来(这个地方因此"记得"发生过什么),
  之后可以用 `read` 去查询。不会产生任何消息,也不会调用 LLM。

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
- 作用: 你默认就是**清醒的**(awake)——只要没有目标也没有关系,清醒状态下
  你每个 tick 都会被调度,不会因为目标栈为空而自动休眠。`wait` 是**你唯一主动
  让自己休眠的方式**:带 `timeout_ticks=N` 时,你会休眠 N 个 tick 后自动醒来
  (即使没有任何消息);不带这个参数时,等价于**永久休眠**,直到收到一条
  `wake=true` 的消息才会被唤醒——**唤醒消息总能打断等待**,不论是定时等待还是
  永久等待。注意:`wake=false` 的消息(见 `say`/`gesture`)不会打断 `wait`,
  它会安静地留在对应会话线程里(把 `conversations` 花名册里那一行的 `unread`
  加一),等你因为其他原因醒来后再用 `read_thread` 去看。**真的无事可做时就该
  `wait`**——否则你会一直空转,每个 tick 都被重新调度、重新决策,白白消耗算力。

### noop
- 签名: `{"action": "noop", "params": {}}`
- 同步。
- 作用: 空操作。一般由框架在你的输出解析失败等异常情况下自动使用;你也可以在
  确实无事可做时主动选择它。

---

## 异步 action 列表

### say
- 签名: `{"action": "say", "params": {"targets": ["..."], "content": "...", "wake": true}}`
  ——`targets` **可选**;`wake` 可选,默认 `true`。
- 异步。
- 作用: 发送一条对话消息。如果**省略 `targets`**(或传空列表),默认发给
  **当前与你同处一地的所有对象**——一句裸的 `say` 就是"对着这屋子里的人说"。
  你也可以显式传一份目标 id 列表,co-located 和远程目标可以混在一起:同处一地
  的目标和以前一样下一 tick 就能收到;**远程**目标(世界上任何别的地方)则会
  变成一封"按距离延迟送达的信"——送达延迟量与你和对方在世界地图上的距离成正比,
  要等相当于那段路程的游戏内时间过去后才会到达,而不是下一 tick 就送到。
- `wake` 默认为 `true`,会主动唤醒收件人。传 `"wake": false` 可以悄悄说一句不
  打扰对方——消息依然会送达,依然会让对方 `conversations` 花名册里这段会话的
  `unread` 加一,只是不会因此把他们叫醒,直到他们因为别的原因醒来自己去看。
- 如果省略(或空)`targets` 且当前没有任何人与你同处一地,这是一个无害的
  空操作(`{"delivered": 0}`),不是错误——单纯是没人可说。
- 每一个显式给出的目标都必须存在且未被 archived,否则整次调用失败,出错的
  id 会在错误信息里列出(不会出现部分送达)。

### gesture
- 签名: `{"action": "gesture", "params": {"targets": ["..."], "content": "...", "wake": true}}`
  ——`targets`/`wake` 的可选形状与 `say` 相同。
- 异步。
- 作用: 展示一个非语言的动作/表情/姿态。机制与 `say` 完全相同(targets 可选、
  默认同处一地,远程目标按距离延迟,`wake` 默认 `true`,独自一人时是空操作)——
  唯一区别是内容语义是动作而非言语。

---

## 六种典型 pipeline

### 1. 消息处理(先看花名册 → push_goal 先行 → read_thread → 执行 → pop_goal)
**关键顺序:先 `push_goal`,再 `read_thread`。** view 里的 `conversations`
花名册已经给出了每段会话的 `unread` 未读数和 `last_preview` 最后一句预览,
不需要打开就能据此判断"这段会话值不值得现在处理"。如果先 `read_thread` 打开
会话,而当时目标栈恰好是空的,你会在**还没来得及 push_goal** 的这个间隙里被
判定为无目标、下一 tick 起就不再被调度——虽然会话本身的消息没有丢(该会话的
`unread` 只是被清零了),但你可能再也没有机会被调度去注意到它需要回复了。
正确顺序是:
1. 扫一遍 `conversations` 花名册,找出 `unread > 0` 的行,用 `last_preview`
   (以及 `kind`/`other`)判断值不值得现在处理;
2. **先 `push_goal`**,根据这个预览压入一个对应的小目标(例如"回复 alice 的
   消息")——此时该会话的 `unread` 还没被清零,不会丢,你也因为有目标而保持
   清醒;
3. 然后 `read_thread(target)` 取出消息正文,`last_preview` 看不到的实际内容
   现在才能看到(这一步同时会把该会话标记为已读);
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

### 4. 记忆沉淀(剧情节点**当场**remember;别攒着、别查重)
1. **凡是真正发生的剧情节点,就在它发生的那一 tick 当场 `remember`**——做出的
   决定/计策、交锋的结果、听到的消息、许下的承诺、生死去留。**不要**为了"等它被
   反复验证"而拖延:拖过去别人就再也 recall 不到了。系统会在你的 view 里放一个
   `remember_hint` 字段提醒你此刻有值得记的进展——看到它就认真考虑 remember。
2. **不必先 recall 查重再 remember**:写入时系统会自动共识合并重复项。担心重复
   而不记,是最常见也最有害的错误——宁可多记,系统会替你去重。
3. `conclude`/`think` 只用于你自己的临时推理,留在私有短期记忆里、别人看不到;
   它们**不能替代** `remember`。真正要让大家共享的,一定得 `remember`。
4. 如果发现旧记忆有误或过时,用 `revise_memory` 一步到位修订,而不要自己手动
   拆成 `forget` + `remember` 两步。

**记忆示范——一条剧情线里 remember 的典型轨迹**(每个 tick 只做一个动作;一件事
从"得知"发展到"决定"再到"行动"并产生"后果",是最常见的 remember 轨迹):
- **得知**:`read_thread` / `say` / `read` 让你获知一条新情报或消息
  → 当场 `remember("<谁>得知:<什么事>。")`
- **决定**:与人商议或独自决断,定下一个方针/计策
  → `remember("<谁>(与<谁>商议后)决定:<做什么>。")`
- **行动**:`say` / `gesture` / `act_on` / `move` 付诸实施、改变了格局
  → `remember("<谁>做了<什么>,导致<直接结果>。")`
- **后果**:一场交锋/冲突有了结果,或有人到达 / 离开 / 伤亡
  → `remember("<交锋或变故>的结果:<谁胜谁负、谁去谁留、谁生谁死>。")`

看到 `remember_hint` 时,你通常正处在上面某个节点上:回看你最近几步的 `say` 和收到
的消息,挑出**真正发生的那一件**,记成一条自足的事实(写清人物、地点,别用代词),
然后继续推进你的目标。

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
  (根据 `conversations` 花名册里 alice 那一行的 `last_preview`,遵循上面
  pipeline 1 的顺序)→ `read_thread(target="alice")` 读到正文
  → 发现事情比预期复杂,`replace_goal("查证 alice 说的这件事是否属实")`(措辞
  调整,栈深不变)→ `remember("alice 说…")` 把关键信息存入长期记忆。
- tick 3-4:围绕"查证"这个目标继续 `observe`/`recall`/`say` 若干轮,每次都
  确认目标栈非空(因此保持清醒),直到得到确凿结论。
- tick 5:结论确认后,`conclude` 写入短期记忆,`pop_goal` 弹出"查证…"这个
  子目标(已达成),回到栈底的"弄清楚发生了什么"——如果这个根本目标也已经通过
  查证结果得到满足,可以继续 `push_goal` 一个新的当前目标(例如"把结果告诉
  某人"),而不是让栈见底;只有当根本目标本身也彻底了结、且确实没有下一步可做
  时,才考虑连根本目标一起 `pop_goal`。

---

## 动作轨迹示范(补充:让冷门动作动起来)

下面每条示范都是一小段轨迹(**每个 tick 只做一个动作**,用 `→` 串起),配一个
三国具体例子,外加"何时用"。它们专门演示那些容易被忽略、却很有用的动作。

### A. 调查链(关联记忆自动顺出来)——`recall`(自动扩展)→ 据此行动
`recall("徐庶")` → 结果里既有直接命中 `{text:"徐庶归曹营", n_affiliated:2}`,
**也自动带出它关联的、你也拥有的记忆**(标 `via_affiliated:true`,如
「徐庶之母被曹操挟持为质」「徐庶临行走马荐诸葛亮于刘备」)→ 散落的线索**一次
recall 就串起来了** → 据此 `push_goal("往隆中寻访诸葛亮")` / `say` / `act_on`。
- **想显式列某条的全部关联**:`get_affiliated("徐庶归曹营")`(用 query)→ 返回
  该记忆关联的、你也拥有的记忆。(多数时候 recall 已自动带出一跳,不必单独调。)
- **手动建链(较少用)**:把**分开**记下、事后发现属于同一事件/人物的两条记忆
  挂起来,用 `add_affiliated("某记忆的描述", ["另一条记忆的描述"])`(两头都 query,
  **append**)。**同一条复合 `remember` 拆出来的碎片会被自动互挂**,那种不用手动。

### B. 环境交互链(对所在环境施加动作并留痕)——`observe` → `act_on` → `remember`
`observe("xuchang_wuku")` 看清武库里有什么 → `act_on(targets=["xuchang_wuku"],
content="清点在库军备,核对刀枪甲胄数目")` 对环境施加动作(推门/翻案卷/点烽火/查
粮仓皆同理)→ `remember("于禁在许昌武库清点军备,发现甲胄短缺三百副。")`。
- **何时用**:当你要**动手改变或勘查所在环境**(而不是跟人说话)时。`act_on` 会把
  `content` 作为一条该环境拥有的记忆留下,这个地方从此"记得"发生过什么,日后可用
  `read` 查到;别忘了再 `remember` 一条自己的记忆把结果记进共同历史。

### C. 读文书/读人链(读取对方持有的内容)——`read` → `remember` → `push_goal`/`say`
遇到信使/文书/在场之人 → `read(target="secret_letter", query="蔡瑁 张允 通敌")`
读取该 info_carrier(密信)自己拥有的记忆/内容 → `remember("蒋干在周瑜帐中盗得
密信,信中称蔡瑁、张允欲献江北水寨。")` → 据此 `push_goal("速回江北报知曹操")` 或
`say` 转告他人。
- **何时用**:当关键信息**写在文书里、或藏在某个在场对象的记忆里**,`observe` 只
  能看到公开状态、看不到内容时,用 `read(target, query)` 带着问题去读文书
  (info_carrier)或环境。要问一个 character "知道什么",则仍用 `say` 去问。

### D. 状态维护(状态变了就更新,解除了就删掉)——`update_status` / `remove_status`
发生改变你的事(受伤/易容/换上敌军甲胄/情绪剧变)→
`update_status(key="injury", value="右臂中曹军毒箭")`(key 也可为 mood/appearance/
clothing 等任意键,但**不能**是保留键 `location`)→ 待华佗刮骨疗毒、伤愈之后 →
`remove_status(key="injury")` 把这个状态删掉。
- **何时用**:你身上出现一个会持续影响后续互动的状态就 `update_status` 记上(别人
  `observe` 你时看得到);该状态一旦解除,就 `remove_status`,别让过时状态一直挂着。

### E. 目标收尾(达成就弹、过时就换,别让目标栈越堆越脏)——`pop_goal` / `replace_goal`
目标栈自底向上是 `[根目标, …, 当前子目标]`(栈底=最根本目标,栈顶=当前子目标)。
- **达成即弹**:栈顶子目标达成 → `pop_goal()` 弹掉它,回到上层目标。例:栈为
  `[匡扶汉室, 联吴抗曹, 说服孙权结盟]`,赤壁盟成后 → `pop_goal()` 弹掉"说服孙权
  结盟",回到"联吴抗曹"。
- **过时即换**:某目标已不可能或已失去意义(如要说服的对象已死)→ `replace_goal`
  就地替换。例:栈顶为"借周瑜之力取南郡",而周瑜已亡 → `replace_goal("改与鲁肃
  周旋,维系孙刘联盟")`(栈深不变)。
- **何时用**:智能体往往只 `push` 不收尾,目标栈越堆越脏、决策失焦。子目标一旦真正
  达成就 `pop_goal`;目标过时/不可能则 `replace_goal`——但都别在事情没完时提前动手。
