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
from entities.player import Player
from entities.enemy import Enemy

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
from ui.gestionnaire_histoire import GestionnaireHistoire

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

        # Fenêtre redimensionnable (pygame.RESIZABLE) à la résolution choisie.
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
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

        # ── 1.14 Menus (titre, pause, fin) ──
        self._creer_menus()

        # ── 1.15 Musique du menu titre + effet de réveil ──
        self._init_audio_menu()

    # ─── Sous-routines de __init__ (pour aérer le constructeur) ──────────────

    def _charger_sons(self):
        """Charge les fichiers audio (sons du joueur, UI). Appelé 1 fois."""
        from audio import sound_manager
        sound_manager.charger("attaque", "ENTRE-DEUX/assets/sounds/attaque.mp3")
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
        self.inventory = Inventory()
        self.inventory.add_item("Pomme")                      # pomme offerte au départ
        self.inventory.add_item("Cassette")                    # cassette offerte au départ

        self.hud        = HUD()                          # cœurs + jauge de peur
        self.peur       = FearSystem(max_fear=100)       # 0 → 100
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
        self.vitesse_fondu       = 0.4                  # secondes pour 0 → 255
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
        music.jouer(self._musique_menu, volume=0.7, fadein_ms=2000)

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
        """Screen shake + particules quand un ennemi vient de mourir."""
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

        for portail in self.editeur.portals:
            if self.joueur.rect.colliderect(portail.rect):
                # On mémorise où on doit arriver, le chargement se fera
                # quand l'écran sera complètement noir.
                self._portail_en_attente = (
                    portail.target_map,
                    portail.target_x,
                    portail.target_y,
                )
                self._fondu_etat  = "out"
                self._fondu_alpha = 0
                return

    def _update_fondu(self, dt):
        """Fait avancer le fondu : alpha ± vitesse*dt chaque frame."""
        if self._fondu_etat == "none":
            return

        # Vitesse = 255 alpha en `vitesse_fondu` secondes.
        # max(0.05, ...) protège d'une division par zéro si on met 0.
        vitesse = 255 / max(0.05, self.vitesse_fondu)

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
        self.cinematiques_jouees = {}

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
        self.compagnons.respawn(self.joueur)
        self.etats.switch(GAME)

    def _sauvegarder(self):
        """Écrit la partie courante dans save.json."""
        sauvegarder({
            "mode":                 self.mode,
            "hp":                   self.joueur.hp,
            "map":                  self.carte_actuelle,
            "x":                    self.joueur.rect.x,
            "y":                    self.joueur.rect.y,
            "cinematiques_jouees":  self.cinematiques_jouees,
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
        # Si un éditeur overlay (cine ou pnj) est ouvert, il consomme TOUS
        # les events clavier (le jeu en arrière-plan reste figé).
        cine = getattr(self.editeur, "cine_editor", None)
        pnj_ed = getattr(self.editeur, "pnj_editor",  None)
        cine_open = cine is not None and cine.actif
        pnj_open  = pnj_ed is not None and pnj_ed.actif
        overlay   = cine if cine_open else (pnj_ed if pnj_open else None)

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

        # Si un dialogue est actif : Espace/Entrée avance le texte.
        if self.dialogue.actif and key in (pygame.K_SPACE, pygame.K_RETURN):
            self.dialogue.avancer()
            return

        # Échap : pause (sauf en mode saisie de texte éditeur).
        if key == pygame.K_ESCAPE:
            if self.editeur.active and self.editeur._text_mode:
                self.editeur.handle_key(key)
            elif not self.dialogue.actif:
                self.etats.switch(PAUSE)
                self.menu_pause.selection = 0
            return

        # TAB : ouvrir/fermer l'inventaire.
        if key == pygame.K_TAB:
            self.inventory.changer_etat_fenetre()
            return

        # C : compagnons → cape.
        if key == pygame.K_c and not self.editeur.active:
            self.compagnons.toggler_cape()
            return

        # E : interagir (mode histoire) ou toggler éditeur (mode éditeur).
        if key == pygame.K_e:
            self._gerer_touche_e()
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
        """Gère l'appui sur E selon le mode."""
        if self.mode == "editeur":
            # En mode éditeur, E bascule l'éditeur (sauf pendant une saisie de texte).
            if self.editeur.active and self.editeur._text_mode:
                return
            etait_actif = self.editeur.active
            self.editeur.toggle()
            # Quand on ferme l'éditeur, on recharge la hitbox du joueur
            # au cas où elle aurait été modifiée.
            if etait_actif and not self.editeur.active:
                self.joueur.reload_hitbox()

        elif self.mode == "histoire" and not self.dialogue.actif:
            # En mode histoire, E parle aux PNJ.
            self._tenter_interaction()

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

        # ── Mise à jour des ennemis ──
        for ennemi in self.ennemis:
            ennemi.update(phys_dt, self.platforms, murs, self.joueur.rect,
                          holes=trous)

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
            resoudre_contacts_ennemis(self.joueur, self.ennemis)

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
            self._pnj_actif.passer_a_suivante()
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

        # Compagnons : IA + influence sur la jauge de peur.
        self.compagnons.update(dt, self.joueur)
        self.compagnons.affecter_peur(self.peur, self.joueur, dt)

        self.hud.update(dt, self.joueur, self.peur)

        # Particules et shake (le shake continue pendant la hit-pause
        # pour qu'on sente bien l'impact).
        self.particles.update(dt)
        self.camera.shake_offset = self.shake.update(dt)
        self.hp_overlay.update(dt)

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
        # 1. Fond uni.
        couleur_fond = tuple(self.editeur.bg_color)
        self.screen.fill(couleur_fond)

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

        # 7a. Lucioles "derrière" (z < 0) : dessinées AVANT le joueur,
        #     donc le joueur les masque si elles passent pile derrière lui.
        #     Effet de profondeur 3D bon marché.
        self.compagnons.draw_derriere(self.screen, self.camera, self.joueur)

        # 7b. Joueur.
        self.joueur.draw(self.screen, self.camera, self.editeur.show_hitboxes)

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

        # 13. Outils éditeur (aperçu + HUD éditeur + coords souris).
        if self.editeur.active:
            draw_mouse_coords(self.screen, self.camera, y_start=110)
            self.editeur.draw_preview(self.screen, pygame.mouse.get_pos())
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

        # 18-21. Gestionnaire histoire, inventaire, dialogue, aide.
        self.gestionnaire_histoire.draw(self.screen)

        if self.inventory.cassette_a_jouer:
            visuel, sonore = self.inventory.cassette_a_jouer
            self.inventory.cassette_a_jouer = None
            play_cassette(visuel, sonore, self.screen)

        self.inventory.draw(self.screen, 6, 5)
        self.dialogue.draw(self.screen)
        self.aide.draw(self.screen)

        # 22. Fondu enchaîné (par-dessus absolument tout).
        self._dessiner_fondu()

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
            self._dt = self.clock.tick(FPS) / 1000

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
        self._gerer_pause(events)
        self._dessiner_monde()
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
