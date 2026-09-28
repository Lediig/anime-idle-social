"""Vigia social (2026-09-28): le comentarios do Instagram (@animeidle) e mencoes do X
(@AnimeIdle_) e avisa a equipe no Discord (#chat-staff-2, por webhook) quando um
perfil da lista vigiada escreve qualquer coisa ou quando qualquer pessoa usa uma
palavra-chave juridica. Espelho do vigia do bot de tickets (anime-idle-tickets,
src/vigia.js): MESMA lista de palavras, mesma logica de palavra inteira sem acento.

Roda no GitHub Actions a cada 15 min (.github/workflows/vigia-social.yml). O que
ja foi visto fica em data/vigia_social.json, commitado pelo workflow.

Uso local / no Actions:
  python bot/vigia_social.py            # passada normal (avisa e grava)
  python bot/vigia_social.py --dry-run  # so imprime o que avisaria; nao grava
"""
import json
import os
import re
import sys
import unicodedata
import datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTADO = os.path.join(ROOT, "data", "vigia_social.json")

IG_API = "https://graph.instagram.com/v23.0"
IG_USER_ID = "17841447727327781"          # @animeidle
X_USERNAME = "AnimeIdle_"

# Quem o alerta menciona no Discord (ids de usuario). leddig.
AVISAR = ["180870799320678400"]
# Nossas proprias contas: o que a gente mesmo escreve nunca vira alerta.
PROPRIAS = ["animeidle", "AnimeIdle_"]

# Perfis vigiados (username do Instagram / do X, sem @, sem distincao de caixa).
# O .kaytto. do ticket-0275 nao tem perfil conhecido nas redes: preencher quando souber.
VIGIA = {
    "usuarios": [],
    # trechos de regex SEM acento e em minusculas; casam so como palavra inteira.
    # MANTER IGUAL a VIGIA.palavras de anime-idle-tickets/src/config.js.
    "palavras": [
        # juridico
        r"advogad\w*", "processo", "processos", "processar", r"processad\w*",
        "judicial", "extrajudicial", r"juridic\w*", "justica", "juiz", "juiza", "tribunal",
        "acao civel", "acao civil", "indenizacao", "danos morais", "notificacao extrajudicial",
        # consumidor
        "cdc", "codigo de defesa do consumidor", "defesa do consumidor", "direito do consumidor",
        "procon", "reclame aqui", "estorno", "chargeback",
        # direitos / propriedade intelectual
        "direitos", "meu direito", "meus direitos", "direito autoral", "direitos autorais",
        "copyright", "copy right", "licenca", "licencas", "licenciamento", r"licenciad\w*",
        "pirataria", "plagio", "denuncia", "denunciar",
    ],
}
EXCECOES = ["com licenca", "processo de", "em processo"]   # fala comum, nao juridico
MAX_VISTOS = 2000                                          # ids guardados por rede

REDE_NOME = {"instagram": "Instagram", "x": "X"}
VERMELHO, AMBAR = 0xED4245, 0xFAA61A


# ---------------------------------------------------------------- classificador
def _normalizar_com_mapa(texto):
    saida, mapa = [], []
    for i, ch in enumerate(str(texto or "")):
        limpo = "".join(c for c in unicodedata.normalize("NFD", ch.lower()) if not unicodedata.combining(c))
        for c in limpo:
            saida.append(c)
            mapa.append(i)
    return "".join(saida), mapa


def normalizar(texto):
    return _normalizar_com_mapa(texto)[0]


def _apagar_excecoes(norm):
    for frase in EXCECOES:
        norm = re.sub(r"(?<![a-z0-9])" + re.escape(frase) + r"(?![a-z0-9])", lambda m: " " * len(m.group(0)), norm)
    return norm


def motivo_de(texto, autor, regras, proprias=None):
    """Por que este texto merece alerta; None quando nao merece."""
    autor_n = normalizar(autor or "").strip().lstrip("@")
    if autor_n in [normalizar(p) for p in (proprias if proprias is not None else PROPRIAS)]:
        return None
    vigiado = autor_n in [normalizar(u).lstrip("@") for u in regras.get("usuarios", [])]

    original = str(texto or "")
    norm, mapa = _normalizar_com_mapa(original)
    alvo = _apagar_excecoes(norm)
    achadas = []
    for p in regras.get("palavras", []):
        for m in re.finditer(r"(?<![a-z0-9])(?:" + p + r")(?![a-z0-9])", alvo):
            if not m.group(0):
                continue
            trecho = original[mapa[m.start()]: mapa[m.end() - 1] + 1].lower()
            if trecho not in achadas:
                achadas.append(trecho)
    if not vigiado and not achadas:
        return None
    return {"vigiado": vigiado, "palavras": achadas}


