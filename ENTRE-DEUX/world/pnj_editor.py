# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Éditeur de dialogues PNJ in-game
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Une interface dédiée pour gérer les conversations d'un PNJ : avant, on
#  ne pouvait qu'AJOUTER une conversation entière sur une seule ligne avec
#  des `|` comme séparateurs. Désormais on peut :
#     - voir TOUTES les conversations d'un PNJ
#     - éditer une conversation existante (ajouter/supprimer/modifier des lignes)
#     - supprimer une conversation
#     - changer l'orateur de chaque ligne (multi-orateur)
#     - changer le mode du PNJ (boucle / restart)
#
#  ON L'OUVRE COMMENT ?
#  --------------------
#  Dans l'éditeur, en mode 11 (PNJ), survol d'un PNJ + [F3].
#
#  STRUCTURE
#  ---------
#  2 niveaux de navigation :
#     1) Liste des CONVERSATIONS du PNJ (vue globale)
#     2) Liste des LIGNES d'une conversation (édition fine)
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS PRESSE-PAPIERS (Ctrl+V / Ctrl+C dans les saisies de texte)
# ─────────────────────────────────────────────────────────────────────────────
#  Permet de coller des répliques depuis un script externe (Word, Google Doc).

def _clipboard_get():
    try:
        import tkinter
        r = tkinter.Tk()
        r.withdraw()
        try:
            text = r.clipboard_get()
        except Exception:
            text = ""
        r.destroy()
        return text or ""
    except Exception:
        return ""


def _clipboard_set(text):
    try:
        import tkinter
        r = tkinter.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(str(text))
        r.update()
        r.destroy()
    except Exception:
        pass


