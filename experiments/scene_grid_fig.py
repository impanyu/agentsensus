"""Draw how one world's screenplay scenes were cut out of spacetime.

Each cell is a (round, location) point: coloured by the agent that acted there,
hatched when several agents acted in the same place and round, white when
nothing happened. The rectangles are the scenes the renderer produced, so the
figure shows the splitting rule directly -- one place, a run of rounds no more
than `scene_gap` apart, capped at `max_span`.

Run: venv/bin/python -m experiments.scene_grid_fig [world]
"""
import json
import os
import sys
from collections import defaultdict

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
import yaml

from society.events import EventLog
from society.screenplay import _is_beat, _dedupe, _split_scenes, _sort_key, _beat_speaker

WORLDS = {
    "three_kingdoms": (["g20", "g40", "g60", "g80"], "scenarios/three_kingdoms.sim.yaml",
                       "runs/g80full_consensus"),
    "red_chamber": (["rc10", "rc40", "rc60", "rc80"], "scenarios/red_chamber.sim.yaml",
                    "runs/rc80full_consensus"),
    "russia_ukraine": (["ru10", "ru20", "ru40"], "scenarios/russia_ukraine.sim.yaml",
                       "runs/ru40full_consensus"),
    "hamlet": (["hl20", "hl30", "hl40"], "scenarios/hamlet.sim.yaml",
               "runs/hl40full_consensus"),
}
PALETTE = ["#2563eb", "#0f9d6b", "#c07a12", "#d63b3b", "#7c3aed", "#0891b2",
           "#be185d", "#4d7c0f", "#b45309", "#0369a1", "#7c9ff5", "#65a30d",
           "#9333ea", "#0d9488", "#dc2626", "#525252"]


def _palette(n):
    """n visually distinct fills. The first sixteen are the hand-picked ones,
    so a small cast (Hamlet) keeps the colours it was published with; beyond
    that, hues are walked by the golden angle at alternating lightness, which
    keeps 30-50 agents apart without hand-mixing that many swatches."""
    import colorsys
    out = list(PALETTE)
    i = 0
    while len(out) < n:
        h = (0.13 + 0.381966 * (i + 1)) % 1.0
        light, sat = (0.38, 0.72) if i % 2 else (0.55, 0.55)
        r, g, b = colorsys.hls_to_rgb(h, light, sat)
        hexc = "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))
        if hexc not in out:
            out.append(hexc)
        i += 1
    return out


def build(world="hamlet"):
    stages, scenario, case_dir = WORLDS[world]
    cfg = yaml.safe_load(open(scenario, encoding="utf-8"))
    tpath = f"{case_dir}/case_study/translations.json"
    gloss = json.load(open(tpath, encoding="utf-8")).get("agents", {}) if os.path.exists(tpath) else {}
    names = {a["id"]: gloss.get(a["id"]) or a["id"].replace("_", " ").title()
             for a in cfg["agents"] if a.get("id")}

    events = []
    for st in stages:
        p = f"runs/{st}_consensus/events.jsonl"
        if os.path.exists(p):
            events.extend(EventLog.load(p))
    beats = _dedupe(sorted((e for e in events if _is_beat(e)), key=_sort_key))
    scenes = _split_scenes(beats, 5)

    cells = defaultdict(list)
    current = None
    for b in beats:
        if b.get("location"):
            current = b["location"]
        cells[(current, b.get("tick", 0))].append(_beat_speaker(b))

    locations = sorted({k[0] for k in cells},
                       key=lambda L: (min(t for (l, t) in cells if l == L), L))
    # the axis is the whole run, round 1 to the last round simulated, not just
    # the stretch that happens to contain beats -- a quiet opening or a silent
    # last round is part of the picture
    last = max(e.get("tick", 0) for e in events)
    rounds = list(range(1, last + 1))
    actors = sorted({a for v in cells.values() for a in v})
    pal = _palette(len(actors))
    colour = {a: pal[i] for i, a in enumerate(actors)}
    return names, cells, locations, rounds, actors, colour, scenes


