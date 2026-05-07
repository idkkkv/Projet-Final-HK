# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Cœur du jeu (boucle principale)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  C'est LE cerveau du jeu. Il contient UNE classe : Game, qui :
#
#     1. Crée tous les objets (joueur, ennemis, menus, systèmes…)
#     2. Lit les événements clavier / souris / manette chaque frame
#     3. Décide "quoi exécuter" selon l'état courant (menu, jeu, pause, mort)
#     4. Met à jour la logique puis dessine à l'écran
#     5. Boucle jusqu'à ce que self.running == False
#
#  main.py fait une seule chose : `Game().run()`.
#
#  LES 4 GRANDS ÉTATS DU JEU (voir self.etats, géré par StateManager) :
#  --------------------------------------------------------------------
#     MENU      → menu titre affiché
#     GAME      → partie en cours (le joueur joue)
#     PAUSE     → menu pause par-dessus le jeu figé
#     GAME_OVER → écran "fin" après la mort du joueur
#
#  ORDRE D'UN FRAME (80 fois par seconde !) :
#  ------------------------------------------
#     1. Calculer dt (temps depuis la frame précédente)                 → voir [D10]
#     2. Lire les événements pygame
#     3. Selon l'état (MENU, GAME, PAUSE, GAME_OVER) :
#          - appeler le gestionnaire correspondant (_gerer_menu, ...)
#          - si GAME : _update_jeu() puis _dessiner_monde()
#          - sinon  : _dessiner_monde() + menu par-dessus
#     4. pygame.display.flip() pour afficher
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Une touche / un bouton          → core/event_handler.py
#     - Une constante (vitesse, FPS…)   → settings.py
#     - Le comportement du joueur        → entities/player.py
#     - Un menu (texte, options)         → ui/menu.py
#     - L'ordre des calques visuels      → ici, méthode _dessiner_monde()
#     - L'enchaînement logique du jeu   → ici, méthode _update_jeu()
#     - LE SON                           → ici, music.jouer()
#
#  Pour la carte générale de qui appelle qui : docs/ARCHITECTURE.md
#  Pour l'index "où modifier quoi"           : docs/OU_EST_QUOI.md
#  Pour les concepts techniques              : docs/DICTIONNAIRE.md
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame
import os

# ── Settings : tout ce qui est réglable + variables runtime (wx, manette, …)
import settings
from settings import *   # noqa: F401,F403 (on veut WIDTH, HEIGHT, FPS, TITLE, ...)

# ── Gestion des états (menu / jeu / pause / fin)
from core.state_manager import StateManager, MENU, GAME, PAUSE, GAME_OVER
from core.event_handler import x_y_man, man_on
from core.camera import Camera

# ── Inventaire
from ui.inventory import Inventory, ITEMS
from ui.items_effects import play_cassette

# ── Entités vivantes
from entities.boss import *
from entities.player import Player
from entities.enemy import Enemy
from entities.marchand import Marchand

# ── Monde (éditeur, plateformes, collisions)
from world.editor import Editor
from world.tilemap import Platform, Wall
from world.collision import appliquer_plateformes
from world.triggers import TriggerZoneGroup, creer_depuis_dict

# ── Systèmes transversaux (peur, lumière, particules, combat…)
from systems.lighting import LightingSystem
from systems.spatial_grid import SpatialGrid
from systems.save_system import sauvegarder, charger, lire_config, ecrire_config
from systems.combat import resoudre_attaques_joueur, resoudre_contacts_ennemis
from systems.fear_system import FearSystem
from systems.effet_reveil import EffetReveil
from systems.particles import ParticleSystem
from systems.juice import ScreenShake, HitPause
from systems.health_overlay import HealthOverlay
from systems.compagnons import CompagnonGroup

# ── Interface (menus, HUD, dialogues)
from ui.menu import Menu
from ui.dialogue_box import BoiteDialogue
from ui.hud import HUD
from ui.help_overlay import HelpOverlay
from ui.settings_screen import SettingsScreen
from ui.inventory import Inventory
from ui.fear_overlay import FearOverlay
from ui.gestionnaire_histoire import GestionnaireHistoire
from ui.boutique import Boutique

# ── Utilitaires et audio
from utils import draw_mouse_coords
from audio import music_manager as music
from audio import sound_manager as sfx

pygame.mixer.init()

class Game:
    """La classe qui contient et orchestre tout le jeu."""

    # ═════════════════════════════════════════════════════════════════════════
    # 1.  CONSTRUCTION — initialise pygame et crée tous les objets du jeu
    # ═════════════════════════════════════════════════════════════════════════
    #
    # Cette méthode est appelée UNE fois, dans main.py, via `Game()`.
    # Elle fait beaucoup de choses — c'est normal, c'est la mise en place.
    # Les blocs sont commentés dans l'ordre d'exécution.

    def __init__(self):
        # ── 1.1 Démarrage de pygame (moteur) ──
        # pygame.init()       → initialise tous les sous-systèmes
        # pygame.mixer.init() → initialise le système audio
        pygame.init()
        pygame.mixer.init()

        # Fenêtre redimensionnable + SCALED (accélération GPU).
        # pygame.SCALED : pygame rend à la résolution logique (WIDTH×HEIGHT)
        #   puis laisse le GPU (SDL2 Renderer) scaler à la taille de la fenêtre.
        #   → les blits SRCALPHA passent de ~100 Mpx/s (CPU) à plusieurs
        #     Gpx/s (GPU). C'est LA clé pour tenir 60+ fps sur les grandes
        #     maps Tiled avec scale≥2 (fonds 2000×2000+ blittés/frame).
        # pygame.RESIZABLE garde le redimensionnement fenêtre (combiné avec
        #   SCALED, la zone de jeu reste nette).
        self.screen = pygame.display.set_mode(
            (WIDTH, HEIGHT), pygame.SCALED | pygame.RESIZABLE)
        pygame.display.set_caption(TITLE)

        # ── 1.2 Horloge et variables de frame ──
        self.running  = True                            # False → on quitte
        self.clock    = pygame.time.Clock()             # régule le FPS
        self.fps_font = pygame.font.SysFont("Consolas", 16)
        self._dt      = 0                               # temps écoulé cette frame

        # ── 1.3 Mode de jeu ──
        #   "histoire" → partie normale (éditeur désactivé)
        #   "editeur"  → accès à l'éditeur de carte (touche E)
        self.mode = "histoire"

        # ── 1.4 Gestionnaire d'états (MENU / GAME / PAUSE / GAME_OVER) ──
        self.etats    = StateManager()
        self.dialogue = BoiteDialogue()
        self.gestionnaire_histoire = GestionnaireHistoire()

        # PNJ qui parle ACTUELLEMENT (None si la boîte est fermée).
        # Sert à savoir à QUI demander d'avancer son index de conversation
        # quand la boîte se ferme (cf. update — on appelle passer_a_suivante
        # à ce moment-là, pas à l'ouverture, pour ne pas sauter de dialogues
        # si le joueur s'éloigne en plein milieu).
        self._pnj_actif = None

        # ── 1.5 Chargement des sons ──
        # On charge les sons UNE fois au démarrage, pas à chaque utilisation.
        sfx.init_sons_ui()
        self._charger_sons()

        # ── 1.6 Police pour l'indicateur H / E (coin haut-droit) ──
        self._font_indicateur = pygame.font.SysFont("Consolas", 48, bold=True)

        # ── 1.7 Systèmes de jeu (peur, HUD, particules, etc.) ──
        self._creer_systemes()

        # ── 1.8 Lecture du fichier de config (préférences persistantes) ──
        cfg = lire_config()
        # Mode HUD (permanent ou immersion).
        mode_hud = cfg.get("hud_mode", "permanent")
        if mode_hud in ("permanent", "immersion"):
            settings.hud_mode = mode_hud
        # Nombre de compagnons choisi par le joueur dans le menu Paramètres.
        nb_compagnons = int(cfg.get("nb_compagnons", 0))

        # Couleur + taille de chaque luciole (préférences personnalisées).
        # Les listes en config sont attendues de longueur COMPAGNON_NB_MAX.
        # Si elles sont absentes ou trop courtes, on garde les défauts définis
        # dans settings.py, en complétant par recyclage des valeurs.
        nb_max = settings.COMPAGNON_NB_MAX
        couleurs_cfg = cfg.get("lucioles_couleurs_idx")
        if isinstance(couleurs_cfg, list) and len(couleurs_cfg) > 0:
            # On complète avec la dernière valeur si la liste est trop courte
            # (config créée quand COMPAGNON_NB_MAX était plus petit).
            settings.lucioles_couleurs_idx = [
                int(couleurs_cfg[min(i, len(couleurs_cfg) - 1)])
                for i in range(nb_max)
            ]
        tailles_cfg = cfg.get("lucioles_tailles_idx")
        if isinstance(tailles_cfg, list) and len(tailles_cfg) > 0:
            settings.lucioles_tailles_idx = [
                int(tailles_cfg[min(i, len(tailles_cfg) - 1)])
                for i in range(nb_max)
            ]
        # Intensité (puissance d'éclairage) : même logique de complétion.
        # Hydrate settings.lucioles_intensites_idx (cf. luciole._get_intensite_mult).
        intens_cfg = cfg.get("lucioles_intensites_idx")
        if isinstance(intens_cfg, list) and len(intens_cfg) > 0:
            settings.lucioles_intensites_idx = [
                int(intens_cfg[min(i, len(intens_cfg) - 1)])
                for i in range(nb_max)
            ]

        # ── 1.9 Création du joueur, des compagnons et des ennemis ──
        self.compagnons = CompagnonGroup(nb=nb_compagnons)
        self.joueur     = Player((100, 400))
        # On branche le menu Paramètres MAINTENANT (après joueur créé).
        self.parametres.bind_compagnons(self.compagnons, self.joueur)

        # ── Tracking des sources de lucioles déjà obtenues ──
        # Ensemble (set) de chaînes : "boss_miroir", "villageois_anna", etc.
        # Mis à jour par gagner_luciole_unique() et sauvegardé dans save.json
        # (cf. _sauvegarder() / _charger_partie()). Sert à NE PAS redonner
        # une luciole quand le joueur retue le même boss après un reload
        # ou parle 2 fois au même villageois récompenseur.
        self.lucioles_sources_obtenues = set()

        # On crée une liste d'ennemis qui contiendra aussi nos Boss
        # On les instancie ici pour qu'ils soient chargés en mémoire dès le début
        self.ennemis = [
            Enemy(500, 530 - 60),
            BossMiroir(800, 400),       # Ajout du premier boss
            LaTempête(1200, 400),    # Ajout du deuxième boss
        ]

        # Zones-déclencheurs (téléportation, cinématiques) — vide au boot,
        # rempli par les cartes / l'éditeur. cf. world/triggers.py [D02]
        self.triggers = TriggerZoneGroup()

        # Cinématique en cours (None si pas de cutscene active).
        # Mis à jour par CutsceneTrigger.on_enter qui pose ici un objet Cutscene.
        # Lu chaque frame dans _simuler_jeu pour avancer la cinématique.
        self.cutscene = None
        self.state    = "play"   # "play" | "cinematic"

        # Compteur persistant : combien de fois CHAQUE cinématique a été
        # jouée dans la partie en cours. Sauvegardé dans save.json, reset
        # à "Nouvelle partie". Utilisé par CutsceneTrigger.on_enter pour
        # respecter max_plays (cinématique unique vs répétable).
        self.cinematiques_jouees = {}

        # Journal des dialogues : trace TOUS les dialogues complétés avec
        # chaque PNJ, organisés par carte. Permet au joueur de relire ce
        # qu'un PNJ lui a dit (utile en mode boucle_dernier où le PNJ ne
        # répète plus que sa dernière phrase). Sauvé dans save.json.
        # Structure : {nom_pnj: {nom_map: [conversation, conversation, ...]}}
        self.historique_dialogues = {}
        from ui.dialogue_history import DialogueHistory
        self.journal_dialogues = DialogueHistory()

        self.camera  = Camera(SCENE_WIDTH, SCENE_HEIGHT)
        self.ennemis = [Enemy(500, 530 - 60)]

        # Plateformes par défaut (visibles au lancement avant toute édition).
        self.platforms = [
            Platform(200, 500, 100, 20, BLANC),
            Platform(300, 400, 100, 20, GRIS),
            Platform(400, 300, 100, 20, BLEU),
        ]

        # ── 1.10 Grille spatiale (optimisation collisions) ──
        # Au lieu de tester le joueur contre CHAQUE plateforme, on les
        # range dans une grille et on n'interroge que les cellules voisines.
        # → gros gain de FPS quand il y a beaucoup de plateformes.
        self.grille_plateformes = SpatialGrid(cell_size=128)
        self._reconstruire_grille()

        # ── 1.11 Éclairage dynamique ──
        self.lumieres = LightingSystem()
        self.lumieres.add_light(300, 480, radius=150, type="torch", flicker=True)
        self.lumieres.add_light(600, 380, radius=200, type="torch", flicker=True)

        # ── 1.12 Éditeur de carte ──
        self.editeur = Editor(self.platforms, self.ennemis,
                              self.camera, self.lumieres, self.joueur)
        self.editeur.build_border_segments()
        # L'éditeur de cinématique a besoin d'un callback pour TESTER une
        # cinématique (touche [T]) : on construit un Cutscene depuis sa liste
        # d'étapes JSON et on le pose dans game.cutscene.
        self.editeur.cine_editor.on_test_callback = self._tester_cinematique
        # [Ctrl+R] dans le cine_editor = reset compteur (rendre rejouable
        # une cinématique 'unique' déjà consommée — utile en dev/test).
        self.editeur.cine_editor.on_reset_counter_callback = \
            self._reset_compteur_cinematique

        # On branche l'éditeur dans le menu Paramètres : la page
        # "Compagnons" (couleur/taille/nb des Lueurs) n'est accessible
        # qu'en mode éditeur (en jeu normal, ces réglages se gagnent
        # via les quêtes — règle produit, voir ui/settings_screen.py).
        self.parametres.bind_editeur(self.editeur)

        # ── 1.13 Variables d'état (transitions, caches) ──
        self._init_transitions()
        self._init_caches()
        self._etait_au_sol = True                       # pour détecter l'atterrissage
        self._etait_dash   = False                      # pour détecter le début de dash
        self.carte_actuelle = ""                        # nom de la map chargée

        self.boss_miroir_actif = False # Variable pour suivre si le boss miroir est actif
        self.tempete_active    = False # Variable pour suivre si la tempête est active

        # ── 1.14 Menus (titre, pause, fin) ──
        self._creer_menus()

        # ── 1.15 Musique du menu titre + effet de réveil ──
        self._init_audio_menu()

    # ─── Sous-routines de __init__ (pour aérer le constructeur) ──────────────

    def _charger_sons(self):
        """Charge les fichiers audio (sons du joueur, UI). Appelé 1 fois."""
        from audio import sound_manager
        sound_manager.charger("attaque", "ENTRE-DEUX/assets/sounds/attaque.mp3")
        sound_manager.charger("attaque_contact", "ENTRE-DEUX/assets/sounds/attaquecontact.mp3")
        sound_manager.charger("pas",     "ENTRE-DEUX/assets/sounds/pas.mp3", trim=True)
        sound_manager.charger("mort",    "ENTRE-DEUX/assets/sounds/mort.mp3")
        sound_manager.charger("degat",   "ENTRE-DEUX/assets/sounds/degat.mp3")

        # Son de saut : si le fichier existe, on le prend. Sinon, on
        # synthétise un petit "pop" court et discret (240 Hz, 70 ms).
        sound_manager.charger_ou_synth(
            "saut", "ENTRE-DEUX/assets/sounds/saut.mp3",
            freq=240, duree=0.07, volume=0.18,
        )

    def _creer_systemes(self):
        """Crée les systèmes transversaux (peur, particules, shake…)."""
        self.boutique = Boutique()
        self.inventory = Inventory()
        self.inventory.add_item("Pomme")                      # pomme offerte au départ
        self.inventory.add_item("Cassette")                    # cassette offerte au départ

        self.hud        = HUD()                          # cœurs + jauge de peur
        self.peur       = FearSystem(max_fear=100)       # 0 → 100
        # Overlay du texte d'avertissement quand on entre dans une fear_zone
        # avec trop de peur. La police sera injectée plus tard (init différée
        # car HUD/police chargés plus tard).
        self.fear_overlay = FearOverlay()
        # Multiplicateur de vitesse appliqué au joueur par les fear_zones.
        # Recalculé chaque frame : 1.0 = vitesse normale, 0.5 = ralenti, etc.
        self._mult_vitesse_peur = 1.0
        self.aide       = HelpOverlay()                  # aide F1
        self.parametres = SettingsScreen()               # écran Paramètres

        # Effets visuels / "game feel"
        self.particles  = ParticleSystem()
        self.shake      = ScreenShake()                  # secouement d'écran
        self.hitpause   = HitPause()                     # micro-pause à l'impact
        self.hp_overlay = HealthOverlay()                # vignette rouge PV bas

    def _init_transitions(self):
        """Initialise les variables de fondu entre cartes et menus."""
        # Fondu enchaîné entre deux cartes (quand on passe un portail).
        self.vitesse_fondu       = 0.4                  # secondes pour 0 → 255 (portail classique)
        # Durée du fondu pour les PORTAILS PORTE (require_up=True).
        # Plus long que pour un portail classique → rend l'entrée dans
        # une maison plus "rituelle" et moins agressive visuellement.
        # Si tu veux un fondu encore plus lent, monte jusqu'à ~1.5 s.
        self.vitesse_fondu_porte = 1.0                  # secondes pour 0 → 255 (porte)
        # Durée utilisée pour la transition en cours. Mise à jour au
        # moment où on déclenche un fondu, pour que _update_fondu sache
        # quelle vitesse appliquer sans avoir à re-tester le type de
        # portail à chaque frame.
        self._fondu_duree_courante = self.vitesse_fondu
        self._fondu_alpha        = 0                    # 0 = rien, 255 = noir total
        self._fondu_etat         = "none"               # "none" / "out" / "in"
        self._fondu_surface      = None                 # cache de la surface noire
        self._portail_en_attente = None                 # (carte, x, y)

        # Fondu lent quand on lance une partie depuis le menu.
        self._menu_fondu_alpha  = 0
        self._menu_fondu_etat   = "none"                # "none" / "out" / "in"
        self._menu_fondu_action = None                  # callback quand alpha = 255

        # Overlay de sélection de carte (menu éditeur)
        self._menu_choix_carte = None

    def _init_caches(self):
        """Caches pour éviter de recalculer certaines choses chaque frame."""
        # Cache des murs (on ne recalcule que quand l'éditeur les modifie).
        self._murs_cache        = None
        self._murs_cache_perime = True                  # True = à recalculer

    def _creer_menus(self):
        """Crée les 3 menus : titre, pause, fin."""
        # L'option "Continuer" n'apparaît que si une sauvegarde existe.
        save = charger()
        options_titre = []
        if save:
            options_titre.append("Continuer")
        options_titre += ["Nouvelle partie", "Mode éditeur", "Quitter"]

        # style="titre"   → fond sombre + particules
        # style="panneau" → cadre sur le jeu en arrière-plan
        self.menu_titre = Menu(options_titre, title=TITLE, style="titre")
        self.menu_pause = Menu(
            ["Reprendre", "Paramètres", "Sauvegarder", "Menu principal", "Quitter"],
            title="PAUSE",
            style="panneau",
        )
        self.menu_fin = Menu(
            ["Recommencer", "Menu principal"],
            title="FIN",
            style="panneau",
        )

    def _init_audio_menu(self):
        """Lance la musique du menu + prépare l'effet de réveil."""
        # Chemin absolu vers la musique du menu (plus robuste qu'un chemin
        # relatif : fonctionne même si on lance depuis un autre dossier).
        _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._musique_menu = os.path.join(
            _base, "assets", "music",
            "i think about you not thinking about me Piano Solo.mp3",
        )
        music.jouer(self._musique_menu, volume=0.05, fadein_ms=2000)

        # Effet "rayons de lumière" qui apparaissent à ~1:57 (chant des oiseaux).
        duree = music.get_duree()
        self.effet_reveil = EffetReveil(
            debut_s=117,
            duree_cycle_s=duree if duree > 0 else 170,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # 2.  CACHES ET LUMIÈRES DYNAMIQUES
    # ═════════════════════════════════════════════════════════════════════════

    def _reconstruire_grille(self):
        """Rebuild la grille spatiale (appelée après modif des plateformes)."""
        self.grille_plateformes.rebuild(self.platforms)

    def _murs_modifies(self):
        """Appelé quand l'éditeur ajoute/supprime un mur → à recalculer."""
        self._murs_cache_perime = True

    def _murs_actifs(self):
        """Renvoie la liste des murs actifs. Calculée paresseusement."""
        if self._murs_cache_perime:
            self._murs_cache = (
                self.editeur.all_segments() + self.editeur.custom_walls
            )
            self._murs_cache_perime = False
        return self._murs_cache

    def _sync_lumieres_ennemis(self):
        """Actualise les lumières portées par les ennemis.

        Certains ennemis ont une "lanterne" (has_light=True). On enlève les
        anciennes lumières d'ennemis puis on en recrée une pour chaque
        ennemi vivant porteur.
        """
        # Filtre les lumières "normales" (on garde tout sauf les _enemy_light).
        # Liste en compréhension — voir [D33].
        self.lumieres.lights = [
            lum for lum in self.lumieres.lights
            if not lum.get("_enemy_light")
        ]

        # Ajoute une nouvelle lumière par ennemi vivant qui en porte une.
        for ennemi in self.ennemis:
            if not ennemi.alive or not ennemi.has_light:
                continue
            lx, ly = ennemi.get_light_pos()
            self.lumieres.lights.append({
                "x": lx, "y": ly,
                "radius": ennemi.light_radius,
                "type": ennemi.light_type,
                "flicker": True,
                "flicker_speed": 4,
                "_phase": 0,
                "_alpha": 210,
                "_enemy_light": True,            # marqueur pour re-filtrer
            })

    # ═════════════════════════════════════════════════════════════════════════
    # 3.  COLLISIONS DES ENNEMIS AVEC LE DÉCOR
    # ═════════════════════════════════════════════════════════════════════════
    #
    # Le joueur a son propre système (world/collision.py). Pour les ennemis,
    # c'est plus simple : on parcourt tous les murs/plateformes et on
    # applique la même résolution à chacun.

    def _collisions_ennemis(self, ennemi, murs):
        """Applique les collisions d'un ennemi avec les murs ET plateformes."""
        # Partie 1 : collisions avec les murs.
        for mur in murs:
            # Certains murs sont marqués "player_only" (le joueur passe mais
            # pas l'ennemi). getattr(obj, "attr", valeur_par_defaut) renvoie
            # la valeur par défaut si l'attribut n'existe pas.
            if getattr(mur, "player_only", False):
                continue

            # Certains "murs" sont des Rect bruts, d'autres des objets Wall
            # avec un champ .rect. hasattr permet de tester.
            if hasattr(mur, "rect"):
                rect_mur = mur.rect
            else:
                rect_mur = mur

            if not ennemi.rect.colliderect(rect_mur):
                continue

            # Mémorise l'état AVANT la résolution pour détecter les effets.
            x_avant   = ennemi.rect.x
            bas_avant = ennemi.rect.bottom
            vy_avant  = ennemi.vy

            mur.verifier_collision(ennemi)

            # Atterrissage : vy tombait (>0) et maintenant bloquée à 0
            # → l'ennemi vient de toucher le sol.
            if ennemi.vy == 0 and vy_avant > 0 and ennemi.rect.bottom <= bas_avant:
                ennemi.on_ground = True

            # Rebond sur mur horizontal : si on a été poussé et qu'on
            # n'était pas en gros saut → on fait demi-tour.
            if ennemi.rect.x != x_avant and abs(vy_avant) < 80:
                ennemi.on_wall_collision_horizontal(rect_mur.height)

        # Partie 2 : même chose avec les plateformes.
        for plateforme in self.platforms:
            if not ennemi.rect.colliderect(plateforme.rect):
                continue

            x_avant   = ennemi.rect.x
            bas_avant = ennemi.rect.bottom
            vy_avant  = ennemi.vy

            plateforme.verifier_collision(ennemi)

            if ennemi.vy == 0 and vy_avant > 0 and ennemi.rect.bottom <= bas_avant:
                ennemi.on_ground = True

            if ennemi.rect.x != x_avant and abs(vy_avant) < 80:
                ennemi.on_wall_collision_horizontal(plateforme.rect.height)

    # ═════════════════════════════════════════════════════════════════════════
    # 4.  EFFETS VISUELS DÉCLENCHÉS PAR LE GAMEPLAY
    # ═════════════════════════════════════════════════════════════════════════
    #
    # Particules, screen shake, hit-pause — ce qu'on appelle le "game feel".
    # Ces effets sont déclenchés par des ÉVÉNEMENTS (atterrir, prendre un
    # coup, tuer un ennemi) et comparent l'état actuel à l'état précédent.

    def _declencher_effets_joueur(self, hp_precedent, dt):
        """Observe l'état du joueur et déclenche particules / shake / hitpause."""
        j = self.joueur

        # ── Atterrissage : était en l'air, maintenant au sol ──
        if j.on_ground and not self._etait_au_sol:
            self.particles.burst(
                j.rect.centerx, j.rect.bottom, nb=8,
                couleur=(220, 210, 180),              # poussière beige
                vx_range=(-140, 140),
                vy_range=(-160, -40),                  # part vers le haut
                gravity=900, taille=(1, 3),
                duree=(0.25, 0.5),
            )

        # ── Début de dash : particules bleutées ──
        if j.dashing and not self._etait_dash:
            self.particles.burst(
                j.rect.centerx, j.rect.centery, nb=10,
                couleur=(180, 220, 255),
                vx_range=(-60 * j.dash_dir, 60 * j.dash_dir),
                vy_range=(-80, 80),
                gravity=0, taille=(1, 3),
                duree=(0.2, 0.4),
            )

        # ── Traînée continue pendant le dash ──
        if j.dashing:
            self.particles.trail(
                j.rect.centerx, j.rect.centery,
                couleur=(160, 200, 240),
            )

        # ── Coup reçu : screen shake + hit-pause + particules rouges ──
        if j.hp < hp_precedent:
            self.shake.trigger(amplitude=8, duree=0.25)
            self.hitpause.trigger(0.08)
            self.particles.burst(
                j.rect.centerx, j.rect.centery, nb=14,
                couleur=(235, 60, 90),
                vx_range=(-180, 180),
                vy_range=(-200, -50),
                gravity=700, taille=(1, 3),
                duree=(0.3, 0.6),
            )

        # Mémorise l'état de ce frame (sera "l'état précédent" du prochain).
        self._etait_au_sol = j.on_ground
        self._etait_dash   = j.dashing

    def _declencher_effets_ennemis(self, ennemis_alive_avant):
        """Screen shake + particules quand un ennemi vient de mourir.

        BONUS : si le mort est un BOSS, on déclenche aussi un gain de
        luciole (récompense rare). On reconnaît un boss en testant
        isinstance(ennemi, Boss) — voir entities/boss.py.
        """
        # Import local pour éviter d'alourdir l'en-tête du fichier et
        # les imports circulaires potentiels.
        from entities.boss import Boss

        for ennemi in self.ennemis:
            if ennemi.alive:
                continue
            # Était vivant avant ce frame et ne l'est plus → mort ce frame.
            if ennemi in ennemis_alive_avant:
                self.shake.trigger(amplitude=5, duree=0.18)
                self.hitpause.trigger(0.05)
                self.particles.burst(
                    ennemi.rect.centerx, ennemi.rect.centery, nb=18,
                    couleur=(255, 240, 200),
                    vx_range=(-220, 220),
                    vy_range=(-260, -60),
                    gravity=800, taille=(1, 4),
                    duree=(0.4, 0.8),
                )

                # ── Récompense BOSS : +1 luciole (max 5 dans tout le jeu) ───
                # On utilise gagner_luciole_unique() qui mémorise la source
                # → un boss déjà tué dans une partie précédente (rechargée)
                # ne donne plus de luciole. Identifiant = type de la classe
                # (ex: "boss_BossMiroir") pour distinguer chaque boss.
                if isinstance(ennemi, Boss):
                    source_id = f"boss_{ennemi.__class__.__name__}"
                    obtenue = self.gagner_luciole_unique(source_id)
                    # Petit feu d'artifice supplémentaire si on a vraiment
                    # gagné quelque chose — plus marquant qu'une mort
                    # d'ennemi normale. À transformer en VRAI effet visuel
                    # (FX, son spécial...) le jour où tu en feras un.
                    if obtenue:
                        self.particles.burst(
                            self.joueur.rect.centerx,
                            self.joueur.rect.centery,
                            nb=30,
                            couleur=(255, 230, 160),
                            vx_range=(-160, 160),
                            vy_range=(-220, -40),
                            gravity=400, taille=(2, 5),
                            duree=(0.6, 1.2),
                        )

    # ═════════════════════════════════════════════════════════════════════════
    # 4b. Récompense de luciole avec mémoire (anti double-don)
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Helper à utiliser POUR TOUTES les récompenses uniques (boss,
    #  villageois, énigmes, etc.). Vérifie d'abord si la source a déjà
    #  donné une luciole, puis :
    #     - si oui → ne fait rien, renvoie False
    #     - si non → ajoute la luciole, mémorise la source, renvoie True
    #
    #  La mémoire est sauvegardée dans save.json (clé "lucioles_sources_obtenues")
    #  → le joueur ne peut pas farmer en rechargeant après un boss.
    #
    #  EXEMPLES D'USAGE :
    #     self.gagner_luciole_unique("boss_BossMiroir")
    #     self.gagner_luciole_unique("villageois_anna_quete1")
    #     self.gagner_luciole_unique("enigme_foret_lune")

    def gagner_luciole_unique(self, source_id):
        """Donne une luciole UNE SEULE FOIS pour une source donnée.

        Renvoie True si une nouvelle luciole a été créée, False sinon
        (déjà obtenue OU groupe au max). La sauvegarde de la mémoire
        se fait quand le joueur appuie sur "Sauvegarder" — ce n'est
        donc pas instantané (cohérent avec le reste du système)."""

        # Source déjà utilisée dans cette partie (ou partie chargée) ?
        # → on refuse.
        if source_id in self.lucioles_sources_obtenues:
            return False

        # On tente l'ajout. La fonction renvoie False si on est au max
        # (5 lucioles déjà). Dans ce cas, on NE mémorise PAS la source,
        # comme ça quand le joueur perdra une luciole d'une autre façon
        # (futur système ?), il pourra retenter. À adapter selon le
        # design qu'on veut.
        ok = self.compagnons.gagner_luciole(
            joueur=self.joueur,
            source=source_id,
        )
        if ok:
            self.lucioles_sources_obtenues.add(source_id)
        return ok

    # ═════════════════════════════════════════════════════════════════════════
    # 5.  PORTAILS & FONDU ENCHAÎNÉ (transitions entre cartes)
    # ═════════════════════════════════════════════════════════════════════════
    #
    # Un portail est un Rect qui, quand le joueur le touche, charge une
    # autre carte. On utilise un fondu noir pour masquer le chargement.
    #
    # Cycle du fondu :
    #   "none" → "out" (alpha 0 → 255, écran devient noir)
    #          → chargement carte
    #          → "in"  (alpha 255 → 0, écran réapparaît)
    #          → "none"

    def _verifier_portails(self):
        """Détecte si le joueur touche un portail → démarre le fondu."""
        if self._fondu_etat != "none":
            return                                      # déjà en transition

        # Input "regarder vers le haut" — utilisé par les portails PORTE.
        # On le lit directement ici pour ne pas dépendre de l'état du
        # joueur (il pourrait être en dash, attaque, etc.).
        keys = pygame.key.get_pressed()
        input_up = keys[pygame.K_z] or keys[pygame.K_UP]

        for portail in self.editeur.portals:
            if not self.joueur.rect.colliderect(portail.rect):
                continue

            # Portail PORTE (require_up=True) : ne se déclenche que si le
            # joueur "entre" volontairement en appuyant sur Z ou ↑. On peut
            # donc rester devant la porte sans être téléporté par accident
            # → plus diégétique, plus sûr pour les portes de maisons.
            if getattr(portail, "require_up", False) and not input_up:
                continue

            # On mémorise où on doit arriver, le chargement se fera
            # quand l'écran sera complètement noir.
            self._portail_en_attente = (
                portail.target_map,
                portail.target_x,
                portail.target_y,
            )
            # Durée du fondu pour CETTE transition. Les PORTES ont un
            # fondu plus long (plus rituel) que les portails classiques.
            if getattr(portail, "require_up", False):
                self._fondu_duree_courante = self.vitesse_fondu_porte
            else:
                self._fondu_duree_courante = self.vitesse_fondu
            self._fondu_etat  = "out"
            self._fondu_alpha = 0
            return

    def _update_fondu(self, dt):
        """Fait avancer le fondu : alpha ± vitesse*dt chaque frame."""
        if self._fondu_etat == "none":
            return

        # Vitesse = 255 alpha en `_fondu_duree_courante` secondes.
        # Cette durée est fixée au moment où le fondu DÉMARRE :
        #   - portail classique → self.vitesse_fondu       (défaut 0.4 s)
        #   - porte (require_up) → self.vitesse_fondu_porte (défaut 1.0 s)
        # max(0.05, ...) protège d'une division par zéro si on met 0.
        duree = getattr(self, "_fondu_duree_courante", self.vitesse_fondu)
        vitesse = 255 / max(0.05, duree)

        if self._fondu_etat == "out":
            self._fondu_alpha += vitesse * dt

            # Écran complètement noir → on charge la carte.
            if self._fondu_alpha >= 255:
                self._fondu_alpha = 255
                self._effectuer_transition_carte()
                self._fondu_etat = "in"

        elif self._fondu_etat == "in":
            self._fondu_alpha -= vitesse * dt

            if self._fondu_alpha <= 0:
                self._fondu_alpha = 0
                self._fondu_etat  = "none"

    def _effectuer_transition_carte(self):
        """Charge la carte cible, place le joueur, reset les caches."""
        if not self._portail_en_attente:
            return

        carte, tx, ty = self._portail_en_attente
        if self.editeur.load_map_for_portal(carte):
            self.carte_actuelle = carte
            self._reconstruire_grille()
            self._murs_modifies()
            # Destination : (tx, ty) si valides, sinon spawn par défaut.
            if tx >= 0 and ty >= 0:
                self.joueur.rect.x = tx
                self.joueur.rect.y = ty
            else:
                self.joueur.respawn()
            # Reset vitesses pour ne pas "propulser" le joueur dans la nouvelle carte.
            self.joueur.vy           = 0
            self.joueur.knockback_vx = 0

        self._portail_en_attente = None
        self._sync_triggers()

    def _sync_triggers(self):
        """Reconstruit self.triggers depuis les trigger_zones de l'éditeur.

        À appeler après chaque chargement de carte (portail, démarrage, sauvegarde)
        pour que les zones déclencheurs de la nouvelle carte soient actives."""
        self.triggers = TriggerZoneGroup(
            creer_depuis_dict(z.to_dict())
            for z in self.editeur.trigger_zones
        )

    def _logger_dialogue(self, pnj):
        """Ajoute la conversation que le joueur vient de lire au journal.

        Évite les doublons : si la conversation est exactement identique à
        la dernière entrée pour ce PNJ sur cette map, on ne re-loggue pas
        (cas typique : mode boucle_dernier qui re-renvoie la dernière ligne
        à chaque talk → on ne pollue pas le journal)."""
        conv = pnj.conversation_actuelle()
        if not conv:
            return
        carte = self.carte_actuelle or "?"
        nom   = pnj.nom or "PNJ"
        par_pnj = self.historique_dialogues.setdefault(nom, {})
        par_map = par_pnj.setdefault(carte, [])
        # Conversion en tuples (texte, orateur) sérialisables pour json.
        conv_norm = []
        for ligne in conv:
            if isinstance(ligne, (list, tuple)) and len(ligne) >= 2:
                conv_norm.append([str(ligne[0]), str(ligne[1])])
            else:
                conv_norm.append([str(ligne), ""])
        # Déduplication : si dernière entrée identique, on saute.
        if par_map and par_map[-1] == conv_norm:
            return
        par_map.append(conv_norm)

    def _reset_compteur_cinematique(self, nom):
        """Remet à zéro le compteur de lectures pour la cinématique `nom`.

        nom=None → reset TOUS les compteurs (Maj+Ctrl+R en cine_editor).
        Aussi : on remet à zéro l'état `declenchee` des trigger_zones qui
        ciblent cette cinématique, sinon une zone "consommée" reste figée
        jusqu'au prochain rechargement de carte."""
        if nom is None:
            self.cinematiques_jouees.clear()
            for z in self.editeur.trigger_zones:
                if hasattr(z, "declenchee"):
                    z.declenchee = False
                    z._dedans_avant = False
            for z in self.triggers.zones:
                if hasattr(z, "declenchee"):
                    z.declenchee = False
                    z._dedans_avant = False
        else:
            self.cinematiques_jouees.pop(nom, None)
            for z in self.editeur.trigger_zones:
                if getattr(z, "cutscene_nom", "") == nom:
                    z.declenchee     = False
                    z._dedans_avant  = False
            for z in self.triggers.zones:
                if getattr(z, "cutscene_nom", "") == nom:
                    z.declenchee     = False
                    z._dedans_avant  = False

    def _skipper_cinematique(self):
        """Avorte proprement la cinématique en cours (touche [Echap]).

        On rend la main au joueur, on libère la caméra cinématique et on
        ferme la boîte de dialogue si elle est ouverte. Le compteur
        cinematiques_jouees reste à sa valeur (la cinématique COMPTE comme
        jouée même si on l'a passée — comportement attendu en jeu)."""
        self.cutscene = None
        self.state    = "play"
        if hasattr(self.camera, "release_cinematic"):
            self.camera.release_cinematic()
        # Si un dialogue est encore affiché, on le ferme.
        if hasattr(self.dialogue, "actif") and self.dialogue.actif:
            try:
                self.dialogue.fermer()
            except AttributeError:
                # Pas de méthode fermer : on coupe à la dure
                self.dialogue.actif = False

    def _tester_cinematique(self, steps_data):
        """Lance une cinématique depuis les données JSON brutes (touche [T]
        de l'éditeur de cinématiques). Permet de prévisualiser sans avoir
        à sauvegarder + recharger la carte + entrer dans la zone trigger."""
        from systems.cutscene import Cutscene
        from world.triggers   import _steps_depuis_data
        try:
            scene = Cutscene(_steps_depuis_data(steps_data))
        except Exception as e:
            print(f"[Cutscene] Erreur construction : {e}")
            return
        self.cutscene = scene
        self.state    = "cinematic"

    def _dessiner_fondu(self):
        """Dessine le voile noir si l'alpha est > 0."""
        if self._fondu_alpha <= 0:
            return

        w, h = self.screen.get_size()
        # On crée la surface une seule fois (cache). Voir [D2] pour SRCALPHA.
        if self._fondu_surface is None or self._fondu_surface.get_size() != (w, h):
            self._fondu_surface = pygame.Surface((w, h), pygame.SRCALPHA)

        self._fondu_surface.fill((0, 0, 0, int(self._fondu_alpha)))
        self.screen.blit(self._fondu_surface, (0, 0))

    # ═════════════════════════════════════════════════════════════════════════
    # 6.  NOUVELLE PARTIE / CHARGEMENT / SAUVEGARDE
    # ═════════════════════════════════════════════════════════════════════════

    def _nouvelle_partie(self):
        """Démarre une nouvelle partie (carte initiale, PV pleins)."""
        # Reset du compteur de cinématiques (toutes les cinématiques uniques
        # rejoueront depuis le début).
        self.cinematiques_jouees  = {}
        # Reset du journal des dialogues : nouvelle partie = nouveau journal.
        self.historique_dialogues = {}

        # Mode histoire → l'éditeur est désactivé (le joueur ne doit pas y accéder).
        if self.mode == "histoire":
            self.editeur.active = False

        # Chargement de la carte selon le mode.
        if self.mode == "histoire":
            config = lire_config()
            debut  = config.get("carte_debut", "")
            if debut and self.editeur.load_map_for_portal(debut):
                self.carte_actuelle = debut
            else:
                # Pas de carte de départ définie → carte vide.
                self.editeur._new_map()
                self.carte_actuelle = ""
        else:
            # Mode éditeur → carte vide prête à éditer.
            self.editeur._new_map()
            self.carte_actuelle = ""

        # Dans tous les cas : reconstruire la grille et le cache.
        self._reconstruire_grille()
        self._murs_modifies()
        self._sync_triggers()

        # Réinitialiser le joueur.
        self.joueur.rect.x       = self.editeur.spawn_x
        self.joueur.rect.y       = self.editeur.spawn_y
        self.joueur.hp           = self.joueur.max_hp
        self.joueur.dead         = False
        self.joueur.vx           = 0
        self.joueur.vy           = 0
        self.joueur.knockback_vx = 0

        # Réveiller tous les ennemis.
        for ennemi in self.ennemis:
            ennemi.alive = True

        # Placer les compagnons autour du joueur.
        self.compagnons.respawn(self.joueur)

        # Passer à l'état GAME.
        self.etats.switch(GAME)

    def _charger_partie(self):
        """Charge save.json et replace le joueur où il était."""
        donnees = charger()
        if not donnees:
            # Pas de sauvegarde → on lance une nouvelle partie à la place.
            self._nouvelle_partie()
            return

        self.mode        = donnees.get("mode", "histoire")
        self.joueur.hp   = donnees.get("hp", self.joueur.max_hp)
        self.joueur.dead = False
        self.joueur.vy   = 0
        # Restaure le compteur de cinématiques jouées (cinématiques uniques).
        self.cinematiques_jouees = dict(donnees.get("cinematiques_jouees", {}))
        # Restaure le journal des dialogues.
        self.historique_dialogues = dict(donnees.get("historique_dialogues", {}))

        if self.mode == "histoire":
            self.editeur.active = False

        # Chargement de la carte sauvegardée.
        carte = donnees.get("map", "")
        if carte:
            self.editeur.load_map_for_portal(carte)
            self.carte_actuelle = carte
            self._reconstruire_grille()
            self._murs_modifies()
            self._sync_triggers()

        self.joueur.rect.x = donnees.get("x", self.joueur.spawn_x)
        self.joueur.rect.y = donnees.get("y", self.joueur.spawn_y)

        # ── Restauration du nombre de LUCIOLES gagnées ─────────────────
        # Sans ça, à chaque "Continuer" on repartirait avec la valeur du
        # menu Paramètres (game_config.json), donc une partie à 4 lucioles
        # gagnées via boss/villageois retomberait à 0 après quit/restart.
        # Si la clé est absente (vieille save), on garde le nb actuel.
        if "nb_compagnons" in donnees:
            self.compagnons.set_nb(int(donnees["nb_compagnons"]))

        # ── Restauration des sources de lucioles déjà obtenues ─────────
        # Évite que tuer 2 fois le même boss (rejouer après reload) ne
        # redonne une luciole en double. Cf. compagnons.gagner_luciole().
        self.lucioles_sources_obtenues = set(
            donnees.get("lucioles_sources_obtenues", [])
        )

        self.compagnons.respawn(self.joueur)
        self.etats.switch(GAME)

    def _sauvegarder(self):
        """Écrit la partie courante dans save.json."""
        sauvegarder({
            "mode":                       self.mode,
            "hp":                         self.joueur.hp,
            "map":                        self.carte_actuelle,
            "x":                          self.joueur.rect.x,
            "y":                          self.joueur.rect.y,
            "cinematiques_jouees":        self.cinematiques_jouees,
            "historique_dialogues":       self.historique_dialogues,
            # ── Lucioles ─────────────────────────────────────────────────
            # Nombre courant de lucioles dans le groupe (incluant celles
            # gagnées en jeu via gagner_luciole). Lu au "Continuer" pour
            # restaurer le bon nombre.
            "nb_compagnons":              len(self.compagnons.compagnons),
            # Liste des sources déjà utilisées (ex: "boss_miroir",
            # "villageois_anna"). Sert à éviter le double-don sur reload.
            # On convertit en list car JSON ne sait pas sérialiser un set.
            "lucioles_sources_obtenues":  list(getattr(self,
                                                "lucioles_sources_obtenues",
                                                set())),
        })

    # ═════════════════════════════════════════════════════════════════════════
    # 7.  INTERACTION AVEC LES PNJ
    # ═════════════════════════════════════════════════════════════════════════

    def _tenter_interaction(self):
        """Cherche un PNJ proche et démarre son dialogue.

        Appelé quand le joueur appuie sur E en mode histoire.

        On NE FAIT PLUS avancer l'index de conversation ici (c'était le
        bug : l'index avançait à l'ouverture, donc un dialogue interrompu
        était quand même 'consommé'). À la place, on retient le PNJ actif
        dans self._pnj_actif ; quand la boîte se ferme (cf. update_play),
        on appelle pnj.passer_a_suivante() pour avancer proprement."""
        print(f"PNJs dispo : {self.editeur.pnjs}")
        for pnj in self.editeur.pnjs:
            if pnj.peut_interagir(self.joueur.rect):
                lignes = pnj.conversation_actuelle()
                if lignes:
                    self.dialogue.demarrer(lignes)
                    self._pnj_actif = pnj
                return

    # ═════════════════════════════════════════════════════════════════════════
    # 8.  LOGIQUE PAR ÉTAT (MENU, PAUSE, GAME_OVER)
    # ═════════════════════════════════════════════════════════════════════════

    def _lancer_fondu_menu(self, action):
        """Lance un fondu noir depuis le menu, puis exécute `action()`.

        Pourquoi ? Pour ne pas avoir de passage brutal du menu titre au
        jeu. La musique du menu s'éteint en 4 s, l'effet "rayons de
        lumière" (effet_reveil) commence à s'estomper IMMÉDIATEMENT
        (forcer_extinction) — l'utilisateur garde un petit halo de
        l'écran-titre pendant qu'il entre dans le jeu / l'éditeur, qui
        disparaît sur ~8 s.
        """
        self._menu_fondu_etat   = "out"
        self._menu_fondu_alpha  = 0
        self._menu_fondu_action = action
        # Fadeout musique 4 s → laisse l'ambiance "bonne nuit" s'estomper
        # progressivement plutôt que se couper sec.
        music.arreter(fadeout_ms=4000)
        # Effet de réveil : commence à descendre TOUT DE SUITE (sans
        # attendre que la musique se coupe). Vitesse 0.12 → ~8 s avant
        # disparition complète, donc on garde un halo pendant les
        # premières secondes en éditeur / jeu.
        self.effet_reveil.forcer_extinction()

    def _gerer_menu(self, events):
        """Gestion du menu titre (état MENU)."""
        # Si un fondu menu→jeu est en cours, on n'accepte plus d'input.
        if self._menu_fondu_etat != "none":
            return

        for event in events:
            if event.type != pygame.KEYDOWN:
                continue

            choix = self.menu_titre.handle_key(event.key)

            if choix == "Continuer":
                # Lambda = mini-fonction créée à la volée, voir [D34].
                self._lancer_fondu_menu(lambda: self._charger_partie())

            elif choix == "Nouvelle partie":
                # On utilise une vraie fonction locale pour pouvoir
                # écrire plusieurs lignes (une lambda ne fait qu'une expression).
                def _action():
                    self.mode = "histoire"
                    self._nouvelle_partie()
                self._lancer_fondu_menu(_action)

            elif choix == "Mode éditeur":
                self.mode = "editeur"
                maps = self.editeur._list_maps()
                opts = ["Nouvelle carte"] + maps
                self._menu_choix_carte = Menu(
                    opts, title="Ouvrir une carte", style="titre",
                )

            elif choix == "Quitter":
                self.running = False

    def _gerer_pause(self, events):
        """Gestion du menu pause (état PAUSE)."""
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue

            # L'écran Paramètres capture TOUS les inputs quand il est ouvert.
            if self.parametres.visible:
                self.parametres.handle_key(event.key)
                continue

            # Échap ferme la pause.
            if event.key == pygame.K_ESCAPE:
                self.etats.switch(GAME)
                return

            choix = self.menu_pause.handle_key(event.key)
            if choix == "Reprendre":
                self.etats.switch(GAME)
            elif choix == "Paramètres":
                self.parametres.open()
            elif choix == "Sauvegarder":
                self._sauvegarder()
            elif choix == "Menu principal":
                self._menu_fondu_etat  = "none"
                self._menu_fondu_alpha = 0
                music.transition(
                    self._musique_menu, volume=0.7,
                    fadeout_ms=600, fadein_ms=1500,
                )
                # On revient au menu → l'effet_reveil reprend son
                # comportement normal (synchronisé sur la musique).
                self.effet_reveil.reactiver()
                self.etats.switch(MENU)
            elif choix == "Quitter":
                self.running = False

    def _gerer_fin(self, events):
        """Gestion de l'écran Game Over (état GAME_OVER)."""
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue

            choix = self.menu_fin.handle_key(event.key)
            if choix == "Recommencer":
                music.arreter(fadeout_ms=400)
                self._nouvelle_partie()
            elif choix == "Menu principal":
                self._menu_fondu_etat  = "none"
                self._menu_fondu_alpha = 0
                music.transition(
                    self._musique_menu, volume=0.7,
                    fadeout_ms=600, fadein_ms=1500,
                )
                self.effet_reveil.reactiver()
                self.etats.switch(MENU)

    # ═════════════════════════════════════════════════════════════════════════
    # 9.  MISE À JOUR DU JEU — appelée chaque frame en état GAME
    # ═════════════════════════════════════════════════════════════════════════
    #
    # C'est la plus longue méthode du fichier, mais elle est découpée en
    # étapes bien séparées :
    #
    #     1. Si un scénario "histoire" est actif → lui donner la main
    #     2. Gestion des événements clavier / souris (beaucoup de cas)
    #     3. Physique du joueur
    #     4. Mise à jour des ennemis
    #     5. Résolution des combats (attaques, contacts)
    #     6. Collisions joueur / plateformes / murs / décors
    #     7. Collisions ennemis / décor
    #     8. Déclenchement des effets visuels
    #     9. Mise à jour des systèmes (lumière, peur, portails, fondu, …)
    #    10. Mort → Game Over

    def _update_jeu(self, events, dt):
        # ── 1. Gestionnaire histoire (prioritaire) ────────────────────────
        if self.gestionnaire_histoire.actif:
            for event in events:
                self.gestionnaire_histoire.handle_event(event)
            return

        # ── 2. Événements clavier / souris ────────────────────────────────
        self._traiter_evenements_jeu(events)

        # ── 3-9. Logique de simulation ────────────────────────────────────
        self._simuler_jeu(dt)

        # ── 10. Mort → Game Over ──────────────────────────────────────────
        if self.joueur.dead:
            self.etats.switch(GAME_OVER)
            self.menu_fin.selection = 0

        # Drag-and-drop dans l'inventaire
        self.inventory.drag_drop(events)

    # ─── Sous-routines de _update_jeu ────────────────────────────────────────

    def _traiter_evenements_jeu(self, events):
        """Traite chaque event du frame (clavier, souris, molette)."""
        # Si un éditeur overlay (cine, pnj ou journal) est ouvert, il consomme
        # TOUS les events clavier (le jeu en arrière-plan reste figé).
        cine    = getattr(self.editeur, "cine_editor", None)
        pnj_ed  = getattr(self.editeur, "pnj_editor",  None)
        journal = self.journal_dialogues
        cine_open    = cine is not None and cine.actif
        pnj_open     = pnj_ed is not None and pnj_ed.actif
        journal_open = journal is not None and journal.actif
        overlay = (cine if cine_open
                   else pnj_ed if pnj_open
                   else journal if journal_open
                   else None)

        for event in events:
            if overlay is not None:
                if event.type == pygame.KEYDOWN:
                    mods = pygame.key.get_mods()
                    overlay.handle_key(event.key, mods)
                elif event.type == pygame.TEXTINPUT:
                    overlay.handle_textinput(event.text)
                continue

            # ── Clavier (touches pressées) ──
            if event.type == pygame.KEYDOWN:
                self._gerer_touche(event.key)

            # ── Saisie de texte (pour les PNJ dans l'éditeur) ──
            if event.type == pygame.TEXTINPUT:
                if self.editeur.active and self.editeur._text_mode:
                    self.editeur.handle_textinput(event.text)

            # ── Souris dans l'éditeur (clic / molette) ──
            if self.editeur.active and self.editeur._text_mode is None:
                self._gerer_souris_editeur(event)

            # ── Caméra libre (clic molette pour pan / mode décor 9) ──
            self._gerer_clic_molette(event)

    def _gerer_touche(self, key):
        """Dispatche une touche vers l'action correspondante."""
        # F1 : overlay d'aide.
        if key == pygame.K_F1:
            self.aide.toggle()
            return

        # Échap ferme l'aide en priorité si elle est ouverte.
        if self.aide.visible and key == pygame.K_ESCAPE:
            self.aide.close()
            return
        
        # Si boutique est active : Espace/Entrée avance le texte.
        
        if self.boutique.actif :
            item = self.boutique.handle_key(key, self.joueur)
            if item:
                nom = item["nom"]
                self.inventory.add_item(item["nom"])
                self.boutique._show_msg = f"{item['nom']} acheté !"
                if nom in ITEMS:
                    self.inventory.add_item(nom)
                elif nom.capitalize() in ITEMS:
                    self.inventory.add_item(nom.capitalize())
                else:
                    print(f"Item inconnu dans ITEMS : '{nom}'")
                    print(f"Items disponibles : {list(ITEMS.keys())}")
            if key == pygame.K_ESCAPE : 
                self.boutique.fermer()
            return

        # Si un dialogue est actif : Espace/Entrée avance le texte.
        if self.dialogue.actif and key in (pygame.K_SPACE, pygame.K_RETURN):
            self.dialogue.avancer()
            return

        # Si l'overlay "fear text" est visible : Espace = fade-out immédiat.
        # Placé APRÈS le dialogue pour ne pas le voler quand un PNJ parle.
        if self.fear_overlay.actif and key == pygame.K_SPACE:
            self.fear_overlay.skip()
            return

        # Échap :
        #   1. Saisie texte éditeur ouverte → on annule la saisie.
        #   2. Cinématique en cours          → on la SKIPE entièrement.
        #   3. Sinon                         → menu pause.
        if key == pygame.K_ESCAPE:
            if self.editeur.active and self.editeur._text_mode:
                self.editeur.handle_key(key)
            elif self.cutscene is not None:
                # Skip : on saute jusqu'à la fin et on libère tout.
                self._skipper_cinematique()
            elif not self.dialogue.actif:
                self.etats.switch(PAUSE)
                self.menu_pause.selection = 0
            return

        # ── Saisie texte de l'éditeur OUVERTE ? ─────────────────────────────
        # Quand une popup demande de taper un texte (nom de map, dialogue
        # PNJ, paramètres de fear zone, etc.), TOUTES les autres touches
        # (E, C, TAB, J, H, F4...) doivent être traitées comme du texte
        # à saisir, PAS comme des raccourcis. Sinon impossible d'écrire
        # "Ne reste pas là" parce que le E fermerait l'éditeur, le C
        # appellerait les compagnons, etc. Échap sert toujours à annuler
        # (déjà géré juste au-dessus).
        if self.editeur.active and self.editeur._text_mode:
            resultat = self.editeur.handle_key(key)
            self._traiter_resultat_editeur(resultat)
            return

        # TAB : ouvrir/fermer l'inventaire.
        if key == pygame.K_TAB:
            self.inventory.changer_etat_fenetre()
            return

        # C : compagnons → cape.
        if key == pygame.K_c and not self.editeur.active:
            self.compagnons.toggler_cape()
            return

        # E : interagir (mode histoire) ou toggler éditeur (mode éditeur,
        # éditeur actif → ferme pour tester ; sinon → parle aux PNJ).
        if key == pygame.K_e:
            self._gerer_touche_e()
            return

        # F4 : toggle éditeur (mode 'editeur' uniquement). Permet de revenir
        # à l'édition après un test, sans utiliser [E] qui est devenu dédié
        # à l'interaction avec les PNJ pendant le test.
        if key == pygame.K_F4:
            self._toggle_editeur()
            return

        # J : Journal des dialogues (relire ce qu'un PNJ a dit). N'ouvre que
        # si l'éditeur n'est pas actif (sinon J est utilisé en mode mob).
        if key == pygame.K_j and not self.editeur.active and not self.dialogue.actif:
            self.journal_dialogues.ouvrir(self.historique_dialogues)
            return

        # H : ouvre le gestionnaire d'histoire (éditeur uniquement).
        if key == pygame.K_h and not self.editeur.active:
            if self.mode == "editeur":
                maps_dispo = self.editeur._list_maps()
                self.gestionnaire_histoire.ouvrir(maps_dispo)
            return

        # Toute autre touche : l'éditeur la reçoit s'il est actif.
        if self.editeur.active:
            resultat = self.editeur.handle_key(key)
            self._traiter_resultat_editeur(resultat)

    def _gerer_touche_e(self):
        """Gère l'appui sur E selon le mode et l'état de l'éditeur.

        - Mode 'histoire' : E parle aux PNJ.
        - Mode 'editeur' éditeur ACTIF : E ferme l'éditeur (test de la map).
        - Mode 'editeur' éditeur INACTIF : E parle aux PNJ (= test grandeur
          nature). Pour ré-ouvrir l'éditeur après avoir testé, utiliser [F4]."""
        if self.mode == "editeur":
            if self.editeur.active and self.editeur._text_mode:
                return
            if self.editeur.active:
                # On sort de l'éditeur pour tester la map.
                self.editeur.toggle()
                self.joueur.reload_hitbox()
            else:
                # Éditeur fermé pendant un test → E doit parler aux PNJ.
                if not self.dialogue.actif:
                    self._tenter_interaction()

        elif self.mode == "histoire" and not self.dialogue.actif:
            self._tenter_interaction()

    def _toggle_editeur(self):
        """[F4] : (re)bascule l'éditeur en mode éditeur. Sert à revenir à
        l'édition après avoir testé la map (puisque [E] est dédié aux PNJ
        pendant le test)."""
        if self.mode != "editeur":
            return
        if self.editeur.active and self.editeur._text_mode:
            return
        etait_actif = self.editeur.active
        self.editeur.toggle()
        if etait_actif and not self.editeur.active:
            self.joueur.reload_hitbox()

    def _traiter_resultat_editeur(self, resultat):
        """Gère la valeur renvoyée par editeur.handle_key()."""
        if resultat in ("done", "undo", "structure"):
            # Modification structurelle → recalculs.
            self._reconstruire_grille()
            self._murs_modifies()
            self._sync_triggers()
        elif resultat and resultat.startswith("set_start:"):
            # Résultat au format "set_start:nom_de_la_carte"
            nom = resultat.split(":", 1)[1]
            config = lire_config()
            config["carte_debut"] = nom
            ecrire_config(config)
            self.editeur._show_msg(f"Carte de départ définie : {nom}")

    def _gerer_souris_editeur(self, event):
        """Clics et molette dans l'éditeur (sauf clic molette, géré ailleurs)."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                # Clic gauche : place ce qui est sélectionné.
                nb_avant = len(self.platforms)
                self.editeur.handle_click(event.pos)
                if len(self.platforms) != nb_avant:
                    self._reconstruire_grille()
                self._murs_modifies()
            elif event.button == 3:
                # Clic droit : supprime.
                nb_avant = len(self.platforms)
                self.editeur.handle_right_click(event.pos)
                if len(self.platforms) != nb_avant:
                    self._reconstruire_grille()
                self._murs_modifies()

        if event.type == pygame.MOUSEWHEEL:
            # Molette en mode caméra libre (sans Ctrl) : pan vertical.
            if self.camera.free_mode and not pygame.key.get_pressed()[pygame.K_LCTRL]:
                self.camera.pan_scroll(event.y)
            else:
                self.editeur.handle_scroll(event.y)

    def _gerer_clic_molette(self, event):
        """Clic molette (bouton 2) pour pan caméra ou toggle décor."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
            if self.editeur.active and self.camera.free_mode:
                self.camera.start_drag(event.pos)
            elif self.editeur.active and self.editeur.mode == 9:
                # Mode 9 = édition des collisions de décor.
                wx = int(event.pos[0] + self.camera.offset_x)
                wy = int(event.pos[1] + self.camera.offset_y)
                self.editeur.toggle_decor_collision_at(wx, wy)

        if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self.camera.stop_drag()

        if event.type == pygame.MOUSEMOTION and self.camera._drag_active:
            self.camera.update_drag(event.pos)

    def respawn_player_at(self, x, y):
        """Téléporte le joueur au point de respawn spécifique et reset sa physique."""
        # 1. On déplace le joueur
        self.joueur.rect.x = x
        self.joueur.rect.y = y
        
        # 2. pn reset les vitesses (important pour pas qu'il garde son élan)
        if hasattr(self.joueur, 'vel_x'): self.joueur.vel_x = 0
        if hasattr(self.joueur, 'vel_y'): self.joueur.vel_y = 0
        
        # 3. petit effet visuel (ScreenShake) puisque tu as le système juice
        if hasattr(self, "shake"):
            self.shake.ajouter(duration=0.2, amplitude=8) # secousse de 0.2s
        

    def _simuler_jeu(self, dt):
        """Physique, collisions, effets, systèmes. Appelé après les events."""
        keys = pygame.key.get_pressed()

        # Active/détecte la manette et lit ses axes (écrit dans settings.axis_x/y).
        man_on()
        x_y_man()

        trous = self.editeur.holes
        murs  = self._murs_actifs()

        # ── Hit-pause : si un impact vient d'avoir lieu, on gèle dt ──
        # La simulation ne bouge pas pendant quelques ms, ce qui fait
        # "sentir" l'impact physique dans Hollow Knight.
        if self.hitpause.is_active():
            self.hitpause.tick(dt)
            phys_dt = 0.0                               # on gèle la physique
        else:
            phys_dt = dt

        # On bloque aussi le mouvement pendant un fondu, un dialogue ou
        # une cinématique en cours.
        mouvement_bloque = (self._fondu_etat != "none"
                            or self.dialogue.actif
                            or self.cutscene is not None)
        if not mouvement_bloque:
            self.joueur.mouvement(phys_dt, keys, holes=trous)

        self.camera.update(self.joueur.rect)

        # Mémorise l'état AVANT mise à jour (pour détecter les événements).
        hp_avant            = self.joueur.hp
        ennemis_alive_avant = [e for e in self.ennemis if e.alive]

        self.ennemis[:] = [e for e in self.ennemis if e.alive or not e.animations["die"].done]

        # ── Mise à jour des entités (Ennemis et Boss) ──
        for entite in self.ennemis:
            # 1. On vérifie si c'est un boss spécial (qui a besoin du joueur entier)
            # hasattr vérifie si l'objet possède la variable ou la méthode indiquée
            if hasattr(entite, 'liste_souvenirs') or hasattr(entite, 'capturer_etat_joueur'):
                # Logique BOSS : On lui passe le joueur et le temps (dt)
                entite.update(phys_dt, self.joueur)
            else:
                # Logique ennemi simple 
                entite.update(phys_dt, self.platforms, murs, self.joueur.rect, holes=trous)

            # 2. Gestion des collisions (Dégâts reçus par le joueur) - UNIQUEMENT si l'entité est vivante
            if entite.alive and self.joueur.rect.colliderect(entite.rect):
                # On utilise ta fonction de recul/dégâts
                self.joueur.hit_by_enemy(entite.rect)
                
            # 3. Cas spécial pour le Boss Tempête - UNIQUEMENT si le boss est vivant
            if entite.alive and hasattr(entite, 'liste_souvenirs'):
                # On vérifie si le joueur touche un des souvenirs dans la liste du boss
                for s in entite.liste_souvenirs:
                    if s["actif"] and self.joueur.rect.colliderect(s["rect"]):
                        if s["est_bon"]:
                            entite.souvenirs_clairs_collectes += 1
                            s["actif"] = False
                        else:
                            self.joueur.hit_by_enemy(s["rect"])
                            s["actif"] = False
            
            # 4. cas spécial pour le Boss Explosion - UNIQUEMENT si le boss est vivant
            if entite.alive and hasattr(entite, 'liste_zones_danger'):
                for zone in entite.liste_zones_danger:
                    if zone["explosion_faite"]:
                        if self.joueur.rect.colliderect(zone["rect"]):
                            self.joueur.hit_by_enemy(entite.rect)

        # ── Combat : attaques du joueur sur les ennemis ──
        resoudre_attaques_joueur(self.joueur, self.ennemis)

        # ── Pogo : l'attaque-bas qui touche → rebond ──
        if (self.joueur.attacking
                and self.joueur.attack_dir == "down"
                and self.joueur._attack_buffered):
            for e in self.ennemis:
                if e.alive and e.rect.colliderect(self.joueur.attack_rect):
                    self.joueur.on_pogo_hit()
                    break

        # ── Collisions du joueur ──
        appliquer_plateformes(self.joueur, self.grille_plateformes)

        if not self.editeur.active:
            for zone in self.editeur.danger_zones:
                if self.joueur.rect.colliderect(zone["rect"]):
                    rx, ry = zone["respawn_pos"]
                    self.respawn_player_at(rx, ry)
                    break

        if not self.editeur.active:
            resoudre_contacts_ennemis(self.joueur, self.ennemis, hud=self.hud)

        for mur in murs:
            mur.verifier_collision(self.joueur)

        # Décors avec collision (comme des plateformes)
        for decor in self.editeur.decors:
            if decor.collision:
                decor.verifier_collision(self.joueur)

        # Toutes les collisions horizontales sont faites → on peut détecter
        # si on est contre un mur pour activer le wall-slide (voir player.py).
        self.joueur.post_physics()

        # ── Collisions des ennemis avec le décor ──
        for ennemi in self.ennemis:
            if ennemi.alive:
                self._collisions_ennemis(ennemi, murs)

        # ── Effets visuels ──
        self._declencher_effets_joueur(hp_avant, dt)
        self._declencher_effets_ennemis(ennemis_alive_avant)

        # ── Animation des PNJ ──
        for pnj in self.editeur.pnjs:
            # Physique active EN PERMANENCE (comme les ennemis). Si on les
            # pose en l'air dans l'éditeur, ils tombent au sol — c'est le
            # comportement attendu pour des ENTITÉS (vs des blocs statiques).
            pnj.update_physique(phys_dt, self.grille_plateformes,
                                self.editeur.holes)
            pnj.update()

        # ── Systèmes transversaux ──
        self.lumieres.update(dt)
        self._sync_lumieres_ennemis()
        self._verifier_portails()
        self._update_fondu(dt)
        self.dialogue.update(dt)

        # ── PNJ : on avance la conversation seulement quand le joueur a
        # FINI de la lire (boîte fermée). Évite que l'index avance dès
        # l'ouverture, ce qui sautait des dialogues si on s'éloignait.
        if self._pnj_actif is not None and not self.dialogue.actif:
            # On enregistre la conversation qui vient d'être lue dans le
            # journal AVANT d'avancer l'index (sinon on logguerait celle
            # d'après).
            self._logger_dialogue(self._pnj_actif)
            self._pnj_actif.passer_a_suivante()
            if isinstance(self._pnj_actif, Marchand):
                self.boutique.ouvrir(self._pnj_actif.inventaire)
            self._pnj_actif = None

        # Zones-déclencheurs (téléportation / cinématiques) — front-montant
        # sur la collision joueur/zone. Vide tant qu'aucune carte n'en pose.
        self.triggers.check(self.joueur, {"game": self})

        # Cinématique en cours : on l'avance, et quand elle est terminée
        # on rend la main au joueur. Le contexte donne accès à camera,
        # joueur, dialogue_box, particles, shake, son, pnjs (cf. CutsceneContext).
        if self.cutscene is not None:
            # Stoppe net la marche du joueur : sinon il garde sa vitesse et
            # son animation walking jusqu'à la fin de la cinématique. Le son
            # de pas est aussi arrêté pour éviter qu'il continue.
            self.joueur.vx           = 0
            self.joueur.knockback_vx = 0
            self.joueur.walking      = False
            try:
                from audio import sound_manager
                sound_manager.arreter("pas")
            except Exception:
                pass

            from systems.cutscene import CutsceneContext
            self.cutscene.update(dt, CutsceneContext(self))
            if self.cutscene.is_done():
                self.cutscene = None
                self.state    = "play"
                # Sécurité : on libère la caméra cinématique au cas où une
                # étape l'aurait laissée active.
                if hasattr(self.camera, "release_cinematic"):
                    self.camera.release_cinematic()

        # Compagnons : IA + nouveau calcul du STADE de peur (5 niveaux discrets).
        # Règle : stade = 5 - nb_proches + nb_loin (clampé). Voir compagnons.py.
        self.compagnons.update(dt, self.joueur)
        target_stade = self.compagnons.calcul_stade_peur(self.joueur,
                                                         FearSystem.NB_STADES)
        self.peur.set_target_stade(target_stade)
        self.peur.update(dt)

        # Fear zones : ralentissement + texte + mur invisible si peur trop forte.
        # On délègue à _appliquer_fear_zones() pour garder ce bloc lisible.
        self._appliquer_fear_zones()

        self.hud.update(dt, self.joueur, self.peur)
        # L'overlay texte se met à jour aussi (pour le fade in/out).
        self.fear_overlay.update(dt)

        # Particules et shake (le shake continue pendant la hit-pause
        # pour qu'on sente bien l'impact).
        self.particles.update(dt)
        self.camera.shake_offset = self.shake.update(dt)
        self.hp_overlay.update(dt)

    # ═════════════════════════════════════════════════════════════════════════
    # 9b. FEAR ZONES — ralentissement progressif + mur côté direction_mur
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Logique appliquée chaque frame, depuis update() :
    #
    #    1) On parcourt les fear_zones de la carte.
    #    2) Si le joueur EST dans la zone :
    #         a) On garde le facteur de vitesse le plus contraignant
    #            (= le plus petit) parmi les zones où il se trouve.
    #         b) On affiche le texte d'avertissement (si stade > peur_max).
    #         c) On érige un mur invisible sur le côté `direction_mur`
    #            (par défaut "d" = droite) → le joueur ne peut PAS
    #            franchir cette frontière tant qu'il a trop peur.
    #    3) Si aucune zone ne le ralentit → multiplier = 1.0.
    #    4) Si le joueur est SORTI de toutes les zones → on cache l'overlay.
    #
    #  POURQUOI LE MUR REVIENT-IL ?
    #  ----------------------------
    #  Sans mur, une zone de peur reste juste "lente" : le joueur peut
    #  passer à 35 % de vitesse, c'est pénible mais pas un vrai obstacle
    #  scénaristique. Avec le mur (côté direction_mur uniquement), on a
    #  un VRAI gate : tu DOIS avoir assez de lucioles pour franchir. Pour
    #  les autres côtés (les bords sans mur), le joueur peut toujours
    #  rebrousser chemin → pas de piège, juste une frontière dirigée.
    #
    #  RÈGLE ANTI-BLOCAGE :
    #  Le multiplicateur de vitesse a un PLANCHER (FEAR_ZONE_VITESSE_MIN
    #  = 0.35). Donc même si tu rentres dans la zone et heurtes le mur,
    #  tu peux toujours marcher pour reculer et en sortir par l'autre
    #  côté. Ce qui résout le bug initial "je rentre un poil et je suis
    #  coincé" tout en gardant la sensation d'un vrai obstacle.

    def _appliquer_fear_zones(self):
        """Calcule self._mult_vitesse_peur, déclenche overlay et mur."""

        # Sans triggers (carte sans fear_zone), on remet les défauts et basta.
        if not hasattr(self, "triggers") or self.triggers is None:
            self.joueur.speed_multiplier = 1.0
            return

        from world.triggers import FearZoneTrigger
        stade = self.peur.get_stade()

        mult_min = 1.0          # Le plus petit (= plus pénalisant) gagne.
        in_zone  = False        # Y a-t-il au moins une zone qui me contient ?
        texte_a_afficher = None
        rect_mur = None         # Le mur le plus contraignant (1 seul à la fois).
        zone_mur = None         # La zone correspondante (pour le côté).

        for zone in self.triggers.zones:
            if not isinstance(zone, FearZoneTrigger):
                continue
            if not zone.rect.colliderect(self.joueur.rect):
                continue

            in_zone = True
            # Facteur PROGRESSIF : varie selon la position du joueur dans
            # la zone. Loin du mur = peu pénalisé. Collé au mur = maximum
            # de ralentissement. Donne un feedback kinesthétique qui
            # indique au joueur dans quel sens fuir.
            facteur = zone.facteur_vitesse_progressif(stade, self.joueur.rect)
            if facteur < mult_min:
                mult_min = facteur

            # Si trop de peur pour cette zone : afficher le texte + mur.
            if stade > zone.peur_max:
                texte_a_afficher = zone.texte
                rect_mur = zone.rect_mur()
                zone_mur = zone

        # Applique le multiplicateur de vitesse au joueur. Lu chaque frame
        # par player.py, à la fois pour la marche/course ET le dash/slide
        # (cf. entities/player.py — la vitesse est ralentie partout).
        self.joueur.speed_multiplier = mult_min

        # ── Direction du mur + bonus de RECUL ──────────────────────────
        # On expose au joueur la direction de la "menace" pour qu'il
        # puisse appliquer un multiplicateur PLUS PERMISSIF quand il va
        # dans le sens OPPOSÉ (= il essaie de sortir de la zone).
        # Sans ça, à 8 % de vitesse, le joueur croit être bloqué quand
        # il appuie pour reculer.
        #
        # Convention :
        #   fear_wall_dir = "d" / "g" / "h" / "b" / None
        #   fear_recul_mult = vitesse en repli (typiquement 0.75)
        #
        # entities/player.py fait le test "ax va dans le sens OPPOSÉ au
        # mur ? Alors j'utilise fear_recul_mult au lieu de speed_multiplier".
        if zone_mur is not None:
            self.joueur.fear_wall_dir = zone_mur.direction_mur
            try:
                import settings as _s
                self.joueur.fear_recul_mult = _s.FEAR_ZONE_VITESSE_RECUL
            except (ImportError, AttributeError):
                self.joueur.fear_recul_mult = 0.75
        else:
            # Pas de mur (zone inactive ou peur OK) → on neutralise.
            self.joueur.fear_wall_dir = None
            self.joueur.fear_recul_mult = 1.0

        # Affichage du texte (seulement si on est dans une zone trop dure).
        # On laisse FearOverlay choisir lui-même sa police "mystère"
        # (cf. ui/fear_overlay.py) — pas besoin d'injecter celle du HUD,
        # qui ne donne pas l'ambiance voulue (Consolas trop "code").
        if texte_a_afficher:
            self.fear_overlay.show(texte_a_afficher)

        # Plus dans aucune zone trop dure → on fait disparaître l'overlay.
        if not in_zone:
            self.fear_overlay.hide()

        # ── Mur invisible côté `direction_mur` ──────────────────────────────
        # Le mur est une fine bande (8 px) sur le bord `direction_mur` de
        # la zone. On bloque la traversée dans LES DEUX SENS à travers
        # cette bande : que le joueur arrive de l'extérieur ou tente de
        # sortir de l'intérieur, il est repoussé du côté où il se trouve
        # déjà (push perpendiculaire au mur, vers le centre de masse du
        # joueur). Les autres bords de la zone restent libres → on peut
        # toujours rebrousser chemin pour ressortir, donc pas de piège.
        if rect_mur and zone_mur and self.joueur.rect.colliderect(rect_mur):
            r = self.joueur.rect
            cote = zone_mur.direction_mur

            if cote in ("d", "g"):
                # Mur vertical : on regarde sur quelle face du mur le
                # joueur se trouve (centerx) et on le pousse de ce côté.
                if r.centerx < rect_mur.centerx:
                    r.right = rect_mur.left
                else:
                    r.left = rect_mur.right
                self.joueur.vx = 0
            else:
                # Mur horizontal ("h" = haut, "b" = bas).
                if r.centery < rect_mur.centery:
                    r.bottom = rect_mur.top
                else:
                    r.top = rect_mur.bottom
                self.joueur.vy = 0

    # ═════════════════════════════════════════════════════════════════════════
    # 10.  RENDU — dessine le monde et les interfaces
    # ═════════════════════════════════════════════════════════════════════════
    #
    # ORDRE IMPORTANT : pygame dessine les choses DANS L'ORDRE où on
    # l'appelle. Ce qui est dessiné en dernier est AU-DESSUS.
    # Calques utilisés, du plus profond au plus haut :
    #
    #     1. Fond uni (couleur de la map)
    #     2. Murs de bordure + murs custom
    #     3. Trous (peints couleur du fond pour "effacer" le sol)
    #     4. Plateformes
    #     5. Décors
    #     6. Ennemis, PNJ
    #     7a. Lucioles "derrière" (z < 0)  — masquées par le joueur
    #     7b. Joueur
    #     8. Lucioles "devant" (z >= 0)    — recouvrent le joueur
    #     9. Particules
    #    10. Portails (seulement en mode debug)
    #    11. Overlays éditeur
    #    12. Éclairage (voile sombre + halos)
    #    13. Outils éditeur (aperçu, HUD éditeur)
    #    14. FPS + nom de la carte
    #    15. Indicateur H/E
    #    16. Overlay PV bas (vignette rouge)
    #    17. HUD principal (cœurs + peur)
    #    18. Gestionnaire histoire
    #    19. Inventaire
    #    20. Dialogue
    #    21. Aide F1
    #    22. Fondu enchaîné

    def _dessiner_monde(self):
        # ── ZOOM CAMÉRA ────────────────────────────────────────────────────
        # Si camera.zoom != 1.0, on rend le monde sur une surface buffer
        # de taille écran//zoom_entier, puis on scale ce buffer sur l'écran
        # réel à la fin. zoom > 1 = rapproche (perso plus gros, vue plus
        # serrée). zoom < 1 = dézoome (perso plus petit, vue plus large).
        #
        # PIXEL ART CRISP — On utilise un facteur de zoom ENTIER pour le
        # rendu. Raison : pygame.transform.scale() fait du nearest-neighbor ;
        # avec un zoom fractionnaire (ex. 1.5×), certains pixels source
        # deviennent 1 px à l'écran et d'autres 2 px → pixel art flou /
        # irrégulier. En arrondissant à l'ENTIER le plus proche (1, 2, 3…),
        # chaque pixel source devient exactement N pixels d'écran → sprite
        # parfaitement net. La valeur float de `zoom` reste stockée et
        # éditable (UI, save), elle est juste arrondie au moment du rendu.
        _real_screen = self.screen
        _zoom = getattr(self.camera, "zoom", 1.0) or 1.0
        _int_zoom = max(1, int(round(_zoom)))
        if _int_zoom != 1:
            rw, rh = _real_screen.get_size()
            bw = max(1, rw // _int_zoom)
            bh = max(1, rh // _int_zoom)
            buf = getattr(self, "_zoom_buffer", None)
            if buf is None or buf.get_size() != (bw, bh):
                self._zoom_buffer = pygame.Surface((bw, bh))
            self.screen = self._zoom_buffer

        # 1. Fond : noir partout, puis couleur d'éditeur seulement DANS la zone
        # jouable (entre SCENE_LEFT et SCENE_WIDTH). Du coup les marges hors
        # monde apparaissent en noir → on voit nettement les bords de la map
        # quand elle est plus petite que l'écran.
        self.screen.fill((0, 0, 0))
        couleur_fond = tuple(self.editeur.bg_color)
        rect_monde = pygame.Rect(
            settings.SCENE_LEFT - int(self.camera.offset_x),
            settings.CEILING_Y  - int(self.camera.offset_y),
            self.camera.scene_width - settings.SCENE_LEFT,
            settings.GROUND_Y - settings.CEILING_Y,
        )
        # Clamp aux bords de l'écran (pygame ne dessine pas hors écran de
        # toute façon, mais évite les valeurs négatives énormes).
        sw, sh = self.screen.get_size()
        rect_clip = rect_monde.clip(pygame.Rect(0, 0, sw, sh))
        if rect_clip.width > 0 and rect_clip.height > 0:
            self.screen.fill(couleur_fond, rect_clip)

        # 2. Murs.
        for mur in self.editeur.all_segments():
            if self.camera.is_visible(mur.rect):
                mur.draw(self.screen, self.camera)
        for mur in self.editeur.custom_walls:
            if self.camera.is_visible(mur.rect):
                mur.draw(self.screen, self.camera)

        # 3. Trous (même couleur que le fond = ça "efface" le sol).
        for trou in self.editeur.holes:
            if self.camera.is_visible(trou):
                rect_ecran = self.camera.apply(trou)
                pygame.draw.rect(self.screen, couleur_fond, rect_ecran)
                # En mode éditeur + hitbox ON : contour rouge pour les voir.
                if self.editeur.active and self.editeur.show_hitboxes:
                    pygame.draw.rect(self.screen, (255, 80, 80), rect_ecran, 2)

        # 4. Plateformes.
        for plateforme in self.platforms:
            if self.camera.is_visible(plateforme.rect):
                plateforme.draw(self.screen, self.camera)
                # En mode éditeur, on dessine un contour discret même quand
                # la plateforme est color=None (invisible en jeu). Sans ça,
                # impossible de voir/éditer les collisions des maps Tiled.
                if self.editeur.active:
                    couleur = (255, 255, 255) if self.editeur.show_hitboxes \
                              else (180, 180, 180)
                    pygame.draw.rect(self.screen, couleur,
                                     self.camera.apply(plateforme.rect), 1)

        # 5. Décors.
        for decor in self.editeur.decors:
            if self.camera.is_visible(decor.rect):
                decor.draw(self.screen, self.camera)
                if self.editeur.active and self.editeur.show_hitboxes and decor.collision:
                    pygame.draw.rect(self.screen, (255, 100, 0),
                                     self.camera.apply(decor.collision_rect), 1)

        # 6. Ennemis et PNJ.
        for ennemi in self.ennemis:
            if self.camera.is_visible(ennemi.rect):
                ennemi.draw(self.screen, self.camera, self.editeur.show_hitboxes)

        for pnj in self.editeur.pnjs:
            if self.camera.is_visible(pnj.rect):
                pnj.draw(self.screen, self.camera, self.joueur.rect)
                # Objets parlants (PNJ avec sprite invisible) : on dessine
                # un contour pointillé violet en mode éditeur pour qu'on
                # puisse les retrouver. Invisibles en jeu, of course.
                if (self.editeur.active and pnj.sprite_name
                        and pnj.sprite_name.startswith("objet_parlant_")):
                    pygame.draw.rect(self.screen, (180, 100, 220),
                                     self.camera.apply(pnj.rect), 1)

        # 7a. Lucioles "derrière" (z < 0) : dessinées AVANT le joueur,
        #     donc le joueur les masque si elles passent pile derrière lui.
        #     Effet de profondeur 3D bon marché.
        self.compagnons.draw_derriere(self.screen, self.camera, self.joueur)

        # 7b. Joueur.
        self.joueur.draw(self.screen, self.camera, self.editeur.show_hitboxes)
        self.joueur.draw_slash(self.screen, self.camera)

        # 8. Lucioles "devant" (z >= 0) : dessinées APRÈS le joueur,
        #     elles passent par-dessus lui.
        self.compagnons.draw_devant(self.screen, self.camera, self.joueur)

        # 9. Particules.
        self.particles.draw(self.screen, self.camera)

        # 10. Portails (visibles seulement avec hitbox ou éditeur actif).
        if self.editeur.show_hitboxes or self.editeur.active:
            police = self.editeur._get_font()
            for portail in self.editeur.portals:
                portail.draw(self.screen, self.camera, police)

        # 10.b Zones-déclencheurs (rectangles colorés) — éditeur uniquement.
        # Vert = téléportation, jaune = cinématique. cf. world/triggers.py
        if self.editeur.active:
            self.triggers.draw_debug(
                self.screen, self.camera, self.editeur._get_font()
            )

        # 11. Overlays éditeur.
        if self.editeur.active:
            self.editeur.draw_overlays(self.screen)

        # 12. Éclairage (voile sombre + halos autour du joueur/torches).
        self.lumieres.render(self.screen, self.camera, self.joueur.rect)

        # 13a. Aperçu éditeur (monde-aligné : reste sur le buffer zoomé
        # pour que la preview soit à la même échelle que le monde).
        if self.editeur.active:
            self.editeur.draw_preview(self.screen, pygame.mouse.get_pos())

        # ── FIN DU ZOOM CAMÉRA (monde + lumières + aperçu) ────────────────
        # On scale maintenant le buffer vers l'écran réel. TOUT ce qui est
        # dessiné APRÈS (HUD, barre de vie, peur, éditeur HUD, inventaire,
        # dialogues, aide, fondus…) est dessiné à LA RÉSOLUTION NATIVE,
        # donc reste de taille "normale" quel que soit le zoom caméra.
        # C'était la demande utilisateur : zoomer le monde et le perso,
        # mais pas les éléments d'interface.
        if _real_screen is not self.screen:
            try:
                pygame.transform.scale(
                    self.screen, _real_screen.get_size(), _real_screen)
            except (ValueError, pygame.error):
                _real_screen.blit(
                    pygame.transform.scale(self.screen, _real_screen.get_size()),
                    (0, 0))
            self.screen = _real_screen

        # 13b. Outils éditeur en TAILLE NATIVE (texte, panneaux, coords souris).
        if self.editeur.active:
            draw_mouse_coords(self.screen, self.camera, y_start=110)
            self.editeur.draw_hud(self.screen, self._dt)
            # Éditeurs overlays (cine + pnj) par-dessus tout
            cine = getattr(self.editeur, "cine_editor", None)
            if cine is not None and cine.actif:
                cine.update(self._dt)
                cine.draw(self.screen)
            pnj_ed = getattr(self.editeur, "pnj_editor", None)
            if pnj_ed is not None and pnj_ed.actif:
                pnj_ed.update(self._dt)
                pnj_ed.draw(self.screen)

        # 14. FPS (coin bas-droite) et nom de la carte (coin bas-gauche).
        self._dessiner_fps_et_carte()

        # 15. Indicateur de mode (H ou E) en haut à droite.
        self._dessiner_indicateur_mode()

        # 16-17. Overlay PV + HUD (masqués en mode éditeur).
        if not self.editeur.active:
            self.hp_overlay.draw(self.screen, self.joueur)
            self.hud.draw(self.screen, self.joueur, self.peur)
            # Overlay "fear text" : dessiné par-dessus le HUD pour rester
            # lisible. Invisible si self.fear_overlay.actif est False.
            self.fear_overlay.draw(self.screen)

        # 18-21. Gestionnaire histoire, inventaire, dialogue, aide.
        self.gestionnaire_histoire.draw(self.screen)

        if self.inventory.cassette_a_jouer:
            visuel, sonore = self.inventory.cassette_a_jouer
            self.inventory.cassette_a_jouer = None
            play_cassette(visuel, sonore, self.screen)
            
        self.inventory.draw(self.screen, 6, 5)
        self.dialogue.draw(self.screen)
        self.boutique.draw(self.screen)
        self.aide.draw(self.screen)

        # 22. Hint "Echap pour passer" pendant une cinématique. Discret,
        # en bas à droite. Sert au testeur ET au joueur impatient.
        if self.cutscene is not None:
            self._dessiner_hint_skip_cinematique()

        # 23. Journal des dialogues (overlay par-dessus tout, mode histoire
        # ou test de l'éditeur).
        if self.journal_dialogues.actif:
            self.journal_dialogues.update(self._dt)
            self.journal_dialogues.draw(self.screen)

        # 22. Fondu enchaîné (par-dessus absolument tout).
        self._dessiner_fondu()

    def _dessiner_hint_skip_cinematique(self):
        """Petit hint discret 'Echap = passer' pendant une cinématique.

        Affiché en haut à droite, avec un fond semi-transparent. Le joueur
        peut toujours skipper depuis _gerer_touche."""
        txt = "[ Echap ] passer"
        rendu = self.fps_font.render(txt, True, (255, 220, 120))
        bg = pygame.Surface((rendu.get_width() + 16, rendu.get_height() + 8),
                            pygame.SRCALPHA)
        bg.fill((0, 0, 0, 180))
        sw = self.screen.get_width()
        self.screen.blit(bg, (sw - bg.get_width() - 12, 12))
        self.screen.blit(rendu, (sw - bg.get_width() - 12 + 8, 16))

    def _dessiner_fps_et_carte(self):
        """Affiche le compteur FPS et le nom de la carte courante."""
        # FPS en vert (coin bas-droite).
        fps_txt  = f"{self.clock.get_fps():.0f} FPS"   # f-string, voir [D32]
        fps_surf = self.fps_font.render(fps_txt, True, (0, 255, 0))
        self.screen.blit(fps_surf, (
            self.screen.get_width()  - fps_surf.get_width() - 10,
            self.screen.get_height() - 25,
        ))

        # Nom de la carte en gris (coin bas-gauche).
        if self.carte_actuelle:
            nom_surf = self.fps_font.render(self.carte_actuelle, True,
                                            (180, 180, 180))
            self.screen.blit(nom_surf, (10, self.screen.get_height() - 25))

    def _dessiner_indicateur_mode(self):
        """Grand H (histoire) ou E (éditeur) discret en haut à droite."""
        if self.mode == "histoire":
            lettre  = "H"
            couleur = (80, 180, 100, 180)        # vert clair
        else:
            lettre  = "E"
            couleur = (100, 140, 255, 180)       # bleu

        ind = self._font_indicateur.render(lettre, True, couleur[:3])
        ind.set_alpha(couleur[3])
        self.screen.blit(ind, (self.screen.get_width() - ind.get_width() - 10, 8))

    # ═════════════════════════════════════════════════════════════════════════
    # 11.  BOUCLE PRINCIPALE — run()
    # ═════════════════════════════════════════════════════════════════════════
    #
    # C'est la méthode appelée depuis main.py. Elle tourne indéfiniment
    # tant que self.running est True.
    #
    # Structure :
    #   Tant que le jeu tourne :
    #     1. Calculer dt
    #     2. Lire les events (et détecter pygame.QUIT)
    #     3. Gérer les cas particuliers (gestionnaire histoire, menu carte)
    #     4. Selon l'état → appeler la bonne routine
    #     5. Afficher l'écran

    def run(self):
        while self.running:
            # ── 1. Calcul de dt ──
            # clock.tick(FPS) attend ce qu'il faut pour viser FPS images/s.
            # Elle renvoie le nombre de MILLISECONDES depuis le dernier appel.
            # On divise par 1000 pour passer en secondes.
            #
            # CAP DU DT (critique sur Windows) : quand l'utilisateur déplace
            # la fenêtre, pygame gèle le main loop. Au moment du lâcher, dt
            # peut grimper à 1-5 secondes → la physique calcule
            # velocity × dt et le joueur se téléporte SOUS la plateforme
            # parce qu'il bouge plus que l'épaisseur de la plateforme en
            # 1 frame (= traverse les collisions). Idem au tout 1er frame
            # après chargement (init lent). On cape donc à 50 ms (= comme
            # si on tournait à 20 fps minimum), ce qui garantit que la
            # détection de collision fonctionne. Sur Mac le bug n'apparaît
            # pas car SDL2 gère le déplacement de fenêtre différemment.
            dt_brut  = self.clock.tick(FPS) / 1000
            self._dt = min(dt_brut, 0.05)

            # ── 2. Collecte des events ──
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:       # clic sur la croix de la fenêtre
                    self.running = False

            # ── 3a. Gestionnaire d'histoire (prioritaire) ──
            if self.gestionnaire_histoire.actif:
                for event in events:
                    self.gestionnaire_histoire.handle_event(event)
                self._dessiner_monde()
                pygame.display.flip()
                continue

            # ── 3b. Sélecteur de carte pour l'éditeur ──
            if self._menu_choix_carte is not None:
                if self._gerer_menu_choix_carte(events):
                    pygame.display.flip()
                continue

            # ── 4. Mise à jour des fondus musicaux ──
            music.update(self._dt)

            # ── 5. Dispatching selon l'état ──
            if self.etats.is_menu:
                self._frame_menu(events)
            elif self.etats.is_game:
                self._frame_jeu(events)
            elif self.etats.is_paused:
                self._frame_pause(events)
            elif self.etats.is_game_over:
                self._frame_game_over(events)

            # Effet de réveil (rayons de lumière synchro avec la musique).
            self.effet_reveil.update(self._dt)
            self.effet_reveil.draw(self.screen)

            # ── 6. Affichage final ──
            pygame.display.flip()

    # ─── Sous-routines de run() ──────────────────────────────────────────────

    def _gerer_menu_choix_carte(self, events):
        """Gère le sélecteur de carte (mode éditeur). Renvoie True si affiché."""
        self._menu_choix_carte.update(self._dt)

        for event in events:
            if event.type != pygame.KEYDOWN:
                continue

            if event.key == pygame.K_ESCAPE:
                # Retour au menu principal.
                self._menu_choix_carte  = None
                self._menu_fondu_etat   = "none"
                self._menu_fondu_alpha  = 0
                music.transition(self._musique_menu, volume=0.7,
                                 fadeout_ms=300, fadein_ms=1500)
                self.effet_reveil.reactiver()
                self.etats.switch(MENU)
                break

            choix = self._menu_choix_carte.handle_key(event.key)
            if choix == "Nouvelle carte":
                # Fondu vers le mode éditeur : on charge la carte + on
                # passe en GAME une fois l'écran noir. Ça arrête la musique
                # du menu en douceur et laisse l'effet_reveil s'estomper.
                def _action_nouvelle():
                    self.editeur._new_map()
                    self.carte_actuelle = ""
                    self._reconstruire_grille()
                    self._murs_modifies()
                    self._menu_choix_carte = None
                    self.etats.switch(GAME)
                self._lancer_fondu_menu(_action_nouvelle)
            elif choix is not None:
                # Idem : fondu doux puis chargement de la carte choisie.
                carte_choisie = choix
                def _action_charger():
                    if self.editeur.load_map_for_portal(carte_choisie):
                        self.carte_actuelle     = carte_choisie
                        self.editeur._nom_carte = carte_choisie
                        self._reconstruire_grille()
                        self._murs_modifies()
                        self._sync_triggers()
                    self._menu_choix_carte = None
                    self.etats.switch(GAME)
                self._lancer_fondu_menu(_action_charger)

        # On a changé d'état → on laisse la boucle principale reprendre.
        if self._menu_choix_carte is None:
            return True

        # Sinon, on dessine le menu de sélection.
        self.screen.fill((0, 0, 0))
        self._menu_choix_carte.draw(self.screen)

        # Pendant le fondu vers GAME : on fait progresser le voile noir
        # ICI aussi (sinon il resterait figé à 0 — _frame_menu n'est jamais
        # appelé tant qu'on est dans le sélecteur). Et on continue à
        # dessiner l'effet_reveil par-dessus → "lumières du titre qui
        # s'éteignent doucement" pendant la transition vers l'éditeur.
        self.effet_reveil.update(self._dt)
        self.effet_reveil.draw(self.screen)
        # update musique aussi (sinon le fadeout ne progresse pas).
        music.update(self._dt)
        self._avancer_fondu_menu()
        if self._menu_fondu_alpha > 0:
            self._dessiner_voile_noir(self._menu_fondu_alpha)
        return True

    # Vitesse du voile noir, en alpha/seconde. 100 → 2.55 s pour aller de
    # 0 à 255 (fade-out) ou inverse (fade-in). Plus lent que 170 → ressenti
    # plus contemplatif, et laisse à l'effet_reveil le temps de s'estomper.
    _MENU_FONDU_VITESSE = 100.0

    def _avancer_fondu_menu(self):
        """Fait progresser le fondu noir d'une frame.

        Centralisé pour que _frame_menu, _frame_jeu ET le sélecteur de
        carte (mode éditeur) partagent exactement la même logique."""
        if self._menu_fondu_etat == "out":
            self._menu_fondu_alpha += self._MENU_FONDU_VITESSE * self._dt
            if self._menu_fondu_alpha >= 255:
                self._menu_fondu_alpha = 255
                if self._menu_fondu_action:
                    self._menu_fondu_action()
                    self._menu_fondu_action = None
                # Passe au fondu entrant (le jeu va réapparaître).
                self._menu_fondu_etat = "in"
        elif self._menu_fondu_etat == "in" and self._menu_fondu_alpha > 0:
            self._menu_fondu_alpha -= self._MENU_FONDU_VITESSE * self._dt
            if self._menu_fondu_alpha <= 0:
                self._menu_fondu_alpha = 0
                self._menu_fondu_etat  = "none"

    def _frame_menu(self, events):
        """Un frame dans l'état MENU."""
        self.menu_titre.update(self._dt)
        self._gerer_menu(events)
        self.screen.fill((0, 0, 0))
        self.menu_titre.draw(self.screen)

        # Fondu menu → jeu (quand on a cliqué "Nouvelle partie" par ex.)
        self._avancer_fondu_menu()

        # Voile noir par-dessus le menu si alpha > 0.
        if self._menu_fondu_alpha > 0:
            self._dessiner_voile_noir(self._menu_fondu_alpha)

    def _frame_jeu(self, events):
        """Un frame dans l'état GAME."""
        self._update_jeu(events, self._dt)
        self._dessiner_monde()

        # Fondu entrant (après une transition depuis le menu).
        if self._menu_fondu_etat == "in" and self._menu_fondu_alpha > 0:
            self._avancer_fondu_menu()
            self._dessiner_voile_noir(self._menu_fondu_alpha)

    def _frame_pause(self, events):
        """Un frame dans l'état PAUSE : le jeu est figé, menu par-dessus."""
        # Indique au joueur de geler ses anims (sinon les loops continuent).
        self.joueur.paused = True
        try:
            self._gerer_pause(events)
            self._dessiner_monde()
        finally:
            self.joueur.paused = False
        self.menu_pause.draw(self.screen)
        # Écran Paramètres par-dessus la pause si ouvert.
        self.parametres.draw(self.screen)

    def _frame_game_over(self, events):
        """Un frame dans l'état GAME_OVER."""
        self._gerer_fin(events)
        self._dessiner_monde()
        self.menu_fin.draw(self.screen)

    def _dessiner_voile_noir(self, alpha):
        """Dessine un rectangle noir semi-transparent sur tout l'écran."""
        w, h = self.screen.get_size()
        voile = pygame.Surface((w, h), pygame.SRCALPHA)          # [D2]
        voile.fill((0, 0, 0, int(min(255, max(0, alpha)))))
        self.screen.blit(voile, (0, 0))
