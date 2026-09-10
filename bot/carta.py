# -*- coding: utf-8 -*-
"""Personagem (do dia): escolhe a carta, compoe a peca 1080x1350 (4:5) e publica no Instagram (e no X, se houver chaves).

Sem IA em tempo de execucao: arte real das poses do jogo, texto da Enciclopedia da Colecao,
fundo dos mundos do PvE. Tudo deterministico a partir da data.

Uso:
  python bot/carta.py compor  [--data 2026-09-09] [--slug goku] [--saida posts/x.jpg]
  python bot/carta.py postar  [--data ...] [--slug ...] [--dry-run]
  python bot/carta.py testar-token
  python bot/carta.py legenda [--slug ...]
"""
import argparse, base64, datetime as dt, hashlib, io, json, os, random, sys, time
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, "assets", *p)
EPOCH = dt.date(2026, 9, 9)          # dia 0 do ciclo
TZ = dt.timezone(dt.timedelta(hours=-3))  # Brasilia
IG_API = "https://graph.instagram.com/v23.0"
IG_USER_ID = "17841447727327781"      # @animeidle (id da conta profissional no app Anime Idle Social)
RAW_BASE = "https://raw.githubusercontent.com/Lediig/anime-idle-social/main"

RAR_NOME = {1: "Comum", 2: "Incomum", 3: "Raro", 4: "Épico", 5: "Lendário", 6: "Mítico"}
RAR_COR = {1: "#b7a6a8", 2: "#63d29a", 3: "#5ca4e0", 4: "#c07bff", 5: "#ffcf5c", 6: "#ff5c6a"}

CARDS = json.load(open(os.path.join(ROOT, "data", "cards.json"), encoding="utf8"))
ANIMES = json.load(open(os.path.join(ROOT, "data", "animes.json"), encoding="utf8"))  # anime -> {tema, mundo}


def fundo(anime, ciclo):
    """O mundo do PvE do MESMO anime da carta; alterna o cenario Normal (a) e o Pesadelo (b) a cada ciclo."""
    tema = ANIMES[anime]["tema"]
    for letra in ("ab"[ciclo % 2], "a", "b"):
        if os.path.exists(A("bg", f"{tema}_{letra}.jpg")):
            return f"{tema}_{letra}.jpg"
    raise SystemExit(f"sem fundo pro tema {tema}")


# ---------------------------------------------------------------- escolha
def hoje():
    return dt.datetime.now(TZ).date()


def pulados():
    """data/pular.txt: um slug por linha (arte em troca, personagem fora de hora...). '#' comenta."""
    p = os.path.join(ROOT, "data", "pular.txt")
    if not os.path.exists(p):
        return set()
    out = set()
    for linha in open(p, encoding="utf8"):
        s = linha.split("#", 1)[0].strip().lower()
        if s:
            out.add(s)
    return out


def carta_do_dia(data=None, slug=None):
    """Ciclo pelas cartas ELEGIVEIS (fora as de pular.txt); cada ciclo embaralha com semente propria.
    Trocar o pular.txt reordena os dias seguintes, nunca os passados (que ficam em state.json)."""
    data = data or hoje()
    dias = (data - EPOCH).days
    if slug is not None:
        card = next(c for c in CARDS if c["slug"] == slug)
        ciclo = 0
    else:
        fora = pulados()
        # embaralha as 152 e SO ENTAO tira as puladas: a ordem das outras nao muda quando a lista muda,
        # quem sai apenas abre a vaga pro seguinte
        n_eleg = len([c for c in CARDS if c["slug"] not in fora]) or len(CARDS)
        ciclo, idx = divmod(dias, n_eleg)
        ordem = list(range(len(CARDS)))
        random.Random(1000 + ciclo).shuffle(ordem)
        eleg = [CARDS[i] for i in ordem if CARDS[i]["slug"] not in fora] or [CARDS[i] for i in ordem]
        card = eleg[idx]
    return dict(card, data=data.isoformat(), ciclo=ciclo, pose=pose_compacta(card["slug"]),
                bg=fundo(card["anime"], ciclo), mundo=ANIMES[card["anime"]]["mundo"])


