import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))
import vigia_social as v  # noqa: E402

REGRAS = {"usuarios": ["kaytto_oficial"], "palavras": ["advogad\\w*", "cdc", "acao judicial", "licenca"]}


class Classificador(unittest.TestCase):
    def test_normalizar(self):
        self.assertEqual(v.normalizar("Ação JUDICIAL, Licença"), "acao judicial, licenca")

    def test_usuario_vigiado_dispara_com_qualquer_texto(self):
        m = v.motivo_de("bom dia", "Kaytto_Oficial", REGRAS)
        self.assertTrue(m["vigiado"])
        self.assertEqual(m["palavras"], [])

    def test_palavra_chave_de_qualquer_um(self):
        m = v.motivo_de("falei com meu ADVOGADO hoje", "fulano", REGRAS)
        self.assertFalse(m["vigiado"])
        self.assertEqual(m["palavras"], ["advogado"])

    def test_acento_e_palavra_inteira(self):
        self.assertEqual(v.motivo_de("vou entrar com Ação Judicial", "x", REGRAS)["palavras"], ["ação judicial"])
        self.assertIsNone(v.motivo_de("abcdcba", "x", REGRAS))

    def test_excecoes_de_fala_comum(self):
        self.assertIsNone(v.motivo_de("com licença, alguém ajuda?", "x", REGRAS))
        r = {"usuarios": [], "palavras": ["processo"]}
        self.assertIsNone(v.motivo_de("o processo de desenvolvimento", "x", r))
        self.assertEqual(v.motivo_de("vou abrir um processo", "x", r)["palavras"], ["processo"])

    def test_sem_nada(self):
        self.assertIsNone(v.motivo_de("alguém troca uma saori?", "x", REGRAS))

    def test_nossa_propria_conta_nunca_dispara(self):
        self.assertIsNone(v.motivo_de("advogado", "animeidle", REGRAS, proprias=["animeidle", "AnimeIdle_"]))


class Alerta(unittest.TestCase):
    def test_alerta_menciona_so_a_equipe(self):
        item = {"rede": "instagram", "id": "c1", "autor": "fulano", "texto": "vou processar vocês",
                "link": "https://www.instagram.com/p/abc/", "quando": "2026-09-28T12:00:00+0000"}
        corpo = v.montar_alerta(item, {"vigiado": False, "palavras": ["processar"]}, avisar=["180870799320678400"])
        self.assertEqual(corpo["content"], "<@180870799320678400>")
        self.assertEqual(corpo["allowed_mentions"], {"parse": [], "users": ["180870799320678400"]})
        e = corpo["embeds"][0]
        self.assertIn("processar", e["title"])
        self.assertIn("Instagram", e["title"])
        self.assertIn("vou processar vocês", e["description"])
        self.assertTrue(any("fulano" in f["value"] for f in e["fields"]))
        self.assertTrue(any("instagram.com/p/abc" in f["value"] for f in e["fields"]))

    def test_alerta_de_vigiado_diz_isso(self):
        item = {"rede": "x", "id": "1", "autor": "kaytto_oficial", "texto": "oi", "link": "https://x.com/a/status/1", "quando": ""}
        corpo = v.montar_alerta(item, {"vigiado": True, "palavras": []}, avisar=[])
        self.assertIn("vigiad", corpo["embeds"][0]["title"].lower())
        self.assertIn("X", corpo["embeds"][0]["title"])


