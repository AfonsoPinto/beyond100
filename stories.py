"""Stories automáticos (1080x1920): campeão da final e resultados do dia. Prioridade a imagens.

  python stories.py out          -> gera os stories em falta (hora UTC >= STORY_HOUR; 1 resumo por dia + 1 por final)
  python stories.py out --force  -> gera já (teste)

Usa só results.json (dados públicos) e fotos com licença livre/tuas em photos/. Fila: stories.json.
O publisher.py envia-os (se PUBLISH_AUTO=1 e MAKE_WEBHOOK_STORY_URL definido).
"""
import json
import os
import sys
import time

from PIL import Image, ImageDraw, ImageOps

import photo_cards as pc
import webapp
from fetch_photos import slug

RESULTS_FILE, STORIES_FILE, PHOTO_DIR = "results.json", "stories.json", os.environ.get("PHOTO_DIR", "photos")
STORY_HOUR = int(os.environ.get("STORY_HOUR", "20"))       # hora UTC a partir da qual sai o resumo do dia
MIN_RESULTS = int(os.environ.get("STORY_MIN_RESULTS", "3"))
MAX_FINALS = 2
W, H = 1080, 1920
GREEN, CREAM, VOLT, SOFT, DEEP, EDGE = pc.GREEN, pc.CREAM, pc.VOLT, pc.SOFT, pc.DEEP, pc.EDGE
SERIF_B, SERIF_I, SANS_B = pc.SERIF_B, pc.SERIF_I, pc.SANS_B


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def photo_of(name):
    fp, cr = _photo_of(name)
    if fp is None and os.environ.get("FETCH_PHOTOS") == "1":          # só licença livre; falhas ficam em cache
        try:
            from fetch_photos import fetch_photo
            fetch_photo(name, None, PHOTO_DIR)
            fp, cr = _photo_of(name)
        except Exception as e:
            print("Foto:", type(e).__name__)
    return fp, cr


def _photo_of(name):
    cr = _load(os.path.join(PHOTO_DIR, "credits.json"), {})
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        fp = os.path.join(PHOTO_DIR, slug(name) + ext)
        if os.path.exists(fp):
            return fp, cr.get(slug(name) + ext)
    return None, None


def _bg():
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    top, bot = (17, 66, 51), (8, 34, 26)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return im


def _logo(img, y=130):
    d = ImageDraw.Draw(img)
    f = pc.font(SERIF_B, 36)
    t = "BEYOND100"
    tw = sum(d.textlength(c, font=f) for c in t) + 10 * (len(t) - 1)
    d.rounded_rectangle([W / 2 - tw / 2 - 34, y - 38, W / 2 + tw / 2 + 34, y + 38], radius=38, fill=CREAM)
    pc.spaced(d, W / 2, y, t, f, GREEN, 10)


def _score(r):
    w = r["winner"]
    a, b = (r["games"][0], r["games"][1]) if w == 1 else (r["games"][1], r["games"][0])
    return "  ".join(f"{x}-{y}" for x, y in zip(a, b))


def _day_matches(results, day):
    out = []
    for r in results:
        if r.get("date") != day or webapp.classify(r)[1] != "singles" or not webapp.match_stats(r):
            continue
        g, lv, tag = webapp.classify(r)[0], webapp.classify(r)[2], webapp.classify(r)[3]
        score = {"tour": 3, "challenger": 2, "itf": 0.5, "other": 0}[lv] + {0: 3, 1: 2, 2: 1}.get(webapp._round_rank(r.get("round")), 0)
        w = r["p%d" % r["winner"]]["name"]
        score += 1.5 if photo_of(w)[0] else 0                    # prioridade a jogos com imagem
        out.append((score, r))
    out.sort(key=lambda x: -x[0])
    return [r for _, r in out]


def story_champion(r):
    w = r["winner"]
    win, los = r["p%d" % w], r["p%d" % (3 - w)]
    fp, credit = photo_of(win["name"])
    base, has = pc._photo_or_monogram((W, H), {"name": win["name"], "photo": fp}, centering=(0.5, 0.25))
    if has:
        img = pc._overlay(base, 0, 520, 150, 0)
        img = pc._overlay(img, 1000, H, 0, 235)
    else:
        img = _bg()
        pc._court(img.resize((W, 1350)))  # textura discreta
        base_d = ImageDraw.Draw(img)
        base_d.text((W / 2, 760), pc.initials(win["name"]), font=pc.font(SERIF_B, 520), fill=(30, 92, 73), anchor="mm")
    img = img.convert("RGB")
    _logo(img, 150)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([W / 2 - 170, 260, W / 2 + 170, 328], radius=34, fill=VOLT)
    d.text((W / 2, 294), "CHAMPION", font=pc.font(SANS_B, 34), fill=GREEN, anchor="mm")
    d.text((W / 2, 1290), win["name"], font=pc.fit(d, win["name"], SERIF_B, 96, 960), fill=CREAM, anchor="mm")
    t = webapp.base_tournament(r.get("tournament", ""))
    d.text((W / 2, 1390), t.upper()[:44], font=pc.fit(d, t.upper()[:44], SANS_B, 38, 960), fill=VOLT, anchor="mm")
    d.text((W / 2, 1480), _score(r), font=pc.font(SERIF_B, 78), fill=CREAM, anchor="mm")
    d.text((W / 2, 1560), f"def. {los['name']}", font=pc.fit(d, "def. " + los["name"], SERIF_I, 44, 960), fill=SOFT, anchor="mm")
    d.text((W / 2, 1700), "@beyond100.tennis", font=pc.font(SANS_B, 34), fill=CREAM, anchor="mm")
    if credit and has:
        d.text((40, 1870), credit[:80], font=pc.font(SANS_B, 20), fill=SOFT, anchor="lm")
    return img


