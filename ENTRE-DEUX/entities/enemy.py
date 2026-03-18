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

_BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENEMIES_DIR = os.path.join(_BASE_DIR, "assets", "images", "enemies")
os.makedirs(ENEMIES_DIR, exist_ok=True)

# Rayon de filtre spatial pour les collisions (px) — on ignore les walls
# trop loin pour qu'ils puissent toucher l'ennemi ce frame.
_CULL_DIST = 300


def list_enemy_sprites():
    sprites = []
    if os.path.isdir(ENEMIES_DIR):
        for f in sorted(os.listdir(ENEMIES_DIR)):
            if f.endswith((".png", ".jpg")):
                sprites.append(f)
    return sprites


def _nearby(walls, rect, margin=_CULL_DIST):
    """Filtre rapide : retourne seulement les walls proches du rect.
    Évite les O(n) colliderect sur tous les segments à chaque frame."""
    cx, cy = rect.centerx, rect.centery
    result = []
    for w in walls:
        wr = w.rect if hasattr(w, 'rect') else w
        if (abs(wr.centerx - cx) < margin and
                abs(wr.centery - cy) < margin):
            result.append(w)
    return result


class Enemy:
    def __init__(self, x, y, has_gravity=True, has_collision=True,
                 sprite_name="monstre_perdu.png", can_jump=False,
                 jump_power=400, detect_range=200, detect_height=80,
                 has_light=False, light_type="dim", light_radius=100,
                 patrol_left=-1, patrol_right=-1, can_jump_patrol=False,
                 can_fall_in_holes=False, respawn_timeout=10.0):

        hb = get_hitbox(sprite_name)
        self.hitbox_w  = hb["w"]
        self.hitbox_h  = hb["h"]
        self.hitbox_ox = hb["ox"]
        self.hitbox_oy = hb["oy"]
        self.rect = pygame.Rect(x, y, self.hitbox_w, self.hitbox_h)

        self.sprite_name = sprite_name
        sprite_path = os.path.join(ENEMIES_DIR, sprite_name)
        img = pygame.image.load(sprite_path if os.path.exists(sprite_path)
                                else find_file(sprite_name))
        self.sprite_w  = img.get_width()
        self.sprite_h  = img.get_height()
        self.idle_anim = Animation([img], img_dur=20)

        self.patrol_speed = 120
        self.chase_speed  = 200
        self.vx           = self.patrol_speed
        self.vy           = 0
        self.direction    = 1
        self.knockback_vx = 0.0

        self.spawn_x = x
        self.spawn_y = y
        self.patrol_left  = patrol_left  if patrol_left  >= 0 else x - 300
        self.patrol_right = patrol_right if patrol_right >= 0 else x + 300

        self.alive            = True
        self.on_ground        = False
        self.has_gravity      = has_gravity
        self.has_collision    = has_collision
        self.can_jump         = can_jump
        self.can_jump_patrol  = can_jump_patrol
        self.jump_power       = jump_power
        self.can_fall_in_holes = can_fall_in_holes
        self.respawn_timeout  = respawn_timeout
        self._returning_timer = 0.0
        self._hole_cooldown   = 0.0

        self._stuck_timer   = 0.0
        self._last_x        = x
        self._stuck_timeout = 0.5

        self.has_light    = has_light
        self.light_type   = light_type
        self.light_radius = light_radius

        self.detect_range    = detect_range
        self.detect_height   = detect_height
        self.chasing         = False
        self.returning       = False
        self.memory_timer    = 0.0
        self.MEMORY_DURATION = 2.5
        self.last_known_dir  = 1
        self.attack_cooldown = 0.0

    # ──────────────────────────────────────────────────────────────────────

    def _teleport_to_spawn(self):
        self.rect.x       = self.spawn_x
        self.rect.bottom  = settings.GROUND_Y
        self.vy = 0; self.vx = self.patrol_speed; self.knockback_vx = 0.0
        self.chasing = False; self.returning = False
        self._returning_timer = 0.0; self._hole_cooldown = 0.0
        self._stuck_timer = 0.0; self._last_x = self.spawn_x
        self.on_ground = True

    def _detect_rect(self):
        if self.direction > 0:
            return pygame.Rect(self.rect.right,
                               self.rect.y - (self.detect_height - self.hitbox_h) // 2,
                               self.detect_range, self.detect_height)
        else:
            return pygame.Rect(self.rect.left - self.detect_range,
                               self.rect.y - (self.detect_height - self.hitbox_h) // 2,
                               self.detect_range, self.detect_height)

    def _chase_rect(self):
        """Zone de maintien de la chasse — grand carré centré, pour ne pas
        perdre le joueur qui saute haut."""
        r = self.detect_range * 2
        return pygame.Rect(self.rect.centerx - r, self.rect.centery - r, r*2, r*2)

    def _has_line_of_sight(self, player_rect, walls, platforms):
        ex, ey = self.rect.centerx, self.rect.centery
        px, py = player_rect.centerx, player_rect.centery
        for i in range(1, 10):
            t  = i / 10
            cx = int(ex + (px - ex) * t)
            cy = int(ey + (py - ey) * t)
            point = pygame.Rect(cx, cy, 2, 2)
            if walls:
                for wall in walls:
                    if getattr(wall, 'is_border', False):
                        continue
                    wr = wall.rect if hasattr(wall, 'rect') else wall
                    if point.colliderect(wr):
                        return False
            if platforms:
                for p in platforms:
                    pr = p.rect if hasattr(p, 'rect') else p
                    if pr.height > 10 and point.colliderect(pr):
                        return False
        return True

    def hit_player(self, player_rect):
        if self.attack_cooldown > 0:
            return False
        self.knockback_vx    = -200 if self.rect.centerx < player_rect.centerx else 200
        self.attack_cooldown = 0.8
        return True

    def _is_in_patrol_zone(self):
        return self.patrol_left <= self.rect.centerx <= self.patrol_right

    def _wall_height_at(self, x, walls):
        """Retourne la hauteur du premier wall dont le bord gauche/droit
        est à la position x (sonde anticipée de saut)."""
        probe = pygame.Rect(x, self.rect.y, 4, self.hitbox_h)
        for w in walls:
            if getattr(w, 'player_only', False):
                continue
            wr = w.rect if hasattr(w, 'rect') else w
            if probe.colliderect(wr):
                return wr.height
        return None

    def _should_jump_ahead(self, total_vx, dt, walls):
        """Sonde anticipée : regarde quelques pixels devant l'ennemi.
        Si un wall se trouve là ET qu'on peut sauter par-dessus,
        retourne True pour déclencher le saut AVANT la collision."""
        if not self.on_ground or not self.can_jump:
            return False
        if not (self.chasing or self.returning or self.can_jump_patrol):
            return False
        # Sonde à ~1.5 frame devant
        lookahead = max(int(abs(total_vx * dt) * 1.5) + 8, 12)
        probe_x   = self.rect.x + lookahead * self.direction
        h = self._wall_height_at(probe_x, walls)
        if h is not None and h <= self.jump_power / 8:
            return True
        return False

    # ──────────────────────────────────────────────────────────────────────

    def update(self, dt, platforms=None, walls=None, player_rect=None, holes=None):
        if not self.alive:
            return

        if self.attack_cooldown > 0: self.attack_cooldown -= dt
        if self._hole_cooldown  > 0: self._hole_cooldown  = max(0.0, self._hole_cooldown - dt)

        # Filtre spatial — on ne teste que les walls proches
        walls_near = _nearby(walls, self.rect) if walls else []

        # ── Détection ────────────────────────────────────────────────────
        if player_rect:
            zone = self._chase_rect() if self.chasing else self._detect_rect()
            can_see = (zone.colliderect(player_rect) and
                       self._has_line_of_sight(player_rect, walls_near, platforms))
            if can_see:
                self.chasing = True; self.returning = False
                self._returning_timer = 0.0; self._hole_cooldown = 0.0
                self._stuck_timer = 0.0; self.memory_timer = self.MEMORY_DURATION
                self.last_known_dir = -1 if player_rect.centerx < self.rect.centerx else 1
            else:
                if self.memory_timer > 0:
                    self.memory_timer -= dt
                elif self.chasing:
                    self.chasing = False; self.returning = True
                    self._returning_timer = 0.0

        # ── Retour à la zone ─────────────────────────────────────────────
        if self.returning:
            if self._is_in_patrol_zone():
                self.returning = False; self._returning_timer = 0.0
            else:
                if self.respawn_timeout > 0:
                    self._returning_timer += dt
                    if self._returning_timer >= self.respawn_timeout:
                        self._teleport_to_spawn(); return
                center = (self.patrol_left + self.patrol_right) // 2
                if   self.rect.centerx < center - 20: self.direction = 1
                elif self.rect.centerx > center + 20: self.direction = -1
                else: self.returning = False; self._returning_timer = 0.0

        # ── Vitesse horizontale ──────────────────────────────────────────
        if self.chasing and player_rect:
            dx = player_rect.centerx - self.rect.centerx
            if abs(dx) > 30: self.direction = -1 if dx < 0 else 1
            self.vx = self.chase_speed * self.direction
        elif self.returning:
            self.vx = self.patrol_speed * self.direction
        else:
            self.vx = self.patrol_speed * self.direction
            if   self.rect.left  <= self.patrol_left:  self.direction = 1
            elif self.rect.right >= self.patrol_right: self.direction = -1

        total_vx = self.vx + self.knockback_vx
        if abs(self.knockback_vx) > 1: self.knockback_vx *= 0.85
        else: self.knockback_vx = 0

        # ── Anti-blocage dans un coin ────────────────────────────────────
        if self.on_ground and not self.chasing:
            if abs(self.rect.x - self._last_x) < 2:
                self._stuck_timer += dt
                if self._stuck_timer >= self._stuck_timeout:
                    self.direction *= -1; self._stuck_timer = 0.0
                    self.rect.x += self.direction * 4
            else:
                self._stuck_timer = 0.0
            self._last_x = self.rect.x

        # ── Sonde anticipée de saut ──────────────────────────────────────
        # On regarde devant AVANT de bouger — si un obstacle sautable est
        # imminent, on saute maintenant sans changer de direction.
        if self._should_jump_ahead(total_vx, dt, walls_near):
            self.vy = -self.jump_power
            self.on_ground = False

        # ── Déplacement horizontal ───────────────────────────────────────
        self.rect.x += int(total_vx * dt)

        # Collisions horizontales walls (filtrées)
        for wall in walls_near:
            if getattr(wall, 'player_only', False): continue
            wr = wall.rect if hasattr(wall, 'rect') else wall
            if not self.rect.colliderect(wr): continue
            if total_vx > 0 and self.rect.right > wr.left and self.rect.left < wr.left:
                self.rect.right = wr.left
                # Saut si possible (déjà géré par la sonde, mais sécurité)
                if self.can_jump and self.on_ground and wr.height <= self.jump_power / 8 and \
                   (self.chasing or self.returning or self.can_jump_patrol):
                    self.vy = -self.jump_power; self.on_ground = False
                else:
                    self.direction *= -1
            elif total_vx < 0 and self.rect.left < wr.right and self.rect.right > wr.right:
                self.rect.left = wr.right
                if self.can_jump and self.on_ground and wr.height <= self.jump_power / 8 and \
                   (self.chasing or self.returning or self.can_jump_patrol):
                    self.vy = -self.jump_power; self.on_ground = False
                else:
                    self.direction *= -1

        # Collisions horizontales plateformes
        if self.has_collision and platforms:
            for p in platforms:
                plat = p.rect if hasattr(p, 'rect') else p
                if not self.rect.colliderect(plat): continue
                can_jump_now = (self.chasing and self.can_jump) or self.can_jump_patrol
                if total_vx > 0 and self.rect.right > plat.left and self.rect.left < plat.left:
                    self.rect.right = plat.left
                    if can_jump_now and self.on_ground and plat.height <= self.jump_power / 8:
                        self.vy = -self.jump_power; self.on_ground = False
                    else: self.direction *= -1
                elif total_vx < 0 and self.rect.left < plat.right and self.rect.right > plat.right:
                    self.rect.left = plat.right
                    if can_jump_now and self.on_ground and plat.height <= self.jump_power / 8:
                        self.vy = -self.jump_power; self.on_ground = False
                    else: self.direction *= -1

        # ── Gravité ──────────────────────────────────────────────────────
        if self.has_gravity:
            self.vy     += GRAVITY * dt
            self.rect.y += int(self.vy * dt)

            if not self.can_fall_in_holes:
                if self.rect.bottom > settings.GROUND_Y:
                    self.rect.bottom = settings.GROUND_Y
                    self.vy = 0; self.on_ground = True
                else:
                    self.on_ground = False

                if self.on_ground and holes and self._hole_cooldown <= 0:
                    step  = max(int(abs(total_vx * dt)) + 12, 20)
                    probe = pygame.Rect(self.rect.x + step * self.direction,
                                        settings.GROUND_Y - 2, self.rect.width, 4)
                    if any(probe.colliderect(h) for h in holes):
                        if self.can_jump:
                            self.vy = -self.jump_power; self.on_ground = False
                            self._hole_cooldown = 0.5
                        else:
                            self.direction *= -1
                            self.rect.x -= int(total_vx * dt) * 4
                            self._hole_cooldown = 0.5
            else:
                in_hole = holes and any(self.rect.colliderect(h) for h in holes)
                if not in_hole and self.rect.bottom > settings.GROUND_Y:
                    self.rect.bottom = settings.GROUND_Y
                    self.vy = 0; self.on_ground = True
                elif not in_hole:
                    self.on_ground = False

        # Collision verticale plateformes
        if self.has_collision and platforms:
            for p in platforms:
                plat = p.rect if hasattr(p, 'rect') else p
                if self.rect.colliderect(plat):
                    if self.vy >= 0 and self.rect.bottom <= plat.top + 20:
                        self.rect.bottom = plat.top
                        self.vy = 0; self.on_ground = True

        # Collision verticale walls (filtrées)
        for wall in walls_near:
            if getattr(wall, 'player_only', False): continue
            wr = wall.rect if hasattr(wall, 'rect') else wall
            if not self.rect.colliderect(wr): continue
            ot  = self.rect.bottom - wr.top
            ob  = wr.bottom - self.rect.top
            ol  = self.rect.right  - wr.left
            or_ = wr.right - self.rect.left
            mn  = min(ot, ob, ol, or_)
            if mn == ot and self.vy >= 0:
                self.rect.bottom = wr.top; self.vy = 0; self.on_ground = True
            elif mn == ob and self.vy < 0:
                self.rect.top = wr.bottom; self.vy = 0

    # ──────────────────────────────────────────────────────────────────────

    def draw(self, surf, camera, show_hitbox=False):
        if not self.alive:
            return
        img = self.idle_anim.img()
        if self.direction < 0:
            img = pygame.transform.flip(img, True, False)
        self.idle_anim.update()

        if self.direction >= 0:
            sx = self.rect.x - self.hitbox_ox
            sy = self.rect.y - self.hitbox_oy
        else:
            sx = self.rect.x - (self.sprite_w - self.hitbox_ox - self.hitbox_w)
            sy = self.rect.y - self.hitbox_oy
        surf.blit(img, camera.apply(pygame.Rect(sx, sy, self.sprite_w, self.sprite_h)))

        if show_hitbox:
            pygame.draw.rect(surf, (255,0,0), camera.apply(self.rect), 1)
            if self.chasing:
                pygame.draw.rect(surf, (255,80,80), camera.apply(self._chase_rect()), 1)
            else:
                pygame.draw.rect(surf, (255,255,0), camera.apply(self._detect_rect()), 1)

            pl = int(self.patrol_left  - camera.offset_x)
            pr = int(self.patrol_right - camera.offset_x)
            py = int(self.rect.bottom  - camera.offset_y) + 5
            pygame.draw.line(surf, (0,200,0), (pl,py), (pr,py), 2)
            pygame.draw.line(surf, (0,200,0), (pl,py-4), (pl,py+4), 2)
            pygame.draw.line(surf, (0,200,0), (pr,py-4), (pr,py+4), 2)

            if self.can_jump and self.jump_power > 0:
                mjh  = int((self.jump_power**2) / (2*GRAVITY))
                jtop = int(self.rect.bottom - camera.offset_y) - mjh
                lx   = self.rect.x     - int(camera.offset_x) - 5
                rx   = self.rect.right - int(camera.offset_x) + 5
                mx2  = self.rect.centerx - int(camera.offset_x)
                fy2  = int(self.rect.bottom - camera.offset_y)
                pygame.draw.line(surf, (0,220,220), (lx,jtop), (rx,jtop), 1)
                pygame.draw.line(surf, (0,220,220), (mx2,fy2), (mx2,jtop), 1)
                font = pygame.font.SysFont("Consolas", 11)
                surf.blit(font.render(f"{mjh}px", True, (0,220,220)), (rx+3, jtop-5))

            cx = self.rect.centerx - int(camera.offset_x)
            cy = self.rect.centery - int(camera.offset_y)
            ex = cx + 25 * self.direction
            pygame.draw.line(surf, (255,255,0), (cx,cy), (ex,cy), 2)
            pygame.draw.line(surf, (255,255,0), (ex,cy), (ex-6*self.direction,cy-5), 2)
            pygame.draw.line(surf, (255,255,0), (ex,cy), (ex-6*self.direction,cy+5), 2)

            if self.chasing:
                font = pygame.font.SysFont("Consolas", 14)
                surf.blit(font.render("!", True, (255,50,50)), (cx-3, cy-30))
            elif self.returning:
                font = pygame.font.SysFont("Consolas", 12)
                if self.respawn_timeout > 0:
                    rem = max(0.0, self.respawn_timeout - self._returning_timer)
                    surf.blit(font.render(f"<< {rem:.0f}s", True, (100,200,100)), (cx-18,cy-28))
                else:
                    surf.blit(font.render("<<", True, (100,200,100)), (cx-8,cy-28))

            if self.memory_timer > 0 and not self.chasing:
                ratio = self.memory_timer / self.MEMORY_DURATION
                bx = self.rect.x - int(camera.offset_x)
                by = self.rect.y - int(camera.offset_y) - 8
                pygame.draw.rect(surf, (255,150,0), (bx, by, int(self.hitbox_w*ratio), 3))

            if self.can_fall_in_holes:
                fx = self.rect.centerx - int(camera.offset_x)
                fy = self.rect.bottom  - int(camera.offset_y) + 8
                pygame.draw.polygon(surf, (0,220,220), [(fx,fy+8),(fx-6,fy),(fx+6,fy)])

            if self._hole_cooldown > 0:
                ratio = self._hole_cooldown / 0.5
                bx = self.rect.x - int(camera.offset_x)
                by = int(self.rect.bottom - camera.offset_y) + 3
                pygame.draw.rect(surf, (255,120,0), (bx, by, int(self.hitbox_w*ratio), 2))

            if self._stuck_timer > 0.2:
                bx = self.rect.x - int(camera.offset_x)
                by = self.rect.y - int(camera.offset_y) - 12
                pygame.draw.rect(surf, (255,0,0),
                    (bx, by, int(self.hitbox_w * self._stuck_timer / self._stuck_timeout), 2))

    def get_light_pos(self):
        return (self.rect.centerx, self.rect.centery)

    def to_dict(self):
        return {
            "x": self.rect.x, "y": self.rect.y,
            "has_gravity":       self.has_gravity,
            "has_collision":     self.has_collision,
            "sprite_name":       self.sprite_name,
            "can_jump":          self.can_jump,
            "can_jump_patrol":   self.can_jump_patrol,
            "jump_power":        self.jump_power,
            "detect_range":      self.detect_range,
            "detect_height":     self.detect_height,
            "has_light":         self.has_light,
            "light_type":        self.light_type,
            "light_radius":      self.light_radius,
            "patrol_left":       self.patrol_left,
            "patrol_right":      self.patrol_right,
            "can_fall_in_holes": self.can_fall_in_holes,
            "respawn_timeout":   self.respawn_timeout,
        }
    

    