# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Ennemi
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Contient la classe Enemy : un ennemi qui patrouille, détecte le joueur,
#  le poursuit, attaque, et éventuellement saute par-dessus des murs.
#
#  Un ennemi a 3 ÉTATS principaux (machine à états, voir [D22]) :
#
#     - PATROUILLE   : fait des allers-retours entre patrol_left et patrol_right
#     - POURSUITE    : fonce vers le joueur (self.chasing = True)
#     - RETOUR       : revient vers sa zone de patrouille (self.returning = True)
#
#  La transition entre ces états dépend de :
#     - la DÉTECTION (cône devant l'ennemi + ligne de vue)
#     - la MÉMOIRE   (continue à poursuivre 2.5 s après avoir perdu de vue)
#     - le RESPAWN   (téléportation au spawn si trop long hors zone)
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  core/game.py crée une liste d'ennemis : `self.ennemis = [Enemy(...), ...]`.
#  Chaque frame :
#       ennemi.update(dt, platforms, walls, player_rect, holes)
#       ennemi.draw(screen, camera, show_hitbox)
#
#  L'éditeur peut ajouter / supprimer des ennemis et configurer leurs
#  paramètres (vitesse, peut-il sauter, portée de détection, etc.).
#  world/editor.py utilise `enemy.to_dict()` pour sauvegarder.
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Le sprite d'un ennemi     → sprite_name (dossier assets/images/enemies)
#     - La vitesse de patrouille  → paramètre patrol_speed
#     - La portée de détection    → paramètre detect_range
#     - La zone de patrouille     → patrol_left / patrol_right
#     - Le fait de pouvoir sauter → can_jump + jump_power
#     - La gravité (vol)          → has_gravity=False
#     - L'IA elle-même            → méthode update() ci-dessous
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D4]  pygame.Rect       — hitbox et zones de détection
#     [D11] math.hypot        — non utilisé directement ici (voir compagnons)
#     [D22] Machine à états   — chasing / returning / patrouille
#     [D33] List comprehension — très utilisée dans _nearby, _has_line_of_sight
#     [D34] Lambda            — tri des frames d'animation
#
# ─────────────────────────────────────────────────────────────────────────────

import os
import random
import pygame

import settings
from settings import *   # noqa: F401,F403 (GRAVITY, GROUND_Y, etc.)
from entities.animation import Animation
from systems.hitbox_config import get_hitbox
from utils import *      # noqa: F401,F403 (find_file)


# ═════════════════════════════════════════════════════════════════════════════
#  Constantes du fichier
# ═════════════════════════════════════════════════════════════════════════════

# Dossier où on stocke les sprites d'ennemis.
# __file__ = chemin de ce fichier, donc os.path.dirname(os.path.dirname(...))
# remonte de deux niveaux (entities/ → ENTRE-DEUX/).
_BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENEMIES_DIR = os.path.join(_BASE_DIR, "assets", "images", "enemies")
os.makedirs(ENEMIES_DIR, exist_ok=True)        # crée le dossier s'il n'existe pas

# _CULL_DIST : distance max pour qu'un mur soit "intéressant" pour cet ennemi.
# On ne teste pas les murs situés à plus de 400 px → gain de perfo massif.
_CULL_DIST = 400

# _LOS_SKIP : la "ligne de vue" n'est recalculée qu'UNE FOIS TOUS LES 4 frames
# (pour économiser des calculs). 80 FPS / 4 = 20 checks/s, largement suffisant.
_LOS_SKIP  = 4

# Cache des polices debug (créées à la première utilisation).
_font_dbg_small = None
_font_dbg_tiny  = None


def _get_debug_fonts():
    """Renvoie les deux polices debug, en les créant à la 1re utilisation.

    Pourquoi `global` ? On veut MODIFIER les variables au niveau du module
    (pas créer des variables locales). `global` dit à Python "la variable
    du même nom existe au niveau global, utilise-la".
    """
    global _font_dbg_small, _font_dbg_tiny
    if _font_dbg_small is None:
        _font_dbg_small = pygame.font.SysFont("Consolas", 12)
        _font_dbg_tiny  = pygame.font.SysFont("Consolas", 11)
    return _font_dbg_small, _font_dbg_tiny


# ═════════════════════════════════════════════════════════════════════════════
#  Chargement des sprites
# ═════════════════════════════════════════════════════════════════════════════

