# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Cinématiques scriptées (étapes typées)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Une cinématique = une petite "vidéo interne au moteur" : pendant
#  quelques secondes le joueur ne contrôle plus son personnage, et le jeu
#  joue une SUITE D'ÉTAPES écrites à l'avance (un PNJ marche jusqu'à un
#  point, puis dit deux phrases, puis l'écran fond au noir, etc.).
#
#  Ce fichier ne FAIT RIEN tout seul : il fournit
#       - une classe `Cutscene` qui contient une LISTE D'ÉTAPES,
#       - des "fabriques d'étapes" (wait, dialogue, npc_walk, …),
#       - un objet de contexte `CutsceneContext` qu'on lui passe au update().
#
#  C'est core/game.py qui :
#       1. crée la cinématique avec la liste d'étapes voulues,
#       2. bascule le jeu en état "cinematic" (input joueur figé),
#       3. appelle cutscene.update(dt, ctx) chaque frame,
#       4. quand cutscene.is_done() → revient en état "play".
#
#  POURQUOI UN MODULE DÉDIÉ ?
#  --------------------------
#  Pour ne PAS éparpiller la logique narrative dans tout le code. Toutes
#  les cinématiques (présentes et futures) se définissent comme une LISTE,
#  testable, modifiable, traduisible. Si on ajoute une nouvelle action
#  possible (ex : "secouer l'écran 1 s"), on l'ajoute UNE fois ici (dans
#  _exec_step), et toutes les cinématiques peuvent l'utiliser.
#
#  EXEMPLE D'UTILISATION
#  ---------------------
#       from systems.cutscene import (
#           Cutscene, CutsceneContext,
#           wait, dialogue, npc_walk, camera_focus, camera_release, fade,
#       )
#
#       # Construction (typiquement quand on entre dans une zone trigger).
#       scene = Cutscene([
#           camera_focus((1500, 200), duration=1.2),
#           dialogue([("Tu te souviens ?", "Voix")]),
#           npc_walk(pnj_1, target=(1600, 300), speed=80),
#           wait(0.5),
#           fade("out", duration=1.0),
#       ])
#
#       # Démarrage.
#       game.cutscene = scene
#       game.state    = "cinematic"
#
#       # Boucle (déjà appelée par game.update) :
#       ctx = CutsceneContext(game)
#       game.cutscene.update(dt, ctx)
#       if game.cutscene.is_done():
#           game.cutscene = None
#           game.state    = "play"
#
#  COMMENT ROUTER LES TOUCHES PENDANT UNE CINÉMATIQUE ?
#  ----------------------------------------------------
#  Pendant une étape "dialogue", la touche Espace/Entrée doit être
#  redirigée vers la BoiteDialogue (pour avancer ligne par ligne). Le
#  reste (Q/D, Espace pour sauter, F pour attaquer…) doit être ignoré.
#  Game.handle_key() peut faire :
#       if self.cutscene is not None:
#           self.cutscene.on_key(key)
#           return
#  → la cinématique gère elle-même les touches utiles.
#
#  Petit lexique :
#     - étape       = (type, params). Ex : ("wait", {"duration": 1.5}).
#     - fabrique    = petite fonction qui CONSTRUIT une étape (lisibilité).
#                     `wait(1.5)` est plus clair que `("wait", {"duration": 1.5})`.
#     - contexte    = boîte d'objets passés à chaque update : caméra, joueur,
#                     dialogue_box, etc. Évite que la cinématique ait à
#                     importer game.py (← circulaire).
#     - bloquante   = une étape qui n'est PAS finie tant qu'une condition
#                     n'est pas remplie (ex : dialogue tant que la boîte
#                     est active). Vs "wait" qui se finit au bout d'un délai.
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D10] dt                     — temps écoulé depuis la frame précédente
#     [D11] math.hypot             — distance entre 2 points (npc_walk)
#     [D13] Interpolation linéaire — caméra qui glisse vers une cible
#     [D22] Machine à états        — chaque cutscene avance étape par étape
#
# ─────────────────────────────────────────────────────────────────────────────

