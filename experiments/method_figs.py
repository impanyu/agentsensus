"""Figures 1 and 2 of the paper, drawn as self-contained SVG.

Drawn in the poster idiom the survey figures use: one heavy rounded panel per
stage, a big black title on it, dashed sub-panels inside, large flat icons
carrying the entities, blocky coral arrows for the flow, and labels of two to
four words. Explanatory prose belongs in the \\caption, not on the canvas.

The icons are OpenMoji (openmoji.org, CC BY-SA 4.0), vendored under
paper/figures/icons and inlined as vector groups. They are NOT the system
emoji font: Apple Color Emoji is glossy and shaded, where this figure needs
the flat fill and uniform black outline the reference style is built on. Same
codepoints, different artwork -- that difference is the whole look.

Run: venv/bin/python -m experiments.method_figs
"""
import math
import os
import re
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

BLACK, GREY = "#161616", "#5b6470"
CORAL = "#e0564e"
F = 'font-family="Helvetica,Arial,sans-serif"'
ICONS = "paper/figures/icons"
_cache = {}

# panel hue: (border, panel fill, sub fill)
HUES = {
    "orange": ("#e0a05a", "#fbead6", "#fffaf3"),
    "blue":   ("#5b93cf", "#dfeef9", "#f5fbff"),
    "green":  ("#6fb87f", "#e6f5e4", "#f6fdf5"),
    "pink":   ("#df8c8c", "#fbe6e6", "#fff8f8"),
    "taupe":  ("#b09a86", "#f0e9e2", "#fbf8f5"),
}


def icon(x, y, name, size=52):
    """One OpenMoji glyph, centred on (x, y), inlined as vector.

    The files share viewBox 0 0 72 72 and carry no internal url(#) references,
    so their ids can be dropped -- which they must be, or a second copy of the
    same glyph would collide with the first."""
    if name not in _cache:
        t = open(f"{ICONS}/{name}.svg", encoding="utf-8").read()
        t = re.sub(r"<svg[^>]*>", "", t, count=1).replace("</svg>", "")
        t = re.sub(r'\s+id="[^"]*"', "", t)
        _cache[name] = t.strip()
    k = size / 72.0
    return (f'<g transform="translate({x - size / 2:.1f},{y - size / 2:.1f}) '
            f'scale({k:.4f})">{_cache[name]}</g>')


def T(x, y, s, size=15, fill=BLACK, anchor="middle", weight="bold"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}" {F}>{s}</text>')


def panel(x, y, w, h, hue, title, size=26):
    b, fill, _ = HUES[hue]
    return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="20" '
            f'fill="{fill}" stroke="{b}" stroke-width="4"/>',
            T(x + w / 2, y + 46, title, size)]


def sub(x, y, w, h, hue, title=None, size=18):
    b, _, fill = HUES[hue]
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="15" '
           f'fill="{fill}" stroke="{b}" stroke-width="2.6" '
           f'stroke-dasharray="9 6"/>']
    if title:
        out.append(T(x + w / 2, y + 30, title, size))
    return out


def fat(x1, y1, x2, y2, shaft=11, head=24, colour=CORAL):
    """A blocky filled arrow -- the reference draws arrow shapes, not strokes
    with a marker glued on the end."""
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1
    ux, uy = dx / L, dy / L
    px, py = -uy, ux
    s, hw = shaft / 2, head / 2
    bx, by = x2 - ux * head, y2 - uy * head
    pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in [
        (x1 + px * s, y1 + py * s), (bx + px * s, by + py * s),
        (bx + px * hw, by + py * hw), (x2, y2),
        (bx - px * hw, by - py * hw), (bx - px * s, by - py * s),
        (x1 - px * s, y1 - py * s)])
    return f'<polygon points="{pts}" fill="{colour}"/>'


def box(x, y, w, label, border, fill="#ffffff", h=28, dashed=False, size=14):
    d = ' stroke-dasharray="6 4"' if dashed else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{fill}" '
            f'stroke="{border}" stroke-width="2.6"{d}/>'
            + T(x + w / 2, y + h / 2 + 5, label, size))


def pill(x, y, w, label, border, fill, dashed=False, size=13):
    d = ' stroke-dasharray="6 4"' if dashed else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="30" rx="15" fill="{fill}" '
            f'stroke="{border}" stroke-width="2.4"{d}/>'
            + T(x + w / 2, y + 20, label, size))


# --------------------------------------------------------------- figure 1

