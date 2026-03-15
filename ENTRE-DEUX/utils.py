# ─────────────────────────────────────────
#  ENTRE-DEUX — Fonctions utilitaires
# ─────────────────────────────────────────

import os
import pygame
import settings

_font_cache = {}


def _get_font(name, size):
    key = (name, size)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont(name, size)
    return _font_cache[key]


def find_file(filename, search_dir="assets"):
    base = os.path.dirname(os.path.abspath(__file__))
    search_path = os.path.join(base, search_dir)
    for root, dirs, files in os.walk(search_path):
        if filename in files:
            return os.path.join(root, filename)
    raise FileNotFoundError(f"Fichier '{filename}' introuvable dans '{search_dir}'")


def draw_mouse_coords(surf, camera=None, y_start=10):
    """
    Affiche les coordonnées de la souris.
    y_start contrôle la position verticale (95 = sous le panneau éditeur).
    """
    font = _get_font("Consolas", 16)
    mx, my = pygame.mouse.get_pos()

    text_screen = font.render(f"Ecran  x:{mx}  y:{my}", True, (255, 255, 0))
    surf.blit(text_screen, (10, y_start))

    if camera:
        wx = settings.wx = int(mx + camera.offset_x)
        wy = settings.wy = int(my + camera.offset_y)
        text_world = font.render(f"Monde  x:{wx}  y:{wy}", True, (0, 255, 180))
        surf.blit(text_world, (10, y_start + 20))