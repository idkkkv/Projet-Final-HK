# ─────────────────────────────────────────
#  ENTRE-DEUX — Les Lueurs (compagnons)
# ─────────────────────────────────────────

import pygame
from settings import *

class Companion:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 20, 20)
        self.collected = False

    # À compléter : suivi du joueur, effet sur la jauge de peur, animation