def list_enemy_sprites():
    """Renvoie la liste des sprites disponibles dans assets/images/enemies/.

    Accepte :
      - un fichier .png / .jpg → sprite statique
      - un dossier contenant des .png / .jpg numérotés → sprite animé
    """
    sprites = []
    if not os.path.isdir(ENEMIES_DIR):
        return sprites

    for name in sorted(os.listdir(ENEMIES_DIR)):
        full = os.path.join(ENEMIES_DIR, name)

        if os.path.isdir(full):
            sprites.append(name)

        elif name.endswith((".png", ".jpg")):
            sprites.append(os.path.splitext(name)[0])

    return sprites

# ═════════════════════════════════════════════════════════════════════════════
#  Helpers géométriques (hors classe)
# ═════════════════════════════════════════════════════════════════════════════

def _nearby(walls, rect, margin=_CULL_DIST):
    """Filtre les murs proches du rectangle (culling = optimisation).

    Idée : au lieu de tester les collisions contre TOUS les murs du niveau,
    on ne garde que ceux proches de l'ennemi. Pour 500 murs sur un gros
    niveau, on passe souvent de 500 à ~10 → énorme gain de FPS.
    """
    cx, cy = rect.centerx, rect.centery
    proches = []
    for w in walls:
        # Certains "murs" sont des Rect bruts, d'autres des objets .rect.
        if hasattr(w, "rect"):
            wr = w.rect
        else:
            wr = w
        # On garde si le mur est à moins de `margin` px dans X ET Y.
        if abs(wr.centerx - cx) < margin and abs(wr.centery - cy) < margin:
            proches.append(w)
    return proches

# ═════════════════════════════════════════════════════════════════════════════
#  CLASSE Enemy
# ═════════════════════════════════════════════════════════════════════════════