def calendario(dias=45, data=None):
    """Escreve CALENDARIO.md com os proximos posts (o GitHub renderiza as poses)."""
    data = data or hoje()
    fora = pulados()
    linhas = ["# Agenda de Personagens", "",
              f"Gerado em {dt.datetime.now(TZ):%d/%m/%Y %H:%M} (Brasília). Post diário às 19:00.",
              "Pra tirar alguém da fila, edite `data/pular.txt` (um slug por linha) e o calendário se refaz.", "",
              f"Fora da fila agora: {', '.join(sorted(fora)) if fora else 'ninguém'}.", "",
              "| Data | Arte | Carta | Anime (fundo: mundo do PvE) | Raridade |", "|---|---|---|---|---|"]
    for i in range(dias):
        c = carta_do_dia(data + dt.timedelta(days=i))
        d = data + dt.timedelta(days=i)
        linhas.append(f"| {d:%d/%m} ({'seg ter qua qui sex sáb dom'.split()[d.weekday()]}) "
                      f"| <img src=\"assets/poses/{c['slug']}_{c['pose']}.png\" width=\"128\"> "
                      f"| **{c['name']}** `{c['slug']}` | {c['anime']} ({c['mundo']}) | {RAR_NOME[c['rarity']]} |")
    open(os.path.join(ROOT, "CALENDARIO.md"), "w", encoding="utf8", newline="\n").write("\n".join(linhas) + "\n")
    calendario_html(dias, data, fora)
    return linhas


def calendario_html(dias, data, fora):
    """Versao local (CALENDARIO.html): abre no navegador direto da pasta, sem precisar do GitHub."""
    e = estado()
    feitos = {p["data"]: p for p in e["posts"]}
    cel = []
    for i in range(dias):
        d = data + dt.timedelta(days=i)
        c = carta_do_dia(d)
        semana = "seg ter qua qui sex sáb dom".split()[d.weekday()]
        ok = feitos.get(d.isoformat())
        cel.append(f"""<div class="c r{c['rarity']}{' ok' if ok else ''}">
  <div class="d">{d:%d/%m} <small>{semana}</small>{' <b>✔ postado</b>' if ok else ''}</div>
  <img src="assets/poses/{c['slug']}_{c['pose']}.png" alt="">
  <div class="n">{c['name']}</div><div class="a">{c['anime']}</div>
  <div class="m">{RAR_NOME[c['rarity']]} · fundo: {c['mundo']}</div><div class="s">{c['slug']}</div></div>""")
    fora_txt = ", ".join(sorted(fora)) if fora else "ninguém"
    html = f"""<!doctype html><meta charset="utf-8"><title>Agenda de Personagens</title>
<style>
body{{font-family:system-ui,Segoe UI,Arial;background:#0f0d1a;color:#eee;margin:0;padding:24px}}
h1{{margin:0 0 6px}} p{{color:#bbb;margin:4px 0}} code{{background:#222;padding:1px 6px;border-radius:4px}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px;margin-top:18px}}
.c{{background:#1b1730;border:2px solid #2a2545;border-radius:12px;padding:10px;text-align:center}}
.c.ok{{opacity:.55}} .c img{{width:160px;height:90px;object-fit:contain;image-rendering:pixelated;margin:6px 0}}
.d{{font-weight:700;color:#fff}} .d small{{color:#999;font-weight:400}} .d b{{color:#63d29a;font-weight:600;font-size:12px}}
.n{{font-size:20px;font-weight:800}} .a{{color:#ccc}} .m{{font-size:12px;color:#999;margin-top:4px}} .s{{font-size:11px;color:#666;font-family:monospace}}
.r2 .n{{color:#63d29a}} .r3 .n{{color:#5ca4e0}} .r4 .n{{color:#c07bff}} .r5 .n{{color:#ffcf5c}} .r6 .n{{color:#ff5c6a}}
</style>
<h1>Agenda de Personagens</h1>
<p>Gerada em {dt.datetime.now(TZ):%d/%m/%Y %H:%M}. Post diário às 19:00 (Brasília). Próximos {dias} dias.</p>
<p>Pra tirar alguém da fila: escreva o <code>slug</code> (texto cinza de cada cartão) numa linha do <code>pular.txt</code> e clique em "Atualizar agenda e enviar". Fora da fila agora: <b>{fora_txt}</b>.</p>
<div class="g">{''.join(cel)}</div>"""
    open(os.path.join(ROOT, "CALENDARIO.html"), "w", encoding="utf8", newline="\n").write(html)


