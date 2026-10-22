"""
Cartões de NOTÍCIA da Beyond100 (1080x1350), escritos só a partir de dados
(ranking, resultado). Nada é inventado: cada campo vem do dicionário de entrada.

Uso:
    py news_card.py            # gera 2 exemplos FICTÍCIOS em news_samples/

Tipos:
    render_rising(d, out)  -> jogador que sobe / entra no top 100
    render_upset(d, out)   -> surpresa (jogador de ranking bem pior vence)
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
GREEN, CREAM, VOLT, MUTED, DEEP = (14, 58, 45), (247, 242, 230), (217, 242, 61), (176, 196, 183), (9, 40, 31)

SERIF_B = ["C:/Windows/Fonts/georgiab.ttf", "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
           "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"]
SERIF_I = ["C:/Windows/Fonts/georgiai.ttf", "/System/Library/Fonts/Supplemental/Georgia Italic.ttf",
           "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"]
SANS_B = ["C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
          "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
SANS_R = ["C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
          "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
BRAND = "@beyond100.tennis"


def font(paths, size):
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def fit(d, text, paths, size, max_w, min_size=30):
    f = font(paths, size)
    while d.textlength(text, font=f) > max_w and size > min_size:
        size -= 2
        f = font(paths, size)
    return f


def spaced(d, cx, cy, text, f, fill, track):
    ws = [d.textlength(c, font=f) for c in text]
    x = cx - (sum(ws) + track * (len(text) - 1)) / 2
    for c, w in zip(text, ws):
        d.text((x, cy), c, font=f, fill=fill, anchor="lm")
        x += w + track


def wrap(d, text, f, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur] if cur else lines


def base(badge):
    im = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(im)
    d.rectangle([36, 36, W - 37, H - 37], outline=CREAM, width=3)
    d.rectangle([52, 52, W - 53, H - 53], outline=CREAM, width=1)
    spaced(d, W / 2, 125, "BEYOND100", font(SERIF_B, 40), CREAM, 10)
    bf = font(SANS_B, 32)
    bw = d.textlength(badge, font=bf) + 8 * (len(badge) - 1) + 80
    d.rounded_rectangle([W / 2 - bw / 2, 175, W / 2 + bw / 2, 237], radius=31, fill=VOLT)
    spaced(d, W / 2, 207, badge, bf, GREEN, 8)
    return im, d


def footer(d):
    d.ellipse([W / 2 - 9, 1228, W / 2 + 9, 1246], fill=VOLT)
    d.text((W / 2, 1280), BRAND, font=font(SANS_B, 34), fill=CREAM, anchor="mm")


def rank_box(d, x, y, w, h, label, rank, hot):
    if hot:
        d.rounded_rectangle([x, y, x + w, y + h], radius=34, fill=VOLT)
        c1, c2 = GREEN, GREEN
    else:
        d.rounded_rectangle([x, y, x + w, y + h], radius=34, outline=CREAM, width=3)
        c1, c2 = MUTED, CREAM
    d.text((x + w / 2, y + 48), label, font=font(SANS_B, 28), fill=c1, anchor="mm")
    d.text((x + w / 2, y + h / 2 + 28), f"#{rank}", font=font(SERIF_B, 120), fill=c2, anchor="mm")


# ---------- RISING ----------
def render_rising(data, out):
    im, d = base("RISING")
    f = font(SERIF_B, 84)
    y = 330
    for line in wrap(d, data["headline"], f, 860):
        d.text((W / 2, y), line, font=f, fill=CREAM, anchor="mm")
        y += 100
    d.text((W / 2, y + 40), data["player"], font=fit(d, data["player"], SERIF_I, 80, 860), fill=VOLT, anchor="mm")
    d.text((W / 2, y + 120), (data.get("country") or "").upper(), font=font(SANS_B, 30), fill=MUTED, anchor="mm")
    by = 760
    rank_box(d, 130, by, 340, 250, "BEFORE", data["rank_before"], False)
    rank_box(d, W - 130 - 340, by, 340, 250, "NOW", data["rank_now"], True)
    cy = by + 125                                           # seta
    d.polygon([(500, cy - 14), (545, cy - 14), (545, cy - 34), (582, cy), (545, cy + 34), (545, cy + 14), (500, cy + 14)], fill=VOLT)
    d.text((W / 2, 1100), data["context"], font=fit(d, data["context"], SANS_R, 34, 860), fill=MUTED, anchor="mm")
    footer(d)
    im.save(out, quality=95)
    return out


# ---------- UPSET ----------
def render_upset(data, out):
    im, d = base("UPSET")
    f = font(SERIF_B, 84)
    y = 330
    for line in wrap(d, data["headline"], f, 860):
        d.text((W / 2, y), line, font=f, fill=CREAM, anchor="mm")
        y += 100
    top = 650
    for i, (key, win) in enumerate([("winner", True), ("loser", False)]):
        p = data[key]
        yy = top + i * 190
        d.rounded_rectangle([110, yy, W - 110, yy + 160], radius=34, fill=DEEP if not win else None,
                            outline=VOLT if win else CREAM, width=4 if win else 2)
        d.rounded_rectangle([140, yy + 38, 310, yy + 122], radius=42, fill=VOLT if win else None,
                            outline=None if win else MUTED, width=2)
        d.text((225, yy + 80), f"#{p['rank']}", font=font(SERIF_B, 54), fill=GREEN if win else MUTED, anchor="mm")
        d.text((345, yy + 80), p["name"], font=fit(d, p["name"], SERIF_B, 56, 650), fill=CREAM if win else MUTED, anchor="lm")
    d.text((W / 2, 1060), data["score"], font=font(SERIF_B, 64), fill=VOLT, anchor="mm")
    d.text((W / 2, 1130), data["context"], font=fit(d, data["context"], SANS_R, 34, 860), fill=MUTED, anchor="mm")
    footer(d)
    im.save(out, quality=95)
    return out


# ---------- exemplos FICTÍCIOS ----------
SAMPLE_RISING = {
    "headline": "Breaks into the top 100 for the first time.",
    "player": "Marco Ellison", "country": "ita",
    "rank_before": 112, "rank_now": 98,
    "context": "Up 14 places · first Challenger final of the season",
}
SAMPLE_UPSET = {
    "headline": "A 141-place gap, closed in three sets.",
    "winner": {"name": "Tomás Verhoeven", "rank": 187},
    "loser": {"name": "Luis Marandi", "rank": 46},
    "score": "6-4  3-6  7-5",
    "context": "Round of 16 · Sample Challenger Open",
}

if __name__ == "__main__":
    os.makedirs("news_samples", exist_ok=True)
    print("Gerado:", render_rising(SAMPLE_RISING, "news_samples/rising.png"))
    print("Gerado:", render_upset(SAMPLE_UPSET, "news_samples/upset.png"))
