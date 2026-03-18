# ─────────────────────────────────────────
#  ENTRE-DEUX — Caméra
# ─────────────────────────────────────────
import pygame
from settings import WIDTH, HEIGHT


class Camera:
    def __init__(self, scene_width, scene_height):
        self.offset_x    = 0
        self.offset_y    = 0
        self.scene_width  = scene_width
        self.scene_height = scene_height
        self.y_offset = 150

    def update(self, target_rect):
        screen_w, screen_h = pygame.display.get_surface().get_size()

        target_x = target_rect.centerx - screen_w // 2
        target_y = target_rect.centery - screen_h // 2 + self.y_offset

        self.offset_x += (target_x - self.offset_x) * 0.1
        self.offset_y += (target_y - self.offset_y) * 0.1

        import settings
        # Borne basse : le sol reste visible
        max_y = settings.GROUND_Y + 40 - screen_h

        # Borne haute : suit le plafond (CEILING_Y peut être négatif)
        # On soustrait la moitié de l'écran pour que le joueur soit
        # centré verticalement quand il touche le plafond.
        min_y = settings.CEILING_Y - screen_h // 2

        self.offset_x = max(0, min(self.offset_x, self.scene_width - screen_w))
        self.offset_y = max(min_y, min(self.offset_y, max(0, max_y)))

    def apply(self, rect):
        return pygame.Rect(
            rect.x - int(self.offset_x),
            rect.y - int(self.offset_y),
            rect.width,
            rect.height,
        )

    def is_visible(self, rect):
        screen_w, screen_h = pygame.display.get_surface().get_size()
        screen_rect = pygame.Rect(self.offset_x, self.offset_y, screen_w, screen_h)
        return screen_rect.colliderect(rect)