# AgentSociety — 多智能体互动框架设计 Spec(一期:基础设施)

**日期:** 2026-07-08
**状态:** 草稿(待用户审阅)
**位置:** `agentsensus/`(仓库根目录下,与 BookWorld/、GMemory/ 平级,零代码依赖它们)
**分期:** 一期只做基础设施(本 spec);评估 benchmark 二期单独出 spec,本期以事件日志、统计快照、预算计数为其预留数据源。

---

## 1. 定位

从零实现一个多智能体互动框架:每个智能体拥有结构化短期记忆与共享长期记忆,在各自的 observation→action 循环中异步运行,通过消息队列交互;框架提供从小说/文本自动初始化场景(含地图)的抽取器、按全局时钟输出的剧本生成器、以及跨智能体长期记忆的共识压缩机制。目标规模:**数百个智能体**。

**技术底座:** Python 3.10+、asyncio 单进程、独立异步 OpenAI 兼容 LLM client(chat + embedding)、ChromaDB 向量库、pytest。

---

## 2. 目录结构

```
agentsensus/
├── config.json                 # API key、模型名、并发/预算/各默认参数
├── society/
│   ├── kernel.py               # tick 调度、消息路由、同步 action 执行、在场索引、静止检测
│   ├── agent.py                # Agent 外壳:STM + observation-action 循环
│   ├── stm.py                  # FIFO 缓存 / 目标栈 / 状态寄存器 / 收件队列视图
│   ├── actions.py              # Action 数据类 + 注册表 + 执行器(同步/异步分派 + 校验)
│   ├── brains/
│   │   ├── base.py             # Brain 接口:async decide(view) -> Action
│   │   ├── llm_brain.py        # 人物/拟人生命(注入 actions skill)
│   │   ├── rule_brain.py       # 简单环境(python 规则)
│   │   └── retrieval_brain.py  # 信息载体(被 read 时检索语料作答,零 LLM)
│   ├── ltm.py                  # 共享向量库 + owner 集合 + 共识(增删改) + 规范化门
│   ├── llm.py                  # 异步 LLM client:信号量限流 + 重试退避 + 预算熔断
│   ├── embeddings.py           # embedding 封装(与 llm.py 同 client 风格)
│   ├── events.py               # 全局事件日志(JSONL,tick + seq)
│   ├── metrics.py              # 周期统计快照(共识占比 / 交流拓扑 / owner 快照)
│   ├── scenario.py             # 场景 YAML 加载器 + 种子记忆入库
│   ├── extract.py              # 小说/文本 → 场景 YAML 抽取器(CLI)
│   ├── screenplay.py           # 剧本生成器(离线,读 events.jsonl)
│   ├── run.py                  # 运行器 CLI:--scenario --ticks --out
│   ├── skills/
│   │   ├── actions_skill_zh.md # 教智能体使用 action 的 skill(含典型 pipeline)
│   │   └── actions_skill_en.md
│   └── prompts/                # zh.py / en.py 全部提示词
├── docs/
│   ├── specs/                  # 本文件
│   └── actions.md              # action 参考手册(人类读者版)
├── scenarios/                  # 场景 YAML + 信息载体语料
└── tests/
```

---

## 3. 时间模型:tick 屏障调度

- 全局时钟 `t = 0, 1, 2, …`。**每个 tick,每个"醒着"的智能体恰好完成一次 action→result 循环。** tick 内各智能体的 decide/execute 用 asyncio 并发执行(受 LLM 信号量限流),全部完成后时钟 +1。
- **消息投递:t 时发出的消息在 t+1 对接收方可见**(投递顺序与 tick 内完成先后无关 → 可复现)。
- **休眠:** 收件队列空且目标栈空的智能体不被调度(零 LLM 成本),队列来消息后于下一 tick 唤醒。`wait` 同理跳过 tick。
- **在途:** 移动中的智能体连续 N 个 tick 不被调度,到达时由内核推送"已到达"消息唤醒。
- **空转快进:** 全员休眠但有人在途/有在飞消息时,tick 无 action 空转推进;全员休眠且无在途无在飞 = **静止态**。
- **停止条件(可组合):** `max_ticks`(任意步数)/ `max_wall_time` / 静止态 / 预算熔断。停止时完成当前 tick 再落盘全部输出。

