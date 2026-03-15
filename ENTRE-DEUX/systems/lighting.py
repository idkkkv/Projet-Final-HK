import os
import pygame
import random
import math

FOND_ALPHA   = 40
RAYON_JOUEUR = 140

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IMG_DIR  = os.path.join(_BASE_DIR, "assets", "images")

class LightingSystem:
    def __init__(self):
        self.lights = []
        self._cache = {}
        self._textures = {
            "player":     pygame.image.load(os.path.join(_IMG_DIR, "light_player.png")).convert(),
            "torch":      pygame.image.load(os.path.join(_IMG_DIR, "light_medium.png")).convert(),
            "large":      pygame.image.load(os.path.join(_IMG_DIR, "light_large.png")).convert(),
            "cool":       pygame.image.load(os.path.join(_IMG_DIR, "light_cool.png")).convert(),
            "dim":        pygame.image.load(os.path.join(_IMG_DIR, "light_dim.png")).convert(),
            "background": pygame.image.load(os.path.join(_IMG_DIR, "light_background.png")).convert(),
        }
        self._darkness = None
        self._ambient = None
        self._screen_size = (0, 0)

    def add_light(self, x, y, radius, type="player", flicker=False, flicker_speed=5):
        self.lights.append({
            "x": x, "y": y, "radius": radius,
            "type": type, "flicker": flicker,
            "flicker_speed": flicker_speed,
            "_phase": random.random() * 6.28,
        })

    def update(self, dt):
        for light in self.lights:
            if light["flicker"]:
                light["_phase"] += dt * light["flicker_speed"]
                light["_alpha"] = int(210 + 45 * math.sin(light["_phase"]))

    def _get_halo(self, radius, type="torch"):
        key = (radius, type)
        if key not in self._cache:
            tex = self._textures.get(type, self._textures["torch"])
            size = max(2, radius * 2)
            halo = pygame.transform.smoothscale(tex, (size, size))
            self._cache[key] = halo
        return self._cache[key]

    def render(self, surf, camera, player_rect):
        screen_w, screen_h = surf.get_size()
        if (screen_w, screen_h) != self._screen_size:
            self._screen_size = (screen_w, screen_h)
            self._darkness = pygame.Surface((screen_w, screen_h))
            self._ambient = pygame.Surface((screen_w, screen_h))

        self._darkness.fill((0, 0, 0))

        sx = player_rect.centerx - int(camera.offset_x)
        sy = player_rect.centery - int(camera.offset_y)
        halo = self._get_halo(RAYON_JOUEUR, "player")
        self._darkness.blit(halo, (sx - RAYON_JOUEUR, sy - RAYON_JOUEUR),
                            special_flags=pygame.BLEND_RGB_ADD)

        for light in self.lights:
            lx = light["x"] - int(camera.offset_x)
            ly = light["y"] - int(camera.offset_y)
            r  = light["radius"]
            if lx + r < 0 or lx - r > screen_w or ly + r < 0 or ly - r > screen_h:
                continue
            halo = self._get_halo(r, light["type"])
            if "_alpha" in light:
                halo = halo.copy()
                a = light["_alpha"]
                halo.fill((a, a, a), special_flags=pygame.BLEND_RGB_MULT)
            self._darkness.blit(halo, (lx - r, ly - r),
                                special_flags=pygame.BLEND_RGB_ADD)

        self._ambient.fill((FOND_ALPHA, FOND_ALPHA, FOND_ALPHA))
        self._darkness.blit(self._ambient, (0, 0), special_flags=pygame.BLEND_RGB_MAX)
        surf.blit(self._darkness, (0, 0), special_flags=pygame.BLEND_RGB_MULT)