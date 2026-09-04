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


def _no():
    return ('<circle cx="36" cy="36" r="24" fill="#ffffff" stroke="#d33a3a" stroke-width="6.5"/>'
            '<path d="M19 19 L53 53" stroke="#d33a3a" stroke-width="6.5" stroke-linecap="round"/>')


GLYPH = {"globe": _globe, "robot": _robot, "book": _book, "glass": _glass,
         "store": _store, "page": _page, "lock": _lock, "no": _no}


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
    W, H = 1120, 780
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" {RF} '
         f'style="max-width:100%;height:auto">', DEFS,
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']

    # ---- stage 1: offline
    s += panel(14, 12, 1092, 228, "orange", "Offline · Sedimentation")

    s += sub(38, 80, 300, 142, "orange", "Source Text")
    s.append(icon(188, 146, "book", 58))
    s.append(T(188, 204, "Novel · Play · Timeline", 16))

    s.append(fat(350, 151, 402, 151))

    s += sub(414, 80, 300, 142, "orange", "Extract &amp; Attribute")
    s.append(icon(564, 146, "glass", 56))
    s.append(T(564, 204, "Who Witnessed It?", 16))

    s.append(fat(726, 151, 778, 151))

    s += sub(790, 80, 292, 142, "blue", "Owner-Tagged Events")
    for i, lab in enumerate(["e &#183; {A, B}", "&#8230; &#183; {C}",
                             "&#8230; &#183; {A, D}"]):
        s.append(box(848, 118 + i * 36, 176, lab, "#3f7fc4"))

    s.append(fat(560, 248, 560, 286, shaft=16, head=30))
    s.append(T(596, 276, "seeds the store", 19, CORAL, "start"))

    # ---- stage 2: runtime
    s += panel(14, 300, 1092, 314, "blue", "Runtime · One Shared Store")

    s += sub(38, 368, 292, 224, "blue", "Shared Memory")
    s.append(icon(184, 448, "store", 82))
    s.append(T(184, 524, "One Store, All Agents", 17))
    s.append(T(184, 562, "structure differs per backend", 14, GREY))

    s.append(fat(340, 428, 424, 428))
    s.append(T(381, 410, "recall", 16, CORAL))
    s.append(fat(424, 508, 340, 508))
    s.append(T(381, 490, "remember", 16, CORAL))
    s.append(T(381, 544, "owner-", 13, GREY))
    s.append(T(381, 560, "scoped", 13, GREY))

    s += sub(432, 368, 650, 224, "green", "The Society")

    s.append(icon(520, 452, "robot", 74))
    s.append(T(520, 508, "Agent", 17))
    s.append(icon(722, 452, "robot", 74))
    s.append(T(722, 508, "Agent", 17))
    s.append(icon(916, 448, "globe", 74))
    s.append(T(916, 508, "World", 17))
    s.append(icon(620, 546, "page", 46))
    s.append(T(700, 552, "Letters &amp; Edicts", 16, BLACK, "start"))

    s.append(fat(568, 438, 674, 438, shaft=11, head=24))
    s.append(T(621, 418, "say", 18, CORAL))

    # ---- stage 3: the repertoire
    s += panel(14, 626, 1092, 142, "taupe", "One Action per Agent per Round", 24)

    GRN, GRN_L = "#0f8a5f", "#d6f5e6"
    BLU, BLU_L = "#2f6fd0", "#dceafa"
    PUR, PUR_L = "#7c4dd6", "#e9e0fb"
    SL, SL_L = "#8a94a3", "#eef1f5"
    RED, RED_L = "#d63b3b", "#fbdede"
    world = ("say", "read_thread", "observe", "move", "act_on", "read")

    x = 44
    for lab, w in [("say", 56), ("read_thread", 112), ("observe", 88),
                   ("move", 66), ("act_on", 78), ("read", 62),
                   ("think", 66), ("conclude", 92), ("wait", 60)]:
        s.append(pill(x, 686, w, lab, *((GRN, GRN_L) if lab in world else (SL, SL_L))))
        x += w + 9
    for lab, w in [("remember", 100), ("recall", 74)]:
        s.append(pill(x, 686, w, lab, BLU, BLU_L)); x += w + 9

    x = 44
    for lab, w in [("push_goal", 98), ("pop_goal", 90), ("replace_goal", 120),
                   ("update_status", 132)]:
        s.append(pill(x, 728, w, lab, PUR, PUR_L)); x += w + 9
    s.append(pill(x + 26, 728, 344, "6 memory-management actions · never used",
                  RED, RED_L, dashed=True))

    s.append('</svg>')
    return "\n".join(s)


# --------------------------------------------------------------- figure 2