---

## 4. 智能体模型

### 4.1 分类(kind)

| kind | 例子 | 默认 brain | 进在场索引 | 被动接口 |
|---|---|---|---|---|
| `character` | 人、拟人化生命 | LLMBrain | ✅ | 公开状态(被 observe) |
| `environment` | 地点、建筑 | RuleBrain(可换 LLMBrain) | ❌(它就是"场") | observe(含在场者集合)、act_on |
| `info_carrier` | 书籍、网站、笔记 | RetrievalBrain | ✅(固定或随身) | read(query) |

kind 与 brain 可独立配置。info_carrier 有 `portable` 标志:随身(跟随携带者 location)或固定于某环境。

### 4.2 短期记忆(STM,四件套)

- **FIFO 缓存:** `deque(maxlen=20)`(可配),元素 `(action, result)`,最近 20 对。
- **目标栈:** list,栈底越 fundamental;初始由场景注入(自底向上);支持 push/pop/replace。
- **状态寄存器:** dict(心情/外表/衣着/地点/任意键)。键分公开/私有:`location`、`appearance`、`clothing` 默认公开,`mood` 默认私有,场景可改。`location` 是结构化保留键(值 = 环境 agent id),仅能通过 `move` 修改。
- **消息队列:** `asyncio.Queue`,他人推送的消息落此。

### 4.3 Brain 接口

`async def decide(view: STMView) -> Action`。`STMView` = FIFO 序列化 + 目标栈 + 状态 + 队列深度与队首预览(发送者/类型) + 当前 tick。LLMBrain 的 system prompt = 角色 profile + actions skill(浓缩版) + 输出格式约束(单个 action 的 JSON)。

### 4.4 循环

```
loop:
  view = build_view(stm)
  action = await brain.decide(view)
  result = await kernel.execute(agent, action)   # 同步action当场返回;异步action返回"已发送"
  stm.fifo.append((action, result)); event_log.append(...)
  if inbox.empty() and goal_stack.empty(): await inbox.wakeup()   # 事件驱动休眠
```

---

## 5. Action 体系

所有 action 携带:发起者、目标对象(可多个)、参数。执行器统一校验(目标存在、同地约束、参数 schema),校验失败 → action 失败,错误信息作为 result 写回 FIFO(brain 下轮自行修正)。

### 5.1 同步 action(当场返回结果)

| action | 语义 |
|---|---|
| `pop_message()` | 取出队首消息(完整内容进 FIFO) |
| `peek_inbox()` | 查看队列各消息头(发送者/类型),不出队 |
| `think(question)` | 针对性一次 LLM 推理(输入=STM+question),结论写回 FIFO |
| `conclude(text)` | 不调 LLM,直接把结论记入 FIFO |
| `push_goal(text)` / `pop_goal()` / `replace_goal(text)` | 目标栈操作 |
| `update_status(key, value)` / `remove_status(key)` | 状态寄存器操作(location 除外) |
| `remember(text)` | LTM 插入,先过规范化门再走共识(见 §8) |
| `recall(query, top_k=5)` | LTM 检索(owner 过滤:只能查到自己拥有的条目) |
| `forget(memory_id)` / `revise_memory(memory_id, new_text)` | 共识适配的删/改(见 §8) |
| `observe(target_id)` | 对 character:返回其公开状态(须同地)。对 environment:返回环境公开状态 + **当前在场智能体集合(id+公开状态摘要)**。对 info_carrier:返回其元信息(须同地或随身) |
| `read(carrier_id, query)` | 信息载体检索作答(内核直调其 RetrievalBrain 被动接口,不经其循环;须同地或随身) |
| `move(destination_id)` | 见 §7 |
| `wait(timeout_ticks?)` | 休眠至来消息(或超时),期间跳过 tick |
| `noop()` | 无操作 |

