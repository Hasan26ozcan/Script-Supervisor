"""Generate nicer, distinct illustrative reference images for each grounding
category. These are stylised (not photographic) scene renders built with
PIL: gradients + simple geometry evoking each location's color palette,
lighting and composition, so relevant/irrelevant pairs are visually
meaningful for the grounding experiment instead of flat color rectangles.
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

W, H = 800, 600
OUT = "data/images/grounding"


def vgrad(size, top, bottom):
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    return img


def add_glow(img, center, radius, color, alpha=120):
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse(
        [center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius],
        fill=color + (alpha,),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius // 2))
    img.paste(Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB"), (0, 0))


def warehouse():
    img = vgrad((W, H), (28, 30, 34), (12, 12, 15))
    d = ImageDraw.Draw(img, "RGBA")
    # rows of shelving silhouettes with vanishing perspective
    for row in range(5):
        y0 = 380 + row * 4
        for i in range(6):
            x0 = 40 + i * 130
            d.rectangle([x0, y0 - 260 + row * 6, x0 + 90, y0], fill=(8, 8, 10, 255), outline=(50, 50, 55, 255))
    # single hanging light with cone
    d.polygon([(400, 40), (250, 420), (550, 420)], fill=(255, 220, 150, 40))
    d.ellipse([385, 25, 415, 55], fill=(255, 235, 190, 230))
    return img


def golden_hour_street():
    img = vgrad((W, H), (255, 176, 90), (255, 120, 70))
    d = ImageDraw.Draw(img, "RGBA")
    add_glow(img, (600, 160), 140, (255, 240, 200))
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse([560, 120, 640, 200], fill=(255, 250, 220, 255))
    # building silhouettes
    silhouettes = [(0, 260, 120, 600), (110, 200, 260, 600), (600, 240, 760, 600), (700, 180, 800, 600)]
    for x0, y0, x1, y1 in silhouettes:
        d.rectangle([x0, y0, x1, y1], fill=(35, 20, 20, 255))
    d.rectangle([0, 440, 800, 600], fill=(50, 30, 28, 255))
    return img


def fluorescent_office():
    img = vgrad((W, H), (225, 228, 232), (195, 198, 202))
    d = ImageDraw.Draw(img, "RGBA")
    # ceiling light panels
    for i in range(4):
        x0 = 60 + i * 180
        d.rectangle([x0, 30, x0 + 130, 60], fill=(255, 255, 250, 255), outline=(150, 150, 150, 255))
        add_glow(img, (x0 + 65, 45), 60, (255, 255, 245), alpha=60)
        d = ImageDraw.Draw(img, "RGBA")
    # cubicle grid
    for i in range(5):
        x = 40 + i * 150
        d.rectangle([x, 350, x + 120, 560], fill=(170, 172, 176, 255), outline=(120, 122, 126, 255))
    return img


def neon_alley():
    img = vgrad((W, H), (15, 10, 25), (25, 15, 35))
    d = ImageDraw.Draw(img, "RGBA")
    add_glow(img, (200, 300), 160, (255, 20, 147))
    add_glow(img, (600, 250), 160, (0, 255, 255))
    d = ImageDraw.Draw(img, "RGBA")
    # buildings
    d.rectangle([0, 100, 250, 600], fill=(10, 8, 15, 255))
    d.rectangle([550, 60, 800, 600], fill=(10, 8, 15, 255))
    # neon sign shapes
    d.rectangle([60, 220, 220, 260], fill=(255, 20, 147, 220))
    d.rectangle([580, 180, 760, 210], fill=(0, 255, 255, 220))
    # wet pavement reflection
    d.rectangle([0, 480, 800, 600], fill=(20, 12, 28, 255))
    for i in range(30):
        x = random.randint(0, 800)
        d.line([(x, 480), (x + random.randint(-5, 5), 600)], fill=(120, 60, 120, 60))
    return img


def forest_clearing():
    img = vgrad((W, H), (150, 200, 120), (40, 80, 40))
    d = ImageDraw.Draw(img, "RGBA")
    add_glow(img, (420, 60), 220, (255, 250, 210), alpha=140)
    d = ImageDraw.Draw(img, "RGBA")
    # light shafts
    for i in range(5):
        x = 150 + i * 120
        d.polygon([(x, 0), (x + 40, 0), (x - 60, 600), (x - 140, 600)], fill=(255, 250, 220, 35))
    # tree trunks
    for i in range(6):
        x = 30 + i * 140 + random.randint(-10, 10)
        d.rectangle([x, 180, x + 34, 600], fill=(45, 33, 22, 255))
    return img


def hospital_corridor():
    img = vgrad((W, H), (225, 232, 235), (205, 214, 218))
    d = ImageDraw.Draw(img, "RGBA")
    vp = (400, 260)
    # receding floor/ceiling lines for corridor perspective
    d.polygon([(0, 600), (800, 600), vp[0] + 60, vp[1] + 20, vp[0] - 60, vp[1] + 20], fill=(190, 196, 200, 255))
    d.polygon([(0, 0), (800, 0), (vp[0] + 60, vp[1] - 20), (vp[0] - 60, vp[1] - 20)], fill=(245, 248, 250, 255))
    # side walls
    d.polygon([(0, 0), (0, 600), (vp[0] - 60, vp[1] + 20), (vp[0] - 60, vp[1] - 20)], fill=(210, 216, 220, 255))
    d.polygon([(800, 0), (800, 600), (vp[0] + 60, vp[1] + 20), (vp[0] + 60, vp[1] - 20)], fill=(215, 221, 225, 255))
    # ceiling light strip
    for i in range(4):
        t = i / 3
        y = int(60 + t * (vp[1] - 40 - 60))
        x0 = int(200 - t * 150)
        x1 = int(600 + t * 150 - (x1 if False else 0))
    d.line([(200, 60), (vp[0] - 40, vp[1] - 15)], fill=(255, 255, 245, 220), width=6)
    d.line([(600, 60), (vp[0] + 40, vp[1] - 15)], fill=(255, 255, 245, 220), width=6)
    return img


def subway_car():
    img = vgrad((W, H), (55, 58, 65), (25, 27, 32))
    d = ImageDraw.Draw(img, "RGBA")
    # windows with faint motion-blur lights outside
    for i in range(4):
        x0 = 60 + i * 180
        d.rectangle([x0, 120, x0 + 140, 260], fill=(70, 90, 110, 255))
        for j in range(4):
            xx = x0 + 10 + j * 32
            d.ellipse([xx, 170, xx + 10, 180], fill=(255, 220, 150, 160))
    # ceiling handrail poles
    for x in (150, 400, 650):
        d.line([(x, 60), (x, 560)], fill=(140, 140, 145, 255), width=8)
    # seats
    d.rectangle([0, 420, 800, 560], fill=(120, 40, 45, 255))
    return img


def rooftop_sunset():
    img = vgrad((W, H), (255, 140, 90), (120, 60, 120))
    d = ImageDraw.Draw(img, "RGBA")
    add_glow(img, (400, 140), 170, (255, 235, 190))
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse([350, 90, 450, 190], fill=(255, 244, 214, 255))
    # skyline silhouette
    xs = 0
    random.seed(7)
    while xs < 800:
        w = random.randint(40, 90)
        h = random.randint(80, 260)
        d.rectangle([xs, 600 - h, xs + w, 600], fill=(25, 15, 30, 255))
        xs += w + random.randint(4, 14)
    # foreground rooftop ledge
    d.rectangle([0, 560, 800, 600], fill=(20, 12, 18, 255))
    return img


GENERATORS = {
    "warehouse": warehouse,
    "golden_hour_street": golden_hour_street,
    "fluorescent_office": fluorescent_office,
    "neon_alley": neon_alley,
    "forest_clearing": forest_clearing,
    "hospital_corridor": hospital_corridor,
    "subway_car": subway_car,
    "rooftop_sunset": rooftop_sunset,
}

# Cross-pair each category with a visually distinct category for the
# "irrelevant" condition, instead of a flat placeholder color.
IRRELEVANT_PAIRING = {
    "warehouse": "rooftop_sunset",
    "golden_hour_street": "hospital_corridor",
    "fluorescent_office": "neon_alley",
    "neon_alley": "forest_clearing",
    "forest_clearing": "subway_car",
    "hospital_corridor": "golden_hour_street",
    "subway_car": "warehouse",
    "rooftop_sunset": "fluorescent_office",
}


def main():
    random.seed(42)
    cache = {}
    for name, fn in GENERATORS.items():
        cache[name] = fn()

    for name in GENERATORS:
        out_dir = os.path.join(OUT, name)
        os.makedirs(out_dir, exist_ok=True)
        cache[name].save(os.path.join(out_dir, "relevant.jpg"), quality=90)
        irrelevant_name = IRRELEVANT_PAIRING[name]
        cache[irrelevant_name].save(os.path.join(out_dir, "irrelevant.jpg"), quality=90)
        print(f"{name}: relevant=self, irrelevant={irrelevant_name}")


if __name__ == "__main__":
    main()
