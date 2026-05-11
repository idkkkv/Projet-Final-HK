# ─────────────────────────────────────────────────────────────────────────────
#  EnemyAIMixin — Détection, poursuite, retour et collisions verticales
# ─────────────────────────────────────────────────────────────────────────────
#
#  Ce mixin contient toute la logique d'intelligence artificielle de l'ennemi.
#
#  MACHINE À ÉTATS :
#    PATROUILLE → voit le joueur                       → POURSUITE
#    POURSUITE  → perd le joueur (mémoire = 0)         → RETOUR
#    RETOUR     → atteint la zone / timeout            → PATROUILLE / SPAWN
#
#  Méthodes de DÉTECTION :
#   _detect_rect              → rectangle de détection (cone ou 360° boss)
#   _chase_rect               → grand rectangle de chasse
#   _has_line_of_sight        → ligne de vue ennemi→joueur (7 points)
#   _is_in_patrol_zone        → l'ennemi est-il dans sa zone ?
#   _can_reach_player_vertically → peut-il atteindre le joueur en hauteur ?
#   _has_ground_ahead         → y a-t-il du sol devant (anti-chute dans trou) ?
#
#  Méthodes d'ACTION :
#   _do_turn                  → demi-tour avec cooldown
#   _teleport_to_spawn        → respawn forcé au point d'origine
#
#  Méthodes de MISE À JOUR :
#   _detecter_joueur          → met à jour chasing/returning chaque frame
#   _gerer_retour             → mouvement de retour vers la patrouille
#   _calculer_vitesse         → choisit vx selon l'état
#   _gerer_collisions_verticales → sol, plafond et trous
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame

import settings
from settings import GRAVITY

# _LOS_SKIP : la ligne de vue n'est recalculée qu'une fois tous les 4 frames.
_LOS_SKIP = 4


