# ─────────────────────────────────────────
#  ENTRE-DEUX — Musique de fond
# ─────────────────────────────────────────

import pygame

_current = None
_target_volume = 0.5
_fade_speed = 0       # 0 = pas de fondu en cours
_after_fade = None     # callback après le fadeout


def jouer(chemin, boucle=-1, volume=0.5, fadein_ms=1500):
    """Lance une musique avec fondu entrant natif pygame."""
    global _current, _target_volume, _fade_speed, _after_fade
    if chemin == _current and pygame.mixer.music.get_busy():
        return
    try:
        pygame.mixer.music.load(chemin)
        _target_volume = volume
        _fade_speed = 0
        _after_fade = None
        pygame.mixer.music.set_volume(volume)
        # Positional args : play(loops, start, fade_ms)
        pygame.mixer.music.play(boucle, 0.0, max(0, fadein_ms))
        _current = chemin
    except Exception as e:
        print(f"[music] Erreur jouer({chemin}): {e}")
        _current = None


def transition(chemin, boucle=-1, volume=0.5, fadeout_ms=1000, fadein_ms=1500):
    """Fondu sortant de la musique actuelle puis lance la nouvelle."""
    global _fade_speed, _after_fade, _target_volume
    if chemin == _current and pygame.mixer.music.get_busy():
        # Même musique déjà en lecture — si elle est en train de fader out,
        # annuler le fadeout et remettre le volume cible directement
        if _fade_speed < 0:
            _after_fade = None
            _fade_speed = 0
            _target_volume = volume
            pygame.mixer.music.set_volume(volume)
        return
    if _current and pygame.mixer.music.get_busy():
        # Fadeout progressif puis callback
        cur_vol = pygame.mixer.music.get_volume()
        _target_volume = 0.0
        _fade_speed = -cur_vol / max(0.001, fadeout_ms / 1000)
        _after_fade = lambda: jouer(chemin, boucle, volume, fadein_ms)
    else:
        jouer(chemin, boucle, volume, fadein_ms)


def arreter(fadeout_ms=800):
    """Arrête la musique avec fondu sortant."""
    global _current, _target_volume, _fade_speed, _after_fade
    if fadeout_ms > 0 and pygame.mixer.music.get_busy():
        vol = pygame.mixer.music.get_volume()
        _target_volume = 0.0
        _fade_speed = -vol / max(0.001, fadeout_ms / 1000)
        _after_fade = lambda: _stop_immediate()
    else:
        _stop_immediate()


def _stop_immediate():
    global _current, _fade_speed, _after_fade
    pygame.mixer.music.stop()
    _current = None
    _fade_speed = 0
    _after_fade = None


def volume(v):
    global _target_volume
    _target_volume = max(0.0, min(1.0, v))
    pygame.mixer.music.set_volume(_target_volume)


def update(dt):
    """Appeler chaque frame pour les fondus progressifs (fadeout uniquement)."""
    global _fade_speed, _after_fade, _target_volume
    if _fade_speed == 0:
        return
    dt = min(dt, 0.05)  # Éviter les sauts de volume quand la fenêtre perd le focus
    vol = pygame.mixer.music.get_volume()
    vol += _fade_speed * dt
    if _fade_speed > 0 and vol >= _target_volume:
        vol = _target_volume
        _fade_speed = 0
    elif _fade_speed < 0 and vol <= _target_volume:
        vol = max(0.0, _target_volume)
        _fade_speed = 0
        if _after_fade:
            cb = _after_fade
            _after_fade = None
            cb()
            return
    pygame.mixer.music.set_volume(max(0.0, min(1.0, vol)))
