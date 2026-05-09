# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Éditeur de niveaux intégré au jeu
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Un éditeur de cartes qui tourne DANS le jeu (on appuie sur [E] en cours
#  de partie). Pas besoin d'un logiciel séparé : on construit le niveau là
#  où on est en train de jouer.
#
#  Avec lui on peut :
#     - poser des plateformes, des murs, des trous                (modes 0/5/7)
#     - placer des ennemis, des lumières, des portails            (modes 1/2/4)
#     - poser des décors libres et des blocs auto-tilés           (modes 9/11)
#     - placer des PNJ (personnages parlants) et écrire leurs dialogues (mode 10)
#     - régler la hitbox du joueur et des ennemis                 (mode 6)
#     - définir le spawn, copier/coller des zones                 (modes 3/8)
#     - annuler (Ctrl+Z) et restaurer une sauvegarde (Ctrl+R)
#
#  Le tout est sauvegardé dans des fichiers texte au format JSON
#  (`maps/*.json`), donc on peut même éditer une map à la main si besoin.
#
#  EXEMPLE CONCRET (ce que ça donne à l'écran)
#  -------------------------------------------
#       1) Tu joues, tu appuies sur [E] → bandeau noir en haut de l'écran,
#          tu es en mode 0 (Plateforme).
#       2) Tu fais 2 clics gauches sur la map → une plateforme blanche
#          apparaît entre les 2 points.
#       3) Tu appuies sur [M] pour passer au mode 1 (Mob), tu cliques →
#          un ennemi est placé.
#       4) Tu appuies sur [S] → popup "Sauvegarder sous :" → tu tapes
#          "ma_map" → fichier `maps/ma_map.json` créé.
#       5) Plus tard tu rouvres l'éditeur, [L]oad, "ma_map" → tout est là.
#
#  PETIT LEXIQUE
#  -------------
#     - mode          = un "outil" actif. Comme dans Photoshop : pinceau,
#                       gomme, sélection... Ici : Plateforme, Mob, Lumière,
#                       Spawn, Portail, Mur, Hitbox, Trou, Copier/Coller,
#                       Décor, PNJ, Blocs (12 modes au total, voir mode 0..11).
#                       On change avec [M].
#
#     - hitbox        = "boîte de collision" d'un sprite. C'est le rectangle
#                       INVISIBLE qui sert aux collisions. Souvent plus
#                       petit que l'image (ex: une silhouette dans une grosse
#                       cape n'a pas de hitbox sur la cape).
#
#     - sprite        = une image (souvent un personnage ou un objet).
#                       Souvent un .png dans `assets/images/...`.
#
#     - JSON          = format texte universel pour stocker des données.
#                       Exemple : { "x": 100, "y": 200, "type": "plateforme" }.
#                       Lisible par un humain ET par n'importe quel langage.
#
#     - sérialisation = transformer un objet Python (Plateforme, Ennemi...)
#                       en quelque chose qu'on peut écrire dans un fichier
#                       (ici : un dict, puis du JSON). Le contraire =
#                       désérialisation (relire le fichier → recréer l'objet).
#
#     - segment       = un morceau de bordure du monde. Au début, le sol est
#                       UN gros segment qui va de gauche à droite. Quand on
#                       perce un trou dedans, ce segment est COUPÉ en
#                       deux morceaux (gauche et droite du trou).
#
#     - snapshot      = "photo" instantanée de l'état complet (toutes les
#                       plateformes, ennemis, etc.) à un moment donné. C'est
#                       ce qu'on empile pour Ctrl+Z.
#
#     - point de restauration = comme un snapshot, mais sauvé sur DISQUE
#                       (dans `maps/_restore/`). Crée automatiquement
#                       avant qu'on perce le 1er trou (action irréversible).
#                       Ctrl+R = revenir au dernier point de restauration.
#
#     - registre PNJ  = la liste des personnages réutilisables (nom + sprite).
#                       Stocké dans game_config.json. Permet de placer le
#                       même PNJ ("Marc", "Théa"...) sur plusieurs maps.
#
#     - auto-tiling   = sélection automatique de la BONNE tuile selon sa
#                       position : un coin met une image de coin, un bord
#                       met une image de bord, etc. Comme dans Tiled ou RPG
#                       Maker. Voir _get_auto_tile().
#
#     - machine à états = "selon la valeur de self.mode (0..11), le clic
#                       fait quelque chose de DIFFÉRENT". Le code est plein
#                       de `if self.mode == X: ...` pour ça.
#
#  PHASES DE CONSTRUCTION D'UNE CARTE
#  ----------------------------------
#  Phase 1 : on règle la taille (sol, plafond, largeur) avec ↑↓←→
#            + on pose plateformes, murs, ennemis, lumières, portails...
#            → tout est RÉVERSIBLE (Ctrl+Z empile l'historique).
#
#  Phase 2 : on perce des trous dans les bordures (mode 7 = Trou).
#            → ACTION IRRÉVERSIBLE pour la structure (la taille du monde
#              ne peut plus changer). Avant le 1er trou, un POINT DE
#              RESTAURATION est créé automatiquement. On peut y revenir
#              avec Ctrl+R (2 appuis en 5 s pour confirmer).
#
#  ANATOMIE DE L'ÉCRAN EN MODE ÉDITEUR
#  -----------------------------------
#       ┌──────────────────────────────────────────────────────────────┐
#       │ EDITEUR [1/12] Plateforme | PHASE 1   Sol:590 Plaf:0 ...    │ ← bandeau
#       │ Clic G x2=rect | Clic D=suppr | [Ctrl+Z]=annuler            │   d'info
#       │ [M]ode [H]itbox [N]ew [S]ave [L]oad ...                     │
#       ├──────────────────────────────────────────────────────────────┤
#       │                                                              │
#       │            (la map jouable normalement)                      │
#       │             plus l'aperçu sous le curseur                    │
#       │             plus le SPAWN bleu, les portails, etc.           │
#       │                                                              │
#       │              ┌─────────────────────────────┐                 │
#       │              │ Message éphémère ici (3 s)  │                 │
#       │              └─────────────────────────────┘                 │
#       └──────────────────────────────────────────────────────────────┘
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  core/game.py crée l'éditeur :
#       self.editor = Editor(platforms, enemies, camera, lighting, player)
#  et chaque frame :
#       if self.editor.active:
#           self.editor.draw_preview(screen, mouse_pos)
#           self.editor.draw_overlays(screen)
#           self.editor.draw_hud(screen, dt)
#  Les évènements clavier/souris sont aussi redirigés vers handle_key(),
#  handle_click(), handle_right_click(), handle_scroll(), handle_textinput().
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Ajouter un mode        → dans self._mode_names + self.mode
#                                  (et câbler dans handle_click / handle_key)
#     - Raccourci clavier      → dans handle_key()
#     - Apparence d'un preview → méthode _draw_*()
#     - Apparence du HUD       → méthode draw_hud()
#     - Format de sauvegarde   → _build_save_data() / _apply_state()
#     - Auto-tiling (thèmes)   → _get_auto_tile()
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D4]  pygame.Rect              — hitbox et zones cliquées
#     [D5]  pygame.Surface / SRCALPHA — panneaux HUD semi-transparents
#     [D12] JSON                     — sérialisation des cartes
#     [D22] Machine à états          — self.mode (0..11) change le comportement
#     [D33] List comprehension       — filtrages partout dans le fichier
#     [D34] Lambda                   — tri des sprites par numéro
#
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
import datetime
import pygame

import settings
from settings import *   # noqa: F401,F403  (BLANC, VIOLET, GROUND_Y, …)

from entities.enemy          import Enemy, list_enemy_sprites
from entities.npc            import PNJ, list_pnj_sprites, creer_sprite_invisible
from entities.marchand       import Marchand
from systems.hitbox_config   import (get_hitbox, set_hitbox,
                                      PLAYER_KEY,
                                      get_player_hitbox, set_player_hitbox)
from world.tilemap           import Platform, Wall, Decor
from world.triggers          import CutsceneTrigger, FearZoneTrigger, creer_depuis_dict
from world.tiled_importer    import importer_tiled
from world.cinematique_editor import CinematiqueEditor
from world.pnj_editor         import PNJEditor
from utils                   import find_file


# ═════════════════════════════════════════════════════════════════════════════
#  Constantes du fichier
# ═════════════════════════════════════════════════════════════════════════════

# Types de lumière proposés dans le mode "Lumière" (mode 2).
# Chaque type est un préréglage d'éclairage dans systems/lighting.py.
LIGHT_TYPES = ["player", "torch", "large", "cool", "dim", "background"]

# Dossiers : on réutilise les constantes centralisées dans settings.py
# (DECORS_DIR, MAPS_DIR). Avant, elles étaient recalculées ici ET dans
# world/tiled_importer.py avec des orthographes différentes ("decor" vs
# "decors") ce qui causait la disparition des décors au reload.
RESTORE_DIR = os.path.join(MAPS_DIR, "_restore")           # points de restauration
# Sprites du joueur (player_idle.png, etc.) pour le mode hitbox (mode 7).
_BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYER_DIR  = os.path.join(_BASE_DIR, "assets", "images", "joueur")

# Couleurs "nommées" acceptées par la commande [N] (nouvelle map).
# Le dictionnaire fait correspondre un nom en français à un tuple RGB.
_NAMED_COLORS = {
    "noir":   (0,   0,   0),   "blanc":  (255, 255, 255), "rouge":  (200,  50,  50),
    "vert":   (50,  180,  80), "bleu":   (30,   80, 200), "violet": ( 80,  40, 140),
    "cyan":   (40,  180, 200), "orange": (220, 130,  40), "rose":   (200,  80, 140),
    "gris":   (90,   90,  90), "jaune":  (220, 200,  50),
}


# ═════════════════════════════════════════════════════════════════════════════
#  Helpers de module (hors classe)
# ═════════════════════════════════════════════════════════════════════════════
def _parse_hex_color(s):
    """Parse une couleur hex Tiled "#rrggbb" ou "#aarrggbb" → tuple (r,g,b)."""
    if not s:
        return None
    s = s.strip().lstrip("#")
    try:
        if len(s) == 8:        # aarrggbb (format Tiled avec alpha)
            return (int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16))
        if len(s) == 6:        # rrggbb
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        pass
    return None
def _lister_decors():
    """Liste les décors disponibles dans `assets/images/decor/`.

    Retourne deux listes :
      - la liste des chemins relatifs utilisables (ex.  "buisson-1.png" ou
        "sol/herbe_1.png")
      - la liste des catégories (= sous-dossiers, sauf "blocs" et ceux
        commençant par "_")

    Les décors dans des sous-dossiers (catégorisés) sont listés EN PREMIER,
    puis ceux à la racine.
    """
    if not os.path.isdir(DECORS_DIR):
        return [], []

    # Fichiers directement à la racine (pas dans un sous-dossier).
    racine = sorted(
        f for f in os.listdir(DECORS_DIR)
        if f.endswith((".png", ".jpg"))
        and os.path.isfile(os.path.join(DECORS_DIR, f))
    )

    # Parcours des sous-dossiers (= catégories).
    categorises = []
    categories  = []
    for d in sorted(os.listdir(DECORS_DIR)):
        chemin = os.path.join(DECORS_DIR, d)
        # On ignore les dossiers techniques ("_restore", "blocs").
        if not os.path.isdir(chemin) or d.startswith("_") or d == "blocs":
            continue
        categories.append(d)
        for f in sorted(os.listdir(chemin)):
            if f.endswith((".png", ".jpg")):
                categorises.append(f"{d}/{f}")

    return categorises + racine, categories


def _lister_sprites_joueur():
    """Renvoie la liste des fichiers image du joueur (ex. player_idle.png).

    Utilisée par le mode 7 (édition de hitbox) pour cycler entre les
    différents sprites du joueur avec la touche [T].
    Si le dossier est introuvable ou vide, on revient sur player_idle.png.
    """
    if not os.path.isdir(PLAYER_DIR):
        return ["sheidle_001.png"]

    fichiers = [nom for nom in sorted(os.listdir(PLAYER_DIR))
                if nom.endswith((".png", ".jpg"))]
    return fichiers if fichiers else ["sheidle_001.png"]


def _parse_color(s):
    """Convertit une chaîne en tuple RGB (r, g, b).

    Accepte :
      - un nom : "rouge", "violet"…      (voir _NAMED_COLORS)
      - un hex : "#ff00aa"
      - des valeurs : "200,50,50"
      - autre     → None
    """
    s = s.strip().lower()
    if s in _NAMED_COLORS:
        return _NAMED_COLORS[s]

    # Format hexadécimal : "#rrggbb"
    if s.startswith("#") and len(s) == 7:
        try:
            return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16))
        except ValueError:
            return None

    # Format "r,g,b"
    parts = s.split(",")
    if len(parts) == 3:
        try:
            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            if all(0 <= v <= 255 for v in (r, g, b)):
                return (r, g, b)
        except ValueError:
            pass
    return None


# ═════════════════════════════════════════════════════════════════════════════
#  CLASSE Portal — zone cliquable qui téléporte vers une autre carte
# ═════════════════════════════════════════════════════════════════════════════

class Portal:
    """Un rectangle bleu cliquable → charge une autre carte JSON.

    Depuis v5, un portail peut être marqué `require_up=True` → il se
    comporte alors comme une PORTE : il faut appuyer sur Z (ou flèche ↑)
    pour "entrer". Sans appui, on peut rester dans la zone sans rien
    déclencher — pratique pour les portes de maison, où on ne veut pas
    être téléporté par accident en passant devant.
    """

    def __init__(self, x, y, w, h, target_map, target_x=-1, target_y=-1,
                 require_up=False):
        self.rect       = pygame.Rect(x, y, w, h)
        self.target_map = target_map
        # target_x / target_y = position d'arrivée dans la map cible.
        # -1 = le joueur atterrit au spawn défini dans la map cible.
        self.target_x   = target_x
        self.target_y   = target_y
        # Si True → portail "porte" : il faut appuyer sur HAUT pour entrer.
        self.require_up = bool(require_up)

    def to_dict(self):
        """Sérialisation pour JSON."""
        return {
            "x": self.rect.x,          "y": self.rect.y,
            "w": self.rect.width,      "h": self.rect.height,
            "target_map": self.target_map,
            "target_x":   self.target_x,
            "target_y":   self.target_y,
            "require_up": self.require_up,
        }

    def draw(self, surf, camera, font):
        """Affiche un rectangle semi-transparent + nom de la map cible.

        Couleur :
            bleu   (défaut)    → portail classique (téléport à l'entrée)
            orange (require_up) → PORTE (téléport sur appui ↑), repérable
                                   en un coup d'œil en mode éditeur.
        """
        sr = camera.apply(self.rect)
        if self.require_up:
            base_rgb = (220, 150, 70)   # orange doré = porte chaleureuse
        else:
            base_rgb = (0, 120, 255)    # bleu portail classique
        # Surface SRCALPHA : supporte la transparence (voir [D5]).
        s  = pygame.Surface((sr.w, sr.h), pygame.SRCALPHA)
        s.fill((*base_rgb, 60))
        surf.blit(s, sr)
        pygame.draw.rect(surf, base_rgb, sr, 2)
        # Libellé : préfixe [PORTE] si require_up, pour bien distinguer.
        prefixe = "[PORTE] " if self.require_up else ""
        surf.blit(font.render(f"{prefixe}-> {self.target_map}",
                              True, base_rgb),
                  (sr.x, sr.y - 18))


# ═════════════════════════════════════════════════════════════════════════════
#  CLASSE Editor — l'éditeur en jeu
# ═════════════════════════════════════════════════════════════════════════════

