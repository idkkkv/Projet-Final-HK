# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — HUD (interface en jeu)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Le petit panneau en haut à gauche pendant le jeu :
#
#       ♥ ♥ ♥ ♥ ♥        ← PV du joueur (cœurs rouges qui se vident en gris)
#       [█████████░░]    ← Jauge de peur (style Hollow Knight, bleu pâle)
#
#  Deux modes (configurables depuis settings.hud_mode, lui-même réglable
#  dans le menu Paramètres → Affichage en jeu) :
#
#  - "permanent" : HUD toujours visible. S'estompe légèrement (ALPHA_MIN)
#                  si tout est plein depuis quelques secondes — c'est le
#                  mode confort, on a toujours ses infos sous les yeux.
#
#  - "immersion" : HUD masqué tant que tout va bien. Apparaît UNIQUEMENT si :
#                     - le joueur regarde vers le haut (Z / ↑)
#                     - il vient de prendre des dégâts (show_hp_timer > 0)
#                     - il est en train de régénérer (regen_active)
#                     - sa jauge de peur n'est pas pleine
#                  Mode plus immersif, on n'a pas l'UI sous les yeux en
#                  permanence.
#
#  Le HUD ne stocke AUCUNE valeur de gameplay : il lit chaque frame l'état
#  du joueur et de la jauge. Ça veut dire qu'on peut hot-changer tout sans
#  jamais le réinitialiser.
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  core/game.py crée l'instance :
#       self.hud = HUD()
#  Et chaque frame :
#       self.hud.update(dt, self.joueur, self.peur)
#       self.hud.draw(self.screen, self.joueur, self.peur)
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Couleurs                → constantes COULEUR_* en haut
#     - Position du HUD         → constantes HUD_X / HUD_Y
#     - Taille des cœurs        → TAILLE_COEUR / ESPACE_COEUR
#     - Délai d'auto-fade       → DUREE_AVANT_FONDU / DUREE_FONDU
#     - Conditions du mode immersion → _alpha_courant (mode "immersion")
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D1]  pygame.Surface       — surface tampon pour moduler l'alpha
#     [D2]  SRCALPHA             — transparence de la surface tampon
#     [D6]  pygame.draw          — cœurs et jauge dessinés avec draw.rect
#     [D10] dt                   — accumulation du timer d'inactivité
#     [D22] Machine à états      — settings.hud_mode (permanent/immersion)
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame

import settings
from settings import BLANC


# ═════════════════════════════════════════════════════════════════════════════
#  1. STYLE (couleurs et géométrie)
# ═════════════════════════════════════════════════════════════════════════════

# ── Couleurs ────────────────────────────────────────────────────────────────
COULEUR_COEUR_PLEIN = (235,  60,  90)   # cœur rempli (rouge vif)
COULEUR_COEUR_VIDE  = ( 60,  20,  30)   # cœur vide (rouge sombre)
COULEUR_BORD_COEUR  = (200, 200, 200)   # bordure des cœurs

COULEUR_PEUR_BG     = ( 25,  25,  35)   # fond de la jauge
COULEUR_PEUR_BORD   = (180, 180, 200)   # bordure de la jauge
COULEUR_PEUR_FILL   = (140, 200, 255)   # bleu pâle "âme" — type Hollow Knight

# ── Géométrie (en pixels) ───────────────────────────────────────────────────
HUD_X            = 16     # marge gauche
HUD_Y            = 16     # marge haute
TAILLE_COEUR     = 22     # côté du carré "cœur"
ESPACE_COEUR     = 8      # gap entre deux cœurs
HAUTEUR_PEUR     = 12     # hauteur de la jauge
ESPACE_VERTICAL  = 10     # gap entre les cœurs et la jauge

# ── Auto-hide (mode permanent) ──────────────────────────────────────────────
DUREE_AVANT_FONDU = 4.0   # secondes d'inactivité avant que le HUD s'estompe
DUREE_FONDU       = 1.0   # durée du fade-out
ALPHA_MIN         = 60    # opacité minimum quand "endormi"


