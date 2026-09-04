"""Figures 1 and 2 of the paper, drawn as self-contained SVG.

Styled after Fig. 5 of arXiv:2606.12191: a heavy rounded panel per stage in
its own hue, thick dashed sub-panels inside, flat icons under a uniform black
outline, coral arrows with a hatch texture, a rounded typeface, and labels of
two to four words. Explanatory prose belongs in the \\caption, not here.

The icons are drawn in this file rather than vendored. Emoji fonts were tried
first and are wrong twice over: the system face (Apple Color Emoji) is glossy
and shaded where this style needs flat fill under black outline, and the flat
sets that do have outlines still do not match. Drawing them keeps the artwork
consistent, keeps the PDF vector, and leaves nothing to attribute.

Run: venv/bin/python -m experiments.method_figs
"""
import math
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

BLACK, GREY = "#141414", "#5b6470"
CORAL, CORAL_D = "#e0564e", "#b8433c"
# the reference figure sets everything in a rounded face; these are the ones
# macOS ships, with a plain fallback so a rebuild elsewhere still renders
RF = ('font-family="Arial Rounded MT Bold,Arial Rounded MT,SF Pro Rounded,'
      'Helvetica Rounded,Nunito,Helvetica,Arial,sans-serif"')

HUES = {                      # (border, panel fill, sub fill)
    "orange": ("#e0a05a", "#fbead6", "#fffaf3"),
    "blue":   ("#3f7fc4", "#e4f0fb", "#f4faff"),
    "green":  ("#4faa6a", "#e8f6e6", "#f4fdf4"),
    "pink":   ("#d97f7f", "#fbe6e6", "#fff8f8"),
    "taupe":  ("#b09a86", "#f0e9e2", "#fbf8f5"),
    "purple": ("#8b7fd4", "#ece8fa", "#faf8ff"),
}

DEFS = ('<defs><pattern id="hx" width="9" height="9" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="9" '
        'stroke="#ffffff" stroke-width="3" opacity="0.30"/></pattern></defs>')


# ------------------------------------------------------------------ icons
# Each returns paths on a 72x72 grid: flat fills, one darker shade for volume,
# black outline. Stroke weights are absolute here and scaled with the glyph.

def _globe():
    g = "#8ecf78"
    return ('<circle cx="36" cy="36" r="26" fill="#2f86d6"/>'
            '<path d="M44 61 a26 26 0 0 0 17 -29 a31 31 0 0 1 -17 29 Z" fill="#1e6cb8"/>'
            f'<g fill="{g}" stroke="{BLACK}" stroke-width="1.9" stroke-linejoin="round">'
            '<path d="M20 14 Q27 17 26 24 Q23 28 19 29 Q22 31 22 34 Q25 38 24 44 '
            'Q22 52 18 54 Q14 48 15 40 Q11 31 14 21 Q16 13 20 14 Z"/>'
            '<path d="M33 13 Q37 16 40 14 Q47 13 52 17 Q58 19 57 25 Q51 27 46 26 '
            'Q48 29 45 30 Q49 32 54 33 Q59 36 53 40 Q47 40 45 44 Q43 52 39 59 '
            'Q34 55 34 46 Q30 42 32 36 Q28 28 31 21 Q31 14 33 13 Z"/></g>'
            f'<circle cx="36" cy="36" r="26" fill="none" stroke="{BLACK}" stroke-width="3.4"/>')


