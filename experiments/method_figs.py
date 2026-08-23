"""Figures 1 and 2 of the paper, drawn as self-contained SVG.

The HTML paper's versions are inline SVG styled by the page's CSS; extracted
on their own they lose their colours (the action pills rendered as blank
boxes in the PDF). These are authored standalone -- every style inline, one
palette shared with the rest of the paper's figures -- and converted to PDF
by the build step.

Run: venv/bin/python -m experiments.method_figs
"""
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

INK, MUT = "#1f2937", "#64748b"
BLUE, BLUE_L, BLUE_D = "#2563eb", "#dbeafe", "#1e3a8a"
GRN, GRN_L, GRN_D = "#059669", "#d1fae5", "#065f46"
AMB, AMB_L, AMB_D = "#d97706", "#fef3c7", "#92400e"
PUR, PUR_L, PUR_D = "#7c3aed", "#ede9fe", "#5b21b6"
RED, RED_L = "#dc2626", "#fee2e2"
F = 'font-family="Helvetica,Arial,sans-serif"'


def T(x, y, s, size=11, fill=INK, anchor="start", weight=None, style=None):
    w = f' font-weight="{weight}"' if weight else ""
    st = f' font-style="{style}"' if style else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}"{w}{st} {F}>{s}</text>')


def person(x, y, stroke=GRN, fill=GRN_L):
    return (f'<circle cx="{x}" cy="{y}" r="9" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>'
            f'<path d="M {x-14},{y+26} C {x-9},{y+12} {x+9},{y+12} {x+14},{y+26}" '
            f'fill="none" stroke="{stroke}" stroke-width="1.6" stroke-linecap="round"/>')


def doc(x, y, w, h, stroke, fill, lines=3):
    fold = 10
    p = (f'<path d="M {x},{y} h {w-fold} l {fold},{fold} v {h-fold} h {-w} z" '
         f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
    for i in range(lines):
        yy = y + 16 + i * 12
        p += (f'<line x1="{x+8}" y1="{yy}" x2="{x+w-8}" y2="{yy}" '
              f'stroke="{stroke}" stroke-width="1.2" opacity="0.55"/>')
    return p


def pill(x, y, w, label, stroke, fill, tfill, dashed=False):
    d = ' stroke-dasharray="4 3"' if dashed else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="22" rx="11" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.3"{d}/>'
            + T(x + w / 2, y + 15, label, 10.5, tfill, "middle"))


DEFS = f'''<defs>
{"".join(f'<marker id="m{n}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>' for n, c in [("i", "#475569"), ("b", BLUE), ("g", GRN), ("a", AMB)])}
</defs>'''


