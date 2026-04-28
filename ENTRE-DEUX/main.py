# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Point d'entrée du jeu
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  C'est LE fichier qu'on lance pour démarrer le jeu :
# 
#  ----------------------------------
#  Convention universelle Python : main.py = un point d'entrée minimal
#  qui DÉLÈGUE tout à un module / une classe métier. Avantages :
#       - lecture immédiate "qu'est-ce qui démarre ?"
#       - facile à remplacer par un autre point d'entrée (ex : tests)
#       - pas de logique cachée dans un fichier qu'on ne lit jamais
#
#  Petit lexique :
#     - point d'entrée   = LE fichier qu'on lance pour démarrer un programme.
#     - __name__         = variable spéciale Python remplie automatiquement.
#                          "__main__" si lancé directement, sinon le nom du module.
#     - if __name__ ...  = formule idiomatique de protection.
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D1]  point d'entrée — convention Python pour démarrer une appli
#
# ─────────────────────────────────────────────────────────────────────────────

from core.game import Game


if __name__ == "__main__":
    game = Game()
    game.run()