def _robot():
    return (f'<g stroke="{BLACK}" stroke-width="3" stroke-linejoin="round" '
            'stroke-linecap="round" fill="none">'
            '<path d="M36 11 v6"/><circle cx="36" cy="8.5" r="3.4" fill="#f0b429"/>'
            '<rect x="16" y="17" width="40" height="27" rx="8" fill="#cdd6de"/>'
            '<path d="M48 17 a8 8 0 0 1 8 8 v11 a8 8 0 0 1 -8 8 z" fill="#aab6c2" stroke="none"/>'
            '<rect x="16" y="17" width="40" height="27" rx="8"/>'
            '<circle cx="27" cy="30" r="5" fill="#f0b429"/>'
            '<circle cx="45" cy="30" r="5" fill="#f0b429"/>'
            f'<circle cx="27" cy="30" r="1.8" fill="{BLACK}" stroke="none"/>'
            f'<circle cx="45" cy="30" r="1.8" fill="{BLACK}" stroke="none"/>'
            '<rect x="6" y="49" width="9" height="12" rx="4" fill="#aab6c2"/>'
            '<rect x="57" y="49" width="9" height="12" rx="4" fill="#aab6c2"/>'
            '<rect x="17" y="47" width="38" height="17" rx="5" fill="#cdd6de"/>'
            '<rect x="24" y="52" width="24" height="8" rx="2" fill="#eef3f7"/>'
            '<circle cx="29" cy="56" r="1.5" fill="#f0b429" stroke="none"/>'
            '<circle cx="36" cy="56" r="1.5" fill="#e0564e" stroke="none"/>'
            '<circle cx="43" cy="56" r="1.5" fill="#5fc44a" stroke="none"/></g>')


def _book():
    return (f'<g stroke="{BLACK}" stroke-width="3" stroke-linejoin="round" '
            'stroke-linecap="round" fill="none">'
            '<path d="M36 21 q-9 -6 -23 -4 v33 q14 -2 23 4 Z" fill="#ffffff"/>'
            '<path d="M36 21 q9 -6 23 -4 v33 q-14 -2 -23 4 Z" fill="#e8eef4"/>'
            '<path d="M36 21 v33"/>'
            '<path d="M19 28 h11 M19 35 h11 M42 28 h11 M42 35 h11" stroke-width="2.3"/></g>')


def _glass():
    return (f'<g stroke="{BLACK}" stroke-width="3" stroke-linecap="round" fill="none">'
            '<circle cx="31" cy="30" r="16" fill="#cfe6fa"/>'
            '<path d="M25 24 a9 9 0 0 1 8 -4" stroke="#ffffff" stroke-width="2.6"/>'
            '<path d="M43 42 L57 56" stroke-width="6"/></g>')


def _store():
    return (f'<g stroke="{BLACK}" stroke-width="3" stroke-linejoin="round" fill="none">'
            '<path d="M13 19 v34 a23 8 0 0 0 46 0 v-34" fill="#7fb6e6"/>'
            '<ellipse cx="36" cy="19" rx="23" ry="8" fill="#bcd9f2"/>'
            '<path d="M13 31 a23 8 0 0 0 46 0 M13 42 a23 8 0 0 0 46 0" stroke-width="2.4"/></g>')


def _page():
    return (f'<g stroke="{BLACK}" stroke-width="3" stroke-linejoin="round" '
            'stroke-linecap="round" fill="none">'
            '<path d="M17 11 h27 l12 12 v38 h-39 Z" fill="#ffffff"/>'
            '<path d="M44 11 l12 12 h-12 z" fill="#d9e2ea"/>'
            '<path d="M44 11 v12 h12"/>'
            '<path d="M24 34 h24 M24 42 h24 M24 50 h15" stroke-width="2.3"/></g>')


def _lock():
    return (f'<g stroke="{BLACK}" stroke-width="3" stroke-linejoin="round" '
            'stroke-linecap="round" fill="none">'
            '<path d="M24 33 v-8 a12 12 0 0 1 24 0 v8" stroke-width="3.6"/>'
            '<rect x="15" y="33" width="42" height="28" rx="6" fill="#f0b429"/>'
            '<path d="M45 33 h6 a6 6 0 0 1 6 6 v16 a6 6 0 0 1 -6 6 h-6 z" '
            'fill="#d99a15" stroke="none"/>'
            '<rect x="15" y="33" width="42" height="28" rx="6"/>'
            f'<circle cx="36" cy="44" r="4.4" fill="{BLACK}"/>'
            '<path d="M36 47 v6" stroke-width="3.4"/></g>')


