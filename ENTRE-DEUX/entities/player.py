# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Joueur (le personnage contrôlé)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Ce fichier contient UNE seule classe : Player.
#  C'est le personnage principal du jeu — celui que le joueur contrôle au
#  clavier ou à la manette. Toutes ses capacités sont gérées ici :
#
#     - se déplacer (Q / D ou joystick)
#     - sauter (Espace / Croix)
#     - DASH  (Shift / L1 / R1)       → foncée horizontale rapide
#     - DOUBLE SAUT (2e Espace en l'air)
#     - ATTAQUER (F / Carré)           → devant, ou vers le bas (S+F en l'air)
#     - POGO (attaque-bas qui touche)  → rebond comme dans Hollow Knight
#     - WALL-SLIDE + WALL-JUMP         → glisser contre un mur et rebondir
#     - COYOTE TIME + JUMP BUFFER      → sauts plus tolérants (voir [D23])
#     - ENCAISSER un coup              → knockback, invincibilité courte, -1 PV
#     - RÉGÉNÉRER                      → récupérer 1 PV quand on reste immobile
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  Une seule instance est créée dans core/game.py :
#        self.joueur = Player(PLAYER_SPAWN)
#
#  Chaque frame, game.py appelle dans l'ordre :
#        self.joueur.mouvement(dt, keys, holes)       ← lit les entrées, bouge
#        ... résolution des collisions par world/collision.py ...
#        self.joueur.post_physics()                   ← corrige contre les murs
#        self.joueur.draw(screen, camera)             ← dessine le sprite
#
#  Quand un ennemi touche le joueur :
#        self.joueur.hit_by_enemy(ennemi.rect)
#
#  Quand l'attaque-bas touche un ennemi (pogo) :
#        self.joueur.on_pogo_hit()
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#  - La vitesse / la hauteur de saut / les dégâts etc. → settings.py
#  - Les TOUCHES  (quelle touche fait quoi)            → core/event_handler.py
#  - Le COMPORTEMENT (logique du saut, du dash...)     → ici, méthode mouvement()
#  - L'ANIMATION (sprites)                             → méthode _charger_frames()
#  - Les CŒURS affichés au-dessus du joueur            → méthode _draw_hearts()
#  - La HITBOX (rectangle de collision)                → hitboxes.json (édité par world/editor.py)
#  - La TAILLE du sprite                               → ctrl+f, self.scale_factor
#  - La VITESSE de marche du sprite                    → ctrl+f, self.idle_anim_walk (+ nb grand, + animation lente)
#  - Ajouter une new animation (à modifier)            → __init__ # ── Animation (sprites de marche) ──
#                                                        draw() # 1. Avance l'animation si on bouge.
#
#  CONCEPTS UTILISÉS (voir docs/DICTIONNAIRE.md) :
#  -----------------------------------------------
#  [D4]  pygame.Rect       — la hitbox est un Rect
#  [D10] dt (delta time)   — on multiplie les vitesses par dt
#  [D11] math.hypot        — (pas utilisé ici mais dans les compagnons)
#  [D22] Machine à états   — self.dashing, self.attacking, self.wall_sliding
#  [D23] Coyote / buffer   — tolérances de saut
#
#  A IMPLEMENTER :
#  ---------------
#  Attaque vers le sol :self.attack_ground = False

# ─────────────────────────────────────────────────────────────────────────────

import pygame
from pygame.locals import *
import math
import time

# On importe settings pour les variables runtime (settings.axis_x, etc.)
import settings
# Et les constantes qu'on utilise souvent (évite d'écrire settings.GRAVITY partout)
from settings import (
    GRAVITY, JUMP_POWER, PLAYER_SPEED,
    PLAYER_W, PLAYER_H,
    ATTACK_DURATION, ATTACK_RECT_W, ATTACK_RECT_H,
    ATTACK_DOWN_W, ATTACK_DOWN_H, POGO_BOUNCE_VY,
    PLAYER_MAX_HP, INVINCIBLE_DURATION, HP_DISPLAY_DURATION,
    REGEN_DELAY, REGEN_INTERVAL,
    KNOCKBACK_PLAYER, KNOCKBACK_DECAY,
    DASH_SPEED, DASH_DURATION, DASH_COOLDOWN,
    DOUBLE_JUMP_POWER, COYOTE_TIME, JUMP_BUFFER,
    WALL_SLIDE_SPEED, WALL_JUMP_VX, WALL_JUMP_VY, WALL_JUMP_LOCK,
    BACK_DODGE_LOCK, BACK_DODGE_INPUT_WINDOW,
    BACK_DODGE_DURATION, BACK_DODGE_SPEED, BACK_DODGE_MOVE_FRACTION,
    DEAD_ZONE, BTN_CROIX, BTN_CARRE, BTN_L1, BTN_R1,
    BLANC, VOLUME_PAS, FPS, PLAYER_RUN_SPEED
)
from utils import find_file
from entities.animation import Animation
from audio import sound_manager
from systems.hitbox_config import get_player_hitbox


# ─── Constantes locales à ce fichier ─────────────────────────────────────────
# Cadence des pas : un son "pas" toutes les STEP_INTERVAL secondes en marche.
# Trop petit → piétinement désagréable. Trop grand → on entend à peine les pas.
STEP_INTERVAL = 0.35


