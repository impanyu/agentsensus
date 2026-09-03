"""Figures 1 and 2 of the paper, drawn as self-contained SVG.

Styled after the panel-and-icon convention common in recent survey figures:
a thick rounded panel per stage in its own hue, dashed sub-panels for the
parts inside it, emoji for the entities and heavy coral arrows for the flow
between them. Everything is inline -- no page CSS, no external assets -- so
the standalone PDF looks exactly like the figure on the page. Emoji are
rasterised into the PDF as colour bitmaps by the Chrome print step.

Run: venv/bin/python -m experiments.method_figs
"""
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

INK, MUT = "#111827", "#6b7280"
ARROW = "#e05a5a"
F = 'font-family="Helvetica,Arial,sans-serif"'
EF = ('font-family="Apple Color Emoji,Segoe UI Emoji,Noto Color Emoji,'
      'sans-serif"')

# panel hue: (border, fill, sub-fill, title ink)
HUES = {
    "amber": ("#e8a33d", "#fdf3e3", "#fffaf0", "#8a5a12"),
    "blue":  ("#5b8fd4", "#e8f1fc", "#f5f9ff", "#1e3a8a"),
    "green": ("#5aab7a", "#e9f7ee", "#f4fcf7", "#0f6b3f"),
    "red":   ("#d97a7a", "#fdeaea", "#fff6f6", "#9b1c1c"),
    "purple": ("#9b8ad4", "#efeafb", "#f8f5ff", "#4c1d95"),
    "slate": ("#9aa4b2", "#eef1f5", "#f8fafc", "#334155"),
}

DEFS = f'''<defs>
<marker id="ar" viewBox="0 0 12 12" refX="9" refY="6" markerWidth="5.2"
        markerHeight="5.2" orient="auto-start-reverse">
  <path d="M0,0.5 L11,6 L0,11.5 Z" fill="{ARROW}"/>
</marker>
<marker id="ard" viewBox="0 0 12 12" refX="9" refY="6" markerWidth="4.4"
        markerHeight="4.4" orient="auto-start-reverse">
  <path d="M0,0.5 L11,6 L0,11.5 Z" fill="#7c3aed"/>
</marker>
<marker id="ai" viewBox="0 0 12 12" refX="9" refY="6" markerWidth="4.2"
        markerHeight="4.2" orient="auto-start-reverse">
  <path d="M0,1 L10,6 L0,11 Z" fill="#475569"/>
</marker>
</defs>'''


def T(x, y, s, size=13, fill=INK, anchor="middle", weight="bold", style=None):
    st = f' font-style="{style}"' if style else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}"{st} {F}>{s}</text>')


def E(x, y, ch, size=44):
    """One emoji, horizontally centred on x, baseline at y."""
    return (f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="middle" '
            f'{EF}>{ch}</text>')


def panel(x, y, w, h, hue, title, title_size=19):
    """Outer stage panel: thick rounded border, tinted fill, bold title."""
    b, fill, _, tink = HUES[hue]
    return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" '
            f'fill="{fill}" stroke="{b}" stroke-width="3"/>',
            T(x + w / 2, y + 30, title, title_size, tink)]


def sub(x, y, w, h, hue, label=None, label_size=14):
    """Dashed sub-panel inside a stage."""
    b, _, fill, tink = HUES[hue]
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="11" '
           f'fill="{fill}" stroke="{b}" stroke-width="1.8" '
           f'stroke-dasharray="7 5"/>']
    if label:
        out.append(T(x + w / 2, y + 22, label, label_size, tink))
    return out


def arrow(x1, y1, x2, y2, width=5):
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{ARROW}" '
            f'stroke-width="{width}" stroke-linecap="round" '
            f'marker-end="url(#ar)"/>')


def curve(d, colour=ARROW, width=5, marker="ar", dash=None):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}" '
            f'stroke-linecap="round"{da} marker-end="url(#{marker})"/>')


