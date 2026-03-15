# ─────────────────────────────────────────
#  ENTRE-DEUX — Caméra
# ─────────────────────────────────────────
import pygame
from settings import WIDTH, HEIGHT


class Camera:
    def __init__(self, scene_width, scene_height):
        self.offset_x = 0
        self.offset_y = 0
        self.scene_width = scene_width
        self.scene_height = scene_height

        # Décalage vertical : valeur positive = le joueur apparaît
        # plus bas sur l'écran (on voit plus de ciel / plateformes au-dessus)
        # 0 = centré, 150 = joueur en bas du tiers inférieur
        self.y_offset = 150

    def update(self, target_rect):
        screen_w, screen_h = pygame.display.get_surface().get_size()

        # Cible : le joueur, décalé vers le bas de l'écran
        target_x = target_rect.centerx - screen_w // 2
        target_y = target_rect.centery - screen_h // 2 + self.y_offset

        # Smooth follow (10% de l'écart par frame)
        self.offset_x += (target_x - self.offset_x) * 0.1
        self.offset_y += (target_y - self.offset_y) * 0.1

        # Clamp : on ne montre pas au-dessus du plafond ni en dessous du sol
        import settings
        max_y = settings.GROUND_Y + 40 - screen_h  # sol + épaisseur - écran
        self.offset_x = max(0, min(self.offset_x, self.scene_width - screen_w))
        self.offset_y = max(-20, min(self.offset_y, max(0, max_y)))

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