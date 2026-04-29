# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — "Lueurs" à collecter — STUB / EMBRYON
# ─────────────────────────────────────────────────────────────────────────────
#
#  ÉTAT ACTUEL : EMBRYON (pas branché au gameplay)
#  -----------------------------------------------
#  Coquille vide pour les "Lueurs" — petits objets/êtres lumineux qu'on
#  collecte dans le monde. À ne PAS confondre avec entities/compagnon.py
#  (les compagnons VIVANTS qui suivent le joueur, déjà implémentés !).
#
#       entities/compagnon.py  (avec un G)  → IMPLÉMENTÉ — les vivants
#                                              qui suivent et combattent.
#       entities/companion.py  (sans G)     → CE FICHIER, stub — les
#                                              objets à collecter.
#
#  Petit lexique :
#     - lueur       = petit objet lumineux. Conçu comme une RÉCOMPENSE
#                     placée dans le monde (à l'éditeur), à récupérer
#                     pour faire BAISSER la jauge de Peur (cf.
#                     systems/fear_system.py).
#     - collected   = booléen mis à True quand le joueur l'a touchée.
#                     On la garde en mémoire mais on ne la dessine plus.
#     - stub        = embryon — coquille vide qui réserve l'API.
#
#  USAGE PRÉVU
#  -----------
#       lueur = Companion(x=200, y=400)
#       ...
#       # Dans game.py, à chaque frame :
#       if not lueur.collected and joueur.rect.colliderect(lueur.rect):
#           lueur.collected = True
#           fear.reduce(15)        # baisse la peur
#           # son + particules + animation à compléter
#
#  À NE PAS FAIRE
#  --------------
#  Ne pas le confondre avec un Compagnon (avec un G). Les Lueurs sont
#  STATIQUES (elles ne suivent pas le joueur). Si tu cherches les compagnons
#  qui combattent à côté du joueur → entities/compagnon.py.
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  PAS ENCORE.
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame
from settings import *


class Companion:
    """Lueur à collecter (≠ Compagnon vivant). Squelette en attente."""

    def __init__(self, x, y):
        self.rect      = pygame.Rect(x, y, 20, 20)
        self.collected = False

    # À compléter :
    #   - effet visuel (animation de scintillement, particules)
    #   - son à la collecte
    #   - effet sur la jauge de peur (FearSystem.reduce())
