# ─────────────────────────────────────────
#  ENTRE-DEUX — Éditeur de niveaux
# ─────────────────────────────────────────
#
#  Modes (cycle avec M) :
#    [1/8] Plateforme   [2/8] Mob        [3/8] Lumière
#    [4/8] Spawn        [5/8] Portail    [6/8] Mur
#    [7/8] Hitbox       [8/8] Trou
#
#  Touches globales :
#    E = éditeur on/off    M = mode suivant
#    H = hitboxes on/off   N = nouvelle map
#    S = sauvegarder       L = charger
#    R = respawn            B = reset spawn (100,100)
#    ↑↓ = sol              Home/End = plafond
#    ←→ = largeur scène    PgUp/PgDn = caméra
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


# ─────────────────────────────────────────
#  Portail (zone de téléportation)
# ─────────────────────────────────────────

class Portal:
    def __init__(self, x, y, w, h, target_map, target_x=-1, target_y=-1):
        self.rect = pygame.Rect(x, y, w, h)
        self.target_map = target_map
        self.target_x = target_x
        self.target_y = target_y

    def to_dict(self):
        return {
            "x": self.rect.x, "y": self.rect.y,
            "w": self.rect.width, "h": self.rect.height,
            "target_map": self.target_map,
            "target_x": self.target_x,
            "target_y": self.target_y,
        }

    def draw(self, surf, camera, font):
        sr = camera.apply(self.rect)
        # Zone semi-transparente bleue
        s = pygame.Surface((sr.w, sr.h), pygame.SRCALPHA)
        s.fill((0, 120, 255, 60))
        surf.blit(s, sr)
        pygame.draw.rect(surf, (0, 120, 255), sr, 2)
        # Nom de la map cible au-dessus
        txt = font.render(f"-> {self.target_map}", True, (0, 180, 255))
        surf.blit(txt, (sr.x, sr.y - 18))


# ─────────────────────────────────────────
#  Éditeur principal
# ─────────────────────────────────────────