def framework():
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 560" {F} '
         f'style="max-width:100%;height:auto">', DEFS,
         '<rect width="840" height="560" fill="#ffffff"/>']

    # ---- band 1: offline
    s.append(f'<rect x="14" y="10" width="812" height="146" rx="10" fill="#fffbeb" stroke="#fcd34d"/>')
    s.append(T(28, 32, "OFFLINE · sedimentation", 13, AMB_D, weight="bold"))
    s.append(T(812, 32, "runs once, before round 0", 10.5, AMB, "end"))
    s.append(doc(44, 52, 56, 78, AMB, "#ffffff"))
    s.append(T(72, 146, "source text", 11, AMB_D, "middle"))
    s.append(f'<line x1="108" y1="92" x2="142" y2="92" stroke="#475569" stroke-width="1.5" marker-end="url(#mi)"/>')
    s.append(f'<path d="M150,56 L242,56 L208,96 L208,122 L184,122 L184,96 Z" fill="{AMB_L}" stroke="{AMB}" stroke-width="1.6"/>')
    s.append(T(196, 146, "extract + attribute", 11, AMB_D, "middle"))
    s.append(f'<line x1="250" y1="92" x2="284" y2="92" stroke="#475569" stroke-width="1.5" marker-end="url(#mi)"/>')
    for i, lab in enumerate(["event · owners {A, B}", "event · owners {C}", "event · owners {A, D}"]):
        y = 54 + i * 30
        s.append(f'<rect x="290" y="{y}" width="168" height="24" rx="6" fill="{BLUE_L}" stroke="{BLUE}" stroke-width="1.4"/>')
        s.append(T(374, y + 16, lab, 10.5, BLUE_D, "middle"))
    s.append(T(374, 148, "owner-tagged events", 11, BLUE_D, "middle"))
    s.append(f'<path d="M462,66 C620,66 560,196 200,224" fill="none" stroke="{BLUE}" stroke-width="1.8" marker-end="url(#mb)"/>')
    s.append(T(560, 120, "seeds the store", 10.5, BLUE, "middle"))

    # ---- band 2: runtime
    s.append(f'<rect x="14" y="164" width="812" height="272" rx="10" fill="#eff6ff" stroke="#bfdbfe"/>')
    s.append(T(28, 186, "RUNTIME · one world, one store", 13, BLUE_D, weight="bold"))
    # store cylinder
    s.append(f'<path d="M42,230 v118 a74,16 0 0 0 148,0 v-118" fill="{BLUE_L}" stroke="{BLUE}" stroke-width="1.8"/>')
    s.append(f'<ellipse cx="116" cy="230" rx="74" ry="16" fill="#eff6ff" stroke="{BLUE}" stroke-width="1.8"/>')
    s.append(T(116, 288, "long-term memory", 12, BLUE_D, "middle", weight="bold"))
    s.append(T(116, 306, "shared by all", 11, BLUE_D, "middle"))
    s.append(T(116, 396, "internal structure differs per backend", 10, MUT, "middle"))
    # society
    s.append(f'<rect x="308" y="198" width="504" height="228" rx="12" fill="#ecfdf5" stroke="#34d399" stroke-dasharray="6 4"/>')
    s.append(T(800, 216, "the society", 11.5, GRN_D, "end"))
    s.append(person(400, 248)); s.append(T(400, 300, "character", 11, GRN_D, "middle"))
    s.append(person(608, 248)); s.append(T(608, 300, "character", 11, GRN_D, "middle"))
    s.append(person(400, 358)); s.append(T(400, 410, "character", 11, GRN_D, "middle"))
    s.append(f'<line x1="422" y1="244" x2="586" y2="244" stroke="{BLUE}" stroke-width="1.6" marker-start="url(#mb)" marker-end="url(#mb)"/>')
    s.append(T(504, 234, "say · kernel-held thread", 10.5, "#1d4ed8", "middle"))
    s.append(f'<line x1="420" y1="350" x2="592" y2="262" stroke="{BLUE}" stroke-width="1.4" stroke-dasharray="5 4" marker-end="url(#mb)"/>')
    s.append(T(530, 322, "delivered with distance delay", 10, "#1d4ed8", "middle"))
    # environment
    s.append(f'<circle cx="742" cy="242" r="12" fill="#ecfdf5" stroke="{GRN}" stroke-width="1.8"/>')
    s.append(f'<path d="M736,239 l6,8 l6,-8" fill="none" stroke="{GRN}" stroke-width="1.6"/>')
    s.append(T(742, 274, "environment", 10.5, GRN_D, "middle"))
    s.append(T(742, 288, "owns memories,", 10, MUT, "middle"))
    s.append(T(742, 300, "never takes a turn", 10, MUT, "middle"))
    # carrier + read
    s.append(doc(718, 340, 46, 58, AMB, AMB_L, lines=3))
    s.append(T(741, 416, "info carrier", 10.5, AMB_D, "middle"))
    s.append(f'<line x1="424" y1="364" x2="712" y2="372" stroke="{GRN}" stroke-width="1.5" marker-end="url(#mg)"/>')
    s.append(T(566, 356, "read", 10.5, GRN_D, "middle"))
    # store <-> society
    s.append(f'<line x1="196" y1="248" x2="304" y2="238" stroke="{BLUE}" stroke-width="1.7" marker-end="url(#mb)"/>')
    s.append(T(250, 230, "recall", 10.5, "#1d4ed8", "middle"))
    s.append(f'<line x1="304" y1="296" x2="196" y2="306" stroke="{BLUE}" stroke-width="1.7" marker-end="url(#mb)"/>')
    s.append(T(250, 290, "remember", 10.5, "#1d4ed8", "middle"))
    s.append(T(250, 326, "both owner-scoped", 10, MUT, "middle"))

    # ---- band 3: actions
    s.append(f'<rect x="14" y="444" width="812" height="106" rx="10" fill="#f8fafc" stroke="#e2e8f0"/>')
    s.append(T(28, 464, "One action per character per round, from a single repertoire", 12, INK, weight="bold"))
    world = [("say", 40), ("read_thread", 78), ("observe", 58), ("move", 44),
             ("act_on", 52), ("read", 42)]
    cog = [("think", 44), ("conclude", 62)]
    x = 28
    row = []
    for lab, w in world:
        row.append(pill(x, 472, w, lab, GRN, GRN_L, GRN_D)); x += w + 6
    for lab, w in cog:
        row.append(pill(x, 472, w, lab, "#94a3b8", "#f1f5f9", "#475569")); x += w + 6
    for lab, w in [("remember", 68), ("recall", 50)]:
        row.append(pill(x, 472, w, lab, BLUE, BLUE_L, BLUE_D)); x += w + 6
    x2 = 28
    for lab, w in [("push_goal", 68), ("pop_goal", 62), ("replace_goal", 84),
                   ("update_status", 90)]:
        row.append(pill(x2, 500, w, lab, PUR, PUR_L, PUR_D)); x2 += w + 6
    row.append(pill(x2, 500, 40, "wait", "#94a3b8", "#f1f5f9", "#475569")); x2 += 46
    row.append(pill(x2, 500, 252, "6 memory-management actions · never used", RED, RED_L, RED, dashed=True))
    s += row
    s.append(T(28, 543, "blue = long-term memory · green = the world · purple = goals · "
                        "each round freezes every view at the barrier, so event order is reproducible",
               10, MUT))
    s.append('</svg>')
    return "\n".join(s)


