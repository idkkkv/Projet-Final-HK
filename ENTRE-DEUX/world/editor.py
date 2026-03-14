import pygame
import json
import settings
from entities.enemy import Enemy
from settings import *
from world.tilemap import Platform

class Editor:
    def __init__(self, platforms, enemies, camera, lighting):
        self.platforms = platforms
        self.enemies = enemies
        self.camera = camera
        self.lighting = lighting
        self.active = False
        self.first_point = None
        self.mod = False
        # Mode lumière
        self.light_mode = False
        self.light_first_point = None

    def toggle(self):
        self.active = not self.active
        self.first_point = None
        self.light_first_point = None
        print("Éditeur :", "ON" if self.active else "OFF")

    def change(self):
        self.first_point = None
        self.mod = not self.mod
        settings.mod = 1 if self.mod else 0
        print("Mode mob :", "ON" if self.mod else "OFF")

    def toggle_light(self):
        self.light_mode = not self.light_mode
        self.light_first_point = None
        print("Mode lumière :", "ON" if self.light_mode else "OFF")

    # ── PLATEFORMES ──────────────────────────────
    def handle_click(self, mouse_pos):
        wx = int(mouse_pos[0] + self.camera.offset_x)
        wy = int(mouse_pos[1] + self.camera.offset_y)

        if self.mod:
            self.enemies.append(Enemy(wx, wy))
            return

        if self.first_point is None:
            self.first_point = (wx, wy)
            print(f"Premier point : {self.first_point}")
            return

        x1, y1 = self.first_point
        x2, y2 = wx, wy
        x = min(x1, x2)
        y = min(y1, y2)
        w = abs(x2 - x1)
        h = abs(y2 - y1)
        if w > 0 and h > 0:
            self.platforms.append(Platform(x, y, w, h, BLANC))
            print(f"Plateforme créée : x={x} y={y} w={w} h={h}")
        self.first_point = None

    def delete_platform(self, mouse_pos):
        wx = int(mouse_pos[0] + self.camera.offset_x)
        wy = int(mouse_pos[1] + self.camera.offset_y)
        point = pygame.Rect(wx, wy, 1, 1)
        self.platforms[:] = [p for p in self.platforms
                              if not p.rect.colliderect(point)]

    def delete_mob(self, mouse_pos):
        wx = int(mouse_pos[0] + self.camera.offset_x)
        wy = int(mouse_pos[1] + self.camera.offset_y)
        point = pygame.Rect(wx, wy, 1, 1)
        self.enemies[:] = [e for e in self.enemies
                           if not e.rect.colliderect(point)]

    # ── LUMIÈRES ─────────────────────────────────
    def handle_light_click(self, mouse_pos):
        wx = int(mouse_pos[0] + self.camera.offset_x)
        wy = int(mouse_pos[1] + self.camera.offset_y)

        if self.light_first_point is None:
            self.light_first_point = (wx, wy)
            print(f"Centre lumière : ({wx}, {wy})")
        else:
            cx, cy = self.light_first_point
            radius = int(((wx - cx)**2 + (wy - cy)**2) ** 0.5)
            print("Type ? (p=player / t=torch / l=large / c=cool / d=dim/ b=back) : ", end="")
            choice = input().strip().lower()
            types = {"p": "player", "t": "torch", "l": "large", "c": "cool", "d": "dim", "b": "background"}
            light_type = types.get(choice, "torch")
            self.lighting.add_light(cx, cy, radius=radius, type=light_type)
            print(f"✓ Lumière '{light_type}' — ({cx},{cy}) r={radius}")
            self.light_first_point = None

    def delete_light(self, mouse_pos):
        wx = int(mouse_pos[0] + self.camera.offset_x)
        wy = int(mouse_pos[1] + self.camera.offset_y)
        self.lighting.lights[:] = [
            l for l in self.lighting.lights
            if not (abs(l["x"] - wx) < l["radius"] and abs(l["y"] - wy) < l["radius"])
        ]
        print("Lumière supprimée")

    def draw_preview(self, surf, mouse_pos):
        if self.first_point is None:
            return
        wx = int(mouse_pos[0] + self.camera.offset_x)
        wy = int(mouse_pos[1] + self.camera.offset_y)
        x = min(self.first_point[0], wx) - int(self.camera.offset_x)
        y = min(self.first_point[1], wy) - int(self.camera.offset_y)
        w = abs(wx - self.first_point[0])
        h = abs(wy - self.first_point[1])
        pygame.draw.rect(surf, (100, 200, 255), (x, y, w, h), 2)

    def draw_light_preview(self, surf, mouse_pos):
        if not self.light_mode:
            return
        if self.light_first_point is None:
            pygame.draw.circle(surf, (255, 200, 0), mouse_pos, 5)
        else:
            cx = int(self.light_first_point[0] - self.camera.offset_x)
            cy = int(self.light_first_point[1] - self.camera.offset_y)
            radius = int(((mouse_pos[0] - cx)**2 + (mouse_pos[1] - cy)**2) ** 0.5)
            pygame.draw.circle(surf, (255, 200, 0), (cx, cy), radius, 2)
            pygame.draw.circle(surf, (255, 200, 0), (cx, cy), 5)
            font = pygame.font.SysFont("Arial", 16)
            text = font.render(f"r={radius}", True, (255, 200, 0))
            surf.blit(text, (mouse_pos[0] + 10, mouse_pos[1]))

    # ── SAVE / LOAD ───────────────────────────────
    def save(self, filename="map.json"):
        data = {
            "platforms": [
                {"x": p.rect.x, "y": p.rect.y,
                 "w": p.rect.width, "h": p.rect.height}
                for p in self.platforms
            ],
            "lights": [
                {"x": l["x"], "y": l["y"],
                 "radius": l["radius"], "type": l["type"]}
                for l in self.lighting.lights
            ]
        }
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Map sauvegardée ({len(data['platforms'])} plateformes, {len(data['lights'])} lumières)")

    def load(self, filename="map.json"):
        try:
            with open(filename) as f:
                data = json.load(f)
            self.platforms.clear()
            for p in data.get("platforms", []):
                self.platforms.append(Platform(p["x"], p["y"], p["w"], p["h"], BLANC))
            self.lighting.lights.clear()
            for l in data.get("lights", []):
                self.lighting.add_light(l["x"], l["y"], radius=l["radius"], type=l["type"])
            print(f"Map chargée !")
        except FileNotFoundError:
            print("Pas de map sauvegardée")