# ─────────────────────────────────────────────────────────────────────────────
#  RenderMixin — Dessin du monde et des interfaces
# ─────────────────────────────────────────────────────────────────────────────
#
#  Ce mixin regroupe tout le code de rendu visuel de la classe Game.
#
#  ORDRE DES CALQUES (du plus profond au plus haut) :
#
#     1.  Fond uni (couleur de la map)
#     2.  Murs de bordure + murs custom
#     3.  Trous (peints couleur du fond pour "effacer" le sol)
#     4.  Plateformes
#     5.  Décors
#     6.  Ennemis, PNJ
#     7a. Lucioles "derrière" (z < 0) — masquées par le joueur
#     7b. Joueur
#     8.  Lucioles "devant" (z >= 0)  — recouvrent le joueur
#     9.  Particules
#    10.  Portails (debug)
#    11.  Overlays éditeur
#    12.  Éclairage (voile sombre + halos)
#    13.  Outils éditeur (aperçu, HUD)
#    14.  FPS + nom de la carte
#    15.  Indicateur H/E
#    16.  Overlay PV bas (vignette rouge)
#    17.  HUD principal (cœurs + peur)
#    18.  Gestionnaire histoire
#    19.  Inventaire
#    20.  Dialogue
#    21.  Aide F1
#    22.  Fondu enchaîné
#
#  Méthodes exposées :
#   _dessiner_monde              → point d'entrée principal appelé chaque frame
#   _dessiner_hint_skip_cinematique → hint "Echap" pendant une cine
#   _dessiner_save_toast         → toast "Sauvegardé" + spinner
#   _dessiner_fps_et_carte       → compteur FPS + nom de la carte
#   _dessiner_indicateur_mode    → grand H (histoire) ou E (éditeur)
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame

import settings
from utils import draw_mouse_coords


class RenderMixin:
    """Rendu visuel du monde et des éléments d'interface."""

    # ─────────────────────────────────────────────────────────────────────────
    # RENDU PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────

    def _dessiner_monde(self):
        """Dessine tous les calques du monde puis les interfaces.

        Gère aussi le zoom caméra : le monde est rendu sur un buffer réduit
        puis mis à l'échelle, tandis que le HUD reste à résolution native."""
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
        # parfaitement net.
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
                # puisse les retrouver.
                if (self.editeur.active and pnj.sprite_name
                        and pnj.sprite_name.startswith("objet_parlant_")):
                    pygame.draw.rect(self.screen, (180, 100, 220),
                                     self.camera.apply(pnj.rect), 1)

        # 7a. Lucioles "derrière" (z < 0) : dessinées AVANT le joueur,
        #     donc le joueur les masque si elles passent pile derrière lui.
        self.compagnons.draw_derriere(self.screen, self.camera, self.joueur)

        # 7b. Joueur.
        self.joueur.draw(self.screen, self.camera, self.editeur.show_hitboxes)
        self.joueur.draw_slash(self.screen, self.camera)

        # 8. Lucioles "devant" (z >= 0) : dessinées APRÈS le joueur.
        self.compagnons.draw_devant(self.screen, self.camera, self.joueur)

        # 9. Particules.
        self.particles.draw(self.screen, self.camera)

        # 10. Portails (visibles seulement avec hitbox ou éditeur actif).
        police = self.editeur._get_font()

        if self.editeur.show_hitboxes or self.editeur.active:
            for portail in self.editeur.portals:
                portail.draw(self.screen, self.camera, police)

        # Affiche [Z] quand le joueur s'approche d'un portail
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

        # 10b. Zones-déclencheurs (rectangles colorés) — éditeur uniquement.
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
            # Barre de vie BOSS (en bas de l'écran).
            self._dessiner_boss_hp_bar()
            # Overlay "fear text" : dessiné par-dessus le HUD.
            self.fear_overlay.draw(self.screen)
            # Croix directionnelle de consommables rapides (bas-droite).
            self.quick_use.draw(self.screen)
            # Toast "Sauvegardé" + spinner après une save.
            self._dessiner_save_toast()
            # Notifications éphémères (compétence débloquée, items reçus…)
            self._dessiner_notifications()

        # Panneau debug story flags (F5 en mode éditeur).
        self._dessiner_story_flags_panel()

        # 18-21. Gestionnaire histoire, inventaire, dialogue, aide.
        self.gestionnaire_histoire.draw(self.screen)

        if self.inventory.cassette_a_jouer:
            from ui.items_effects import play_cassette
            visuel, sonore = self.inventory.cassette_a_jouer
            self.inventory.cassette_a_jouer = None
            play_cassette(visuel, sonore, self.screen)

        self.update_bonus()

        self.inventory.draw(self.screen, 6, 5)
        self.dialogue.draw(self.screen)
        self.boutique.draw(self.screen)
        self.aide.draw(self.screen)

        # 22. Hint "Echap pour passer" pendant une cinématique.
        if self.cutscene is not None:
            self._dessiner_hint_skip_cinematique()

        # 23. Journal des dialogues (overlay par-dessus tout).
        if self.journal_dialogues.actif:
            self.journal_dialogues.update(self._dt)
            self.journal_dialogues.draw(self.screen)

        # 24. Fondu enchaîné (par-dessus absolument tout).
        self._dessiner_fondu()

    # ─────────────────────────────────────────────────────────────────────────
    # ÉLÉMENTS HUD SECONDAIRES
    # ─────────────────────────────────────────────────────────────────────────

    def _dessiner_hint_skip_cinematique(self):
        """Petit hint discret 'Echap = passer' pendant une cinématique.

        Affiché en haut à droite, avec un fond semi-transparent."""
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
        plus rien ne s'affiche."""
        if self._save_toast_timer <= 0:
            return
        self._save_toast_timer -= self._dt
        # Alpha : pleine opacité au début, fade-out sur la dernière demi-seconde.
        ratio = max(0.0, min(1.0, self._save_toast_timer / 0.5))
        alpha = int(255 * (1.0 if self._save_toast_timer > 0.5 else ratio))

        w, h = self.screen.get_size()
        font = pygame.font.SysFont("Consolas", 14, bold=True)
        txt = font.render("Sauvegardé", True, (255, 215, 70))
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
        fps_txt  = f"{self.clock.get_fps():.0f} FPS"
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
