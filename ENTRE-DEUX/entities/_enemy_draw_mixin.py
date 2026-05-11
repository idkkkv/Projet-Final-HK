# ─────────────────────────────────────────────────────────────────────────────
#  EnemyDrawMixin — Rendu du sprite et informations de debug
# ─────────────────────────────────────────────────────────────────────────────
#
#  Ce mixin regroupe tout ce qui concerne l'affichage de l'ennemi :
#
#   draw            → dessine le sprite (et les projectiles) ; en mode debug
#                     appelle _dessiner_debug pour afficher toutes les infos.
#   _dessiner_debug → affiche hitbox, zones, patrouille, direction, état, etc.
#
#  ANCRAGE CENTRE-BAS :
#  Le sprite est centré horizontalement sur la hitbox et aligné par le bas.
#  C'est l'approche standard des platformers 2D : robuste aux changements de
#  taille entre animations et au flip horizontal.
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame

from settings import GRAVITY

# ─── Polices debug (créées à la première utilisation, partagées par toutes
#     les instances d'Enemy pour éviter de recréer des polices à chaque frame)
_font_dbg_small = None
_font_dbg_tiny  = None


def _get_debug_fonts():
    """Renvoie les deux polices debug, en les créant à la 1re utilisation."""
    global _font_dbg_small, _font_dbg_tiny
    if _font_dbg_small is None:
        _font_dbg_small = pygame.font.SysFont("Consolas", 12)
        _font_dbg_tiny  = pygame.font.SysFont("Consolas", 11)
    return _font_dbg_small, _font_dbg_tiny


