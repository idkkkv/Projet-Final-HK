# ─────────────────────────────────────────
#  ENTRE-DEUX — Ennemi
# ─────────────────────────────────────────

import os
import random
import pygame
import settings
from settings import *
from entities.animation import Animation
from systems.hitbox_config import get_hitbox
from utils import *

_BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENEMIES_DIR = os.path.join(_BASE_DIR, "assets", "images", "enemies")
os.makedirs(ENEMIES_DIR, exist_ok=True)

_CULL_DIST = 400
_LOS_SKIP  = 4

<<<<<<< HEAD
=======
# Fonts partagés entre toutes les instances — créés une seule fois
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce
_font_dbg_small = None
_font_dbg_tiny  = None

def _get_debug_fonts():
    global _font_dbg_small, _font_dbg_tiny
    if _font_dbg_small is None:
        _font_dbg_small = pygame.font.SysFont("Consolas", 12)
        _font_dbg_tiny  = pygame.font.SysFont("Consolas", 11)
    return _font_dbg_small, _font_dbg_tiny


def list_enemy_sprites():
    sprites = []
    if os.path.isdir(ENEMIES_DIR):
        for f in sorted(os.listdir(ENEMIES_DIR)):
            if f.endswith((".png", ".jpg")):
                sprites.append(f)
    return sprites


def _nearby(walls, rect, margin=_CULL_DIST):
    cx, cy = rect.centerx, rect.centery
    result = []
    for w in walls:
        wr = w.rect if hasattr(w, 'rect') else w
        if abs(wr.centerx - cx) < margin and abs(wr.centery - cy) < margin:
            result.append(w)
    return result


class Enemy:
    def __init__(self, x, y, has_gravity=True, has_collision=True,
                 sprite_name="monstre_perdu.png", can_jump=False,
                 jump_power=400, detect_range=200, detect_height=80,
                 has_light=False, light_type="dim", light_radius=100,
                 patrol_left=-1, patrol_right=-1, can_jump_patrol=False,
                 can_fall_in_holes=False, respawn_timeout=10.0,
                 can_turn_randomly=False,
                 patrol_speed=120, chase_speed=200):

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

<<<<<<< HEAD
        self.patrol_speed = patrol_speed   # vitesse patrouille (configurable)
        self.chase_speed  = chase_speed    # vitesse poursuite (configurable)
=======
        self.patrol_speed = 120
        self.chase_speed  = 200
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce
        self.vx = self.patrol_speed
        self.vy = 0
        self.direction    = 1
        self.knockback_vx = 0.0

        self.spawn_x = x
        self.spawn_y = y
        self.patrol_left  = patrol_left  if patrol_left  >= 0 else x - 300
        self.patrol_right = patrol_right if patrol_right >= 0 else x + 300

        self.alive              = True
        self.on_ground          = False
        self.has_gravity        = has_gravity
        self.has_collision      = has_collision
        self.can_jump           = can_jump
        self.can_jump_patrol    = can_jump_patrol
        self.jump_power         = jump_power
        self.can_fall_in_holes  = can_fall_in_holes
        self.can_turn_randomly  = can_turn_randomly
        self._random_turn_timer = random.uniform(3.0, 6.0)
        self.respawn_timeout    = respawn_timeout
        self._returning_timer   = 0.0
        self._hole_cooldown     = 0.0

        self._turn_cooldown     = 0.0
        self._TURN_COOLDOWN_DUR = 0.8

        self._jump_lock     = 0.0
        self._JUMP_LOCK_DUR = 0.6

        self._los_frame = 0
        self._los_cache = True

        self._jump_lock     = 0.0
        self._JUMP_LOCK_DUR = 0.4

        self._los_frame = 0
        self._los_cache = True

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

    def _teleport_to_spawn(self):
        self.rect.x = self.spawn_x
        self.rect.bottom = settings.GROUND_Y
        self.vy = 0; self.vx = self.patrol_speed; self.knockback_vx = 0.0
        self.chasing = False; self.returning = False
        self._returning_timer = 0.0; self._hole_cooldown = 0.0
<<<<<<< HEAD
        self._turn_cooldown = 0.0; self._jump_lock = 0.0
        self.on_ground = True
=======
        self._stuck_timer = 0.0; self._last_x = self.spawn_x
        self._jump_lock = 0.0; self.on_ground = True
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce

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
        r = self.detect_range * 2
        return pygame.Rect(self.rect.centerx - r, self.rect.centery - r, r*2, r*2)

