import pygame
import random

# ─── Réglages ───────────────────────────
FOND_ALPHA   = 40  # luminosité ambiante (0=noir total, 100=sombre, 255=jour)
RAYON_JOUEUR = 140  # taille du halo du joueur
# ────────────────────────────────────────

class LightingSystem:
    def __init__(self):
        self.lights = []
        self._cache = {}
        self._textures = {
                "player":     pygame.image.load("assets/images/light_player.png").convert(),
                "torch":      pygame.image.load("assets/images/light_medium.png").convert(),
                "large":      pygame.image.load("assets/images/light_large.png").convert(),
                "cool":       pygame.image.load("assets/images/light_cool.png").convert(),
                "dim":        pygame.image.load("assets/images/light_dim.png").convert(),
                "background": pygame.image.load("assets/images/light_background.png").convert(),  }

    def add_light(self, x, y, radius, type="player", flicker=False):
        self.lights.append({"x": x, "y": y, "radius": radius,
                            "type": type, "flicker": flicker})

    def update(self):
        for light in self.lights:
            if light.get("flicker"):
                light["radius"] += random.randint(-2, 2)
                light["radius"] = max(80, min(200, light["radius"]))
                self._cache.pop((light["radius"], light["type"]), None)

    def _get_halo(self, radius, type="torch"):
        key = (radius, type)
        if key not in self._cache:
            tex = self._textures[type]
            size = radius * 2
            halo = pygame.transform.smoothscale(tex, (size, size))
            self._cache[key] = halo
        return self._cache[key]

    def render(self, surf, camera, player_rect):
        screen_w, screen_h = surf.get_size()

        darkness = pygame.Surface((screen_w, screen_h))
        darkness.fill((0, 0, 0))

        # Joueur
        sx = player_rect.centerx - int(camera.offset_x)
        sy = player_rect.centery - int(camera.offset_y)
        halo = self._get_halo(RAYON_JOUEUR, "player")
        darkness.blit(halo, (sx - RAYON_JOUEUR, sy - RAYON_JOUEUR),
              special_flags=pygame.BLEND_RGB_ADD)

        # Torches
        for light in self.lights:
            lx = light["x"] - int(camera.offset_x)
            ly = light["y"] - int(camera.offset_y)
            r  = light["radius"]
            halo = self._get_halo(r, light["type"])
            darkness.blit(halo, (lx - r, ly - r),
              special_flags=pygame.BLEND_RGB_ADD)

        # Lumière ambiante
        ambient = pygame.Surface((screen_w, screen_h))
        ambient.fill((FOND_ALPHA, FOND_ALPHA, FOND_ALPHA))
        darkness.blit(ambient, (0, 0), special_flags=pygame.BLEND_RGB_MAX)

        surf.blit(darkness, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
