"""
Vai buscar fotos de jogadores com LICENÇA LIVRE (Wikidata + Wikimedia Commons).

Fluxo, por jogador:
  1. Procura o jogador na Wikidata e confirma que é tenista (e, se houver data de nascimento, que coincide).
  2. Lê a imagem principal (P18) e, na Commons, a licença e o autor.
  3. Só aceita CC0 / domínio público / CC BY (sem SA, NC ou ND). Guarda a foto em photos/ e o crédito
     em photos/credits.json (o cartão mostra o crédito automaticamente). Regista a origem em photos/sources.json.

Uso:
    py fetch_photos.py "Nome Do Jogador" --birthday 1997-02-19
    set FETCH_PHOTOS=1     (o result_card.py passa a chamar isto sozinho, uma vez por jogador)

Variáveis: WIKI_CONTACT (o teu email, a Wikimedia pede-o no User-Agent), PHOTO_DIR (por omissão photos),
           ALLOW_SA=1 para aceitar também CC BY-SA (NÃO recomendado: obriga a partilhar a imagem sob a mesma licença).

Cobertura: só existe foto para quem tem imagem na Wikidata. Muitos jogadores de Challenger/ITF não têm; nesses
casos o cartão continua a usar o monograma. Uma licença livre não dispensa atribuição nem cobre marcas ou
patrocinadores visíveis na foto. Não é aconselhamento jurídico.
Requisitos: py -m pip install requests pillow
"""
import argparse
import html
import json
import os
import re
import sys
import time
import unicodedata

PHOTO_DIR = os.environ.get("PHOTO_DIR", "photos")
UA = f"Beyond100/0.1 (https://beyond100.tennis; {os.environ.get('WIKI_CONTACT', 'contact-not-set')})"
WD = "https://www.wikidata.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"
Q_HUMAN, Q_TENNIS = "Q5", "Q10833314"
MISS_RETRY_DAYS = 30


def slug(text):
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def _get(url, params):
    import requests
    r = requests.get(url, params={**params, "format": "json"}, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    time.sleep(0.25)  # simpatia com o servidor
    return r.json()


def _download(url, path):
    import requests
    from PIL import Image
    import io
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    Image.open(io.BytesIO(r.content)).convert("RGB").save(path, quality=92)


def _claim_ids(entity, prop):
    out = []
    for c in entity.get("claims", {}).get(prop, []):
        v = (c.get("mainsnak", {}).get("datavalue") or {}).get("value")
        if isinstance(v, dict) and "id" in v:
            out.append(v["id"])
    return out


def _birth(entity):
    for c in entity.get("claims", {}).get("P569", []):
        v = (c.get("mainsnak", {}).get("datavalue") or {}).get("value")
        if isinstance(v, dict) and v.get("time"):
            return v["time"][1:11]          # "+1997-02-19T00:00:00Z" -> "1997-02-19"
    return None


def find_image_file(name, birthday=None):
    """Nome do ficheiro da Commons (P18) de um tenista que bate certo com nome (e data de nascimento)."""
    found = _get(WD, {"action": "wbsearchentities", "search": name, "language": "en", "type": "item", "limit": 7})
    ids = [x["id"] for x in found.get("search", [])]
    if not ids:
        return None
    ents = _get(WD, {"action": "wbgetentities", "ids": "|".join(ids), "props": "claims"}).get("entities", {})
    cands = []
    for qid in ids:
        e = ents.get(qid, {})
        if Q_HUMAN not in _claim_ids(e, "P31") or Q_TENNIS not in _claim_ids(e, "P106"):
            continue
        if birthday and _birth(e) and _birth(e) != birthday:
            continue
        cands.append(e)
    if not cands or (not birthday and len(cands) > 1):   # sem data de nascimento, só aceita um candidato único
        return None
    for c in cands[0].get("claims", {}).get("P18", []):
        v = (c.get("mainsnak", {}).get("datavalue") or {}).get("value")
        if isinstance(v, str):
            return v
    return None


def license_ok(lic):
    L = (lic or "").upper().strip()
    if L.startswith("CC0") or L.startswith("PUBLIC DOMAIN") or L.startswith("PDM"):
        return True
    m = re.match(r"CC BY(?:-([A-Z-]+))? \d", L)
    if not m:
        return False
    mods = m.group(1)
    return mods is None or (mods == "SA" and os.environ.get("ALLOW_SA") == "1")


def commons_info(filename):
    q = _get(COMMONS, {"action": "query", "titles": "File:" + filename, "prop": "imageinfo",
                       "iiprop": "url|extmetadata", "iiurlwidth": 800})
    for page in q.get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [None])[0]
        if not info:
            continue
        meta = info.get("extmetadata", {})
        val = lambda k: (meta.get(k) or {}).get("value", "")
        artist = re.sub(r"<[^>]+>", "", html.unescape(val("Artist"))).strip()
        return {"url": info.get("thumburl") or info.get("url"), "license": val("LicenseShortName"),
                "artist": artist[:60] or "Wikimedia Commons", "page": info.get("descriptionurl", "")}
    return None


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_photo(name, birthday=None, photo_dir=None):
    """Devolve o caminho da foto guardada, ou None. Nunca guarda fotos sem licença aceite."""
    photo_dir = photo_dir or PHOTO_DIR
    key = slug(name)
    if not key:
        return None
    os.makedirs(photo_dir, exist_ok=True)
    dest = os.path.join(photo_dir, key + ".jpg")
    if os.path.exists(dest):
        return dest
    misses_path = os.path.join(photo_dir, "misses.json")
    misses = _load(misses_path, {})
    if time.time() - misses.get(key, 0) < MISS_RETRY_DAYS * 86400:
        return None

    def miss(reason):
        misses[key] = time.time()
        _save(misses_path, misses)
        print(f"Sem foto livre para {name}: {reason}", file=sys.stderr)
        return None

    try:
        fname = find_image_file(name, birthday)
        if not fname:
            return miss("sem imagem na Wikidata ou jogador não identificado com certeza")
        info = commons_info(fname)
        if not info or not info["url"]:
            return miss("ficheiro não encontrado na Commons")
        if not license_ok(info["license"]):
            return miss(f"licença não aceite ({info['license'] or 'desconhecida'})")
        _download(info["url"], dest)
    except Exception as e:                       # rede em baixo, limite de pedidos, etc.
        print(f"Falha ao obter foto de {name}: {e}", file=sys.stderr)
        return None
    credits = _load(os.path.join(photo_dir, "credits.json"), {})
    credits[key + ".jpg"] = f"Photo: {info['artist']} / {info['license']}"
    _save(os.path.join(photo_dir, "credits.json"), credits)
    sources = _load(os.path.join(photo_dir, "sources.json"), {})
    sources[key + ".jpg"] = {"commons_page": info["page"], "license": info["license"], "artist": info["artist"]}
    _save(os.path.join(photo_dir, "sources.json"), sources)
    return dest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--birthday", help="AAAA-MM-DD (a API dá este campo; ajuda a não trocar de pessoa)")
    a = ap.parse_args()
    p = fetch_photo(a.name, a.birthday)
    print("Foto guardada em:" if p else "Sem foto livre.", p or "")
