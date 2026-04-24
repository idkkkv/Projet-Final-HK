# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Une luciole (petite lumière qui flotte autour du joueur)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Définit UNE SEULE luciole : un petit point lumineux chaud qui flotte
#  AUTOUR du joueur, sans tourner, sans IA agressive. Juste une lumière
#  un peu vivante, comme dans le fond d'écran du jeu.
#
#  COMPORTEMENT (l'esprit visé)
#  ----------------------------
#  Imagine une luciole en vrai : elle ne FAIT PAS le tour de toi.
#  Elle se pose mentalement à un endroit ("là, en haut à gauche") et
#  flotte sur place pendant quelques secondes. Puis elle change d'idée
#  et dérive doucement vers un nouvel endroit. Quand toi tu marches,
#  elle suit MOLLEMENT — pas instantanément. Si tu cours et qu'elle
#  s'éloigne trop, à un moment elle se rappelle et se met à courir
#  pour te rattraper, sinon elle reste un peu à la traîne.
#
#  Concrètement, on a 3 mécanismes superposés :
#       1. UNE ANCRE relative au joueur (ex : "+30 px à droite, -20 en
#          haut"). Cette ancre dérive lentement vers une nouvelle ancre
#          tirée au hasard toutes les 4 à 8 secondes.
#       2. UN FLOTTEMENT vertical très subtil (oscillation de ±2 px)
#          qui simule le battement d'aile de la luciole.
#       3. UN MODE DE SUIVI ("calme" ou "rattrape") qui change de temps
#          en temps : en "rattrape", le lissage est rapide → la luciole
#          court vers le joueur. Sinon elle traîne mollement.
#
#  ON AJOUTE UNE 4ᵉ DIMENSION : Z (profondeur)
#  -------------------------------------------
#  Chaque luciole a une variable z ∈ [-1, +1] qui dérive lentement.
#       z négatif → la luciole est "derrière" le joueur → on la dessine
#                   AVANT le joueur (donc le joueur la cache si elle est
#                   pile derrière).
#       z positif → "devant" → dessinée APRÈS le joueur.
#  Effet visuel : impression de profondeur 3D bon marché, sans rien
#  changer au reste du moteur 2D.
#
#  La séparation "avant/après le joueur" est gérée dans
#  systems/compagnons.py via deux méthodes :
#       group.draw_derriere(surf, camera, joueur)  ← appelée AVANT le joueur
#       group.draw_devant(surf, camera, joueur)    ← appelée APRÈS
#
#  POURQUOI PAS DE COLLISION ?
#  ---------------------------
#  Une luciole n'a pas besoin de bloquer le joueur ni d'être bloquée par
#  les murs. Du coup elle traverse les murs sans bug. C'est intentionnel :
#  l'ancienne classe Compagnon essayait de garder ses distances par rapport
#  au joueur quand celui-ci se collait à un mur, ce qui faisait des
#  rebonds visuels disgracieux.
#
#  La GESTION DU GROUPE (combien il y en a, rappel cape [C], peur) est
#  dans systems/compagnons.py → classe CompagnonGroup.
#
#  COMPATIBILITÉ AVEC L'ANCIEN CODE
#  --------------------------------
#  Cette classe expose la même API publique que l'ancienne classe
#  Compagnon : __init__(x, y, idx), update(dt, joueur), draw(surf, camera,
#  joueur), distance_au_joueur(joueur). Plus deux nouveautés :
#       - attribut self.z (lecture seule depuis l'extérieur)
#       - draw() est polymorphe : on l'appelle pour les deux passes,
#         mais elle ne fait rien si la luciole n'est pas dans la bonne
#         couche (gérée par le groupe — voir CompagnonGroup).
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Couleur                            → CONSTANTE COULEUR_LUCIOLE
#     - Distance d'ancrage autour du joueur→ ANCRE_RAYON_X / ANCRE_RAYON_Y
#     - Vitesse de suivi (mou/rapide)      → SUIVI_LENT / SUIVI_RATTRAPE
#     - Fréquence des "rattrapages"        → INTERVALLE_RATTRAPAGE_*
#     - Fréquence du changement d'ancre    → INTERVALLE_NOUVELLE_ANCRE_*
#     - Taille / douceur du halo           → RAYON_HALO_BASE, OPACITE_MAX
#
#  Petit lexique :
#     - ancre       = un point relatif au joueur, ex : (+30, -20). C'est
#                     "où la luciole veut être" en ce moment. Elle change
#                     d'ancre de temps en temps.
#     - lissage     = "tendre vers" sans atteindre instantanément.
#                     Formule : pos += (cible - pos) * facteur * dt.
#                     Plus le facteur est grand, plus c'est nerveux.
#     - flottement  = le tout petit va-et-vient vertical (sinus).
#     - z           = profondeur visuelle simulée (juste un nombre, pas
#                     une vraie 3D). Sert à choisir si on dessine la
#                     luciole avant ou après le joueur.
#     - SRCALPHA    = mode pygame qui permet la transparence par pixel.
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D1]  pygame.Surface          — petite feuille pour dessiner le halo
#     [D2]  SRCALPHA                — transparence du halo
#     [D10] dt                      — temps écoulé depuis la frame précédente
#     [D11] math.hypot              — distance entre 2 points
#     [D12] math.sin                — flottement vertical
#     [D13] Interpolation linéaire  — fondu position luciole ↔ joueur (cape)
#                                     + lissage de la position vers l'ancre
#     [D20] Caméra                  — coordonnées écran = monde - offset
#
# ─────────────────────────────────────────────────────────────────────────────

