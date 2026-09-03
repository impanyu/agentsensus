# Icon assets

The SVGs in this directory are **OpenMoji** glyphs, vendored so the figure
build does not depend on the network.

- Source: https://openmoji.org (openmoji-15.0.0, `color/svg`)
- Licence: **CC BY-SA 4.0** — attribution *and* share-alike
- Used by: `experiments/method_figs.py`, which inlines them as vector groups
  into Figures 1 and 2

They are deliberately not the system emoji font. Apple Color Emoji is glossy
and shaded; these are flat fills under a uniform black outline, which is what
the figures' style is built on. Same codepoints, different artwork.

If the share-alike term is unwanted, Twemoji (CC BY 4.0, attribution only) is
a drop-in swap at the same viewBox — its glyphs have no black outline, so the
figures would read softer.

A camera-ready using these icons should carry an attribution line, e.g.
"Figure icons from OpenMoji (openmoji.org), CC BY-SA 4.0."
