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

        # Même méthode que Wall : pénétration minimum
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
    def __init__(self, x, y, width, height, visible=False):
        self.rect = pygame.Rect(x, y, width, height)
        self.visible = visible

    def verifier_collision(self, player):
        if not player.rect.colliderect(self.rect):
            return

        # Calcule la profondeur de pénétration de chaque côté
        overlap_left   = player.rect.right - self.rect.left
        overlap_right  = self.rect.right - player.rect.left
        overlap_top    = player.rect.bottom - self.rect.top
        overlap_bottom = self.rect.bottom - player.rect.top

        # Trouve le côté où la pénétration est la plus petite
        # C'est par là que le joueur est entré → on le repousse de ce côté
        min_overlap = min(overlap_left, overlap_right, overlap_top, overlap_bottom)

        if min_overlap == overlap_top and player.vy >= 0:
            # Atterrit sur le dessus du mur
            player.rect.bottom = self.rect.top
            player.vy = 0
            player.on_ground = True
        elif min_overlap == overlap_bottom and player.vy <= 0:
            # Tape le plafond (dessous du mur)
            player.rect.top = self.rect.bottom
            player.vy = 0
        elif min_overlap == overlap_left and player.vx >= 0:
            # Bloqué à gauche du mur
            player.rect.right = self.rect.left
            player.vx = 0
        elif min_overlap == overlap_right and player.vx <= 0:
            # Bloqué à droite du mur
            player.rect.left = self.rect.right
            player.vx = 0
        else:
            # Fallback : repousse du côté le plus proche
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