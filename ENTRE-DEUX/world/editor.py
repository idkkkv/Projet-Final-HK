# ─────────────────────────────────────────
#  ENTRE-DEUX — Éditeur de niveaux
# ─────────────────────────────────────────
#
#  E            → activer/désactiver l'éditeur
#  M            → changer de mode (Plateforme / Mob / Lumière)
#  H            → afficher/masquer les hitboxes
#  S            → sauvegarder la map (demande un nom)
#  L            → charger la map (demande un nom)
#  ↑ ↓          → monter/descendre le sol
#  ← →          → rétrécir/agrandir la largeur de la scène
#  PgUp / PgDn  → décaler la caméra
#
#  Mode Plateforme : clic G ×2, clic D suppr
#  Mode Mob : [G] gravité, [C] collision, clic G poser, clic D suppr
#  Mode Lumière : [T] type, [F] flicker, [Molette] speed
# ─────────────────────────────────────────

import os
import pygame
import json
import settings
from entities.enemy import Enemy
from settings import *
from world.tilemap import Platform

LIGHT_TYPES = ["player", "torch", "large", "cool", "dim", "background"]

# Dossier de sauvegarde des maps
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS_DIR = os.path.join(_BASE_DIR, "maps")


class Editor:
    def __init__(self, platforms, enemies, camera, lighting):
        self.platforms = platforms
        self.enemies = enemies
        self.camera = camera
        self.lighting = lighting
        self.active = False
        self.first_point = None

        # Mode : 0 = plateforme, 1 = mob, 2 = lumière
        self.mode = 0
        self._mode_names = ["Plateforme", "Mob", "Lumière"]

        # Options lumière
        self.light_type_index = 1
        self.light_flicker = False
        self.light_flicker_speed = 5
        self.light_first_point = None

        # Options mob
        self.mob_gravity = True
        self.mob_collision = True

        # Affichage des hitboxes
        self.show_hitboxes = False

        # Input texte pour noms de maps
        self._text_input = ""
        self._text_mode = None   # "save" ou "load" ou None
        self._text_prompt = ""

        # Fonts
        self._font = None
        self._font_small = None

        # Crée le dossier maps/ s'il n'existe pas
        os.makedirs(MAPS_DIR, exist_ok=True)

    def _get_font(self):
        if self._font is None:
            self._font = pygame.font.SysFont("Consolas", 16)
            self._font_small = pygame.font.SysFont("Consolas", 13)
        return self._font

    def toggle(self):
        self.active = not self.active
        self.first_point = None
        self.light_first_point = None
        self._text_mode = None

    def change_mode(self):
        self.mode = (self.mode + 1) % 3
        self.first_point = None
        self.light_first_point = None

    # ── Gestion des touches ──────────────────

    def handle_key(self, key):
        # Si on est en mode texte (saisie de nom de map)
        if self._text_mode is not None:
            return self._handle_text_input(key)

        if key == pygame.K_m:
            self.change_mode()
        elif key == pygame.K_h:
            self.show_hitboxes = not self.show_hitboxes
        elif key == pygame.K_s:
            self._text_mode = "save"
            self._text_input = ""
            self._text_prompt = "Nom de la map à sauvegarder :"
            return "text_input"
        elif key == pygame.K_l:
            self._text_mode = "load"
            self._text_input = ""
            self._text_prompt = "Nom de la map à charger :"
            # Lister les maps existantes
            maps = self._list_maps()
            if maps:
                self._text_prompt += f"  ({', '.join(maps)})"
            return "text_input"

        elif key == pygame.K_UP:
            settings.GROUND_Y = max(100, settings.GROUND_Y - 20)
        elif key == pygame.K_DOWN:
            settings.GROUND_Y = min(3000, settings.GROUND_Y + 20)
        elif key == pygame.K_LEFT:
            settings.SCENE_WIDTH = max(800, settings.SCENE_WIDTH - 100)
            self.camera.scene_width = settings.SCENE_WIDTH
        elif key == pygame.K_RIGHT:
            settings.SCENE_WIDTH = settings.SCENE_WIDTH + 100
            self.camera.scene_width = settings.SCENE_WIDTH
        elif key == pygame.K_PAGEUP:
            self.camera.y_offset = max(-400, self.camera.y_offset - 20)
        elif key == pygame.K_PAGEDOWN:
            self.camera.y_offset = min(400, self.camera.y_offset + 20)

        # Mode lumière
        elif key == pygame.K_t and self.mode == 2:
            self.light_type_index = (self.light_type_index + 1) % len(LIGHT_TYPES)
        elif key == pygame.K_f and self.mode == 2:
            self.light_flicker = not self.light_flicker

        # Mode mob
        elif key == pygame.K_g and self.mode == 1:
            self.mob_gravity = not self.mob_gravity
        elif key == pygame.K_c and self.mode == 1:
            self.mob_collision = not self.mob_collision

        return None

    def _handle_text_input(self, key):
        """Gère la saisie de texte pour le nom de map."""
        if key == pygame.K_RETURN:
            name = self._text_input.strip()
            if name:
                if self._text_mode == "save":
                    self.save(name)
                elif self._text_mode == "load":
                    self.load(name)
            self._text_mode = None
            self._text_input = ""
            return "done"
        elif key == pygame.K_ESCAPE:
            self._text_mode = None
            self._text_input = ""
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
        """Liste les noms de maps existantes."""
        if not os.path.isdir(MAPS_DIR):
            return []
        maps = []
        for f in os.listdir(MAPS_DIR):
            if f.endswith(".json"):
                maps.append(f[:-5])
        return sorted(maps)

    def handle_scroll(self, direction):
        if self.mode == 2:
            self.light_flicker_speed = max(1, min(15,
                self.light_flicker_speed + direction))

    # ── Clics ────────────────────────────────

    def handle_click(self, mouse_pos):
        if self._text_mode is not None:
            return
        wx = int(mouse_pos[0] + self.camera.offset_x)
        wy = int(mouse_pos[1] + self.camera.offset_y)

        if self.mode == 0:
            self._click_platform(wx, wy)
        elif self.mode == 1:
            self._click_mob(wx, wy)
        elif self.mode == 2:
            self._click_light(wx, wy)

    def _click_platform(self, wx, wy):
        if self.first_point is None:
            self.first_point = (wx, wy)
        else:
            x1, y1 = self.first_point
            x, y = min(x1, wx), min(y1, wy)
            w, h = abs(wx - x1), abs(wy - y1)
            if w > 0 and h > 0:
                self.platforms.append(Platform(x, y, w, h, BLANC))
            self.first_point = None

    def _click_mob(self, wx, wy):
        test_rect = pygame.Rect(wx, wy, 40, 50)
        for p in self.platforms:
            if test_rect.colliderect(p.rect):
                print("✗ Ennemi dans une plateforme")
                return
        self.enemies.append(Enemy(wx, wy,
                                  has_gravity=self.mob_gravity,
                                  has_collision=self.mob_collision))

    def _click_light(self, wx, wy):
        if self.light_first_point is None:
            self.light_first_point = (wx, wy)
        else:
            cx, cy = self.light_first_point
            radius = int(((wx - cx)**2 + (wy - cy)**2) ** 0.5)
            if radius > 5:
                ltype = LIGHT_TYPES[self.light_type_index]
                self.lighting.add_light(cx, cy, radius=radius, type=ltype,
                                        flicker=self.light_flicker,
                                        flicker_speed=self.light_flicker_speed)
            self.light_first_point = None

    def handle_right_click(self, mouse_pos):
        if self._text_mode is not None:
            return
        wx = int(mouse_pos[0] + self.camera.offset_x)
        wy = int(mouse_pos[1] + self.camera.offset_y)
        point = pygame.Rect(wx, wy, 1, 1)

        if self.mode == 0:
            self.platforms[:] = [p for p in self.platforms
                                 if not p.rect.colliderect(point)]
        elif self.mode == 1:
            self.enemies[:] = [e for e in self.enemies
                               if not e.rect.colliderect(point)]
        elif self.mode == 2:
            self.lighting.lights[:] = [
                l for l in self.lighting.lights
                if not (abs(l["x"] - wx) < l["radius"]
                        and abs(l["y"] - wy) < l["radius"])]

    # ── Preview ──────────────────────────────

    def draw_preview(self, surf, mouse_pos):
        if self.mode == 0:
            self._draw_platform_preview(surf, mouse_pos)
        elif self.mode == 2:
            self._draw_light_preview(surf, mouse_pos)

    def _draw_platform_preview(self, surf, mouse_pos):
        if self.first_point is None:
            return
        wx = int(mouse_pos[0] + self.camera.offset_x)
        wy = int(mouse_pos[1] + self.camera.offset_y)
        x = min(self.first_point[0], wx) - int(self.camera.offset_x)
        y = min(self.first_point[1], wy) - int(self.camera.offset_y)
        w = abs(wx - self.first_point[0])
        h = abs(wy - self.first_point[1])
        pygame.draw.rect(surf, (100, 200, 255), (x, y, w, h), 2)

    def _draw_light_preview(self, surf, mouse_pos):
        if self.light_first_point is None:
            pygame.draw.circle(surf, (255, 200, 0), mouse_pos, 5)
        else:
            cx = int(self.light_first_point[0] - self.camera.offset_x)
            cy = int(self.light_first_point[1] - self.camera.offset_y)
            r = int(((mouse_pos[0] - cx)**2 + (mouse_pos[1] - cy)**2) ** 0.5)
            pygame.draw.circle(surf, (255, 200, 0), (cx, cy), r, 2)
            pygame.draw.circle(surf, (255, 200, 0), (cx, cy), 5)

    # ── HUD Éditeur ──────────────────────────

    def draw_hud(self, surf):
        font = self._get_font()
        small = self._font_small
        w = surf.get_width()

        # ── Si saisie de texte en cours → boîte de dialogue ──
        if self._text_mode is not None:
            self._draw_text_input(surf)
            return

        # Fond
        panel = pygame.Surface((w, 90), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 180))
        surf.blit(panel, (0, 0))

        # Ligne 1 : mode
        hb_text = " [H] Hitbox ON" if self.show_hitboxes else ""
        mode_surf = font.render(
            f"ÉDITEUR — {self._mode_names[self.mode]}{hb_text}", True,
            (0, 255, 120))
        surf.blit(mode_surf, (10, 6))

        # Infos scène (droite)
        info = (f"Sol: {settings.GROUND_Y}  "
                f"Scène: {settings.SCENE_WIDTH}  "
                f"Cam: {self.camera.y_offset}")
        surf.blit(small.render(info, True, (255, 255, 0)),
                  (w - small.size(info)[0] - 10, 6))

        # Ligne 2 : options du mode
        y2 = 28
        if self.mode == 0:
            surf.blit(font.render(
                "Clic G ×2 = plateforme   |   Clic D = supprimer",
                True, (200, 200, 255)), (10, y2))

        elif self.mode == 1:
            g_color = (0, 255, 0) if self.mob_gravity else (255, 80, 80)
            c_color = (0, 255, 0) if self.mob_collision else (255, 80, 80)
            surf.blit(font.render(
                f"[G] Gravité: {'ON' if self.mob_gravity else 'OFF'}",
                True, g_color), (10, y2))
            surf.blit(font.render(
                f"[C] Collision: {'ON' if self.mob_collision else 'OFF'}",
                True, c_color), (230, y2))

        elif self.mode == 2:
            ltype = LIGHT_TYPES[self.light_type_index]
            f_color = (0, 255, 0) if self.light_flicker else (255, 80, 80)
            surf.blit(font.render(f"[T] {ltype}", True,
                                  (255, 200, 100)), (10, y2))
            surf.blit(font.render(
                f"[F] Flicker: {'ON' if self.light_flicker else 'OFF'}",
                True, f_color), (200, y2))
            surf.blit(font.render(
                f"Speed: {self.light_flicker_speed}",
                True, (200, 200, 255)), (410, y2))

        # Ligne 3 : raccourcis
        keys = ("[M] mode  [H] hitbox  [S] save  [L] load  "
                "[↑↓] sol  [←→] scène  [PgUp/Dn] cam")
        surf.blit(small.render(keys, True, (140, 140, 140)), (10, 70))

    def _draw_text_input(self, surf):
        """Dessine la boîte de saisie de nom de map."""
        font = self._get_font()
        w, h = surf.get_size()

        # Fond assombri
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surf.blit(overlay, (0, 0))

        # Boîte centrale
        box_w, box_h = 500, 120
        box_x = (w - box_w) // 2
        box_y = (h - box_h) // 2
        pygame.draw.rect(surf, (30, 20, 40), (box_x, box_y, box_w, box_h))
        pygame.draw.rect(surf, (100, 200, 255),
                         (box_x, box_y, box_w, box_h), 2)

        # Prompt
        prompt_surf = font.render(self._text_prompt, True, (200, 200, 255))
        surf.blit(prompt_surf, (box_x + 15, box_y + 15))

        # Input
        input_text = self._text_input + "█"
        input_surf = font.render(input_text, True, (255, 255, 255))
        surf.blit(input_surf, (box_x + 15, box_y + 50))

        # Aide
        help_surf = font.render("[Entrée] valider   [Échap] annuler",
                                True, (140, 140, 140))
        surf.blit(help_surf, (box_x + 15, box_y + 85))

    # ── SAVE / LOAD ──────────────────────────

    def save(self, name="map"):
        filepath = os.path.join(MAPS_DIR, f"{name}.json")
        data = {
            "ground_y": settings.GROUND_Y,
            "scene_width": settings.SCENE_WIDTH,
            "camera_y_offset": self.camera.y_offset,
            "platforms": [
                {"x": p.rect.x, "y": p.rect.y,
                 "w": p.rect.width, "h": p.rect.height}
                for p in self.platforms
            ],
            "enemies": [e.to_dict() for e in self.enemies],
            "lights": [
                {"x": l["x"], "y": l["y"],
                 "radius": l["radius"], "type": l["type"],
                 "flicker": l["flicker"],
                 "flicker_speed": l["flicker_speed"]}
                for l in self.lighting.lights
            ],
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✓ Sauvegardé : maps/{name}.json")

    def load(self, name="map"):
        filepath = os.path.join(MAPS_DIR, f"{name}.json")
        try:
            with open(filepath) as f:
                data = json.load(f)

            if "ground_y" in data:
                settings.GROUND_Y = data["ground_y"]
            if "scene_width" in data:
                settings.SCENE_WIDTH = data["scene_width"]
                self.camera.scene_width = data["scene_width"]
            if "camera_y_offset" in data:
                self.camera.y_offset = data["camera_y_offset"]

            self.platforms.clear()
            for p in data.get("platforms", []):
                self.platforms.append(
                    Platform(p["x"], p["y"], p["w"], p["h"], BLANC))

            self.enemies.clear()
            for e in data.get("enemies", []):
                self.enemies.append(Enemy(
                    e["x"], e["y"],
                    has_gravity=e.get("has_gravity", True),
                    has_collision=e.get("has_collision", True)))

            self.lighting.lights.clear()
            for l in data.get("lights", []):
                self.lighting.add_light(
                    l["x"], l["y"], radius=l["radius"], type=l["type"],
                    flicker=l.get("flicker", False),
                    flicker_speed=l.get("flicker_speed", 5))

            print(f"✓ Chargé : maps/{name}.json")
        except FileNotFoundError:
            print(f"✗ maps/{name}.json introuvable")