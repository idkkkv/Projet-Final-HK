# ─────────────────────────────────────────
#  ENTRE-DEUX — Caméra
# ─────────────────────────────────────────
# À compléter : caméra qui suit le joueur
import pygame
from settings import WIDTH, HEIGHT

class Camera:
    def __init__(self, scene_width, scene_height):
        self.offset_x = 0
        self.offset_y = 0
        self.scene_width = scene_width
        self.scene_height = scene_height

    def update(self, target_rect):
        screen_w, screen_h = pygame.display.get_surface().get_size()

        # Smooth follow
        self.offset_x += (target_rect.centerx - screen_w // 2 - self.offset_x) * 0.1
        self.offset_y += (target_rect.centery - screen_h // 2 - self.offset_y) * 0.1

        # Clamp aux bords de la scène
        self.offset_x = max(0, min(self.offset_x, self.scene_width - screen_w))
        self.offset_y = max(0, min(self.offset_y, self.scene_height - screen_h))

    def apply(self, rect):
        """Retourne la position à l'écran d'un objet du monde."""
        return pygame.Rect(
            rect.x - int(self.offset_x),
            rect.y - int(self.offset_y),
            rect.width,
            rect.height
        )

    def is_visible(self, rect):
        """Retourne True si l'objet est dans la zone visible."""
        screen_w, screen_h = pygame.display.get_surface().get_size()
        screen_rect = pygame.Rect(self.offset_x, self.offset_y, screen_w, screen_h)
        return screen_rect.colliderect(rect)