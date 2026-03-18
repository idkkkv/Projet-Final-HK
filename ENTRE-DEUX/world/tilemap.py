# ─────────────────────────────────────────
#  ENTRE-DEUX — Plateformes & décors
# ─────────────────────────────────────────

import pygame
from settings import *


class Platform:
    def __init__(self, x, y, width, height, color):
        self.rect  = pygame.Rect(x, y, width, height)
        self.color = color

    def verifier_collision(self, player):
        if not player.rect.colliderect(self.rect):
            return
        ol = player.rect.right  - self.rect.left
        or_ = self.rect.right   - player.rect.left
        ot = player.rect.bottom - self.rect.top
        ob = self.rect.bottom   - player.rect.top
        mn = min(ol, or_, ot, ob)
        if mn == ot and player.vy >= 0:
            player.rect.bottom = self.rect.top;  player.vy = 0; player.on_ground = True
        elif mn == ob and player.vy <= 0:
            player.rect.top    = self.rect.bottom; player.vy = 0
        elif mn == ol:
            player.rect.right  = self.rect.left;  player.vx = 0
        elif mn == or_:
            player.rect.left   = self.rect.right;  player.vx = 0

    def draw(self, surf, camera):
        pygame.draw.rect(surf, self.color, camera.apply(self.rect))


class Wall:
    def __init__(self, x, y, width, height, visible=False,
                 player_only=False, is_border=False):
        self.rect        = pygame.Rect(x, y, width, height)
        self.visible     = visible
        self.player_only = player_only   # ignoré par les ennemis
        self.is_border   = is_border     # segment de bordure (sol/plafond/côtés)
                                         # → ignoré par _has_line_of_sight

    def verifier_collision(self, player):
        if not player.rect.colliderect(self.rect):
            return
        ol  = player.rect.right  - self.rect.left
        or_ = self.rect.right    - player.rect.left
        ot  = player.rect.bottom - self.rect.top
        ob  = self.rect.bottom   - player.rect.top
        mn  = min(ol, or_, ot, ob)

        if mn == ot and player.vy >= 0:
            player.rect.bottom = self.rect.top;   player.vy = 0; player.on_ground = True
        elif mn == ob and player.vy <= 0:
            player.rect.top    = self.rect.bottom; player.vy = 0
        elif mn == ol and player.vx >= 0:
            player.rect.right  = self.rect.left;   player.vx = 0
        elif mn == or_ and player.vx <= 0:
            player.rect.left   = self.rect.right;  player.vx = 0
        else:
            if mn == ot:
                player.rect.bottom = self.rect.top;   player.vy = 0; player.on_ground = True
            elif mn == ob:
                player.rect.top    = self.rect.bottom; player.vy = 0
            elif mn == ol:
                player.rect.right  = self.rect.left;   player.vx = 0
            elif mn == or_:
                player.rect.left   = self.rect.right;  player.vx = 0

    def draw(self, surf, camera):
        if self.visible:
            pygame.draw.rect(surf, (0, 0, 0), camera.apply(self.rect))