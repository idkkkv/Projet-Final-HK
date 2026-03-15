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
        # Hitbox
        hb = get_hitbox(sprite_name)
        self.hitbox_w = hb["w"]
        self.hitbox_h = hb["h"]
        self.hitbox_ox = hb["ox"]
        self.hitbox_oy = hb["oy"]
        self.rect = pygame.Rect(x, y, self.hitbox_w, self.hitbox_h)

        # Sprite
        self.sprite_name = sprite_name
        sprite_path = os.path.join(ENEMIES_DIR, sprite_name)
        if os.path.exists(sprite_path):
            img = pygame.image.load(sprite_path)
        else:
            img = pygame.image.load(find_file(sprite_name))
        self.sprite_w = img.get_width()
        self.sprite_h = img.get_height()
        self.idle_anim = Animation([img], img_dur=20)

        # Mouvement
        self.patrol_speed = 120
        self.chase_speed = 200
        self.vx = self.patrol_speed
        self.vy = 0
        self.direction = 1
        self.knockback_vx = 0.0

        # Zone de patrouille (par défaut ±300px autour du spawn)
        self.spawn_x = x
        self.spawn_y = y
        self.patrol_left = patrol_left if patrol_left >= 0 else x - 300
        self.patrol_right = patrol_right if patrol_right >= 0 else x + 300

        # Options
        self.alive = True
        self.on_ground = False
        self.has_gravity = has_gravity
        self.has_collision = has_collision
        self.can_jump = can_jump
        self.jump_power = jump_power

        # Lumière attachée
        self.has_light = has_light
        self.light_type = light_type
        self.light_radius = light_radius

        # Détection
        self.detect_range = detect_range
        self.detect_height = detect_height
        self.chasing = False
        self.returning = False   # en train de retourner à sa zone
        self.memory_timer = 0.0
        self.MEMORY_DURATION = 2.5
        self.last_known_dir = 1
        self.attack_cooldown = 0.0

    def _detect_rect(self):
        if self.direction > 0:
            return pygame.Rect(
                self.rect.right,
                self.rect.y - (self.detect_height - self.hitbox_h) // 2,
                self.detect_range, self.detect_height)
        else:
            return pygame.Rect(
                self.rect.left - self.detect_range,
                self.rect.y - (self.detect_height - self.hitbox_h) // 2,
                self.detect_range, self.detect_height)

    def _has_line_of_sight(self, player_rect, walls, platforms):
        """Vérifie qu'aucun mur ou plateforme ne bloque la vue."""
        # Ligne entre les centres
        ex, ey = self.rect.centerx, self.rect.centery
        px, py = player_rect.centerx, player_rect.centery

        # On teste 10 points le long de la ligne
        steps = 10
        for i in range(1, steps):
            t = i / steps
            cx = int(ex + (px - ex) * t)
            cy = int(ey + (py - ey) * t)
            point = pygame.Rect(cx, cy, 2, 2)

            # Vérifie les murs
            if walls:
                for wall in walls:
                    wr = wall.rect if hasattr(wall, 'rect') else wall
                    if point.colliderect(wr):
                        return False

            # Vérifie les plateformes (seulement les hautes,
            # pas celles au niveau des pieds)
            if platforms:
                for p in platforms:
                    pr = p.rect if hasattr(p, 'rect') else p
                    # Ignore les plateformes au même niveau
                    if pr.height > 10 and point.colliderect(pr):
                        return False
        return True

    def hit_player(self, player_rect):
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

    def update(self, dt, platforms=None, walls=None, player_rect=None, holes=None):
        if not self.alive:
            return

        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt

        # ── Détection ──
        if player_rect:
            detect = self._detect_rect()
            can_see_zone = detect.colliderect(player_rect)

            # Vérification de la ligne de vue (pas à travers les murs)
            all_obstacles = (walls or [])
            can_see = can_see_zone and self._has_line_of_sight(
                player_rect, all_obstacles, platforms)

            if can_see:
                self.chasing = True
                self.returning = False
                self.memory_timer = self.MEMORY_DURATION
                if player_rect.centerx < self.rect.centerx:
                    self.last_known_dir = -1
                else:
                    self.last_known_dir = 1
            else:
                if self.memory_timer > 0:
                    self.memory_timer -= dt
                else:
                    if self.chasing:
                        # Perd le joueur → commence à retourner
                        self.chasing = False
                        self.returning = True

        # ── Retour à la zone de patrouille ──
        if self.returning:
            if self._is_in_patrol_zone():
                self.returning = False
            else:
                # Se dirige vers le centre de sa zone
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
            # Patrouille : demi-tour aux limites de la zone
            self.vx = self.patrol_speed * self.direction
            if self.rect.left <= self.patrol_left:
                self.direction = 1
            elif self.rect.right >= self.patrol_right:
                self.direction = -1

        total_vx = self.vx + self.knockback_vx
        if abs(self.knockback_vx) > 1:
            self.knockback_vx *= 0.85
        else:
            self.knockback_vx = 0

        # ── Déplacement horizontal ──
        self.rect.x += int(total_vx * dt)

        # Murs de la scène
        if walls and len(walls) > 3:
            if self.rect.colliderect(walls[2].rect):
                self.rect.left = walls[2].rect.right
                self.direction = 1
            if self.rect.colliderect(walls[3].rect):
                self.rect.right = walls[3].rect.left
                self.direction = -1

        # Murs custom
        if walls:
            for wall in walls[4:]:
                wr = wall.rect if hasattr(wall, 'rect') else wall
                if self.rect.colliderect(wr):
                    if total_vx > 0:
                        self.rect.right = wr.left
                    else:
                        self.rect.left = wr.right
                    if not self.chasing:
                        self.direction *= -1
                    elif self.can_jump and self.on_ground:
                        # Saute seulement si l'obstacle est assez bas
                        if wr.height <= self.jump_power / 8:
                            self.vy = -self.jump_power
                            self.on_ground = False

        # Collision latérale plateformes
        if self.has_collision and platforms:
            for p in platforms:
                plat = p.rect if hasattr(p, 'rect') else p
                if self.rect.colliderect(plat):
                    if total_vx > 0 and self.rect.right > plat.left and self.rect.left < plat.left:
                        self.rect.right = plat.left
                        if not self.chasing:
                            self.direction *= -1
                        elif self.can_jump and self.on_ground and plat.height <= self.jump_power / 8:
                            self.vy = -self.jump_power
                            self.on_ground = False
                    elif total_vx < 0 and self.rect.left < plat.right and self.rect.right > plat.right:
                        self.rect.left = plat.right
                        if not self.chasing:
                            self.direction *= -1
                        elif self.can_jump and self.on_ground and plat.height <= self.jump_power / 8:
                            self.vy = -self.jump_power
                            self.on_ground = False

        # ── Gravité ──
        if self.has_gravity:
            self.vy += GRAVITY * dt
            self.rect.y += int(self.vy * dt)

            # Vérifier si dans un trou
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

        if self.has_collision and platforms:
            for p in platforms:
                plat = p.rect if hasattr(p, 'rect') else p
                if self.rect.colliderect(plat):
                    if self.vy >= 0 and self.rect.bottom <= plat.top + 20:
                        self.rect.bottom = plat.top
                        self.vy = 0
                        self.on_ground = True

    def draw(self, surf, camera, show_hitbox=False):
        if not self.alive:
            return
        img = self.idle_anim.img()
        if self.direction < 0:
            img = pygame.transform.flip(img, True, False)
        self.idle_anim.update()

        # Sprite centré horizontalement, pieds au bas de la hitbox
        sprite_x = self.rect.centerx - self.sprite_w // 2
        sprite_y = self.rect.bottom - self.sprite_h
        sprite_rect = pygame.Rect(sprite_x, sprite_y, self.sprite_w, self.sprite_h)
        surf.blit(img, camera.apply(sprite_rect))

        if show_hitbox:
            # Hitbox
            pygame.draw.rect(surf, (255, 0, 0), camera.apply(self.rect), 1)
            # Zone détection
            pygame.draw.rect(surf, (255, 255, 0), camera.apply(self._detect_rect()), 1)

            # Zone de patrouille (ligne verte en bas)
            pl = int(self.patrol_left - camera.offset_x)
            pr = int(self.patrol_right - camera.offset_x)
            py = int(self.rect.bottom - camera.offset_y) + 5
            pygame.draw.line(surf, (0, 200, 0), (pl, py), (pr, py), 2)
            pygame.draw.line(surf, (0, 200, 0), (pl, py-4), (pl, py+4), 2)
            pygame.draw.line(surf, (0, 200, 0), (pr, py-4), (pr, py+4), 2)

            # Hauteur max de saut (ligne cyan pointillée)
            if self.can_jump and self.jump_power > 0:
                # Formule : hauteur max = v² / (2*g)
                max_jump_h = int((self.jump_power * self.jump_power) / (2 * GRAVITY))
                jump_top = int(self.rect.bottom - camera.offset_y) - max_jump_h
                left_x = self.rect.x - int(camera.offset_x) - 5
                right_x = self.rect.right - int(camera.offset_x) + 5
                # Ligne horizontale cyan = hauteur max
                pygame.draw.line(surf, (0, 220, 220), (left_x, jump_top), (right_x, jump_top), 1)
                # Ligne verticale du sol à la hauteur max
                foot_y = int(self.rect.bottom - camera.offset_y)
                mid_x = self.rect.centerx - int(camera.offset_x)
                pygame.draw.line(surf, (0, 220, 220), (mid_x, foot_y), (mid_x, jump_top), 1)
                # Texte hauteur
                font = pygame.font.SysFont("Consolas", 11)
                surf.blit(font.render(f"{max_jump_h}px", True, (0, 220, 220)),
                          (right_x + 3, jump_top - 5))

            # Flèche direction
            cx = self.rect.centerx - int(camera.offset_x)
            cy = self.rect.centery - int(camera.offset_y)
            ex = cx + 25 * self.direction
            pygame.draw.line(surf, (255, 255, 0), (cx, cy), (ex, cy), 2)
            pygame.draw.line(surf, (255, 255, 0), (ex, cy),
                             (ex - 6*self.direction, cy-5), 2)
            pygame.draw.line(surf, (255, 255, 0), (ex, cy),
                             (ex - 6*self.direction, cy+5), 2)

            # État
            if self.chasing:
                font = pygame.font.SysFont("Consolas", 14)
                surf.blit(font.render("!", True, (255, 50, 50)), (cx-3, cy-30))
            elif self.returning:
                font = pygame.font.SysFont("Consolas", 12)
                surf.blit(font.render("<<", True, (100, 200, 100)), (cx-8, cy-28))

            if self.memory_timer > 0 and not self.chasing:
                ratio = self.memory_timer / self.MEMORY_DURATION
                bw = int(self.hitbox_w * ratio)
                bx = self.rect.x - int(camera.offset_x)
                by = self.rect.y - int(camera.offset_y) - 8
                pygame.draw.rect(surf, (255, 150, 0), (bx, by, bw, 3))

    def get_light_pos(self):
        return (self.rect.centerx, self.rect.centery)

    def to_dict(self):
        return {
            "x": self.rect.x, "y": self.rect.y,
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