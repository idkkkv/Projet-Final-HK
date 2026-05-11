# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Mixin Checkpoint (auto-save zones + respawn)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Mixin qui contient toute la logique des "checkpoints" du jeu :
#
#       _snapshot_player()              capture l'état joueur (HP, position,
#                                       inventaire, argent) sans toucher à
#                                       l'histoire
#       _verifier_autosave_zones()      détecte le passage dans une zone
#                                       d'auto-save → snapshot avec cooldown
#                                       10s pour ne pas spammer
#       _restaurer_checkpoint()         restaure le snapshot après une mort
#       _respawn_meme_salle()           respawn brut sur la map courante
#       _compter_pommes_inventaire()    helper pour compter les pommes
#       _garantir_minimum_pommes(n)     ajoute des pommes au respawn
#
#  PRINCIPE DES CHECKPOINTS
#  ------------------------
#  Quand le joueur passe dans une autosave_zone (placée dans l'éditeur,
#  mode 16), on snapshot uniquement SON état (position, HP, argent,
#  inventaire) — pas l'histoire (story_flags, cines jouées). Quand il
#  meurt, on restaure ce snapshot pour qu'il reprenne juste avant.
#
#  Pour éviter le spam : cooldown de 10s par zone (sinon on snapshot
#  à chaque frame que le joueur passe dans la zone).
# ─────────────────────────────────────────────────────────────────────────────

import time

import pygame


class CheckpointMixin:
    """Méthodes liées aux checkpoints d'auto-save (sauvegarde rapide)."""

    # ─────────────────────────────────────────────────────────────────────
    #  Helpers : inventaire (pommes)
    # ─────────────────────────────────────────────────────────────────────

    def _compter_pommes_inventaire(self):
        """Compte les pommes (toutes variantes 'Pomme*') dans l'inventaire."""
        n = 0
        for slot in getattr(self.inventory, "slots", []) or []:
            if slot is None:
                continue
            nom = getattr(slot, "name", "") or ""
            if "pomme" in nom.lower():
                n += int(getattr(slot, "count", 1))
        return n

    def _garantir_minimum_pommes(self, mini=10):
        """Au respawn, garantit que le joueur a au moins `mini` pommes.

        Si déjà ≥ mini, on ne touche à rien. Sinon on ajoute ce qui manque
        via inventory.add_item. Permet au joueur de retenter une zone
        difficile sans être bloqué à sec après une mauvaise série.
        """
        actuel = self._compter_pommes_inventaire()
        manque = mini - actuel
        if manque <= 0:
            return
        try:
            self.inventory.add_item("Pomme", count=manque)
        except Exception as e:
            print(f"[Respawn] échec ajout pommes : {e}")

    # ─────────────────────────────────────────────────────────────────────
    #  Snapshot / restauration de l'état joueur
    # ─────────────────────────────────────────────────────────────────────

    def _snapshot_player(self):
        """Capture l'état actuel du joueur (player-only) dans un dict.

        Cf. self._dernier_checkpoint pour le format. Volontairement minimal
        — pas de story_flags, pas de cines jouées : ces infos restent
        celles du runtime au moment du respawn (= l'histoire ne régresse
        pas, on ne rejoue pas les cines déjà vues).
        """
        j = self.joueur
        inv = []
        for slot in getattr(self.inventory, "slots", []):
            if slot is None:
                inv.append(None)
            else:
                inv.append({
                    "name":  slot.name,
                    "count": int(getattr(slot, "count", 1)),
                })
        return {
            "map":       self.carte_actuelle,
            "x":         int(j.rect.x),
            "y":         int(j.rect.y),
            "hp":        int(j.hp),
            "coins":     int(getattr(j, "coins", 0)),
            "inventory": inv,
        }

    def _verifier_autosave_zones(self):
        """Si le joueur traverse une autosave_zone, on snapshot son état.

        Cooldown de 10s par zone : sans ça, tant que le joueur reste dans
        la zone (ou même plusieurs frames le temps de la traverser), on
        sauvegarderait à chaque frame → spam de notifications "Checkpoint
        enregistré ✓". On garde donc un dict id(zone) → timestamp et on
        ignore la zone tant que ce timestamp est trop récent.
        """
        if self.editeur.active or self.joueur.dead:
            return
        zones = getattr(self.editeur, "autosave_zones", []) or []
        if not zones:
            return
        maintenant = time.time()
        cooldowns = getattr(self, "_autosave_cooldowns", None)
        if cooldowns is None:
            cooldowns = {}
            self._autosave_cooldowns = cooldowns
        COOLDOWN_S = 10.0
        for zone in zones:
            if not self.joueur.rect.colliderect(zone["rect"]):
                continue
            zid = id(zone)
            dernier = cooldowns.get(zid, 0.0)
            if maintenant - dernier < COOLDOWN_S:
                # Encore en cooldown → on ignore (pas de re-snapshot ni notif)
                return
            cooldowns[zid] = maintenant
            self._dernier_checkpoint = self._snapshot_player()
            if hasattr(self, "notifier"):
                self.notifier("Checkpoint enregistré ✓", duree=1.5)
            return

    def _restaurer_checkpoint(self):
        """Restaure l'état joueur depuis self._dernier_checkpoint, sans
        toucher à l'histoire.

        Renvoie True si un checkpoint a été appliqué, False sinon (pas de
        checkpoint → fallback à gérer par l'appelant : spawn de map ou
        _dernier_save_pos).
        """
        cp = self._dernier_checkpoint
        if not cp:
            return False
        j = self.joueur
        # Charger la map du checkpoint si différente
        map_cp = cp.get("map")
        if map_cp and map_cp != self.carte_actuelle:
            try:
                if self.editeur.load_map_for_portal(map_cp):
                    self.carte_actuelle = map_cp
                    self._reconstruire_grille()
                    self._murs_modifies()
                    self._sync_triggers()
                    self._appliquer_musique_carte()
            except Exception as e:
                print(f"[Checkpoint] échec chgt map : {e}")
        j.rect.x        = int(cp.get("x", j.rect.x))
        j.rect.y        = int(cp.get("y", j.rect.y))
        j.hp            = int(cp.get("hp", j.max_hp))
        j.coins         = int(cp.get("coins", getattr(j, "coins", 0)))
        j.dead          = False
        j.vx            = 0
        j.vy            = 0
        j.knockback_vx  = 0
        j.invincible    = False
        # Restaure l'inventaire (recrée chaque slot via Item)
        try:
            inv_data = cp.get("inventory", [])
            slots = getattr(self.inventory, "slots", None)
            if slots is not None and inv_data is not None:
                for i, item in enumerate(inv_data):
                    if i >= len(slots):
                        break
                    if item is None:
                        slots[i] = None
                    else:
                        try:
                            from ui.inventory import Item
                            slots[i] = Item(item["name"],
                                            count=int(item.get("count", 1)))
                        except Exception:
                            pass
        except Exception as e:
            print(f"[Checkpoint] inventaire : {e}")
        # Snap caméra
        if hasattr(self.camera, "snap_to"):
            self.camera.snap_to(j.rect)
        return True

    # ─────────────────────────────────────────────────────────────────────
    #  Respawn sur place (boss avec pommes restantes)
    # ─────────────────────────────────────────────────────────────────────

    def _respawn_meme_salle(self):
        """Respawn le joueur dans la map COURANTE (utilisé en fallback
        quand pas de checkpoint disponible). PV pleins, ennemis ressuscités.
        """
        j = self.joueur
        j.hp           = j.max_hp
        j.dead         = False
        j.vx           = 0
        j.vy           = 0
        j.knockback_vx = 0
        j.invincible   = False
        # Si on a un dernier point de sauvegarde explicite sur la map
        # courante, on l'utilise (priorité sur le spawn par défaut).
        _dsp = getattr(self, "_dernier_save_pos", None)
        if _dsp and _dsp[0] == self.carte_actuelle:
            j.rect.x = _dsp[1]
            j.rect.y = _dsp[2]
        else:
            j.rect.x = self.editeur.spawn_x
            j.rect.y = self.editeur.spawn_y
        if hasattr(self.camera, "snap_to"):
            self.camera.snap_to(j.rect)
        # Réveille les ennemis de la map courante (les boss reviennent).
        for e in self.ennemis:
            e.alive = True
        self.compagnons.respawn(j)
