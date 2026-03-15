# ─────────────────────────────────────────
#  ENTRE-DEUX — Configuration des hitboxes
# ─────────────────────────────────────────
#
#  Stocke la hitbox de chaque sprite ennemi
#  dans hitboxes.json à côté des maps.
#  Format : { "sprite_name.png": {"w": 36, "h": 40, "ox": 12, "oy": 20} }
#  ox, oy = offset depuis le coin haut-gauche du sprite
# ─────────────────────────────────────────

import os
import json

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HITBOX_FILE = os.path.join(_BASE_DIR, "hitboxes.json")

# Hitbox par défaut si pas de config
DEFAULT_HITBOX = {"w": 36, "h": 40, "ox": 0, "oy": 0}

_cache = None


def _load():
    global _cache
    if _cache is not None:
        return _cache
    if os.path.exists(HITBOX_FILE):
        try:
            with open(HITBOX_FILE) as f:
                _cache = json.load(f)
        except (json.JSONDecodeError, IOError):
            _cache = {}
    else:
        _cache = {}
    return _cache


def get_hitbox(sprite_name):
    """Retourne {"w", "h", "ox", "oy"} pour un sprite."""
    data = _load()
    return data.get(sprite_name, DEFAULT_HITBOX.copy())


def set_hitbox(sprite_name, w, h, ox, oy):
    """Enregistre la hitbox d'un sprite et sauvegarde."""
    global _cache
    data = _load()
    data[sprite_name] = {"w": w, "h": h, "ox": ox, "oy": oy}
    _cache = data
    with open(HITBOX_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Hitbox '{sprite_name}': {w}×{h} offset({ox},{oy})")