import math


# ═════════════════════════════════════════════════════════════════════════════
#  1. CONTEXTE — la boîte d'objets que la cinématique a le droit d'utiliser
# ═════════════════════════════════════════════════════════════════════════════
#
#  Une cinématique a besoin d'agir sur plusieurs systèmes du jeu (caméra,
#  boîte de dialogue, fondu, etc.). Plutôt que de faire dépendre cutscene.py
#  de game.py (ce qui créerait un import circulaire), on lui passe un
#  CONTEXTE — un petit objet qui contient les références utiles.
#
#  Si une référence est manquante (ex : pas de fondu prêt), l'étape
#  correspondante est ignorée silencieusement plutôt que de planter — c'est
#  voulu, pour permettre des cinématiques "minimales" en debug.

class CutsceneContext:
    """Boîte d'objets passés à Cutscene.update().

    Le seul attribut obligatoire est `game` (la référence à core.Game).
    Les autres sont des raccourcis lisibles vers ses sous-systèmes.

    Les fabriques d'étapes en bas du fichier listent ce qu'elles attendent
    dans le contexte (ex : npc_walk a besoin de game.dt, dialogue a besoin
    de game.dialogue_box, etc.)."""

    def __init__(self, game):
        self.game = game
        # Raccourcis pratiques. On utilise getattr avec un défaut None pour
        # rester robuste si un de ces systèmes n'existe pas encore (jeu en
        # cours d'initialisation, tests, etc.).
        self.camera       = getattr(game, "camera", None)
        self.joueur       = getattr(game, "joueur", None)
        # Note : la boîte de dialogue s'appelle "dialogue" dans game.py, pas
        # "dialogue_box". On expose les deux noms pour rester compatible
        # avec les anciens scripts.
        self.dialogue_box = getattr(game, "dialogue_box", None) \
                         or getattr(game, "dialogue",     None)
        self.particles    = getattr(game, "particles",    None)
        self.shake        = getattr(game, "shake",        None)
        # Liste des PNJ disponibles (passée par editeur.pnjs).
        editeur           = getattr(game, "editeur",      None)
        self.pnjs         = getattr(editeur, "pnjs", []) if editeur else []


# ═════════════════════════════════════════════════════════════════════════════
#  2. LA CLASSE CUTSCENE — joue une suite d'étapes
# ═════════════════════════════════════════════════════════════════════════════
#
#  Une étape = un tuple (type, params) où :
#       - type   : string identifiant l'action (cf. dispatch dans _exec_step)
#       - params : dictionnaire d'arguments
#
#  Algorithme :
#       1. update(dt, ctx) appelle _exec_step pour l'étape courante.
#       2. _exec_step renvoie True si l'étape est TERMINÉE, False sinon.
#       3. Quand True → on passe à la suivante (et on appelle aussi son
#          init la première fois → voir _step_local_state).
#       4. Quand toutes les étapes sont passées → is_done() = True.

