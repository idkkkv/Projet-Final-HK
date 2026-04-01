# ─────────────────────────────────────────
#  ENTRE-DEUX — Effets sonores
# ─────────────────────────────────────────

import math
import struct
import pygame

_sons = {}


def _trim_silence(son, seuil=400):
    """Supprime le silence au début d'un son (pour des sons courts type pas)."""
    raw = son.get_raw()
    # 4 bytes par sample stéréo 16-bit
    for i in range(0, len(raw) - 4, 4):
        left = struct.unpack_from("<h", raw, i)[0]
        if abs(left) > seuil:
            # Garder à partir de ce sample
            trimmed = raw[i:]
            return pygame.mixer.Sound(buffer=bytes(trimmed))
    return son


def charger(nom, chemin, trim=False):
    """Charge un son et le stocke sous un nom. trim=True coupe le silence initial."""
    try:
        son = pygame.mixer.Sound(chemin)
        if trim:
            son = _trim_silence(son)
        _sons[nom] = son
    except Exception:
        pass


def jouer(nom, volume=1.0):
    """Joue un son par son nom. Limite à 1 instance pour les pas."""
    son = _sons.get(nom)
    if son:
        # Empêcher la superposition pour les sons de pas
        if nom == "pas" and son.get_num_channels() > 0:
            return
        son.set_volume(max(0.0, min(1.0, volume)))
        son.play()


def arreter(nom):
    son = _sons.get(nom)
    if son:
        son.stop()


# ── Sons synthétiques (pas de fichier nécessaire) ──

def _generer_son(freq, duree, volume=0.3, forme="sin"):
    """Génère un son synthétique court."""
    sample_rate = 44100
    n = int(sample_rate * duree)
    buf = bytearray()
    for i in range(n):
        t = i / sample_rate
        env = min(1.0, i / (n * 0.1)) * min(1.0, (n - i) / (n * 0.3))
        if forme == "sin":
            val = math.sin(2 * math.pi * freq * t)
        else:
            val = (2 * (freq * t % 1) - 1)  # dent de scie
        sample = int(val * env * volume * 32767)
        sample = max(-32768, min(32767, sample))
        packed = struct.pack("<h", sample)
        buf += packed + packed  # stéréo
    return pygame.mixer.Sound(buffer=bytes(buf))


def init_sons_ui():
    """Initialise les sons d'interface synthétiques."""
    if "ui_nav" not in _sons:
        _sons["ui_nav"] = _generer_son(520, 0.04, 0.15)
        _sons["ui_select"] = _generer_son(680, 0.08, 0.2)
        _sons["ui_back"] = _generer_son(320, 0.06, 0.15)
