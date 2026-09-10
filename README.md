# Anime Idle Social

Robô de posts diários do Anime Idle: **Personagem** (um por dia) no Instagram (@animeidle) e no X (@AnimeIdle_).

Sem IA em tempo de execução. A peça é montada com a **arte real das poses do jogo**, o texto vem da
**Enciclopédia da Coleção** (revisada pelo Douglas) e o fundo é um dos mundos do PvE. Tudo é
determinístico a partir da data, então o post de qualquer dia pode ser reproduzido.

## Como funciona

- `bot/carta.py escolher` diz qual carta cai em qual dia. Ciclo de 152 dias a partir de 2026-09-09;
  cada ciclo embaralha a ordem com semente própria, então em 5 meses nenhuma carta repete.
- `bot/carta.py compor` monta a peça 1080x1350 (4:5, retrato do feed) (`posts/AAAA-MM-DD.jpg`). Pose: a mais compacta das
  três, que é a que o personagem domina (lição do anúncio do Ikki). Nome na cor da raridade.
- `bot/carta.py postar` publica: post no feed (4:5) e, logo depois, um **Story** 9:16 da mesma peça apontando pro feed (o Story só no Instagram; falha no Story não derruba o dia). O Instagram só aceita imagem por URL pública, por isso a imagem é
  commitada antes e servida pelo `raw.githubusercontent.com` deste repositório (que precisa ser público).
- `.github/workflows/carta-do-dia.yml` roda todo dia às 19:00 de Brasília. Também dá pra rodar na mão em
  **Actions → Carta do Dia → Run workflow**, com `dry_run` (não publica) e `slug` (forçar uma carta).

## Segredos (Settings → Secrets → Actions)

| Nome | O que é |
|---|---|
| `IG_ACCESS_TOKEN` | Token de longa duração do app Meta "Anime Idle Social" (API do Instagram com login do Instagram). |
| `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` | OAuth 1.0a do app no console.x.com. Enquanto não existirem, o X é pulado sem erro. |

O token do Instagram vale 60 dias. O robô renova a cada 7 e guarda o renovado **cifrado** em
`data/ig_token.enc` (chave derivada do token original, que fica só no secret; o arquivo pode ser público). Se algum dia a Meta recusar o
token, gere outro em developers.facebook.com → app → Instagram → Generate token e troque o secret.

## Custos

- Instagram: grátis.
- X: pré-pago, US$ 0,015 por post sem link (post com link custa US$ 0,20, por isso a legenda do X não
  tem URL e manda pro link da bio). US$ 5 de crédito dão quase um ano.

## Rodar local

```
pip install -r requirements.txt
python bot/carta.py compor --slug goku --saida /tmp/goku.jpg
python bot/carta.py legenda --slug goku
```

## Atualizar cartas

`tools/preparar_dados.py` regenera `data/cards.json` e `assets/bg/` a partir do repositório do jogo e do
`lore.json` da Enciclopédia. Poses novas entram copiando `assets/poses/<slug>_{0,1,2}.png` do jogo.
