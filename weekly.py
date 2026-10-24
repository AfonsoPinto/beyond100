"""Carrossel semanal "The week on the Challenger tour" (slides 1080x1350 + legenda).

  python weekly.py out          -> gera o carrossel se for domingo à tarde (UTC) e ainda não existir o desta semana
  python weekly.py out --force  -> gera já (para testar)

Só usa dados públicos de results.json (resultados guardados). Nada é inventado.
O carrossel entra na fila carousels.json; o publisher.py envia-o (se PUBLISH_AUTO=1).
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw

import photo_cards as pc
import webapp
from captions import make_caption

RESULTS_FILE = "results.json"
CAROUSELS_FILE = "carousels.json"
WEEKLY_DAY = int(os.environ.get("WEEKLY_DAY", "6"))      # 0=segunda ... 6=domingo (UTC)
WEEKLY_HOUR = int(os.environ.get("WEEKLY_HOUR", "17"))   # a partir desta hora UTC
W, H = pc.W, pc.H
GREEN, CREAM, VOLT, SOFT, DEEP, EDGE = pc.GREEN, pc.CREAM, pc.VOLT, pc.SOFT, pc.DEEP, pc.EDGE
SERIF_B, SERIF_I, SANS_B = pc.SERIF_B, pc.SERIF_I, pc.SANS_B
MAX_SLIDES = 10


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _score(r, winner_first=True):
    g, w = r["games"], r.get("winner")
    a, b = (g[0], g[1]) if w == 1 or not winner_first else (g[1], g[0])
    if w == 2 and winner_first:
        a, b = g[1], g[0]
    return "  ".join(f"{x}-{y}" for x, y in zip(a, b))


def _last(name):
    return (name or "?").split()[-1]


def week_data(results, today=None):
    today = today or datetime.now(timezone.utc).date()
    start = today - timedelta(days=6)
    rs = [r for r in results
          if start.isoformat() <= (r.get("date") or "") <= today.isoformat()
          and webapp.classify(r)[1] == "singles"]
    finals, stats = [], {"matches": 0, "three": 0, "tb": 0, "bagels": 0, "comebacks": 0}
    tourn = set()
    best = None
    for r in rs:
        st = webapp.match_stats(r)
        if not st:
            continue
        stats["matches"] += 1
        tourn.add(webapp.base_tournament(r.get("tournament", "")))
        badges, dom, tbs, tot, margin = st
        stats["three"] += 1 if len(r["games"][0]) >= 3 else 0
        stats["tb"] += tbs
        stats["bagels"] += 1 if "bagel" in badges else 0
        stats["comebacks"] += 1 if "comeback" in badges else 0
        if (r.get("round") or "").strip().lower() in ("final", "finals"):
            finals.append(r)
        if len(r["games"][0]) >= 3 or tbs:
            key = (margin, -tot)
            if best is None or key < best[0]:
                best = (key, r)
    dom = None
    for r in rs:
        st = webapp.match_stats(r)
        if st and (dom is None or st[1] > dom[0]):
            dom = (st[1], r)
    return {"start": start, "end": today, "finals": finals, "stats": stats, "_rs": rs,
            "tournaments": len(tourn), "closest": best[1] if best else None, "dominant": dom[1] if dom else None}


# ------------------------------------------------------------ slides
def _base():
    img = pc._gradient()
    pc._court(img)
    pc._header(img)
    return img


def _title(d, text, y=210, size=78):
    d.text((W / 2, y), text, font=pc.fit(d, text, SERIF_B, size, 900), fill=CREAM, anchor="mm")


def _dots(img, i, n):
    d = ImageDraw.Draw(img)
    gap = 26
    x0 = W / 2 - gap * (n - 1) / 2
    for k in range(n):
        d.ellipse([x0 + k * gap - 7, 1250 - 7, x0 + k * gap + 7, 1250 + 7], fill=VOLT if k == i else EDGE)


def slide_cover(wd):
    img = pc._gradient()
    pc._court(img)
    pc._header(img)
    d = ImageDraw.Draw(img)
    d.text((W / 2, 470), "THE WEEK", font=pc.font(SERIF_B, 150), fill=CREAM, anchor="mm")
    d.text((W / 2, 610), "BEYOND THE TOP 100", font=pc.font(SANS_B, 40), fill=VOLT, anchor="mm")
    rng = f"{wd['start'].strftime('%b %d')} – {wd['end'].strftime('%b %d')}".replace(" 0", " ")
    d.text((W / 2, 700), rng, font=pc.font(SERIF_I, 56), fill=SOFT, anchor="mm")
    s = wd["stats"]
    items = [(s["matches"], "matches"), (wd["tournaments"], "tournaments"), (len(wd["finals"]), "finals")]
    x0 = 120
    for i, (n, lab) in enumerate(items):
        x = x0 + i * 280
        d.rounded_rectangle([x, 820, x + 240, 1040], radius=30, outline=EDGE, width=3, fill=DEEP)
        d.text((x + 120, 900), str(n), font=pc.font(SERIF_B, 92), fill=VOLT, anchor="mm")
        d.text((x + 120, 990), lab.upper(), font=pc.font(SANS_B, 26), fill=SOFT, anchor="mm")
    d.text((W / 2, 1130), "Swipe →", font=pc.font(SANS_B, 34), fill=CREAM, anchor="mm")
    pc._footer(img)
    return img


def slide_champions(wd):
    img = _base()
    d = ImageDraw.Draw(img)
    _title(d, "Champions")
    rows = wd["finals"][:5]
    y = 330
    for r in rows:
        _, _, _, tag = webapp.classify(r)
        w = r.get("winner")
        win, los = r["p%d" % w], r["p%d" % (3 - w)]
        d.rounded_rectangle([70, y, W - 70, y + 156], radius=28, fill=DEEP, outline=EDGE, width=2)
        t = (webapp.base_tournament(r.get("tournament", "")) or "")
        label = f"{tag} · {t}" if tag and tag not in t else t
        d.text((100, y + 34), label[:46].upper(), font=pc.font(SANS_B, 22), fill=VOLT, anchor="lm")
        d.text((100, y + 84), win["name"], font=pc.fit(d, win["name"], SERIF_B, 46, 560), fill=CREAM, anchor="lm")
        d.text((100, y + 126), f"d. {los['name']}", font=pc.fit(d, "d. " + los["name"], SERIF_I, 28, 560), fill=SOFT, anchor="lm")
        d.text((W - 100, y + 84), _score(r), font=pc.fit(d, _score(r), SERIF_B, 40, 300), fill=VOLT, anchor="rm")
        y += 176
    pc._footer(img)
    return img


def slide_closest(wd):
    r = wd["closest"]
    img = _base()
    d = ImageDraw.Draw(img)
    _title(d, "Match of the week")
    w = r["winner"]
    win, los = r["p%d" % w], r["p%d" % (3 - w)]
    t = webapp.base_tournament(r.get("tournament", ""))
    d.text((W / 2, 340), f"{t} · {r.get('round', '')}".upper()[:60], font=pc.font(SANS_B, 28), fill=VOLT, anchor="mm")
    d.text((W / 2, 560), win["name"], font=pc.fit(d, win["name"], SERIF_B, 78, 900), fill=CREAM, anchor="mm")
    d.text((W / 2, 650), "def.", font=pc.font(SERIF_I, 40), fill=SOFT, anchor="mm")
    d.text((W / 2, 740), los["name"], font=pc.fit(d, los["name"], SERIF_B, 64, 900), fill=SOFT, anchor="mm")
    sc = _score(r)
    d.rounded_rectangle([140, 860, W - 140, 1010], radius=40, fill=VOLT)
    d.text((W / 2, 935), sc, font=pc.fit(d, sc, SERIF_B, 84, 760), fill=GREEN, anchor="mm")
    st = webapp.match_stats(r)
    margin = st[4] if st else None
    if margin is not None:
        msg = ("Won the match with fewer games than the opponent" if margin <= 0
               else f"Separated by just {margin} game{'s' if margin != 1 else ''} across the match")
        d.text((W / 2, 1090), msg, font=pc.font(SANS_B, 30), fill=SOFT, anchor="mm")
    pc._footer(img)
    return img


def slide_tournaments(wd):
    img = _base()
    d = ImageDraw.Draw(img)
    _title(d, "Where the action was")
    counts = {}
    for r in wd["_rs"]:
        t = webapp.base_tournament(r.get("tournament", ""))
        tag = webapp.classify(r)[3]
        k = (t, tag)
        counts[k] = counts.get(k, 0) + 1
    rows = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
    y = 340
    for (t, tag), n in rows:
        d.rounded_rectangle([70, y, W - 70, y + 130], radius=28, fill=DEEP, outline=EDGE, width=2)
        d.text((100, y + 40), (tag or "").upper(), font=pc.font(SANS_B, 22), fill=VOLT, anchor="lm")
        d.text((100, y + 88), t, font=pc.fit(d, t, SERIF_B, 40, 700), fill=CREAM, anchor="lm")
        d.text((W - 100, y + 65), f"{n} matches", font=pc.font(SANS_B, 32), fill=SOFT, anchor="rm")
        y += 150
    pc._footer(img)
    return img


def slide_dominant(wd):
    r = wd["dominant"]
    img = _base()
    d = ImageDraw.Draw(img)
    _title(d, "Most dominant win")
    w = r["winner"]
    win, los = r["p%d" % w], r["p%d" % (3 - w)]
    t = webapp.base_tournament(r.get("tournament", ""))
    d.text((W / 2, 340), f"{t} · {r.get('round', '')}".upper()[:60], font=pc.font(SANS_B, 28), fill=VOLT, anchor="mm")
    d.text((W / 2, 560), win["name"], font=pc.fit(d, win["name"], SERIF_B, 78, 900), fill=CREAM, anchor="mm")
    d.text((W / 2, 650), "def.", font=pc.font(SERIF_I, 40), fill=SOFT, anchor="mm")
    d.text((W / 2, 740), los["name"], font=pc.fit(d, los["name"], SERIF_B, 64, 900), fill=SOFT, anchor="mm")
    sc = _score(r)
    d.rounded_rectangle([140, 860, W - 140, 1010], radius=40, fill=VOLT)
    d.text((W / 2, 935), sc, font=pc.fit(d, sc, SERIF_B, 84, 760), fill=GREEN, anchor="mm")
    st = webapp.match_stats(r)
    if st:
        d.text((W / 2, 1090), f"Won {st[1]}% of all games played", font=pc.font(SANS_B, 30), fill=SOFT, anchor="mm")
    pc._footer(img)
    return img


def slide_numbers(wd):
    img = _base()
    d = ImageDraw.Draw(img)
    _title(d, "By the numbers")
    s = wd["stats"]
    tiles = [(s["three"], "three-set matches"), (s["tb"], "tie-breaks"),
             (s["comebacks"], "comebacks"), (s["bagels"], "6-0 sets")]
    for i, (n, lab) in enumerate(tiles):
        x = 90 + (i % 2) * 450
        y = 340 + (i // 2) * 400
        d.rounded_rectangle([x, y, x + 410, y + 360], radius=36, fill=DEEP, outline=EDGE, width=3)
        d.text((x + 205, y + 150), str(n), font=pc.font(SERIF_B, 150), fill=VOLT, anchor="mm")
        d.text((x + 205, y + 275), lab.upper(), font=pc.fit(d, lab.upper(), SANS_B, 28, 360), fill=CREAM, anchor="mm")
    pc._footer(img)
    return img


def slide_cta():
    img = pc._gradient()
    pc._court(img)
    pc._header(img)
    d = ImageDraw.Draw(img)
    d.text((W / 2, 520), "Tennis beyond", font=pc.font(SERIF_B, 100), fill=CREAM, anchor="mm")
    d.text((W / 2, 640), "the top 100", font=pc.font(SERIF_B, 100), fill=VOLT, anchor="mm")
    d.text((W / 2, 790), "Results, stats and stories", font=pc.font(SERIF_I, 48), fill=SOFT, anchor="mm")
    d.text((W / 2, 850), "from Challenger, ITF and WTA events.", font=pc.font(SERIF_I, 48), fill=SOFT, anchor="mm")
    d.rounded_rectangle([200, 960, W - 200, 1070], radius=55, fill=VOLT)
    d.text((W / 2, 1015), "Follow · Save · Share", font=pc.font(SANS_B, 40), fill=GREEN, anchor="mm")
    d.text((W / 2, 1160), "beyond100tennis.com", font=pc.font(SANS_B, 36), fill=CREAM, anchor="mm")
    pc._footer(img)
    return img


def build_slides(wd):
    """Sempre 5 slides (a Make precisa de um número fixo): capa, 2 de conteúdo, números, apelo."""
    slides = [slide_cover(wd)]
    slides.append(slide_champions(wd) if wd["finals"] else slide_tournaments(wd))
    slides.append(slide_closest(wd) if wd["closest"] else slide_dominant(wd))
    slides.append(slide_numbers(wd))
    slides.append(slide_cta())
    for i, im in enumerate(slides):
        _dots(im, i, len(slides))
    return slides


def facts(wd):
    fin = []
    for r in wd["finals"][:5]:
        w = r["winner"]
        fin.append({"tournament": webapp.base_tournament(r.get("tournament", "")),
                    "winner": r["p%d" % w]["name"], "runner_up": r["p%d" % (3 - w)]["name"], "score": _score(r)})
    c = wd["closest"]
    return {"period": f"{wd['start']} to {wd['end']}", "matches": wd["stats"]["matches"],
            "tournaments": wd["tournaments"], "three_set_matches": wd["stats"]["three"],
            "tiebreaks": wd["stats"]["tb"], "comebacks": wd["stats"]["comebacks"],
            "finals": fin,
            "match_of_the_week": ({"tournament": webapp.base_tournament(c.get("tournament", "")),
                                   "winner": c["p%d" % c["winner"]]["name"],
                                   "loser": c["p%d" % (3 - c["winner"])]["name"], "score": _score(c)} if c else None)}


def run(out_dir="out", force=False):
    now = datetime.now(timezone.utc)
    if not force and not (now.weekday() == WEEKLY_DAY and now.hour >= WEEKLY_HOUR):
        print("Carrossel semanal: ainda não é a hora.")
        return None
    week_id = f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"
    queue = _load(CAROUSELS_FILE, [])
    if not force and any(c["id"] == week_id for c in queue):
        print("Carrossel semanal: já existe o desta semana.")
        return None
    wd = week_data(_load(RESULTS_FILE, []), now.date())
    if wd["stats"]["matches"] < 8:                       # semana vazia: não vale a pena publicar
        print(f"Carrossel semanal: só {wd['stats']['matches']} jogos esta semana, salto.")
        return None
    slides = build_slides(wd)
    os.makedirs(os.path.join(out_dir, "weekly"), exist_ok=True)
    os.makedirs("posts", exist_ok=True)
    names = []
    for i, im in enumerate(slides, 1):
        name = f"week-{week_id}-{i}.jpg"
        im.convert("RGB").save(os.path.join("posts", name), quality=92)
        im.save(os.path.join(out_dir, "weekly", f"slide{i}.png"))
        names.append(name)
    cap = make_caption("weekly", facts(wd))
    with open(os.path.join(out_dir, "weekly", "caption.txt"), "w", encoding="utf-8") as f:
        f.write(cap)
    queue = [c for c in queue if c["id"] != week_id]
    queue.append({"id": week_id, "kind": "weekly", "images": names, "caption": cap, "sent": False,
                  "created": time.strftime("%Y-%m-%d %H:%M", time.gmtime())})
    with open(CAROUSELS_FILE, "w", encoding="utf-8") as f:
        json.dump(queue[-20:], f, ensure_ascii=False, indent=2)
    print(f"Carrossel semanal {week_id}: {len(names)} slides na fila.")
    return names


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "out", "--force" in sys.argv)
