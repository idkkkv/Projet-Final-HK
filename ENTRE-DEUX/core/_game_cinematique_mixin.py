# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Mixin Cinématique (events PNJ, déclenchement, etc.)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Mixin qui contient TOUTE la logique liée aux cinématiques :
#
#       _appliquer_event_pnj()                  → events de fin de dialogue
#                                                 PNJ (skill, luciole, coins,
#                                                 hp, item, flag, teleport,
#                                                 flag_increment).
#
#       _declencher_cinematique_mort()          → cherche un trigger on_death
#                                                 sur la position du joueur
#                                                 et lance la cine associée.
#
#       _charger_cine_flag_watchers()           → scan des cinématiques avec
#                                                 condition au démarrage et
#                                                 à chaque chgt de map.
#       _scanner_cines_avec_trigger()           → scan des maps pour trouver
#                                                 quelles cines sont liées à
#                                                 un trigger zone.
#
#       _programmer_verif_cine()                → programme une vérification
#       _avancer_verif_cine(dt)                 → fait avancer le timer
#       _verifier_cinematiques_conditionnelles → check + lance la cine si
#                                                 condition remplie
#
#       _lancer_cinematique_par_nom(nom)        → charge un JSON et le joue
#       _tester_cinematique(steps, ...)         → test depuis l'éditeur [T]
#       _reset_compteur_cinematique(nom)        → reset compteur de lectures
#       _skipper_cinematique()                  → annule la cine en cours
#                                                 (laissé pour les appels
#                                                 internes, plus exposé via
#                                                 Échap depuis la maj)
# ─────────────────────────────────────────────────────────────────────────────

import json
import os

import pygame

import settings