class Editor:
    """Éditeur de niveaux intégré (mode [E])."""

    # ═════════════════════════════════════════════════════════════════════════
    # 1.  CONSTRUCTION
    # ═════════════════════════════════════════════════════════════════════════

    def __init__(self, platforms, enemies, camera, lighting, player):
        # Les listes passées ici sont les MÊMES objets que ceux utilisés par
        # le jeu : on édite directement le niveau en cours.
        self.platforms    = platforms
        self.enemies      = enemies
        self.camera       = camera
        self.lighting     = lighting
        self.player       = player

        # ── État général ──
        self.active       = False        # éditeur ouvert ou fermé
        self.first_point  = None         # 1er clic des tracés à 2 clics
        self.portals      = []
        self.custom_walls = []

        # ── Bordures du monde et trous (Phase 2) ──
        # Segments = morceaux des 4 murs du monde (haut, bas, gauche, droite).
        # Quand on perce un trou, on DÉCOUPE les segments en sous-segments.
        self.ground_segments  = []
        self.ceiling_segments = []
        self.left_segments    = []
        self.right_segments   = []
        self.holes            = []

        # ── Historique pour Ctrl+Z ──
        self._history     = []
        self._max_history = 20

        # ── Message HUD éphémère ──
        self._hud_msg       = ""
        self._hud_msg_timer = 0.0

        # ── Confirmation Ctrl+R (2 appuis en 5 s) ──
        self._restore_confirm       = False
        self._restore_confirm_timer = 0.0

        # ── Décors ──
        self.decors             = []
        self.decor_collision    = False
        self.decor_sprite_index = 0
        self.decor_echelle      = 1.0     # taille du prochain décor
        self._decor_sprites, self._decor_categories = _lister_decors()
        self._decor_cat_index   = -1      # -1 = toutes, sinon index catégorie
        self._ECHELLES          = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0]

        # ── PNJs ──
        self.pnjs              = []
        self._pnj_sprites      = list_pnj_sprites()
        self._pnj_sprite_index = 0
        self._pnj_edit_target  = None          # PNJ en cours d'édition
        # Mode "objet parlant" : si défini (= tuple (largeur, hauteur)), le
        # prochain clic en mode 10 pose un PNJ invisible de cette taille.
        # Activé par la touche [X] qui demande la dimension à l'utilisateur.
        # Remis à None après le placement (1 clic = 1 objet).
        self._pnj_invisible_taille = None

        # Registre PNJ : personnages réutilisables (stockés dans game_config.json).
        self._pnj_registry  = []       # [{"nom": str, "sprite_name": str}, …]
        self._pnj_reg_index = -1       # -1 = nouveau, >=0 = index dans registre
        self._charger_registre_pnj()

        # ── Outil remplissage en mode décor ──
        self.decor_fill_mode = False   # [F] en mode décor

        # Dernier nom de carte sauvegardé / chargé.
        self._nom_carte = ""

        # ── Mode Blocs (auto-tiling) ──
        self.bloc_theme      = "bleu"  # "bleu" ou "vert"
        self.bloc_scale      = 1       # multiplicateur : 1=32px, 2=64px, …
        self._BLOC_ECHELLES  = [1, 2, 3, 4]
        self._bloc_base_size = 32      # taille de base d'un bloc (px)
        self._bloc_shape     = 0       # 0=plein 1=contour 2=ligne H 3=ligne V 4=terre
        self._BLOC_SHAPES    = ["Plein", "Contour", "Ligne H", "Ligne V", "Terre"]
        self._bloc_facing    = 0       # orientation (selon la forme)
        self._BLOC_FACINGS   = {
            0: ["—", "—"],                          # plein : pas de choix
            1: ["Extérieur", "Intérieur"],          # contour
            2: ["—", "—"],                          # ligne H : pas de choix
            3: ["Mur →", "Mur ←"],                  # ligne V : direction
            4: ["—", "—"],                          # terre : pas de choix
        }

        # ── Machine à états : le mode actif (voir [D22]) ──
        self.mode        = 0
        self._mode_names = [
            "Plateforme", "Mob", "Lumiere", "Spawn", "Portail",
            "Mur", "Hitbox", "Trou", "Copier/Coller", "Décor", "PNJ", "Blocs",
            "Trigger", "Danger", "Spawn nommé",
        ]
        # Dict {nom: [x, y]} des spawns nommés placés sur la carte. Utilisé
        # par les portails dont target_map vaut "carte spawn_nom" : à
        # l'arrivée, on cherche le spawn portant ce nom et on s'y téléporte.
        # Persisté dans le JSON de la map (cf. _build_save_data / _apply_state).
        self.named_spawns = {}

        # ── Copier/Coller ──
        self._copy_rect           = None
        self._clipboard_platforms = []
        self._clipboard_walls     = []
        self._has_clipboard       = False

        # ── Paramètres "lumière" ──
        self.light_type_index    = 1
        self.light_flicker       = False
        self.light_flicker_speed = 5
        self.light_first_point   = None

        # ── Paramètres "ennemi" par défaut ──
        self.mob_gravity           = True
        self.mob_collision         = True
        self.mob_can_jump          = False
        self.mob_can_jump_patrol   = False
        self.mob_detect_range      = 200
        self.mob_has_light         = False
        self.mob_sprite_index      = 0
        self.mob_can_fall_in_holes = False
        self.mob_can_turn_randomly = False
        self.mob_respawn_timeout   = 10.0
        self.mob_jump_power        = 400
        self._enemy_sprites        = []
        self._refresh_sprites()

        # Modes secondaires du mode 1 (ennemi) :
        #   - patrol : cliquer pour définir la zone de patrouille
        #   - detect : cliquer pour régler direction + portée d'un ennemi
        self.mob_patrol_mode = False
        self._patrol_target  = None
        self._patrol_first_x = None
        self.mob_detect_mode = False
        self._detect_target  = None

        # ── Paramètres "hitbox" ──
        self._hb_sprite_index = 0
        self._hb_first_point  = None

        # Afficher les hitbox en jeu.
        self.show_hitboxes = False

        # ── Saisie de texte (popup) ──
        self._text_input          = ""
        self._text_mode           = None
        self._text_prompt         = ""
        self._pending_portal_rect  = None
        # Si True, le prochain portail tracé sera une PORTE (require_up) :
        # téléportation uniquement sur appui ↑/Z, pas à l'entrée bête.
        # Basculé par [P] en mode 4. Reset à False après création.
        self._pending_portal_is_door = False
        self._pending_trigger_rect = None
        self._pending_trigger_nom  = ""
        # Si True, le prochain rect tracé en mode 12 deviendra une fear_zone
        # (et non une cutscene). Activé par la touche [F] en mode 12.
        # Remis à False après création (1 [F] = 1 fear_zone).
        self._pending_trigger_is_fear = False
        self._editing_trigger      = None   # zone en cours de rename ([R])
        self.trigger_zones         = []
        self.danger_zones           = []
        self._pending_danger_rect      = None 
        self._pending_danger_rect = None

        # Éditeur de cinématiques (overlay activé par [F2]).
        self.cine_editor = CinematiqueEditor()
        # Partage la caméra pour le picker [P] (cliquer dans le monde).
        self.cine_editor.camera = self.camera

        # Éditeur de PNJ (overlay activé par [F3] sur un PNJ proche).
        self.pnj_editor = PNJEditor()

        # ── Spawn et couleurs ──
        self.spawn_x    = self.player.spawn_x
        self.spawn_y    = self.player.spawn_y
        self.bg_color   = list(VIOLET)
        self.wall_color = [0, 0, 0]

        # ── Polices (créées à la demande) ──
        self._font       = None
        self._font_small = None

        # On s'assure que les dossiers existent.
        os.makedirs(MAPS_DIR,    exist_ok=True)
        os.makedirs(RESTORE_DIR, exist_ok=True)

    # ═════════════════════════════════════════════════════════════════════════
    # 2.  HELPERS (polices, sprites, registres)
    # ═════════════════════════════════════════════════════════════════════════

    def _get_font(self):
        """Crée les polices à la 1re utilisation (évite un coût inutile)."""
        if self._font is None:
            self._font       = pygame.font.SysFont("Consolas", 16)
            self._font_small = pygame.font.SysFont("Consolas", 13)
        return self._font

    def _refresh_sprites(self):
        """Rafraîchit la liste des sprites d'ennemis (utile si on en ajoute)."""
        self._enemy_sprites = list_enemy_sprites()
        if not self._enemy_sprites:
            self._enemy_sprites = ["monstre_perdu.png"]

    def _current_sprite(self):
        """Sprite d'ennemi actuellement sélectionné (cyclique)."""
        if not self._enemy_sprites:
            return "monstre_perdu.png"
        return self._enemy_sprites[self.mob_sprite_index % len(self._enemy_sprites)]

    def _hb_sprite_list(self):
        """Liste des sprites éditables en mode hitbox (mode 7).

        Format : liste de tuples (clé_hitbox, nom_fichier).
          1) D'abord TOUS les sprites du joueur : ils partagent une seule clé
             PLAYER_KEY dans hitboxes.json, donc la même hitbox, mais on
             permet de la prévisualiser sur n'importe quel sprite (touche T).
          2) Puis les sprites d'ennemis.
        """
        liste = []
        # 1) Sprites du joueur (cycle T).
        for sprite_joueur in _lister_sprites_joueur():
            liste.append((PLAYER_KEY, sprite_joueur))
        # 2) Sprites d'ennemis.
        for nom in self._enemy_sprites:
            liste.append((nom, nom))
        return liste

    def _hb_current(self):
        """Tuple (clé, nom_fichier) actuellement sélectionné en mode 7."""
        liste = self._hb_sprite_list()
        return liste[self._hb_sprite_index % len(liste)]

    @property
    def has_holes(self):
        """True si la map a au moins un trou (= Phase 2 active)."""
        return len(self.holes) > 0

    # ─── Registre PNJ (personnages réutilisables) ──────────────────────────

    def _charger_registre_pnj(self):
        """Lit le registre PNJ depuis game_config.json."""
        from systems.save_system import lire_config
        config = lire_config()
        self._pnj_registry = config.get("pnj_registry", [])

    def _sauver_registre_pnj(self):
        """Écrit le registre PNJ dans game_config.json."""
        from systems.save_system import lire_config, ecrire_config
        config = lire_config()
        config["pnj_registry"] = self._pnj_registry
        ecrire_config(config)

    def _ajouter_au_registre(self, nom, sprite_name):
        """Ajoute un personnage au registre (ou met à jour son sprite)."""
        for entry in self._pnj_registry:
            if entry["nom"] == nom:
                entry["sprite_name"] = sprite_name
                self._sauver_registre_pnj()
                return
        self._pnj_registry.append({"nom": nom, "sprite_name": sprite_name})
        self._sauver_registre_pnj()

    def _pnj_reg_courant(self):
        """Entrée du registre actuellement sélectionnée, ou None."""
        if self._pnj_reg_index < 0 or self._pnj_reg_index >= len(self._pnj_registry):
            return None
        return self._pnj_registry[self._pnj_reg_index]

    def _pnj_le_plus_proche(self, max_dist=120):
        """PNJ le plus proche du curseur (ou None)."""
        mx, my = pygame.mouse.get_pos()
        wx = int(mx + self.camera.offset_x)
        wy = int(my + self.camera.offset_y)
        best, bd = None, max_dist * max_dist
        for p in self.pnjs:
            d = (p.rect.centerx - wx) ** 2 + (p.rect.centery - wy) ** 2
            if d < bd:
                bd   = d
                best = p
        return best

    def _decor_le_plus_proche(self, max_dist=200):
        """Décor (objet) le plus proche du curseur (ou None).

        Sert au toggle save point en mode 9/11 : on appuie B et on prend
        le décor sous (ou très près de) la souris.
        """
        mx, my = pygame.mouse.get_pos()
        wx = int(mx + self.camera.offset_x)
        wy = int(my + self.camera.offset_y)
        best, bd = None, max_dist * max_dist
        for d in self.decors:
            cx = d.rect.centerx if hasattr(d, "rect") else d.x
            cy = d.rect.centery if hasattr(d, "rect") else d.y
            dist2 = (cx - wx) ** 2 + (cy - wy) ** 2
            if dist2 < bd:
                bd   = dist2
                best = d
        return best

    def _trigger_sous_curseur(self):
        """Renvoie la zone-déclencheur sous le curseur, ou None.

        Sert au mode 12 [R] pour identifier quelle zone on veut éditer."""
        mx, my = pygame.mouse.get_pos()
        wx = int(mx + self.camera.offset_x)
        wy = int(my + self.camera.offset_y)
        pt = pygame.Rect(wx, wy, 1, 1)
        for z in self.trigger_zones:
            if z.rect.colliderect(pt):
                return z
        return None

    def _decor_sprites_filtrés(self):
        """Liste des décors filtrée par la catégorie courante."""
        if self._decor_cat_index < 0 or not self._decor_categories:
            return self._decor_sprites
        cat = self._decor_categories[self._decor_cat_index]
        # List comprehension (voir [D33]).
        return [s for s in self._decor_sprites if s.startswith(f"{cat}/")]

    # ═════════════════════════════════════════════════════════════════════════
    # 3.  BORDURES DU MONDE ET TROUS (Phase 1 / Phase 2)
    # ═════════════════════════════════════════════════════════════════════════
    #
    # Le monde est délimité par 4 "murs" invisibles (sol, plafond, gauche,
    # droite). Chacun peut être découpé en sous-segments quand on perce un
    # trou, d'où les listes `*_segments`.

    def build_border_segments(self):
        """Reconstruit les 4 bordures à partir de GROUND_Y / CEILING_Y /
        SCENE_LEFT (bord gauche, peut être négatif) et SCENE_WIDTH (bord droit)."""
        gy = settings.GROUND_Y
        cy = settings.CEILING_Y
        sw = settings.SCENE_WIDTH       # X du bord droit
        sl = settings.SCENE_LEFT        # X du bord gauche
        largeur = sw - sl
        t  = 800                         # épaisseur de chaque bordure
        self.ground_segments  = [Wall(sl,     gy,      largeur, t, visible=True, is_border=True)]
        self.ceiling_segments = [Wall(sl,     cy - t,  largeur, t, visible=True, is_border=True)]
        self.left_segments    = [Wall(sl - t, cy - t,  t, gy - cy + t * 2, visible=True, is_border=True)]
        self.right_segments   = [Wall(sw,     cy - t,  t, gy - cy + t * 2, visible=True, is_border=True)]
        self.holes            = []

    def all_segments(self):
        """Tous les segments de bordure réunis."""
        return (self.ground_segments + self.ceiling_segments +
                self.left_segments   + self.right_segments)

    def _punch_hole_in_list(self, segments, hole, is_border=False):
        """Découpe un trou dans une liste de segments et renvoie la nouvelle liste.

        IDÉE GÉNÉRALE
        -------------
        Imagine le SOL comme un long rectangle. Quand on perce un trou
        rectangulaire DEDANS, le sol se retrouve coupé en plusieurs morceaux
        autour du trou. Cette fonction calcule ces morceaux pour CHAQUE
        segment qui touche le trou.

        SCHÉMA (un segment qui contient le trou) :

                 segment original
            ┌───────────────────────────────┐
            │                               │
            │       ┌─────────┐             │       Le trou est au milieu.
            │       │  TROU   │             │       Résultat : 4 morceaux
            │       │         │             │       autour de lui.
            │       └─────────┘             │
            │                               │
            └───────────────────────────────┘

                          devient

            ┌───────────────────────────────┐    ← morceau du HAUT
            └───────────────────────────────┘
            ┌──────┐             ┌──────────┐
            │ GCH  │             │  DROITE  │    ← morceaux à GAUCHE / DROITE
            └──────┘             └──────────┘       (sur la HAUTEUR du trou)
            ┌───────────────────────────────┐
            └───────────────────────────────┘    ← morceau du BAS

        Selon où tombe le trou, on génère 0 à 4 morceaux :
            - trou qui dépasse en haut → pas de morceau haut
            - trou plus large que le segment → ni gauche ni droite
            - trou qui sort complètement du segment → on garde le segment
              entier (filtré tout en haut par `if not colliderect`)
        """
        hx,  hy  = hole.x, hole.y
        hx2, hy2 = hx + hole.width, hy + hole.height
        result   = []
        for wall in segments:
            wr = wall.rect
            # Pas de chevauchement → on garde le segment tel quel.
            if not wr.colliderect(hole):
                result.append(wall)
                continue
            wx,  wy  = wr.x, wr.y
            wx2, wy2 = wx + wr.width, wy + wr.height
            # Morceau AU-DESSUS du trou.
            if hy  > wy:
                result.append(Wall(wx, wy,  wr.width, hy - wy,
                                   visible=True, is_border=is_border))
            # Morceau EN-DESSOUS du trou.
            if hy2 < wy2:
                result.append(Wall(wx, hy2, wr.width, wy2 - hy2,
                                   visible=True, is_border=is_border))
            # Morceaux À GAUCHE et À DROITE du trou (sur la hauteur du trou).
            top = max(wy, hy)
            bot = min(wy2, hy2)
            if bot > top:
                if hx  > wx:
                    result.append(Wall(wx,  top, hx  - wx,  bot - top,
                                       visible=True, is_border=is_border))
                if hx2 < wx2:
                    result.append(Wall(hx2, top, wx2 - hx2, bot - top,
                                       visible=True, is_border=is_border))
        return result

    def _punch_hole_in_custom_walls(self, hole):
        """Même logique que _punch_hole_in_list, mais pour self.custom_walls."""
        hx,  hy  = hole.x, hole.y
        hx2, hy2 = hx + hole.width, hy + hole.height
        to_remove = []
        new_walls = []
        for wall in self.custom_walls:
            wr = wall.rect
            if not wr.colliderect(hole):
                continue
            to_remove.append(wall)
            wx,  wy  = wr.x, wr.y
            wx2, wy2 = wx + wr.width, wy + wr.height
            if hy  > wy:  new_walls.append(Wall(wx, wy,  wr.width, hy - wy,   visible=True))
            if hy2 < wy2: new_walls.append(Wall(wx, hy2, wr.width, wy2 - hy2, visible=True))
            top = max(wy, hy); bot = min(wy2, hy2)
            if bot > top:
                if hx  > wx:  new_walls.append(Wall(wx,  top, hx  - wx,  bot - top, visible=True))
                if hx2 < wx2: new_walls.append(Wall(hx2, top, wx2 - hx2, bot - top, visible=True))
        for w in to_remove:
            self.custom_walls.remove(w)
        self.custom_walls.extend(new_walls)

    def apply_hole(self, hole_rect):
        """Perce un trou : découpe toutes les bordures + les murs custom."""
        self.ground_segments  = self._punch_hole_in_list(self.ground_segments,  hole_rect, is_border=True)
        self.ceiling_segments = self._punch_hole_in_list(self.ceiling_segments, hole_rect, is_border=True)
        self.left_segments    = self._punch_hole_in_list(self.left_segments,    hole_rect, is_border=True)
        self.right_segments   = self._punch_hole_in_list(self.right_segments,   hole_rect, is_border=True)
        self._punch_hole_in_custom_walls(hole_rect)
        self.holes.append(hole_rect)

    # ═════════════════════════════════════════════════════════════════════════
    # 4.  HISTORIQUE (Ctrl+Z) ET RESTAURATION (Ctrl+R)
    # ═════════════════════════════════════════════════════════════════════════

    def _snapshot(self):
        """Empile un instantané complet de la map dans l'historique (Ctrl+Z)."""
        state = {
            "ground_y":    settings.GROUND_Y,
            "ceiling_y":   settings.CEILING_Y,
            "scene_width": settings.SCENE_WIDTH,
            "scene_left":  settings.SCENE_LEFT,
            "spawn":       {"x": self.spawn_x, "y": self.spawn_y},
            # Spawns NOMMÉS (optionnels). Permet à un portail d'arriver à
            # un endroit précis via syntaxe "mapname spawnname".
            # Exemple : sortie de maison → portail.target_map = "village porte_maison"
            # → le joueur réapparaît à la position du spawn nommé "porte_maison"
            # défini dans village.json (au lieu du spawn par défaut).
            "named_spawns": dict(getattr(self, "named_spawns", {})),
            "bg_color":    list(self.bg_color),
            "platforms":   [{"x": p.rect.x, "y": p.rect.y,
                             "w": p.rect.width, "h": p.rect.height}
                            for p in self.platforms],
            "custom_walls": [{"x": w.rect.x, "y": w.rect.y,
                              "w": w.rect.width, "h": w.rect.height}
                             for w in self.custom_walls],
            "ground_segments":  [{"x": w.rect.x, "y": w.rect.y,
                                  "w": w.rect.width, "h": w.rect.height}
                                 for w in self.ground_segments],
            "ceiling_segments": [{"x": w.rect.x, "y": w.rect.y,
                                  "w": w.rect.width, "h": w.rect.height}
                                 for w in self.ceiling_segments],
            "left_segments":    [{"x": w.rect.x, "y": w.rect.y,
                                  "w": w.rect.width, "h": w.rect.height}
                                 for w in self.left_segments],
            "right_segments":   [{"x": w.rect.x, "y": w.rect.y,
                                  "w": w.rect.width, "h": w.rect.height}
                                 for w in self.right_segments],
            "holes":    [{"x": h.x, "y": h.y, "w": h.width, "h": h.height}
                         for h in self.holes],
            "enemies":  [e.to_dict() for e in self.enemies],
            "lights":   [{"x": l["x"], "y": l["y"],
                          "radius": l["radius"], "type": l["type"],
                          "flicker": l["flicker"],
                          "flicker_speed": l["flicker_speed"]}
                         for l in self.lighting.lights
                         if not l.get("_enemy_light")],
            "portals":       [p.to_dict() for p in self.portals],
            "decors":        [d.to_dict() for d in self.decors],
            "pnjs":          [p.to_dict() for p in self.pnjs],
            "trigger_zones": [z.to_dict() for z in self.trigger_zones],
        }
        self._history.append(state)
        # On limite la taille : si on dépasse, on retire le PLUS ancien.
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def _undo(self):
        """Restaure le dernier snapshot."""
        if not self._history:
            self._show_msg("Rien à annuler")
            return
        state = self._history.pop()
        self._apply_state(state)
        self._show_msg(f"Annulé — {len(self._history)} état(s) restant(s)")

    def _show_msg(self, msg, duration=3.0):
        """Affiche un message éphémère en bas du HUD."""
        self._hud_msg       = msg
        self._hud_msg_timer = duration

    def _list_restore_points(self):
        """Liste des points de restauration triés (noms sans .json)."""
        if not os.path.isdir(RESTORE_DIR):
            return []
        return sorted(f[:-5] for f in os.listdir(RESTORE_DIR)
                      if f.endswith(".json"))

    def _save_restore_point(self):
        """Crée un point de restauration daté (avant de percer le premier trou)."""
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"restore_{ts}"
        fp   = os.path.join(RESTORE_DIR, f"{name}.json")
        self._save_to(fp)
        return name

    def _load_restore_point(self, name):
        """Recharge un point de restauration (Ctrl+R)."""
        fp = os.path.join(RESTORE_DIR, f"{name}.json")
        try:
            with open(fp) as f:
                data = json.load(f)
            self._snapshot()                   # historique → on peut undo
            self._apply_state(data)
            if not self.ground_segments:
                self.build_border_segments()
            # Replacer le joueur au spawn restauré.
            self.player.respawn()
            self._show_msg(f"Restauré : {name}")
        except FileNotFoundError:
            self._show_msg(f"Fichier introuvable : {name}")

    # ═════════════════════════════════════════════════════════════════════════
    # 5.  ACTIVATION ET CHANGEMENT DE MODE
    # ═════════════════════════════════════════════════════════════════════════

    def toggle(self):
        """Ouvre/ferme l'éditeur (touche [E] dans game.py)."""
        self.active            = not self.active
        self.first_point       = None
        self.light_first_point = None
        self._text_mode        = None
        self._hb_first_point   = None

    def change_mode(self):
        """Passe au mode suivant (touche [M] en éditeur). Remet les états à zéro."""
        self.mode              = (self.mode + 1) % len(self._mode_names)
        self.first_point       = None
        self.light_first_point = None
        self._hb_first_point   = None
        self.mob_patrol_mode   = False
        self._patrol_target    = None
        self._patrol_first_x   = None
        self.mob_detect_mode   = False
        self._detect_target    = None
        self._copy_rect        = None
        # Si on passe dans un mode qui utilise des sprites, on rafraîchit.
        if self.mode in (1, 6):
            self._refresh_sprites()

    # ═════════════════════════════════════════════════════════════════════════
    # 6.  CLAVIER — handle_key()
    # ═════════════════════════════════════════════════════════════════════════
    #
    # Énorme dispatch de toutes les touches. Pour chaque touche pressée,
    # on regarde :
    #     1) Est-ce qu'une popup texte est ouverte ?     → on redirige vers _handle_text
    #     2) Est-ce un raccourci GLOBAL (Ctrl+Z, etc.) ? → on l'exécute partout
    #     3) Est-ce une touche d'un MODE spécifique ?    → ex: [G] en mode 1 (mob)
    #                                                       bascule la gravité
    #
    # Pourquoi un gros if/elif au lieu d'un dictionnaire ?
    # → Parce que la plupart des branches dépendent À LA FOIS de la touche
    #   ET du mode actif (ex: [T] fait des choses différentes en mode 1, 2,
    #   6, 9, 10, 11). Un dict imbriqué serait plus lourd à lire.
    #
    # `mods & pygame.KMOD_CTRL` = test que la touche Ctrl est ENFONCÉE en
    # même temps. KMOD_CTRL est un "drapeau de bit", on l'extrait avec & (ET).

    def handle_key(self, key):
        # Si une saisie de texte est en cours, on redirige TOUT le clavier
        # vers le handler texte (voir section 7).
        if self._text_mode is not None:
            return self._handle_text(key)

        mods = pygame.key.get_mods()

        # ── Raccourcis globaux ─────────────────────────────────────────────

        # Ctrl+Z : annuler.
        if key == pygame.K_z and (mods & pygame.KMOD_CTRL):
            self._undo()
            return "undo"

        # Ctrl+U : régler "taille joueur" + "zoom caméra" (propre à la carte).
        if key == pygame.K_u and (mods & pygame.KMOD_CTRL):
            cur_ps = getattr(settings, "PLAYER_SCALE", 1.0)
            cur_cz = getattr(self.camera, "zoom", 1.0)
            self._ask_text(
                "scale_zoom",
                f"Taille joueur + zoom caméra (ex: '0.5 1.2') "
                f"— actuel: {cur_ps:.2f} {cur_cz:.2f} :",
            )
            return "text_input"

        # Ctrl+R : restaurer (2 appuis en 5 s pour confirmer).
        if key == pygame.K_r and (mods & pygame.KMOD_CTRL):
            restores = self._list_restore_points()
            if not restores:
                self._show_msg("Aucun point de restauration — utilisez [S] pour sauvegarder d'abord")
            elif self._restore_confirm:
                # 2e appui → on charge.
                self._load_restore_point(restores[-1])
                self._restore_confirm       = False
                self._restore_confirm_timer = 0.0
                return "done"   # demande à game.py de reconstruire son cache
            else:
                # 1er appui → on demande confirmation.
                self._restore_confirm       = True
                self._restore_confirm_timer = 5.0
                self._show_msg(f"Ctrl+R encore pour charger : {restores[-1]}  (5s)", 5.0)
            return None

        # R seul : respawn (replace le joueur au spawn).
        if key == pygame.K_o and not (mods & pygame.KMOD_CTRL):
            self.player.respawn()
            return None

        # Touches "action simple".
        if   key == pygame.K_m:
            self.change_mode()
        elif key == pygame.K_h:
            self.show_hitboxes = not self.show_hitboxes
        elif key == pygame.K_n:
            # Nouvelle map : on demande la couleur de fond.
            self._ask_text("bg_color_new", "Couleur de fond (nom / r,g,b / #hex) :")
            return "text_input"
        elif key == pygame.K_s:
            self._ask_text("save", "Sauvegarder sous :")
            return "text_input"
        elif key == pygame.K_l:
            maps = self._list_maps()
            self._ask_text("load", "Charger :" +
                           (f"  ({', '.join(maps)})" if maps else ""))
            return "text_input"
        elif key == pygame.K_i and not (mods & pygame.KMOD_CTRL):
            tiled_files = self._list_tiled_files()
            hint = f"  ({', '.join(tiled_files)})" if tiled_files else "  (aucun fichier dans tiled/)"
            self._ask_text("import_tiled",
                           f"Importer Tiled — 'nom' / 'nom X Y' / 'nom X Y SCALE' :{hint}")
            return "text_input"
        elif key == pygame.K_F2:
            # Si on est sur une zone trigger, on ouvre la cinématique liée ;
            # sinon, le navigateur de cinématiques.
            cine_nom = ""
            if self.mode == 12 and self.trigger_zones:
                # Zone la plus proche du curseur souris (en monde)
                mx, my = pygame.mouse.get_pos()
                wx = int(mx + self.camera.offset_x)
                wy = int(my + self.camera.offset_y)
                pt = pygame.Rect(wx, wy, 1, 1)
                for z in self.trigger_zones:
                    if z.rect.colliderect(pt) and getattr(z, "cutscene_nom", ""):
                        cine_nom = z.cutscene_nom
                        break
            self.cine_editor.ouvrir(cine_nom)
            return "cine_open"
        elif key == pygame.K_F3:
            # Édite les dialogues du PNJ le plus proche du curseur.
            pnj = self._pnj_le_plus_proche(max_dist=200)
            if pnj is None:
                self._show_msg("Aucun PNJ proche — passe en mode 11 (PNJ) et survole-en un")
            else:
                self.pnj_editor.ouvrir(pnj)
            return "pnj_open"
        elif key == pygame.K_k and self._nom_carte:
            # Définir la carte actuelle comme point de départ de l'histoire.
            return f"set_start:{self._nom_carte}"
        elif key == pygame.K_k:
            self._show_msg("[K] Sauvegardez d'abord la carte avec [S]")
        elif key == pygame.K_b and (mods & pygame.KMOD_CTRL):
            # Ctrl+B : reset spawn en (100, 100).
            self.spawn_x = self.spawn_y = 100
            self.player.spawn_x = self.player.spawn_y = 100
            self.player.respawn()
            self._show_msg("Spawn réinitialisé à (100, 100)")
        elif key == pygame.K_b and self.mode in (9, 11):
            # B (mode 9 Décor / 11 Blocs) : toggle SAVE POINT sur le décor
            # le plus proche du curseur. Permet de transformer n'importe
            # quel objet du monde (pancarte, banc, autel, ou même un décor
            # invisible) en point de sauvegarde — l'interaction (E) en jeu
            # ouvre alors le menu sauvegarde au lieu de rien faire.
            d = self._decor_le_plus_proche(max_dist=200)
            if d is None:
                self._show_msg("Aucun décor proche — survole-en un et appuie B")
            else:
                d.is_save_point = not getattr(d, "is_save_point", False)
                etat = "ON (point de sauvegarde)" if d.is_save_point else "OFF"
                self._show_msg(f"Décor '{d.nom_sprite}' : save point = {etat}")
        elif key == pygame.K_F5:
            # F5 : caméra libre / suivi du joueur.
            self.camera.free_mode = not self.camera.free_mode
            if self.camera.free_mode:
                self._show_msg("Caméra libre — Molette=déplacer  Clic molette=glisser  [F5]=retour")
            else:
                self.camera.stop_drag()
                self._show_msg("Caméra : suivi du joueur")

        # ── Flèches : règlent la taille du monde (Phase 1 uniquement) ──
        elif key in (pygame.K_UP, pygame.K_DOWN, pygame.K_HOME, pygame.K_END,
                     pygame.K_LEFT, pygame.K_RIGHT):
            if self.has_holes:
                self._show_msg("Phase 2 active — structure verrouillée  |  [Ctrl+R]=restaurer  [N]=nouvelle map")
                return None
            self._snapshot()
            if   key == pygame.K_UP:    settings.GROUND_Y  = max(100,  settings.GROUND_Y - 20)
            elif key == pygame.K_DOWN:  settings.GROUND_Y  = min(4000, settings.GROUND_Y + 20)
            elif key == pygame.K_HOME:  settings.CEILING_Y = max(-1500, settings.CEILING_Y - 20)
            elif key == pygame.K_END:   settings.CEILING_Y = min(settings.GROUND_Y - 100,
                                                                 settings.CEILING_Y + 20)
            elif key == pygame.K_LEFT:
                if mods & pygame.KMOD_SHIFT:
                    settings.SCENE_LEFT = max(-5000, settings.SCENE_LEFT - 100)
                    self._show_msg(f"Mur GAUCHE → x={settings.SCENE_LEFT}")
                else:
                    nouvelle = max(settings.SCENE_LEFT + 800,
                                   settings.SCENE_WIDTH - 100)
                    settings.SCENE_WIDTH    = nouvelle
                    self.camera.scene_width = settings.SCENE_WIDTH
                    self._show_msg(f"Mur DROIT → x={settings.SCENE_WIDTH}")
            elif key == pygame.K_RIGHT:
                if mods & pygame.KMOD_SHIFT:
                    nouvelle = min(settings.SCENE_WIDTH - 800,
                                   settings.SCENE_LEFT + 100)
                    settings.SCENE_LEFT = nouvelle
                    self._show_msg(f"Mur GAUCHE → x={settings.SCENE_LEFT}")
                else:
                    settings.SCENE_WIDTH    += 100
                    self.camera.scene_width  = settings.SCENE_WIDTH
                    self._show_msg(f"Mur DROIT → x={settings.SCENE_WIDTH}")
            self.build_border_segments()
            return "structure"

        # ── PageUp/Down : jump_power ennemi OU caméra Y ──
        elif key == pygame.K_PAGEUP:
            if self.mode == 1 and self.mob_detect_mode and self._detect_target:
                self._detect_target.jump_power = min(800, self._detect_target.jump_power + 50)
                self._show_msg(f"Jump power ennemi = {self._detect_target.jump_power}")
            elif self.mode == 1:
                self.mob_jump_power = min(800, self.mob_jump_power + 50)
                self._show_msg(f"Hauteur de saut : {self.mob_jump_power}")
            else:
                self.camera.y_offset = max(-400, self.camera.y_offset - 20)
        elif key == pygame.K_PAGEDOWN:
            if self.mode == 1 and self.mob_detect_mode and self._detect_target:
                self._detect_target.jump_power = max(100, self._detect_target.jump_power - 50)
                self._show_msg(f"Jump power ennemi = {self._detect_target.jump_power}")
            elif self.mode == 1:
                self.mob_jump_power = max(100, self.mob_jump_power - 50)
                self._show_msg(f"Hauteur de saut : {self.mob_jump_power}")
            else:
                self.camera.y_offset = min(400, self.camera.y_offset + 20)

        # ── Mode 2 : Lumière ───────────────────────────────────────────────
        elif key == pygame.K_t and self.mode == 2:
            self.light_type_index = (self.light_type_index + 1) % len(LIGHT_TYPES)
        elif key == pygame.K_f and self.mode == 2:
            self.light_flicker = not self.light_flicker

        # ── Mode 1 : Ennemi (mob) ──────────────────────────────────────────
        elif key == pygame.K_g and self.mode == 1: self.mob_gravity           = not self.mob_gravity
        elif key == pygame.K_c and self.mode == 1: self.mob_collision         = not self.mob_collision
        elif key == pygame.K_j and self.mode == 1: self.mob_can_jump          = not self.mob_can_jump
        elif key == pygame.K_v and self.mode == 1: self.mob_can_jump_patrol   = not self.mob_can_jump_patrol
        elif key == pygame.K_i and self.mode == 1: self.mob_has_light         = not self.mob_has_light
        elif key == pygame.K_o and self.mode == 1: self.mob_can_fall_in_holes = not self.mob_can_fall_in_holes
        elif key == pygame.K_u and self.mode == 1: self.mob_can_turn_randomly = not self.mob_can_turn_randomly
        elif key == pygame.K_t and self.mode == 1:
            self.mob_sprite_index = (self.mob_sprite_index + 1) % max(1, len(self._enemy_sprites))
        elif key == pygame.K_KP_MULTIPLY and self.mode == 1:
            # Touche * du pavé num. : augmente respawn_timeout.
            if self.mob_respawn_timeout < 0:
                self.mob_respawn_timeout = 5.0
            else:
                self.mob_respawn_timeout = min(120.0, self.mob_respawn_timeout + 5.0)
        elif key == pygame.K_KP_DIVIDE and self.mode == 1:
            # Touche / : diminue respawn_timeout (0 → -1 = OFF).
            self.mob_respawn_timeout = max(-1.0, self.mob_respawn_timeout - 5.0)
            if self.mob_respawn_timeout == 0.0:
                self.mob_respawn_timeout = -1.0
        elif key == pygame.K_KP_PLUS  and self.mode == 1 and self.mob_detect_mode and self._detect_target:
            self._detect_target.detect_range = min(600, self._detect_target.detect_range + 25)
        elif key == pygame.K_KP_MINUS and self.mode == 1 and self.mob_detect_mode and self._detect_target:
            self._detect_target.detect_range = max(50,  self._detect_target.detect_range - 25)
        elif key == pygame.K_KP_PLUS  and self.mode == 1:
            self.mob_detect_range = min(500, self.mob_detect_range + 25)
        elif key == pygame.K_KP_MINUS and self.mode == 1:
            self.mob_detect_range = max(50,  self.mob_detect_range - 25)
        elif key == pygame.K_p and self.mode == 1:
            # Bascule "mode patrouille" (régler la zone d'un ennemi existant).
            self.mob_patrol_mode = not self.mob_patrol_mode
            self.mob_detect_mode = False
            self._patrol_target  = None
            self._patrol_first_x = None
        elif key == pygame.K_d and self.mode == 1:
            # Bascule "mode détection" (régler direction/portée).
            self.mob_detect_mode = not self.mob_detect_mode
            self.mob_patrol_mode = False
            self._detect_target  = None

        # ── Mode 6 : Hitbox ────────────────────────────────────────────────
        elif key == pygame.K_t and self.mode == 6:
            self._hb_sprite_index = (self._hb_sprite_index + 1) % max(1, len(self._hb_sprite_list()))
            self._hb_first_point  = None

        # ── Mode 8 : Copier/Coller ─────────────────────────────────────────
        elif key == pygame.K_c and self.mode == 8:
            self._do_copy()
        elif key == pygame.K_v and self.mode == 8:
            if self._has_clipboard:
                mx, my = pygame.mouse.get_pos()
                self._do_paste(int(mx + self.camera.offset_x),
                               int(my + self.camera.offset_y))

        # ── Mode 9 : Décor ─────────────────────────────────────────────────
        elif key == pygame.K_t and self.mode == 9:
            sprites = self._decor_sprites_filtrés()
            if sprites:
                self.decor_sprite_index = (self.decor_sprite_index + 1) % len(sprites)
        elif key == pygame.K_g and self.mode == 9:
            # Changer de catégorie (cycle : cat1 → cat2 → … → TOUTES → cat1).
            self._decor_sprites, self._decor_categories = _lister_decors()
            if self._decor_categories:
                self._decor_cat_index += 1
                if self._decor_cat_index >= len(self._decor_categories):
                    self._decor_cat_index = -1
                self.decor_sprite_index = 0
                cat = (self._decor_categories[self._decor_cat_index]
                       if self._decor_cat_index >= 0 else "TOUTES")
                self._show_msg(f"Catégorie : {cat} ({len(self._decor_sprites_filtrés())} décors)")
        elif key == pygame.K_c and self.mode == 9:
            self.decor_collision = not self.decor_collision
            etat = "AVEC collision" if self.decor_collision else "sans collision"
            self._show_msg(f"Décor : {etat}")
        elif key == pygame.K_f and self.mode == 9:
            self.decor_fill_mode = not self.decor_fill_mode
            etat = "REMPLISSAGE activé" if self.decor_fill_mode else "placement normal"
            self._show_msg(f"Décor : {etat}")
        elif key == pygame.K_y and self.mode == 9:
            # Activer/désactiver le mode édition de hitbox décor.
            self._decor_hb_mode   = not getattr(self, '_decor_hb_mode', False)
            self._decor_hb_target = None
            self._decor_hb_first  = None
            if self._decor_hb_mode:
                self._show_msg("Hitbox décor : clic sur un décor puis 2 clics pour la zone")
            else:
                self._show_msg("Hitbox décor : désactivé")
        elif key == pygame.K_x and self.mode == 9:
            # Reset hitbox du décor sous le curseur à image entière.
            mx, my = pygame.mouse.get_pos()
            wx = int(mx + self.camera.offset_x)
            wy = int(my + self.camera.offset_y)
            pt = pygame.Rect(wx, wy, 1, 1)
            # `reversed` : on itère en priorité sur le DERNIER décor posé.
            for d in reversed(self.decors):
                if d.rect.colliderect(pt):
                    d.collision_box = None
                    self._show_msg("Hitbox réinitialisée (image entière)")
                    break

        # ── Mode 10 : PNJ ──────────────────────────────────────────────────
        elif key == pygame.K_t and self.mode == 10:
            # Naviguer dans le registre PNJ.
            self._charger_registre_pnj()
            if self._pnj_registry:
                self._pnj_reg_index += 1
                if self._pnj_reg_index >= len(self._pnj_registry):
                    self._pnj_reg_index = -1
                reg = self._pnj_reg_courant()
                if reg:
                    self._show_msg(f"PNJ : {reg['nom']} ({reg.get('sprite_name','—')})")
                else:
                    self._show_msg("PNJ : + Nouveau personnage")
            else:
                self._show_msg("Registre vide — placez un PNJ pour créer un personnage")
        elif key == pygame.K_g and self.mode == 10:
            # Changer le sprite pour un nouveau PNJ.
            self._pnj_sprites = list_pnj_sprites()
            if self._pnj_sprites:
                self._pnj_sprite_index = (self._pnj_sprite_index + 1) % len(self._pnj_sprites)
                self._show_msg(f"Sprite : {self._pnj_sprites[self._pnj_sprite_index]}")
            else:
                self._show_msg("Aucun sprite dans assets/images/pnj/")
        elif key == pygame.K_d and self.mode == 10:
            # Ajouter un dialogue au PNJ le plus proche du curseur.
            pnj = self._pnj_le_plus_proche()
            if pnj:
                self._pnj_edit_target = pnj
                self._ask_text("pnj_dialogue",
                               f"Dialogue pour {pnj.nom} (ligne1|ligne2|...) :")
                return "text_input"
            else:
                self._show_msg("Aucun PNJ proche")
        elif key == pygame.K_w and self.mode == 10:
            # Changer le mode de répétition du dialogue.
            pnj = self._pnj_le_plus_proche()
            if pnj:
                modes = ["boucle_dernier", "restart"]
                idx = modes.index(pnj.dialogue_mode) if pnj.dialogue_mode in modes else 0
                pnj.dialogue_mode = modes[(idx + 1) % len(modes)]
                labels = {"boucle_dernier": "Boucle dernière phrase",
                          "restart":        "Recommence tout"}
                self._show_msg(f"{pnj.nom} : {labels[pnj.dialogue_mode]}")
        elif key == pygame.K_x and self.mode == 10:
            # Mode "objet parlant" : crée un PNJ INVISIBLE (sprite 100%
            # transparent) au prochain clic. Pratique pour des panneaux,
            # voix off, journaux au sol, etc. Le joueur déclenche le
            # dialogue avec [E] comme un PNJ classique.
            self._ask_text("pnj_invisible_taille",
                           "Taille de l'objet (LxH ou L H, ex: 64 96) :")
            return "text_input"

        # ── Mode 4 : Portail → [P] bascule "prochaine porte" ─────────────
        # Une "porte" est un portail qui ne se déclenche QUE si le joueur
        # appuie sur Z (ou ↑) — comme pour "entrer" dans une maison. Sans
        # appui, on peut rester devant la porte sans être téléporté.
        # À activer AVANT de tracer le rectangle du portail.
        elif key == pygame.K_p and self.mode == 4:
            current = getattr(self, "_pending_portal_is_door", False)
            self._pending_portal_is_door = not current
            if self._pending_portal_is_door:
                self._show_msg("Prochain portail = PORTE (Z pour entrer)")
            else:
                self._show_msg("Prochain portail = classique")

        # ── Mode 11 : Blocs (auto-tiling) ──────────────────────────────────
        elif key == pygame.K_t and self.mode == 11:
            self.bloc_theme = "vert" if self.bloc_theme == "bleu" else "bleu"
            self._show_msg(f"Thème : {self.bloc_theme}")
        elif key == pygame.K_f and self.mode == 11:
            self._bloc_shape  = (self._bloc_shape + 1) % len(self._BLOC_SHAPES)
            self._bloc_facing = 0   # reset le sens quand on change de forme
            self._show_msg(f"Forme : {self._BLOC_SHAPES[self._bloc_shape]}")
        elif key == pygame.K_v and self.mode == 11:
            self._bloc_facing = 1 - self._bloc_facing
            label = self._BLOC_FACINGS[self._bloc_shape][self._bloc_facing]
            self._show_msg(f"Sens : {label}")

        # ── Mode 12 : Trigger (cinématiques) ──────────────────────────────
        # [R] = renommer / régler la zone trigger SOUS LE CURSEUR (cutscene_nom
        #       puis max_plays). Évite de devoir supprimer + recréer la zone.
        # [F] = la PROCHAINE zone tracée sera une "fear_zone" (= ralentit le
        #       joueur s'il a trop peur, et bloque s'il n'a pas assez de
        #       compagnons). Une seule activation = une seule fear_zone.
        elif key == pygame.K_f and self.mode == 12:
            self._pending_trigger_is_fear = not self._pending_trigger_is_fear
            if self._pending_trigger_is_fear:
                self._show_msg("Prochaine zone = FEAR_ZONE — trace le rect.")
            else:
                self._show_msg("Mode fear_zone annulé.")
        elif key == pygame.K_r and self.mode == 12:
            zone = self._trigger_sous_curseur()
            if zone is None:
                self._show_msg("Aucun trigger sous le curseur")
            else:
                self._snapshot()
                self._editing_trigger      = zone
                self._pending_trigger_nom  = ""
                actuel = getattr(zone, "cutscene_nom", "")
                self._ask_text(
                    "trigger_edit_nom",
                    f"Nouveau nom de cinématique (actuel : '{actuel}') :"
                )
                return "text_input"

        return None

    def _new_map(self, bg_color=None):
        """Remet tout à zéro (nouvelle carte vierge)."""
        self._history.clear()
        self.platforms.clear()
        self.enemies.clear()
        self.lighting.lights.clear()
        self.portals.clear()
        self.custom_walls.clear()
        self.decors.clear()
        self.pnjs.clear()
        self.trigger_zones.clear()
        self._has_clipboard         = False
        self._restore_confirm       = False
        self._restore_confirm_timer = 0.0

        # Réglages de base.
        settings.GROUND_Y    = 590
        settings.CEILING_Y   = 0
        settings.SCENE_WIDTH = 2400
        settings.SCENE_LEFT  = 0
        self.spawn_x = self.spawn_y = 100
        self.player.spawn_x = self.player.spawn_y = 100
        self.player.respawn()
        self.camera.y_offset = 150
        self.bg_color = list(bg_color) if bg_color else list(VIOLET)
        self.build_border_segments()
        self._show_msg("Nouvelle map — Phase 1 : règle la taille avec ↑↓←→")

    # ═════════════════════════════════════════════════════════════════════════
    # 7.  SAISIE DE TEXTE (popups : sauver, charger, nommer PNJ, dialogue, …)
    # ═════════════════════════════════════════════════════════════════════════

    def _ask_text(self, mode, prompt):
        """Ouvre la popup de saisie."""
        self._text_mode   = mode
        self._text_input  = ""
        self._text_prompt = prompt

    def _handle_text(self, key):
        """Gère les touches pendant une saisie de texte."""
        if key == pygame.K_RETURN:
            # Entrée : on valide et on agit selon le mode.
            name = self._text_input.strip()
            mode = self._text_mode
            self._text_mode  = None
            self._text_input = ""

            if mode == "bg_color_new":
                # Nouvelle map + couleur de fond.
                color = _parse_color(name) if name else None
                self._new_map(bg_color=color or tuple(VIOLET))
                return "done"

            if mode == "named_spawn":
                # Mode 14 : enregistre la position cliquée sous le nom donné.
                # Le nom sert ensuite dans les portails : target_map = "carte nom".
                if name and getattr(self, "_pending_spawn_pos", None):
                    x, y = self._pending_spawn_pos
                    self.named_spawns[name] = [int(x), int(y)]
                    self._show_msg(f"Spawn '{name}' placé en ({x}, {y})")
                self._pending_spawn_pos = None
                return "done"

            if mode == "pnj_nom":
                # Renomme le PNJ + enregistre au registre.
                if self._pnj_edit_target:
                    if name:
                        self._pnj_edit_target.nom = name
                    self._ajouter_au_registre(
                        self._pnj_edit_target.nom,
                        self._pnj_edit_target.sprite_name,
                    )
                    self._show_msg(f"PNJ enregistré : {self._pnj_edit_target.nom}")
                self._pnj_edit_target = None
                return "done"

            if mode == "pnj_dialogue":
                # Format : ligne1|ligne2|ligne3 → une conversation.
                if self._pnj_edit_target and name:
                    lignes = [(l.strip(), self._pnj_edit_target.nom)
                              for l in name.split("|") if l.strip()]
                    if lignes:
                        self._pnj_edit_target._dialogues.append(lignes)
                        self._show_msg(f"Dialogue ajouté ({len(lignes)} lignes)")
                self._pnj_edit_target = None
                return "done"

            if mode == "pnj_invisible_taille":
                # Parse "LxH" ou "L H" ou "L,H" → (largeur, hauteur).
                # Si vide ou invalide → on annule, on ne pose rien.
                txt = (name or "").lower().replace("x", " ").replace(",", " ")
                parts = txt.split()
                if len(parts) >= 2:
                    try:
                        w = int(float(parts[0]))
                        h = int(float(parts[1]))
                        self._pnj_invisible_taille = (w, h)
                        self._show_msg(
                            f"Objet parlant {w}x{h} : clic pour le poser, "
                            "puis [D] pour ajouter un dialogue.")
                    except ValueError:
                        self._show_msg("Taille invalide (ex: 64 96)")
                else:
                    self._show_msg("Tape la taille (ex: 64 96)")
                return "done"

            if not name:
                return "done"

            if   mode == "save":       self.save(name)
            elif mode == "load":       self.load(name)
            elif mode == "scale_zoom": self._appliquer_scale_zoom(name)
            elif mode == "portal_name" and self._pending_portal_rect:
                r = self._pending_portal_rect
                # _pending_portal_is_door : True si on a appuyé sur [P]
                # avant de tracer (= "prochain portail = PORTE").
                is_door = getattr(self, "_pending_portal_is_door", False)
                self.portals.append(Portal(r[0], r[1], r[2], r[3], name,
                                           require_up=is_door))
                self._pending_portal_rect    = None
                self._pending_portal_is_door = False     # désarme après usage
            elif mode == "trigger_nom" and self._pending_trigger_rect:
                # Étape 1/2 : on a le nom, on demande max_plays
                self._pending_trigger_nom = name
                self._ask_text("trigger_max_plays",
                               "Nombre max de lectures (1=unique, 0=illimité, défaut=1) :")
                return "done"
            elif mode == "fear_zone_params" and self._pending_trigger_rect:
                # Format saisie : "max_peur direction texte..."
                # ex: "0 d Vous avez trop peur"   ou  "2 g"   ou  "0"
                # max_peur : 0..5 (défaut 0). direction : g/d/h/b (défaut d).
                # texte : tout le reste de la ligne (peut être vide → défaut).
                parts = name.split(" ", 2)
                try:
                    peur_max = int(parts[0]) if parts and parts[0] else 0
                except ValueError:
                    peur_max = 0
                direction = "d"
                if len(parts) >= 2 and parts[1] in ("g", "d", "h", "b"):
                    direction = parts[1]
                texte = parts[2] if len(parts) >= 3 and parts[2] else \
                        "Vous avez trop peur pour avancer..."
                # Les espaces tapés étaient remplacés par "_" → on les remet.
                texte = texte.replace("_", " ")
                r = self._pending_trigger_rect
                self.trigger_zones.append(FearZoneTrigger(
                    (r[0], r[1], r[2], r[3]),
                    peur_max=peur_max, direction_mur=direction, texte=texte,
                    nom=f"fear_{peur_max}",
                ))
                self._pending_trigger_rect    = None
                self._pending_trigger_is_fear = False
                self._show_msg(
                    f"Fear zone créée (peur_max={peur_max}, mur={direction}).")
                return "done"
            elif mode == "trigger_max_plays" and self._pending_trigger_rect:
                # Étape 2/2 : on construit le trigger
                try:
                    max_plays = int(name) if name else 1
                except ValueError:
                    max_plays = 1
                r   = self._pending_trigger_rect
                nom_cine = self._pending_trigger_nom
                zone = CutsceneTrigger(
                    (r[0], r[1], r[2], r[3]),
                    cutscene_nom=nom_cine,
                    nom=nom_cine,
                    max_plays=max_plays,
                )
                self.trigger_zones.append(zone)
                self._pending_trigger_rect = None
                self._pending_trigger_nom  = ""
                if max_plays == 0:
                    self._show_msg(f"Trigger '{nom_cine}' placé (illimité)")
                else:
                    self._show_msg(f"Trigger '{nom_cine}' placé (max {max_plays} fois)")
            elif mode == "trigger_edit_nom" and self._editing_trigger is not None:
                # Étape 1/2 du rename : on retient le nouveau nom (vide = on
                # garde l'ancien) et on demande max_plays.
                if name:
                    self._pending_trigger_nom = name
                else:
                    self._pending_trigger_nom = self._editing_trigger.cutscene_nom
                actuel = self._editing_trigger.max_plays
                self._ask_text(
                    "trigger_edit_max_plays",
                    f"Max lectures (actuel : {actuel}, 1=unique, 0=illimité) :"
                )
                return "done"
            elif mode == "trigger_edit_max_plays" and self._editing_trigger is not None:
                # Étape 2/2 : on applique les modifs
                try:
                    max_plays = int(name) if name else self._editing_trigger.max_plays
                except ValueError:
                    max_plays = self._editing_trigger.max_plays
                z = self._editing_trigger
                z.cutscene_nom = self._pending_trigger_nom
                z.nom          = self._pending_trigger_nom or z.nom
                z.max_plays    = max_plays
                self._show_msg(
                    f"Trigger mis à jour : '{z.cutscene_nom}'  (max {max_plays})"
                )
                self._editing_trigger     = None
                self._pending_trigger_nom = ""
            elif mode == "bg_color":
                color = _parse_color(name)
                if color:
                    self.bg_color = list(color)
            elif mode == "import_tiled":
                self._appliquer_import_tiled(name)
            return "done"

        elif key == pygame.K_ESCAPE:
            self._text_mode            = None
            self._text_input           = ""
            self._pending_portal_rect  = None
            self._pending_trigger_rect = None
            self._pending_trigger_nom  = ""
            self._editing_trigger      = None
            return "cancel"

        elif key == pygame.K_BACKSPACE:
            self._text_input = self._text_input[:-1]

        else:
            # ── Modes "riches" : saisie via TEXTINPUT (gère majuscules,
            # accents, ponctuation française) ─────────────────────────────
            # Pour ces modes, on NE traite PAS la touche en KEYDOWN
            # (sauf BACKSPACE/ENTER plus haut, qui ne génèrent pas de
            # TEXTINPUT). Tout le caractère arrive via handle_textinput().
            #
            # Par défaut : modes PNJ + fear_zone_params. Si tu veux ajouter
            # un autre mode (ex: titre de map, commentaire libre…), ajoute
            # son nom ici ET dans handle_textinput() ci-dessous.
            modes_riches = ("pnj_nom", "pnj_dialogue", "fear_zone_params")
            if self._text_mode not in modes_riches:
                char = pygame.key.name(key)
                if len(char) == 1 and (char.isalnum() or char in ",.#"):
                    self._text_input += char
                elif char == "space":
                    # Modes qui ont besoin du VRAI espace (multi-valeurs,
                    # ou syntaxe "mapname spawnname" pour les portails).
                    # Pour les autres modes (noms de fichiers de save…),
                    # on convertit en "_" pour éviter les espaces dans
                    # les chemins.
                    if self._text_mode in (
                            "import_tiled", "scale_zoom",
                            "pnj_invisible_taille",
                            "named_spawn",        # nom de spawn (peut contenir espaces)
                            "portal_name",        # "carte spawn_nom" (espace = séparateur)
                    ):
                        self._text_input += " "
                    else:
                        self._text_input += "_"
                elif char == "-":
                    self._text_input += "-"
                elif char in ("period", "[.]", "kp_period", "kp_decimal"):
                    # pygame renvoie "period" pour la touche . du clavier
                    # principal, "kp_period"/"kp_decimal" pour le pavé num.
                    # Indispensable pour les décimales (ex: "0.5").
                    self._text_input += "."
                elif char in ("comma", "kp_comma"):
                    # Beaucoup de claviers FR utilisent la virgule comme
                    # séparateur décimal — on l'accepte aussi.
                    self._text_input += ","


        return "typing"

    def handle_textinput(self, text):
        """Appelé depuis game.py sur les TEXTINPUT (saisie riche).

        Les TEXTINPUT remontent les caractères "finalisés" par l'OS, donc
        gèrent NATIVEMENT les majuscules (Shift), les accents (â, é, ç…)
        et la ponctuation française. Pour ces modes-ci, on by-pass la
        boucle KEYDOWN (cf. _handle_text) — le caractère arrive ici."""
        if self._text_mode in ("pnj_nom", "pnj_dialogue", "fear_zone_params"):
            self._text_input += text

    def _list_maps(self):
        """Liste les fichiers map*.json du dossier maps/."""
        if not os.path.isdir(MAPS_DIR):
            return []
        return sorted(f[:-5] for f in os.listdir(MAPS_DIR)
                      if f.endswith(".json") and not f.startswith("_"))

    def _list_tiled_files(self):
        """Liste les fichiers .tmj et .tmx dans le dossier tiled/."""
        from world.tiled_importer import TILED_DIR
        if not os.path.isdir(TILED_DIR):
            return []
        noms = set()
        for f in os.listdir(TILED_DIR):
            if f.endswith(".tmj") or f.endswith(".tmx"):
                noms.add(f[:-4])
        return sorted(noms)
    def _appliquer_scale_zoom(self, saisie):
        """Applique 'taille joueur' + 'zoom caméra' à partir d'une saisie
        type "0.5" (joueur uniquement) ou "0.5 1.2" (joueur + zoom)."""
        parts = (saisie or "").strip().replace(",", ".").split()
        if not parts:
            self._show_msg("Aucune valeur saisie")
            return
        try:
            new_ps = float(parts[0])
            new_cz = float(parts[1]) if len(parts) >= 2 else getattr(self.camera, "zoom", 1.0)
        except ValueError:
            self._show_msg("Saisie invalide (utiliser des nombres)")
            return
        # Bornage raisonnable pour éviter de tout faire crasher.
        new_ps = max(0.1, min(5.0, new_ps))
        new_cz = max(0.1, min(8.0, new_cz))

        self._snapshot()

        # Applique au joueur (resize hitbox + sprite via PLAYER_SCALE).
        settings.PLAYER_SCALE = new_ps
        if hasattr(self.player, "reload_hitbox"):
            self.player.reload_hitbox()

        # Applique à la caméra.
        self.camera.zoom = new_cz

        # Pixel art crisp : le rendu arrondit le zoom à l'entier le plus
        # proche (1, 2, 3…) pour garder le pixel art NET. On affiche la
        # valeur effective pour que l'utilisateur ne soit pas surpris.
        zoom_effectif = max(1, int(round(new_cz)))
        if abs(new_cz - zoom_effectif) > 0.01:
            self._show_msg(
                f"Taille joueur = {new_ps:.2f}  |  Zoom demandé = {new_cz:.2f}  "
                f"→ zoom effectif (pixel art net) = {zoom_effectif}×"
            )
        else:
            self._show_msg(
                f"Taille joueur = {new_ps:.2f}  |  Zoom caméra = {new_cz:.2f}"
            )
    def _appliquer_import_tiled(self, saisie):
        """Importe une carte Tiled. La saisie peut être :
            - "nom"            → offset (0, 0), scale 1.0
            - "nom X"          → offset (X, 0), scale 1.0
            - "nom X Y"        → offset (X, Y), scale 1.0
            - "nom X Y SCALE"  → offset (X, Y), scale SCALE
                                 (1.0 = taille native ; 2.0 = 2x plus grand ;
                                  0.5 = 2x plus petit)
        Les valeurs X et Y sont en PIXELS dans le monde.
        """
        # Parse la saisie : nom + offset éventuel + scale éventuel
        parts = (saisie or "").strip().replace(",", ".").split()
        if not parts:
            self._show_msg("Tiled : nom de fichier vide")
            return
        nom = parts[0]
        try:
            offset_x = int(float(parts[1])) if len(parts) >= 2 else 0
            offset_y = int(float(parts[2])) if len(parts) >= 3 else 0
            scale    = float(parts[3])     if len(parts) >= 4 else 1.0
        except ValueError:
            self._show_msg("Tiled : valeur invalide (utiliser des nombres)")
            return

        resultat = importer_tiled(nom, offset_x=offset_x,
                                  offset_y=offset_y, scale=scale)
        if resultat["erreur"]:
            self._show_msg(f"Tiled: {resultat['erreur']}")
            return

        self._snapshot()

        # Ajoute les platforms de collision à celles existantes.
        self.platforms.extend(resultat["platforms"])

        # Ajoute les décors importés. On les insère TRIÉS PAR PARALLAX (les
        # plus lointains d'abord) pour que le rendu de game.py (qui parcourt
        # self.decors dans l'ordre) affiche les fonds éloignés en premier.
        nouveaux_decors = list(resultat["decors"])
        # On fusionne avec l'existant et on retrie tout par parallax.
        tous_decors = self.decors + nouveaux_decors
        tous_decors.sort(key=lambda d: (
            # Foreground tout à la fin (sera filtré par game.py de toute façon)
            1 if d.foreground else 0,
            d.parallax_x,
            d.parallax_y,
        ))
        self.decors[:] = tous_decors

        # Adapte la taille du monde si la carte Tiled (offset compris) est
        # plus grande que la scène actuelle. On NE rétrécit JAMAIS.
        world_w = resultat["world_w"]
        world_h = resultat["world_h"]
        if world_w > 0:
            import settings as _s
            if world_w > _s.SCENE_WIDTH:
                _s.SCENE_WIDTH          = world_w
                self.camera.scene_width = world_w
            # GROUND_Y = bas du monde. On ne descend que si nécessaire pour
            # contenir la carte importée (pas avant, sinon le joueur tombe
            # dans le vide quand la carte importée est plus grande que
            # l'ancienne map).
            if world_h > 0 and world_h > _s.GROUND_Y:
                _s.GROUND_Y = world_h

        # Applique la couleur de fond de Tiled (si définie dans la map)
        bg_tiled = resultat.get("bg_color")
        if bg_tiled:
            couleur = _parse_hex_color(bg_tiled)
            if couleur:
                self.bg_color = list(couleur)

        # Message récapitulatif (avec avertissement si tilesets manquants)
        nb_p = len(resultat["platforms"])
        nb_d = len(nouveaux_decors)
        ko   = resultat.get("tilesets_ko") or []
        msg  = f"Tiled '{nom}' : {nb_p} platform(s), {nb_d} décor(s)"
        if offset_x or offset_y:
            msg += f"  @({offset_x},{offset_y})"
        if scale != 1.0:
            msg += f"  ×{scale:g}"
        if ko:
            apercu = ", ".join(os.path.basename(k) for k in ko[:3])
            if len(ko) > 3:
                apercu += f" +{len(ko)-3}"
            msg += f"  ⚠ tilesets introuvables : {apercu}"
        self._show_msg(msg)
    # ═════════════════════════════════════════════════════════════════════════
    # 8.  SOURIS : molette, clic droit, clic gauche
    # ═════════════════════════════════════════════════════════════════════════

    def handle_scroll(self, direction):
        """Molette : change la vitesse de flicker (mode lumière) ou la taille."""
        if self.mode == 2:
            self.light_flicker_speed = max(1, min(15, self.light_flicker_speed + direction))
        elif self.mode == 9:
            # Molette = taille du décor (index dans self._ECHELLES).
            idx = (self._ECHELLES.index(self.decor_echelle)
                   if self.decor_echelle in self._ECHELLES else 3)
            idx = max(0, min(len(self._ECHELLES) - 1, idx + direction))
            self.decor_echelle = self._ECHELLES[idx]
        elif self.mode == 11:
            # Molette = taille du bloc.
            idx = (self._BLOC_ECHELLES.index(self.bloc_scale)
                   if self.bloc_scale in self._BLOC_ECHELLES else 0)
            idx = max(0, min(len(self._BLOC_ECHELLES) - 1, idx + direction))
            self.bloc_scale = self._BLOC_ECHELLES[idx]
            self._show_msg(f"Taille bloc : {self._bloc_base_size * self.bloc_scale}px (x{self.bloc_scale})")

    def toggle_decor_collision_at(self, wx, wy):
        """Clic molette en mode 9 : bascule la collision du décor sous le curseur."""
        pt = pygame.Rect(wx, wy, 1, 1)
        for d in reversed(self.decors):       # priorité au plus récent (devant)
            if d.rect.colliderect(pt):
                d.collision = not d.collision
                return

    def handle_click(self, mouse_pos):
        """Clic gauche : action dépendant du mode actif."""
        if self._text_mode:
            return
        wx = int(mouse_pos[0] + self.camera.offset_x)
        wy = int(mouse_pos[1] + self.camera.offset_y)
        if   self.mode == 0:  self._click_rect(wx, wy, "platform")
        elif self.mode == 1:  self._click_mob(wx, wy)
        elif self.mode == 2:  self._click_light(wx, wy)
        elif self.mode == 3:
            self.spawn_x, self.spawn_y             = wx, wy
            self.player.spawn_x, self.player.spawn_y = wx, wy
        elif self.mode == 4:  self._click_rect(wx, wy, "portal")
        elif self.mode == 5:  self._click_rect(wx, wy, "wall")
        elif self.mode == 6:  self._click_hitbox(wx, wy)
        elif self.mode == 7:  self._click_rect(wx, wy, "hole")
        elif self.mode == 8:
            if self._has_clipboard: self._do_paste(wx, wy)
            else:                   self._click_rect(wx, wy, "copy_select")
        elif self.mode == 9:  self._click_decor(wx, wy)
        elif self.mode == 10: self._click_pnj(wx, wy)
        elif self.mode == 11: self._click_bloc(wx, wy)
        elif self.mode == 12: self._click_rect(wx, wy, "trigger")
        if self.mode == 13:
            if self._pending_danger_rect:
                self._click_danger_respawn(wx, wy)
            else:
                self._click_rect(wx, wy, "danger")
        elif self.mode == 14:
            # Mode "Spawn nommé" : clic gauche → demande un nom puis
            # enregistre la position. Le nom servira dans les portails
            # (target_map = "carte spawn_nom").
            self._pending_spawn_pos = (wx, wy)
            self._ask_text("named_spawn", "Nom du spawn (ex: porte_maison) :")

    def handle_right_click(self, mouse_pos):
        """Clic droit : supprimer l'objet sous le curseur (selon le mode)."""
        if self._text_mode:
            return
        wx = int(mouse_pos[0] + self.camera.offset_x)
        wy = int(mouse_pos[1] + self.camera.offset_y)
        pt = pygame.Rect(wx, wy, 1, 1)
        self._snapshot()

        # Filtrage "in-place" via `[:] = ...` : garde le même objet liste.
        if   self.mode == 0:
            self.platforms[:]    = [p for p in self.platforms    if not p.rect.colliderect(pt)]
        elif self.mode == 1:
            self.enemies[:]      = [e for e in self.enemies      if not e.rect.colliderect(pt)]
        elif self.mode == 2:
            # Les lumières sont des dicts, pas des Rect.
            self.lighting.lights[:] = [
                l for l in self.lighting.lights
                if not (abs(l["x"] - wx) < l["radius"]
                        and abs(l["y"] - wy) < l["radius"])
            ]
        elif self.mode == 4:
            self.portals[:]      = [p for p in self.portals      if not p.rect.colliderect(pt)]
        elif self.mode == 5:
            self.custom_walls[:] = [w for w in self.custom_walls if not w.rect.colliderect(pt)]
        elif self.mode == 8:
            self._copy_rect      = None
            self._has_clipboard  = False
            self.first_point     = None
        elif self.mode == 9:
            self.decors[:]       = [d for d in self.decors       if not d.rect.colliderect(pt)]
        elif self.mode == 10:
            self.pnjs[:]         = [p for p in self.pnjs         if not p.rect.colliderect(pt)]
        elif self.mode == 11:
            self.decors[:]       = [d for d in self.decors       if not d.rect.colliderect(pt)]
        elif self.mode == 12:
            self.trigger_zones[:] = [z for z in self.trigger_zones if not z.rect.colliderect(pt)]
        elif self.mode == 13:
            self.danger_zones[:] = [z for z in self.danger_zones if not z["rect"].colliderect(pt)]
        elif self.mode == 14:
            # Mode "Spawn nommé" : clic droit supprime le spawn LE PLUS PROCHE
            # du curseur (rayon 32 px). Plus simple qu'un test rect parce que
            # un spawn est juste un point (pas de surface).
            if self.named_spawns:
                meilleur = None
                meilleure_d2 = 32 * 32
                for nom, (sx, sy) in self.named_spawns.items():
                    d2 = (sx - wx) ** 2 + (sy - wy) ** 2
                    if d2 < meilleure_d2:
                        meilleure_d2 = d2
                        meilleur     = nom
                if meilleur is not None:
                    del self.named_spawns[meilleur]
                    self._show_msg(f"Spawn '{meilleur}' supprimé")
    # ═════════════════════════════════════════════════════════════════════════
    # 9.  ACTIONS DE CLIC (placer plateforme / mob / lumière / décor / …)
    # ═════════════════════════════════════════════════════════════════════════

    def _click_rect(self, wx, wy, kind):
        """Clic à 2 points pour dessiner un rectangle (plateforme, mur, …)."""
        if self.first_point is None:
            self.first_point = (wx, wy)
            return

        # 2e clic : on calcule le rectangle couvrant les deux points.
        x1, y1 = self.first_point
        x = min(x1, wx)
        y = min(y1, wy)
        w = abs(wx - x1)
        h = abs(wy - y1)
        self.first_point = None
        # On ignore les rectangles trop petits (erreurs de clic).
        if w < 5 or h < 5:
            return

        self._snapshot()

        if kind == "platform":
            # color=None → invisible en jeu (le visuel vient du décor).
            # L'éditeur affiche un contour gris tant qu'il est actif.
            self.platforms.append(Platform(x, y, w, h, None))
        elif kind == "wall":
            self.custom_walls.append(Wall(x, y, w, h, visible=True))
        elif kind == "portal":
            self._pending_portal_rect = (x, y, w, h)
            maps = self._list_maps()
            # Syntaxe : "nom_map" → arrivée au spawn par défaut
            #          "nom_map nom_spawn" → arrivée au spawn nommé (mode 14
            #          "Spawn nommé" pour les placer)
            self._ask_text(
                "portal_name",
                "Map cible (ou 'map spawn') :"
                + (f"  ({', '.join(maps)})" if maps else "")
            )
        elif kind == "trigger":
            self._pending_trigger_rect = (x, y, w, h)
            if self._pending_trigger_is_fear:
                # Saisie unique pour les 3 paramètres : "max dir texte"
                # exemple : "0 d Vous avez trop peur pour avancer..."
                # Astuce multi-ligne : utiliser | comme séparateur.
                # exemple : "0 d Le couloir est sombre.|Reviens plus tard."
                self._ask_text(
                    "fear_zone_params",
                    "Fear zone — peur_max(0-5) dir(g/d/h/b) texte (| = saut de ligne) :")
            else:
                self._ask_text("trigger_nom",
                               "Nom de la cinématique (ex: intro) :")
        elif kind == "hole":
            # Avant le 1er trou, on crée un point de restauration (Phase 2).
            if not self.has_holes:
                name = self._save_restore_point()
                self._show_msg(f"Point de restauration créé : {name}  |  Phase 2 active")
            self.apply_hole(pygame.Rect(x, y, w, h))
        elif kind == "copy_select":
            self._copy_rect = pygame.Rect(x, y, w, h)
            self._show_msg(f"Zone ({w}x{h}) — [C] copier")
        elif kind == "danger":
            self._pending_danger_rect = pygame.Rect(x, y, w, h)
            self._show_msg("Rectangle de mort placé. Cliquez là où le joueur doit réapparaître.")

    def _click_mob(self, wx, wy):
        """Clic en mode 1 : ajoute un ennemi (sauf si dans une plateforme)."""
        # Sous-modes spéciaux ?
        if self.mob_patrol_mode:
            self._click_mob_patrol(wx, wy); return
        if self.mob_detect_mode:
            self._click_mob_detect(wx, wy); return

        # Vérifie qu'on ne place pas dans une plateforme.
        hb   = get_hitbox(self._current_sprite())
        test = pygame.Rect(wx, wy, hb["w"], hb["h"])
        for p in self.platforms:
            if test.colliderect(p.rect):
                print("X Ennemi dans plateforme")
                return

        self._snapshot()
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
            can_fall_in_holes=self.mob_can_fall_in_holes,
            can_turn_randomly=self.mob_can_turn_randomly,
            respawn_timeout=self.mob_respawn_timeout,
            jump_power=self.mob_jump_power,
        ))

    def _click_mob_patrol(self, wx, wy):
        """Sous-mode patrouille : clic1 = choisir l'ennemi, clic2/3 = limites."""
        if self._patrol_target is None:
            # 1er clic : on cherche l'ennemi le plus proche.
            best, bd = None, 9999999
            for e in self.enemies:
                d = (e.rect.centerx - wx) ** 2 + (e.rect.centery - wy) ** 2
                if d < bd:
                    bd = d
                    best = e
            if best and bd < 100 * 100:
                self._patrol_target = best
            else:
                print("Aucun mob proche")

        elif self._patrol_first_x is None:
            # 2e clic : 1re limite X.
            self._patrol_first_x = wx

        else:
            # 3e clic : 2e limite X.
            l, r = min(self._patrol_first_x, wx), max(self._patrol_first_x, wx)
            if r - l > 20:
                self._patrol_target.patrol_left  = l
                self._patrol_target.patrol_right = r
            self._patrol_target  = None
            self._patrol_first_x = None

    def _click_mob_detect(self, wx, wy):
        """Sous-mode détection : clic1 = ennemi, clic2 = direction."""
        if self._detect_target is None:
            best, bd = None, 9999999
            for e in self.enemies:
                d = (e.rect.centerx - wx) ** 2 + (e.rect.centery - wy) ** 2
                if d < bd:
                    bd = d
                    best = e
            if best and bd < 100 * 100:
                self._detect_target = best
            else:
                print("Aucun mob proche")
        else:
            # Oriente l'ennemi selon la position cliquée.
            self._detect_target.direction = -1 if wx < self._detect_target.rect.centerx else 1
            self._detect_target = None

    def _click_light(self, wx, wy):
        """Mode 2 : 1er clic = centre, 2e clic = rayon."""
        if self.light_first_point is None:
            self.light_first_point = (wx, wy)
        else:
            cx, cy = self.light_first_point
            r = int(((wx - cx) ** 2 + (wy - cy) ** 2) ** 0.5)
            if r > 5:
                self._snapshot()
                self.lighting.add_light(
                    cx, cy,
                    radius=r,
                    type=LIGHT_TYPES[self.light_type_index],
                    flicker=self.light_flicker,
                    flicker_speed=self.light_flicker_speed,
                )
            self.light_first_point = None

    def _click_danger_respawn(self, wx, wy):
        """3ème étape du mode danger : on place le point de respawn."""
        if self._pending_danger_rect:
            # On stocke un dictionnaire avec le Rect et le point (x, y)
            new_zone = {
                "rect": self._pending_danger_rect,
                "respawn_pos": (wx, wy)
            }
            self.danger_zones.append(new_zone)
            self._pending_danger_rect = None # On reset pour la suite
            self._show_msg("Zone de danger et Respawn liés avec succès !")

    def _do_copy(self):
        """Mode 8 : copie plateformes + murs de la zone sélectionnée."""
        if self._copy_rect is None:
            self._show_msg("Sélectionne d'abord une zone")
            return
        r = self._copy_rect
        # On stocke en coordonnées RELATIVES au coin haut-gauche du rectangle.
        self._clipboard_platforms = [
            pygame.Rect(p.rect.x - r.x, p.rect.y - r.y, p.rect.w, p.rect.h)
            for p in self.platforms if r.colliderect(p.rect)
        ]
        self._clipboard_walls = [
            pygame.Rect(w.rect.x - r.x, w.rect.y - r.y, w.rect.w, w.rect.h)
            for w in self.custom_walls if r.colliderect(w.rect)
        ]
        self._has_clipboard = True
        self._show_msg(f"Copié {len(self._clipboard_platforms)} plt, {len(self._clipboard_walls)} murs")

    def _do_paste(self, wx, wy):
        """Mode 8 : colle le presse-papiers avec (wx, wy) comme coin haut-gauche."""
        if not self._has_clipboard:
            return
        self._snapshot()
        for rel in self._clipboard_platforms:
            self.platforms.append(Platform(wx + rel.x, wy + rel.y, rel.w, rel.h, None))
        for rel in self._clipboard_walls:
            self.custom_walls.append(Wall(wx + rel.x, wy + rel.y, rel.w, rel.h, visible=True))

    def _click_decor(self, wx, wy):
        """Mode 9 : place un décor (ou bascule vers un sous-mode)."""
        # Sous-modes spéciaux.
        if getattr(self, '_decor_hb_mode', False):
            self._click_decor_hitbox(wx, wy)
            return
        if self.decor_fill_mode:
            self._click_decor_fill(wx, wy)
            return

        # Placement simple.
        sprites = self._decor_sprites_filtrés()
        if not sprites:
            self._show_msg("Aucun décor dans assets/images/decor/")
            return
        nom    = sprites[self.decor_sprite_index % len(sprites)]
        chemin = os.path.join(DECORS_DIR, nom)
        if not os.path.exists(chemin):
            return
        self._snapshot()
        self.decors.append(Decor(wx, wy, chemin, nom,
                                 collision=self.decor_collision,
                                 echelle=self.decor_echelle))

    def _click_decor_fill(self, wx, wy):
        """Mode 9 + [F] : 2 clics définissent une zone, remplie de tuiles.

        Si une catégorie est sélectionnée, on pioche AU HASARD une variante
        parmi tous les décors de la catégorie → rendu plus naturel.
        """
        import random as _rnd
        sprites = self._decor_sprites_filtrés()
        if not sprites:
            self._show_msg("Aucun décor disponible")
            return

        if self.first_point is None:
            self.first_point = (wx, wy)
            self._show_msg("Remplissage : clic pour le coin opposé")
            return

        # 2e clic : calcule la zone.
        x1, y1 = self.first_point
        self.first_point = None
        x, y   = min(x1, wx), min(y1, wy)
        rw, rh = abs(wx - x1), abs(wy - y1)
        if rw < 5 or rh < 5:
            return

        # Taille d'une tuile (basée sur le sprite courant).
        nom_ref    = sprites[self.decor_sprite_index % len(sprites)]
        chemin_ref = os.path.join(DECORS_DIR, nom_ref)
        if not os.path.exists(chemin_ref):
            return
        base = pygame.image.load(chemin_ref)
        tw = max(1, int(base.get_width()  * self.decor_echelle))
        th = max(1, int(base.get_height() * self.decor_echelle))

        # Pré-valide toutes les variantes.
        variantes = []
        for s in sprites:
            ch = os.path.join(DECORS_DIR, s)
            if os.path.exists(ch):
                variantes.append((s, ch))
        if not variantes:
            return

        # Remplissage en grille.
        self._snapshot()
        count = 0
        cy = y
        while cy < y + rh:
            cx = x
            while cx < x + rw:
                nom, chemin = _rnd.choice(variantes)
                self.decors.append(Decor(cx, cy, chemin, nom,
                                         collision=self.decor_collision,
                                         echelle=self.decor_echelle))
                count += 1
                cx += tw
            cy += th
        nb_var = len(variantes)
        self._show_msg(f"Remplissage : {count} décors "
                       f"({nb_var} variante{'s' if nb_var > 1 else ''}) sur {rw}x{rh}")

    def _click_decor_hitbox(self, wx, wy):
        """Mode 9 + [Y] : sélectionne un décor puis 2 clics pour sa hitbox."""
        if self._decor_hb_target is None:
            pt = pygame.Rect(wx, wy, 1, 1)
            for d in reversed(self.decors):
                if d.rect.colliderect(pt):
                    self._decor_hb_target = d
                    self._decor_hb_first  = None
                    self._show_msg("Décor sélectionné — clic x2 pour la hitbox")
                    return
            self._show_msg("Aucun décor sous le curseur")

        elif self._decor_hb_first is None:
            self._decor_hb_first = (wx, wy)

        else:
            x1, y1 = self._decor_hb_first
            x, y = min(x1, wx), min(y1, wy)
            w, h = abs(wx - x1), abs(wy - y1)
            if w > 2 and h > 2:
                d = self._decor_hb_target
                # Offset par rapport au coin haut-gauche du décor.
                ox = x - d.rect.x
                oy = y - d.rect.y
                d.collision_box = (ox, oy, w, h)
                d.collision     = True
                self._show_msg(f"Hitbox: {w}x{h} offset({ox},{oy})")
            self._decor_hb_target = None
            self._decor_hb_first  = None
            self._decor_hb_mode   = False

    def _click_pnj(self, wx, wy):
        """Mode 10 : place un PNJ (depuis le registre ou en crée un nouveau).

        Cas spécial "objet parlant" : si l'utilisateur a appuyé sur [X] juste
        avant et tapé une taille, le prochain clic pose un PNJ avec un sprite
        100% TRANSPARENT à cette dimension. Reste un PNJ normal côté code →
        on parle avec [E], on lui ajoute un dialogue avec [D], il se sauve
        dans le JSON comme tous les autres.
        """
        self._snapshot()

        # Branche "objet parlant" (PNJ invisible). Prioritaire sur le registre.
        if self._pnj_invisible_taille is not None:
            w, h = self._pnj_invisible_taille
            sprite = creer_sprite_invisible(w, h)
            # Refresh la liste de sprites du registre pour inclure le nouveau
            # PNG transparent (sinon il manque dans le cycle [P] de l'éditeur).
            self._pnj_sprites = list_pnj_sprites()
            nom = f"objet_{len(self.pnjs) + 1}"
            self.pnjs.append(PNJ(wx, wy, nom, [], sprite_name=sprite,
                                 has_gravity=False))
            self._pnj_edit_target = self.pnjs[-1]
            self._pnj_invisible_taille = None  # consommé : 1 clic = 1 objet
            self._ask_text("pnj_dialogue",
                           f"Dialogue de l'objet parlant (ligne1|ligne2|...) :")
            return

        reg = self._pnj_reg_courant()
        if reg:
            # Placer un personnage existant du registre.
            self.pnjs.append(PNJ(wx, wy, reg["nom"], [],
                                 sprite_name=reg.get("sprite_name")))
            self._show_msg(f"PNJ placé : {reg['nom']}")
        else:
            # Nouveau personnage → demander le nom puis l'enregistrer.
            nom = f"PNJ_{len(self.pnjs) + 1}"
            sprite = None
            if self._pnj_sprites:
                sprite = self._pnj_sprites[self._pnj_sprite_index % len(self._pnj_sprites)]
            self.pnjs.append(PNJ(wx, wy, nom, [], sprite_name=sprite))
            self._pnj_edit_target = self.pnjs[-1]
            self._ask_text("pnj_nom", f"Nom du PNJ (défaut: {nom}) :")

    # ═════════════════════════════════════════════════════════════════════════
    # 10.  AUTO-TILING (mode Blocs)
    # ═════════════════════════════════════════════════════════════════════════

    def _click_bloc(self, wx, wy):
        """Mode 11 : 2 clics définissent une zone, remplie selon la forme."""
        import random as _rnd
        cell  = self._bloc_base_size * self.bloc_scale
        shape = self._bloc_shape    # 0=plein, 1=contour, 2=ligne H, 3=ligne V, 4=terre
        theme = self.bloc_theme

        if self.first_point is None:
            # 1er clic : snap sur grille.
            self.first_point = ((wx // cell) * cell, (wy // cell) * cell)
            if shape == 4:
                self._show_msg("Terre : clic pour le coin opposé")
            elif shape in (2, 3):
                self._show_msg("Blocs : clic pour la fin de la ligne")
            else:
                self._show_msg("Blocs : clic pour le coin opposé")
            return

        # 2e clic : on calcule la zone.
        x1, y1 = self.first_point
        self.first_point = None

        # Snap du 2e point.
        x2 = (wx // cell) * cell
        y2 = (wy // cell) * cell
        x  = min(x1, x2)
        y  = min(y1, y2)
        rw = abs(x2 - x1) + cell
        rh = abs(y2 - y1) + cell

        cols = max(1, rw // cell)
        rows = max(1, rh // cell)

        # Pour les lignes, forcer une seule rangée/colonne.
        if shape == 2:          # Ligne H
            rows = 1
            rh   = cell
        elif shape == 3:        # Ligne V
            cols = 1
            rw   = cell

        self._snapshot()
        count = 0

        # ── Mode Terre (shape 4) : intérieurs uniquement, sans collision ──
        if shape == 4:
            for row in range(rows):
                for col in range(cols):
                    r = _rnd.random()
                    # Raretés : ~8% fossile, ~30% os, reste normal.
                    if r < 0.08:
                        tile_name = f"interieur_fossile_{theme}_{_rnd.randint(1, 3)}.png"
                    elif r < 0.38:
                        tile_name = f"interieur_os_{theme}_{_rnd.randint(1, 3)}.png"
                    else:
                        tile_name = f"interieur_{theme}_{_rnd.randint(1, 3)}.png"
                    chemin = os.path.join(DECORS_DIR, "blocs", tile_name)
                    if not os.path.exists(chemin):
                        continue
                    bx = x + col * cell
                    by = y + row * cell
                    self.decors.append(Decor(bx, by, chemin, f"blocs/{tile_name}",
                                             collision=False,
                                             echelle=self.bloc_scale))
                    count += 1
            self._show_msg(f"Terre : {count} tuiles ({cols}x{rows}) — {theme}")
            return

        # ── Autres modes (plein, contour, lignes) ──
        for row in range(rows):
            for col in range(cols):
                # En mode contour : saute l'intérieur.
                if shape == 1:
                    is_border = (row == 0 or row == rows - 1 or
                                 col == 0 or col == cols - 1)
                    if not is_border:
                        continue

                tile_name = self._get_auto_tile(row, col, rows, cols, theme,
                                                _rnd, shape, self._bloc_facing)
                chemin = os.path.join(DECORS_DIR, "blocs", tile_name)
                if not os.path.exists(chemin):
                    continue
                bx = x + col * cell
                by = y + row * cell
                self.decors.append(Decor(bx, by, chemin, f"blocs/{tile_name}",
                                         collision=True,
                                         echelle=self.bloc_scale))
                count += 1

        shape_name = self._BLOC_SHAPES[shape]
        self._show_msg(f"Blocs : {count} tuiles ({cols}x{rows}) {shape_name} — {theme}")

    def _get_auto_tile(self, row, col, rows, cols, theme, rnd, shape=0, facing=0):
        """Renvoie le nom de fichier de tuile à mettre en (row, col).

        QU'EST-CE QUE L'AUTO-TILING ?
        -----------------------------
        Au lieu d'avoir UNE seule image "bloc" et de la répéter partout,
        on a plusieurs images : "coin haut-gauche", "bord du haut", "intérieur"...
        Cette fonction regarde où se trouve la cellule (row, col) dans le
        rectangle et choisit la bonne.

        SCHÉMA pour un rectangle 4 × 5 cellules (cols × rows) en mode "Plein" :

             col=0   col=1   col=2   col=3
           ┌───────┬───────┬───────┬───────┐
        r=0│ coin  │  sol  │  sol  │ coin  │   ← row=0 = bord du HAUT
           │ G_H   │       │       │ D_H   │     (coin gauche, sol, sol, coin droit)
           ├───────┼───────┼───────┼───────┤
        r=1│ mur D │ inté- │ inté- │ mur G │   ← row intérieure
           │       │ rieur │ rieur │       │     bords latéraux + intérieurs
           ├───────┼───────┼───────┼───────┤
        r=2│ mur D │ inté- │ inté- │ mur G │
           │       │ rieur │ rieur │       │
           ├───────┼───────┼───────┼───────┤
        r=3│ mur D │ inté- │ inté- │ mur G │
           │       │ rieur │ rieur │       │
           ├───────┼───────┼───────┼───────┤
        r=4│ coin  │ plaf  │ plaf  │ coin  │   ← row=rows-1 = bord du BAS
           │ G_B   │       │       │ D_B   │
           └───────┴───────┴───────┴───────┘

        Les variables  is_top / is_bottom / is_left / is_right  encodent ces
        positions, et chaque branche du `if` choisit le nom de fichier correct.

        rnd.randint(1, 3) : il y a 3 variantes pour chaque type (sol_bleu_1.png,
        sol_bleu_2.png, sol_bleu_3.png) → on en pioche une au hasard pour que
        ça ne soit pas trop répétitif visuellement.

        PARAMÈTRES
        ----------
        shape  : 0 = plein, 1 = contour, 2 = ligne H, 3 = ligne V, 4 = terre
        facing : pour shape=1 (contour) → 0 extérieur, 1 intérieur
                 pour shape=3 (ligne V) → 0 mur orienté droite, 1 vers gauche
        """
        is_top    = (row == 0)
        is_bottom = (row == rows - 1)
        is_left   = (col == 0)
        is_right  = (col == cols - 1)

        # ── Ligne V : un seul mur dans la direction choisie ──
        if shape == 3:
            if facing == 0:
                return f"mur_D_{theme}_{rnd.randint(1, 3)}.png"       # Mur → (côté droit visible)
            else:
                return f"mur_G_{theme}_{rnd.randint(1, 3)}.png"       # Mur ← (côté gauche visible)

        # ── Contour intérieur : coins + murs inversés ──
        if shape == 1 and facing == 1:
            if is_top    and is_left:  return f"coin_interieur_D_B_{theme}.png"
            if is_top    and is_right: return f"coin_interieur_G_B_{theme}.png"
            if is_bottom and is_left:  return f"coin_interieur_D_H_{theme}.png"
            if is_bottom and is_right: return f"coin_interieur_G_H_{theme}.png"
            if is_top:    return f"plaf_{theme}_{rnd.randint(1, 3)}.png"
            if is_bottom: return f"sol_{theme}_{rnd.randint(1, 3)}.png"
            if is_left:   return f"mur_G_{theme}_{rnd.randint(1, 3)}.png"
            if is_right:  return f"mur_D_{theme}_{rnd.randint(1, 3)}.png"

        # ── Coins extérieurs ──
        if is_top    and is_left:  return f"coin_G_H_{theme}.png"
        if is_top    and is_right: return f"coin_D_H_{theme}.png"
        if is_bottom and is_left:  return f"coin_G_B_{theme}.png"
        if is_bottom and is_right: return f"coin_D_B_{theme}.png"

        # ── Bords (bord gauche utilise mur_D, bord droit utilise mur_G) ──
        if is_top:    return f"sol_{theme}_{rnd.randint(1, 3)}.png"
        if is_bottom: return f"plaf_{theme}_{rnd.randint(1, 3)}.png"
        if is_left:   return f"mur_D_{theme}_{rnd.randint(1, 3)}.png"
        if is_right:  return f"mur_G_{theme}_{rnd.randint(1, 3)}.png"

        # ── Intérieur avec raretés (~8% fossile, ~30% os, reste normal) ──
        r = rnd.random()
        if r < 0.08:
            return f"interieur_fossile_{theme}_{rnd.randint(1, 3)}.png"
        elif r < 0.38:
            return f"interieur_os_{theme}_{rnd.randint(1, 3)}.png"
        else:
            return f"interieur_{theme}_{rnd.randint(1, 3)}.png"

    def _click_hitbox(self, wx, wy):
        """Mode 7 : 2 clics dans l'aperçu grand format définissent la hitbox."""
        if not self._hb_sprite_list():
            return
        key, file_name = self._hb_current()

        # Charge l'image correspondante (joueur = find_file, ennemi = ENEMIES_DIR).
        try:
            from entities.enemy import ENEMIES_DIR
            if key == PLAYER_KEY:
                path = find_file(file_name)
            else:
                path = os.path.join(ENEMIES_DIR, file_name)
                if os.path.isdir(path):
                    # Sprite animé : on prend la 1re frame.
                    frames = sorted(g for g in os.listdir(path)
                                    if g.endswith((".png", ".jpg")))
                    path = os.path.join(path, frames[0]) if frames else None
                elif not os.path.exists(path):
                    path = find_file(file_name)
            if not path:
                return
            img = pygame.image.load(path)
        except Exception:
            return

        # Coordonnées à l'écran de l'aperçu grand format.
        scale = 4
        sw_i  = img.get_width()  * scale
        sh_i  = img.get_height() * scale
        screen = pygame.display.get_surface()
        sx = (screen.get_width() - sw_i) // 2
        sy = 120

        # Conversion world → écran pour la position du clic.
        mx = int(wx - self.camera.offset_x)
        my = int(wy - self.camera.offset_y)
        # On ne réagit qu'aux clics DANS l'aperçu.
        if not (sx <= mx <= sx + sw_i and sy <= my <= sy + sh_i):
            return

        # Coordonnées dans l'image originale (avant scale).
        rx = (mx - sx) // scale
        ry = (my - sy) // scale
        if self._hb_first_point is None:
            self._hb_first_point = (rx, ry)
        else:
            x1, y1 = self._hb_first_point
            x, y = min(x1, rx), min(y1, ry)
            w, h = abs(rx - x1), abs(ry - y1)
            self._hb_first_point = None
            if w > 1 and h > 1:
                set_hitbox(key, w, h, x, y)

    # ═════════════════════════════════════════════════════════════════════════
    # 11.  APERÇUS (preview sous le curseur)
    # ═════════════════════════════════════════════════════════════════════════

    def draw_preview(self, surf, mouse_pos):
        """Aperçu de l'action en cours sous le curseur."""
        # Modes qui dessinent un rectangle 2 points.
        if self.mode in (0, 4, 5, 7, 8, 12, 13):
            colors = {
                0: (100, 200, 255), 4: (0, 120, 255), 5: (180, 180, 180),
                7: (255, 80, 80),   8: (255, 200, 0), 
                12: (200, 100, 255), 13: (255, 0, 0)
            }
            if self.first_point:
                wx = int(mouse_pos[0] + self.camera.offset_x)
                wy = int(mouse_pos[1] + self.camera.offset_y)
                x = min(self.first_point[0], wx) - int(self.camera.offset_x)
                y = min(self.first_point[1], wy) - int(self.camera.offset_y)
                
                pygame.draw.rect(surf, colors.get(self.mode, (255, 255, 255)),
                                 (x, y,
                                  abs(wx - self.first_point[0]),
                                  abs(wy - self.first_point[1])), 2)

        # Mode lumière : cercle.
        elif self.mode == 2:
            if self.light_first_point is None:
                pygame.draw.circle(surf, (255, 200, 0), mouse_pos, 5)
            else:
                cx = int(self.light_first_point[0] - self.camera.offset_x)
                cy = int(self.light_first_point[1] - self.camera.offset_y)
                r = int(((mouse_pos[0] - cx) ** 2 + (mouse_pos[1] - cy) ** 2) ** 0.5)
                pygame.draw.circle(surf, (255, 200, 0), (cx, cy), r, 2)
                pygame.draw.circle(surf, (255, 200, 0), (cx, cy), 5)

        # Mode spawn : un petit cercle bleu.
        elif self.mode == 3:
            pygame.draw.circle(surf, (0, 150, 255), mouse_pos, 8, 2)

        # Mode 1 en sous-mode patrouille.
        elif self.mode == 1 and self.mob_patrol_mode:
            if self._patrol_target:
                pygame.draw.rect(surf, (255, 200, 0),
                                 self.camera.apply(self._patrol_target.rect), 3)
            if self._patrol_first_x is not None:
                lx = int(self._patrol_first_x - self.camera.offset_x)
                h  = surf.get_height()
                pygame.draw.line(surf, (0, 200, 0), (lx, 0), (lx, h), 2)
                pygame.draw.line(surf, (0, 200, 0),
                                 (lx, mouse_pos[1]), (mouse_pos[0], mouse_pos[1]), 1)
                pygame.draw.line(surf, (0, 200, 0),
                                 (mouse_pos[0], 0), (mouse_pos[0], h), 1)

        # Mode 1 en sous-mode détection.
        elif self.mode == 1 and self.mob_detect_mode:
            if self._detect_target:
                pygame.draw.rect(surf, (255, 100, 0),
                                 self.camera.apply(self._detect_target.rect), 3)
                dr = self.camera.apply(self._detect_target._detect_rect())
                pygame.draw.rect(surf, (255, 255, 0), dr, 2)
                font = self._get_font()
                surf.blit(font.render(
                    f"Portee:{self._detect_target.detect_range} "
                    f"Dir:{'D' if self._detect_target.direction > 0 else 'G'} "
                    f"Jump:{self._detect_target.jump_power}",
                    True, (255, 255, 0)), (dr.x, dr.y - 18))

        # Modes avec leur propre méthode d'aperçu.
        elif self.mode == 6:
            self._draw_hitbox_editor(surf, mouse_pos)
        
        # Note : On utilise des 'if' ici car certains modes peuvent se chevaucher 
        # ou avoir des comportements spécifiques (comme le mode 8 copier/coller).
        if self.mode == 8:
            self._draw_copy_paste_preview(surf, mouse_pos)
        if self.mode == 9:
            self._draw_decor_preview(surf, mouse_pos)
        if self.mode == 10:
            self._draw_pnj_preview(surf, mouse_pos)
        if self.mode == 11:
            self._draw_bloc_preview(surf, mouse_pos)

    def _draw_hitbox_editor(self, surf, mouse_pos):
        """Affiche l'image zoomée + la hitbox courante (mode 7)."""
        font = self._get_font()
        if not self._hb_sprite_list():
            return
        key, file_name = self._hb_current()

        # Charge l'image (même logique que _click_hitbox).
        try:
            from entities.enemy import ENEMIES_DIR
            if key == PLAYER_KEY:
                path = find_file(file_name)
            else:
                path = os.path.join(ENEMIES_DIR, file_name)
                if os.path.isdir(path):
                    frames = sorted(g for g in os.listdir(path)
                                    if g.endswith((".png", ".jpg")))
                    path = os.path.join(path, frames[0]) if frames else None
                elif not os.path.exists(path):
                    path = find_file(file_name)
            if not path:
                raise FileNotFoundError
            img = pygame.image.load(path)
        except Exception:
            label = "JOUEUR" if key == PLAYER_KEY else file_name
            surf.blit(font.render(f"Sprite introuvable:{label}",
                                  True, (255, 0, 0)), (10, 130))
            return

        # Affichage zoomé x4 centré.
        scale = 4
        sw_i  = img.get_width()  * scale
        sh_i  = img.get_height() * scale
        sx = (surf.get_width() - sw_i) // 2
        sy = 120

        # Fond sombre derrière l'image.
        bg_r = pygame.Rect(sx - 10, sy - 10, sw_i + 20, sh_i + 20)
        pygame.draw.rect(surf, (20, 10, 30),      bg_r)
        pygame.draw.rect(surf, (100, 100, 100),   bg_r, 1)
        surf.blit(pygame.transform.scale(img, (sw_i, sh_i)), (sx, sy))

        # Hitbox actuelle en vert.
        hb = get_hitbox(key) if key != PLAYER_KEY else get_player_hitbox()
        pygame.draw.rect(surf, (0, 255, 0),
                         pygame.Rect(sx + hb["ox"] * scale,
                                     sy + hb["oy"] * scale,
                                     hb["w"]  * scale,
                                     hb["h"]  * scale), 2)
        surf.blit(font.render(
            f"Actuel:{hb['w']}x{hb['h']} off({hb['ox']},{hb['oy']})",
            True, (0, 255, 0)), (sx, sy + sh_i + 8))

        # Rectangle en cours de tracé (entre 1er clic et position actuelle).
        if self._hb_first_point:
            p1sx = sx + self._hb_first_point[0] * scale
            p1sy = sy + self._hb_first_point[1] * scale
            mx, my = mouse_pos
            if sx <= mx <= sx + sw_i and sy <= my <= sy + sh_i:
                rx, ry = min(p1sx, mx), min(p1sy, my)
                rw, rh = abs(mx - p1sx), abs(my - p1sy)
                pygame.draw.rect(surf, (255, 0, 0), (rx, ry, rw, rh), 2)
                surf.blit(font.render(f"{rw // scale}x{rh // scale}",
                                      True, (255, 0, 0)),
                          (rx + rw + 5, ry + rh + 2))

        label = "JOUEUR" if key == PLAYER_KEY else file_name
        surf.blit(font.render(f"[T]:{label}  Clic=hitbox", True, (200, 200, 200)),
                  (sx, sy + sh_i + 28))

    def _draw_copy_paste_preview(self, surf, mouse_pos):
        """Mode 8 : affiche la zone copiée + l'aperçu du collage."""
        font = self._get_font()
        if self._copy_rect:
            sr = pygame.Rect(
                self._copy_rect.x - int(self.camera.offset_x),
                self._copy_rect.y - int(self.camera.offset_y),
                self._copy_rect.w, self._copy_rect.h,
            )
            pygame.draw.rect(surf, (255, 200, 0), sr, 2)
            surf.blit(font.render("COPIE", True, (255, 200, 0)), (sr.x, sr.y - 18))

        if self._has_clipboard:
            wx = int(mouse_pos[0] + self.camera.offset_x)
            wy = int(mouse_pos[1] + self.camera.offset_y)
            for rel in self._clipboard_platforms:
                pygame.draw.rect(surf, (100, 200, 255),
                                 pygame.Rect(wx + rel.x - int(self.camera.offset_x),
                                             wy + rel.y - int(self.camera.offset_y),
                                             rel.w, rel.h), 1)
            for rel in self._clipboard_walls:
                pygame.draw.rect(surf, (180, 180, 180),
                                 pygame.Rect(wx + rel.x - int(self.camera.offset_x),
                                             wy + rel.y - int(self.camera.offset_y),
                                             rel.w, rel.h), 1)

    def _draw_decor_preview(self, surf, mouse_pos):
        """Mode 9 : image du décor semi-transparente sous le curseur."""
        font = self._get_font()
        sprites = self._decor_sprites_filtrés()
        if not sprites:
            return
        nom = sprites[self.decor_sprite_index % len(sprites)]
        chemin = os.path.join(DECORS_DIR, nom)
        try:
            img = pygame.image.load(chemin)
        except Exception:
            return

        # Appliquer l'échelle courante.
        if self.decor_echelle != 1.0:
            w = max(1, int(img.get_width()  * self.decor_echelle))
            h = max(1, int(img.get_height() * self.decor_echelle))
            img = pygame.transform.scale(img, (w, h))

        # Sous-mode Hitbox : montre le décor sélectionné.
        if getattr(self, '_decor_hb_mode', False):
            coul = (255, 0, 0)
            if self._decor_hb_target:
                dr = self.camera.apply(self._decor_hb_target.rect)
                pygame.draw.rect(surf, (255, 255, 0), dr, 2)
                if self._decor_hb_first:
                    fx = int(self._decor_hb_first[0] - self.camera.offset_x)
                    fy = int(self._decor_hb_first[1] - self.camera.offset_y)
                    rw = abs(mouse_pos[0] - fx)
                    rh = abs(mouse_pos[1] - fy)
                    rx = min(fx, mouse_pos[0])
                    ry = min(fy, mouse_pos[1])
                    pygame.draw.rect(surf, (255, 0, 0), (rx, ry, rw, rh), 2)
            surf.blit(font.render(
                "[Y] Hitbox mode — clic=sélectionner décor puis 2 clics",
                True, coul), (10, surf.get_height() - 50))
            return

        # Sous-mode Remplissage : rectangle de preview + grille.
        if self.decor_fill_mode and self.first_point:
            wx = int(mouse_pos[0] + self.camera.offset_x)
            wy = int(mouse_pos[1] + self.camera.offset_y)
            x1, y1 = self.first_point
            x, y = min(x1, wx), min(y1, wy)
            rw_f, rh_f = abs(wx - x1), abs(wy - y1)
            sx = int(x - self.camera.offset_x)
            sy = int(y - self.camera.offset_y)
            pygame.draw.rect(surf, (0, 255, 200), (sx, sy, rw_f, rh_f), 2)

            # Grille de tuiles en alpha 60 (aperçu du remplissage).
            tw, th = img.get_width(), img.get_height()
            count = 0
            cy = sy
            while cy < sy + rh_f:
                cx = sx
                while cx < sx + rw_f:
                    s = img.copy()
                    s.set_alpha(60)
                    surf.blit(s, (cx, cy))
                    count += 1
                    cx += tw
                cy += th
            surf.blit(font.render(f"REMPLISSAGE : {count} tuiles",
                                  True, (0, 255, 200)), (sx, sy - 18))
            return

        # Aperçu normal : image semi-transparente.
        s = img.copy()
        s.set_alpha(140)
        surf.blit(s, (mouse_pos[0], mouse_pos[1]))
        coul = (255, 100, 0) if self.decor_collision else (0, 220, 100)
        fill_txt = "  [F]REMPLISSAGE" if self.decor_fill_mode else ""
        surf.blit(font.render(
            f"[T] {nom}  x{self.decor_echelle}  "
            f"[C] collision:{self.decor_collision}{fill_txt}",
            True, coul), (mouse_pos[0] + 4, mouse_pos[1] - 18))

    def _draw_pnj_preview(self, surf, mouse_pos):
        """Mode 10 : sprite PNJ semi-transparent sous le curseur."""
        font = self._get_font()
        from entities.npc import PNJ_DIR

        # Quel sprite afficher ?
        reg = self._pnj_reg_courant()
        sprite_nom = None
        label = ""
        if reg:
            sprite_nom = reg.get("sprite_name")
            label      = reg["nom"]
        elif self._pnj_sprites:
            sprite_nom = self._pnj_sprites[self._pnj_sprite_index % len(self._pnj_sprites)]
            label      = "+ Nouveau"

        # Charger l'image (gère fichier simple ou dossier animé).
        img = None
        if sprite_nom:
            chemin = os.path.join(PNJ_DIR, sprite_nom)
            try:
                if os.path.isdir(chemin):
                    frames = sorted(g for g in os.listdir(chemin)
                                    if g.endswith((".png", ".jpg")))
                    img = pygame.image.load(os.path.join(chemin, frames[0])) if frames else None
                else:
                    img = pygame.image.load(chemin)
            except Exception:
                pass

        if img:
            s = img.copy()
            s.set_alpha(140)
            surf.blit(s, mouse_pos)
        else:
            # Fallback : rectangle violet.
            r = pygame.Rect(mouse_pos[0], mouse_pos[1], 34, 54)
            s = pygame.Surface((34, 54), pygame.SRCALPHA)
            s.fill((180, 160, 230, 120))
            surf.blit(s, r)
            pygame.draw.rect(surf, (255, 255, 255), r, 1)

        surf.blit(font.render(label, True, (190, 175, 240)),
                  (mouse_pos[0] + 4, mouse_pos[1] - 18))

    def _draw_bloc_preview(self, surf, mouse_pos):
        """Mode 11 : aperçu de la grille de blocs qui sera remplie."""
        font = self._get_font()
        cell = self._bloc_base_size * self.bloc_scale

        if self.first_point:
            # 1er clic déjà posé : dessine le rectangle de preview.
            wx = int(mouse_pos[0] + self.camera.offset_x)
            wy = int(mouse_pos[1] + self.camera.offset_y)
            x1, y1 = self.first_point
            # Snap sur grille.
            x2 = (wx // cell) * cell
            y2 = (wy // cell) * cell
            x  = min(x1, x2)
            y  = min(y1, y2)
            rw = abs(x2 - x1) + cell
            rh = abs(y2 - y1) + cell
            cols = max(1, rw // cell)
            rows = max(1, rh // cell)

            sx = int(x - self.camera.offset_x)
            sy = int(y - self.camera.offset_y)
            shape = self._bloc_shape

            # Ajuster pour les modes ligne.
            draw_cols, draw_rows = cols, rows
            draw_rw,   draw_rh   = rw, rh
            if shape == 2:          # Ligne H
                draw_rows = 1
                draw_rh   = cell
            elif shape == 3:        # Ligne V
                draw_cols = 1
                draw_rw   = cell

            # Contour bleu.
            pygame.draw.rect(surf, (0, 200, 255), (sx, sy, draw_rw, draw_rh), 2)

            # Chaque cellule (filtrée si contour).
            for r in range(draw_rows):
                for c in range(draw_cols):
                    cx = sx + c * cell
                    cy = sy + r * cell
                    if shape == 1:  # Contour : n'affiche que le pourtour
                        is_border = (r == 0 or r == draw_rows - 1 or
                                     c == 0 or c == draw_cols - 1)
                        if is_border:
                            pygame.draw.rect(surf, (0, 200, 255),
                                             (cx, cy, cell, cell), 1)
                    else:
                        pygame.draw.rect(surf, (0, 200, 255),
                                         (cx, cy, cell, cell), 1)

            surf.blit(font.render(f"{draw_cols}x{draw_rows} {self._BLOC_SHAPES[shape]}",
                                  True, (0, 200, 255)), (sx, sy - 18))
        else:
            # Pas encore de 1er clic : un carré au curseur.
            pygame.draw.rect(surf, (0, 200, 255),
                             (mouse_pos[0], mouse_pos[1], cell, cell), 2)

        # Infobulle : thème, taille, forme, sens.
        coul = (100, 160, 255) if self.bloc_theme == "bleu" else (100, 220, 100)
        shape_name   = self._BLOC_SHAPES[self._bloc_shape]
        facing_label = self._BLOC_FACINGS[self._bloc_shape][self._bloc_facing]
        facing_txt   = f"  {facing_label}" if facing_label != "—" else ""
        surf.blit(font.render(
            f"{self.bloc_theme}  {self._bloc_base_size * self.bloc_scale}px  "
            f"{shape_name}{facing_txt}",
            True, coul), (mouse_pos[0] + 4, mouse_pos[1] - 18))

    # ═════════════════════════════════════════════════════════════════════════
    # 12.  OVERLAYS & HUD (barre du haut, spawn, portails, messages)
    # ═════════════════════════════════════════════════════════════════════════

    def draw_overlays(self, surf):
        """Cercle bleu SPAWN + portails (dans le monde)."""
        font = self._get_font()
        sx = int(self.spawn_x - self.camera.offset_x)
        sy = int(self.spawn_y - self.camera.offset_y)
        pygame.draw.circle(surf, (0, 150, 255), (sx, sy), 8, 2)
        surf.blit(font.render("SPAWN", True, (0, 150, 255)),
                  (sx - font.size("SPAWN")[0] // 2, sy - 22))
        for portal in self.portals:
            portal.draw(surf, self.camera, font)
        for zone in self.trigger_zones:
            zone.draw_debug(surf, self.camera, font)

        #dessine les zones de danger (je t'ai mis max de com pour comprendre Julien)
        for zone in self.danger_zones:
            # On récupère les données du dictionnaire
            rect_objet = zone["rect"]
            respawn_pt = zone["respawn_pos"]

            # 1. Dessin du rectangle rouge (mort)
            draw_rect = self.camera.apply(rect_objet)
            s = pygame.Surface((draw_rect.width, draw_rect.height), pygame.SRCALPHA)
            s.fill((255, 0, 0, 80)) 
            surf.blit(s, (draw_rect.x, draw_rect.y))
            pygame.draw.rect(surf, (255, 0, 0), draw_rect, 1)

            # 2. Dessin du point de respawn (petit cercle vert)
            # on applique l'offset caméra manuellement car c'est un point (x, y)
            rx = int(respawn_pt[0] - self.camera.offset_x)
            ry = int(respawn_pt[1] - self.camera.offset_y)
            pygame.draw.circle(surf, (0, 255, 100), (rx, ry), 6)
            pygame.draw.circle(surf, (255, 255, 255), (rx, ry), 6, 1) # Contour blanc pour le voir partout

            # 3. ligne de liaison (pour savoir quel point va avec quel bloc)
            pygame.draw.line(surf, (255, 255, 255), draw_rect.center, (rx, ry), 1)

        # ── Spawns nommés (visible TOUT LE TEMPS pour pouvoir les
        #    retrouver, mais plus voyant en mode 14 dédié) ─────────────
        if self.named_spawns:
            font_small = self._font_small if hasattr(self, "_font_small") else None
            actif = (self.mode == 14)
            for nom, (sx, sy) in self.named_spawns.items():
                cx = int(sx - self.camera.offset_x)
                cy = int(sy - self.camera.offset_y)
                couleur = (60, 220, 255) if actif else (60, 220, 255, 120)
                # Petit cercle bleu ciel + croix au centre.
                pygame.draw.circle(surf, (60, 220, 255), (cx, cy), 8, 2)
                pygame.draw.line(surf, (60, 220, 255), (cx-4, cy), (cx+4, cy), 1)
                pygame.draw.line(surf, (60, 220, 255), (cx, cy-4), (cx, cy+4), 1)
                if font_small and actif:
                    label = font_small.render(nom, True, (60, 220, 255))
                    surf.blit(label, (cx - label.get_width() // 2, cy + 12))

        # ── Points de sauvegarde sur les décors (étoile dorée) ─────────
        # Marqueur visible TOUT LE TEMPS dans l'éditeur pour qu'on
        # repère d'un coup d'œil les décors qui servent de save point
        # (toggle via touche dédiée en mode décor : cf. ligne 1082).
        for d in self.decors:
            if not getattr(d, "is_save_point", False):
                continue
            r = self.camera.apply(d.rect)
            cx, cy = r.centerx, r.top - 10
            # Étoile dorée à 5 branches.
            import math as _m
            pts = []
            for i in range(10):
                ang = -_m.pi / 2 + i * _m.pi / 5
                rr  = 9 if i % 2 == 0 else 4
                pts.append((cx + rr * _m.cos(ang), cy + rr * _m.sin(ang)))
            pygame.draw.polygon(surf, (255, 215, 70), pts)
            pygame.draw.polygon(surf, (90, 60, 0), pts, 1)

    def draw_hud(self, surf, dt=0.016):
        """Bandeau d'information en haut + message éphémère en bas."""
        font  = self._get_font()
        small = self._font_small
        w     = surf.get_width()
        sh    = surf.get_height()

        # Décrémente les timers.
        if self._hud_msg_timer > 0:
            self._hud_msg_timer = max(0.0, self._hud_msg_timer - dt)
        if self._restore_confirm_timer > 0:
            self._restore_confirm_timer = max(0.0, self._restore_confirm_timer - dt)
            if self._restore_confirm_timer <= 0 and self._restore_confirm:
                self._restore_confirm = False
                self._show_msg("Restauration annulée (délai expiré)")

        # Popup texte par-dessus tout : prend la main.
        if self._text_mode:
            self._draw_text_box(surf)
            return

        # Bandeau semi-transparent.
        panel = pygame.Surface((w, 90), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 180))
        surf.blit(panel, (0, 0))

        # Ligne 1 : mode + phase.
        phase_color = (255, 120, 40) if self.has_holes else (0, 255, 120)
        phase_label = "PHASE 2 — trous" if self.has_holes else "PHASE 1 — structure"
        surf.blit(font.render(
            f"EDITEUR [{self.mode + 1}/{len(self._mode_names)}] {self._mode_names[self.mode]}"
            f"{'  [Hitbox]' if self.show_hitboxes else ''}  |  {phase_label}",
            True, phase_color), (10, 6))

        # Infos de taille à droite. Maj+←/→ déplacent le mur GAUCHE
        # (= SCENE_LEFT, peut être négatif). ←/→ seuls déplacent le DROIT.
        info = (f"Sol:{settings.GROUND_Y} Plaf:{settings.CEILING_Y} "
                f"X:[{settings.SCENE_LEFT},{settings.SCENE_WIDTH}] "
                f"Cam:{self.camera.y_offset}")
        surf.blit(small.render(info, True, (255, 255, 0)),
                  (w - small.size(info)[0] - 10, 6))

        # Ligne 2 : contexte du mode actif.
        y2 = 28
        if   self.mode == 0:
            surf.blit(font.render(
                "Clic G x2=rect | Clic D=suppr | [Ctrl+Z]=annuler",
                True, (200, 200, 255)), (10, y2))

        elif self.mode == 1:
            # Un code couleur ON/OFF pour chaque flag.
            gc  = (0, 255, 0) if self.mob_gravity            else (255, 80, 80)
            cc  = (0, 255, 0) if self.mob_collision           else (255, 80, 80)
            jc  = (0, 255, 0) if self.mob_can_jump            else (255, 80, 80)
            vpc = (0, 255, 0) if self.mob_can_jump_patrol     else (255, 80, 80)
            lc  = (0, 255, 0) if self.mob_has_light           else (255, 80, 80)
            oc  = (0, 255, 0) if self.mob_can_fall_in_holes   else (255, 80, 80)
            uc  = (0, 255, 0) if self.mob_can_turn_randomly   else (255, 80, 80)
            rt  = f"{self.mob_respawn_timeout:.0f}s" if self.mob_respawn_timeout > 0 else "OFF"
            surf.blit(font.render(f"[G]:{self.mob_gravity}",              True, gc),  (10,  y2))
            surf.blit(font.render(f"[C]:{self.mob_collision}",            True, cc),  (120, y2))
            surf.blit(font.render(f"[J]:{self.mob_can_jump}",             True, jc),  (240, y2))
            surf.blit(font.render(f"[V]patr:{self.mob_can_jump_patrol}",  True, vpc), (360, y2))
            surf.blit(font.render(f"[I]:{self.mob_has_light}",            True, lc),  (530, y2))
            surf.blit(font.render(f"[O]Trou:{self.mob_can_fall_in_holes}",True, oc),  (640, y2))
            surf.blit(font.render(f"[U]Rand:{self.mob_can_turn_randomly}",True, uc),  (810, y2))
            surf.blit(small.render(
                f"[T]:{self._current_sprite()}  Det:{self.mob_detect_range}  "
                f"[*/÷]Resp:{rt}  [PgUp/Dn]Jump:{self.mob_jump_power}",
                True, (200, 200, 255)), (10, 50))

            # Statut du sous-mode (patrouille/détection) au milieu.
            if self.mob_patrol_mode:
                ptxt = ("[P] ON: clic sur mob" if self._patrol_target is None else
                        "[P] clic=limite G"    if self._patrol_first_x is None else
                        f"[P] clic=limite D (G={self._patrol_first_x})")
                surf.blit(small.render(ptxt, True, (255, 200, 0)), (500, 50))
            elif self.mob_detect_mode:
                dtxt = ("[D] ON: clic sur mob" if self._detect_target is None else
                        f"[D] portee={self._detect_target.detect_range} [+/-]  "
                        f"jump={self._detect_target.jump_power} [PgUp/Dn]")
                surf.blit(small.render(dtxt, True, (255, 150, 0)), (500, 50))
            else:
                surf.blit(small.render("[P]atrouille [D]etection",
                                       True, (140, 140, 140)), (500, 50))

        elif self.mode == 2:
            surf.blit(font.render(
                f"[T]{LIGHT_TYPES[self.light_type_index]} "
                f"[F]{'ON' if self.light_flicker else 'OFF'} "
                f"Spd:{self.light_flicker_speed}",
                True, (255, 200, 100)), (10, y2))

        elif self.mode == 3:
            surf.blit(font.render(
                f"Clic=spawn [R]espawn [Ctrl+B]reset ({self.spawn_x},{self.spawn_y})",
                True, (100, 200, 255)), (10, y2))

        elif self.mode == 4:
            surf.blit(font.render(
                f"Clic G x2=portail | Clic D=suppr | {len(self.portals)}",
                True, (0, 180, 255)), (10, y2))

        elif self.mode == 5:
            surf.blit(font.render(
                f"Clic G x2=mur | Clic D=suppr | {len(self.custom_walls)}",
                True, (180, 180, 180)), (10, y2))

        elif self.mode == 6:
            key, file_name = (self._hb_current() if self._hb_sprite_list()
                              else (PLAYER_KEY, "?"))
            label = "JOUEUR" if key == PLAYER_KEY else file_name
            hbd = get_player_hitbox() if key == PLAYER_KEY else get_hitbox(key)
            surf.blit(font.render(
                f"[T]:{label} | Clic x2=hitbox | {hbd['w']}x{hbd['h']}",
                True, (255, 100, 100)), (10, y2))

        elif self.mode == 7:
            restores = self._list_restore_points()
            rinfo = f"dernier: {restores[-1]}" if restores else "aucun"
            surf.blit(font.render(
                f"Clic G x2=trou permanent | [Ctrl+Z]=annuler | "
                f"{len(self.holes)} trou(s) | restore: {rinfo}",
                True, (255, 80, 80)), (10, y2))

        elif self.mode == 8:
            if not self._has_clipboard:
                txt = ("[C]=copier | Clic D=effacer" if self._copy_rect
                       else "Clic G x2=zone | [C]=copier")
                surf.blit(font.render(txt, True, (255, 200, 0)), (10, y2))
            else:
                nb = len(self._clipboard_platforms) + len(self._clipboard_walls)
                surf.blit(font.render(
                    f"Clipboard:{nb} | Clic=coller | Clic D=effacer",
                    True, (255, 200, 0)), (10, y2))

        elif self.mode == 9:
            _spr = self._decor_sprites_filtrés()
            nom = _spr[self.decor_sprite_index % len(_spr)] if _spr else "—"
            cc = (255, 100, 0) if self.decor_collision else (0, 220, 100)
            fill_txt = " [F]REMPLISSAGE" if self.decor_fill_mode else ""
            cat_txt = (self._decor_categories[self._decor_cat_index]
                       if self._decor_cat_index >= 0 and self._decor_categories
                       else "TOUTES")
            surf.blit(font.render(
                f"[G]:{cat_txt}  [T]:{nom}  [C]coll:{self.decor_collision}  "
                f"x{self.decor_echelle}  [Y]hitbox  [X]reset{fill_txt}",
                True, cc), (10, y2))

        elif self.mode == 10:
            reg = self._pnj_reg_courant()
            if reg:
                perso = reg["nom"]
            elif self._pnj_sprites:
                perso = f"+ Nouveau ({self._pnj_sprites[self._pnj_sprite_index % len(self._pnj_sprites)]})"
            else:
                perso = "+ Nouveau (pas de sprite)"
            surf.blit(font.render(
                f"[T]:{perso}  [G]sprite  [D]dialogue  [W]mode  ({len(self.pnjs)} PNJ)",
                True, (190, 175, 240)), (10, y2))

        elif self.mode == 12:
            surf.blit(font.render(
                f"Clic G x2=zone | Clic D=suppr | [R]=régler | [F2]=cinéma | {len(self.trigger_zones)} trigger(s)",
                True, (240, 200, 80)), (10, y2))

        elif self.mode == 11:
            coul = (100, 160, 255) if self.bloc_theme == "bleu" else (100, 220, 100)
            px = self._bloc_base_size * self.bloc_scale
            shape_name   = self._BLOC_SHAPES[self._bloc_shape]
            facing_label = self._BLOC_FACINGS[self._bloc_shape][self._bloc_facing]
            facing_txt   = f"  [V]:{facing_label}" if facing_label != "—" else ""
            surf.blit(font.render(
                f"[T]hème:{self.bloc_theme}  [F]orme:{shape_name}{facing_txt}  "
                f"{px}px  Clic x2  Clic D=suppr  Molette=taille",
                True, coul), (10, y2))

        # Ligne 3 : raccourcis globaux.
        carte_info = f" | carte: {self._nom_carte}" if self._nom_carte else ""
        cam_info   = "  [F5]CAM LIBRE" if not self.camera.free_mode else ""
        surf.blit(small.render(
            f"[M]ode [H]itbox [N]ew [S]ave [L]oad [I]mportTiled [K]carte_debut "
            f"[Ctrl+Z]annuler [Ctrl+R]restaurer{cam_info}{carte_info}",
            True, (140, 140, 140)), (10, 70))

        # Indicateur caméra libre.
        if self.camera.free_mode:
            cam_txt  = "CAM LIBRE — Molette↕ Clic molette=glisser [F5]=retour"
            cam_surf = font.render(cam_txt, True, (255, 200, 50))
            surf.blit(cam_surf, (w - cam_surf.get_width() - 10, 70))

        # Message éphémère (boîte centrée en bas).
        if self._hud_msg and self._hud_msg_timer > 0:
            if self._restore_confirm:
                mc = (255, 100, 0)
            elif "restaur" in self._hud_msg or "Annulé" in self._hud_msg:
                mc = (255, 200, 0)
            elif "verrouillée" in self._hud_msg:
                mc = (255, 80, 80)
            else:
                mc = (180, 255, 180)
            msg_surf = small.render(self._hud_msg, True, mc)
            mw = msg_surf.get_width() + 20
            mh = msg_surf.get_height() + 10
            bg = pygame.Surface((mw, mh), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 190))
            bx = (w - mw) // 2
            by = sh - 48
            surf.blit(bg,       (bx, by))
            surf.blit(msg_surf, (bx + 10, by + 5))

    def _draw_text_box(self, surf):
        """Popup centrale de saisie de texte.

        Le prompt est wrappé sur plusieurs lignes si nécessaire, pour gérer
        les listes de maps longues qui débordaient avant."""
        font  = self._get_font()
        w, h  = surf.get_size()
        # Voile noir semi-transparent derrière la popup.
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surf.blit(overlay, (0, 0))

        # Boîte plus large pour mieux accueillir les longues listes.
        bw = min(w - 80, 800)
        max_text_w = bw - 30

        # Word-wrap du prompt
        lignes = self._wrap_text(self._text_prompt, font, max_text_w)
        # On limite à 6 lignes max pour éviter une popup géante
        if len(lignes) > 6:
            lignes = lignes[:6]
            lignes[-1] = lignes[-1].rstrip(",") + " …"

        # Hauteur dynamique
        line_h = font.get_height() + 4
        bh = 30 + line_h * len(lignes) + 30 + 30  # prompt + saisie + aide
        bx, by = (w - bw) // 2, (h - bh) // 2
        pygame.draw.rect(surf, (30, 20, 40), (bx, by, bw, bh))
        pygame.draw.rect(surf, (100, 200, 255), (bx, by, bw, bh), 2)

        # Prompt sur plusieurs lignes
        y = by + 15
        for ligne in lignes:
            surf.blit(font.render(ligne, True, (200, 200, 255)), (bx + 15, y))
            y += line_h

        y += 6
        surf.blit(font.render(self._text_input + "_", True, (255, 255, 255)),
                  (bx + 15, y))
        y += line_h + 6
        surf.blit(font.render("[Entrée]=valider  [Échap]=annuler",
                              True, (140, 140, 140)), (bx + 15, y))

    def _wrap_text(self, text, font, max_width):
        """Word-wrap simple : casse aux espaces. Renvoie liste de lignes."""
        if not text:
            return [""]
        mots = text.split(" ")
        lignes = []
        courante = ""
        for mot in mots:
            essai = (courante + " " + mot) if courante else mot
            if font.size(essai)[0] <= max_width:
                courante = essai
            else:
                if courante:
                    lignes.append(courante)
                # Si le mot seul dépasse → on le force quand même
                courante = mot
        if courante:
            lignes.append(courante)
        return lignes

    # ═════════════════════════════════════════════════════════════════════════
    # 13.  SAUVEGARDE / CHARGEMENT (JSON → disque et inverse)
    # ═════════════════════════════════════════════════════════════════════════
    #
    # SCHÉMA DU FLUX (sauvegarde → fichier → chargement) :
    #
    #     OBJETS PYTHON              DICT PYTHON              FICHIER JSON
    #     (Plateforme,        →      {"x": 100,         →     {"x": 100,
    #      Enemy, Decor,              "y": 200,                "y": 200,
    #      Portal, ...)               "type": "..."}           "type": "..."}
    #
    #   _build_save_data()           json.dump()               maps/ma_map.json
    #
    # Et le retour (chargement) parcourt le chemin INVERSE :
    #
    #     FICHIER JSON              DICT PYTHON               OBJETS PYTHON
    #     {"x": 100, ...}    →      {"x": 100, ...}    →     Plateforme(100, ...)
    #                                                         Enemy(...)
    #                                                         Decor(...)
    #
    #   json.load()                _apply_state()
    #
    # Donc : _build_save_data() et _apply_state() sont DEUX FONCTIONS
    # SYMÉTRIQUES — si on ajoute une nouvelle clé dans l'une, il faut
    # l'ajouter dans l'autre, sinon les vieilles maps ne se relisent plus
    # correctement.

    def _save_to(self, fp):
        """Écrit les données dans un chemin de fichier."""
        data = self._build_save_data()
        with open(fp, "w") as f:
            json.dump(data, f, indent=2)

    def _build_save_data(self):
        """Construit le dict complet de sauvegarde (toutes les clés)."""
        return {
            "ground_y":        settings.GROUND_Y,
            "ceiling_y":       settings.CEILING_Y,
            "scene_width":     settings.SCENE_WIDTH,
            "scene_left":      settings.SCENE_LEFT,
            "camera_y_offset": self.camera.y_offset,
            "camera_zoom":     getattr(self.camera, "zoom", 1.0),
            "player_scale":    getattr(settings, "PLAYER_SCALE", 1.0),
            "spawn":           {"x": self.spawn_x, "y": self.spawn_y},
            # Spawns NOMMÉS placés dans le mode 14 "Spawn nommé".
            # Format : { "nom": [x, y] }. Lus dans _apply_state.
            # Utilisés par les portails via la syntaxe "mapname spawnname".
            "named_spawns":    dict(getattr(self, "named_spawns", {})),
            "bg_color":        self.bg_color,
            "wall_color":      self.wall_color,
            "platforms": [{"x": p.rect.x, "y": p.rect.y,
                           "w": p.rect.width, "h": p.rect.height}
                          for p in self.platforms],
            "custom_walls": [{"x": w.rect.x, "y": w.rect.y,
                              "w": w.rect.width, "h": w.rect.height}
                             for w in self.custom_walls],
            "ground_segments":  [{"x": w.rect.x, "y": w.rect.y,
                                  "w": w.rect.width, "h": w.rect.height}
                                 for w in self.ground_segments],
            "ceiling_segments": [{"x": w.rect.x, "y": w.rect.y,
                                  "w": w.rect.width, "h": w.rect.height}
                                 for w in self.ceiling_segments],
            "left_segments":    [{"x": w.rect.x, "y": w.rect.y,
                                  "w": w.rect.width, "h": w.rect.height}
                                 for w in self.left_segments],
            "right_segments":   [{"x": w.rect.x, "y": w.rect.y,
                                  "w": w.rect.width, "h": w.rect.height}
                                 for w in self.right_segments],
            "holes": [{"x": h.x, "y": h.y, "w": h.width, "h": h.height}
                      for h in self.holes],
            "enemies": [e.to_dict() for e in self.enemies],
            "lights":  [{"x": l["x"], "y": l["y"],
                         "radius": l["radius"], "type": l["type"],
                         "flicker": l["flicker"],
                         "flicker_speed": l["flicker_speed"]}
                        for l in self.lighting.lights
                        if not l.get("_enemy_light")],
            "portals":       [p.to_dict() for p in self.portals],
            "decors":        [d.to_dict() for d in self.decors],
            "pnjs":          [p.to_dict() for p in self.pnjs],
            "trigger_zones": [z.to_dict() for z in self.trigger_zones],
            "trigger_zones": [z.to_dict() for z in self.trigger_zones],
            "danger_zones": [
            {
                "x": z["rect"].x, 
                "y": z["rect"].y, 
                "w": z["rect"].width, 
                "h": z["rect"].height,
                "rx": z["respawn_pos"][0], 
                "ry": z["respawn_pos"][1]
            } for z in self.danger_zones
        ],
        }

    def save(self, name="map"):
        """Sauvegarde dans maps/<name>.json."""
        fp = os.path.join(MAPS_DIR, f"{name}.json")
        self._save_to(fp)
        self._nom_carte = name
        self._show_msg(f"Sauvegardé : {name}.json  |  [K]=définir comme carte de départ")

    def load(self, name="map"):
        """Charge maps/<name>.json → remplace l'état courant."""
        fp = os.path.join(MAPS_DIR, f"{name}.json")
        try:
            with open(fp) as f:
                data = json.load(f)
            self._history.clear()
            self._apply_state(data)
            self._nom_carte = name
            self._show_msg(f"Chargé : {name}.json  |  [K]=définir comme carte de départ")
        except FileNotFoundError:
            self._show_msg(f"{name}.json introuvable")

    def _apply_state(self, data):
        """Applique un dict (chargé ou historique) → remplace tout l'état."""
        # Dimensions du monde.
        if "ground_y"    in data: settings.GROUND_Y  = data["ground_y"]
        if "ceiling_y"   in data: settings.CEILING_Y = data["ceiling_y"]
        # scene_left avant scene_width pour que les clamps soient cohérents
        # quand build_border_segments tourne ensuite. Anciennes maps : 0.
        settings.SCENE_LEFT = data.get("scene_left", 0)
        if "scene_width" in data:
            settings.SCENE_WIDTH    = data["scene_width"]
            self.camera.scene_width = data["scene_width"]
        # IMPORTANT : on applique TOUJOURS une valeur, même si la clé
        # n'est pas dans le JSON (ancienne map). Sinon, charger une
        # vieille map après avoir joué une map zoomée garderait le zoom
        # de la map précédente → chaque map DOIT avoir son propre zoom,
        # y_offset et échelle joueur.
        self.camera.y_offset  = data.get("camera_y_offset", 150)
        # Zoom caméra (par carte). Défaut = 1.0 (pas de zoom) pour les
        # anciennes maps qui n'ont pas encore ce champ.
        self.camera.zoom      = float(data.get("camera_zoom", 1.0))
        # Échelle joueur (par carte). Défaut = 1.0.
        settings.PLAYER_SCALE = float(data.get("player_scale", 1.0))
        if hasattr(self.player, "reload_hitbox"):
            self.player.reload_hitbox()
        if "spawn" in data:
            self.spawn_x = data["spawn"]["x"]
            self.spawn_y = data["spawn"]["y"]
            self.player.spawn_x = self.spawn_x
            self.player.spawn_y = self.spawn_y
        # Spawns nommés (peut être édité à la main dans le JSON, ou
        # rempli plus tard par un mode éditeur dédié).
        # Format : { "nom_du_spawn": [x, y], ... }
        self.named_spawns = dict(data.get("named_spawns", {}))
        if "bg_color"   in data: self.bg_color   = data["bg_color"]
        if "wall_color" in data: self.wall_color = data["wall_color"]

        # Plateformes et murs custom.
        # color=None → collision invisible en jeu (le visuel vient du
        # décor Tiled par-dessus). Un contour gris sera dessiné dans
        # game.py quand l'éditeur active le mode [H]itbox (toggle).
        self.platforms.clear()
        for p in data.get("platforms", []):
            self.platforms.append(Platform(p["x"], p["y"], p["w"], p["h"], None))
        self.custom_walls.clear()
        for w in data.get("custom_walls", []):
            self.custom_walls.append(Wall(w["x"], w["y"], w["w"], w["h"], visible=True))
        self.danger_zones.clear()
        for d in data.get("danger_zones", []):
            self.danger_zones.append({
                "rect": pygame.Rect(d["x"], d["y"], d["w"], d["h"]),
                "respawn_pos": (d["rx"], d["ry"])
            })

        # Segments de bordure : soit chargés, soit reconstruits par défaut.
        def _segs(key, is_border=False):
            """Helper local : reconstruit une liste de Wall depuis data[key]."""
            return [Wall(s["x"], s["y"], s["w"], s["h"],
                         visible=True, is_border=is_border)
                    for s in data.get(key, [])]

        if "ground_segments" in data:
            gs = _segs("ground_segments",  is_border=True)
            cs = _segs("ceiling_segments", is_border=True)
            ls = _segs("left_segments",    is_border=True)
            rs = _segs("right_segments",   is_border=True)
            if gs or cs or ls or rs:
                self.ground_segments  = gs
                self.ceiling_segments = cs
                self.left_segments    = ls
                self.right_segments   = rs
            else:
                self.build_border_segments()
        else:
            self.build_border_segments()

        # Trous.
        self.holes = [pygame.Rect(h["x"], h["y"], h["w"], h["h"])
                      for h in data.get("holes", [])]

        # Ennemis.
        self.enemies.clear()
        for e in data.get("enemies", []):
            self.enemies.append(Enemy(
                e["x"], e["y"],
                has_gravity=e.get("has_gravity", True),
                has_collision=e.get("has_collision", True),
                sprite_name=e.get("sprite_name", "monstre_perdu.png"),
                can_jump=e.get("can_jump", False),
                can_jump_patrol=e.get("can_jump_patrol", False),
                jump_power=e.get("jump_power", 400),
                detect_range=e.get("detect_range", 200),
                detect_height=e.get("detect_height", 80),
                has_light=e.get("has_light", False),
                light_type=e.get("light_type", "dim"),
                light_radius=e.get("light_radius", 100),
                patrol_left=e.get("patrol_left", -1),
                patrol_right=e.get("patrol_right", -1),
                can_fall_in_holes=e.get("can_fall_in_holes", False),
                respawn_timeout=e.get("respawn_timeout", 10.0),
                can_turn_randomly=e.get("can_turn_randomly", False),
            ))

        # Lumières.
        self.lighting.lights.clear()
        for l in data.get("lights", []):
            self.lighting.add_light(
                l["x"], l["y"],
                radius=l["radius"], type=l["type"],
                flicker=l.get("flicker", False),
                flicker_speed=l.get("flicker_speed", 5),
            )

        # Portails.
        self.portals.clear()
        for p in data.get("portals", []):
            self.portals.append(Portal(
                p["x"], p["y"], p["w"], p["h"],
                p["target_map"],
                p.get("target_x", -1),
                p.get("target_y", -1),
                # require_up : portail "porte" (activé par appui ↑/Z).
                # Absent dans les vieilles saves → défaut False (classique).
                require_up=p.get("require_up", False),
            ))

        # Décors.
        self.decors.clear()
        for d in data.get("decors", []):
            # DECORS_DIR (défini dans settings.py) regroupe à la fois les
            # sprites manuels (buisson-1.png…) et les PNG générés par
            # l'import Tiled (tiled_*.png). Un seul dossier → pas de
            # confusion, pas de décor qui disparaît au reload.
            sprite = d["sprite"]
            chemin = os.path.join(DECORS_DIR, sprite)
            if not os.path.exists(chemin):
                print(f"[Load] Decor introuvable : {sprite}")
                continue

            cb = tuple(d["collision_box"]) if "collision_box" in d else None

            # Parallax et foreground : sauvés par to_dict() mais n'étaient
            # pas relus ici → les décors d'arrière-plan (bg2, sky…) se
            # rechargeaient avec parallax 1.0 et les foregrounds passaient
            # derrière le joueur. On les restaure.
            parallax = d.get("parallax", [1.0, 1.0])
            try:
                px = float(parallax[0]); py = float(parallax[1])
            except (TypeError, IndexError, ValueError):
                px, py = 1.0, 1.0
            fg = bool(d.get("foreground", False))

            try:
                decor = Decor(
                    d["x"], d["y"], chemin, sprite,
                    d.get("collision", False),
                    d.get("echelle", 1.0),
                    collision_box=cb,
                    parallax_x=px, parallax_y=py, foreground=fg,
                    is_save_point=bool(d.get("is_save_point", False)),
                )
            except TypeError:
                # Ancien Decor sans params parallax — fallback défensif.
                decor = Decor(
                    d["x"], d["y"], chemin, sprite,
                    d.get("collision", False),
                    d.get("echelle", 1.0),
                    collision_box=cb,
                )
                decor.parallax_x = px
                decor.parallax_y = py
                decor.is_save_point = bool(d.get("is_save_point", False))
                decor.foreground = fg
            self.decors.append(decor)

        # Re-tri par parallax (fonds d'abord) pour cohérence d'affichage.
        self.decors.sort(key=lambda d: (
            1 if d.foreground else 0,
            d.parallax_x, d.parallax_y,
        ))

        # PNJs.
        self.pnjs.clear()
        for p in data.get("pnjs", []):
            if p.get("type") == "marchand":
                self.pnjs.append(Marchand.from_dict(p))
            else:
                self.pnjs.append(PNJ.from_dict(p))

        # Trigger zones (cinématiques, téléportations scriptées, etc.).
        self.trigger_zones.clear()
        for t in data.get("trigger_zones", []):
            self.trigger_zones.append(creer_depuis_dict(t))

        # Remise à zéro du timer de confirmation.
        self._restore_confirm       = False
        self._restore_confirm_timer = 0.0

    def load_map_for_portal(self, name):
        """Charge une autre carte (suite à un portail). Renvoie True / False."""
        fp = os.path.join(MAPS_DIR, f"{name}.json")
        try:
            with open(fp) as f:
                data = json.load(f)
            # On vide l'historique pour ne pas permettre un undo vers l'autre map.
            self._history.clear()
            self._apply_state(data)
            return True
        except FileNotFoundError:
            return False