def qpanel(x, y, w, h, stroke, fill):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.3"/>')


def row(x, y, w, label, stroke, fill, tfill, dashed=False):
    d = ' stroke-dasharray="4 3"' if dashed else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="22" rx="5" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.4"{d}/>'
            + T(x + w / 2, y + 15, label, 10.5, tfill, "middle"))


def backends():
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 660" {F} '
         f'style="max-width:100%;height:auto">', DEFS,
         '<rect width="840" height="660" fill="#ffffff"/>']

    # ---------- (a) Generative-Agents (green)
    s.append(T(20, 26, "(a) Generative-Agents — private streams + reflection tree", 12.5, GRN_D, weight="bold"))
    s.append(qpanel(14, 36, 400, 280, "#a7f3d0", "#f0fdf9"))
    for cx, who in [(110, "A"), (250, "B")]:
        s.append(person(cx, 66)); s.append(T(cx + 20, 70, who, 11, INK, weight="bold"))
    for i, (lab, op) in enumerate([("e · importance .8", 1), ("… · .4", 1), ("… · .9", 1)]):
        s.append(row(50, 96 + i * 30, 124, lab, GRN, "#ffffff", GRN_D))
    for i, lab in enumerate(["e · importance .7", "… · .5", "… · .6"]):
        s.append(row(196, 96 + i * 30, 112, lab, GRN, "#ffffff", GRN_D))
    s.append(row(50, 196, 96, "reflection", GRN, GRN_L, GRN_D, dashed=True))
    s.append(row(50, 226, 108, "reflection²", GRN, GRN_L, GRN_D, dashed=True))
    s.append(f'<path d="M85,186 v6 M105,186 v6" stroke="{GRN}" stroke-width="1.3"/>')
    s.append(T(170, 212, "evidence links,", 10, MUT))
    s.append(T(170, 224, "reflections stack in the lane", 10, MUT))
    s.append(T(322, 120, "recall scores", 10.5, MUT))
    s.append(T(322, 133, "recency ×", 10.5, MUT))
    s.append(T(322, 146, "importance ×", 10.5, MUT))
    s.append(T(322, 159, "relevance", 10.5, MUT))
    s.append(T(214, 268, "event e stored once per witness;", 10.5, GRN_D, "middle"))
    s.append(T(214, 281, "no edge crosses lanes", 10.5, GRN_D, "middle"))
    s.append(T(214, 304, "streams + a private reflection tree", 10, MUT, "middle", style="italic"))

    # ---------- (b) G-Memory (amber)
    s.append(T(446, 26, "(b) G-Memory — two-tier graph, per owner", 12.5, AMB_D, weight="bold"))
    s.append(qpanel(426, 36, 400, 280, "#fcd34d", "#fffdf5"))
    for cx, who in [(540, "A"), (720, "B")]:
        s.append(person(cx, 66, AMB, AMB_L)); s.append(T(cx + 20, 70, who, 11, INK, weight="bold"))
    s.append(T(444, 118, "insight tier", 10.5, MUT))
    s.append(T(690, 104, "distilled every 20", 10, MUT))
    for cx in (540, 720):
        s.append(f'<ellipse cx="{cx}" cy="132" rx="42" ry="16" fill="{AMB_L}" stroke="{AMB}" stroke-width="1.4" stroke-dasharray="4 3"/>')
        s.append(T(cx, 136, "insight", 10.5, AMB_D, "middle"))
    s.append(f'<line x1="444" y1="166" x2="808" y2="166" stroke="{AMB}" stroke-dasharray="3 4" opacity="0.5"/>')
    s.append(T(444, 200, "interaction tier", 10.5, MUT))
    for base, cx in [(478, 540), (658, 720)]:
        for i in range(3):
            lab = "e" if i == 0 else "…"
            s.append(row(base + i * 46, 212, 40, lab, AMB, "#ffffff", AMB_D))
        for i in range(3):
            x1 = base + i * 46 + 20
            s.append(f'<line x1="{cx}" y1="148" x2="{x1}" y2="210" stroke="{AMB}" stroke-width="1.2" marker-end="url(#ma)"/>')
    s.append(T(626, 190, "derived_from", 10, AMB_D, "middle"))
    s.append(T(626, 262, "recall hits both tiers, then walks derived_from", 10.5, AMB_D, "middle"))
    s.append(T(626, 304, "a real graph — never across owners", 10, MUT, "middle", style="italic"))

    # ---------- (c) Collaborative (red)
    s.append(T(20, 348, "(c) Collaborative — one store, ACL-partitioned", 12.5, "#991b1b", weight="bold"))
    s.append(qpanel(14, 358, 400, 282, "#fecaca", "#fffafa"))
    for cx, who in [(110, "A"), (250, "B")]:
        s.append(person(cx, 390, RED, RED_L)); s.append(T(cx + 20, 394, who, 11, INK, weight="bold"))
    s.append(f'<rect x="40" y="428" width="348" height="128" rx="10" fill="#ffffff" stroke="{RED}" stroke-width="1.5"/>')
    s.append(T(214, 446, "one physical collection, no merge", 10, MUT, "middle"))
    s.append(row(56, 456, 150, "e · acl {A}", RED, RED_L, "#991b1b"))
    s.append(row(222, 456, 150, "e · acl {A, B}", RED, RED_L, "#991b1b"))
    s.append(row(56, 488, 150, "… · acl {A}", RED, "#ffffff", "#991b1b"))
    s.append(row(222, 488, 150, "… · acl {B}", RED, "#ffffff", "#991b1b"))
    s.append(f'<line x1="120" y1="400" x2="128" y2="452" stroke="{RED}" stroke-width="1.2" marker-end="url(#mi)"/>')
    s.append(f'<line x1="256" y1="400" x2="290" y2="452" stroke="{RED}" stroke-width="1.2" marker-end="url(#mi)"/>')
    s.append(f'<line x1="208" y1="467" x2="220" y2="467" stroke="{RED}" stroke-width="1.2" stroke-dasharray="3 3"/>')
    s.append(T(214, 540, "grant", 9.5, "#991b1b", "middle"))
    s.append(f'<path d="M131,478 C150,522 278,522 297,478" fill="none" stroke="{RED}" stroke-width="1.1" stroke-dasharray="4 3" marker-end="url(#mi)"/>')
    s.append(T(214, 580, "B may be granted access to A's copy; the copy remains.", 10.5, "#991b1b", "middle"))
    s.append(T(214, 594, "Sharing is a permission, not a merge.", 10.5, "#991b1b", "middle"))
    s.append(T(214, 622, "access control over intact per-owner rows", 10, MUT, "middle", style="italic"))

    # ---------- (d) Consensus (blue)
    s.append(T(446, 348, "(d) Consensus — one record, several owners", 12.5, BLUE_D, weight="bold"))
    s.append(qpanel(426, 358, 400, 282, "#bfdbfe", "#f7faff"))
    for cx, who in [(520, "A"), (626, "B"), (732, "C")]:
        s.append(person(cx, 392, BLUE, BLUE_L)); s.append(T(cx + 18, 396, who, 11, INK, weight="bold"))
    s.append(f'<rect x="500" y="446" width="252" height="26" rx="7" fill="{BLUE_L}" stroke="{BLUE}" stroke-width="1.7"/>')
    s.append(T(626, 463, "e · owners {A, B, C}", 11, BLUE_D, "middle", weight="bold"))
    for cx in (520, 626, 732):
        s.append(f'<line x1="{cx}" y1="404" x2="{626 if cx==626 else cx + (18 if cx<626 else -18)}" y2="442" stroke="{BLUE}" stroke-width="1.3" marker-end="url(#mb)"/>')
    s.append(T(626, 492, "equivalent deposits merged; owner set is the union", 10, MUT, "middle"))
    s.append(T(626, 522, "affiliated", 10.5, PUR_D, "middle"))
    s.append(row(478, 532, 128, "sibling · {A, B}", PUR, PUR_L, PUR_D))
    s.append(row(650, 532, 118, "sibling · {C}", PUR, PUR_L, PUR_D))
    s.append(f'<line x1="560" y1="472" x2="545" y2="528" stroke="{PUR}" stroke-width="1.2"/>')
    s.append(f'<line x1="692" y1="472" x2="706" y2="528" stroke="{PUR}" stroke-width="1.2"/>')
    s.append(f'<line x1="608" y1="543" x2="648" y2="543" stroke="{PUR}" stroke-width="1.2" stroke-dasharray="4 3"/>')
    s.append(T(626, 580, "recall: rows you own, then one hop", 10.5, BLUE_D, "middle"))
    s.append(T(626, 594, "along the affiliation edges", 10.5, BLUE_D, "middle"))
    s.append(T(626, 622, "sharing computed at deposit time", 10, MUT, "middle", style="italic"))

    s.append(f'<line x1="14" y1="648" x2="826" y2="648" stroke="#e2e8f0"/>')
    s.append(T(420, 659, "the same event e in every panel · person = owner · solid box = stored row · dashed = mechanism-generated",
               10, MUT, "middle"))
    s.append('</svg>')
    return "\n".join(s)


if __name__ == "__main__":
    for name, fn in [("framework", framework), ("backends", backends)]:
        open(f"paper/figures/{name}.svg", "w", encoding="utf-8").write(fn())
        print(f"wrote paper/figures/{name}.svg")