### 5.2 异步 action(结果日后经消息队列回来)

| action | 语义 |
|---|---|
| `say(targets, content)` | 语言交流;targets 显式指定(从 observe 环境获得的在场集合中选),内核校验同地 |
| `gesture(targets, description)` | 肢体/行为表达;同上 |
| `act_on(env_id, action_desc)` | 对环境施动(须在该环境);环境 brain 处理后把结果推回发起者队列 |

消息结构:`{id, correlation_id, sender, recipients, kind(say/gesture/env_result/system/arrival), content, tick_sent}`。回复带 correlation_id 关联原消息。异步 action 发出后循环**不阻塞**;要等回复用 `wait`。

### 5.3 Actions Skill(教智能体的说明书)

`society/skills/actions_skill_{zh,en}.md`:每个 action 的签名/语义/返回 + **典型 pipeline**,至少包含:
- **消息处理:** peek → pop → 依据消息 push 小目标 → 逐步 action 直到达成 → pop 目标;
- **社交:** observe(环境) 获取在场者 → 选 targets → say/gesture → wait 回复;
- **移动:** observe 当前环境 → move(目的地) → 到达消息唤醒 → observe 新环境;
- **记忆卫生:** remember 前先 recall 查重;结论先 conclude 进 FIFO,沉淀确认后再 remember;
- **目标管理:** fundamental 目标在栈底,当前小目标在栈顶,达成即 pop。

LLMBrain 注入浓缩版;场景可为个别智能体追加自定义 skill 文档。

---

## 6. 内核(kernel)

- **tick 调度器:** 维护醒/睡/在途三态集合,逐 tick gather 醒者的一次循环。
- **消息路由:** t 发出 → 暂存 → t+1 入接收方队列并唤醒休眠者。
- **在场索引:** `location_id -> set[agent_id]`,由 move 与初始配置维护;供 observe(环境)与同地校验。
- **被动接口:** environment 的 observe/act_on(RuleBrain 时同步执行;LLMBrain 环境的 act_on 走异步消息)、info_carrier 的 read,由内核直接调用,不占用目标的 tick。
- **静止检测与停止条件:** 见 §3。
- **预算与限流:** 见 §9。

---

## 7. 地图与移动

- 场景含 `map`:节点 = 全部 environment agent,边 = `(a, b, distance)`(单位 tick)。**缺省全联通、两两距离 20**(可配)。
- `move(destination)`:校验 destination 为 environment 且与当前位置联通 → 本 tick 离开(原环境收到"离开"系统消息,在场索引移除)→ 在途 `distance` 个 tick(不被调度)→ 到达(目的环境收"到达"消息,在场索引加入,自己收"已到达"消息唤醒,status.location 更新)。
- 一期不做:途中相遇、中途改道、地图动态变更。

---

## 8. 共享长期记忆与共识

单一 Chroma collection(显式传 embedding),每条:`{id, text(原子记忆), owners: set[agent_id], created_at, source(scenario_seed/runtime), scenario, tick}`。

### 8.1 规范化门(remember 与种子入库的前置)

- 配置 `memory_max_chars`(默认 **80**)。
- 启发式检查:超长,或含多义征兆(分号/句号多句、并列连接词、多谓语)→ 触发一次 LLM **规范化**调用:拆解(多义 → 多条)或压缩(冗长 → 精简),输出 JSON 数组,每条为主谓宾+必要定状的原子短句且 ≤ 上限;达标输入直接通过(零 LLM 成本)。
- 规范化产物逐条进入共识插入。

### 8.2 共识插入(增)

1. embedding 检索 top-5 中相似度 ≥ 阈值(默认 **0.86**,可配)的候选;
2. 无候选 → 直接新增(owners = {当前 agent});
3. 有候选 → 一次 LLM 批量判定语义等价;
4. 等价 → **取两者中较短文本**留存(若新文本更短则替换原条目文本并重算 embedding),owners ∪= {当前 agent},不新增;不等价 → 新增。