<<<<<<< HEAD
    def _has_line_of_sight(self, player_rect, walls_near, platforms):
=======
    def _has_line_of_sight(self, player_rect, walls, platforms):
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce
        self._los_frame += 1
        if self._los_frame % _LOS_SKIP != 0:
            return self._los_cache
        ex, ey = self.rect.centerx, self.rect.centery
        px, py = player_rect.centerx, player_rect.centery
        result = True
        for i in range(1, 8):
<<<<<<< HEAD
            t = i / 8
            point = pygame.Rect(int(ex+(px-ex)*t), int(ey+(py-ey)*t), 2, 2)
            for w in walls_near:
                if getattr(w, 'is_border', False): continue
                wr = w.rect if hasattr(w, 'rect') else w
=======
            t  = i / 8
            cx = int(ex + (px - ex) * t)
            cy = int(ey + (py - ey) * t)
            point = pygame.Rect(cx, cy, 2, 2)
            for wall in walls:
                if getattr(wall, 'is_border', False): continue
                wr = wall.rect if hasattr(wall, 'rect') else wall
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce
                if point.colliderect(wr): result = False; break
            if not result: break
            if platforms:
                for p in platforms:
                    pr = p.rect if hasattr(p, 'rect') else p
                    if pr.height > 10 and point.colliderect(pr):
                        result = False; break
            if not result: break
        self._los_cache = result
        return result

    def hit_player(self, player_rect):
        if self.attack_cooldown > 0: return False
        self.knockback_vx = -200 if self.rect.centerx < player_rect.centerx else 200
        self.attack_cooldown = 0.8
        return True

    def _is_in_patrol_zone(self):
        return self.patrol_left <= self.rect.centerx <= self.patrol_right

<<<<<<< HEAD
    def _can_reach_player_vertically(self, player_rect):
        if not self.can_jump:
            return abs(player_rect.centery - self.rect.centery) < self.hitbox_h * 3
        max_jump_h = (self.jump_power ** 2) / (2 * GRAVITY)
        dy = self.rect.bottom - player_rect.bottom
        return dy < max_jump_h + self.hitbox_h * 2

    def _has_ground_ahead(self, step, walls_near, holes):
        check_x = self.rect.centerx + step * self.direction
        check_y = self.rect.bottom
        if holes:
            probe = pygame.Rect(check_x - 2, check_y - 4, 4, 8)
            for h in holes:
                if probe.colliderect(h):
                    return False
        if abs(check_y - settings.GROUND_Y) < 20:
            return True
        probe = pygame.Rect(check_x - 2, check_y, 4, 8)
        for w in walls_near:
            if not getattr(w, 'is_border', False): continue
            wr = w.rect if hasattr(w, 'rect') else w
            if probe.colliderect(wr): return True
        return False

    def _do_turn(self):
        if self._turn_cooldown > 0:
            return
        self.direction *= -1
        self._turn_cooldown = self._TURN_COOLDOWN_DUR

    def on_wall_collision_horizontal(self, wall_height):
        """Appelé par game.py quand verifier_collision détecte un blocage horizontal."""
        if self._jump_lock > 0:
            return
        can_jp = self.chasing or self.returning or self.can_jump_patrol
        # nearly_grounded : au sol OU en train de tomber (pas en saut)
        # Couvre le cas où on_ground n'est pas encore True ce frame
        nearly_grounded = self.on_ground or self.vy >= 0
        if self.can_jump and nearly_grounded and can_jp and wall_height <= self.jump_power / 8:
            # Saut — pas bloqué par _turn_cooldown
            self.vy = -self.jump_power
            self.on_ground = False
            self._jump_lock = self._JUMP_LOCK_DUR
        elif self._turn_cooldown <= 0:
            # Demi-tour — respecte le cooldown
            self._do_turn()

    # ──────────────────────────────────────────────────────────────────────
=======
    def _probe_wall_ahead(self, total_vx, dt, walls_near):
        if not self.on_ground: return None
        lookahead = max(int(abs(total_vx * dt) * 1.5) + 10, 14)
        probe = pygame.Rect(self.rect.x + lookahead * self.direction,
                            self.rect.y, 4, self.hitbox_h)
        for w in walls_near:
            if getattr(w, 'player_only', False): continue
            wr = w.rect if hasattr(w, 'rect') else w
            if probe.colliderect(wr): return w
        return None

    def _probe_hole_ahead(self, total_vx, dt, holes):
        if not self.on_ground or not holes: return False
        step  = max(int(abs(total_vx * dt)) + 12, 20)
        probe = pygame.Rect(self.rect.x + step * self.direction,
                            settings.GROUND_Y - 2, self.rect.width, 4)
        return any(probe.colliderect(h) for h in holes)
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce

    def update(self, dt, platforms=None, walls=None, player_rect=None, holes=None):
        if not self.alive: return

        if self.attack_cooldown > 0: self.attack_cooldown -= dt
        if self._hole_cooldown  > 0: self._hole_cooldown  = max(0.0, self._hole_cooldown - dt)
        if self._jump_lock      > 0: self._jump_lock       = max(0.0, self._jump_lock - dt)
