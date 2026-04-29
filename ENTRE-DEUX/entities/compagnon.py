# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Un compagnon (petit fantôme blanc)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Définit UN SEUL compagnon : un petit "blob" blanc avec deux yeux bleus
#  qui flotte derrière le joueur. Le compagnon a trois états :
#
#       "suit"   → avance doucement vers la position "derrière le joueur"
#       "court"  → se dépêche parce qu'il est trop loin
#       "pause"  → s'arrête un instant pour regarder autour
#
#  La GESTION DU GROUPE de compagnons (combien il y en a, rappel dans la
#  cape avec [C], effet sur la jauge de peur) est dans un autre fichier :
#       systems/compagnons.py   →  classe CompagnonGroup
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  systems/compagnons.py (CompagnonGroup) crée un Compagnon par "slot"
#  demandé dans game_config.json (clé "nb_compagnons") :
#       self.compagnons.append(Compagnon(x, y, idx=i))
#  puis chaque frame :
#       compagnon.update(dt, joueur)
#       compagnon.draw(surf, camera, joueur)
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Vitesses de marche/course     → settings.py (COMPAGNON_VITESSE_*)
#     - Distance "il est trop loin"   → settings.py (COMPAGNON_DIST_COURSE)
#     - Probabilités des états        → _choisir_nouvel_etat()
#     - Durée de l'animation de cape  → constante DUREE_ANIM_CAPE ci-dessous
#     - Apparence (couleurs, taille)  → méthodes _dessiner_*()
#
#  ENTRÉE / SORTIE DE LA CAPE :
#  Quand le joueur appuie sur [C], CompagnonGroup bascule dans_cape pour
#  chaque compagnon. Mais on NE téléporte PAS : on fait varier la variable
#  self.visibilite entre 0.0 (caché) et 1.0 (visible) sur ~0.35 s, ce qui
#  donne un fondu + une interpolation linéaire de la position vers le
#  joueur. Le compagnon a l'air de rentrer dans la cape en rétrécissant.
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D1]  pygame.Surface          — petite feuille pour dessiner la lueur
#     [D2]  SRCALPHA                — transparence du halo
#     [D10] dt                      — temps écoulé depuis la frame précédente
#     [D11] math.hypot              — distance entre le compagnon et le joueur
#     [D12] math.sin                — oscillation (flottement, pulsation halo)
#     [D13] Interpolation linéaire  — fondu position compagnon ↔ joueur
#     [D14] Normaliser un vecteur   — diviser (dx, dy) par la distance
#     [D20] Caméra                  — coordonnées écran = monde - offset
#     [D22] Machine à états         — self.etat ∈ {suit, court, pause}
#
# ─────────────────────────────────────────────────────────────────────────────

import math
import random
import pygame

import settings


# Durée (en secondes) de l'animation d'entrée / sortie de la cape.
# 0.35 s = ~20 frames à 60 fps → assez court pour rester réactif,
# assez long pour qu'on voie bien l'effet.
DUREE_ANIM_CAPE = 0.35


# ═════════════════════════════════════════════════════════════════════════════
#  1. CONSTRUCTION
# ═════════════════════════════════════════════════════════════════════════════

