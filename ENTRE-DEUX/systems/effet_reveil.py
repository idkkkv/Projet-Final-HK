# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Effet de réveil (lumière du matin)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Un effet visuel qui simule une lumière chaude qui entre par une fenêtre
#  imaginaire pendant que les oiseaux chantent dans la musique. Il est
#  synchronisé avec la position de lecture de pygame.mixer.music : à un
#  moment précis (debut_s), le halo commence à apparaître progressivement.
#
#  Trois couches superposées :
#     1) Un halo radial chaud (jaune-blanc), pré-rendu avec numpy pour
#        avoir un dégradé mathématiquement parfait sans banding.
#     2) Des particules de poussière qui flottent dans la lumière (animées,
#        avec pulsation alpha pour faire "vivant").
#     3) Un voile blanc doux par-dessus, qui adoucit l'image entière comme
#        si la pupille s'éblouissait.
#
#  Le résultat : sensation d'ouvrir les yeux après un long sommeil.
#
#  POURQUOI NUMPY ?
#  ----------------
#  Calculer un dégradé radial pixel par pixel en pur Python prend ~50 ms
#  pour 1280×720 — visible comme un freeze. numpy le fait en ~3 ms grâce
#  aux opérations vectorisées (toutes les lignes/colonnes calculées en
#  une seule instruction C optimisée). On le calcule UNE SEULE FOIS et
#  on cache le résultat dans self._halo_cache.
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  core/game.py crée l'effet :
#       self.effet_reveil = EffetReveil(debut_s=117, duree_cycle_s=...)
#  Et chaque frame :
#       self.effet_reveil.update(dt)
#       self.effet_reveil.draw(self.screen)
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Quand l'effet se déclenche → debut_s (constructeur)
#     - Couleur du halo            → arr3d[..., 0/1/2] dans _prerender_halo
#     - Position de la "fenêtre"   → cx, cy dans _prerender_halo
#     - Nombre de particules       → boucle for _ in range(25) du __init__
#     - Voile final intensité      → 50 dans `int(i * i * 50)` (draw)
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D1]  pygame.Surface       — halo, voile, surface temporaire
#     [D2]  SRCALPHA             — transparence des trois couches
#     [D3]  blit                 — empilement halo + voile
#     [D10] dt                   — interpolation de l'intensité, particules
#     [D12] math.sin             — pulsation alpha des particules
#     [D13] Interpolation linéaire — montée et descente de self.intensite
#
# ─────────────────────────────────────────────────────────────────────────────

import math
import random
import pygame
import numpy as np


