"""One-off: enrich 俄乌 registry with institutional actors, then re-run the
owner-ASSIGN step over the existing sedimented memories (atomize untouched).

Why: the war timeline's events are mostly performed by collective actors
(armies, ministries, alliances) that were absent from the registry, so 65% of
memories had location-only owners. This adds 16 institutions (as `characters`)
+ 3 missing HQ environments, reconstructs each event group from the affiliated
links, and re-assigns owners per event with the enriched role table.

Run: venv/bin/python -m experiments.reassign_ru_owners
"""
import asyncio
import json
import os

from society.run import _build_llm_and_embed
from society.history_extract import _assign_prompt, _RegistryResolvers
from society.extract import _extract_json_block

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SC = os.path.join(BASE, "scenarios")
REG = os.path.join(SC, "russia_ukraine.yaml.registry.json")
LTM = os.path.join(SC, "russia_ukraine.yaml.ltm.json")

INSTITUTIONS = [
    # ---- Russian side ----
    ("russian_forces", "Russian Armed Forces", "俄罗斯武装力量:俄军(陆海空天)整体,执行入侵作战、导弹与无人机打击",
     ["Russian forces", "Russian troops", "Russian military", "Russian army", "俄军"], "russia"),
    ("russian_mod", "Russian Ministry of Defence", "俄罗斯国防部:战况通报与军事决策",
     ["Russian Defense Ministry", "Russian Defence Ministry", "Russia's Ministry of Defence"], "moscow"),
    ("kremlin", "Kremlin", "克里姆林宫/俄联邦政府:政治决策中枢(动员令、并吞、谈判立场)",
     ["Russian government", "Moscow government", "Russian presidential administration"], "moscow"),
    ("black_sea_fleet", "Russian Black Sea Fleet", "俄黑海舰队:黑海作战与封锁(莫斯科号、塞瓦斯托波尔)",
     ["Black Sea Fleet"], "crimea"),
    ("wagner_group", "Wagner Group", "瓦格纳雇佣兵集团:巴赫穆特攻坚、2023-06 兵变",
     ["Wagner", "Wagner PMC", "Wagner mercenaries"], "russia"),
    ("fsb", "FSB", "俄联邦安全局:情报与国内安全(克里米亚大桥调查、抓捕)",
     ["Federal Security Service"], "moscow"),
    # ---- Ukrainian side ----
    ("ukrainian_forces", "Armed Forces of Ukraine", "乌克兰武装部队:防御反攻、防空拦截、战报主体",
     ["Ukrainian forces", "Ukrainian troops", "Ukrainian military", "Ukrainian army", "AFU", "ZSU", "乌军"], "ukraine"),
    ("ukrainian_mod", "Ministry of Defence of Ukraine", "乌克兰国防部:军事政策与战况通报",
     ["Ukrainian Defense Ministry", "Ukraine's Ministry of Defence"], "kyiv"),
    ("ukrainian_government", "Government of Ukraine", "乌克兰政府:民事决策(戒严、外交、重建、求援)",
     ["Ukrainian government", "Kyiv government", "Zelenskyy administration"], "kyiv"),
    ("gur", "Defence Intelligence of Ukraine (GUR)", "乌国防情报总局:军事情报与特种行动",
     ["GUR", "HUR", "Ukrainian military intelligence"], "kyiv"),
    ("sbu", "Security Service of Ukraine (SBU)", "乌克兰安全局:反谍与安全行动",
     ["SBU"], "kyiv"),
    ("azov_regiment", "Azov Regiment", "亚速团:马里乌波尔/亚速钢铁厂防御战当事部队",
     ["Azov", "Azov Battalion", "Azov Brigade"], "mariupol"),
    # ---- International ----
    ("nato", "NATO", "北约:军援协调、东翼增兵、瑞典芬兰入盟进程",
     ["North Atlantic Treaty Organization"], "brussels"),
    ("eu", "European Union", "欧盟:制裁方案、财政援助、候选国地位",
     ["EU", "European Commission"], "brussels"),
    ("un", "United Nations", "联合国:决议、黑海粮食协议斡旋、人道通道",
     ["UN", "United Nations Security Council", "UNSC"], "new_york"),
    ("iaea", "IAEA", "国际原子能机构:扎波罗热核电站安全危机核心机构",
     ["International Atomic Energy Agency"], "vienna"),
]