class CinematiqueMixin:
    """Toute la logique liée aux cinématiques scriptées (events PNJ,
    auto-déclenchement par flag, mort scriptée, etc.)."""

    # ─────────────────────────────────────────────────────────────────────
    #  Cinématique de MORT scriptée
    # ─────────────────────────────────────────────────────────────────────

    def _declencher_cinematique_mort(self):
        """Cherche une CutsceneTrigger en mode "on_death" qui couvre la
        position du joueur. Si trouvée et déclenchée, renvoie True. Sinon
        renvoie False → game.py basculera en GAME_OVER normal.

        Si plusieurs zones on_death se chevauchent (cas typique : une
        cine de secours sans condition + une cine alternative conditionnée
        par un flag), on essaie toutes les zones tant qu'aucune ne démarre.
        Permet à la cine alternative de se lancer une fois que la cine de
        secours est consommée (max_plays=1).
        """
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
                return True
            # Sinon, la zone n'a rien lancé : on passe à la suivante.
        return False

    # ─────────────────────────────────────────────────────────────────────
    #  Events de fin de dialogue PNJ
    # ─────────────────────────────────────────────────────────────────────

    def _appliquer_event_pnj(self, event):
        """Applique un événement déclenché en fin de conversation PNJ.

        Types supportés : skill, luciole, coins, hp, max_hp, item, flag,
        flag_increment, teleport.
        Cf. entities/npc.py PNJ.events pour la pose côté éditeur/JSON.
        """
        if not isinstance(event, dict):
            return
        etype = event.get("type")

        if etype == "skill":
            self._event_skill(event)
        elif etype == "luciole":
            self._event_luciole(event)
        elif etype == "coins":
            self._event_coins(event)
        elif etype == "hp":
            self._event_hp(event)
        elif etype == "max_hp":
            self._event_max_hp(event)
        elif etype == "item":
            self._event_item(event)
        elif etype == "flag":
            self._event_flag(event)
        elif etype == "teleport":
            self._event_teleport(event)
        elif etype == "flag_increment":
            self._event_flag_increment(event)
        else:
            print(f"[event PNJ] type inconnu : {etype!r}")

    # ─────────────────────────────────────────────────────────────────────
    #  Sous-handlers par type d'event PNJ (un par type pour rester lisible)
    # ─────────────────────────────────────────────────────────────────────

    def _event_skill(self, event):
        """Débloque une compétence (settings.skill_<value> = True)."""
        val  = event.get("value", "")
        attr = f"skill_{val}"
        if hasattr(settings, attr):
            setattr(settings, attr, True)
            self.notifier(f"Compétence débloquée : {val}")
        else:
            print(f"[event PNJ] skill inconnu : {val!r}")

    def _event_luciole(self, event):
        """Ajoute une luciole (compagnon)."""
        src = event.get("source") or f"pnj_{getattr(self._pnj_actif, 'nom', 'x')}"
        try:
            self.compagnons.gagner_luciole(joueur=self.joueur, source=src)
            self.notifier("+ 1 luciole")
        except Exception as exc:
            print(f"[event PNJ] luciole : {exc}")

    def _event_coins(self, event):
        """Ajoute (ou retire) des pièces (Échos)."""
        v = int(event.get("value", 0))
        self.joueur.coins = getattr(self.joueur, "coins", 0) + v
        if v != 0:
            self.notifier(f"+ {v} pièces" if v > 0 else f"{v} pièces")

    def _event_hp(self, event):
        """Soigne le joueur (cap = max_hp)."""
        v = int(event.get("value", 0))
        self.joueur.hp = min(self.joueur.max_hp, self.joueur.hp + v)
        if v > 0:
            self.notifier(f"+ {v} PV")

    def _event_max_hp(self, event):
        """Augmente le max de PV (et soigne plein)."""
        v = int(event.get("value", 0))
        self.joueur.max_hp += v
        self.joueur.hp = self.joueur.max_hp
        if v > 0:
            self.notifier(f"+ {v} PV max")

    def _event_item(self, event):
        """Ajoute un item dans l'inventaire."""
        val = event.get("value", "")
        if hasattr(self, "inventory") and val:
            try:
                n = int(event.get("count", 1))
                self.inventory.add_item(val, count=n)
                self.notifier(f"+ {n} {val}" if n > 1 else f"+ {val}")
            except Exception:
                pass

    def _event_flag(self, event):
        """Pose un story flag (booléen).

        Utilise flag_poser qui normalise vers {current, required}.
        Déclenche une vérif des cines conditionnelles (qui pourraient
        désormais avoir leur condition remplie).
        """
        key = event.get("key", "")
        val = bool(event.get("value", True))
        if not key:
            return
        if not hasattr(self, "story_flags"):
            self.story_flags = {}
        from systems.story_flags import flag_poser
        flag_poser(self.story_flags, key, val)
        self._programmer_verif_cine()

    def _event_flag_increment(self, event):
        """Incrémente un flag avec compteur (crée le flag si absent)."""
        key      = event.get("key", "")
        delta    = int(event.get("delta", 1))
        required = event.get("required", None)
        if not key:
            return
        if not hasattr(self, "story_flags"):
            self.story_flags = {}
        from systems.story_flags import flag_incrementer, flag_valeur
        flag_incrementer(self.story_flags, key,
                         delta=delta, required=required)
        cur, req = flag_valeur(self.story_flags, key)
        self.notifier(f"{key} : {cur}/{req}")
        # Vérif TOUJOURS (seuils intermédiaires possibles).
        self._programmer_verif_cine()

    def _event_teleport(self, event):
        """Téléporte le joueur vers une autre map ou un spawn nommé.

        Format identique à teleport_player de cutscene.py :
          cible "spawn"        → carte courante, spawn nommé
          cible "map spawn"    → autre carte, spawn nommé
          sinon (x, y)         → carte courante, coords explicites
        """
        cible = str(event.get("cible", "")).strip()
        nom_map = None
        nom_spawn = None
        if cible:
            if " " in cible:
                parts = cible.split(" ", 1)
                nom_map   = parts[0].strip()
                nom_spawn = parts[1].strip()
            else:
                nom_spawn = cible
        print(f"[TP] cible='{cible}' → map='{nom_map}' spawn='{nom_spawn}'")
        # Changement de carte si nécessaire
        if nom_map and nom_map != getattr(self, "carte_actuelle", ""):
            if hasattr(self.editeur, "load_map_for_portal"):
                if self.editeur.load_map_for_portal(nom_map):
                    self.carte_actuelle = nom_map
                    print(f"[TP] map changée → {nom_map}")
                    try:
                        self._reconstruire_grille()
                        self._murs_modifies()
                        self._sync_triggers()
                        self._appliquer_musique_carte()
                    except Exception as e:
                        print(f"[TP] reconstruction map : {e}")
                else:
                    print(f"[TP] échec load_map_for_portal('{nom_map}')")
        # Récupération du spawn (avec fallback disque si jamais éditeur
        # a perdu ses named_spawns)
        named = getattr(self.editeur, "named_spawns", {}) or {}
        if nom_spawn and nom_spawn not in named:
            target_map = nom_map or getattr(self, "carte_actuelle", "")
            if target_map:
                try:
                    from world.editor import MAPS_DIR
                    fp = os.path.join(MAPS_DIR, f"{target_map}.json")
                    with open(fp, encoding="utf-8") as f:
                        map_data = json.load(f)
                    named_disk = map_data.get("named_spawns", {}) or {}
                    if named_disk:
                        print(f"[TP] reload spawns de '{target_map}' depuis disque")
                        self.editeur.named_spawns = dict(named_disk)
                        named = self.editeur.named_spawns
                except Exception as e:
                    print(f"[TP] échec relecture {target_map}.json : {e}")
        print(f"[TP] spawns disponibles : {list(named.keys())}")
        pos = None
        if nom_spawn and nom_spawn in named:
            pos = named[nom_spawn]
        if pos is not None:
            self.joueur.rect.x = int(pos[0])
            self.joueur.rect.y = int(pos[1])
            print(f"[TP] OK → ({pos[0]}, {pos[1]})")
        else:
            x = event.get("x")
            y = event.get("y")
            if x is not None and y is not None:
                self.joueur.rect.x = int(x)
                self.joueur.rect.y = int(y)
                print(f"[TP] fallback x/y → ({x}, {y})")
            elif nom_spawn:
                print(f"[TP] spawn '{nom_spawn}' INTROUVABLE — "
                      f"le spawn doit être posé sur la map cible "
                      f"(mode 15 'Spawn nommé') et la map sauvée.")
        # Reset vélocités + snap caméra
        self.joueur.vx           = 0
        self.joueur.vy           = 0
        self.joueur.knockback_vx = 0
        if hasattr(self.camera, "snap_to"):
            self.camera.snap_to(self.joueur.rect)

    # ─────────────────────────────────────────────────────────────────────
    #  Cinématiques conditionnelles (déclenchées par flags)
    # ─────────────────────────────────────────────────────────────────────

    def _charger_cine_flag_watchers(self):
        """Scanne cinematiques/ et met à jour la liste des cinématiques avec
        condition. Appelé au démarrage et à chaque chargement de map.

        On scanne aussi toutes les maps pour construire la liste des
        cinématiques référencées par un trigger zone n'importe où dans le
        jeu (utilisé par d'autres checks pour ne pas auto-fire à tort).
        """
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

        Le délai par défaut est le MAX des delays de tous les watchers
        (pour laisser à chaque cine le temps de jouer). Si une vérif est
        déjà programmée, on prend le délai le plus long pour ne pas en
        oublier.
        """
        if not self._cine_flag_watchers:
            return
        if delai is None:
            delai = max((w.get("delay", 1.0)
                         for w in self._cine_flag_watchers), default=1.0)
        self._cine_verif_pending = True
        self._cine_verif_delay = max(self._cine_verif_delay, float(delai))

    def _avancer_verif_cine(self, dt):
        """Décompte du timer + déclenchement à 0.

        Appelé chaque frame depuis _update_jeu. Si dialogue/cine en cours
        ou éditeur ouvert, on reporte la vérif.
        """
        if not self._cine_verif_pending:
            return
        self._cine_verif_delay -= dt
        if self._cine_verif_delay > 0:
            return
        # Timer expiré : on vérifie maintenant.
        self._cine_verif_pending = False
        self._cine_verif_delay   = 0.0
        if self.dialogue.actif or self.cutscene is not None:
            # On reprogramme pour plus tard
            self._cine_verif_pending = True
            self._cine_verif_delay   = 0.5
            return
        if self.editeur.active:
            return
        self._verifier_cinematiques_conditionnelles()

    def _verifier_cinematiques_conditionnelles(self):
        """Vérifie chaque watcher : si sa condition est vraie ET qu'il
        n'a pas déjà été déclenché (one_shot), on lance la cinématique.

        Comportement par défaut : toute cine avec une condition s'auto-
        déclenche dès que la condition devient vraie. Pour les cines qui
        doivent fire UNIQUEMENT via leur trigger zone, l'utilisateur
        désactive explicitement l'auto-fire via [F] dans l'éditeur
        (auto_fire: False dans le JSON).
        """
        from systems.story_flags import tester_condition

        for watcher in self._cine_flag_watchers:
            nom       = watcher.get("nom", "")
            condition = watcher.get("condition")
            one_shot  = watcher.get("one_shot", True)
            auto_fire = watcher.get("auto_fire", None)
            if not nom or not condition:
                continue
            if auto_fire is False:
                continue
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
        jusqu'au prochain rechargement de carte.
        """
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

    # ─────────────────────────────────────────────────────────────────────
    #  Skip / test depuis l'éditeur
    # ─────────────────────────────────────────────────────────────────────

    def _skipper_cinematique(self):
        """Avorte proprement la cinématique en cours.

        DÉSACTIVÉ depuis Échap (cf. game._gerer_touche) parce que ça
        sautait les events de fin (téléport, set_flag, give_item…) →
        cassait le scénario. Mais la méthode reste là pour les appels
        internes (nettoyage d'urgence, game over forcé, etc.).
        """
        self.cutscene = None
        self.state    = "play"
        if hasattr(self.camera, "release_cinematic"):
            self.camera.release_cinematic()
        # Si un dialogue est encore affiché, on le ferme.
        if hasattr(self.dialogue, "actif") and self.dialogue.actif:
            try:
                self.dialogue.fermer()
            except AttributeError:
                self.dialogue.actif = False

    def _tester_cinematique(self, steps_data, player_libre=False):
        """Lance une cinématique depuis les données JSON brutes (touche [T]
        de l'éditeur de cinématiques). Permet de prévisualiser sans avoir
        à sauvegarder + recharger la carte + entrer dans la zone trigger.

        player_libre : reflète l'option de l'éditeur — si True le joueur
        garde le contrôle pendant la cinématique (test fidèle au comportement
        en jeu).
        """
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