def _goals():
    """A stack of layers -- goals are pushed and popped, index 0 the bottom."""
    return (f'<g stroke="{BLACK}" stroke-width="3" stroke-linejoin="round" fill="none">'
            '<rect x="10" y="43" width="52" height="15" rx="5" fill="#c9b6f2"/>'
            '<rect x="10" y="27" width="52" height="15" rx="5" fill="#a98ae8"/>'
            '<rect x="10" y="11" width="52" height="15" rx="5" fill="#7c4dd6"/>'
            '<path d="M36 15 v7 M32.5 18.5 h7" stroke="#ffffff" stroke-width="2.6"/></g>')


def _status():
    """A gauge: the status register is the agent's readable state."""
    return (f'<g stroke="{BLACK}" stroke-width="3" stroke-linejoin="round" '
            'stroke-linecap="round" fill="none">'
            '<path d="M10 50 a26 26 0 0 1 52 0 z" fill="#eceff3"/>'
            '<path d="M17 50 a19 19 0 0 1 38 0" stroke="#b9c2cc" stroke-width="6"/>'
            '<path d="M36 50 L51 31" stroke-width="4.5"/>'
            f'<circle cx="36" cy="50" r="5" fill="{BLACK}"/>'
            '<path d="M8 50 h56" stroke-width="3.2"/></g>')


def _cache():
    """Two cards and an arrow: the cache holds (action, result) pairs."""
    return (f'<g stroke="{BLACK}" stroke-width="3" stroke-linejoin="round" fill="none">'
            '<rect x="7" y="20" width="24" height="32" rx="5" fill="#d3f0ee"/>'
            '<rect x="41" y="20" width="24" height="32" rx="5" fill="#8fd9d3"/>'
            '<path d="M32 36 h8" stroke="#12857e" stroke-width="4"/>'
            '<path d="M36 31 l6 5 l-6 5 z" fill="#12857e" stroke="none"/>'
            '<path d="M13 29 h12 M13 37 h12 M47 29 h12 M47 37 h12" '
            'stroke-width="2.4"/></g>')


def _city():
    return (f'<g stroke="{BLACK}" stroke-width="3" stroke-linejoin="round" fill="none">'
            '<rect x="9" y="33" width="20" height="29" fill="#8fb8d9"/>'
            '<rect x="27" y="15" width="20" height="47" fill="#c3dcf0"/>'
            '<rect x="45" y="26" width="18" height="36" fill="#8fb8d9"/>'
            '<g fill="#f0b429" stroke="none">'
            '<rect x="14" y="39" width="4.5" height="5"/><rect x="21" y="39" width="4.5" height="5"/>'
            '<rect x="14" y="48" width="4.5" height="5"/><rect x="21" y="48" width="4.5" height="5"/>'
            '<rect x="32" y="23" width="4.5" height="5"/><rect x="39" y="23" width="4.5" height="5"/>'
            '<rect x="32" y="33" width="4.5" height="5"/><rect x="39" y="33" width="4.5" height="5"/>'
            '<rect x="32" y="43" width="4.5" height="5"/><rect x="39" y="43" width="4.5" height="5"/>'
            '<rect x="50" y="33" width="4.5" height="5"/><rect x="56" y="33" width="4.5" height="5"/>'
            '<rect x="50" y="43" width="4.5" height="5"/><rect x="56" y="43" width="4.5" height="5"/>'
            '</g><path d="M5 62 h62" stroke-width="3.4"/></g>')


def _no():
    return ('<circle cx="36" cy="36" r="24" fill="#ffffff" stroke="#d33a3a" stroke-width="6.5"/>'
            '<path d="M19 19 L53 53" stroke="#d33a3a" stroke-width="6.5" stroke-linecap="round"/>')


GLYPH = {"globe": _globe, "robot": _robot, "book": _book, "glass": _glass,
         "store": _store, "page": _page, "lock": _lock, "no": _no, "city": _city,
         "goals": _goals, "status": _status, "cache": _cache}


def icon(x, y, name, size=56):
    k = size / 72.0
    return (f'<g transform="translate({x - size / 2:.1f},{y - size / 2:.1f}) '
            f'scale({k:.4f})">{GLYPH[name]()}</g>')