# ---------------------------------------------------------------- alerta (webhook do Discord)
def montar_alerta(item, motivo, avisar=None):
    avisar = AVISAR if avisar is None else avisar
    rede = REDE_NOME.get(item["rede"], item["rede"])
    if motivo["vigiado"] and motivo["palavras"]:
        titulo = f"👁️ {rede}: perfil vigiado escreveu · palavras: {', '.join(motivo['palavras'])}"
    elif motivo["vigiado"]:
        titulo = f"👁️ {rede}: perfil vigiado escreveu"
    else:
        titulo = f"🔎 {rede}: palavra-chave: {', '.join(motivo['palavras'])}"
    descricao = (item.get("texto") or "").strip()[:1500] or "_(sem texto)_"
    embed = {
        "title": titulo[:256],
        "description": descricao,
        "color": VERMELHO if motivo["vigiado"] else AMBAR,
        "fields": [
            {"name": "Quem", "value": f"@{item.get('autor') or '?'}", "inline": True},
            {"name": "Onde", "value": rede, "inline": True},
            {"name": "Link", "value": item.get("link") or "-", "inline": False},
        ],
    }
    if item.get("quando"):
        embed["timestamp"] = _iso(item["quando"])
    return {
        "content": " ".join(f"<@{i}>" for i in avisar),
        "allowed_mentions": {"parse": [], "users": list(avisar)},
        "embeds": [embed],
    }


def _iso(s):
    """Instagram manda '+0000' (sem dois-pontos); o Discord quer ISO 8601 de verdade."""
    s = str(s)
    if re.search(r"[+-]\d{4}$", s):
        s = s[:-2] + ":" + s[-2:]
    return s


# ---------------------------------------------------------------- estado
def ler_estado(arq):
    if not os.path.exists(arq):
        return {"vistos": {}}
    return json.load(open(arq, encoding="utf8"))