def story_results(day, rows):
    img = _bg()
    _logo(img, 150)
    d = ImageDraw.Draw(img)
    d.text((W / 2, 300), "TODAY'S RESULTS", font=pc.font(SERIF_B, 76), fill=CREAM, anchor="mm")
    d.text((W / 2, 372), time.strftime("%b %d", time.strptime(day, "%Y-%m-%d")).replace(" 0", " ").upper(),
           font=pc.font(SANS_B, 34), fill=VOLT, anchor="mm")
    y = 460
    for r in rows[:5]:
        w = r["winner"]
        win, los = r["p%d" % w], r["p%d" % (3 - w)]
        d.rounded_rectangle([60, y, W - 60, y + 200], radius=34, fill=DEEP, outline=EDGE, width=2)
        fp, _ = photo_of(win["name"])
        av, _has = pc._photo_or_monogram((150, 150), {"name": win["name"], "photo": fp}, centering=(0.5, 0.25))
        mask = Image.new("L", (150, 150), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, 149, 149], fill=255)
        img.paste(av, (90, y + 25), mask)
        tag = webapp.classify(r)[3]
        t = webapp.base_tournament(r.get("tournament", ""))
        d.text((270, y + 42), (f"{tag} · {t}" if tag and tag not in t else t).upper()[:38], font=pc.font(SANS_B, 22), fill=VOLT, anchor="lm")
        d.text((270, y + 96), win["name"], font=pc.fit(d, win["name"], SERIF_B, 44, 460), fill=CREAM, anchor="lm")
        d.text((270, y + 150), f"d. {los['name']}", font=pc.fit(d, "d. " + los["name"], SERIF_I, 28, 460), fill=SOFT, anchor="lm")
        sc = _score(r)
        d.text((W - 90, y + 100), sc, font=pc.fit(d, sc, SERIF_B, 40, 260), fill=VOLT, anchor="rm")
        y += 228
    d.text((W / 2, 1700), "@beyond100.tennis", font=pc.font(SANS_B, 34), fill=CREAM, anchor="mm")
    return img


def run(out_dir="out", force=False):
    now = time.gmtime()
    day = time.strftime("%Y-%m-%d", now)
    if not force and now.tm_hour < STORY_HOUR:
        print("Stories: ainda não é a hora do resumo.")
        return []
    queue = _load(STORIES_FILE, [])
    have = {s["id"] for s in queue}
    results = _load(RESULTS_FILE, [])
    os.makedirs("posts", exist_ok=True)
    os.makedirs(os.path.join(out_dir, "stories"), exist_ok=True)
    made = []

    def add(sid, img):
        name = f"story-{sid}.jpg"
        img.convert("RGB").save(os.path.join("posts", name), quality=92)
        img.save(os.path.join(out_dir, "stories", f"story-{sid}.png"))
        queue.append({"id": sid, "image": name, "sent": False, "created": time.strftime("%Y-%m-%d %H:%M", now)})
        made.append(name)

    finals = [r for r in _day_matches(results, day) if (r.get("round") or "").strip().lower() in ("final", "finals")]
    for r in finals[:MAX_FINALS]:
        sid = f"champion-{r.get('id')}"
        if force or sid not in have:
            queue = [s for s in queue if s["id"] != sid]
            add(sid, story_champion(r))
    rows = [r for r in _day_matches(results, day)]
    sid = f"results-{day}"
    if len(rows) >= MIN_RESULTS and (force or sid not in have):
        queue = [s for s in queue if s["id"] != sid]
        add(sid, story_results(day, rows))
    with open(STORIES_FILE, "w", encoding="utf-8") as f:
        json.dump(queue[-40:], f, ensure_ascii=False, indent=2)
    print(f"Stories: {len(made)} novos na fila.")
    return made


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "out", "--force" in sys.argv)
