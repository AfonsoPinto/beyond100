"""Teste: a chave da Anthropic funciona e as legendas saem bem? (1 chamada, custo ~0 )."""
import os

import captions

print("Chave presente:", bool(os.environ.get("ANTHROPIC_API_KEY")), "| modelo:", captions.MODEL)
facts = {"tournament": "Sample Challenger Open", "p1": {"name": "Marco Ellison"}, "p2": {"name": "Luis Marandi"},
         "games": [[6, 3, 7], [4, 6, 5]], "winner": 1, "round": "Quarter-finals",
         "reasons": ["challenger", "quarterfinal", "upset", "comeback"], "rank_winner": 187, "rank_loser": 46}
print("\n--- Legenda (IA, se a chave funcionar; senão modelo simples) ---\n")
print(captions.make_caption("final", facts))