class Editor:
    def __init__(self, platforms, enemies, camera, lighting, player):
        self.platforms = platforms
        self.enemies = enemies
        self.camera = camera
        self.lighting = lighting
        self.player = player
        self.active = False
        self.first_point = None

        # Portails, murs custom, trous
        self.portals = []
        self.custom_walls = []
        self.hole_borders = []    # murs auto-générés DANS les trous
        self.holes = []           # zones qui "percent" les murs

        # Modes : 0-7
        self.mode = 0
        self._mode_names = [
            "Plateforme", "Mob", "Lumiere",
            "Spawn", "Portail", "Mur", "Hitbox", "Trou"
        ]

        # ── Options Lumière ──
        self.light_type_index = 1
        self.light_flicker = False
        self.light_flicker_speed = 5
        self.light_first_point = None

        # ── Options Mob ──
        self.mob_gravity = True
        self.mob_collision = True
        self.mob_can_jump = False
        self.mob_detect_range = 200
        self.mob_has_light = False
        self.mob_sprite_index = 0
        self._enemy_sprites = []
        self._refresh_sprites()

        # Sous-mode Patrouille (touche P)
        self.mob_patrol_mode = False
        self._patrol_target = None
        self._patrol_first_x = None

        # Sous-mode Détection (touche D)
        self.mob_detect_mode = False
        self._detect_target = None

        # ── Options Hitbox ──
        self._hb_sprite_index = 0
        self._hb_first_point = None

        # ── Affichage ──
        self.show_hitboxes = False

        # ── Saisie texte ──
        self._text_input = ""
        self._text_mode = None
        self._text_prompt = ""
        self._pending_portal_rect = None

        # ── Spawn ──
        self.spawn_x = self.player.spawn_x
        self.spawn_y = self.player.spawn_y

        # ── Settings par map ──
        self.bg_color = list(VIOLET)
        self.wall_color = [0, 0, 0]

        # ── Fonts (cache) ──
        self._font = None
        self._font_small = None

        os.makedirs(MAPS_DIR, exist_ok=True)

    # ─────────────────────────────────────
    #  Utilitaires
    # ─────────────────────────────────────

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
        self.mode = (self.mode + 1) % 8
        self.first_point = None
        self.light_first_point = None
        self._hb_first_point = None
        self.mob_patrol_mode = False
        self.mob_detect_mode = False
        self._patrol_target = None
        self._detect_target = None
        self._patrol_first_x = None
        if self.mode in (1, 6):
            self._refresh_sprites()

    # ─────────────────────────────────────
    #  Gestion des touches
    # ─────────────────────────────────────

    def handle_key(self, key):
        # Si saisie texte en cours
        if self._text_mode is not None:
            return self._handle_text(key)

        # ── Commandes globales ──
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
            prompt = "Charger :"
            if maps:
                prompt += f"  ({', '.join(maps)})"
            self._ask_text("load", prompt)
            return "text_input"
        elif key == pygame.K_r:
            self.player.respawn()
        elif key == pygame.K_b:
            self.spawn_x = 100
            self.spawn_y = 100
            self.player.spawn_x = 100
            self.player.spawn_y = 100
            self.player.respawn()

        # ── Sol / Plafond ──
        elif key == pygame.K_UP:
            settings.GROUND_Y = max(100, settings.GROUND_Y - 20)
        elif key == pygame.K_DOWN:
            settings.GROUND_Y = min(3000, settings.GROUND_Y + 20)
        elif key == pygame.K_HOME:
            settings.CEILING_Y = max(-500, settings.CEILING_Y - 20)
        elif key == pygame.K_END:
            settings.CEILING_Y = min(settings.GROUND_Y - 100, settings.CEILING_Y + 20)

        # ── Scène ──
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

        # ── Mode Lumière ──
        elif key == pygame.K_t and self.mode == 2:
            self.light_type_index = (self.light_type_index + 1) % len(LIGHT_TYPES)
        elif key == pygame.K_f and self.mode == 2:
            self.light_flicker = not self.light_flicker

        # ── Mode Mob ──
        elif key == pygame.K_g and self.mode == 1:
            self.mob_gravity = not self.mob_gravity
        elif key == pygame.K_c and self.mode == 1:
            self.mob_collision = not self.mob_collision
        elif key == pygame.K_j and self.mode == 1:
            self.mob_can_jump = not self.mob_can_jump
        elif key == pygame.K_i and self.mode == 1:
            self.mob_has_light = not self.mob_has_light
        elif key == pygame.K_t and self.mode == 1:
            self.mob_sprite_index = (self.mob_sprite_index + 1) % max(1, len(self._enemy_sprites))

        # Sous-mode Détection : +/- = portée, * / = jump_power du mob sélectionné
        elif key == pygame.K_KP_PLUS and self.mode == 1 and self.mob_detect_mode and self._detect_target:
            self._detect_target.detect_range = min(600, self._detect_target.detect_range + 25)
            print(f"Portee = {self._detect_target.detect_range}")
        elif key == pygame.K_KP_MINUS and self.mode == 1 and self.mob_detect_mode and self._detect_target:
            self._detect_target.detect_range = max(50, self._detect_target.detect_range - 25)
            print(f"Portee = {self._detect_target.detect_range}")
        elif key == pygame.K_KP_MULTIPLY and self.mode == 1 and self.mob_detect_mode and self._detect_target:
            self._detect_target.jump_power = min(1000, self._detect_target.jump_power + 50)
            print(f"Jump = {self._detect_target.jump_power}")
        elif key == pygame.K_KP_DIVIDE and self.mode == 1 and self.mob_detect_mode and self._detect_target:
            self._detect_target.jump_power = max(0, self._detect_target.jump_power - 50)
            print(f"Jump = {self._detect_target.jump_power}")

        # +/- par défaut (pour les prochains mobs)
        elif key == pygame.K_KP_PLUS and self.mode == 1:
            self.mob_detect_range = min(500, self.mob_detect_range + 25)
        elif key == pygame.K_KP_MINUS and self.mode == 1:
            self.mob_detect_range = max(50, self.mob_detect_range - 25)

        # Sous-modes P et D
        elif key == pygame.K_p and self.mode == 1:
            self.mob_patrol_mode = not self.mob_patrol_mode
            self.mob_detect_mode = False
            self._patrol_target = None
            self._patrol_first_x = None
            print(f"Patrouille : {'ON' if self.mob_patrol_mode else 'OFF'}")
        elif key == pygame.K_d and self.mode == 1:
            self.mob_detect_mode = not self.mob_detect_mode
            self.mob_patrol_mode = False
            self._detect_target = None
            print(f"Detection : {'ON' if self.mob_detect_mode else 'OFF'}")

        # ── Mode Hitbox ──
        elif key == pygame.K_t and self.mode == 6:
            self._hb_sprite_index = (self._hb_sprite_index + 1) % max(1, len(self._enemy_sprites))
            self._hb_first_point = None

        return None

    # ─────────────────────────────────────
    #  Nouvelle map / Trous
    # ─────────────────────────────────────

    def _new_map(self):
        """Vide tout pour une nouvelle map."""
        self.platforms.clear()
        self.enemies.clear()
        self.lighting.lights.clear()
        self.portals.clear()
        self.custom_walls.clear()
        self.hole_borders.clear()
        self.holes.clear()
        settings.GROUND_Y = 590
        settings.CEILING_Y = 0
        settings.SCENE_WIDTH = 2400
        self.spawn_x = 100
        self.spawn_y = 100
        self.player.spawn_x = 100
        self.player.spawn_y = 100
        self.player.respawn()
        self.camera.y_offset = 150
        self.bg_color = list(VIOLET)

    def rebuild_hole_borders(self):
        """
        Recalcule les murs de bordure pour tous les trous.
        Les bordures sont DANS le trou (pas en dehors).
        3 côtés fermés, 1 côté ouvert (face à la zone de jeu).
        """
        self.hole_borders.clear()
        t = 10  # épaisseur des bordures
        gy = settings.GROUND_Y
        cy = settings.CEILING_Y
        sw = settings.SCENE_WIDTH

        for hole in self.holes:
            x = hole.x
            y = hole.y
            w = hole.width
            h = hole.height

            # ── Trou dans le sol (ouvert en haut) ──
            if y < gy and y + h > gy:
                # Mur gauche (dans le trou, commence au sol)
                self.hole_borders.append(Wall(x, gy, t, y + h - gy, visible=True))
                # Mur droit
                self.hole_borders.append(Wall(x + w - t, gy, t, y + h - gy, visible=True))
                # Sol du trou (en bas)
                self.hole_borders.append(Wall(x, y + h - t, w, t, visible=True))

            # ── Trou dans le plafond (ouvert en bas) ──
            elif y < cy and y + h > cy:
                self.hole_borders.append(Wall(x, y, t, cy - y, visible=True))
                self.hole_borders.append(Wall(x + w - t, y, t, cy - y, visible=True))
                self.hole_borders.append(Wall(x, y, w, t, visible=True))

            # ── Trou dans le mur gauche (ouvert à droite) ──
            elif x < 0:
                self.hole_borders.append(Wall(x, y, w, t, visible=True))
                self.hole_borders.append(Wall(x, y + h - t, w, t, visible=True))
                self.hole_borders.append(Wall(x, y, t, h, visible=True))

            # ── Trou dans le mur droit (ouvert à gauche) ──
            elif x + w > sw:
                self.hole_borders.append(Wall(x, y, w, t, visible=True))
                self.hole_borders.append(Wall(x, y + h - t, w, t, visible=True))
                self.hole_borders.append(Wall(x + w - t, y, t, h, visible=True))

            # ── Trou dans un mur custom (ouvert en haut par défaut) ──
            else:
                self.hole_borders.append(Wall(x, y, t, h, visible=True))
                self.hole_borders.append(Wall(x + w - t, y, t, h, visible=True))
                self.hole_borders.append(Wall(x, y + h - t, w, t, visible=True))

    # ─────────────────────────────────────
    #  Saisie texte
    # ─────────────────────────────────────

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

    # ─────────────────────────────────────
    #  Clics
    # ─────────────────────────────────────

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
            self.spawn_x = wx
            self.spawn_y = wy
            self.player.spawn_x = wx
            self.player.spawn_y = wy
        elif self.mode == 4:
            self._click_rect(wx, wy, "portal")
        elif self.mode == 5:
            self._click_rect(wx, wy, "wall")
        elif self.mode == 6:
            self._click_hitbox(wx, wy)
        elif self.mode == 7:
            self._click_rect(wx, wy, "hole")

    def _click_rect(self, wx, wy, kind):
        """Clic ×2 pour dessiner un rectangle (plateforme, mur, portail, trou)."""
        if self.first_point is None:
            self.first_point = (wx, wy)
        else:
            x1, y1 = self.first_point
            x = min(x1, wx)
            y = min(y1, wy)
            w = abs(wx - x1)
            h = abs(wy - y1)
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
                prompt = "Map cible :"
                if maps:
                    prompt += f"  ({', '.join(maps)})"
                self._ask_text("portal_name", prompt)
            elif kind == "hole":
                self.holes.append(pygame.Rect(x, y, w, h))
                self.rebuild_hole_borders()

    def _click_mob(self, wx, wy):
        """Mode Mob : placer un ennemi ou utiliser un sous-mode."""
        # Sous-mode patrouille
        if self.mob_patrol_mode:
            self._click_mob_patrol(wx, wy)
            return

        # Sous-mode détection
        if self.mob_detect_mode:
            self._click_mob_detect(wx, wy)
            return

        # Mode normal : placer un ennemi
        hb = get_hitbox(self._current_sprite())
        self.enemies.append(Enemy(
            wx, wy,
            has_gravity=self.mob_gravity,
            has_collision=self.mob_collision,
            sprite_name=self._current_sprite(),
            can_jump=self.mob_can_jump,
            detect_range=self.mob_detect_range,
            has_light=self.mob_has_light,
            patrol_left=wx - 300,
            patrol_right=wx + 300))

    def _click_mob_patrol(self, wx, wy):
        """3 clics : sélectionner mob → limite gauche → limite droite."""
        if self._patrol_target is None:
            # Étape 1 : sélectionner le mob le plus proche
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
                print("Mob selectionne - clic = limite gauche")
            else:
                print("Aucun mob proche")

        elif self._patrol_first_x is None:
            # Étape 2 : limite gauche
            self._patrol_first_x = wx
            print(f"Limite gauche = {wx} - clic = limite droite")

        else:
            # Étape 3 : limite droite → appliquer
            left = min(self._patrol_first_x, wx)
            right = max(self._patrol_first_x, wx)
            if right - left > 20:
                self._patrol_target.patrol_left = left
                self._patrol_target.patrol_right = right
                print(f"Zone patrouille : {left} - {right}")
            self._patrol_target = None
            self._patrol_first_x = None

    def _click_mob_detect(self, wx, wy):
        """Clic sur un mob = sélection, puis clic = direction."""
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
                print("Mob selectionne - +/- portee, */div jump, clic = direction")
            else:
                print("Aucun mob proche")
        else:
            # Clic = changer la direction du mob
            if wx < self._detect_target.rect.centerx:
                self._detect_target.direction = -1
                print("Direction = gauche")
            else:
                self._detect_target.direction = 1
                print("Direction = droite")
            self._detect_target = None

    def _click_light(self, wx, wy):
        """Clic ×2 : centre puis rayon."""
        if self.light_first_point is None:
            self.light_first_point = (wx, wy)
        else:
            cx, cy = self.light_first_point
            r = int(((wx - cx)**2 + (wy - cy)**2) ** 0.5)
            if r > 5:
                lt = LIGHT_TYPES[self.light_type_index]
                self.lighting.add_light(
                    cx, cy, radius=r, type=lt,
                    flicker=self.light_flicker,
                    flicker_speed=self.light_flicker_speed)
            self.light_first_point = None

    def _click_hitbox(self, wx, wy):
        """Mode hitbox : on clique sur le sprite affiché à l'écran."""
        if not self._enemy_sprites:
            return
        name = self._enemy_sprites[self._hb_sprite_index % len(self._enemy_sprites)]

        # Charger l'image pour connaître sa taille
        try:
            from entities.enemy import ENEMIES_DIR
            path = os.path.join(ENEMIES_DIR, name)
            if not os.path.exists(path):
                path = find_file(name)
            img = pygame.image.load(path)
        except Exception:
            return

        scale = 4
        sw = img.get_width() * scale
        sh = img.get_height() * scale
        screen = pygame.display.get_surface()
        sx = (screen.get_width() - sw) // 2
        sy = 120  # sous le panneau éditeur

        # Convertir le clic monde en clic écran
        mx = int(wx - self.camera.offset_x)
        my = int(wy - self.camera.offset_y)

        # Vérifier que le clic est sur le sprite
        if not (sx <= mx <= sx + sw and sy <= my <= sy + sh):
            return

        # Position relative au sprite (en pixels originaux)
        rel_x = (mx - sx) // scale
        rel_y = (my - sy) // scale

        if self._hb_first_point is None:
            self._hb_first_point = (rel_x, rel_y)
        else:
            x1, y1 = self._hb_first_point
            x = min(x1, rel_x)
            y = min(y1, rel_y)
            w = abs(rel_x - x1)
            h = abs(rel_y - y1)
            self._hb_first_point = None
            if w > 1 and h > 1:
                set_hitbox(name, w, h, x, y)
                print(f"Hitbox '{name}': {w}x{h} offset({x},{y})")

    # ─────────────────────────────────────
    #  Clic droit (suppression)
    # ─────────────────────────────────────

    def handle_right_click(self, mouse_pos):
        if self._text_mode:
            return
        wx = int(mouse_pos[0] + self.camera.offset_x)
        wy = int(mouse_pos[1] + self.camera.offset_y)
        pt = pygame.Rect(wx, wy, 1, 1)

        if self.mode == 0:
            self.platforms[:] = [p for p in self.platforms
                                 if not p.rect.colliderect(pt)]
        elif self.mode == 1:
            self.enemies[:] = [e for e in self.enemies
                               if not e.rect.colliderect(pt)]
        elif self.mode == 2:
            self.lighting.lights[:] = [
                l for l in self.lighting.lights
                if not (abs(l["x"] - wx) < l["radius"]
                        and abs(l["y"] - wy) < l["radius"])]
        elif self.mode == 4:
            self.portals[:] = [p for p in self.portals
                               if not p.rect.colliderect(pt)]
        elif self.mode == 5:
            self.custom_walls[:] = [w for w in self.custom_walls
                                    if not w.rect.colliderect(pt)]
        elif self.mode == 7:
            self.holes[:] = [h for h in self.holes if not h.colliderect(pt)]
            self.rebuild_hole_borders()

    # ─────────────────────────────────────
    #  Preview (affichage en temps réel)
    # ─────────────────────────────────────

    def draw_preview(self, surf, mouse_pos):
        # ── Modes rectangle (plateforme, portail, mur, trou) ──
        if self.mode in (0, 4, 5, 7):
            colors = {
                0: (100, 200, 255),
                4: (0, 120, 255),
                5: (180, 180, 180),
                7: (255, 80, 80),
            }
            if self.first_point:
                wx = int(mouse_pos[0] + self.camera.offset_x)
                wy = int(mouse_pos[1] + self.camera.offset_y)
                x = min(self.first_point[0], wx) - int(self.camera.offset_x)
                y = min(self.first_point[1], wy) - int(self.camera.offset_y)
                w = abs(wx - self.first_point[0])
                h = abs(wy - self.first_point[1])
                pygame.draw.rect(surf, colors.get(self.mode, (255, 255, 255)),
                                 (x, y, w, h), 2)

        # ── Mode Lumière ──
        elif self.mode == 2:
            if self.light_first_point is None:
                pygame.draw.circle(surf, (255, 200, 0), mouse_pos, 5)
            else:
                cx = int(self.light_first_point[0] - self.camera.offset_x)
                cy = int(self.light_first_point[1] - self.camera.offset_y)
                r = int(((mouse_pos[0] - cx)**2 + (mouse_pos[1] - cy)**2) ** 0.5)
                pygame.draw.circle(surf, (255, 200, 0), (cx, cy), r, 2)
                pygame.draw.circle(surf, (255, 200, 0), (cx, cy), 5)

        # ── Mode Spawn ──
        elif self.mode == 3:
            pygame.draw.circle(surf, (0, 150, 255), mouse_pos, 8, 2)

        # ── Mode Mob : sous-mode patrouille ──
        elif self.mode == 1 and self.mob_patrol_mode:
            if self._patrol_target:
                tr = self.camera.apply(self._patrol_target.rect)
                pygame.draw.rect(surf, (255, 200, 0), tr, 3)
            if self._patrol_first_x is not None:
                lx = int(self._patrol_first_x - self.camera.offset_x)
                h = surf.get_height()
                pygame.draw.line(surf, (0, 200, 0), (lx, 0), (lx, h), 2)
                pygame.draw.line(surf, (0, 200, 0),
                                 (mouse_pos[0], 0), (mouse_pos[0], h), 1)

        # ── Mode Mob : sous-mode détection ──
        elif self.mode == 1 and self.mob_detect_mode:
            if self._detect_target:
                tr = self.camera.apply(self._detect_target.rect)
                pygame.draw.rect(surf, (255, 100, 0), tr, 3)
                dr = self.camera.apply(self._detect_target._detect_rect())
                pygame.draw.rect(surf, (255, 255, 0), dr, 2)
                font = self._get_font()
                dt = self._detect_target
                info = (f"Det:{dt.detect_range}  Jump:{dt.jump_power}  "
                        f"Dir:{'D' if dt.direction > 0 else 'G'}")
                surf.blit(font.render(info, True, (255, 255, 0)),
                          (dr.x, dr.y - 18))

        # ── Mode Hitbox ──
        elif self.mode == 6:
            self._draw_hitbox_editor(surf, mouse_pos)

    def _draw_hitbox_editor(self, surf, mouse_pos):
        """Affiche le sprite agrandi au centre + hitbox actuelle + preview."""
        font = self._get_font()
        if not self._enemy_sprites:
            return
        name = self._enemy_sprites[self._hb_sprite_index % len(self._enemy_sprites)]

        # Charger l'image
        try:
            from entities.enemy import ENEMIES_DIR
            path = os.path.join(ENEMIES_DIR, name)
            if not os.path.exists(path):
                path = find_file(name)
            img = pygame.image.load(path)
        except Exception:
            surf.blit(font.render(f"Sprite introuvable: {name}", True, (255, 0, 0)),
                      (10, 130))
            return

        scale = 4
        sw_img = img.get_width() * scale
        sh_img = img.get_height() * scale
        sx = (surf.get_width() - sw_img) // 2
        sy = 120

        # Fond sombre
        bg_rect = pygame.Rect(sx - 10, sy - 10, sw_img + 20, sh_img + 20)
        pygame.draw.rect(surf, (20, 10, 30), bg_rect)
        pygame.draw.rect(surf, (100, 100, 100), bg_rect, 1)

        # Sprite agrandi
        scaled = pygame.transform.scale(img, (sw_img, sh_img))
        surf.blit(scaled, (sx, sy))

        # Hitbox actuelle (vert)
        hb = get_hitbox(name)
        hb_screen = pygame.Rect(
            sx + hb["ox"] * scale,
            sy + hb["oy"] * scale,
            hb["w"] * scale,
            hb["h"] * scale)
        pygame.draw.rect(surf, (0, 255, 0), hb_screen, 2)
        surf.blit(font.render(
            f"Actuel: {hb['w']}x{hb['h']} off({hb['ox']},{hb['oy']})",
            True, (0, 255, 0)), (sx, sy + sh_img + 8))

        # Preview de la sélection en cours (rouge)
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

        # Instructions
        surf.blit(font.render(
            f"[T] sprite: {name}  |  Clic sur le sprite pour dessiner la hitbox",
            True, (200, 200, 200)), (sx, sy + sh_img + 28))

    # ─────────────────────────────────────
    #  Overlays (spawn, portails)
    # ─────────────────────────────────────

    def draw_overlays(self, surf):
        font = self._get_font()

        # Marqueur spawn
        sx = int(self.spawn_x - self.camera.offset_x)
        sy = int(self.spawn_y - self.camera.offset_y)
        pygame.draw.circle(surf, (0, 150, 255), (sx, sy), 8, 2)
        txt = font.render("SPAWN", True, (0, 150, 255))
        surf.blit(txt, (sx - txt.get_width() // 2, sy - 22))

        # Portails
        for portal in self.portals:
            portal.draw(surf, self.camera, font)

    # ─────────────────────────────────────
    #  HUD (panneau en haut)
    # ─────────────────────────────────────

    def draw_hud(self, surf):
        font = self._get_font()
        small = self._font_small
        w = surf.get_width()

        # Si saisie texte → boîte de dialogue
        if self._text_mode:
            self._draw_text_box(surf)
            return

        # Fond du panneau
        panel = pygame.Surface((w, 90), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 180))
        surf.blit(panel, (0, 0))

        # Ligne 1 : mode + hitbox
        hb = " [Hitbox]" if self.show_hitboxes else ""
        surf.blit(font.render(
            f"EDITEUR - [{self.mode + 1}/8] {self._mode_names[self.mode]}{hb}",
            True, (0, 255, 120)), (10, 6))

        # Infos scène (droite)
        info = (f"Sol:{settings.GROUND_Y}  Plaf:{settings.CEILING_Y}  "
                f"Scene:{settings.SCENE_WIDTH}  Cam:{self.camera.y_offset}")
        surf.blit(small.render(info, True, (255, 255, 0)),
                  (w - small.size(info)[0] - 10, 6))

        # Ligne 2 : options du mode
        y2 = 28

        if self.mode == 0:
            surf.blit(font.render(
                "Clic G x2 = rect  |  Clic D = suppr",
                True, (200, 200, 255)), (10, y2))

        elif self.mode == 1:
            gc = (0, 255, 0) if self.mob_gravity else (255, 80, 80)
            cc = (0, 255, 0) if self.mob_collision else (255, 80, 80)
            jc = (0, 255, 0) if self.mob_can_jump else (255, 80, 80)
            lc = (0, 255, 0) if self.mob_has_light else (255, 80, 80)
            surf.blit(font.render(f"[G]:{self.mob_gravity}", True, gc), (10, y2))
            surf.blit(font.render(f"[C]:{self.mob_collision}", True, cc), (120, y2))
            surf.blit(font.render(f"[J]:{self.mob_can_jump}", True, jc), (240, y2))
            surf.blit(font.render(f"[I]:{self.mob_has_light}", True, lc), (370, y2))
            surf.blit(small.render(
                f"[T]:{self._current_sprite()}  Det:{self.mob_detect_range}",
                True, (200, 200, 255)), (10, 50))

            # Sous-modes
            if self.mob_patrol_mode:
                if self._patrol_target is None:
                    ptxt = "[P]atrouille ON : clic sur un mob"
                elif self._patrol_first_x is None:
                    ptxt = "[P]atrouille : clic = limite gauche"
                else:
                    ptxt = f"[P]atrouille : clic = limite droite (G={self._patrol_first_x})"
                surf.blit(small.render(ptxt, True, (255, 200, 0)), (300, 50))
            elif self.mob_detect_mode:
                if self._detect_target is None:
                    dtxt = "[D]etect ON : clic sur un mob"
                else:
                    dt = self._detect_target
                    dtxt = (f"[D] det:{dt.detect_range}[+/-]  "
                            f"jump:{dt.jump_power}[*/div]  clic=dir")
                surf.blit(small.render(dtxt, True, (255, 150, 0)), (300, 50))
            else:
                surf.blit(small.render(
                    "[P]atrouille  [D]etection", True, (140, 140, 140)), (300, 50))

        elif self.mode == 2:
            lt = LIGHT_TYPES[self.light_type_index]
            fc = (0, 255, 0) if self.light_flicker else (255, 80, 80)
            surf.blit(font.render(
                f"[T] {lt}  [F] {'ON' if self.light_flicker else 'OFF'}  "
                f"Spd: {self.light_flicker_speed}",
                True, (255, 200, 100)), (10, y2))

        elif self.mode == 3:
            surf.blit(font.render(
                f"Clic = spawn  [R]espawn  [B]ase  ({self.spawn_x}, {self.spawn_y})",
                True, (100, 200, 255)), (10, y2))

        elif self.mode == 4:
            surf.blit(font.render(
                f"Clic G x2 = portail  |  Clic D = suppr  |  {len(self.portals)} portail(s)",
                True, (0, 180, 255)), (10, y2))

        elif self.mode == 5:
            surf.blit(font.render(
                f"Clic G x2 = mur  |  Clic D = suppr  |  {len(self.custom_walls)} mur(s)",
                True, (180, 180, 180)), (10, y2))

        elif self.mode == 6:
            name = "?"
            if self._enemy_sprites:
                name = self._enemy_sprites[self._hb_sprite_index % len(self._enemy_sprites)]
            hbd = get_hitbox(name)
            surf.blit(font.render(
                f"[T]: {name}  |  Clic G x2 = hitbox  |  {hbd['w']}x{hbd['h']}",
                True, (255, 100, 100)), (10, y2))

        elif self.mode == 7:
            surf.blit(font.render(
                f"Clic G x2 = trou  |  Clic D = suppr  |  {len(self.holes)} trou(s)",
                True, (255, 80, 80)), (10, y2))

        # Ligne 3 : raccourcis
        keys = "[M]ode  [H]itbox  [N]ew  [S]ave  [L]oad  [R]espawn  [B]ase  [Home/End] plafond"
        surf.blit(small.render(keys, True, (140, 140, 140)), (10, 70))

    def _draw_text_box(self, surf):
        """Dessine la boîte de saisie de texte."""
        font = self._get_font()
        w, h = surf.get_size()

        # Fond assombri
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surf.blit(overlay, (0, 0))

        # Boîte centrale
        bw, bh = 500, 120
        bx = (w - bw) // 2
        by = (h - bh) // 2
        pygame.draw.rect(surf, (30, 20, 40), (bx, by, bw, bh))
        pygame.draw.rect(surf, (100, 200, 255), (bx, by, bw, bh), 2)

        # Prompt
        surf.blit(font.render(self._text_prompt, True, (200, 200, 255)),
                  (bx + 15, by + 15))
        # Input
        surf.blit(font.render(self._text_input + "_", True, (255, 255, 255)),
                  (bx + 15, by + 50))
        # Aide
        surf.blit(font.render("[Entree] valider   [Echap] annuler", True,
                              (140, 140, 140)), (bx + 15, by + 85))

    # ─────────────────────────────────────
    #  SAVE / LOAD
    # ─────────────────────────────────────

    def save(self, name="map"):
        filepath = os.path.join(MAPS_DIR, f"{name}.json")
        data = {
            "ground_y": settings.GROUND_Y,
            "ceiling_y": settings.CEILING_Y,
            "scene_width": settings.SCENE_WIDTH,
            "camera_y_offset": self.camera.y_offset,
            "spawn": {"x": self.spawn_x, "y": self.spawn_y},
            "bg_color": self.bg_color,
            "wall_color": self.wall_color,
            "platforms": [
                {"x": p.rect.x, "y": p.rect.y,
                 "w": p.rect.width, "h": p.rect.height}
                for p in self.platforms
            ],
            "custom_walls": [
                {"x": w.rect.x, "y": w.rect.y,
                 "w": w.rect.width, "h": w.rect.height}
                for w in self.custom_walls
            ],
            "enemies": [e.to_dict() for e in self.enemies],
            "lights": [
                {"x": l["x"], "y": l["y"], "radius": l["radius"],
                 "type": l["type"], "flicker": l["flicker"],
                 "flicker_speed": l["flicker_speed"]}
                for l in self.lighting.lights
                if not l.get("_enemy_light")
            ],
            "portals": [p.to_dict() for p in self.portals],
            "holes": [
                {"x": h.x, "y": h.y, "w": h.width, "h": h.height}
                for h in self.holes
            ],
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"maps/{name}.json")

    def load(self, name="map"):
        filepath = os.path.join(MAPS_DIR, f"{name}.json")
        try:
            with open(filepath) as f:
                data = json.load(f)
            self._apply(data)
        except FileNotFoundError:
            print(f"maps/{name}.json introuvable")

    def _apply(self, data):
        """Applique les données d'une map."""
        if "ground_y" in data:
            settings.GROUND_Y = data["ground_y"]
        if "ceiling_y" in data:
            settings.CEILING_Y = data["ceiling_y"]
        if "scene_width" in data:
            settings.SCENE_WIDTH = data["scene_width"]
            self.camera.scene_width = data["scene_width"]
        if "camera_y_offset" in data:
            self.camera.y_offset = data["camera_y_offset"]
        if "spawn" in data:
            self.spawn_x = data["spawn"]["x"]
            self.spawn_y = data["spawn"]["y"]
            self.player.spawn_x = self.spawn_x
            self.player.spawn_y = self.spawn_y
        if "bg_color" in data:
            self.bg_color = data["bg_color"]
        if "wall_color" in data:
            self.wall_color = data["wall_color"]

        # Plateformes
        self.platforms.clear()
        for p in data.get("platforms", []):
            self.platforms.append(
                Platform(p["x"], p["y"], p["w"], p["h"], BLANC))

        # Murs custom
        self.custom_walls.clear()
        for w in data.get("custom_walls", []):
            self.custom_walls.append(
                Wall(w["x"], w["y"], w["w"], w["h"], visible=True))

        # Ennemis
        self.enemies.clear()
        for e in data.get("enemies", []):
            self.enemies.append(Enemy(
                e["x"], e["y"],
                has_gravity=e.get("has_gravity", True),
                has_collision=e.get("has_collision", True),
                sprite_name=e.get("sprite_name", "monstre_perdu.png"),
                can_jump=e.get("can_jump", False),
                detect_range=e.get("detect_range", 200),
                detect_height=e.get("detect_height", 80),
                has_light=e.get("has_light", False),
                light_type=e.get("light_type", "dim"),
                light_radius=e.get("light_radius", 100),
                patrol_left=e.get("patrol_left", -1),
                patrol_right=e.get("patrol_right", -1)))

        # Lumières
        self.lighting.lights.clear()
        for l in data.get("lights", []):
            self.lighting.add_light(
                l["x"], l["y"],
                radius=l["radius"], type=l["type"],
                flicker=l.get("flicker", False),
                flicker_speed=l.get("flicker_speed", 5))

        # Portails
        self.portals.clear()
        for p in data.get("portals", []):
            self.portals.append(Portal(
                p["x"], p["y"], p["w"], p["h"],
                p["target_map"],
                p.get("target_x", -1),
                p.get("target_y", -1)))

        # Trous
        self.holes.clear()
        for h in data.get("holes", []):
            self.holes.append(pygame.Rect(h["x"], h["y"], h["w"], h["h"]))
        self.rebuild_hole_borders()

    def load_map_for_portal(self, name):
        """Charge une map suite à un portail."""
        filepath = os.path.join(MAPS_DIR, f"{name}.json")
        try:
            with open(filepath) as f:
                data = json.load(f)
            self._apply(data)
            return True
        except FileNotFoundError:
            print(f"maps/{name}.json introuvable")
            return False