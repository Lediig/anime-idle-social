# -*- coding: utf-8 -*-
"""Atualiza a agenda da Carta do Dia e manda o pular.txt pro GitHub (de onde o robo le).

A lista oficial e a da pasta "Posts Sociais" na area de trabalho; ela e copiada pra data/pular.txt.
Roda por duplo clique (atalho na pasta) ou: python tools/atualizar_agenda.py
"""
import json, os, shutil, subprocess, sys, webbrowser

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
PASTA = os.path.join(os.path.expanduser("~"), "OneDrive", "Área de Trabalho", "Anime Idle", "Posts Sociais")
LISTA = os.path.join(PASTA, "pular.txt")


def git(*args, silencio=False):
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf8", errors="replace")
    if r.returncode and not silencio:
        print(r.stdout, r.stderr)
    return r.returncode


def main():
    print("== Carta do Dia: atualizar agenda e enviar ==\n")
    if os.path.exists(LISTA):
        shutil.copyfile(LISTA, os.path.join(REPO, "data", "pular.txt"))
        print("Lista lida de:", LISTA)
    else:
        print("Aviso: nao achei", LISTA, "- usando a lista que ja esta no repositorio.")

    cards = {c["slug"] for c in json.load(open("data/cards.json", encoding="utf8"))}
    fora = [l.split("#", 1)[0].strip().lower() for l in open("data/pular.txt", encoding="utf8")]
    fora = [s for s in fora if s]
    ruins = [s for s in fora if s not in cards]
    if ruins:
        print("ATENCAO, nomes que nao existem no jogo (confira a grafia):", ", ".join(ruins))
    print("Fora da fila:", ", ".join(s for s in fora if s in cards) or "ninguem")

    git("pull", "--rebase", "-q", "origin", "main", silencio=True)
    if subprocess.call([sys.executable, "bot/carta.py", "calendario"], stdout=subprocess.DEVNULL):
        input("ERRO ao gerar a agenda. Enter pra fechar."); return
    git("add", "data/pular.txt", "CALENDARIO.md", "CALENDARIO.html")
    if git("diff", "--cached", "--quiet", silencio=True) == 0:
        print("\nNada mudou no GitHub. A agenda local foi refeita.")
    else:
        git("commit", "-q", "-m", "agenda: pular.txt e calendario")
        if git("push", "-q", "origin", "HEAD:main") == 0:
            print("\nEnviado. O GitHub refaz a agenda online em cerca de 1 minuto.")
        else:
            print("\nO push falhou (sem internet ou sem login do git?). A agenda local foi refeita mesmo assim.")
    webbrowser.open(os.path.join(REPO, "CALENDARIO.html"))
    input("\nEnter pra fechar.")


if __name__ == "__main__":
    main()