def backends():
    W, H = 1120, 830
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" {RF} '
         f'style="max-width:100%;height:auto">', DEFS,
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']

    GRN, GRN_L = "#0f8a5f", "#d6f5e6"
    AMB, AMB_L = "#c97e14", "#fceccb"
    RED, RED_L = "#cf4444", "#fbdede"
    BLU, BLU_L = "#2f6fd0", "#dceafa"
    PUR, PUR_L = "#7c4dd6", "#e9e0fb"

    # ---- (a) Generative Agents
    s += panel(14, 12, 542, 396, "green", "(a) Generative Agents")
    s += sub(38, 84, 494, 234, "green", "One Private Stream per Agent")
    for cx, who in [(154, "A"), (416, "B")]:
        s.append(icon(cx - 22, 152, "robot", 52))
        s.append(T(cx + 26, 158, who, 20))
        s.append(box(cx - 72, 182, 144, "e", GRN, "#ffffff", h=28))
        s.append(box(cx - 72, 218, 144, "&#8230;", GRN, "#ffffff", h=28))
        s.append(box(cx - 72, 262, 144, "reflection", GRN, GRN_L, h=28, dashed=True, size=14))
    s.append(icon(285, 224, "no", 40))
    s.append(T(285, 268, "no link", 15))
    s.append(T(285, 356, "One Copy per Witness", 21))
    s.append(T(285, 384, "recency × importance × relevance", 15, GREY))

    # ---- (b) G-Memory
    s += panel(564, 12, 542, 396, "orange", "(b) G-Memory")
    s += sub(588, 84, 494, 234, "orange", "Two-Tier Graph, per Owner")
    for cx, who in [(704, "A"), (966, "B")]:
        s.append(icon(cx - 22, 150, "robot", 50))
        s.append(T(cx + 24, 156, who, 20))
        s.append(f'<ellipse cx="{cx}" cy="208" rx="66" ry="23" fill="{AMB_L}" '
                 f'stroke="{AMB}" stroke-width="3" stroke-dasharray="7 5"/>')
        s.append(T(cx, 215, "insight", 17))
        for i in range(3):
            bx = cx - 76 + i * 53
            s.append(box(bx, 268, 46, "e" if i == 0 else "&#8230;", AMB, "#ffffff",
                         h=28, size=14))
            s.append(fat(cx, 233, bx + 23, 263, shaft=5, head=12, colour=AMB, edge="#9c5f0d"))
    s.append(T(835, 216, "derived_from", 15, GREY))
    s.append(T(835, 356, "A Graph — Never Across Owners", 20))
    s.append(T(835, 384, "insights distilled every 20 rounds", 15, GREY))

    # ---- (c) Collaborative
    s += panel(14, 426, 542, 392, "pink", "(c) Collaborative")
    s += sub(38, 498, 494, 234, "pink", "One Store, Split by Permission")
    for cx, who in [(154, "A"), (416, "B")]:
        s.append(icon(cx - 22, 566, "robot", 52))
        s.append(T(cx + 26, 572, who, 20))
    s.append(box(84, 596, 144, "e &#183; {A}", RED, RED_L))
    s.append(box(346, 596, 144, "e &#183; {A, B}", RED, RED_L))
    s.append(box(84, 638, 144, "&#8230; &#183; {A}", RED, "#ffffff"))
    s.append(box(346, 638, 144, "&#8230; &#183; {B}", RED, "#ffffff"))
    s.append(icon(285, 618, "lock", 46))
    s.append(fat(232, 690, 342, 690, shaft=9, head=20, colour=RED, edge="#a33"))
    s.append(T(285, 718, "grant", 16))
    s.append(T(285, 774, "A Permission, Not a Merge", 21))
    s.append(T(285, 802, "two rows survive, one event", 15, GREY))

    # ---- (d) Consensus
    s += panel(564, 426, 542, 392, "blue", "(d) Consensus  (ours)")
    s += sub(588, 498, 494, 234, "blue", "One Record, Several Owners")
    for cx, who, tx in [(712, "A", 742), (835, "B", 835), (958, "C", 928)]:
        s.append(icon(cx - 20, 564, "robot", 50))
        s.append(T(cx + 26, 570, who, 20))
        s.append(fat(cx, 592, tx, 624, shaft=9, head=20))
    s.append(box(648, 630, 376, "e &#183; owners {A, B, C}", BLU, BLU_L, h=38, size=19))
    s.append(box(618, 686, 156, "sibling &#183; {A, B}", PUR, PUR_L, h=30, size=14))
    s.append(box(900, 686, 142, "sibling &#183; {C}", PUR, PUR_L, h=30, size=14))
    s.append(fat(664, 670, 682, 682, shaft=5, head=12, colour=PUR, edge="#5b2fa8"))
    s.append(fat(1008, 670, 990, 682, shaft=5, head=12, colour=PUR, edge="#5b2fa8"))
    s.append(T(835, 718, "affiliated", 15))
    s.append(T(835, 774, "Computed at Deposit Time", 21))
    s.append(T(835, 802, "owner set is the union", 15, GREY))

    s.append('</svg>')
    return "\n".join(s)


if __name__ == "__main__":
    for name, fn in [("framework", framework), ("backends", backends)]:
        open(f"paper/figures/{name}.svg", "w", encoding="utf-8").write(fn())
        print(f"wrote paper/figures/{name}.svg")
