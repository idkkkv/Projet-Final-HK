# ─────────────────────────────────────────────────────────────────────────────
#  SimulationMixin — Physique, collisions et effets chaque frame
# ─────────────────────────────────────────────────────────────────────────────
#
#  Ce mixin regroupe la logique de simulation du monde appelée chaque frame :
#
#   _simuler_jeu       → physique, collisions, entités, systèmes transversaux
#   _appliquer_fear_zones → ralentissement + mur invisible selon stade de peur
#   update_bonus       → effets d'équipement actifs (épée, bouclier)
#
#  Ces méthodes sont appelées depuis _update_jeu() à chaque frame de jeu.
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame

from core.event_handler import x_y_man, man_on
from entities.marchand import Marchand
from systems.combat import resoudre_attaques_joueur, resoudre_contacts_ennemis
from systems.fear_system import FearSystem
from ui.items_effects import ajouter_atk, ajouter_vie, retirer_atk, retirer_vie
from world.collision import appliquer_plateformes


class SimulationMixin:
    """Physique, collisions, systèmes transversaux et effets frame-by-frame."""

    # ─────────────────────────────────────────────────────────────────────────
    # BOUCLE DE SIMULATION PRINCIPALE
    # ─────────────────────────────────────────────────────────────────────────

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

            # 4. Cas spécial pour le Boss Explosion - UNIQUEMENT si le boss est vivant
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
            # Auto-save zones : checkpoint léger (joueur seul, pas l'histoire)
            self._verifier_autosave_zones()

        # ── Projectiles d'ombre tirés par les boss ──────────────────────────
        # On vérifie toujours la collision avec le joueur (même s'il est
        # invincible) : si dash/dodge → la boule TRAVERSE sans dégât (pas
        # consommée). Sinon, contact = -1 PV via hit_by_enemy (qui gère
        # l'invincibilité / anim hurt). Le projectile s'auto-détruit sur
        # un hit qui inflige des dégâts pour ne pas re-toucher en boucle.
        if not self.editeur.active:
            joueur_immune = (getattr(self.joueur, "dashing", False)
                             or getattr(self.joueur, "back_dodge_lock_timer", 0.0) > 0)
            for ennemi in self.ennemis:
                if not getattr(ennemi, "alive", False):
                    continue
                projs = getattr(ennemi, "projectiles", None)
                if not projs:
                    continue
                touche = False
                for p in projs:
                    if not p.alive:
                        continue
                    if p.rect.colliderect(self.joueur.rect):
                        if joueur_immune:
                            # Dash/slide/dodge : la boule passe à travers
                            continue
                        # Contact normal : on consomme le projectile et
                        # on inflige les dégâts via la voie standard.
                        p.alive = False
                        try:
                            self.joueur.hit_by_enemy(p.rect)
                        except Exception:
                            self.joueur.hp = max(0, self.joueur.hp - 1)
                            if self.joueur.hp <= 0:
                                self.joueur.dead = True
                        if getattr(ennemi, "nom", ""):
                            self._derniere_cause_mort = "boss"
                        touche = True
                        break
                if touche:
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

    # ─────────────────────────────────────────────────────────────────────────
    # FEAR ZONES
    # ─────────────────────────────────────────────────────────────────────────
    #
    #  Logique appliquée chaque frame depuis _simuler_jeu() :
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
    #  POURQUOI LE MUR ?
    #  Sans mur, une zone de peur reste juste "lente" : le joueur peut
    #  passer à 35 % de vitesse, c'est pénible mais pas un vrai obstacle
    #  scénaristique. Avec le mur (côté direction_mur uniquement), on a
    #  un VRAI gate : tu DOIS avoir assez de lucioles pour franchir. Pour
    #  les autres côtés (sans mur), le joueur peut toujours rebrousser
    #  chemin → pas de piège, juste une frontière dirigée.
    #
    #  RÈGLE ANTI-BLOCAGE :
    #  Le multiplicateur de vitesse a un PLANCHER (FEAR_ZONE_VITESSE_MIN
    #  = 0.35). Donc même si tu rentres dans la zone et heurtes le mur,
    #  tu peux toujours marcher pour reculer et en sortir par l'autre
    #  côté.

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
        if texte_a_afficher:
            self.fear_overlay.show(texte_a_afficher)

        # Plus dans aucune zone trop dure → on fait disparaître l'overlay.
        if not in_zone:
            self.fear_overlay.hide()

        # ── Mur invisible côté `direction_mur` ──────────────────────────────
        # Le mur est une fine bande (8 px) sur le bord `direction_mur` de
        # la zone. On bloque la traversée dans LES DEUX SENS à travers
        # cette bande. Les autres bords restent libres → pas de piège.
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

    # ─────────────────────────────────────────────────────────────────────────
    # BONUS D'ÉQUIPEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def update_bonus(self):
        """Applique ou retire les bonus d'équipement actifs (épée, bouclier).

        Appelé depuis _dessiner_monde() à chaque frame pour synchroniser
        les stats du joueur avec l'état de l'inventaire."""
        # Épée : +1 ATK tant qu'elle est équipée
        if self.inventory.epee_active:
            if not self.joueur.epee_bonus:
                ajouter_atk(self.joueur)
                self.joueur.epee_bonus = True
                now = pygame.time.get_ticks()
                if now - getattr(self, "_last_epee_msg", 0) > 3000:
                    self.notifier("attaque supp active")
                    self._last_epee_msg = now
        else:
            if self.joueur.epee_bonus:
                retirer_atk(self.joueur)
                self.joueur.epee_bonus = False
                now = pygame.time.get_ticks()
                if now - getattr(self, "_last_epee_msg2", 0) > 3000:
                    self.notifier("attaque supp desactive")
                    self._last_epee_msg2 = now

        # Bouclier : +1 PV maximum tant qu'il est équipé
        if self.inventory.bouclier_actif:
            if not self.joueur.bouclier_bonus:
                ajouter_vie(self.joueur)
                self.joueur.bouclier_bonus = True
                now = pygame.time.get_ticks()
                if now - getattr(self, "_last_bouclier_msg", 0) > 3000:
                    self.notifier("vie supp active")
                    self._last_bouclier_msg = now
        else:
            if self.joueur.bouclier_bonus:
                retirer_vie(self.joueur)
                self.joueur.bouclier_bonus = False
                now = pygame.time.get_ticks()
                if now - getattr(self, "_last_bouclier_msg2", 0) > 3000:
                    self.notifier("vie supp desactive")
                    self._last_bouclier_msg2 = now
