#!/usr/bin/env python3
"""Draws the source icons of the cards -> assets/icons/ring.png and book.png (512, red, transparent).

The icon in the corner of a card says where the item comes from; src/rules.toml ([sources]) names
the icon of each source. assets/icons/finsterwacht.png is the logo of the adventure and is not drawn here.

    python3 tools/icons.py        # needs Pillow
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "icons")
RED = (0x7A, 0x2A, 0x1F, 255)   # fwred in latex/tor2e.sty
SIZE = 512
S = 4                           # supersampling


def canvas():
    im = Image.new("RGBA", (SIZE * S, SIZE * S), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def save(im, name):
    os.makedirs(OUT, exist_ok=True)
    im.resize((SIZE, SIZE), Image.LANCZOS).save(os.path.join(OUT, name))
    print("assets/icons/" + name)


def box(cx, cy, rx, ry):
    return [(cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S]


def ring():
    """A plain band, seen slightly from above: the opening and the inside of the far wall."""
    im, d = canvas()
    d.ellipse(box(256, 270, 216, 170), fill=RED)                 # the band
    d.ellipse(box(256, 246, 172, 112), fill=(0, 0, 0, 0))        # the opening
    d.ellipse(box(256, 262, 172, 112), outline=RED, width=14 * S)  # inner edge: the far wall
    d.ellipse(box(256, 300, 150, 92), fill=(0, 0, 0, 0))         # ... cut back to a crescent
    # keep the crescent only inside the opening; outside of it the band stays solid
    hole = Image.new("L", im.size, 0)
    ImageDraw.Draw(hole).ellipse(box(256, 246, 172, 126), fill=255)
    inside = Image.composite(im.getchannel("A"), Image.new("L", im.size, 0), hole)
    solid = Image.new("L", im.size, 0)
    ds = ImageDraw.Draw(solid)
    ds.ellipse(box(256, 270, 216, 170), fill=255)
    ds.ellipse(box(256, 246, 172, 112), fill=0)
    alpha = Image.composite(Image.new("L", im.size, 255), inside, solid)
    out = Image.new("RGBA", im.size, RED)
    out.putalpha(alpha)
    save(out, "ring.png")


def book():
    """An open book: two pages rising from the spine, a few lines of writing."""
    im, d = canvas()

    def poly(points, **kw):
        d.polygon([(x * S, y * S) for x, y in points], **kw)

    def line(points, width):
        d.line([(x * S, y * S) for x, y in points], fill=RED, width=width * S, joint="curve")

    # cover, showing below the pages
    poly([(40, 150), (256, 196), (472, 150), (472, 400), (256, 446), (40, 400)], fill=RED)
    # pages
    clear = (0, 0, 0, 0)
    poly([(66, 132), (244, 172), (244, 408), (66, 368)], fill=clear)
    poly([(446, 132), (268, 172), (268, 408), (446, 368)], fill=clear)
    for x0, x1, sign in ((66, 244, 1), (446, 268, -1)):
        d.line([(x0 * S, 132 * S), (x1 * S, 172 * S), (x1 * S, 408 * S), (x0 * S, 368 * S), (x0 * S, 132 * S)],
               fill=RED, width=14 * S, joint="curve")
        for y in (204, 256, 308):
            line([(x0 + sign * 34, y), (x1 - sign * 30, y + 32)], 14)
    save(im, "book.png")


if __name__ == "__main__":
    ring()
    book()