class PNJEditor:
    """Mini-éditeur de dialogues pour un PNJ.

    Modes internes :
        None         = navigation (niveau conv / niveau ligne selon self.niveau)
        "edit_line"  = saisie texte (édition d'une ligne)
        "edit_orator"= saisie texte (édition de l'orateur d'une ligne)
        "confirm"    = confirmation (suppression d'une conversation)
    """

    def __init__(self):
        self.actif       = False
        self.pnj         = None        # référence au PNJ en cours d'édition
        self.niveau      = "conv"      # "conv" (liste convs) | "line" (lignes d'une conv)

        self.conv_idx    = 0           # index de la conversation sélectionnée
        self.line_idx    = 0           # index de la ligne (en mode "line")

        self.mode        = None        # cf. docstring
        self._input      = ""
        self._input_for  = ""          # "line" | "orator" | "cond" | "events" | "flag_req"

        # ── Popup "nouveau flag" ─────────────────────────────────────────
        # Quand l'utilisateur écrit flag:key+=N sans :req=M et que "key"
        # n'est pas encore dans le registre, on demande le required count
        # avant de finaliser les events. Ces attributs gèrent cette file.
        self._pending_events   = []    # events parsés en attente de validation
        self._new_flags_queue  = []    # noms de flags qui ont besoin d'un required
        self._asking_flag      = ""    # flag actuellement en cours de demande

        # Polices lazy
        self._font   = None
        self._fontsm = None

        self._msg       = ""
        self._msg_timer = 0.0

    # ─────────────────────────────────────────────────────────────────────────
    #  Cycle de vie
    # ─────────────────────────────────────────────────────────────────────────

    def ouvrir(self, pnj):
        if pnj is None:
            return
        self.actif    = True
        self.pnj      = pnj
        self.niveau   = "conv"
        self.conv_idx = 0
        self.line_idx = 0
        self.mode     = None

    def fermer(self):
        self.actif = False
        self.pnj   = None
        self.mode  = None

    def _msg_show(self, msg, duration=2.0):
        self._msg       = msg
        self._msg_timer = duration

    # ─────────────────────────────────────────────────────────────────────────
    #  Polices
    # ─────────────────────────────────────────────────────────────────────────

    def _get_fonts(self):
        if self._font is None:
            self._font   = pygame.font.SysFont("Consolas", 17)
            self._fontsm = pygame.font.SysFont("Consolas", 13)
        return self._font, self._fontsm

    # ─────────────────────────────────────────────────────────────────────────
    #  Helpers d'accès aux conversations
    # ─────────────────────────────────────────────────────────────────────────

    def _convs(self):
        if self.pnj is None:
            return []
        return self.pnj._dialogues

    def _conv_courante(self):
        convs = self._convs()
        if 0 <= self.conv_idx < len(convs):
            return convs[self.conv_idx]
        return None

    # ─────────────────────────────────────────────────────────────────────────
    #  Entrée clavier
    # ─────────────────────────────────────────────────────────────────────────

    def handle_key(self, key, mods=0):
        if not self.actif:
            return False

        if key == pygame.K_ESCAPE:
            if self.mode == "ask_flag_req":
                # Annule toute la saisie des events (y compris la file)
                self._pending_events  = []
                self._new_flags_queue = []
                self._asking_flag     = ""
                self.mode   = None
                self._input = ""
            elif self.mode is not None:
                self.mode   = None
                self._input = ""
            elif self.niveau == "line":
                self.niveau = "conv"
            else:
                self.fermer()
            return True

        if self.mode in ("edit_line", "edit_orator", "edit_cond",
                         "edit_events", "ask_flag_req"):
            return self._handle_key_text(key)

        if self.niveau == "conv":
            return self._handle_key_convs(key, mods)
        else:
            return self._handle_key_lines(key, mods)

    def handle_textinput(self, text):
        if not self.actif:
            return
        if self.mode in ("edit_line", "edit_orator", "edit_cond",
                         "edit_events", "ask_flag_req"):
            self._input += text

    def _handle_key_text(self, key):
        mods = pygame.key.get_mods()
        ctrl = bool(mods & pygame.KMOD_CTRL)
        if key == pygame.K_RETURN:
            self._confirmer_saisie()
        elif key == pygame.K_BACKSPACE:
            self._input = self._input[:-1]
        elif ctrl and key == pygame.K_v:
            # Ctrl+V : colle le presse-papiers (utile pour coller des
            # répliques depuis un script Word/Google Doc).
            txt = _clipboard_get().replace("\r\n", "\n").replace("\r", "\n")
            # Pour les saisies de ligne, on remplace les retours de ligne
            # par un espace (1 réplique = 1 ligne).
            self._input += txt.replace("\n", " ")
        elif ctrl and key == pygame.K_c:
            _clipboard_set(self._input)
        return True

    # ── Niveau 1 : liste des conversations ───────────────────────────────────

    def _handle_key_convs(self, key, mods):
        convs = self._convs()
        n = len(convs)
        ctrl = bool(mods & pygame.KMOD_CTRL)

        if key == pygame.K_UP and n:
            self.conv_idx = (self.conv_idx - 1) % n
        elif key == pygame.K_DOWN and n:
            self.conv_idx = (self.conv_idx + 1) % n
        elif key == pygame.K_RETURN and n:
            # Entrer dans la conversation
            self.niveau   = "line"
            self.line_idx = 0
        elif key in (pygame.K_a, pygame.K_KP_PLUS, pygame.K_PLUS, pygame.K_EQUALS):
            # Nouvelle conversation : avec une ligne vide pour démarrer
            convs.append([("", self.pnj.nom)])
            self.conv_idx = len(convs) - 1
            self.niveau   = "line"
            self.line_idx = 0
            self._commencer_edition_ligne()
        elif key in (pygame.K_d, pygame.K_KP_MINUS, pygame.K_MINUS,
                     pygame.K_DELETE) and n:
            # Supprimer la conversation sélectionnée
            convs.pop(self.conv_idx)
            if self.conv_idx >= len(convs):
                self.conv_idx = max(0, len(convs) - 1)
        elif key == pygame.K_w:
            # Cycle entre boucle_dernier et restart
            modes = ["boucle_dernier", "restart"]
            cur   = self.pnj.dialogue_mode
            idx   = modes.index(cur) if cur in modes else 0
            self.pnj.dialogue_mode = modes[(idx + 1) % len(modes)]
            self._msg_show(f"Mode : {self.pnj.dialogue_mode}")
        elif key == pygame.K_b:
            # Toggle SAVE POINT : si activé, l'interaction (E) avec ce PNJ
            # ouvrira le menu de sauvegarde au lieu de jouer un dialogue.
            # Style banc Hollow Knight.
            self.pnj.is_save_point = not getattr(self.pnj, "is_save_point", False)
            etat = "ON" if self.pnj.is_save_point else "OFF"
            self._msg_show(f"Save point : {etat}  (touche B pour basculer)")
        elif key == pygame.K_f and n:
            # [F] = éditer la CONDITION de la conversation sélectionnée.
            # Format texte (cf. _parser_condition / _format_condition).
            self._commencer_edition_condition()
        elif key == pygame.K_e and n:
            # [E] = éditer les ÉVÉNEMENTS déclenchés à la fin de la conv
            # (skill, luciole, coins, hp, max_hp, item, flag).
            self._commencer_edition_events()
        return True

    # ── Niveau 2 : lignes d'une conversation ─────────────────────────────────

    def _handle_key_lines(self, key, mods):
        conv = self._conv_courante()
        if conv is None:
            self.niveau = "conv"
            return True
        n     = len(conv)
        shift = bool(mods & pygame.KMOD_SHIFT)

        # Réordonner avec Maj+↑/↓
        if shift and key == pygame.K_UP and n and self.line_idx > 0:
            conv[self.line_idx], conv[self.line_idx - 1] = \
                conv[self.line_idx - 1], conv[self.line_idx]
            self.line_idx -= 1
        elif shift and key == pygame.K_DOWN and n and self.line_idx < n - 1:
            conv[self.line_idx], conv[self.line_idx + 1] = \
                conv[self.line_idx + 1], conv[self.line_idx]
            self.line_idx += 1

        elif key == pygame.K_UP and n:
            self.line_idx = (self.line_idx - 1) % n
        elif key == pygame.K_DOWN and n:
            self.line_idx = (self.line_idx + 1) % n
        elif key == pygame.K_RETURN and n:
            self._commencer_edition_ligne()
        elif key == pygame.K_o and n:
            # [O] = changer l'orateur
            self._commencer_edition_orateur()
        elif key in (pygame.K_a, pygame.K_KP_PLUS, pygame.K_PLUS, pygame.K_EQUALS):
            # Nouvelle ligne (insère APRÈS la sélection)
            conv.insert(self.line_idx + 1, ("", self.pnj.nom))
            self.line_idx += 1
            self._commencer_edition_ligne()
        elif key in (pygame.K_d, pygame.K_KP_MINUS, pygame.K_MINUS,
                     pygame.K_DELETE) and n:
            conv.pop(self.line_idx)
            if self.line_idx >= len(conv):
                self.line_idx = max(0, len(conv) - 1)
            # Si la conv est vide, on revient au niveau 1
            if not conv:
                convs = self._convs()
                convs.pop(self.conv_idx)
                if self.conv_idx >= len(convs):
                    self.conv_idx = max(0, len(convs) - 1)
                self.niveau = "conv"
        return True

    # ─────────────────────────────────────────────────────────────────────────
    #  Saisie de texte
    # ─────────────────────────────────────────────────────────────────────────

    def _commencer_edition_ligne(self):
        conv = self._conv_courante()
        if conv is None or not (0 <= self.line_idx < len(conv)):
            return
        texte, _ = conv[self.line_idx]
        self.mode       = "edit_line"
        self._input_for = "line"
        self._input     = texte

    def _commencer_edition_orateur(self):
        conv = self._conv_courante()
        if conv is None or not (0 <= self.line_idx < len(conv)):
            return
        _, orateur = conv[self.line_idx]
        self.mode       = "edit_orator"
        self._input_for = "orator"
        self._input     = orateur

    def _confirmer_saisie(self):
        # Réponse au popup "required count d'un nouveau flag"
        if self._input_for == "flag_req":
            self._confirmer_flag_req()
            return
        # Édition d'une condition (mode "edit_cond")
        if self._input_for == "cond":
            self._enregistrer_condition(self._input)
            self.mode   = None
            self._input = ""
            return
        # Édition des events de fin de conv (mode "edit_events")
        if self._input_for == "events":
            events, nouveaux_flags = self._parser_events(self._input)
            if nouveaux_flags:
                # Il y a des flags inconnus → on demande leur required avant
                # de finaliser. On stocke les events parsés et on lance la
                # file d'attente.
                self._pending_events  = events
                self._new_flags_queue = list(nouveaux_flags)
                self._input = ""
                self._start_ask_flag_req()
            else:
                self._finaliser_events(events)
            return
        conv = self._conv_courante()
        if conv is None or not (0 <= self.line_idx < len(conv)):
            self.mode = None
            return
        texte, orateur = conv[self.line_idx]
        if self._input_for == "line":
            conv[self.line_idx] = (self._input, orateur)
        elif self._input_for == "orator":
            conv[self.line_idx] = (texte, self._input or self.pnj.nom)
        self.mode   = None
        self._input = ""

    # ── Édition des conditions de dialogue (story flags) ─────────────────────

    def _commencer_edition_condition(self):
        """Ouvre la saisie de condition pour la conversation sélectionnée.

        Format texte attendu :
            (vide)              → pas de condition (toujours dispo)
            flag:key            → dispo si game.story_flags[key] == True
            flag:key=0          → dispo si flag absent ou False
            any:k1,k2,k3        → dispo si AU MOINS un flag est True
            all:k1,k2,k3        → dispo si TOUS les flags sont True
        """
        if self.pnj is None:
            return
        # Aligne le tableau si nécessaire (PNJ ouverts avant la feature).
        if not hasattr(self.pnj, "dialogue_conditions"):
            self.pnj.dialogue_conditions = []
        while len(self.pnj.dialogue_conditions) < len(self._convs()):
            self.pnj.dialogue_conditions.append(None)
        cond_actuelle = self.pnj.dialogue_conditions[self.conv_idx]
        self.mode       = "edit_cond"
        self._input_for = "cond"
        self._input     = self._format_condition(cond_actuelle)

    def _format_condition(self, cond):
        """Convertit un dict condition en texte éditable."""
        if not cond:
            return ""
        if "flag" in cond:
            v = cond.get("value", True)
            return f"flag:{cond['flag']}" if v else f"flag:{cond['flag']}=0"
        if "any" in cond:
            return "any:" + ",".join(cond.get("any", []))
        if "all" in cond:
            return "all:" + ",".join(cond.get("all", []))
        return ""

    def _enregistrer_condition(self, texte):
        """Parse le texte saisi et le stocke dans dialogue_conditions[idx]."""
        if not hasattr(self.pnj, "dialogue_conditions"):
            self.pnj.dialogue_conditions = []
        while len(self.pnj.dialogue_conditions) < len(self._convs()):
            self.pnj.dialogue_conditions.append(None)
        t = texte.strip()
        cond = None
        if not t:
            cond = None
        elif t.startswith("flag:"):
            rest = t[5:]
            if "=" in rest:
                key, val = rest.split("=", 1)
                cond = {"flag": key.strip(), "value": val.strip() not in ("0", "false", "False", "")}
            else:
                cond = {"flag": rest.strip()}
        elif t.startswith("any:"):
            cond = {"any": [k.strip() for k in t[4:].split(",") if k.strip()]}
        elif t.startswith("all:"):
            cond = {"all": [k.strip() for k in t[4:].split(",") if k.strip()]}
        else:
            self._msg_show("Format invalide (vide / flag:k / flag:k=0 / any:k1,k2 / all:k1,k2)", 4)
            return
        self.pnj.dialogue_conditions[self.conv_idx] = cond
        self._msg_show("Condition enregistrée ✓")

    # ── Édition des events de fin de dialogue ────────────────────────────────

    def _commencer_edition_events(self):
        """Ouvre la saisie des events pour la conversation sélectionnée.

        Format texte (1 event par segment, séparés par "; ") :
            (vide)                         → aucun event
            skill:double_jump              → débloque la compétence
            luciole:anna_rite              → +1 luciole (source unique)
            coins:50                       → +50 pièces
            hp:2                           → +2 PV
            max_hp:1                       → +1 PV max
            item:Pomme                     → +1 Pomme (count=1)
            item:Pomme:5                   → +5 Pommes
            flag:parchemins_lus            → pose flag à True
            flag:parchemins_lus=0          → pose flag à False

        Les events s'ENCHAÎNENT dans l'ordre :
            skill:dash; luciole:boss_foret; coins:20
        """
        if self.pnj is None:
            return
        if not hasattr(self.pnj, "events"):
            self.pnj.events = []
        while len(self.pnj.events) < len(self._convs()):
            self.pnj.events.append([])
        events_actuels = self.pnj.events[self.conv_idx] or []
        self.mode       = "edit_events"
        self._input_for = "events"
        self._input     = self._format_events(events_actuels)

    # ── Gestion des nouveaux flags (popup required count) ────────────────────

    def _start_ask_flag_req(self):
        """Lance (ou avance) la file de demande de required count."""
        if not self._new_flags_queue:
            # File vide : on peut finaliser
            self._finaliser_events(self._pending_events)
            return
        self._asking_flag   = self._new_flags_queue[0]
        self.mode           = "ask_flag_req"
        self._input_for     = "flag_req"
        self._input         = "1"   # valeur par défaut

    def _confirmer_flag_req(self):
        """L'utilisateur vient de valider le required count pour un flag."""
        try:
            req = max(1, int(self._input.strip()))
        except ValueError:
            req = 1
        from systems.story_flags import ajouter_au_registre
        ajouter_au_registre(self._asking_flag, required=req)
        # Cherche dans _pending_events cet event flag_increment et lui injecte required
        for ev in self._pending_events:
            if (ev.get("type") == "flag_increment"
                    and ev.get("key") == self._asking_flag
                    and ev.get("required") is None):
                ev["required"] = req
        self._new_flags_queue.pop(0)
        self._input = ""
        self._start_ask_flag_req()   # continue avec le suivant

    def _finaliser_events(self, events):
        """Enregistre la liste d'events finalisée pour la conv courante."""
        if not hasattr(self.pnj, "events"):
            self.pnj.events = []
        while len(self.pnj.events) < len(self._convs()):
            self.pnj.events.append([])
        self.pnj.events[self.conv_idx] = events
        self._pending_events  = []
        self._new_flags_queue = []
        self._asking_flag     = ""
        self.mode             = None
        self._input           = ""
        self._msg_show(f"Événements enregistrés ({len(events)}) ✓")

    # ── Format / parse des events ────────────────────────────────────────────

    def _format_events(self, events):
        """Convertit une liste d'events en texte éditable."""
        parts = []
        for e in events:
            if not isinstance(e, dict):
                continue
            t = e.get("type", "")
            if t == "skill":
                parts.append(f"skill:{e.get('value','')}")
            elif t == "luciole":
                parts.append(f"luciole:{e.get('source','')}")
            elif t in ("coins", "hp", "max_hp"):
                parts.append(f"{t}:{e.get('value', 0)}")
            elif t == "item":
                n = e.get("count", 1)
                parts.append(f"item:{e.get('value','')}"
                             + (f":{n}" if n != 1 else ""))
            elif t == "flag":
                v = e.get("value", True)
                k = e.get("key", "")
                parts.append(f"flag:{k}" if v else f"flag:{k}=0")
            elif t == "flag_increment":
                k     = e.get("key", "")
                delta = int(e.get("delta", 1))
                req   = e.get("required")
                sign  = f"+={delta}" if delta >= 0 else f"-={abs(delta)}"
                suffix = f":req={req}" if req is not None else ""
                parts.append(f"flag:{k}{sign}{suffix}")
            elif t == "teleport":
                # tp:cible[:x:y]   où cible peut être "spawn" ou "map spawn"
                cible = e.get("cible", "") or ""
                x = e.get("x")
                y = e.get("y")
                if x is not None and y is not None:
                    parts.append(f"tp:{cible}:{x}:{y}")
                else:
                    parts.append(f"tp:{cible}")
        return "; ".join(parts)

    def _parser_events(self, texte):
        """Parse le texte et retourne (events_list, nouveaux_flags).

        nouveaux_flags = set des clés flag_increment non présentes dans le
        registre et sans :req= explicite → ils nécessitent une popup.
        """
        from systems.story_flags import flag_dans_registre

        events         = []
        nouveaux_flags = []

        for seg in texte.split(";"):
            seg = seg.strip()
            if not seg or ":" not in seg:
                continue
            t, rest = seg.split(":", 1)
            t    = t.strip()
            rest = rest.strip()

            if t == "skill":
                events.append({"type": "skill", "value": rest})
            elif t == "luciole":
                events.append({"type": "luciole", "source": rest})
            elif t in ("coins", "hp", "max_hp"):
                try:
                    events.append({"type": t, "value": int(rest)})
                except ValueError:
                    pass
            elif t == "item":
                if ":" in rest:
                    name, cnt = rest.split(":", 1)
                    try:
                        events.append({"type": "item",
                                       "value": name.strip(),
                                       "count": int(cnt)})
                    except ValueError:
                        events.append({"type": "item", "value": name.strip()})
                else:
                    events.append({"type": "item", "value": rest})
            elif t == "flag":
                # Syntaxe flag:key            → booléen True
                # Syntaxe flag:key=0          → booléen False
                # Syntaxe flag:key+=N         → incrémentation (N peut être omis = 1)
                # Syntaxe flag:key+=N:req=M   → incrémentation avec required explicite
                if "+=" in rest or "-=" in rest:
                    op  = "+=" if "+=" in rest else "-="
                    key_part, delta_part = rest.split(op, 1)
                    key   = key_part.strip()
                    delta = 1 if op == "+=" else -1
                    req   = None
                    # Cherche :req=N dans delta_part
                    if ":req=" in delta_part:
                        dp, rp = delta_part.split(":req=", 1)
                        try:
                            delta = int(dp.strip()) if dp.strip() else 1
                        except ValueError:
                            delta = 1
                        try:
                            req = max(1, int(rp.strip()))
                        except ValueError:
                            req = None
                    else:
                        try:
                            delta = int(delta_part.strip()) if delta_part.strip() else 1
                        except ValueError:
                            delta = 1
                    if op == "-=":
                        delta = -abs(delta)
                    ev = {"type": "flag_increment", "key": key, "delta": delta}
                    if req is not None:
                        ev["required"] = req
                    events.append(ev)
                    # Est-ce un nouveau flag sans required explicite ?
                    if req is None and not flag_dans_registre(key):
                        if key not in nouveaux_flags:
                            nouveaux_flags.append(key)
                elif "=" in rest:
                    k, v = rest.split("=", 1)
                    events.append({"type": "flag", "key": k.strip(),
                                   "value": v.strip() not in ("0", "false", "False", "")})
                else:
                    events.append({"type": "flag", "key": rest, "value": True})
            elif t == "tp":
                # tp:cible                → cible est "spawn" ou "map spawn"
                # tp:cible:X:Y            → fallback x/y si spawn introuvable
                # tp::X:Y                 → x/y purs sans cible
                ev = {"type": "teleport"}
                # Sépare cible / x / y. On découpe sur ":" mais la cible
                # peut contenir un espace ("map spawn"), donc on s'attend
                # à au plus 3 segments.
                segs = rest.split(":")
                if len(segs) >= 1:
                    ev["cible"] = segs[0].strip()
                if len(segs) >= 3:
                    try:
                        ev["x"] = float(segs[1].strip()) if segs[1].strip() else None
                        ev["y"] = float(segs[2].strip()) if segs[2].strip() else None
                    except ValueError:
                        pass
                events.append(ev)
            else:
                self._msg_show(f"Event inconnu : {t}", 4)

        return events, nouveaux_flags

    def _enregistrer_events(self, texte):
        """Parse le texte et stocke la liste d'events pour la conv courante.

        Méthode de compatibilité — appelle _parser_events + _finaliser_events.
        """
        events, nouveaux_flags = self._parser_events(texte)
        if nouveaux_flags:
            self._pending_events  = events
            self._new_flags_queue = list(nouveaux_flags)
            self._start_ask_flag_req()
        else:
            self._finaliser_events(events)

    # ─────────────────────────────────────────────────────────────────────────
    #  Rendu
    # ─────────────────────────────────────────────────────────────────────────

    def update(self, dt):
        if self._msg_timer > 0:
            self._msg_timer -= dt

    def draw(self, surf):
        if not self.actif or self.pnj is None:
            return
        font, fontsm = self._get_fonts()
        w, h = surf.get_size()

        # Voile
        voile = pygame.Surface((w, h), pygame.SRCALPHA)
        voile.fill((0, 0, 0, 200))
        surf.blit(voile, (0, 0))

        # Cadre
        marge = 60
        cadre = pygame.Rect(marge, marge, w - 2 * marge, h - 2 * marge)
        pygame.draw.rect(surf, (25, 25, 35), cadre)
        pygame.draw.rect(surf, (190, 175, 240), cadre, 2)

        # Titre
        chemin = f"PNJ > {self.pnj.nom}"
        if self.niveau == "line":
            chemin += f" > Conversation {self.conv_idx + 1}"
        surf.blit(font.render(chemin, True, (190, 175, 240)),
                  (cadre.x + 16, cadre.y + 12))

        # Aide contextuelle
        if self.niveau == "conv":
            aide = ("[↑↓] [Entrée] ouvrir [A]+ [D]- [W]mode [B]save [F]cond "
                    "[E]events [Ctrl+V]coller [Esc]")
        else:
            aide = ("[↑↓] | [Entrée] éditer texte | [O] orateur | [A] +ligne | "
                    "[D] -ligne | [Maj+↑↓] reordonner | [Esc] retour")
        surf.blit(fontsm.render(aide, True, (140, 140, 140)),
                  (cadre.x + 16, cadre.y + 38))

        # Mode info + flag save point
        save_pt = " | [SAVE POINT]" if getattr(self.pnj, "is_save_point", False) else ""
        info = (f"Mode : {self.pnj.dialogue_mode}  |  "
                f"{len(self._convs())} conversation(s){save_pt}")
        couleur = (255, 220, 100) if save_pt else (180, 200, 230)
        surf.blit(fontsm.render(info, True, couleur),
                  (cadre.x + 16, cadre.y + 60))

        # Contenu selon niveau
        y = cadre.y + 90
        if self.niveau == "conv":
            self._draw_convs(surf, font, cadre, y)
        else:
            self._draw_lines(surf, font, cadre, y)

        # Message
        if self._msg_timer > 0 and self._msg:
            ms = font.render(self._msg, True, (255, 220, 120))
            surf.blit(ms, (cadre.centerx - ms.get_width() // 2, cadre.bottom - 30))

        # Popup d'édition
        if self.mode in ("edit_line", "edit_orator", "edit_cond", "edit_events"):
            self._draw_popup_edit(surf, font, fontsm)
        elif self.mode == "ask_flag_req":
            self._draw_popup_flag_req(surf, font, fontsm)

    def _draw_convs(self, surf, font, cadre, y):
        convs = self._convs()
        if not convs:
            surf.blit(font.render("(aucune conversation — [A] pour en créer une)",
                                  True, (140, 140, 140)),
                      (cadre.x + 16, y))
            return
        for i, conv in enumerate(convs):
            if i == self.conv_idx and self.mode is None:
                pygame.draw.rect(surf, (60, 60, 90),
                                 (cadre.x + 12, y - 2, cadre.width - 24, 22))
            color = (255, 255, 255) if i == self.conv_idx else (200, 200, 220)
            apercu = "(vide)"
            if conv:
                apercu = (conv[0][0] or "")[:55]
                if len(conv) > 1:
                    apercu += f"  …  ({len(conv)} lignes)"
            surf.blit(font.render(f"{i+1:2d}. {apercu}", True, color),
                      (cadre.x + 16, y))
            # Affiche condition (doré) et indicateur events (vert) à droite.
            conds = getattr(self.pnj, "dialogue_conditions", []) or []
            cond  = conds[i] if i < len(conds) else None
            evts  = getattr(self.pnj, "events", []) or []
            evs   = evts[i] if i < len(evts) else []
            x_end = cadre.right - 20
            if evs:
                tag = self._fontsm.render(
                    f"[E×{len(evs)}]", True, (140, 220, 140))
                x_end -= tag.get_width()
                surf.blit(tag, (x_end, y + 4))
                x_end -= 8
            if cond:
                cond_str = "[?] " + self._format_condition(cond)
                cs = self._fontsm.render(cond_str, True, (255, 215, 70))
                x_end -= cs.get_width()
                surf.blit(cs, (x_end, y + 4))
            y += 22
            if y > cadre.bottom - 30:
                break

    def _draw_lines(self, surf, font, cadre, y):
        conv = self._conv_courante()
        if conv is None:
            return
        if not conv:
            surf.blit(font.render("(conversation vide — [A] pour ajouter une ligne)",
                                  True, (140, 140, 140)),
                      (cadre.x + 16, y))
            return
        for i, (texte, orateur) in enumerate(conv):
            if i == self.line_idx and self.mode is None:
                pygame.draw.rect(surf, (60, 60, 90),
                                 (cadre.x + 12, y - 2, cadre.width - 24, 22))
            color  = (255, 255, 255) if i == self.line_idx else (200, 200, 220)
            label  = f"{i+1:2d}. [{orateur}] {texte}"
            # Tronque visuellement si trop long
            if font.size(label)[0] > cadre.width - 40:
                while label and font.size(label + "…")[0] > cadre.width - 40:
                    label = label[:-1]
                label += "…"
            surf.blit(font.render(label, True, color),
                      (cadre.x + 16, y))
            y += 22
            if y > cadre.bottom - 30:
                break

    def _draw_popup_edit(self, surf, font, fontsm):
        sw, sh = surf.get_size()
        # Plus large + plus haut pour accueillir le wrap multi-lignes.
        bw, bh = 900, 230
        box = pygame.Rect(sw // 2 - bw // 2, sh // 2 - bh // 2, bw, bh)
        pygame.draw.rect(surf, (30, 30, 45), box)
        pygame.draw.rect(surf, (190, 175, 240), box, 2)
        if self._input_for == "line":
            titre = "Texte de la ligne :"
            aide  = "[Enter] valider | [Esc] annuler | [Ctrl+V] coller"
        elif self._input_for == "orator":
            titre = "Orateur (qui parle) :"
            aide  = "[Enter] valider | [Esc] annuler | [Ctrl+V] coller"
        elif self._input_for == "cond":
            titre = "Condition de la conversation :"
            aide  = ("[vide] = toujours dispo | flag:k | flag:k=0 | "
                     "any:k1,k2 | all:k1,k2  —  [Enter] valider | [Esc]")
        else:  # events
            titre = "Événements de fin de conversation :"
            aide  = ("Ex: skill:double_jump; coins:50; item:Pomme:5; "
                     "flag:tiroirs+=1:req=2; tp:nom_spawn; tp:map nom_spawn  "
                     "—  [Enter] | [Esc]")
        surf.blit(font.render(titre, True, (190, 175, 240)),
                  (box.x + 16, box.y + 12))

        # ── Affichage avec wrap automatique ──────────────────────────────
        # Le texte saisi peut être très long ; on coupe en lignes pour
        # rester dans la box au lieu de déborder.
        largeur_max = box.width - 32
        lignes = self._wrap_texte(self._input + "_", font, largeur_max)
        # On affiche au plus 5 lignes (en gardant les dernières si besoin)
        max_lignes_visibles = 5
        lignes_visibles = lignes[-max_lignes_visibles:]
        y = box.y + 46
        for ligne in lignes_visibles:
            surf.blit(font.render(ligne, True, (255, 255, 255)),
                      (box.x + 16, y))
            y += 22

        surf.blit(fontsm.render(aide, True, (140, 140, 140)),
                  (box.x + 16, box.bottom - 24))

    def _draw_popup_flag_req(self, surf, font, fontsm):
        """Popup demandant le nombre d'activations requises pour un nouveau flag."""
        sw, sh = surf.get_size()
        bw, bh = 700, 170
        box = pygame.Rect(sw // 2 - bw // 2, sh // 2 - bh // 2, bw, bh)
        pygame.draw.rect(surf, (30, 30, 45), box)
        pygame.draw.rect(surf, (255, 215, 70), box, 2)

        titre = f"Nouveau flag : '{self._asking_flag}'"
        surf.blit(font.render(titre, True, (255, 215, 70)),
                  (box.x + 16, box.y + 12))
        question = "Combien d'activations sont nécessaires pour le compléter ?"
        surf.blit(fontsm.render(question, True, (220, 220, 220)),
                  (box.x + 16, box.y + 44))
        surf.blit(font.render(self._input + "_", True, (255, 255, 255)),
                  (box.x + 16, box.y + 76))
        # Indication de la file d'attente
        if len(self._new_flags_queue) > 1:
            reste = len(self._new_flags_queue) - 1
            surf.blit(fontsm.render(
                f"({reste} autre(s) flag(s) à définir après celui-ci)",
                True, (180, 180, 120)),
                (box.x + 16, box.y + 110))
        surf.blit(fontsm.render("[Enter] valider | [Esc] annuler tout",
                                True, (140, 140, 140)),
                  (box.x + 16, box.bottom - 24))

    def _wrap_texte(self, texte, font, largeur_max):
        """Coupe `texte` en lignes pour rester dans `largeur_max` (px).

        On respecte les espaces si possible, sinon on coupe au caractère
        (utile pour des chaînes sans espaces ou des URL longues)."""
        if not texte:
            return [""]
        lignes = []
        for paragraphe in texte.split("\n"):
            mots  = paragraphe.split(" ")
            ligne = ""
            for mot in mots:
                test = (ligne + " " + mot).strip()
                if font.size(test)[0] <= largeur_max:
                    ligne = test
                else:
                    if ligne:
                        lignes.append(ligne)
                    # Si le mot seul dépasse, on coupe au caractère.
                    if font.size(mot)[0] > largeur_max:
                        cur = ""
                        for c in mot:
                            if font.size(cur + c)[0] > largeur_max:
                                if cur:
                                    lignes.append(cur)
                                cur = c
                            else:
                                cur += c
                        ligne = cur
                    else:
                        ligne = mot
            lignes.append(ligne)
        return lignes or [""]
