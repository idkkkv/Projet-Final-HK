# ─────────────────────────────────────────────────────────────────────────────
#  PlayerInputMixin — Lecture des entrées clavier et manette
# ─────────────────────────────────────────────────────────────────────────────
#
#  Toutes les méthodes _input_* qui transforment les touches/boutons en
#  valeurs simples (entiers d'axe ou booléens) pour la méthode mouvement().
#  Unifie clavier AZERTY et manette PS5.
#
# ─────────────────────────────────────────────────────────────────────────────

import time

from pygame.locals import (
    K_d, K_q, K_r, K_s, K_UP, K_DOWN, K_SPACE, K_BACKSPACE, K_f,
    K_LSHIFT, K_RSHIFT,
)

import settings
from settings import DEAD_ZONE, BTN_CROIX, BTN_CARRE


class PlayerInputMixin:
    """Lecture unifiée clavier + manette pour le joueur."""

    def _input_axis_x(self, keys):
        """Renvoie -1 (gauche), 0 (rien) ou +1 (droite)."""
        # Priorité au joystick s'il est sorti de sa zone morte.
        if abs(settings.axis_x) > DEAD_ZONE:
            if settings.axis_x < 0:
                return -1
            else:
                return 1
        # Sinon, on lit le clavier AZERTY (Q/D).
        if keys[K_d]:
            return 1
        if keys[K_q]:
            return -1
        return 0

    def _input_axis_y(self, keys):
        """Renvoie -1 (haut), 0 ou +1 (bas).
        if abs(settings.axis_y) > DEAD_ZONE:
            if settings.axis_y < 0:
                return -1
            else:
                return 1"""
        if keys[K_r] or keys[K_UP]:
            return -1
        if keys[K_s] or keys[K_DOWN]:
            return 1
        return 0

    def _input_jump(self, keys):
        """True si Espace est enfoncée OU si Croix (PS5) l'est."""
        if keys[K_SPACE]:
            return True
        if settings.manette and settings.manette.get_button(BTN_CROIX):
            return True
        return False

    def _input_attack(self, keys):
        """True si F est enfoncée OU si Carré l'est."""
        if keys[K_BACKSPACE]:
            return True
        if settings.manette and settings.manette.get_button(BTN_CARRE):
            return True
        return False

    def _input_super_atk(self, keys):
        """True si F enfoncé"""
        if keys[K_f]:
            return True
        return False

    def _input_dash(self, keys):
        """True si Shift (gauche ou droit) est enfoncée OU L1/R1."""
        if keys[K_LSHIFT] or keys[K_RSHIFT]:
            return True
        if settings.manette:
            # On accepte L1 OU R1 (certains joueurs préfèrent l'une ou l'autre).
            if settings.manette.get_button(3) or settings.manette.get_button(9):
                return True
        return False

    def _input_run(self, keys):
        """True si la touche de course est enfoncée (ex: Maj gauche)."""
        now = time.time()
        d_pressed = keys[K_d] and not getattr(self, "_prev_d", False)
        q_pressed = keys[K_q] and not getattr(self, "_prev_q", False)
        self._prev_d = keys[K_d]
        self._prev_q = keys[K_q]

        if d_pressed or q_pressed or (settings.manette and settings.manette.get_button(10)) :
            if now - self._last_d_press_time < self._double_tap_delay:
                self.running = True
            self._last_d_press_time = now
            self._last_q_press_time = now

        # stop si plus de touche
        if not keys[K_d] and not keys[K_q] and not(settings.manette and settings.manette.get_button(10)):
            self.running = False

        return self.running

    # ═════════════════════════════════════════════════════════════════════════
    # 6.  MOUVEMENT PRINCIPAL — appelé CHAQUE FRAME par game.py
    # ═════════════════════════════════════════════════════════════════════════
    #
    # C'est LE point d'entrée de la logique du joueur. Les étapes sont
    # numérotées pour que tu puisses suivre dans l'ordre. En résumé :
    #
    #   1. Lire les entrées
    #   2. Décrémenter les timers
    #   3. Gérer le wall-lock (recul du wall-jump)
    #   4. Calculer la vitesse horizontale
    #   5. Appliquer le knockback
    #   6. Regard vers le haut → montrer les cœurs
    #   7. Saut (avec coyote time et jump buffer)
    #   8. Dash
    #   9. Gravité
    #  10. Détecter le wall-slide
    #  11. Appliquer le déplacement (rect.x += vx*dt)
    #  12. Collisions avec le sol et le plafond
    #  13. Reset des sauts au sol
    #  14. Attaque (hitbox)
    #  15. Son de pas
    #  16. Timers de combat (invincibilité, attaque)
    #  17. Régénération passive
    #
    # Les collisions avec les plateformes sont gérées APRÈS par collision.py.
