# -*- coding: utf-8 -*-
"""Prepara data/cards.json e assets/bg a partir das fontes do jogo (uso local, uma vez).

Fontes: anime/data/cards.js do live (origin/main) + lore.json da Enciclopedia.
Rodar de dentro da raiz do repo: python tools/preparar_dados.py <pasta_src> <lore.json>
"""
import json, os, sys
from PIL import Image

SRC, LORE = sys.argv[1], sys.argv[2]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

s = open(os.path.join(SRC, "anime/data/cards.js"), encoding="utf8").read()
cards = json.loads(s[s.index("["):s.rindex("]") + 1])
lore = json.load(open(LORE, encoding="utf8"))
out = [{"slug": c["slug"], "name": c["name"], "anime": c["anime"], "rarity": c["rarity"], "lore": lore[c["slug"]]}
       for c in sorted(cards, key=lambda c: c["slug"])]
assert len(out) == 152 and all(o["lore"] for o in out)
json.dump(out, open(os.path.join(ROOT, "data/cards.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)

worlds = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35, 37, 39, 41, 45, 50, 55]
n = 0
for w in worlds:
    p = os.path.join(SRC, f"assets/bg/world{w}.png")
    if not os.path.exists(p):
        continue
    im = Image.open(p).convert("RGB")
    W, H = im.size
    side = min(W, H)
    im = im.crop(((W - side) // 2, 0, (W - side) // 2 + side, side)).resize((1080, 1080), Image.LANCZOS)
    im.save(os.path.join(ROOT, f"assets/bg/world{w}.jpg"), "JPEG", quality=86)
    n += 1
print("cartas", len(out), "bgs", n, "lore max", max(len(o["lore"]) for o in out), "nome max", max(len(o["name"]) for o in out))
