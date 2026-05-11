# ─────────────────────────────────────────────────────────────────────────────
#  InputMixin — Gestion des entrées clavier et souris
# ─────────────────────────────────────────────────────────────────────────────
#
#  Ce mixin regroupe toutes les méthodes de `Game` liées à la lecture des
#  entrées utilisateur :
#
#   _gerer_touche          → dispatch d'une touche vers l'action correspondante
#   _gerer_touche_e        → logique de la touche E (interaction / éditeur)
#   _toggle_editeur        → [F4] : bascule l'éditeur en mode éditeur
#   _traiter_resultat_editeur → interprète le retour de editeur.handle_key()
#   _gerer_souris_editeur  → clics gauche/droit + molette dans l'éditeur
#   _gerer_clic_molette    → clic molette (pan caméra ou toggle décor)
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame

from ui.inventory import ITEMS
from systems.save_system import lire_config, ecrire_config


class InputMixin:
    """Gestion des entrées clavier et souris pour la classe Game."""

    # ─────────────────────────────────────────────────────────────────────────
    # CLAVIER
    # ─────────────────────────────────────────────────────────────────────────

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
        if self.boutique.actif:
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
            if key == pygame.K_ESCAPE:
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
                # Skip cinématique DÉSACTIVÉ : skip_all sautait toutes
                # les étapes restantes, ce qui faisait foirer les events
                # de fin (téléport, set_flag, give_item…) qui n'étaient
                # jamais déclenchés. Le joueur doit attendre la fin
                # normale. Échap ne fait plus rien pendant une cine.
                return
            elif not self.dialogue.actif:
                self.etats.switch(self.etats.PAUSE)
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
            # Sync carte_actuelle avec le nom de carte de l'éditeur.
            # Quand l'utilisateur charge une carte via [L], l'éditeur
            # met à jour son _nom_carte mais game.carte_actuelle reste
            # bloqué sur l'ancienne valeur → conséquence : le système de
            # téléport considérait être encore sur l'ancienne map et ne
            # rechargeait pas la nouvelle, ce qui faisait perdre les
            # named_spawns. On resynchronise systématiquement.
            nc = getattr(self.editeur, "_nom_carte", "")
            if nc and nc != self.carte_actuelle:
                self.carte_actuelle = nc
                # Nouvelle map → on applique sa musique (fondu).
                self._appliquer_musique_carte()
        elif resultat and resultat.startswith("set_start:"):
            # Résultat au format "set_start:nom_de_la_carte"
            nom = resultat.split(":", 1)[1]
            config = lire_config()
            config["carte_debut"] = nom
            ecrire_config(config)
            self.editeur._show_msg(f"Carte de départ définie : {nom}")

    # ─────────────────────────────────────────────────────────────────────────
    # SOURIS
    # ─────────────────────────────────────────────────────────────────────────

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