# ------------------------------------------------------------------ parts

def T(x, y, s, size=17, fill=BLACK, anchor="middle"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" {RF}>{s}</text>')


def panel(x, y, w, h, hue, title, size=30):
    b, fill, _ = HUES[hue]
    return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22" '
            f'fill="{fill}" stroke="{b}" stroke-width="5"/>',
            T(x + w / 2, y + 52, title, size)]


def sub(x, y, w, h, hue, title=None, size=21):
    b, _, fill = HUES[hue]
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" '
           f'fill="{fill}" stroke="{b}" stroke-width="3.4" '
           f'stroke-dasharray="12 9" stroke-linecap="round"/>']
    if title:
        out.append(T(x + w / 2, y + 34, title, size))
    return out


def fat(x1, y1, x2, y2, shaft=13, head=27, colour=CORAL, edge=CORAL_D):
    """Coral arrow with the hatch texture the reference figure uses."""
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
    return (f'<polygon points="{pts}" fill="{colour}" stroke="{edge}" stroke-width="1.6" '
            f'stroke-linejoin="round"/><polygon points="{pts}" fill="url(#hx)"/>')


def box(x, y, w, label, border, fill="#ffffff", h=32, dashed=False, size=16):
    d = ' stroke-dasharray="7 5"' if dashed else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" '
            f'stroke="{border}" stroke-width="3"{d}/>'
            + T(x + w / 2, y + h / 2 + 6, label, size))


def pill(x, y, w, label, border, fill, dashed=False, size=14):
    d = ' stroke-dasharray="7 5"' if dashed else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="32" rx="16" fill="{fill}" '
            f'stroke="{border}" stroke-width="2.8"{d}/>'
            + T(x + w / 2, y + 21, label, size))


# --------------------------------------------------------------- figure 1