### 8.3 删与改

- **forget:** 仅把自己移出 owners;owners 变空才物理删除(他人仍共享则保留)。
- **revise_memory:** = 对旧条目执行 forget 语义 + 新文本走一遍规范化门与共识插入。

### 8.4 检索

`recall(query, top_k)`:owner 过滤(只检索 owners 含自己的条目),embedding 相似度排序。

---

## 9. LLM client 与成本控制

- 独立异步 OpenAI 兼容 client(chat + embedding),key/模型名从 `agentsensus/config.json` 读。
- 全局 `asyncio.Semaphore` 限并发(默认 **16**,可配);指数退避重试(最多 3 次)。
- **运行级预算熔断:** 最大 LLM 调用次数 / 最大 token(可配);触发即优雅停止(完成当前 tick、落盘全部输出)。
- 所有调用计数按用途分桶记录(decide/think/consensus/normalize/extract/screenplay),写入 run 输出,供二期 benchmark 使用。

---

## 10. 场景与预配置

### 10.1 场景 YAML(单一权威格式,手写与抽取共用)

```yaml
scenario: red_chamber_demo
language: zh
defaults: {fifo_size: 20, memory_max_chars: 80, distance: 20, stats_interval: 10}
agents:
  - id: lin_daiyu
    kind: character
    brain: llm
    profile: "..."
    status: {location: xiaoxiang_guan, mood: "忧郁", appearance: "...", clothing: "..."}
    private_status_keys: [mood]
    goals: ["求得安身与真情(fundamental)", "弄清宝玉真心(当前)"]   # 自底向上
    seed_memories: ["黛玉葬花于沁芳闸畔", ...]                    # 入库走规范化+共识
  - id: xiaoxiang_guan
    kind: environment
    brain: rule
    profile: "潇湘馆,竹影参差……"
  - id: shitou_ji
    kind: info_carrier
    brain: retrieval
    portable: false
    location: daguan_yuan
    corpus: corpora/shitou_ji.txt
map:
  default_distance: 20
  edges:                       # 省略的配对回落默认全联通+default_distance
    - [xiaoxiang_guan, hengwu_yuan, 5]
kickoff:
  - {to: [lin_daiyu], kind: system, content: "宝玉遣人送来旧帕两方……"}
```

### 10.2 小说/文本抽取器(`society/extract.py`)

输入一本小说或一大段文字(+ 可选:聚焦角色、`--max-agents`、指定起始戏剧时刻),输出上述标准 YAML + 信息载体语料文件。流水线(map-reduce 处理长文本,全走预算 client):

1. 分块(章节/长度,带重叠),逐块抽取后合并去重(角色按名/别名归并,地点同理);
2. 角色抽取 → character(profile / 初始状态 / 动机分层 → 目标栈);
3. 地点抽取 → environment + **地图推断**(文本中的空间关系与路程 → 联通边与距离;未提及配对回落默认);
4. 信息载体抽取 → info_carrier(语料 = 相关原文摘录落盘);
5. 种子记忆抽取 → 逐角色原子条目(入库时经共识自然合并成多 owner 共享条目);
6. kickoff 生成(抽取或按用户提示指定起始时刻)。

每步输出按 JSON schema 校验,失败重试;抽取为一次性离线操作,产物即缓存,人可先审改再加载。

---

## 11. 运行器与输出

CLI:`python -m society.run --scenario scenarios/x.yaml --ticks 500 --out runs/x_500`

