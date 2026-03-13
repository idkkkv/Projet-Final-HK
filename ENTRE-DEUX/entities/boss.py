# ─────────────────────────────────────────
#  ENTRE-DEUX — Boss (hérite d'Enemy)
# ─────────────────────────────────────────

import pygame
from settings import *
from entities.enemy import Enemy

class Boss(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.rect = pygame.Rect(x, y, 120, 120)  # Plus grand qu'un ennemi normal
        self.hp = 5
        self.phase = 1  # Les boss ont plusieurs phases

    # À compléter selon les boss de l'histoire
