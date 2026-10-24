"""Páginas do site Beyond100: classificação dos jogos + página de resultados com filtros (JS no browser)."""
import html
import json
import re

LEVEL_ORDER = {"tour": 0, "challenger": 1, "itf": 2, "other": 3}
LEVEL_LABEL = {"tour": "Tour", "challenger": "Challenger", "itf": "ITF", "other": "Other"}


def base_tournament(t):
    """Tira o tipo de prova do fim do nome ('... MEN DOUBLES' -> '...') para agrupar singulares e pares."""
    t = re.sub(r"\s+(WOMEN|MEN|MIXED|BOYS|GIRLS)?\s*(SINGLES|DOUBLES)\s*$", "", t.strip(), flags=re.I)
    return re.sub(r"\s+", " ", t).strip()


def slugify(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-") or "torneio"


def classify(r):
    """Deduz género, formato e nível a partir do nome do torneio e dos jogadores."""
    t = (r.get("tournament") or "").upper()
    names = (r["p1"]["name"], r["p2"]["name"])
    kind = "doubles" if ("DOUBLES" in t or any(" / " in n for n in names)) else "singles"
    gender = None
    if "MIXED" in t:
        gender = "mixed"
    elif "WOMEN" in t or "WTA" in t or "GIRLS" in t or re.search(r"\bW\d{2,3}\b", t):
        gender = "women"
    elif re.search(r"\bMEN\b", t) or "ATP" in t or "BOYS" in t or "CHALLENGER" in t or re.search(r"\bM\d{2,3}\b", t):
        gender = "men"
    m = re.search(r"\b([MW])\s?(\d{2,3})\b", t)
    if "CHALLENGER" in t or re.search(r"WTA\s*(125|100)", t):
        level, tag = "challenger", "Challenger" if "CHALLENGER" in t else "WTA 125"
    elif m or "ITF" in t:
        level, tag = "itf", ("ITF " + m.group(1) + m.group(2)) if m else "ITF"
    elif "ATP" in t or "WTA" in t or "GRAND SLAM" in t:
        level, tag = "tour", "ATP" if "ATP" in t else "WTA"
    else:
        level, tag = "other", ""
    # a API traz o circuito (tour) e o género: é mais fiável do que o nome do torneio
    if r.get("gender") in ("men", "women"):
        gender = r["gender"]
    tour = (r.get("tour") or "").lower()
    if tour:
        if "challenger" in tour or "125" in tour:
            level, tag = "challenger", ("WTA 125" if gender == "women" else "Challenger")
        elif tour in ("atp", "wta"):
            level, tag = "tour", tour.upper()
        elif "itf" in tour:
            level, tag = "itf", (("ITF " + m.group(1) + m.group(2)) if m else "ITF")
    return gender, kind, level, tag


def api_view(m):
    """Jogo cru da API -> dicionário que o classify() percebe (nome, circuito, género)."""
    pl = m.get("players") or {}
    return {"tournament": m.get("tournament", ""), "tour": m.get("tour"), "gender": m.get("gender"),
            "p1": {"name": (pl.get("p1") or {}).get("name", "")}, "p2": {"name": (pl.get("p2") or {}).get("name", "")}}


def _round_rank(rd):
    s = (rd or "").lower()
    if "semi" in s: return 1
    if "quarter" in s or "1/4" in s: return 2
    if "final" in s and "1/" not in s: return 0
    m = re.search(r"1/(\d+)", s)
    if m: return 2 + {"8": 1, "16": 2, "32": 3, "64": 4, "128": 5}.get(m.group(1), 6)
    return 9


def _set_done(a, b):
    hi, lo = max(a, b), min(a, b)
    return (hi >= 10 and hi - lo >= 2) or (hi >= 6 and hi - lo >= 2) or (hi == 7 and lo in (5, 6))


def match_stats(r):
    """Estatísticas derivadas do resultado (sem dados extra da API).
    Devolve (distintivos, % de jogos ganhos pelo vencedor, nº de tie-breaks, jogos totais, margem) ou None se o jogo não está completo."""
    w = r.get("winner")
    g = r.get("games") or [[], []]
    if w not in (1, 2) or not g[0] or len(g[0]) != len(g[1]):
        return None
    mine, other = (g[0], g[1]) if w == 1 else (g[1], g[0])
    if not all(_set_done(a, b) for a, b in zip(mine, other)):
        return None                      # desistência / resultado incompleto: não tiramos conclusões
    if sum(a > b for a, b in zip(mine, other)) <= sum(a < b for a, b in zip(mine, other)):
        return None                      # resultado incoerente com o vencedor
    badges = []
    if mine[0] < other[0]:
        badges.append("comeback")
    if any(b == 0 and a >= 6 for a, b in zip(mine, other)) or any(a == 0 and b >= 6 for a, b in zip(mine, other)):
        badges.append("bagel")
    elif any((a, b) in ((6, 1), (1, 6)) for a, b in zip(mine, other)):
        badges.append("breadstick")
    sets = list(zip(g[0], g[1]))
    super_tb = any(max(a, b) >= 10 for a, b in sets)
    tbs = sum(1 for a, b in sets if (a, b) in ((7, 6), (6, 7)))
    if super_tb:
        badges.append("super")
    if tbs:
        badges.append("tb")
    tot_w, tot_o = sum(mine), sum(other)
    return badges, round(100 * tot_w / (tot_w + tot_o)), tbs, tot_w + tot_o, tot_w - tot_o


def prepare(results, tr):
    """Lista compacta para o browser."""
    out = []
    for r in results:
        gender, kind, level, tag = classify(r)
        rd = (r.get("round") or "")
        out.append({
            "id": r.get("id"), "d": r.get("date", ""), "t": base_tournament(r.get("tournament", "")),
            "rd": tr["rounds"].get(rd.lower(), rd), "ro": _round_rank(rd),
            "sf": tr["surfaces"].get(r.get("surface"), ""),
            "a": r["p1"]["name"], "ac": (r["p1"].get("country") or "").upper(),
            "b": r["p2"]["name"], "bc": (r["p2"].get("country") or "").upper(),
            "g": r["games"], "w": r.get("winner"),
            "sx": gender or "", "k": kind, "lv": level, "tag": tag,
            "sl": slugify(base_tournament(r.get("tournament", ""))),
            "fin": (rd.strip().lower() in ("final", "finals")) and kind == "singles",
            "win": (r["p%d" % r["winner"]]["name"] if r.get("winner") in (1, 2) else ""),
        })
        st = match_stats(r)
        out[-1]["bd"], out[-1]["dom"], out[-1]["tbn"] = (st[0], st[1], st[2]) if st else ([], None, 0)
        out[-1]["_c"] = (st[4], -st[3]) if (st and kind == "singles" and len(r["games"][0]) >= 2
                                            and (len(r["games"][0]) >= 3 or st[2])) else None
    best = {}
    for o in out:
        if o["_c"] is not None and (o["d"] not in best or o["_c"] < best[o["d"]]["_c"]):
            best[o["d"]] = o
    for o in best.values():
        o["bd"].append("closest")
    for o in out:
        o.pop("_c", None)
    return out


def _date_key(r):
    return (r.get("date", ""), -_round_rank(r.get("round")))      # mais tarde = mais recente


def player_table(results):
    """Vitórias/derrotas e sequência por jogador (só singulares terminados)."""
    stats = {}
    for r in sorted([x for x in results if classify(x)[1] == "singles" and x.get("winner") in (1, 2)], key=_date_key):
        for i in (1, 2):
            p = r["p%d" % i]
            st = stats.setdefault(p["name"], {"name": p["name"], "c": (p.get("country") or "").upper(),
                                              "w": 0, "l": 0, "seq": [], "last": "", "t": ""})
            won = r["winner"] == i
            st["w" if won else "l"] += 1
            st["seq"].append(won)
            st["last"], st["t"] = r.get("date", ""), base_tournament(r.get("tournament", ""))
    out = []
    for st in stats.values():
        n, cur = 0, st["seq"][-1]
        for v in reversed(st["seq"]):
            if v != cur:
                break
            n += 1
        st["streak"] = ("W" if cur else "L") + str(n)
        st["sn"] = n if cur else -n
        out.append(st)
    out.sort(key=lambda x: (-x["w"], x["l"], x["name"]))
    return out


def players_page(results, tx):
    esc = html.escape
    rows = player_table(results)
    if not rows:
        return f'<section class="page-h"><h1>{esc(tx.get("players", "Players"))}</h1><p class="empty">{esc(tx.get("empty", ""))}</p></section>'
    body = "".join(
        f'<tr><td class="pn">{esc(r["name"])} <small>{esc(r["c"])}</small></td><td>{r["w"]}-{r["l"]}</td>'
        f'<td class="{"hot" if r["sn"] >= 3 else ""}">{r["streak"]}</td><td class="lt">{esc(r["t"])} · {esc(r["last"])}</td></tr>'
        for r in rows[:400])
    return (f'<section class="page-h"><h1>{esc(tx.get("players", "Players"))}</h1>'
            f'<p>{esc(tx.get("players_lead", "Wins, losses and streaks from the matches we track."))}</p>'
            f'<input id="q" class="srch" placeholder="{esc(tx.get("search", "Search a player"))}"></section>'
            f'<table class="pt"><thead><tr><th>{esc(tx.get("player", "Player"))}</th><th>W-L</th>'
            f'<th>{esc(tx.get("streak", "Streak"))}</th><th>{esc(tx.get("last", "Last match"))}</th></tr></thead>'
            f'<tbody id="pb">{body}</tbody></table>'
            '<script>document.getElementById("q").addEventListener("input",function(e){var v=e.target.value.toLowerCase();'
            'document.querySelectorAll("#pb tr").forEach(function(r){r.style.display=r.textContent.toLowerCase().indexOf(v)<0?"none":""})})</script>')


def week_numbers(results, days=7):
    """Números dos últimos `days` dias, para o bloco da página inicial."""
    import datetime as dt
    today = dt.datetime.now(dt.timezone.utc).date()
    start = (today - dt.timedelta(days=days - 1)).isoformat()
    rs = [r for r in results if r.get("date", "") >= start and classify(r)[1] == "singles"]
    n = {"matches": 0, "three": 0, "tb": 0, "comebacks": 0, "bagels": 0, "finals": 0}
    tourn, wins = set(), {}
    for r in rs:
        st = match_stats(r)
        if not st:
            continue
        n["matches"] += 1
        tourn.add(base_tournament(r.get("tournament", "")))
        n["three"] += 1 if len(r["games"][0]) >= 3 else 0
        n["tb"] += st[2]
        n["comebacks"] += 1 if "comeback" in st[0] else 0
        n["bagels"] += 1 if "bagel" in st[0] else 0
        n["finals"] += 1 if (r.get("round") or "").strip().lower() in ("final", "finals") else 0
        w = r["p%d" % r["winner"]]["name"]
        wins[w] = wins.get(w, 0) + 1
    top = max(wins.items(), key=lambda kv: (kv[1], kv[0])) if wins else None
    n["tournaments"] = len(tourn)
    n["top"] = top if top and top[1] >= 2 else None
    return n


def week_block(n, tx):
    esc = html.escape
    if n["matches"] < 3:
        return ""
    tiles = [(n["matches"], tx.get("w_matches", "matches")), (n["tournaments"], tx.get("w_tourn", "tournaments")),
             (n["three"], tx.get("w_three", "three-setters")), (n["tb"], tx.get("w_tb", "tie-breaks")),
             (n["comebacks"], tx.get("w_comeback", "comebacks")), (n["bagels"], tx.get("w_bagel", "6-0 sets"))]
    h = "".join(f'<div class="nbox"><b>{v}</b><span>{esc(str(l))}</span></div>' for v, l in tiles)
    top = (f'<p class="topw">{esc(tx.get("w_top", "Most wins"))}: <b>{esc(n["top"][0])}</b> ({n["top"][1]})</p>' if n["top"] else "")
    return (f'<h2 class="sec"><span>{esc(tx.get("week", "This week in numbers"))}</span>'
            f'<a href="players.html">{esc(tx.get("players", "Players"))} →</a></h2><div class="numgrid">{h}</div>{top}')


CSS = """
.numgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:0 0 10px}
.nbox{background:var(--deep);border:1px solid var(--e);border-radius:16px;padding:14px;text-align:center}
.nbox b{display:block;font:700 2rem Georgia,serif;color:var(--v)}
.nbox span{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--s)}
.topw{color:var(--s);margin:4px 0 22px}.topw b{color:var(--c)}
.srch{width:100%;padding:12px 14px;border-radius:12px;border:1px solid var(--e);background:var(--deep);color:var(--c);font-size:1rem;margin-top:8px}
.pt{width:100%;border-collapse:collapse;margin:14px 0 30px}
.pt th{font:600 .75rem system-ui;letter-spacing:.08em;text-transform:uppercase;color:var(--s);text-align:left;padding:8px 6px;border-bottom:1px solid var(--e)}
.pt td{padding:10px 6px;border-bottom:1px solid #123f31}
.pt .pn{font-family:Georgia,serif;font-weight:700}.pt small{color:var(--s);font-weight:400}
.pt .hot{color:var(--v);font-weight:700}.pt .lt{color:var(--s);font-size:.85rem}
@media(max-width:560px){.pt .lt{display:none}.pt th:last-child{display:none}.numgrid{grid-template-columns:repeat(2,1fr)}}
:root{--g:#0e3a2d;--deep:#09281f;--c:#f7f2e6;--v:#d9f23d;--s:#b0c4b7;--e:#2c5d4c}
*{box-sizing:border-box}
body{margin:0;background:var(--g);color:var(--c);font:16px/1.5 system-ui,"Segoe UI",Arial,sans-serif}
a{color:inherit}
.wrap{max-width:860px;margin:0 auto;padding:0 16px}
nav{display:flex;justify-content:space-between;align-items:center;padding:20px 0}
.brand{font:700 1.15rem Georgia,"Times New Roman",serif;letter-spacing:.22em;text-decoration:none}
nav div a{margin-left:18px;color:var(--s);text-decoration:none;font-size:.95rem}
nav div a:hover,nav div a.on{color:var(--c)}
.hero{text-align:center;padding:24px 0 40px}
.emb{width:min(250px,64vw);height:auto}
h1{font:700 2.6rem/1.05 Georgia,"Times New Roman",serif;margin:24px 0 12px;letter-spacing:-.01em}
h1 em{color:var(--v);font-weight:400}
.hero p{color:var(--s);max-width:34ch;margin:0 auto 26px}
.btn{display:inline-block;background:var(--v);color:var(--g);font-weight:700;padding:13px 24px;border-radius:999px;text-decoration:none;margin:4px}
.btn.ghost{background:none;color:var(--c);border:2px solid var(--c)}
h2.sec{font:700 1.4rem Georgia,serif;margin:12px 0 14px;display:flex;justify-content:space-between;align-items:baseline}
h2.sec a{font:500 .9rem system-ui;color:var(--v)}
.page-h{padding:10px 0 6px}.page-h h1{font-size:2.1rem;margin:0 0 6px;text-align:left}
.page-h p{color:var(--s);margin:0}
.filters{position:sticky;top:0;z-index:5;background:var(--g);padding:12px 0 10px;border-bottom:1px solid var(--e)}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px}
.seg{display:inline-flex;border:1px solid var(--e);border-radius:999px;overflow:hidden}
.seg button{background:none;border:0;color:var(--s);padding:7px 14px;font:600 .85rem system-ui;cursor:pointer}
.seg button.on{background:var(--v);color:var(--g)}
.filters select,.filters input{background:var(--deep);color:var(--c);border:1px solid var(--e);border-radius:999px;padding:8px 14px;font:500 .9rem system-ui;min-width:0}
.filters select{max-width:100%;flex:1 1 200px}.filters input{flex:1 1 160px}
.count{color:var(--s);font-size:.8rem}
.dh{font:700 1.05rem Georgia,serif;margin:26px 0 8px;color:var(--v)}
.tg{background:var(--deep);border:1px solid var(--e);border-radius:20px;padding:6px 16px 8px;margin:0 0 12px}
.th{margin:10px 0 2px;font:700 .95rem system-ui;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.tag{background:var(--v);color:var(--g);border-radius:6px;padding:1px 7px;font:800 .68rem system-ui;letter-spacing:.06em;text-transform:uppercase}
.mt{padding:8px 0}.mt+.mt{border-top:1px solid var(--e)}
.mh{color:var(--s);font-size:.78rem;margin-bottom:2px}
.pl{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:3px 0;color:var(--s)}
.pl.win{color:var(--c)}
.nm{font:700 1.02rem Georgia,serif}.pl small{color:var(--s);margin-left:6px;font-size:.72rem}
.ch{display:flex;gap:5px;flex:none}
.ch b{min-width:32px;height:32px;border-radius:9px;border:1px solid var(--e);color:var(--s);display:grid;place-items:center;font:700 .95rem Georgia,serif}
.ch b.on{background:var(--v);border-color:var(--v);color:var(--g)}
.bd{display:flex;flex-wrap:wrap;gap:5px;margin:6px 0 2px}
.bd i{font:600 .68rem system-ui;font-style:normal;color:var(--v);border:1px solid var(--v);border-radius:999px;padding:1px 8px;letter-spacing:.03em}
.bd i.hot{background:var(--v);color:var(--g)}
.seg button.hl{color:var(--v)}.seg button.hl.on{color:var(--g)}
.strip{display:flex;gap:10px;overflow-x:auto;padding:14px 0 6px;scroll-snap-type:x proximity;-webkit-overflow-scrolling:touch}
.tc{flex:0 0 200px;scroll-snap-align:start;text-align:left;background:var(--deep);border:1px solid var(--e);border-radius:16px;padding:10px 12px;color:var(--c);cursor:pointer;display:flex;flex-direction:column;gap:3px;font:inherit}
.tc.on{border-color:var(--v);box-shadow:0 0 0 1px var(--v) inset}
.tc b{font:700 .92rem/1.2 system-ui;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.4em}
.tc small{color:var(--s);font-size:.72rem}.tc em{font:600 .76rem system-ui;font-style:normal;color:var(--v)}
.tt{display:flex;align-items:center;justify-content:space-between;min-height:20px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--v);box-shadow:0 0 0 3px rgba(217,242,61,.25)}
.allbtn{background:none;border:1px solid var(--e);color:var(--c);border-radius:999px;padding:8px 14px;font:600 .85rem system-ui;cursor:pointer}
.allt{background:var(--deep);border:1px solid var(--e);border-radius:16px;padding:10px;margin:8px 0}
.allt input{width:100%;background:var(--g);color:var(--c);border:1px solid var(--e);border-radius:999px;padding:8px 14px;margin-bottom:8px}
#alllist{max-height:260px;overflow:auto;display:flex;flex-direction:column}
#alllist button{background:none;border:0;border-top:1px solid var(--e);color:var(--c);text-align:left;padding:8px 4px;font:500 .88rem system-ui;cursor:pointer}
#alllist small{color:var(--s);margin-left:6px}
.th a{text-decoration:none}.th a:hover{text-decoration:underline}
.champ{color:var(--v)!important;margin-top:6px!important}.champ b{color:var(--c)}
.page-h a{color:var(--v);text-decoration:none;font-size:.9rem}
.bk{display:grid;grid-template-columns:repeat(3,minmax(210px,1fr));gap:0 30px;overflow-x:auto;padding:4px 2px 12px}
.bc{display:grid;position:relative}
.bc.q{grid-template-rows:auto repeat(4,1fr)}.bc.s{grid-template-rows:auto repeat(2,2fr)}.bc.f{grid-template-rows:auto 4fr}
.bc h4{margin:0 0 8px;font:700 .72rem system-ui;letter-spacing:.12em;text-transform:uppercase;color:var(--v)}
.bcell{display:flex;align-items:center;padding:5px 0;position:relative}
.bc.q .bcell::after,.bc.s .bcell::after{content:"";position:absolute;right:-30px;width:30px;top:50%;border-top:1px solid var(--e)}
.bm{background:var(--deep);border:1px solid var(--e);border-radius:12px;padding:4px 10px;width:100%}
.bm .pl{padding:3px 0;gap:8px}.bm .pl+.pl{border-top:1px solid var(--e)}
.bm .nm{font:700 .86rem system-ui;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.bm .ch b{min-width:24px;height:24px;border-radius:7px;font-size:.8rem}
.bm.tbd{color:var(--s);font:500 .8rem system-ui;text-align:center;padding:14px 10px;border-style:dashed}
.more{display:block;margin:20px auto;background:none;color:var(--c);border:2px solid var(--c);border-radius:999px;padding:10px 22px;font:700 .9rem system-ui;cursor:pointer}
.empty{color:var(--s);padding:24px 0}
footer{color:var(--s);font-size:.8rem;padding:28px 0 44px;border-top:1px solid var(--e);margin-top:28px}
@media(max-width:520px){h1{font-size:2.2rem}.ch b{min-width:28px;height:28px}.nm{font-size:.95rem}}
"""

JS = r"""
const D=JSON.parse(document.getElementById('data').textContent);
const UI=JSON.parse(document.getElementById('ui').textContent);
const LV={tour:0,challenger:1,itf:2,other:3};
const st={sx:'all',k:'singles',lv:'all',t:'',q:'',h:'',n:60};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const $=id=>document.getElementById(id);
function load(){try{const p=new URLSearchParams(location.hash.slice(1));for(const k of ['sx','k','lv','t','q','h'])if(p.has(k))st[k]=p.get(k);}catch(e){}}
function save(){try{const p=new URLSearchParams();for(const k of ['sx','k','lv','t','q','h'])if(st[k]&&!((k==='sx'||k==='lv')&&st[k]==='all')&&!(k==='k'&&st[k]==='singles'))p.set(k,st[k]);history.replaceState(null,'','#'+p.toString());}catch(e){}}
function base(){return D.filter(r=>(st.sx==='all'||r.sx===st.sx)&&(st.k==='all'||r.k===st.k)&&(st.lv==='all'||r.lv===st.lv)&&(!st.h||r.bd.length>0));}
function matches(){const q=st.q.trim().toLowerCase();return base().filter(r=>(!st.t||r.t===st.t)&&(!q||(r.a+' '+r.b).toLowerCase().includes(q)));}
function seg(id,key,opts){$(id).innerHTML=opts.map(([v,l])=>`<button data-v="${v}" class="${st[key]===v?'on':''}">${esc(l)}</button>`).join('');
 $(id).onclick=e=>{const v=e.target.dataset&&e.target.dataset.v;if(v===undefined)return;st[key]=v;st.t='';st.n=60;draw();};}
function chips(r,i){return r.g[i].map((x,j)=>{const o=r.g[1-i][j];return `<b class="${x>o?'on':''}">${x}</b>`}).join('');}
function bdg(r){return r.bd.length?`<div class="bd">${r.bd.map(b=>{const l=b==='tb'?UI.bd.tb.replace('{n}',r.tbn)+(r.tbn>1?'s':''):UI.bd[b];return `<i class="${b==='closest'||b==='comeback'?'hot':''}">${esc(l)}</i>`}).join('')}</div>`:'';}
function mrow(r){const m=[r.rd,r.sf,r.dom?r.dom+'% '+UI.games:''].filter(Boolean).join(' · ');
 const p=(i,n,c)=>`<div class="pl ${r.w===i+1?'win':''}"><div><span class="nm">${esc(n)}</span><small>${esc(c)}</small></div><div class="ch">${chips(r,i)}</div></div>`;
 return `<div class="mt"><div class="mh">${esc(m)}</div>${p(0,r.a,r.ac)}${p(1,r.b,r.bc)}${bdg(r)}</div>`;}
function draw(){
 seg('sx','sx',[['all',UI.all],['men',UI.men],['women',UI.women]]);
 seg('k','k',[['singles',UI.singles],['doubles',UI.doubles],['all',UI.all]]);
 seg('lv','lv',[['all',UI.all],['tour','Tour'],['challenger','Challenger'],['itf','ITF']]);
 seg('h','h',[['',UI.all],['1','\u2605 '+UI.hl]]);
 const pool=base();const ts={};
 pool.forEach(r=>{const o=ts[r.t]||(ts[r.t]={n:0,d:'',lv:r.lv,tag:r.tag,sf:r.sf,sl:r.sl,champ:''});o.n++;if(r.d>o.d)o.d=r.d;if(r.fin&&r.win)o.champ=r.win;});
 const names=Object.keys(ts).sort((x,y)=>ts[y].d.localeCompare(ts[x].d)||(LV[ts[x].lv]-LV[ts[y].lv])||x.localeCompare(y));
 if(st.t&&!ts[st.t])st.t='';
 const today=new Date();const age=d=>Math.round((Date.UTC(today.getFullYear(),today.getMonth(),today.getDate())-Date.parse(d+'T00:00:00Z'))/864e5);
 const recent=names.filter(n=>age(ts[n].d)<=10).sort((x,y)=>((age(ts[x].d)<=2?0:1)-(age(ts[y].d)<=2?0:1))||(LV[ts[x].lv]-LV[ts[y].lv])||ts[y].d.localeCompare(ts[x].d)||x.localeCompare(y));
 $('strip').innerHTML=recent.map(n=>{const o=ts[n];const live=age(o.d)<=2;
  return `<button class="tc ${n===st.t?'on':''}" data-t="${esc(n)}"><span class="tt">${o.tag?`<span class="tag">${esc(o.tag)}</span>`:''}${live?'<span class="dot"></span>':''}</span><b>${esc(n)}</b><small>${esc([o.sf,o.d].filter(Boolean).join(' · '))}</small><em>${o.champ?esc(UI.champ+': '+o.champ):o.n+' '+esc(UI.matches)}</em></button>`;}).join('');
 $('strip').style.display=recent.length?'flex':'none';
 $('strip').onclick=e=>{const c=e.target.closest('.tc');if(!c)return;const v=c.dataset.t;st.t=st.t===v?'':v;st.n=60;draw();};
 $('allbtn').textContent=(st.t?st.t+' ✕':UI.tours+' ('+names.length+')');
 $('allbtn').onclick=()=>{if(st.t){st.t='';st.n=60;draw();}else{const p=$('allt');p.hidden=!p.hidden;if(!p.hidden)$('tq').focus();}};
 const tq=$('tq').value.trim().toLowerCase();
 $('alllist').innerHTML=names.filter(n=>!tq||n.toLowerCase().includes(tq)).slice(0,200).map(n=>`<button data-t="${esc(n)}">${ts[n].tag?`<span class="tag">${esc(ts[n].tag)}</span> `:''}${esc(n)} <small>${esc(ts[n].d)} · ${ts[n].n}</small></button>`).join('');
 $('alllist').onclick=e=>{const c=e.target.closest('button');if(!c)return;st.t=c.dataset.t;st.n=60;$('allt').hidden=true;draw();};
 const all=matches();$('cnt').textContent=all.length+' '+UI.matches;
 const shown=all.slice(0,st.n);const days={};
 shown.forEach(r=>{((days[r.d]=days[r.d]||{})[r.t]=days[r.d][r.t]||[]).push(r);});
 let h='';
 Object.keys(days).sort().reverse().forEach(d=>{
  let label=d;try{label=new Date(d+'T12:00:00').toLocaleDateString(UI.lang,{weekday:'long',day:'numeric',month:'long'});}catch(e){}
  h+=`<h2 class="dh">${esc(label)}</h2>`;
  Object.keys(days[d]).sort((a,b)=>{const x=days[d][a][0],y=days[d][b][0];return (LV[x.lv]-LV[y.lv])||a.localeCompare(b);}).forEach(t=>{
   const ms=days[d][t].sort((a,b)=>a.ro-b.ro);const tag=ms[0].tag?`<span class="tag">${esc(ms[0].tag)}</span>`:'';
   h+=`<section class="tg"><h3 class="th">${tag}<a href="t/${esc(ms[0].sl)}.html">${esc(t)}</a></h3>${ms.map(mrow).join('')}</section>`;});});
 if(!h)h=`<p class="empty">${esc(UI.empty)}</p>`;
 if(all.length>shown.length)h+=`<button class="more" id="more">${esc(UI.more)}</button>`;
 $('list').innerHTML=h;const mb=$('more');if(mb)mb.onclick=()=>{st.n+=60;draw();};
 save();}
load();$('q').value=st.q;
$('tq').oninput=()=>draw();
$('q').oninput=e=>{st.q=e.target.value;st.n=60;draw();};
draw();
"""


def match_html(r, tr, esc=html.escape):
    lines = []
    for i in (0, 1):
        p = r["p%d" % (i + 1)]
        chips = ""
        for a_, b_ in zip(r["games"][0], r["games"][1]):
            mine, other = (a_, b_) if i == 0 else (b_, a_)
            chips += f'<b class="{"on" if mine > other else ""}">{mine}</b>'
        lines.append(f'<div class="pl {"win" if r.get("winner") == i + 1 else ""}"><div><span class="nm">{esc(p["name"])}</span>'
                     f'<small>{esc((p.get("country") or "").upper())}</small></div><div class="ch">{chips}</div></div>')
    rd = r.get("round") or ""
    meta = " · ".join(x for x in [r.get("date", ""), tr["rounds"].get(rd.lower(), rd), tr["surfaces"].get(r.get("surface"), "")] if x)
    st = match_stats(r)
    bd = ""
    if st:
        names = {"comeback": "b_comeback", "bagel": "b_bagel", "breadstick": "b_breadstick", "super": "b_super"}
        tags = [tr["_tx"][names[b]] for b in st[0] if b in names]
        if st[2]:
            tags.append(tr["_tx"]["b_tb"].format(n=st[2]) + ("s" if st[2] > 1 else ""))
        bd = ('<div class="bd">' + "".join(f"<i>{esc(t)}</i>" for t in tags) + "</div>") if tags else ""
        meta += f' · {st[1]}% {tr["_tx"]["f_games"]}'
    return f'<div class="mt"><div class="mh">{esc(meta)}</div>{lines[0]}{lines[1]}{bd}</div>'


def _bm(r, tx, esc=html.escape):
    """Cartão compacto de um jogo no quadro."""
    if r is None:
        return f'<div class="bm tbd">{esc(tx["f_tbd"])}</div>'
    rows = ""
    for i in (0, 1):
        p = r["p%d" % (i + 1)]
        chips = "".join(f'<b class="{"on" if (a if i == 0 else b) > (b if i == 0 else a) else ""}">{a if i == 0 else b}</b>'
                        for a, b in zip(r["games"][0], r["games"][1]))
        rows += (f'<div class="pl {"win" if r.get("winner") == i + 1 else ""}"><span class="nm">{esc(p["name"])}</span>'
                 f'<div class="ch">{chips}</div></div>')
    return f'<div class="bm">{rows}</div>'


def bracket_html(singles, tr, tx):
    """Quadro dos quartos de final até à final, só com os jogos que temos (o resto fica 'por apurar')."""
    by = {0: [], 1: [], 2: []}
    for r in singles:
        k = _round_rank(r.get("round"))
        if k in by:
            by[k].append(r)
    if not any(by.values()):
        return ""
    fin = by[0][:1]
    sfs = by[1][:2]
    qfs = by[2][:4]
    # ordena os quartos para ficarem ao lado da meia-final em que o vencedor jogou
    def sf_index(q):
        w = q["p%d" % q["winner"]]["name"] if q.get("winner") in (1, 2) else None
        for i, sf in enumerate(sfs):
            if w and w in (sf["p1"]["name"], sf["p2"]["name"]):
                return i
        return 9
    qfs = sorted(qfs, key=sf_index)
    slots_q = [None] * 4
    used = set()
    for q in qfs:                                  # coloca cada quarto nos 2 lugares da sua meia-final
        base = sf_index(q)
        spots = [base * 2, base * 2 + 1] if base < 2 else [0, 1, 2, 3]
        for sp in spots:
            if sp < 4 and sp not in used:
                slots_q[sp] = q; used.add(sp); break
    # meias-finais ordenadas pelo índice
    sfo = sfs + [None] * (2 - len(sfs))
    lab = lambda k, d: tr["rounds"].get(k, d)
    col = lambda title, cls, cells: (f'<div class="bc {cls}"><h4>{html.escape(title)}</h4>'
                                       + "".join(f'<div class="bcell">{_bm(c, tx)}</div>' for c in cells) + '</div>')
    return (f'<h2 class="dh">{html.escape(tx["f_bracket"])}</h2><div class="bk">'
            + col(lab("1/4-finals", "Quarterfinals"), "q", slots_q)
            + col(lab("semi-finals", "Semifinals"), "s", sfo)
            + col(lab("final", "Final"), "f", fin + [None] * (1 - len(fin)))
            + '</div>')


def tournament_page(name, rs, tr, tx):
    """Corpo da página de um torneio (singulares primeiro, pares depois)."""
    esc = html.escape
    tr = dict(tr, _tx=tx)
    first = rs[0]
    gender, _, level, tag = classify(first)
    singles = sorted([r for r in rs if classify(r)[1] == "singles"], key=lambda r: (r["date"], -_round_rank(r.get("round"))), reverse=True)
    doubles = [r for r in rs if classify(r)[1] == "doubles"]
    champ = next((r["p%d" % r["winner"]]["name"] for r in singles if r.get("winner") in (1, 2)
                  and (r.get("round") or "").strip().lower() in ("final", "finals")), "")
    surf = tr["surfaces"].get(first.get("surface"), "")
    dates = sorted(r["date"] for r in rs)
    sub = " · ".join(x for x in [surf, dates[0] if dates[0] == dates[-1] else f"{dates[0]} → {dates[-1]}"] if x)
    tagh = f'<span class="tag">{esc(tag)}</span> ' if tag else ""
    h = (f'<section class="page-h"><p><a href="../results.html">← {esc(tx["title"])}</a></p>'
         f'<h1>{tagh}{esc(name)}</h1><p>{esc(sub)}</p>'
         + (f'<p class="champ">{esc(tx["f_champion"])}: <b>{esc(champ)}</b></p>' if champ else "") + '</section>')
    def sec(title, items):
        if not items:
            return ""
        body = "".join(match_html(r, tr) for r in items)
        return f'<h2 class="dh">{esc(title)}</h2><section class="tg">{body}</section>'
    h += bracket_html(singles, tr, tx) + sec(tx["f_singles"], singles) + sec(tx["f_doubles"], doubles)
    return h


def results_page(results, tr, tx, lang):
    esc = html.escape
    data = prepare(results, tr)
    ui = {"all": tx["f_all"], "men": tx["f_men"], "women": tx["f_women"], "singles": tx["f_singles"],
          "doubles": tx["f_doubles"], "alltour": tx["f_alltour"], "matches": tx["f_matches"],
          "more": tx["f_more"], "empty": tx["empty"], "lang": lang, "hl": tx["f_highlights"],
          "bd": {"comeback": tx["b_comeback"], "bagel": tx["b_bagel"], "breadstick": tx["b_breadstick"],
                 "super": tx["b_super"], "tb": tx["b_tb"], "closest": tx["b_closest"]}, "games": tx["f_games"],
          "champ": tx["f_champion"], "searchtour": tx["f_search_tour"], "tours": tx["f_tournaments"]}
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    ui_json = json.dumps(ui, ensure_ascii=False).replace("</", "<\\/")
    fallback = "".join(
        f'<p class="empty">{esc(r["a"])} – {esc(r["b"])} · {esc(r["t"])}</p>'
        for r in [x for x in data if x["k"] == "singles"][:20])
    return (f'<section class="page-h"><h1>{esc(tx["title"])}</h1><p>{esc(tx["lead"])}</p></section>'
            '<div class="filters">'
            '<div class="row"><div class="seg" id="sx"></div><div class="seg" id="k"></div></div>'
            '<div class="row"><div class="seg" id="lv"></div><div class="seg" id="h"></div></div>'
            f'<div class="row"><input id="q" type="search" placeholder="{esc(tx["f_player"])}" aria-label="{esc(tx["f_player"])}">'
            '<button class="allbtn" id="allbtn"></button><span class="count" id="cnt"></span></div></div>'
            '<div class="strip" id="strip"></div>'
            f'<div class="allt" id="allt" hidden><input id="tq" type="search" placeholder="{esc(tx["f_search_tour"])}"><div id="alllist"></div></div>'
            f'<div id="list"><noscript>{fallback}</noscript></div>'
            f'<script id="data" type="application/json">{data_json}</script>'
            f'<script id="ui" type="application/json">{ui_json}</script>'
            f'<script>{JS}</script>')