import math
import random
import pygame

# settings = module avec état partagé. On lit dedans la palette de couleurs
# choisie par le joueur (settings.LUCIOLE_PALETTE + settings.lucioles_couleurs_idx)
# et la taille (settings.LUCIOLE_TAILLES + settings.lucioles_tailles_idx).
# La lecture se fait dans draw() à chaque frame → si le joueur change un
# réglage en jeu, ça se voit instantanément (pas besoin de respawn).
import settings


# ═════════════════════════════════════════════════════════════════════════════
#  RÉGLAGES (faciles à toucher pour changer le rendu)
# ═════════════════════════════════════════════════════════════════════════════

# Couleur de base d'une luciole : jaune-blanc chaud (R, G, B).
# Plus pâle qu'avant pour ne pas créer un point trop "lampe" au centre.
COULEUR_LUCIOLE = (255, 225, 170)

# ── Ancre (= position relative voulue par rapport au joueur) ────────────────
# La luciole tire au hasard une ancre dans ce rectangle autour du joueur :
#       x ∈ [-ANCRE_RAYON_X, +ANCRE_RAYON_X]
#       y ∈ [-ANCRE_RAYON_Y, +ANCRE_RAYON_Y_HAUT]  (Y négatif = au-dessus)
# Elle reste à cette ancre quelques secondes, puis en tire une nouvelle.
ANCRE_RAYON_X      = 60      # demi-largeur de la zone d'ancrage
ANCRE_RAYON_Y_HAUT = 50      # combien de px au-dessus du centre joueur (Y négatif)
ANCRE_RAYON_Y_BAS  = 25      # combien de px en dessous

# Combien de temps une luciole reste sur la même ancre avant d'en tirer
# une nouvelle (en secondes). Le timer est tiré au hasard dans cet intervalle.
INTERVALLE_NOUVELLE_ANCRE_MIN = 4.0
INTERVALLE_NOUVELLE_ANCRE_MAX = 9.0

# ── Suivi du joueur (lissage) ───────────────────────────────────────────────
# La position courante de la luciole tend vers (joueur + ancre) avec un
# facteur de lissage. Plus c'est petit, plus elle traîne / a l'air mou.
#       SUIVI_LENT      = vitesse normale (calme)
#       SUIVI_RATTRAPE  = quand elle décide de rattraper le joueur d'un coup
SUIVI_LENT     = 1.2     # à 60 fps, ~2% du chemin par frame → bien mou
SUIVI_RATTRAPE = 5.5     # 9% par frame → elle file vraiment