NEW_ENVS = [
    ("brussels", "Brussels", "比利时首都,北约与欧盟总部所在地"),
    ("new_york", "New York", "联合国总部所在地"),
    ("vienna", "Vienna", "奥地利首都,国际原子能机构总部所在地"),
]


def enrich_registry() -> dict:
    reg = json.load(open(REG, encoding="utf-8"))
    chars = reg.setdefault("characters", [])
    have = {c.get("id") for c in chars}
    added_c = 0
    for cid, name, profile, aliases, _loc in INSTITUTIONS:
        if cid in have:
            continue
        chars.append({"id": cid, "name": name, "aliases": aliases, "profile": profile})
        added_c += 1
    locs = reg.setdefault("locations", [])
    have_l = {l.get("id") for l in locs}
    added_l = 0
    for lid, name, profile in NEW_ENVS:
        if lid in have_l:
            continue
        locs.append({"id": lid, "name": name, "aliases": [], "profile": profile})
        added_l += 1
    json.dump(reg, open(REG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"registry: +{added_c} institutions, +{added_l} envs")
    return reg


def reconstruct_events(entries: list[dict]) -> list[list[dict]]:
    """Event groups = connected components over the (mutual) affiliated links."""
    byid = {e["id"]: e for e in entries}
    parent = {e["id"]: e["id"] for e in entries}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for e in entries:
        for a in e.get("affiliated") or []:
            if a in byid:
                union(e["id"], a)
    groups: dict[str, list[dict]] = {}
    for e in entries:
        groups.setdefault(find(e["id"]), []).append(e)
    evs = list(groups.values())
    for g in evs:
        g.sort(key=lambda e: (e.get("meta", {}).get("story_order") or 0))
    evs.sort(key=lambda g: (g[0].get("meta", {}).get("story_order") or 0))
    return evs


async def main():
    reg = enrich_registry()
    resolvers = _RegistryResolvers(reg)
    llm, _ = _build_llm_and_embed(os.path.join(BASE, "config.json"))
    llm.max_concurrency = 8
    llm._semaphore = asyncio.Semaphore(8)

    entries = json.load(open(LTM, encoding="utf-8"))
    events = reconstruct_events(entries)
    print(f"{len(entries)} memories -> {len(events)} event groups")

    sem = asyncio.Semaphore(8)
    changed = [0]
    failed = [0]

    async def reassign(group: list[dict]):
        frags = [e["text"] for e in group]
        # split oversized events into <=20-frag sub-batches, same as the pipeline
        for start in range(0, len(frags), 20):
            batch = group[start:start + 20]
            btexts = frags[start:start + 20]
            prompt = _assign_prompt(btexts, reg, "", scene_context=frags if len(frags) > len(btexts) else None)
            async with sem:
                try:
                    raw = await llm.chat(prompt, bucket="extract")
                    owners_arr = _extract_json_block(raw)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    failed[0] += 1
                    continue  # keep old owners for this batch
            if not isinstance(owners_arr, list):
                failed[0] += 1
                continue
            # pad/truncate to batch size
            owners_arr = (owners_arr + [[] for _ in batch])[: len(batch)]
            for e, refs in zip(batch, owners_arr):
                new_owners = []
                for ref in refs if isinstance(refs, list) else []:
                    got = resolvers.classify(str(ref))
                    if got:
                        cid, _kind = got
                        if cid not in new_owners:
                            new_owners.append(cid)
                if new_owners and sorted(new_owners) != sorted(e.get("owners", [])):
                    e["owners"] = sorted(new_owners)
                    changed[0] += 1
                # no valid owners -> keep old owners (fallback)

    results = await asyncio.gather(*(reassign(g) for g in events), return_exceptions=True)
    for r in results:
        if isinstance(r, asyncio.CancelledError):
            raise r

    json.dump(entries, open(LTM, "w", encoding="utf-8"), ensure_ascii=False)
    usage = llm.usage().get("_total")
    print(f"done: owners changed on {changed[0]} memories, {failed[0]} batch failures (old owners kept)")
    print(f"usage: {json.dumps(usage)}")


if __name__ == "__main__":
    asyncio.run(main())