def rowbox(x, y, w, label, border, fill, tink, h=25, dashed=False, size=11.5,
           weight="bold"):
    """A stored row: chunky outlined box with centred label."""
    d = ' stroke-dasharray="5 4"' if dashed else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" '
            f'stroke="{border}" stroke-width="2"{d}/>'
            + T(x + w / 2, y + h / 2 + 4, label, size, tink, weight=weight))


def pill(x, y, w, label, border, fill, tink, dashed=False):
    d = ' stroke-dasharray="5 4"' if dashed else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="26" rx="13" fill="{fill}" '
            f'stroke="{border}" stroke-width="1.9"{d}/>'
            + T(x + w / 2, y + 17.5, label, 11.5, tink))


# --------------------------------------------------------------- figure 1

def framework():
    W, H = 1020, 704
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" {F} '
         f'style="max-width:100%;height:auto">', DEFS,
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']

    # ============ stage 1: offline sedimentation (amber) ============
    s += panel(12, 10, 996, 198, "amber", "Offline · Sedimentation")
    s.append(T(986, 30, "runs once, before round 0", 11.5, "#a97528", "end",
               weight="normal", style="italic"))

    s += sub(30, 44, 236, 148, "amber", "Source Text")
    s.append(E(148, 118, "📖", 48))
    s.append(T(148, 146, "novel · play · timeline", 11, MUT, weight="normal"))
    s.append(T(148, 168, "held-out tail kept", 11, MUT, weight="normal"))
    s.append(T(148, 182, "for scoring", 11, MUT, weight="normal"))

    s.append(arrow(276, 118, 320, 118))

    s += sub(330, 44, 236, 148, "amber", "Extract &amp; Attribute")
    s.append(E(448, 112, "🔍", 42))
    s.append(T(448, 140, "who witnessed", 11.5, "#8a5a12"))
    s.append(T(448, 158, "each event?", 11.5, "#8a5a12"))
    s.append(T(448, 182, "one LLM pass per span", 11, MUT, weight="normal"))

    s.append(arrow(576, 118, 620, 118))

    s += sub(630, 44, 358, 148, "blue", "Owner-Tagged Events")
    for i, lab in enumerate(["e &#183; owners {A, B}", "&#8230; &#183; owners {C}",
                             "&#8230; &#183; owners {A, D}"]):
        s.append(rowbox(676, 74 + i * 32, 266, lab, "#3b82f6", "#ffffff", "#1e3a8a"))
    s.append(T(809, 182, "an event, not a copy per witness", 11, MUT, weight="normal"))

    # ============ stage 2: runtime (blue) ============
    # sits 40px below stage 1 so the seeding arrow has a lane of its own
    s += panel(12, 248, 996, 288, "blue", "Runtime · One World, One Shared Store")

    # --- the store
    s += sub(30, 284, 268, 234, "blue", "Shared Long-Term Memory")
    s.append(E(164, 352, "🧠", 44))
    s.append(f'<path d="M96,374 v66 a68,15 0 0 0 136,0 v-66" fill="#dbeafe" '
             f'stroke="#2563eb" stroke-width="2.5"/>')
    s.append(f'<ellipse cx="164" cy="374" rx="68" ry="15" fill="#eff6ff" '
             f'stroke="#2563eb" stroke-width="2.5"/>')
    s.append(T(164, 414, "one store,", 12.5, "#1e3a8a"))
    s.append(T(164, 432, "all characters", 12.5, "#1e3a8a"))
    s.append(T(164, 488, "internal structure", 11, MUT, weight="normal"))
    s.append(T(164, 502, "differs per backend", 11, MUT, weight="normal"))

    # drawn here, on top of the panel it lands in: it runs flat through the
    # gap, then drops well left of the panel title
    s.append(curve("M809,200 C640,216 400,216 176,278", width=5))
    s.append(T(600, 238, "seeds the store", 12.5, ARROW))

    # --- recall / remember
    s.append(arrow(306, 342, 372, 342))
    s.append(T(339, 330, "recall", 12, ARROW))
    s.append(arrow(372, 422, 306, 422))
    s.append(T(339, 410, "remember", 12, ARROW))
    s.append(T(339, 454, "both", 11, MUT, weight="normal"))
    s.append(T(339, 468, "owner-scoped", 11, MUT, weight="normal"))

    # --- the society
    s += sub(382, 284, 606, 234, "green", "The Society")

    s.append(E(470, 344, "🤖", 40))
    s.append(T(470, 366, "character", 11.5, "#0f6b3f"))
    s.append(E(700, 344, "🤖", 40))
    s.append(T(700, 366, "character", 11.5, "#0f6b3f"))
    s.append(E(470, 450, "🤖", 40))
    s.append(T(470, 472, "character", 11.5, "#0f6b3f"))

    # say thread
    s.append(f'<line x1="502" y1="330" x2="668" y2="330" stroke="{ARROW}" '
             f'stroke-width="4" stroke-linecap="round" marker-start="url(#ar)" '
             f'marker-end="url(#ar)"/>')
    s.append(T(585, 320, "say · kernel-held thread", 11.5, ARROW))
    s.append(curve("M500,442 L664,360", width=3.4, dash="7 5"))
    s.append(T(672, 438, "delivered with distance delay", 10.5, ARROW,
               weight="normal"))

    # environment + carrier
    s.append(E(892, 342, "🌍", 40))
    s.append(T(892, 364, "environment", 11.5, "#0f6b3f"))
    s.append(T(892, 380, "owns memories,", 10.5, MUT, weight="normal"))
    s.append(T(892, 394, "never takes a turn", 10.5, MUT, weight="normal"))
    s.append(E(892, 462, "📄", 36))
    s.append(T(892, 484, "info carrier", 11.5, "#8a5a12"))
    s.append(arrow(508, 460, 856, 464, 3.4))
    s.append(T(680, 492, "read", 12, ARROW))

    # ============ stage 3: the action repertoire (slate) ============
    s += panel(12, 554, 996, 138, "slate",
               "One Action per Character per Round, from a Single Repertoire", 17)

    GRN, GRN_L, GRN_D = "#059669", "#d1fae5", "#065f46"
    BLU, BLU_L, BLU_D = "#2563eb", "#dbeafe", "#1e3a8a"
    PUR, PUR_L, PUR_D = "#7c3aed", "#ede9fe", "#5b21b6"
    SL, SL_L, SL_D = "#94a3b8", "#f1f5f9", "#475569"
    RED, RED_L = "#dc2626", "#fee2e2"

    x = 34
    for lab, w in [("say", 48), ("read_thread", 92), ("observe", 70),
                   ("move", 54), ("act_on", 62), ("read", 50)]:
        s.append(pill(x, 598, w, lab, GRN, GRN_L, GRN_D)); x += w + 7
    for lab, w in [("think", 54), ("conclude", 74)]:
        s.append(pill(x, 598, w, lab, SL, SL_L, SL_D)); x += w + 7
    for lab, w in [("remember", 82), ("recall", 60)]:
        s.append(pill(x, 598, w, lab, BLU, BLU_L, BLU_D)); x += w + 7
    s.append(pill(x, 598, 48, "wait", SL, SL_L, SL_D))

    x = 34
    for lab, w in [("push_goal", 80), ("pop_goal", 74), ("replace_goal", 98),
                   ("update_status", 106)]:
        s.append(pill(x, 632, w, lab, PUR, PUR_L, PUR_D)); x += w + 7
    s.append(pill(x + 14, 632, 306, "6 memory-management actions · never used",
                  RED, RED_L, "#b91c1c", dashed=True))

    s.append(T(34, 680, "green = the world · blue = long-term memory · purple = goals · "
                        "grey = cognitive · red dashed = offered but never called",
               11, MUT, "start", weight="normal"))
    s.append('</svg>')
    return "\n".join(s)


