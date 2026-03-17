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
        if not player.rect.colliderect(self.rect):
            return
        overlap_left   = player.rect.right - self.rect.left
        overlap_right  = self.rect.right - player.rect.left
        overlap_top    = player.rect.bottom - self.rect.top
        overlap_bottom = self.rect.bottom - player.rect.top
        min_overlap = min(overlap_left, overlap_right, overlap_top, overlap_bottom)
        if min_overlap == overlap_top and player.vy >= 0:
            player.rect.bottom = self.rect.top
            player.vy = 0
            player.on_ground = True
        elif min_overlap == overlap_bottom and player.vy <= 0:
            player.rect.top = self.rect.bottom
            player.vy = 0
        elif min_overlap == overlap_left:
            player.rect.right = self.rect.left
            player.vx = 0
        elif min_overlap == overlap_right:
            player.rect.left = self.rect.right
            player.vx = 0

    def draw(self, surf, camera):
        pygame.draw.rect(surf, self.color, camera.apply(self.rect))


class Wall:
    def __init__(self, x, y, width, height, visible=False, player_only=False):
        self.rect = pygame.Rect(x, y, width, height)
        self.visible = visible
        self.player_only = player_only   # ← NOUVEAU : ignoré par les ennemis

    def verifier_collision(self, player):
        if not player.rect.colliderect(self.rect):
            return
        overlap_left   = player.rect.right - self.rect.left
        overlap_right  = self.rect.right - player.rect.left
        overlap_top    = player.rect.bottom - self.rect.top
        overlap_bottom = self.rect.bottom - player.rect.top
        min_overlap = min(overlap_left, overlap_right, overlap_top, overlap_bottom)
        if min_overlap == overlap_top and player.vy >= 0:
            player.rect.bottom = self.rect.top
            player.vy = 0
            player.on_ground = True
        elif min_overlap == overlap_bottom and player.vy <= 0:
            player.rect.top = self.rect.bottom
            player.vy = 0
        elif min_overlap == overlap_left and player.vx >= 0:
            player.rect.right = self.rect.left
            player.vx = 0
        elif min_overlap == overlap_right and player.vx <= 0:
            player.rect.left = self.rect.right
            player.vx = 0
        else:
            if min_overlap == overlap_top:
                player.rect.bottom = self.rect.top
                player.vy = 0
                player.on_ground = True
            elif min_overlap == overlap_bottom:
                player.rect.top = self.rect.bottom
                player.vy = 0
            elif min_overlap == overlap_left:
                player.rect.right = self.rect.left
                player.vx = 0
            elif min_overlap == overlap_right:
                player.rect.left = self.rect.right
                player.vx = 0

    def draw(self, surf, camera):
        if self.visible:
            pygame.draw.rect(surf, (0, 0, 0), camera.apply(self.rect))