class Cutscene:
    """Une cinématique scriptée.

    Usage :
        c = Cutscene([wait(1.0), dialogue([...]), npc_walk(pnj, (x,y))])
        # chaque frame :
        c.update(dt, ctx)
        if c.is_done(): ...
    """

    # ─────────────────────────────────────────────────────────────────────
    #  2.1 Construction
    # ─────────────────────────────────────────────────────────────────────

    def __init__(self, steps):
        """steps : liste d'étapes, soit produites par les fabriques en bas
        du fichier (recommandé), soit des tuples (type, params) bruts."""
        self.steps = list(steps)
        self.index = 0

        # État local de l'étape courante (timers, cibles intermédiaires, etc.).
        # Réinitialisé à chaque passage à une nouvelle étape — ça évite de
        # gérer des "if first_frame" partout dans _exec_step.
        self._local = {}
        self._step_initialized = False

    # ─────────────────────────────────────────────────────────────────────
    #  2.2 Mise à jour (boucle de jeu)
    # ─────────────────────────────────────────────────────────────────────

    def update(self, dt, ctx):
        """Avance la cinématique d'une frame.

        Renvoie True si la cinématique est encore en cours, False si elle
        est terminée (équivalent à not self.is_done() après l'appel)."""

        if self.is_done():
            return False

        step_type, params = self._etape_actuelle()

        # Première frame de cette étape → on initialise le state local.
        if not self._step_initialized:
            self._init_step(step_type, params, ctx)
            self._step_initialized = True

        terminee = self._exec_step(step_type, params, ctx, dt)

        if terminee:
            # Hook de fin d'étape (ex : libérer la caméra à la fin d'un
            # camera_focus avec duration). Optionnel.
            self._cleanup_step(step_type, params, ctx)
            self.index += 1
            self._local = {}
            self._step_initialized = False

        return not self.is_done()

    # ─────────────────────────────────────────────────────────────────────
    #  2.3 Hook clavier (relayé depuis game.handle_key)
    # ─────────────────────────────────────────────────────────────────────
    #
    #  Pendant une étape "dialogue", on veut qu'Espace / Entrée fasse avancer
    #  la boîte de dialogue (skip ou ligne suivante). On laisse aussi la
    #  cinématique se faire "skipper" entièrement avec Échap si jamais on
    #  veut un débrayage d'urgence (ex : tester rapidement une scène).

    def on_key(self, key, ctx):
        """Une touche a été pressée pendant la cinématique. Retourne True si
        elle a été 'consommée' par la cinématique (= ne pas la repasser au
        reste du jeu)."""

        # Pour éviter de coder en dur les codes pygame ici (et donc de
        # l'importer pour rien), on laisse l'appelant nous filer un nom
        # symbolique si besoin. Ici on suppose `key` = un entier pygame.
        try:
            import pygame
            ESPACE  = pygame.K_SPACE
            RETOUR  = pygame.K_RETURN
            ECHAP   = pygame.K_ESCAPE
        except ImportError:
            return False

        if not self.steps:
            return False

        step_type, _params = self._etape_actuelle()

        if step_type == "dialogue":
            if key in (ESPACE, RETOUR):
                if ctx.dialogue_box is not None:
                    ctx.dialogue_box.avancer()
                return True

        # Échap = annuler la cinématique (saute toutes les étapes restantes).
        # Volontairement permissif : utile en debug et en cas de blocage.
        if key == ECHAP:
            self.skip_all(ctx)
            return True

        return False

    # ─────────────────────────────────────────────────────────────────────
    #  2.4 Skip / état
    # ─────────────────────────────────────────────────────────────────────

    def skip_all(self, ctx):
        """Annule toutes les étapes restantes — la cinématique se termine
        immédiatement à la prochaine frame. Nettoie aussi les effets en
        cours (caméra cinématique, boîte de dialogue ouverte, etc.)."""

        # Nettoyage des effets de l'étape en cours.
        if 0 <= self.index < len(self.steps):
            step_type, params = self._etape_actuelle()
            self._cleanup_step(step_type, params, ctx)

        # On force la fin de la cinématique.
        self.index = len(self.steps)
        self._local = {}
        self._step_initialized = False

        # Sécurité : on libère la caméra et on ferme la boîte si elle est
        # ouverte par un dialogue de cutscene.
        if ctx.camera is not None and hasattr(ctx.camera, "release_cinematic"):
            ctx.camera.release_cinematic()
        if ctx.dialogue_box is not None and getattr(ctx.dialogue_box, "actif", False):
            ctx.dialogue_box.actif = False

    def is_done(self):
        """True si toutes les étapes ont été jouées."""
        return self.index >= len(self.steps)

    def _etape_actuelle(self):
        """Renvoie (type, params) de l'étape courante. Suppose not is_done()."""
        return self.steps[self.index]

    # ─────────────────────────────────────────────────────────────────────
    #  2.5 Dispatcher principal — exécute UNE étape pendant UNE frame
    # ─────────────────────────────────────────────────────────────────────
    #
    #  Conventions :
    #       - _init_step : appelé UNE FOIS au début de l'étape.
    #       - _exec_step : appelé chaque frame, renvoie True quand fini.
    #       - _cleanup_step : appelé UNE FOIS quand l'étape se termine.
    #
    #  Pour ajouter un nouveau type d'étape, suivre l'exemple de "wait" :
    #  un bloc dans chacune des 3 méthodes ci-dessous (init/exec/cleanup),
    #  + une fabrique en bas du fichier pour la lisibilité.

    def _init_step(self, step_type, params, ctx):
        """Initialise les variables locales nécessaires à l'étape."""

        if step_type == "wait":
            # On crée un timer qui décompte vers 0.
            self._local["t_restant"] = float(params.get("duration", 1.0))

        elif step_type == "dialogue":
            # Démarre la boîte de dialogue si elle existe.
            lignes = params.get("lines", [])
            if ctx.dialogue_box is not None:
                ctx.dialogue_box.demarrer(lignes)

        elif step_type == "npc_walk":
            # Pas de state à pré-calculer : tout se fait dans _exec_step.
            # On note juste le temps écoulé, utile pour debug ou timeout.
            self._local["t_ecoule"] = 0.0

        elif step_type == "camera_focus":
            # Active la caméra cinématique si la caméra le supporte.
            cible = params.get("target", (0, 0))
            duree = params.get("duration", None)
            speed = params.get("speed",    None)
            if ctx.camera is not None and hasattr(ctx.camera, "set_cinematic_target"):
                ctx.camera.set_cinematic_target(cible, speed=speed)
            self._local["t_ecoule"] = 0.0
            self._local["duree"]    = duree   # None = blocage manuel via release

        elif step_type == "camera_release":
            # Étape instantanée : on libère la caméra dans _exec_step.
            pass

        elif step_type == "fade":
            self._local["t_ecoule"] = 0.0
            # On essaie d'utiliser un éventuel système de fondu du jeu.
            # S'il n'existe pas, l'étape devient un simple wait.
            direction = params.get("direction", "out")
            duree     = params.get("duration", 1.0)
            game = ctx.game
            if hasattr(game, "demarrer_fondu"):
                game.demarrer_fondu(direction, duree)

        elif step_type == "set_state":
            # Modifie un attribut de game (ex : game.state = "play").
            # Étape instantanée : tout le travail est dans _exec_step.
            pass

        elif step_type == "callback":
            # Appel d'une fonction libre. Étape instantanée.
            pass

        elif step_type == "shake":
            # Déclenche un screenshake : amplitude (px), duree (s).
            amplitude = float(params.get("amplitude", 6))
            duree     = float(params.get("duration",  0.3))
            if ctx.shake is not None:
                ctx.shake.trigger(amplitude=amplitude, duree=duree)
            self._local["t_restant"] = duree

        elif step_type == "play_sound":
            nom    = params.get("nom", "")
            volume = float(params.get("volume", 1.0))
            if nom:
                try:
                    from audio import sound_manager
                    sound_manager.jouer(nom, volume=volume)
                except Exception as e:
                    print(f"[Cutscene] Son '{nom}' échoué : {e}")

        elif step_type == "particles_burst":
            x       = float(params.get("x", 0))
            y       = float(params.get("y", 0))
            nb      = int(params.get("nb", 12))
            couleur = tuple(params.get("couleur", (255, 255, 200)))
            if ctx.particles is not None:
                ctx.particles.burst(x, y, nb=nb, couleur=couleur)

        elif step_type == "player_walk":
            self._local["t_ecoule"] = 0.0

        elif step_type == "npc_walk_by_name":
            # Résolution du PNJ par nom (au moment du démarrage de l'étape)
            nom_pnj = params.get("nom_pnj", "")
            self._local["t_ecoule"] = 0.0
            self._local["npc_ref"]  = _trouver_pnj(ctx, nom_pnj)

        elif step_type == "camera_focus_pnj":
            # Cible un PNJ par son nom. On résout la position MAINTENANT.
            # Si follow=True, on garde la référence pour mettre à jour la
            # cible chaque frame dans _exec_step (suit un PNJ qui marche).
            nom_pnj = params.get("nom", "")
            duree   = params.get("duration", None)
            speed   = params.get("speed",    None)
            follow  = bool(params.get("follow", False))
            pnj_ref = _trouver_pnj(ctx, nom_pnj)
            cible   = None
            if pnj_ref is not None and hasattr(pnj_ref, "rect"):
                cible = (pnj_ref.rect.centerx, pnj_ref.rect.centery)
            if cible and ctx.camera is not None and hasattr(ctx.camera, "set_cinematic_target"):
                ctx.camera.set_cinematic_target(cible, speed=speed)
            self._local["t_ecoule"] = 0.0
            self._local["duree"]    = duree
            self._local["pnj_ref"]  = pnj_ref if follow else None
            self._local["follow"]   = follow

        elif step_type == "set_player_pos":
            # Téléporte le joueur à (x, y) instantanément. Étape instantanée.
            pass

    def _exec_step(self, step_type, params, ctx, dt):
        """Avance l'étape d'une frame. Renvoie True quand elle est terminée."""

        if step_type == "wait":
            self._local["t_restant"] -= dt
            return self._local["t_restant"] <= 0.0

        if step_type == "dialogue":
            # L'étape dure tant que la boîte est active. Si elle n'existe
            # pas (mode test), on termine immédiatement pour ne pas bloquer.
            if ctx.dialogue_box is None:
                return True
            return not getattr(ctx.dialogue_box, "actif", False)

        if step_type == "npc_walk":
            # Avance un PNJ vers une cible à vitesse constante. Termine
            # quand la distance restante est négligeable.
            npc      = params.get("npc")
            cible    = params.get("target", (0, 0))
            vitesse  = float(params.get("speed", 80))
            tol      = float(params.get("tolerance", 4.0))
            self._local["t_ecoule"] += dt

            if npc is None or not hasattr(npc, "rect"):
                return True   # Rien à déplacer : on saute.

            dx = cible[0] - npc.rect.centerx
            dy = cible[1] - npc.rect.centery
            distance = math.hypot(dx, dy)            # [D11]

            if distance <= tol:
                return True

            # Pas de plus que la distance restante : évite l'overshoot.
            pas = min(vitesse * dt, distance)
            if distance > 0:
                npc.rect.centerx += int(round(dx / distance * pas))
                npc.rect.centery += int(round(dy / distance * pas))

            # Sécurité : timeout à 30 s pour ne jamais bloquer une cinématique
            # si la cible est inatteignable (par bug ou config).
            if self._local["t_ecoule"] > 30.0:
                return True
            return False

        if step_type == "camera_focus":
            # Si une durée a été fournie → l'étape est limitée dans le temps,
            # puis on libère la caméra automatiquement.
            duree = self._local.get("duree", None)
            if duree is None:
                # Étape "instantanée" : on a juste configuré la cible, et
                # camera_release viendra la libérer plus tard.
                return True
            self._local["t_ecoule"] += dt
            return self._local["t_ecoule"] >= duree

        if step_type == "camera_release":
            if ctx.camera is not None and hasattr(ctx.camera, "release_cinematic"):
                ctx.camera.release_cinematic()
            return True

        if step_type == "fade":
            duree = float(params.get("duration", 1.0))
            self._local["t_ecoule"] += dt
            return self._local["t_ecoule"] >= duree

        if step_type == "set_state":
            attr   = params.get("attr")
            valeur = params.get("value")
            if attr:
                setattr(ctx.game, attr, valeur)
            return True

        if step_type == "callback":
            fn = params.get("fn")
            if callable(fn):
                # On passe le contexte pour que la fonction puisse agir
                # sur le jeu (changer de carte, jouer un son, etc.).
                fn(ctx)
            return True

        if step_type == "shake":
            self._local["t_restant"] -= dt
            return self._local["t_restant"] <= 0.0

        if step_type == "play_sound":
            return True   # Étape instantanée

        if step_type == "particles_burst":
            return True   # Étape instantanée

        if step_type == "player_walk":
            cible    = params.get("target", (0, 0))
            vitesse  = float(params.get("speed", 100))
            tol      = float(params.get("tolerance", 6.0))
            self._local["t_ecoule"] += dt

            joueur = ctx.joueur
            if joueur is None or not hasattr(joueur, "rect"):
                return True

            dx = cible[0] - joueur.rect.centerx
            dy = cible[1] - joueur.rect.centery
            distance = math.hypot(dx, dy)

            if distance <= tol:
                return True

            pas = min(vitesse * dt, distance)
            if distance > 0:
                joueur.rect.centerx += int(round(dx / distance * pas))
                joueur.rect.centery += int(round(dy / distance * pas))

            # Sécurité : timeout 30 s
            return self._local["t_ecoule"] > 30.0

        if step_type == "camera_focus_pnj":
            # Si follow=True, on met à jour la cible caméra chaque frame
            # pour qu'elle suive le PNJ qui marche (cf. npc_walk_by_name
            # exécuté en parallèle d'une autre étape, ou enchaîné).
            if self._local.get("follow") and self._local.get("pnj_ref") is not None:
                pnj = self._local["pnj_ref"]
                if hasattr(pnj, "rect") and ctx.camera is not None \
                        and hasattr(ctx.camera, "set_cinematic_target"):
                    ctx.camera.set_cinematic_target(
                        (pnj.rect.centerx, pnj.rect.centery)
                    )
            duree = self._local.get("duree", None)
            if duree is None:
                # Pas de durée → étape instantanée, la caméra reste fixée
                # (ou suit avec follow) jusqu'à la prochaine étape camera_focus
                # ou camera_release. Permet l'ENCHAÎNEMENT entre PNJ sans
                # retour au joueur entre les deux dialogues.
                return True
            self._local["t_ecoule"] += dt
            return self._local["t_ecoule"] >= duree

        if step_type == "npc_walk_by_name":
            npc      = self._local.get("npc_ref")
            cible    = params.get("target", (0, 0))
            vitesse  = float(params.get("speed", 80))
            tol      = float(params.get("tolerance", 4.0))
            self._local["t_ecoule"] += dt

            if npc is None or not hasattr(npc, "rect"):
                return True   # PNJ introuvable : on saute

            dx = cible[0] - npc.rect.centerx
            dy = cible[1] - npc.rect.centery
            distance = math.hypot(dx, dy)
            if distance <= tol:
                return True
            pas = min(vitesse * dt, distance)
            if distance > 0:
                npc.rect.centerx += int(round(dx / distance * pas))
                npc.rect.centery += int(round(dy / distance * pas))
            return self._local["t_ecoule"] > 30.0

        if step_type == "set_player_pos":
            x = params.get("x", None)
            y = params.get("y", None)
            joueur = ctx.joueur
            if joueur is not None and hasattr(joueur, "rect") and x is not None and y is not None:
                joueur.rect.x = int(x)
                joueur.rect.y = int(y)
            return True

        # Type inconnu → on n'ose pas bloquer la cinématique : on saute.
        return True

    def _cleanup_step(self, step_type, params, ctx):
        """Nettoyage optionnel à la fin d'une étape.

        Utilisé par camera_focus(duration=…) pour libérer la caméra à la fin
        de la durée. Pour les autres étapes, ne fait rien."""

        if step_type == "camera_focus":
            duree = self._local.get("duree", None)
            if duree is not None:
                # Libération auto à la fin de la durée. Si on veut garder le
                # focus indéfiniment, ne pas passer de duration → utiliser
                # camera_release séparément.
                if ctx.camera is not None and hasattr(ctx.camera, "release_cinematic"):
                    ctx.camera.release_cinematic()


