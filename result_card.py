"""
Gera cartões de resultado de ténis (1080x1350, formato Instagram 4:5)
a partir da Live Tennis API.

Uso (PowerShell):
    py result_card.py                  # cartões de exemplo (sem API)
    $env:LIVETENNIS_KEY="a_tua_chave"  # define a chave só nesta janela
    py result_card.py --live           # jogos ao vivo reais
    py result_card.py --live --pt      # só jogos com jogadores portugueses
    py result_card.py --live --max 3   # no máximo 3 cartões
    py result_card.py --live --lang pt # cartões em português (default: inglês)
    py result_card.py --results        # cartões finais dos jogos acompanhados que já acabaram
    py result_card.py --page           # gera a pasta site/ (index.html + results.html)
    py result_card.py --page --player Borges   # results.html só com jogos de um jogador
    (RESULTS_RETENTION_DAYS define quantos dias se guardam resultados; por omissão 90)

Notícias (cartões RISING / UPSET) saem sozinhas de --live e --results; precisam do news_card.py na mesma pasta.
Fotos (opcional): põe imagens em photos/<id>.jpg ou photos/<nome-do-jogador>.jpg. Só usa fotos tuas ou com licença
(e, se pedir atribuição, regista-a em photos/credits.json: {"nome-do-jogador.jpg": "Foto: Autor / CC BY 4.0"}).
Com FETCH_PHOTOS=1, tenta obter fotos de licença livre (Wikimedia) através do fetch_photos.py.
Sem foto, o cartão usa um monograma com as iniciais.
Requisitos: py -m pip install pillow requests
Nota: a chave grátis permite ~100 pedidos/dia. Cada execução com --live usa 1.
"""
import argparse
import shutil
import html
import json
import os
import sys
import time
import unicodedata
import re
from PIL import Image, ImageDraw, ImageFont, ImageOps

API_BASE = "https://api.livetennisapi.com/api/public/v1"
BRAND = "@beyond100.tennis"

W, H = 1080, 1350
BG_TOP, BG_BOTTOM = (14, 59, 46), (6, 28, 22)
ACCENT = (212, 232, 80)
WHITE = (245, 245, 240)
MUTED = (150, 175, 165)
LINE = (40, 90, 75)
DARK = (6, 28, 22)

