"""Teste: tenta obter fotos de licença livre de alguns jogadores e gera cartões de exemplo em photo_test/."""
import json
import os

import fetch_photos
import photo_cards as pc

PLAYERS = ["Jannik Sinner", "Carlos Alcaraz", "Novak Djokovic", "Iga Świątek", "Aryna Sabalenka",
           "Nuno Borges", "Francisco Cabral", "Jaume Munar", "Arthur Fils", "Coco Gauff"]
OUT = "photo_test"
os.makedirs(OUT, exist_ok=True)
os.makedirs("photos", exist_ok=True)
found = []
for name in PLAYERS:
    try:
        fetch_photos.fetch_photo(name, None, "photos")
    except Exception as e:
        print(name, "erro:", type(e).__name__, e)
    fp = os.path.join("photos", fetch_photos.slug(name) + ".jpg")
    print(name, "->", "FOTO" if os.path.exists(fp) else "sem foto")
    if os.path.exists(fp):
        found.append((name, fp))
try:
    credits = json.load(open("photos/credits.json", encoding="utf-8"))
except (OSError, ValueError):
    credits = {}
for i, (name, fp) in enumerate(found[:4]):
    cr = credits.get(os.path.basename(fp))
    pc.render_rank_news({"player": name, "country": "", "rank_now": 98, "rank_before": 112, "system": "ATP",
                         "headline": "Sample card (test).", "context": "Layout test with a free-licence photo",
                         "photo": fp, "credit": cr}, os.path.join(OUT, f"rank-{i}.png"))
    pc.render_match_photo({"winner": {"name": name, "rank": 187, "photo": fp, "credit": cr},
                           "loser": {"name": "Sample Opponent", "rank": 46}, "sets": [(6, 4), (3, 6), (7, 5)],
                           "tournament": "Sample Challenger Open", "round": "Quarter-finals",
                           "level": "CHALLENGER", "tag": "UPSET", "headline": "Layout test."},
                          os.path.join(OUT, f"match-{i}.png"))
import shutil
for name, fp in found:
    shutil.copy(fp, os.path.join(OUT, os.path.basename(fp)))
if os.path.exists("photos/credits.json"):
    shutil.copy("photos/credits.json", os.path.join(OUT, "credits.json"))
print(f"Fotos encontradas: {len(found)} de {len(PLAYERS)}")