# ═════════════════════════════════════════════════════════════════════════════
#  3. FABRIQUES D'ÉTAPES — sucre syntaxique pour des scripts lisibles
# ═════════════════════════════════════════════════════════════════════════════
#
#  Chaque fabrique renvoie un tuple (type, params) prêt à être ajouté à une
#  liste passée à Cutscene(). On préfère écrire :
#       Cutscene([wait(1.0), dialogue([...]), camera_release()])
#  plutôt que :
#       Cutscene([("wait", {"duration": 1.0}), ...])
#
#  Si tu ajoutes un nouveau type d'étape dans la classe, ajoute aussi sa
#  fabrique ici pour rester cohérent.

def wait(duration):
    """Pause passive de `duration` secondes."""
    return ("wait", {"duration": float(duration)})


def dialogue(lines):
    """Affiche un dialogue. `lines` = liste de (texte, orateur) ou de strings.

    L'étape se termine quand le joueur a fait défiler toutes les lignes
    (la boîte de dialogue passe à actif=False)."""
    return ("dialogue", {"lines": list(lines)})


def npc_walk(npc, target, speed=80, tolerance=4.0):
    """Déplace `npc` jusqu'à `target` (x, y monde) à `speed` px/s.

    Suppose que `npc.rect` existe (PNJ standard ou n'importe quelle entité
    avec un rect pygame). L'étape termine à l'arrivée OU au bout de 30 s
    (sécurité anti-blocage)."""
    return ("npc_walk", {
        "npc": npc,
        "target": tuple(target),
        "speed": float(speed),
        "tolerance": float(tolerance),
    })