def framework():
    W, H = 1060, 752
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" {F} '
         f'style="max-width:100%;height:auto">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']

    # ---------------- stage 1: offline ----------------
    s += panel(14, 12, 1032, 214, "orange", "Offline · Sedimentation")

    s += sub(36, 74, 296, 138, "orange", "Source Text")
    s.append(icon(184, 140, "book", 54))
    s.append(T(184, 192, "Novel · Play · Timeline", 14))

    s.append(fat(344, 143, 388, 143))

    s += sub(400, 74, 296, 138, "orange", "Extract &amp; Attribute")
    s.append(icon(548, 140, "glass", 50))
    s.append(T(548, 192, "Who Witnessed It?", 14))

    s.append(fat(708, 143, 752, 143))

    s += sub(764, 74, 282, 138, "blue", "Owner-Tagged Events")
    for i, lab in enumerate(["e &#183; {A, B}", "&#8230; &#183; {C}",
                             "&#8230; &#183; {A, D}"]):
        s.append(box(818, 112 + i * 34, 174, lab, "#2f6fd0", "#ffffff"))

    # ---------------- between the stages ----------------
    s.append(fat(530, 232, 530, 264, shaft=14, head=26))
    s.append(T(556, 257, "seeds the store", 16, CORAL, "start"))

    # ---------------- stage 2: runtime ----------------
    s += panel(14, 276, 1032, 296, "blue", "Runtime · One Shared Store")

    s += sub(36, 338, 296, 216, "blue", "Shared Memory")
    s.append(icon(184, 400, "brain", 50))
    s.append(f'<path d="M112,436 v56 a72,16 0 0 0 144,0 v-56" fill="#cfe4f7" '
             f'stroke="#2f6fd0" stroke-width="3"/>')
    s.append(f'<ellipse cx="184" cy="436" rx="72" ry="16" fill="#eaf4fd" '
             f'stroke="#2f6fd0" stroke-width="3"/>')
    s.append(T(184, 472, "One Store,", 15))
    s.append(T(184, 492, "All Agents", 15))
    s.append(T(184, 534, "Structure differs per backend", 12.5, GREY))

    s.append(fat(340, 394, 396, 394))
    s.append(T(368, 380, "recall", 15, CORAL))
    s.append(fat(396, 472, 340, 472))
    s.append(T(368, 458, "remember", 15, CORAL))
    s.append(T(368, 512, "Owner-Scoped", 11))

    s += sub(410, 338, 636, 216, "green", "The Society")

    s.append(icon(506, 400, "robot", 50))
    s.append(T(506, 448, "Agent", 15))
    s.append(icon(726, 400, "robot", 50))
    s.append(T(726, 448, "Agent", 15))
    s.append(icon(948, 398, "globe", 50))
    s.append(T(948, 448, "World", 15))
    s.append(icon(608, 504, "page", 40))
    s.append(T(676, 510, "Letters &amp; Edicts", 14, BLACK, "start"))

    s.append(fat(546, 388, 686, 388, shaft=9, head=20))
    s.append(T(616, 374, "say", 15, CORAL))
    s.append(T(948, 470, "Places · Objects", 12.5, GREY))

    # ---------------- stage 3: the repertoire ----------------
    s += panel(14, 588, 1032, 150, "taupe",
               "One Action per Agent per Round", 22)

    GRN, GRN_L = "#0f8a5f", "#d6f5e6"
    BLU, BLU_L = "#2f6fd0", "#dceafa"
    PUR, PUR_L = "#7c4dd6", "#e9e0fb"
    SL, SL_L = "#8a94a3", "#eef1f5"
    RED, RED_L = "#d63b3b", "#fbdede"

    world = ("say", "read_thread", "observe", "move", "act_on", "read")
    x = 40
    for lab, w in [("say", 54), ("read_thread", 104), ("observe", 82),
                   ("move", 62), ("act_on", 72), ("read", 58),
                   ("think", 62), ("conclude", 86), ("wait", 56)]:
        s.append(pill(x, 652, w, lab, *((GRN, GRN_L) if lab in world else (SL, SL_L))))
        x += w + 8
    for lab, w in [("remember", 94), ("recall", 68)]:
        s.append(pill(x, 652, w, lab, BLU, BLU_L)); x += w + 8

    x = 40
    for lab, w in [("push_goal", 92), ("pop_goal", 84), ("replace_goal", 112),
                   ("update_status", 122)]:
        s.append(pill(x, 690, w, lab, PUR, PUR_L)); x += w + 8
    s.append(pill(x + 24, 690, 322, "6 memory-management actions · never used",
                  RED, RED_L, dashed=True))

    s.append('</svg>')
    return "\n".join(s)


# --------------------------------------------------------------- figure 2

