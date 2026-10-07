#!/usr/bin/env python3
"""Draws the logo (a shield in front of a sword) -> assets/logo.svg, logo.png (512), logo-print.png (512, red).

White on transparent, plus logo-print.png in the title red of latex/tor2e.sty for the PDF. SVG and rasters come
from the same coordinates (64 x 64 grid).

    python3 tools/logo.py        # needs Pillow
"""
import math
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "assets")
INK = (245, 243, 242)      # #f5f3f2
RED = (0x7A, 0x2A, 0x1F)   # fwred in latex/tor2e.sty
HALO = 2.6                 # gap between the shield and the sword behind it


def curve(p0, p1, p2, n=16):
    """Points of a quadratic Bezier curve from p0 to p2, without p0."""
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (i / n for i in range(1, n + 1))]


# Shield: a flat top with a shallow point, straight sides, curving to a point below
outer = [(21, 29), (32, 27), (43, 29), (43, 38)]
outer += curve((43, 38), (42.5, 46), (32, 49.5))
outer += curve((32, 49.5), (21.5, 46), (21, 38))
cx, cy, f = 32, 38.5, 0.70
inner = [(cx + (x - cx) * f, cy + (y - cy) * f) for x, y in outer]   # the rim is the gap between the two
boss = (32, 38.5, 2.6)                                                  # x, y, radius

# Sword upright behind the shield; u runs from the tip down the sword, v across it
tip = (32, 6.5)
d = (0, 1)
n = (1, 0)


def P(u, v):
    return (tip[0] + u * d[0] + v * n[0], tip[1] + u * d[1] + v * n[1])


blade = [P(0, 0), P(5, 2.3), P(16.5, 2.3), P(16.5, -2.3), P(5, -2.3)]
guard = [P(16.5, -8), P(16.5, 8), P(19.3, 8), P(19.3, -8)]
grip = [P(19.3, -1.3), P(19.3, 1.3), P(48.5, 1.3), P(48.5, -1.3)]
pommel = (*P(48.5, 0), 2.1)


def path(p):
    return "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in p) + "Z"


svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <mask id="behind"><rect width="64" height="64" fill="#fff"/><path d="{path(outer)}" fill="#000" stroke="#000" stroke-width="{2 * HALO:g}" stroke-linejoin="round"/></mask>
  </defs>
  <circle cx="32" cy="32" r="29" fill="none" stroke="#f5f3f2" stroke-width="3"/>
  <g fill="#f5f3f2">
    <g mask="url(#behind)"><path d="{path(blade)} {path(guard)} {path(grip)}"/><circle cx="{pommel[0]:.2f}" cy="{pommel[1]:.2f}" r="{pommel[2]}"/></g>
    <path fill-rule="evenodd" d="{path(outer)} {path(inner)}"/>
    <circle cx="{boss[0]}" cy="{boss[1]}" r="{boss[2]}"/>
  </g>
</svg>
'''
open(os.path.join(A, "logo.svg"), "w", encoding="utf-8").write(svg)

S = 8 * 64
k = S / 64


def sc(p):
    return [(x * k, y * k) for x, y in p]


def disc(m, x, y, r, fill):
    ImageDraw.Draw(m).ellipse([(x - r) * k, (y - r) * k, (x + r) * k, (y + r) * k], fill=fill)


# the sword, without what the shield and its gap cover
sword = Image.new("L", (S, S), 0)
ImageDraw.Draw(sword).polygon(sc(blade), fill=255)
ImageDraw.Draw(sword).polygon(sc(guard), fill=255)
ImageDraw.Draw(sword).polygon(sc(grip), fill=255)
disc(sword, *pommel, 255)
halo = Image.new("L", (S, S), 0)
hd = ImageDraw.Draw(halo)
hd.polygon(sc(outer), fill=255)
hd.line(sc(outer + outer[:1]), fill=255, width=int(2 * HALO * k), joint="curve")
for x, y in sc(outer):
    hd.ellipse([x - HALO * k, y - HALO * k, x + HALO * k, y + HALO * k], fill=255)
sword.paste(0, mask=halo)

m = sword
d_ = ImageDraw.Draw(m)
d_.ellipse([3 * k, 3 * k, 61 * k, 61 * k], outline=255, width=int(3 * k))
d_.polygon(sc(outer), fill=255)
d_.polygon(sc(inner), fill=0)
disc(m, *boss, 255)

for name, rgb in (("logo.png", INK), ("logo-print.png", RED)):
    img = Image.new("RGBA", (S, S), rgb + (0,))
    img.putalpha(m)
    img.resize((512, 512), Image.LANCZOS).save(os.path.join(A, name), optimize=True)
print("assets/logo.svg, logo.png, logo-print.png")
