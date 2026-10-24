"""Legendas de Instagram geradas com a Anthropic API (Haiku).

Regras de segurança:
- a IA só recebe dados públicos do cartão e é instruída a não inventar nada;
- todo o número da legenda tem de existir nos dados; se não, usa-se a legenda-modelo;
- sem chave ou com erro de rede, usa-se a legenda-modelo (o workflow nunca falha por causa disto).
"""
import json
import os
import re

import requests

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("CAPTION_MODEL", "claude-haiku-5-5")
SYSTEM = (
    "You write Instagram captions for Beyond100, a tennis account about Challenger, ITF and WTA "
    "tennis beyond the top 100. Tone: modern, concise, knowledgeable, never hype-y.\n"
    "Rules: use ONLY the facts in the JSON you are given. Never invent names, scores, rankings, "
    "records, quotes or dates. Max 3 short lines, then one question to the reader, then 3-5 "
    "relevant hashtags (e.g. #tennis #challengertennis). At most 1 emoji. English. "
    "Every number you write must appear literally in the JSON. Never compute anything (no differences, "
    "totals, percentages, counts of sets or games). Use the ranking_gap value if given, otherwise do not mention gaps. "
    "Do not describe events that are not in the JSON: no match points, breaks, aces, injuries, serving, "
    "crowd, emotions, records, streaks or career context. Stick to who won, the score, the round, the "
    "tournament, rankings and the listed reasons. Output the caption text only."
)


def _name(p):
    return (p or {}).get("name", "")


def fallback(kind, facts):
    tag = "#tennis #challengertennis #beyond100"
    if kind == "final":
        w = facts.get("winner")
        if w in (1, 2):
            win, los = facts["p%d" % w], facts["p%d" % (3 - w)]
            score = "  ".join(f"{a}-{b}" for a, b in zip(facts["games"][w - 1], facts["games"][2 - w]))
            why = facts.get("reasons") or []
            extra = ("Upset alert. " if "upset" in why else "") + ("A comeback win. " if "comeback" in why else "")
            stage = {"final": "in the final", "semifinal": "in the semifinals", "quarterfinal": "in the quarterfinals"}
            where = next((stage[r] for r in why if r in stage), "")
            return (f"{extra}{_name(win)} beats {_name(los)} {score} {where}.\n{facts.get('tournament', '')}\n"
                    f"Who impressed you most today?\n{tag}").replace("  ", " ").replace(" .", ".").strip()
    if kind == "upset":
        return (f"{facts.get('headline', 'Upset alert.')}\n{facts.get('context', '')}\n"
                f"Did you see this coming?\n{tag} #upset").strip()
    if kind == "weekly":
        fin = facts.get("finals") or []
        lines = [f"{f['winner']} won {f['tournament']}." for f in fin[:2]]
        return ("The week beyond the top 100.\n" + " ".join(lines) + f"\n{facts.get('matches', 0)} matches tracked. "
                f"Which result surprised you most?\n{tag} #weeklyrecap").strip()
    if kind == "rising":
        return f"A new name inside the top 100.\nWho's next?\n{tag} #rising"
    return f"{tag}"


def _numbers(text):
    return set(re.findall(r"\d+", text))


LINK_LINE = "Full results: link in bio"


def _finish(text):
    """Acrescenta 'Full results: link in bio' antes das hashtags (uma só vez)."""
    text = (text or "").strip()
    if "link in bio" in text.lower():
        return text
    lines = text.split("\n")
    if lines and lines[-1].lstrip().startswith("#"):
        return "\n".join(lines[:-1]).rstrip() + "\n" + LINK_LINE + "\n\n" + lines[-1]
    return text + "\n" + LINK_LINE


def make_caption(kind, facts):
    return _finish(_make_caption(kind, facts))


def _ask(key, payload, extra=""):
    r = requests.post(
        API_URL,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": 300, "system": SYSTEM + extra,
              "messages": [{"role": "user", "content": payload}]},
        timeout=30,
    )
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text").strip()


def _make_caption(kind, facts):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return fallback(kind, facts)
    payload = json.dumps({"kind": kind, "facts": facts}, ensure_ascii=False)
    allowed = _numbers(payload)
    extra = ""
    for attempt in (1, 2):                      # uma segunda tentativa, mais restrita, antes de usar o modelo simples
        try:
            text = _ask(key, payload, extra)
        except Exception as e:  # rede, quota, chave inválida...
            print("Legenda: IA indisponível, a usar modelo:", type(e).__name__)
            return fallback(kind, facts)
        bad = sorted(_numbers(text) - allowed)
        if text and not bad:
            return text
        print(f"Legenda (tentativa {attempt}): números fora dos dados {bad}.")
        extra = (" IMPORTANT: your previous answer used numbers not in the JSON (" + ", ".join(bad) +
                 "). Rewrite without them; do not do any arithmetic.")
    print("Legenda: a usar modelo simples.")
    return fallback(kind, facts)


def save_caption(png_path, kind, facts):
    path = os.path.splitext(png_path)[0] + ".txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(make_caption(kind, facts))
    return path
