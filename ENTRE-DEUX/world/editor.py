# ─────────────────────────────────────────
#  ENTRE-DEUX — Éditeur de niveaux
# ─────────────────────────────────────────

import os
import pygame
import json
import settings
from entities.enemy import Enemy, list_enemy_sprites
from systems.hitbox_config import get_hitbox, set_hitbox
from settings import *
from world.tilemap import Platform, Wall
from utils import find_file

LIGHT_TYPES = ["player", "torch", "large", "cool", "dim", "background"]

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS_DIR = os.path.join(_BASE_DIR, "maps")


class Portal:
    def __init__(self, x, y, w, h, target_map, target_x=-1, target_y=-1):
        self.rect = pygame.Rect(x, y, w, h)
        self.target_map = target_map
        self.target_x = target_x
        self.target_y = target_y

    def to_dict(self):
        return {"x": self.rect.x, "y": self.rect.y,
                "w": self.rect.width, "h": self.rect.height,
                "target_map": self.target_map,
                "target_x": self.target_x, "target_y": self.target_y}

    def draw(self, surf, camera, font):
        sr = camera.apply(self.rect)
        s = pygame.Surface((sr.w, sr.h), pygame.SRCALPHA)
        s.fill((0, 120, 255, 60))
        surf.blit(s, sr)
        pygame.draw.rect(surf, (0, 120, 255), sr, 2)
        txt = font.render(f"-> {self.target_map}", True, (0, 180, 255))
        surf.blit(txt, (sr.x, sr.y - 18))


