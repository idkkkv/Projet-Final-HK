# ─────────────────────────────────────────
#  ENTRE-DEUX — Caméra
# ─────────────────────────────────────────
import pygame
import settings
from settings import WIDTH, HEIGHT


class Camera:
    def __init__(self, scene_width, scene_height):
        self.offset_x     = 0
        self.offset_y     = 0
        self.scene_width  = scene_width
        self.scene_height = scene_height
        self.y_offset     = 150

        # Cache de la taille écran — évite get_surface() à chaque appel
        self._sw = WIDTH
        self._sh = HEIGHT

    def update(self, target_rect):
        # Mise à jour du cache taille écran une fois par frame
        surf = pygame.display.get_surface()
        if surf:
            self._sw, self._sh = surf.get_size()

        target_x = target_rect.centerx - self._sw // 2
        target_y = target_rect.centery - self._sh // 2 + self.y_offset

        self.offset_x += (target_x - self.offset_x) * 0.1
        self.offset_y += (target_y - self.offset_y) * 0.1

        max_y = settings.GROUND_Y + 40 - self._sh
        min_y = settings.CEILING_Y - self._sh // 2

        self.offset_x = max(0, min(self.offset_x, self.scene_width - self._sw))
        self.offset_y = max(min_y, min(self.offset_y, max(0, max_y)))

    def apply(self, rect):
        return pygame.Rect(
            rect.x - int(self.offset_x),
            rect.y - int(self.offset_y),
            rect.width,
            rect.height,
        )

    def is_visible(self, rect):
        """Test de visibilité sans appel à get_surface()."""
        return (rect.right  > self.offset_x and
                rect.left   < self.offset_x + self._sw and
                rect.bottom > self.offset_y and
<<<<<<< HEAD
                rect.top    < self.offset_y + self._sh)
=======
                rect.top    < self.offset_y + self._sh)
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce
