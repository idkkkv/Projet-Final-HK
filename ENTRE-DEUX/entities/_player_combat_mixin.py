# ─────────────────────────────────────────────────────────────────────────────
#  PlayerCombatMixin — Combat, encaissement et attaque
# ─────────────────────────────────────────────────────────────────────────────
#
#  Tout ce qui concerne le combat du joueur :
#
#   hit_by_enemy   : encaisser un coup (knockback, invincibilité, -1 PV, son)
#   on_pogo_hit    : rebond vers le haut quand l'attaque-bas touche
#   on_side_hit    : petit recul horizontal sur un coup latéral
#   _gerer_attaque : combo d'attaque (3 coups + attaques descendantes)
#
# ─────────────────────────────────────────────────────────────────────────────

import time

from audio import sound_manager
from settings import (
    KNOCKBACK_PLAYER, INVINCIBLE_DURATION, HP_DISPLAY_DURATION,
    POGO_BOUNCE_VY, ATTACK_DURATION, ATTACK_RECT_W, ATTACK_RECT_H,
    ATTACK_DOWN_W, ATTACK_DOWN_H, VOLUME_ATK,
)


class PlayerCombatMixin:
    """Encaissement de coups et logique d'attaque du joueur."""

    def hit_by_enemy(self, enemy_rect, degats=1):
        """Appelé par systems/combat.py quand un ennemi touche le joueur.

        Effets : recul (knockback), invincibilité courte, -1 PV, son.
        Si PV ≤ 0 → self.dead = True (la boucle de jeu affichera "Game Over").
        """
        
        # Déjà invincible ou mort ? → on ignore ce coup.
        if self.invincible or self.dead:
            return

        # ── Calcul du recul ──
        # On pousse le joueur dans la direction OPPOSÉE à celle de l'ennemi.
        if self.rect.centerx < enemy_rect.centerx:
            # L'ennemi est à ma droite → je recule vers la gauche.
            self.knockback_vx = -KNOCKBACK_PLAYER
        else:
            self.knockback_vx = KNOCKBACK_PLAYER

        # ── Comportement vertical ────────────────────────────────────────
        # AU SOL : petit bond vers le haut pour le feedback "ouch".
        # EN L'AIR (cas typique : on saute SUR un ennemi) : on FORCE la vy
        # vers le BAS pour que le joueur traverse l'ennemi et continue sa
        # chute. Sans ça, même avec la collision désactivée pendant
        # l'invincibilité, certains setups (ennemi qui bouge vers le haut,
        # micro-collisions résiduelles) faisaient flotter le joueur au
        # sommet de l'ennemi pendant toute l'invincibilité.
        if self.on_ground:
            self.vy = -150
        else:
            # Si le joueur tombait déjà → on amplifie un peu pour passer net.
            # Si le joueur montait → on force à descendre quand même.
            self.vy = max(self.vy, 250)

        # On annule un dash en cours : un joueur ne peut pas à la fois
        # dasher (invincible) ET se faire toucher. Cohérence visuelle.
        self.dashing = False

        # Déclenchement de l'invincibilité.
        self.invincible       = True
        self.invincible_timer = INVINCIBLE_DURATION

        self.hp = max(0, self.hp - degats)
        sound_manager.jouer("degat")
        self.show_hp_timer = HP_DISPLAY_DURATION
        #mppp

        if self.hp <= self.max_hp // 2:          # coup "fort" si PV ≤ moitié
            self.hitted_hard   = True
            self.hitted_normal = False
            self.idle_anim_hurt_hard.reset()
        else:
            self.hitted_normal = True
            self.hitted_hard   = False
            self.idle_anim_hurt_normal.reset()

        # Mort ?
        if self.hp <= 0:
            self.dead = True
            sound_manager.jouer("mort")

    def on_pogo_hit(self):
        """Appelé quand l'attaque-bas touche un ennemi → rebond vers le haut.

        C'est le fameux "pogo" de Hollow Knight : frapper vers le bas sur un
        ennemi en l'air permet de rebondir et d'enchaîner les sauts.
        """
        if self.attack_dir == "down":
            self.vy         = POGO_BOUNCE_VY   # impulsion vers le haut
            self.jumps_used = 1                # autorise un double-saut après le pogo

    def on_side_hit(self):
        """Petit recul horizontal quand on touche un ennemi de côté."""
        recul_force = 300  # ajuste cette valeur selon tes préférences
        if self.direction == 1: # si on regarde à droite, on recule à gauche
            self.vx = -recul_force
        else: # Si on regarde à gauche, on recule à droite
            self.vx = recul_force
    # ═════════════════════════════════════════════════════════════════════════
    # 5.  LECTURE DES ENTRÉES (clavier AZERTY + manette PS5)
    # ═════════════════════════════════════════════════════════════════════════
    #
    # Chaque fonction renvoie une valeur simple : un entier (-1/0/+1) pour
    # les axes, un booléen pour les boutons. Ça permet à mouvement() de ne
    # PAS se soucier de savoir si c'est le clavier ou la manette qui joue.

    def _gerer_attaque(self, dt, attack_pressed, ay, sp_attack_pressed):
        """Déclenche et place la hitbox d'attaque.

        - attack_pressed = True → on lance une nouvelle attaque
        - attack_dir = "down" si on appuie vers le bas ET qu'on est en l'air,
                       "side" sinon (attaque devant)
        """
        now = time.time()

        # ── Gating de la compétence ────────────────────────────────────
        # En mode histoire, l'attaque normale (skill_attack) et le pogo
        # (attaque vers le bas en l'air, skill_pogo) sont des compétences
        # à débloquer. En mode éditeur, tout est dispo.
        attaque_dispo = self._skill_unlocked("attack")
        pogo_voulu    = (ay > 0 and not self.on_ground)
        pogo_dispo    = self._skill_unlocked("pogo")

        # On bloque le déclenchement d'une nouvelle attaque tant que la
        # compétence requise n'est pas débloquée. Mais on n'interrompt
        # PAS une attaque déjà en cours (sinon visuels cassés).
        if attack_pressed and not self.attacking:
            if not attaque_dispo:
                attack_pressed = False
            elif pogo_voulu and not pogo_dispo:
                # On a appuyé pour un pogo mais pas débloqué → on ignore
                # (la touche ne déclenche pas l'attaque par défaut).
                attack_pressed = False

        if attack_pressed:
            self._last_f_press_time = now
            if self.attacking and self.combo_step < 3:
                self._combo_queued = True
                
        if not self.on_ground:
            self.anim_finie = (
                (self.combo_step == 0 and self.idle_anim_dodge_atk_3x.done) or
                (self.combo_step == 1 and self.idle_anim_1xjumpatk.done) or
                (self.combo_step == 2 and self.idle_anim_2xjumpatk.done)
            )
        else:
            self.anim_finie = (
                (self.combo_step == 0 and self.idle_anim_dodge_atk_3x.done) or
                (self.combo_step == 1 and self.idle_anim_1xatk.done) or
                (self.combo_step == 2 and self.idle_anim_2xatk_short.done) or
                (self.combo_step == 3 and self.idle_anim_3xatk.done)
            )
        # fin atk
        if self.attacking and self.anim_finie:
            self.just_fallen = False
            if self.combo_step == 0:
                self.idle_anim_dodge_atk_3x.reset()
                self.attacking = False
                self._combo_queued = False
                return
            if self.combo_step == 1:
                self.idle_anim_1xatk.reset()
                self.idle_anim_1xjumpatk.reset()
            if self.combo_step == 2:
                self.idle_anim_2xatk_short.reset()
                self.idle_anim_2xjumpatk.reset()
            elif self.combo_step == 3:
                self.idle_anim_3xatk.reset()

            if self._combo_queued and (now - self._last_f_press_time < self.combo_max_delay):
                self.combo_step = min(self.combo_step + 1, 3)
                self._combo_queued = False
                self.attack_has_hit = False
                self.attack_timer = ATTACK_DURATION 
                sound_manager.jouer("attaque", volume=VOLUME_ATK)
            else:
                # fin combo
                self.attacking = False
                self.combo_step = 0
                self._combo_queued = False

        # pas combo, new atk
        if (attack_pressed or sp_attack_pressed) and not self.attacking:
            self._combo_queued = False
            self.attacking = True
            self.attack_has_hit = False
            self.attack_timer = ATTACK_DURATION
            self.attack_dir = "down" if (ay > 0 and not self.on_ground) else "side"

            if sp_attack_pressed:
                self.combo_step = 0
                self.idle_anim_dodge_atk_3x.reset() 
                sound_manager.jouer("attaque", volume=VOLUME_ATK)

            elif attack_pressed:
                self.combo_step = 1
                if not self.on_ground:
                    self.idle_anim_1xjumpatk.reset()
                    self.idle_anim_2xjumpatk.reset()
                else:
                    self.idle_anim_1xatk.reset()
                    self.idle_anim_2xatk_short.reset()
                    self.idle_anim_3xatk.reset()

                sound_manager.jouer("attaque", volume=VOLUME_ATK)

        # inactif trop longtemps, reset combo
        if not self.attacking and now - self._last_f_press_time > self.combo_max_delay:
            self.combo_step = 0

        # Repositionnement de la hitbox (doit suivre le joueur chaque frame).
        if self.attack_dir == "down":
            # Hitbox carrée collée au-dessous du joueur.
            self.attack_rect.size   = (ATTACK_DOWN_W, ATTACK_DOWN_H)
            self.attack_rect.midtop = (self.rect.centerx, self.rect.bottom)
        else:
            # Hitbox horizontale à gauche ou à droite selon direction.
            self.attack_rect.size = (ATTACK_RECT_W, ATTACK_RECT_H)
            if self.direction == 1:
                self.attack_rect.topleft  = (self.rect.right, self.rect.y + 20)
            else:
                self.attack_rect.topright = (self.rect.left,  self.rect.y + 20)