# Combien de temps une luciole reste en mode "rattrape" avant de revenir calme.
DUREE_RATTRAPAGE_MIN = 0.7
DUREE_RATTRAPAGE_MAX = 1.6

# Fréquence des décisions de rattrapage : toutes les X secondes, on tire au
# sort si on bascule en "rattrape" (seulement si on est trop loin).
INTERVALLE_DECISION_MIN = 1.5
INTERVALLE_DECISION_MAX = 4.0

# Distance au-delà de laquelle on AUTORISE le mode rattrape.
# En dessous, la luciole reste calme — elle est déjà bien.
DISTANCE_DECLENCHE_RATTRAPAGE = 90

# Probabilité (à chaque décision) de basculer en "rattrape" si on est loin.
# 0.6 = 60% → la luciole rattrape souvent mais pas toujours → naturel.
PROBA_RATTRAPAGE = 0.6

# ── Flottement vertical (battement d'aile) ──────────────────────────────────
# Très subtil : on veut juste que ça vibre légèrement.
AMPLITUDE_FLOTTEMENT = 2.0   # ±2 px (avant : 6)
VITESSE_FLOTTEMENT   = 1.7   # rad/s, ~3.7 s par cycle

# ── Profondeur Z (devant/derrière le joueur) ────────────────────────────────
# Z dérive lentement vers une cible tirée au hasard toutes les ~5-10 s.
# Z > 0 → devant le joueur, Z < 0 → derrière.
INTERVALLE_NOUVEAU_Z_MIN = 5.0
INTERVALLE_NOUVEAU_Z_MAX = 12.0
VITESSE_DERIVE_Z         = 0.4   # rad/s — combien Z se rapproche de sa cible

# ── Halo (rendu) ────────────────────────────────────────────────────────────
# Plus doux qu'avant : opacité max plus basse, courbe d'opacité en CUBE
# (au lieu de carré) → centre moins dur, dégradé plus diffus.
RAYON_HALO_BASE = 14    # rayon de base du halo (un peu plus large qu'avant)
OPACITE_MAX     = 130   # alpha au cœur (avant : 220 → trop "lampe")

# Pulsation : on en garde juste un soupçon, sinon on retombe dans le
# scintillement criard. 0.05 = ±5% → presque rien à l'œil.
PULSATION_AMPLITUDE = 0.05
PULSATION_VITESSE   = 1.0   # rad/s

# Quand la luciole est "derrière" le joueur (z < 0), on la rétrécit et on
# baisse son opacité pour donner une impression de profondeur.
ECHELLE_ARRIERE = 0.75      # ×0.75 quand z = -1
ALPHA_ARRIERE   = 0.65      # ×0.65 d'opacité quand z = -1

# Durée (s) de l'animation d'entrée/sortie de la cape (touche [C]).
DUREE_ANIM_CAPE = 0.35


# ═════════════════════════════════════════════════════════════════════════════
#  LA CLASSE LUCIOLE
# ═════════════════════════════════════════════════════════════════════════════