class Editor:
    def __init__(self, platforms, enemies, camera, lighting, player):
        self.platforms = platforms
        self.enemies = enemies
        self.camera = camera
        self.lighting = lighting
        self.player = player
        self.active = False
        self.first_point = None
        self.portals = []
        self.custom_walls = []
        self.hole_borders = []

        # 0=Plateforme 1=Mob 2=Lumiere 3=Spawn 4=Portail 5=Mur 6=Hitbox 7=Trou 8=Copier/Coller
        self.mode = 0
        self._mode_names = ["Plateforme", "Mob", "Lumiere",
                            "Spawn", "Portail", "Mur", "Hitbox", "Trou", "Copier/Coller"]

        self.holes = []

        # Copy/Paste (mode 8)
        self._copy_rect = None
        self._clipboard_platforms = []
        self._clipboard_walls = []
        self._copy_origin = None
        self._has_clipboard = False

        # Lumiere
        self.light_type_index = 1
        self.light_flicker = False
        self.light_flicker_speed = 5
        self.light_first_point = None

        # Mob
        self.mob_gravity = True
        self.mob_collision = True
        self.mob_can_jump = False
        self.mob_can_jump_patrol = False
        self.mob_detect_range = 200
        self.mob_has_light = False
        self.mob_sprite_index = 0
        self.mob_can_fall_in_holes = False   # ← NOUVEAU
        self.mob_respawn_timeout = 10.0      # ← NOUVEAU (-1 = désactivé)
        self._enemy_sprites = []
        self._refresh_sprites()

        # Mob patrol editing
        self.mob_patrol_mode = False
        self._patrol_target = None
        self._patrol_first_x = None

        # Mob detection editing
        self.mob_detect_mode = False
        self._detect_target = None

        # Hitbox editor
        self._hb_sprite_index = 0
        self._hb_first_point = None

        # Display
        self.show_hitboxes = False

        # Text input
        self._text_input = ""
        self._text_mode = None
        self._text_prompt = ""
        self._pending_portal_rect = None

        # Spawn
        self.spawn_x = self.player.spawn_x
        self.spawn_y = self.player.spawn_y

        # Per-map
        self.bg_color = list(BLEU)
        self.wall_color = [0, 0, 0]

        self._font = None
        self._font_small = None
        os.makedirs(MAPS_DIR, exist_ok=True)

    def _get_font(self):
        if self._font is None:
            self._font = pygame.font.SysFont("Consolas", 16)
            self._font_small = pygame.font.SysFont("Consolas", 13)
        return self._font

    def _refresh_sprites(self):
        self._enemy_sprites = list_enemy_sprites()
        if not self._enemy_sprites:
            self._enemy_sprites = ["monstre_perdu.png"]

    def _current_sprite(self):
        if self._enemy_sprites:
            return self._enemy_sprites[self.mob_sprite_index % len(self._enemy_sprites)]
        return "monstre_perdu.png"

    def toggle(self):
        self.active = not self.active
        self.first_point = None
        self.light_first_point = None
        self._text_mode = None
        self._hb_first_point = None

    def change_mode(self):
        self.mode = (self.mode + 1) % 9
        self.first_point = None
        self.light_first_point = None
        self._hb_first_point = None
        self.mob_patrol_mode = False
        self._patrol_target = None
        self._patrol_first_x = None
        self.mob_detect_mode = False
        self._detect_target = None
        self._copy_rect = None
        if self.mode in (1, 6):
            self._refresh_sprites()

    # ── Touches ──────────────────────────────

    def handle_key(self, key):
        if self._text_mode is not None:
            return self._handle_text(key)

        if key == pygame.K_m:
            self.change_mode()
        elif key == pygame.K_h:
            self.show_hitboxes = not self.show_hitboxes
        elif key == pygame.K_n:
            self._new_map()
            return "done"
        elif key == pygame.K_s:
            self._ask_text("save", "Sauvegarder sous :")
            return "text_input"
        elif key == pygame.K_l:
            maps = self._list_maps()
            p = "Charger :" + (f"  ({', '.join(maps)})" if maps else "")
            self._ask_text("load", p)
            return "text_input"
        elif key == pygame.K_r:
            self.player.respawn()
        elif key == pygame.K_b:
            self.spawn_x = self.spawn_y = 100
            self.player.spawn_x = self.player.spawn_y = 100
            self.player.respawn()

        # Sol / Plafond
        elif key == pygame.K_UP:
            settings.GROUND_Y = max(100, settings.GROUND_Y - 20)
        elif key == pygame.K_DOWN:
            settings.GROUND_Y = min(3000, settings.GROUND_Y + 20)
        elif key == pygame.K_HOME:
            settings.CEILING_Y = max(-500, settings.CEILING_Y - 20)
        elif key == pygame.K_END:
            settings.CEILING_Y = min(settings.GROUND_Y - 100, settings.CEILING_Y + 20)

        # Scene
        elif key == pygame.K_LEFT:
            settings.SCENE_WIDTH = max(800, settings.SCENE_WIDTH - 100)
            self.camera.scene_width = settings.SCENE_WIDTH
        elif key == pygame.K_RIGHT:
            settings.SCENE_WIDTH += 100
            self.camera.scene_width = settings.SCENE_WIDTH
        elif key == pygame.K_PAGEUP:
            self.camera.y_offset = max(-400, self.camera.y_offset - 20)
        elif key == pygame.K_PAGEDOWN:
            self.camera.y_offset = min(400, self.camera.y_offset + 20)

        # Lumiere
        elif key == pygame.K_t and self.mode == 2:
            self.light_type_index = (self.light_type_index + 1) % len(LIGHT_TYPES)
        elif key == pygame.K_f and self.mode == 2:
            self.light_flicker = not self.light_flicker

        # Mob
        elif key == pygame.K_g and self.mode == 1:
            self.mob_gravity = not self.mob_gravity
        elif key == pygame.K_c and self.mode == 1:
            self.mob_collision = not self.mob_collision
        elif key == pygame.K_j and self.mode == 1:
            self.mob_can_jump = not self.mob_can_jump
        elif key == pygame.K_v and self.mode == 1:
            self.mob_can_jump_patrol = not self.mob_can_jump_patrol
        elif key == pygame.K_i and self.mode == 1:
            self.mob_has_light = not self.mob_has_light
        elif key == pygame.K_o and self.mode == 1:                      # ← NOUVEAU
            self.mob_can_fall_in_holes = not self.mob_can_fall_in_holes
            print(f"Tombe dans trous : {'ON' if self.mob_can_fall_in_holes else 'OFF'}")
        elif key == pygame.K_t and self.mode == 1:
            self.mob_sprite_index = (self.mob_sprite_index + 1) % max(1, len(self._enemy_sprites))

        # Timeout respawn (pavé numérique * et /)                        # ← NOUVEAU
        elif key == pygame.K_KP_MULTIPLY and self.mode == 1:
            if self.mob_respawn_timeout < 0:
                self.mob_respawn_timeout = 5.0
            else:
                self.mob_respawn_timeout = min(120.0, self.mob_respawn_timeout + 5.0)
            print(f"Respawn timeout = {self.mob_respawn_timeout:.0f}s")
        elif key == pygame.K_KP_DIVIDE and self.mode == 1:
            self.mob_respawn_timeout = max(-1.0, self.mob_respawn_timeout - 5.0)
            if self.mob_respawn_timeout == 0.0:
                self.mob_respawn_timeout = -1.0
            val = f"{self.mob_respawn_timeout:.0f}s" if self.mob_respawn_timeout > 0 else "OFF"
            print(f"Respawn timeout = {val}")

        elif key == pygame.K_KP_PLUS and self.mode == 1 and self.mob_detect_mode and self._detect_target:
            self._detect_target.detect_range = min(600, self._detect_target.detect_range + 25)
            print(f"Portee mob = {self._detect_target.detect_range}")
        elif key == pygame.K_KP_MINUS and self.mode == 1 and self.mob_detect_mode and self._detect_target:
            self._detect_target.detect_range = max(50, self._detect_target.detect_range - 25)
            print(f"Portee mob = {self._detect_target.detect_range}")
        elif key == pygame.K_KP_PLUS and self.mode == 1:
            self.mob_detect_range = min(500, self.mob_detect_range + 25)
        elif key == pygame.K_KP_MINUS and self.mode == 1:
            self.mob_detect_range = max(50, self.mob_detect_range - 25)

        elif key == pygame.K_p and self.mode == 1:
            self.mob_patrol_mode = not self.mob_patrol_mode
            self.mob_detect_mode = False
            self._patrol_target = None
            self._patrol_first_x = None
            print(f"Patrouille : {'ON - clic sur un mob puis 2 clics pour la zone' if self.mob_patrol_mode else 'OFF'}")
        elif key == pygame.K_d and self.mode == 1:
            self.mob_detect_mode = not self.mob_detect_mode
            self.mob_patrol_mode = False
            self._detect_target = None
            print(f"Detection : {'ON - clic sur un mob, +/- portee, clic G/D du mob = direction' if self.mob_detect_mode else 'OFF'}")

        # Hitbox editor
        elif key == pygame.K_t and self.mode == 6:
            self._hb_sprite_index = (self._hb_sprite_index + 1) % max(1, len(self._enemy_sprites))
            self._hb_first_point = None

        # Copy/Paste
        elif key == pygame.K_c and self.mode == 8:
            self._do_copy()
        elif key == pygame.K_v and self.mode == 8:
            if self._has_clipboard:
                mx, my = pygame.mouse.get_pos()
                wx = int(mx + self.camera.offset_x)
                wy = int(my + self.camera.offset_y)
                self._do_paste(wx, wy)

        return None

    def _new_map(self):
        self.platforms.clear()
        self.enemies.clear()
        self.lighting.lights.clear()
        self.portals.clear()
        self.custom_walls.clear()
        self.hole_borders.clear()
        self.holes.clear()
        self._copy_rect = None
        self._has_clipboard = False
        settings.GROUND_Y = 590
        settings.CEILING_Y = 0
        settings.SCENE_WIDTH = 2400
        self.spawn_x = self.spawn_y = 100
        self.player.spawn_x = self.player.spawn_y = 100
        self.player.respawn()
        self.camera.y_offset = 150
        self.bg_color = list(VIOLET)

    def _merge_holes(self):
        if not self.holes:
            return []
        merged = [h.copy() for h in self.holes]
        changed = True
        while changed:
            changed = False
            result = []
            used = [False] * len(merged)
            for i in range(len(merged)):
                if used[i]:
                    continue
                current = merged[i].copy()
                for j in range(i + 1, len(merged)):
                    if used[j]:
                        continue
                    exp = pygame.Rect(current.x - 1, current.y - 1,
                                      current.w + 2, current.h + 2)
                    if exp.colliderect(merged[j]):
                        current = current.union(merged[j])
                        used[j] = True
                        changed = True
                result.append(current)
            merged = result
        return merged

    def rebuild_hole_borders(self):
        self.hole_borders.clear()
        t = 20
        gy = settings.GROUND_Y
        cy = settings.CEILING_Y
        sw = settings.SCENE_WIDTH

        for hole in self._merge_holes():
            hx, hy, hw, hh = hole.x, hole.y, hole.width, hole.height
            hx2 = hx + hw
            hy2 = hy + hh

            if hy2 > gy - t:
                side_top = max(hy, gy)
                side_bot = hy2 + t
                side_h   = side_bot - side_top
                if side_h > 0:
                    self.hole_borders.append(
                        Wall(hx - t, side_top, t, side_h, visible=True, player_only=True))
                    self.hole_borders.append(
                        Wall(hx2, side_top, t, side_h, visible=True, player_only=True))
                self.hole_borders.append(
                    Wall(hx - t, hy2, hw + t * 2, t, visible=True, player_only=True))

            elif hy < cy + t:
                side_top = hy - t
                side_bot = min(hy2, cy)
                side_h   = side_bot - side_top
                if side_h > 0:
                    self.hole_borders.append(
                        Wall(hx - t, side_top, t, side_h, visible=True, player_only=True))
                    self.hole_borders.append(
                        Wall(hx2, side_top, t, side_h, visible=True, player_only=True))
                self.hole_borders.append(
                    Wall(hx - t, hy - t, hw + t * 2, t, visible=True, player_only=True))

            elif hx < t:
                side_left  = hx - t
                side_right = min(hx2, 0)
                side_w = side_right - side_left
                if side_w > 0:
                    self.hole_borders.append(
                        Wall(side_left, hy - t, side_w, t, visible=True, player_only=True))
                    self.hole_borders.append(
                        Wall(side_left, hy2, side_w, t, visible=True, player_only=True))
                self.hole_borders.append(
                    Wall(hx - t, hy - t, t, hh + t * 2, visible=True, player_only=True))

            elif hx2 > sw - t:
                side_left = max(hx, sw)
                side_w = hx2 + t - side_left
                if side_w > 0:
                    self.hole_borders.append(
                        Wall(side_left, hy - t, side_w, t, visible=True, player_only=True))
                    self.hole_borders.append(
                        Wall(side_left, hy2, side_w, t, visible=True, player_only=True))
                self.hole_borders.append(
                    Wall(hx2, hy - t, t, hh + t * 2, visible=True, player_only=True))

            else:
                self._punch_hole_in_custom_walls(hole)
                self.hole_borders.append(
                    Wall(hx - t, hy, t, hh + t, visible=True, player_only=True))
                self.hole_borders.append(
                    Wall(hx2, hy, t, hh + t, visible=True, player_only=True))
                self.hole_borders.append(
                    Wall(hx - t, hy2, hw + t * 2, t, visible=True, player_only=True))

    def _punch_hole_in_custom_walls(self, hole):
        from world.tilemap import Wall as WallCls
        hx, hy, hw, hh = hole.x, hole.y, hole.width, hole.height
        hx2 = hx + hw
        hy2 = hy + hh

        new_walls = []
        walls_to_remove = []

        for wall in self.custom_walls:
            wr = wall.rect
            if not wr.colliderect(hole):
                continue
            walls_to_remove.append(wall)
            wx, wy, ww, wh = wr.x, wr.y, wr.width, wr.height
            wx2 = wx + ww
            wy2 = wy + wh

            if hy > wy:
                new_walls.append(WallCls(wx, wy, ww, hy - wy, visible=True))
            if hy2 < wy2:
                new_walls.append(WallCls(wx, hy2, ww, wy2 - hy2, visible=True))
            top = max(wy, hy)
            bot = min(wy2, hy2)
            if bot > top:
                if hx > wx:
                    new_walls.append(WallCls(wx, top, hx - wx, bot - top, visible=True))
                if hx2 < wx2:
                    new_walls.append(WallCls(hx2, top, wx2 - hx2, bot - top, visible=True))

        for w in walls_to_remove:
            self.custom_walls.remove(w)
        self.custom_walls.extend(new_walls)

    def _ask_text(self, mode, prompt):
        self._text_mode = mode
        self._text_input = ""
        self._text_prompt = prompt

    def _handle_text(self, key):
        if key == pygame.K_RETURN:
            name = self._text_input.strip()
            mode = self._text_mode
            self._text_mode = None
            self._text_input = ""
            if name:
                if mode == "save":
                    self.save(name)
                elif mode == "load":
                    self.load(name)
                elif mode == "portal_name" and self._pending_portal_rect:
                    r = self._pending_portal_rect
                    self.portals.append(Portal(r[0], r[1], r[2], r[3], name))
                    self._pending_portal_rect = None
            return "done"
        elif key == pygame.K_ESCAPE:
            self._text_mode = None
            self._text_input = ""
            self._pending_portal_rect = None
            return "cancel"
        elif key == pygame.K_BACKSPACE:
            self._text_input = self._text_input[:-1]
        else:
            char = pygame.key.name(key)
            if len(char) == 1 and char.isalnum():
                self._text_input += char
            elif char == "space":
                self._text_input += "_"
            elif char == "-":
                self._text_input += "-"
        return "typing"

    def _list_maps(self):
        if not os.path.isdir(MAPS_DIR):
            return []
        return sorted(f[:-5] for f in os.listdir(MAPS_DIR) if f.endswith(".json"))

    def handle_scroll(self, direction):
        if self.mode == 2:
            self.light_flicker_speed = max(1, min(15, self.light_flicker_speed + direction))

    # ── Clics ────────────────────────────────

    def handle_click(self, mouse_pos):
        if self._text_mode:
            return
        wx = int(mouse_pos[0] + self.camera.offset_x)
        wy = int(mouse_pos[1] + self.camera.offset_y)

        if self.mode == 0:
            self._click_rect(wx, wy, "platform")
        elif self.mode == 1:
            self._click_mob(wx, wy)
        elif self.mode == 2:
            self._click_light(wx, wy)
        elif self.mode == 3:
            self.spawn_x, self.spawn_y = wx, wy
            self.player.spawn_x, self.player.spawn_y = wx, wy
        elif self.mode == 4:
            self._click_rect(wx, wy, "portal")
        elif self.mode == 5:
            self._click_rect(wx, wy, "wall")
        elif self.mode == 6:
            self._click_hitbox(wx, wy)
        elif self.mode == 7:
            self._click_rect(wx, wy, "hole")
        elif self.mode == 8:
            if self._has_clipboard:
                self._do_paste(wx, wy)
            else:
                self._click_rect(wx, wy, "copy_select")

    def _click_rect(self, wx, wy, kind):
        if self.first_point is None:
            self.first_point = (wx, wy)
        else:
            x1, y1 = self.first_point
            x, y = min(x1, wx), min(y1, wy)
            w, h = abs(wx - x1), abs(wy - y1)
            self.first_point = None
            if w < 5 or h < 5:
                return
            if kind == "platform":
                self.platforms.append(Platform(x, y, w, h, BLANC))
            elif kind == "wall":
                self.custom_walls.append(Wall(x, y, w, h, visible=True))
            elif kind == "portal":
                self._pending_portal_rect = (x, y, w, h)
                maps = self._list_maps()
                p = "Map cible :" + (f"  ({', '.join(maps)})" if maps else "")
                self._ask_text("portal_name", p)
            elif kind == "hole":
                self.holes.append(pygame.Rect(x, y, w, h))
                self.rebuild_hole_borders()
            elif kind == "copy_select":
                self._copy_rect = pygame.Rect(x, y, w, h)
                print(f"Zone sélectionnée ({w}x{h}) - [C] pour copier, [V] pour coller")

    def _click_mob(self, wx, wy):
        if self.mob_patrol_mode:
            self._click_mob_patrol(wx, wy)
            return
        if self.mob_detect_mode:
            self._click_mob_detect(wx, wy)
            return

        hb = get_hitbox(self._current_sprite())
        test = pygame.Rect(wx, wy, hb["w"], hb["h"])
        for p in self.platforms:
            if test.colliderect(p.rect):
                print("X Ennemi dans une plateforme")
                return
        self.enemies.append(Enemy(
            wx, wy,
            has_gravity=self.mob_gravity,
            has_collision=self.mob_collision,
            sprite_name=self._current_sprite(),
            can_jump=self.mob_can_jump,
            can_jump_patrol=self.mob_can_jump_patrol,
            detect_range=self.mob_detect_range,
            has_light=self.mob_has_light,
            patrol_left=wx - 300,
            patrol_right=wx + 300,
            can_fall_in_holes=self.mob_can_fall_in_holes,   # ← NOUVEAU
            respawn_timeout=self.mob_respawn_timeout,        # ← NOUVEAU
        ))

    def _click_mob_patrol(self, wx, wy):
        if self._patrol_target is None:
            best = None
            best_dist = 9999999
            for enemy in self.enemies:
                dx = enemy.rect.centerx - wx
                dy = enemy.rect.centery - wy
                d = dx * dx + dy * dy
                if d < best_dist:
                    best_dist = d
                    best = enemy
            if best and best_dist < 100 * 100:
                self._patrol_target = best
                print("Mob selectionne - clic gauche pour la limite gauche")
            else:
                print("Aucun mob proche - clique sur un mob")
        elif self._patrol_first_x is None:
            self._patrol_first_x = wx
            print(f"Limite gauche = {wx} - clic pour la limite droite")
        else:
            left  = min(self._patrol_first_x, wx)
            right = max(self._patrol_first_x, wx)
            if right - left > 20:
                self._patrol_target.patrol_left  = left
                self._patrol_target.patrol_right = right
                print(f"Zone patrouille : {left} - {right}")
            self._patrol_target  = None
            self._patrol_first_x = None

    def _click_mob_detect(self, wx, wy):
        if self._detect_target is None:
            best = None
            best_dist = 9999999
            for enemy in self.enemies:
                dx = enemy.rect.centerx - wx
                dy = enemy.rect.centery - wy
                d = dx * dx + dy * dy
                if d < best_dist:
                    best_dist = d
                    best = enemy
            if best and best_dist < 100 * 100:
                self._detect_target = best
                print("Mob selectionne - clic a gauche ou droite pour la direction, +/- pour la portee")
            else:
                print("Aucun mob proche")
        else:
            if wx < self._detect_target.rect.centerx:
                self._detect_target.direction = -1
                print("Direction = gauche")
            else:
                self._detect_target.direction = 1
                print("Direction = droite")
            self._detect_target = None

    def _click_light(self, wx, wy):
        if self.light_first_point is None:
            self.light_first_point = (wx, wy)
        else:
            cx, cy = self.light_first_point
            r = int(((wx - cx)**2 + (wy - cy)**2)**0.5)
            if r > 5:
                lt = LIGHT_TYPES[self.light_type_index]
                self.lighting.add_light(cx, cy, radius=r, type=lt,
                    flicker=self.light_flicker, flicker_speed=self.light_flicker_speed)
            self.light_first_point = None

    def _do_copy(self):
        if self._copy_rect is None:
            print("Sélectionne d'abord une zone (clic x2)")
            return
        r = self._copy_rect
        self._copy_origin = (r.x, r.y)
        self._clipboard_platforms = []
        self._clipboard_walls = []
        for p in self.platforms:
            if r.colliderect(p.rect):
                self._clipboard_platforms.append(pygame.Rect(
                    p.rect.x - r.x, p.rect.y - r.y, p.rect.w, p.rect.h))
        for w in self.custom_walls:
            if r.colliderect(w.rect):
                self._clipboard_walls.append(pygame.Rect(
                    w.rect.x - r.x, w.rect.y - r.y, w.rect.w, w.rect.h))
        self._has_clipboard = True
        print(f"Copié : {len(self._clipboard_platforms)} plateformes, "
              f"{len(self._clipboard_walls)} murs. Clic pour coller.")

    def _do_paste(self, wx, wy):
        if not self._has_clipboard:
            return
        for rel in self._clipboard_platforms:
            self.platforms.append(Platform(wx + rel.x, wy + rel.y, rel.w, rel.h, BLANC))
        for rel in self._clipboard_walls:
            self.custom_walls.append(Wall(wx + rel.x, wy + rel.y, rel.w, rel.h, visible=True))
        total = len(self._clipboard_platforms) + len(self._clipboard_walls)
        print(f"Collé {total} élément(s) à ({wx}, {wy})")

    def _click_hitbox(self, wx, wy):
        if not self._enemy_sprites:
            return
        name = self._enemy_sprites[self._hb_sprite_index % len(self._enemy_sprites)]
        try:
            from entities.enemy import ENEMIES_DIR
            path = os.path.join(ENEMIES_DIR, name)
            if not os.path.exists(path):
                path = find_file(name)
            img = pygame.image.load(path)
        except Exception:
            return

        scale = 4
        sw, sh = img.get_width() * scale, img.get_height() * scale
        screen = pygame.display.get_surface()
        sx = (screen.get_width() - sw) // 2
        sy = 120

        mx = int(wx - self.camera.offset_x)
        my = int(wy - self.camera.offset_y)

        if not (sx <= mx <= sx + sw and sy <= my <= sy + sh):
            return

        rel_x = (mx - sx) // scale
        rel_y = (my - sy) // scale

        if self._hb_first_point is None:
            self._hb_first_point = (rel_x, rel_y)
        else:
            x1, y1 = self._hb_first_point
            x, y = min(x1, rel_x), min(y1, rel_y)
            w, h = abs(rel_x - x1), abs(rel_y - y1)
            self._hb_first_point = None
            if w > 1 and h > 1:
                set_hitbox(name, w, h, x, y)
                print(f"Hitbox '{name}': {w}x{h} offset({x},{y})")

    def handle_right_click(self, mouse_pos):
        if self._text_mode:
            return
        wx = int(mouse_pos[0] + self.camera.offset_x)
        wy = int(mouse_pos[1] + self.camera.offset_y)
        pt = pygame.Rect(wx, wy, 1, 1)
        if self.mode == 0:
            self.platforms[:] = [p for p in self.platforms if not p.rect.colliderect(pt)]
        elif self.mode == 1:
            self.enemies[:] = [e for e in self.enemies if not e.rect.colliderect(pt)]
        elif self.mode == 2:
            self.lighting.lights[:] = [l for l in self.lighting.lights
                if not (abs(l["x"]-wx) < l["radius"] and abs(l["y"]-wy) < l["radius"])]
        elif self.mode == 4:
            self.portals[:] = [p for p in self.portals if not p.rect.colliderect(pt)]
        elif self.mode == 5:
            self.custom_walls[:] = [w for w in self.custom_walls if not w.rect.colliderect(pt)]
        elif self.mode == 7:
            self.holes[:] = [h for h in self.holes if not h.colliderect(pt)]
            self.rebuild_hole_borders()
        elif self.mode == 8:
            self._copy_rect = None
            self._has_clipboard = False
            self.first_point = None
            print("Sélection effacée")

    # ── Preview ──────────────────────────────

    def draw_preview(self, surf, mouse_pos):
        if self.mode in (0, 4, 5, 7, 8):
            colors = {0: (100,200,255), 4: (0,120,255), 5: (180,180,180), 7: (255,80,80), 8: (255,200,0)}
            if self.first_point:
                wx = int(mouse_pos[0] + self.camera.offset_x)
                wy = int(mouse_pos[1] + self.camera.offset_y)
                x = min(self.first_point[0], wx) - int(self.camera.offset_x)
                y = min(self.first_point[1], wy) - int(self.camera.offset_y)
                w = abs(wx - self.first_point[0])
                h = abs(wy - self.first_point[1])
                pygame.draw.rect(surf, colors.get(self.mode, (255,255,255)), (x, y, w, h), 2)
        elif self.mode == 2:
            if self.light_first_point is None:
                pygame.draw.circle(surf, (255,200,0), mouse_pos, 5)
            else:
                cx = int(self.light_first_point[0] - self.camera.offset_x)
                cy = int(self.light_first_point[1] - self.camera.offset_y)
                r = int(((mouse_pos[0]-cx)**2+(mouse_pos[1]-cy)**2)**0.5)
                pygame.draw.circle(surf, (255,200,0), (cx,cy), r, 2)
                pygame.draw.circle(surf, (255,200,0), (cx,cy), 5)
        elif self.mode == 3:
            pygame.draw.circle(surf, (0,150,255), mouse_pos, 8, 2)
        elif self.mode == 1 and self.mob_patrol_mode:
            if self._patrol_target:
                tr = self.camera.apply(self._patrol_target.rect)
                pygame.draw.rect(surf, (255, 200, 0), tr, 3)
            if self._patrol_first_x is not None:
                lx = int(self._patrol_first_x - self.camera.offset_x)
                h = surf.get_height()
                pygame.draw.line(surf, (0, 200, 0), (lx, 0), (lx, h), 2)
                pygame.draw.line(surf, (0, 200, 0), (lx, mouse_pos[1]),
                                 (mouse_pos[0], mouse_pos[1]), 1)
                pygame.draw.line(surf, (0, 200, 0),
                                 (mouse_pos[0], 0), (mouse_pos[0], h), 1)
        elif self.mode == 1 and self.mob_detect_mode:
            if self._detect_target:
                tr = self.camera.apply(self._detect_target.rect)
                pygame.draw.rect(surf, (255, 100, 0), tr, 3)
                dr = self.camera.apply(self._detect_target._detect_rect())
                pygame.draw.rect(surf, (255, 255, 0), dr, 2)
                font = self._get_font()
                surf.blit(font.render(
                    f"Portee: {self._detect_target.detect_range}  Dir: {'D' if self._detect_target.direction > 0 else 'G'}",
                    True, (255, 255, 0)), (dr.x, dr.y - 18))
        elif self.mode == 6:
            self._draw_hitbox_editor(surf, mouse_pos)
        if self.mode == 8:
            self._draw_copy_paste_preview(surf, mouse_pos)

    def _draw_hitbox_editor(self, surf, mouse_pos):
        font = self._get_font()
        if not self._enemy_sprites:
            return
        name = self._enemy_sprites[self._hb_sprite_index % len(self._enemy_sprites)]
        try:
            from entities.enemy import ENEMIES_DIR
            path = os.path.join(ENEMIES_DIR, name)
            if not os.path.exists(path):
                path = find_file(name)
            img = pygame.image.load(path)
        except Exception:
            surf.blit(font.render(f"Sprite introuvable: {name}", True, (255,0,0)), (10, 130))
            return

        scale = 4
        sw_img, sh_img = img.get_width() * scale, img.get_height() * scale
        screen_w = surf.get_width()
        sx = (screen_w - sw_img) // 2
        sy = 120

        bg_rect = pygame.Rect(sx - 10, sy - 10, sw_img + 20, sh_img + 20)
        pygame.draw.rect(surf, (20, 10, 30), bg_rect)
        pygame.draw.rect(surf, (100, 100, 100), bg_rect, 1)

        scaled = pygame.transform.scale(img, (sw_img, sh_img))
        surf.blit(scaled, (sx, sy))

        hb = get_hitbox(name)
        hb_screen = pygame.Rect(
            sx + hb["ox"] * scale, sy + hb["oy"] * scale,
            hb["w"] * scale, hb["h"] * scale)
        pygame.draw.rect(surf, (0, 255, 0), hb_screen, 2)
        surf.blit(font.render(f"Actuel: {hb['w']}x{hb['h']} off({hb['ox']},{hb['oy']})",
            True, (0, 255, 0)), (sx, sy + sh_img + 8))

        if self._hb_first_point:
            p1_sx = sx + self._hb_first_point[0] * scale
            p1_sy = sy + self._hb_first_point[1] * scale
            mx, my = mouse_pos
            if sx <= mx <= sx + sw_img and sy <= my <= sy + sh_img:
                rx = min(p1_sx, mx)
                ry = min(p1_sy, my)
                rw = abs(mx - p1_sx)
                rh = abs(my - p1_sy)
                pygame.draw.rect(surf, (255, 0, 0), (rx, ry, rw, rh), 2)
                ow = rw // scale
                oh = rh // scale
                surf.blit(font.render(f"{ow}x{oh}", True, (255, 0, 0)),
                          (rx + rw + 5, ry + rh + 2))

        surf.blit(font.render(f"[T] sprite: {name}  |  Clic sur le sprite pour dessiner la hitbox",
            True, (200, 200, 200)), (sx, sy + sh_img + 28))

    def _draw_copy_paste_preview(self, surf, mouse_pos):
        font = self._get_font()
        if self._copy_rect:
            sr = pygame.Rect(
                self._copy_rect.x - int(self.camera.offset_x),
                self._copy_rect.y - int(self.camera.offset_y),
                self._copy_rect.w, self._copy_rect.h)
            pygame.draw.rect(surf, (255, 200, 0), sr, 2)
            surf.blit(font.render("COPIE", True, (255, 200, 0)), (sr.x, sr.y - 18))
        if self._has_clipboard:
            wx = int(mouse_pos[0] + self.camera.offset_x)
            wy = int(mouse_pos[1] + self.camera.offset_y)
            for rel in self._clipboard_platforms:
                pr = pygame.Rect(
                    wx + rel.x - int(self.camera.offset_x),
                    wy + rel.y - int(self.camera.offset_y),
                    rel.w, rel.h)
                pygame.draw.rect(surf, (100, 200, 255, 100), pr, 1)
            for rel in self._clipboard_walls:
                wr = pygame.Rect(
                    wx + rel.x - int(self.camera.offset_x),
                    wy + rel.y - int(self.camera.offset_y),
                    rel.w, rel.h)
                pygame.draw.rect(surf, (180, 180, 180), wr, 1)
            surf.blit(font.render("CLIC = coller | Clic D = effacer",
                True, (255, 200, 0)), (10, surf.get_height() - 45))

    def draw_overlays(self, surf):
        font = self._get_font()
        sx = int(self.spawn_x - self.camera.offset_x)
        sy = int(self.spawn_y - self.camera.offset_y)
        pygame.draw.circle(surf, (0,150,255), (sx,sy), 8, 2)
        txt = font.render("SPAWN", True, (0,150,255))
        surf.blit(txt, (sx - txt.get_width()//2, sy - 22))
        for portal in self.portals:
            portal.draw(surf, self.camera, font)

    # ── HUD ──────────────────────────────────

    def draw_hud(self, surf):
        font = self._get_font()
        small = self._font_small
        w = surf.get_width()

        if self._text_mode:
            self._draw_text_box(surf)
            return

        panel = pygame.Surface((w, 90), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 180))
        surf.blit(panel, (0, 0))

        hb = " [Hitbox]" if self.show_hitboxes else ""
        surf.blit(font.render(f"EDITEUR - [{self.mode+1}/9] {self._mode_names[self.mode]}{hb}",
            True, (0,255,120)), (10, 6))

        info = (f"Sol:{settings.GROUND_Y} Plaf:{settings.CEILING_Y} "
                f"Scene:{settings.SCENE_WIDTH} Cam:{self.camera.y_offset}")
        surf.blit(small.render(info, True, (255,255,0)),
                  (w - small.size(info)[0] - 10, 6))

        y2 = 28
        if self.mode == 0:
            surf.blit(font.render("Clic G x2 = rect | Clic D = suppr",
                True, (200,200,255)), (10, y2))

        elif self.mode == 1:
            gc  = (0,255,0) if self.mob_gravity          else (255,80,80)
            cc  = (0,255,0) if self.mob_collision         else (255,80,80)
            jc  = (0,255,0) if self.mob_can_jump          else (255,80,80)
            vpc = (0,255,0) if self.mob_can_jump_patrol   else (255,80,80)
            lc  = (0,255,0) if self.mob_has_light         else (255,80,80)
            oc  = (0,255,0) if self.mob_can_fall_in_holes else (255,80,80)   # ← NOUVEAU
            sn  = self._current_sprite()
            rt  = f"{self.mob_respawn_timeout:.0f}s" if self.mob_respawn_timeout > 0 else "OFF"

            surf.blit(font.render(f"[G]:{self.mob_gravity}",         True, gc),  (10,  y2))
            surf.blit(font.render(f"[C]:{self.mob_collision}",       True, cc),  (120, y2))
            surf.blit(font.render(f"[J]saut:{self.mob_can_jump}",    True, jc),  (240, y2))
            surf.blit(font.render(f"[V]patr:{self.mob_can_jump_patrol}", True, vpc), (390, y2))
            surf.blit(font.render(f"[I]Light:{self.mob_has_light}",  True, lc),  (560, y2))
            surf.blit(font.render(f"[O]Trou:{self.mob_can_fall_in_holes}", True, oc), (700, y2))  # ← NOUVEAU

            # Ligne 2 : sprite, detect, respawn timeout
            surf.blit(small.render(f"[T]:{sn}  Det:{self.mob_detect_range}  [*/÷]Resp:{rt}",
                True, (200,200,255)), (10, 50))

            if self.mob_patrol_mode:
                pc = (255, 200, 0)
                if self._patrol_target is None:
                    ptxt = "[P]atrouille ON : clic sur un mob"
                elif self._patrol_first_x is None:
                    ptxt = "[P]atrouille : clic = limite gauche"
                else:
                    ptxt = f"[P]atrouille : clic = limite droite (G={self._patrol_first_x})"
                surf.blit(small.render(ptxt, True, pc), (500, 50))
            elif self.mob_detect_mode:
                dc = (255, 150, 0)
                if self._detect_target is None:
                    dtxt = "[D]etection ON : clic sur un mob"
                else:
                    dtxt = f"[D]etect: portee={self._detect_target.detect_range} [+/-] | clic=direction"
                surf.blit(small.render(dtxt, True, dc), (500, 50))
            else:
                surf.blit(small.render("[P]atrouille [D]etection", True, (140,140,140)), (500, 50))

        elif self.mode == 2:
            lt = LIGHT_TYPES[self.light_type_index]
            fc = (0,255,0) if self.light_flicker else (255,80,80)
            surf.blit(font.render(
                f"[T]{lt} [F]{'ON' if self.light_flicker else 'OFF'} Spd:{self.light_flicker_speed}",
                True, (255,200,100)), (10, y2))
        elif self.mode == 3:
            surf.blit(font.render(
                f"Clic=spawn [R]espawn [B]ase ({self.spawn_x},{self.spawn_y})",
                True, (100,200,255)), (10, y2))
        elif self.mode == 4:
            surf.blit(font.render(
                f"Clic G x2=portail | Clic D=suppr | {len(self.portals)}",
                True, (0,180,255)), (10, y2))
        elif self.mode == 5:
            surf.blit(font.render(
                f"Clic G x2=mur | Clic D=suppr | {len(self.custom_walls)}",
                True, (180,180,180)), (10, y2))
        elif self.mode == 6:
            name = self._enemy_sprites[self._hb_sprite_index % len(self._enemy_sprites)] if self._enemy_sprites else "?"
            hbd = get_hitbox(name)
            surf.blit(font.render(
                f"[T]:{name} | Clic G x2=hitbox | {hbd['w']}x{hbd['h']}",
                True, (255,100,100)), (10, y2))
        elif self.mode == 7:
            surf.blit(font.render(
                f"Clic G x2=trou dans mur | Clic D=suppr | {len(self.holes)} trou(s)",
                True, (255,80,80)), (10, y2))
        elif self.mode == 8:
            if not self._has_clipboard:
                if self._copy_rect:
                    surf.blit(font.render(
                        "[C]=copier la sélection | Clic D=effacer",
                        True, (255,200,0)), (10, y2))
                else:
                    surf.blit(font.render(
                        "Clic G x2=sélectionner zone | [C]=copier | [V]=coller",
                        True, (255,200,0)), (10, y2))
            else:
                nb = len(self._clipboard_platforms) + len(self._clipboard_walls)
                surf.blit(font.render(
                    f"Presse-papier: {nb} élément(s) | Clic G=coller | [V]=coller | Clic D=effacer",
                    True, (255,200,0)), (10, y2))

        keys = "[M]ode [H]itbox [N]ew [S]ave [L]oad [R]espawn [B]ase [Home/End]plafond"
        surf.blit(small.render(keys, True, (140,140,140)), (10, 70))

    def _draw_text_box(self, surf):
        font = self._get_font()
        w, h = surf.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surf.blit(overlay, (0, 0))
        bw, bh = 500, 120
        bx, by = (w-bw)//2, (h-bh)//2
        pygame.draw.rect(surf, (30, 20, 40), (bx, by, bw, bh))
        pygame.draw.rect(surf, (100, 200, 255), (bx, by, bw, bh), 2)
        surf.blit(font.render(self._text_prompt, True, (200,200,255)), (bx+15, by+15))
        surf.blit(font.render(self._text_input+"_", True, (255,255,255)), (bx+15, by+50))
        surf.blit(font.render("[Entree] valider  [Echap] annuler",
            True, (140,140,140)), (bx+15, by+85))

    # ── SAVE / LOAD ──────────────────────────

    def save(self, name="map"):
        fp = os.path.join(MAPS_DIR, f"{name}.json")
        data = {
            "ground_y": settings.GROUND_Y,
            "ceiling_y": settings.CEILING_Y,
            "scene_width": settings.SCENE_WIDTH,
            "camera_y_offset": self.camera.y_offset,
            "spawn": {"x": self.spawn_x, "y": self.spawn_y},
            "bg_color": self.bg_color,
            "wall_color": self.wall_color,
            "platforms": [{"x":p.rect.x,"y":p.rect.y,"w":p.rect.width,"h":p.rect.height}
                          for p in self.platforms],
            "custom_walls": [{"x":w.rect.x,"y":w.rect.y,"w":w.rect.width,"h":w.rect.height}
                             for w in self.custom_walls],
            "enemies": [e.to_dict() for e in self.enemies],
            "lights": [{"x":l["x"],"y":l["y"],"radius":l["radius"],"type":l["type"],
                        "flicker":l["flicker"],"flicker_speed":l["flicker_speed"]}
                       for l in self.lighting.lights if not l.get("_enemy_light")],
            "portals": [p.to_dict() for p in self.portals],
            "holes": [{"x":h.x,"y":h.y,"w":h.width,"h":h.height} for h in self.holes],
        }
        with open(fp, "w") as f:
            json.dump(data, f, indent=2)
        print(f"maps/{name}.json")

    def load(self, name="map"):
        fp = os.path.join(MAPS_DIR, f"{name}.json")
        try:
            with open(fp) as f:
                data = json.load(f)
            self._apply(data)
        except FileNotFoundError:
            print(f"maps/{name}.json introuvable")

    def _apply(self, data):
        if "ground_y" in data:    settings.GROUND_Y = data["ground_y"]
        if "ceiling_y" in data:   settings.CEILING_Y = data["ceiling_y"]
        if "scene_width" in data:
            settings.SCENE_WIDTH = data["scene_width"]
            self.camera.scene_width = data["scene_width"]
        if "camera_y_offset" in data: self.camera.y_offset = data["camera_y_offset"]
        if "spawn" in data:
            self.spawn_x = data["spawn"]["x"]
            self.spawn_y = data["spawn"]["y"]
            self.player.spawn_x = self.spawn_x
            self.player.spawn_y = self.spawn_y
        if "bg_color" in data:   self.bg_color   = data["bg_color"]
        if "wall_color" in data: self.wall_color = data["wall_color"]

        self.platforms.clear()
        for p in data.get("platforms", []):
            self.platforms.append(Platform(p["x"], p["y"], p["w"], p["h"], BLANC))

        self.custom_walls.clear()
        for w in data.get("custom_walls", []):
            self.custom_walls.append(Wall(w["x"], w["y"], w["w"], w["h"], visible=True))

        self.enemies.clear()
        for e in data.get("enemies", []):
            self.enemies.append(Enemy(
                e["x"], e["y"],
                has_gravity=e.get("has_gravity", True),
                has_collision=e.get("has_collision", True),
                sprite_name=e.get("sprite_name", "monstre_perdu.png"),
                can_jump=e.get("can_jump", False),
                can_jump_patrol=e.get("can_jump_patrol", False),
                detect_range=e.get("detect_range", 200),
                detect_height=e.get("detect_height", 80),
                has_light=e.get("has_light", False),
                light_type=e.get("light_type", "dim"),
                light_radius=e.get("light_radius", 100),
                patrol_left=e.get("patrol_left", -1),
                patrol_right=e.get("patrol_right", -1),
                can_fall_in_holes=e.get("can_fall_in_holes", False),   # ← NOUVEAU
                respawn_timeout=e.get("respawn_timeout", 10.0),         # ← NOUVEAU
            ))

        self.lighting.lights.clear()
        for l in data.get("lights", []):
            self.lighting.add_light(l["x"], l["y"], radius=l["radius"], type=l["type"],
                flicker=l.get("flicker", False), flicker_speed=l.get("flicker_speed", 5))

        self.portals.clear()
        for p in data.get("portals", []):
            self.portals.append(Portal(p["x"], p["y"], p["w"], p["h"],
                p["target_map"], p.get("target_x", -1), p.get("target_y", -1)))

        self.holes.clear()
        for h in data.get("holes", []):
            self.holes.append(pygame.Rect(h["x"], h["y"], h["w"], h["h"]))
        self.rebuild_hole_borders()

    def load_map_for_portal(self, name):
        fp = os.path.join(MAPS_DIR, f"{name}.json")
        try:
            with open(fp) as f:
                data = json.load(f)
            self._apply(data)
            return True
        except FileNotFoundError:
            return False
        