def camera_focus(target, duration=None, speed=None):
    """Pose la caméra sur un point fixe (x, y monde).

    duration : si None → l'étape est instantanée (la caméra reste focalisée
               jusqu'à camera_release). Si nombre → libération auto à la fin.
    speed    : facteur de lissage du déplacement (0.0 < x ≤ 1.0).
               0.1 = doux (défaut), 0.5 = nerveux, 1.0 = instantané.
               None = garde la vitesse en cours."""
    params = {"target": tuple(target)}
    if duration is not None:
        params["duration"] = float(duration)
    if speed is not None:
        params["speed"] = float(speed)
    return ("camera_focus", params)


def camera_release():
    """Rend la caméra au joueur (suivi normal)."""
    return ("camera_release", {})


def fade(direction="out", duration=1.0):
    """Lance un fondu écran. direction = "out" (vers noir) ou "in" (depuis noir).

    Délègue à game.demarrer_fondu(direction, duration) si elle existe.
    Sinon l'étape se comporte comme un wait(duration)."""
    return ("fade", {"direction": str(direction), "duration": float(duration)})


def set_state(attr, value):
    """Modifie `game.<attr> = value` (utile pour basculer game.state)."""
    return ("set_state", {"attr": attr, "value": value})


def callback(fn):
    """Appelle `fn(ctx)` une fois et passe à l'étape suivante.

    Échappatoire : si on a besoin d'une action ponctuelle qui n'a pas de
    type d'étape dédié (jouer un son, changer de carte, ajouter un item à
    l'inventaire…), on l'enveloppe dans une fonction et on la passe ici."""
    return ("callback", {"fn": fn})


