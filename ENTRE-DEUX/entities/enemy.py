# ─────────────────────────────────────────
#  ENTRE-DEUX — Ennemi
# ─────────────────────────────────────────

import os
import pygame
import settings
from settings import *
from entities.animation import Animation
from systems.hitbox_config import get_hitbox
from utils import *

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENEMIES_DIR = os.path.join(_BASE_DIR, "assets", "images", "enemies")
os.makedirs(ENEMIES_DIR, exist_ok=True)


def list_enemy_sprites():
    """Liste les sprites disponibles dans le dossier enemies/."""
    sprites = []
    if os.path.isdir(ENEMIES_DIR):
        for f in sorted(os.listdir(ENEMIES_DIR)):
            if f.endswith((".png", ".jpg")):
                sprites.append(f)
    return sprites


class Enemy:
    def __init__(self, x, y, has_gravity=True, has_collision=True,
                 sprite_name="monstre_perdu.png", can_jump=False,
                 jump_power=400, detect_range=200, detect_height=80,
                 has_light=False, light_type="dim", light_radius=100,
                 patrol_left=-1, patrol_right=-1):

        # ── Hitbox (chargée depuis hitbox_config.py) ──
        hb = get_hitbox(sprite_name)
        self.hitbox_w = hb["w"]
        self.hitbox_h = hb["h"]
        self.hitbox_ox = hb["ox"]   # offset X du sprite vers la hitbox
        self.hitbox_oy = hb["oy"]   # offset Y
        self.rect = pygame.Rect(x, y, self.hitbox_w, self.hitbox_h)

        # ── Sprite ──
        self.sprite_name = sprite_name
        sprite_path = os.path.join(ENEMIES_DIR, sprite_name)
        if os.path.exists(sprite_path):
            img = pygame.image.load(sprite_path)
        else:
            img = pygame.image.load(find_file(sprite_name))
        self.sprite_w = img.get_width()
        self.sprite_h = img.get_height()
        self.idle_anim = Animation([img], img_dur=20)

        # ── Mouvement ──
        self.patrol_speed = 120
        self.chase_speed = 200
        self.vx = self.patrol_speed
        self.vy = 0
        self.direction = 1          # 1 = droite, -1 = gauche
        self.knockback_vx = 0.0

        # ── Zone de patrouille ──
        self.spawn_x = x
        self.spawn_y = y
        self.patrol_left = patrol_left if patrol_left >= 0 else x - 300
        self.patrol_right = patrol_right if patrol_right >= 0 else x + 300

        # ── Options ──
        self.alive = True
        self.on_ground = False
        self.has_gravity = has_gravity
        self.has_collision = has_collision
        self.can_jump = can_jump
        self.jump_power = jump_power

        # ── Lumière attachée ──
        self.has_light = has_light
        self.light_type = light_type
        self.light_radius = light_radius

        # ── Détection ──
        self.detect_range = detect_range
        self.detect_height = detect_height
        self.chasing = False
        self.returning = False
        self.memory_timer = 0.0
        self.MEMORY_DURATION = 2.5
        self.last_known_dir = 1
        self.attack_cooldown = 0.0

    # ─────────────────────────────────────
    #  Utilitaires
    # ─────────────────────────────────────

    def _detect_rect(self):
        """Rectangle de détection devant l'ennemi."""
        dy = (self.detect_height - self.hitbox_h) // 2
        if self.direction > 0:
            return pygame.Rect(
                self.rect.right,
                self.rect.y - dy,
                self.detect_range,
                self.detect_height)
        else:
            return pygame.Rect(
                self.rect.left - self.detect_range,
                self.rect.y - dy,
                self.detect_range,
                self.detect_height)

    def _max_jump_height(self):
        """Hauteur max de saut avec la vraie formule physique : v²/(2g)."""
        if self.jump_power <= 0 or GRAVITY <= 0:
            return 0
        return int((self.jump_power ** 2) / (2 * GRAVITY))

    def _has_line_of_sight(self, player_rect, walls, platforms):
        """Vérifie qu'aucun mur ou plateforme ne bloque la vue."""
        ex, ey = self.rect.centerx, self.rect.centery
        px, py = player_rect.centerx, player_rect.centery

        # Teste 10 points le long de la ligne
        for i in range(1, 10):
            t = i / 10
            cx = int(ex + (px - ex) * t)
            cy = int(ey + (py - ey) * t)
            point = pygame.Rect(cx, cy, 2, 2)

            # Murs
            if walls:
                for wall in walls:
                    wr = wall.rect if hasattr(wall, 'rect') else wall
                    if point.colliderect(wr):
                        return False

            # Plateformes épaisses
            if platforms:
                for p in platforms:
                    pr = p.rect if hasattr(p, 'rect') else p
                    if pr.height > 10 and point.colliderect(pr):
                        return False
        return True

    def _hole_cancels(self, wall_rect, holes):
        """Retourne True si un trou annule la collision avec ce mur."""
        if not holes:
            return False
        for hole in holes:
            if hole.colliderect(wall_rect) and hole.colliderect(self.rect):
                return True
        return False

    def hit_player(self, player_rect):
        """Appelé quand l'ennemi touche le joueur → recul de l'ennemi."""
        if self.attack_cooldown > 0:
            return False
        if self.rect.centerx < player_rect.centerx:
            self.knockback_vx = -200
        else:
            self.knockback_vx = 200
        self.attack_cooldown = 0.8
        return True

    def _is_in_patrol_zone(self):
        return self.patrol_left <= self.rect.centerx <= self.patrol_right

    # ─────────────────────────────────────
    #  Mise à jour (chaque frame)
    # ─────────────────────────────────────

    def update(self, dt, platforms=None, walls=None, player_rect=None, holes=None):
        if not self.alive:
            return

        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt

        # ── Détection du joueur ──
        if player_rect:
            detect = self._detect_rect()
            can_see = (detect.colliderect(player_rect) and
                       self._has_line_of_sight(player_rect, walls or [], platforms))

            if can_see:
                self.chasing = True
                self.returning = False
                self.memory_timer = self.MEMORY_DURATION
                if player_rect.centerx < self.rect.centerx:
                    self.last_known_dir = -1
                else:
                    self.last_known_dir = 1
            else:
                # Mémoire : continue de chercher X secondes
                if self.memory_timer > 0:
                    self.memory_timer -= dt
                else:
                    if self.chasing:
                        self.chasing = False
                        self.returning = True

        # ── Retour à la zone de patrouille ──
        if self.returning:
            if self._is_in_patrol_zone():
                self.returning = False
            else:
                center = (self.patrol_left + self.patrol_right) // 2
                if self.rect.centerx < center - 20:
                    self.direction = 1
                elif self.rect.centerx > center + 20:
                    self.direction = -1
                else:
                    self.returning = False

        # ── Vitesse horizontale ──
        if self.chasing and player_rect:
            dx = player_rect.centerx - self.rect.centerx
            if abs(dx) > 30:
                self.direction = -1 if dx < 0 else 1
            self.vx = self.chase_speed * self.direction
        elif self.returning:
            self.vx = self.patrol_speed * self.direction
        else:
            # Patrouille : demi-tour aux limites
            self.vx = self.patrol_speed * self.direction
            if self.rect.left <= self.patrol_left:
                self.direction = 1
            elif self.rect.right >= self.patrol_right:
                self.direction = -1

        # Knockback (diminue avec la friction)
        total_vx = self.vx + self.knockback_vx
        if abs(self.knockback_vx) > 1:
            self.knockback_vx *= 0.85
        else:
            self.knockback_vx = 0

        # ── Déplacement horizontal ──
        self.rect.x += int(total_vx * dt)
        max_jh = self._max_jump_height()

        # Murs de la scène (avec annulation par trou)
        if walls and len(walls) > 3:
            # Mur gauche
            if (self.rect.colliderect(walls[2].rect) and
                    not self._hole_cancels(walls[2].rect, holes)):
                self.rect.left = walls[2].rect.right
                self.direction = 1
            # Mur droit
            if (self.rect.colliderect(walls[3].rect) and
                    not self._hole_cancels(walls[3].rect, holes)):
                self.rect.right = walls[3].rect.left
                self.direction = -1

        # Murs custom (avec annulation par trou)
        if walls:
            for wall in walls[4:]:
                wr = wall.rect if hasattr(wall, 'rect') else wall
                if self.rect.colliderect(wr) and not self._hole_cancels(wr, holes):
                    if total_vx > 0:
                        self.rect.right = wr.left
                    else:
                        self.rect.left = wr.right
                    if not self.chasing:
                        self.direction *= -1
                    elif self.can_jump and self.on_ground and wr.height <= max_jh:
                        self.vy = -self.jump_power
                        self.on_ground = False

        # Collision latérale plateformes
        if self.has_collision and platforms:
            for p in platforms:
                plat = p.rect if hasattr(p, 'rect') else p
                if self.rect.colliderect(plat):
                    if (total_vx > 0 and self.rect.right > plat.left
                            and self.rect.left < plat.left):
                        self.rect.right = plat.left
                        if not self.chasing:
                            self.direction *= -1
                        elif self.can_jump and self.on_ground and plat.height <= max_jh:
                            self.vy = -self.jump_power
                            self.on_ground = False
                    elif (total_vx < 0 and self.rect.left < plat.right
                            and self.rect.right > plat.right):
                        self.rect.left = plat.right
                        if not self.chasing:
                            self.direction *= -1
                        elif self.can_jump and self.on_ground and plat.height <= max_jh:
                            self.vy = -self.jump_power
                            self.on_ground = False

        # ── Gravité ──
        if self.has_gravity:
            self.vy += GRAVITY * dt
            self.rect.y += int(self.vy * dt)

            # Vérifier si dans un trou (ignore le sol)
            in_hole = False
            if holes:
                for hole in holes:
                    if self.rect.colliderect(hole):
                        in_hole = True
                        break

            if not in_hole and self.rect.bottom > settings.GROUND_Y:
                self.rect.bottom = settings.GROUND_Y
                self.vy = 0
                self.on_ground = True
            elif not in_hole:
                self.on_ground = False

        # Collision verticale plateformes (atterrissage)
        if self.has_collision and platforms:
            for p in platforms:
                plat = p.rect if hasattr(p, 'rect') else p
                if self.rect.colliderect(plat):
                    if self.vy >= 0 and self.rect.bottom <= plat.top + 20:
                        self.rect.bottom = plat.top
                        self.vy = 0
                        self.on_ground = True

    # ─────────────────────────────────────
    #  Affichage
    # ─────────────────────────────────────

    def draw(self, surf, camera, show_hitbox=False):
        if not self.alive:
            return

        img = self.idle_anim.img()
        if self.direction < 0:
            img = pygame.transform.flip(img, True, False)
        self.idle_anim.update()

        # Sprite positionné avec l'offset de hitbox
        if self.direction >= 0:
            sprite_x = self.rect.x - self.hitbox_ox
            sprite_y = self.rect.y - self.hitbox_oy
        else:
            # Quand retourné, l'offset X est miroir
            flipped_ox = self.sprite_w - self.hitbox_ox - self.hitbox_w
            sprite_x = self.rect.x - flipped_ox
            sprite_y = self.rect.y - self.hitbox_oy
        sprite_rect = pygame.Rect(sprite_x, sprite_y,
                                  self.sprite_w, self.sprite_h)
        surf.blit(img, camera.apply(sprite_rect))

        # ── Debug (H) ──
        if show_hitbox:
            # Hitbox rouge
            pygame.draw.rect(surf, (255, 0, 0), camera.apply(self.rect), 1)

            # Zone de détection jaune
            pygame.draw.rect(surf, (255, 255, 0),
                             camera.apply(self._detect_rect()), 1)

            # Zone de patrouille (ligne verte)
            pl = int(self.patrol_left - camera.offset_x)
            pr = int(self.patrol_right - camera.offset_x)
            py = int(self.rect.bottom - camera.offset_y) + 5
            pygame.draw.line(surf, (0, 200, 0), (pl, py), (pr, py), 2)
            pygame.draw.line(surf, (0, 200, 0), (pl, py - 4), (pl, py + 4), 2)
            pygame.draw.line(surf, (0, 200, 0), (pr, py - 4), (pr, py + 4), 2)

            # Hauteur max de saut (ligne cyan)
            if self.can_jump and self.jump_power > 0:
                mjh = self._max_jump_height()
                cx = self.rect.centerx - int(camera.offset_x)
                foot = int(self.rect.bottom - camera.offset_y)
                top = foot - mjh
                lx = self.rect.x - int(camera.offset_x) - 5
                rx = self.rect.right - int(camera.offset_x) + 5
                # Ligne horizontale = hauteur max
                pygame.draw.line(surf, (0, 220, 220), (lx, top), (rx, top), 1)
                # Ligne verticale
                pygame.draw.line(surf, (0, 220, 220), (cx, foot), (cx, top), 1)
                # Texte
                font = pygame.font.SysFont("Consolas", 11)
                surf.blit(font.render(f"{mjh}px", True, (0, 220, 220)),
                          (rx + 3, top - 5))

            # Flèche direction
            cx = self.rect.centerx - int(camera.offset_x)
            cy = self.rect.centery - int(camera.offset_y)
            ex = cx + 25 * self.direction
            pygame.draw.line(surf, (255, 255, 0), (cx, cy), (ex, cy), 2)
            pygame.draw.line(surf, (255, 255, 0), (ex, cy),
                             (ex - 6 * self.direction, cy - 5), 2)
            pygame.draw.line(surf, (255, 255, 0), (ex, cy),
                             (ex - 6 * self.direction, cy + 5), 2)

            # État : ! = poursuite, << = retour
            if self.chasing:
                font = pygame.font.SysFont("Consolas", 14)
                surf.blit(font.render("!", True, (255, 50, 50)),
                          (cx - 3, cy - 30))
            elif self.returning:
                font = pygame.font.SysFont("Consolas", 12)
                surf.blit(font.render("<<", True, (100, 200, 100)),
                          (cx - 8, cy - 28))

            # Barre de mémoire (orange, diminue)
            if self.memory_timer > 0 and not self.chasing:
                ratio = self.memory_timer / self.MEMORY_DURATION
                bw = int(self.hitbox_w * ratio)
                bx = self.rect.x - int(camera.offset_x)
                by = self.rect.y - int(camera.offset_y) - 8
                pygame.draw.rect(surf, (255, 150, 0), (bx, by, bw, 3))

    # ─────────────────────────────────────
    #  Utilitaires publics
    # ─────────────────────────────────────

    def get_light_pos(self):
        """Position de la lumière attachée (centre)."""
        return (self.rect.centerx, self.rect.centery)

    def to_dict(self):
        """Sérialise l'ennemi pour la sauvegarde JSON."""
        return {
            "x": self.rect.x,
            "y": self.rect.y,
            "has_gravity": self.has_gravity,
            "has_collision": self.has_collision,
            "sprite_name": self.sprite_name,
            "can_jump": self.can_jump,
            "jump_power": self.jump_power,
            "detect_range": self.detect_range,
            "detect_height": self.detect_height,
            "has_light": self.has_light,
            "light_type": self.light_type,
            "light_radius": self.light_radius,
            "patrol_left": self.patrol_left,
            "patrol_right": self.patrol_right,
        }