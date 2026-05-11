# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Mixin Boss UI (barre de vie en bas d'écran)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Mixin qui contient la logique d'affichage de la grande barre de vie
#  de boss en bas d'écran :
#
#       _trouver_boss_actif()       → cherche un ennemi NOMMÉ vivant et
#                                     visible à l'écran (un boss). Renvoie
#                                     None si aucun.
#       _dessiner_boss_hp_bar()     → dessine la barre rouge (vire au
#                                     jaune sous 30% de PV), le nom du
#                                     boss en doré au-dessus, et le
#                                     compteur PV à droite.
#
#  Un boss est un Enemy dont l'attribut `nom` est non-vide (mis via
#  l'éditeur, touche [N] en mode 1 sur l'ennemi).
# ─────────────────────────────────────────────────────────────────────────────

import pygame


class BossUIMixin:
    """Méthodes liées à l'UI des combats de boss (barre de vie en bas)."""

    def _trouver_boss_actif(self):
        """Renvoie l'ennemi nommé (= boss) le plus pertinent à afficher,
        ou None s'il n'y en a aucun.

        Critères :
          - vivant
          - a un nom non vide (= a été désigné comme boss)
          - sa hitbox est sur l'écran (au moins partiellement visible)
        S'il y en a plusieurs (rare), on prend le plus proche du joueur.
        """
        if not getattr(self, "ennemis", None):
            return None
        # Rect écran en coordonnées monde (pour test de visibilité)
        sw, sh = self.screen.get_size()
        ox = getattr(self.camera, "offset_x", 0)
        oy = getattr(self.camera, "offset_y", 0)
        ecran_monde = pygame.Rect(ox, oy, sw, sh)
        candidats = []
        for e in self.ennemis:
            if not getattr(e, "alive", False):
                continue
            nom = getattr(e, "nom", "") or ""
            if not nom:
                continue
            if not e.rect.colliderect(ecran_monde):
                continue
            candidats.append(e)
        if not candidats:
            return None
        # Le plus proche du joueur
        jx, jy = self.joueur.rect.centerx, self.joueur.rect.centery
        candidats.sort(
            key=lambda e: (e.rect.centerx - jx) ** 2 + (e.rect.centery - jy) ** 2
        )
        return candidats[0]

    def _dessiner_boss_hp_bar(self):
        """Affiche une grande barre de vie en bas de l'écran avec le nom du
        boss au-dessus. Visible uniquement si un boss (ennemi nommé) est
        vivant ET visible à l'écran.
        """
        boss = self._trouver_boss_actif()
        if boss is None:
            return

        sw, sh = self.screen.get_size()
        # Dimensions et placement
        bar_w   = int(sw * 0.6)              # 60% de la largeur d'écran
        bar_h   = 22
        bar_x   = (sw - bar_w) // 2          # centré horizontalement
        bar_y   = sh - 60                    # à 60 px du bas

        # Police lazy (créée à la 1re utilisation, gardée en cache)
        if not hasattr(self, "_boss_bar_font"):
            try:
                self._boss_bar_font = pygame.font.SysFont("Consolas", 22, bold=True)
            except Exception:
                self._boss_bar_font = pygame.font.Font(None, 26)

        nom    = boss.nom or "Boss"
        max_hp = max(1, int(getattr(boss, "max_vie", 1)))
        hp     = max(0, int(getattr(boss, "hp", 0)))
        ratio  = hp / max_hp

        # ── Cadre : fond noir semi-transparent ──
        fond = pygame.Surface((bar_w + 8, bar_h + 8), pygame.SRCALPHA)
        fond.fill((0, 0, 0, 180))
        self.screen.blit(fond, (bar_x - 4, bar_y - 4))

        # ── Barre de fond (rouge sombre) ──
        pygame.draw.rect(self.screen, (60, 12, 16),
                         (bar_x, bar_y, bar_w, bar_h))

        # ── Barre actuelle (rouge vif → jaune en bas) ──
        cur_w = int(bar_w * ratio)
        if cur_w > 0:
            # Couleur : rouge si > 30%, jaune sinon (signal "presque mort")
            if ratio > 0.3:
                couleur = (210, 35, 45)
            else:
                couleur = (240, 180, 40)
            pygame.draw.rect(self.screen, couleur,
                             (bar_x, bar_y, cur_w, bar_h))

        # ── Bordure dorée ──
        pygame.draw.rect(self.screen, (240, 200, 80),
                         (bar_x, bar_y, bar_w, bar_h), 2)

        # ── Nom du boss au-dessus ──
        nom_surf = self._boss_bar_font.render(nom.upper(), True, (255, 230, 180))
        nom_rect = nom_surf.get_rect(midbottom=(bar_x + bar_w // 2, bar_y - 6))
        # Petite ombre pour la lisibilité
        ombre = self._boss_bar_font.render(nom.upper(), True, (0, 0, 0))
        self.screen.blit(ombre, (nom_rect.x + 2, nom_rect.y + 2))
        self.screen.blit(nom_surf, nom_rect)

        # ── HP en chiffres (petit, à droite de la barre) ──
        try:
            font_sm = pygame.font.SysFont("Consolas", 14)
        except Exception:
            font_sm = pygame.font.Font(None, 18)
        hp_txt = f"{hp} / {max_hp}"
        hp_surf = font_sm.render(hp_txt, True, (255, 255, 255))
        self.screen.blit(hp_surf,
                         (bar_x + bar_w - hp_surf.get_width() - 6,
                          bar_y + (bar_h - hp_surf.get_height()) // 2))