def shake(amplitude=6.0, duration=0.3):
    """Tremblement de caméra. amplitude en px, duration en secondes."""
    return ("shake", {"amplitude": float(amplitude), "duration": float(duration)})


def play_sound(nom, volume=1.0):
    """Joue le son `nom` (déjà chargé via audio/sound_manager.charger)."""
    return ("play_sound", {"nom": str(nom), "volume": float(volume)})


def particles_burst(x, y, nb=12, couleur=(255, 255, 200)):
    """Émet `nb` particules à (x, y). couleur = (r, g, b)."""
    return ("particles_burst", {
        "x": float(x), "y": float(y), "nb": int(nb), "couleur": tuple(couleur),
    })


def player_walk(target, speed=100, tolerance=6.0):
    """Déplace le JOUEUR jusqu'à `target` (x, y monde) à `speed` px/s.

    Le joueur n'est pas piloté par le clavier pendant la cinématique
    (cf. game.cutscene → mouvement_bloque), donc on peut le bouger ici."""
    return ("player_walk", {
        "target": tuple(target),
        "speed": float(speed),
        "tolerance": float(tolerance),
    })


def npc_walk_by_name(nom_pnj, target, speed=80, tolerance=4.0):
    """Comme npc_walk, mais on retrouve le PNJ par son NOM (au moment du run).

    Plus pratique que npc_walk(npc=...) qui exige une référence Python : ici
    on stocke juste le nom dans le JSON et on résout au runtime."""
    return ("npc_walk_by_name", {
        "nom_pnj":   str(nom_pnj),
        "target":    tuple(target),
        "speed":     float(speed),
        "tolerance": float(tolerance),
    })