def gravar_estado(arq, estado):
    os.makedirs(os.path.dirname(arq), exist_ok=True)
    json.dump(estado, open(arq, "w", encoding="utf8"), ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- passada
def varrer(leitores, avisar_fn, arq_estado, regras, dry_run=False, agora=None):
    """leitores: {rede: fn(estado) -> [item]}; item = {rede,id,autor,texto,link,quando}.
    O leitor recebe o MESMO dicionario de estado que sera gravado no fim (e onde
    o X guarda o user_id e le o since_id).
    Primeira passada de uma rede so marca o que existe (nao acorda a equipe com o
    historico inteiro). Rede que falha e pulada e reportada em `falhas`."""
    estado = ler_estado(arq_estado)
    vistos = estado.setdefault("vistos", {})
    r = {"redes": 0, "itens": 0, "novos": 0, "alertas": 0, "falhas": [], "primeira": []}

    for rede, ler in leitores.items():
        r["redes"] += 1
        try:
            itens = ler(estado)
        except Exception as e:  # noqa: BLE001 - uma rede fora do ar nao pode calar a outra
            print(f"vigia-social: {rede} falhou: {e}", file=sys.stderr)
            r["falhas"].append(rede)
            continue
        r["itens"] += len(itens)
        primeira = rede not in vistos
        ja = set(vistos.get(rede, []))
        novos = [i for i in itens if str(i["id"]) not in ja]
        if primeira:
            r["primeira"].append(rede)
        else:
            r["novos"] += len(novos)
            for item in novos:
                motivo = motivo_de(item.get("texto"), item.get("autor"), regras)
                if not motivo:
                    continue
                r["alertas"] += 1
                corpo = montar_alerta(item, motivo)
                if dry_run:
                    print("ALERTA:", json.dumps(corpo["embeds"][0], ensure_ascii=True)[:700])
                else:
                    avisar_fn(corpo)
        if not dry_run:
            lista = list(vistos.get(rede, [])) + [str(i["id"]) for i in novos]
            vistos[rede] = lista[-MAX_VISTOS:]

    if not dry_run:
        estado["ultima"] = (agora or dt.datetime.now(dt.timezone.utc)).isoformat()
        gravar_estado(arq_estado, estado)
    return r


# ---------------------------------------------------------------- tradutores (sem rede)
def itens_do_instagram(media):
    itens = []
    for m in media or []:
        link = m.get("permalink") or ""
        for c in (m.get("comments") or {}).get("data", []):
            itens.append({"rede": "instagram", "id": str(c["id"]), "autor": c.get("username") or "",
                          "texto": c.get("text") or "", "link": link, "quando": c.get("timestamp") or ""})
            for rp in (c.get("replies") or {}).get("data", []):
                itens.append({"rede": "instagram", "id": str(rp["id"]), "autor": rp.get("username") or "",
                              "texto": rp.get("text") or "", "link": link, "quando": rp.get("timestamp") or ""})
    return itens


def itens_do_x(resp):
    dados = (resp or {}).get("data") or []
    nomes = {u["id"]: u.get("username", "") for u in ((resp or {}).get("includes") or {}).get("users", [])}
    itens = []
    for t in dados:
        autor = nomes.get(t.get("author_id"), "")
        itens.append({"rede": "x", "id": str(t["id"]), "autor": autor, "texto": t.get("text") or "",
                      "link": f"https://x.com/{autor or 'i'}/status/{t['id']}", "quando": t.get("created_at") or ""})
    return itens


# ---------------------------------------------------------------- leitores (com rede)
def ler_instagram(estado=None, get=None, token=None):
    """Comentarios (+respostas) dos ultimos 12 posts. A API com login do Instagram nao
    traz `comments` expandido no /media (medido em 28/09/2026: veio 0 itens), entao
    pede `comments_count` e busca /{media}/comments so nos posts que tem algum."""
    if get is None:
        import requests

        def get(url, params):
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
    if token is None:
        from carta import token_atual  # mesmo token/renovacao do robo Carta do Dia
        token, _ = token_atual()
    media = get(f"{IG_API}/{IG_USER_ID}/media",
                {"fields": "id,permalink,timestamp,comments_count", "limit": 12, "access_token": token}).get("data", [])
    campos = "id,text,username,timestamp,replies.limit(20){id,text,username,timestamp}"
    for m in media:
        if int(m.get("comments_count") or 0) <= 0:
            continue
        m["comments"] = get(f"{IG_API}/{m['id']}/comments", {"fields": campos, "limit": 50, "access_token": token})
    return itens_do_instagram(media)


def _x_sessao():
    chaves = [os.environ.get(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")]
    if not all(chaves):
        raise RuntimeError("X: faltam chaves no ambiente")
    from requests_oauthlib import OAuth1Session
    return OAuth1Session(*chaves)


def ler_x(estado, sessao=None):
    """Mencoes a @AnimeIdle_ desde a ultima vista. Custo (pay-per-use, 09/2026):
    US$ 0,01 por mencao devolvida; passada sem mencao nova nao devolve nada.
    O user_id fica em `estado` (gravado pelo varrer) pra nao pagar users/me toda passada."""
    s = sessao or _x_sessao()
    uid = estado.get("x_user_id")
    if not uid:
        r = s.get("https://api.x.com/2/users/me", timeout=30)
        r.raise_for_status()
        uid = r.json()["data"]["id"]
        estado["x_user_id"] = uid
    params = {"max_results": 20, "tweet.fields": "created_at,author_id", "expansions": "author_id", "user.fields": "username"}
    vistos = estado.get("vistos", {}).get("x") or []
    if vistos:
        params["since_id"] = max(vistos, key=int)
    r = s.get(f"https://api.x.com/2/users/{uid}/mentions", params=params, timeout=30)
    r.raise_for_status()
    return itens_do_x(r.json())


def avisar_discord(corpo):
    import requests
    url = os.environ.get("DISCORD_WEBHOOK_VIGIA")
    if not url:
        raise RuntimeError("DISCORD_WEBHOOK_VIGIA nao definido")
    r = requests.post(url, json=corpo, timeout=30)
    r.raise_for_status()


# ---------------------------------------------------------------- cli
def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # console do Windows
    except Exception:  # noqa: BLE001
        pass
    dry = "--dry-run" in argv
    leitores = {}
    if os.environ.get("IG_ACCESS_TOKEN"):
        leitores["instagram"] = ler_instagram
    if os.environ.get("X_API_KEY"):
        leitores["x"] = ler_x
    if not leitores:
        print("vigia-social: sem credenciais de rede nenhuma; nada a fazer")
        return 0
    r = varrer(leitores, avisar_discord, ESTADO, VIGIA, dry_run=dry)
    print("vigia-social:", json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
