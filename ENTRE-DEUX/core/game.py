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
from ui.quick_use import QuickUseBar
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
from ui.save_menu       import SaveMenu
from ui.inventory import Inventory
from ui.fear_overlay import FearOverlay
from ui.gestionnaire_histoire import GestionnaireHistoire
from ui.boutique import Boutique

# ── Utilitaires et audio
from utils import draw_mouse_coords
from audio import music_manager as music
from audio import sound_manager as sfx

os.environ["SDL_AUDIODRIVER"] = "coreaudio"
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
        # Volumes + luminosité (réglés par les sliders dans les paramètres).
        settings.volume_musique = float(cfg.get("volume_musique", settings.volume_musique))
        settings.volume_sfx     = float(cfg.get("volume_sfx",     settings.volume_sfx))
        settings.luminosite     = float(cfg.get("luminosite",     settings.luminosite))
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
        # Barre quick-use (croix directionnelle bas-droite, touches 1/2/3/4).
        # Créée ICI parce qu'elle a besoin de self.joueur ET de
        # self.inventory (déjà créé plus haut dans _creer_systemes).
        # Cf. ui/quick_use.py pour configurer les slots et effets.
        self.quick_use = QuickUseBar(self.inventory, self.joueur, game=self)

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
        # [Ctrl+S] dans le cine_editor = re-scan des cinématiques avec condition
        # (au cas où on vient d'ajouter une condition à un fichier).
        self.editeur.cine_editor.on_save_callback = \
            self._charger_cine_flag_watchers

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

        # ── 1.15 Hot reload : on détecte un éventuel state file AVANT
        #         de lancer la musique du menu, pour ne pas l'entendre
        #         dans le jeu après un Ctrl+R.
        from core.hot_reload import HOT_STATE_PATH, consommer_state_si_present
        en_hot_reload = os.path.exists(HOT_STATE_PATH)

        # ── 1.16 Musique du menu titre + effet de réveil ──
        # Skip TOTAL si on est en hot reload : le joueur était en jeu, il
        # ne doit ni entendre la musique du menu, ni voir l'effet_reveil.
        # On instancie quand même un EffetReveil VIDE (intensite=0) pour
        # ne pas casser les références plus tard dans le code.
        if en_hot_reload:
            from systems.effet_reveil import EffetReveil
            self._musique_menu = ""               # pas de musique de menu
            self.effet_reveil  = EffetReveil(debut_s=99999, duree_cycle_s=1)
            self.effet_reveil.intensite = 0.0     # extinction totale immédiate
            self.effet_reveil.forcer_extinction()
        else:
            self._init_audio_menu()

        # ── 1.17 Application de l'état hot reload ──
        if en_hot_reload:
            try:
                # Lance directement une partie (charge la carte de départ),
                # puis _consommer_state remplacera la map et la position
                # par celles sauvées avant le reload.
                self.mode = "histoire"
                self._nouvelle_partie()
                consommer_state_si_present(self)
                # Sécurité : on coupe net tout ce qui aurait pu se relancer
                # pendant _nouvelle_partie (musique titre, etc.).
                try:
                    pygame.mixer.music.stop()
                except Exception:
                    pass
            except Exception as e:
                print(f"[HotReload] Restauration auto échouée : {e}")

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
        # Note : aucune pomme au départ. Elles sont données par la
        # cinématique de Nymbus (action unlock_quickuse) qui débloque
        # aussi la croix directionnelle de consommables rapides.
        self.inventory.add_item("Cassette")                    # cassette offerte au départ
        # Note : la barre quick-use est créée plus tard dans __init__,
        # une fois que self.joueur existe (cf. après Player((100, 400))).

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
        self._menu_fondu_etat   = "none"        # none / out / loading / in
        self._menu_fondu_action = None          # callback quand alpha = 255
        self._chargement_timer  = 0.0           # décompte phase "loading"

        # Overlay de sélection de carte (menu éditeur)
        self._menu_choix_carte = None

    def _init_caches(self):
        """Caches pour éviter de recalculer certaines choses chaque frame."""
        # Cache des murs (on ne recalcule que quand l'éditeur les modifie).
        self._murs_cache        = None
        self._murs_cache_perime = True                  # True = à recalculer

    def _options_menu_titre(self):
        """Retourne la liste des options du menu titre (recalculée à chaque fois).

        L'option "Continuer" n'apparaît que si AU MOINS un slot de
        sauvegarde manuel existe (pas seulement slot 1 — n'importe lequel
        des 3). On la recalcule dynamiquement pour qu'après avoir sauvé
        en jeu et être revenu au menu, le bouton apparaisse.
        """
        from systems.save_system import au_moins_une_save
        options = []
        if au_moins_une_save():
            options.append("Continuer")
        options += ["Nouvelle partie", "Mode éditeur", "Quitter"]
        return options

    def _rafraichir_menu_titre(self):
        """Reconstruit le menu titre avec ses options à jour.

        À appeler quand on revient au menu (ex : "Menu principal" depuis
        la pause). Sans ça, "Continuer" reste invisible jusqu'au prochain
        lancement complet du jeu.
        """
        self.menu_titre = Menu(self._options_menu_titre(), title=TITLE,
                                style="titre")

    def _creer_menus(self):
        """Crée les 3 menus : titre, pause, fin."""
        # style="titre"   → fond sombre + particules
        # style="panneau" → cadre sur le jeu en arrière-plan
        self.menu_titre = Menu(self._options_menu_titre(), title=TITLE,
                                style="titre")
        # Plus de bouton "Sauvegarder" : le jeu sauvegarde uniquement via
        # des objets/PNJ interactifs dans le monde (style Hollow Knight).
        self.menu_pause = Menu(
            ["Reprendre", "Paramètres",
             "Charger",
             "Menu principal", "Quitter"],
            title="PAUSE",
            style="panneau",
        )
        # Overlay multi-slots ouvert par "Sauvegarder" / "Charger"
        self.save_menu = SaveMenu()
        # (carte, x, y) du dernier save manuel — utilisé par Recommencer
        # après mort pour respawn au banc plutôt qu'au spawn de map.
        self._dernier_save_pos = None
        # Story flags : dict {key: {"current": N, "required": M}}.
        # (Anciens flags booléens automatiquement normalisés à la lecture.)
        # Posé par cutscene set_flag/flag_increment ou PNJ events. Lu pour
        # conditionner dialogues (PNJ.dialogue_conditions) et cinématiques
        # (cinématique JSON enrichi avec "condition"). Sauvegardé.
        self.story_flags = {}
        # ── Cinématiques conditionnelles ─────────────────────────────────
        # Liste des cinematiques avec une condition de déclenchement (scan
        # de cinematiques/*.json au démarrage). Vérifiée après chaque flag
        # event avec un délai (1s par défaut) pour laisser le dialogue se
        # fermer proprement avant d'enchaîner sur la cinématique.
        self._cine_flag_watchers = []
        self._cine_verif_pending = False
        self._cine_verif_delay   = 0.0
        # File de notifications éphémères (haut-centre). Une notif =
        # (texte, timer_restant). Posée via self.notifier(text).
        # Affichée au-dessus du HUD pendant ~3 secondes.
        self._notifs = []
        # Toast "Sauvegardé ✓" en bas-droite (timer + spinner).
        # Activé pour SAVE_TOAST_DUREE secondes après chaque save réussie.
        self._save_toast_timer = 0.0
        self._save_toast_duree = 2.0
        self.menu_fin = Menu(
            ["Recommencer", "Menu principal"],
            title="FIN",
            style="panneau",
        )
        # Scan initial des cinématiques conditionnelles (cf. systems/story_flags).
        self._charger_cine_flag_watchers()

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

            if getattr(portail, "need_key", False):
                key_type = getattr(portail, "key_type", "Keys")
                if not self.inventory.utiliser(key_type):

                    # afficher "Il te faut une clé"

                    now = pygame.time.get_ticks()

                    if not hasattr(self, "_last_key_msg"):
                        self._last_key_msg = 0

                    if now - self._last_key_msg > 3000:
                        self.notifier(f"Il te faut une {key_type}")
                        self._last_key_msg = now

                    continue

            # On mémorise où on doit arriver, le chargement se fera
            # quand l'écran sera complètement noir.
            self._portail_en_attente = (
                portail.target_map,
                portail.target_x,
                portail.target_y,
            )
            # Pour les portails AUTO (pas require_up), on mémorise la
            # vélocité courante du joueur → la transition est plus fluide
            # (le joueur "continue son saut/sa chute" à l'arrivée au lieu
            # de s'arrêter pile dans le vide).
            if not getattr(portail, "require_up", False):
                self._portail_keep_vy = self.joueur.vy
                self._portail_keep_vx = self.joueur.vx
                # Type "auto" : on laisse la physique tourner pendant le
                # fondu out (le joueur continue sa chute / son saut), c'est
                # plus réaliste qu'un freeze net.
                self._portail_freeze_pendant_fondu = False
            else:
                self._portail_keep_vy = 0
                self._portail_keep_vx = 0
                # Type "porte" : on fige (animation rituelle, le joueur
                # entre dans une porte → pas de chute parasite).
                self._portail_freeze_pendant_fondu = True
            # Durée du fondu pour CETTE transition. Les PORTES ont un
            # fondu plus long (plus rituel) que les portails classiques.
            if getattr(portail, "require_up", False):
                self._fondu_duree_courante = self.vitesse_fondu_porte
            else:
                self._fondu_duree_courante = self.vitesse_fondu
            self._fondu_etat  = "out"
            self._fondu_alpha = 0
            # Pour les PORTES (require_up = entrée volontaire), on stoppe
            # la course/marche → l'anim de retour s'arrête net (pas de
            # glisse résiduelle). Pour les portails AUTO (sauter dedans),
            # on laisse la vélocité telle quelle (le joueur tombait dans
            # le portail, sa chute reprend de l'autre côté avec vy=0).
            if getattr(portail, "require_up", False):
                try:
                    self.joueur.forcer_idle()
                except Exception:
                    pass
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
        """Charge la carte cible, place le joueur, reset les caches.

        Le champ `target_map` du portail peut prendre 2 formes :
            "village"            → carte village, spawn par défaut
            "village porte_haut" → carte village, spawn nommé "porte_haut"

        Le 2e format permet d'avoir plusieurs points d'arrivée par carte
        (ex: en sortant d'une maison, on apparaît devant la porte de la
        maison, pas au spawn principal). Les spawns nommés sont stockés
        dans le JSON de chaque map (champ "named_spawns").
        """
        if not self._portail_en_attente:
            return

        carte, tx, ty = self._portail_en_attente

        # On parse "mapname spawnname" : 1er mot = vraie carte, reste = spawn.
        nom_spawn = None
        if isinstance(carte, str) and " " in carte:
            morceaux = carte.split(" ", 1)
            carte    = morceaux[0]
            nom_spawn = morceaux[1].strip() or None

        if self.editeur.load_map_for_portal(carte):
            self.carte_actuelle = carte
            self._reconstruire_grille()
            self._murs_modifies()

            # Priorité de placement (du plus précis au plus général) :
            #   1. Spawn nommé (si défini dans le portail ET dans la map)
            #   2. Coords explicites (tx, ty) du portail si > 0
            #   3. Spawn par défaut de la map
            named = getattr(self.editeur, "named_spawns", {}) or {}
            if nom_spawn and nom_spawn in named:
                pos = named[nom_spawn]
                self.joueur.rect.x = int(pos[0])
                self.joueur.rect.y = int(pos[1])
            elif tx >= 0 and ty >= 0:
                self.joueur.rect.x = tx
                self.joueur.rect.y = ty
            else:
                self.joueur.respawn()

            # Vélocité à l'arrivée :
            #   - portail AUTO : on REPREND la vélocité capturée à l'entrée
            #     (le joueur continue son saut/chute → effet fluide)
            #   - PORTE : tout à 0 (l'entrée est volontaire et statique)
            self.joueur.knockback_vx = 0
            # On RESET la vélocité à 0 à l'arrivée d'un téléport. Avant on
            # gardait celle d'entrée → si le joueur tombait à 1000 px/s
            # dans un portail, il arrivait dans la nouvelle map à 1000 px/s
            # et accélérait encore (gravité), invisible sous la caméra.
            # Maintenant : départ doux, la gravité reprend depuis 0 → la
            # chute est lisible même quand on apparaît en hauteur.
            self.joueur.vy = 0
            self.joueur.vx = 0
            self._portail_keep_vy = 0
            self._portail_keep_vx = 0

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
        conv = pnj.conversation_actuelle(getattr(self, "story_flags", {}))
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

    # ── Panneau debug des story flags (éditeur, F5) ──────────────────────

    def _story_flags_panel_handle_key(self, key):
        """Gère les touches quand le panneau debug flags est ouvert.

        Touches :
          ↑↓     naviguer dans la liste
          T      basculer le flag sélectionné (True ↔ False)
          D      supprimer le flag sélectionné
          A      ajouter un nouveau flag (saisie texte interne)
          Esc/F5 fermer

        Renvoie True si la touche est consommée."""
        import pygame as _pg
        if not hasattr(self, "_story_flags_panel_sel"):
            self._story_flags_panel_sel = 0
        if not hasattr(self, "_story_flags_input_actif"):
            self._story_flags_input_actif = False
            self._story_flags_input_buf   = ""

        # Mode saisie : RETURN valide, ESC annule, BACKSPACE efface.
        if self._story_flags_input_actif:
            if key == _pg.K_RETURN:
                k = self._story_flags_input_buf.strip()
                if k:
                    self.story_flags[k] = True
                self._story_flags_input_actif = False
                self._story_flags_input_buf   = ""
                return True
            if key == _pg.K_ESCAPE:
                self._story_flags_input_actif = False
                self._story_flags_input_buf   = ""
                return True
            if key == _pg.K_BACKSPACE:
                self._story_flags_input_buf = self._story_flags_input_buf[:-1]
                return True
            if key == _pg.K_v and (_pg.key.get_mods() & _pg.KMOD_CTRL):
                # Ctrl+V : colle depuis le presse-papiers
                try:
                    from world.cinematique_editor import _clipboard_get
                    self._story_flags_input_buf += _clipboard_get().strip().replace("\n", "").replace("\r", "")
                except Exception:
                    pass
                return True
            return True

        flags = list(self.story_flags.keys())
        n = len(flags)
        if key == _pg.K_ESCAPE:
            self._story_flags_panel_open = False
            return True
        if key == _pg.K_UP and n:
            self._story_flags_panel_sel = (self._story_flags_panel_sel - 1) % n
            return True
        if key == _pg.K_DOWN and n:
            self._story_flags_panel_sel = (self._story_flags_panel_sel + 1) % n
            return True
        if key == _pg.K_t and n:
            k = flags[self._story_flags_panel_sel]
            self.story_flags[k] = not bool(self.story_flags.get(k, False))
            return True
        if key == _pg.K_d and n:
            k = flags[self._story_flags_panel_sel]
            self.story_flags.pop(k, None)
            self._story_flags_panel_sel = max(
                0, min(self._story_flags_panel_sel, len(self.story_flags) - 1))
            return True
        if key == _pg.K_a:
            self._story_flags_input_actif = True
            self._story_flags_input_buf   = ""
            return True
        return False

    def _story_flags_panel_handle_textinput(self, text):
        """Hook TEXTINPUT pour la saisie d'un nom de flag."""
        if getattr(self, "_story_flags_input_actif", False):
            self._story_flags_input_buf += text
            return True
        return False

    def _dessiner_story_flags_panel(self):
        """Affiche l'overlay debug des story flags si _story_flags_panel_open."""
        if not getattr(self, "_story_flags_panel_open", False):
            return
        w, h = self.screen.get_size()
        pw, ph = 380, 320
        px = w - pw - 16
        py = 80
        bg = pygame.Surface((pw, ph), pygame.SRCALPHA)
        bg.fill((16, 10, 30, 235))
        pygame.draw.rect(bg, (180, 150, 220),
                         pygame.Rect(0, 0, pw, ph), 2)
        pygame.draw.rect(bg, (255, 215, 70),
                         pygame.Rect(3, 3, pw - 6, ph - 6), 1)
        self.screen.blit(bg, (px, py))

        font_t = pygame.font.SysFont("Consolas", 14, bold=True)
        font   = pygame.font.SysFont("Consolas", 13)
        font_s = pygame.font.SysFont("Consolas", 11)

        self.screen.blit(font_t.render("STORY FLAGS  (F5 ferme)",
                                        True, (255, 215, 70)),
                         (px + 14, py + 10))
        self.screen.blit(font_s.render(
            "[↑↓] naviguer  [T] toggle  [D] supprimer  [A] ajouter",
            True, (170, 170, 200)),
                         (px + 14, py + 32))

        flags = list(self.story_flags.items())
        if not flags:
            self.screen.blit(font.render("(aucun flag posé)",
                                          True, (140, 140, 160)),
                             (px + 14, py + 70))
        else:
            sel = getattr(self, "_story_flags_panel_sel", 0)
            ly = py + 60
            for i, (k, v) in enumerate(flags):
                if i == sel:
                    pygame.draw.rect(self.screen, (50, 35, 80),
                                     pygame.Rect(px + 8, ly - 2, pw - 16, 18))
                col_v = (140, 220, 140) if v else (180, 90, 100)
                txt = font.render(f"{k}", True, (240, 230, 255))
                self.screen.blit(txt, (px + 14, ly))
                etat = font.render("TRUE" if v else "FALSE", True, col_v)
                self.screen.blit(etat, (px + pw - etat.get_width() - 16, ly))
                ly += 18
                if ly > py + ph - 30:
                    break

        # Saisie active ?
        if getattr(self, "_story_flags_input_actif", False):
            box_h = 30
            sx = px + 8
            sy = py + ph - box_h - 8
            pygame.draw.rect(self.screen, (40, 30, 70),
                             pygame.Rect(sx, sy, pw - 16, box_h))
            pygame.draw.rect(self.screen, (255, 215, 70),
                             pygame.Rect(sx, sy, pw - 16, box_h), 1)
            txt = self._story_flags_input_buf + "_"
            self.screen.blit(font.render("Nouveau flag : " + txt, True,
                                          (255, 255, 255)),
                             (sx + 6, sy + 6))

    def _declencher_cinematique_mort(self):
        """Cherche une CutsceneTrigger en mode "on_death" qui couvre la
        position du joueur. Si trouvée et déclenchée, renvoie True. Sinon
        renvoie False → game.py basculera en GAME_OVER normal.

        Permet de scripter une "mort narrative" (PNJ qui parle pendant
        l'écran noir, téléport vers un lieu safe, etc.) au lieu du Game
        Over basique. Voir CutsceneTrigger(mode="on_death").

        Si plusieurs zones on_death se chevauchent (cas typique : une cine
        de secours sans condition + une cine alternative conditionnée par
        un flag), on essaie toutes les zones tant qu'aucune ne démarre.
        Permet à la cine alternative de se lancer une fois que la cine de
        secours est consommée (max_plays=1)."""
        from world.triggers import CutsceneTrigger
        for zone in (self.editeur.trigger_zones or []):
            if not isinstance(zone, CutsceneTrigger):
                continue
            if getattr(zone, "mode", "enter") != "on_death":
                continue
            if not zone.rect.colliderect(self.joueur.rect):
                continue
            # On capture l'état avant fire() pour détecter si la cine a
            # vraiment démarré (fire peut être no-op si max_plays atteint
            # ou si la condition d'activation n'est pas remplie).
            cutscene_avant = self.cutscene
            try:
                zone.fire({"game": self})
            except Exception as e:
                print(f"[Mort scriptée] fire échoué : {e}")
                continue
            if self.cutscene is not cutscene_avant and self.cutscene is not None:
                # Une cinématique a bien démarré. On garde joueur.dead = True
                # jusqu'à ce qu'elle appelle revive_player → la physique
                # reste figée pendant les dialogues d'agonie.
                return True
            # Sinon, la zone n'a rien lancé (consommée, condition non remplie) ;
            # on passe à la suivante.
        return False

    def notifier(self, texte, duree=3.0):
        """Affiche une notification éphémère en haut-centre de l'écran.

        Utilisé par les events PNJ et les actions de cinématique pour
        signaler au joueur un changement (compétence débloquée, item
        reçu, flag posé, etc.). Plusieurs notifs s'empilent verticalement.
        """
        if texte:
            self._notifs.append([str(texte), float(duree), float(duree)])

    def _dessiner_notifications(self):
        """Affiche / met à jour les notifications éphémères."""
        if not self._notifs:
            return
        dt = self._dt
        # Décrémente les timers, retire celles qui ont fini.
        nouvelles = []
        for n in self._notifs:
            n[1] -= dt
            if n[1] > 0:
                nouvelles.append(n)
        self._notifs = nouvelles
        if not self._notifs:
            return

        w, h = self.screen.get_size()
        font = pygame.font.SysFont("Consolas", 16, bold=True)
        y = 60
        for texte, restant, total in self._notifs:
            # Alpha : fade-in 0.2s + fade-out 0.5s
            ratio_in  = min(1.0, (total - restant) / 0.2) if total > 0.2 else 1.0
            ratio_out = min(1.0, restant / 0.5)
            alpha = int(255 * min(ratio_in, ratio_out))
            txt_surf = font.render(texte, True, (255, 215, 70))
            bw = txt_surf.get_width() + 32
            bh = txt_surf.get_height() + 12
            bx = (w - bw) // 2
            bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
            bg.fill((20, 14, 38, int(220 * alpha / 255)))
            pygame.draw.rect(bg, (180, 150, 220, alpha),
                             pygame.Rect(0, 0, bw, bh), 1)
            pygame.draw.rect(bg, (255, 215, 70, int(150 * alpha / 255)),
                             pygame.Rect(2, 2, bw - 4, bh - 4), 1)
            txt_surf.set_alpha(alpha)
            bg.blit(txt_surf, (16, 6))
            self.screen.blit(bg, (bx, y))
            y += bh + 6

    def _appliquer_event_pnj(self, event):
        """Applique un événement déclenché en fin de conversation PNJ.

        Format attendu : dict { "type": str, ...params }.
        Types supportés (extensibles — ajouter une branche ici) :

          {"type": "skill",   "value": "double_jump"}
              → settings.skill_<value> = True
              valeurs : double_jump, dash, back_dodge, wall_jump,
                        attack, pogo

          {"type": "luciole", "source": "anna"}
              → self.compagnons.gagner_luciole(joueur, source=...)
                "source" doit être un identifiant unique pour éviter
                qu'on regagne la même luciole à chaque relecture.

          {"type": "coins",   "value": 50}    → joueur.coins += value
          {"type": "hp",      "value": 2}     → soigne (cap = max_hp)
          {"type": "max_hp",  "value": 1}     → +max_hp ET soigne plein
          {"type": "item",    "value": "potion"}
              → joueur.inventaire.append(value) (si attribut existe)

        Tout type inconnu logue un avertissement et est ignoré.
        Cf. entities/npc.py PNJ.events pour la pose côté éditeur/JSON.
        """
        if not isinstance(event, dict):
            return
        etype = event.get("type")

        if etype == "skill":
            val = event.get("value", "")
            attr = f"skill_{val}"
            if hasattr(settings, attr):
                setattr(settings, attr, True)
                self.notifier(f"Compétence débloquée : {val}")
            else:
                print(f"[event PNJ] skill inconnu : {val!r}")

        elif etype == "luciole":
            src = event.get("source") or f"pnj_{getattr(self._pnj_actif, 'nom', 'x')}"
            try:
                self.compagnons.gagner_luciole(joueur=self.joueur, source=src)
                self.notifier("+ 1 luciole")
            except Exception as exc:
                print(f"[event PNJ] luciole : {exc}")

        elif etype == "coins":
            v = int(event.get("value", 0))
            self.joueur.coins = getattr(self.joueur, "coins", 0) + v
            if v != 0:
                self.notifier(f"+ {v} pièces" if v > 0 else f"{v} pièces")

        elif etype == "hp":
            v = int(event.get("value", 0))
            self.joueur.hp = min(self.joueur.max_hp, self.joueur.hp + v)
            if v > 0:
                self.notifier(f"+ {v} PV")

        elif etype == "max_hp":
            v = int(event.get("value", 0))
            self.joueur.max_hp += v
            self.joueur.hp = self.joueur.max_hp
            if v > 0:
                self.notifier(f"+ {v} PV max")

        elif etype == "item":
            val = event.get("value", "")
            if hasattr(self, "inventory") and val:
                # Préfère l'inventaire UI (stackable) plutôt qu'une liste
                # custom sur le joueur — comportement uniforme.
                try:
                    n = int(event.get("count", 1))
                    self.inventory.add_item(val, count=n)
                    self.notifier(f"+ {n} {val}" if n > 1 else f"+ {val}")
                except Exception:
                    pass

        elif etype == "flag":
            # Pose un story flag (booléen). Utilise le système avec compteurs
            # (flag_poser normalise vers {current, required}).
            key = event.get("key", "")
            val = bool(event.get("value", True))
            if key:
                if not hasattr(self, "story_flags"):
                    self.story_flags = {}
                from systems.story_flags import flag_poser
                flag_poser(self.story_flags, key, val)
                # Si la condition d'une cinématique est désormais remplie,
                # elle se déclenchera après un court délai.
                self._programmer_verif_cine()

        elif etype == "flag_increment":
            # Incrémente un flag avec compteur. Crée le flag si absent (avec
            # le required donné en argument, sinon depuis le registre).
            key      = event.get("key", "")
            delta    = int(event.get("delta", 1))
            required = event.get("required", None)
            if not key:
                return
            if not hasattr(self, "story_flags"):
                self.story_flags = {}
            from systems.story_flags import flag_incrementer, flag_valeur
            vient_de_finir = flag_incrementer(
                self.story_flags, key, delta=delta, required=required)
            cur, req = flag_valeur(self.story_flags, key)
            self.notifier(f"{key} : {cur}/{req}")
            # On vérifie TOUJOURS (pas seulement à la complétion) — certaines
            # conditions utilisent un seuil (flag:k=N avec N < required).
            self._programmer_verif_cine()

        else:
            print(f"[event PNJ] type inconnu : {etype!r}")

    # ─────────────────────────────────────────────────────────────────────
    #  CINÉMATIQUES CONDITIONNELLES (déclenchées par flags)
    # ─────────────────────────────────────────────────────────────────────

    def _charger_cine_flag_watchers(self):
        """Scanne cinematiques/ et met à jour la liste des cinématiques avec
        condition. Appelé au démarrage et à chaque chargement de map.

        On scanne ÉGALEMENT toutes les maps pour construire la liste des
        cinématiques référencées par un trigger zone N'IMPORTE OÙ dans le
        jeu — sinon une cine on_death sur la map B serait auto-déclenchée
        depuis la map A (le trigger n'étant pas encore chargé)."""
        try:
            from systems.story_flags import charger_cinematiques_conditionnelles
            self._cine_flag_watchers = charger_cinematiques_conditionnelles()
        except Exception as e:
            print(f"[Cine watchers] échec scan : {e}")
            self._cine_flag_watchers = []
        # Scan de TOUTES les maps pour collecter les cinématiques liées à
        # un trigger zone (même si le trigger n'est pas chargé maintenant).
        self._cines_avec_trigger_global = self._scanner_cines_avec_trigger()

    def _scanner_cines_avec_trigger(self):
        """Renvoie le set des cutscene_nom référencés par un trigger zone
        dans n'importe quelle map de maps/. Très léger (lecture JSON)."""
        import json, os
        cines = set()
        maps_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "maps")
        if not os.path.isdir(maps_dir):
            return cines
        for nom_fichier in os.listdir(maps_dir):
            if not nom_fichier.endswith(".json"):
                continue
            try:
                with open(os.path.join(maps_dir, nom_fichier),
                          encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            for z in data.get("trigger_zones", []) or []:
                nom_cine = z.get("cutscene_nom", "")
                if nom_cine:
                    cines.add(nom_cine)
        return cines

    def _programmer_verif_cine(self, delai=None):
        """Programme une vérification des cinématiques conditionnelles.

        Le délai par défaut est lu sur chaque watcher individuellement
        (à la vérification). Ici on stocke juste l'attente max parmi
        tous les watchers définis (ou 1.0s si aucun)."""
        if not self._cine_flag_watchers:
            return
        # Délai = max des délais des watchers (laisse à TOUS le temps de jouer)
        if delai is None:
            delai = max((w.get("delay", 1.0)
                         for w in self._cine_flag_watchers), default=1.0)
        self._cine_verif_pending = True
        # Si une vérification est déjà en attente, on prend le délai le plus long
        # pour qu'aucune ne soit oubliée.
        self._cine_verif_delay = max(self._cine_verif_delay, float(delai))

    def _avancer_verif_cine(self, dt):
        """Décompte du timer + déclenchement quand il atteint 0. Appelé
        depuis _update_jeu chaque frame."""
        if not self._cine_verif_pending:
            return
        self._cine_verif_delay -= dt
        if self._cine_verif_delay > 0:
            return
        # Timer expiré : on vérifie maintenant.
        self._cine_verif_pending = False
        self._cine_verif_delay   = 0.0
        # Ne déclenche pas une cinématique pendant un dialogue, une cinématique
        # en cours ou un overlay éditeur — sinon on perturbe l'écran courant.
        if self.dialogue.actif or self.cutscene is not None:
            # On reprogramme pour plus tard
            self._cine_verif_pending = True
            self._cine_verif_delay   = 0.5
            return
        if self.editeur.active:
            return
        self._verifier_cinematiques_conditionnelles()

    def _verifier_cinematiques_conditionnelles(self):
        """Vérifie chaque watcher : si sa condition est vraie ET qu'il n'a pas
        déjà été déclenché (one_shot), on lance la cinématique.

        Comportement par défaut : toute cine avec une condition s'auto-
        déclenche dès que la condition devient vraie. Les éventuels triggers
        zone offrent une autre voie (enter, on_death) ; le compteur
        max_plays empêche le double-fire.

        Pour les cines qui doivent fire UNIQUEMENT via leur trigger zone
        (cas d'une on_death où la condition n'est qu'un filtre), l'utilisateur
        désactive explicitement l'auto-fire via [F] dans l'éditeur de
        cinématique → le JSON gagne "auto_fire": false."""
        from systems.story_flags import tester_condition

        for watcher in self._cine_flag_watchers:
            nom       = watcher.get("nom", "")
            condition = watcher.get("condition")
            one_shot  = watcher.get("one_shot", True)
            auto_fire = watcher.get("auto_fire", None)  # None=auto-fire, True=auto-fire, False=jamais
            if not nom or not condition:
                continue
            # Auto-fire par défaut. L'utilisateur désactive explicitement
            # via [F] dans l'éditeur (auto_fire=False) pour les rares cines
            # qui ne doivent fire QUE via leur trigger zone — typiquement
            # une cine on_death où la condition n'est qu'un filtre. Le
            # compteur max_plays empêche le double-fire si une trigger
            # zone existe par ailleurs.
            if auto_fire is False:
                continue
            # Compteur de déclenchement (one_shot = max 1)
            joues = self.cinematiques_jouees.get(nom, 0)
            if one_shot and joues >= 1:
                continue
            if not tester_condition(self.story_flags, condition):
                continue
            # Tout est OK → on lance la cinématique
            self._lancer_cinematique_par_nom(nom)
            self.cinematiques_jouees[nom] = joues + 1
            # Une seule cinématique à la fois (on n'enchaîne pas).
            return

    def _lancer_cinematique_par_nom(self, nom):
        """Charge cinematiques/<nom>.json et lance la cinématique."""
        try:
            from world.triggers import _charger_cutscene_fichier
            ctx = {"game": self}
            scene = _charger_cutscene_fichier(nom, ctx)
            if scene is None:
                print(f"[Cine watcher] introuvable : {nom}")
                return
            self.cutscene = scene
            self.state    = "cinematic"
            # Stoppe net la marche du joueur. SAUF si la cinématique est
            # "joueur libre" — auquel cas on ne touche à rien (chute en
            # cours, course, etc.).
            if (hasattr(self.joueur, "forcer_idle")
                    and not getattr(scene, "player_libre", False)):
                try:
                    self.joueur.forcer_idle()
                except Exception:
                    pass
        except Exception as e:
            print(f"[Cine watcher] échec lancement '{nom}' : {e}")

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

    def _tester_cinematique(self, steps_data, player_libre=False):
        """Lance une cinématique depuis les données JSON brutes (touche [T]
        de l'éditeur de cinématiques). Permet de prévisualiser sans avoir
        à sauvegarder + recharger la carte + entrer dans la zone trigger.

        player_libre : reflète l'option de l'éditeur — si True le joueur
        garde le contrôle pendant la cinématique (test fidèle au comportement
        en jeu)."""
        from systems.cutscene import Cutscene
        from world.triggers   import _steps_depuis_data
        try:
            scene = Cutscene(_steps_depuis_data(steps_data),
                             player_libre=player_libre)
        except Exception as e:
            print(f"[Cutscene] Erreur construction : {e}")
            return
        self.cutscene = scene
        self.state    = "cinematic"
        # Si le joueur est libre, on ne le force PAS en idle (sinon on
        # casse l'animation de chute / course en cours).
        if not player_libre:
            try:
                self.joueur.forcer_idle()
            except Exception:
                pass

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
        # Reset des story flags : page blanche pour toutes les conditions
        # de dialogue PNJ et tous les déblocages (quickuse_unlocked, etc.).
        self.story_flags = {}
        # Reset des sources de lucioles déjà obtenues : sinon les PNJ qui
        # avaient déjà donné leur luciole refuseraient de la redonner.
        self.lucioles_sources_obtenues = set()
        # Reset des ennemis tués mémorisés par carte.
        self._ennemis_morts_par_map = {}
        # Reset du dernier point de save mémorisé.
        self._dernier_save_pos = None

        # Reset des compétences en mode histoire : le joueur démarre avec
        # SEULEMENT le saut. Les autres compétences (double saut, dash,
        # esquive, wall jump, attaque, pogo) se débloqueront via quêtes /
        # dialogues / objets en cours d'aventure.
        # En mode éditeur, on garde tout débloqué (les flags ne sont pas
        # consultés grâce à _in_editor_mode dans Player._skill_unlocked).
        if self.mode == "histoire":
            for nom in ("double_jump", "dash", "back_dodge",
                        "wall_jump", "attack", "pogo"):
                setattr(settings, f"skill_{nom}", False)

        # Reset inventaire : seule la cassette de départ. Pas de pommes
        # (elles sont données par la cinématique de Nymbus).
        if self.mode == "histoire":
            try:
                self.inventory.slots = [None] * len(self.inventory.slots)
                self.inventory.add_item("Cassette")
            except Exception as e:
                print(f"[Nouvelle partie] reset inventaire : {e}")

        # Reset des compagnons : retour au nombre initial du game_config.
        # Sinon ceux acquis dans la partie précédente persistent.
        try:
            nb_init = int(lire_config().get("nb_compagnons", 2))
            from systems.compagnons import CompagnonGroup
            self.compagnons = CompagnonGroup(nb=nb_init)
            # Re-bind paramètres
            self.parametres.bind_compagnons(self.compagnons, self.joueur)
        except Exception as e:
            print(f"[Nouvelle partie] reset compagnons : {e}")

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

        # SNAP la caméra sur le joueur AVANT le 1er rendu : sinon la caméra
        # part de sa position antérieure (souvent (0,0)) et fait un défilé
        # visible vers le joueur pendant le fade-in.
        self.camera.snap_to(self.joueur.rect)

        # Passer à l'état GAME.
        self.etats.switch(GAME)

    # ═════════════════════════════════════════════════════════════════════════
    # 6.  SAUVEGARDE / CHARGEMENT (multi-slots, état complet)
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Le dict produit par _construire_save_data() / consommé par
    #  _appliquer_save_data() contient TOUT ce que le joueur a fait :
    #       - position / hp / direction
    #       - inventaire (items + slots)
    #       - peur courante
    #       - lucioles + sources obtenues
    #       - ennemis tués (par map)
    #       - cinématiques jouées + historique dialogues
    #       - map courante + mode + temps de jeu
    #
    #  Ces 2 méthodes sont aussi utilisées par le hot reload (Ctrl+R) :
    #  → garantit que TOUT est restauré pareil après le reload.

    def _construire_save_data(self):
        """Capture l'état complet du jeu dans un dict sérialisable JSON.

        Format : voir l'en-tête de systems/save_system.py.
        Toute donnée qui doit survivre à une fermeture / un reload doit
        figurer ici.
        """
        j = self.joueur

        # Inventaire : on sauve UNIQUEMENT le nom des items par slot
        # (les images seront re-résolues à la restauration via ITEMS).
        inv_slots = []
        for slot in getattr(self.inventory, "slots", []):
            if slot is None:
                inv_slots.append(None)
            else:
                # Format stackable {name, count}. Rétro-compat : si count=1
                # on aurait pu garder string mais on uniformise.
                inv_slots.append({
                    "name":  slot.name,
                    "count": int(getattr(slot, "count", 1)),
                })

        # Ennemis tués : pour chaque map où on a tué qqn, on retient
        # les indices d'ennemis morts. Sauve dict {map → [idx1, idx2…]}.
        # On fusionne avec un dict accumulateur qu'on construit au fur
        # et à mesure des changements de map.
        ennemis_morts = dict(getattr(self, "_ennemis_morts_par_map", {}))
        morts_actuels = [i for i, e in enumerate(self.ennemis) if not e.alive]
        if self.carte_actuelle and morts_actuels:
            ennemis_morts[self.carte_actuelle] = morts_actuels

        return {
            "_meta": {
                "play_time_s": int(getattr(self, "play_time_s", 0)),
            },
            "story": {
                "mode":                 self.mode,
                "current_map":          self.carte_actuelle,
                "cinematics_played":    self.cinematiques_jouees,
                "dialog_history":       self.historique_dialogues,
                "flags":                dict(getattr(self, "story_flags", {})),
            },
            "player": {
                "x":         int(j.rect.x),
                "y":         int(j.rect.y),
                "hp":        int(j.hp),
                "max_hp":    int(j.max_hp),
                "direction": int(j.direction),
            },
            "inventory": {
                "slots": inv_slots,
            },
            "fear": {
                "current": float(getattr(self.peur, "current", 0)),
                "target":  float(getattr(self.peur, "_target", 0)),
            },
            "companions": {
                "count":            len(self.compagnons.compagnons),
                "sources_obtained": list(getattr(self,
                                          "lucioles_sources_obtenues", set())),
            },
            "enemies": {
                "killed_per_map": ennemis_morts,
            },
            # ── Compétences débloquées (mode histoire) ─────────────────
            # Toutes les compétences (saut2, dash, dodge, wall jump, attaque,
            # pogo) → flag par skill. À chaque sauvegarde, on capture l'état
            # courant. À la restauration, on remet ces flags dans settings.
            "skills": {
                "double_jump": bool(getattr(settings, "skill_double_jump", False)),
                "dash":        bool(getattr(settings, "skill_dash",        False)),
                "back_dodge":  bool(getattr(settings, "skill_back_dodge",  False)),
                "wall_jump":   bool(getattr(settings, "skill_wall_jump",   False)),
                "attack":      bool(getattr(settings, "skill_attack",      False)),
                "pogo":        bool(getattr(settings, "skill_pogo",        False)),
            },
        }

    def _appliquer_save_data(self, data):
        """Restaure l'état complet du jeu depuis un dict produit par
        _construire_save_data(). Symétrique de la méthode précédente."""
        if not data:
            return

        # ── Story / map / mode ─────────────────────────────────────────
        story = data.get("story", {})
        self.mode                  = story.get("mode", "histoire")
        self.cinematiques_jouees   = dict(story.get("cinematics_played",  {}))
        self.historique_dialogues  = dict(story.get("dialog_history",     {}))
        self.story_flags           = dict(story.get("flags",              {}))

        if self.mode == "histoire":
            self.editeur.active = False

        carte = story.get("current_map", "")
        if carte:
            self.editeur.load_map_for_portal(carte)
            self.carte_actuelle = carte
            self._reconstruire_grille()
            self._murs_modifies()
            self._sync_triggers()

        # ── Player ─────────────────────────────────────────────────────
        j = self.joueur
        p = data.get("player", {})
        j.rect.x      = p.get("x", j.spawn_x)
        j.rect.y      = p.get("y", j.spawn_y)
        j.hp          = p.get("hp", j.max_hp)
        j.direction   = p.get("direction", j.direction)
        j.dead        = False
        j.vx = j.vy   = 0
        j.knockback_vx = 0
        # Mémorise la position chargée comme dernier point de save :
        # si le joueur meurt, "Recommencer" le ramène ICI plutôt qu'au
        # spawn de map. Sinon on perdait la progression d'exploration
        # depuis le dernier banc à chaque mort.
        if carte:
            self._dernier_save_pos = (carte, j.rect.x, j.rect.y)

        # ── Inventaire ─────────────────────────────────────────────────
        try:
            from ui.inventory import ITEMS, InventoryItem
            inv_slots = data.get("inventory", {}).get("slots", [])
            # Reset puis re-place chaque item à son ancien index.
            self.inventory.slots = [None] * len(self.inventory.slots)
            for i, entry in enumerate(inv_slots):
                if i >= len(self.inventory.slots) or entry is None:
                    continue
                # Rétro-compat : ancien format = juste le nom (string).
                if isinstance(entry, str):
                    name, count = entry, 1
                else:
                    name  = entry.get("name")
                    count = int(entry.get("count", 1))
                if not name or name not in ITEMS:
                    continue
                info = ITEMS[name]
                img  = self.inventory.images.get(name) if hasattr(self.inventory, "images") else None
                self.inventory.slots[i] = InventoryItem(
                    name, img, info.get("category", "Consommable"),
                    count=count,
                    stackable=bool(info.get("stackable", False)),
                    max_stack=int(info.get("max_stack", 1)),
                )
        except Exception as e:
            print(f"[Save] Restauration inventaire échouée : {e}")

        # ── Peur ───────────────────────────────────────────────────────
        fear = data.get("fear", {})
        if hasattr(self.peur, "current"):
            self.peur.current = float(fear.get("current", self.peur.current))
        if hasattr(self.peur, "_target"):
            self.peur._target = float(fear.get("target",  self.peur._target))

        # ── Compagnons / lucioles ──────────────────────────────────────
        comps = data.get("companions", {})
        if "count" in comps:
            self.compagnons.set_nb(int(comps["count"]))
        self.lucioles_sources_obtenues = set(comps.get("sources_obtained", []))
        self.compagnons.respawn(self.joueur)

        # ── Ennemis tués ───────────────────────────────────────────────
        # On stocke le dict complet pour pouvoir réappliquer à chaque
        # changement de map (cf. _ennemis_morts_par_map).
        ennemis = data.get("enemies", {})
        self._ennemis_morts_par_map = dict(ennemis.get("killed_per_map", {}))

        # ── Restauration des compétences débloquées ───────────────────
        # On remet les flags settings.skill_* à leur valeur sauvegardée.
        # Si la save n'a pas la section "skills" (vieille save), on garde
        # les valeurs courantes (par défaut tout False = début de partie).
        skills = data.get("skills", {})
        for nom in ("double_jump", "dash", "back_dodge",
                    "wall_jump", "attack", "pogo"):
            if nom in skills:
                setattr(settings, f"skill_{nom}", bool(skills[nom]))
        # Ré-applique sur la map courante si pertinent.
        morts = self._ennemis_morts_par_map.get(self.carte_actuelle, [])
        for i, e in enumerate(self.ennemis):
            e.alive = i not in morts

        # ── Temps de jeu ───────────────────────────────────────────────
        self.play_time_s = float(data.get("_meta", {}).get("play_time_s", 0))

        # ── SNAP CAMÉRA ────────────────────────────────────────────────
        # Sans ça, la caméra reste à sa position précédente (souvent (0, 0)
        # au tout 1er chargement) et "rattrape" le joueur en lerpant. On
        # voit la map défiler depuis un coin → on a un aperçu de la map
        # avant l'apparition du perso. snap_to() la positionne pile sur
        # le joueur d'un coup.
        self.camera.snap_to(self.joueur.rect)

    def _charger_partie(self):
        """Charge le slot le plus récent (= bouton "Continuer" du menu).

        Convention type Hollow Knight / Celeste : "Continuer" = ta partie
        la plus fraîche, sans choix à faire. Pour switcher entre slots,
        utilise le menu Charger pendant la pause.
        """
        from systems.save_system import charger_slot, slot_le_plus_recent
        slot = slot_le_plus_recent()
        donnees = charger_slot(slot) if slot else None
        if not donnees:
            self._nouvelle_partie()
            return

        self._appliquer_save_data(donnees)
        self.etats.switch(GAME)

    def _sauvegarder(self):
        """Sauvegarde la partie dans le slot 1 (bouton sauvegarde par défaut)."""
        from systems.save_system import sauvegarder_slot
        sauvegarder_slot(1, self._construire_save_data())

    # ═════════════════════════════════════════════════════════════════════════
    # 7.  INTERACTION AVEC LES PNJ
    # ═════════════════════════════════════════════════════════════════════════

    def _tenter_interaction(self):
        """Cherche un objet interactif proche et déclenche son action.

        Priorité :
          1. SAVE POINT le plus proche (décor OU PNJ avec is_save_point=True)
             → ouvre le menu de sauvegarde
          2. PNJ classique (avec dialogues) → démarre son dialogue

        Pour les save points sur DÉCORS : on prend le 1er décor avec le
        flag is_save_point dans un rayon de 80 px du joueur. Permet de
        transformer une pancarte / un banc / un autel / un décor invisible
        en point de sauvegarde, sans utiliser un PNJ.
        """
        # ── 1) Save point sur DÉCOR proche ────────────────────────────
        if self.mode == "histoire":
            jc = self.joueur.rect
            for d in getattr(self.editeur, "decors", []) or []:
                if not getattr(d, "is_save_point", False):
                    continue
                # Distance entre le centre du joueur et celui du décor.
                dx = abs(d.rect.centerx - jc.centerx)
                dy = abs(d.rect.centery - jc.centery)
                if dx < 80 and dy < 80:
                    self._ouvrir_save_point()
                    return

        # ── 2) PNJ proche (save point ou dialogue normal) ─────────────
        for pnj in self.editeur.pnjs:
            if not pnj.peut_interagir(self.joueur.rect):
                continue

            if getattr(pnj, "is_save_point", False) and self.mode == "histoire":
                self._ouvrir_save_point()
                return

            # PNJ normal : on démarre son dialogue. On passe les story
            # flags pour que conversation_actuelle puisse débloquer/sauter
            # les conv selon les conditions (cf. PNJ.dialogue_conditions).
            lignes = pnj.conversation_actuelle(getattr(self, "story_flags", {}))
            if lignes:
                self.dialogue.demarrer(lignes)
                self._pnj_actif = pnj
                # Stoppe net la course/marche du joueur AU MOMENT où il
                # appuie sur E (sinon il glisse pendant 1-2 frames avec
                # son anim run avant que mouvement_bloque prenne effet).
                self.joueur.forcer_idle()
            return

    def _ouvrir_save_point(self):
        """Bascule en pause + ouvre le SaveMenu (commun PNJ et décor)."""
        self.etats.switch(PAUSE)
        self.menu_pause.selection = 0
        self.save_menu.open(mode="save")
        self._save_point_actif = True

    # ═════════════════════════════════════════════════════════════════════════
    # 8.  LOGIQUE PAR ÉTAT (MENU, PAUSE, GAME_OVER)
    # ═════════════════════════════════════════════════════════════════════════

    def _lancer_fondu_menu(self, action):
        """Lance un fondu noir depuis le menu, puis exécute `action()`.

        On veut une SÉPARATION NETTE entre le menu et le jeu :
          - musique du menu : fade-out rapide (~1.5s) pour ne pas dépasser
            sur le jeu (avant : 4s → on l'entendait encore en jeu)
          - effet de réveil : descente forcée + hard-cut au switch GAME
            (cf. _wrap_action) → pas de halo qui traîne en jeu
          - quand le voile est noir (alpha=255), action() s'exécute, on
            cale tout à zéro proprement, puis fondu entrant.
        """
        self._menu_fondu_etat   = "out"
        self._menu_fondu_alpha  = 0
        self._menu_fondu_action = self._wrap_action(action)
        # Fadeout musique du menu : court (1.5s) pour qu'elle soit
        # silencieuse au moment où le voile noir est plein → on ne
        # l'entend pas dans le jeu.
        music.arreter(fadeout_ms=1500)
        # Effet de réveil : descente forcée pour qu'il atteigne 0
        # avant qu'on entre vraiment en jeu.
        self.effet_reveil.forcer_extinction()

    def _wrap_action(self, action):
        """Wrappe l'action de transition pour CASSER NET les artefacts du
        menu juste avant d'exécuter le code de transition.

        Quand on a fini le fondu noir et qu'on s'apprête à entrer en jeu :
          - on coupe la musique du menu instantanément (au cas où le fade
            n'a pas fini)
          - on remet l'intensité de l'effet_reveil à 0 (hard cut → pas de
            résidu lumineux qui traîne au début du jeu)
        """
        def _wrapped():
            # Hard cut musique
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            # Hard cut effet_reveil (intensité interne)
            try:
                self.effet_reveil.intensite = 0.0
                self.effet_reveil._cible    = 0.0
            except AttributeError:
                pass
            # Maintenant on lance vraiment l'action (chargement / nouvelle partie)
            action()
        return _wrapped

    def _gerer_menu(self, events):
        """Gestion du menu titre (état MENU)."""
        # Si un fondu menu→jeu est en cours, on n'accepte plus d'input.
        if self._menu_fondu_etat != "none":
            return

        for event in events:
            if event.type != pygame.KEYDOWN:
                continue

            # Le menu de sélection de slot intercepte tout tant qu'il est
            # visible (ouvert par "Continuer" → mode load).
            if self.save_menu.visible:
                res = self.save_menu.handle_key(event.key)
                if res is not None:
                    action, slot = res
                    if action == "load":
                        # On charge la sauvegarde DANS le fondu pour avoir
                        # une transition propre (écran noir → chargement →
                        # apparition progressive du jeu).
                        from systems.save_system import charger_slot
                        donnees = charger_slot(slot)
                        if donnees is not None:
                            def _action():
                                self._appliquer_save_data(donnees)
                                self.etats.switch(GAME)
                            self._lancer_fondu_menu(_action)
                continue

            choix = self.menu_titre.handle_key(event.key)

            if choix == "Continuer":
                # On ouvre le menu de sélection de slot AU LIEU de charger
                # automatiquement le plus récent. Le joueur choisit lui-même
                # quelle sauvegarde reprendre (essentiel s'il a plusieurs
                # parties en parallèle dans des slots différents).
                self.save_menu.open(mode="load")

            elif choix == "Nouvelle partie":
                # On utilise une vraie fonction locale pour pouvoir
                # écrire plusieurs lignes (une lambda ne fait qu'une expression).
                def _action():
                    # Nouvelle partie = on EFFACE TOUTES les sauvegardes
                    # (manuelles + autosave). Convention attendue par le
                    # joueur : repartir d'une page blanche.
                    from systems.save_system import supprimer_tout
                    supprimer_tout()
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

            # Le menu de sauvegarde / chargement (overlay) intercepte tout
            # tant qu'il est visible. Retours possibles :
            #   ("save", n)  → écrire la partie dans le slot n
            #   ("load", n)  → charger le slot n
            #   ("close", _) → simple fermeture
            if self.save_menu.visible:
                res = self.save_menu.handle_key(event.key)
                if res is not None:
                    action, slot = res
                    if action == "save":
                        from systems.save_system import sauvegarder_slot
                        sauvegarder_slot(slot, self._construire_save_data())
                        # Mémorise le dernier point de sauvegarde pour que
                        # "Recommencer" après mort y revienne au lieu du
                        # spawn de la map.
                        self._dernier_save_pos = (
                            self.carte_actuelle,
                            self.joueur.rect.x,
                            self.joueur.rect.y,
                        )
                        self.save_menu._refresh()
                        # Déclenche le toast "Sauvegardé" avec spinner.
                        self._save_toast_timer = self._save_toast_duree
                    elif action == "load":
                        from systems.save_system import charger_slot
                        donnees = charger_slot(slot)
                        if donnees is not None:
                            self._appliquer_save_data(donnees)
                            self.etats.switch(GAME)
                    # Si on est venu d'un SAVE POINT (interaction PNJ
                    # sauvegarde), on renvoie direct en GAME au lieu de
                    # rester bloqué dans le menu pause après la save.
                    if getattr(self, "_save_point_actif", False):
                        self._save_point_actif = False
                        if not self.save_menu.visible:
                            self.etats.switch(GAME)
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
            elif choix == "Charger":
                self.save_menu.open(mode="load")
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
                # On reconstruit le menu titre pour que "Continuer" apparaisse
                # si une sauvegarde a été faite pendant la partie.
                self._rafraichir_menu_titre()
                self.etats.switch(MENU)
            elif choix == "Quitter":
                self.running = False

    def _gerer_fin(self, events):
        """Gestion de l'écran Game Over (état GAME_OVER)."""
        # Cinématique de mort scriptée en cours ? On bloque les boutons
        # « Recommencer / Menu » : seules les touches du dialogue (Espace
        # / Entrée pour avancer) sont autorisées. Le clavier passe par
        # cutscene.on_key qui consomme Espace/Entrée pour advancer la
        # boîte de dialogue. La cinématique se terminera par revive_player
        # → on rebascule en GAME automatiquement (ci-dessous _frame_game_over).
        if self.cutscene is not None:
            for event in events:
                if event.type != pygame.KEYDOWN:
                    continue
                # On laisse cutscene.on_key décider — il consomme Espace/
                # Entrée pour le dialogue, et IGNORE Échap (on n'autorise
                # pas le skip d'une cinématique de mort, ce serait un
                # contournement du blocage).
                if event.key == pygame.K_ESCAPE:
                    continue
                try:
                    from systems.cutscene import CutsceneContext
                    self.cutscene.on_key(event.key, CutsceneContext(self))
                except Exception:
                    pass
            return

        for event in events:
            if event.type != pygame.KEYDOWN:
                continue

            choix = self.menu_fin.handle_key(event.key)
            if choix == "Recommencer":
                # Recommencer = respawn sur la MAP COURANTE (pas retour
                # à la map de début). Avant on appelait _nouvelle_partie()
                # qui rechargeait la carte_debut → le joueur était puni
                # de mort en perdant TOUTE sa progression de map.
                # Maintenant : on remet juste les PV, on respawn au point
                # de spawn de la map courante, on revive les ennemis. La
                # progression (objets ramassés, ennemis tués, dialogues)
                # est conservée comme dans la plupart des metroidvanias.
                self.joueur.hp           = self.joueur.max_hp
                self.joueur.dead         = False
                self.joueur.vx           = 0
                self.joueur.vy           = 0
                self.joueur.knockback_vx = 0
                self.joueur.invincible   = False
                # Si on a un dernier point de sauvegarde sur la map COURANTE,
                # on respawn dessus. Sinon, fallback au spawn de map.
                _dsp = getattr(self, "_dernier_save_pos", None)
                if _dsp and _dsp[0] == self.carte_actuelle:
                    self.joueur.rect.x = _dsp[1]
                    self.joueur.rect.y = _dsp[2]
                else:
                    self.joueur.rect.x = self.editeur.spawn_x
                    self.joueur.rect.y = self.editeur.spawn_y
                self.camera.snap_to(self.joueur.rect)
                # Réveille les ennemis de la map courante.
                for e in self.ennemis:
                    e.alive = True
                self.compagnons.respawn(self.joueur)
                self._gameover_fade_alpha = 0.0
                self.etats.switch(GAME)
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
        # ── ÉCRAN DE CHARGEMENT : simulation gelée tant que le fondu IN
        # n'est pas terminé. Le joueur ne tombe pas, les ennemis ne bougent
        # pas, mais on continue de RENDRE la scène (fait via _frame_jeu →
        # _dessiner_monde) pour que les textures pré-chargent en mémoire.
        # Quand l'image est pleinement révélée, la simulation reprend.
        if self._est_en_chargement():
            return

        # Tracking du temps de jeu cumulé (pour l'affichage dans le menu de
        # sauvegarde). Compte uniquement le temps PASSÉ dans l'état GAME
        # ET hors écran de chargement.
        self.play_time_s = getattr(self, "play_time_s", 0.0) + dt

        # ── 1. Gestionnaire histoire (prioritaire) ────────────────────────
        if self.gestionnaire_histoire.actif:
            for event in events:
                self.gestionnaire_histoire.handle_event(event)
            return

        # ── 2. Événements clavier / souris ────────────────────────────────
        self._traiter_evenements_jeu(events)

        # ── 3-9. Logique de simulation ────────────────────────────────────
        self._simuler_jeu(dt)

        # ── 10. Mort → Cinématique de mort scriptée + Game Over ─────────
        if self.joueur.dead:
            # On bascule TOUJOURS en GAME_OVER (l'écran de mort apparaît).
            # En PLUS, on cherche une CutsceneTrigger mode "on_death" qui
            # couvre la position : si trouvée, on la lance — son dialogue
            # s'affichera PAR-DESSUS l'écran de mort. Tant que la cinéma-
            # tique tourne, _gerer_fin bloque le bouton « Recommencer ».
            # À la fin (action revive_player), le joueur est téléporté
            # ailleurs et l'écran de mort disparaît.
            self.etats.switch(GAME_OVER)
            self.menu_fin.selection = 0
            self._gameover_fade_alpha = 0.0
            self._declencher_cinematique_mort()

        # Drag-and-drop dans l'inventaire
        self.inventory.drag_drop(events)

        # Barre quick-use (touches 1/2/3/4 → consomme l'item du slot).
        # On la traite ici plutôt que dans _traiter_evenements_jeu pour
        # qu'elle reste active même quand un overlay éditeur est ouvert.
        if not self.editeur.active and not self.dialogue.actif:
            for ev in events:
                self.quick_use.handle_event(ev)
        self.quick_use.update(dt)

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
                # Panneau debug story flags (F5) prioritaire.
                if self._story_flags_panel_handle_textinput(event.text):
                    pass
                elif self.editeur.active and self.editeur._text_mode:
                    self.editeur.handle_textinput(event.text)

            # ── Souris dans l'éditeur (clic / molette) ──
            if self.editeur.active and self.editeur._text_mode is None:
                self._gerer_souris_editeur(event)

            # ── Caméra libre (clic molette pour pan / mode décor 9) ──
            self._gerer_clic_molette(event)

    def _gerer_touche(self, key):
        """Dispatche une touche vers l'action correspondante."""
        # Ctrl+R : HOT RELOAD (sauvegarde position + relance process Python).
        # Très tôt dans la chaîne pour court-circuiter dialogues/menus/éditeur.
        # On ne le déclenche QUE si le mode texte de l'éditeur n'est PAS actif,
        # sinon "r" doit pouvoir s'écrire dans une saisie de nom.
        if key == pygame.K_r and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            if not (self.editeur.active and self.editeur._text_mode):
                from core.hot_reload import declencher_hot_reload
                declencher_hot_reload(self)
                return  # jamais atteint (execv remplace le process)

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
                # Résolution tolérante du nom (ex. "pomme" → "Pomme").
                nom_brut = item.get("nom", "")
                if nom_brut in ITEMS:
                    nom = nom_brut
                elif nom_brut.capitalize() in ITEMS:
                    nom = nom_brut.capitalize()
                else:
                    nom = None
                    print(f"[Boutique] Item inconnu dans ITEMS : '{nom_brut}'. "
                          f"Items disponibles : {list(ITEMS.keys())}")

                if nom is not None:
                    # UN SEUL add_item (auparavant : on ajoutait 2 fois).
                    ok = self.inventory.add_item(nom)
                    if ok:
                        self.boutique._show_msg = f"{nom} acheté !"
                        # Son d'achat (réutilise ui_select).
                        try:
                            from audio import sound_manager
                            sound_manager.jouer("ui_select", volume=0.5)
                        except Exception:
                            pass
                    else:
                        # Inventaire plein → on rembourse pour ne pas
                        # punir le joueur (avant : il perdait ses pièces).
                        self.joueur.coins += int(item.get("prix", 0))
                        self.boutique._show_msg = "Inventaire plein !"
                else:
                    # Refund si item introuvable côté ITEMS.
                    self.joueur.coins += int(item.get("prix", 0))
                    self.boutique._show_msg = "Item indisponible."
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

        # F5 : panneau debug des story flags (éditeur seulement).
        # Toggle l'overlay qui liste tous les flags posés et permet de
        # les basculer pour tester les conditions de dialogue PNJ.
        if key == pygame.K_F5 and self.mode == "editeur" and key == pygame.K_s:
            self._story_flags_panel_open = not getattr(
                self, "_story_flags_panel_open", False)
            return

        # En mode éditeur, si le panneau flags est ouvert, il intercepte
        # les touches utiles (T pour toggle, A pour ajouter).
        if (self.mode == "editeur"
                and getattr(self, "_story_flags_panel_open", False)):
            if self._story_flags_panel_handle_key(key):
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
        """Téléporte le joueur au respawn d'une danger_zone et applique 1 PV
        de dégât (sans l'animation de hurt qui figerait le perso).

        Comportement attendu :
          - 1 cœur de dégât par chute dans la zone
          - téléport au point de respawn défini avec la zone
          - invincibilité courte pour ne pas reprendre des dégâts en boucle
            si on retombe immédiatement dans la zone
          - si le joueur meurt (hp ≤ 0) → flag dead = True → l'écran de
            mort prend le relais et le bouton « Recommencer » respawne au
            dernier point de sauvegarde (cf. _gerer_fin)."""
        # ── 1. Si déjà invincible : on ignore (anti-spam des dégâts) ──
        # mais on laisse quand même la téléportation se faire pour ne pas
        # rester coincé dans la zone.
        applique_degat = (not getattr(self.joueur, "invincible", False)
                          and not getattr(self.joueur, "dead", False))

        # ── 2. Téléportation ──
        self.joueur.rect.x = x
        self.joueur.rect.y = y

        # ── 3. Reset des vitesses (vx/vy + knockback) pour ne pas garder
        # l'élan de chute et retomber instantanément. Attention : les
        # attributs sont vx/vy, pas vel_x/vel_y.
        self.joueur.vx           = 0
        self.joueur.vy           = 0
        self.joueur.knockback_vx = 0

        # ── 4. Dégât + invincibilité (sans animation hurt) ──
        if applique_degat:
            self.joueur.hp -= 1
            try:
                from audio import sound_manager
                sound_manager.jouer("degat")
            except Exception:
                pass
            # Affichage des cœurs au-dessus du joueur
            try:
                import settings
                self.joueur.show_hp_timer  = settings.HP_DISPLAY_DURATION
                self.joueur.invincible       = True
                self.joueur.invincible_timer = settings.INVINCIBLE_DURATION
            except Exception:
                # Fallback si settings ne charge pas (ne devrait pas arriver)
                self.joueur.invincible       = True
                self.joueur.invincible_timer = 1.0
            # Mort ? Le bouton Recommencer respawnera au dernier save.
            if self.joueur.hp <= 0:
                self.joueur.dead = True
                try:
                    from audio import sound_manager
                    sound_manager.jouer("mort")
                except Exception:
                    pass

        # ── 5. Effet visuel (screen shake) ──
        # API : trigger(amplitude, duree). Avant on appelait ajouter(...)
        # qui n'existait pas → crash.
        if hasattr(self, "shake"):
            self.shake.trigger(amplitude=8, duree=0.2)

        # ── 6. Snap caméra sur le nouveau point (évite le glissement) ──
        if hasattr(self.camera, "snap_to"):
            self.camera.snap_to(self.joueur.rect)
        

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
        # une cinématique en cours. EXCEPTION : pour les portails AUTO
        # (sauter dans un trou téléporteur), on laisse la physique tourner
        # pendant le fondu out → le joueur continue sa chute, plus réaliste.
        # EXCEPTION 2 : pendant une étape `wait_for_player_at`, la
        # cinématique a explicitement libéré le contrôle (drapeau posé
        # par cutscene.py). On le RESET à False ici, c'est l'étape qui
        # le rallumera chaque frame tant qu'elle est active.
        fondu_freeze = (self._fondu_etat != "none"
                        and getattr(self, "_portail_freeze_pendant_fondu", True))
        # 3 façons de laisser le joueur bouger pendant une cinématique :
        #   1. _cutscene_player_libre : drapeau frame-by-frame posé par
        #      l'étape wait_for_player_at (joueur libre durant cette étape).
        #   2. cutscene.player_libre  : drapeau permanent posé sur l'objet
        #      Cutscene tout entier — ex. shake d'ambiance à la chute, le
        #      joueur garde sa gravité du début à la fin de la cinématique.
        #   3. Pas de cutscene en cours : trivial, freeze=False.
        cine_libre = (self.cutscene is not None
                      and getattr(self.cutscene, "player_libre", False))
        cutscene_freeze = (self.cutscene is not None
                           and not getattr(self, "_cutscene_player_libre", False)
                           and not cine_libre)
        self._cutscene_player_libre = False
        # Pareil pour le dialogue : si la cinématique est "joueur libre",
        # l'éventuelle étape dialogue ne doit pas bloquer la course/gravité.
        dialogue_freeze = self.dialogue.actif and not cine_libre
        mouvement_bloque = (fondu_freeze
                            or dialogue_freeze
                            or cutscene_freeze)
        # Drapeau "mode éditeur" pour le gating des compétences (toutes
        # débloquées en mode éditeur, restrictif en mode histoire).
        self.joueur._in_editor_mode = (self.mode == "editeur")

        if not mouvement_bloque:
            self.joueur.mouvement(phys_dt, keys, holes=trous)
        else:
            # Force la pose idle pendant dialogue / cutscene / fondu :
            # sinon l'anim "running" continue à tourner alors que le perso
            # est censé être figé pour parler.
            self.joueur.vx       = 0
            self.joueur.walking  = False
            self.joueur.running  = False
            # Stoppe aussi le son des pas qui pourrait tourner
            try:
                from audio import sound_manager
                sound_manager.arreter("pas")
            except Exception:
                pass

        self.camera.update(self.joueur.rect, dt)

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

            # 2. Gestion des collisions (Dégâts reçus par le joueur)
            # Skip total si invincible : le joueur PASSE À TRAVERS l'ennemi
            # (pas de re-déclenchement de hit, et indirectement ça évite tout
            # effet collatéral de la collision pendant la phase de recul).
            if (entite.alive
                    and not self.joueur.invincible
                    and self.joueur.rect.colliderect(entite.rect)):
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
            # ── ÉVÉNEMENTS DE DIALOGUE ─────────────────────────────────
            # On déclenche AVANT passer_a_suivante() pour que les events
            # référent à la conv qui VIENT D'ÊTRE LUE (et pas la suivante).
            try:
                evts = self._pnj_actif.evenements_a_declencher()
            except AttributeError:
                evts = []
            for e in evts:
                try:
                    self._appliquer_event_pnj(e)
                except Exception as exc:
                    print(f"[event PNJ] Échec {e!r} : {exc}")
            self._pnj_actif.passer_a_suivante()
            if isinstance(self._pnj_actif, Marchand):
                self.boutique.ouvrir(self._pnj_actif.inventaire)
            self._pnj_actif = None

        # Zones-déclencheurs (téléportation / cinématiques) — front-montant
        # sur la collision joueur/zone. Vide tant qu'aucune carte n'en pose.
        self.triggers.check(self.joueur, {"game": self})

        # Cinématiques conditionnelles (déclenchées par flags). On décompte
        # le délai post-dialogue puis on lance la cinématique éligible.
        self._avancer_verif_cine(dt)

        # Cinématique en cours : on l'avance, et quand elle est terminée
        # on rend la main au joueur. Le contexte donne accès à camera,
        # joueur, dialogue_box, particles, shake, son, pnjs (cf. CutsceneContext).
        if self.cutscene is not None:
            # Stoppe net la marche du joueur : sinon il garde sa vitesse et
            # son animation walking jusqu'à la fin de la cinématique. Le son
            # de pas est aussi arrêté pour éviter qu'il continue.
            # SAUF si la cinématique est "joueur libre" (ex. shake à la chute) :
            # on laisse les contrôles et l'animation telle quelle.
            if not getattr(self.cutscene, "player_libre", False):
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
        police = self.editeur._get_font()

        if self.editeur.show_hitboxes or self.editeur.active:
            for portail in self.editeur.portals:
                portail.draw(self.screen, self.camera, police)

        # affiche Z quand tu t'approches d'un portail 

        for portail in self.editeur.portals:
            
            dx = abs(portail.rect.centerx - self.joueur.rect.centerx)
            dy = abs(portail.rect.centery - self.joueur.rect.centery)
            if dx > 150 or dy > 100:
                continue

            cam = self.camera.apply(portail.rect)
            text = police.render("[Z]", True, (220, 200, 50))

            self.screen.blit(
                text, (cam.centerx - text.get_width() // 2,
                cam.top - 22
                ))

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
            # Croix directionnelle de consommables rapides (bas-droite).
            self.quick_use.draw(self.screen)
            # Toast "Sauvegardé" + spinner après une save (timer décroit).
            self._dessiner_save_toast()
            # Notifications éphémères (compétence débloquée, items reçus…)
            self._dessiner_notifications()

        # Panneau debug story flags (F5 en mode éditeur). Dessiné en
        # dehors du if-not-editor pour rester visible en mode éditeur.
        self._dessiner_story_flags_panel()

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

    def _dessiner_save_toast(self):
        """Affiche le petit toast 'Sauvegardé' avec spinner en bas-droite.

        Activé via self._save_toast_timer (set à _save_toast_duree à
        chaque save réussie). Décrémenté à chaque frame ; quand <=0,
        plus rien ne s'affiche.
        """
        if self._save_toast_timer <= 0:
            return
        self._save_toast_timer -= self._dt
        # Alpha : pleine opacité au début, fade-out sur la dernière demi-seconde.
        ratio = max(0.0, min(1.0, self._save_toast_timer / 0.5))
        alpha = int(255 * (1.0 if self._save_toast_timer > 0.5 else ratio))

        w, h = self.screen.get_size()
        font = pygame.font.SysFont("Consolas", 14, bold=True)
        txt = font.render("Sauvegardé", True, (255, 215, 70))
        # Spinner : cercle qui tourne — segment rotatif basé sur le temps.
        import math as _m
        t = pygame.time.get_ticks() / 1000.0
        spin_r = 8
        cx, cy = 14, 14
        # Bandeau
        bandeau_w = txt.get_width() + 30 + spin_r * 2
        bandeau_h = 28
        bx = w - bandeau_w - 16
        by = h - bandeau_h - 16
        bg = pygame.Surface((bandeau_w, bandeau_h), pygame.SRCALPHA)
        bg.fill((20, 14, 38, int(220 * alpha / 255)))
        pygame.draw.rect(bg, (110, 90, 200, alpha),
                         pygame.Rect(0, 0, bandeau_w, bandeau_h), 1)
        # Spinner (4 points sur cercle, intensité variable selon angle)
        for i in range(8):
            ang = t * 6 + i * (_m.pi / 4)
            px = cx + int(_m.cos(ang) * spin_r)
            py = cy + int(_m.sin(ang) * spin_r)
            inten = int(255 * (i + 1) / 8 * alpha / 255)
            pygame.draw.circle(bg, (255, 215, 70, inten), (px, py), 2)
        # Texte
        bg.blit(txt, (30, (bandeau_h - txt.get_height()) // 2))
        self.screen.blit(bg, (bx, by))

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
            # IMPORTANT : on ne le dessine QUE dans l'état MENU. Une fois
            # qu'on entre en jeu, c'est un environnement totalement différent
            # → pas de halo ni de particules du menu. Sans ça, l'effet
            # restait visible plusieurs secondes en jeu (descente lente).
            # _frame_menu lui-même appelle déjà update() pendant le fondu,
            # mais ici on garantit qu'AUCUN draw ne fuite hors du menu.
            if self.etats.is_menu:
                self.effet_reveil.update(self._dt)
                self.effet_reveil.draw(self.screen)

            # ── 5b. Filtre de luminosité (post-process global) ──
            # settings.luminosite : 1.0 = normal, < 1.0 = assombrit (overlay
            # noir), > 1.0 = éclaircit (overlay blanc). On applique ICI, en
            # dernier, pour que TOUT (jeu, HUD, menus, paramètres) soit
            # affecté pareil → cohérent quel que soit l'écran utilisé.
            self._appliquer_luminosite()

            # ── 5c. Indicateur de chargement (3 points animés en bas-droite) ──
            # Dessiné PAR-DESSUS le voile noir pendant la phase "loading".
            self._dessiner_indicateur_chargement()

            # ── 6. Affichage final ──
            pygame.display.flip()

    def _precharger_textures_legacy(self):
        """Ancienne version (laissée en référence). Voir _precharger_textures."""
        return

    def _precharger_textures(self):
        """Pré-conversion légère des textures de la map.

        On se contente de .convert_alpha() chaque surface (= les met au bon
        format mémoire CPU). Sur la plupart des configs pygame/SDL, ça
        suffit pour éviter le pop visible quand le sprite est rendu pour
        la 1ère fois.

        On a abandonné le blit-sur-display+flip qu'on avait essayé avant :
        sur certaines configs il causait des freezes au boot (gros lots
        de flips → GPU thrashing → FPS qui yo-yo pendant 1 minute) sans
        avantage perceptible côté upload textures.

        Si du flicker persiste après ce convert_alpha, c'est probablement
        une limitation pygame/SDL qu'on ne peut pas vraiment court-circuiter.
        """
        # ── Décors ──
        for liste_attr in ("decors", "decors_fond", "decors_avant"):
            for d in (getattr(self.editeur, liste_attr, None) or []):
                img = getattr(d, "image", None)
                if img is not None:
                    try:
                        d.image = img.convert_alpha()
                    except Exception:
                        pass

        # ── Ennemis ──
        for ennemi in (getattr(self, "ennemis", None) or []):
            for attr in ("image", "_image", "sprite_courant"):
                img = getattr(ennemi, attr, None)
                if img is not None:
                    try:
                        setattr(ennemi, attr, img.convert_alpha())
                    except Exception:
                        pass

        # ── Joueur : toutes les frames de toutes les anims ──
        for nom in dir(self.joueur):
            if not (nom.startswith("idle_anim_") or nom.startswith("anim_")):
                continue
            anim = getattr(self.joueur, nom, None)
            images = getattr(anim, "images", None) if anim else None
            if images is None:
                continue
            for i, frame in enumerate(images):
                try:
                    images[i] = frame.convert_alpha()
                except Exception:
                    pass

    def _precharger_textures_OLD(self):
        """Force le chargement GPU de TOUTES les textures de la map courante.

        Pourquoi ? pygame charge les textures en LAZY : la conversion vers
        le format display (et l'upload GPU sur certains backends) se fait
        au premier blit SUR LA DISPLAY SURFACE (l'écran réel).

        Mon premier essai blittait sur un dummy 1×1 → ça convertit le
        format mémoire mais ne déclenche PAS l'upload GPU. Du coup les
        gros décors (fonds Tiled, parallax) re-flickaient au 1er rendu.

        Cette version blit TOUS les sprites sur self.screen (la vraie
        display surface), à des coords NÉGATIVES (= 100% clippés, donc
        invisibles), ce qui force pygame à uploader chaque texture côté
        GPU. Ensuite on fill l'écran en noir pour repartir propre.
        """
        screen = self.screen

        # 1) On collecte toutes les images uniques de la map à pré-charger.
        textures = []
        for liste_attr in ("decors", "decors_fond", "decors_avant"):
            for d in (getattr(self.editeur, liste_attr, None) or []):
                img = getattr(d, "image", None)
                if img is not None:
                    try:
                        d.image = img.convert_alpha()
                    except Exception:
                        pass
                    textures.append(d.image)

        for ennemi in (getattr(self, "ennemis", None) or []):
            for attr in ("image", "_image", "sprite_courant"):
                img = getattr(ennemi, attr, None)
                if img is not None:
                    try:
                        setattr(ennemi, attr, img.convert_alpha())
                    except Exception:
                        pass
                    textures.append(getattr(ennemi, attr))

        for nom in dir(self.joueur):
            if not (nom.startswith("idle_anim_") or nom.startswith("anim_")):
                continue
            anim   = getattr(self.joueur, nom, None)
            images = getattr(anim, "images", None) if anim else None
            if images is None:
                continue
            for i, frame in enumerate(images):
                try:
                    images[i] = frame.convert_alpha()
                except Exception:
                    pass
                textures.append(images[i])

        # 2) Pré-upload : on blit chaque texture à des coords VISIBLES (0,0)
        # de la display surface. Coords visibles = SDL fait l'upload GPU
        # vraiment (les blits clippés à coords négatives sont souvent
        # court-circuités côté backend → pas d'upload).
        # On flip() périodiquement pour FORCER SDL à committer le batch.
        # Le joueur ne voit rien : on est en plein OUT/LOADING, le voile
        # noir est dessiné dès la frame suivante.
        BATCH = 25
        for i, img in enumerate(textures):
            screen.blit(img, (0, 0))
            if (i + 1) % BATCH == 0:
                pygame.display.flip()
                screen.fill((0, 0, 0))

        # Flip + clear final pour repartir d'un écran propre.
        pygame.display.flip()
        screen.fill((0, 0, 0))

        # Décommente pour debug :
        # print(f"[Loading] {len(textures)} textures uploadees au GPU")

    def _appliquer_luminosite(self):
        """Pose un voile final selon settings.luminosite.

        Permet d'ajuster la luminosité globale de l'image rendue sans
        toucher aux assets ni à l'éclairage du moteur. Utile quand
        l'écran physique du joueur est très sombre ou très clair.

        - luminosite = 1.0 → rien à faire (chemin rapide)
        - luminosite < 1.0 → voile NOIR semi-transparent (assombrit)
        - luminosite > 1.0 → voile BLANC semi-transparent (éclaircit)

        L'alpha est proportionnel à l'écart par rapport à 1.0, plafonné à
        ~150 pour ne jamais blanchir/noircir totalement l'écran.
        """
        l = settings.luminosite
        if abs(l - 1.0) < 0.02:
            return    # quasi-neutre → rien à dessiner

        w, h = self.screen.get_size()

        # On utilise un BLEND MULTIPLICATIF / ADDITIF au lieu d'un overlay
        # alpha (qui faisait un effet "brouillard" devant les objets).
        #
        #   l < 1.0 (assombrir)  → BLEND_MULT avec un gris (l, l, l) :
        #       chaque pixel devient pixel * l → noirs restent noirs,
        #       blancs deviennent gris. Pas de brume, juste sombre.
        #   l > 1.0 (éclaircir)  → BLEND_ADD avec un gris (l-1)*255 :
        #       chaque pixel ajouté → on tire vers le blanc proprement.
        #
        # Ça ressemble vraiment à un réglage de luminosité d'écran et
        # non à un filtre de brume.
        cle = (w, h, round(l, 2))
        if getattr(self, "_voile_lumi_cle", None) != cle:
            voile = pygame.Surface((w, h))
            if l < 1.0:
                # Multiplier par l → on encode l*255 dans un gris
                v = int(max(0.0, min(1.0, l)) * 255)
                voile.fill((v, v, v))
                self._voile_lumi_mode = pygame.BLEND_MULT
            else:
                # Ajouter (l-1)*255 → gris additionné aux pixels
                v = int(min(0.5, l - 1.0) * 220)   # plafonné pour éviter blanc total
                voile.fill((v, v, v))
                self._voile_lumi_mode = pygame.BLEND_ADD
            self._voile_lumi     = voile
            self._voile_lumi_cle = cle
        self.screen.blit(self._voile_lumi, (0, 0),
                         special_flags=self._voile_lumi_mode)

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

    # Vitesses du voile noir (alpha/seconde) + durée de la phase loading.
    #   OUT      : 130 → ~2 s pour passer de 0 à 255 (fade-out rapide)
    #   LOADING  : 1.5 s minimum, voile NOIR PLEIN + indicateur de chargement
    #              On continue de rendre la scène EN DESSOUS du voile pour
    #              warmup les textures sans que le joueur les voit.
    #   IN       : 90 → ~3 s pour passer de 255 à 0 (fade-in court, doux)
    _MENU_FONDU_VITESSE_OUT = 130.0
    _MENU_FONDU_VITESSE_IN  = 90.0
    _CHARGEMENT_DUREE       = 4  # secondes mini sur l'écran de chargement

    def _avancer_fondu_menu(self):
        """Fait progresser le fondu noir d'une frame.

        États possibles :
          "none"     : rien à faire
          "out"      : fade-out depuis menu (alpha 0 → 255)
                       à la fin, action() s'exécute → on passe en "loading"
          "loading"  : écran 100% noir + indicateur de chargement
                       reste affiché _CHARGEMENT_DUREE secondes mini
                       → on passe en "in" automatiquement
          "in"       : fade-in vers le jeu (alpha 255 → 0)
                       à la fin, état "none"
        """
        if self._menu_fondu_etat == "out":
            self._menu_fondu_alpha += self._MENU_FONDU_VITESSE_OUT * self._dt
            if self._menu_fondu_alpha >= 255:
                self._menu_fondu_alpha = 255
                if self._menu_fondu_action:
                    self._menu_fondu_action()
                    self._menu_fondu_action = None
                # Passe en phase de chargement (écran noir + loader).
                self._menu_fondu_etat   = "loading"
                self._chargement_timer  = self._CHARGEMENT_DUREE
                # PRÉ-CHARGE TOUTES les textures de la map maintenant que
                # action() les a chargées en mémoire. Sans ça, les textures
                # hors champ de caméra restent en format natif et causent
                # un stutter quand le joueur les croise plus tard.
                try:
                    self._precharger_textures()
                except Exception as e:
                    print(f"[Loading] précharge textures : {e}")
        elif self._menu_fondu_etat == "loading":
            # Décompte du chargement. Le voile reste à 255 (noir total).
            self._menu_fondu_alpha = 255
            self._chargement_timer -= self._dt
            if self._chargement_timer <= 0:
                self._menu_fondu_etat = "in"
        elif self._menu_fondu_etat == "in" and self._menu_fondu_alpha > 0:
            self._menu_fondu_alpha -= self._MENU_FONDU_VITESSE_IN * self._dt
            if self._menu_fondu_alpha <= 0:
                self._menu_fondu_alpha = 0
                self._menu_fondu_etat  = "none"

    def _est_en_chargement(self):
        """True UNIQUEMENT pendant la phase 'loading' (écran noir total).

        Avant : retournait True aussi pendant 'in' → le joueur restait
        figé en l'air pendant 3s de fade-in puis tombait d'un coup. Pas
        immersif, ressemblait à un bug.

        Maintenant : dès que la phase 'in' commence (donc dès la fin de
        l'écran noir), la simulation reprend → le joueur SUBIT la gravité
        et commence à tomber pendant que le voile noir se lève. Le joueur
        voit la chute en même temps que le monde apparaît, comme dans
        n'importe quel jeu vidéo.
        """
        return self._menu_fondu_etat == "loading"

    def _dessiner_indicateur_chargement(self):
        """3 points animés en bas à droite pendant la phase loading.

        Visible pendant LOADING + début de IN, avec un fade-out doux quand
        on bascule sur IN (sinon les points disparaissent brutalement). On
        calcule l'opacité en fonction de l'état :
          - LOADING : opacité pleine (255)
          - IN avec alpha > 200 : opacité décroît proportionnellement
          - IN avec alpha < 200 : invisibles
        Donne une transition naturelle "écran noir avec dots → fade in".
        """
        # Détermine l'opacité des points selon la phase
        if self._menu_fondu_etat == "loading":
            opacite = 255
        elif self._menu_fondu_etat == "in":
            # Fade out des points sur les ~50 premiers points d'alpha
            if self._menu_fondu_alpha >= 220:
                opacite = int((self._menu_fondu_alpha - 220) / 35 * 255)
                opacite = max(0, min(255, opacite))
            else:
                return  # plus rien à dessiner
        else:
            return

        w, h = self.screen.get_size()
        import time as _t
        # Animation continue : chaque point pulse légèrement, déphasés.
        # plus doux qu'un "ON/OFF" → ressenti plus moderne.
        for i in range(3):
            phase = (_t.time() * 1.8 + i * 0.35) % 1.0
            # Sinusoidale pour pulse fluide
            import math as _m
            pulse = 0.5 + 0.5 * _m.sin(phase * _m.pi * 2)
            r     = int(5 + pulse * 3)
            tint  = int(140 + pulse * 80)
            col   = (tint, tint, tint + 15, opacite)

            x = w - 70 + i * 20
            y = h - 35
            # Surface SRCALPHA pour gérer l'opacité du cercle
            tmp = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(tmp, col, (r + 1, r + 1), r)
            self.screen.blit(tmp, (x - r, y - r))

    def _frame_menu(self, events):
        """Un frame dans l'état MENU."""
        self.menu_titre.update(self._dt)
        self._gerer_menu(events)
        self.screen.fill((0, 0, 0))
        self.menu_titre.draw(self.screen)

        # Overlay de sélection de slot (ouvert par "Continuer").
        self.save_menu.update(self._dt)
        self.save_menu.draw(self.screen)

        # Fondu menu → jeu (quand on a cliqué "Nouvelle partie" par ex.)
        self._avancer_fondu_menu()

        # Voile noir par-dessus le menu si alpha > 0.
        if self._menu_fondu_alpha > 0:
            self._dessiner_voile_noir(self._menu_fondu_alpha)

    def _frame_jeu(self, events):
        """Un frame dans l'état GAME."""
        self._update_jeu(events, self._dt)
        self._dessiner_monde()

        # Fondu après transition depuis le menu : 2 phases possibles.
        # Avant le fix, on n'avançait que si état == "in" → la phase
        # "loading" tournait en boucle infinie (timer jamais décrémenté).
        if self._menu_fondu_etat in ("loading", "in"):
            self._avancer_fondu_menu()
            if self._menu_fondu_alpha > 0:
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
        # Pas de menu pause si on est venu d'un SAVE POINT (l'overlay
        # SaveMenu prend toute la place — sinon le pause apparaît
        # brièvement entre le clic du slot et le retour au jeu).
        if not getattr(self, "_save_point_actif", False):
            self.menu_pause.draw(self.screen)
        # Écran Paramètres par-dessus la pause si ouvert.
        self.parametres.draw(self.screen)
        # Overlay de sauvegarde / chargement par-dessus tout.
        self.save_menu.update(self._dt)
        self.save_menu.draw(self.screen)
        # Toast "Sauvegardé" : affiché même en pause (court moment où
        # le save_menu se ferme et l'état n'a pas encore basculé).
        self._dessiner_save_toast()

    def _frame_game_over(self, events):
        """Un frame dans l'état GAME_OVER : fondu progressif vers le noir
        puis affichage du menu de mort.

        Le fondu (~1 s) évite la transition brutale "jeu → écran noir" qu'on
        avait avant. L'alpha grimpe de 0 à 255 par incréments de 255 * dt.
        """
        self._gerer_fin(events)
        self._dessiner_monde()

        # Avance le fondu : 1 seconde pour passer de 0 à 255.
        VITESSE = 255.0
        self._gameover_fade_alpha = min(
            255.0,
            getattr(self, "_gameover_fade_alpha", 0.0) + VITESSE * self._dt
        )
        self._dessiner_voile_noir(self._gameover_fade_alpha)

        # ── Cinématique de mort scriptée ?
        # Si une cinématique est active pendant le GAME_OVER, on la fait
        # avancer (dialogue qui défile) et on l'affiche par-dessus le voile.
        # Le revive_player en fin de cinématique remettra dead=False et
        # rebasculera l'état en GAME via _verifier_revive_post_cutscene.
        if self.cutscene is not None:
            try:
                # IMPORTANT : on doit aussi avancer la boîte de dialogue
                # pendant l'état GAME_OVER, sinon le texte n'apparaît pas
                # lettre par lettre et le bip ne joue pas (l'anim dépend
                # de dialogue.update(dt) qui n'est appelé que dans
                # _update_jeu — branche non exécutée en GAME_OVER).
                self.dialogue.update(self._dt)
                from systems.cutscene import CutsceneContext
                self.cutscene.update(self._dt, CutsceneContext(self))
                if self.cutscene.is_done():
                    self.cutscene = None
                    # Si revive_player a été appelée, joueur.dead est False.
                    if not self.joueur.dead:
                        self._gameover_fade_alpha = 0.0
                        self.etats.switch(GAME)
                        return
            except Exception as e:
                print(f"[Mort scriptée] update : {e}")
            # Boîte de dialogue par-dessus le voile noir.
            try:
                self.dialogue.draw(self.screen)
            except Exception:
                pass
            return

        # Le menu de mort n'apparaît que quand le voile est complètement
        # opaque (sinon on le voit s'estomper en transparence sur le jeu,
        # peu lisible). Apparition nette une fois le noir total atteint.
        if self._gameover_fade_alpha >= 255:
            self.menu_fin.draw(self.screen)

    def _dessiner_voile_noir(self, alpha):
        """Dessine un rectangle noir semi-transparent sur tout l'écran.

        CACHE de surface (cf. _appliquer_luminosite) : la surface est créée
        une seule fois pour la taille d'écran, puis on ne fait que set_alpha
        à chaque frame (très rapide vs alloc + fill complets).
        """
        w, h = self.screen.get_size()
        if (getattr(self, "_voile_noir", None) is None
                or self._voile_noir.get_size() != (w, h)):
            self._voile_noir = pygame.Surface((w, h), pygame.SRCALPHA)
            self._voile_noir.fill((0, 0, 0, 255))
        self._voile_noir.set_alpha(int(min(255, max(0, alpha))))
        self.screen.blit(self._voile_noir, (0, 0))
