# 历史沉淀模式(Whole-Book Initialization v2)— 设计 Spec

**日期:** 2026-07-11
**状态:** 已与用户确认方向(时间标记双轨、先用三国前 20 回验证)
**前置:** 一期基础设施 + checkpoint 持久化已完成(61+ 测试);别名解析与剧本 grounding 修复并行进行中。

---

## 1. 核心理念

把整本书当作**已经发生的历史时间轴**,而非某一时刻的快照:

- 逐块(chunk)沿时间轴抽取每个角色的经历,作为带时间标记的原子记忆,经现有**规范化门 + 共识机制**沉淀进共享 LTM——共同经历(桃园结义)自动合并为多 owner 共享条目;
- 模拟的是全书结束之后的**后传**;
- **已死角色也建 agent**(archive):照常拥有记忆(可参与共识合并、可被生者经共享条目"共同记得"),但永不参与运行;
- **不抽取目标**:后传开局所有角色目标栈为空,由 agent 自己 recall 过去 + 观察现状后 figure out(goal 自举)。

旧的"快照式抽取"(extract.py 现有路径)保留,用于短文本/单场景;历史沉淀是**新增模式**。

## 2. 用户已确认的决策

1. **时间标记双轨**:记忆文本带时间前缀(如"【建安五年】关羽挂印封金离开曹营"),同时 metadata 增加可排序的 `story_order`(int,来源块序号×1000+块内序号)供分析/排序;`story_time`(自由文本,可空)也入 metadata。
2. **验证语料**:先用三国演义**前 20 回**(~15 万字,≈19 块)验证管线,再考虑全本。

## 3. 抽取管线(两个 pass)

### Pass 1 — 注册表(便宜,先行)
逐块生成短摘要 → 汇总后一次(或分批)LLM 调用产出**全书注册表**:
```json
{"characters": [{"id": "caocao", "name": "曹操", "aliases": ["孟德","丞相","阿瞒"], "profile": "..."}],
 "locations":  [{"id": "xuchang", "name": "许昌", "profile": "..."}],
 "carriers":   [...]}
```
- 别名表是解决跨块归并的关键:**封闭世界原则**——Pass 2 只允许把记忆归到注册表中的规范 id,prompt 中附别名表。
- 注册表落盘(`<out>.registry.json`),人工可审改后再跑 Pass 2(与场景 YAML 同样的人工在环设计)。

### Pass 2 — 记忆沉淀(逐块,时间轴顺序)
对每块,一次 LLM 调用抽取:
```json
{"memories": {"<canonical_id>": ["【时间】原子记忆", ...]},
 "state_updates": [{"id": "...", "location": "loc_id|null", "alive": true|false}],
 "story_time": "本块大致时代(自由文本)"}
```
- 记忆逐条经 `SharedMemory.remember(agent_id, text, source="history", story_order=..., story_time=...)` 入库(共识照常);
- 终态表:沿块序 last-write-wins,得到每人书末的 alive/location;死者的 location 记为其"殁地"仅供档案。

### 组装
输出标准场景 YAML(+ 已在库里的 LTM?见 §5 持久化):
- 活人 → `kind: character, brain: llm, goals: []`(空目标栈),status 只含书末 location(+ name);
- 死者 → 同上但 `archived: true`;
- 地点/信息载体照常;地图边由 Pass 1 注册表阶段的空间关系抽取(可缺省全联通);
- kickoff:用户提供后传前提(`--hints`),或 LLM 依据书末状态生成"后传起点"事件,推给若干在世主要角色。

## 4. 框架改动

### 4.1 `archived` 标志
- 场景 YAML agent 可带 `archived: true`;
- Kernel:archived agent 不参与调度资格判定、不进在场索引、observe 目标为 archived → 失败("此人已故");
- 其记忆正常存在于共享 LTM(owner 身份保留),生者 recall 共享条目不受影响。

### 4.2 goal 自举
- view:当目标栈为空时附加提示字段 `"goal_hint": "你的目标栈为空——先 recall 你的过去,结合现状 conclude,然后 push_goal 设立根本目标与当前目标"`;
- skills(zh/en)新增"开局自省"pipeline:recall(关于自己)→ observe(环境)→ conclude → push_goal(fundamental)→ push_goal(当前)。

### 4.3 LTM 元数据扩展
- `remember(...)` 及底层插入接受可选 `story_order: int`、`story_time: str`,写入条目 metadata;共识合并时保留**较小的 story_order**(更早的史实时间);导出/checkpoint 全息包含。

## 5. 沉淀产物的持久化

Pass 2 的 LTM 沉淀成本高(千条级),**必须可复用**:沉淀完成后自动 `SharedMemory.export()` 写 `<out>.ltm.json`(全息,含 embedding);`build_society` 检测到场景 YAML 同名 `.ltm.json` 时用 `restore()` 灌入而非重放种子(YAML 中 `ltm_file: xxx.ltm.json` 字段显式指向)。快照式旧路径不受影响。

## 6. CLI

```
python -m society.extract --input book.txt --output scenarios/x.yaml \
    --mode history [--registry-only] [--registry path.json] \
    [--max-agents N,仅约束"活跃后传阵容",archived 不计入] [--hints "后传前提"]
```
- `--registry-only`:只跑 Pass 1 供人工审改;
- 再次运行带 `--registry` 跳过 Pass 1。

## 7. 测试

- 注册表 pass:FakeLLM 两块文本 → 合并注册表、别名齐全;
- 记忆 pass:别名归并到规范 id;story_order 单调;state_updates last-write-wins;死者标 archived;
- 共识跨角色合并:两角色同一事件 → 多 owner + story_order 取较小;
- archived:不调度/不在场/observe 报错/记忆保留;
- goal 自举:空目标栈 view 含 goal_hint;skill 文档含开局自省;
- ltm_file 复用:build_society 从 .ltm.json 恢复且零 embed 重算,不重放 seeds;
- 端到端(FakeLLM):两块合成"微型小说"→ history 抽取 → build → 跑 5 tick,活人自举目标,死者沉默。

## 8. 成本预估(三国前 20 回 ≈ 15 万字 ≈ 19 块)

Pass 1:19 次摘要 + 1-2 次汇总;Pass 2:19 次;共识插入:约 400-800 条记忆 × (1 embed + ≤1 等价判定)。gpt-4o-mini 合计 **≈ $1 以内**。全本约 4-5 倍。

## 9. 不做(本期)

- 别名消歧的完美化(注册表人工在环兜底);
- 死者"显灵"参与模拟(archive 即纯档案);
- 按时代切片初始化("从赤壁之战打完开始")——留作 history 模式的显然扩展(state 表按 story_order 截断即可)。
