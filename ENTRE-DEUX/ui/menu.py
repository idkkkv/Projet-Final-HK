# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Menus (titre, pause, fin)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Une seule classe `Menu` qui sait dessiner trois sortes d'écrans :
#
#     style="titre"   → fond sombre total + particules flottantes +
#                        petit personnage qui traverse
#                        (utilisé quand il n'y a rien d'intéressant derrière :
#                         écran de démarrage, écran de fin)
#
#     style="panneau" → cadre semi-transparent centré sur le fond actuel
#                        (utilisé pour la pause : on voit le jeu derrière)
#
#  On lui passe une liste d'options (["Nouvelle partie", "Quitter"]), elle
#  gère la sélection au clavier et renvoie la chaîne choisie.
#
#  Ce fichier contient aussi deux classes décoratives :
#     - Particule       → poussière lumineuse qui flotte vers le haut
#     - PersonnageMenu  → petit bonhomme lumineux qui passe en fond
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  core/game.py crée trois menus principaux :
#       self.main_menu  = Menu([...], title="LIMINAL", style="titre")
#       self.pause_menu = Menu([...], title="PAUSE",   style="panneau")
#       self.end_menu   = Menu([...], title="FIN",     style="titre")
#  Puis dans sa boucle :
#       menu.handle_key(event.key)  →  renvoie "Quitter" ou None
#       menu.update(dt)
#       menu.draw(screen)
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Nombre de particules     → _init_particules() (actuellement 45)
#     - Couleur des particules   → Particule.COULEURS
#     - Polices                  → _init_polices()
#     - Couleur du titre / hover → _dessiner_ecran_titre / _dessiner_panneau
#     - Dimensions du panneau    → _dessiner_panneau (panneau_w / panneau_h)
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D1]  pygame.Surface       — particules et voile semi-transparent
#     [D2]  SRCALPHA             — transparence des lueurs et du voile
#     [D3]  blit                 — coller les surfaces sur l'écran
#     [D6]  pygame.draw          — cercles, lignes, rectangles
#     [D10] dt                   — déplacement des particules
#     [D12] math.sin             — pulsation de la lueur du personnage
#     [D22] Machine à états      — self._visible du PersonnageMenu
#     [D33] List comprehension   — création des 45 particules
#
# ─────────────────────────────────────────────────────────────────────────────

import math
import random
import pygame
from audio import sound_manager as sfx


# ═════════════════════════════════════════════════════════════════════════════
#  1. PARTICULE DÉCORATIVE (poussière lumineuse)
# ═════════════════════════════════════════════════════════════════════════════

