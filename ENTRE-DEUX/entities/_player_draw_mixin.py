# ─────────────────────────────────────────────────────────────────────────────
#  PlayerDrawMixin — Rendu du joueur (sprite + FX + cœurs)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Tout le code de rendu du joueur. _draw_inner() choisit l'animation à jouer
#  selon l'état (hurt, dash, wall_slide, jump, attack, run, walk, idle…),
#  applique scale + flip, ajoute des compensations de position selon les
#  particularités de chaque sprite, puis dessine.
#
# ─────────────────────────────────────────────────────────────────────────────

import math

import pygame

import settings
from entities.animation import Animation


class PlayerDrawMixin:
    """Rendu visuel du joueur : sprite animé, FX dash aérien, cœurs."""

    def _draw_aerial_dash_fx(self, surf, camera):
        """Dessine la fumée + le FX rémanent au point de départ d'un dash aérien.

        Effet "téléportation" : à l'endroit où le joueur a déclenché le dash,
        on laisse pendant ~0.4s une silhouette qui se dissipe (fx) et un
        petit nuage de fumée (smoke). Les deux ne suivent PAS le joueur :
        ils restent à `self.aerial_smoke_pos` / `self.aerial_fx_pos`.

        Les 2 effets sont :
          - flippés selon la direction du joueur (sinon ils regardent
            toujours du même côté, comme un perso bloqué dans son sens),
          - remontés d'un offset car les sprites natifs ont un peu de marge
            sous le motif → sans offset le centre visuel paraît trop bas.
        """
        # Offset vertical pour caler visuellement les centres (la silhouette
        # et le rond de fumée ont une marge transparente sous leur "vrai"
        # centre dans le PNG → on remonte un peu).
        OFFSET_Y = -18

        # On flippe les FX dans le sens du joueur (idem logique du sprite).
        flip = (self.direction == 1)

        # Fumée — CENTRÉE sur le point de départ (même niveau que le joueur)
        if self.aerial_smoke_pos is not None and not self.aerial_smoke_anim.done:
            self.aerial_smoke_anim.update()
            sm = self.aerial_smoke_anim.img()
            sm = pygame.transform.smoothscale(
                sm,
                (int(sm.get_width()  * self.scale_factor),
                 int(sm.get_height() * self.scale_factor))
            )
            if flip:
                sm = pygame.transform.flip(sm, True, False)
            x = self.aerial_smoke_pos[0] - sm.get_width()  // 2
            y = self.aerial_smoke_pos[1] - sm.get_height() // 2 + OFFSET_Y
            surf.blit(sm, camera.apply(pygame.Rect(x, y, sm.get_width(), sm.get_height())))

        # FX rémanent (silhouette translucide, à hauteur du perso)
        if self.aerial_fx_pos is not None and not self.aerial_fx_anim.done:
            self.aerial_fx_anim.update()
            fx = self.aerial_fx_anim.img()
            fx = pygame.transform.smoothscale(
                fx,
                (int(fx.get_width()  * self.scale_factor),
                 int(fx.get_height() * self.scale_factor))
            )
            if flip:
                fx = pygame.transform.flip(fx, True, False)
            x = self.aerial_fx_pos[0] - fx.get_width()  // 2
            y = self.aerial_fx_pos[1] - fx.get_height() // 2 + OFFSET_Y
            surf.blit(fx, camera.apply(pygame.Rect(x, y, fx.get_width(), fx.get_height())))

    def draw(self, surf, camera, show_hitbox=False):
        # ── Gel des animations en pause ──────────────────────────────────
        # game.py met self.paused = True quand on est dans l'état PAUSE.
        # Pendant la pause, _dessiner_monde() continue d'être appelé donc
        # draw() est ré-invoqué chaque frame → les anims loop=True (jump,
        # walk, idle, wall_slide…) continueraient de cycler. On neutralise
        # les .update() en sauvegardant l'originale et en la remplaçant
        # par une fonction qui ne fait rien. Restaurée à la fin de draw().
        if self.paused:
            _orig_update = Animation.update
            Animation.update = lambda self_: None
        try:
            self._draw_inner(surf, camera, show_hitbox)
        finally:
            if self.paused:
                Animation.update = _orig_update

    def _draw_inner(self, surf, camera, show_hitbox=False):
        # ── Effets visuels du dash AÉRIEN (smoke + fx au point de départ) ──
        # Dessinés AVANT le perso pour qu'ils soient en arrière-plan.
        # On les dessine tant qu'ils ne sont pas terminés (one-shot).
        self._draw_aerial_dash_fx(surf, camera)

        # ── Détection des transitions sol/air pour l'anim de saut ──────
        # 1) On vient de QUITTER le sol → on reset le statut "done" de
        #    l'arc de saut. Pour un VRAI saut (jumps_used>=1), l'arc va
        #    rejouer ses 20 frames. Pour une marche en bord de plateforme
        #    (jumps_used==0), on force directement le mode "fall_loop"
        #    en marquant l'arc déjà terminé.
        # 2) On vient de TOUCHER le sol après être en l'air → on déclenche
        #    l'anim d'atterrissage (frames 21-24) jouée une fois.
        if self._prev_on_ground and not self.on_ground:
            # Quitte le sol
            if self.jumps_used >= 1:
                # Vrai saut → arc rejoué depuis le début (le code de
                # _tenter_saut a déjà reset frame=0 ; on s'assure que
                # done=False).
                self.idle_anim_jump.done  = False
            else:
                # Pas de saut (marche en bord) → on saute directement
                # sur la boucle de chute en marquant l'arc done.
                self.idle_anim_jump.frame = (len(self.idle_anim_jump.images) - 1) * self.idle_anim_jump.img_duration
                self.idle_anim_jump.done  = True
                if self.idle_anim_fall_loop is not None:
                    self.idle_anim_fall_loop.frame = 0
        elif not self._prev_on_ground and self.on_ground:
            # Atterrissage : on déclenche l'anim landing si elle existe.
            if self.idle_anim_landing is not None and not self.dashing:
                self.idle_anim_landing.reset()
                self._landing_active = True
        self._prev_on_ground = self.on_ground

        # ── Anim d'atterrissage prioritaire (sur idle/walk uniquement) ─
        # On laisse les actions interrompre le landing : si le joueur
        # appuie pour courir, attaquer, dasher, etc., on coupe.
        if self._landing_active:
            interrupt = (self.attacking or self.dashing or self.walking
                         or self.running or not self.on_ground)
            if interrupt or self.idle_anim_landing is None or self.idle_anim_landing.done:
                self._landing_active = False

        # hurt -----------------------------
        if self.hitted_hard:
            self.idle_anim_hurt_hard.update()
            img = self.idle_anim_hurt_hard.img()
            if self.idle_anim_hurt_hard.done:
                self.hitted_hard = False
        elif self.hitted_normal:
            self.idle_anim_hurt_normal.update()
            img = self.idle_anim_hurt_normal.img()
            if self.idle_anim_hurt_normal.done:
                self.hitted_normal = False

        # heal -----------------------------
        elif self.healing:
            self.idle_anim_heal.update()
            img = self.idle_anim_heal.img()
            if self.idle_anim_heal.done:
                self.healing = False

        # dash -----------------------------

        elif self.dashing:
            # Avant ou arrière selon le drapeau dash_back
            if self.dash_back:
                self.idle_anim_dash_back.update()
                img = self.idle_anim_dash_back.img()
            elif not self.on_ground:
                # Dash AÉRIEN : anim spécifique (sheaerialdash, 12 frames)
                self.idle_anim_aerial_dash.update()
                img = self.idle_anim_aerial_dash.img()
            else:
                # Dash sol : slide_merged
                self.idle_anim_dash_fwd.update()
                img = self.idle_anim_dash_fwd.img()
        elif self.wall_sliding:
            # Glisse contre un mur (looped, 3 frames)
            self.idle_anim_wall_slide.update()
            img = self.idle_anim_wall_slide.img()
        elif self.wall_jump_windup_timer > 0:
            # Phase de prep : le perso est collé au mur, l'anim joue
            # (3 frames qui se ramassent puis poussent). À la fin du
            # wind-up, la physique du saut est appliquée et on entre en
            # phase push (cf. branche suivante).
            self.idle_anim_wall_jump.update()
            img = self.idle_anim_wall_jump.img()
            
        # jump -----------------------------
        elif not self.on_ground:
            # Double saut en cours ?
            if self.jumps_used >= 2:
                # Forward (touche maintenue) ou vertical (statique) ?
                if self.attacking and not self.on_ground:
                    if self.combo_step == 1:
                        self.idle_anim_1xjumpatk.update()
                        img = self.idle_anim_1xjumpatk.img()
                    else:
                        self.idle_anim_2xjumpatk.update()
                        img = self.idle_anim_2xjumpatk.img()
                    self.just_fallen = True

                else :
                    if self.double_jump_forward:
                        anim = self.idle_anim_double_jump_fwd
                    else:
                        anim = self.idle_anim_double_jump

                    if not anim.done:
                        anim.update()
                        img = anim.img()
                    else:
                        # Double saut terminé → bascule sur l'arc de saut
                        # (ou la boucle de chute si l'arc est lui-même fini).
                        img = self._anim_air_normale()
            else:
                # Saut normal
                if self.attacking and not self.on_ground:
                    if self.combo_step == 1:
                        anim = self.idle_anim_1xjumpatk
                        self.idle_anim_1xjumpatk.update()
                        img = self.idle_anim_1xjumpatk.img()
                    else:
                        anim = self.idle_anim_2xjumpatk
                        self.idle_anim_2xjumpatk.update()
                        img = self.idle_anim_2xjumpatk.img()

                    self.just_fallen = True
                else:
                    img = self._anim_air_normale()

        # landing (atterrissage) — frames 21-24, joué une fois au contact sol
        elif self._landing_active and self.idle_anim_landing is not None:
            self.idle_anim_landing.update()
            img = self.idle_anim_landing.img()
            if self.idle_anim_landing.done:
                self._landing_active = False

        # atk ------------------------------
        elif self.attacking and not self.just_fallen:
            if self.combo_step == 0:
                anim = self.idle_anim_dodge_atk_3x
                self.idle_anim_dodge_atk_3x.update()
                img = self.idle_anim_dodge_atk_3x.img()
            elif self.combo_step == 1:
                anim = self.idle_anim_1xatk
                self.idle_anim_1xatk.update()
                img = self.idle_anim_1xatk.img()
            elif self.combo_step == 2:
                anim = self.idle_anim_2xatk_short
                self.idle_anim_2xatk_short.update()
                img = self.idle_anim_2xatk_short.img()
            else:
                anim = self.idle_anim_3xatk
                self.idle_anim_3xatk.update()
                img = self.idle_anim_3xatk.img()

        # debut du run ----------------------------

        elif self.run_state == "turn":
            self.idle_anim_run_turn.update()
            img = self.idle_anim_run_turn.img()

            if self.idle_anim_run_turn.done:
                self.run_state = "run"

        elif self.run_state == "start":
            if self.idle_anim_run_start.done:
                self.run_state = "run"
            self.idle_anim_run_start.update()
            img = self.idle_anim_run_start.img()

        elif self.run_state == "run":
            self.idle_anim_run.update()
            img = self.idle_anim_run.img()

        elif self.run_state == "stop":
            if self.idle_anim_run_stop.done:
                self.run_state = "idle"
            self.idle_anim_run_stop.update()
            img = self.idle_anim_run_stop.img()

        # fin du run -----------------------------
        
        elif self.walking:
            self.idle_anim_walk.update()
            img = self.idle_anim_walk.img()
        else:
            self.idle_anim_idle.update()
            img = self.idle_anim_idle.img()

        img = pygame.transform.smoothscale(
            img,
            (int(img.get_width()  * self.scale_factor),
            int(img.get_height() * self.scale_factor))
        )

        if self.direction == 1:
            img = pygame.transform.flip(img, True, False)

        img_w = img.get_width()
        img_h = img.get_height()
        sx = self.rect.centerx - img_w // 2
        sy = self.rect.bottom  - img_h

        # ── Compensation attaques ────────────────────────────────────────
        if self.attacking and self.attack_dir == "side" :
            if not self.just_fallen :
                if self.combo_step == 0 :
                    sy += 92 
                elif self.combo_step == 1 :
                    sx += 85 * self.direction
                elif self.combo_step == 2 :
                    sx += 65 * self.direction
                else:  # x3
                    sx += 107 * self.direction
            else :
                if self.combo_step == 1 :
                    sx += 65 * self.direction

        # ── Compensation back dodge ──────────────────────────────────────
        # Le sprite back dodge utilise une toile 142×61 (vs ~46×55 pour
        # idle/walk). Le corps du perso N'EST PAS au centre de cette toile :
        # il se balade entre offset +41 (départ) et -18 (peak du recoil)
        # puis se stabilise à +35 sur les frames 14-20 (pose de fin).
        # Sans correction, à la fin de l'anim quand idle prend le relais,
        # le perso "saute" de 35px (il passe d'un point décalé au centre
        # du rect → effet de téléportation gênant).
        # → on décale le sprite pour que la POSE FINALE coïncide avec
        # rect.centerx. Le mouvement de recoil est préservé (juste shifté
        # uniformément) et la transition vers idle devient fluide.
        if self.dashing and self.dash_back:
            sx += 53 * self.direction
        elif self.dashing and not self.dash_back and self.on_ground:
            # Slide / dash sol : même problème de toile (144×64, perso à
            # gauche du canvas). Pose finale offset -34 vs idle -7 → on
            # shifte de -27px pour que la fin du slide soit alignée idle.
            sx -= 27 * self.direction

        # ── Compensation Y wall slide ────────────────────────────────────
        # Le sprite wall slide a 3 frames où le corps descend dans le canvas
        # (body bottom = 61, 66, 72 px sur 73 px de hauteur). Comme le rect
        # avance déjà uniformément en Y avec vy, cette descente intra-sprite
        # SE CUMULE et donne un effet saccadé (descend vite, remonte un
        # peu en bouclant frame 3 → frame 1, redescend...).
        # → On verrouille la base du corps sur rect.bottom en compensant
        # la position Y selon la frame courante. Résultat : descente
        # parfaitement uniforme pilotée uniquement par vy.
        if self.wall_sliding:
            # Ratios body_bottom_y / canvas_h pour chaque frame de slide.
            BODY_RATIOS = (61/73, 66/73, 72/73)
            f = self.idle_anim_wall_slide.index()
            if 0 <= f < len(BODY_RATIOS):
                sy += int(img_h * (1 - BODY_RATIOS[f]))

        sprite_rect = pygame.Rect(sx, sy, img_w, img_h)

        # ── Application de PLAYER_SCALE au sprite ────────────────────────
        # La hitbox est déjà scalée dans __init__/reload_hitbox. Ici on
        # scale l'IMAGE pour que le visuel corresponde. On recentre pour
        # garder les pieds au bas de la hitbox (sinon le sprite flotte).
        _ps = getattr(settings, "PLAYER_SCALE", 1.0) or 1.0
        if _ps != 1.0:
            new_w = max(1, int(img_w * _ps))
            new_h = max(1, int(img_h * _ps))
            try:
                img = pygame.transform.smoothscale(img, (new_w, new_h))
            except (ValueError, pygame.error):
                img = pygame.transform.scale(img, (new_w, new_h))
            sprite_rect = pygame.Rect(
                sx - (new_w - img_w) // 2,
                sy - (new_h - img_h),
                new_w, new_h,
            )

        if self.invincible and not (self.hitted_hard or self.hitted_normal) and self.dead:
            if int(self.invincible_timer * 12) % 2 == 0:
                surf.blit(img, camera.apply(sprite_rect))
        else:
            surf.blit(img, camera.apply(sprite_rect))

        if self.show_hp_timer > 0:
            self._draw_hearts(surf, camera)

        if show_hitbox:
            pygame.draw.rect(surf, (0, 255, 0),    camera.apply(self.rect),       1)
            pygame.draw.rect(surf, (80, 80, 200),  camera.apply(sprite_rect),     1)

    def _draw_hearts(self, surf, camera):
        """Dessine une rangée de petits carrés rouges/gris au-dessus du joueur.

        Rouges   = PV restants
        Gris     = PV perdus
        """
        # Création paresseuse de la police (seulement à la 1re utilisation).
        if self._heart_font is None:
            self._heart_font = pygame.font.SysFont("Consolas", 18)

        # Calcul de la position de la rangée de cœurs.
        sr         = camera.apply(self.rect)
        heart_size = 12                                   # côté d'un cœur (px)
        gap        = 4                                    # espace entre cœurs
        total_w    = self.max_hp * (heart_size + gap) - gap
        start_x    = sr.centerx - total_w // 2            # centré au-dessus du joueur
        y          = sr.top - 20                          # 20 px plus haut

        # Dessine max_hp cœurs, un par un.
        for i in range(self.max_hp):
            x = start_x + i * (heart_size + gap)
            # Rouge si PV restant, gris foncé sinon.
            if i < self.hp:
                couleur = (255, 50, 80)
            else:
                couleur = (80, 80, 80)
            # Rectangle plein (le "cœur") puis contour clair autour.
            pygame.draw.rect(surf, couleur,        (x, y, heart_size, heart_size))
            pygame.draw.rect(surf, (200, 200, 200), (x, y, heart_size, heart_size), 1)

    def draw_slash(self, surface, camera):
        if not self.attacking:
            return

        has_hit = getattr(self, "attack_has_hit", False)
        puissance = 1.8 if has_hit else 1.0
        
        # 1. On crée un rectangle bien large pour l'arc
        vis_rect = self.attack_rect.inflate(
            self.attack_rect.width * (puissance - 0.2), 
            self.attack_rect.height * (puissance + 0.2)
        )
        rect_ecran = camera.apply(vis_rect)

        # 2. Préparation de la surface
        surf_slash = pygame.Surface(vis_rect.size, pygame.SRCALPHA)
        alpha = int((self.attack_timer / 0.15) * 255)
        couleur = (255, 255, 255, alpha)
        
        if self.attack_dir == "down":
            # Arc vers le bas
            start_angle, end_angle = math.pi, 2 * math.pi
        elif self.direction == 1:
            # Arc vers la droite (de -90° à 90°)
            start_angle, end_angle = -math.pi/2, math.pi/2
        else:
            # Arc vers la gauche (de 90° à 270°)
            start_angle, end_angle = math.pi/2, 3*math.pi/2

        # 4. Dessin de l'arc (plusieurs épaisseurs pour faire "briller")
        epaisseur = 8 if has_hit else 5
        
        # L'arc principal
        #pygame.draw.arc(surf_slash, couleur, (0, 0, vis_rect.width, vis_rect.height), 
                        #start_angle, end_angle, epaisseur)
        
        # Un deuxième arc plus fin et plus clair pour l'éclat
        #pygame.draw.arc(surf_slash, (200, 240, 255, alpha), (2, 2, vis_rect.width-4, vis_rect.height-4), 
                        #start_angle, end_angle, 2)

        #surface.blit(surf_slash, rect_ecran.topleft)
