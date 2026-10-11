#!/usr/bin/env python3
"""Draws the GitHub social preview (1280 x 640) -> assets/social-preview.png.

Three item cards in the look of the printed ones in front of the dark background, the logo and the title.
Needs Pillow and the TeX Gyre Pagella fonts that come with TeX Live / MiKTeX.

    python3 tools/social.py

GitHub has no API for the image: upload it by hand under Settings > General > Social preview.
"""
import glob
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1280, 640
INK, RED, GOLD, PARCH = (29, 23, 20), (122, 42, 31), (184, 156, 108), (247, 241, 230)
GREY, PARCH_DARK, CARD_LINE = (111, 102, 92), (239, 227, 198), (216, 203, 178)
CARD_W, CARD_H = 280, 392  # 63.5 x 88.9 mm


def font(style, size):
    for base in (os.path.expandvars(r"%LOCALAPPDATA%\Programs\MiKTeX\fonts"),
                 "/usr/share/texlive/texmf-dist/fonts", "/usr/share/texmf/fonts"):
        hit = glob.glob(os.path.join(base, f"**/texgyrepagella-{style}.otf"), recursive=True)
        if hit:
            return ImageFont.truetype(hit[0], size)
    return ImageFont.load_default()


def wrap(d, text, f, width):
    lines, line = [], ""
    for word in text.split():
        if line and d.textlength(line + " " + word, font=f) > width:
            lines.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    return lines + [line]


def card(name, kind, stats, text, bullets):
    """One card: stats are (label, value) pairs, bullets are (label, text) pairs."""
    img = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, CARD_W - 1, CARD_H - 1], radius=14, fill=PARCH)
    d.rounded_rectangle([7, 7, CARD_W - 8, CARD_H - 8], radius=10, outline=GOLD, width=2)
    x, w = 22, CARD_W - 44
    y = 22
    d.text((x, y), name, font=font("bold", 21), fill=RED)
    y += 29
    d.text((x, y), kind, font=font("italic", 12), fill=GREY)
    y += 20
    d.line([x, y, x + w, y], fill=CARD_LINE, width=1)
    y += 10
    if stats:
        d.rounded_rectangle([x, y, x + w, y + 46], radius=5, fill=PARCH_DARK)
        for i, (label, value) in enumerate(stats):
            cx = x + w * (2 * i + 1) / (2 * len(stats))
            d.text((cx, y + 11), label, font=font("regular", 10), fill=GREY, anchor="mm")
            d.text((cx, y + 31), value, font=font("bold", 17), fill=INK, anchor="mm")
        y += 58
    body, bold = font("regular", 13), font("bold", 13)
    for line in wrap(d, text, body, w):
        d.text((x, y), line, font=body, fill=INK)
        y += 16
    y += 6
    for label, rest in bullets:
        d.text((x, y), "•", font=body, fill=INK)
        d.text((x + 12, y), label + ":", font=bold, fill=INK)
        lead = d.textlength(label + ": ", font=bold)
        first = True
        for line in wrap(d, " " * 0 + rest, body, w - 12 - lead):
            d.text((x + 12 + (lead if first else 0), y), line, font=body, fill=INK)
            first = False
            y += 16
        if first:
            y += 16
        y += 3
    return img


def place(canvas, c, center, angle, scale=0.9):
    """Pastes a card rotated by `angle` degrees around `center`, with a soft shadow."""
    c = c.resize((int(c.width * scale), int(c.height * scale)), Image.LANCZOS)
    rot = c.rotate(angle, resample=Image.BICUBIC, expand=True)
    shadow = Image.new("RGBA", rot.size, (0, 0, 0, 0))
    shadow.putalpha(rot.getchannel("A").point(lambda a: a * 190 // 255))
    pad = 30  # room for the blur
    padded = Image.new("RGBA", (rot.width + 2 * pad, rot.height + 2 * pad), (0, 0, 0, 0))
    padded.paste(shadow, (pad, pad))
    padded = padded.filter(ImageFilter.GaussianBlur(12))
    x, y = int(center[0] - rot.width / 2), int(center[1] - rot.height / 2)
    canvas.alpha_composite(padded, (x - pad + 5, y - pad + 12))
    canvas.alpha_composite(rot, (x, y))


# Background: dark, a little lighter towards the cards
img = Image.new("RGBA", (W, H), INK + (255,))
glow = Image.new("L", (W, H), 0)
ImageDraw.Draw(glow).ellipse([640, 40, 1240, 600], fill=70)
img = Image.composite(Image.new("RGBA", (W, H), (70, 40, 30, 255)), img, glow.filter(ImageFilter.GaussianBlur(120)))

armour = card("Kettenhemd der Wacht", "Coat of mail · númenórische Arbeit", [("Protection", "4d"), ("Load", "12")],
              "Ein langes Hemd aus feinen númenórischen Ringen, leicht wie Leder und blank geblieben.",
              [("Close-fitting", "+2 auf Protection-Würfe"), ("Cunning Make", "Load −2")])
horn = card("Das Horn der Wacht", "Wondrous Item · númenórische Arbeit", [],
            "Ein silberbeschlagenes Horn, von den Dúnedain des Nordens gefertigt, das einst die Besatzung auf die Mauern rief.",
            [("Blessings", "Awe, Battle (2d)"), ("Ruf der Wacht", "Einmal pro Nacht: Gegner mit Hate 3 oder weniger fliehen.")])
sword = card("Narcrist", "Famous Weapon · Long sword", [("Damage", "5"), ("Injury", "16/18"), ("Load", "3")],
             "In Gondolin geschmiedet, weit älter als die Festung. Die Runen nannten ihren Namen: Narcrist.",
             [("Keen", "Piercing Blow schon bei 9 auf dem Feat die"), ("Superior Fell", "Injury +4"),
              ("Bane", "Orks")])
place(img, armour, (805, 335), 7)
place(img, horn, (1075, 335), -7)
place(img, sword, (940, 315), 0)

d = ImageDraw.Draw(img)
d.rectangle([28, 28, W - 29, H - 29], outline=GOLD, width=3)
d.rectangle([40, 40, W - 41, H - 41], outline=GOLD, width=1)

logo = Image.open(os.path.join(ROOT, "assets", "logo.png")).convert("RGBA")
logo = logo.resize((88, 88), Image.LANCZOS)
img.alpha_composite(logo, (88, 100))

x = 90
d.text((x, 215), "THE ONE RING · 2. EDITION", font=font("bold", 26), fill=GOLD)
d.text((x, 255), "Schatzkammer", font=font("bolditalic", 80), fill=PARCH)
d.line([x, 378, x + 330, 370], fill=GOLD, width=2)
d.text((x, 395), "Gegenstände und Horte", font=font("italic", 38), fill=(226, 212, 184))
d.text((x, 462), "Karten im Pokerformat zum Ausdrucken", font=font("regular", 24), fill=(190, 176, 150))

out = os.path.join(ROOT, "assets", "social-preview.png")
img.convert("RGB").save(out, optimize=True)
print(out)
