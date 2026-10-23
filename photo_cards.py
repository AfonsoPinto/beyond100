"""Cartões com foto da Beyond100 (1080x1350), desenho próprio em verde e creme.

  render_match_photo(d, out)  -> jogo importante: foto a toda a largura + painel de resultado em baixo
  render_rank_news(d, out)    -> notícia de ranking: foto em painel + número do ranking + subida

Sem foto (a maioria dos jogadores de Challenger/ITF não tem licença livre), usa-se um monograma grande.
A foto é sempre passada por quem chama (já com licença verificada); aqui nada é descarregado.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 1080, 1350
GREEN, DEEP, CREAM, VOLT = (14, 58, 45), (9, 40, 31), (247, 242, 230), (217, 242, 61)
SOFT, EDGE, LINE = (176, 196, 183), (44, 93, 76), (24, 78, 61)
BRAND = "@beyond100.tennis"

SERIF_B = ["C:/Windows/Fonts/georgiab.ttf", "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
           "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"]
SERIF_I = ["C:/Windows/Fonts/georgiai.ttf", "/System/Library/Fonts/Supplemental/Georgia Italic.ttf",
           "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"]
SANS_B = ["C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
          "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def font(paths, size):
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def fit(d, text, paths, size, max_w, min_size=24):
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


def initials(name):
    parts = (name or "?").split()
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else parts[0][:2].upper()


def _court(img, alpha_line=LINE):
    d = ImageDraw.Draw(img)
    x0, x1, y0, y1 = 170, 910, 120, 1240
    mid = (y0 + y1) // 2
    d.rectangle([x0, y0, x1, y1], outline=alpha_line, width=4)
    for x in (x0 + 74, x1 - 74):
        d.line([(x, y0), (x, y1)], fill=alpha_line, width=4)
    d.line([(x0 - 20, mid), (x1 + 20, mid)], fill=alpha_line, width=6)
    for y in (mid - 270, mid + 270):
        d.line([(x0 + 74, y), (x1 - 74, y)], fill=alpha_line, width=4)
    d.line([(540, mid - 270), (540, mid + 270)], fill=alpha_line, width=4)


def _gradient(top=(17, 66, 51), bottom=(8, 34, 26)):
    g = Image.new("RGB", (W, H))
    px = g.load()
    for y in range(H):
        t = y / (H - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = c
    return g


def _overlay(img, y0, y1, a0, a1):
    """Escurece uma faixa vertical (de a0 a a1 de opacidade preta) para o texto ler bem sobre a foto."""
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for y in range(y0, y1):
        a = int(a0 + (a1 - a0) * (y - y0) / max(1, y1 - y0))
        od.line([(0, y), (img.width, y)], fill=(5, 22, 17, a))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def _header(img, y=78):
    d = ImageDraw.Draw(img)
    f = font(SERIF_B, 34)
    text = "BEYOND100"
    tw = sum(d.textlength(c, font=f) for c in text) + 10 * (len(text) - 1)
    d.rounded_rectangle([W / 2 - tw / 2 - 34, y - 36, W / 2 + tw / 2 + 34, y + 36], radius=36, fill=CREAM)
    spaced(d, W / 2, y, text, f, GREEN, 10)


def _footer(img, credit=None):
    d = ImageDraw.Draw(img)
    d.text((W / 2, 1306), BRAND, font=font(SANS_B, 30), fill=CREAM, anchor="mm")
    if credit:
        d.text((40, 1334), credit[:90], font=font(SANS_B, 18), fill=SOFT, anchor="lm")


def _photo_or_monogram(size, who, centering=(0.5, 0.22)):
    """Imagem do jogador do tamanho pedido: foto licenciada ou monograma sobre fundo escuro."""
    w, h = size
    if who.get("photo") and os.path.exists(who["photo"]):
        return ImageOps.fit(Image.open(who["photo"]).convert("RGB"), size, centering=centering), True
    im = _gradient((19, 72, 56), (8, 34, 26)).resize((max(w, 1), max(h, 1)))
    d = ImageDraw.Draw(im)
    d.text((w / 2, h * 0.46), initials(who.get("name")), font=font(SERIF_B, int(min(w, h) * 0.5)), fill=(30, 92, 73), anchor="mm")
    return im, False


# ------------------------------------------------------------------ jogo importante
def render_match_photo(d, out_path):
    """d = {winner:{name,country,rank,photo,credit}, loser:{name,rank}, sets:[(w,l),...] do ponto de vista do vencedor,
            tournament, round, level (ex. 'CHALLENGER'), tag (ex. 'UPSET'), headline}"""
    win, los = d["winner"], d["loser"]
    img, has_photo = _photo_or_monogram((W, H), win, centering=(0.5, 0.2))
    if has_photo:
        img = _overlay(img, 0, 330, 120, 0)
        img = _overlay(img, 640, H, 0, 215)
    else:
        _court(img)
    img = img.convert("RGB")
    _header(img)
    dr = ImageDraw.Draw(img)

    # etiquetas (nível e, se houver, UPSET)
    x = 70
    for label, fill, fg in [(d.get("level"), VOLT, GREEN), (d.get("tag"), RED_TAG, CREAM)]:
        if label:
            f = font(SANS_B, 26)
            tw = dr.textlength(label, font=f) + 36
            dr.rounded_rectangle([x, 150, x + tw, 196], radius=23, fill=fill)
            dr.text((x + tw / 2, 173), label, font=f, fill=fg, anchor="mm")
            x += tw + 12

    # painel de resultado
    px0, px1, py0, py1 = 70, 1010, 905, 1155
    dr.rounded_rectangle([px0, py0, px1, py1], radius=30, fill=CREAM)
    sets = d["sets"]
    tile, gap = 78, 10
    tiles_w = len(sets) * tile + (len(sets) - 1) * gap
    name_w = (px1 - px0) - 80 - tiles_w - 20
    rows = [(win, [s[0] for s in sets], [s[1] for s in sets], True), (los, [s[1] for s in sets], [s[0] for s in sets], False)]
    for i, (p, mine, other, is_w) in enumerate(rows):
        cy = py0 + 62 + i * 126
        nm = (p.get("name") or "").upper()
        f = fit(dr, nm, SERIF_B, 50 if is_w else 44, name_w, 26)
        dr.text((px0 + 40, cy), nm, font=f, fill=GREEN if is_w else (96, 120, 108), anchor="lm")
        tx0 = px1 - 40 - tiles_w
        for j, (a, b) in enumerate(zip(mine, other)):
            x0 = tx0 + j * (tile + gap)
            won = a > b
            if is_w and won:
                dr.rounded_rectangle([x0, cy - tile / 2, x0 + tile, cy + tile / 2], radius=18, fill=GREEN)
                dr.text((x0 + tile / 2, cy), str(a), font=font(SERIF_B, 44), fill=VOLT, anchor="mm")
            else:
                dr.rounded_rectangle([x0, cy - tile / 2, x0 + tile, cy + tile / 2], radius=18, outline=(190, 200, 192), width=3)
                dr.text((x0 + tile / 2, cy), str(a), font=font(SERIF_B, 44), fill=GREEN if is_w else (120, 140, 128), anchor="mm")
        if i == 0:
            for xx in range(px0 + 40, px1 - 40, 14):
                dr.line([(xx, py0 + 125), (xx + 5, py0 + 125)], fill=(160, 176, 166), width=2)

    sub = " · ".join(x for x in [d.get("tournament"), d.get("round")] if x).upper()
    dr.text((W / 2, 1200), sub, font=fit(dr, sub, SANS_B, 30, 920, 20), fill=VOLT, anchor="mm")
    if d.get("headline"):
        dr.text((W / 2, 1246), d["headline"], font=fit(dr, d["headline"], SERIF_I, 36, 920, 24), fill=CREAM, anchor="mm")
    _footer(img, win.get("credit"))
    img.save(out_path, quality=95)
    return out_path


RED_TAG = (196, 52, 40)


# ------------------------------------------------------------------ notícia de ranking
def render_rank_news(d, out_path):
    """d = {player, country, rank_now, rank_before, system ('ATP'/'WTA'/''), headline, context, photo, credit}"""
    img = _gradient()
    _court(img)
    _header(img)
    dr = ImageDraw.Draw(img)

    # painel da foto (à esquerda)
    x0, y0, x1, y1 = 60, 190, 640, 1190
    ph, has_photo = _photo_or_monogram((x1 - x0, y1 - y0), {"name": d["player"], "photo": d.get("photo")})
    mask = Image.new("L", ph.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, ph.width - 1, ph.height - 1], radius=40, fill=255)
    img.paste(ph, (x0, y0), mask)
    dr.rounded_rectangle([x0, y0, x1, y1], radius=40, outline=CREAM, width=4)

    # coluna da direita
    cx = (660 + 1030) / 2
    label = f"{d.get('system', '')} RANKING".strip()
    spaced(dr, cx, 262, label, font(SANS_B, 28), SOFT, 6)
    parts = (d["player"] or "").upper().split()
    first, last = " ".join(parts[:-1]), parts[-1] if parts else ""
    if first:
        dr.text((cx, 360), first, font=fit(dr, first, SERIF_B, 46, 360, 26), fill=CREAM, anchor="mm")
    dr.text((cx, 428), last, font=fit(dr, last, SERIF_B, 78, 360, 34), fill=CREAM, anchor="mm")
    num = str(d["rank_now"])
    dr.text((cx, 640), num, font=fit(dr, num, SERIF_B, 250, 370, 120), fill=VOLT, anchor="mm")

    # selo de subida (círculo sobre a borda da foto)
    delta = (d.get("rank_before") or 0) - d["rank_now"]
    bx, by, r = x1, 960, 84
    dr.ellipse([bx - r, by - r, bx + r, by + r], fill=DEEP, outline=CREAM, width=5)
    if delta > 0:
        dr.polygon([(bx, by - 52), (bx - 22, by - 24), (bx + 22, by - 24)], fill=VOLT)
        dr.text((bx, by + 18), f"+{delta}", font=font(SANS_B, 52), fill=CREAM, anchor="mm")

    head = d.get("headline") or ""
    if head:
        f = fit(dr, head.upper(), SANS_B, 30, 380, 20)
        dr.text((cx, 800), head.upper(), font=f, fill=CREAM, anchor="mm")
    if d.get("context"):
        dr.text((cx, 850), d["context"], font=fit(dr, d["context"], SERIF_I, 30, 380, 20), fill=SOFT, anchor="mm")
    _footer(img, d.get("credit"))
    img.save(out_path, quality=95)
    return out_path