FONT_BOLD = [
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT_HEAD = [
    "C:/Windows/Fonts/seguibl.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT_REG = [
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

I18N = {
    "pt": {
        "live": "AO VIVO", "final": "RESULTADO FINAL", "cur": "GAME ATUAL",
        "winner": "VENCEDOR", "rank": "Ranking", "set": "SET",
        "surfaces": {"clay": "Terra batida", "hard": "Piso duro", "grass": "Relva", "carpet": "Carpete"},
        "rounds": {
            "1/64-finals": "Ronda de 128", "1/32-finals": "Ronda de 64",
            "1/16-finals": "Ronda de 32", "1/8-finals": "Oitavos de final",
            "1/4-finals": "Quartos de final", "semi-finals": "Meias-finais",
            "semifinals": "Meias-finais", "final": "Final",
        },
        "formats": {"BO3": "Melhor de 3 sets", "BO5": "Melhor de 5 sets"},
    },
    "en": {
        "live": "LIVE", "final": "FINAL RESULT", "cur": "CURRENT GAME",
        "winner": "WINNER", "rank": "Rank", "set": "SET",
        "surfaces": {"clay": "Clay", "hard": "Hard court", "grass": "Grass", "carpet": "Carpet"},
        "rounds": {
            "1/64-finals": "Round of 128", "1/32-finals": "Round of 64",
            "1/16-finals": "Round of 32", "1/8-finals": "Round of 16",
            "1/4-finals": "Quarterfinals", "semi-finals": "Semifinals",
            "semifinals": "Semifinals", "final": "Final",
        },
        "formats": {"BO3": "Best of 3 sets", "BO5": "Best of 5 sets"},
    },
}
T = I18N["en"]  # idioma ativo (definido por --lang)
LANG = "en"


# ---------- utilitários de desenho ----------
def font(paths, size):
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def gradient():
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        row = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = row
    return img


def fit_font(d, text, paths, size, max_w, min_size=28):
    f = font(paths, size)
    while d.textlength(text, font=f) > max_w and size > min_size:
        size -= 2
        f = font(paths, size)
    return f


def centered(d, y, text, paths, size, fill, max_w=W - 160):
    f = fit_font(d, text, paths, size, max_w)
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill)


def pill(d, y, text, filled):
    f = font(FONT_BOLD, 30)
    w = d.textlength(text, font=f)
    pad, h = 30, 58
    x0 = (W - w) / 2 - pad
    box = [x0, y, x0 + w + 2 * pad, y + h]
    if filled:
        d.rounded_rectangle(box, radius=h // 2, fill=ACCENT)
        d.text((x0 + pad, y + h / 2), text, font=f, fill=DARK, anchor="lm")
    else:
        d.rounded_rectangle(box, radius=h // 2, outline=MUTED, width=2)
        d.text((x0 + pad, y + h / 2), text, font=f, fill=MUTED, anchor="lm")


def pick_name(d, full, max_w, size=54):
    """Nome completo se couber; senão 'N. Apelido' (abreviado)."""
    parts = full.split()
    cands = [full]
    if len(parts) > 2:
        cands.append(f"{parts[0][0]}. {' '.join(parts[-2:])}")
    if len(parts) > 1:
        cands.append(f"{parts[0][0]}. {parts[-1]}")
    for c in cands:
        f = font(FONT_BOLD, size)
        if d.textlength(c, font=f) <= max_w:
            return c, f
    return cands[-1], fit_font(d, cands[-1], FONT_BOLD, size, max_w)


# ---------- tradução dos dados da API ----------
def round_pt(text):
    tail = (text or "").split(" - ")[-1].strip()
    return T["rounds"].get(tail.lower(), tail)


def is_live(m):
    return m.get("status") == "live"


def winner_index(m):
    s = (m.get("score") or {}).get("sets") or [0, 0]
    return 1 if s[0] > s[1] else 2 if s[1] > s[0] else 0


# ---------- cartão (identidade Beyond100: verde e creme) ----------
GREEN, DEEP, CREAM, VOLT = (14, 58, 45), (9, 40, 31), (247, 242, 230), (217, 242, 61)
SOFT, RED, TILE_EDGE = (176, 196, 183), (235, 64, 52), (88, 124, 108)
FONT_SERIF_B = [
    "C:/Windows/Fonts/georgiab.ttf", "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
]
FONT_SERIF_I = [
    "C:/Windows/Fonts/georgiai.ttf", "/System/Library/Fonts/Supplemental/Georgia Italic.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
]


def _tw(d, text, f, track=0):
    return sum(d.textlength(c, font=f) for c in text) + track * (len(text) - 1)


def spaced(d, cx, cy, text, f, fill, track):
    x = cx - _tw(d, text, f, track) / 2
    for c in text:
        d.text((x, cy), c, font=f, fill=fill, anchor="lm")
        x += d.textlength(c, font=f) + track


def _wrap(d, text, f, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur] if cur else lines


def pick_name2(d, full, max_w, size, paths):
    """Nome completo se couber; senão 'N. Apelido'; senão reduz a letra."""
    parts = full.split()
    cands = [full]
    if len(parts) > 2:
        cands.append(f"{parts[0][0]}. {' '.join(parts[-2:])}")
    if len(parts) > 1:
        cands.append(f"{parts[0][0]}. {parts[-1]}")
    for c in cands:
        f = font(paths, size)
        if d.textlength(c, font=f) <= max_w:
            return c, f
    return cands[-1], fit_font(d, cands[-1], paths, size, max_w)


PHOTO_DIR = os.environ.get("PHOTO_DIR", "photos")   # fotos TUAS ou com licença (ver notas no fim do ficheiro)
SURFACE_COL = {"clay": (201, 106, 60), "hard": (80, 130, 225), "grass": (120, 190, 90), "carpet": (170, 100, 150)}
COURT_LINE = (24, 76, 61)


def _slug(text):
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def find_photo(p):
    """photos/<id>.jpg ou photos/<nome-do-jogador>.jpg. Devolve (caminho, crédito) ou (None, None)."""
    def lookup():
        credits = _load_json(os.path.join(PHOTO_DIR, "credits.json"), {}) if os.path.isdir(PHOTO_DIR) else {}
        for key in (str(p.get("id")), _slug(p.get("name", ""))):
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                fp = os.path.join(PHOTO_DIR, key + ext)
                if key and os.path.exists(fp):
                    return fp, credits.get(key + ext)
        return None, None

    found = lookup()
    if found[0] is None and os.environ.get("FETCH_PHOTOS") == "1":   # só fotos com licença livre
        try:
            from fetch_photos import fetch_photo
            fetch_photo(p.get("name"), p.get("birthday"), PHOTO_DIR)
            found = lookup()
        except ImportError:
            pass
    return found


def court_watermark(d):
    """Campo visto de cima, quase invisível, como textura de fundo."""
    x0, x1, y0, y1 = 190, 890, 150, 1210
    sid, sv, mid = 70, 255, (150 + 1210) // 2
    d.rectangle([x0, y0, x1, y1], outline=COURT_LINE, width=4)
    for x in (x0 + sid, x1 - sid):
        d.line([(x, y0), (x, y1)], fill=COURT_LINE, width=4)
    d.line([(x0 - 20, mid), (x1 + 20, mid)], fill=COURT_LINE, width=6)
    for y in (mid - sv, mid + sv):
        d.line([(x0 + sid, y), (x1 - sid, y)], fill=COURT_LINE, width=4)
    d.line([(540, mid - sv), (540, mid + sv)], fill=COURT_LINE, width=4)


def avatar(img, cx, cy, r, p, ring, credits_out):
    """Foto (se existir em photos/) ou monograma com as iniciais."""
    d = ImageDraw.Draw(img)
    fp, credit = find_photo(p)
    if fp:
        ph = ImageOps.fit(Image.open(fp).convert("RGB"), (2 * r, 2 * r), centering=(0.5, 0.3))
        mask = Image.new("L", (2 * r, 2 * r), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=255)
        img.paste(ph, (cx - r, cy - r), mask)
        if credit:
            credits_out.append(credit)
    else:
        parts = (p.get("name") or "?").split()
        ini = (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else parts[0][:2].upper()
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=DEEP)
        d.text((cx, cy), ini, font=font(FONT_SERIF_B, int(r * 0.85)), fill=CREAM, anchor="mm")
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ring, width=5)


def render_card(m, out_path):
    """Texto importante fica dentro de x=120..960 (a grelha do Instagram corta as margens)."""
    img = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(img)
    d.rectangle([36, 36, W - 37, H - 37], outline=CREAM, width=3)
    d.rectangle([52, 52, W - 53, H - 53], outline=CREAM, width=1)
    court_watermark(d)
    credits_used = []
    live = is_live(m)
    score = m.get("score") or {}
    g1, g2 = (score.get("games") or [[], []])[:2]
    n = max(len(g1), len(g2), 1)
    sets = [(g1[i] if i < len(g1) else 0, g2[i] if i < len(g2) else 0) for i in range(n)]
    win = 0 if live else winner_index(m)

    # marca + estado
    spaced(d, W / 2, 125, "BEYOND100", font(FONT_SERIF_B, 40), CREAM, 10)
    label = T["live"] if live else T["final"]
    bf, track = font(FONT_BOLD, 30), 6
    tw = _tw(d, label, bf, track)
    bw = tw + (130 if live else 90)
    x0, y0 = W / 2 - bw / 2, 175
    if live:
        d.rounded_rectangle([x0, y0, x0 + bw, y0 + 62], radius=31, fill=VOLT)
        d.ellipse([x0 + 34, y0 + 21, x0 + 54, y0 + 41], fill=RED)
        spaced(d, x0 + 70 + tw / 2, y0 + 31, label, bf, GREEN, track)
    else:
        d.rounded_rectangle([x0, y0, x0 + bw, y0 + 62], radius=31, outline=CREAM, width=3)
        spaced(d, W / 2, y0 + 31, label, bf, CREAM, track)

    # torneio (até 2 linhas) e subtítulo
    tf = font(FONT_SERIF_B, 62)
    lines = _wrap(d, m.get("tournament", ""), tf, 800)
    if len(lines) > 2:
        tf = font(FONT_SERIF_B, 50)
        lines = _wrap(d, m.get("tournament", ""), tf, 800)[:2]
    y = 330 if len(lines) == 1 else 305
    for ln in lines:
        d.text((W / 2, y), ln, font=tf, fill=CREAM, anchor="mm")
        y += 74
    sub = " · ".join(x for x in [round_pt(m.get("round")), T["surfaces"].get(m.get("surface"), "")] if x)
    d.text((W / 2, y + 18), sub, font=fit_font(d, sub, FONT_SERIF_I, 38, 800), fill=SOFT, anchor="mm")

    # painel dos jogadores
    d.rounded_rectangle([120, 520, 960, 930], radius=38, fill=DEEP, outline=CREAM, width=2)
    d.line([(160, 725), (920, 725)], fill=TILE_EDGE, width=2)
    ts, gap = (92, 12) if n <= 3 else (72, 10)
    tiles_left = 920 - (n * ts + (n - 1) * gap)
    name_x = 262
    name_max = tiles_left - name_x - 24
    for i in range(2):
        p = m["players"]["p%d" % (i + 1)]
        yc = 622 + i * 206
        dim = win and win != i + 1
        name, nf = pick_name2(d, p.get("name", "?"), name_max, 50, FONT_SERIF_B)
        d.text((name_x, yc - 22), name, font=nf, fill=SOFT if dim else CREAM, anchor="lm")
        info = (p.get("country") or "").upper()
        if p.get("ranking"):
            info += f"  ·  {T['rank']} {p['ranking']}"
        inf = font(FONT_REG, 28)
        d.text((name_x, yc + 36), info, font=inf, fill=SOFT, anchor="lm")
        mv = p.get("ranking_movement")
        if p.get("ranking") and mv in ("up", "down"):        # seta a partir dos dados da API
            ax, ay = name_x + d.textlength(info, font=inf) + 22, yc + 36
            tri = [(ax - 9, ay + 7), (ax + 9, ay + 7), (ax, ay - 9)] if mv == "up" else [(ax - 9, ay - 7), (ax + 9, ay - 7), (ax, ay + 9)]
            d.polygon(tri, fill=VOLT if mv == "up" else RED)
        ring = VOLT if win == i + 1 else SURFACE_COL.get(m.get("surface"), SOFT)
        avatar(img, 190, yc, 52, p, ring, credits_used)
        if live and score.get("server") == i + 1:
            d.ellipse([222, yc - 58, 244, yc - 36], fill=VOLT, outline=GREEN, width=3)
        for j, st in enumerate(sets):
            mine, other = st[i], st[1 - i]
            bx = tiles_left + j * (ts + gap)
            box = [bx, yc - ts / 2, bx + ts, yc + ts / 2]
            if mine > other:
                d.rounded_rectangle(box, radius=22, fill=VOLT)
                col = GREEN
            else:
                d.rounded_rectangle(box, radius=22, outline=TILE_EDGE, width=2)
                col = SOFT
            d.text((bx + ts / 2, yc), str(mine), font=font(FONT_SERIF_B, int(ts * 0.55)), fill=col, anchor="mm")

    # bloco inferior
    pts = score.get("points") or []
    if live and len(pts) == 2:
        lab2, big = T["cur"], f"{pts[0]} – {pts[1]}"
    elif live:                                   # fonte sem pontos: mostra os jogos do set em curso
        lab2, big = f"{T['set']} {n}", f"{sets[-1][0]} – {sets[-1][1]}"
    else:
        lab2, big = T["winner"], None
    spaced(d, W / 2, 1000, lab2.upper(), font(FONT_BOLD, 26), SOFT, 6)
    if live:
        d.text((W / 2, 1085), big, font=font(FONT_SERIF_B, 112), fill=VOLT, anchor="mm")
    elif win:
        wn = m["players"]["p%d" % win].get("name", "")
        d.text((W / 2, 1085), wn, font=fit_font(d, wn, FONT_SERIF_I, 84, 800), fill=VOLT, anchor="mm")
    extra = " · ".join(x for x in [m.get("court"), T["formats"].get(m.get("format"), "")] if x)
    if extra:
        d.text((W / 2, 1160), extra, font=fit_font(d, extra, FONT_REG, 30, 800), fill=SOFT, anchor="mm")

    if credits_used:
        ct = " · ".join(dict.fromkeys(credits_used))
        d.text((W / 2, 1200), ct, font=fit_font(d, ct, FONT_REG, 22, 760), fill=SOFT, anchor="mm")

    # rodapé
    d.ellipse([W / 2 - 9, 1228, W / 2 + 9, 1246], fill=VOLT)
    d.text((W / 2, 1280), BRAND, font=font(FONT_BOLD, 34), fill=CREAM, anchor="mm")

    img.save(out_path, quality=95)
    return out_path


# ---------- dados ----------
def _headers():
    key = os.environ.get("LIVETENNIS_KEY")
    if not key:
        sys.exit('Falta a chave. No PowerShell: $env:LIVETENNIS_KEY="a_tua_chave"')
    return {"X-API-Key": key}


def fetch_live():
    import requests
    r = requests.get(f"{API_BASE}/matches", params={"status": "live"},
                     headers=_headers(), timeout=20)
    r.raise_for_status()
    return r.json().get("data", [])


def fetch_match(match_id):
    """Um jogo por id (inclui jogos terminados; grátis no plano FREE)."""
    import requests
    r = requests.get(f"{API_BASE}/matches/{match_id}", headers=_headers(), timeout=20)
    r.raise_for_status()
    return r.json()


# ---------- acompanhamento mínimo (só ids, para respeitar os termos de armazenamento) ----------
STATE_FILE = "tracked.json"
MIN_AGE_BEFORE_CHECK_S = int(os.environ.get("MIN_AGE_MIN") or "45") * 60   # execuções manuais podem baixar isto
MAX_TRACKED = int(os.environ.get("MAX_TRACKED") or "12")
TRACK_MAX_PRIO = int(os.environ.get("TRACK_MAX_PRIO") or "2")             # 1 = só Tour+Challenger gastam quota; 2 = também ITF
PRIO_FILE = "tracked_prio.json"                                          # id -> prioridade (0 Tour, 1 Challenger, 2 ITF, 3 resto)
TRACK_MAX_AGE_H = 48  # ids mais antigos são apagados


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load_prio():
    try:
        with open(PRIO_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_prio(prio):
    with open(PRIO_FILE, "w", encoding="utf-8") as f:
        json.dump(prio, f, indent=2)


def track(ids):
    state = load_state()
    now = time.time()
    for i in ids:
        state.setdefault(str(i), now)
    save_state(state)


# ---------- resultados guardados (só os campos que se mostram ao público) ----------
RESULTS_FILE = "results.json"
RETENTION_DAYS = int(os.environ.get("RESULTS_RETENTION_DAYS", "90"))


def load_results():
    try:
        with open(RESULTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def prune(results):
    cutoff = time.strftime("%Y-%m-%d", time.gmtime(time.time() - RETENTION_DAYS * 86400))
    return [r for r in results if r.get("date", "") >= cutoff]


def save_results(results):
    results = sorted(prune(results), key=lambda r: r.get("date", ""), reverse=True)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def slim(m):
    """Reduz um jogo da API aos campos públicos (nunca guardamos a resposta completa)."""
    sc = m.get("score") or {}
    games = sc.get("games") or [[], []]
    pl = m.get("players") or {}
    return {
        "id": m.get("id"),
        "date": (m.get("updated_at") or "")[:10] or time.strftime("%Y-%m-%d", time.gmtime()),
        "tournament": m.get("tournament", ""),
        "round": (m.get("round") or "").split(" - ")[-1].strip(),
        "surface": m.get("surface"),
        "p1": {"name": pl.get("p1", {}).get("name", "?"), "country": pl.get("p1", {}).get("country")},
        "p2": {"name": pl.get("p2", {}).get("name", "?"), "country": pl.get("p2", {}).get("country")},
        "games": [list(games[0]), list(games[1])],
        "winner": winner_index(m),
        "tour": m.get("tour"), "gender": m.get("gender"), "q": bool(m.get("is_qualifying")),
    }


def add_result(m):
    results = [r for r in load_results() if r.get("id") != m.get("id")]
    results.append(slim(m))
    save_results(results)


# ---------- site estático (verde e creme) ----------
IG_URL = "https://www.instagram.com/beyond100.tennis/"
PAGE_TEXT = {
    "en": {"title": "Latest results", "lead": "Challenger, ITF and the tour beyond the top 100.",
           "empty": "No results yet. Check back soon.", "nav": "Results", "home": "Home",
           "h1a": "Tennis beyond", "h1b": "the top 100.",
           "desc": "Live scores, clean result cards and the stories from the Challenger, ITF and WTA courts.",
           "follow": "Follow @beyond100.tennis", "all": "All results",
           "note": "Scores are provided for information only and may contain delays or errors.",
           "f_all": "All", "f_men": "Men", "f_women": "Women", "f_singles": "Singles", "f_doubles": "Doubles",
           "f_alltour": "All tournaments", "f_matches": "matches", "f_more": "Show more",
           "f_tournament": "Tournament", "f_player": "Search player", "f_highlights": "Highlights", "f_games": "of games",
           "f_champion": "Champion", "f_bracket": "Bracket", "f_tbd": "To be decided", "f_search_tour": "Search tournament", "f_tournaments": "All tournaments",
           "b_comeback": "Comeback", "b_bagel": "Bagel (6-0)", "b_breadstick": "Breadstick (6-1)",
           "b_super": "Super tie-break", "b_tb": "{n} tie-break", "b_closest": "Closest of the day"},
    "pt": {"title": "Últimos resultados", "lead": "Challenger, ITF e o circuito para lá do top 100.",
           "empty": "Ainda sem resultados. Volta em breve.", "nav": "Resultados", "home": "Início",
           "h1a": "Ténis para lá", "h1b": "do top 100.",
           "desc": "Resultados ao vivo, cartões limpos e as histórias dos campos de Challenger, ITF e WTA.",
           "follow": "Segue @beyond100.tennis", "all": "Todos os resultados",
           "note": "Os resultados são apenas informativos e podem conter atrasos ou erros.",
           "f_all": "Todos", "f_men": "Masculino", "f_women": "Feminino", "f_singles": "Singulares", "f_doubles": "Pares",
           "f_alltour": "Todos os torneios", "f_matches": "jogos", "f_more": "Mostrar mais",
           "f_tournament": "Torneio", "f_player": "Pesquisar jogador", "f_highlights": "Destaques", "f_games": "dos jogos",
           "f_champion": "Campeão", "f_bracket": "Quadro", "f_tbd": "Por apurar", "f_search_tour": "Pesquisar torneio", "f_tournaments": "Todos os torneios",
           "b_comeback": "Virada", "b_bagel": "Set a 0", "b_breadstick": "Set 6-1",
           "b_super": "Super tie-break", "b_tb": "{n} tie-break", "b_closest": "Mais disputado do dia"},
}

EMBLEM_SVG = """<svg viewBox="0 0 600 600" role="img" aria-label="Beyond100" class="emb">
<circle cx="300" cy="300" r="290" fill="#0e3a2d" stroke="#f7f2e6" stroke-width="8"/>
<circle cx="300" cy="300" r="170" fill="none" stroke="#f7f2e6" stroke-width="2"/>
<defs><path id="pt" d="M 100,300 A 200,200 0 0 1 500,300"/><path id="pb" d="M 68,300 A 232,232 0 0 0 532,300"/></defs>
<text font-family="Georgia,'Times New Roman',serif" font-weight="700" font-size="46" letter-spacing="8" fill="#f7f2e6" text-anchor="middle"><textPath href="#pt" startOffset="50%">BEYOND100</textPath></text>
<text font-family="Georgia,'Times New Roman',serif" font-weight="700" font-size="30" letter-spacing="5" fill="#f7f2e6" text-anchor="middle"><textPath href="#pb" startOffset="50%">TENNIS · CHALLENGER · ITF</textPath></text>
<circle cx="64" cy="300" r="10" fill="#d9f23d"/><circle cx="536" cy="300" r="10" fill="#d9f23d"/>
<text x="300" y="352" font-family="Georgia,'Times New Roman',serif" font-weight="700" font-size="150" fill="#f7f2e6" text-anchor="middle">100</text>
</svg>"""

import webapp
SITE_CSS_OLD = """
:root{--g:#0e3a2d;--deep:#09281f;--c:#f7f2e6;--v:#d9f23d;--s:#b0c4b7;--e:#2c5d4c}
*{box-sizing:border-box}
body{margin:0;background:var(--g);color:var(--c);font:16px/1.5 system-ui,"Segoe UI",Arial,sans-serif}
a{color:inherit}
.wrap{max-width:720px;margin:0 auto;padding:0 20px}
nav{display:flex;justify-content:space-between;align-items:center;padding:22px 0}
.brand{font:700 1.15rem Georgia,"Times New Roman",serif;letter-spacing:.22em;text-decoration:none}
nav div a{margin-left:18px;color:var(--s);text-decoration:none;font-size:.95rem}
nav div a:hover{color:var(--c)}
.hero{text-align:center;padding:24px 0 40px}
.emb{width:min(250px,64vw);height:auto}
h1{font:700 2.6rem/1.05 Georgia,"Times New Roman",serif;margin:24px 0 12px;letter-spacing:-.01em}
h1 em{color:var(--v);font-weight:400}
.hero p{color:var(--s);max-width:34ch;margin:0 auto 26px}
.btn{display:inline-block;background:var(--v);color:var(--g);font-weight:700;padding:13px 24px;border-radius:999px;text-decoration:none;margin:4px}
.btn.ghost{background:none;color:var(--c);border:2px solid var(--c)}
h2.sec{font:700 1.4rem Georgia,serif;margin:12px 0 14px;display:flex;justify-content:space-between;align-items:baseline}
h2.sec a{font:500 .9rem system-ui;color:var(--v)}
.page-h{padding:18px 0 10px}.page-h h1{font-size:2.1rem;margin:0 0 6px;text-align:left}
.page-h p{color:var(--s);margin:0}
article{background:var(--deep);border:1px solid var(--e);border-radius:22px;padding:16px 18px;margin:0 0 14px}
article h3{margin:0;font:700 .78rem system-ui;text-transform:uppercase;letter-spacing:.12em;color:var(--v)}
.m{color:var(--s);font-size:.85rem;margin:2px 0 8px}
.pl{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:8px 0;color:var(--s)}
.pl+.pl{border-top:1px solid var(--e)}
.pl.win{color:var(--c)}
.nm{display:block;font:700 1.1rem Georgia,serif}.pl small{color:var(--s)}
.ch{display:flex;gap:6px}
.ch b{min-width:38px;height:38px;border-radius:11px;border:1px solid var(--e);color:var(--s);display:grid;place-items:center;font:700 1.05rem Georgia,serif}
.ch b.on{background:var(--v);border-color:var(--v);color:var(--g)}
.empty{color:var(--s)}
footer{color:var(--s);font-size:.8rem;padding:28px 0 44px;border-top:1px solid var(--e);margin-top:28px}
"""


SITE_CSS = webapp.CSS


def _results_html(results, tr, empty):
    esc = html.escape
    rows = []
    for r in results:
        _, _, _, tag = webapp.classify(r)
        lines = []
        for i in (0, 1):
            p = r["p%d" % (i + 1)]
            chips = ""
            for a_, b_ in zip(r["games"][0], r["games"][1]):
                mine, other = (a_, b_) if i == 0 else (b_, a_)
                chips += f'<b class="{"on" if mine > other else ""}">{mine}</b>'
            cls = "win" if r["winner"] == i + 1 else ""
            lines.append(f'<div class="pl {cls}"><div><span class="nm">{esc(p["name"])}</span>'
                         f'<small>{esc((p.get("country") or "").upper())}</small></div>'
                         f'<div class="ch">{chips}</div></div>')
        meta = " · ".join(x for x in [r["date"], tr["rounds"].get(r["round"].lower(), r["round"]),
                                       tr["surfaces"].get(r.get("surface"), "")] if x)
        tagh = f'<span class="tag">{esc(tag)}</span>' if tag else ""
        rows.append(f'<section class="tg"><h3 class="th">{tagh}<span>{esc(webapp.base_tournament(r["tournament"]))}</span></h3>'
                    f'<div class="mt"><div class="mh">{esc(meta)}</div>{lines[0]}{lines[1]}</div></section>')
    return "\n".join(rows) or f'<p class="empty">{esc(empty)}</p>'


def _shell(title, body, tx, root=""):
    esc = html.escape
    return (f'<!doctype html>\n<html lang="{LANG}"><head><meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{esc(title)}</title>\n<meta name="theme-color" content="#0e3a2d">\n'
            f'<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">\n'
            f'<link rel="icon" href="{root}favicon.png" sizes="192x192" type="image/png">\n'
            f'<link rel="apple-touch-icon" href="{root}favicon.png">\n'
            f'<style>{SITE_CSS}</style></head><body><div class="wrap">\n'
            f'<nav><a class="brand" href="{root}index.html">BEYOND100</a><div>'
            f'<a href="{root}results.html">{esc(tx["nav"])}</a><a href="{root}players.html">{esc(tx.get("players", "Players"))}</a><a href="{IG_URL}">Instagram</a></div></nav>\n'
            f'{body}\n<footer>{esc(tx["note"])}</footer></div></body></html>')


FAVICON_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#0e3a2d"/>'
               '<circle cx="32" cy="32" r="25" fill="none" stroke="#f4efe0" stroke-width="3"/>'
               '<text x="32" y="40" text-anchor="middle" font-family="Georgia,serif" font-weight="700" font-size="22" fill="#d9f23a">100</text></svg>')


def write_favicons(out_dir):
    with open(os.path.join(out_dir, "favicon.svg"), "w", encoding="utf-8") as f:
        f.write(FAVICON_SVG)
    S = 192
    im = Image.new("RGB", (S, S), (14, 58, 45))
    d = ImageDraw.Draw(im)
    d.ellipse((14, 14, S - 14, S - 14), outline=(244, 239, 224), width=8)
    d.text((S / 2, S / 2 + 2), "100", font=font(FONT_SERIF_B, 62), fill=(217, 242, 58), anchor="mm")
    im.save(os.path.join(out_dir, "favicon.png"))


def build_site(out_dir="site", player=None):
    """Gera site/index.html e site/results.html (pasta pronta para o Cloudflare Pages)."""
    tx, tr = PAGE_TEXT[LANG], T
    esc = html.escape
    results = prune(load_results())
    results = sorted(results, key=lambda r: r.get("date", ""), reverse=True)
    if player:
        q = player.lower()
        results = [r for r in results if q in r["p1"]["name"].lower() or q in r["p2"]["name"].lower()]
    os.makedirs(out_dir, exist_ok=True)
    singles = [r for r in results if webapp.classify(r)[1] == "singles"]
    home = (f'<section class="hero">{EMBLEM_SVG}<h1>{esc(tx["h1a"])}<br><em>{esc(tx["h1b"])}</em></h1>'
            f'<p>{esc(tx["desc"])}</p><a class="btn" href="{IG_URL}">{esc(tx["follow"])}</a>'
            f'<a class="btn ghost" href="results.html">{esc(tx["title"])}</a></section>'
            f'<h2 class="sec"><span>{esc(tx["title"])}</span><a href="results.html">{esc(tx["all"])} →</a></h2>'
            f'{_results_html(singles[:4], tr, tx["empty"])}'
            f'{webapp.week_block(webapp.week_numbers(results), tx)}')
    page = webapp.results_page(results, tr, tx, LANG)
    paths = []
    write_favicons(out_dir)
    if os.path.isdir("posts"):                         # JPEGs dos posts (o Instagram vai buscá-los a este endereço)
        shutil.copytree("posts", os.path.join(out_dir, "posts"), dirs_exist_ok=True)
    for name, body, title in [("index.html", home, "Beyond100 · Tennis beyond the top 100"),
                              ("results.html", page, "Beyond100 · " + tx["title"]),
                              ("players.html", webapp.players_page(results, tx), "Beyond100 · " + tx.get("players", "Players"))]:
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(_shell(title, body, tx))
        paths.append(path)
    # uma página por torneio (singulares primeiro, pares depois)
    groups = {}
    for x in results:
        groups.setdefault(webapp.base_tournament(x.get("tournament", "")), []).append(x)
    tdir = os.path.join(out_dir, "t")
    os.makedirs(tdir, exist_ok=True)
    for name, rs in groups.items():
        body = webapp.tournament_page(name, rs, tr, tx)
        path = os.path.join(tdir, webapp.slugify(name) + ".html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(_shell(f"{name} · Beyond100", body, tx, root="../"))
        paths.append(path)
    return paths


# ---------- notícias a partir de dados reais (nada é inventado) ----------
RANKS_FILE = "ranks.json"
def _env(name, default):
    v = os.environ.get(name)
    return default if v is None or not v.strip() else v


PHOTO_BONUS = float(_env("PHOTO_BONUS", "2"))          # bónus se o vencedor tem foto licenciada
NO_PHOTO_EXTRA = float(_env("NO_PHOTO_EXTRA", "1"))   # sem foto, o limiar sobe
UPSET_GAP = int(os.environ.get("UPSET_GAP", "80"))
UPSET_MAX_LOSER_RANK = int(_env("UPSET_MAX_LOSER_RANK", "250"))   # o derrotado tem de ser top 250 para contar como surpresa
TOUR_MIN_RANK = int(_env("TOUR_MIN_RANK", "50"))                     # no Tour, o vencedor tem de estar fora do top N (ranking > N)
POST_LEVELS = {x.strip() for x in _env("POST_LEVELS", "challenger,tour").lower().split(",") if x.strip()}   # níveis que geram post: challenger,tour,itf
REQUIRE_PHOTO = _env("REQUIRE_PHOTO", "1") == "1"                      # só publica se o vencedor tiver foto licenciada
MIN_ITF_TIER = int(_env("MIN_ITF_TIER", "60"))                      # ITF só é publicado a partir de W60/M60 (M15/M25/W35... ficam só no site)   # diferença mínima de ranking para ser "surpresa"
RISING_MAX_JUMP = 150                                 # saltos maiores são tratados como erro nos dados
RANK_MAX_AGE_D = 60                                   # só compara com rankings vistos nos últimos 60 dias


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def update_ranks(m):
    """Guarda só (id, nome, país, ranking, data). Devolve eventos 'sobe para o top 100'."""
    ranks = _load_json(RANKS_FILE, {})
    now, today = time.time(), time.strftime("%Y-%m-%d", time.gmtime())
    events = []
    for k in ("p1", "p2"):
        p = (m.get("players") or {}).get(k) or {}
        pid, rank = p.get("id"), p.get("ranking")
        if pid is None or not isinstance(rank, int):
            continue
        prev = ranks.get(str(pid))
        if (prev and prev["rank"] > 100 and rank <= 100 and prev["rank"] - rank <= RISING_MAX_JUMP
                and now - prev["ts"] <= RANK_MAX_AGE_D * 86400):
            events.append({
                "headline": "Enters the top 100." if LANG == "en" else "Entra no top 100.",
                "player": p.get("name", ""), "country": p.get("country"),
                "rank_before": prev["rank"], "rank_now": rank,
                "context": (f"Up {prev['rank'] - rank} places since {prev['date']}" if LANG == "en"
                            else f"Sobe {prev['rank'] - rank} lugares desde {prev['date']}"),
            })
        ranks[str(pid)] = {"name": p.get("name"), "country": p.get("country"), "rank": rank,
                           "date": today, "ts": now}
    ranks = {k: v for k, v in ranks.items() if now - v["ts"] <= RETENTION_DAYS * 86400}
    with open(RANKS_FILE, "w", encoding="utf-8") as f:
        json.dump(ranks, f, ensure_ascii=False, indent=2)
    return events


def upset_event(m):
    """Surpresa: o vencedor tem ranking pelo menos UPSET_GAP lugares pior que o derrotado."""
    w = winner_index(m)
    sets = (m.get("score") or {}).get("sets") or [0, 0]
    if not w or max(sets) < 2:          # ignora desistências e walkovers
        return None
    pw, pl = m["players"]["p%d" % w], m["players"]["p%d" % (3 - w)]
    rw, rl = pw.get("ranking"), pl.get("ranking")
    if not (isinstance(rw, int) and isinstance(rl, int)) or rw - rl < UPSET_GAP or rl > UPSET_MAX_LOSER_RANK:
        return None
    games = (m.get("score") or {}).get("games") or [[], []]
    mine, other = games[w - 1], games[2 - w]
    gap = rw - rl
    return {
        "headline": (f"Beats a player ranked {gap} places higher." if LANG == "en"
                     else f"Vence um jogador {gap} lugares acima no ranking."),
        "winner": {"name": pw.get("name", ""), "rank": rw},
        "loser": {"name": pl.get("name", ""), "rank": rl},
        "score": "  ".join(f"{a}-{b}" for a, b in zip(mine, other)),
        "context": " · ".join(x for x in [round_pt(m.get("round")), m.get("tournament", "")] if x),
    }


POSTS_FILE = "posts.json"
POST_MIN_SCORE = float(_env("POST_MIN_SCORE", "4"))
MAX_POSTS_PER_DAY = int(_env("MAX_POSTS_PER_DAY", "3"))


def interest(m):
    """Pontuação de interesse de um jogo terminado (só para escolher o que vale a pena publicar)."""
    import webapp
    sets = (m.get("score") or {}).get("sets") or [0, 0]
    w = winner_index(m)
    if not w or max(sets) < 2:                      # walkover / desistência: não publicar
        return 0.0, []
    score, why = 0.0, []
    if m.get("is_qualifying"):                       # qualificação: só no site
        return 0.0, []
    lv = int(_priority(m))                          # a parte decimal é só desempate
    score += {0: 3, 1: 2, 2: 0.5, 3: 0}[lv]
    if lv <= 1:
        why.append({0: "tour", 1: "challenger"}[lv])
    rr = webapp._round_rank(m.get("round"))
    if rr in (0, 1, 2):
        score += {0: 3, 1: 2, 2: 1}[rr]
        why.append({0: "final", 1: "semifinal", 2: "quarterfinal"}[rr])
    ev = upset_event(m)
    if ev:
        score += 3
        why.append("upset")
    ranks = [(m["players"][k].get("ranking")) for k in ("p1", "p2")]
    best = min([r for r in ranks if isinstance(r, int)] or [9999])
    if best <= 100:
        score += 2
        why.append("top100")
        if best <= 50:
            score += 1
    elif best <= 150:                                # zona 100-150: perto do top 100, mais provável ter foto
        score += 1
    g = (m.get("score") or {}).get("games") or [[], []]
    if g[0] and len(g[0]) == len(g[1]):
        mine, other = (g[0], g[1]) if w == 1 else (g[1], g[0])
        if len(mine) >= 3 and mine[0] < other[0] and sum(a > b for a, b in zip(mine, other)) > sum(a < b for a, b in zip(mine, other)):
            score += 1
            why.append("comeback")
    return score, why


def _who(p):
    fp, credit = find_photo(p)
    return {"name": p.get("name", ""), "rank": p.get("ranking"), "photo": fp, "credit": credit}


def _headline(why, ev):
    """Frase curta para o cartão, só a partir de factos verificados (sem inventar)."""
    if ev:
        return ev["headline"]
    if "final" in why:
        return "Wins the title." if LANG == "en" else "Vence o torneio."
    if "comeback" in why:
        return "Down a set, wins in three." if LANG == "en" else "Perdeu o 1.º set e vira."
    if "semifinal" in why:
        return "Into the final." if LANG == "en" else "Está na final."
    if "quarterfinal" in why:
        return "Into the semifinals." if LANG == "en" else "Está nas meias-finais."
    return ""


def maybe_post(m, out_dir):
    """Se o jogo for suficientemente interessante (e não houver já posts a mais hoje), gera o cartão com foto."""
    from photo_cards import render_match_photo
    from captions import save_caption
    import webapp
    import re as _re
    _g, _k, _lv, _tag = webapp.classify(webapp.api_view(m))
    if _lv not in POST_LEVELS:
        print(f"Jogo {m.get('id')}: nível '{_lv}' não gera posts (POST_LEVELS={','.join(sorted(POST_LEVELS))}), fica só no site.")
        return None
    if _lv == "tour":
        _w0 = winner_index(m)
        _rk = ((m.get("players") or {}).get("p%d" % _w0) or {}).get("ranking") if _w0 else None
        if isinstance(_rk, int) and _rk <= TOUR_MIN_RANK:
            print(f"Jogo {m.get('id')}: Tour, vencedor ranking {_rk} (<= {TOUR_MIN_RANK}), fica só no site.")
            return None
    if _lv == "itf":
        _n = _re.search(r"(\d+)", _tag or "")
        if not _n or int(_n.group(1)) < MIN_ITF_TIER:
            print(f"Jogo {m.get('id')}: {_tag or 'ITF'} abaixo de {MIN_ITF_TIER}, fica só no site.")
            return None
    score, why = interest(m)
    # prioridade a jogos COM imagem: com foto licenciada ganha bónus; sem foto precisa de mais interesse
    _w = winner_index(m)
    has_photo = bool(_w and find_photo(m["players"]["p%d" % _w])[0])
    score += PHOTO_BONUS if has_photo else 0
    if REQUIRE_PHOTO and not has_photo:
        print(f"Jogo {m.get('id')}: sem foto licenciada do vencedor, fica só no site.")
        return None
    need = POST_MIN_SCORE + (0 if has_photo else NO_PHOTO_EXTRA)
    if score < need:
        print(f"Jogo {m.get('id')}: interesse {score:g} (< {need:g}{'' if has_photo else ', sem foto'}), fica só no site.")
        return None
    today = time.strftime("%Y-%m-%d", time.gmtime())
    posts = _load_json(POSTS_FILE, {})
    if len(posts.get(today, [])) >= MAX_POSTS_PER_DAY:
        print(f"Jogo {m.get('id')}: interesse {score:g}, mas já há {MAX_POSTS_PER_DAY} posts hoje.")
        return None
    w = winner_index(m)
    pw, pl = m["players"]["p%d" % w], m["players"]["p%d" % (3 - w)]
    g = (m.get("score") or {}).get("games") or [[], []]
    sets = list(zip(g[w - 1], g[2 - w]))
    ev = upset_event(m)
    _, _, _, tag = webapp.classify(webapp.api_view(m))
    d = {"winner": _who(pw), "loser": _who(pl), "sets": sets,
         "tournament": m.get("tournament", ""), "round": round_pt(m.get("round")),
         "level": tag.upper(), "tag": "UPSET" if ev else "", "headline": _headline(why, ev)}
    pdir = os.path.join(out_dir, "post")
    os.makedirs(pdir, exist_ok=True)
    png = render_match_photo(d, os.path.join(pdir, f"final-{m.get('id')}.png"))
    _facts = dict(slim(m), reasons=why)
    _rw, _rl = pw.get("ranking"), pl.get("ranking")
    if isinstance(_rw, int):
        _facts["rank_winner"] = _rw
    if isinstance(_rl, int):
        _facts["rank_loser"] = _rl
    if isinstance(_rw, int) and isinstance(_rl, int) and _rw > _rl:
        _facts["ranking_gap"] = _rw - _rl
    save_caption(png, "final", _facts)
    posts.setdefault(today, []).append({"id": m.get("id"), "score": score, "reasons": why, "file": os.path.basename(png)})
    keep = sorted(posts)[-14:]
    posts = {k: posts[k] for k in keep}
    with open(POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    print(f"Post: {png} (interesse {score:g}: {', '.join(why)})")
    return png


def rising_cards(m, out_dir):
    """Notícia 'entra no top 100' (foto + número do ranking). Vai para out/post/."""
    from photo_cards import render_rank_news
    from captions import save_caption
    import webapp
    events = update_ranks(m)
    if not events:
        return []
    pdir = os.path.join(out_dir, "post")
    os.makedirs(pdir, exist_ok=True)
    paths = []
    for i, e in enumerate(events):
        pl = next((((m.get("players") or {}).get(k) or {}) for k in ("p1", "p2")
                   if ((m.get("players") or {}).get(k) or {}).get("name") == e["player"]), {"name": e["player"]})
        fp, credit = find_photo(pl)
        if REQUIRE_PHOTO and not fp:
            print(f"Notícia de ranking de {e['player']}: sem foto licenciada, não é publicada.")
            continue
        women = webapp.classify(webapp.api_view(m))[0] == "women"
        d = {"player": e["player"], "rank_now": e["rank_now"], "rank_before": e["rank_before"],
             "system": "WTA" if women else "ATP", "headline": e["headline"].rstrip("."),
             "context": e["context"], "photo": fp, "credit": credit}
        png = render_rank_news(d, os.path.join(pdir, f"news-rising-{m.get('id')}-{i}.png"))
        save_caption(png, "rising", e)
        paths.append(png)
    return paths


def upset_cards(m, out_dir):
    return []          # as surpresas agora são um jogo importante (ver maybe_post), com a etiqueta UPSET


def run_results(out_dir, max_checks):
    import requests
    now = time.time()
    state = {k: t for k, t in load_state().items() if now - t < TRACK_MAX_AGE_H * 3600}
    if not state:
        save_state(state)
        print("Sem jogos em acompanhamento. Corre primeiro com --live.")
        return
    os.makedirs(out_dir, exist_ok=True)
    checks = 0
    try:
        prio = load_prio()
        for mid in sorted(state, key=lambda k: (prio.get(k, 3), state[k])):     # Tour e Challenger primeiro
            if now - state[mid] < MIN_AGE_BEFORE_CHECK_S:
                continue                      # jogo acompanhado há pouco: é improvável que já tenha acabado
            if checks >= max_checks:
                print(f"Limite de {max_checks} consultas atingido (poupa a quota diária).")
                break
            checks += 1
            try:
                m = fetch_match(mid)
            except requests.exceptions.HTTPError as e:
                code = e.response.status_code if e.response is not None else None
                if code in (404, 410):        # jogo removido/cancelado na API: deixa de ser acompanhado
                    print(f"Jogo {mid}: já não existe na API ({code}), removido do acompanhamento.")
                    del state[mid]
                    continue
                if code == 429:               # quota esgotada: pára e guarda o que já se sabe
                    print("Quota da API esgotada (429): a parar por agora.")
                    break
                print(f"Jogo {mid}: erro {code} da API, fica para a próxima.")
                state[mid] = state.pop(mid)
                continue
            except requests.exceptions.RequestException as e:
                print(f"Jogo {mid}: erro de rede ({type(e).__name__}), fica para a próxima.")
                state[mid] = state.pop(mid)
                continue
            if m.get("status") == "completed":
                add_result(m)                 # vai sempre para o site
                maybe_post(m, out_dir)        # só os mais interessantes geram cartão para o Instagram
                del state[mid]
            else:
                print(f"Jogo {mid}: ainda não terminou (estado: {m.get('status')}).")
                state[mid] = state.pop(mid)   # vai para o fim da fila: os outros jogos também são verificados
    finally:
        save_state(state)                     # mesmo com erro inesperado, o progresso não se perde
        save_prio({k: v for k, v in prio.items() if k in state})


def is_doubles_match(m):
    """Pares (a quota gratuita é pequena: só acompanhamos singulares)."""
    names = [((m.get("players") or {}).get(k) or {}).get("name", "") for k in ("p1", "p2")]
    return "DOUBLES" in (m.get("tournament") or "").upper() or any(" / " in n for n in names)


def _priority(m):
    """Menor = mais importante: Tour, Challenger, ITF; depois o resto. Qualificação vale menos."""
    import webapp
    _, _, level, _ = webapp.classify(webapp.api_view(m))
    # desempate: jogos com jogadores mais bem ranqueados primeiro (mais fotos livres, mais interesse)
    ranks = [((m.get("players") or {}).get(k) or {}).get("ranking") for k in ("p1", "p2")]
    best = min([r for r in ranks if isinstance(r, int)] or [900])
    return webapp.LEVEL_ORDER.get(level, 3) + (0.5 if m.get("is_qualifying") else 0) + min(best, 900) / 10000


def has_portuguese(m):
    return any((m["players"][k].get("country") or "").lower() == "por" for k in ("p1", "p2"))


# Exemplos com a estrutura real da API (o segundo tem resultado inventado, só para testar)
SAMPLES = [
    {
        "id": "sample-live", "status": "live", "tournament": "W15 Campina Grande (Brazil)",
        "round": "W15 Campina Grande - 1/8-finals", "surface": "clay", "court": "Court 3", "format": "BO3",
        "players": {
            "p1": {"name": "Arias Valentina Mediorreal", "country": "col", "ranking": 850},
            "p2": {"name": "Julia Camargo Silva Konishi", "country": "bra", "ranking": 663},
        },
        "score": {"games": [[5, 7, 4], [7, 6, 1]], "sets": [1, 1], "points": ["40", "30"], "server": 2},
    },
    {
        "id": "sample-final", "status": "completed", "tournament": "Estoril Open",
        "round": "Estoril Open - Semi-finals", "surface": "clay", "court": "Court Central", "format": "BO3",
        "players": {
            "p1": {"name": "Nuno Borges", "country": "por", "ranking": 40},
            "p2": {"name": "Jaume Munar", "country": "esp", "ranking": 60},
        },
        "score": {"games": [[6, 3, 7], [4, 6, 5]], "sets": [2, 1]},
    },
]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="usar jogos ao vivo da API")
    ap.add_argument("--pt", action="store_true", help="só jogos com jogadores portugueses")
    ap.add_argument("--max", type=int, default=5, help="máximo de cartões (ou de jogos novos a acompanhar com --track-only)")
    ap.add_argument("--track-only", action="store_true", help="com --live: só acompanha jogos (não gera cartões de jogos a decorrer)")
    ap.add_argument("--out", default="cards", help="pasta de saída")
    ap.add_argument("--results", action="store_true", help="gerar cartões finais dos jogos acompanhados")
    ap.add_argument("--max-checks", type=int, default=10, help="máx. de consultas em --results")
    ap.add_argument("--page", action="store_true", help="gerar a pasta site/ (index.html + results.html)")
    ap.add_argument("--player", help="com --page: filtrar por nome de jogador")
    ap.add_argument("--lang", choices=["en", "pt"], default="en", help="idioma dos cartões")
    a = ap.parse_args()
    T = I18N[a.lang]
    LANG = a.lang

    if a.page:
        paths = build_site("site", a.player)
        print(f"Gerado: {len(paths)} páginas em site/")
        sys.exit(0)

    if a.results:
        run_results(a.out, a.max_checks)
        sys.exit(0)

    try:
        matches = fetch_live() if a.live else SAMPLES
    except Exception as e:
        print(f"Não consegui obter jogos ao vivo ({e}); salto este passo.")
        sys.exit(0)
    if a.live:
        matches = sorted([m for m in matches if not is_doubles_match(m)], key=_priority)
    all_matches = matches
    if a.pt:
        matches = [m for m in matches if has_portuguese(m)]
    if not matches:
        if a.live:
            print("Sem jogos de singulares ao vivo neste momento.")
            sys.exit(0)
        sys.exit("Nenhum jogo encontrado com estes filtros.")

    os.makedirs(a.out, exist_ok=True)
    shown = matches[: a.max]
    for m in ([] if a.track_only else shown):
        print("Gerado:", render_card(m, os.path.join(a.out, f"{m['id']}.png")))
    if a.live:
        for m in all_matches:
            for pth in rising_cards(m, a.out):
                print("Notícia:", pth)
        if a.track_only:
            state = load_state()
            prio = load_prio()
            added = 0
            for m in [m for m in matches if is_live(m) and str(m["id"]) not in state]:
                if added >= a.max:
                    break
                mp = int(_priority(m))
                if mp > TRACK_MAX_PRIO:
                    continue
                if len(state) >= MAX_TRACKED:
                    # lista cheia: um jogo de Tour/Challenger tira o lugar ao de menor prioridade (ITF/resto)
                    victims = [k for k in state if prio.get(k, 3) > max(mp, 1)]
                    if mp > 1 or not victims:
                        continue
                    victim = max(victims, key=lambda k: (prio.get(k, 3), -state[k]))
                    del state[victim]
                    prio.pop(victim, None)
                state[str(m["id"])] = time.time()
                prio[str(m["id"])] = mp
                added += 1
            save_state(state)
            save_prio({k: v for k, v in prio.items() if k in state})
            print(f"Acompanhados: {len(state)} (+{added} novos, máx. {MAX_TRACKED}).")
        else:
            track([m["id"] for m in shown if is_live(m)])