class Particule:
    """Petite lueur qui flotte vers le haut dans le fond du menu titre.

    Inspiré de l'ambiance Hollow Knight — poussière lumineuse dans l'obscurité.
    Chaque particule a sa propre couleur, vitesse et opacité. Quand elle sort
    par le haut, on la "réincarne" en bas avec de nouveaux paramètres."""

    # Palette de 4 couleurs. On en pioche une au hasard dans _respawn().
    COULEURS = [
        (180, 160, 255),  # violet clair
        (255, 220, 100),  # doré
        (140, 200, 255),  # bleu-blanc
        (200, 255, 200),  # vert très pâle
    ]

    def __init__(self, largeur, hauteur):
        """Crée une particule quelque part dans l'écran (largeur × hauteur)."""
        self._w = largeur
        self._h = hauteur
        self._respawn()

    def _respawn(self):
        """Donne à la particule une position et des paramètres aléatoires.

        Appelé à la création et à chaque fois qu'elle sort de l'écran."""
        self.x       = random.uniform(0, self._w)
        self.y       = random.uniform(0, self._h)
        self.vx      = random.uniform(-12, 12)
        self.vy      = random.uniform(-30, -8)   # remonte lentement (y négatif)
        self.rayon   = random.uniform(1.0, 2.5)
        self.alpha   = random.randint(40, 160)
        self.couleur = random.choice(self.COULEURS)

    def update(self, dt):
        """Avance la particule selon sa vitesse. dt = temps écoulé [D10]."""
        self.x += self.vx * dt
        self.y += self.vy * dt
        # Quand elle sort de l'écran, elle réapparaît en bas avec une
        # nouvelle position / vitesse (plus léger que de la recréer).
        if self.y < -4 or self.x < -4 or self.x > self._w + 4:
            self.x = random.uniform(0, self._w)
            self.y = self._h + 4
            self.vx = random.uniform(-12, 12)
            self.vy = random.uniform(-30, -8)

    def draw(self, surf):
        """Dessine la particule (petit cercle semi-transparent)."""
        # On passe par une petite Surface [D1] avec SRCALPHA [D2] pour
        # gérer proprement la transparence du cercle. Dessiner directement
        # un cercle alpha sur surf peut donner des artefacts.
        taille = int(self.rayon * 2) + 2
        s = pygame.Surface((taille, taille), pygame.SRCALPHA)
        centre = (taille // 2, taille // 2)
        pygame.draw.circle(s, (*self.couleur, self.alpha), centre, int(self.rayon))
        surf.blit(s, (int(self.x) - taille // 2, int(self.y) - taille // 2))


# ═════════════════════════════════════════════════════════════════════════════
#  2. PERSONNAGE ANIMÉ (silhouette qui traverse le menu titre)
# ═════════════════════════════════════════════════════════════════════════════

class PersonnageMenu:
    """Petit personnage qui se balade en fond du menu titre avec une lueur.

    Machine à états simplifiée [D22] : alterne "invisible, attend" et
    "visible, marche" pour donner de la vie sans distraire du menu."""

    def __init__(self, largeur, hauteur):
        self._w = largeur
        self._h = hauteur

        # Position de départ : en dehors de l'écran à gauche
        self.x = -40.0
        self.y = hauteur * 0.82

        # Vitesse et direction (+1 = vers la droite, -1 = vers la gauche)
        self.vx = random.uniform(18, 30)
        self.direction = 1

        # Timers pour l'alternance "caché ↔ visible"
        self._timer_pause = 0.0
        self._timer_attente = random.uniform(4, 12)
        self._visible = False

        # Animation de marche (4 frames)
        self._anim_timer = 0.0
        self._frame = 0

        # Lueur pulsante autour du personnage
        self._lueur_alpha = 0
        self._lueur_pulse = 0.0

        # Couleurs (corps + lueur)
        self._couleur = (180, 160, 230)
        self._lueur_couleur = (140, 120, 255)

    def update(self, dt):
        """Avance l'animation, gère l'apparition et la disparition."""
        self._anim_timer += dt
        self._lueur_pulse += dt * 3   # vitesse de la pulsation lumineuse

        # ── État "invisible" : on attend puis on réapparaît ──────────────────
        if not self._visible:
            self._timer_attente -= dt
            if self._timer_attente <= 0:
                # Retour en scène : on choisit un côté au hasard, une vitesse,
                # une hauteur sur le sol, et on se place juste hors écran.
                self._visible = True
                self.direction = random.choice([-1, 1])
                self.vx = random.uniform(20, 35)
                if self.direction == 1:
                    self.x = -30
                else:
                    self.x = self._w + 30
                self.y = self._h * random.uniform(0.75, 0.88)
                self._lueur_alpha = 0
            return

        # ── État "visible" : avance et calcule la lueur ──────────────────────
        self.x += self.vx * self.direction * dt

        # La lueur apparaît progressivement au début de la traversée
        # (prog < 0.1) et disparaît à la fin (prog > 0.9). Cela évite
        # qu'elle surgisse et disparaisse brutalement.
        if self.direction == 1:
            prog = self.x / self._w
        else:
            prog = 1 - self.x / self._w
        if prog < 0.1:
            self._lueur_alpha = min(120, int(prog * 1200))
        elif prog > 0.9:
            self._lueur_alpha = max(0, int((1 - prog) * 1200))
        else:
            self._lueur_alpha = 120

        # Animation de marche : on change de frame toutes les 0,3 s
        if self._anim_timer > 0.3:
            self._frame = (self._frame + 1) % 4
            self._anim_timer = 0

        # Sorti de l'écran → on repasse en invisible pour 6 à 18 secondes
        if self.x < -40 or self.x > self._w + 40:
            self._visible = False
            self._timer_attente = random.uniform(6, 18)

    def draw(self, surf):
        """Dessine la lueur + le petit personnage (tête, corps, bras, jambes)."""
        if not self._visible:
            return
        x = int(self.x)
        y = int(self.y)

        # ── Lueur douce autour du personnage ─────────────────────────────────
        # pulse = oscillation [D12] qui fait "respirer" le rayon.
        pulse = math.sin(self._lueur_pulse) * 15
        rayon_lueur = int(28 + pulse)
        if self._lueur_alpha > 0:
            # Surface SRCALPHA dédiée [D1][D2] pour le halo.
            lueur_surf = pygame.Surface((rayon_lueur * 2, rayon_lueur * 2), pygame.SRCALPHA)
            # Cercles concentriques de plus en plus opaques (effet "glow").
            for r in range(rayon_lueur, 4, -4):
                a = int(self._lueur_alpha * (r / rayon_lueur) * 0.4)
                pygame.draw.circle(lueur_surf, (*self._lueur_couleur, a),
                                   (rayon_lueur, rayon_lueur), r)
            surf.blit(lueur_surf, (x - rayon_lueur, y - 10 - rayon_lueur))

        # ── Silhouette (dessin à la main, pas de sprite PNG) ─────────────────
        # Tête
        pygame.draw.circle(surf, self._couleur, (x, y - 16), 5)
        # Corps
        pygame.draw.line(surf, self._couleur, (x, y - 11), (x, y), 2)
        # Bras — petite alternance selon la frame pour simuler le balancement
        bras_offset = 2 if self._frame in (1, 3) else -1
        pygame.draw.line(surf, self._couleur, (x, y - 8), (x - 4, y - 4 + bras_offset), 1)
        pygame.draw.line(surf, self._couleur, (x, y - 8), (x + 4, y - 4 - bras_offset), 1)
        # Jambes (4 poses selon self._frame)
        if self._frame == 0:
            pygame.draw.line(surf, self._couleur, (x, y), (x - 3, y + 7), 1)
            pygame.draw.line(surf, self._couleur, (x, y), (x + 3, y + 7), 1)
        elif self._frame == 1:
            pygame.draw.line(surf, self._couleur, (x, y), (x - 4, y + 6), 1)
            pygame.draw.line(surf, self._couleur, (x, y), (x + 1, y + 7), 1)
        elif self._frame == 2:
            pygame.draw.line(surf, self._couleur, (x, y), (x - 2, y + 7), 1)
            pygame.draw.line(surf, self._couleur, (x, y), (x + 2, y + 7), 1)
        else:
            pygame.draw.line(surf, self._couleur, (x, y), (x - 1, y + 7), 1)
            pygame.draw.line(surf, self._couleur, (x, y), (x + 4, y + 6), 1)


# ═════════════════════════════════════════════════════════════════════════════
#  3. MENU — classe principale
# ═════════════════════════════════════════════════════════════════════════════

class Menu:
    """Menu réutilisable pour le titre, la pause et l'écran de fin.

    style="titre"   → fond sombre total + particules flottantes
                       (utilisé quand il n'y a rien derrière)

    style="panneau" → petit cadre semi-transparent centré sur le fond actuel
                       (utilisé pour la pause et le game over — on voit le jeu)

    Positions configurables :
        title_y         → position Y du titre (ratio 0.0 - 1.0 de l'écran)
        options_y       → position Y du début des options (ratio)
        offset_x        → décalage horizontal en pixels
        offset_y        → décalage vertical en pixels (pour panneau)
        options_spacing → espacement vertical entre options en pixels
    """

    # ── Construction ─────────────────────────────────────────────────────────

    def __init__(self, options, title="", style="panneau",
                 offset_x=0, offset_y=0,
                 title_y=0.25, options_y=0.48, options_spacing=42):
        """Crée un menu. `options` = liste de chaînes (le texte des choix)."""
        self.options   = options
        self.title     = title
        self.style     = style
        self.selection = 0        # index de l'option surlignée

        # Positions configurables (pour que le même code serve aux 3 menus)
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.title_y = title_y                 # ratio vertical du titre
        self.options_y = options_y             # ratio vertical des options
        self.options_spacing = options_spacing # pixels entre chaque option

        # Initialisation paresseuse (lazy) : les particules, personnage et
        # polices sont créés à la première utilisation. Ça évite de consommer
        # de la mémoire pour des menus qu'on n'a pas encore ouverts.
        self._particules        = []
        self._personnage        = None
        self._police_titre      = None
        self._police_option     = None
        self._police_option_sel = None
        self._police_sous       = None

        # Animation : phase qui pulse (sin) pour glow + barre accent.
        self._anim_t = 0.0

    # ═════════════════════════════════════════════════════════════════════════
    #  4. INITIALISATION PARESSEUSE (lazy init)
    # ═════════════════════════════════════════════════════════════════════════

    def _init_polices(self):
        """Charge les polices la première fois qu'on dessine le menu.

        On ne peut pas charger une police avant pygame.font.init(), c'est
        pourquoi on le fait ici et pas dans __init__.

        REFONTE V2 : on garde les mêmes attributs (compat) mais on
        utilise des polices plus modernes et un peu plus rondes.
        """
        if self._police_titre is None:
            # Cambria/Constantia ont un rendu plus contemporain que Georgia
            # tout en restant "sérieux/narratif". Si la police n'existe pas
            # sur le système, pygame retombe sur la police par défaut.
            self._police_titre         = pygame.font.SysFont("Cambria",  76, bold=True)
            self._police_titre_panneau = pygame.font.SysFont("Cambria",  34, bold=True)
            self._police_option        = pygame.font.SysFont("Consolas", 21)
            self._police_option_sel    = pygame.font.SysFont("Consolas", 23, bold=True)
            self._police_sous          = pygame.font.SysFont("Consolas", 13)

    def _init_particules(self, w, h):
        """Crée 45 particules à la première frame (liste vide → on remplit).

        Utilise une list comprehension [D33] : on construit la liste en une
        seule expression au lieu d'une boucle for avec append."""
        if not self._particules:
            self._particules = [Particule(w, h) for _ in range(45)]

    # ═════════════════════════════════════════════════════════════════════════
    #  5. UPDATE (appeler chaque frame)
    # ═════════════════════════════════════════════════════════════════════════

    def update(self, dt):
        """Avance les particules + le timer d'animation."""
        surf = pygame.display.get_surface()
        if surf:
            self._init_particules(*surf.get_size())
        for p in self._particules:
            p.update(dt)
        self._anim_t += dt

    # ═════════════════════════════════════════════════════════════════════════
    #  6. ENTRÉES CLAVIER
    # ═════════════════════════════════════════════════════════════════════════

    def handle_key(self, key):
        """Gère les touches fléchées et Entrée/Espace.

        Renvoie la chaîne de l'option choisie, ou None si pas de validation.
        Joue aussi les petits sons d'interface (ui_nav, ui_select, ui_back)."""

        if key == pygame.K_UP:
            # Modulo pour boucler de la première à la dernière option.
            self.selection = (self.selection - 1) % len(self.options)
            sfx.jouer("ui_nav", 0.3)
        elif key == pygame.K_DOWN:
            self.selection = (self.selection + 1) % len(self.options)
            sfx.jouer("ui_nav", 0.3)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            # On renvoie la chaîne exacte : c'est l'appelant qui interprète
            # ("Nouvelle partie", "Continuer", "Quitter", etc.).
            sfx.jouer("ui_select", 0.4)
            return self.options[self.selection]
        elif key == pygame.K_ESCAPE:
            sfx.jouer("ui_back", 0.3)
        return None

    # ═════════════════════════════════════════════════════════════════════════
    #  7. RENDU — aiguillage selon le style
    # ═════════════════════════════════════════════════════════════════════════

    def draw(self, surf):
        """Dessine le menu sur surf.

        Aiguille vers _dessiner_ecran_titre (fond plein écran) ou
        _dessiner_panneau (cadre centré) selon self.style."""

        self._init_polices()
        w, h = surf.get_size()

        if self.style == "titre":
            self._dessiner_ecran_titre(surf, w, h)
        else:
            self._dessiner_panneau(surf, w, h)

    # ═════════════════════════════════════════════════════════════════════════
    #  8. RENDU — écran titre (fond plein écran)
    # ═════════════════════════════════════════════════════════════════════════

    def _dessiner_ecran_titre(self, surf, w, h):
        """Menu titre — refonte V2 (violet).

        Esthétique : palette violet sombre + accent doré.
          - fond très sombre (6, 6, 18) presque noir
          - titre avec halo violet doux
          - ligne décorative classique avec losanges aux extrémités
          - sélection : glow doré pulsant + barre verticale dorée à gauche
          - particules / lueurs conservées
        """
        import math

        # ── Fond très sombre (style "profondeurs") ───────────────────────
        fond = pygame.Surface((w, h), pygame.SRCALPHA)
        fond.fill((6, 6, 18, 245))
        surf.blit(fond, (0, 0))

        # ── Particules / Lueurs ─────────────────────────────────────────
        self._init_particules(w, h)
        for p in self._particules:
            p.draw(surf)

        cx = w // 2 + self.offset_x
        cy_titre = int(h * self.title_y) + self.offset_y

        # ── Titre avec halo violet ───────────────────────────────────────
        if self.title:
            # 3 calques de halo à différents offsets/alphas pour un glow doux.
            for offset, alpha in ((0, 80), (1, 50), (2, 25)):
                halo = self._police_titre.render(self.title, True, (130, 100, 220))
                halo.set_alpha(alpha)
                surf.blit(halo,
                          (cx - halo.get_width() // 2 - offset, cy_titre - offset))
                surf.blit(halo,
                          (cx - halo.get_width() // 2 + offset, cy_titre + offset))

            titre_surf = self._police_titre.render(self.title, True, (210, 190, 255))
            surf.blit(titre_surf, (cx - titre_surf.get_width() // 2, cy_titre))

        # ── Ligne décorative sous le titre (style classique avec losanges) ─
        lx1 = cx - w // 4
        lx2 = cx + w // 4
        ly  = cy_titre + 95
        pygame.draw.line(surf, (80, 60, 160), (lx1, ly), (lx2, ly), 1)
        # Petits losanges aux extrémités de la ligne
        for lx in (lx1, lx2):
            points = [(lx, ly - 4), (lx + 4, ly), (lx, ly + 4), (lx - 4, ly)]
            pygame.draw.polygon(surf, (130, 100, 220), points)

        # ── Options ──────────────────────────────────────────────────────
        debut_y = int(h * self.options_y) + self.offset_y
        max_h        = h - debut_y - 60
        max_visible  = max(3, max_h // self.options_spacing)
        n            = len(self.options)
        if n <= max_visible:
            scroll_start, scroll_end = 0, n
        else:
            scroll_start = max(0, min(n - max_visible,
                                      self.selection - max_visible // 2))
            scroll_end = scroll_start + max_visible

        max_text_w = w - 100
        # Pulse pour la sélection (utilisé pour la couleur du glow)
        pulse = 0.5 + 0.5 * math.sin(self._anim_t * 3.5)

        for i in range(scroll_start, scroll_end):
            option = self.options[i]
            est_sel = (i == self.selection)

            # Couleur + police selon état (palette violette restaurée)
            if est_sel:
                couleur = (255, 215, 70)
                police  = self._police_option_sel
            else:
                couleur = (150, 135, 200)
                police  = self._police_option

            opt_surf = police.render(option, True, couleur)
            if opt_surf.get_width() > max_text_w:
                texte = option
                while texte and police.size(texte + "…")[0] > max_text_w:
                    texte = texte[:-1]
                opt_surf = police.render(texte + "…", True, couleur)

            ox = cx - opt_surf.get_width() // 2
            oy = debut_y + (i - scroll_start) * self.options_spacing

            if est_sel:
                # Glow doré pulsant derrière le texte
                glow_alpha = int(80 + 60 * pulse)
                glow = police.render(option, True, (255, 195, 90))
                glow.set_alpha(glow_alpha)
                surf.blit(glow, (ox - 1, oy - 1))
                surf.blit(glow, (ox + 1, oy + 1))
                # Barre verticale dorée à gauche du texte (signature "actif")
                bar_h = opt_surf.get_height()
                pygame.draw.rect(surf, (255, 215, 70),
                                 (ox - 24, oy + 2, 3, bar_h - 4))

            surf.blit(opt_surf, (ox, oy))

        # Indicateurs scroll
        if scroll_start > 0:
            up = self._police_option.render("▲", True, (150, 135, 200))
            surf.blit(up, (cx - up.get_width() // 2, debut_y - 26))
        if scroll_end < n:
            dn = self._police_option.render("▼", True, (150, 135, 200))
            surf.blit(dn, (cx - dn.get_width() // 2,
                           debut_y + (scroll_end - scroll_start)
                           * self.options_spacing + 4))

        # Aide en bas
        aide = self._police_sous.render(
            "↑↓  naviguer    ⏎  valider", True, (70, 60, 110))
        surf.blit(aide, (cx - aide.get_width() // 2, h - 32))

        # Indicateurs "il y en a au-dessus / en-dessous"
        if scroll_start > 0:
            up = self._police_option.render("▲", True, (150, 135, 200))
            surf.blit(up, (cx - up.get_width() // 2, debut_y - 28))
        if scroll_end < n:
            dn = self._police_option.render("▼", True, (150, 135, 200))
            surf.blit(dn, (cx - dn.get_width() // 2,
                           debut_y + (scroll_end - scroll_start) * self.options_spacing + 4))

        # ── Petite indication en bas ─────────────────────────────────────────
        aide = self._police_sous.render("↑↓ Naviguer   Entrée Valider", True, (70, 60, 110))
        surf.blit(aide, (cx - aide.get_width() // 2, h - 30))

    # ═════════════════════════════════════════════════════════════════════════
    #  9. RENDU — panneau flottant (pause)
    # ═════════════════════════════════════════════════════════════════════════

    def _dessiner_panneau(self, surf, w, h):
        """Panneau flottant V2 — pause / fin (palette violette).

        Refonte : double bordure violette + accents dorés aux coins +
        glow doré pulsant sur la sélection. Plus moderne que la v1
        sans dénaturer l'esprit "violet" du jeu.
        """
        import math

        # ── Voile légèrement violacé ─────────────────────────────────────
        voile = pygame.Surface((w, h), pygame.SRCALPHA)
        voile.fill((10, 6, 22, 120))
        surf.blit(voile, (0, 0))

        # ── Dimensions du panneau — s'adaptent au texte le plus large ────────
        nb_options = len(self.options)
        ft = self._police_titre_panneau
        # On calcule la largeur de texte la plus grande parmi les options
        # (plus un padding de 60 px). Si une option est très longue, le
        # panneau s'élargit.
        max_opt_w = max(
            (self._police_option.size(f" >  {o}")[0] for o in self.options),
            default=200
        ) + 60
        if self.title:
            max_opt_w = max(max_opt_w, ft.size(self.title)[0] + 60)
        panneau_w = max(300, min(max_opt_w, w - 60))
        panneau_h = 50 + nb_options * self.options_spacing + (80 if self.title else 20)

        px = (w - panneau_w) // 2 + self.offset_x
        py = (h - panneau_h) // 2 + self.offset_y

        # ── Fond du panneau (violet sombre presque opaque) ────────────────
        panneau = pygame.Surface((panneau_w, panneau_h), pygame.SRCALPHA)
        panneau.fill((14, 10, 28, 230))
        surf.blit(panneau, (px, py))

        # Double bordure violette (style "gravé") + petits coins dorés.
        pygame.draw.rect(surf, (110, 90, 200),
                         (px, py, panneau_w, panneau_h), 1)
        pygame.draw.rect(surf, (50, 40, 90),
                         (px + 3, py + 3, panneau_w - 6, panneau_h - 6), 1)
        # Coins dorés (signature visuelle — signe que la pause est un
        # moment "important"). Petite équerre L à chaque angle.
        c = 12
        for (ax, ay, dx, dy) in (
                (px,             py,             +1, +1),
                (px + panneau_w, py,             -1, +1),
                (px,             py + panneau_h, +1, -1),
                (px + panneau_w, py + panneau_h, -1, -1)):
            pygame.draw.line(surf, (255, 215, 70),
                             (ax, ay), (ax + dx * c, ay), 2)
            pygame.draw.line(surf, (255, 215, 70),
                             (ax, ay), (ax, ay + dy * c), 2)

        y_courant = py + 18

        # ── Titre du panneau (violet clair) ───────────────────────────────
        centre_x = px + panneau_w // 2
        if self.title:
            t = ft.render(self.title, True, (210, 190, 255))
            surf.blit(t, (centre_x - t.get_width() // 2, y_courant))
            y_courant += t.get_height() + 12

            # Séparateur dégradé violet sous le titre (plus joli qu'une
            # ligne pleine).
            sep_y = y_courant - 6
            for i in range(60):
                t1 = i / 60
                ox = int(px + 20 + (panneau_w - 40) * t1)
                w_seg = max(1, int((panneau_w - 40) / 60))
                opacite = int(180 * math.sin(t1 * math.pi))
                tmp = pygame.Surface((w_seg, 1), pygame.SRCALPHA)
                tmp.fill((130, 100, 220, opacite))
                surf.blit(tmp, (ox, sep_y))

        # ── Options ───────────────────────────────────────────────────────
        pulse = 0.5 + 0.5 * math.sin(self._anim_t * 3.5)
        for i, option in enumerate(self.options):
            est_sel = (i == self.selection)
            if est_sel:
                couleur = (255, 215, 70)
                police  = self._police_option_sel
            else:
                couleur = (150, 135, 200)
                police  = self._police_option

            opt_surf = police.render(option, True, couleur)
            ox = centre_x - opt_surf.get_width() // 2
            oy = y_courant + i * self.options_spacing

            if est_sel:
                # Glow doré pulsant
                glow_alpha = int(80 + 60 * pulse)
                glow = police.render(option, True, (255, 195, 90))
                glow.set_alpha(glow_alpha)
                surf.blit(glow, (ox - 1, oy - 1))
                surf.blit(glow, (ox + 1, oy + 1))
                # Barre verticale dorée à gauche
                bar_h = opt_surf.get_height()
                pygame.draw.rect(surf, (255, 215, 70),
                                 (ox - 18, oy + 2, 3, bar_h - 4))

            surf.blit(opt_surf, (ox, oy))