def framework():
    W, H = 1300, 748
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" {RF} '
         f'style="max-width:100%;height:auto">', DEFS,
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']

    # ---- stage 1: offline
    s += panel(14, 12, 1272, 228, "orange",
               "Offline · Long-Term Memory Initialization")

    s += sub(38, 74, 372, 142, "orange", "Source Text")
    s.append(icon(224, 144, "book", 72))
    s.append(T(224, 204, "Novel · Play · Timeline", 17))

    s.append(fat(424, 151, 472, 151))

    s += sub(486, 74, 372, 142, "orange", "Extract &amp; Attribute")
    s.append(icon(672, 144, "glass", 68))
    s.append(T(672, 204, "Who Witnessed It?", 17))

    s.append(fat(872, 151, 920, 151))

    s += sub(934, 74, 328, 142, "blue", "Owner-Tagged Memory Items")
    for i2, lab in enumerate(["item 1 owned by {Agent A, Agent B}",
                              "item 2 owned by {Agent C}",
                              "item 3 owned by {Agent A, Agent C}"]):
        s.append(box(950, 116 + i2 * 33, 300, lab, "#3f7fc4", h=30, size=15))

    s.append(fat(1150, 248, 1150, 292, shaft=16, head=30))

    # ---- stage 2: runtime -- the actions are drawn where they happen, in
    # the society, so the separate repertoire strip is gone
    s += panel(14, 300, 1272, 424, "blue", "Runtime · Simulation")

    # society -> short-term -> long-term, left to right, so the offline
    # column above feeds straight down into the store it seeds
    s += sub(38, 372, 522, 322, "green", "The Society")

    for cx, who in ((145, "A"), (300, "B"), (455, "C")):
        s.append(icon(cx, 458, "robot", 84))
        s.append(T(cx, 520, f"Agent {who}", 18))
    s.append(fat(190, 438, 258, 438, shaft=9, head=20))
    s.append(T(224, 420, "say", 17, CORAL))
    s.append(fat(258, 472, 190, 472, shaft=9, head=20))
    s.append(T(224, 500, "read_thread", 15, CORAL))

    s.append(fat(141, 528, 117, 574, shaft=8, head=18))
    s.append(T(160, 556, "observe", 16, CORAL, "start"))
    s.append(fat(294, 528, 250, 574, shaft=8, head=18))
    s.append(T(304, 556, "move", 16, CORAL, "start"))
    s.append(fat(440, 530, 400, 574, shaft=8, head=18))
    s.append(T(378, 556, "act_on", 16, CORAL))
    s.append(fat(474, 530, 500, 574, shaft=8, head=18))
    s.append(T(518, 556, "read", 16, CORAL, "start"))

    for cx, n in ((110, 1), (240, 2), (370, 3)):
        s.append(icon(cx, 612, "city", 74))
        s.append(T(cx, 670, f"Location {n}", 17))
    s.append(icon(500, 606, "page", 62))
    s.append(T(500, 654, "Letters", 16))
    s.append(T(500, 672, "&amp; Edicts", 16))

    s.append(fat(652, 476, 574, 476, shaft=10, head=22))
    s.append(T(613, 456, "context", 16, CORAL))
    s.append(fat(574, 564, 652, 564, shaft=10, head=22))
    s.append(T(613, 544, "result", 16, CORAL))

    # ---- short-term memory: what build_view() hands the brain each round
    s += sub(666, 372, 266, 322, "purple", "Short-Term Memory")

    for cy, name, lab in [(444, "goals", "Goal Stack"),
                          (536, "status", "Status"),
                          (628, "cache", "Action–Result Cache")]:
        s.append(icon(799, cy, name, 72))
        s.append(T(799, cy + 50, lab, 18))

    s.append(fat(1024, 476, 946, 476))
    s.append(T(985, 456, "recall", 17, CORAL))
    s.append(fat(946, 564, 1024, 564))
    s.append(T(985, 544, "remember", 17, CORAL))
    s.append(T(985, 598, "owner-", 14, GREY))
    s.append(T(985, 616, "scoped", 14, GREY))

    s += sub(1038, 372, 224, 322, "blue", "Long-Term Memory")
    s.append(icon(1150, 502, "store", 110))
    s.append(T(1150, 612, "structure differs", 15, GREY))
    s.append(T(1150, 632, "per backend", 15, GREY))

    s.append('</svg>')
    return "\n".join(s)


# --------------------------------------------------------------- figure 2

