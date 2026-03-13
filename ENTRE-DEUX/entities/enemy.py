# ─────────────────────────────────────────
#  ENTRE-DEUX — Ennemi de base
# ─────────────────────────────────────────

import pygame
from settings import *

class Enemy:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 60, 60)
        self.vx = 120
        self.alive = True

    def update(self, dt):
        self.rect.x += self.vx * dt

        # Change de direction s'il touche un bord
        if self.rect.left < 0 or self.rect.right > WIDTH:
            self.vx *= -1

    def draw(self, surf):
        if self.alive:
            pygame.draw.rect(surf, ROUGE, self.rect)