def svg(world="hamlet", max_width=790):
    """The grid: one row per place, one column per round, sized to the column.

    The cell is what shrinks when a run is long -- a colour block stays
    readable at six pixels wide, where scaling the whole drawing down would
    take the labels with it. Scene numbers sit in the gap above their
    rectangle so they never cover a cell, however narrow it gets.
    """
    names, cells, locations, rounds, actors, colour, scenes = build(world)

    def _w(text):  # rough advance width at 11.5px, CJK counted double
        return sum(11.5 if ord(c) > 0x2E80 else 6.2 for c in text)

    left = max(118, 14 + max(_w(names.get(l, l)) for l in locations))
    cw = min(17, max(5, (max_width - left - 16) / len(rounds)))
    gap = 2 if cw >= 12 else (1.5 if cw >= 8 else 1)
    # narrow cells get shorter rows too, so a cell stays a block rather than
    # a tall bar and the whole figure keeps a readable proportion
    ch, cellh = (34, 25) if cw >= 12 else (25, 17)
    top = 46
    W = left + cw * len(rounds) + 16
    legend_rows = (len(actors) + 3) // 4
    H = top + ch * len(locations) + 36 + legend_rows * 20 + 24
    ri = {r: i for i, r in enumerate(rounds)}
    li = {l: i for i, l in enumerate(locations)}
    every = 5 if cw >= 12 else (10 if cw >= 7 else 20)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" role="img" '
           f'aria-label="Grid of rounds by '
           f'location for the {world} run, each cell coloured by the agent that acted '
           f'there, with the screenplay scenes outlined" style="max-width:100%;height:auto">',
           f'<rect width="{W:.0f}" height="{H:.0f}" rx="6" fill="#ffffff"/>',
           '<g font-family="system-ui,sans-serif" fill="#1f2937">']

    for r in rounds:
        if r % every == 0 or r == rounds[0]:
            out.append(f'<text x="{left + ri[r]*cw + cw/2:.1f}" y="{top-15}" '
                       f'text-anchor="middle" font-size="11" opacity=".7">{r}</text>')
    out.append(f'<text x="{left + cw*len(rounds)/2:.1f}" y="{top-31}" text-anchor="middle" '
               f'font-size="12" opacity=".75">round</text>')

    for loc in locations:
        y = top + li[loc] * ch
        out.append(f'<text x="{left-8:.0f}" y="{y+cellh/2+4:.1f}" text-anchor="end" '
                   f'font-size="11.5">{names.get(loc, loc)}</text>')
        for r in rounds:
            x = left + ri[r] * cw
            who = cells.get((loc, r))
            if not who:
                fill, extra = "#ffffff", ' stroke="#cbd5e1"'
            elif len(set(who)) == 1:
                fill, extra = colour[who[0]], ""
            else:
                fill, extra = "url(#mix)", ""
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{cw-gap:.1f}" height="{cellh}" '
                       f'rx="{1.5 if cw < 10 else 2}" fill="{fill}"{extra}/>')

    for n, sc in enumerate(scenes, start=1):
        y = top + li[sc["location"]] * ch
        x0 = left + ri[sc["tick_start"]] * cw
        x1 = left + ri[sc["tick_end"]] * cw + cw - gap
        out.append(f'<rect x="{x0-2:.1f}" y="{y-2}" width="{x1-x0+4:.1f}" height="{cellh+4}" '
                   f'rx="3" fill="none" stroke="#1f2937" stroke-width="1.3"/>')
        # the number lives in the gap above its scene, never on top of a cell
        out.append(f'<text x="{x0-1:.1f}" y="{y-4}" font-size="9" font-weight="700" '
                   f'fill="#1f2937" stroke="#ffffff" stroke-width="2.4" '
                   f'paint-order="stroke">{n}</text>')

    ly = top + ch * len(locations) + 26
    out.append(f'<text x="4" y="{ly}" font-size="11.5" opacity=".75">'
               f'agent acting in that round and place:</text>')
    for i, a in enumerate(actors):
        col, row = i % 4, i // 4
        x = 4 + col * (W // 4)
        y = ly + 16 + row * 20
        out.append(f'<rect x="{x:.0f}" y="{y-9}" width="11" height="11" rx="2" fill="{colour[a]}"/>')
        out.append(f'<text x="{x+16:.0f}" y="{y}" font-size="11">'
                   f'{names.get(a, a)}</text>')
    y = ly + 16 + legend_rows * 20
    out.append(f'<rect x="4" y="{y-9}" width="11" height="11" rx="2" fill="url(#mix)"/>')
    out.append(f'<text x="20" y="{y}" font-size="11">several agents</text>')
    out.append(f'<rect x="{W//4+4:.0f}" y="{y-9}" width="11" height="11" rx="2" fill="#ffffff" '
               f'stroke="#cbd5e1"/>')
    out.append(f'<text x="{W//4+20:.0f}" y="{y}" font-size="11">nothing happened</text>')

    out.insert(1, '<defs><pattern id="mix" width="5" height="5" patternUnits="userSpaceOnUse" '
                  'patternTransform="rotate(45)"><rect width="5" height="5" fill="#2563eb" '
                  'opacity=".25"/><line x1="0" y1="0" x2="0" y2="5" stroke="#2563eb" '
                  'stroke-width="2.4"/></pattern></defs>')
    out.append("</g></svg>")
    return "\n".join(out)


def stats(world):
    """What the screenplay of `world` was cut from: rounds, scenes, beats, cast, places.

    Read from the event log, not from the rendered markdown, so the numbers hold
    whichever language the screenplay was rendered into.
    """
    _, cells, locations, rounds, actors, _, scenes = build(world)
    return {"rounds": (rounds[0], rounds[-1]), "scenes": len(scenes),
            "beats": sum(len(v) for v in cells.values()),
            "speakers": len(actors), "places": len(locations)}


if __name__ == "__main__":
    world = sys.argv[1] if len(sys.argv) > 1 else "hamlet"
    path = f"runs/scene_grid_{world}.svg"
    open(path, "w", encoding="utf-8").write(svg(world))
    print("wrote", path)