def camera_focus_pnj(nom_pnj, duration=None, speed=None, follow=False):
    """Pose la caméra sur le PNJ dont le nom est `nom_pnj`.

    Si plusieurs PNJ portent le même nom, on prend le premier trouvé.
    Si aucun n'est trouvé, l'étape ne fait rien (mais ne bloque pas).

    duration : durée explicite de l'étape (s).
               Si None → ÉTAPE INSTANTANÉE : la caméra se pose puis on passe
               directement à l'étape suivante (un dialogue par exemple). La
               caméra reste fixée jusqu'au prochain camera_focus ou
               camera_release. C'est ce qui permet d'enchaîner caméra-PNJ-A
               → dialogue-A → caméra-PNJ-B → dialogue-B sans retour au joueur.
    speed    : vitesse du lerp caméra (0.05 lent → 1.0 instantané, défaut 0.1).
    follow   : True = la caméra met à jour sa cible chaque frame pour suivre
               le PNJ s'il bouge (npc_walk_by_name)."""
    params = {"nom": str(nom_pnj)}
    if duration is not None:
        params["duration"] = float(duration)
    if speed is not None:
        params["speed"] = float(speed)
    if follow:
        params["follow"] = True
    return ("camera_focus_pnj", params)


def set_player_pos(x, y):
    """Téléporte le joueur à (x, y) instantanément (en coords monde)."""
    return ("set_player_pos", {"x": float(x), "y": float(y)})


# ═════════════════════════════════════════════════════════════════════════════
#  4. UTILITAIRES INTERNES
# ═════════════════════════════════════════════════════════════════════════════

def _trouver_position_pnj(ctx, nom_pnj):
    """Renvoie (x, y) du PNJ nommé `nom_pnj` ou None s'il n'existe pas.

    Cherche dans ctx.pnjs (peuplé par CutsceneContext depuis editeur.pnjs).
    Insensible à la casse pour la souplesse."""
    pnj = _trouver_pnj(ctx, nom_pnj)
    if pnj is None:
        return None
    r = getattr(pnj, "rect", None)
    return (r.centerx, r.centery) if r is not None else None


def _trouver_pnj(ctx, nom_pnj):
    """Renvoie l'OBJET PNJ nommé `nom_pnj` (insensible à la casse) ou None."""
    if not nom_pnj:
        return None
    cible = nom_pnj.lower().strip()
    for pnj in (ctx.pnjs or []):
        nom = getattr(pnj, "nom", "")
        if nom and nom.lower().strip() == cible:
            return pnj
    return None
