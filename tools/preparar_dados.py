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

# WORLD_THEMES do jogo (anime/pve_view.js): mundo i+1 e o cenario Normal do tema, mundo i+41 o do Pesadelo.
TEMAS = [("naruto", "Vila Oculta da Folha"), ("dragonball", "Ermos do Torneio"), ("onepiece", "Porto dos Piratas"),
         ("konosuba", "Praça dos Aventureiros"), ("demonslayer", "Montanha Nevada"), ("mha", "Domo de Desastres"),
         ("bleach", "Deserto de Hueco Mundo"), ("aot", "Distrito da Muralha"), ("jujutsukaisen", "Cruzamento Assombrado"),
         ("sao", "Castelo Flutuante"), ("inuyasha", "Floresta do Poço Sagrado"), ("onepunchman", "Cidade em Ruínas"),
         ("hunterxhunter", "Portão da Mansão Sombria"), ("chainsawman", "Viela dos Demônios"), ("deathnote", "Telhados do Crepúsculo"),
         ("evangelion", "Cidade-Fortaleza"), ("rezero", "Planície da Névoa"), ("frieren", "Vila do Grande Herói"),
         ("yuyuhakusho", "Arena das Trevas"), ("overlord", "Grande Tumba de Mármore"), ("jojo", "Telhados do Cairo"),
         ("sevendeadlysins", "Colina da Taverna"), ("mobpsycho", "Parque do Brócolis Colossal"), ("blackclover", "Ossada do Demônio Ancestral"),
         ("goblinslayer", "Caverna dos Goblins"), ("berserk", "Colina do Eclipse"), ("tokyoghoul", "Beco dos Devoradores"),
         ("samuraix", "Pátio do Dojo"), ("hokutonoken", "Deserto Sem Lei"), ("spyxfamily", "Academia de Elite"),
         ("drstone", "Selva Petrificada"), ("cowboybebop", "Ruas de Marte"), ("sailormoon", "Torre sob a Lua Cheia"),
         ("saintseiya", "Santuário dos Doze Templos"), ("codegeass", "Metrópole Dividida"), ("tensura", "Caverna do Dragão Selado"),
         ("ghibli", "Estrada da Floresta Encantada"), ("umaruchan", "Quarto do Kotatsu"), ("yugioh", "Arena de Duelos"),
         ("fma", "Portal da Verdade")]
# nome do anime na carta -> chave do tema (os que nao batem pela normalizacao simples)
APELIDO = {"attackontitan": "aot", "myheroacademia": "mha", "swordartonline": "sao", "slimedattaken": "tensura",
           "fullmetalalchemist": "fma", "mobpsycho100": "mobpsycho"}


def chave(anime):
    k = "".join(ch for ch in anime.lower() if ch.isalnum())
    return APELIDO.get(k, k)


chaves = {t[0] for t in TEMAS}
sem_tema = sorted({c["anime"] for c in out if chave(c["anime"]) not in chaves})
assert not sem_tema, f"anime sem mundo: {sem_tema}"
animes = {a: {"tema": chave(a), "mundo": dict(TEMAS)[chave(a)]} for a in sorted({c["anime"] for c in out})}
json.dump(animes, open(os.path.join(ROOT, "data/animes.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)

for f in os.listdir(os.path.join(ROOT, "assets/bg")):
    os.remove(os.path.join(ROOT, "assets/bg", f))
n = 0
for i, (k, _) in enumerate(TEMAS):
    for letra, w in (("a", i + 1), ("b", i + 41)):
        p = os.path.join(SRC, f"assets/bg/world{w}.png")
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB")
        W, H = im.size  # fonte 1344x768: recorte central 4:5 (614x768) esticado pra 1080x1350
        lw = int(H * 0.8)
        im = im.crop(((W - lw) // 2, 0, (W - lw) // 2 + lw, H)).resize((1080, 1350), Image.LANCZOS)
        im.save(os.path.join(ROOT, f"assets/bg/{k}_{letra}.jpg"), "JPEG", quality=86)
        n += 1
print("cartas", len(out), "animes", len(animes), "bgs", n, "lore max", max(len(o["lore"]) for o in out))