class Luciole:
    """Une petite lumière qui flotte autour du joueur, sans orbite."""

    # ─────────────────────────────────────────────────────────────────────────
    #  1. CONSTRUCTION
    # ─────────────────────────────────────────────────────────────────────────

    def __init__(self, x, y, idx=0):
        """Crée une luciole. idx = numéro dans le groupe (sert juste à
        décaler les tirages aléatoires initiaux pour que toutes les
        lucioles ne synchronisent pas leurs ancres / décisions)."""
        self.idx = idx

        # Position monde courante (float pour mouvements fluides).
        self.x = float(x)
        self.y = float(y)

        # Vitesse — exposée pour compat avec l'ancienne API Compagnon.
        # Pas vraiment utilisée ici (pas de physique), gardée à 0.
        self.vx = 0.0
        self.vy = 0.0

        # ── Cape (compat) ────────────────────────────────────────────────
        # dans_cape  = ce qu'on VEUT (True = rappelée, False = sortie)
        # visibilite = ce qu'on VOIT (1 = entièrement visible, 0 = cachée)
        self.dans_cape = False
        self.visibilite = 1.0

        # État textuel exposé pour compat (ancien code testait c.etat).
        # Toujours "suit" : la luciole n'a pas de machine à états réelle.
        self.etat = "suit"

        # ── Ancre relative au joueur ─────────────────────────────────────
        # Position que la luciole CHERCHE à occuper, exprimée RELATIVEMENT
        # au joueur (ex : (-30, -15) = un peu à gauche au-dessus).
        # ancre_actuelle = ce qu'on suit en ce moment (interpolée)
        # ancre_cible    = nouvelle ancre tirée au hasard, vers laquelle
        #                  l'ancre actuelle dérive très lentement.
        self.ancre_actuelle_x = 0.0
        self.ancre_actuelle_y = -20.0
        self.ancre_cible_x, self.ancre_cible_y = self._tirer_nouvelle_ancre()
        # Au tout début, on colle l'actuelle à la cible pour ne pas dériver
        # depuis (0,0) au démarrage.
        self.ancre_actuelle_x = self.ancre_cible_x
        self.ancre_actuelle_y = self.ancre_cible_y
        # Timer avant de tirer une nouvelle ancre cible.
        self.t_changer_ancre = random.uniform(
            INTERVALLE_NOUVELLE_ANCRE_MIN, INTERVALLE_NOUVELLE_ANCRE_MAX)

        # ── Mode de suivi ────────────────────────────────────────────────
        # "calme" (lissage lent) ou "rattrape" (lissage rapide pendant
        # quelques secondes, pour combler une distance).
        self.mode_suivi = "calme"
        self.t_decision = random.uniform(
            INTERVALLE_DECISION_MIN, INTERVALLE_DECISION_MAX)
        self.t_rattrapage = 0.0   # >0 quand on est en mode rattrape

        # ── Flottement vertical ──────────────────────────────────────────
        # Phase initiale aléatoire pour que toutes les lucioles ne
        # battent pas en même temps (sinon on verrait le motif).
        self.t_flottement = random.uniform(0.0, 6.28)

        # ── Profondeur Z (devant/derrière) ───────────────────────────────
        # Tirée au hasard au démarrage : ~50% devant, ~50% derrière.
        self.z = random.uniform(-1.0, 1.0)
        self.z_cible = random.uniform(-1.0, 1.0)
        self.t_changer_z = random.uniform(
            INTERVALLE_NOUVEAU_Z_MIN, INTERVALLE_NOUVEAU_Z_MAX)

    # ─────────────────────────────────────────────────────────────────────────
    #  2. TIRAGE D'UNE NOUVELLE ANCRE
    # ─────────────────────────────────────────────────────────────────────────

    def _tirer_nouvelle_ancre(self):
        """Renvoie un (dx, dy) au hasard dans le rectangle d'ancrage.

        Y est tiré entre -ANCRE_RAYON_Y_HAUT (au-dessus du joueur) et
        +ANCRE_RAYON_Y_BAS (en dessous). Comme HAUT > BAS, les lucioles
        flottent statistiquement plus haut que bas — c'est joli."""
        dx = random.uniform(-ANCRE_RAYON_X, +ANCRE_RAYON_X)
        dy = random.uniform(-ANCRE_RAYON_Y_HAUT, +ANCRE_RAYON_Y_BAS)
        return dx, dy

    # ─────────────────────────────────────────────────────────────────────────
    #  3. UPDATE (appelé chaque frame)
    # ─────────────────────────────────────────────────────────────────────────

    def update(self, dt, joueur):
        """Met à jour l'ancre, la position lissée, le mode de suivi et z."""

        # ── 1) Animation de visibilité (fondu cape) ─────────────────────
        vitesse_anim = 1.0 / DUREE_ANIM_CAPE
        if self.dans_cape:
            self.visibilite -= vitesse_anim * dt
            if self.visibilite < 0.0:
                self.visibilite = 0.0
        else:
            self.visibilite += vitesse_anim * dt
            if self.visibilite > 1.0:
                self.visibilite = 1.0

        # ── 2) Cas particulier : quasi totalement dans la cape ──────────
        if self.dans_cape and self.visibilite <= 0.01:
            self.x = float(joueur.rect.centerx)
            self.y = float(joueur.rect.centery)
            return

        # ── 3) Avance les compteurs (flottement, timers) ────────────────
        self.t_flottement += dt * VITESSE_FLOTTEMENT
        self.t_changer_ancre -= dt
        self.t_decision -= dt
        self.t_changer_z -= dt
        if self.t_rattrapage > 0:
            self.t_rattrapage -= dt
            if self.t_rattrapage <= 0:
                self.mode_suivi = "calme"

        # ── 4) Changement d'ancre cible si le timer est écoulé ──────────
        if self.t_changer_ancre <= 0:
            self.ancre_cible_x, self.ancre_cible_y = self._tirer_nouvelle_ancre()
            self.t_changer_ancre = random.uniform(
                INTERVALLE_NOUVELLE_ANCRE_MIN, INTERVALLE_NOUVELLE_ANCRE_MAX)

        # ── 5) L'ancre actuelle dérive très lentement vers la cible ─────
        # Facteur 0.6 → la dérive prend ~2 s pour combler la moitié de
        # l'écart, ce qui rend le déplacement très doux.
        derive_facteur = 0.6
        self.ancre_actuelle_x += (self.ancre_cible_x - self.ancre_actuelle_x) * derive_facteur * dt
        self.ancre_actuelle_y += (self.ancre_cible_y - self.ancre_actuelle_y) * derive_facteur * dt

        # ── 6) Position cible = joueur + ancre actuelle + flottement ────
        cible_x = joueur.rect.centerx + self.ancre_actuelle_x
        cible_y = joueur.rect.centery + self.ancre_actuelle_y - 10  # un peu plus haut
        cible_y += math.sin(self.t_flottement) * AMPLITUDE_FLOTTEMENT

        # ── 7) Distance courante au joueur (pour la logique rattrapage) ─
        dx_joueur = joueur.rect.centerx - self.x
        dy_joueur = joueur.rect.centery - self.y
        distance = math.hypot(dx_joueur, dy_joueur)

        # ── 8) Décision : "est-ce que je rattrape ?" ────────────────────
        # Toutes les ~2-4 s, si on est loin du joueur, on tire au sort.
        if self.t_decision <= 0:
            if distance > DISTANCE_DECLENCHE_RATTRAPAGE and self.mode_suivi == "calme":
                if random.random() < PROBA_RATTRAPAGE:
                    self.mode_suivi = "rattrape"
                    self.t_rattrapage = random.uniform(
                        DUREE_RATTRAPAGE_MIN, DUREE_RATTRAPAGE_MAX)
            self.t_decision = random.uniform(
                INTERVALLE_DECISION_MIN, INTERVALLE_DECISION_MAX)

        # ── 9) Application du lissage selon le mode ─────────────────────
        if self.mode_suivi == "rattrape":
            facteur = SUIVI_RATTRAPE
        else:
            facteur = SUIVI_LENT
        self.x += (cible_x - self.x) * facteur * dt
        self.y += (cible_y - self.y) * facteur * dt

        # ── 10) Profondeur Z dérive vers sa cible ───────────────────────
        # On utilise la même technique de lissage que pour l'ancre.
        self.z += (self.z_cible - self.z) * VITESSE_DERIVE_Z * dt
        if self.t_changer_z <= 0:
            # Nouvelle cible Z aléatoire dans [-1, +1].
            # On évite de re-tirer trop près de la valeur actuelle pour
            # qu'on voie la transition (un changement de 0.1 à 0.05 ne
            # se verrait pas).
            nouvelle = random.uniform(-1.0, 1.0)
            if abs(nouvelle - self.z) < 0.4:
                # Trop proche → on force un saut vers l'autre côté.
                if self.z >= 0:
                    nouvelle = random.uniform(-1.0, -0.4)
                else:
                    nouvelle = random.uniform(0.4, 1.0)
            self.z_cible = nouvelle
            self.t_changer_z = random.uniform(
                INTERVALLE_NOUVEAU_Z_MIN, INTERVALLE_NOUVEAU_Z_MAX)

    # ─────────────────────────────────────────────────────────────────────────
    #  4. EST-ELLE DEVANT OU DERRIÈRE LE JOUEUR ?
    # ─────────────────────────────────────────────────────────────────────────
    #
    #  Utilisé par CompagnonGroup pour décider à quelle passe (avant/après
    #  le joueur) on dessine cette luciole.

    def est_devant_joueur(self):
        """True si la luciole doit être dessinée DEVANT le joueur (z >= 0)."""
        return self.z >= 0.0

    # ─────────────────────────────────────────────────────────────────────────
    #  5. DISTANCE AU JOUEUR (pour la jauge de peur)
    # ─────────────────────────────────────────────────────────────────────────

    def distance_au_joueur(self, joueur):
        """Distance en pixels. 0 si totalement dans la cape (cf. compat)."""
        if self.dans_cape and self.visibilite <= 0.01:
            return 0.0
        dx = joueur.rect.centerx - self.x
        dy = joueur.rect.centery - self.y
        return math.hypot(dx, dy)   # [D11]

    # ─────────────────────────────────────────────────────────────────────────
    #  6. CONFIG INDIVIDUELLE (couleur + taille choisies dans le menu)
    # ─────────────────────────────────────────────────────────────────────────
    #
    #  Le joueur peut, via Paramètres → Compagnons, choisir sa propre couleur
    #  et sa propre taille pour CHAQUE slot de luciole. On lit ces choix ici,
    #  à chaque frame (peu coûteux : ce sont des accès liste). Si quelque
    #  chose manque (config corrompue, idx hors borne…), on retombe sur les
    #  constantes par défaut — la luciole s'affiche toujours, jamais de crash.

    def _get_couleur(self):
        """Renvoie le tuple (R, G, B) à utiliser pour cette luciole.

        Cherche settings.LUCIOLE_PALETTE[settings.lucioles_couleurs_idx[idx]].
        Fallback : la constante COULEUR_LUCIOLE (jaune chaud)."""
        try:
            i_choix = settings.lucioles_couleurs_idx[self.idx]
            nom, rgb = settings.LUCIOLE_PALETTE[i_choix]
            return rgb
        except (AttributeError, IndexError, TypeError):
            return COULEUR_LUCIOLE

    def _get_taille_mult(self):
        """Renvoie le multiplicateur de taille (float) à appliquer au halo.

        Cherche settings.LUCIOLE_TAILLES[settings.lucioles_tailles_idx[idx]].
        Fallback : 1.0 (taille de base)."""
        try:
            i_choix = settings.lucioles_tailles_idx[self.idx]
            nom, mult = settings.LUCIOLE_TAILLES[i_choix]
            return mult
        except (AttributeError, IndexError, TypeError):
            return 1.0

    def _get_intensite_mult(self):
        """Renvoie le multiplicateur d'INTENSITÉ (puissance d'éclairage).

        S'applique sur OPACITE_MAX dans draw() : plus c'est grand, plus le
        halo est brillant et "présent" dans la scène.
        Cherche settings.LUCIOLE_INTENSITES[settings.lucioles_intensites_idx[idx]].
        Fallback : 1.6 — équivalent à "Forte" dans la liste par défaut, qui
        est aussi la valeur initiale pour tous les slots (cf. settings.py)."""
        try:
            i_choix = settings.lucioles_intensites_idx[self.idx]
            nom, mult = settings.LUCIOLE_INTENSITES[i_choix]
            return mult
        except (AttributeError, IndexError, TypeError):
            return 1.6

    # ─────────────────────────────────────────────────────────────────────────
    #  7. RENDU
    # ─────────────────────────────────────────────────────────────────────────

    def draw(self, surf, camera, joueur):
        """Dessine la luciole : juste un halo doux, rien d'autre."""

        # Totalement invisible → rien à faire.
        if self.visibilite <= 0.01:
            return

        # ── Position à l'écran (avec interpolation cape) ────────────────
        # t = 1 → vraie position de la luciole
        # t = 0 → position du joueur
        t = self.visibilite
        pos_x = (1 - t) * joueur.rect.centerx + t * self.x
        pos_y = (1 - t) * joueur.rect.centery + t * self.y

        # Coordonnées écran (on retire l'offset de la caméra [D20]).
        sx = int(pos_x - camera.offset_x)
        sy = int(pos_y - camera.offset_y)

        # ── Pulsation TRÈS subtile (juste de la vie, pas du clignotement) ─
        pulsation = 1.0 + PULSATION_AMPLITUDE * math.sin(
            self.t_flottement * PULSATION_VITESSE)

        # ── Effet de profondeur lié à z ─────────────────────────────────
        # z =  +1 → 100% taille, 100% opacité  (devant)
        # z =  -1 → ECHELLE_ARRIERE × taille, ALPHA_ARRIERE × opacité (derrière)
        # On interpole linéairement entre ces deux valeurs en utilisant
        # un facteur f = (z + 1) / 2 ∈ [0, 1] qui vaut 0 quand z=-1 et 1 quand z=+1.
        f_z = (self.z + 1.0) / 2.0
        echelle_z = ECHELLE_ARRIERE + (1.0 - ECHELLE_ARRIERE) * f_z
        alpha_z   = ALPHA_ARRIERE   + (1.0 - ALPHA_ARRIERE)   * f_z

        # ── Calcul du rayon final du halo ───────────────────────────────
        # On applique en plus le multiplicateur de taille choisi par le
        # joueur (settings.LUCIOLE_TAILLES) — voir _get_taille_mult().
        taille_mult = self._get_taille_mult()
        rayon = int(RAYON_HALO_BASE * taille_mult * self.visibilite * pulsation * echelle_z)
        if rayon < 2:
            return

        # ── Dessin du halo : cercles concentriques sur Surface SRCALPHA ─
        # On dessine sur une petite Surface séparée [D1] avec SRCALPHA [D2]
        # pour avoir une vraie transparence par pixel.
        taille = rayon * 2
        halo = pygame.Surface((taille, taille), pygame.SRCALPHA)

        # Couleur choisie par le joueur (settings.LUCIOLE_PALETTE) — voir
        # _get_couleur(). Permet d'avoir des lucioles de couleurs différentes
        # dans le même groupe (la 1ʳᵉ jaune, la 2ᵉ bleue, etc.).
        r_couleur, g_couleur, b_couleur = self._get_couleur()
        # Intensité = puissance d'éclairage choisie par le joueur (slot par slot).
        # On l'applique en multiplicateur sur l'opacité, puis on clamp pour ne
        # jamais dépasser 255 (sinon overflow → couleurs fausses au centre).
        intensite_mult = self._get_intensite_mult()
        opacite_centre = OPACITE_MAX * alpha_z * intensite_mult
        if opacite_centre > 255:
            opacite_centre = 255

        # Cercles concentriques, du grand au petit. La courbe d'opacité
        # est en CUBE (puissance 3) au lieu du carré : ça écrase la valeur
        # vers le centre, donc le cœur ne paraît pas brillant — le halo
        # s'estompe TRÈS doucement et n'a plus ce point dur central qui
        # faisait "lampe LED". Comparaison :
        #     carré (avant) : monte vite vers 1 → centre dur
        #     cube  (ici)   : monte plus lentement → centre doux et diffus
        for r in range(rayon, 0, -2):
            facteur = 1.0 - (r / rayon)        # 0 au bord, 1 au centre
            alpha = int(facteur ** 3 * opacite_centre)
            if alpha <= 0:
                continue
            couleur = (r_couleur, g_couleur, b_couleur, alpha)
            pygame.draw.circle(halo, couleur, (rayon, rayon), r)

        surf.blit(halo, (sx - rayon, sy - rayon))
