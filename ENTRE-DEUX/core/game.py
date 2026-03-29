# ─────────────────────────────────────────
#  ENTRE-DEUX — Boucle principale du jeu
# ─────────────────────────────────────────

import pygame
import settings
from world.editor import Editor
from core.event_handler import x_y_man, man_on
from settings import *
from core.camera import Camera
from core.state_manager import StateManager, MENU, GAME, PAUSE, GAME_OVER
from entities.player import Player
from entities.enemy import Enemy
from entities.npc import PNJ
from world.tilemap import Platform, Wall
from systems.lighting import LightingSystem
from systems.spatial_grid import SpatialGrid
from systems.save_system import sauvegarder, charger, lire_config, ecrire_config
from ui.menu import Menu
from ui.dialogue_box import BoiteDialogue
from utils import draw_mouse_coords
from world.collision import (verifier_attaques,
                             appliquer_plateformes,
                             verifier_contact_ennemi)
from ui.inventory import Inventory
from ui.gestionnaire_histoire import GestionnaireHistoire
from audio import music_manager, sound_manager

if not hasattr(settings, 'CEILING_Y'):
    settings.CEILING_Y = 0


class Game:

    def __init__(self):
        pygame.init()
        pygame.mixer.init() # on force l'allumage du moteur de son
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption(TITLE)
        self.running  = True
        self.clock    = pygame.time.Clock()
        self.fps_font = pygame.font.SysFont("Consolas", 16)
        self._dt      = 0

        # "histoire" → jeu normal avec histoire, éditeur désactivé
        # "editeur"  → accès à l'éditeur de carte (E pour basculer)
        self.mode = "histoire"

        self.etats   = StateManager()
        self.dialogue = BoiteDialogue()
        self.gestionnaire_histoire = GestionnaireHistoire()

        # Overlays de sélection actifs (None = inactif)
        self._menu_choix_carte  = None   # menu de sélection de carte avant d'entrer en éditeur
        self._font_indicateur   = pygame.font.SysFont("Consolas", 48, bold=True)

        # __ Sons ________________________________
        music_manager.jouer("ENTRE-DEUX/assets/music/fond.mp3", volume=0.4) # Musique de fond dès le lancement du jeu

        sound_manager.charger("attaque", "ENTRE-DEUX/assets/sounds/attaque.mp3")
        sound_manager.charger("pas", "ENTRE-DEUX/assets/sounds/pas.mp3")
        sound_manager.charger("mort", "ENTRE-DEUX/assets/sounds/mort.mp3")
        sound_manager.charger("degat", "ENTRE-DEUX/assets/sounds/degat.mp3")

        # ── Objets du jeu ──────────────────────────────────────────────────
        self.inventory = Inventory()
        self.inventory.add_pomme()

        self.joueur    = Player((100, 400))
        self.camera    = Camera(SCENE_WIDTH, SCENE_HEIGHT)
        self.ennemis   = [Enemy(500, 530 - 60)]
        self.platforms = [
            Platform(200, 500, 100, 20, BLANC),
            Platform(300, 400, 100, 20, GRIS),
            Platform(400, 300, 100, 20, BLEU),
        ]

        # PNJ de la scène de départ — Nimbus, le premier personnage de l'histoire
        self.pnjs = [
            PNJ(350, 460, "Nimbus", [
                [
                    ("...", "Nimbus"),
                    ("Tu es tombé de bien haut.", "Nimbus"),
                ],
                [
                    ("Je t'attendais.", "Nimbus"),
                    ("Tout le monde a une porte qu'il refuse d'ouvrir.", "Nimbus"),
                ],
                [
                    ("Continue.", "Nimbus"),
                ],
            ], couleur=(190, 175, 240)),
        ]

        # Grille spatiale : n'interroge que les plateformes proches du joueur
        self.grille_plateformes = SpatialGrid(cell_size=128)
        self._reconstruire_grille()

        self.lumieres = LightingSystem()
        self.lumieres.add_light(300, 480, radius=150, type="torch", flicker=True)
        self.lumieres.add_light(600, 380, radius=200, type="torch", flicker=True)

        self.editeur = Editor(self.platforms, self.ennemis,
                              self.camera, self.lumieres, self.joueur)
        self.editeur.build_border_segments()

        self.carte_actuelle = ""

        # Fondu enchaîné entre deux cartes
        self.vitesse_fondu       = 0.4
        self._fondu_alpha        = 0
        self._fondu_etat         = "none"
        self._fondu_surface      = None
        self._portail_en_attente = None

        # Cache des murs (recalculé uniquement quand l'éditeur les modifie)
        self._murs_cache        = None
        self._murs_cache_perime = True

        # ── Menus ──────────────────────────────────────────────────────────
        # "Continuer" n'apparaît que si une sauvegarde existe
        save = charger()
        options_titre = (["Continuer"] if save else []) + [
            "Nouvelle partie",
            "Mode éditeur",
            "Quitter",
        ]

        # style="titre"   → fond sombre + particules flottantes
        # style="panneau" → cadre transparent sur le jeu en arrière-plan
        self.menu_titre = Menu(options_titre, title=TITLE, style="titre")
        self.menu_pause = Menu(
            ["Reprendre", "Sauvegarder", "Menu principal", "Quitter"],
            title="PAUSE",
            style="panneau",
        )
        self.menu_fin   = Menu(
            ["Recommencer", "Menu principal"],
            title="FIN",
            style="panneau",
        )

    # ── Cache des murs ────────────────────────────────────────────────────

    def _reconstruire_grille(self):
        self.grille_plateformes.rebuild(self.platforms)

    def _murs_modifies(self):
        self._murs_cache_perime = True

    def _murs_actifs(self):
        if self._murs_cache_perime:
            self._murs_cache = self.editeur.all_segments() + self.editeur.custom_walls
            self._murs_cache_perime = False
        return self._murs_cache

    # ── Lumières portées par les ennemis ──────────────────────────────────

    def _sync_lumieres_ennemis(self):
        self.lumieres.lights = [l for l in self.lumieres.lights
                                if not l.get("_enemy_light")]

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
                "_enemy_light": True,
            })

    # ── Collisions ennemis avec le décor ──────────────────────────────────

    def _collisions_ennemis(self, ennemi, murs):
        for mur in murs:
            if getattr(mur, 'player_only', False):
                continue

            rect_mur = mur.rect if hasattr(mur, 'rect') else mur
            if not ennemi.rect.colliderect(rect_mur):
                continue

            x_avant   = ennemi.rect.x
            bas_avant = ennemi.rect.bottom
            vy_avant  = ennemi.vy

            mur.verifier_collision(ennemi)

            if ennemi.vy == 0 and vy_avant > 0 and ennemi.rect.bottom <= bas_avant:
                ennemi.on_ground = True

            if ennemi.rect.x != x_avant and abs(vy_avant) < 80:
                ennemi.on_wall_collision_horizontal(rect_mur.height)

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

    # ── Portails & fondu enchaîné ─────────────────────────────────────────

    def _verifier_portails(self):
        if self._fondu_etat != "none":
            return

        for portail in self.editeur.portals:
            if self.joueur.rect.colliderect(portail.rect):
                self._portail_en_attente = (
                    portail.target_map,
                    portail.target_x,
                    portail.target_y,
                )
                self._fondu_etat  = "out"
                self._fondu_alpha = 0
                return

    def _update_fondu(self, dt):
        if self._fondu_etat == "none":
            return

        vitesse = 255 / max(0.05, self.vitesse_fondu)

        if self._fondu_etat == "out":
            self._fondu_alpha += vitesse * dt

            if self._fondu_alpha >= 255:
                self._fondu_alpha = 255

                if self._portail_en_attente:
                    carte, tx, ty = self._portail_en_attente
                    if self.editeur.load_map_for_portal(carte):
                        self.carte_actuelle = carte
                        self._reconstruire_grille()
                        self._murs_modifies()
                        if tx >= 0 and ty >= 0:
                            self.joueur.rect.x = tx
                            self.joueur.rect.y = ty
                        else:
                            self.joueur.respawn()
                        self.joueur.vy = 0
                        self.joueur.knockback_vx = 0
                    self._portail_en_attente = None

                self._fondu_etat = "in"

        elif self._fondu_etat == "in":
            self._fondu_alpha -= vitesse * dt

            if self._fondu_alpha <= 0:
                self._fondu_alpha = 0
                self._fondu_etat  = "none"

    def _dessiner_fondu(self):
        if self._fondu_alpha <= 0:
            return

        w, h = self.screen.get_size()

        if self._fondu_surface is None or self._fondu_surface.get_size() != (w, h):
            self._fondu_surface = pygame.Surface((w, h), pygame.SRCALPHA)

        self._fondu_surface.fill((0, 0, 0, int(self._fondu_alpha)))
        self.screen.blit(self._fondu_surface, (0, 0))

    # ── Gestion de partie ─────────────────────────────────────────────────

    def _nouvelle_partie(self):
        # Charge la carte de départ selon le mode
        if self.mode == "histoire":
            config = lire_config()
            debut  = config.get("carte_debut", "")
            if debut and self.editeur.load_map_for_portal(debut):
                self.carte_actuelle = debut
                self._reconstruire_grille()
                self._murs_modifies()
            else:
                # Aucune carte de départ définie → carte vide
                self.editeur._new_map()
                self.carte_actuelle = ""
                self._reconstruire_grille()
                self._murs_modifies()
        else:
            # Mode éditeur → carte vide prête à éditer
            self.editeur._new_map()
            self.carte_actuelle = ""
            self._reconstruire_grille()
            self._murs_modifies()

        self.joueur.rect.x       = self.editeur.spawn_x
        self.joueur.rect.y       = self.editeur.spawn_y
        self.joueur.hp           = self.joueur.max_hp
        self.joueur.dead         = False
        self.joueur.vy           = 0
        self.joueur.vx           = 0
        self.joueur.knockback_vx = 0
        for ennemi in self.ennemis:
            ennemi.alive = True
        self.etats.switch(GAME)

    def _charger_partie(self):
        donnees = charger()
        if not donnees:
            self._nouvelle_partie()
            return

        self.mode         = donnees.get("mode", "histoire")
        self.joueur.hp    = donnees.get("hp", self.joueur.max_hp)
        self.joueur.dead  = False
        self.joueur.vy    = 0

        carte = donnees.get("map", "")
        if carte:
            self.editeur.load_map_for_portal(carte)
            self.carte_actuelle = carte
            self._reconstruire_grille()
            self._murs_modifies()

        self.joueur.rect.x = donnees.get("x", self.joueur.spawn_x)
        self.joueur.rect.y = donnees.get("y", self.joueur.spawn_y)
        self.etats.switch(GAME)

    def _sauvegarder(self):
        sauvegarder({
            "mode": self.mode,
            "hp":   self.joueur.hp,
            "map":  self.carte_actuelle,
            "x":    self.joueur.rect.x,
            "y":    self.joueur.rect.y,
        })

    # ── Interaction PNJ ───────────────────────────────────────────────────

    def _tenter_interaction(self):
        """
        Cherche un PNJ proche et démarre son dialogue.
        Appelé quand le joueur appuie sur E en mode histoire.
        """
        for pnj in self.pnjs:
            if pnj.peut_interagir(self.joueur.rect):
                lignes = pnj.conversation_actuelle()
                if lignes:
                    self.dialogue.demarrer(lignes)
                return

    # ── Logique par état ──────────────────────────────────────────────────

    def _gerer_menu(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN:
                choix = self.menu_titre.handle_key(event.key)
                if choix == "Continuer":
                    self._charger_partie()
                elif choix == "Nouvelle partie":
                    self.mode = "histoire"
                    self._nouvelle_partie()
                elif choix == "Mode éditeur":
                    self.mode = "editeur"
                    # Ouvrir le sélecteur de carte avant d'entrer dans l'éditeur
                    maps = self.editeur._list_maps()
                    opts = ["Nouvelle carte"] + maps
                    self._menu_choix_carte = Menu(opts, title="Ouvrir une carte", style="titre")
                elif choix == "Quitter":
                    self.running = False

    def _gerer_pause(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.etats.switch(GAME)
                    return
                choix = self.menu_pause.handle_key(event.key)
                if choix == "Reprendre":
                    self.etats.switch(GAME)
                elif choix == "Sauvegarder":
                    self._sauvegarder()
                elif choix == "Menu principal":
                    self.etats.switch(MENU)
                elif choix == "Quitter":
                    self.running = False

    def _gerer_fin(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN:
                choix = self.menu_fin.handle_key(event.key)
                if choix == "Recommencer":
                    self._nouvelle_partie()
                elif choix == "Menu principal":
                    self.etats.switch(MENU)

    def _update_jeu(self, events, dt):
        # ── Gestionnaire histoire (reçoit les événements en priorité) ──────
        if self.gestionnaire_histoire.actif:
            for event in events:
                self.gestionnaire_histoire.handle_event(event)
            return

        # ── Événements ────────────────────────────────────────────────────
        for event in events:
            if event.type == pygame.KEYDOWN:

                # Dialogue actif → Espace/Entrée avance le texte
                if self.dialogue.actif and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.dialogue.avancer()
                    continue

                if event.key == pygame.K_ESCAPE:
                    if self.editeur.active and self.editeur._text_mode:
                        self.editeur.handle_key(event.key)
                    elif not self.dialogue.actif:
                        self.etats.switch(PAUSE)
                        self.menu_pause.selection = 0
                    continue

                if event.key == pygame.K_TAB:
                    self.inventory.changer_etat_fenetre()

                if event.key == pygame.K_e:
                    if self.mode == "editeur" and not (
                            self.editeur.active and self.editeur._text_mode):
                        # En mode éditeur, E bascule l'éditeur
                        self.editeur.toggle()
                    elif self.mode == "histoire" and not self.dialogue.actif:
                        # En mode histoire, E interagit avec les PNJ
                        self._tenter_interaction()

                elif event.key == pygame.K_h and not self.editeur.active:
                    if self.mode == "editeur":
                        # H en mode éditeur → ouvre le gestionnaire d'histoire
                        maps_dispo = self.editeur._list_maps()
                        self.gestionnaire_histoire.ouvrir(maps_dispo)
                    else:
                        # H en mode histoire → bascule vers éditeur
                        self.mode = "editeur"
                        self.editeur._show_msg("Mode Éditeur — [E] ouvrir éditeur  [H] gérer histoire")

                elif self.editeur.active:
                    resultat = self.editeur.handle_key(event.key)
                    if resultat in ("done", "undo", "structure"):
                        self._reconstruire_grille()
                        self._murs_modifies()
                    elif resultat and resultat.startswith("set_start:"):
                        nom = resultat.split(":", 1)[1]
                        config = lire_config()
                        config["carte_debut"] = nom
                        ecrire_config(config)
                        self.editeur._show_msg(f"Carte de départ définie : {nom}")

            # Souris dans l'éditeur
            if self.editeur.active and self.editeur._text_mode is None:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        nb_avant = len(self.platforms)
                        self.editeur.handle_click(event.pos)
                        if len(self.platforms) != nb_avant:
                            self._reconstruire_grille()
                        self._murs_modifies()
                    elif event.button == 3:
                        nb_avant = len(self.platforms)
                        self.editeur.handle_right_click(event.pos)
                        if len(self.platforms) != nb_avant:
                            self._reconstruire_grille()
                        self._murs_modifies()
                if event.type == pygame.MOUSEWHEEL:
                    self.editeur.handle_scroll(event.y)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
                if self.editeur.active and self.editeur.mode == 9:
                    # Clic milieu en mode décor → bascule collision du décor sous le curseur
                    wx = int(event.pos[0] + self.camera.offset_x)
                    wy = int(event.pos[1] + self.camera.offset_y)
                    self.editeur.toggle_decor_collision_at(wx, wy)
                else:
                    print(f"Monde x:{settings.wx} y:{settings.wy}")

        # ── Physique ──────────────────────────────────────────────────────
        keys  = pygame.key.get_pressed()
        man_on()
        x_y_man()

        trous = self.editeur.holes
        murs  = self._murs_actifs()

        # Bloque le mouvement pendant un fondu ou un dialogue
        mouvement_bloque = (self._fondu_etat != "none" or self.dialogue.actif)
        if not mouvement_bloque:
            self.joueur.mouvement(dt, keys, holes=trous)

        self.camera.update(self.joueur.rect)

        for ennemi in self.ennemis:
            ennemi.update(dt, self.platforms, murs, self.joueur.rect, holes=trous)

        # ── Collisions ────────────────────────────────────────────────────
        verifier_attaques(self.joueur, self.ennemis)
        appliquer_plateformes(self.joueur, self.grille_plateformes)

        if not self.editeur.active:
            verifier_contact_ennemi(self.joueur, self.ennemis)

        for mur in murs:
            mur.verifier_collision(self.joueur)

        # Décors avec collision — poussent le joueur comme une plateforme
        for decor in self.editeur.decors:
            if decor.collision:
                decor.verifier_collision(self.joueur)

        for ennemi in self.ennemis:
            if ennemi.alive:
                self._collisions_ennemis(ennemi, murs)

        # ── Systèmes ──────────────────────────────────────────────────────
        self.lumieres.update(dt)
        self._sync_lumieres_ennemis()
        self._verifier_portails()
        self._update_fondu(dt)
        self.dialogue.update(dt)

        if self.joueur.dead:
            self.etats.switch(GAME_OVER)
            self.menu_fin.selection = 0

        self.inventory.drag_drop(events)

    # ── Rendu ─────────────────────────────────────────────────────────────

    def _dessiner_monde(self):
        couleur_fond = tuple(self.editeur.bg_color)
        self.screen.fill(couleur_fond)

        # Murs de bordure et murs custom
        for mur in self.editeur.all_segments():
            if self.camera.is_visible(mur.rect):
                mur.draw(self.screen, self.camera)

        for mur in self.editeur.custom_walls:
            if self.camera.is_visible(mur.rect):
                mur.draw(self.screen, self.camera)

        # Les trous sont peints de la couleur du fond (ils "effacent" le sol)
        for trou in self.editeur.holes:
            if self.camera.is_visible(trou):
                rect_ecran = self.camera.apply(trou)
                pygame.draw.rect(self.screen, couleur_fond, rect_ecran)
                if self.editeur.active and self.editeur.show_hitboxes:
                    pygame.draw.rect(self.screen, (255, 80, 80), rect_ecran, 2)

        for plateforme in self.platforms:
            if self.camera.is_visible(plateforme.rect):
                plateforme.draw(self.screen, self.camera)

        # Décors placés dans l'éditeur (s'affichent devant les plateformes)
        for decor in self.editeur.decors:
            if self.camera.is_visible(decor.rect):
                decor.draw(self.screen, self.camera)
                if self.editeur.active and self.editeur.show_hitboxes and decor.collision:
                    pygame.draw.rect(self.screen, (255, 100, 0),
                                     self.camera.apply(decor.rect), 1)

        for ennemi in self.ennemis:
            if self.camera.is_visible(ennemi.rect):
                ennemi.draw(self.screen, self.camera, self.editeur.show_hitboxes)

        # PNJ — en mode histoire uniquement (pas besoin de les voir dans l'éditeur seul)
        for pnj in self.pnjs:
            if self.camera.is_visible(pnj.rect):
                pnj.draw(self.screen, self.camera, self.joueur.rect)

        self.joueur.draw(self.screen, self.camera, self.editeur.show_hitboxes)

        # Portails (visibles seulement avec hitboxes ou éditeur actif)
        if self.editeur.show_hitboxes or self.editeur.active:
            police = self.editeur._get_font()
            for portail in self.editeur.portals:
                portail.draw(self.screen, self.camera, police)

        if self.editeur.active:
            self.editeur.draw_overlays(self.screen)

        # Éclairage dynamique (appliqué par-dessus tous les sprites)
        self.lumieres.render(self.screen, self.camera, self.joueur.rect)

        # Outils éditeur
        if self.editeur.active:
            draw_mouse_coords(self.screen, self.camera, y_start=110)
            self.editeur.draw_preview(self.screen, pygame.mouse.get_pos())
            self.editeur.draw_hud(self.screen, self._dt)

        # HUD : FPS et nom de la carte
        fps_surf = self.fps_font.render(f"{self.clock.get_fps():.0f} FPS", True, (0, 255, 0))
        self.screen.blit(fps_surf, (
            self.screen.get_width()  - fps_surf.get_width() - 10,
            self.screen.get_height() - 25,
        ))

        if self.carte_actuelle:
            nom_surf = self.fps_font.render(self.carte_actuelle, True, (180, 180, 180))
            self.screen.blit(nom_surf, (10, self.screen.get_height() - 25))

        # Indicateur de mode — grand H ou E, discret, coin haut-gauche
        lettre  = "H" if self.mode == "histoire" else "E"
        couleur = (80, 180, 100, 180) if self.mode == "histoire" else (100, 140, 255, 180)
        ind = self._font_indicateur.render(lettre, True, couleur[:3])
        ind.set_alpha(couleur[3])
        self.screen.blit(ind, (8, 8))

        # Gestionnaire histoire (s'affiche par-dessus tout sauf le fondu)
        self.gestionnaire_histoire.draw(self.screen)

        self.inventory.draw(self.screen, 6, 5)

        # Dialogue (au-dessus de tout sauf le fondu)
        self.dialogue.draw(self.screen)

        self._dessiner_fondu()

    # ── Boucle principale ─────────────────────────────────────────────────

    def run(self):
        while self.running:
            self._dt = self.clock.tick(FPS) / 1000
            events   = pygame.event.get()

            for event in events:
                if event.type == pygame.QUIT:
                    self.running = False

            # ── Gestionnaire d'histoire (overlay prioritaire) ──────────────
            if self.gestionnaire_histoire.actif:
                for event in events:
                    self.gestionnaire_histoire.handle_event(event)
                self._dessiner_monde()
                pygame.display.flip()
                continue

            # ── Sélecteur de carte pour l'éditeur ─────────────────────────
            if self._menu_choix_carte is not None:
                self._menu_choix_carte.update(self._dt)
                for event in events:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self._menu_choix_carte = None
                            self.etats.switch(MENU)
                            break
                        choix = self._menu_choix_carte.handle_key(event.key)
                        if choix == "Nouvelle carte":
                            self.editeur._new_map()
                            self.carte_actuelle = ""
                            self._reconstruire_grille()
                            self._murs_modifies()
                            self._menu_choix_carte = None
                            self.etats.switch(GAME)
                        elif choix is not None:
                            if self.editeur.load_map_for_portal(choix):
                                self.carte_actuelle = choix
                                self.editeur._nom_carte = choix
                                self._reconstruire_grille()
                                self._murs_modifies()
                            self._menu_choix_carte = None
                            self.etats.switch(GAME)
                if self._menu_choix_carte is None:
                    pygame.display.flip()
                    continue
                self.screen.fill((0, 0, 0))
                self._menu_choix_carte.draw(self.screen)
                pygame.display.flip()
                continue

            if self.etats.is_menu:
                # Le menu titre anime ses particules avant d'être dessiné
                self.menu_titre.update(self._dt)
                self._gerer_menu(events)
                self.screen.fill((0, 0, 0))
                self.menu_titre.draw(self.screen)

            elif self.etats.is_game:
                self._update_jeu(events, self._dt)
                self._dessiner_monde()

            elif self.etats.is_paused:
                # Le jeu reste visible en arrière-plan — le panneau se superpose
                self._gerer_pause(events)
                self._dessiner_monde()
                self.menu_pause.draw(self.screen)

            elif self.etats.is_game_over:
                self._gerer_fin(events)
                self._dessiner_monde()
                self.menu_fin.draw(self.screen)

            pygame.display.flip()
