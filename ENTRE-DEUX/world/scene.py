# ─────────────────────────────────────────
#  ENTRE-DEUX — Scène (zone du jeu)
# ─────────────────────────────────────────

import pygame
from settings import *

class Scene:
    def __init__(self, name):
        self.name = name
        self.platforms = []
        self.enemies = []
        self.npcs = []
        self.companions = []

    def update(self, dt, player):
        for enemy in self.enemies:
            enemy.update(dt)

    def draw(self, surf):
        for platform in self.platforms:
            platform.draw(surf)
        for enemy in self.enemies:
            enemy.draw(surf)
        for npc in self.npcs:
            pass  # À compléter
        for companion in self.companions:
            pass  # À compléter
