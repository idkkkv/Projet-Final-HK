# ─────────────────────────────────────────
#  ENTRE-DEUX — Éditeur de niveaux
# ─────────────────────────────────────────

import os
import json
import datetime
import pygame
import settings
from entities.enemy import Enemy, list_enemy_sprites
from systems.hitbox_config import get_hitbox, set_hitbox
from settings import *
from world.tilemap import Platform, Wall
from utils import find_file

LIGHT_TYPES = ["player", "torch", "large", "cool", "dim", "background"]

_BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS_DIR    = os.path.join(_BASE_DIR, "maps")
RESTORE_DIR = os.path.join(MAPS_DIR, "_restore")

_NAMED_COLORS = {
    "noir":(0,0,0),"blanc":(255,255,255),"rouge":(200,50,50),
    "vert":(50,180,80),"bleu":(30,80,200),"violet":(80,40,140),
    "cyan":(40,180,200),"orange":(220,130,40),"rose":(200,80,140),
    "gris":(90,90,90),"jaune":(220,200,50),
}

def _parse_color(s):
    s = s.strip().lower()
    if s in _NAMED_COLORS: return _NAMED_COLORS[s]
    if s.startswith("#") and len(s)==7:
        try: return (int(s[1:3],16),int(s[3:5],16),int(s[5:7],16))
        except ValueError: return None
    parts = s.split(",")
    if len(parts)==3:
        try:
            r,g,b = int(parts[0]),int(parts[1]),int(parts[2])
            if all(0<=v<=255 for v in (r,g,b)): return (r,g,b)
        except ValueError: pass
    return None


class Portal:
    def __init__(self, x, y, w, h, target_map, target_x=-1, target_y=-1):
        self.rect       = pygame.Rect(x, y, w, h)
        self.target_map = target_map
        self.target_x   = target_x
        self.target_y   = target_y

    def to_dict(self):
        return {"x":self.rect.x,"y":self.rect.y,
                "w":self.rect.width,"h":self.rect.height,
                "target_map":self.target_map,
                "target_x":self.target_x,"target_y":self.target_y}

    def draw(self, surf, camera, font):
        sr = camera.apply(self.rect)
        s  = pygame.Surface((sr.w,sr.h),pygame.SRCALPHA)
        s.fill((0,120,255,60)); surf.blit(s,sr)
        pygame.draw.rect(surf,(0,120,255),sr,2)
        surf.blit(font.render(f"-> {self.target_map}",True,(0,180,255)),(sr.x,sr.y-18))