# --------------------------------------------------------------- figure 2

def backends():
    W, H = 1020, 752
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" {F} '
         f'style="max-width:100%;height:auto">', DEFS,
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']

    GRN, GRN_L, GRN_D = "#059669", "#d1fae5", "#0f6b3f"
    AMB, AMB_L, AMB_D = "#d97706", "#fef3c7", "#8a5a12"
    RED, RED_L, RED_D = "#dc2626", "#fee2e2", "#9b1c1c"
    BLU, BLU_L, BLU_D = "#2563eb", "#dbeafe", "#1e3a8a"
    PUR, PUR_L, PUR_D = "#7c3aed", "#ede9fe", "#4c1d95"

    # ---------------- (a) Generative Agents ----------------
    s += panel(12, 10, 494, 336, "green", "(a) Generative Agents")
    s += sub(30, 44, 458, 226, "green", "One Private Stream per Agent")
    for cx, who in [(140, "A"), (378, "B")]:
        s.append(E(cx, 96, "🤖", 32))
        s.append(T(cx + 26, 90, who, 13, INK))
    for i, lab in enumerate(["e &#183; imp .8", "&#8230; &#183; .4", "&#8230; &#183; .9"]):
        s.append(rowbox(66, 108 + i * 30, 148, lab, GRN, "#ffffff", GRN_D, h=24))
    for i, lab in enumerate(["e &#183; imp .7", "&#8230; &#183; .5", "&#8230; &#183; .6"]):
        s.append(rowbox(304, 108 + i * 30, 148, lab, GRN, "#ffffff", GRN_D, h=24))
    s.append(E(259, 128, "🌳", 26))
    s.append(rowbox(66, 202, 148, "reflection", GRN, GRN_L, GRN_D, h=24, dashed=True))
    s.append(rowbox(304, 202, 148, "reflection", GRN, GRN_L, GRN_D, h=24, dashed=True))
    s.append(T(259, 220, "no edge", 10.5, MUT, weight="normal"))
    s.append(T(259, 233, "crosses", 10.5, MUT, weight="normal"))
    s.append(T(259, 246, "the lanes", 10.5, MUT, weight="normal"))
    s.append(T(259, 292, "The same event e is stored once per witness.", 12, GRN_D))
    s.append(T(259, 314, "Recall scores recency × importance × relevance.",
               11, MUT, weight="normal"))
    s.append(T(259, 334, "streams + a private reflection tree", 11, MUT,
               weight="normal", style="italic"))

    # ---------------- (b) G-Memory ----------------
    s += panel(514, 10, 494, 336, "amber", "(b) G-Memory")
    s += sub(532, 44, 458, 226, "amber", "Two-Tier Graph, per Owner")
    for cx, who in [(642, "A"), (880, "B")]:
        s.append(E(cx, 96, "🤖", 32))
        s.append(T(cx + 26, 90, who, 13, INK))
        s.append(f'<ellipse cx="{cx}" cy="132" rx="52" ry="18" fill="{AMB_L}" '
                 f'stroke="{AMB}" stroke-width="2" stroke-dasharray="5 4"/>')
        s.append(T(cx, 137, "insight", 12, AMB_D))
        for i in range(3):
            bx = cx - 78 + i * 52
            s.append(rowbox(bx, 208, 44, "e" if i == 0 else "&#8230;", AMB,
                            "#ffffff", AMB_D, h=24))
            s.append(f'<line x1="{cx}" y1="152" x2="{bx + 22}" y2="204" '
                     f'stroke="{AMB}" stroke-width="1.6" marker-end="url(#ai)"/>')
    s.append(E(761, 142, "🕸️", 26))
    s.append(T(761, 186, "derived_from", 11, AMB_D))
    s.append(T(761, 250, "insight tier distilled every 20 rounds", 11, MUT,
               weight="normal"))
    s.append(T(761, 292, "Recall hits both tiers, then walks the edges.", 12, AMB_D))
    s.append(T(761, 314, "A real graph — but never across owners.", 11, MUT,
               weight="normal", style="italic"))

    # ---------------- (c) Collaborative ----------------
    s += panel(12, 362, 494, 354, "red", "(c) Collaborative")
    s += sub(30, 396, 458, 226, "red", "One Store, Partitioned by Permission")
    for cx, who in [(140, "A"), (378, "B")]:
        s.append(E(cx, 448, "🤖", 32))
        s.append(T(cx + 26, 442, who, 13, INK))
    s.append(rowbox(60, 470, 168, "e &#183; acl {A}", RED, RED_L, RED_D))
    s.append(rowbox(290, 470, 168, "e &#183; acl {A, B}", RED, RED_L, RED_D))
    s.append(rowbox(60, 506, 168, "&#8230; &#183; acl {A}", RED, "#ffffff", RED_D))
    s.append(rowbox(290, 506, 168, "&#8230; &#183; acl {B}", RED, "#ffffff", RED_D))
    s.append(E(259, 492, "🔒", 26))
    s.append(curve("M144,544 C180,584 338,584 374,544", colour=RED, width=2.6,
                   marker="ai", dash="6 4"))
    s.append(T(259, 588, "grant", 12, RED_D))
    s.append(T(259, 610, "two rows, one event", 11, MUT, weight="normal"))
    s.append(T(259, 654, "B may be granted access to A's copy —", 12, RED_D))
    s.append(T(259, 674, "but the copy remains.", 12, RED_D))
    s.append(T(259, 700, "sharing is a permission, not a merge", 11, MUT,
               weight="normal", style="italic"))

    # ---------------- (d) Consensus ----------------
    s += panel(514, 362, 494, 354, "blue", "(d) Consensus  (ours)")
    s += sub(532, 396, 458, 226, "blue", "One Record, Several Owners")
    for cx, who, tx in [(628, "A", 672), (760, "B", 760), (892, "C", 848)]:
        s.append(E(cx, 448, "🤖", 32))
        s.append(T(cx + 24, 442, who, 13, INK))
        s.append(f'<line x1="{cx}" y1="458" x2="{tx}" y2="482" stroke="{ARROW}" '
                 f'stroke-width="3" stroke-linecap="round" marker-end="url(#ar)"/>')
    s.append(rowbox(600, 490, 320, "e &#183; owners {A, B, C}", BLU, BLU_L, BLU_D,
                    h=30, size=13.5))
    s.append(T(760, 538, "equivalent deposits merged · owners unioned",
               11, MUT, weight="normal"))
    s.append(E(760, 578, "🔗", 24))
    s.append(rowbox(566, 560, 152, "sibling &#183; {A, B}", PUR, PUR_L, PUR_D, h=24))
    s.append(rowbox(802, 560, 140, "sibling &#183; {C}", PUR, PUR_L, PUR_D, h=24))
    s.append(f'<line x1="606" y1="520" x2="642" y2="556" stroke="{PUR}" '
             f'stroke-width="1.8" marker-end="url(#ard)"/>')
    s.append(f'<line x1="914" y1="520" x2="872" y2="556" stroke="{PUR}" '
             f'stroke-width="1.8" marker-end="url(#ard)"/>')
    s.append(T(760, 604, "affiliated", 11, PUR_D))
    s.append(T(760, 654, "Recall returns the rows you own,", 12, BLU_D))
    s.append(T(760, 674, "then walks one hop along the affiliation edges.", 12, BLU_D))
    s.append(T(760, 700, "sharing is computed at deposit time", 11, MUT,
               weight="normal", style="italic"))

    s.append(T(510, 740, "the same event e in every panel · 🤖 = owner · "
                         "solid box = a stored row · dashed = generated by the mechanism",
               11, MUT, weight="normal"))
    s.append('</svg>')
    return "\n".join(s)


if __name__ == "__main__":
    for name, fn in [("framework", framework), ("backends", backends)]:
        open(f"paper/figures/{name}.svg", "w", encoding="utf-8").write(fn())
        print(f"wrote paper/figures/{name}.svg")