class EnemyAIMixin:
    """Logique d'intelligence artificielle (détection, poursuite, retour)."""

    # ─────────────────────────────────────────────────────────────────────────
    # DÉTECTION
    # ─────────────────────────────────────────────────────────────────────────

    def _detect_rect(self):
        """Renvoie le rectangle de détection.

        Cas standard (mob anonyme) : cône directionnel devant l'ennemi.
        Cas BOSS (ennemi nommé) : zone symétrique des deux côtés — le joueur
        ne peut pas se cacher derrière lui pour le taper dans le dos."""
        y = self.rect.y - (self.detect_height - self.hitbox_h) // 2

        if getattr(self, "boss_tier", 0) >= 1:
            return pygame.Rect(
                self.rect.centerx - self.detect_range,
                y,
                self.detect_range * 2 + self.rect.width,
                self.detect_height,
            )

        if self.direction > 0:
            return pygame.Rect(self.rect.right, y,
                               self.detect_range, self.detect_height)
        else:
            return pygame.Rect(self.rect.left - self.detect_range, y,
                               self.detect_range, self.detect_height)

    def _chase_rect(self):
        """Renvoie un grand rectangle autour de l'ennemi (zone de chasse).

        Une fois que l'ennemi a vu le joueur, il continue de le voir même
        s'il passe derrière lui : on élargit la détection dans tous les sens."""
        r = self.detect_range * 2
        return pygame.Rect(self.rect.centerx - r, self.rect.centery - r,
                           r * 2, r * 2)

    def _has_line_of_sight(self, player_rect, walls_near, platforms):
        """True si l'ennemi a une ligne de vue directe sur le joueur.

        On discrétise le segment ennemi→joueur en 7 points et on teste si
        chacun traverse un mur ou une plateforme. Résultat mis en cache
        et recalculé seulement tous les _LOS_SKIP frames."""
        self._los_frame += 1
        if self._los_frame % _LOS_SKIP != 0:
            return self._los_cache

        ex, ey = self.rect.centerx, self.rect.centery
        px, py = player_rect.centerx, player_rect.centery

        vu = True
        for i in range(1, 8):
            t = i / 8
            px_i = int(ex + (px - ex) * t)
            py_i = int(ey + (py - ey) * t)
            point = pygame.Rect(px_i, py_i, 2, 2)

            for w in walls_near:
                if getattr(w, "is_border", False):
                    continue
                if hasattr(w, "rect"):
                    wr = w.rect
                else:
                    wr = w
                if point.colliderect(wr):
                    vu = False
                    break
            if not vu:
                break

            if platforms:
                for p in platforms:
                    if hasattr(p, "rect"):
                        pr = p.rect
                    else:
                        pr = p
                    if pr.height > 10 and point.colliderect(pr):
                        vu = False
                        break
            if not vu:
                break

        self._los_cache = vu
        return vu

    def _is_in_patrol_zone(self):
        """True si l'ennemi est dans sa zone de patrouille (tolérance 5 px)."""
        eps = 5
        return (self.patrol_left - eps
                <= self.rect.centerx
                <= self.patrol_right + eps)

    def _can_reach_player_vertically(self, player_rect):
        """True si le joueur est accessible en sautant (sinon inutile de chasser)."""
        if not self.can_jump:
            return abs(player_rect.centery - self.rect.centery) < self.hitbox_h * 3

        # Hauteur max : v² / (2 × g)
        max_jump_h = (self.jump_power ** 2) / (2 * GRAVITY)
        dy = self.rect.bottom - player_rect.bottom
        return dy < max_jump_h + self.hitbox_h * 2

    def _has_ground_ahead(self, step, walls_near, holes, platforms=None):
        """True s'il y a du sol `step` pixels devant l'ennemi (sinon = trou).

        Teste dans l'ordre : trous explicites → sol global → murs de bordure
        → plateformes custom. Sans le test des plateformes, un ennemi posé
        sur une plateforme surélevée ferait demi-tour en permanence en
        croyant voir un vide."""
        check_x = self.rect.centerx + step * self.direction
        check_y = self.rect.bottom

        # 1. Trou explicite → pas de sol.
        if holes:
            probe = pygame.Rect(check_x - 2, check_y - 4, 4, 8)
            for h in holes:
                if probe.colliderect(h):
                    return False

        # 2. Sol global du monde.
        if abs(check_y - settings.GROUND_Y) < 20:
            return True

        probe = pygame.Rect(check_x - 2, check_y, 4, 8)

        # 3. Mur de bordure.
        for w in walls_near:
            if not getattr(w, "is_border", False):
                continue
            wr = w.rect if hasattr(w, "rect") else w
            if probe.colliderect(wr):
                return True

        # 4. Plateformes custom.
        if platforms:
            if hasattr(platforms, "query"):
                proches = platforms.query(probe)
            else:
                proches = platforms
            for p in proches:
                pr = p.rect if hasattr(p, "rect") else p
                if probe.colliderect(pr):
                    return True

        return False

    # ─────────────────────────────────────────────────────────────────────────
    # ACTIONS
    # ─────────────────────────────────────────────────────────────────────────

    def _do_turn(self):
        """Fait faire demi-tour à l'ennemi (respecte le cooldown de demi-tour)."""
        if self._turn_cooldown > 0:
            return
        self.direction *= -1
        self._turn_cooldown = self._TURN_COOLDOWN_DUR

    def _teleport_to_spawn(self):
        """Téléporte l'ennemi à son point de spawn (après trop long hors zone)."""
        self.rect.x           = self.spawn_x
        self.rect.bottom      = settings.GROUND_Y
        self.vy               = 0
        self.vx               = self.patrol_speed
        self.knockback_vx     = 0.0
        self.chasing          = False
        self.returning        = False
        self._returning_timer = 0.0
        self._hole_cooldown   = 0.0
        self._turn_cooldown   = 0.0
        self._jump_lock       = 0.0
        self.on_ground        = True

    # ─────────────────────────────────────────────────────────────────────────
    # MISE À JOUR IA (appelées chaque frame depuis update())
    # ─────────────────────────────────────────────────────────────────────────

    def _detecter_joueur(self, dt, player_rect, walls_near, platforms, holes):
        """Met à jour chasing / returning selon la détection + mémoire."""
        if self.attack_cooldown <= 0:
            attack_rect = self.rect.inflate(30, 10)
            if attack_rect.colliderect(player_rect):
                self.atk_active = True
                self.attack_timer = 0.3
                self.attack_cooldown = 0.4

        if self.chasing:
            zone = self._chase_rect()
        else:
            zone = self._detect_rect()
        in_zone = zone.colliderect(player_rect)

        # Si le joueur est dans un trou et qu'on ne peut pas tomber → stop.
        if in_zone and not self.can_fall_in_holes:
            if holes:
                joueur_dans_trou = any(
                    player_rect.colliderect(h) for h in holes
                )
                if joueur_dans_trou:
                    in_zone = False
                    if self.chasing:
                        self.chasing          = False
                        self.returning        = True
                        self._returning_timer = 0.0

        # Si en chasse mais qu'on ne peut pas atteindre le joueur en hauteur.
        if in_zone and self.chasing:
            if not self._can_reach_player_vertically(player_rect):
                in_zone = False

        # Ligne de vue.
        can_see = in_zone and self._has_line_of_sight(
            player_rect, walls_near, platforms,
        )

        if can_see:
            self.chasing          = True
            self.returning        = False
            self._returning_timer = 0.0
            self._hole_cooldown   = 0.0
            self.memory_timer     = self.MEMORY_DURATION
            if player_rect.centerx < self.rect.centerx:
                self.last_known_dir = -1
            else:
                self.last_known_dir = 1
        else:
            if self.memory_timer > 0:
                # On s'en souvient encore → on continue de chasser.
                self.memory_timer -= dt
            elif self.chasing:
                # Mémoire perdue → on revient à la patrouille.
                self.chasing          = False
                self.returning        = True
                self._returning_timer = 0.0

    def _gerer_retour(self, dt):
        """Retour vers la zone de patrouille. Renvoie True si téléporté."""
        if self._is_in_patrol_zone():
            self.returning        = False
            self._returning_timer = 0.0
            return False

        # Timeout trop long → téléportation au spawn.
        if self.respawn_timeout > 0:
            self._returning_timer += dt
            if self._returning_timer >= self.respawn_timeout:
                self._teleport_to_spawn()
                return True

        # Marche vers le centre de la zone.
        centre = (self.patrol_left + self.patrol_right) // 2
        if self.rect.centerx < centre - 20:
            self.direction = 1
        elif self.rect.centerx > centre + 20:
            self.direction = -1
        else:
            self.returning        = False
            self._returning_timer = 0.0
        return False

    def _calculer_vitesse(self, player_rect):
        """Calcule self.vx selon l'état (chase / return / patrouille)."""
        if self.chasing and player_rect:
            dx = player_rect.centerx - self.rect.centerx
            if abs(dx) > 30:
                if dx < 0:
                    self.direction = -1
                else:
                    self.direction = 1
            # Boss tier 3 en dash : ×3 sur la vitesse pendant 0.4 s.
            mult = 3.0 if self._boss_dash_timer > 0 else 1.0
            self.vx = self.chase_speed * self.direction * mult

        elif self.returning:
            self.vx = self.patrol_speed * self.direction

        else:
            # Patrouille : demi-tour aux bords de la zone.
            self.vx = self.patrol_speed * self.direction
            if self.rect.left <= self.patrol_left:
                if self.direction != 1:
                    self.direction      = 1
                    self._turn_cooldown = self._TURN_COOLDOWN_DUR
            elif self.rect.right >= self.patrol_right:
                if self.direction != -1:
                    self.direction      = -1
                    self._turn_cooldown = self._TURN_COOLDOWN_DUR

    def _gerer_collisions_verticales(self, holes):
        """Applique sol, plafond et expulsion des trous chaque frame."""
        in_hole = False
        if holes:
            for hole in holes:
                if self.rect.colliderect(hole):
                    in_hole = True
                    break

        # Sol du monde (GROUND_Y).
        if not in_hole and self.rect.bottom > settings.GROUND_Y:
            self.rect.bottom = settings.GROUND_Y
            self.vy          = 0
            self.on_ground   = True
        elif not in_hole and self.rect.bottom < settings.GROUND_Y:
            self.on_ground = False
        elif in_hole:
            self.on_ground = False

        # Plafond.
        if not in_hole and self.rect.top < settings.CEILING_Y:
            self.rect.top = settings.CEILING_Y
            self.vy       = 0

        # Expulsion des trous si can_fall_in_holes=False.
        if not self.can_fall_in_holes and in_hole:
            self.rect.bottom = settings.GROUND_Y
            self.vy          = 0
            self.on_ground   = True
            if self._hole_cooldown <= 0:
                self._do_turn()
                self._hole_cooldown = 0.8
