# ─────────────────────────────────────────
#  ENTRE-DEUX — Menus (titre, pause, fin)
# ─────────────────────────────────────────

import math
import random
import pygame
from audio import sound_manager as sfx


# ── Particule décorative ──────────────────────────────────────────────────────

class Particule:
    """
    Petite lueur qui flotte vers le haut dans le fond du menu titre.
    Inspiré de l'ambiance Hollow Knight — poussière lumineuse dans l'obscurité.
    """

    COULEURS = [
        (180, 160, 255),  # violet clair
        (255, 220, 100),  # doré
        (140, 200, 255),  # bleu-blanc
        (200, 255, 200),  # vert très pâle
    ]

    def __init__(self, largeur, hauteur):
        self._w = largeur
        self._h = hauteur
        self._respawn()

    def _respawn(self):
        self.x      = random.uniform(0, self._w)
        self.y      = random.uniform(0, self._h)
        self.vx     = random.uniform(-12, 12)
        self.vy     = random.uniform(-30, -8)   # remonte lentement
        self.rayon  = random.uniform(1.0, 2.5)
        self.alpha  = random.randint(40, 160)
        self.couleur = random.choice(self.COULEURS)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        # Quand la particule sort de l'écran, elle réapparaît en bas
        if self.y < -4 or self.x < -4 or self.x > self._w + 4:
            self.x = random.uniform(0, self._w)
            self.y = self._h + 4
            self.vx = random.uniform(-12, 12)
            self.vy = random.uniform(-30, -8)

    def draw(self, surf):
        taille = int(self.rayon * 2) + 2
        s = pygame.Surface((taille, taille), pygame.SRCALPHA)
        centre = (taille // 2, taille // 2)
        pygame.draw.circle(s, (*self.couleur, self.alpha), centre, int(self.rayon))
        surf.blit(s, (int(self.x) - taille // 2, int(self.y) - taille // 2))


# ── Personnage animé du menu ──────────────────────────────────────────────────

class PersonnageMenu:
    """Petit personnage qui se balade en fond du menu titre avec une lueur."""

    def __init__(self, largeur, hauteur):
        self._w = largeur
        self._h = hauteur
        self.x = -40.0
        self.y = hauteur * 0.82
        self.vx = random.uniform(18, 30)
        self.direction = 1  # 1=droite, -1=gauche
        self._timer_pause = 0.0
        self._timer_attente = random.uniform(4, 12)
        self._visible = False
        self._anim_timer = 0.0
        self._frame = 0
        # Lueur autour du personnage
        self._lueur_alpha = 0
        self._lueur_pulse = 0.0
        # Couleur du personnage
        self._couleur = (180, 160, 230)
        self._lueur_couleur = (140, 120, 255)

    def update(self, dt):
        self._anim_timer += dt
        self._lueur_pulse += dt * 3

        if not self._visible:
            self._timer_attente -= dt
            if self._timer_attente <= 0:
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

        # Déplacement
        self.x += self.vx * self.direction * dt

        # Lueur apparaît/disparaît en douceur
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

        # Animation de marche
        if self._anim_timer > 0.3:
            self._frame = (self._frame + 1) % 4
            self._anim_timer = 0

        # Sorti de l'écran → disparaître et attendre
        if self.x < -40 or self.x > self._w + 40:
            self._visible = False
            self._timer_attente = random.uniform(6, 18)

    def draw(self, surf):
        if not self._visible:
            return
        x = int(self.x)
        y = int(self.y)

        # Lueur douce autour du personnage
        pulse = math.sin(self._lueur_pulse) * 15
        rayon_lueur = int(28 + pulse)
        if self._lueur_alpha > 0:
            lueur_surf = pygame.Surface((rayon_lueur*2, rayon_lueur*2), pygame.SRCALPHA)
            for r in range(rayon_lueur, 4, -4):
                a = int(self._lueur_alpha * (r / rayon_lueur) * 0.4)
                pygame.draw.circle(lueur_surf, (*self._lueur_couleur, a),
                                   (rayon_lueur, rayon_lueur), r)
            surf.blit(lueur_surf, (x - rayon_lueur, y - 10 - rayon_lueur))

        # Corps simple (silhouette)
        # Tête
        pygame.draw.circle(surf, self._couleur, (x, y - 16), 5)
        # Corps
        pygame.draw.line(surf, self._couleur, (x, y - 11), (x, y), 2)
        # Bras
        bras_offset = 2 if self._frame in (1, 3) else -1
        pygame.draw.line(surf, self._couleur, (x, y - 8), (x - 4, y - 4 + bras_offset), 1)
        pygame.draw.line(surf, self._couleur, (x, y - 8), (x + 4, y - 4 - bras_offset), 1)
        # Jambes (animation de marche)
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


# ── Classe Menu ───────────────────────────────────────────────────────────────

class Menu:
    """
    Menu réutilisable pour le titre, la pause et l'écran de fin.

    style="titre"   → fond sombre total + particules flottantes
                       (utilisé quand il n'y a rien derrière)

    style="panneau" → petit cadre semi-transparent centré sur le fond actuel
                       (utilisé pour la pause et le game over — on voit le jeu derrière)

    Positions configurables :
        title_y       → position Y du titre (en ratio de l'écran, ex: 0.25 = 25%)
        options_y     → position Y du début des options (ratio)
        offset_x      → décalage horizontal en pixels
        offset_y      → décalage vertical en pixels (pour panneau)
        options_spacing → espacement vertical entre options en pixels
    """

    def __init__(self, options, title="", style="panneau",
                 offset_x=0, offset_y=0,
                 title_y=0.25, options_y=0.48, options_spacing=42):
        self.options   = options
        self.title     = title
        self.style     = style
        self.selection = 0

        # ── Positions configurables ──
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.title_y = title_y              # ratio vertical du titre (0.0 - 1.0)
        self.options_y = options_y            # ratio vertical des options (0.0 - 1.0)
        self.options_spacing = options_spacing  # pixels entre chaque option

        self._particules    = []
        self._personnage    = None
        self._police_titre  = None
        self._police_option = None
        self._police_sous   = None

    # ── Initialisation lazy ───────────────────────────────────────────────

    def _init_polices(self):
        if self._police_titre is None:
            self._police_titre  = pygame.font.SysFont("Georgia", 72, bold=True)
            self._police_titre_panneau = pygame.font.SysFont("Georgia", 38, bold=True)
            self._police_option = pygame.font.SysFont("Consolas", 22)
            self._police_sous   = pygame.font.SysFont("Consolas", 13)

    def _init_particules(self, w, h):
        if not self._particules:
            self._particules = [Particule(w, h) for _ in range(45)]
        pass

    # ── Mise à jour (appeler chaque frame) ────────────────────────────────

    def update(self, dt):
        surf = pygame.display.get_surface()
        if surf:
            self._init_particules(*surf.get_size())
        for p in self._particules:
            p.update(dt)
        pass

    # ── Entrées clavier ───────────────────────────────────────────────────

    def handle_key(self, key):
        if key == pygame.K_UP:
            self.selection = (self.selection - 1) % len(self.options)
            sfx.jouer("ui_nav", 0.3)
        elif key == pygame.K_DOWN:
            self.selection = (self.selection + 1) % len(self.options)
            sfx.jouer("ui_nav", 0.3)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            sfx.jouer("ui_select", 0.4)
            return self.options[self.selection]
        elif key == pygame.K_ESCAPE:
            sfx.jouer("ui_back", 0.3)
        return None

    # ── Rendu ─────────────────────────────────────────────────────────────

    def draw(self, surf):
        self._init_polices()
        w, h = surf.get_size()

        if self.style == "titre":
            self._dessiner_ecran_titre(surf, w, h)
        else:
            self._dessiner_panneau(surf, w, h)

    def _dessiner_ecran_titre(self, surf, w, h):
        # Fond très sombre — comme les profondeurs de l'Entremonde
        fond = pygame.Surface((w, h), pygame.SRCALPHA)
        fond.fill((6, 6, 18, 245))
        surf.blit(fond, (0, 0))

        # Lueurs flottantes
        self._init_particules(w, h)
        for p in self._particules:
            p.draw(surf)

        pass

        cx = w // 2 + self.offset_x
        cy_titre = int(h * self.title_y) + self.offset_y

        # Titre avec effet de glow (ombre décalée + texte principal)
        if self.title:
            ombre = self._police_titre.render(self.title, True, (60, 40, 120))
            surf.blit(ombre, (cx - ombre.get_width() // 2 + 2, cy_titre + 2))

            titre_surf = self._police_titre.render(self.title, True, (210, 190, 255))
            surf.blit(titre_surf, (cx - titre_surf.get_width() // 2, cy_titre))

        # Ligne décorative sous le titre
        lx1 = cx - w // 4
        lx2 = cx + w // 4
        ly  = cy_titre + 95
        pygame.draw.line(surf, (80, 60, 160), (lx1, ly), (lx2, ly), 1)

        # Petits losanges aux extrémités de la ligne
        for lx in (lx1, lx2):
            points = [(lx, ly - 4), (lx + 4, ly), (lx, ly + 4), (lx - 4, ly)]
            pygame.draw.polygon(surf, (130, 100, 220), points)

        # Options — le texte est centré, l'indicateur est à gauche
        debut_y = int(h * self.options_y) + self.offset_y
        for i, option in enumerate(self.options):
            if i == self.selection:
                couleur = (255, 215, 70)
            else:
                couleur = (150, 135, 200)

            opt_surf = self._police_option.render(option, True, couleur)
            ox = cx - opt_surf.get_width() // 2
            oy = debut_y + i * self.options_spacing
            surf.blit(opt_surf, (ox, oy))
            if i == self.selection:
                ind = self._police_option.render(">", True, couleur)
                surf.blit(ind, (ox - ind.get_width() - 8, oy))

        # Petite indication en bas
        aide = self._police_sous.render("↑↓ Naviguer   Entrée Valider", True, (70, 60, 110))
        surf.blit(aide, (cx - aide.get_width() // 2, h - 30))

    def _dessiner_panneau(self, surf, w, h):
        """
        Panneau flottant — le jeu reste visible en arrière-plan.
        On dessine d'abord un voile très léger pour assombrir un peu,
        puis le cadre centré avec le contenu.
        """
        # Voile léger (laisse voir le décor derrière)
        voile = pygame.Surface((w, h), pygame.SRCALPHA)
        voile.fill((0, 0, 0, 100))
        surf.blit(voile, (0, 0))

        # Dimensions du panneau — s'adapte au texte le plus large
        nb_options = len(self.options)
        ft = self._police_titre_panneau
        max_opt_w  = max(
            (self._police_option.size(f" >  {o}")[0] for o in self.options),
            default=200
        ) + 60
        if self.title:
            max_opt_w = max(max_opt_w, ft.size(self.title)[0] + 60)
        panneau_w  = max(300, min(max_opt_w, w - 60))
        panneau_h  = 50 + nb_options * self.options_spacing + (80 if self.title else 20)

        px = (w - panneau_w) // 2 + self.offset_x
        py = (h - panneau_h) // 2 + self.offset_y

        # Fond du panneau
        panneau = pygame.Surface((panneau_w, panneau_h), pygame.SRCALPHA)
        panneau.fill((10, 10, 22, 210))
        surf.blit(panneau, (px, py))

        # Double bordure (extérieure + intérieure fine)
        pygame.draw.rect(surf, (110, 90, 200), (px, py, panneau_w, panneau_h), 1)
        pygame.draw.rect(surf, (50, 40, 90),   (px + 3, py + 3, panneau_w - 6, panneau_h - 6), 1)

        y_courant = py + 18

        # Titre du panneau — centré dans le panneau (pas dans l'écran entier)
        centre_x = px + panneau_w // 2
        if self.title:
            t = ft.render(self.title, True, (190, 170, 255))
            surf.blit(t, (centre_x - t.get_width() // 2, y_courant))
            y_courant += t.get_height() + 12

            # Ligne sous le titre
            pygame.draw.line(surf, (70, 55, 140),
                             (px + 20, y_courant - 6),
                             (px + panneau_w - 20, y_courant - 6), 1)

        # Options — centrées dans le panneau
        for i, option in enumerate(self.options):
            if i == self.selection:
                couleur = (255, 215, 70)
            else:
                couleur = (150, 135, 200)

            opt_surf = self._police_option.render(option, True, couleur)
            ox = centre_x - opt_surf.get_width() // 2
            oy = y_courant + i * self.options_spacing
            surf.blit(opt_surf, (ox, oy))
            if i == self.selection:
                ind = self._police_option.render(">", True, couleur)
                surf.blit(ind, (ox - ind.get_width() - 8, oy))