class Compagnon:
    """Un petit compagnon blanc qui suit le joueur.

    Créé et géré par CompagnonGroup (systems/compagnons.py).
    Le rendu est dessiné "à la main" avec pygame.draw (pas de sprite PNG) :
    ça permet de faire varier la taille et la couleur dynamiquement, et
    d'ajouter facilement un halo, une traînée, etc."""

    def __init__(self, x, y, idx=0):
        """Crée un compagnon à la position (x, y).

        idx = numéro du compagnon dans le groupe (0 = le plus proche du
        joueur, 1 = un peu plus loin derrière, etc.). Sert à étaler les
        compagnons en file indienne dans la fonction update().
        """
        self.idx = idx

        # Position en float pour des mouvements fluides entre frames
        # (si on mettait des int, à petite vitesse on aurait des saccades).
        self.x = float(x)
        self.y = float(y)

        # Vitesse actuelle (en pixels par seconde)
        self.vx = 0.0
        self.vy = 0.0

        # Machine à états [D22] : "suit", "court" ou "pause".
        # Un timer (self.temps_etat) empêche de changer d'état à chaque
        # frame — sinon le compagnon oscillerait en permanence.
        self.etat = "suit"
        self.temps_etat = random.uniform(1.0, 3.0)

        # Cape :
        #   dans_cape  = ce qu'on VEUT (True = rappelé, False = sorti)
        #   visibilite = ce qu'on VOIT (1 = entièrement visible, 0 = caché)
        # L'animation tire visibilite vers la cible sur DUREE_ANIM_CAPE s.
        self.dans_cape = False
        self.visibilite = 1.0

        # Petit compteur qui avance à chaque frame, sert à faire osciller
        # le compagnon (effet "flotte dans l'air") avec math.sin [D12].
        # Valeur de départ aléatoire pour que tous les compagnons ne
        # flottent pas en rythme (sinon on verrait clairement que c'est
        # une copie du même motif).
        self.oscillation = random.uniform(0.0, 6.28)

    # ═════════════════════════════════════════════════════════════════════════
    #  2. UPDATE (appelé chaque frame)
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Appelé par CompagnonGroup.update(), lui-même appelé depuis
    #  core/game.py dans _update_jeu(). dt = temps écoulé depuis la
    #  frame précédente (en secondes) [D10].

    def update(self, dt, joueur):
        """Met à jour la position, la vitesse et l'état du compagnon."""

        # ── 1) Animation de visibilité (fondu cape) ──────────────────────────
        # vitesse_anim = combien la visibilité change par seconde.
        # Si on veut parcourir 0→1 en DUREE_ANIM_CAPE s,
        # alors vitesse_anim = 1 / DUREE_ANIM_CAPE.
        vitesse_anim = 1.0 / DUREE_ANIM_CAPE
        if self.dans_cape:
            # On veut être caché → visibilité baisse vers 0.
            self.visibilite -= vitesse_anim * dt
            if self.visibilite < 0.0:
                self.visibilite = 0.0
        else:
            # On veut être visible → visibilité remonte vers 1.
            self.visibilite += vitesse_anim * dt
            if self.visibilite > 1.0:
                self.visibilite = 1.0

        # ── 2) Oscillation verticale "il flotte" ─────────────────────────────
        # On avance à ~3 rad/s. Un tour complet ≈ 2 s → flottement doux.
        self.oscillation += dt * 3.0

        # ── 3) Cas particulier : quasi totalement dans la cape ───────────────
        # Pas la peine de calculer l'IA, on le colle au joueur (économise
        # quelques calculs et évite qu'il dérive sous nos pieds).
        if self.dans_cape and self.visibilite <= 0.01:
            self.x = float(joueur.rect.centerx)
            self.y = float(joueur.rect.centery)
            self.vx = 0.0
            self.vy = 0.0
            return

        # ── 4) Calcul de la position cible ("derrière le joueur") ────────────
        # joueur.direction vaut +1 (regarde à droite) ou -1 (à gauche).
        # Donc si direction>0, on se place à gauche (derriere=-1).
        if joueur.direction > 0:
            derriere = -1
        else:
            derriere = +1

        # Plus idx est grand, plus on se met loin derrière :
        #   idx 0 → 50 px, idx 1 → 85 px, idx 2 → 120 px, etc.
        # → les compagnons forment une file indienne sans se superposer.
        decalage = 50 + 35 * self.idx

        cible_x = joueur.rect.centerx + derriere * decalage
        cible_y = joueur.rect.bottom - 8   # à hauteur des pieds du joueur

        # ── 5) Vecteur "vers la cible" + distance [D11] ──────────────────────
        dx = cible_x - self.x
        dy = cible_y - self.y
        # math.hypot(dx, dy) = racine(dx² + dy²) = distance entre 2 points.
        # Pratique pour éviter d'écrire math.sqrt(dx*dx + dy*dy) à la main.
        distance = math.hypot(dx, dy)

        # ── 6) Changement d'état si le timer est écoulé ──────────────────────
        self.temps_etat -= dt
        if self.temps_etat <= 0:
            self._choisir_nouvel_etat(distance)

        # ── 7) Vitesse à appliquer selon l'état courant ──────────────────────
        if self.etat == "court":
            vitesse = settings.COMPAGNON_VITESSE_COURSE
        elif self.etat == "pause":
            vitesse = 0.0
        else:
            # "suit" : on ralentit quand on est tout proche pour ne pas coller.
            if distance < settings.COMPAGNON_DIST_RAPPROCHE:
                vitesse = 0.0
            else:
                vitesse = settings.COMPAGNON_VITESSE_MARCHE

        # ── 8) Calcul de vx / vy : normalisation du vecteur [D14] ────────────
        # On "normalise" : on divise (dx, dy) par la distance pour obtenir
        # un vecteur de longueur 1, puis on multiplie par la vitesse voulue.
        #       vx = (dx / distance) * vitesse
        #       vy = (dy / distance) * vitesse
        # Attention à la division par zéro → on ne le fait que si on est
        # assez loin et que la vitesse n'est pas nulle.
        if distance > 5 and vitesse > 0:
            self.vx = (dx / distance) * vitesse
            self.vy = (dy / distance) * vitesse
        else:
            # Très proche ou pause → on freine progressivement.
            # *0.85 par frame = diminue d'environ 15% chaque frame.
            self.vx *= 0.85
            self.vy *= 0.85

        # ── 9) Application du mouvement : position += vitesse × temps ────────
        self.x += self.vx * dt
        self.y += self.vy * dt

    # ═════════════════════════════════════════════════════════════════════════
    #  3. MACHINE À ÉTATS [D22]
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Appelé depuis update() quand le timer d'état tombe à 0.
    #  Pas à modifier pour changer les vitesses (→ settings.py), mais à
    #  modifier ici si on veut ajouter un état ou changer les probabilités.

    def _choisir_nouvel_etat(self, distance):
        """Décide de l'état suivant et règle le timer self.temps_etat."""

        # Si on est trop loin du joueur, on court pour rattraper.
        if distance > settings.COMPAGNON_DIST_COURSE:
            self.etat = "court"
            self.temps_etat = random.uniform(1.0, 2.0)
            return

        # Sinon, on tire un nombre aléatoire entre 0 et 1 :
        #   - 10% de chance de faire une pause
        #   - 90% de chance de rester en mode "suit"
        tirage = random.random()
        if tirage < 0.1:
            self.etat = "pause"
            self.temps_etat = random.uniform(0.4, 1.0)
        else:
            self.etat = "suit"
            self.temps_etat = random.uniform(1.0, 3.0)

    # ═════════════════════════════════════════════════════════════════════════
    #  4. API UTILISÉE PAR CompagnonGroup
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  distance_au_joueur() sert dans CompagnonGroup.affecter_peur() :
    #     - si distance < COMPAGNON_DIST_RASSURANT → la peur baisse
    #     - sinon                                  → la peur monte

    def distance_au_joueur(self, joueur):
        """Renvoie la distance (pixels) entre le compagnon et le joueur.

        Si le compagnon est totalement dans la cape, la distance est
        considérée comme nulle (il est "avec" le joueur physiquement)."""

        if self.dans_cape and self.visibilite <= 0.01:
            return 0.0
        dx = joueur.rect.centerx - self.x
        dy = joueur.rect.centery - self.y
        return math.hypot(dx, dy)   # [D11]

    # ═════════════════════════════════════════════════════════════════════════
    #  5. RENDU — chef d'orchestre
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Appelé chaque frame par CompagnonGroup.draw(), lui-même appelé
    #  depuis core/game.py dans _dessiner_monde() juste après le joueur.
    #
    #  Pendant l'animation de cape, on interpole [D13] la position entre
    #  le compagnon et le joueur : il "rentre" dans le joueur en rétrécissant.

    def draw(self, surf, camera, joueur):
        """Dessine le compagnon sur surf."""

        # Totalement invisible → rien à faire (optimisation).
        if self.visibilite <= 0.01:
            return

        # ── Position affichée (interpolation linéaire [D13]) ────────────────
        #   visibilite = 1 → pos réelle du compagnon
        #   visibilite = 0 → pos du joueur
        #   entre les deux → mélange pondéré.
        # Formule classique : pos = (1 - t) * A  +  t * B
        # avec t = self.visibilite ∈ [0, 1].
        t = self.visibilite
        pos_x = (1 - t) * joueur.rect.centerx + t * self.x
        pos_y = (1 - t) * joueur.rect.centery + t * self.y

        # Petit flottement vertical (sinus [D12] → va et vient ±3 px).
        flottement = math.sin(self.oscillation) * 3

        # Coordonnées à l'écran (on retire l'offset de la caméra [D20]).
        sx = int(pos_x - camera.offset_x)
        sy = int(pos_y - camera.offset_y + flottement)

        # Échelle du corps : proportionnelle à la visibilité.
        #   visibilité = 1 → taille normale
        #   visibilité ≈ 0 → taille quasi nulle (on a déjà return juste au-dessus)
        echelle = self.visibilite
        largeur_corps = int(18 * echelle)
        hauteur_corps = int(20 * echelle)

        # Sécurité : si on est vraiment petit, inutile de dessiner.
        if largeur_corps <= 1 or hauteur_corps <= 1:
            return

        # Ordre de dessin (du fond vers le dessus) :
        #   1) lueur douce derrière le compagnon
        #   2) petits traits de mouvement (seulement en état "court")
        #   3) corps (ellipse blanche)
        #   4) yeux bleus + petite bouche
        self._dessiner_lueur(surf, sx, sy, echelle)
        if self.etat == "court":
            self._dessiner_trainee(surf, sx, sy, echelle)
        self._dessiner_corps(surf, sx, sy, largeur_corps, hauteur_corps)
        self._dessiner_yeux_et_sourire(surf, sx, sy, largeur_corps, hauteur_corps)

    # ═════════════════════════════════════════════════════════════════════════
    #  6. RENDU — pièces détachées
    # ═════════════════════════════════════════════════════════════════════════

    def _dessiner_lueur(self, surf, cx, cy, echelle):
        """Petit halo bleuté pulsant autour du compagnon.

        C'est ce qui donne l'effet "fantôme lumineux"."""

        # Rayon = base + pulsation (sinus oscille entre -3 et +3 px).
        # * 1.5 pour que la pulsation soit un peu plus rapide que le
        # flottement du corps (les deux effets se distinguent mieux).
        rayon_base = int(16 * echelle)
        pulsation = int(math.sin(self.oscillation * 1.5) * 3)
        rayon = rayon_base + pulsation
        if rayon < 4:
            return

        # On dessine la lueur sur une petite Surface à part [D1], avec
        # SRCALPHA [D2] pour qu'elle accepte la transparence. Sinon les
        # cercles transparents s'accumuleraient au-dessus du décor.
        taille = rayon * 2
        lueur = pygame.Surface((taille, taille), pygame.SRCALPHA)

        # Cercles concentriques de plus en plus opaques vers le centre.
        # range(rayon, 4, -3) = rayon, rayon-3, rayon-6, … (jusqu'à 4 exclu).
        # Pour chaque cercle :
        #   - plus il est petit (près du centre), plus alpha est grand
        #   - 80 = opacité max d'un cercle
        for r in range(rayon, 4, -3):
            alpha = int(80 * (r / rayon) * 0.5)
            couleur = (200, 220, 255, alpha)
            pygame.draw.circle(lueur, couleur, (rayon, rayon), r)

        # On colle la surface à l'écran, centrée sur le compagnon.
        surf.blit(lueur, (cx - rayon, cy - rayon))

    def _dessiner_trainee(self, surf, cx, cy, echelle):
        """Trois petits traits derrière le compagnon quand il court.

        Simule les "lignes de vitesse" des mangas/BDs."""

        # Si le compagnon va presque droit (vx ~ 0), on ne dessine rien.
        if abs(self.vx) < 10:
            return

        # Sens du mouvement horizontal (+1 droite, -1 gauche).
        if self.vx > 0:
            sens = 1
        else:
            sens = -1

        # Trois petits traits derrière lui (opposé au sens de déplacement).
        couleur = (210, 220, 240)
        for i in range(3):
            decalage_x = -sens * (8 + i * 6)   # -8, -14, -20  (si sens=1)
            decalage_y = (i - 1) * 4           # -4,   0,  +4
            x1 = cx + decalage_x
            y1 = cy + decalage_y
            x2 = x1 - sens * int(6 * echelle)
            y2 = y1
            pygame.draw.line(surf, couleur, (x1, y1), (x2, y2), 2)

    def _dessiner_corps(self, surf, cx, cy, largeur, hauteur):
        """Ellipse blanche qui forme le "blob" du compagnon.

        Changer les couleurs ici pour changer l'apparence du corps."""

        # On prépare le rectangle qui contient l'ellipse (pygame demande
        # un Rect pour draw.ellipse, pas un centre + rayons).
        rect = pygame.Rect(cx - largeur, cy - hauteur, largeur * 2, hauteur * 2)
        # Remplissage blanc cassé (très légèrement bleuté pour l'ambiance).
        pygame.draw.ellipse(surf, (250, 250, 255), rect)
        # Contour bleuté d'épaisseur 2 pour bien détacher le compagnon du fond.
        pygame.draw.ellipse(surf, (170, 180, 210), rect, 2)

    def _dessiner_yeux_et_sourire(self, surf, cx, cy, largeur, hauteur):
        """Deux petits cercles bleus + un trait pour la bouche."""

        # Quand le compagnon est très petit (en pleine animation de cape),
        # on n'affiche plus les détails — ça ferait sale.
        if largeur < 8:
            return

        # Écart entre les deux yeux et taille des yeux, proportionnels
        # à la taille actuelle du corps (pour que ça reste joli quand
        # le compagnon rétrécit).
        ecart_yeux = max(3, largeur // 3)
        taille_oeil = max(2, largeur // 6)

        # Yeux : deux petits cercles bleus.
        couleur_yeux = (70, 160, 220)
        oeil_y = cy - hauteur // 4
        pygame.draw.circle(surf, couleur_yeux, (cx - ecart_yeux, oeil_y), taille_oeil)
        pygame.draw.circle(surf, couleur_yeux, (cx + ecart_yeux, oeil_y), taille_oeil)

        # Bouche : un simple trait horizontal (on ne la dessine que si
        # le corps est assez grand pour que ça soit lisible).
        if largeur >= 10:
            bouche_y = cy + hauteur // 4
            demi_bouche = max(2, largeur // 5)
            pygame.draw.line(surf, (120, 140, 180),
                             (cx - demi_bouche, bouche_y),
                             (cx + demi_bouche, bouche_y), 2)