class EnemyDrawMixin:
    """Rendu visuel de l'ennemi (sprite + debug)."""

    def draw(self, surf, camera, show_hitbox=False):
        """Dessine le sprite de l'ennemi (et ses projectiles si boss).

        En mode mort : affiche l'animation "die" jusqu'à la fin, puis
        l'ennemi est retiré de la liste. Ancrage centre-bas pour que
        les pieds soient toujours alignés avec la hitbox."""
        if not self.alive:
            img = self.animations["die"].img()
            img_w, img_h = img.get_width(), img.get_height()
            if self.direction < 0:
                img = pygame.transform.flip(img, True, False)
            sx = self.rect.centerx - img_w // 2
            sy = self.rect.bottom  - img_h
            surf.blit(img, camera.apply(pygame.Rect(sx, sy, img_w, img_h)))
            return

        # ── Sprite ──
        img = self.animations[self.current_anim].img()
        self.animations[self.current_anim].update()
        img_w, img_h = img.get_width(), img.get_height()

        if self.direction < 0:
            img = pygame.transform.flip(img, True, False)

        # Centre horizontal sur la hitbox + alignement par les pieds.
        sx = self.rect.centerx - img_w // 2
        sy = self.rect.bottom  - img_h
        surf.blit(img, camera.apply(pygame.Rect(sx, sy, img_w, img_h)))

        # ── Projectiles (boules d'ombre des boss) ──
        for p in self.projectiles:
            p.draw(surf, camera)

        if not show_hitbox:
            return

        # ── Debug visuel ──
        self._dessiner_debug(surf, camera)

    def _dessiner_debug(self, surf, camera):
        """Affiche les infos de debug en mode hitbox activé.

        Affiche : hitbox (rouge), zone de détection (jaune/rouge selon état),
        zone de patrouille (vert), hauteur de saut max (cyan), flèche de
        direction (jaune), indicateur d'état (! ou <<), barre de mémoire,
        marqueurs de flags spéciaux et vitesses numériques."""
        font_s, font_t = _get_debug_fonts()

        # Hitbox en rouge.
        pygame.draw.rect(surf, (255, 0, 0), camera.apply(self.rect), 1)

        # Zone de détection (jaune si pas en chasse, rouge si en chasse).
        if self.chasing:
            pygame.draw.rect(surf, (255, 80, 80),
                             camera.apply(self._chase_rect()), 1)
        else:
            pygame.draw.rect(surf, (255, 255, 0),
                             camera.apply(self._detect_rect()), 1)

        # Zone de patrouille (ligne verte avec barres aux extrémités).
        pl = int(self.patrol_left  - camera.offset_x)
        pr = int(self.patrol_right - camera.offset_x)
        py = int(self.rect.bottom  - camera.offset_y) + 5
        pygame.draw.line(surf, (0, 200, 0), (pl, py), (pr, py), 2)
        pygame.draw.line(surf, (0, 200, 0), (pl, py - 4), (pl, py + 4), 2)
        pygame.draw.line(surf, (0, 200, 0), (pr, py - 4), (pr, py + 4), 2)

        # Hauteur max sautable (cyan).
        if self.can_jump and self.jump_power > 0:
            mjh  = int((self.jump_power ** 2) / (2 * GRAVITY))
            jtop = int(self.rect.bottom - camera.offset_y) - mjh
            lx   = self.rect.x     - int(camera.offset_x) - 5
            rx   = self.rect.right - int(camera.offset_x) + 5
            mx2  = self.rect.centerx - int(camera.offset_x)
            fy2  = int(self.rect.bottom - camera.offset_y)
            pygame.draw.line(surf, (0, 220, 220), (lx, jtop), (rx, jtop), 1)
            pygame.draw.line(surf, (0, 220, 220), (mx2, fy2), (mx2, jtop), 1)
            surf.blit(font_t.render(f"{mjh}px", True, (0, 220, 220)),
                      (rx + 3, jtop - 5))

        # Flèche de direction (jaune).
        cx = self.rect.centerx - int(camera.offset_x)
        cy = self.rect.centery - int(camera.offset_y)
        ex = cx + 25 * self.direction
        pygame.draw.line(surf, (255, 255, 0), (cx, cy), (ex, cy), 2)
        pygame.draw.line(surf, (255, 255, 0), (ex, cy),
                         (ex - 6 * self.direction, cy - 5), 2)
        pygame.draw.line(surf, (255, 255, 0), (ex, cy),
                         (ex - 6 * self.direction, cy + 5), 2)

        # Indicateurs d'état (! = chasse, << = retour avec timer).
        if self.chasing:
            surf.blit(font_s.render("!", True, (255, 50, 50)),
                      (cx - 3, cy - 30))
        elif self.returning:
            if self.respawn_timeout > 0:
                rem = max(0.0, self.respawn_timeout - self._returning_timer)
                surf.blit(font_s.render(f"<< {rem:.0f}s", True, (100, 200, 100)),
                          (cx - 18, cy - 28))
            else:
                surf.blit(font_s.render("<<", True, (100, 200, 100)),
                          (cx - 8, cy - 28))

        # Barre de mémoire (orange) : temps restant de souvenir du joueur.
        if self.memory_timer > 0 and not self.chasing:
            ratio = self.memory_timer / self.MEMORY_DURATION
            bx = self.rect.x - int(camera.offset_x)
            by = self.rect.y - int(camera.offset_y) - 8
            pygame.draw.rect(surf, (255, 150, 0),
                             (bx, by, int(self.hitbox_w * ratio), 3))

        # Marqueurs triangulaires pour flags spéciaux.
        if self.can_fall_in_holes:
            fx = self.rect.centerx - int(camera.offset_x)
            fy = self.rect.bottom  - int(camera.offset_y) + 8
            pygame.draw.polygon(surf, (0, 220, 220),
                                [(fx, fy + 8), (fx - 6, fy), (fx + 6, fy)])

        if self.can_turn_randomly:
            fx = self.rect.centerx - int(camera.offset_x)
            fy = self.rect.bottom  - int(camera.offset_y) + 14
            pygame.draw.polygon(surf, (200, 100, 255),
                                [(fx, fy + 6), (fx - 5, fy), (fx + 5, fy)])

        # Barre de cooldown trou (orange).
        if self._hole_cooldown > 0:
            ratio = self._hole_cooldown / 0.8
            bx = self.rect.x - int(camera.offset_x)
            by = int(self.rect.bottom - camera.offset_y) + 3
            pygame.draw.rect(surf, (255, 120, 0),
                             (bx, by, int(self.hitbox_w * ratio), 2))

        # Vitesses numériques (texte bleu).
        spd_txt = f"p:{self.patrol_speed} c:{self.chase_speed}"
        surf.blit(font_t.render(spd_txt, True, (180, 180, 255)),
                  (cx - 20, cy - 44))
