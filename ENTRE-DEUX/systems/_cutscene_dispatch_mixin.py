# ─────────────────────────────────────────────────────────────────────────────
#  CutsceneDispatchMixin — Initialisation, exécution et nettoyage des étapes
# ─────────────────────────────────────────────────────────────────────────────
#
#  Pour CHAQUE TYPE d'étape (wait, dialogue, npc_walk, fade, camera_focus…)
#  trois méthodes coopèrent :
#
#     _init_step      → lance les effets one-shot quand l'étape démarre
#                       (ex : démarrer un fondu, jouer un son, ouvrir la
#                       boîte de dialogue avec le texte fourni…).
#     _exec_step      → appelée à CHAQUE FRAME tant que l'étape n'est pas
#                       terminée. Met à jour la physique de la cinématique
#                       (déplacer le PNJ, faire glisser la caméra, etc.)
#                       et renvoie True quand l'étape est terminée.
#     _cleanup_step   → nettoyage final quand l'étape se termine (relâcher
#                       la caméra cinématique, etc.).
#
#  Pour ajouter un nouveau type d'étape : ajouter un bloc dans chacune de
#  ces 3 méthodes + une fabrique dans systems/cutscene_steps.py.
#
# ─────────────────────────────────────────────────────────────────────────────

import math

from systems.cutscene_steps import _trouver_pnj, _trouver_position_pnj


