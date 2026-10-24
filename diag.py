"""Diagnóstico: o que a API devolve AGORA em direto? (usa 1-2 pedidos da quota). Só imprime nomes públicos de torneios."""
import collections
import json

import result_card as rc
import webapp

try:
    live = rc.fetch_live()
except Exception as e:
    print("Erro a obter jogos ao vivo:", type(e).__name__, e)
    raise SystemExit(0)

print(f"Jogos ao vivo agora: {len(live)}")
by = collections.OrderedDict()
for m in live:
    t = m.get("tournament", "?")
    r = {"tournament": t, "p1": {"name": (m.get("players", {}).get("p1") or {}).get("name", "")},
         "p2": {"name": (m.get("players", {}).get("p2") or {}).get("name", "")}}
    g, kind, lv, tag = webapp.classify(r)
    by.setdefault((t, lv, tag), []).append(m)
print("\nTorneio | nível deduzido | tag | nº de jogos")
for (t, lv, tag), ms in sorted(by.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    print(f"- {t} | {lv} | {tag or '-'} | {len(ms)}")
print("\nCampos de um jogo (só chaves):", sorted(live[0].keys()) if live else "-")
shown = 0
for (t, lv, tag), ms in by.items():
    if lv == "other" and t in ("Basel", "Vienna", "Lisbon", "Florence", "Tokyo", "Guangzhou") and shown < 3:
        m = ms[0]
        print("\nExemplo (" + t + "):")
        print(json.dumps({k: v for k, v in m.items() if k not in ("score", "players")}, ensure_ascii=False, default=str)[:600])
        pl = m.get("players") or {}
        print("  p1:", {k: v for k, v in (pl.get("p1") or {}).items() if k in ("name", "ranking", "country")},
              "p2:", {k: v for k, v in (pl.get("p2") or {}).items() if k in ("name", "ranking", "country")})
        shown += 1