<<<<<<< HEAD
        if self._turn_cooldown  > 0: self._turn_cooldown   = max(0.0, self._turn_cooldown - dt)
=======
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce

        walls_near = _nearby(walls, self.rect) if walls else []

        # ── Détection ────────────────────────────────────────────────────
        if player_rect:
            zone = self._chase_rect() if self.chasing else self._detect_rect()
            in_zone = zone.colliderect(player_rect)
<<<<<<< HEAD

            if in_zone and not self.can_fall_in_holes:
                if holes and any(player_rect.colliderect(h) for h in holes):
                    in_zone = False
                    if self.chasing:
                        self.chasing = False
                        self.returning = True
                        self._returning_timer = 0.0

            if in_zone and self.chasing:
                if not self._can_reach_player_vertically(player_rect):
                    in_zone = False

            can_see = in_zone and self._has_line_of_sight(player_rect, walls_near, platforms)

=======
            player_in_hole = holes and any(player_rect.colliderect(h) for h in holes)
            if player_in_hole and not self.can_fall_in_holes:
                in_zone = False
            can_see = in_zone and self._has_line_of_sight(player_rect, walls_near, platforms)
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce
            if can_see:
                self.chasing = True; self.returning = False
                self._returning_timer = 0.0; self._hole_cooldown = 0.0
                self.memory_timer = self.MEMORY_DURATION
                self.last_known_dir = -1 if player_rect.centerx < self.rect.centerx else 1
            else:
                if self.memory_timer > 0: self.memory_timer -= dt
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
            if self.rect.left <= self.patrol_left:
                if self.direction != 1:
                    self.direction = 1
                    self._turn_cooldown = self._TURN_COOLDOWN_DUR
            elif self.rect.right >= self.patrol_right:
                if self.direction != -1:
                    self.direction = -1
                    self._turn_cooldown = self._TURN_COOLDOWN_DUR

        total_vx = self.vx + self.knockback_vx
        if abs(self.knockback_vx) > 1: self.knockback_vx *= 0.85
        else: self.knockback_vx = 0

