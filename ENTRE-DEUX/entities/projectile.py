# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Projectiles (boules d'ombre tirées par les boss)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Un projectile poursuit légèrement le joueur pendant quelques secondes
#  avant de disparaître. Tiré par les boss (ennemis nommés) toutes les
#  3-5 secondes quand ils ont détecté le joueur.
#
#  Pourquoi un fichier dédié ? Pour ne pas alourdir entities/enemy.py qui
#  fait déjà 1000+ lignes, et permettre de réutiliser les projectiles
#  pour d'autres entités (cinematique, piège…) plus tard.
# ─────────────────────────────────────────────────────────────────────────────

import math
import pygame


class ShadowProjectile:
    """Boule d'ombre semi-téléguidée.

    À chaque frame :
      - se rapproche un peu du joueur (poursuite molle, pas téléguidée)
      - décrémente sa durée de vie
      - inflige des dégâts au joueur s'il y a contact
    Disparaît quand la durée de vie atteint 0 ou si elle touche le joueur.
    """

    # ── Constantes (tweakables) ─────────────────────────────────────
    RADIUS     = 14      # rayon visuel et de collision (px)
    SPEED      = 460     # vitesse de base (px/s) — agressif
    HOMING     = 2.4     # facteur d'attirance vers le joueur (rad/s)
    LIFETIME   = 6.0     # durée avant disparition (s)
    DAMAGE     = 1       # PV retirés au joueur sur impact

    def __init__(self, x, y, target_x, target_y):
        self.x      = float(x)
        self.y      = float(y)
        # Vecteur initial vers la cible
        dx = target_x - x
        dy = target_y - y
        d  = math.hypot(dx, dy) or 1.0
        self.vx = (dx / d) * self.SPEED
        self.vy = (dy / d) * self.SPEED
        self.lifetime  = self.LIFETIME
        self.alive     = True
        # Phase d'animation pour le pulse visuel
        self._phase    = 0.0

    @property
    def rect(self):
        """Rect de collision (centré sur la position courante)."""
        r = self.RADIUS
        return pygame.Rect(int(self.x - r), int(self.y - r), 2 * r, 2 * r)

    def update(self, dt, joueur_rect):
        """Avance le projectile, applique le suivi mou, gère la durée de vie.

        ATTENTION : la collision avec le joueur N'EST PAS gérée ici. C'est
        game.py (boucle principale) qui teste la collision et applique les
        dégâts via joueur.hit_by_enemy() — ce module-ci n'a pas accès à
        l'état d'invincibilité / dash / dodge du joueur. Le projectile est
        marqué `alive = False` par game.py après un hit qui inflige des
        dégâts. Ici, on ne s'auto-détruit que sur expiration de lifetime.
        """
        if not self.alive:
            return False

        self.lifetime -= dt
        self._phase   += dt * 6.0
        if self.lifetime <= 0:
            self.alive = False
            return False

        # ── Suivi mou : on courbe la vélocité vers le joueur ──
        if joueur_rect is not None:
            tgt_dx = joueur_rect.centerx - self.x
            tgt_dy = joueur_rect.centery - self.y
            tgt_d  = math.hypot(tgt_dx, tgt_dy) or 1.0
            # Vélocité désirée vers le joueur, à la même norme
            v_norm = math.hypot(self.vx, self.vy) or 1.0
            desired_vx = (tgt_dx / tgt_d) * v_norm
            desired_vy = (tgt_dy / tgt_d) * v_norm
            # Lerp doux entre vélocité actuelle et désirée
            blend = min(1.0, self.HOMING * dt)
            self.vx += (desired_vx - self.vx) * blend
            self.vy += (desired_vy - self.vy) * blend

        # ── Avance ──
        self.x += self.vx * dt
        self.y += self.vy * dt
        return False

    def draw(self, surf, camera):
        """Dessine la boule d'ombre. Effet : disque sombre avec halo violacé
        et léger pulse pour la vie."""
        if not self.alive:
            return
        sx = int(self.x - getattr(camera, "offset_x", 0))
        sy = int(self.y - getattr(camera, "offset_y", 0))
        # Pulse léger sur le rayon
        pulse = 1.0 + 0.15 * math.sin(self._phase)
        r_visu = int(self.RADIUS * pulse)
        # Halo extérieur (violet sombre, semi-transparent)
        halo = pygame.Surface((r_visu * 4, r_visu * 4), pygame.SRCALPHA)
        pygame.draw.circle(halo, (90, 30, 110, 90),
                           (r_visu * 2, r_visu * 2), r_visu * 2)
        pygame.draw.circle(halo, (40, 10, 60, 200),
                           (r_visu * 2, r_visu * 2), int(r_visu * 1.4))
        surf.blit(halo, (sx - r_visu * 2, sy - r_visu * 2))
        # Cœur opaque
        pygame.draw.circle(surf, (10, 0, 20), (sx, sy), r_visu)
        pygame.draw.circle(surf, (180, 100, 220), (sx, sy), r_visu, 1)
