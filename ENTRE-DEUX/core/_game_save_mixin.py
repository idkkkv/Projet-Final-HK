# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Mixin Save (système de sauvegarde + chargement)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Mixin qui contient la logique de sauvegarde / chargement de la partie :
#
#       _construire_save_data()   → produit un dict sérialisable JSON
#                                   avec TOUT l'état du jeu (player,
#                                   inventaire, story_flags, ennemis tués,
#                                   compétences, etc.)
#       _appliquer_save_data(d)   → restaure le jeu depuis un tel dict
#       _charger_partie()         → charge le slot le plus récent
#                                   (bouton "Continuer" du menu)
#       _sauvegarder()            → écrit le slot 1 (sauvegarde manuelle)
#
#  Le détail du format JSON est documenté dans systems/save_system.py.
# ─────────────────────────────────────────────────────────────────────────────

import settings


class SaveMixin:
    """Méthodes liées à la sauvegarde / chargement de la partie."""

    # ─────────────────────────────────────────────────────────────────────
    #  Construction du dict à sauvegarder
    # ─────────────────────────────────────────────────────────────────────

    def _construire_save_data(self):
        """Capture l'état complet du jeu dans un dict sérialisable JSON.

        Format : voir l'en-tête de systems/save_system.py.
        Toute donnée qui doit survivre à une fermeture / un reload doit
        figurer ici.
        """
        j = self.joueur

        # Inventaire : on sauve UNIQUEMENT le nom des items par slot
        # (les images seront re-résolues à la restauration via ITEMS).
        inv_slots = []
        for slot in getattr(self.inventory, "slots", []):
            if slot is None:
                inv_slots.append(None)
            else:
                inv_slots.append({
                    "name":  slot.name,
                    "count": int(getattr(slot, "count", 1)),
                })

        # Ennemis tués : pour chaque map où on a tué qqn, on retient
        # les indices d'ennemis morts. Sauve dict {map → [idx1, idx2…]}.
        ennemis_morts = dict(getattr(self, "_ennemis_morts_par_map", {}))
        morts_actuels = [i for i, e in enumerate(self.ennemis) if not e.alive]
        if self.carte_actuelle and morts_actuels:
            ennemis_morts[self.carte_actuelle] = morts_actuels

        return {
            "_meta": {
                "play_time_s": int(getattr(self, "play_time_s", 0)),
            },
            "story": {
                "mode":                 self.mode,
                "current_map":          self.carte_actuelle,
                "cinematics_played":    self.cinematiques_jouees,
                "dialog_history":       self.historique_dialogues,
                "flags":                dict(getattr(self, "story_flags", {})),
            },
            "player": {
                "x":         int(j.rect.x),
                "y":         int(j.rect.y),
                "hp":        int(j.hp),
                "max_hp":    int(j.max_hp),
                "direction": int(j.direction),
            },
            "inventory": {
                "slots": inv_slots,
            },
            "fear": {
                "current": float(getattr(self.peur, "current", 0)),
                "target":  float(getattr(self.peur, "_target", 0)),
            },
            "companions": {
                "count":            len(self.compagnons.compagnons),
                "sources_obtained": list(getattr(self,
                                          "lucioles_sources_obtenues", set())),
            },
            "enemies": {
                "killed_per_map": ennemis_morts,
            },
            # Compétences débloquées (flags settings.skill_*).
            "skills": {
                "double_jump": bool(getattr(settings, "skill_double_jump", False)),
                "dash":        bool(getattr(settings, "skill_dash",        False)),
                "back_dodge":  bool(getattr(settings, "skill_back_dodge",  False)),
                "wall_jump":   bool(getattr(settings, "skill_wall_jump",   False)),
                "attack":      bool(getattr(settings, "skill_attack",      False)),
                "pogo":        bool(getattr(settings, "skill_pogo",        False)),
            },
        }

    # ─────────────────────────────────────────────────────────────────────
    #  Application d'un dict (chargement)
    # ─────────────────────────────────────────────────────────────────────

    def _appliquer_save_data(self, data):
        """Restaure l'état complet du jeu depuis un dict produit par
        _construire_save_data(). Symétrique de la méthode précédente.

        Découpée en plusieurs sections appelées dans l'ordre :
          1. story (mode, map, cines, flags)
          2. player (position, HP, direction)
          3. inventaire
          4. peur
          5. compagnons / lucioles
          6. ennemis tués par map
          7. compétences (skills)
          8. snap caméra
        """
        if not data:
            return
        self._restaurer_story(data)
        self._restaurer_player(data)
        self._restaurer_inventaire(data)
        self._restaurer_peur(data)
        self._restaurer_compagnons(data)
        self._restaurer_ennemis_tues(data)
        self._restaurer_skills(data)
        # Temps de jeu (méta).
        self.play_time_s = float(data.get("_meta", {}).get("play_time_s", 0))
        # Snap caméra (sinon elle lerp depuis 0,0 → on voit la map défiler).
        self.camera.snap_to(self.joueur.rect)

    # ── Sous-handlers de restauration ────────────────────────────────────

    def _restaurer_story(self, data):
        """Restaure mode / map / cines jouées / story flags."""
        story = data.get("story", {})
        self.mode                  = story.get("mode", "histoire")
        self.cinematiques_jouees   = dict(story.get("cinematics_played",  {}))
        self.historique_dialogues  = dict(story.get("dialog_history",     {}))
        self.story_flags           = dict(story.get("flags",              {}))
        if self.mode == "histoire":
            self.editeur.active = False
        carte = story.get("current_map", "")
        if carte:
            self.editeur.load_map_for_portal(carte)
            self.carte_actuelle = carte
            self._reconstruire_grille()
            self._murs_modifies()
            self._sync_triggers()
            self._appliquer_musique_carte()

    def _restaurer_player(self, data):
        """Restaure position / HP / direction du joueur."""
        j = self.joueur
        p = data.get("player", {})
        j.rect.x      = p.get("x", j.spawn_x)
        j.rect.y      = p.get("y", j.spawn_y)
        j.hp          = p.get("hp", j.max_hp)
        j.direction   = p.get("direction", j.direction)
        j.dead        = False
        j.vx = j.vy   = 0
        j.knockback_vx = 0
        # Mémorise la position chargée comme dernier point de save :
        # si le joueur meurt, "Recommencer" le ramène ICI.
        carte = data.get("story", {}).get("current_map", "")
        if carte:
            self._dernier_save_pos = (carte, j.rect.x, j.rect.y)

    def _restaurer_inventaire(self, data):
        """Restaure les items de l'inventaire (avec rétro-compat string)."""
        try:
            from ui.inventory import ITEMS, InventoryItem
            inv_slots = data.get("inventory", {}).get("slots", [])
            self.inventory.slots = [None] * len(self.inventory.slots)
            for i, entry in enumerate(inv_slots):
                if i >= len(self.inventory.slots) or entry is None:
                    continue
                # Rétro-compat : ancien format = juste le nom (string).
                if isinstance(entry, str):
                    name, count = entry, 1
                else:
                    name  = entry.get("name")
                    count = int(entry.get("count", 1))
                if not name or name not in ITEMS:
                    continue
                info = ITEMS[name]
                img  = self.inventory.images.get(name) if hasattr(self.inventory, "images") else None
                self.inventory.slots[i] = InventoryItem(
                    name, img, info.get("category", "Consommable"),
                    count=count,
                    stackable=bool(info.get("stackable", False)),
                    max_stack=int(info.get("max_stack", 1)),
                )
        except Exception as e:
            print(f"[Save] Restauration inventaire échouée : {e}")

    def _restaurer_peur(self, data):
        """Restaure le niveau de peur courant (et la cible)."""
        fear = data.get("fear", {})
        if hasattr(self.peur, "current"):
            self.peur.current = float(fear.get("current", self.peur.current))
        if hasattr(self.peur, "_target"):
            self.peur._target = float(fear.get("target",  self.peur._target))

    def _restaurer_compagnons(self, data):
        """Restaure le nombre de lucioles + leurs sources obtenues."""
        comps = data.get("companions", {})
        if "count" in comps:
            self.compagnons.set_nb(int(comps["count"]))
        self.lucioles_sources_obtenues = set(comps.get("sources_obtained", []))
        self.compagnons.respawn(self.joueur)

    def _restaurer_ennemis_tues(self, data):
        """Restaure les ennemis déjà tués (par map) et applique à la map
        courante."""
        ennemis = data.get("enemies", {})
        self._ennemis_morts_par_map = dict(ennemis.get("killed_per_map", {}))
        morts = self._ennemis_morts_par_map.get(self.carte_actuelle, [])
        for i, e in enumerate(self.ennemis):
            e.alive = i not in morts

    def _restaurer_skills(self, data):
        """Restaure les compétences débloquées (flags settings.skill_*)."""
        skills = data.get("skills", {})
        for nom in ("double_jump", "dash", "back_dodge",
                    "wall_jump", "attack", "pogo"):
            if nom in skills:
                setattr(settings, f"skill_{nom}", bool(skills[nom]))

    # ─────────────────────────────────────────────────────────────────────
    #  Charger / Sauvegarder (raccourcis menu)
    # ─────────────────────────────────────────────────────────────────────

    def _charger_partie(self):
        """Charge le slot le plus récent (= bouton "Continuer" du menu).

        Convention type Hollow Knight / Celeste : "Continuer" = ta partie
        la plus fraîche, sans choix à faire. Pour switcher entre slots,
        utilise le menu Charger pendant la pause.
        """
        from systems.save_system import charger_slot, slot_le_plus_recent
        from core.state_manager import GAME
        slot = slot_le_plus_recent()
        donnees = charger_slot(slot) if slot else None
        if not donnees:
            self._nouvelle_partie()
            return

        self._appliquer_save_data(donnees)
        self.etats.switch(GAME)

    def _sauvegarder(self):
        """Sauvegarde la partie dans le slot 1 (bouton sauvegarde par défaut)."""
        from systems.save_system import sauvegarder_slot
        sauvegarder_slot(1, self._construire_save_data())