<<<<<<< HEAD
        # ── Demi-tour aléatoire ──────────────────────────────────────────
        if (self.can_turn_randomly and self.on_ground
                and not self.chasing and not self.returning
                and self._jump_lock <= 0 and self._turn_cooldown <= 0):
            self._random_turn_timer -= dt
            if self._random_turn_timer <= 0:
                if random.random() < 0.3:
                    self._do_turn()
                self._random_turn_timer = random.uniform(3.0, 6.0)

        # ── Demi-tour bord de trou ────────────────────────────────────────
        if (not self.can_fall_in_holes and self.on_ground
                and self._hole_cooldown <= 0 and self._turn_cooldown <= 0):
            step = max(int(abs(total_vx * dt)) + self.hitbox_w // 2, 24)
            if not self._has_ground_ahead(step, walls_near, holes):
                self._do_turn()
                self.rect.x -= int(total_vx * dt) * 4
                self._hole_cooldown = 0.6
                total_vx = 0
=======
        # ── Anti-blocage coin ────────────────────────────────────────────
        if self.on_ground and not self.chasing and self._jump_lock <= 0:
            if abs(self.rect.x - self._last_x) < 2:
                self._stuck_timer += dt
                if self._stuck_timer >= self._stuck_timeout:
                    self.direction *= -1; self._stuck_timer = 0.0
                    self.rect.x += self.direction * 4
            else:
                self._stuck_timer = 0.0
            self._last_x = self.rect.x

        # ── Sonde anticipée ──────────────────────────────────────────────
        can_jump_now = self.can_jump and self.on_ground
        will_jump = False

        if can_jump_now and self._jump_lock <= 0:
            if not self.can_fall_in_holes and self._probe_hole_ahead(total_vx, dt, holes):
                if self.chasing or self.can_jump_patrol:
                    self.vy = -self.jump_power; self.on_ground = False
                    self._jump_lock = self._JUMP_LOCK_DUR
                    self._hole_cooldown = 0.5; will_jump = True
                else:
                    self.direction *= -1
                    self.rect.x -= int(total_vx * dt) * 4
                    self._hole_cooldown = 0.5

            if not will_jump and (self.chasing or self.returning or self.can_jump_patrol):
                w_ahead = self._probe_wall_ahead(total_vx, dt, walls_near)
                if w_ahead is not None:
                    wr = w_ahead.rect if hasattr(w_ahead, 'rect') else w_ahead
                    if wr.height <= self.jump_power / 8:
                        self.vy = -self.jump_power; self.on_ground = False
                        self._jump_lock = self._JUMP_LOCK_DUR; will_jump = True

        # ── Déplacement horizontal ───────────────────────────────────────
        self.rect.x += int(total_vx * dt)

        for wall in walls_near:
            if getattr(wall, 'player_only', False): continue
            wr = wall.rect if hasattr(wall, 'rect') else wall
            if not self.rect.colliderect(wr): continue
            if total_vx > 0 and self.rect.right > wr.left and self.rect.left < wr.left:
                self.rect.right = wr.left
                if not will_jump and self._jump_lock <= 0:
                    if self.can_jump and self.on_ground and wr.height <= self.jump_power / 8 and \
                       (self.chasing or self.returning or self.can_jump_patrol):
                        self.vy = -self.jump_power; self.on_ground = False
                        self._jump_lock = self._JUMP_LOCK_DUR; will_jump = True
                    else: self.direction *= -1
            elif total_vx < 0 and self.rect.left < wr.right and self.rect.right > wr.right:
                self.rect.left = wr.right
                if not will_jump and self._jump_lock <= 0:
                    if self.can_jump and self.on_ground and wr.height <= self.jump_power / 8 and \
                       (self.chasing or self.returning or self.can_jump_patrol):
                        self.vy = -self.jump_power; self.on_ground = False
                        self._jump_lock = self._JUMP_LOCK_DUR; will_jump = True
                    else: self.direction *= -1

        if self.has_collision and platforms:
            for p in platforms:
                plat = p.rect if hasattr(p, 'rect') else p
                if not self.rect.colliderect(plat): continue
                can_jp = (self.chasing and self.can_jump) or self.can_jump_patrol
                if total_vx > 0 and self.rect.right > plat.left and self.rect.left < plat.left:
                    self.rect.right = plat.left
                    if can_jp and self.on_ground and plat.height <= self.jump_power / 8 and not will_jump:
                        self.vy = -self.jump_power; self.on_ground = False
                        self._jump_lock = self._JUMP_LOCK_DUR; will_jump = True
                    elif not will_jump: self.direction *= -1
                elif total_vx < 0 and self.rect.left < plat.right and self.rect.right > plat.right:
                    self.rect.left = plat.right
                    if can_jp and self.on_ground and plat.height <= self.jump_power / 8 and not will_jump:
                        self.vy = -self.jump_power; self.on_ground = False
                        self._jump_lock = self._JUMP_LOCK_DUR; will_jump = True
                    elif not will_jump: self.direction *= -1
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce

        # ── Gravité ──────────────────────────────────────────────────────
        if self.has_gravity:
            self.vy += GRAVITY * dt

<<<<<<< HEAD
        # ── Déplacement ──────────────────────────────────────────────────
        self.rect.x += int(total_vx * dt)
        self.rect.y += int(self.vy * dt)

        # ── In_hole / Sol ─────────────────────────────────────────────────
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
        elif not in_hole and self.rect.bottom < settings.GROUND_Y:
            self.on_ground = False
        elif in_hole:
            self.on_ground = False

        if not in_hole and self.rect.top < settings.CEILING_Y:
            self.rect.top = settings.CEILING_Y
            self.vy = 0

        # Expulsion trou si can_fall_in_holes=False
        if not self.can_fall_in_holes and in_hole:
            self.rect.bottom = settings.GROUND_Y
            self.vy = 0
            self.on_ground = True
            if self._hole_cooldown <= 0:
                self._do_turn()
                self._hole_cooldown = 0.8
=======
            if not self.can_fall_in_holes:
                if self.rect.bottom > settings.GROUND_Y:
                    self.rect.bottom = settings.GROUND_Y
                    self.vy = 0; self.on_ground = True
                else: self.on_ground = False
            else:
                in_hole = holes and any(self.rect.colliderect(h) for h in holes)
                if not in_hole and self.rect.bottom > settings.GROUND_Y:
                    self.rect.bottom = settings.GROUND_Y
                    self.vy = 0; self.on_ground = True
                else:
                    if not in_hole: self.on_ground = False

        if self.has_collision and platforms:
            for p in platforms:
                plat = p.rect if hasattr(p, 'rect') else p
                if self.rect.colliderect(plat):
                    if self.vy >= 0 and self.rect.bottom <= plat.top + 20:
                        self.rect.bottom = plat.top
                        self.vy = 0; self.on_ground = True

        for wall in walls_near:
            if getattr(wall, 'player_only', False): continue
            wr = wall.rect if hasattr(wall, 'rect') else wall
            if not self.rect.colliderect(wr): continue
            ot = self.rect.bottom - wr.top
            ob = wr.bottom - self.rect.top
            ol = self.rect.right  - wr.left
            or_ = wr.right - self.rect.left
            mn = min(ot, ob, ol, or_)
            if mn == ot and self.vy >= 0:
                self.rect.bottom = wr.top; self.vy = 0; self.on_ground = True
            elif mn == ob and self.vy < 0:
                self.rect.top = wr.bottom; self.vy = 0
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce

    def draw(self, surf, camera, show_hitbox=False):
        if not self.alive: return
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

<<<<<<< HEAD
        if not show_hitbox: return

=======
        if not show_hitbox:
            return

        # Fonts cachés — plus de SysFont par frame
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce
        font_s, font_t = _get_debug_fonts()

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
<<<<<<< HEAD
            surf.blit(font_t.render(f"{mjh}px", True, (0,220,220)), (rx+3, jtop-5))
=======
            surf.blit(font_t.render(f"{mjh}px", True, (0,220,220)),
                      (rx+3, jtop-5))
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce

        cx = self.rect.centerx - int(camera.offset_x)
        cy = self.rect.centery - int(camera.offset_y)
        ex = cx + 25 * self.direction
        pygame.draw.line(surf, (255,255,0), (cx,cy), (ex,cy), 2)
        pygame.draw.line(surf, (255,255,0), (ex,cy), (ex-6*self.direction,cy-5), 2)
        pygame.draw.line(surf, (255,255,0), (ex,cy), (ex-6*self.direction,cy+5), 2)

        if self.chasing:
            surf.blit(font_s.render("!", True, (255,50,50)), (cx-3, cy-30))
        elif self.returning:
            if self.respawn_timeout > 0:
                rem = max(0.0, self.respawn_timeout - self._returning_timer)
                surf.blit(font_s.render(f"<< {rem:.0f}s", True, (100,200,100)), (cx-18,cy-28))
            else:
                surf.blit(font_s.render("<<", True, (100,200,100)), (cx-8,cy-28))

        if self.memory_timer > 0 and not self.chasing:
            ratio = self.memory_timer / self.MEMORY_DURATION
            bx = self.rect.x - int(camera.offset_x)
            by = self.rect.y - int(camera.offset_y) - 8
            pygame.draw.rect(surf, (255,150,0), (bx, by, int(self.hitbox_w*ratio), 3))

        if self.can_fall_in_holes:
            fx = self.rect.centerx - int(camera.offset_x)
            fy = self.rect.bottom  - int(camera.offset_y) + 8
            pygame.draw.polygon(surf, (0,220,220), [(fx,fy+8),(fx-6,fy),(fx+6,fy)])

<<<<<<< HEAD
        if self.can_turn_randomly:
            fx = self.rect.centerx - int(camera.offset_x)
            fy = self.rect.bottom  - int(camera.offset_y) + 14
            pygame.draw.polygon(surf, (200,100,255), [(fx,fy+6),(fx-5,fy),(fx+5,fy)])

        if self._hole_cooldown > 0:
            ratio = self._hole_cooldown / 0.8
            bx = self.rect.x - int(camera.offset_x)
            by = int(self.rect.bottom - camera.offset_y) + 3
            pygame.draw.rect(surf, (255,120,0), (bx, by, int(self.hitbox_w*ratio), 2))

        # Vitesses affichées en mode debug
        spd_txt = f"p:{self.patrol_speed} c:{self.chase_speed}"
        surf.blit(font_t.render(spd_txt, True, (180,180,255)),
                  (cx - 20, cy - 44))
=======
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
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce

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
<<<<<<< HEAD
            "can_turn_randomly": self.can_turn_randomly,
            "patrol_speed":      self.patrol_speed,
            "chase_speed":       self.chase_speed,
        }
=======
        }
>>>>>>> 351da4f4be0af0233a53dd061de2feec0afef2ce