def backends():
    """Four panels, one per backend. No inner frame and no summary lines: the
    structure is the argument, and the caption carries the rest."""
    W, H = 1120, 728
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" {RF} '
         f'style="max-width:100%;height:auto">', DEFS,
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']

    GRN, GRN_L, GRN_D = "#0f8a5f", "#d6f5e6", "#0a6b49"
    AMB, AMB_L = "#c97e14", "#fceccb"
    RED, RED_L = "#cf4444", "#fbdede"
    BLU, BLU_L = "#2f6fd0", "#dceafa"
    PUR, PUR_L = "#7c4dd6", "#e9e0fb"

    # ---- (a) Generative Agents: the reflection tree drawn out. Reflections
    # are stored back into the stream and linked to their evidence, so a later
    # reflection can take an earlier one as evidence -- hence the second level.
    s += panel(14, 12, 542, 340, "green", "(a) Generative Agents")
    s.append(T(285, 106, "One Private Stream per Agent", 21))
    for cx, who in [(154, "A"), (416, "B")]:
        s.append(icon(cx - 24, 148, "robot", 52))
        s.append(T(cx + 28, 154, who, 20))
        s.append(box(cx - 62, 182, 124, "reflection²", GRN, GRN_L, h=28,
                     dashed=True, size=13))
        s.append(fat(cx, 232, cx, 212, shaft=4.5, head=11, colour=GRN, edge=GRN_D))
        s.append(box(cx - 62, 234, 124, "reflection", GRN, GRN_L, h=28,
                     dashed=True, size=13))
        s.append(fat(cx - 52, 290, cx - 18, 266, shaft=4.5, head=11,
                     colour=GRN, edge=GRN_D))
        s.append(fat(cx + 52, 290, cx + 18, 266, shaft=4.5, head=11,
                     colour=GRN, edge=GRN_D))
        s.append(box(cx - 106, 296, 100, "memory item", GRN, "#ffffff", h=28, size=13))
        s.append(box(cx + 6, 296, 100, "&#8230;", GRN, "#ffffff", h=28, size=13))
    s.append(T(285, 250, "evidence", 14, GREY))

    # ---- (b) G-Memory
    s += panel(564, 12, 542, 340, "orange", "(b) G-Memory")
    s.append(T(835, 106, "Two-Tier Graph, per Owner", 21))
    for cx, who in [(704, "A"), (966, "B")]:
        s.append(icon(cx - 22, 164, "robot", 52))
        s.append(T(cx + 26, 170, who, 20))
        s.append(f'<ellipse cx="{cx}" cy="228" rx="66" ry="23" fill="{AMB_L}" '
                 f'stroke="{AMB}" stroke-width="3" stroke-dasharray="7 5"/>')
        s.append(T(cx, 235, "insight", 17))
        for i2, lab in enumerate(("memory item", "&#8230;")):
            bx = cx - 108 + i2 * 112
            s.append(box(bx, 290, 104, lab, AMB, "#ffffff", h=30, size=14))
            s.append(fat(bx + 52, 286, cx, 255, shaft=5, head=12, colour=AMB,
                         edge="#9c5f0d"))
    s.append(T(835, 274, "distilled into", 14, GREY))

    # ---- (c) Collaborative
    s += panel(14, 372, 542, 340, "pink", "(c) Collaborative")
    s.append(T(285, 466, "One Store, Split by Permission", 21))
    for cx, who in [(154, "A"), (416, "B")]:
        s.append(icon(cx - 22, 516, "robot", 54))
        s.append(T(cx + 28, 522, who, 20))
    s.append(box(74, 550, 164, "memory item &#183; {A}", RED, RED_L, h=30, size=13.5))
    s.append(box(336, 550, 164, "memory item &#183; {A, B}", RED, RED_L, h=30, size=13.5))
    s.append(box(74, 590, 164, "&#8230; &#183; {A}", RED, "#ffffff", h=30, size=13.5))
    s.append(box(336, 590, 164, "&#8230; &#183; {B}", RED, "#ffffff", h=30, size=13.5))
    s.append(icon(285, 572, "lock", 46))
    s.append(fat(238, 648, 336, 648, shaft=9, head=20, colour=RED, edge="#a33"))
    s.append(T(285, 678, "grant", 16))

    # ---- (d) Consensus
    s += panel(564, 372, 542, 340, "blue", "(d) Consensus  (ours)")
    s.append(T(835, 466, "One Record, Several Owners", 21))
    for cx, who, tx in [(712, "A", 742), (835, "B", 835), (958, "C", 928)]:
        s.append(icon(cx - 20, 516, "robot", 52))
        s.append(T(cx + 26, 522, who, 20))
        s.append(fat(cx, 546, tx, 578, shaft=9, head=20))
    s.append(box(628, 584, 416, "memory item &#183; owners {A, B, C}", BLU, BLU_L,
                 h=38, size=18))
    s.append(box(608, 640, 176, "memory item &#183; {A, B}", PUR, PUR_L, h=30, size=13))
    s.append(box(890, 640, 162, "memory item &#183; {C}", PUR, PUR_L, h=30, size=13))
    s.append(fat(664, 624, 682, 636, shaft=5, head=12, colour=PUR, edge="#5b2fa8"))
    s.append(fat(1008, 624, 990, 636, shaft=5, head=12, colour=PUR, edge="#5b2fa8"))
    s.append(T(835, 662, "affiliated", 14, PUR))

    s.append('</svg>')
    return "\n".join(s)


if __name__ == "__main__":
    for name, fn in [("framework", framework), ("backends", backends)]:
        open(f"paper/figures/{name}.svg", "w", encoding="utf-8").write(fn())
        print(f"wrote paper/figures/{name}.svg")
