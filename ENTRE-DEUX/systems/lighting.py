import os
import pygame
import random
import math

FOND_ALPHA   = 40
RAYON_JOUEUR = 140

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IMG_DIR  = os.path.join(_BASE_DIR, "assets", "images", "lumieres")


class LightingSystem:
    def __init__(self):
        self.lights      = []
        self._cache      = {}   # (radius, type)        → surface de base
        self._flick_cache = {}  # (radius, type, alpha) → surface pré-modulée
        self._darkness   = None
        self._ambient    = None
        self._screen_size = (0, 0)

    def add_light(self, x, y, radius, type="player", flicker=False, flicker_speed=5):
        self.lights.append({
            "x": x, "y": y, "radius": radius,
            "type": type, "flicker": flicker,
            "flicker_speed": flicker_speed,
            "_phase": random.random() * 6.28,
            "_alpha": 210,
        })

    def update(self, dt):
        for light in self.lights:
            if light["flicker"]:
                light["_phase"] += dt * light["flicker_speed"]
                # Quantifie l'alpha en paliers de 8 → moins de variations → moins de copies
                raw = 210 + 45 * math.sin(light["_phase"])
                light["_alpha"] = (int(raw) >> 3) << 3   # arrondi au multiple de 8

    def _load_textures(self):
        """Charge les textures à la première utilisation (lazy)."""
        if hasattr(self, '_textures'):
            return
        self._textures = {}
        names = {
            "player":     "light_player.png",
            "torch":      "light_medium.png",
            "large":      "light_large.png",
            "cool":       "light_cool.png",
            "dim":        "light_dim.png",
            "background": "light_background.png",
        }
        for k, fname in names.items():
            path = os.path.join(_IMG_DIR, fname)
            self._textures[k] = pygame.image.load(path).convert()

    def _get_halo(self, radius, ltype):
        """Surface de base (sans modulation alpha)."""
        self._load_textures()
        key = (radius, ltype)
        if key not in self._cache:
            tex  = self._textures.get(ltype, self._textures["torch"])
            size = max(2, radius * 2)
            self._cache[key] = pygame.transform.smoothscale(tex, (size, size))
        return self._cache[key]

    def _get_flick_halo(self, radius, ltype, alpha):
        """Surface modulée par l'alpha, mise en cache par (radius, type, alpha).
        Grâce à la quantification par paliers de 8 dans update(),
        il y a au plus ~12 valeurs d'alpha distinctes → cache très petit."""
        key = (radius, ltype, alpha)
        if key not in self._flick_cache:
            base = self._get_halo(radius, ltype)
            surf = base.copy()
            surf.fill((alpha, alpha, alpha), special_flags=pygame.BLEND_RGB_MULT)
            self._flick_cache[key] = surf
            # Limite la taille du cache flicker (sécurité)
            if len(self._flick_cache) > 256:
                # Retire la moitié la plus ancienne
                keys = list(self._flick_cache.keys())
                for k in keys[:128]:
                    del self._flick_cache[k]
        return self._flick_cache[key]

    def render(self, surf, camera, player_rect):
        screen_w, screen_h = surf.get_size()

        # Recrée les surfaces seulement si la taille change
        if (screen_w, screen_h) != self._screen_size:
            self._screen_size = (screen_w, screen_h)
            self._darkness = pygame.Surface((screen_w, screen_h))
            self._ambient  = pygame.Surface((screen_w, screen_h))
            self._ambient.fill((FOND_ALPHA, FOND_ALPHA, FOND_ALPHA))
            # Ne plus recréer _ambient à chaque frame — elle est statique

        self._darkness.fill((0, 0, 0))

        # Lumière du joueur
        sx   = player_rect.centerx - int(camera.offset_x)
        sy   = player_rect.centery - int(camera.offset_y)
        halo = self._get_halo(RAYON_JOUEUR, "player")
        self._darkness.blit(halo, (sx - RAYON_JOUEUR, sy - RAYON_JOUEUR),
                            special_flags=pygame.BLEND_RGB_ADD)

        # Lumières de la scène
        for light in self.lights:
            lx = light["x"] - int(camera.offset_x)
            ly = light["y"] - int(camera.offset_y)
            r  = light["radius"]
            # Cull : hors écran → skip
            if lx + r < 0 or lx - r > screen_w or ly + r < 0 or ly - r > screen_h:
                continue
            if light["flicker"]:
                halo = self._get_flick_halo(r, light["type"], light["_alpha"])
            else:
                halo = self._get_halo(r, light["type"])
            self._darkness.blit(halo, (lx - r, ly - r),
                                special_flags=pygame.BLEND_RGB_ADD)

        # Fusion ambiance + rendu final
        self._darkness.blit(self._ambient, (0, 0), special_flags=pygame.BLEND_RGB_MAX)
        surf.blit(self._darkness, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
