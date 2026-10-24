"""Diagnóstico 2: que dados extra o API gratuito oferece? (~5 pedidos da quota). Imprime só chaves e amostras públicas."""
import json

import requests

import result_card as rc


def get(path, **params):
    try:
        r = requests.get(f"{rc.API_BASE}{path}", params=params, headers=rc._headers(), timeout=20)
        print(f"\n=== GET {path} {params or ''} -> {r.status_code}")
        if r.status_code != 200:
            print(r.text[:200])
            return None
        return r.json()
    except Exception as e:
        print(f"\n=== GET {path} -> erro {type(e).__name__}")
        return None


def short(v, n=900):
    return json.dumps(v, ensure_ascii=False, default=str)[:n]


live = get("/matches", status="live")
data = (live or {}).get("data", []) if isinstance(live, dict) else []
print("Jogos ao vivo:", len(data))
vienna = next((m for m in data if m.get("tournament") == "Vienna" and not m.get("is_doubles")), data[0] if data else None)
if vienna:
    print("\n--- Jogo completo (chaves de 1.º nível e valores simples) ---")
    print(short({k: v for k, v in vienna.items() if k != "players"}))
    print("\n--- p1 completo ---")
    print(short((vienna.get("players") or {}).get("p1")))
    mid = vienna.get("id")
    one = get(f"/matches/{mid}")
    if one:
        print("Chaves do jogo por id:", sorted(one.keys()) if isinstance(one, dict) else type(one))
        print(short({k: v for k, v in one.items() if k in ("score", "h2h", "stats", "statistics", "analysis", "odds")}, 700))
up = get("/matches", status="upcoming")
if isinstance(up, dict):
    d = up.get("data", [])
    print("Próximos jogos:", len(d), "| exemplo:", short(d[0], 500) if d else "-")
t = get("/tournaments")
if isinstance(t, dict):
    d = t.get("data", t)
    print("Torneios (chaves/exemplo):", short(d[:2] if isinstance(d, list) else d, 900))
pl = get("/players", search="Fearnley")
if isinstance(pl, dict):
    d = pl.get("data", pl)
    print("Jogador (exemplo):", short(d[:1] if isinstance(d, list) else d, 900))