def backends():
    W, H = 1060, 786
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" {F} '
         f'style="max-width:100%;height:auto">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']

    GRN, GRN_L = "#0f8a5f", "#d6f5e6"
    AMB, AMB_L = "#c97e14", "#fceccb"
    RED, RED_L = "#cf4444", "#fbdede"
    BLU, BLU_L = "#2f6fd0", "#dceafa"
    PUR, PUR_L = "#7c4dd6", "#e9e0fb"

    # ---------------- (a) Generative Agents ----------------
    s += panel(14, 12, 512, 376, "green", "(a) Generative Agents")
    s += sub(36, 76, 468, 220, "green", "One Private Stream per Agent")
    for cx, who in [(146, "A"), (394, "B")]:
        s.append(icon(cx - 16, 134, "robot", 44))
        s.append(T(cx + 22, 142, who, 18))
        s.append(box(cx - 66, 166, 132, "e", GRN, "#ffffff", h=26))
        s.append(box(cx - 66, 200, 132, "&#8230;", GRN, "#ffffff", h=26))
        s.append(box(cx - 66, 240, 132, "reflection", GRN, GRN_L, h=26,
                     dashed=True, size=13))
    s.append(icon(270, 206, "no", 36))
    s.append(T(270, 248, "no link", 13.5))
    s.append(T(270, 336, "One Copy per Witness", 19))
    s.append(T(270, 362, "recency × importance × relevance", 14, GREY))

    # ---------------- (b) G-Memory ----------------
    s += panel(534, 12, 512, 376, "orange", "(b) G-Memory")
    s += sub(556, 76, 468, 220, "orange", "Two-Tier Graph, per Owner")
    for cx, who in [(666, "A"), (914, "B")]:
        s.append(icon(cx - 16, 132, "robot", 42))
        s.append(T(cx + 22, 140, who, 18))
        s.append(f'<ellipse cx="{cx}" cy="192" rx="62" ry="21" fill="{AMB_L}" '
                 f'stroke="{AMB}" stroke-width="2.6" stroke-dasharray="6 4"/>')
        s.append(T(cx, 198, "insight", 15))
        for i in range(3):
            bx = cx - 72 + i * 50
            s.append(box(bx, 248, 44, "e" if i == 0 else "&#8230;", AMB,
                         "#ffffff", h=26, size=13))
            s.append(fat(cx, 214, bx + 22, 244, shaft=4.5, head=11, colour=AMB))
    s.append(T(790, 200, "derived_from", 13, GREY))
    s.append(T(790, 336, "A Graph — Never Across Owners", 18))
    s.append(T(790, 362, "insights distilled every 20 rounds", 14, GREY))

    # ---------------- (c) Collaborative ----------------
    s += panel(14, 400, 512, 376, "pink", "(c) Collaborative")
    s += sub(36, 464, 468, 220, "pink", "One Store, Split by Permission")
    for cx, who in [(146, "A"), (394, "B")]:
        s.append(icon(cx - 16, 522, "robot", 44))
        s.append(T(cx + 22, 530, who, 18))
    s.append(box(80, 554, 132, "e &#183; {A}", RED, RED_L))
    s.append(box(328, 554, 132, "e &#183; {A, B}", RED, RED_L))
    s.append(box(80, 592, 132, "&#8230; &#183; {A}", RED, "#ffffff"))
    s.append(box(328, 592, 132, "&#8230; &#183; {B}", RED, "#ffffff"))
    s.append(icon(270, 574, "lock", 38))
    s.append(fat(214, 644, 326, 644, shaft=7, head=17, colour=RED))
    s.append(T(270, 672, "grant", 14))
    s.append(T(270, 724, "A Permission, Not a Merge", 19))
    s.append(T(270, 750, "two rows survive, one event", 14, GREY))

    # ---------------- (d) Consensus ----------------
    s += panel(534, 400, 512, 376, "blue", "(d) Consensus  (ours)")
    s += sub(556, 464, 468, 220, "blue", "One Record, Several Owners")
    for cx, who, tx in [(672, "A", 700), (790, "B", 790), (908, "C", 880)]:
        s.append(icon(cx - 14, 520, "robot", 42))
        s.append(T(cx + 24, 528, who, 18))
        s.append(fat(cx, 546, tx, 578, shaft=8, head=18))
    s.append(box(610, 584, 360, "e &#183; owners {A, B, C}", BLU, BLU_L, h=34,
                 size=16))
    s.append(box(586, 634, 142, "sibling &#183; {A, B}", PUR, PUR_L, size=13))
    s.append(box(852, 634, 130, "sibling &#183; {C}", PUR, PUR_L, size=13))
    s.append(fat(626, 620, 648, 632, shaft=6, head=14, colour=PUR))
    s.append(fat(954, 620, 932, 632, shaft=6, head=14, colour=PUR))
    s.append(T(790, 654, "affiliated", 13.5))
    s.append(T(790, 724, "Computed at Deposit Time", 19))
    s.append(T(790, 750, "owner set is the union", 14, GREY))

    s.append('</svg>')
    return "\n".join(s)


if __name__ == "__main__":
    for name, fn in [("framework", framework), ("backends", backends)]:
        open(f"paper/figures/{name}.svg", "w", encoding="utf-8").write(fn())
        print(f"wrote paper/figures/{name}.svg")
