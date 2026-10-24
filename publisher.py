"""Publicação automática no Instagram, em dois passos:

  python publisher.py prepare   -> converte os cartões novos (out/post/*.png) em JPEG público (posts/) e põe-nos na fila
  python publisher.py send      -> envia a fila para o Instagram (só se PUBLISH_AUTO=1)

Duas maneiras de publicar (escolhe-se com PUBLISH_BACKEND):
  webhook : chama um webhook (Make, Zapier, n8n...) com {image_url, caption, id}; não precisa de app Meta própria
  graph   : API oficial do Instagram (precisa de IG_USER_ID e IG_ACCESS_TOKEN)

Segurança: sem PUBLISH_AUTO=1 não se envia nada; os posts ficam na fila (posts.json) e nos "Artifacts".
"""
import json
import os
import shutil
import sys
import time

from PIL import Image

POSTS_FILE = "posts.json"
POSTS_DIR = "posts"
CAROUSELS_FILE = "carousels.json"
STORIES_FILE = "stories.json"
SITE_URL = os.environ.get("SITE_URL", "https://beyond100.pages.dev").rstrip("/")
KEEP_DAYS = 30


def _load():
    try:
        with open(POSTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(posts):
    with open(POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


def prepare(out_dir="out"):
    src = os.path.join(out_dir, "post")
    posts = _load()
    os.makedirs(POSTS_DIR, exist_ok=True)
    n = 0
    for day, entries in posts.items():
        for e in entries:
            if e.get("image"):
                continue
            png = os.path.join(src, e["file"])
            if not os.path.exists(png):
                continue                       # entrada de uma execução anterior que já foi tratada
            stem = os.path.splitext(e["file"])[0] + "-" + day
            Image.open(png).convert("RGB").save(os.path.join(POSTS_DIR, stem + ".jpg"), quality=92)
            cap = os.path.splitext(png)[0] + ".txt"
            if os.path.exists(cap):
                shutil.copy(cap, os.path.join(POSTS_DIR, stem + ".txt"))
            e["image"], e["sent"] = stem + ".jpg", False
            n += 1
    # limpa ficheiros com mais de KEEP_DAYS dias
    cutoff = time.time() - KEEP_DAYS * 86400
    for fn in os.listdir(POSTS_DIR):
        fp = os.path.join(POSTS_DIR, fn)
        if os.path.getmtime(fp) < cutoff:
            os.remove(fp)
    _save(posts)
    print(f"Fila: {n} posts novos preparados.")


def _caption(e):
    fp = os.path.join(POSTS_DIR, os.path.splitext(e["image"])[0] + ".txt")
    try:
        with open(fp, encoding="utf-8") as f:
            return f.read().strip()[:2200]
    except OSError:
        return ""


def _send_webhook(url, image_url, caption, pid):
    import requests
    r = requests.post(url, json={"image_url": image_url, "caption": caption, "id": pid}, timeout=30)
    r.raise_for_status()


def _send_graph(image_url, caption):
    import requests
    ver = os.environ.get("GRAPH_VERSION", "v21.0")
    uid, tok = os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"]
    base = f"https://graph.facebook.com/{ver}"
    r = requests.post(f"{base}/{uid}/media", data={"image_url": image_url, "caption": caption, "access_token": tok}, timeout=60)
    r.raise_for_status()
    cid = r.json()["id"]
    for _ in range(6):                          # o Instagram precisa de uns segundos para processar a imagem
        st = requests.get(f"{base}/{cid}", params={"fields": "status_code", "access_token": tok}, timeout=30).json()
        if st.get("status_code") in (None, "FINISHED"):
            break
        time.sleep(5)
    r = requests.post(f"{base}/{uid}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
    r.raise_for_status()


def _send_carousels():
    """Carrosséis (ex.: resumo semanal): webhook próprio com image_urls e image_1..image_10."""
    try:
        with open(CAROUSELS_FILE, encoding="utf-8") as f:
            queue = json.load(f)
    except (OSError, ValueError):
        return
    pending = [c for c in queue if not c.get("sent")]
    if not pending:
        return
    url = os.environ.get("MAKE_WEBHOOK_CAROUSEL_URL")
    if not url:
        print(f"{len(pending)} carrosséis na fila, mas falta MAKE_WEBHOOK_CAROUSEL_URL: nada enviado.")
        return
    import requests
    for c in pending:
        urls = [f"{SITE_URL}/posts/{n}" for n in c["images"]]
        body = {"id": c["id"], "caption": c["caption"][:2200], "image_urls": urls}
        body.update({f"image_{i}": u for i, u in enumerate(urls, 1)})
        try:
            requests.post(url, json=body, timeout=30).raise_for_status()
        except Exception as ex:
            print(f"Carrossel {c['id']}: falhou ({type(ex).__name__}), tenta de novo mais tarde.")
            continue
        c["sent"], c["sent_at"] = True, time.strftime("%Y-%m-%d %H:%M", time.gmtime())
        with open(CAROUSELS_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        print(f"Carrossel {c['id']}: enviado.")


def _send_stories():
    try:
        with open(STORIES_FILE, encoding="utf-8") as f:
            queue = json.load(f)
    except (OSError, ValueError):
        return
    pending = [c for c in queue if not c.get("sent")]
    url = os.environ.get("MAKE_WEBHOOK_STORY_URL")
    if not pending:
        return
    if not url:
        print(f"{len(pending)} stories na fila, mas falta MAKE_WEBHOOK_STORY_URL: nada enviado.")
        return
    import requests
    for c in pending[:3]:                       # no máximo 3 por execução
        try:
            requests.post(url, json={"id": c["id"], "image_url": f"{SITE_URL}/posts/{c['image']}"}, timeout=30).raise_for_status()
        except Exception as ex:
            print(f"Story {c['id']}: falhou ({type(ex).__name__}), tenta de novo mais tarde.")
            continue
        c["sent"], c["sent_at"] = True, time.strftime("%Y-%m-%d %H:%M", time.gmtime())
        with open(STORIES_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        print(f"Story {c['id']}: enviado.")


def send():
    posts = _load()
    pending = [(d, e) for d, es in posts.items() for e in es if e.get("image") and not e.get("sent")]
    if os.environ.get("PUBLISH_AUTO") != "1":
        print(f"{len(pending)} posts na fila, mas PUBLISH_AUTO não está a 1: nada enviado.")
        return
    _send_carousels()
    _send_stories()
    if not pending:
        print("Fila vazia.")
        return
    backend = os.environ.get("PUBLISH_BACKEND", "webhook")
    for d, e in pending:
        url = f"{SITE_URL}/posts/{e['image']}"
        try:
            if backend == "graph":
                _send_graph(url, _caption(e))
            else:
                _send_webhook(os.environ["MAKE_WEBHOOK_URL"], url, _caption(e), e.get("id"))
        except Exception as ex:                 # falhou: fica na fila para a próxima execução
            print(f"Post {e.get('id')}: falhou ({type(ex).__name__}), tenta de novo mais tarde.")
            continue
        e["sent"] = True
        e["sent_at"] = time.strftime("%Y-%m-%d %H:%M", time.gmtime())
        print(f"Post {e.get('id')}: enviado ({backend}).")
        _save(posts)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "prepare":
        prepare(sys.argv[2] if len(sys.argv) > 2 else "out")
    elif cmd == "send":
        send()
    else:
        sys.exit("Uso: python publisher.py prepare|send")
