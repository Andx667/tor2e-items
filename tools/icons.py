#!/usr/bin/env python3
"""Draws the source icons of the cards -> assets/icons/ring.png, book.png, lone-lands.png, erebor.png and over-hill.png (512, red, transparent).

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


def lone_lands():
    """A horse with two riders, up to its knees in snow: the cover of Tales from the Lone-lands."""
    im, d = canvas()

    def poly(points):
        d.polygon([(x * S, y * S) for x, y in points], fill=RED)

    d.ellipse(box(240, 290, 140, 62), fill=RED)                                 # body
    poly([(318, 262), (372, 150), (420, 176), (382, 318)])                      # neck
    poly([(372, 150), (396, 132), (486, 204), (470, 236), (412, 204)])          # head
    poly([(378, 150), (384, 104), (408, 140)])                                  # ear
    poly([(112, 262), (62, 300), (52, 392), (84, 392), (128, 316)])             # tail
    for x in (128, 176, 292, 340):                                              # legs, cut off by the snow
        d.rectangle([x * S, 300 * S, (x + 30) * S, 404 * S], fill=RED)
    for x, top, r in ((284, 150, 26), (196, 164, 24)):                          # the riders
        poly([(x - 36, 252), (x - 24, top), (x + 24, top), (x + 40, 252)])
        d.ellipse(box(x + 4, top - r + 2, r, r), fill=RED)
    d.line([(x * S, y * S) for x, y in ((14, 430), (120, 412), (256, 428), (392, 410), (498, 428))],
           fill=RED, width=18 * S, joint="curve")                               # the snow
    save(im, "lone-lands.png")


def erebor():
    """The Lonely Mountain: a single peak with a cap of snow, two lower shoulders."""
    im, d = canvas()

    def poly(points, fill=RED):
        d.polygon([(x * S, y * S) for x, y in points], fill=fill)

    poly([(8, 440), (112, 318), (150, 352), (256, 70), (362, 352), (400, 318), (504, 440)])
    # the snow line: a jagged gap below the summit
    top = [(176, 204), (212, 226), (234, 198), (256, 226), (278, 198), (300, 226), (336, 204)]
    poly(top + [(x, y + 28) for x, y in reversed(top)], fill=(0, 0, 0, 0))
    save(im, "erebor.png")


def over_hill():
    """A hill with a round door in it: Over Hill and Under Hill."""
    im, d = canvas()
    d.pieslice(box(256, 420, 240, 320), 180, 360, fill=RED)          # the hill
    d.rectangle([4 * S, 404 * S, 508 * S, 436 * S], fill=RED)          # the ground
    d.ellipse(box(256, 318, 92, 92), fill=(0, 0, 0, 0))                # the door ...
    d.ellipse(box(256, 318, 66, 66), fill=RED)                         # ... in its frame
    d.ellipse(box(256, 318, 14, 14), fill=(0, 0, 0, 0))                # the knob in the middle
    save(im, "over-hill.png")


if __name__ == "__main__":
    ring()
    book()
    lone_lands()
    erebor()
    over_hill()
