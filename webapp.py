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
    return gender, kind, level, tag


def _round_rank(rd):
    s = (rd or "").lower()
    if "semi" in s: return 1
    if "quarter" in s or "1/4" in s: return 2
    if "final" in s and "1/" not in s: return 0
    m = re.search(r"1/(\d+)", s)
    if m: return 2 + {"8": 1, "16": 2, "32": 3, "64": 4, "128": 5}.get(m.group(1), 6)
    return 9


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
        })
    return out


CSS = """
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
.more{display:block;margin:20px auto;background:none;color:var(--c);border:2px solid var(--c);border-radius:999px;padding:10px 22px;font:700 .9rem system-ui;cursor:pointer}
.empty{color:var(--s);padding:24px 0}
footer{color:var(--s);font-size:.8rem;padding:28px 0 44px;border-top:1px solid var(--e);margin-top:28px}
@media(max-width:520px){h1{font-size:2.2rem}.ch b{min-width:28px;height:28px}.nm{font-size:.95rem}}
"""

JS = r"""
const D=JSON.parse(document.getElementById('data').textContent);
const UI=JSON.parse(document.getElementById('ui').textContent);
const LV={tour:0,challenger:1,itf:2,other:3};
const st={sx:'all',k:'singles',lv:'all',t:'',q:'',n:60};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const $=id=>document.getElementById(id);
function load(){try{const p=new URLSearchParams(location.hash.slice(1));for(const k of ['sx','k','lv','t','q'])if(p.has(k))st[k]=p.get(k);}catch(e){}}
function save(){try{const p=new URLSearchParams();for(const k of ['sx','k','lv','t','q'])if(st[k]&&!((k==='sx'||k==='lv')&&st[k]==='all')&&!(k==='k'&&st[k]==='singles'))p.set(k,st[k]);history.replaceState(null,'','#'+p.toString());}catch(e){}}
function base(){return D.filter(r=>(st.sx==='all'||r.sx===st.sx)&&(st.k==='all'||r.k===st.k)&&(st.lv==='all'||r.lv===st.lv));}
function matches(){const q=st.q.trim().toLowerCase();return base().filter(r=>(!st.t||r.t===st.t)&&(!q||(r.a+' '+r.b).toLowerCase().includes(q)));}
function seg(id,key,opts){$(id).innerHTML=opts.map(([v,l])=>`<button data-v="${v}" class="${st[key]===v?'on':''}">${esc(l)}</button>`).join('');
 $(id).onclick=e=>{const v=e.target.dataset&&e.target.dataset.v;if(v===undefined)return;st[key]=v;st.t='';st.n=60;draw();};}
function chips(r,i){return r.g[i].map((x,j)=>{const o=r.g[1-i][j];return `<b class="${x>o?'on':''}">${x}</b>`}).join('');}
function mrow(r){const m=[r.rd,r.sf].filter(Boolean).join(' · ');
 const p=(i,n,c)=>`<div class="pl ${r.w===i+1?'win':''}"><div><span class="nm">${esc(n)}</span><small>${esc(c)}</small></div><div class="ch">${chips(r,i)}</div></div>`;
 return `<div class="mt"><div class="mh">${esc(m)}</div>${p(0,r.a,r.ac)}${p(1,r.b,r.bc)}</div>`;}
function draw(){
 seg('sx','sx',[['all',UI.all],['men',UI.men],['women',UI.women]]);
 seg('k','k',[['singles',UI.singles],['doubles',UI.doubles],['all',UI.all]]);
 seg('lv','lv',[['all',UI.all],['tour','Tour'],['challenger','Challenger'],['itf','ITF']]);
 const pool=base();const ts={};pool.forEach(r=>{const o=ts[r.t]||(ts[r.t]={n:0,d:'',lv:r.lv});o.n++;if(r.d>o.d)o.d=r.d;});
 const names=Object.keys(ts).sort((a,b)=>ts[b].d.localeCompare(ts[a].d)||a.localeCompare(b));
 if(st.t&&!ts[st.t])st.t='';
 $('t').innerHTML=`<option value="">${esc(UI.alltour)}</option>`+names.map(n=>`<option value="${esc(n)}" ${n===st.t?'selected':''}>${esc(n)} (${ts[n].n})</option>`).join('');
 const all=matches();$('cnt').textContent=all.length+' '+UI.matches;
 const shown=all.slice(0,st.n);const days={};
 shown.forEach(r=>{((days[r.d]=days[r.d]||{})[r.t]=days[r.d][r.t]||[]).push(r);});
 let h='';
 Object.keys(days).sort().reverse().forEach(d=>{
  let label=d;try{label=new Date(d+'T12:00:00').toLocaleDateString(UI.lang,{weekday:'long',day:'numeric',month:'long'});}catch(e){}
  h+=`<h2 class="dh">${esc(label)}</h2>`;
  Object.keys(days[d]).sort((a,b)=>{const x=days[d][a][0],y=days[d][b][0];return (LV[x.lv]-LV[y.lv])||a.localeCompare(b);}).forEach(t=>{
   const ms=days[d][t].sort((a,b)=>a.ro-b.ro);const tag=ms[0].tag?`<span class="tag">${esc(ms[0].tag)}</span>`:'';
   h+=`<section class="tg"><h3 class="th">${tag}<span>${esc(t)}</span></h3>${ms.map(mrow).join('')}</section>`;});});
 if(!h)h=`<p class="empty">${esc(UI.empty)}</p>`;
 if(all.length>shown.length)h+=`<button class="more" id="more">${esc(UI.more)}</button>`;
 $('list').innerHTML=h;const mb=$('more');if(mb)mb.onclick=()=>{st.n+=60;draw();};
 save();}
load();$('q').value=st.q;
$('t').onchange=e=>{st.t=e.target.value;st.n=60;draw();};
$('q').oninput=e=>{st.q=e.target.value;st.n=60;draw();};
draw();
"""


def results_page(results, tr, tx, lang):
    esc = html.escape
    data = prepare(results, tr)
    ui = {"all": tx["f_all"], "men": tx["f_men"], "women": tx["f_women"], "singles": tx["f_singles"],
          "doubles": tx["f_doubles"], "alltour": tx["f_alltour"], "matches": tx["f_matches"],
          "more": tx["f_more"], "empty": tx["empty"], "lang": lang}
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    ui_json = json.dumps(ui, ensure_ascii=False).replace("</", "<\\/")
    fallback = "".join(
        f'<p class="empty">{esc(r["a"])} – {esc(r["b"])} · {esc(r["t"])}</p>'
        for r in [x for x in data if x["k"] == "singles"][:20])
    return (f'<section class="page-h"><h1>{esc(tx["title"])}</h1><p>{esc(tx["lead"])}</p></section>'
            '<div class="filters">'
            '<div class="row"><div class="seg" id="sx"></div><div class="seg" id="k"></div></div>'
            '<div class="row"><div class="seg" id="lv"></div></div>'
            f'<div class="row"><select id="t" aria-label="{esc(tx["f_tournament"])}"></select>'
            f'<input id="q" type="search" placeholder="{esc(tx["f_player"])}" aria-label="{esc(tx["f_player"])}">'
            '<span class="count" id="cnt"></span></div></div>'
            f'<div id="list"><noscript>{fallback}</noscript></div>'
            f'<script id="data" type="application/json">{data_json}</script>'
            f'<script id="ui" type="application/json">{ui_json}</script>'
            f'<script>{JS}</script>')