def pose_compacta(slug):
    """A pose com a menor caixa: e a que o PERSONAGEM domina, nao o efeito (licao do anuncio do Ikki)."""
    def area(i):
        bb = Image.open(A("poses", f"{slug}_{i}.png")).convert("RGBA").getbbox()
        return (bb[2] - bb[0]) * (bb[3] - bb[1]) if bb else 10**9
    return min(range(3), key=area)


# ---------------------------------------------------------------- composicao
def fonte(tam):
    return ImageFont.truetype(A("Bangers-Regular.ttf"), tam)


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def texto(draw, xy, s, tam, cor, contorno=(0, 0, 0), esp=0, largura_max=None, ancora="mm"):
    f = fonte(tam)
    if largura_max:
        while tam > 24 and draw.textlength(s, font=f) > largura_max:
            tam -= 2
            f = fonte(tam)
    draw.text(xy, s, font=f, fill=cor, anchor=ancora, stroke_width=esp, stroke_fill=contorno)
    return f


def pose_grande(slug, i, alvo_alt):
    im = Image.open(A("poses", f"{slug}_{i}.png")).convert("RGBA")
    bb = im.getbbox()
    im = im.crop(bb)
    fator = max(1, min(alvo_alt // im.height, 1080 * 0.82 // im.width))
    return im.resize((im.width * int(fator), im.height * int(fator)), Image.NEAREST)


TITULO = "PERSONAGEM"          # titulo da peca (era "CARTA DO DIA" ate 09/09)
# Dois formatos com a mesma composicao. feed: 4:5, inteiro no post e quase sem corte na grade.
# story: 9:16; o Instagram cobre ~250px no topo (nome do perfil) e ~250px embaixo (resposta), entao tudo
# fica dentro da faixa segura e o rodape ganha a chamada pro feed.
FORMATOS = {
    "feed":  dict(W=1080, H=1350, topo=18,  chao=1050, pose=700, faixa_topo=290, logo=200),
    "story": dict(W=1080, H=1920, topo=270, chao=1330, pose=760, faixa_topo=600, logo=300),
}


def compor(card, formato="feed"):
    F = FORMATOS[formato]
    W, H, CHAO = F["W"], F["H"], F["chao"]
    cor = hexrgb(RAR_COR[card["rarity"]])
    bg = Image.open(A("bg", card["bg"])).convert("RGB")
    if bg.size != (W, H):  # cobre o quadro cortando o que sobrar (o fundo e 4:5; no story perde as laterais)
        s = max(W / bg.width, H / bg.height)
        bg = bg.resize((round(bg.width * s), round(bg.height * s)), Image.LANCZOS)
        bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = bg.filter(ImageFilter.GaussianBlur(1.2))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (8, 6, 16)), 0.30)
    # brilho radial na cor da raridade atras do personagem
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    cy = CHAO - 270
    for r in range(480, 0, -12):
        a = int(150 * (1 - r / 480) ** 1.6)
        g.ellipse((W // 2 - r, cy - r * 0.9, W // 2 + r, cy + r * 0.9), fill=cor + (a,))
    glow = glow.filter(ImageFilter.GaussianBlur(28))
    out = Image.alpha_composite(bg.convert("RGBA"), glow)
    # faixas escuras (finas, pra nao comer o fundo)
    faixa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(faixa)
    fd.rectangle((0, 0, W, F["faixa_topo"]), fill=(6, 4, 14, 150))
    fd.rectangle((0, CHAO + 20, W, H), fill=(6, 4, 14, 190))
    out = Image.alpha_composite(out, faixa.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(out)
    # logo (emblema quadrado, transparente) + titulo
    logo = Image.open(A("logo.png")).convert("RGBA")
    logo = logo.resize((int(F["logo"] * logo.width / logo.height), F["logo"]), Image.LANCZOS)
    out.alpha_composite(logo, (W // 2 - logo.width // 2, F["topo"]))
    d = ImageDraw.Draw(out)
    texto(d, (W // 2, F["topo"] + F["logo"] + 36), TITULO, 60, (255, 255, 255), esp=5)
    # personagem
    p = pose_grande(card["slug"], card["pose"], F["pose"])
    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).ellipse((W // 2 - p.width // 2 - 10, CHAO - 12 - 26, W // 2 + p.width // 2 + 10, CHAO - 12 + 26), fill=(0, 0, 0, 120))
    out.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(12)))
    out.alpha_composite(p, (W // 2 - p.width // 2, CHAO - p.height))
    d = ImageDraw.Draw(out)
    # placa: nome, anime, selo de raridade
    y_nome, y_linha = CHAO + 100, CHAO + 182
    texto(d, (W // 2, y_nome), card["name"].upper(), 112, cor, esp=7, largura_max=980)
    rar = Image.open(A("icons", f"rar_{card['rarity']}.png")).convert("RGBA").resize((44, 44), Image.LANCZOS)
    linha = f"{card['anime']}  ·  {RAR_NOME[card['rarity']].upper()}"
    f = fonte(44)
    lw = d.textlength(linha, font=f) + 56
    x0 = W // 2 - lw // 2
    out.alpha_composite(rar, (int(x0), y_linha - 22))
    d = ImageDraw.Draw(out)
    d.text((x0 + 56, y_linha), linha, font=f, fill=(255, 255, 255), anchor="lm", stroke_width=4, stroke_fill=(0, 0, 0))
    if formato == "story":
        # so o site, dentro da faixa segura (acima dos ~250px que o Instagram cobre com a caixa de resposta)
        texto(d, (W // 2, CHAO + 290), "anime-idle.com", 36, cor, esp=4)
    else:
        texto(d, (W - 28, H - 24), "anime-idle.com", 30, (255, 255, 255, 210), esp=3, ancora="rm")
    return out.convert("RGB")


def hashtag_anime(anime):
    return "#" + "".join(ch for ch in anime.title() if ch.isalnum())


def legenda(card, rede="ig"):
    nome, anime, rar = card["name"], card["anime"], RAR_NOME[card["rarity"]]
    tags = f"#AnimeIdle {hashtag_anime(anime)} #anime #idlegame #gacha #jogobrasileiro"
    if rede == "x":
        # sem URL: post com link custa 13x mais na API do X. O link fica na bio.
        cabeca = f"Personagem: {nome} ({anime}, {rar})\n\n{card['lore']}"
        for rabo in (f"\n\nJogue de graça no navegador, link na bio.\n#AnimeIdle {hashtag_anime(anime)}",
                     f"\n\n#AnimeIdle {hashtag_anime(anime)}", "\n\n#AnimeIdle", ""):
            if len(cabeca + rabo) <= 280:
                return cabeca + rabo
        return cabeca[:277] + "..."
    return (f"Personagem: {nome} ({anime}) · {rar}\n\n{card['lore']}\n\n"
            f"Colecione {nome} e mais de 150 heróis de anime. Jogue de graça no navegador: anime-idle.com\n"
            f"Play free in your browser: anime-idle.com\n\n{tags}")


# ---------------------------------------------------------------- token do Instagram
def _fernet():
    from cryptography.fernet import Fernet
    semente = os.environ["IG_ACCESS_TOKEN"]  # o token original, nunca muda: serve de chave
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("chave:" + semente).encode()).digest()))


TOKEN_ENC = os.path.join(ROOT, "data", "ig_token.enc")  # token renovado, cifrado; o workflow commita este arquivo


def token_atual():
    """Token vigente: o renovado (data/ig_token.enc, cifrado com chave derivada do original) ou o original do secret.
    O arquivo pode ficar num repositorio publico: sem o secret original nao se abre."""
    original = os.environ["IG_ACCESS_TOKEN"]
    if not os.path.exists(TOKEN_ENC):
        return original, None
    try:
        dados = json.loads(_fernet().decrypt(open(TOKEN_ENC, "rb").read()).decode())
        return dados["token"], dt.datetime.fromisoformat(dados["em"])
    except Exception as e:  # arquivo de outro secret ou corrompido: volta ao original e avisa
        print("aviso: ig_token.enc ilegivel, usando o token original:", e)
        return original, None


def guardar_token(token):
    dados = json.dumps({"token": token, "em": dt.datetime.now(dt.timezone.utc).isoformat()}).encode()
    open(TOKEN_ENC, "wb").write(_fernet().encrypt(dados))


def renovar_se_preciso(token, em):
    """Token de longa duracao vale 60 dias; renova a cada 7 (a API exige que tenha ao menos 24h)."""
    import requests
    if em is not None and (dt.datetime.now(dt.timezone.utc) - em).days < 7:
        return token
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=30)
    if r.status_code != 200:
        print("aviso: renovacao falhou (segue com o token atual):", r.text[:300])
        return token
    novo = r.json()["access_token"]
    guardar_token(novo)
    print("token renovado; vale por", r.json().get("expires_in", 0) // 86400, "dias")
    return novo


def testar_token():
    import requests
    token, em = token_atual()
    r = requests.get(f"{IG_API}/me", params={"fields": "user_id,username,account_type", "access_token": token}, timeout=30)
    print(r.status_code, r.text[:400])
    r.raise_for_status()
    assert r.json().get("username") == "animeidle", "token nao e do @animeidle"
    if em:
        print("token renovado pela ultima vez em", em.date())


# ---------------------------------------------------------------- publicacao
def esperar_url(url, tent=24):
    import requests
    for _ in range(tent):
        r = requests.get(url, timeout=30)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
            return True
        time.sleep(5)
    raise SystemExit(f"imagem nao ficou publica: {url}")


def postar_instagram(url_img, txt, token, story=False):
    """Feed (com legenda) ou Story (media_type=STORIES, sem legenda; a API nao poe figurinha de link)."""
    import requests
    dados = {"image_url": url_img, "access_token": token}
    if story:
        dados["media_type"] = "STORIES"
    else:
        dados["caption"] = txt
    r = requests.post(f"{IG_API}/{IG_USER_ID}/media", data=dados, timeout=60)
    if r.status_code != 200:
        raise SystemExit("IG media: " + r.text)
    cid = r.json()["id"]
    for _ in range(20):
        s = requests.get(f"{IG_API}/{cid}", params={"fields": "status_code,status", "access_token": token}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise SystemExit("IG container: " + json.dumps(s))
        time.sleep(3)
    r = requests.post(f"{IG_API}/{IG_USER_ID}/media_publish", data={"creation_id": cid, "access_token": token}, timeout=60)
    if r.status_code != 200:
        raise SystemExit("IG publish: " + r.text)
    return r.json()["id"]


def postar_x(caminho_img, txt):
    """Publica no X por OAuth 1.0a. So roda se as 4 chaves existirem no ambiente."""
    chaves = [os.environ.get(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")]
    if not all(chaves):
        print("X: sem chaves, pulando")
        return None
    from requests_oauthlib import OAuth1Session
    s = OAuth1Session(*chaves)
    with open(caminho_img, "rb") as f:
        r = s.post("https://upload.twitter.com/1.1/media/upload.json", files={"media": f}, timeout=120)
    if r.status_code not in (200, 201):
        print("X upload falhou:", r.status_code, r.text[:300])
        return None
    mid = r.json()["media_id_string"]
    r = s.post("https://api.x.com/2/tweets", json={"text": txt, "media": {"media_ids": [mid]}}, timeout=60)
    if r.status_code not in (200, 201):
        print("X post falhou:", r.status_code, r.text[:300])
        return None
    return r.json()["data"]["id"]


def estado():
    p = os.path.join(ROOT, "state.json")
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else {"posts": []}


def gravar_estado(e):
    json.dump(e, open(os.path.join(ROOT, "state.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["compor", "postar", "testar-token", "legenda", "escolher", "calendario"])
    ap.add_argument("--data")
    ap.add_argument("--slug")
    ap.add_argument("--saida")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fase", choices=["imagem", "publicar"], default=None,
                    help="postar em duas fases: 'imagem' gera e grava; 'publicar' le a imagem ja no repo e publica")
    a = ap.parse_args()
    data = dt.date.fromisoformat(a.data) if a.data else hoje()
    card = carta_do_dia(data, a.slug)

    if a.cmd == "calendario":
        for l in calendario(data=data)[8:]:
            cel = l.split("|")
            print(cel[1].strip(), cel[3].strip(), "|", cel[4].strip(), "|", cel[5].strip())
        return
    if a.cmd == "escolher":
        print(json.dumps({k: card[k] for k in ("data", "slug", "name", "anime", "rarity", "pose", "bg")}, ensure_ascii=False))
        return
    if a.cmd == "legenda":
        print(legenda(card)); print("\n--- X ---\n"); print(legenda(card, "x"))
        return
    if a.cmd == "testar-token":
        testar_token(); print("token ok"); return

    saida = a.saida or os.path.join(ROOT, "posts", f"{card['data']}.jpg")
    saida_story = os.path.splitext(saida)[0] + "-story.jpg"
    if a.cmd == "compor" or a.fase in (None, "imagem"):
        os.makedirs(os.path.dirname(saida), exist_ok=True)
        compor(card).save(saida, "JPEG", quality=92, optimize=True)
        compor(card, "story").save(saida_story, "JPEG", quality=92, optimize=True)
        print("imagem:", saida, os.path.getsize(saida) // 1024, "KB; story:", os.path.getsize(saida_story) // 1024, "KB")
        if a.cmd == "compor" or a.fase == "imagem":
            return

    # publicar (cada rede so uma vez por dia: um dia pela metade, ex. X sem chaves de manha, completa depois)
    e = estado()
    reg = next((p for p in e["posts"] if p["data"] == card["data"]), None) or {"data": card["data"], "slug": card["slug"]}
    tem_x = all(os.environ.get(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"))
    falta_ig, falta_x = not reg.get("ig"), tem_x and not reg.get("x")
    falta_story = not reg.get("story") and "story" not in reg  # story so uma vez; se falhar fica None e nao repete
    if not (falta_ig or falta_x or falta_story) and not a.dry_run:
        print("ja postado hoje nas redes disponiveis, nada a fazer"); return
    url = f"{RAW_BASE}/posts/{card['data']}.jpg"
    url_story = f"{RAW_BASE}/posts/{card['data']}-story.jpg"
    txt_ig, txt_x = legenda(card), legenda(card, "x")
    if a.dry_run:
        print("DRY RUN\n", url, "\n", url_story, "\n", txt_ig, "\n--- X ---\n", txt_x)
        testar_token(); return
    token = None
    if falta_ig or falta_story:
        token, em = token_atual()
        token = renovar_se_preciso(token, em)
    if falta_ig:
        esperar_url(url)
        reg["ig"] = postar_instagram(url, txt_ig, token)
        print("instagram ok:", reg["ig"])
    if falta_story and reg.get("ig"):
        # o story aponta pro feed, entao so sai depois dele; falha no story nao derruba o dia
        try:
            esperar_url(url_story)
            reg["story"] = postar_instagram(url_story, "", token, story=True)
            print("story ok:", reg["story"])
        except SystemExit as err:
            reg["story"] = None
            print("aviso: story falhou:", err)
    if falta_x:
        reg["x"] = postar_x(saida, txt_x)
        if reg["x"]:
            print("x ok:", reg["x"])
    e["posts"] = [p for p in e["posts"] if p["data"] != card["data"]] + [reg]
    gravar_estado(e)


if __name__ == "__main__":
    main()