class Editor:
    def __init__(self, platforms, enemies, camera, lighting, player):
        self.platforms    = platforms
        self.enemies      = enemies
        self.camera       = camera
        self.lighting     = lighting
        self.player       = player
        self.active       = False
        self.first_point  = None
        self.portals      = []
        self.custom_walls = []

        self.ground_segments  = []
        self.ceiling_segments = []
        self.left_segments    = []
        self.right_segments   = []

        self.holes = []

        self._history     = []
        self._max_history = 20

        self._hud_msg       = ""
        self._hud_msg_timer = 0.0

        self._restore_confirm       = False
        self._restore_confirm_timer = 0.0

        self.mode = 0
        self._mode_names = ["Plateforme","Mob","Lumiere","Spawn","Portail",
                            "Mur","Hitbox","Trou","Copier/Coller"]

        self._copy_rect           = None
        self._clipboard_platforms = []
        self._clipboard_walls     = []
        self._has_clipboard       = False

        self.light_type_index    = 1
        self.light_flicker       = False
        self.light_flicker_speed = 5
        self.light_first_point   = None

        self.mob_gravity           = True
        self.mob_collision         = True
        self.mob_can_jump          = False
        self.mob_can_jump_patrol   = False
        self.mob_detect_range      = 200
        self.mob_has_light         = False
        self.mob_sprite_index      = 0
        self.mob_can_fall_in_holes = False
        self.mob_respawn_timeout   = 10.0
        self.mob_jump_power        = 400
        self._enemy_sprites        = []
        self._refresh_sprites()

        self.mob_patrol_mode = False
        self._patrol_target  = None
        self._patrol_first_x = None
        self.mob_detect_mode = False
        self._detect_target  = None

        self._hb_sprite_index = 0
        self._hb_first_point  = None

        self.show_hitboxes = False

        self._text_input          = ""
        self._text_mode           = None
        self._text_prompt         = ""
        self._pending_portal_rect = None

        self.spawn_x = self.player.spawn_x
        self.spawn_y = self.player.spawn_y

        self.bg_color   = list(VIOLET)
        self.wall_color = [0, 0, 0]

        self._font       = None
        self._font_small = None
        os.makedirs(MAPS_DIR,    exist_ok=True)
        os.makedirs(RESTORE_DIR, exist_ok=True)

    # ── Fonts ─────────────────────────────────────────────────────────────
    def _get_font(self):
        if self._font is None:
            self._font       = pygame.font.SysFont("Consolas", 16)
            self._font_small = pygame.font.SysFont("Consolas", 13)
        return self._font

    def _refresh_sprites(self):
        self._enemy_sprites = list_enemy_sprites()
        if not self._enemy_sprites: self._enemy_sprites = ["monstre_perdu.png"]

    def _current_sprite(self):
        return (self._enemy_sprites[self.mob_sprite_index % len(self._enemy_sprites)]
                if self._enemy_sprites else "monstre_perdu.png")

    # ── Phases ────────────────────────────────────────────────────────────
    @property
    def has_holes(self):
        return len(self.holes) > 0

    # ── Segments de bordure ───────────────────────────────────────────────
    def build_border_segments(self):
        gy = settings.GROUND_Y
        cy = settings.CEILING_Y
        sw = settings.SCENE_WIDTH
        t  = 800
        self.ground_segments  = [Wall(0,  gy,   sw, t,          visible=True, is_border=True)]
        self.ceiling_segments = [Wall(0,  cy-t, sw, t,          visible=True, is_border=True)]
        self.left_segments    = [Wall(-t, cy-t, t,  gy-cy+t*2, visible=True, is_border=True)]
        self.right_segments   = [Wall(sw, cy-t, t,  gy-cy+t*2, visible=True, is_border=True)]
        self.holes            = []

    def all_segments(self):
        return (self.ground_segments + self.ceiling_segments +
                self.left_segments   + self.right_segments)

    def _punch_hole_in_list(self, segments, hole, is_border=False):
        hx,hy   = hole.x, hole.y
        hx2,hy2 = hx+hole.width, hy+hole.height
        result  = []
        for wall in segments:
            wr = wall.rect
            if not wr.colliderect(hole):
                result.append(wall); continue
            wx,wy   = wr.x,wr.y; wx2,wy2=wx+wr.width,wy+wr.height
            if hy  > wy:  result.append(Wall(wx, wy,  wr.width, hy-wy,       visible=True, is_border=is_border))
            if hy2 < wy2: result.append(Wall(wx, hy2, wr.width, wy2-hy2,     visible=True, is_border=is_border))
            top=max(wy,hy); bot=min(wy2,hy2)
            if bot>top:
                if hx  > wx:  result.append(Wall(wx,  top, hx-wx,   bot-top, visible=True, is_border=is_border))
                if hx2 < wx2: result.append(Wall(hx2, top, wx2-hx2, bot-top, visible=True, is_border=is_border))
        return result

    def _punch_hole_in_custom_walls(self, hole):
        hx,hy   = hole.x, hole.y
        hx2,hy2 = hx+hole.width, hy+hole.height
        to_remove=[]; new_walls=[]
        for wall in self.custom_walls:
            wr = wall.rect
            if not wr.colliderect(hole): continue
            to_remove.append(wall)
            wx,wy=wr.x,wr.y; wx2,wy2=wx+wr.width,wy+wr.height
            if hy  > wy:  new_walls.append(Wall(wx, wy,  wr.width, hy-wy,   visible=True))
            if hy2 < wy2: new_walls.append(Wall(wx, hy2, wr.width, wy2-hy2, visible=True))
            top=max(wy,hy); bot=min(wy2,hy2)
            if bot>top:
                if hx  > wx:  new_walls.append(Wall(wx,  top, hx-wx,   bot-top, visible=True))
                if hx2 < wx2: new_walls.append(Wall(hx2, top, wx2-hx2, bot-top, visible=True))
        for w in to_remove: self.custom_walls.remove(w)
        self.custom_walls.extend(new_walls)

    def apply_hole(self, hole_rect):
        self.ground_segments  = self._punch_hole_in_list(self.ground_segments,  hole_rect, is_border=True)
        self.ceiling_segments = self._punch_hole_in_list(self.ceiling_segments, hole_rect, is_border=True)
        self.left_segments    = self._punch_hole_in_list(self.left_segments,    hole_rect, is_border=True)
        self.right_segments   = self._punch_hole_in_list(self.right_segments,   hole_rect, is_border=True)
        self._punch_hole_in_custom_walls(hole_rect)
        self.holes.append(hole_rect)

    # ── Historique Ctrl+Z ─────────────────────────────────────────────────
    def _snapshot(self):
        state = {
            "ground_y":    settings.GROUND_Y,
            "ceiling_y":   settings.CEILING_Y,
            "scene_width": settings.SCENE_WIDTH,
            "spawn":       {"x":self.spawn_x,"y":self.spawn_y},
            "bg_color":    list(self.bg_color),
            "platforms":   [{"x":p.rect.x,"y":p.rect.y,"w":p.rect.width,"h":p.rect.height} for p in self.platforms],
            "custom_walls":[{"x":w.rect.x,"y":w.rect.y,"w":w.rect.width,"h":w.rect.height} for w in self.custom_walls],
            "ground_segments":  [{"x":w.rect.x,"y":w.rect.y,"w":w.rect.width,"h":w.rect.height} for w in self.ground_segments],
            "ceiling_segments": [{"x":w.rect.x,"y":w.rect.y,"w":w.rect.width,"h":w.rect.height} for w in self.ceiling_segments],
            "left_segments":    [{"x":w.rect.x,"y":w.rect.y,"w":w.rect.width,"h":w.rect.height} for w in self.left_segments],
            "right_segments":   [{"x":w.rect.x,"y":w.rect.y,"w":w.rect.width,"h":w.rect.height} for w in self.right_segments],
            "holes":  [{"x":h.x,"y":h.y,"w":h.width,"h":h.height} for h in self.holes],
            "enemies":[e.to_dict() for e in self.enemies],
            "lights": [{"x":l["x"],"y":l["y"],"radius":l["radius"],"type":l["type"],
                        "flicker":l["flicker"],"flicker_speed":l["flicker_speed"]}
                       for l in self.lighting.lights if not l.get("_enemy_light")],
            "portals":[p.to_dict() for p in self.portals],
        }
        self._history.append(state)
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def _undo(self):
        if not self._history:
            self._show_msg("Rien à annuler"); return
        state = self._history.pop()
        self._apply_state(state)
        self._show_msg(f"Annulé — {len(self._history)} état(s) restant(s)")

    def _show_msg(self, msg, duration=3.0):
        self._hud_msg       = msg
        self._hud_msg_timer = duration

    # ── Point de restauration ─────────────────────────────────────────────
    def _list_restore_points(self):
        if not os.path.isdir(RESTORE_DIR): return []
        return sorted(f[:-5] for f in os.listdir(RESTORE_DIR) if f.endswith(".json"))

    def _save_restore_point(self):
        """Sauvegarde l'état courant comme point de restauration."""
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"restore_{ts}"
        fp   = os.path.join(RESTORE_DIR, f"{name}.json")
        self._save_to(fp)
        return name

    def _load_restore_point(self, name):
        """Charge un point de restauration depuis _restore/."""
        fp = os.path.join(RESTORE_DIR, f"{name}.json")
        try:
            with open(fp) as f: data = json.load(f)
            self._snapshot()
            self._apply_state(data)
            self._show_msg(f"Restauré : {name}")
        except FileNotFoundError:
            self._show_msg(f"Fichier introuvable : {name}")

    # ── Toggle / Mode ─────────────────────────────────────────────────────
    def toggle(self):
        self.active            = not self.active
        self.first_point       = None
        self.light_first_point = None
        self._text_mode        = None
        self._hb_first_point   = None

    def change_mode(self):
        self.mode              = (self.mode+1) % 9
        self.first_point       = None
        self.light_first_point = None
        self._hb_first_point   = None
        self.mob_patrol_mode   = False
        self._patrol_target    = None
        self._patrol_first_x   = None
        self.mob_detect_mode   = False
        self._detect_target    = None
        self._copy_rect        = None
        if self.mode in (1,6): self._refresh_sprites()

    # ── Touches ───────────────────────────────────────────────────────────
    def handle_key(self, key):
        if self._text_mode is not None:
            return self._handle_text(key)

        mods = pygame.key.get_mods()

        # Ctrl+Z — annuler
        if key == pygame.K_z and (mods & pygame.KMOD_CTRL):
            self._undo(); return "undo"

        # Ctrl+R — charger le dernier point de restauration (avec confirmation)
        if key == pygame.K_r and (mods & pygame.KMOD_CTRL):
            restores = self._list_restore_points()
            if not restores:
                self._show_msg("Aucun point de restauration — utilisez [S] pour sauvegarder d'abord")
            elif self._restore_confirm:
                # Deuxième Ctrl+R : charge le plus récent
                self._load_restore_point(restores[-1])
                self._restore_confirm       = False
                self._restore_confirm_timer = 0.0
            else:
                # Premier Ctrl+R : demande confirmation
                self._restore_confirm       = True
                self._restore_confirm_timer = 5.0
                self._show_msg(
                    f"Ctrl+R encore pour charger : {restores[-1]}  (5s)", 5.0)
            return None

        # R seul — respawn joueur
        if key == pygame.K_r and not (mods & pygame.KMOD_CTRL):
            self.player.respawn(); return None

        if   key == pygame.K_m: self.change_mode()
        elif key == pygame.K_h: self.show_hitboxes = not self.show_hitboxes
        elif key == pygame.K_n:
            self._ask_text("bg_color_new","Couleur de fond (nom / r,g,b / #hex) :")
            return "text_input"
        elif key == pygame.K_s:
            self._ask_text("save","Sauvegarder sous :"); return "text_input"
        elif key == pygame.K_l:
            maps = self._list_maps()
            self._ask_text("load","Charger :"+(f"  ({', '.join(maps)})" if maps else ""))
            return "text_input"
        elif key == pygame.K_b:
            self.spawn_x=self.spawn_y=100
            self.player.spawn_x=self.player.spawn_y=100
            self.player.respawn()

        # ── Structure (Phase 1 seulement) ─────────────────────────────────
        elif key in (pygame.K_UP, pygame.K_DOWN, pygame.K_HOME, pygame.K_END,
                     pygame.K_LEFT, pygame.K_RIGHT):
            if self.has_holes:
                self._show_msg(
                    "Phase 2 active — structure verrouillée  |  [Ctrl+R]=restaurer  [N]=nouvelle map")
                return None
            self._snapshot()
            if   key == pygame.K_UP:   settings.GROUND_Y  = max(100,  settings.GROUND_Y-20)
            elif key == pygame.K_DOWN: settings.GROUND_Y  = min(3000, settings.GROUND_Y+20)
            elif key == pygame.K_HOME: settings.CEILING_Y = max(-500, settings.CEILING_Y-20)
            elif key == pygame.K_END:  settings.CEILING_Y = min(settings.GROUND_Y-100, settings.CEILING_Y+20)
            elif key == pygame.K_LEFT:
                settings.SCENE_WIDTH = max(800, settings.SCENE_WIDTH-100)
                self.camera.scene_width = settings.SCENE_WIDTH
            elif key == pygame.K_RIGHT:
                settings.SCENE_WIDTH += 100
                self.camera.scene_width = settings.SCENE_WIDTH
            self.build_border_segments()
            return "structure"

        # PageUp/PageDown — priorité : ennemi sélectionné > mode mob > caméra
        elif key == pygame.K_PAGEUP:
            if self.mode == 1 and self.mob_detect_mode and self._detect_target:
                self._detect_target.jump_power = min(800, self._detect_target.jump_power + 50)
                self._show_msg(f"Jump power ennemi = {self._detect_target.jump_power}")
            elif self.mode == 1:
                self.mob_jump_power = min(800, self.mob_jump_power + 50)
                self._show_msg(f"Hauteur de saut : {self.mob_jump_power}")
            else:
                self.camera.y_offset = max(-400, self.camera.y_offset-20)
        elif key == pygame.K_PAGEDOWN:
            if self.mode == 1 and self.mob_detect_mode and self._detect_target:
                self._detect_target.jump_power = max(100, self._detect_target.jump_power - 50)
                self._show_msg(f"Jump power ennemi = {self._detect_target.jump_power}")
            elif self.mode == 1:
                self.mob_jump_power = max(100, self.mob_jump_power - 50)
                self._show_msg(f"Hauteur de saut : {self.mob_jump_power}")
            else:
                self.camera.y_offset = min(400, self.camera.y_offset+20)

        # Lumière
        elif key==pygame.K_t and self.mode==2:
            self.light_type_index=(self.light_type_index+1)%len(LIGHT_TYPES)
        elif key==pygame.K_f and self.mode==2:
            self.light_flicker=not self.light_flicker

        # Mob
        elif key==pygame.K_g and self.mode==1: self.mob_gravity=not self.mob_gravity
        elif key==pygame.K_c and self.mode==1: self.mob_collision=not self.mob_collision
        elif key==pygame.K_j and self.mode==1: self.mob_can_jump=not self.mob_can_jump
        elif key==pygame.K_v and self.mode==1: self.mob_can_jump_patrol=not self.mob_can_jump_patrol
        elif key==pygame.K_i and self.mode==1: self.mob_has_light=not self.mob_has_light
        elif key==pygame.K_o and self.mode==1: self.mob_can_fall_in_holes=not self.mob_can_fall_in_holes
        elif key==pygame.K_t and self.mode==1:
            self.mob_sprite_index=(self.mob_sprite_index+1)%max(1,len(self._enemy_sprites))
        elif key==pygame.K_KP_MULTIPLY and self.mode==1:
            self.mob_respawn_timeout=(5.0 if self.mob_respawn_timeout<0
                                      else min(120.0,self.mob_respawn_timeout+5.0))
        elif key==pygame.K_KP_DIVIDE and self.mode==1:
            self.mob_respawn_timeout=max(-1.0,self.mob_respawn_timeout-5.0)
            if self.mob_respawn_timeout==0.0: self.mob_respawn_timeout=-1.0
        elif key==pygame.K_KP_PLUS  and self.mode==1 and self.mob_detect_mode and self._detect_target:
            self._detect_target.detect_range=min(600,self._detect_target.detect_range+25)
        elif key==pygame.K_KP_MINUS and self.mode==1 and self.mob_detect_mode and self._detect_target:
            self._detect_target.detect_range=max(50,self._detect_target.detect_range-25)
        elif key==pygame.K_KP_PLUS  and self.mode==1: self.mob_detect_range=min(500,self.mob_detect_range+25)
        elif key==pygame.K_KP_MINUS and self.mode==1: self.mob_detect_range=max(50,self.mob_detect_range-25)
        elif key==pygame.K_p and self.mode==1:
            self.mob_patrol_mode=not self.mob_patrol_mode
            self.mob_detect_mode=False; self._patrol_target=None; self._patrol_first_x=None
        elif key==pygame.K_d and self.mode==1:
            self.mob_detect_mode=not self.mob_detect_mode
            self.mob_patrol_mode=False; self._detect_target=None

        # Hitbox
        elif key==pygame.K_t and self.mode==6:
            self._hb_sprite_index=(self._hb_sprite_index+1)%max(1,len(self._enemy_sprites))
            self._hb_first_point=None

        # Copy/Paste
        elif key==pygame.K_c and self.mode==8: self._do_copy()
        elif key==pygame.K_v and self.mode==8:
            if self._has_clipboard:
                mx,my=pygame.mouse.get_pos()
                self._do_paste(int(mx+self.camera.offset_x),int(my+self.camera.offset_y))

        return None

    # ── Nouvelle map ──────────────────────────────────────────────────────
    def _new_map(self, bg_color=None):
        self._snapshot()
        self.platforms.clear(); self.enemies.clear()
        self.lighting.lights.clear(); self.portals.clear(); self.custom_walls.clear()
        self._has_clipboard=False
        self._restore_confirm=False; self._restore_confirm_timer=0.0
        settings.GROUND_Y=590; settings.CEILING_Y=0; settings.SCENE_WIDTH=2400
        self.spawn_x=self.spawn_y=100
        self.player.spawn_x=self.player.spawn_y=100
        self.player.respawn()
        self.camera.y_offset=150
        self.bg_color=list(bg_color) if bg_color else list(VIOLET)
        self.build_border_segments()
        self._show_msg("Nouvelle map — Phase 1 : règle la taille avec ↑↓←→")

    # ── Saisie texte ──────────────────────────────────────────────────────
    def _ask_text(self, mode, prompt):
        self._text_mode=mode; self._text_input=""; self._text_prompt=prompt

    def _handle_text(self, key):
        if key==pygame.K_RETURN:
            name=self._text_input.strip(); mode=self._text_mode
            self._text_mode=None; self._text_input=""
            if mode=="bg_color_new":
                color=_parse_color(name) if name else None
                self._new_map(bg_color=color or tuple(VIOLET))
                return "done"
            if not name: return "done"
            if   mode=="save":  self.save(name)
            elif mode=="load":  self.load(name)
            elif mode=="portal_name" and self._pending_portal_rect:
                r=self._pending_portal_rect
                self.portals.append(Portal(r[0],r[1],r[2],r[3],name))
                self._pending_portal_rect=None
            elif mode=="bg_color":
                color=_parse_color(name)
                if color: self.bg_color=list(color)
            return "done"
        elif key==pygame.K_ESCAPE:
            self._text_mode=None; self._text_input=""; self._pending_portal_rect=None
            return "cancel"
        elif key==pygame.K_BACKSPACE:
            self._text_input=self._text_input[:-1]
        else:
            char=pygame.key.name(key)
            if len(char)==1 and (char.isalnum() or char in ",.#"): self._text_input+=char
            elif char=="space": self._text_input+="_"
            elif char=="-":     self._text_input+="-"
        return "typing"

    def _list_maps(self):
        if not os.path.isdir(MAPS_DIR): return []
        return sorted(f[:-5] for f in os.listdir(MAPS_DIR)
                      if f.endswith(".json") and not f.startswith("_"))

    def handle_scroll(self, direction):
        if self.mode==2:
            self.light_flicker_speed=max(1,min(15,self.light_flicker_speed+direction))

    # ── Clics ─────────────────────────────────────────────────────────────
    def handle_click(self, mouse_pos):
        if self._text_mode: return
        wx=int(mouse_pos[0]+self.camera.offset_x)
        wy=int(mouse_pos[1]+self.camera.offset_y)
        if   self.mode==0: self._click_rect(wx,wy,"platform")
        elif self.mode==1: self._click_mob(wx,wy)
        elif self.mode==2: self._click_light(wx,wy)
        elif self.mode==3:
            self.spawn_x,self.spawn_y=wx,wy
            self.player.spawn_x,self.player.spawn_y=wx,wy
        elif self.mode==4: self._click_rect(wx,wy,"portal")
        elif self.mode==5: self._click_rect(wx,wy,"wall")
        elif self.mode==6: self._click_hitbox(wx,wy)
        elif self.mode==7: self._click_rect(wx,wy,"hole")
        elif self.mode==8:
            if self._has_clipboard: self._do_paste(wx,wy)
            else: self._click_rect(wx,wy,"copy_select")

    def _click_rect(self, wx, wy, kind):
        if self.first_point is None:
            self.first_point=(wx,wy)
        else:
            x1,y1=self.first_point; x,y=min(x1,wx),min(y1,wy)
            w,h=abs(wx-x1),abs(wy-y1); self.first_point=None
            if w<5 or h<5: return
            self._snapshot()
            if   kind=="platform": self.platforms.append(Platform(x,y,w,h,BLANC))
            elif kind=="wall":     self.custom_walls.append(Wall(x,y,w,h,visible=True))
            elif kind=="portal":
                self._pending_portal_rect=(x,y,w,h)
                maps=self._list_maps()
                self._ask_text("portal_name","Map cible :"+(f"  ({', '.join(maps)})" if maps else ""))
            elif kind=="hole":
                # Avant le premier trou : sauvegarde automatique d'un point de restauration
                if not self.has_holes:
                    name = self._save_restore_point()
                    self._show_msg(f"Point de restauration créé : {name}  |  Phase 2 active")
                self.apply_hole(pygame.Rect(x,y,w,h))
            elif kind=="copy_select":
                self._copy_rect=pygame.Rect(x,y,w,h)
                self._show_msg(f"Zone ({w}x{h}) — [C] copier")

    def _click_mob(self, wx, wy):
        if self.mob_patrol_mode: self._click_mob_patrol(wx,wy); return
        if self.mob_detect_mode: self._click_mob_detect(wx,wy); return
        hb=get_hitbox(self._current_sprite())
        test=pygame.Rect(wx,wy,hb["w"],hb["h"])
        for p in self.platforms:
            if test.colliderect(p.rect): print("X Ennemi dans plateforme"); return
        self._snapshot()
        self.enemies.append(Enemy(wx,wy,
            has_gravity=self.mob_gravity, has_collision=self.mob_collision,
            sprite_name=self._current_sprite(), can_jump=self.mob_can_jump,
            can_jump_patrol=self.mob_can_jump_patrol, detect_range=self.mob_detect_range,
            has_light=self.mob_has_light, patrol_left=wx-300, patrol_right=wx+300,
            can_fall_in_holes=self.mob_can_fall_in_holes,
            respawn_timeout=self.mob_respawn_timeout,
            jump_power=self.mob_jump_power))

    def _click_mob_patrol(self, wx, wy):
        if self._patrol_target is None:
            best,bd=None,9999999
            for e in self.enemies:
                d=(e.rect.centerx-wx)**2+(e.rect.centery-wy)**2
                if d<bd: bd=d; best=e
            if best and bd<100*100: self._patrol_target=best
            else: print("Aucun mob proche")
        elif self._patrol_first_x is None:
            self._patrol_first_x=wx
        else:
            l,r=min(self._patrol_first_x,wx),max(self._patrol_first_x,wx)
            if r-l>20: self._patrol_target.patrol_left=l; self._patrol_target.patrol_right=r
            self._patrol_target=None; self._patrol_first_x=None

    def _click_mob_detect(self, wx, wy):
        if self._detect_target is None:
            best,bd=None,9999999
            for e in self.enemies:
                d=(e.rect.centerx-wx)**2+(e.rect.centery-wy)**2
                if d<bd: bd=d; best=e
            if best and bd<100*100: self._detect_target=best
            else: print("Aucun mob proche")
        else:
            self._detect_target.direction=-1 if wx<self._detect_target.rect.centerx else 1
            self._detect_target=None

    def _click_light(self, wx, wy):
        if self.light_first_point is None:
            self.light_first_point=(wx,wy)
        else:
            cx,cy=self.light_first_point
            r=int(((wx-cx)**2+(wy-cy)**2)**0.5)
            if r>5:
                self._snapshot()
                self.lighting.add_light(cx,cy,radius=r,type=LIGHT_TYPES[self.light_type_index],
                    flicker=self.light_flicker,flicker_speed=self.light_flicker_speed)
            self.light_first_point=None

    def _do_copy(self):
        if self._copy_rect is None: self._show_msg("Sélectionne d'abord une zone"); return
        r=self._copy_rect
        self._clipboard_platforms=[pygame.Rect(p.rect.x-r.x,p.rect.y-r.y,p.rect.w,p.rect.h)
                                    for p in self.platforms if r.colliderect(p.rect)]
        self._clipboard_walls    =[pygame.Rect(w.rect.x-r.x,w.rect.y-r.y,w.rect.w,w.rect.h)
                                    for w in self.custom_walls if r.colliderect(w.rect)]
        self._has_clipboard=True
        self._show_msg(f"Copié {len(self._clipboard_platforms)} plt, {len(self._clipboard_walls)} murs")

    def _do_paste(self, wx, wy):
        if not self._has_clipboard: return
        self._snapshot()
        for rel in self._clipboard_platforms:
            self.platforms.append(Platform(wx+rel.x,wy+rel.y,rel.w,rel.h,BLANC))
        for rel in self._clipboard_walls:
            self.custom_walls.append(Wall(wx+rel.x,wy+rel.y,rel.w,rel.h,visible=True))

    def _click_hitbox(self, wx, wy):
        if not self._enemy_sprites: return
        name=self._enemy_sprites[self._hb_sprite_index%len(self._enemy_sprites)]
        try:
            from entities.enemy import ENEMIES_DIR
            path=os.path.join(ENEMIES_DIR,name)
            if not os.path.exists(path): path=find_file(name)
            img=pygame.image.load(path)
        except Exception: return
        scale=4; sw_i=img.get_width()*scale; sh_i=img.get_height()*scale
        screen=pygame.display.get_surface()
        sx=(screen.get_width()-sw_i)//2; sy=120
        mx=int(wx-self.camera.offset_x); my=int(wy-self.camera.offset_y)
        if not(sx<=mx<=sx+sw_i and sy<=my<=sy+sh_i): return
        rx=(mx-sx)//scale; ry=(my-sy)//scale
        if self._hb_first_point is None:
            self._hb_first_point=(rx,ry)
        else:
            x1,y1=self._hb_first_point; x,y=min(x1,rx),min(y1,ry)
            w,h=abs(rx-x1),abs(ry-y1); self._hb_first_point=None
            if w>1 and h>1: set_hitbox(name,w,h,x,y)

    def handle_right_click(self, mouse_pos):
        if self._text_mode: return
        wx=int(mouse_pos[0]+self.camera.offset_x)
        wy=int(mouse_pos[1]+self.camera.offset_y)
        pt=pygame.Rect(wx,wy,1,1); self._snapshot()
        if   self.mode==0: self.platforms[:]   =[p for p in self.platforms    if not p.rect.colliderect(pt)]
        elif self.mode==1: self.enemies[:]     =[e for e in self.enemies      if not e.rect.colliderect(pt)]
        elif self.mode==2:
            self.lighting.lights[:]=[l for l in self.lighting.lights
                if not(abs(l["x"]-wx)<l["radius"] and abs(l["y"]-wy)<l["radius"])]
        elif self.mode==4: self.portals[:]     =[p for p in self.portals      if not p.rect.colliderect(pt)]
        elif self.mode==5: self.custom_walls[:]=[w for w in self.custom_walls if not w.rect.colliderect(pt)]
        elif self.mode==8: self._copy_rect=None; self._has_clipboard=False; self.first_point=None

    # ── Preview ───────────────────────────────────────────────────────────
    def draw_preview(self, surf, mouse_pos):
        if self.mode in(0,4,5,7,8):
            colors={0:(100,200,255),4:(0,120,255),5:(180,180,180),7:(255,80,80),8:(255,200,0)}
            if self.first_point:
                wx=int(mouse_pos[0]+self.camera.offset_x); wy=int(mouse_pos[1]+self.camera.offset_y)
                x=min(self.first_point[0],wx)-int(self.camera.offset_x)
                y=min(self.first_point[1],wy)-int(self.camera.offset_y)
                pygame.draw.rect(surf,colors.get(self.mode,(255,255,255)),
                    (x,y,abs(wx-self.first_point[0]),abs(wy-self.first_point[1])),2)
        elif self.mode==2:
            if self.light_first_point is None: pygame.draw.circle(surf,(255,200,0),mouse_pos,5)
            else:
                cx=int(self.light_first_point[0]-self.camera.offset_x)
                cy=int(self.light_first_point[1]-self.camera.offset_y)
                r=int(((mouse_pos[0]-cx)**2+(mouse_pos[1]-cy)**2)**0.5)
                pygame.draw.circle(surf,(255,200,0),(cx,cy),r,2)
                pygame.draw.circle(surf,(255,200,0),(cx,cy),5)
        elif self.mode==3: pygame.draw.circle(surf,(0,150,255),mouse_pos,8,2)
        elif self.mode==1 and self.mob_patrol_mode:
            if self._patrol_target:
                pygame.draw.rect(surf,(255,200,0),self.camera.apply(self._patrol_target.rect),3)
            if self._patrol_first_x is not None:
                lx=int(self._patrol_first_x-self.camera.offset_x); h=surf.get_height()
                pygame.draw.line(surf,(0,200,0),(lx,0),(lx,h),2)
                pygame.draw.line(surf,(0,200,0),(lx,mouse_pos[1]),(mouse_pos[0],mouse_pos[1]),1)
                pygame.draw.line(surf,(0,200,0),(mouse_pos[0],0),(mouse_pos[0],h),1)
        elif self.mode==1 and self.mob_detect_mode:
            if self._detect_target:
                pygame.draw.rect(surf,(255,100,0),self.camera.apply(self._detect_target.rect),3)
                dr=self.camera.apply(self._detect_target._detect_rect())
                pygame.draw.rect(surf,(255,255,0),dr,2)
                font=self._get_font()
                surf.blit(font.render(
                    f"Portee:{self._detect_target.detect_range} Dir:{'D' if self._detect_target.direction>0 else 'G'} Jump:{self._detect_target.jump_power}",
                    True,(255,255,0)),(dr.x,dr.y-18))
        elif self.mode==6: self._draw_hitbox_editor(surf,mouse_pos)
        if self.mode==8:   self._draw_copy_paste_preview(surf,mouse_pos)

    def _draw_hitbox_editor(self, surf, mouse_pos):
        font=self._get_font()
        if not self._enemy_sprites: return
        name=self._enemy_sprites[self._hb_sprite_index%len(self._enemy_sprites)]
        try:
            from entities.enemy import ENEMIES_DIR
            path=os.path.join(ENEMIES_DIR,name)
            if not os.path.exists(path): path=find_file(name)
            img=pygame.image.load(path)
        except Exception:
            surf.blit(font.render(f"Sprite introuvable:{name}",True,(255,0,0)),(10,130)); return
        scale=4; sw_i=img.get_width()*scale; sh_i=img.get_height()*scale
        sx=(surf.get_width()-sw_i)//2; sy=120
        bg_r=pygame.Rect(sx-10,sy-10,sw_i+20,sh_i+20)
        pygame.draw.rect(surf,(20,10,30),bg_r); pygame.draw.rect(surf,(100,100,100),bg_r,1)
        surf.blit(pygame.transform.scale(img,(sw_i,sh_i)),(sx,sy))
        hb=get_hitbox(name)
        pygame.draw.rect(surf,(0,255,0),
            pygame.Rect(sx+hb["ox"]*scale,sy+hb["oy"]*scale,hb["w"]*scale,hb["h"]*scale),2)
        surf.blit(font.render(f"Actuel:{hb['w']}x{hb['h']} off({hb['ox']},{hb['oy']})",
            True,(0,255,0)),(sx,sy+sh_i+8))
        if self._hb_first_point:
            p1sx=sx+self._hb_first_point[0]*scale; p1sy=sy+self._hb_first_point[1]*scale
            mx,my=mouse_pos
            if sx<=mx<=sx+sw_i and sy<=my<=sy+sh_i:
                rx,ry=min(p1sx,mx),min(p1sy,my); rw,rh=abs(mx-p1sx),abs(my-p1sy)
                pygame.draw.rect(surf,(255,0,0),(rx,ry,rw,rh),2)
                surf.blit(font.render(f"{rw//scale}x{rh//scale}",True,(255,0,0)),(rx+rw+5,ry+rh+2))
        surf.blit(font.render(f"[T]:{name}  Clic=hitbox",True,(200,200,200)),(sx,sy+sh_i+28))

    def _draw_copy_paste_preview(self, surf, mouse_pos):
        font=self._get_font()
        if self._copy_rect:
            sr=pygame.Rect(self._copy_rect.x-int(self.camera.offset_x),
                           self._copy_rect.y-int(self.camera.offset_y),
                           self._copy_rect.w,self._copy_rect.h)
            pygame.draw.rect(surf,(255,200,0),sr,2)
            surf.blit(font.render("COPIE",True,(255,200,0)),(sr.x,sr.y-18))
        if self._has_clipboard:
            wx=int(mouse_pos[0]+self.camera.offset_x); wy=int(mouse_pos[1]+self.camera.offset_y)
            for rel in self._clipboard_platforms:
                pygame.draw.rect(surf,(100,200,255),
                    pygame.Rect(wx+rel.x-int(self.camera.offset_x),wy+rel.y-int(self.camera.offset_y),rel.w,rel.h),1)
            for rel in self._clipboard_walls:
                pygame.draw.rect(surf,(180,180,180),
                    pygame.Rect(wx+rel.x-int(self.camera.offset_x),wy+rel.y-int(self.camera.offset_y),rel.w,rel.h),1)

    def draw_overlays(self, surf):
        font=self._get_font()
        sx=int(self.spawn_x-self.camera.offset_x); sy=int(self.spawn_y-self.camera.offset_y)
        pygame.draw.circle(surf,(0,150,255),(sx,sy),8,2)
        surf.blit(font.render("SPAWN",True,(0,150,255)),(sx-font.size("SPAWN")[0]//2,sy-22))
        for portal in self.portals: portal.draw(surf,self.camera,font)

    # ── HUD ───────────────────────────────────────────────────────────────
    def draw_hud(self, surf, dt=0.016):
        font=self._get_font(); small=self._font_small; w=surf.get_width(); sh=surf.get_height()

        if self._hud_msg_timer > 0:
            self._hud_msg_timer = max(0.0, self._hud_msg_timer - dt)
        if self._restore_confirm_timer > 0:
            self._restore_confirm_timer = max(0.0, self._restore_confirm_timer - dt)
            if self._restore_confirm_timer <= 0 and self._restore_confirm:
                self._restore_confirm = False
                self._show_msg("Restauration annulée (délai expiré)")

        if self._text_mode: self._draw_text_box(surf); return

        panel=pygame.Surface((w,90),pygame.SRCALPHA); panel.fill((0,0,0,180)); surf.blit(panel,(0,0))

        phase_color=(255,120,40) if self.has_holes else (0,255,120)
        phase_label="PHASE 2 — trous" if self.has_holes else "PHASE 1 — structure"
        surf.blit(font.render(
            f"EDITEUR [{self.mode+1}/9] {self._mode_names[self.mode]}"
            f"{'  [Hitbox]' if self.show_hitboxes else ''}  |  {phase_label}",
            True,phase_color),(10,6))

        info=f"Sol:{settings.GROUND_Y} Plaf:{settings.CEILING_Y} Scene:{settings.SCENE_WIDTH} Cam:{self.camera.y_offset}"
        surf.blit(small.render(info,True,(255,255,0)),(w-small.size(info)[0]-10,6))

        y2=28
        if self.mode==0:
            surf.blit(font.render("Clic G x2=rect | Clic D=suppr | [Ctrl+Z]=annuler",True,(200,200,255)),(10,y2))
        elif self.mode==1:
            gc =(0,255,0) if self.mob_gravity          else (255,80,80)
            cc =(0,255,0) if self.mob_collision         else (255,80,80)
            jc =(0,255,0) if self.mob_can_jump          else (255,80,80)
            vpc=(0,255,0) if self.mob_can_jump_patrol   else (255,80,80)
            lc =(0,255,0) if self.mob_has_light         else (255,80,80)
            oc =(0,255,0) if self.mob_can_fall_in_holes else (255,80,80)
            rt =f"{self.mob_respawn_timeout:.0f}s" if self.mob_respawn_timeout>0 else "OFF"
            surf.blit(font.render(f"[G]:{self.mob_gravity}",              True,gc), (10,y2))
            surf.blit(font.render(f"[C]:{self.mob_collision}",            True,cc), (120,y2))
            surf.blit(font.render(f"[J]:{self.mob_can_jump}",             True,jc), (240,y2))
            surf.blit(font.render(f"[V]patr:{self.mob_can_jump_patrol}",  True,vpc),(360,y2))
            surf.blit(font.render(f"[I]:{self.mob_has_light}",            True,lc), (530,y2))
            surf.blit(font.render(f"[O]Trou:{self.mob_can_fall_in_holes}",True,oc), (650,y2))
            surf.blit(small.render(
                f"[T]:{self._current_sprite()}  Det:{self.mob_detect_range}  "
                f"[*/÷]Resp:{rt}  [PgUp/Dn]Jump:{self.mob_jump_power}",
                True,(200,200,255)),(10,50))
            if self.mob_patrol_mode:
                ptxt=("[P] ON: clic sur mob" if self._patrol_target is None else
                      "[P] clic=limite G" if self._patrol_first_x is None else
                      f"[P] clic=limite D (G={self._patrol_first_x})")
                surf.blit(small.render(ptxt,True,(255,200,0)),(500,50))
            elif self.mob_detect_mode:
                dtxt=("[D] ON: clic sur mob" if self._detect_target is None
                      else f"[D] portee={self._detect_target.detect_range} [+/-]  jump={self._detect_target.jump_power} [PgUp/Dn]")
                surf.blit(small.render(dtxt,True,(255,150,0)),(500,50))
            else:
                surf.blit(small.render("[P]atrouille [D]etection",True,(140,140,140)),(500,50))
        elif self.mode==2:
            fc=(0,255,0) if self.light_flicker else (255,80,80)
            surf.blit(font.render(
                f"[T]{LIGHT_TYPES[self.light_type_index]} [F]{'ON' if self.light_flicker else 'OFF'} Spd:{self.light_flicker_speed}",
                True,(255,200,100)),(10,y2))
        elif self.mode==3:
            surf.blit(font.render(f"Clic=spawn [R]espawn [B]ase ({self.spawn_x},{self.spawn_y})",
                True,(100,200,255)),(10,y2))
        elif self.mode==4:
            surf.blit(font.render(f"Clic G x2=portail | Clic D=suppr | {len(self.portals)}",
                True,(0,180,255)),(10,y2))
        elif self.mode==5:
            surf.blit(font.render(f"Clic G x2=mur | Clic D=suppr | {len(self.custom_walls)}",
                True,(180,180,180)),(10,y2))
        elif self.mode==6:
            name=self._enemy_sprites[self._hb_sprite_index%len(self._enemy_sprites)] if self._enemy_sprites else "?"
            hbd=get_hitbox(name)
            surf.blit(font.render(f"[T]:{name} | Clic x2=hitbox | {hbd['w']}x{hbd['h']}",
                True,(255,100,100)),(10,y2))
        elif self.mode==7:
            restores = self._list_restore_points()
            rinfo = f"dernier: {restores[-1]}" if restores else "aucun"
            surf.blit(font.render(
                f"Clic G x2=trou permanent | [Ctrl+Z]=annuler | {len(self.holes)} trou(s) | restore: {rinfo}",
                True,(255,80,80)),(10,y2))
        elif self.mode==8:
            if not self._has_clipboard:
                txt="[C]=copier | Clic D=effacer" if self._copy_rect else "Clic G x2=zone | [C]=copier"
                surf.blit(font.render(txt,True,(255,200,0)),(10,y2))
            else:
                nb=len(self._clipboard_platforms)+len(self._clipboard_walls)
                surf.blit(font.render(f"Clipboard:{nb} | Clic=coller | Clic D=effacer",True,(255,200,0)),(10,y2))

        surf.blit(small.render(
            "[M]ode [H]itbox [N]ew [S]ave [L]oad [R]espawn [Ctrl+Z]annuler [Ctrl+R]restaurer",
            True,(140,140,140)),(10,70))

        # Message temporaire en bas de l'écran
        if self._hud_msg and self._hud_msg_timer > 0:
            if self._restore_confirm:
                mc = (255,100,0)
            elif "restaur" in self._hud_msg or "Annulé" in self._hud_msg:
                mc = (255,200,0)
            elif "verrouillée" in self._hud_msg:
                mc = (255,80,80)
            else:
                mc = (180,255,180)
            msg_surf = small.render(self._hud_msg, True, mc)
            mw = msg_surf.get_width() + 20
            mh = msg_surf.get_height() + 10
            bg  = pygame.Surface((mw, mh), pygame.SRCALPHA)
            bg.fill((0,0,0,190))
            bx = (w - mw) // 2
            by = sh - 48
            surf.blit(bg,       (bx, by))
            surf.blit(msg_surf, (bx+10, by+5))

    def _draw_text_box(self, surf):
        font=self._get_font(); w,h=surf.get_size()
        overlay=pygame.Surface((w,h),pygame.SRCALPHA); overlay.fill((0,0,0,150)); surf.blit(overlay,(0,0))
        bw,bh=540,130; bx,by=(w-bw)//2,(h-bh)//2
        pygame.draw.rect(surf,(30,20,40),(bx,by,bw,bh))
        pygame.draw.rect(surf,(100,200,255),(bx,by,bw,bh),2)
        surf.blit(font.render(self._text_prompt,True,(200,200,255)),(bx+15,by+15))
        surf.blit(font.render(self._text_input+"_",True,(255,255,255)),(bx+15,by+52))
        surf.blit(font.render("[Entrée]=valider  [Échap]=annuler",True,(140,140,140)),(bx+15,by+90))

    # ── Save / Load ───────────────────────────────────────────────────────
    def _save_to(self, fp):
        data = self._build_save_data()
        with open(fp,"w") as f: json.dump(data,f,indent=2)

    def _build_save_data(self):
        return {
            "ground_y":settings.GROUND_Y,"ceiling_y":settings.CEILING_Y,
            "scene_width":settings.SCENE_WIDTH,"camera_y_offset":self.camera.y_offset,
            "spawn":{"x":self.spawn_x,"y":self.spawn_y},
            "bg_color":self.bg_color,"wall_color":self.wall_color,
            "platforms":  [{"x":p.rect.x,"y":p.rect.y,"w":p.rect.width,"h":p.rect.height} for p in self.platforms],
            "custom_walls":[{"x":w.rect.x,"y":w.rect.y,"w":w.rect.width,"h":w.rect.height} for w in self.custom_walls],
            "ground_segments":  [{"x":w.rect.x,"y":w.rect.y,"w":w.rect.width,"h":w.rect.height} for w in self.ground_segments],
            "ceiling_segments": [{"x":w.rect.x,"y":w.rect.y,"w":w.rect.width,"h":w.rect.height} for w in self.ceiling_segments],
            "left_segments":    [{"x":w.rect.x,"y":w.rect.y,"w":w.rect.width,"h":w.rect.height} for w in self.left_segments],
            "right_segments":   [{"x":w.rect.x,"y":w.rect.y,"w":w.rect.width,"h":w.rect.height} for w in self.right_segments],
            "holes":  [{"x":h.x,"y":h.y,"w":h.width,"h":h.height} for h in self.holes],
            "enemies":[e.to_dict() for e in self.enemies],
            "lights": [{"x":l["x"],"y":l["y"],"radius":l["radius"],"type":l["type"],
                        "flicker":l["flicker"],"flicker_speed":l["flicker_speed"]}
                       for l in self.lighting.lights if not l.get("_enemy_light")],
            "portals":[p.to_dict() for p in self.portals],
        }

    def save(self, name="map"):
        fp=os.path.join(MAPS_DIR,f"{name}.json")
        self._save_to(fp)
        self._show_msg(f"Sauvegardé : {name}.json")

    def load(self, name="map"):
        fp=os.path.join(MAPS_DIR,f"{name}.json")
        try:
            with open(fp) as f: data=json.load(f)
            self._snapshot(); self._apply_state(data)
            self._show_msg(f"Chargé : {name}.json")
        except FileNotFoundError: self._show_msg(f"{name}.json introuvable")

    def _apply_state(self, data):
        if "ground_y"    in data: settings.GROUND_Y   =data["ground_y"]
        if "ceiling_y"   in data: settings.CEILING_Y  =data["ceiling_y"]
        if "scene_width" in data:
            settings.SCENE_WIDTH=data["scene_width"]; self.camera.scene_width=data["scene_width"]
        if "camera_y_offset" in data: self.camera.y_offset=data["camera_y_offset"]
        if "spawn" in data:
            self.spawn_x=data["spawn"]["x"]; self.spawn_y=data["spawn"]["y"]
            self.player.spawn_x=self.spawn_x; self.player.spawn_y=self.spawn_y
        if "bg_color"   in data: self.bg_color  =data["bg_color"]
        if "wall_color" in data: self.wall_color=data["wall_color"]

        self.platforms.clear()
        for p in data.get("platforms",[]):
            self.platforms.append(Platform(p["x"],p["y"],p["w"],p["h"],BLANC))
        self.custom_walls.clear()
        for w in data.get("custom_walls",[]):
            self.custom_walls.append(Wall(w["x"],w["y"],w["w"],w["h"],visible=True))

        def _segs(key, is_border=False):
            return [Wall(s["x"],s["y"],s["w"],s["h"],visible=True,is_border=is_border)
                    for s in data.get(key,[])]
        if "ground_segments" in data:
            self.ground_segments  =_segs("ground_segments",  is_border=True)
            self.ceiling_segments =_segs("ceiling_segments", is_border=True)
            self.left_segments    =_segs("left_segments",    is_border=True)
            self.right_segments   =_segs("right_segments",   is_border=True)
        else:
            self.build_border_segments()

        self.holes=[pygame.Rect(h["x"],h["y"],h["w"],h["h"]) for h in data.get("holes",[])]

        self.enemies.clear()
        for e in data.get("enemies",[]):
            self.enemies.append(Enemy(e["x"],e["y"],
                has_gravity=e.get("has_gravity",True),has_collision=e.get("has_collision",True),
                sprite_name=e.get("sprite_name","monstre_perdu.png"),
                can_jump=e.get("can_jump",False),can_jump_patrol=e.get("can_jump_patrol",False),
                jump_power=e.get("jump_power",400),
                detect_range=e.get("detect_range",200),detect_height=e.get("detect_height",80),
                has_light=e.get("has_light",False),light_type=e.get("light_type","dim"),
                light_radius=e.get("light_radius",100),
                patrol_left=e.get("patrol_left",-1),patrol_right=e.get("patrol_right",-1),
                can_fall_in_holes=e.get("can_fall_in_holes",False),
                respawn_timeout=e.get("respawn_timeout",10.0)))

        self.lighting.lights.clear()
        for l in data.get("lights",[]):
            self.lighting.add_light(l["x"],l["y"],radius=l["radius"],type=l["type"],
                flicker=l.get("flicker",False),flicker_speed=l.get("flicker_speed",5))
        self.portals.clear()
        for p in data.get("portals",[]):
            self.portals.append(Portal(p["x"],p["y"],p["w"],p["h"],
                p["target_map"],p.get("target_x",-1),p.get("target_y",-1)))

        self._restore_confirm       = False
        self._restore_confirm_timer = 0.0

    def load_map_for_portal(self, name):
        fp=os.path.join(MAPS_DIR,f"{name}.json")
        try:
            with open(fp) as f: data=json.load(f)
            self._apply_state(data); return True
        except FileNotFoundError: return False