class Player:
    """Le personnage contrôlé par le joueur."""

    # ═════════════════════════════════════════════════════════════════════════
    # 1.  CONSTRUCTION — appelée UNE fois quand on fait Player(...)
    # ═════════════════════════════════════════════════════════════════════════
    #
    # À QUOI SERT __init__ ?                                  voir [D31]
    # ----------------------
    # C'est le « constructeur » : c'est exécuté au moment où on écrit
    # `self.joueur = Player((100, 400))` dans game.py.
    # On y initialise TOUTES les variables de l'objet (self.x, self.hp, ...).
    #
    # Si tu ajoutes une nouvelle variable à Player, pense à lui donner
    # une valeur ICI (sinon tu auras un AttributeError plus tard).

    def __init__(self, pos=(0, 0)):
        # ── Hitbox (rectangle invisible utilisé pour les collisions) ──
        # La hitbox est lue depuis hitboxes.json (éditable dans l'éditeur,
        # touche 6). Si le fichier est vide, on utilise PLAYER_W × PLAYER_H
        # comme valeurs de repli.
        #
        # ox / oy = décalage du sprite à l'intérieur de la hitbox. Ça permet
        # d'avoir un sprite plus grand que la hitbox (le personnage déborde
        # visuellement sans qu'on prenne des coups "dans le vide").
        hb = get_player_hitbox()
        self.hitbox_w  = hb.get("w",  PLAYER_W)
        self.hitbox_h  = hb.get("h",  PLAYER_H)
        self.hitbox_ox = hb.get("ox", 0)
        self.hitbox_oy = hb.get("oy", 0)

        # Le Rect est l'outil pygame qu'on utilisera pour toutes les
        # collisions (sol, murs, ennemis). Voir [D4].
        self.rect    = pygame.Rect(pos[0], pos[1], self.hitbox_w, self.hitbox_h)

        # Position de spawn : mémorisée pour respawn() (après la mort).
        self.spawn_x = pos[0]
        self.spawn_y = pos[1]

        # ── Vitesses & état physique ──
        # vx / vy sont en pixels PAR SECONDE. On les multiplie par dt
        # quand on les applique à rect.x / rect.y (voir [D10]).
        self.vx            = 0
        self.vy            = 0
        self.knockback_vx  = 0.0      # vitesse "poussée" (après avoir pris un coup)
        self.on_ground     = True     # True = pieds au sol
        self.direction     = -1        # 1 = regarde à droite, -1 = à gauche
        self.walking       = False    # True = se déplace horizontalement
        self.running       = False    # True = se déplace assez vite
        self.run_duree     = 0.0      # durée écoulée depuis le début du déplacement rapide (pour l'anim de course)
        self.run_state    = "idle"    # "start", "run" ou "stop" (pour l'anim de course)
        self._last_d_press_time = 0 # pour double clic 
        self._last_q_press_time = 0 # pour double clic 
        self._double_tap_delay = 0.25  # secondes
        self.idle          = (self.vx == 0 and self.vy == 0)     # True = immobile
        self.looking_up    = False    # True = appuie vers le haut

        # ── Constantes physiques (copiées pour autoriser des bonus en jeu) ──
        # On copie les valeurs de settings au lieu de les lire directement,
        # ce qui permettrait dans le futur d'avoir un power-up qui augmente
        # la vitesse du joueur sans toucher à settings.
        self.gravity        = GRAVITY
        self.puissance_saut = JUMP_POWER
        self.speed          = PLAYER_SPEED
        self.run_speed      = PLAYER_RUN_SPEED

        # ── Combat ──
        self.attack_has_hit   = False                 # True si on a touché un ennemi durant l'attaque actuelle
        self.attacking        = False                 # True pendant une attaque
        self.attack_dir       = "side"                # "side" ou "down"
        self.attack_rect      = pygame.Rect(0, 0, ATTACK_RECT_W, ATTACK_RECT_H)
        self.attack_timer     = 0                     # temps restant de l'attaque
        # Drapeau qui assure qu'un pogo ne se déclenche qu'une fois par attaque.
        self._attack_buffered = False
        self.attack_ground = False                    # True si l'attaque a été déclenchée vers le sol

        # ── Vie & dégâts ──
        self.max_hp           = PLAYER_MAX_HP
        self.hp               = self.max_hp
        self.dead             = False
        self.invincible       = False
        self.invincible_timer = 0.0      # secondes restantes d'invincibilité
        self.show_hp_timer    = 0.0      # secondes restantes d'affichage des cœurs

        # ── Régénération passive ──
        # Le joueur récupère 1 PV s'il reste TOTALEMENT immobile au sol
        # pendant REGEN_DELAY secondes, puis 1 de plus toutes les REGEN_INTERVAL.
        # Tout input ou dégât remet _idle_timer à 0.
        self._idle_timer      = 0.0
        self.regen_active     = False    # signalé au HUD pour afficher une icône

        # ── Capacités Hollow Knight ──
        self.dashing          = False    # True pendant un dash
        self.dash_timer       = 0.0
        self.dash_cooldown    = 0.0      # délai avant le prochain dash
        self.dash_dir         = 1        # direction du dash en cours
        self.jumps_used       = 0        # 0 = aucun, 1 = saut sol, 2 = double saut
        self.coyote_timer     = 0.0      # > 0 → on peut encore sauter "depuis le sol" [D23]
        self.jump_buffer      = 0.0      # > 0 → un saut a été pré-bufferisé [D23]
        self.against_wall     = 0        # 0=rien, -1=mur à gauche, +1=mur à droite
        self.wall_lock_timer  = 0.0      # ignore l'input opposé après un wall-jump
        self.wall_sliding     = False    # True = glisse contre un mur

        # ── Détection des appuis ("fronts montants") ──
        # On veut détecter le moment où on APPUIE sur une touche (pas quand on
        # la maintient). Pour ça, on compare "était-elle pressée la frame
        # précédente ?" avec "est-elle pressée maintenant ?".
        #   - True cette frame + False la précédente  → front montant (déclenche)
        #   - True des deux côtés                     → touche maintenue (ignore)
        self._prev_jump   = False
        self._prev_dash   = False
        self._prev_attack = False

        # ── Animation (sprites) ──
        # 1. On charge les frames de chaque animation dans des listes.
        # basiques
        frames_marche = self._charger_frames("shewalks_0", 24)
        frames_run_start = self._charger_frames("sherunsstart_0", 2)
        frames_run = self._charger_frames("sherun_0", 20)
        frames_run_stop = self._charger_frames("sherunsstop_0", 15)
        frames_run_turn = self._charger_frames("sherunsturn_00", 8)
        frames_idle = self._charger_frames("sheidle_00", 10)

        # sauts
        frames_idle_jump = self._charger_frames("shejumps__0", 24)
        duree_saut = (2 * abs(JUMP_POWER)) / GRAVITY
        img_duration_saut = (duree_saut * FPS) / len(frames_idle_jump)
        print(len(frames_idle_jump))

        frames_idle_double_jump = self._charger_frames("shejumpsvertical_00", 7)
        frames_idle_double_jump_fwd = self._charger_frames("shejumpsfoward_00", 7)

        # Dash : avant (slide_merged 17 frames) et arrière (back dodge fx 20 frames)
        frames_dash_fwd  = self._charger_frames("sheslide_00",     17)
        frames_dash_back = self._charger_frames("shebackdodge_00", 20)

        # Aerial dash (dash dans les airs) : 12 frames perso + FX visuels au
        # point de départ (effet de téléportation/après-image).
        frames_aerial_dash       = self._charger_frames("sheaerialdash_00",         6)
        frames_aerial_dash_smoke = self._charger_frames("sheaerialdash_smoke_00",   6)
        frames_aerial_dash_fx    = self._charger_frames("sheaerialdash_fx_00",      5)

        self.scale_factor = 1.5
        self.sprite_w  = frames_marche[0].get_width()
        self.sprite_h  = frames_marche[0].get_height()
        self.sprite_rescaled = (int(self.sprite_w * self.scale_factor), int(self.sprite_h * self.scale_factor))
        self.sprite_scaled_prop = pygame.transform.smoothscale(frames_marche[0], self.sprite_rescaled)

        # ── VITESSE des anims (img_dur = nb de frames moteur par image) ──
        # Plus le chiffre est GRAND, plus l'anim est LENTE.
        # Modifie ces 2 valeurs pour ajuster rapidement le rythme :
        #   idle_anim_walk : 4-6 = naturel, 2 = course rapide
        #   idle_anim_idle : 8-12 = posé, 4-5 = nerveux

        # 3. Animation pour chaque animation du joueur
        # basiques
        self.idle_anim_walk = Animation(frames_marche, img_dur=4, loop=True)
        self.idle_anim_run_start = Animation(frames_run_start, img_dur=10, loop=False)
        self.idle_anim_run = Animation(frames_run, img_dur=2, loop=True)
        self.idle_anim_run_stop = Animation(frames_run_stop, img_dur=3, loop=False)
        self.idle_anim_run_turn = Animation(frames_run_turn, img_dur=5, loop= False)
        self.idle_anim_idle = Animation(frames_idle, img_dur=10, loop=True)

        # sauts
        self.idle_anim_jump = Animation(frames_idle_jump, img_dur=img_duration_saut, loop=True)
        self.idle_anim_double_jump = Animation(frames_idle_double_jump, img_dur=5, loop=False)
        self.idle_anim_double_jump_fwd = Animation(frames_idle_double_jump_fwd, img_dur=5, loop=False)

        # Dash forward / back dodge : on lit DASH_DURATION/FPS pour caler la vitesse
        # de défilement à la durée du dash (sinon l'anim finit avant ou après).
        img_dur_dash_fwd     = max(1, int((DASH_DURATION       * FPS) / len(frames_dash_fwd)))
        # Back dodge : on cale sur sa propre durée (1.25s) pour avoir ~5 fm
        # par image et que les 20 frames soient toutes bien visibles.
        img_dur_dash_back    = max(1, int((BACK_DODGE_DURATION  * FPS) / len(frames_dash_back)))
        img_dur_aerial_dash  = max(1, int((DASH_DURATION        * FPS) / len(frames_aerial_dash)))
        self.idle_anim_dash_fwd     = Animation(frames_dash_fwd,    img_dur=img_dur_dash_fwd,    loop=False)
        self.idle_anim_dash_back    = Animation(frames_dash_back,   img_dur=img_dur_dash_back,   loop=False)
        self.idle_anim_aerial_dash  = Animation(frames_aerial_dash, img_dur=img_dur_aerial_dash, loop=False)

        # Effets visuels du dash aérien (rejoués UNE fois au point de départ).
        self.aerial_smoke_anim = Animation(frames_aerial_dash_smoke, img_dur=5, loop=False)
        self.aerial_fx_anim    = Animation(frames_aerial_dash_fx,    img_dur=6, loop=False)
        # Position où dessiner les effets (set au déclenchement, None sinon).
        self.aerial_smoke_pos = None
        self.aerial_fx_pos    = None

        # Drapeau d'état : True = back dodge en cours, False = dash avant
        self.dash_back = False

        # Verrou de direction après un back dodge.
        # > 0 → on BLOQUE le retournement du regard. Le perso continue de
        # regarder l'ennemi (vers l'avant) même si le joueur maintient la
        # touche opposée. À 0, comportement normal reprend.
        # → décrémenté dans _tick_state_timers, armé dans _declencher_dash
        #   quand on déclenche un back dodge.
        self.back_dodge_lock_timer = 0.0

        # Fenêtre de tolérance pour déclencher un back dodge.
        # > 0 → si Shift est pressé maintenant, c'est un back dodge même si
        # le joueur n'appuie plus sur la direction opposée. Armé chaque fois
        # que le joueur appuie sur direction opposée à son regard.
        self._back_dodge_buffer = 0.0
        # Direction face à conserver si le back dodge se déclenche pendant
        # le buffer (mémorisée juste avant le retournement).
        self._pre_back_dodge_facing = self.direction

        self.step_timer = STEP_INTERVAL

        # ── Cache de la police (créée à la 1re utilisation dans _draw_hearts) ──
        self._heart_font = None

        # ── Mémoire pour post_physics() ──
        # On mémorise ici la position X qu'on VOULAIT atteindre cette frame.
        # Après la résolution des collisions, si rect.x est différent de
        # _intended_x, c'est qu'un mur a poussé le joueur → on active le
        # wall-slide. Voir post_physics() pour le détail.
        #
        # On l'initialise dès __init__ pouself.frames_idle_jumpup.update()r éviter d'avoir à utiliser
        # getattr() plus tard (plus lisible).
        self._intended_x = self.rect.x

    # ═════════════════════════════════════════════════════════════════════════
    # 2.  CHARGEMENT DES SPRITES DE MARCHE
    # ═════════════════════════════════════════════════════════════════════════
    #
    # On cherche x frames nommées file (sheshejumpsvertical_00 par ex) ... Sprite Sheet Frame 0024.png.
    # Si elles ne sont pas toutes là, on se rabat sur player_idle.png.
    # Si même ce fichier manque, on crée un rectangle rose vif pour que le
    # jeu puisse au moins démarrer (et qu'on voie tout de suite le problème).

    def _charger_frames(self, file, x, start = 1):
        """Charge les x frames, avec repli si des fichiers manquent."""
        frames = []
        for i in range(start, x+1):
            try:
                frames.append(pygame.image.load(find_file(f"{file}{i}.png")))
            except FileNotFoundError:
                print(f"Frame manquante : {file}{i}.png")
                # Dès qu'une frame manque, on arrête (on garde celles qu'on a).
                break

        # Cas 1 : on a trouvé au moins une frame → on la/les utilise.
        if frames:
            return frames

        # Cas 2 : aucune frame → on essaie player_idle.png.
        try:
            return [pygame.image.load(find_file("player_idle.png"))]
        except FileNotFoundError:
            # Cas 3 : même ça manque → carré rose (sprite de secours).
            placeholder = pygame.Surface((PLAYER_W, PLAYER_H))
            placeholder.fill((255, 0, 200))
            return [placeholder]

    # ═════════════════════════════════════════════════════════════════════════
    # 3.  CYCLE DE VIE (respawn, rechargement de la hitbox)
    # ═════════════════════════════════════════════════════════════════════════

    def respawn(self):
        """Fait réapparaître le joueur à son point de spawn avec PV pleins.

        Utilisé quand :
          - le joueur meurt (écran "Game Over" puis respawn)
          - on change de scène et on veut recaler le joueur proprement
        """
        self.rect.x       = self.spawn_x
        self.rect.y       = self.spawn_y
        self.vx           = 0
        self.vy           = 0
        self.knockback_vx = 0
        self.on_ground    = False
        self.hp           = self.max_hp
        self.dead         = False
        self.dashing      = False
        self.running      = False
        self.dash_timer   = 0.0
        self.jumps_used   = 0
        self._idle_timer  = 0.0
        self.regen_active = False

    def reload_hitbox(self):
        """Relit la hitbox depuis hitboxes.json.

        Utilisé quand tu édites la hitbox du joueur dans le mode 6 de
        l'éditeur : on recharge la nouvelle taille SANS replacer le joueur
        (on garde le centre-bas pour qu'il reste au sol comme avant).
        """
        cx     = self.rect.centerx
        bottom = self.rect.bottom
        hb = get_player_hitbox()
        self.hitbox_w  = hb.get("w",  PLAYER_W)
        self.hitbox_h  = hb.get("h",  PLAYER_H)
        self.hitbox_ox = hb.get("ox", 0)
        self.hitbox_oy = hb.get("oy", 0)
        self.rect.size      = (self.hitbox_w, self.hitbox_h)
        self.rect.midbottom = (cx, bottom)

    # ═════════════════════════════════════════════════════════════════════════
    # 4.  DÉGÂTS / COMBAT (événements ponctuels)
    # ═════════════════════════════════════════════════════════════════════════

    def hit_by_enemy(self, enemy_rect):
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
        # Petit bond vertical pour donner un effet "ouch" dynamique.
        self.vy = -150

        # On annule un dash en cours : un joueur ne peut pas à la fois
        # dasher (invincible) ET se faire toucher. Cohérence visuelle.
        self.dashing = False

        # Déclenchement de l'invincibilité.
        self.invincible       = True
        self.invincible_timer = INVINCIBLE_DURATION

        # Perte de PV et affichage des cœurs.
        self.hp -= 1
        sound_manager.jouer("degat")
        self.show_hp_timer = HP_DISPLAY_DURATION

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

    def _input_axis_x(self, keys):
        """Renvoie -1 (gauche), 0 (rien) ou +1 (droite)."""
        # Priorité au joystick s'il est sorti de sa zone morte.
        if abs(settings.axis_x) > DEAD_ZONE:
            if settings.axis_x < 0:
                return -1
            else:
                return 1
        # Sinon, on lit le clavier AZERTY (Q/D).
        if keys[K_d]:
            return 1
        if keys[K_q]:
            return -1
        return 0

    def _input_axis_y(self, keys):
        """Renvoie -1 (haut), 0 ou +1 (bas)."""
        if abs(settings.axis_y) > DEAD_ZONE:
            if settings.axis_y < 0:
                return -1
            else:
                return 1
        if keys[K_z] or keys[K_UP]:
            return -1
        if keys[K_s] or keys[K_DOWN]:
            return 1
        return 0

    def _input_jump(self, keys):
        """True si Espace est enfoncée OU si Croix (PS5) l'est."""
        if keys[K_SPACE]:
            return True
        if settings.manette and settings.manette.get_button(BTN_CROIX):
            return True
        return False

    def _input_attack(self, keys):
        """True si F est enfoncée OU si Carré l'est."""
        if keys[K_f]:
            return True
        if settings.manette and settings.manette.get_button(BTN_CARRE):
            return True
        return False

    def _input_dash(self, keys):
        """True si Shift (gauche ou droit) est enfoncée OU L1/R1."""
        if keys[K_LSHIFT] or keys[K_RSHIFT]:
            return True
        if settings.manette:
            # On accepte L1 OU R1 (certains joueurs préfèrent l'une ou l'autre).
            if settings.manette.get_button(BTN_L1) or settings.manette.get_button(BTN_R1):
                return True
        return False

    def _input_run(self, keys):
        """True si la touche de course est enfoncée (ex: Maj gauche)."""
        now = time.time()
        d_pressed = keys[K_d] and not getattr(self, "_prev_d", False)
        q_pressed = keys[K_q] and not getattr(self, "_prev_q", False)
        self._prev_d = keys[K_d]
        self._prev_q = keys[K_q]

        if d_pressed or q_pressed:
            if now - self._last_d_press_time < self._double_tap_delay:
                self.running = True
            self._last_d_press_time = now
            self._last_q_press_time = now

        # stop si plus de touche
        if not keys[K_d] and not keys[K_q]:
            self.running = False

        return self.running

    # ═════════════════════════════════════════════════════════════════════════
    # 6.  MOUVEMENT PRINCIPAL — appelé CHAQUE FRAME par game.py
    # ═════════════════════════════════════════════════════════════════════════
    #
    # C'est LE point d'entrée de la logique du joueur. Les étapes sont
    # numérotées pour que tu puisses suivre dans l'ordre. En résumé :
    #
    #   1. Lire les entrées
    #   2. Décrémenter les timers
    #   3. Gérer le wall-lock (recul du wall-jump)
    #   4. Calculer la vitesse horizontale
    #   5. Appliquer le knockback
    #   6. Regard vers le haut → montrer les cœurs
    #   7. Saut (avec coyote time et jump buffer)
    #   8. Dash
    #   9. Gravité
    #  10. Détecter le wall-slide
    #  11. Appliquer le déplacement (rect.x += vx*dt)
    #  12. Collisions avec le sol et le plafond
    #  13. Reset des sauts au sol
    #  14. Attaque (hitbox)
    #  15. Son de pas
    #  16. Timers de combat (invincibilité, attaque)
    #  17. Régénération passive
    #
    # Les collisions avec les plateformes sont gérées APRÈS par collision.py.

    def mouvement(self, dt, keys, holes=None):
        # On mémorise la direction du regard AVANT de lire les inputs.
        # Sert pour distinguer dash AVANT (input dans le sens du regard ou
        # rien) vs BACK DODGE (input opposé au regard) — sinon, étape 4
        # remplace self.direction par ax et on ne saurait plus.
        facing_before = self.direction

        # ── 1. Lecture des entrées ────────────────────────────────────────
        ax = self._input_axis_x(keys)          # -1, 0, +1
        ay = self._input_axis_y(keys)
        jump_held   = self._input_jump(keys)
        attack_held = self._input_attack(keys)
        dash_held   = self._input_dash(keys)
        run_held = self._input_run(keys)

        # Fronts montants : "juste pressé CE frame-ci" (voir __init__ pour
        # l'explication). On met à jour les mémoires _prev_* APRÈS avoir
        # calculé les fronts, sinon on écrase la valeur précédente trop tôt.
        jump_pressed   = jump_held   and not self._prev_jump
        attack_pressed = attack_held and not self._prev_attack
        dash_pressed   = dash_held   and not self._prev_dash
        self.prev_dir = self.direction
        self._prev_jump   = jump_held
        self._prev_attack = attack_held
        self._prev_dash   = dash_held

        # ── 1b. Détection back dodge (buffer de tolérance) ────────────────
        # Si le joueur appuie sur la direction opposée à son regard, on
        # arme un buffer : pendant BACK_DODGE_INPUT_WINDOW secondes, un
        # appui Shift sera traité comme back dodge même si le joueur a
        # déjà commencé à se retourner. Évite d'avoir à presser pile au
        # même frame Shift+direction-opposée.
        if ax != 0 and ax != facing_before:
            # 1er frame de l'input opposé → on mémorise le regard d'avant.
            # Sinon (déjà dans le buffer), on garde la mémoire et on
            # rafraîchit juste le timer.
            if self._back_dodge_buffer <= 0:
                self._pre_back_dodge_facing = facing_before
            self._back_dodge_buffer = BACK_DODGE_INPUT_WINDOW

        # ── 2. Décrémentation des timers d'état ───────────────────────────
        self._tick_state_timers(dt)

        # ── 3. Wall-lock : après un wall-jump, on ignore l'input opposé ──
        # Pourquoi ? Le joueur vient de se propulser dans un sens ; s'il
        # maintient la direction vers le mur, il reviendrait coller dessus
        # tout de suite. On lui "refuse" cette direction pendant WALL_JUMP_LOCK.
        if self.wall_lock_timer > 0:
            # ax * self.direction < 0 = l'input va DANS L'AUTRE SENS que la
            # direction actuelle (celle donnée par le wall-jump).
            if ax * self.direction < 0:
                ax = 0

        # ── 4. Calcul de la vitesse horizontale ───────────────────────────

        if self.dashing:
            # Pendant un dash, la vitesse est fixée (ignore l'input).
            # Back dodge : vitesse réduite + arrêt du mouvement pendant la
            # phase de récupération (frames 14-20 = perso se relève, ne
            # doit plus reculer physiquement).
            if self.dash_back:
                progress = 1.0 - (self.dash_timer / BACK_DODGE_DURATION)
                if progress >= BACK_DODGE_MOVE_FRACTION:
                    # Phase recovery : le perso reste sur place, l'anim
                    # continue (touche la tête / se relève).
                    self.vx = 0
                else:
                    # Phase recoil : le perso recule.
                    self.vx = BACK_DODGE_SPEED * self.dash_dir
            else:
                self.vx = DASH_SPEED * self.dash_dir
            self.walking = False
            self.idle = False
        else:
            if self.running :
                if self.run_state == "idle":
                    self.run_state = "start"
                    self.idle_anim_run_start.reset()

                # animation run_turn
                if ax != 0 and ax != self.prev_dir and self.prev_dir != 0 :
                    self.run_state = "turn"
                    self.idle_anim_run_turn.reset()
                    self.direction = ax

                self.vx = ax * self.run_speed
                self.run_duree += dt
            else:
                if self.run_state in ["run", "start"]:
                    self.run_state = "stop"
                    self.idle_anim_run_stop.reset()
                self.vx = ax * self.speed

            self.walking = (ax != 0)
            # On ne change la direction "regardée" que si on bouge vraiment
            # ET que le verrou back-dodge n'est PAS actif. Sinon le perso
            # garde son regard vers l'ennemi pendant la fenêtre d'esquive.
            if ax != 0 and self.back_dodge_lock_timer <= 0:
                self.direction = ax

        # Si on ne fait rien, on prend l'animation idle
        if not self.walking and not self.dashing:
            self.idle_anim_idle

        # ── 5. Knockback (recul après avoir pris un coup) ─────────────────
        # On l'ajoute à la vitesse courante, puis on l'amortit (× 0.85).
        # Quand il devient tout petit, on le met à zéro "net".
        self.vx += self.knockback_vx
        if abs(self.knockback_vx) > 1:
            self.knockback_vx *= KNOCKBACK_DECAY
        else:
            self.knockback_vx = 0

        # ── 6. Regard vers le haut → afficher les cœurs ────────────────────
        # Dans Hollow Knight, regarder vers le haut affiche l'état. On fait
        # pareil : on reset le timer → les cœurs restent visibles tant qu'on
        # regarde en l'air.
        self.looking_up = (ay < 0)
        if self.looking_up:
            self.show_hp_timer = HP_DISPLAY_DURATION

        # ── 7. Saut (jump buffer + coyote + double-saut + wall-jump) ──────
        # Si on vient d'appuyer sur saut : on "mémorise" l'appui pendant
        # JUMP_BUFFER secondes. À chaque frame, on retente de sauter tant
        # que le buffer est actif. C'est ce qui rend les sauts "généreux".
        if jump_pressed:
            self.jump_buffer = JUMP_BUFFER

        if self.jump_buffer > 0:
            if self._tenter_saut():
                # Saut réussi → on consomme le buffer.
                self.jump_buffer = 0.0
                self.idle_anim_jump.frame = 0
                # PRIORITÉ DU SAUT SUR LE DASH : si on était en plein dash
                # (au sol ou aérien) au moment de l'appui Espace, on coupe
                # le dash net pour laisser le saut prendre effet. Sinon vy
                # serait écrasé à 0 par l'étape 9 (gravité = 0 pendant dash)
                # et l'impulsion du saut serait perdue → le perso roulerait
                # sans monter.
                if self.dashing:
                    self.dashing    = False
                    self.dash_timer = 0.0

        # ── 8. Dash ───────────────────────────────────────────────────────
        if dash_pressed and self.dash_cooldown <= 0 and not self.dashing:
            self._declencher_dash(ax, facing_before)

        # ── 9. Gravité ────────────────────────────────────────────────────
        if not self.dashing:
            self.vy += self.gravity * dt
            # Wall-slide → on plafonne la vitesse de chute.
            if self.wall_sliding and self.vy > WALL_SLIDE_SPEED:
                self.vy = WALL_SLIDE_SPEED
        else:
            # Pendant un dash, on flotte à la même hauteur (pas de gravité).
            self.vy = 0

        # ── 10. Détection du wall-slide ────────────────────────────────────
        # On glisse seulement si :
        #   - on est EN L'AIR
        #   - on est COLLÉ à un mur (against_wall calculé dans post_physics)
        #   - on APPUIE vers ce mur (sinon on décroche)
        self.wall_sliding = (
            not self.on_ground
            and self.against_wall != 0
            and ax == self.against_wall
        )

        # ── 11. Application du déplacement ────────────────────────────────
        # int(...) sert à convertir la valeur en entier (rect ne gère que
        # des entiers). Les pertes de précision sont négligeables à 80 FPS.
        was_on_ground = self.on_ground
        self.rect.x += int(self.vx * dt)
        self.rect.y += int(self.vy * dt)

        # On mémorise la X qu'on "voulait" atteindre. Si les collisions vont
        # nous pousser, on détectera la différence dans post_physics().
        self._intended_x = self.rect.x

        # ── 12. Sol et plafond (ignorés si on est au-dessus d'un trou) ────
        in_hole = self._dans_un_trou(holes)

        if not in_hole and self.rect.bottom > settings.GROUND_Y:
            self.rect.bottom = settings.GROUND_Y
            self.vy          = 0
            self.on_ground   = True
        if not in_hole and self.rect.top < settings.CEILING_Y:
            self.rect.top = settings.CEILING_Y
            self.vy       = 0

        # ── 13. Au contact du sol → reset des sauts ───────────────────────
        if self.on_ground:
            self.jumps_used   = 0
            self.coyote_timer = COYOTE_TIME
            self.against_wall = 0
            self.wall_sliding = False
        elif was_on_ground:
            # Frame où on vient de quitter le sol (marche dans le vide,
            # sauté, tombé). On lance le coyote timer : on peut encore
            # sauter "comme si on était au sol" pendant COYOTE_TIME.
            self.coyote_timer = COYOTE_TIME

        # ── 14. Attaque ───────────────────────────────────────────────────
        self._gerer_attaque(dt, attack_pressed, ay)

        # ── 15. Sons de pas ───────────────────────────────────────────────
        self._gerer_son_pas(dt)

        # ── 16. Timers de combat (invincibilité, durée de l'attaque) ──────
        self._tick_combat_timers(dt)

        # ── 17. Régénération passive ──────────────────────────────────────
        self._gerer_regen(dt, ax, ay, jump_held, attack_held, dash_held)

    def post_physics(self):
        """Appelé par game.py APRÈS la résolution des collisions.

        Pourquoi ? Pendant mouvement(), on a calculé la position qu'on
        VOULAIT (_intended_x). Ensuite, collision.py a peut-être poussé
        le joueur pour l'empêcher de rentrer dans un mur. En comparant
        la position VOULUE et la position RÉELLE, on déduit s'il y a un
        mur à gauche ou à droite → utile pour activer le wall-slide.
        """
        # push_dx > 0 : la collision a poussé vers la droite → mur à gauche
        # push_dx < 0 : la collision a poussé vers la gauche → mur à droite
        # push_dx ≈ 0 : pas de mur
        push_dx = self.rect.x - self._intended_x

        if push_dx > 1:
            self.against_wall = -1
        elif push_dx < -1:
            self.against_wall = 1
        else:
            self.against_wall = 0

    # ═════════════════════════════════════════════════════════════════════════
    # 7.  SOUS-ROUTINES DE mouvement()
    # ═════════════════════════════════════════════════════════════════════════

    def _tick_state_timers(self, dt):
        """Décrémente les timers liés aux capacités (dash, coyote, buffer)."""
        # Cooldown du dash.
        if self.dash_cooldown > 0:
            self.dash_cooldown -= dt

        # Coyote timer : seulement quand on est en l'air (pas au sol).
        if self.coyote_timer > 0 and not self.on_ground:
            self.coyote_timer -= dt

        # Jump buffer.
        if self.jump_buffer > 0:
            self.jump_buffer -= dt

        # Lock après wall-jump.
        if self.wall_lock_timer > 0:
            self.wall_lock_timer -= dt

        # Lock du regard après un back dodge.
        if self.back_dodge_lock_timer > 0:
            self.back_dodge_lock_timer -= dt

        # Buffer de tolérance pour déclencher un back dodge.
        if self._back_dodge_buffer > 0:
            self._back_dodge_buffer -= dt

        # Durée du dash en cours.
        if self.dashing:
            self.dash_timer -= dt
            if self.dash_timer <= 0:
                self.dashing = False

    def _tick_combat_timers(self, dt):
        """Décrémente les timers liés à l'invincibilité et l'attaque."""
        if self.invincible:
            self.invincible_timer -= dt
            if self.invincible_timer <= 0:
                self.invincible = False

        if self.show_hp_timer > 0:
            self.show_hp_timer -= dt

        if self.attacking:
            self.attack_timer -= dt
            if self.attack_timer <= 0:
                self.attacking        = False
                self._attack_buffered = False

    def _tenter_saut(self):
        """Tente un saut. Renvoie True si ça a réussi.

        Ordre de priorité :
            1. Saut au sol (ou coyote time actif)
            2. Wall-jump (si collé à un mur en l'air)
            3. Double-saut (si on a encore un saut dispo)
        """
        # 1. Saut depuis le sol (ou coyote).
        if self.on_ground or self.coyote_timer > 0:
            self.vy           = -self.puissance_saut
            self.on_ground    = False
            self.coyote_timer = 0
            self.jumps_used   = 1
            sound_manager.jouer("saut", volume=0.7)
            return True

        # 2. Wall-jump : contre un mur, en l'air.
        if self.against_wall != 0 and not self.on_ground:
            self.vy              = WALL_JUMP_VY
            self.vx              = -self.against_wall * WALL_JUMP_VX
            self.direction       = -self.against_wall
            self.wall_lock_timer = WALL_JUMP_LOCK
            self.jumps_used      = 1
            self.wall_sliding    = False
            sound_manager.jouer("saut", volume=0.7)
            return True

        # 3. Double-saut.
        if self.jumps_used < 2:
            self.vy         = -DOUBLE_JUMP_POWER
            self.jumps_used = 2
            # On retient si le joueur tenait une direction (Q ou D / stick)
            self.double_jump_forward = (self.vx != 0)
            if self.double_jump_forward:
                self.idle_anim_double_jump_fwd.reset()
            else:
                self.idle_anim_double_jump.reset()
            sound_manager.jouer("saut", volume=0.7)
            return True



    def _declencher_dash(self, ax, facing_before):
        """Démarre un dash. Choisit AVANT (slide) ou ARRIÈRE (back dodge).

        Règle :
          - Buffer back dodge actif (joueur a appuyé sur direction opposée
            dans les BACK_DODGE_INPUT_WINDOW dernières secondes) → BACK DODGE
          - ax opposé au regard ACTUEL                            → BACK DODGE
          - sinon (ax == 0 ou ax == regard)                       → DASH AVANT

        Le buffer permet de NE PAS avoir à presser pile en même temps
        Shift + direction-opposée : on tolère un décalage de 250 ms.
        """
        # Détection back dodge : soit buffer actif, soit input opposé MAINTENANT.
        in_buffer = self._back_dodge_buffer > 0
        opposite_now = (ax != 0 and ax != facing_before)

        if in_buffer or opposite_now:
            # BACK DODGE
            # Le regard à conserver = celui mémorisé au début du buffer
            # (sinon on prend facing_before qui peut déjà avoir tourné).
            original_facing = self._pre_back_dodge_facing if in_buffer else facing_before
            self.dash_back = True
            # Direction du dash : la touche pressée maintenant si dispo,
            # sinon l'inverse de l'ancien regard (recule par défaut).
            self.dash_dir  = ax if ax != 0 else -original_facing
            self.direction = original_facing            # garde le regard avant
            self.back_dodge_lock_timer = BACK_DODGE_LOCK
            self._back_dodge_buffer    = 0.0            # consomme le buffer
            self.idle_anim_dash_back.reset()
        else:
            # DASH AVANT
            self.dash_back = False
            self.dash_dir  = ax if ax != 0 else facing_before
            self.direction = self.dash_dir
            self.idle_anim_dash_fwd.reset()
            self.idle_anim_aerial_dash.reset()

        self.dashing       = True
        # Durée plus longue pour back dodge (anim de 20 frames à voir)
        self.dash_timer    = BACK_DODGE_DURATION if self.dash_back else DASH_DURATION
        self.dash_cooldown = DASH_COOLDOWN

        # ── Effets visuels du dash AÉRIEN ──────────────────────────────
        # Quand on dash en l'air (forward), on plante 2 effets au POINT DE
        # DÉPART qui restent là et se dissipent : effet "téléportation".
        #   - smoke : nuage de fumée au sol/à hauteur des pieds
        #   - fx    : silhouette résiduelle (after-image) à hauteur du perso
        # Le back dodge n'utilise PAS ces FX (sa propre anim contient déjà
        # les effets de mouvement).
        if not self.on_ground and not self.dash_back:
            # Les 2 effets sont CENTRÉS sur le perso (même point que centery).
            # Comme ça smoke + fx + perso s'alignent parfaitement à la même
            # hauteur quand le perso s'envole — effet "téléportation propre".
            center = (self.rect.centerx, self.rect.centery)
            self.aerial_smoke_pos = center
            self.aerial_fx_pos    = center
            self.aerial_smoke_anim.reset()
            self.aerial_fx_anim.reset()

        sound_manager.jouer("saut", volume=0.5)

    def _dans_un_trou(self, holes):
        """Renvoie True si la hitbox chevauche l'un des trous passés."""
        if not holes:
            return False
        # On parcourt chaque trou un par un. Dès qu'on trouve une intersection,
        # on renvoie True tout de suite (pas besoin de tester les suivants).
        for trou in holes:
            if self.rect.colliderect(trou):
                return True
        return False

    def _gerer_attaque(self, dt, attack_pressed, ay):
        """Déclenche et place la hitbox d'attaque.

        - attack_pressed = True → on lance une nouvelle attaque
        - attack_dir = "down" si on appuie vers le bas ET qu'on est en l'air,
                       "side" sinon (attaque devant)
        """
        # Déclenchement.
        if attack_pressed and not self.attacking:
            self.attacking        = True
            self.attack_has_hit   = False 
            self.attack_timer     = ATTACK_DURATION
            self._attack_buffered = True
            # Attaque vers le bas possible UNIQUEMENT en l'air (comme dans HK).
            if ay > 0 and not self.on_ground:
                self.attack_dir = "down"
            else:
                self.attack_dir = "side"
            sound_manager.jouer("attaque")

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

    def _gerer_son_pas(self, dt):
        """Joue un son "pas" à intervalles réguliers quand on marche au sol."""
        # On veut un son uniquement si on bouge vraiment (|vx| > 10) et qu'on
        # est au sol. abs(...) donne la valeur absolue.
        if self.on_ground and abs(self.vx) > 10 and not self.dashing:
            self.step_timer -= dt
            if self.step_timer <= 0:
                sound_manager.jouer("pas", volume=VOLUME_PAS)
                self.step_timer = STEP_INTERVAL
        else:
            # Arrête tout son de pas en cours (ex. passage en saut).
            self.step_timer = 0.2
            sound_manager.arreter("pas")

    def _gerer_regen(self, dt, ax, ay, jump_held, attack_held, dash_held):
        """Régénère 1 PV quand le joueur est parfaitement immobile au sol.

        Règle : il faut rester inactif pendant REGEN_DELAY (1.5 s) pour le
        premier PV, puis 1 PV de plus toutes les REGEN_INTERVAL (1 s).
        La moindre action remet le compteur à zéro.
        """
        # On vérifie TOUTES les conditions : si une seule est fausse,
        # le joueur n'est pas considéré comme immobile.
        immobile_au_sol = (
            self.on_ground
            and ax == 0 and ay == 0
            and not jump_held and not attack_held and not dash_held
            and not self.attacking
            and not self.invincible
            and not self.dashing
            and abs(self.vx) < 5
            and self.knockback_vx == 0
        )

        # Pas immobile OU PV déjà plein → on reset et on sort.
        if not immobile_au_sol or self.hp >= self.max_hp:
            self._idle_timer  = 0.0
            self.regen_active = False
            return

        # Immobile : on avance le compteur.
        self._idle_timer += dt
        self.regen_active = True

        # Seuil atteint → on récupère 1 PV et on "consomme" REGEN_INTERVAL
        # du timer (ainsi le 2e PV arrive pile 1 seconde après le 1er).
        if self._idle_timer >= REGEN_DELAY:
            self.hp            = min(self.max_hp, self.hp + 1)
            self.show_hp_timer = HP_DISPLAY_DURATION
            self._idle_timer  -= REGEN_INTERVAL
            sound_manager.jouer("ui_select", volume=0.25)   # petit "tic" doux

    # ═════════════════════════════════════════════════════════════════════════
    # 8.  RENDU (dessin du joueur à l'écran)
    # ═════════════════════════════════════════════════════════════════════════
    #
    # Appelé par game.py dans _dessiner_monde(). On dessine :
    #   - le sprite de marche (avec miroir si on regarde à gauche)
    #   - la hitbox d'attaque en blanc (pendant une attaque)
    #   - les cœurs au-dessus du joueur (récents dégâts ou regard en l'air)
    #   - des rectangles de debug si show_hitbox=True
    #   - dessin provisoire de l'attaque

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
        # ── Effets visuels du dash AÉRIEN (smoke + fx au point de départ) ──
        # Dessinés AVANT le perso pour qu'ils soient en arrière-plan.
        # On les dessine tant qu'ils ne sont pas terminés (one-shot).
        self._draw_aerial_dash_fx(surf, camera)

        if self.dashing:
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
        elif not self.on_ground:
            # Double saut en cours ?
            if self.jumps_used >= 2:
                # Forward (touche maintenue) ou vertical (statique) ?
                if self.double_jump_forward:
                    anim = self.idle_anim_double_jump_fwd
                else:
                    anim = self.idle_anim_double_jump
                if not anim.done:
                    anim.update()
                    img = anim.img()
                else:
                    # Anim terminée → on bascule sur jump (chute)
                    self.idle_anim_jump.update()
                    img = self.idle_anim_jump.img()
            else:
                # Saut normal
                self.idle_anim_jump.update()
                img = self.idle_anim_jump.img()

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

        sprite_rect = pygame.Rect(sx, sy, img_w, img_h)

        if self.invincible:
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
        pygame.draw.arc(surf_slash, couleur, (0, 0, vis_rect.width, vis_rect.height), 
                        start_angle, end_angle, epaisseur)
        
        # Un deuxième arc plus fin et plus clair pour l'éclat
        pygame.draw.arc(surf_slash, (200, 240, 255, alpha), (2, 2, vis_rect.width-4, vis_rect.height-4), 
                        start_angle, end_angle, 2)

        surface.blit(surf_slash, rect_ecran.topleft)