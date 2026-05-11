# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Mixin Preload (pré-chargement des textures GPU)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Quand on change de map, pygame charge les images en LAZY : la conversion
#  vers le format display (et l'upload GPU) se fait au premier blit. Sur
#  les grosses maps Tiled, ça cause un "pop" visible / un flicker / un
#  freeze d'une frame à l'arrivée. Ce mixin pré-charge tout d'un coup
#  pendant l'écran de chargement (= le voile noir entre 2 maps).
#
#  Méthodes :
#       _precharger_textures()       version actuelle (convert_alpha sur
#                                    décors / ennemis / joueur). Léger,
#                                    suffit pour la plupart des configs.
#       _precharger_textures_OLD()   ancienne version : blit-flip forcé
#                                    pour upload GPU explicite. Gardée
#                                    en référence (cause des freezes sur
#                                    certaines configs → désactivée).
#       _precharger_textures_legacy() stub vide (compat avec d'anciens
#                                    appelants).
# ─────────────────────────────────────────────────────────────────────────────

import pygame


class PreloadMixin:
    """Pré-chargement des textures au changement de map (évite le pop)."""

    def _precharger_textures_legacy(self):
        """Ancienne version (laissée en référence). Voir _precharger_textures."""
        return

    def _precharger_textures(self):
        """Pré-conversion légère des textures de la map.

        On se contente de .convert_alpha() chaque surface (= les met au bon
        format mémoire CPU). Sur la plupart des configs pygame/SDL, ça
        suffit pour éviter le pop visible quand le sprite est rendu pour
        la 1ère fois.

        On a abandonné le blit-sur-display+flip qu'on avait essayé avant :
        sur certaines configs il causait des freezes au boot (gros lots
        de flips → GPU thrashing → FPS qui yo-yo pendant 1 minute) sans
        avantage perceptible côté upload textures.

        Si du flicker persiste après ce convert_alpha, c'est probablement
        une limitation pygame/SDL qu'on ne peut pas vraiment court-circuiter.
        """
        # ── Décors ──
        for liste_attr in ("decors", "decors_fond", "decors_avant"):
            for d in (getattr(self.editeur, liste_attr, None) or []):
                img = getattr(d, "image", None)
                if img is not None:
                    try:
                        d.image = img.convert_alpha()
                    except Exception:
                        pass

        # ── Ennemis ──
        for ennemi in (getattr(self, "ennemis", None) or []):
            for attr in ("image", "_image", "sprite_courant"):
                img = getattr(ennemi, attr, None)
                if img is not None:
                    try:
                        setattr(ennemi, attr, img.convert_alpha())
                    except Exception:
                        pass

        # ── Joueur : toutes les frames de toutes les anims ──
        for nom in dir(self.joueur):
            if not (nom.startswith("idle_anim_") or nom.startswith("anim_")):
                continue
            anim = getattr(self.joueur, nom, None)
            images = getattr(anim, "images", None) if anim else None
            if images is None:
                continue
            for i, frame in enumerate(images):
                try:
                    images[i] = frame.convert_alpha()
                except Exception:
                    pass

    def _precharger_textures_OLD(self):
        """Force le chargement GPU de TOUTES les textures de la map courante.

        Pourquoi ? pygame charge les textures en LAZY : la conversion vers
        le format display (et l'upload GPU sur certains backends) se fait
        au premier blit SUR LA DISPLAY SURFACE (l'écran réel).

        Cette version blit TOUS les sprites sur self.screen (la vraie
        display surface), à des coords 0,0 (visibles), ce qui force pygame
        à uploader chaque texture côté GPU. Ensuite on fill l'écran en
        noir pour repartir propre.

        ATTENTION : abandonné en pratique car causait des freezes au boot
        sur certaines configs. Gardé en référence.
        """
        screen = self.screen

        # 1) On collecte toutes les images uniques de la map à pré-charger.
        textures = []
        for liste_attr in ("decors", "decors_fond", "decors_avant"):
            for d in (getattr(self.editeur, liste_attr, None) or []):
                img = getattr(d, "image", None)
                if img is not None:
                    try:
                        d.image = img.convert_alpha()
                    except Exception:
                        pass
                    textures.append(d.image)

        for ennemi in (getattr(self, "ennemis", None) or []):
            for attr in ("image", "_image", "sprite_courant"):
                img = getattr(ennemi, attr, None)
                if img is not None:
                    try:
                        setattr(ennemi, attr, img.convert_alpha())
                    except Exception:
                        pass
                    textures.append(getattr(ennemi, attr))

        for nom in dir(self.joueur):
            if not (nom.startswith("idle_anim_") or nom.startswith("anim_")):
                continue
            anim   = getattr(self.joueur, nom, None)
            images = getattr(anim, "images", None) if anim else None
            if images is None:
                continue
            for i, frame in enumerate(images):
                try:
                    images[i] = frame.convert_alpha()
                except Exception:
                    pass
                textures.append(images[i])

        # 2) Pré-upload : on blit chaque texture à des coords VISIBLES (0,0)
        # de la display surface. SDL fait l'upload GPU.
        # On flip() périodiquement pour committer le batch.
        BATCH = 25
        for i, img in enumerate(textures):
            screen.blit(img, (0, 0))
            if (i + 1) % BATCH == 0:
                pygame.display.flip()
                screen.fill((0, 0, 0))

        # Flip + clear final pour repartir d'un écran propre.
        pygame.display.flip()
        screen.fill((0, 0, 0))