class Varredura(unittest.TestCase):
    """A passada recebe leitores e um avisador injetados: nada de rede aqui."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arq = os.path.join(self.tmp.name, "vigia_social.json")
        self.avisos = []

    def tearDown(self):
        self.tmp.cleanup()

    def avisar(self, corpo):
        self.avisos.append(corpo)

    def itens(self, *pares):
        return [{"rede": "instagram", "id": i, "autor": a, "texto": t, "link": "https://l/" + i, "quando": ""}
                for i, a, t in pares]

    def test_primeira_passada_so_marca_o_que_ja_existe_sem_alertar(self):
        leitores = {"instagram": lambda: self.itens(("1", "x", "advogado antigo"))}
        r = v.varrer(leitores, self.avisar, self.arq, REGRAS)
        self.assertEqual(self.avisos, [])
        self.assertEqual(r["alertas"], 0)
        estado = json.load(open(self.arq, encoding="utf8"))
        self.assertIn("1", estado["vistos"]["instagram"])

    def test_segunda_passada_alerta_so_o_novo(self):
        v.gravar_estado(self.arq, {"vistos": {"instagram": ["1"]}})
        leitores = {"instagram": lambda: self.itens(("1", "x", "advogado antigo"), ("2", "y", "chamei a advogada"), ("3", "z", "nada"))}
        r = v.varrer(leitores, self.avisar, self.arq, REGRAS)
        self.assertEqual(len(self.avisos), 1)
        self.assertIn("advogada", self.avisos[0]["embeds"][0]["title"])
        self.assertEqual(r["alertas"], 1)
        estado = json.load(open(self.arq, encoding="utf8"))
        self.assertEqual(sorted(estado["vistos"]["instagram"]), ["1", "2", "3"])

    def test_rede_que_falha_nao_derruba_a_outra(self):
        def quebrado():
            raise RuntimeError("401")
        v.gravar_estado(self.arq, {"vistos": {"instagram": [], "x": []}})
        leitores = {"x": quebrado, "instagram": lambda: self.itens(("9", "y", "meu advogado"))}
        r = v.varrer(leitores, self.avisar, self.arq, REGRAS)
        self.assertEqual(len(self.avisos), 1)
        self.assertEqual(r["falhas"], ["x"])

    def test_dry_run_nao_avisa_nem_grava(self):
        v.gravar_estado(self.arq, {"vistos": {"instagram": []}})
        leitores = {"instagram": lambda: self.itens(("9", "y", "meu advogado"))}
        r = v.varrer(leitores, self.avisar, self.arq, REGRAS, dry_run=True)
        self.assertEqual(self.avisos, [])
        self.assertEqual(r["alertas"], 1)
        self.assertEqual(json.load(open(self.arq, encoding="utf8"))["vistos"]["instagram"], [])

    def test_vistos_nao_crescem_para_sempre(self):
        v.gravar_estado(self.arq, {"vistos": {"instagram": [str(i) for i in range(3000)]}})
        leitores = {"instagram": lambda: self.itens(("novo", "y", "oi"))}
        v.varrer(leitores, self.avisar, self.arq, REGRAS)
        vistos = json.load(open(self.arq, encoding="utf8"))["vistos"]["instagram"]
        self.assertLessEqual(len(vistos), v.MAX_VISTOS)
        self.assertIn("novo", vistos)


class Tradutores(unittest.TestCase):
    def test_instagram_media_com_comentarios_e_respostas_vira_itens(self):
        media = [{"id": "m1", "permalink": "https://www.instagram.com/p/abc/", "comments": {"data": [
            {"id": "c1", "text": "lindo", "username": "ana", "timestamp": "2026-09-28T12:00:00+0000",
             "replies": {"data": [{"id": "c2", "text": "obrigado", "username": "animeidle", "timestamp": "2026-09-28T12:01:00+0000"}]}},
        ]}}]
        itens = v.itens_do_instagram(media)
        self.assertEqual([i["id"] for i in itens], ["c1", "c2"])
        self.assertEqual(itens[0]["autor"], "ana")
        self.assertEqual(itens[0]["link"], "https://www.instagram.com/p/abc/")
        self.assertEqual(itens[1]["rede"], "instagram")

    def test_x_mencoes_viram_itens_com_nome_do_autor(self):
        resp = {"data": [{"id": "10", "text": "@AnimeIdle_ vou processar", "author_id": "u1", "created_at": "2026-09-28T12:00:00.000Z"}],
                "includes": {"users": [{"id": "u1", "username": "fulano"}]}}
        itens = v.itens_do_x(resp)
        self.assertEqual(itens[0]["autor"], "fulano")
        self.assertEqual(itens[0]["link"], "https://x.com/fulano/status/10")
        self.assertEqual(itens[0]["rede"], "x")

    def test_x_sem_dados_vira_lista_vazia(self):
        self.assertEqual(v.itens_do_x({"meta": {"result_count": 0}}), [])


if __name__ == "__main__":
    unittest.main()