class EffetReveil:
    """Halo de lumière chaude + poussière + voile blanc, déclenché par la musique.

    Gradient calculé avec numpy pour un dégradé sans banding."""

    # ═════════════════════════════════════════════════════════════════════════
    #  1. CONSTRUCTION
    # ═════════════════════════════════════════════════════════════════════════

    def __init__(self, debut_s=117, duree_cycle_s=0):
        """Crée l'effet.

        debut_s       = position (en secondes) dans la musique à laquelle
                        l'effet commence à monter en intensité.
        duree_cycle_s = durée totale de la musique en boucle (0 = ne boucle pas).
                        Si > 0, on fait pos_s % duree pour repérer
                        correctement debut_s dans chaque tour de boucle."""

        self.debut_s = debut_s
        self.duree_cycle_s = duree_cycle_s

        # Intensité affichée (0.0 à 1.0) et cible vers laquelle on tend.
        # On les sépare pour faire un fondu doux [D13] vers la cible.
        self.intensite = 0.0
        self._cible    = 0.0

        # Quand True : la cible est forcée à 0 même si la musique joue
        # encore. Permet à game.py de déclencher l'extinction de l'effet
        # AU MOMENT où on quitte le menu (sans attendre que la musique
        # soit coupée). Réinitialisé par activer_normal().
        self._force_extinction = False

        # Cache du halo pré-rendu (recalculé seulement si la taille change).
        self._halo_cache = None
        self._halo_size  = (0, 0)

        # Cache du voile blanc (Surface réutilisée pour ne pas en allouer
        # une nouvelle à chaque frame — le GC apprécie).
        self._veil      = None
        self._veil_size = (0, 0)

        # ── Particules de poussière ──────────────────────────────────────────
        # Coordonnées normalisées (0..1) → indépendantes de la résolution.
        # Chaque particule a sa propre vitesse, taille, alpha max, phase et
        # fréquence pour que toutes ne pulsent pas en rythme (ce qui ferait
        # un effet artificiel).
        self._particules = []
        for _ in range(25):
            self._particules.append({
                "x": random.random(),
                "y": random.uniform(0, 0.65),
                "vx": random.uniform(-0.002, 0.002),
                "vy": random.uniform(-0.006, -0.001),  # remontent (y < 0)
                "taille":    random.uniform(1.0, 2.2),
                "alpha_max": random.uniform(0.3, 0.7),
                "phase":     random.uniform(0, math.pi * 2),
                "freq":      random.uniform(0.5, 1.2),
            })

    # ═════════════════════════════════════════════════════════════════════════
    #  2. PRÉ-RENDU DU HALO (numpy, calculé une fois)
    # ═════════════════════════════════════════════════════════════════════════

    def _prerender_halo(self, w, h):
        """Gradient radial parfait pixel par pixel via numpy.

        Renvoie une Surface SRCALPHA déjà remplie. Mise en cache : on ne
        recalcule que si la taille de l'écran change (rarissime)."""

        # Cache hit : taille inchangée → on renvoie directement.
        if self._halo_cache is not None and self._halo_size == (w, h):
            return self._halo_cache

        # ── Grille de coordonnées (h, w) ─────────────────────────────────────
        # np.meshgrid construit deux matrices xx et yy telles que
        # xx[y, x] = x et yy[y, x] = y. C'est ce qui permet de calculer
        # la distance en une opération vectorisée plus bas.
        xs = np.arange(w, dtype=np.float32)
        ys = np.arange(h, dtype=np.float32)
        xx, yy = np.meshgrid(xs, ys)  # forme (h, w)

        # ── Source de lumière virtuelle ──────────────────────────────────────
        # Au-dessus du centre de l'écran (cy négatif → hors écran),
        # comme une fenêtre invisible plus haut.
        cx = w / 2
        cy = -h * 0.12

        # ── Distance de chaque pixel à la source ─────────────────────────────
        dist  = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        max_r = max(w, h) * 0.85

        # Dégradé linéaire normalisé puis cubique : la cubique donne une
        # chute plus douce au début et plus marquée vers les bords (= une
        # vraie lumière atténuée au carré inverse, simplifiée).
        grad  = np.clip(1.0 - dist / max_r, 0, 1) ** 3
        alpha = (grad * 140).astype(np.uint8)  # forme (h, w)

        # ── Construction de la Surface RGBA ──────────────────────────────────
        # surfarray.pixels3d et pixels_alpha donnent un accès DIRECT aux
        # pixels (modifications in-place). del après usage = on libère le
        # "lock" sur la surface, sinon impossible de blit dessus.
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        arr3d = pygame.surfarray.pixels3d(surf)   # forme (w, h, 3)
        arr3d[:, :, 0] = 255   # R — blanc chaud, légèrement orangé
        arr3d[:, :, 1] = 252   # G
        arr3d[:, :, 2] = 235   # B
        del arr3d

        arr_a = pygame.surfarray.pixels_alpha(surf)  # forme (w, h)
        # ⚠️ Transposer (h, w) → (w, h) car surfarray utilise l'autre
        # convention que numpy (Surface en (w, h), array en (h, w)).
        arr_a[:] = alpha.T
        del arr_a

        self._halo_cache = surf
        self._halo_size  = (w, h)
        return self._halo_cache

    # ═════════════════════════════════════════════════════════════════════════
    #  3. UPDATE (synchronisation avec la musique + animation particules)
    # ═════════════════════════════════════════════════════════════════════════

    def forcer_extinction(self):
        """Force la cible à 0 indépendamment de la musique. Utilisé par
        game.py quand on quitte le menu titre : l'effet commence à
        s'estomper TOUT DE SUITE, sans attendre que la musique se coupe."""
        self._force_extinction = True

    def reactiver(self):
        """Annule forcer_extinction(). À appeler quand on revient au menu."""
        self._force_extinction = False

    def update(self, dt):
        """Calcule l'intensité cible selon la position dans la musique,
        puis lisse l'intensité affichée vers cette cible."""

        # ── Extinction forcée (transition menu → jeu) ────────────────────────
        if self._force_extinction:
            self._cible = 0.0
        # ── Pas de musique en cours → tout retombe vers 0 ────────────────────
        elif not pygame.mixer.music.get_busy():
            self._cible = 0.0
        else:
            # Position en secondes (get_pos renvoie des millisecondes).
            pos_s = pygame.mixer.music.get_pos() / 1000

            # Si la musique boucle, on travaille modulo la durée pour
            # repérer debut_s à chaque tour.
            if self.duree_cycle_s > 0:
                pos_s = pos_s % self.duree_cycle_s

            if pos_s >= self.debut_s:
                # On calcule la progression entre debut_s et la fin du cycle.
                # Sans cycle on suppose 30 s pour la montée maximale.
                if self.duree_cycle_s > 0:
                    restant = self.duree_cycle_s - self.debut_s
                    progress = (pos_s - self.debut_s) / max(1, restant)
                else:
                    progress = (pos_s - self.debut_s) / 30
                # *1.3 puis clamp 1.0 → on atteint 1.0 avant la fin et on
                # reste au max sur le dernier ~20 % du cycle.
                self._cible = min(1.0, progress * 1.3)
            else:
                self._cible = 0.0

        # ── Lissage de l'intensité vers la cible (interpolation [D13]) ───────
        # Vitesses différentes pour la montée (rapide, dt*0.6) et la
        # descente (très lente, dt*0.12) → l'effet apparaît comme une
        # révélation et S'ÉTEINT TRÈS PROGRESSIVEMENT quand on lance une
        # partie / le mode éditeur (≈8 s avant disparition complète, on
        # garde donc un peu d'ambiance "bonne nuit" pendant le début du jeu).
        if self._cible > self.intensite:
            self.intensite += (self._cible - self.intensite) * min(1.0, dt * 0.6)
        else:
            self.intensite += (self._cible - self.intensite) * min(1.0, dt * 0.12)

        # Petit seuil pour éviter de garder une intensité résiduelle qui
        # ferait dessiner pour rien (et qui n'atteindrait jamais 0).
        if self.intensite < 0.002:
            self.intensite = 0.0

        # ── Animation des particules (seulement si l'effet est visible) ──────
        if self.intensite > 0.05:
            for p in self._particules:
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
                # Sortie par le haut → on relance en bas
                if p["y"] < -0.03:
                    p["y"] = random.uniform(0.5, 0.7)
                    p["x"] = random.random()
                # Sortie horizontale → on enroule (toroïdal)
                if p["x"] < -0.03:
                    p["x"] = 1.03
                elif p["x"] > 1.03:
                    p["x"] = -0.03

    # ═════════════════════════════════════════════════════════════════════════
    #  4. RENDU (3 couches : halo, particules, voile)
    # ═════════════════════════════════════════════════════════════════════════

    def draw(self, screen):
        """Dessine les 3 couches dans l'ordre fond → premier plan."""

        # Optimisation : intensité quasi nulle → rien à dessiner.
        if self.intensite < 0.005:
            return

        w, h = screen.get_size()
        i = self.intensite
        t = pygame.time.get_ticks() / 1000

        # ── 1) Halo de lumière (gradient numpy modulé par l'intensité) ───────
        halo = self._prerender_halo(w, h)

        # On ne peut pas multiplier l'alpha du halo en place (cache !), donc
        # on prépare un masque blanc d'opacité = i et on le multiplie au halo
        # via BLEND_RGBA_MULT sur une surface temporaire.
        alpha_global = int(i * 255)
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        mask.fill((255, 255, 255, alpha_global))

        temp = pygame.Surface((w, h), pygame.SRCALPHA)
        temp.blit(halo, (0, 0))
        temp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        screen.blit(temp, (0, 0))

        # ── 2) Particules de poussière dans la lumière ───────────────────────
        # Apparaissent quand l'intensité dépasse 0.08 (sinon on verrait des
        # points lumineux flotter sur du noir, bizarre).
        if i > 0.08:
            for p in self._particules:
                # Pulsation alpha : sinus normalisé entre 0.4 et 1.0.
                pulse = 0.4 + 0.6 * ((1 + math.sin(t * p["freq"] + p["phase"])) / 2)
                a = int(i * p["alpha_max"] * pulse * 255)
                # Particule trop transparente → on saute pour économiser.
                if a < 8:
                    continue

                # Conversion coordonnées normalisées → pixels écran.
                px = int(p["x"] * w)
                py = int(p["y"] * h)
                taille  = max(1, int(p["taille"]))
                couleur = (255, 255, 230, min(255, a))

                # Particule de 1 px : set_at est plus rapide qu'un draw.circle.
                # try/except : si la particule sort de l'écran, set_at lève IndexError.
                if taille <= 1:
                    try:
                        screen.set_at((px, py), couleur)
                    except IndexError:
                        pass
                else:
                    pygame.draw.circle(screen, couleur, (px, py), taille)

        # ── 3) Voile blanc doux (effet "éblouissement") ──────────────────────
        # i² (i*i) : croît plus lentement au début → le voile reste léger
        # tant que l'effet n'est pas pleinement développé. Plafonné à 130.
        a_voile = int(i * i * 50)
        if a_voile > 0:
            # Réutilisation de la même Surface pour éviter d'allouer à chaque frame.
            if self._veil is None or self._veil_size != (w, h):
                self._veil = pygame.Surface((w, h), pygame.SRCALPHA)
                self._veil_size = (w, h)
            self._veil.fill((255, 255, 245, min(130, a_voile)))
            screen.blit(self._veil, (0, 0))