class Enemy:
    """Un ennemi du jeu : patrouille, détecte, poursuit, attaque."""

    # ═════════════════════════════════════════════════════════════════════════
    # 1.  CONSTRUCTION
    # ═════════════════════════════════════════════════════════════════════════
    #
    # Beaucoup de paramètres ! Ils sont tous optionnels sauf x et y.
    # Chacun a une valeur par défaut adaptée à un ennemi "standard".

    def __init__(self, x, y, 
                 nb_frames=1,
                 sprite_name="mushroom",
                 scale_factor = 2,
                 max_vie = 3,
                 has_gravity=True,             # False = vole (fantôme, oiseau)
                 has_collision=True,
                 can_jump=False,               # peut-il sauter au-dessus des murs ?
                 jump_power=400,               # impulsion de saut (px/s)
                 detect_range=200,             # portée en X de détection (px)
                 detect_height=80,             # hauteur du cône (px)
                 has_light=False,              # porte-t-il une lanterne ?
                 light_type="dim",
                 light_radius=100,
                 patrol_left=-1,               # -1 = (spawn - 300)
                 patrol_right=-1,              # -1 = (spawn + 300)
                 can_jump_patrol=False,        # sauter aussi en patrouille (pas seulement en chasse)
                 can_fall_in_holes=False,      # False = fait demi-tour aux bords de trou
                 respawn_timeout=10.0,         # s avant téléportation si bloqué hors zone
                 can_turn_randomly=False,      # fait-il des demi-tours aléatoires ?
                 patrol_speed=120,             # vitesse en patrouille (px/s)
                 chase_speed=200):             # vitesse en poursuite (px/s)

        # ── Hitbox (lue depuis hitboxes.json, avec repli par défaut) ──
        hb = get_hitbox(sprite_name)
        self.hitbox_w  = hb["w"]
        self.hitbox_h  = hb["h"]
        self.hitbox_ox = hb["ox"]
        self.hitbox_oy = hb["oy"]
        self.rect = pygame.Rect(x, y, self.hitbox_w, self.hitbox_h)

        # ── Sprites / animation ──
        self.scale_factor = {
            "mushroom": 2,
            "flamur": 1,
            "monstre_perdu": 1
        }.get(sprite_name, scale_factor)

        frames = self._charger_frames(sprite_name, nb_frames)
        self.sprite_w = frames[0].get_width()
        self.sprite_h = frames[0].get_height()

        self.animations = {
            "idle": Animation(self._scale_frames(self._charger_frames(sprite_name + "idle", 7)), img_dur=10),
            "run": Animation(self._scale_frames(self._charger_frames(sprite_name + "run", 8)), img_dur=4),
            "walk": Animation(self._scale_frames(self._charger_frames(sprite_name + "run", 8)), img_dur=4),
            "atk": Animation(self._scale_frames(self._charger_frames(sprite_name + "atk", 10)), img_dur=4),
            "die": Animation(self._scale_frames(self._charger_frames(sprite_name + "die", 15)), img_dur=4, loop=False),
        }
        self.current_anim = "idle"
        self.sprite_name = sprite_name

        # ── Vitesses ──
        self.patrol_speed = patrol_speed
        self.chase_speed  = chase_speed
        self.vx = self.patrol_speed
        self.vy = 0
        self.direction    = 1          # 1 = regarde à droite, -1 à gauche
        self.knockback_vx = 0.0        # vitesse "poussée" quand on prend un coup

        # ── Spawn et zone de patrouille ──
        self.spawn_x = x
        self.spawn_y = y
        # Si patrol_left/right = -1, on utilise spawn ± 300 par défaut.
        self.patrol_left  = patrol_left  if patrol_left  >= 0 else x - 300
        self.patrol_right = patrol_right if patrol_right >= 0 else x + 300

        # ── États booléens ──
        self.on_ground         = False
        self.has_gravity       = has_gravity
        self.has_collision     = has_collision
        self.can_jump          = can_jump
        self.can_jump_patrol   = can_jump_patrol
        self.jump_power        = jump_power
        self.can_fall_in_holes = can_fall_in_holes
        self.can_turn_randomly = can_turn_randomly

        # ── Timers divers (tous décrémentés dans update()) ──
        # Demi-tour aléatoire : prochain test dans 3-6 s.
        self._random_turn_timer = random.uniform(3.0, 6.0)
        # Temps de retour avant téléportation.
        self._returning_timer   = 0.0
        self.respawn_timeout    = respawn_timeout
        # Après un demi-tour au bord d'un trou : on attend avant de re-tester.
        self._hole_cooldown     = 0.0
        # Cooldown général de demi-tour (évite les oscillations).
        self._turn_cooldown     = 0.0
        self._TURN_COOLDOWN_DUR = 0.8
        # Après un saut : on ne retente pas tout de suite.
        self._jump_lock         = 0.0
        self._JUMP_LOCK_DUR     = 0.6

        # ── Cache de la ligne de vue (recalculée tous les 4 frames) ──
        self._los_frame = 0
        self._los_cache = True

        # ── Lumière portée (lanterne) ──
        self.has_light    = has_light
        self.light_type   = light_type
        self.light_radius = light_radius

        # ── Détection ──
        self.detect_range    = detect_range
        self.detect_height   = detect_height
        self.atk_active = False
        self.attack_timer = 0.0
        self.chasing         = False
        self.returning       = False
        self.memory_timer    = 0.0
        self.MEMORY_DURATION = 2.5          # s de "mémoire" du joueur perdu
        self.last_known_dir  = 1
        self.attack_cooldown = 0.0

        # ──Santé ──
        self.alive             = True
        self.max_vie = max_vie
    
    # ═════════════════════════════════════════════════════════════════════════════
    #  Redimentionner
    # ═════════════════════════════════════════════════════════════════════════════

    def _scale_frames(self, frames):
        return [
            pygame.transform.smoothscale(
                f,
                (int(f.get_width() * self.scale_factor),
                int(f.get_height() * self.scale_factor))
            )
            for f in frames
        ]
    
    # ═════════════════════════════════════════════════════════════════════════
    # 2.  HELPERS GÉOMÉTRIQUES (détection, zones, ligne de vue)
    # ═════════════════════════════════════════════════════════════════════════

    def _detect_rect(self):
        """Renvoie le rectangle de détection devant l'ennemi.

        C'est un cône horizontal de `detect_range` pixels de long et
        `detect_height` pixels de haut, positionné du côté où regarde
        l'ennemi.
        """
        # Calage vertical : centré sur le centre de la hitbox.
        y = self.rect.y - (self.detect_height - self.hitbox_h) // 2

        if self.direction > 0:
            # Regarde à droite → zone à DROITE de la hitbox.
            return pygame.Rect(self.rect.right, y,
                               self.detect_range, self.detect_height)
        else:
            # Regarde à gauche → zone à GAUCHE.
            return pygame.Rect(self.rect.left - self.detect_range, y,
                               self.detect_range, self.detect_height)

    def _chase_rect(self):
        """Renvoie un grand rectangle autour de l'ennemi (zone de chasse).

        Une fois que l'ennemi a vu le joueur, il continue de le voir même
        s'il passe derrière lui : on élargit la détection dans tous les sens.
        """
        r = self.detect_range * 2
        return pygame.Rect(self.rect.centerx - r, self.rect.centery - r,
                           r * 2, r * 2)

    def _has_line_of_sight(self, player_rect, walls_near, platforms):
        """True si l'ennemi a une ligne de vue directe sur le joueur.

        Méthode : on discrétise le segment ennemi→joueur en 7 points et
        on teste si chaque point traverse un mur ou une plateforme.

        Pour économiser : on ne recalcule qu'UNE fois tous les _LOS_SKIP
        frames (4), et entre-temps on renvoie la valeur du cache.
        """
        self._los_frame += 1
        # Si on n'est PAS sur une frame de recalcul, renvoie le cache.
        if self._los_frame % _LOS_SKIP != 0:
            return self._los_cache

        # Point de départ (ennemi) et d'arrivée (joueur).
        ex, ey = self.rect.centerx, self.rect.centery
        px, py = player_rect.centerx, player_rect.centery

        vu = True
        # On teste 7 points intermédiaires : t = 1/8, 2/8, ... 7/8.
        for i in range(1, 8):
            t = i / 8
            # Interpolation linéaire entre ennemi et joueur. Voir [D13].
            px_i = int(ex + (px - ex) * t)
            py_i = int(ey + (py - ey) * t)
            point = pygame.Rect(px_i, py_i, 2, 2)

            # Test contre les murs proches.
            for w in walls_near:
                # On ignore les murs de bordure (le sol, le plafond, etc.)
                # sinon tout serait bloqué.
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

            # Test contre les plateformes "solides" (>10 px d'épaisseur).
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
        """True si l'ennemi est dans sa zone de patrouille."""
        eps = 5                                # tolérance de 5 px
        return (self.patrol_left - eps
                <= self.rect.centerx
                <= self.patrol_right + eps)

    def _can_reach_player_vertically(self, player_rect):
        """True si le joueur est accessible en sautant (sinon, inutile de chasser)."""
        if not self.can_jump:
            # Sans saut : on ne peut atteindre le joueur que s'il est presque
            # à la même hauteur que nous (± 3 × hitbox_h).
            return abs(player_rect.centery - self.rect.centery) < self.hitbox_h * 3

        # Hauteur max qu'on peut atteindre avec jump_power :
        #     h_max = v² / (2 × g)   (physique classique)
        max_jump_h = (self.jump_power ** 2) / (2 * GRAVITY)
        # Différence de hauteur (positif si joueur au-dessus de nous).
        dy = self.rect.bottom - player_rect.bottom
        return dy < max_jump_h + self.hitbox_h * 2

    def _has_ground_ahead(self, step, walls_near, holes):
        """True s'il y a du sol `step` pixels devant l'ennemi (sinon = trou)."""
        check_x = self.rect.centerx + step * self.direction
        check_y = self.rect.bottom

        # Trou explicite → pas de sol.
        if holes:
            probe = pygame.Rect(check_x - 2, check_y - 4, 4, 8)
            for h in holes:
                if probe.colliderect(h):
                    return False

        # Si on est proche du sol global (GROUND_Y), considère qu'il y a du sol.
        if abs(check_y - settings.GROUND_Y) < 20:
            return True

        # Sinon : on cherche un mur de bordure juste sous la position de test.
        probe = pygame.Rect(check_x - 2, check_y, 4, 8)
        for w in walls_near:
            if not getattr(w, "is_border", False):
                continue
            if hasattr(w, "rect"):
                wr = w.rect
            else:
                wr = w
            if probe.colliderect(wr):
                return True
        return False

    # ═════════════════════════════════════════════════════════════════════════
    # 3.  ACTIONS (demi-tour, saut, téléportation, dégâts)
    # ═════════════════════════════════════════════════════════════════════════

    def _do_turn(self):
        """Fait faire demi-tour à l'ennemi (respecte le cooldown)."""
        if self._turn_cooldown > 0:
            return
        self.direction *= -1                    # inverse la direction
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

    def hit_player(self, player_rect):
        """Appelé par systems/combat.py quand l'ennemi touche le joueur.

        Renvoie True si le coup a été porté, False s'il était en cooldown.
        """
        if self.attack_cooldown > 0:
            return False

        # Recul : on se pousse dans le sens opposé au joueur.
        if self.rect.centerx < player_rect.centerx:
            self.knockback_vx = -200
        else:
            self.knockback_vx = 200
        self.attack_cooldown = 0.8
        return True

    def on_wall_collision_horizontal(self, wall_height):
        """Appelé par game.py quand l'ennemi est bloqué horizontalement.

        Décision : sauter (si c'est un petit mur) ou faire demi-tour.
        """
        if self._jump_lock > 0:
            return

        # Peut-on sauter ? Oui si on a can_jump, qu'on est en chasse/retour
        # (ou configuré can_jump_patrol), qu'on est presque au sol, et
        # que le mur est sautable (≤ jump_power / 8).
        can_jp = self.chasing or self.returning or self.can_jump_patrol
        # "presque au sol" = au sol OU en train de tomber (pas en saut).
        nearly_grounded = self.on_ground or self.vy >= 0

        if (self.can_jump and nearly_grounded and can_jp
                and wall_height <= self.jump_power / 8):
            # Saut (pas bloqué par _turn_cooldown).
            self.vy         = -self.jump_power
            self.on_ground  = False
            self._jump_lock = self._JUMP_LOCK_DUR
        elif self._turn_cooldown <= 0:
            # Demi-tour (respecte le cooldown).
            self._do_turn()

    # ═════════════════════════════════════════════════════════════════════════
    # 4.  IA PRINCIPALE — update() : appelé chaque frame par game.py
    # ═════════════════════════════════════════════════════════════════════════
    #
    # Étapes :
    #     1. Décrémenter les timers
    #     2. Filtrer les murs proches (culling)
    #     3. Détection du joueur (chasing / returning)
    #     4. Si returning : retour vers la zone
    #     5. Calculer la vitesse horizontale
    #     6. Appliquer knockback
    #     7. Demi-tour aléatoire (si activé)
    #     8. Demi-tour au bord d'un trou (si can_fall_in_holes=False)
    #     9. Gravité
    #    10. Déplacement
    #    11. Sol / plafond / trou

    def _charger_frames(self, file, x, start=1):
        """Charge x frames PNG numérotées séquentiellement."""
        frames = []
        for i in range(start, x + 1):
            try:
                # .convert_alpha() = optimisation perf cruciale (cf. docstring)
                surf = pygame.image.load(find_file(f"{file}{i}.png")).convert_alpha()
                frames.append(surf)
            except FileNotFoundError:
                print(f"Frame manquante : {file}{i}.png")
                # Dès qu'une frame manque, on arrête (on garde celles qu'on a).
                break

        # Cas 1 : au moins une frame → on l'utilise.
        if frames:
            return frames

        # Cas 2 : aucune frame → fallback sur monstre_perdu.png
        try:
            return [pygame.image.load(find_file("monstre_perdu.png")).convert_alpha()]
        except FileNotFoundError:
            # Cas 3 : tout manque → carré vert
            placeholder = pygame.Surface((PLAYER_W, PLAYER_H))
            placeholder.fill((0, 255, 86))
            return [placeholder]

    def update(self, dt, platforms=None, walls=None, player_rect=None,
               holes=None):
        if not self.alive:
            self.vx = 0
            self.vy = 0
            self.knockback_vx = 0
            self.animations["die"].update()
            return
        
        if self.atk_active:
            self.attack_timer -= dt
            if self.attack_timer <= 0:
                self.atk_active = False

        # ── 1. Décrémentation des timers ──────────────────────────────────
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt
        if self._hole_cooldown > 0:
            self._hole_cooldown = max(0.0, self._hole_cooldown - dt)
        if self._jump_lock > 0:
            self._jump_lock = max(0.0, self._jump_lock - dt)
        if self._turn_cooldown > 0:
            self._turn_cooldown = max(0.0, self._turn_cooldown - dt)

        # ── 2. Murs proches (culling) ─────────────────────────────────────
        if walls:
            walls_near = _nearby(walls, self.rect)
        else:
            walls_near = []

        # ── 3. Détection du joueur ───────────────────────────────────────
        if player_rect:
            self._detecter_joueur(dt, player_rect, walls_near, platforms, holes)

        # ── 4. Retour vers la zone de patrouille ──────────────────────────
        if self.returning:
            if self._gerer_retour(dt):
                return   # téléporté → on arrête la frame

        # ── 5. Calcul de la vitesse horizontale ──────────────────────────
        self._calculer_vitesse(player_rect)

        # Total avec knockback (amorti)
        total_vx = self.vx + self.knockback_vx
        if abs(self.knockback_vx) > 1:
            self.knockback_vx *= 0.85
        else:
            self.knockback_vx = 0

        # ── 6. Demi-tour aléatoire (si activé) ────────────────────────────
        if (self.can_turn_randomly and self.on_ground
                and not self.chasing and not self.returning
                and self._jump_lock <= 0 and self._turn_cooldown <= 0):
            self._random_turn_timer -= dt
            if self._random_turn_timer <= 0:
                # 30% de chance de tourner à chaque fois qu'on arrive au bout du timer.
                if random.random() < 0.3:
                    self._do_turn()
                self._random_turn_timer = random.uniform(3.0, 6.0)

        # ── 7. Demi-tour au bord d'un trou ────────────────────────────────
        if (not self.can_fall_in_holes and self.on_ground
                and self._hole_cooldown <= 0 and self._turn_cooldown <= 0):
            # Distance de test devant l'ennemi (proportionnelle à la vitesse).
            step = max(int(abs(total_vx * dt)) + self.hitbox_w // 2, 24)
            if not self._has_ground_ahead(step, walls_near, holes):
                self._do_turn()
                # On recule un peu pour ne pas rester à cheval sur le bord.
                self.rect.x -= int(total_vx * dt) * 4
                self._hole_cooldown = 0.6
                total_vx = 0

        # ── 8. Gravité ────────────────────────────────────────────────────
        if self.has_gravity:
            self.vy += GRAVITY * dt

        # ── 9. Déplacement effectif ───────────────────────────────────────
        self.rect.x += int(total_vx * dt)
        self.rect.y += int(self.vy * dt)

        # ── 10. Collisions sol / plafond / trou ──────────────────────────
        self._gerer_collisions_verticales(holes)

        # changer d'animation
        if self.atk_active:
            self.current_anim = "atk"
        elif self.chasing:
            self.current_anim = "run"
        elif abs(self.vx) > 10:
            self.current_anim = "walk"
        else:
            self.current_anim = "idle"

    # ─── Sous-routines de update() ───────────────────────────────────────────

    def _detecter_joueur(self, dt, player_rect, walls_near, platforms, holes):
        """Met à jour chasing / returning selon la détection + mémoire."""
        # Zone à tester : plus large si déjà en chasse.
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

        # Si le joueur est dans un trou et qu'on ne peut pas tomber → on arrête.
        if in_zone and not self.can_fall_in_holes:
            if holes:
                # any() renvoie True si au moins un élément satisfait la condition.
                joueur_dans_trou = any(
                    player_rect.colliderect(h) for h in holes
                )
                if joueur_dans_trou:
                    in_zone = False
                    if self.chasing:
                        self.chasing          = False
                        self.returning        = True
                        self._returning_timer = 0.0

        # Si on est en chasse mais qu'on ne peut pas atteindre le joueur
        # verticalement, on abandonne.
        if in_zone and self.chasing:
            if not self._can_reach_player_vertically(player_rect):
                in_zone = False

        # Ligne de vue (intégrée au in_zone).
        can_see = in_zone and self._has_line_of_sight(
            player_rect, walls_near, platforms,
        )

        if can_see:
            # On voit le joueur → on chasse.
            self.chasing          = True
            self.returning        = False
            self._returning_timer = 0.0
            self._hole_cooldown   = 0.0
            self.memory_timer     = self.MEMORY_DURATION
            # Retenir de quel côté est le joueur.
            if player_rect.centerx < self.rect.centerx:
                self.last_known_dir = -1
            else:
                self.last_known_dir = 1
        else:
            # On ne voit pas le joueur.
            if self.memory_timer > 0:
                # On s'en souvient encore → on continue de chasser.
                self.memory_timer -= dt
            elif self.chasing:
                # Mémoire perdue → on revient à sa zone.
                self.chasing          = False
                self.returning        = True
                self._returning_timer = 0.0

    def _gerer_retour(self, dt):
        """Retour vers la zone de patrouille. Renvoie True si téléporté."""
        # Déjà dans la zone → on arrête de revenir.
        if self._is_in_patrol_zone():
            self.returning        = False
            self._returning_timer = 0.0
            return False

        # Timeout : trop longtemps bloqué → on téléporte au spawn.
        if self.respawn_timeout > 0:
            self._returning_timer += dt
            if self._returning_timer >= self.respawn_timeout:
                self._teleport_to_spawn()
                return True

        # Sinon, on marche vers le centre de la zone.
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
            # En chasse : on vise le joueur.
            dx = player_rect.centerx - self.rect.centerx
            if abs(dx) > 30:
                if dx < 0:
                    self.direction = -1
                else:
                    self.direction = 1
            self.vx = self.chase_speed * self.direction

        elif self.returning:
            self.vx = self.patrol_speed * self.direction

        else:
            # Patrouille normale : on inverse la direction aux bords de la zone.
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
        """Sol, plafond et expulsion des trous."""
        # Dans un trou ?
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

        # Expulsion des trous (si can_fall_in_holes=False).
        if not self.can_fall_in_holes and in_hole:
            self.rect.bottom = settings.GROUND_Y
            self.vy          = 0
            self.on_ground   = True
            if self._hole_cooldown <= 0:
                self._do_turn()
                self._hole_cooldown = 0.8

    # ═════════════════════════════════════════════════════════════════════════
    # 5.  RENDU
    # ═════════════════════════════════════════════════════════════════════════
    #
    # draw() dessine le sprite et — si show_hitbox est True — un tas
    # d'informations de debug : hitbox, zone de détection, zone de
    # patrouille, saut max possible, flèche de direction, etc.

    def draw(self, surf, camera, show_hitbox=False):
        if not self.alive:
            img = self.animations["die"].img()

            if self.direction < 0:
                img = pygame.transform.flip(img, True, False)
            if self.direction >= 0:
                sx = self.rect.x - self.hitbox_ox
                sy = self.rect.y - self.hitbox_oy
            else:
                sx = self.rect.x - (self.sprite_w - self.hitbox_ox - self.hitbox_w)
                sy = self.rect.y - self.hitbox_oy

            surf.blit(img, camera.apply(pygame.Rect(sx, sy, self.sprite_w, self.sprite_h)))
            return            
        
        # ── 1. Sprite ──
        
        #base
        img = self.animations[self.current_anim].img()
        self.animations[self.current_anim].update()

        # se retourner
        if self.direction < 0:
            img = pygame.transform.flip(img, True, False)

        # Position du sprite (le offset est miroir si on regarde à gauche).
        if self.direction >= 0:
            sx = self.rect.x - self.hitbox_ox
            sy = self.rect.y - self.hitbox_oy
        else:
            sx = self.rect.x - (self.sprite_w - self.hitbox_ox - self.hitbox_w)
            sy = self.rect.y - self.hitbox_oy
        surf.blit(img, camera.apply(pygame.Rect(
            sx, sy, self.sprite_w, self.sprite_h,
        )))

        if not show_hitbox:
            return

        # ── 2. Debug visuel (tout ce qui suit) ──
        self._dessiner_debug(surf, camera)

    def _dessiner_debug(self, surf, camera):
        """Affiche les infos de debug (hitbox, détection, patrouille, etc.)."""
        font_s, font_t = _get_debug_fonts()

        # Hitbox en rouge.
        pygame.draw.rect(surf, (255, 0, 0), camera.apply(self.rect), 1)

        # Zone de détection (jaune si pas en chasse, rouge si en chasse).
        if self.chasing:
            pygame.draw.rect(surf, (255, 80, 80),
                             camera.apply(self._chase_rect()), 1)
        else:
            pygame.draw.rect(surf, (255, 255, 0),
                             camera.apply(self._detect_rect()), 1)

        # Zone de patrouille (ligne verte avec petites barres aux extrémités).
        pl = int(self.patrol_left  - camera.offset_x)
        pr = int(self.patrol_right - camera.offset_x)
        py = int(self.rect.bottom  - camera.offset_y) + 5
        pygame.draw.line(surf, (0, 200, 0), (pl, py), (pr, py), 2)
        pygame.draw.line(surf, (0, 200, 0), (pl, py - 4), (pl, py + 4), 2)
        pygame.draw.line(surf, (0, 200, 0), (pr, py - 4), (pr, py + 4), 2)

        # Hauteur max sautable (cyan).
        if self.can_jump and self.jump_power > 0:
            mjh  = int((self.jump_power ** 2) / (2 * GRAVITY))
            jtop = int(self.rect.bottom - camera.offset_y) - mjh
            lx   = self.rect.x     - int(camera.offset_x) - 5
            rx   = self.rect.right - int(camera.offset_x) + 5
            mx2  = self.rect.centerx - int(camera.offset_x)
            fy2  = int(self.rect.bottom - camera.offset_y)
            pygame.draw.line(surf, (0, 220, 220), (lx, jtop), (rx, jtop), 1)
            pygame.draw.line(surf, (0, 220, 220), (mx2, fy2), (mx2, jtop), 1)
            surf.blit(font_t.render(f"{mjh}px", True, (0, 220, 220)),
                      (rx + 3, jtop - 5))

        # Flèche de direction (jaune).
        cx = self.rect.centerx - int(camera.offset_x)
        cy = self.rect.centery - int(camera.offset_y)
        ex = cx + 25 * self.direction
        pygame.draw.line(surf, (255, 255, 0), (cx, cy), (ex, cy), 2)
        pygame.draw.line(surf, (255, 255, 0), (ex, cy),
                         (ex - 6 * self.direction, cy - 5), 2)
        pygame.draw.line(surf, (255, 255, 0), (ex, cy),
                         (ex - 6 * self.direction, cy + 5), 2)

        # Indicateurs d'état (! = chasse, << = retour).
        if self.chasing:
            surf.blit(font_s.render("!", True, (255, 50, 50)),
                      (cx - 3, cy - 30))
        elif self.returning:
            if self.respawn_timeout > 0:
                rem = max(0.0, self.respawn_timeout - self._returning_timer)
                surf.blit(font_s.render(f"<< {rem:.0f}s", True, (100, 200, 100)),
                          (cx - 18, cy - 28))
            else:
                surf.blit(font_s.render("<<", True, (100, 200, 100)),
                          (cx - 8, cy - 28))

        # Barre de mémoire (orange) : restant de temps où on se souvient du joueur.
        if self.memory_timer > 0 and not self.chasing:
            ratio = self.memory_timer / self.MEMORY_DURATION
            bx = self.rect.x - int(camera.offset_x)
            by = self.rect.y - int(camera.offset_y) - 8
            pygame.draw.rect(surf, (255, 150, 0),
                             (bx, by, int(self.hitbox_w * ratio), 3))

        # Marqueurs en bas (triangles) pour les flags spéciaux.
        if self.can_fall_in_holes:
            fx = self.rect.centerx - int(camera.offset_x)
            fy = self.rect.bottom  - int(camera.offset_y) + 8
            pygame.draw.polygon(surf, (0, 220, 220),
                                [(fx, fy + 8), (fx - 6, fy), (fx + 6, fy)])

        if self.can_turn_randomly:
            fx = self.rect.centerx - int(camera.offset_x)
            fy = self.rect.bottom  - int(camera.offset_y) + 14
            pygame.draw.polygon(surf, (200, 100, 255),
                                [(fx, fy + 6), (fx - 5, fy), (fx + 5, fy)])

        # Barre de cooldown trou (orange).
        if self._hole_cooldown > 0:
            ratio = self._hole_cooldown / 0.8
            bx = self.rect.x - int(camera.offset_x)
            by = int(self.rect.bottom - camera.offset_y) + 3
            pygame.draw.rect(surf, (255, 120, 0),
                             (bx, by, int(self.hitbox_w * ratio), 2))

        # Vitesses affichées (texte bleu).
        spd_txt = f"p:{self.patrol_speed} c:{self.chase_speed}"
        surf.blit(font_t.render(spd_txt, True, (180, 180, 255)),
                  (cx - 20, cy - 44))

    # ═════════════════════════════════════════════════════════════════════════
    # 6.  SÉRIALISATION (sauvegarde dans map.json)
    # ═════════════════════════════════════════════════════════════════════════

    def get_light_pos(self):
        """Position où placer la lumière portée par cet ennemi."""
        return (self.rect.centerx, self.rect.centery)

    def to_dict(self):
        """Convertit l'ennemi en dict pour l'écriture dans map.json.

        Le dict a les mêmes clés que les paramètres de __init__ →
        l'éditeur peut recréer l'ennemi avec Enemy(**dict).
        """
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
            "can_turn_randomly": self.can_turn_randomly,
            "patrol_speed":      self.patrol_speed,
            "chase_speed":       self.chase_speed,
        }
