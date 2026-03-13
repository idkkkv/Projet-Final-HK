# ─────────────────────────────────────────
#  ENTRE-DEUX — Plateformes & décors
# ─────────────────────────────────────────

import pygame
from settings import *

class Platform:
    def __init__(self, x, y, width, height, color):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color

    def verifier_collision(self, player):
        if player.rect.colliderect(self.rect):
            if player.vy > 0 and player.rect.bottom <= self.rect.top + 15:
                player.rect.bottom = self.rect.top
                player.on_ground = True
                player.vy = 0

    def draw(self, surf):
        pygame.draw.rect(surf, self.color, self.rect)