```
runs/<run_name>/
├── events.jsonl               # 全局事件日志:每 action/result/消息投递一条(tick+seq+agent)
├── transcripts/<agent>.md     # 每个智能体逐步 action-result 流水账(人类可读)
├── screenplay.md              # 剧本
├── stats/tick_000010.json …   # 每 stats_interval(默认 10)tick 一份:
│    ├ consensus_ratio         #   共识条目(owners≥2)/ 总条目
│    ├ comm_graph              #   截至当前交流拓扑:say/gesture 计边,次数为 weight(含有向计数+无向聚合)
│    └ consensus_owners        #   每个共识条目 {id, text, owners} 快照
├── llm_usage.json             # 分桶调用/token 计数
└── config_snapshot.yaml       # 完整配置快照(可复现)
```

可选 `--checkpoint`(已实现,见 `society/persistence.py`):每 stats_interval
落一份可恢复状态到 `{out}/checkpoint.json`(STM + LTM 全息导出含 embedding +
tick + event_seq + presence + 待投递消息 + 通信图有向计数),运行停止时再补
落一次;`--resume --out <dir> --ticks N` 从中恢复并继续跑 N 个 tick,长跑
防崩、可续跑。

### 剧本生成器(`society/screenplay.py`,离线)

读 events.jsonl → 按 (tick, seq) 排序、按地点与参与者切幕 → LLM 两阶段:①筛选有展现/文学价值的事件(丢流水账);②渲染剧本格式(幕/场标题含 tick 范围与地点、对白、舞台指示,think/conclude 心理活动作旁白或独白)→ `screenplay.md`。

---

## 12. 默认参数汇总(全部可配)

| 参数 | 默认 |
|---|---|
| FIFO 容量 | 20 对 |
| memory_max_chars | 80 |
| 共识相似度阈值 / top-k | 0.86 / 5 |
| 地图默认距离 | 20 tick |
| stats_interval | 10 tick |
| LLM 并发信号量 | 16 |
| LLM 重试 | 3 次指数退避 |
| 消息投递延迟 | 1 tick |
| recall top_k | 5 |

---

## 13. 失败处理

- brain 输出解析失败:重试(≤3),仍失败该 tick 记 noop + 错误 result;
- LLM 调用失败:退避重试,最终失败按上;
- action 校验失败:错误作为 result 入 FIFO,循环继续;
- 预算熔断/停止条件:完成当前 tick,全量落盘。

---

## 14. 测试策略

pytest + FakeLLM / Fake embedding(参考 BookWorld tests 风格):

- STM 单测(FIFO 淘汰、目标栈、公开/私有状态);
- action 执行器单测(校验规则、同步/异步分派、错误回写);
- kernel 单测(tick 屏障、t+1 投递、休眠/唤醒、在途、静止检测);
- LTM 单测(规范化门触发条件、共识增删改、owner 集合演化、较短文本胜出);
- metrics 单测(三项统计的正确性,合成事件流);
- scenario 加载单测 + extract 器用短文本冒烟(FakeLLM 返回固定 JSON);
- 集成冒烟:3 个 character + 1 个 environment + 1 个 info_carrier,FakeLLM 脚本化跑 30 tick,断言事件日志、统计快照、流水账、剧本文件齐全且结构正确。

---

## 15. 一期不做

- 评估 benchmark(二期独立 spec);
- 跨进程/分布式、UI 可视化;
- 途中相遇、动态地图、耗时可变的移动;
- 远程通信(不同地 say)、广播到整个地图;
- 记忆遗忘曲线/重要性打分(共识机制之外的记忆管理)。

---

## 16. 风险

- **LLM 结构化输出稳定性**(action JSON / 抽取 schema):以 schema 校验 + 重试 + 失败降级(noop)兜底;
- **共识误合并**(相似但不等价):阈值初筛 + LLM 确认双闸;阈值可调,统计快照可观测 owner 演化便于诊断;
- **数百 agent 的成本**:事件驱动休眠 + 信号量 + 预算熔断三重控制;think 等昂贵 action 在 skill 中引导节制使用;
- **tick 屏障的吞吐**:醒着的 agent 数 × 每 tick 一次 LLM;瓶颈在 LLM 并发,信号量可调,休眠机制保证"安静的社会"近乎零成本。