# ═════════════════════════════════════════════════════════════════════════════
#  2. CLASSE HUD
# ═════════════════════════════════════════════════════════════════════════════

class HUD:
    """HUD persistant pour les PV et la peur.

    Ne stocke AUCUNE valeur de gameplay : il lit chaque frame l'état du
    joueur et de la jauge."""

    def __init__(self):
        # On retient les dernières valeurs pour DÉTECTER les changements :
        # tant que rien ne change, on accumule self._timer_inactif. Dès
        # qu'une valeur bouge, on remet le timer à 0 (= HUD réveillé).
        self._derniere_hp     = None
        self._derniere_peur   = None
        self._timer_inactif   = 0.0

    # ═════════════════════════════════════════════════════════════════════════
    #  3. UPDATE — détection d'inactivité (auto-hide en mode permanent)
    # ═════════════════════════════════════════════════════════════════════════

    def update(self, dt, joueur, peur=None):
        """Compare les valeurs courantes avec les précédentes pour détecter un
        changement, et ajuste self._timer_inactif en conséquence."""

        # On extrait peur.current dans une variable séparée pour gérer
        # proprement le cas peur=None (jeux/démos sans système de peur).
        if peur:
            peur_val = peur.current
        else:
            peur_val = None

        # Détection de changement → on réveille le HUD (timer = 0).
        # Sinon → on accumule dt jusqu'à atteindre DUREE_AVANT_FONDU.
        if (joueur.hp != self._derniere_hp) or (peur_val != self._derniere_peur):
            self._timer_inactif = 0.0
        else:
            self._timer_inactif += dt

        # On retient les nouvelles valeurs pour la prochaine frame.
        self._derniere_hp   = joueur.hp
        self._derniere_peur = peur_val

    # ═════════════════════════════════════════════════════════════════════════
    #  4. CALCUL DE L'OPACITÉ (selon le mode et l'état)
    # ═════════════════════════════════════════════════════════════════════════

    def _alpha_courant(self, joueur, peur):
        """Renvoie l'alpha (0..255) du HUD selon le mode et l'état du joueur."""

        plein_pv   = joueur.hp >= joueur.max_hp
        plein_peur = (peur is None) or (peur.current >= peur.max_fear)

        # ── Mode immersion : on cache TOUT sauf signaux explicites ───────────
        # getattr(obj, "nom", default) : récupère un attribut s'il existe,
        # sinon la valeur par défaut. Évite des crashs si le joueur n'a
        # pas encore tous les attributs (ex: ancien save).
        #
        # ⚠️ On NE déclenche PAS sur "peur non pleine" : la peur descend en
        # permanence dès que les compagnons sont proches → le HUD ne se
        # cacherait jamais. Le joueur consulte sa peur en regardant en haut.
        if settings.hud_mode == "immersion":
            visible = (
                getattr(joueur, "looking_up",   False)        # regarde en haut (Z)
                or getattr(joueur, "show_hp_timer", 0) > 0    # vient d'être touché
                or getattr(joueur, "regen_active",  False)    # en train de regen
            )
            return 255 if visible else 0

        # ── Mode permanent (par défaut) ──────────────────────────────────────
        # Si quelque chose n'est pas plein → le HUD est utile → 255 (opaque).
        if not (plein_pv and plein_peur):
            return 255

        # Tout est plein → fade-out après DUREE_AVANT_FONDU secondes.
        # excess = combien de temps s'est écoulé APRÈS le seuil.
        excess = self._timer_inactif - DUREE_AVANT_FONDU
        if excess <= 0:
            return 255

        # Ratio entre 0 et 1 : 0 = début du fondu, 1 = fondu terminé.
        ratio = max(0.0, min(1.0, excess / DUREE_FONDU))
        # Interpolation linéaire de 255 vers ALPHA_MIN.
        return int(255 - (255 - ALPHA_MIN) * ratio)

    # ═════════════════════════════════════════════════════════════════════════
    #  5. RENDU — chef d'orchestre
    # ═════════════════════════════════════════════════════════════════════════

    def draw(self, screen, joueur, peur=None):
        """Dessine cœurs + jauge sur une surface tampon, puis sur l'écran."""

        alpha = self._alpha_courant(joueur, peur)
        # Optimisation : alpha 0 → on ne dessine rien (mode immersion caché).
        if alpha <= 0:
            return

        # ── Surface tampon avec SRCALPHA pour moduler l'alpha global ─────────
        # On dessine d'abord tout sur cette surface, puis on lui applique
        # set_alpha avant de la blitter à l'écran. C'est plus simple que
        # de propager l'alpha à chaque draw.rect.
        largeur_coeurs = joueur.max_hp * (TAILLE_COEUR + ESPACE_COEUR) - ESPACE_COEUR
        largeur_jauge  = max(largeur_coeurs, 180)
        h_total        = TAILLE_COEUR + ESPACE_VERTICAL + HAUTEUR_PEUR
        if peur is None:
            # Pas de peur → pas de jauge → hauteur réduite.
            h_total = TAILLE_COEUR

        surf = pygame.Surface((largeur_jauge, h_total), pygame.SRCALPHA)

        # ── Cœurs en haut ────────────────────────────────────────────────────
        self._draw_hearts(surf, joueur, 0, 0)

        # ── Jauge de peur sous les cœurs ─────────────────────────────────────
        if peur is not None:
            jy = TAILLE_COEUR + ESPACE_VERTICAL
            self._draw_fear_bar(surf, peur, 0, jy, largeur_jauge)

        # ── Application de l'alpha global puis collage à l'écran ─────────────
        if alpha < 255:
            surf.set_alpha(alpha)
        screen.blit(surf, (HUD_X, HUD_Y))

    # ═════════════════════════════════════════════════════════════════════════
    #  6. RENDU — pièces détachées
    # ═════════════════════════════════════════════════════════════════════════

    def _draw_hearts(self, surf, joueur, x, y):
        """Dessine les cœurs : remplis tant que i < joueur.hp, vides après."""

        for i in range(joueur.max_hp):
            cx = x + i * (TAILLE_COEUR + ESPACE_COEUR)
            # Couleur selon l'état du i-ème cœur
            if i < joueur.hp:
                color = COULEUR_COEUR_PLEIN
            else:
                color = COULEUR_COEUR_VIDE
            pygame.draw.rect(surf, color, (cx, y, TAILLE_COEUR, TAILLE_COEUR))
            # Bordure (épaisseur 2)
            pygame.draw.rect(surf, COULEUR_BORD_COEUR,
                             (cx, y, TAILLE_COEUR, TAILLE_COEUR), 2)

    def _draw_fear_bar(self, surf, peur, x, y, largeur):
        """Dessine la jauge de peur : fond, remplissage proportionnel, bordure."""

        # Fond complet
        pygame.draw.rect(surf, COULEUR_PEUR_BG, (x, y, largeur, HAUTEUR_PEUR))

        # Remplissage proportionnel à peur.get_ratio() (clampé 0..1).
        ratio = max(0.0, min(1.0, peur.get_ratio()))
        if ratio > 0:
            # -2 / +1 : on laisse 1 px de marge à l'intérieur de la bordure.
            pygame.draw.rect(surf, COULEUR_PEUR_FILL,
                             (x + 1, y + 1,
                              int((largeur - 2) * ratio), HAUTEUR_PEUR - 2))

        # Bordure (épaisseur 1, par-dessus pour qu'elle reste visible).
        pygame.draw.rect(surf, COULEUR_PEUR_BORD,
                         (x, y, largeur, HAUTEUR_PEUR), 1)