class CutsceneDispatchMixin:
    """Trois méthodes coopératives pour chaque type d'étape : init / exec / cleanup."""

    def _init_step(self, step_type, params, ctx):
        """Initialise les variables locales nécessaires à l'étape."""

        if step_type == "wait":
            # On crée un timer qui décompte vers 0.
            self._local["t_restant"] = float(params.get("duration", 1.0))

        elif step_type == "dialogue":
            # Démarre la boîte de dialogue si elle existe.
            lignes = params.get("lines", [])
            if ctx.dialogue_box is not None:
                ctx.dialogue_box.demarrer(lignes)

        elif step_type == "npc_walk":
            # Pas de state à pré-calculer : tout se fait dans _exec_step.
            # On note juste le temps écoulé, utile pour debug ou timeout.
            self._local["t_ecoule"] = 0.0

        elif step_type == "camera_focus":
            # Active la caméra cinématique si la caméra le supporte.
            cible = params.get("target", (0, 0))
            duree = params.get("duration", None)
            speed = params.get("speed",    None)
            if ctx.camera is not None and hasattr(ctx.camera, "set_cinematic_target"):
                ctx.camera.set_cinematic_target(cible, speed=speed)
            self._local["t_ecoule"] = 0.0
            self._local["duree"]    = duree   # None = blocage manuel via release

        elif step_type == "camera_release":
            # Étape instantanée : on libère la caméra dans _exec_step.
            pass

        elif step_type == "fade":
            self._local["t_ecoule"] = 0.0
            # On essaie d'utiliser un éventuel système de fondu du jeu.
            # S'il n'existe pas, l'étape devient un simple wait.
            direction = params.get("direction", "out")
            duree     = params.get("duration", 1.0)
            game = ctx.game
            if hasattr(game, "demarrer_fondu"):
                game.demarrer_fondu(direction, duree)

        elif step_type == "set_state":
            # Modifie un attribut de game (ex : game.state = "play").
            # Étape instantanée : tout le travail est dans _exec_step.
            pass

        elif step_type == "callback":
            # Appel d'une fonction libre. Étape instantanée.
            pass

        elif step_type == "shake":
            # Déclenche un screenshake : amplitude (px), duree (s).
            amplitude = float(params.get("amplitude", 6))
            duree     = float(params.get("duration",  0.3))
            if ctx.shake is not None:
                ctx.shake.trigger(amplitude=amplitude, duree=duree)
            self._local["t_restant"] = duree

        elif step_type == "play_sound":
            nom    = params.get("nom", "")
            volume = float(params.get("volume", 1.0))
            if nom:
                try:
                    from audio import sound_manager
                    sound_manager.jouer(nom, volume=volume)
                except Exception as e:
                    print(f"[Cutscene] Son '{nom}' échoué : {e}")

        elif step_type == "particles_burst":
            x       = float(params.get("x", 0))
            y       = float(params.get("y", 0))
            nb      = int(params.get("nb", 12))
            couleur = tuple(params.get("couleur", (255, 255, 200)))
            if ctx.particles is not None:
                ctx.particles.burst(x, y, nb=nb, couleur=couleur)

        elif step_type == "player_walk":
            self._local["t_ecoule"] = 0.0

        elif step_type == "npc_walk_by_name":
            # Résolution du PNJ par nom (au moment du démarrage de l'étape)
            nom_pnj = params.get("nom_pnj", "")
            self._local["t_ecoule"] = 0.0
            self._local["npc_ref"]  = _trouver_pnj(ctx, nom_pnj)

        elif step_type == "camera_focus_pnj":
            # Cible un PNJ par son nom. On résout la position MAINTENANT.
            # Si follow=True, on garde la référence pour mettre à jour la
            # cible chaque frame dans _exec_step (suit un PNJ qui marche).
            nom_pnj = params.get("nom", "")
            duree   = params.get("duration", None)
            speed   = params.get("speed",    None)
            follow  = bool(params.get("follow", False))
            pnj_ref = _trouver_pnj(ctx, nom_pnj)
            cible   = None
            if pnj_ref is not None and hasattr(pnj_ref, "rect"):
                cible = (pnj_ref.rect.centerx, pnj_ref.rect.centery)
            if cible and ctx.camera is not None and hasattr(ctx.camera, "set_cinematic_target"):
                ctx.camera.set_cinematic_target(cible, speed=speed)
            self._local["t_ecoule"] = 0.0
            self._local["duree"]    = duree
            self._local["pnj_ref"]  = pnj_ref if follow else None
            self._local["follow"]   = follow

        elif step_type == "set_player_pos":
            # Téléporte le joueur à (x, y) instantanément. Étape instantanée.
            pass

        elif step_type in ("npc_spawn", "npc_despawn", "grant_skill",
                            "grant_luciole", "give_item", "give_coins",
                            "set_flag", "flag_increment", "unlock_quickuse",
                            "revive_player", "teleport_player"):
            # Étapes instantanées : tout est fait dans _exec_step.
            pass

        elif step_type == "wait_for_player_at":
            # Rend la main au joueur pendant l'étape.
            self._local["t_ecoule"] = 0.0

        elif step_type == "play_music":
            # Étape instantanée : déclenchée dans _exec_step.
            pass

        elif step_type == "wait_input":
            # Réinitialise le drapeau d'entrée. Le on_key le lève.
            self._local["started"]   = False
            self._local["satisfied"] = False

    def _exec_step(self, step_type, params, ctx, dt):
        """Avance l'étape d'une frame. Renvoie True quand elle est terminée."""

        if step_type == "wait":
            self._local["t_restant"] -= dt
            return self._local["t_restant"] <= 0.0

        if step_type == "dialogue":
            # L'étape dure tant que la boîte est active. Si elle n'existe
            # pas (mode test), on termine immédiatement pour ne pas bloquer.
            if ctx.dialogue_box is None:
                return True
            return not getattr(ctx.dialogue_box, "actif", False)

        if step_type == "npc_walk":
            # Avance un PNJ vers une cible à vitesse constante. Termine
            # quand la distance restante est négligeable.
            npc      = params.get("npc")
            cible    = params.get("target", (0, 0))
            vitesse  = float(params.get("speed", 80))
            tol      = float(params.get("tolerance", 4.0))
            self._local["t_ecoule"] += dt

            if npc is None or not hasattr(npc, "rect"):
                return True   # Rien à déplacer : on saute.

            dx = cible[0] - npc.rect.centerx
            dy = cible[1] - npc.rect.centery
            distance = math.hypot(dx, dy)            # [D11]

            if distance <= tol:
                return True

            # Pas de plus que la distance restante : évite l'overshoot.
            pas = min(vitesse * dt, distance)
            if distance > 0:
                npc.rect.centerx += int(round(dx / distance * pas))
                npc.rect.centery += int(round(dy / distance * pas))

            # Sécurité : timeout à 30 s pour ne jamais bloquer une cinématique
            # si la cible est inatteignable (par bug ou config).
            if self._local["t_ecoule"] > 30.0:
                return True
            return False

        if step_type == "camera_focus":
            # Si une durée a été fournie → l'étape est limitée dans le temps,
            # puis on libère la caméra automatiquement.
            duree = self._local.get("duree", None)
            if duree is None:
                # Étape "instantanée" : on a juste configuré la cible, et
                # camera_release viendra la libérer plus tard.
                return True
            self._local["t_ecoule"] += dt
            return self._local["t_ecoule"] >= duree

        if step_type == "camera_release":
            if ctx.camera is not None and hasattr(ctx.camera, "release_cinematic"):
                ctx.camera.release_cinematic()
            return True

        if step_type == "fade":
            duree = float(params.get("duration", 1.0))
            self._local["t_ecoule"] += dt
            return self._local["t_ecoule"] >= duree

        if step_type == "set_state":
            attr   = params.get("attr")
            valeur = params.get("value")
            if attr:
                setattr(ctx.game, attr, valeur)
            return True

        if step_type == "callback":
            fn = params.get("fn")
            if callable(fn):
                # On passe le contexte pour que la fonction puisse agir
                # sur le jeu (changer de carte, jouer un son, etc.).
                fn(ctx)
            return True

        if step_type == "shake":
            self._local["t_restant"] -= dt
            return self._local["t_restant"] <= 0.0

        if step_type == "play_sound":
            return True   # Étape instantanée

        if step_type == "particles_burst":
            return True   # Étape instantanée

        if step_type == "player_walk":
            cible    = params.get("target", (0, 0))
            vitesse  = float(params.get("speed", 100))
            tol      = float(params.get("tolerance", 6.0))
            self._local["t_ecoule"] += dt

            joueur = ctx.joueur
            if joueur is None or not hasattr(joueur, "rect"):
                return True

            dx = cible[0] - joueur.rect.centerx
            dy = cible[1] - joueur.rect.centery
            distance = math.hypot(dx, dy)

            if distance <= tol:
                return True

            pas = min(vitesse * dt, distance)
            if distance > 0:
                joueur.rect.centerx += int(round(dx / distance * pas))
                joueur.rect.centery += int(round(dy / distance * pas))

            # Sécurité : timeout 30 s
            return self._local["t_ecoule"] > 30.0

        if step_type == "camera_focus_pnj":
            # Si follow=True, on met à jour la cible caméra chaque frame
            # pour qu'elle suive le PNJ qui marche (cf. npc_walk_by_name
            # exécuté en parallèle d'une autre étape, ou enchaîné).
            if self._local.get("follow") and self._local.get("pnj_ref") is not None:
                pnj = self._local["pnj_ref"]
                if hasattr(pnj, "rect") and ctx.camera is not None \
                        and hasattr(ctx.camera, "set_cinematic_target"):
                    ctx.camera.set_cinematic_target(
                        (pnj.rect.centerx, pnj.rect.centery)
                    )
            duree = self._local.get("duree", None)
            if duree is None:
                # Pas de durée → étape instantanée, la caméra reste fixée
                # (ou suit avec follow) jusqu'à la prochaine étape camera_focus
                # ou camera_release. Permet l'ENCHAÎNEMENT entre PNJ sans
                # retour au joueur entre les deux dialogues.
                return True
            self._local["t_ecoule"] += dt
            return self._local["t_ecoule"] >= duree

        if step_type == "npc_walk_by_name":
            npc      = self._local.get("npc_ref")
            cible    = params.get("target", (0, 0))
            vitesse  = float(params.get("speed", 80))
            tol      = float(params.get("tolerance", 4.0))
            self._local["t_ecoule"] += dt

            if npc is None or not hasattr(npc, "rect"):
                return True   # PNJ introuvable : on saute

            dx = cible[0] - npc.rect.centerx
            dy = cible[1] - npc.rect.centery
            distance = math.hypot(dx, dy)
            if distance <= tol:
                return True
            pas = min(vitesse * dt, distance)
            if distance > 0:
                npc.rect.centerx += int(round(dx / distance * pas))
                npc.rect.centery += int(round(dy / distance * pas))
            return self._local["t_ecoule"] > 30.0

        if step_type == "set_player_pos":
            x = params.get("x", None)
            y = params.get("y", None)
            joueur = ctx.joueur
            if joueur is not None and hasattr(joueur, "rect") and x is not None and y is not None:
                joueur.rect.x = int(x)
                joueur.rect.y = int(y)
            return True

        if step_type == "teleport_player":
            # Téléporte le joueur vers une autre map et/ou un spawn nommé.
            # cible : str au format identique à revive_player et aux portails :
            #   "spawn_nom"          → même carte, spawn nommé
            #   "map_nom spawn_nom"  → autre carte, spawn nommé
            #   ""                   → fallback sur x/y (mêmes que set_player_pos)
            game   = ctx.game
            joueur = ctx.joueur
            if joueur is None or game is None:
                return True
            cible = str(params.get("cible", "")).strip()
            nom_map = None
            nom_spawn = None
            if cible:
                if " " in cible:
                    parts = cible.split(" ", 1)
                    nom_map   = parts[0].strip()
                    nom_spawn = parts[1].strip()
                else:
                    nom_spawn = cible
            # Changement de carte si nécessaire
            if nom_map and nom_map != getattr(game, "carte_actuelle", ""):
                if hasattr(game.editeur, "load_map_for_portal"):
                    if game.editeur.load_map_for_portal(nom_map):
                        game.carte_actuelle = nom_map
                        try:
                            game._reconstruire_grille()
                            game._murs_modifies()
                            game._sync_triggers()
                        except Exception:
                            pass
                        # Musique de la nouvelle map (fondu)
                        if hasattr(game, "_appliquer_musique_carte"):
                            try:
                                game._appliquer_musique_carte()
                            except Exception:
                                pass
            # Position cible
            named = getattr(game.editeur, "named_spawns", {}) or {}
            pos = None
            if nom_spawn and nom_spawn in named:
                pos = named[nom_spawn]
            if pos is not None:
                joueur.rect.x = int(pos[0])
                joueur.rect.y = int(pos[1])
            else:
                # Fallback sur x/y explicites (s'ils ont été fournis)
                x = params.get("x", None)
                y = params.get("y", None)
                if x is not None and y is not None:
                    joueur.rect.x = int(x)
                    joueur.rect.y = int(y)
                elif nom_spawn:
                    print(f"[teleport_player] spawn '{nom_spawn}' introuvable")
            # Reset vélocités + snap caméra pour ne pas glisser
            joueur.vx           = 0
            joueur.vy           = 0
            joueur.knockback_vx = 0
            if hasattr(game.camera, "snap_to"):
                game.camera.snap_to(joueur.rect)
            return True

        # ────────────────────────────────────────────────────────────────
        #  Apparition / disparition de PNJ (étape instantanée)
        # ────────────────────────────────────────────────────────────────
        if step_type == "npc_spawn":
            # Crée un PNJ runtime et l'ajoute à game.pnjs (si dispo via ctx).
            try:
                from entities.npc import PNJ
            except Exception:
                return True
            x       = float(params.get("x", 0))
            y       = float(params.get("y", 0))
            nom     = str(params.get("nom", "PNJ"))
            sprite  = params.get("sprite", None)
            dialogues_   = params.get("dialogues", [])
            mode    = str(params.get("dialogue_mode", "boucle_dernier"))
            # has_gravity : si l'utilisateur a laissé le champ vide en
            # éditeur, params.get renvoie None → bool(None)=False (= flotte
            # par accident). On traite explicitement None comme True (défaut).
            has_grav_raw = params.get("has_gravity", True)
            gravity = True if has_grav_raw is None else bool(has_grav_raw)
            events  = params.get("events", None)
            try:
                nv = PNJ(
                    int(x), int(y), nom, dialogues_,
                    sprite_name=sprite,
                    dialogue_mode=mode,
                    has_gravity=gravity,
                    events=events,
                )
            except Exception as e:
                print(f"[Cutscene] npc_spawn échoué : {e}")
                return True
            # Direction initiale du PNJ : 1 = regarde à droite (défaut),
            # -1 = regarde à gauche. L'éditeur expose le champ "facing"
            # (1 ou -1) pour les PNJ scénarisés (ex: Nimbus qui doit
            # accueillir le joueur en lui faisant face).
            facing_raw = params.get("facing", 1)
            try:
                facing = -1 if int(facing_raw) < 0 else 1
            except (TypeError, ValueError):
                facing = 1
            try:
                nv._facing = facing
            except Exception:
                pass
            # Cible privilégiée : ctx.editeur.pnjs (rebuild via _sync_triggers
            # n'est pas nécessaire : ctx.pnjs pointe sur la même liste).
            target_list = None
            if hasattr(ctx, "editeur") and ctx.editeur is not None:
                target_list = getattr(ctx.editeur, "pnjs", None)
            if target_list is None:
                target_list = ctx.pnjs
            if target_list is not None:
                target_list.append(nv)
                # Si ctx.pnjs est une référence distincte, on l'aligne aussi.
                if ctx.pnjs is not target_list and ctx.pnjs is not None:
                    ctx.pnjs.append(nv)
            return True

        if step_type == "npc_despawn":
            nom = str(params.get("nom", ""))
            cible = _trouver_pnj(ctx, nom)
            if cible is None:
                return True
            for lst in (
                getattr(ctx.editeur, "pnjs", None) if hasattr(ctx, "editeur") else None,
                ctx.pnjs,
            ):
                if lst is None:
                    continue
                try:
                    lst.remove(cible)
                except ValueError:
                    pass
            return True

        # ────────────────────────────────────────────────────────────────
        #  Récompenses (skill / luciole / item / coins) — instantanées
        # ────────────────────────────────────────────────────────────────
        if step_type == "grant_skill":
            try:
                import settings
                val = str(params.get("value", ""))
                attr = f"skill_{val}"
                if hasattr(settings, attr):
                    setattr(settings, attr, True)
                    if ctx.game and hasattr(ctx.game, "notifier"):
                        ctx.game.notifier(f"Compétence débloquée : {val}")
                else:
                    print(f"[Cutscene] skill inconnu : {val!r}")
            except Exception as e:
                print(f"[Cutscene] grant_skill : {e}")
            return True

        if step_type == "grant_luciole":
            game = ctx.game
            src = str(params.get("source", "cutscene"))
            try:
                game.compagnons.gagner_luciole(joueur=game.joueur, source=src)
                if hasattr(game, "notifier"):
                    game.notifier("+ 1 luciole")
            except Exception as e:
                print(f"[Cutscene] grant_luciole : {e}")
            return True

        if step_type == "give_item":
            game = ctx.game
            nom = str(params.get("name", ""))
            n   = int(params.get("count", 1))
            try:
                if hasattr(game, "inventory") and nom:
                    game.inventory.add_item(nom, count=n)
                    if hasattr(game, "notifier"):
                        game.notifier(f"+ {n} {nom}" if n > 1 else f"+ {nom}")
            except Exception as e:
                print(f"[Cutscene] give_item : {e}")
            return True

        if step_type == "give_coins":
            game = ctx.game
            n = int(params.get("amount", 0))
            if hasattr(game, "joueur"):
                game.joueur.coins = getattr(game.joueur, "coins", 0) + n
                if hasattr(game, "notifier") and n != 0:
                    game.notifier(f"+ {n} pièces" if n > 0 else f"{n} pièces")
            return True

        if step_type == "revive_player":
            # Réanime le joueur après une cinématique de mort scriptée.
            # - PV remis à max_hp
            # - position via SPAWN NOMMÉ (cf. mode 14 de l'éditeur) :
            #   cible = "mapname spawnname" ou juste "spawnname" pour la
            #   carte courante. Comme pour les portails (target_map).
            # - dead = False (annule l'écran de mort)
            # - revive les ennemis de la map d'arrivée
            game = ctx.game
            joueur = ctx.joueur
            if joueur is None or game is None:
                return True

            joueur.hp           = joueur.max_hp
            joueur.dead         = False
            joueur.vx           = 0
            joueur.vy           = 0
            joueur.knockback_vx = 0
            joueur.invincible   = False

            cible = str(params.get("cible", "")).strip()
            nom_map  = None
            nom_spawn = None
            if cible:
                if " " in cible:
                    parts = cible.split(" ", 1)
                    nom_map   = parts[0].strip()
                    nom_spawn = parts[1].strip()
                else:
                    # Pas d'espace → c'est un nom de spawn dans la carte
                    # courante (raccourci).
                    nom_spawn = cible

            # Charger la carte cible si différente de l'actuelle.
            if nom_map and nom_map != game.carte_actuelle:
                if hasattr(game.editeur, "load_map_for_portal"):
                    if game.editeur.load_map_for_portal(nom_map):
                        game.carte_actuelle = nom_map
                        # Reconstruction des index spatiaux après chgt map.
                        try:
                            game._reconstruire_grille()
                            game._murs_modifies()
                            game._sync_triggers()
                        except Exception:
                            pass
                        # Musique de la nouvelle map
                        if hasattr(game, "_appliquer_musique_carte"):
                            try:
                                game._appliquer_musique_carte()
                            except Exception:
                                pass

            # Récupère la position du spawn nommé.
            named = getattr(game.editeur, "named_spawns", {}) or {}
            pos = None
            if nom_spawn and nom_spawn in named:
                pos = named[nom_spawn]
            if pos is not None:
                joueur.rect.x = int(pos[0])
                joueur.rect.y = int(pos[1])
            else:
                # Fallback : spawn par défaut de la map.
                joueur.rect.x = game.editeur.spawn_x
                joueur.rect.y = game.editeur.spawn_y
                if cible:
                    print(f"[Cutscene] revive_player : spawn '{cible}' "
                          f"introuvable, fallback spawn défaut")

            # Snap caméra sur la nouvelle pos.
            if hasattr(game.camera, "snap_to"):
                game.camera.snap_to(joueur.rect)
            # Revive les ennemis du niveau.
            for e in getattr(game, "ennemis", []):
                e.alive = True
            # Replace les compagnons.
            if hasattr(game, "compagnons"):
                try:
                    game.compagnons.respawn(joueur)
                except Exception:
                    pass
            return True

        if step_type == "unlock_quickuse":
            # Macro : pose le flag "quickuse_unlocked", donne N pommes,
            # affiche une notification. Tout-en-un pour la cinématique
            # de Nymbus qui débloque la mécanique.
            game = ctx.game
            if game is not None:
                if not hasattr(game, "story_flags"):
                    game.story_flags = {}
                game.story_flags["quickuse_unlocked"] = True
                # Quantité de pommes offertes (paramétrable).
                n = int(params.get("pommes", 10))
                if n > 0 and hasattr(game, "inventory"):
                    try:
                        game.inventory.add_item("Pomme", count=n)
                    except Exception as e:
                        print(f"[Cutscene] unlock_quickuse pommes : {e}")
                if hasattr(game, "notifier"):
                    game.notifier("Consommables rapides débloqués !")
                    if n > 0:
                        game.notifier(f"+ {n} Pommes")
            return True

        if step_type == "set_flag":
            # Pose un story flag (booléen) — utilise le système avec compteurs.
            game = ctx.game
            if not hasattr(game, "story_flags"):
                game.story_flags = {}
            key = str(params.get("key", ""))
            val = bool(params.get("value", True))
            if key:
                from systems.story_flags import flag_poser
                flag_poser(game.story_flags, key, val)
                # Notifie game.py pour que les cinématiques conditionnelles
                # puissent se déclencher si la condition vient d'être remplie.
                if hasattr(game, "_programmer_verif_cine"):
                    game._programmer_verif_cine()
            return True

        if step_type == "flag_increment":
            # Incrémente un flag avec compteur. Crée le flag si absent (avec
            # le required donné, sinon depuis le registre).
            game = ctx.game
            if not hasattr(game, "story_flags"):
                game.story_flags = {}
            key      = str(params.get("key", ""))
            delta    = int(params.get("delta", 1))
            required = params.get("required", None)
            if required in ("", None):
                required = None
            else:
                try:
                    required = int(required)
                except (TypeError, ValueError):
                    required = None
            if key:
                from systems.story_flags import flag_incrementer, flag_valeur
                flag_incrementer(
                    game.story_flags, key, delta=delta, required=required)
                # Affiche le toast "key : current/required" comme pour les
                # events PNJ — feedback indispensable pour le joueur.
                cur, req = flag_valeur(game.story_flags, key)
                if hasattr(game, "notifier"):
                    game.notifier(f"{key} : {cur}/{req}")
                # Vérification des cinématiques conditionnelles (peu importe
                # qu'on vienne de finir : un seuil intermédiaire compte aussi).
                if hasattr(game, "_programmer_verif_cine"):
                    game._programmer_verif_cine()
            return True

        # ────────────────────────────────────────────────────────────────
        #  Musique : transition fluide vers une autre piste
        # ────────────────────────────────────────────────────────────────
        if step_type == "play_music":
            chemin     = str(params.get("chemin", ""))
            volume     = float(params.get("volume",     0.6))
            fadeout_ms = int(params.get("fadeout_ms",   1000))
            fadein_ms  = int(params.get("fadein_ms",    1500))
            try:
                from audio import music_manager as music
                if chemin:
                    music.transition(chemin, volume=volume,
                                     fadeout_ms=fadeout_ms,
                                     fadein_ms=fadein_ms)
                else:
                    music.fadeout(fadeout_ms)
            except Exception as e:
                print(f"[Cutscene] play_music : {e}")
            return True

        # ────────────────────────────────────────────────────────────────
        #  Attente d'une touche du joueur
        # ────────────────────────────────────────────────────────────────
        if step_type == "wait_input":
            # L'étape se termine quand le joueur a appuyé sur la touche
            # demandée (ex: "space"). Si "any", n'importe quelle touche.
            # Stocke un drapeau attendu sur le runner ; on_key() le lève.
            if not self._local.get("started", False):
                self._local["started"]   = True
                self._local["satisfied"] = False
                self._local["t_ecoule"]  = 0.0
            self._local["t_ecoule"] += dt
            if self._local.get("satisfied", False):
                return True
            timeout = float(params.get("timeout", 0))
            return timeout > 0 and self._local["t_ecoule"] > timeout

        # ────────────────────────────────────────────────────────────────
        #  Attente conditionnelle : laisse le joueur libre jusqu'à un point
        # ────────────────────────────────────────────────────────────────
        if step_type == "wait_for_player_at":
            # Pendant cette étape, on rend la main au joueur (bouger,
            # sauter…) jusqu'à ce qu'il atteigne (x, y) ± rayon.
            # Utile pour scènes mi-cinématique mi-gameplay (ex : aller
            # ouvrir un tiroir, monter une échelle, etc.).
            x      = float(params.get("x", 0))
            y      = float(params.get("y", 0))
            rayon  = float(params.get("radius", 32))
            timeout = float(params.get("timeout", 60))
            self._local["t_ecoule"] = self._local.get("t_ecoule", 0.0) + dt
            joueur = ctx.joueur
            if joueur is None or not hasattr(joueur, "rect"):
                return True
            # Drapeau lu par game._simuler_jeu : si True, ne pas bloquer
            # le mouvement même si une cutscene tourne. Cf. game.py.
            game = ctx.game
            if game is not None:
                game._cutscene_player_libre = True
            dx = x - joueur.rect.centerx
            dy = y - joueur.rect.centery
            if (dx * dx + dy * dy) ** 0.5 <= rayon:
                return True
            return self._local["t_ecoule"] > timeout

        # Type inconnu → on n'ose pas bloquer la cinématique : on saute.
        return True

    def _cleanup_step(self, step_type, params, ctx):
        """Nettoyage optionnel à la fin d'une étape.

        Utilisé par camera_focus(duration=…) pour libérer la caméra à la fin
        de la durée. Pour les autres étapes, ne fait rien."""

        if step_type == "camera_focus":
            duree = self._local.get("duree", None)
            if duree is not None:
                # Libération auto à la fin de la durée. Si on veut garder le
                # focus indéfiniment, ne pas passer de duration → utiliser
                # camera_release séparément.
                if ctx.camera is not None and hasattr(ctx.camera, "release_cinematic"):
                    ctx.camera.release_cinematic()