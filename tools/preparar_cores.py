# -*- coding: utf-8 -*-
"""Gera data/cores.json: a cor de cada pose, a MESMA do cut-in do jogo (POSE_DB em
anime/data/poses.js, extraida da propria arte da habilidade).

E a cor do nome e do brilho atras do personagem na peca. Ate 24/09/2026 essa cor
vinha da raridade do catalogo, que nao existe mais como atributo do personagem
(toda carta sai de Comum a Mitica): regra do Mateus, a publicacao nao menciona
raridade, nem pela palavra nem pela cor.

Uso (da raiz deste repo): python tools/preparar_cores.py <pasta_do_jogo>
  <pasta_do_jogo> = um checkout do anime-idle (o live e o origin/main)
"""
import json
import os
import re
import sys

SRC = sys.argv[1]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

js = open(os.path.join(SRC, "anime", "data", "poses.js"), encoding="utf8").read()
cores = {m.group(1): re.findall(r"'(#[0-9a-fA-F]{6})'", m.group(2))
         for m in re.finditer(r"^  ([a-z_0-9]+): \[([^\]]*)\]", js, re.M)}
cards = json.load(open(os.path.join(ROOT, "data", "cards.json"), encoding="utf8"))
falta = [c["slug"] for c in cards if len(cores.get(c["slug"], [])) != 3]
assert not falta, f"sem as 3 cores no poses.js: {falta}"
out = {c["slug"]: cores[c["slug"]] for c in cards}
json.dump(out, open(os.path.join(ROOT, "data", "cores.json"), "w", encoding="utf8", newline="\n"),
          ensure_ascii=False, indent=1, sort_keys=True)
print(f"data/cores.json: {len(out)} personagens x 3 poses")
