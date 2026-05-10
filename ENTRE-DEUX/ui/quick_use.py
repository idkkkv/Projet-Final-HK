# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Barre de consommables rapides (D-Pad)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Affiche en bas-droite de l'écran une croix directionnelle (4 slots
#  arrangés en croix) avec un consommable assigné à chacun. Quand le
#  joueur appuie sur la touche d'un slot, l'item est consommé immédiatement.
#
#  STYLE — inspiration Elden Ring / Souls : carrés avec icône de l'item
#  + compteur en bas-droite. Slot vide = carré gris. Slot grisé = item
#  épuisé (count == 0 dans tout l'inventaire).
#
#  CONFIG (modifiable ici) :
#  -------------------------
#     SLOTS               — liste des items assignés aux 4 directions
#                           ordre : [HAUT, DROITE, BAS, GAUCHE]
#     KEY_BINDINGS        — touches pygame mappées aux 4 slots (1/2/3/4)
#     SLOT_SIZE           — taille d'un slot (px)
#     MARGIN_RIGHT/BOTTOM — marge depuis le coin bas-droite
#
#  COMMENT L'UTILISER DEPUIS game.py :
#  -----------------------------------
#     self.quick_use = QuickUseBar(self.inventory, self.joueur)
#
#     # Dans la boucle d'événements :
#     for ev in events:
#         self.quick_use.handle_event(ev)
#
#     # Chaque frame (rendu) :
#     self.quick_use.draw(self.screen)
#
#  Pour changer l'effet d'un item : voir ITEMS dans ui/inventory.py
#  → la clé "consumable": True + "heal_hp": N déclenche une heal sur
#  consommation. Pour ajouter d'autres effets, étendre _effet_consommation().
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame


class QuickUseBar:
    # Ordre des slots : HAUT, DROITE, BAS, GAUCHE — comme une croix de manette.
    #   1 (Haut)   : Pomme — consommable de soin classique
    #   2 (Droite) : Épée  — toggle +ATK (cf. inventory.epee_active)
    #   3 (Bas)    : GODMODE — toggle "one-shot tous les ennemis" (debug prof)
    #   4 (Gauche) : Bouclier — toggle +HP (cf. inventory.bouclier_actif)
    SLOTS = ["Pomme", "Epee", "Godmode", "Bouclier"]

    # Items qui ne se "consomment" pas mais TOGGLENT un état (équipement).
    # Mapping nom → (target, attribut) :
    #   target = "inv" (lue/écrite sur self.inventory) ou
    #            "joueur" (sur self.joueur — accessible depuis combat.py).
    TOGGLE_ITEMS = {
        "Epee":     ("inv",    "epee_active"),
        "Bouclier": ("inv",    "bouclier_actif"),
        "Godmode":  ("joueur", "_godmode"),
    }

    def _toggle_target(self, item_name):
        """Renvoie l'objet sur lequel lire/écrire l'attribut toggle."""
        target, attr = self.TOGGLE_ITEMS[item_name]
        return (self.joueur if target == "joueur" else self.inventory), attr

    # Mapping touche → index de slot (0=Haut, 1=Droite, 2=Bas, 3=Gauche).
    # Les touches 1/2/3/4 sont assignées dans cet ordre.
    KEY_BINDINGS = {
        pygame.K_1: 0,   # Haut
        pygame.K_2: 1,   # Droite
        pygame.K_3: 2,   # Bas
        pygame.K_4: 3,   # Gauche
    }

    SLOT_SIZE      = 44
    SPACING        = 6     # espace entre le centre et un slot
    MARGIN_RIGHT   = 24
    MARGIN_BOTTOM  = 40   # au-dessus de la barre HP/peur

    # Couleurs
    COL_BG         = (28, 22, 40, 220)
    COL_BORDER     = (180, 150, 220)
    COL_BORDER_DIS = (90, 90, 110)        # slot grisé (item épuisé)
    COL_FLASH      = (255, 255, 200)      # flash blanc à la consommation

    def __init__(self, inventory, joueur, game=None):
        self.inventory = inventory
        self.joueur    = joueur
        # Référence au game pour lire les story flags (visibilité de la
        # barre conditionnée par story_flags["quickuse_unlocked"]).
        self.game      = game
        # Index du slot qui flashe (animation visuelle de consommation),
        # avec un timer décroissant.
        self._flash_idx   = -1
        self._flash_timer = 0.0
        # Police compteur (paresseux pour éviter init avant pygame.font.init)
        self._font = None
        self._font_key = None

    def est_visible(self):
        """True si la barre doit s'afficher.

        Conditionnée par le story flag « quickuse_unlocked ». Posé par
        la cinématique de Nymbus via l'action unlock_quickuse.
        Si pas de game référencé (test hors jeu), True par défaut."""
        if self.game is None:
            return True
        flags = getattr(self.game, "story_flags", {}) or {}
        return bool(flags.get("quickuse_unlocked", False))

    # ------------------------------------------------------------------
    #  ENTRÉES
    # ------------------------------------------------------------------

    def handle_event(self, event):
        """À appeler dans la boucle d'événements. Consomme la touche si
        elle correspond à un slot."""
        # Pas de barre visible → pas d'input. Évite que le joueur
        # consomme des pommes accidentellement avant le déblocage.
        if not self.est_visible():
            return
        if event.type != pygame.KEYDOWN:
            return
        idx = self.KEY_BINDINGS.get(event.key)
        if idx is None:
            return
        self._consommer(idx)

    def _consommer(self, idx):
        """Consomme (ou toggle, selon le type) l'item du slot `idx`."""
        if not (0 <= idx < len(self.SLOTS)):
            return
        item_name = self.SLOTS[idx]
        if not item_name:
            return

        # ── Items TOGGLE (équipements + godmode) ────────────────────────
        # Pas de consommation : on inverse le flag correspondant sur
        # l'inventaire. Pour Epee/Bouclier on exige aussi de POSSÉDER
        # l'item dans l'inventaire (sinon le joueur l'activerait sans
        # l'avoir trouvé). Godmode est libre (mode debug prof).
        if item_name in self.TOGGLE_ITEMS:
            obj, attr = self._toggle_target(item_name)
            if item_name in ("Epee", "Bouclier"):
                if self.inventory.quantite(item_name) <= 0:
                    return  # pas équipé
            actuel = bool(getattr(obj, attr, False))
            setattr(obj, attr, not actuel)
            # Petit son
            try:
                from audio import sound_manager
                sound_manager.jouer("ui_select", volume=0.4)
            except Exception:
                pass
            self._flash_idx   = idx
            self._flash_timer = 0.25
            return

        # Quantité dispo dans l'inventaire ?
        if self.inventory.quantite(item_name) <= 0:
            return
        # Lookup data + effet
        from ui.inventory import ITEMS
        data = ITEMS.get(item_name)
        if not data or not data.get("consumable", False):
            return
        # Refus de consommer si effet inutile (ex. PV au max pour heal_hp).
        # Évite que le joueur gaspille bêtement une pomme s'il a déjà
        # tous ses PV.
        heal = int(data.get("heal_hp", 0))
        if heal > 0 and self.joueur.hp >= self.joueur.max_hp:
            return
        # Retire l'item de l'inventaire (1 unité)
        if not self.inventory.consommer(item_name, 1):
            return
        # Applique l'effet
        self._effet_consommation(item_name, data)
        # Flash visuel
        self._flash_idx   = idx
        self._flash_timer = 0.25

    def _effet_consommation(self, name, data):
        """Applique l'effet d'un consommable.

        Pour l'instant : heal_hp (PV +N capé à max_hp) + animation de
        soin sur le joueur (pieds plantés, lumière). Le joueur est gelé
        pendant l'anim ; toute touche de mouvement la coupe net (cf.
        player.mouvement → check self.healing).

        Pour ajouter un nouvel effet, ajouter une branche ici (ex.
        "buff_invincibilite", "shield_temp", etc.).
        """
        heal = int(data.get("heal_hp", 0))
        if heal > 0:
            self.joueur.hp = min(self.joueur.max_hp, self.joueur.hp + heal)
            # Déclenche l'animation de soin (pieds plantés).
            try:
                self.joueur.healing = True
                self.joueur.idle_anim_heal.reset()
                # Affiche les cœurs pendant la heal.
                from settings import HP_DISPLAY_DURATION
                self.joueur.show_hp_timer = HP_DISPLAY_DURATION
            except Exception:
                pass
            # Petit son de heal (réutilise ui_select à un volume doux).
            try:
                from audio import sound_manager
                sound_manager.jouer("ui_select", volume=0.4)
            except Exception:
                pass

    # ------------------------------------------------------------------
    #  RENDU
    # ------------------------------------------------------------------

    def update(self, dt):
        if self._flash_timer > 0:
            self._flash_timer -= dt
            if self._flash_timer <= 0:
                self._flash_idx = -1

    def _ensure_font(self):
        if self._font is None:
            self._font = pygame.font.SysFont("Consolas", 14, bold=True)

    def _slot_positions(self, screen):
        """Renvoie [(x, y) × 4] : positions des coins haut-gauche des slots
        arrangés en croix. Ordre = SLOTS = [Haut, Droite, Bas, Gauche]."""
        w, h = screen.get_size()
        # Centre de la croix
        s   = self.SLOT_SIZE
        gap = self.SPACING
        cx  = w - self.MARGIN_RIGHT - (s * 3 + gap * 2) // 2 - s // 2
        # En réalité on calcule plus simplement : largeur totale = s*3 + gap*2.
        total_w = s * 3 + gap * 2
        total_h = s * 3 + gap * 2
        ox = w - self.MARGIN_RIGHT - total_w
        oy = h - self.MARGIN_BOTTOM - total_h
        # Centre du carré 3×3 :
        ccx = ox + s + gap
        ccy = oy + s + gap
        # Haut, Droite, Bas, Gauche :
        return [
            (ccx,                 ccy - (s + gap)),
            (ccx + (s + gap),     ccy),
            (ccx,                 ccy + (s + gap)),
            (ccx - (s + gap),     ccy),
        ]

    def draw(self, screen):
        # Pas de rendu tant que la mécanique n'est pas débloquée.
        if not self.est_visible():
            return
        self._ensure_font()
        positions = self._slot_positions(screen)
        s = self.SLOT_SIZE

        for idx, (x, y) in enumerate(positions):
            rect = pygame.Rect(x, y, s, s)
            item_name = self.SLOTS[idx] if idx < len(self.SLOTS) else None

            # ── Détermination du type de slot ────────────────────────
            est_toggle = item_name in self.TOGGLE_ITEMS
            actif = False
            if est_toggle:
                obj, attr = self._toggle_target(item_name)
                actif = bool(getattr(obj, attr, False))

            # Pour Epee/Bouclier on exige de posséder l'item ; pour Godmode non.
            if item_name == "Godmode":
                qty = 1
                disponible = True
            elif item_name:
                qty = self.inventory.quantite(item_name)
                disponible = qty > 0
            else:
                qty = 0
                disponible = False

            # ── Fond translucide ──
            bg = pygame.Surface((s, s), pygame.SRCALPHA)
            if self._flash_idx == idx and self._flash_timer > 0:
                a = int(180 * (self._flash_timer / 0.25))
                bg.fill((*self.COL_FLASH, a))
            elif est_toggle and actif:
                # Toggle ACTIF → fond doré pour signaler "équipé / on"
                bg.fill((90, 70, 20, 220))
            else:
                bg.fill(self.COL_BG)
            screen.blit(bg, rect.topleft)

            # ── Bordure ──
            if est_toggle and actif:
                border = (255, 215, 80)   # doré actif
                width  = 3
            else:
                border = self.COL_BORDER if disponible else self.COL_BORDER_DIS
                width  = 2
            pygame.draw.rect(screen, border, rect, width)

            # ── Image de l'item ──
            if item_name:
                img = self.inventory.images.get(item_name) if item_name != "Godmode" else None
                if img is not None:
                    img2 = img
                    if not disponible:
                        img2 = img.copy()
                        gris = pygame.Surface(img2.get_size(), pygame.SRCALPHA)
                        gris.fill((40, 40, 40, 180))
                        img2.blit(gris, (0, 0),
                                  special_flags=pygame.BLEND_RGBA_MULT)
                    img_rect = img2.get_rect(center=rect.center)
                    screen.blit(img2, img_rect)
                else:
                    # Pas d'image → texte de fallback (utile pour Godmode)
                    label = "GOD" if item_name == "Godmode" else item_name[:4].upper()
                    color = (255, 100, 100) if (est_toggle and actif) else (200, 200, 220)
                    lf = self._font.render(label, True, color)
                    screen.blit(lf, lf.get_rect(center=rect.center))

                # ── Indicateur ON/OFF pour les toggles ──
                if est_toggle:
                    etat_txt = "ON" if actif else "OFF"
                    etat_col = (200, 255, 130) if actif else (160, 160, 180)
                    es = self._font.render(etat_txt, True, etat_col)
                    sh = self._font.render(etat_txt, True, (0, 0, 0))
                    bx = rect.right - es.get_width() - 3
                    by = rect.bottom - es.get_height() - 1
                    screen.blit(sh, (bx + 1, by + 1))
                    screen.blit(es, (bx, by))
                # ── Compteur en bas-droite (uniquement pour les consommables) ──
                elif qty > 0:
                    txt = self._font.render(f"x{qty}", True, (255, 255, 255))
                    sh  = self._font.render(f"x{qty}", True, (0, 0, 0))
                    bx = rect.right - txt.get_width() - 3
                    by = rect.bottom - txt.get_height() - 1
                    screen.blit(sh,  (bx + 1, by + 1))
                    screen.blit(txt, (bx, by))

            # Étiquette de touche (1/2/3/4) en haut-gauche
            key_label = {0: "1", 1: "2", 2: "3", 3: "4"}.get(idx, "")
            if key_label:
                kf = self._font.render(key_label, True, (200, 200, 230))
                screen.blit(kf, (rect.left + 3, rect.top + 1))
