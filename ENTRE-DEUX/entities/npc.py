# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — PNJ (personnages non-joueurs)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Définit la classe PNJ : un personnage placé dans une carte qui peut
#  parler au joueur quand celui-ci s'approche et appuie sur [E].
#
#  Un PNJ a :
#     - un nom (affiché en flottant au-dessus de lui)
#     - un sprite (image fixe ou dossier d'animation, dans assets/images/pnj/)
#     - une liste de "conversations" — chacune = liste de répliques
#     - un mode de dialogue : "boucle_dernier" ou "restart"
#
#  Les sprites sont gérés via la classe Animation (entities/animation.py)
#  qui fait défiler les frames à intervalle régulier.
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  - world/editor.py : mode 11 (PNJs) → clic G = poser un PNJ
#                      le même mode permet d'éditer les dialogues
#  - core/game.py    : la carte les charge depuis JSON via PNJ.from_dict
#  - boucle de jeu   : si peut_interagir() et touche [E] →
#                          dialogue_box.demarrer(pnj.conversation_actuelle())
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Distance de proximité   → constante RAYON_INTERACTION (90 px)
#     - Couleur du fallback     → constante COULEUR_FALLBACK
#     - Position du nom flottant→ draw() (offset -16 px)
#     - Format de sauvegarde    → to_dict() / from_dict()
#     - Ajouter un sprite       → poser un .png dans assets/images/pnj/
#                                  ou un dossier (frames numérotées)
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D3]  blit                 — sprite, nom, indicateur [E]
#     [D4]  pygame.Rect          — hitbox du PNJ
#     [D20] Caméra               — camera.apply(self.rect) pour l'écran
#     [D33] List comprehension   — list_pnj_sprites (filtrer .png)
#     [D34] Lambda               — tri des frames par numéro
#     [D35] JSON                 — to_dict / from_dict pour les sauvegardes
#
# ─────────────────────────────────────────────────────────────────────────────

import os
import pygame
import settings
from entities.animation import Animation
from systems.hitbox_config import get_hitbox
from world.collision     import resoudre_collision


# ═════════════════════════════════════════════════════════════════════════════
#  1. CHEMINS ET HELPERS DE FICHIERS
# ═════════════════════════════════════════════════════════════════════════════

# Chemin vers le dossier des sprites PNJ (assets/images/pnj/).
# On remonte deux niveaux depuis ce fichier : entities/ → ENTRE-DEUX/ → racine.
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PNJ_DIR   = os.path.join(_BASE_DIR, "assets", "images", "pnj")

# Création du dossier si absent (évite une erreur au premier lancement).
os.makedirs(PNJ_DIR, exist_ok=True)


def list_pnj_sprites():
    """Liste les sprites disponibles dans assets/images/pnj/.

    Renvoie une liste de noms : un fichier .png/.jpg compte comme un
    sprite ; un dossier compte aussi (= sprite animé multi-frames)."""

    sprites = []
    if not os.path.isdir(PNJ_DIR):
        return sprites

    for f in sorted(os.listdir(PNJ_DIR)):
        full = os.path.join(PNJ_DIR, f)

        # Image directe → un seul sprite statique.
        if f.endswith((".png", ".jpg")):
            sprites.append(f)

        # Dossier → on vérifie qu'il contient au moins une image.
        # Sinon on l'ignore (dossier vide = pas un sprite valide).
        elif os.path.isdir(full):
            frames = [g for g in sorted(os.listdir(full))
                      if g.endswith((".png", ".jpg"))]   # [D33]
            if frames:
                sprites.append(f)

    return sprites


# ─────────────────────────────────────────────────────────────────────────
#  OBJET PARLANT (PNJ invisible avec un sprite 100% transparent)
# ─────────────────────────────────────────────────────────────────────────
#
# Usage : poser dans le monde un "objet" qui déclenche un dialogue quand
# le joueur appuie sur [E] à proximité, MAIS sans sprite visible (panneau
# invisible, voix off, journal au sol qu'on entend penser, etc.).
#
# Concrètement c'est juste un PNJ classique avec un PNG totalement
# transparent comme sprite. La fonction ci-dessous génère ce PNG à la
# bonne dimension à la demande (et le met en cache disque pour ne pas
# recréer le même fichier 50 fois).

def creer_sprite_invisible(largeur, hauteur):
    """Crée (si besoin) un PNG transparent de la taille demandée et
    renvoie son nom de fichier (à utiliser comme sprite_name de PNJ).

    Le PNG est sauvé dans assets/images/pnj/ avec un nom qui contient
    sa dimension : objet_parlant_<L>x<H>.png. Si une autre map a déjà
    demandé la même taille, on réutilise le fichier — pas de doublon.

    On enregistre AUSSI la hitbox du sprite dans hitboxes.json pour que
    le PNJ ait un rect aux dimensions du PNG (sinon il prend la taille
    par défaut 36×40 et la zone d'interaction [E] est mal placée).

    Les dimensions sont bornées (1..512) pour éviter qu'une faute de
    frappe crée un PNG énorme.
    """
    largeur = max(1, min(512, int(largeur)))
    hauteur = max(1, min(512, int(hauteur)))
    nom = f"objet_parlant_{largeur}x{hauteur}.png"
    chemin = os.path.join(PNJ_DIR, nom)
    if not os.path.exists(chemin):
        os.makedirs(PNJ_DIR, exist_ok=True)
        # SRCALPHA + remplissage (0,0,0,0) = surface 100% transparente.
        surf = pygame.Surface((largeur, hauteur), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        pygame.image.save(surf, chemin)
        # Hitbox = exactement le PNG. Sans ça PNJ tombe sur DEFAULT_HITBOX
        # 36×40 → la zone d'interaction ne couvre pas tout l'objet.
        try:
            from systems.hitbox_config import set_hitbox
            set_hitbox(nom, largeur, hauteur, 0, 0)
        except ImportError:
            # En cas d'utilisation hors-jeu (tests unitaires) on s'en passe.
            pass
    return nom


def _charger_frames_dossier(chemin_dossier):
    """Charge toutes les images d'un dossier, triées par numéro extrait du nom.

    "frame_10.png" → 10 (extraction des chiffres) — évite que frame_10 passe
    avant frame_2 dans un tri alphabétique."""
    if not os.path.isdir(chemin_dossier):
        return []
    fichiers = sorted(
        (g for g in os.listdir(chemin_dossier) if g.endswith((".png", ".jpg"))),
        key=lambda s: int("".join(filter(str.isdigit, s)) or "0"),
    )
    return [pygame.image.load(os.path.join(chemin_dossier, ff)) for ff in fichiers]


def _charger_frames_pnj(sprite_name):
    """Charge les images pour un sprite PNJ (mode rétrocompatible).

    - sprite_name est un fichier .png/.jpg → liste à 1 image
    - sprite_name est un dossier sans sous-dossiers idle/walk → toutes les
      frames du dossier (animation cyclique unique, ancien comportement)
    - Sinon → liste vide (fallback rectangle dans __init__).
    """
    chemin = os.path.join(PNJ_DIR, sprite_name)
    if os.path.isdir(chemin):
        return _charger_frames_dossier(chemin)
    if os.path.exists(chemin):
        return [pygame.image.load(chemin)]
    return []


def _charger_animations_pnj(sprite_name):
    """Charge les animations multi-états (idle / walk) d'un PNJ.

    CONVENTION :
        assets/images/pnj/<sprite_name>/idle/*.png  → animation au repos
        assets/images/pnj/<sprite_name>/walk/*.png  → animation en marche

    Renvoie un dict {"idle": [frames], "walk": [frames]}.
        - Si seul l'un des deux dossiers existe, l'autre reprend ses frames.
        - Si NI idle/ NI walk/ → renvoie {} (le PNJ retombera sur le mode
          mono-animation via _charger_frames_pnj — back-compat avec les anciens
          dossiers à frames directes ou les fichiers .png uniques)."""
    chemin_base = os.path.join(PNJ_DIR, sprite_name)
    if not os.path.isdir(chemin_base):
        return {}
    idle_dir = os.path.join(chemin_base, "idle")
    walk_dir = os.path.join(chemin_base, "walk")
    has_idle = os.path.isdir(idle_dir)
    has_walk = os.path.isdir(walk_dir)
    if not has_idle and not has_walk:
        return {}

    anims = {}
    if has_idle:
        idle_frames = _charger_frames_dossier(idle_dir)
        if idle_frames:
            anims["idle"] = idle_frames
    if has_walk:
        walk_frames = _charger_frames_dossier(walk_dir)
        if walk_frames:
            anims["walk"] = walk_frames
    # Fallback croisé : un seul des deux états dispo → on duplique
    if "idle" not in anims and "walk" in anims:
        anims["idle"] = anims["walk"]
    if "walk" not in anims and "idle" in anims:
        anims["walk"] = anims["idle"]
    return anims


# ═════════════════════════════════════════════════════════════════════════════
#  2. CLASSE PNJ
# ═════════════════════════════════════════════════════════════════════════════

class PNJ:
    """Personnage non-joueur positionné dans la scène.

    Il peut engager un dialogue quand le joueur s'approche et appuie sur [E].

    dialogues : liste de "conversations".
        Chaque conversation est une liste de lignes :  [(texte, orateur), ...]
        Le mode "boucle_dernier" (défaut) répète la dernière indéfiniment.
        Le mode "restart" recommence depuis la première après la dernière.

    sprite_name : nom du fichier ou dossier dans assets/images/pnj/
                  Si None ou introuvable → rectangle violet de fallback.
    """

    # Distance (en pixels) sous laquelle le joueur peut parler au PNJ
    # (testée séparément en X et Y → forme un carré, pas un cercle).
    RAYON_INTERACTION = 90

    # Couleur du rectangle affiché si le sprite n'existe pas / pas chargé.
    COULEUR_FALLBACK  = (180, 160, 230)

    # ═════════════════════════════════════════════════════════════════════════
    #  3. CONSTRUCTION
    # ═════════════════════════════════════════════════════════════════════════

    def __init__(self, x, y, nom, dialogues, sprite_name=None,
                 dialogue_mode="boucle_dernier", has_gravity=True,
                 is_save_point=False, events=None, dialogue_conditions=None):
        self.nom           = nom
        self.sprite_name   = sprite_name
        self._dialogues    = dialogues
        self._conv_idx     = 0

        # ── ÉVÉNEMENTS DE DIALOGUE ──────────────────────────────────────
        # Liste parallèle à `_dialogues` : pour chaque conversation, une
        # liste d'événements à déclencher quand le joueur a fini de la lire.
        # Chaque événement est un dict { "type": str, ...params }.
        # Types supportés (cf. game._appliquer_event_pnj) :
        #
        #   {"type": "skill", "value": "double_jump"}  → débloque skill_double_jump
        #         valeurs possibles : double_jump, dash, back_dodge,
        #                             wall_jump, attack, pogo
        #
        #   {"type": "luciole", "source": "anna"}      → ajoute 1 compagnon
        #         "source" est un identifiant unique pour éviter le double-don
        #
        #   {"type": "coins", "value": 50}             → +50 pièces
        #   {"type": "hp",    "value": 2}              → +2 PV (max → max_hp)
        #   {"type": "max_hp","value": 1}              → +1 PV max (et soigne)
        #   {"type": "item",  "value": "potion"}       → ajoute item à l'inventaire
        #
        # JSON exemple : un PNJ qui débloque le double saut au 2e dialogue :
        #   {
        #     "type": "pnj",
        #     "dialogues": [
        #       [["Tu sembles fatigué...", "Anna"]],
        #       [["Prends ceci, ça t'aidera.", "Anna"]]
        #     ],
        #     "events": [
        #       [],                                            // conv 0 : rien
        #       [{"type": "skill", "value": "double_jump"}]    // conv 1 : double saut
        #     ]
        #   }
        if events is None:
            self.events = [[] for _ in (dialogues or [])]
        else:
            # Padding/troncage pour rester aligné avec les dialogues.
            self.events = list(events)
            while len(self.events) < len(dialogues or []):
                self.events.append([])

        # ── CONDITIONS DE DIALOGUE (story flags) ────────────────────────
        # Liste parallèle aux dialogues : dialogue_conditions[i] est la
        # condition à remplir pour que la conv i soit "disponible". Si la
        # conv i n'est pas dispo, on saute à la suivante (ou on revient à
        # la dernière dispo en mode boucle_dernier).
        #
        # Format d'une condition : dict ou None
        #   None                          → toujours disponible (défaut)
        #   {"flag": "key"}              → dispo si game.story_flags[key]==True
        #   {"flag": "key", "value": False} → dispo si flag absent OU False
        #   {"any": ["k1","k2"]}         → dispo si AU MOINS un flag True
        #   {"all": ["k1","k2"]}         → dispo si TOUS les flags True
        #
        # Story flags : posés depuis cutscene (set_flag) ou depuis events
        # PNJ (cf. game._appliquer_event_pnj). Cf. game.story_flags.
        if dialogue_conditions is None:
            self.dialogue_conditions = [None] * len(dialogues or [])
        else:
            self.dialogue_conditions = list(dialogue_conditions)
            while len(self.dialogue_conditions) < len(dialogues or []):
                self.dialogue_conditions.append(None)
        # Marqué True dès que la DERNIÈRE conversation a été jouée. En mode
        # boucle_dernier, après ce flag, on ne renvoie plus que LA DERNIÈRE
        # LIGNE (et pas la conv entière) pour signifier "il a déjà tout dit".
        self._has_played_last = False
        # "boucle_dernier" = ne répète QUE la dernière phrase une fois tout dit ;
        # "restart"        = recommence depuis la première conv.
        self.dialogue_mode = dialogue_mode

        # ── Physique : un PNJ est une ENTITÉ comme un ennemi (gravité + ──
        # collisions avec les plateformes). Avant, il était traité comme un
        # bloc statique → on pouvait le "punaiser" en l'air, c'était bizarre.
        # has_gravity=False permet de garder un PNJ qui flotte (fantôme,
        # sprite céleste, etc.) — c'est un opt-out explicite.
        self.vx          = 0
        self.vy          = 0
        self.on_ground   = False
        self.has_gravity = has_gravity

        # Point de SAUVEGARDE : si True, l'interaction avec ce PNJ ouvre
        # le menu de sauvegarde (au lieu de jouer un dialogue). Style
        # "banc Hollow Knight" : un objet du monde où le joueur s'arrête
        # pour sauvegarder. Le bouton "Sauvegarder" du menu pause ayant
        # été retiré, c'est la SEULE façon de sauvegarder en mode histoire.
        self.is_save_point = is_save_point

        # ── Chargement des sprites (multi-états ou mono) ─────────────────────
        # Animations multi-états (idle/walk) si la convention de dossier est
        # respectée, sinon fallback à _frames + _anim mono.
        self._frames     = []        # frames du mode mono (back-compat)
        self._anim       = None      # animation mono (back-compat)
        self._anims      = {}        # {"idle": Animation, "walk": Animation}
        self._etat_anim  = "idle"    # état courant ("idle" | "walk")
        self._facing     = 1         # 1 = droite (sprite normal), -1 = gauche (flip)
        self._prev_pos   = (x, y)    # pour détecter le mouvement

        if sprite_name:
            anims_par_etat = _charger_animations_pnj(sprite_name)
            if anims_par_etat:
                # Mode multi-états : idle/walk
                for etat, frames in anims_par_etat.items():
                    self._anims[etat] = Animation(frames, img_dur=8, loop=True)
                # Pour le rect, on prend la 1re frame de idle (ou walk si pas d'idle)
                ref_frames = anims_par_etat.get("idle") or anims_par_etat.get("walk")
                self._frames = ref_frames or []
            else:
                # Mode mono (back-compat)
                self._frames = _charger_frames_pnj(sprite_name)

        if self._frames:
            if not self._anims:
                self._anim = Animation(self._frames, img_dur=8, loop=True)
            hb = get_hitbox(sprite_name) if sprite_name else None
            if hb:
                self.rect = pygame.Rect(x, y, hb["w"], hb["h"])
            else:
                img = self._frames[0]
                self.rect = pygame.Rect(x, y, img.get_width(), img.get_height())
        else:
            # Pas de frames → fallback rectangle.
            self.rect = pygame.Rect(x, y, 34, 54)

        # Police initialisée paresseusement (au premier draw).
        self._police = None

    # ═════════════════════════════════════════════════════════════════════════
    #  4. DÉTECTION DE PROXIMITÉ
    # ═════════════════════════════════════════════════════════════════════════

    def peut_interagir(self, joueur_rect):
        """True si le joueur est dans le carré RAYON_INTERACTION × RAYON_INTERACTION."""
        dist_x = abs(self.rect.centerx - joueur_rect.centerx)
        dist_y = abs(self.rect.centery - joueur_rect.centery)
        return dist_x < self.RAYON_INTERACTION and dist_y < self.RAYON_INTERACTION

    # ═════════════════════════════════════════════════════════════════════════
    #  5. DIALOGUE (gestion de la conversation courante)
    # ═════════════════════════════════════════════════════════════════════════

    def _condition_satisfaite(self, cond, story_flags):
        """True si la condition `cond` est validée par les flags fournis.

        story_flags : dict str→bool (probablement game.story_flags). Une
                      clé absente est considérée comme False."""
        if cond is None:
            return True
        if not isinstance(cond, dict):
            return True
        flags = story_flags or {}
        if "flag" in cond:
            wanted = cond.get("value", True)
            return bool(flags.get(cond["flag"], False)) == bool(wanted)
        if "any" in cond:
            return any(bool(flags.get(k, False)) for k in cond.get("any", []))
        if "all" in cond:
            return all(bool(flags.get(k, False)) for k in cond.get("all", []))
        return True

    def _index_conv_dispo(self, story_flags):
        """Renvoie l'index de la conversation à jouer maintenant.

        Avance si la conv courante n'est pas débloquée. Si plus aucune
        conv dispo derrière, on revient à la dernière dispo trouvée.
        """
        if not self._dialogues:
            return 0
        idx = self._conv_idx
        # On essaie de trouver la première conv dispo à partir de _conv_idx.
        derniere_dispo = None
        for i in range(len(self._dialogues)):
            cond = self.dialogue_conditions[i] if i < len(self.dialogue_conditions) else None
            if self._condition_satisfaite(cond, story_flags):
                derniere_dispo = i
                if i >= idx:
                    return i
        # Aucune conv dispo ≥ idx → on prend la dernière dispo trouvée.
        return derniere_dispo if derniere_dispo is not None else idx

    def conversation_actuelle(self, story_flags=None):
        """Retourne la liste de lignes de la conversation à jouer maintenant.

        N'AVANCE PAS l'index (c'est le rôle de passer_a_suivante() à la
        FERMETURE de la boîte de dialogue, pour ne pas "consommer" un
        dialogue qu'on a interrompu).

        Sémantique selon dialogue_mode :
          - boucle_dernier : tant qu'on n'a pas encore vidé toutes les conv,
                             on renvoie la conv courante en entier. Une fois
                             que _has_played_last est marqué (toute la dernière
                             conv a été jouée), on renvoie SEULEMENT la
                             dernière ligne — d'où le nom : il ne re-dit que
                             sa dernière phrase, en boucle.
          - restart        : on renvoie la conv courante en entier, et l'index
                             cycle 0→1→…→N-1→0 à chaque close de dialogue."""
        if not self._dialogues:
            return []

        if self.dialogue_mode == "boucle_dernier" and self._has_played_last:
            derniere_conv = self._dialogues[-1]
            if not derniere_conv:
                return []
            # On enveloppe la dernière ligne dans une liste à 1 élément pour
            # que la dialogue_box reçoive bien un format compatible.
            return [derniere_conv[-1]]

        # Sélection de la conv en tenant compte des conditions (story flags).
        # Si aucun story_flags fourni → comportement legacy (utilise _conv_idx).
        idx = self._conv_idx
        if story_flags is not None:
            idx = self._index_conv_dispo(story_flags)
            self._conv_idx = idx
        return self._dialogues[idx]

    def evenements_a_declencher(self):
        """Renvoie la liste d'événements à déclencher pour la conv qui
        VIENT D'ÊTRE LUE. À appeler AVANT passer_a_suivante().

        Ne touche PAS à l'état (game.py est responsable d'appliquer).
        """
        if not self.events or self._has_played_last:
            return []
        if 0 <= self._conv_idx < len(self.events):
            return list(self.events[self._conv_idx])
        return []

    def passer_a_suivante(self):
        """Avance après la fermeture d'une boîte de dialogue.

        - boucle_dernier : avance l'index ; quand on vient de jouer la dernière
                           conv, on lève le flag _has_played_last. Les talks
                           suivants ne renverront plus que la dernière ligne.
        - restart        : cycle 0 → 1 → … → 0."""
        if not self._dialogues:
            return

        if self.dialogue_mode == "restart":
            self._conv_idx = (self._conv_idx + 1) % len(self._dialogues)
            return

        # boucle_dernier
        if self._conv_idx >= len(self._dialogues) - 1:
            # On vient de jouer (ou de re-jouer) la DERNIÈRE conversation.
            # → à partir de maintenant, conversation_actuelle() ne donnera
            # plus que la dernière ligne.
            self._has_played_last = True
        else:
            self._conv_idx += 1

    def reset_dialogue(self):
        """Revient à la 1re conversation (respawn / nouvelle partie). Reset
        aussi le flag _has_played_last pour repartir de zéro."""
        self._conv_idx        = 0
        self._has_played_last = False

    # ═════════════════════════════════════════════════════════════════════════
    #  6. UPDATE (animation seulement)
    # ═════════════════════════════════════════════════════════════════════════

    def update_physique(self, dt, platforms, holes=None):
        """Applique gravité + collisions plateformes + sol/plafond du monde.

        À appeler chaque frame DEPUIS LE JEU (pas l'éditeur — sinon le PNJ
        tomberait pendant qu'on essaie de le placer).

        platforms : liste OU SpatialGrid (compatible avec query() ou itération
                    directe). Pour la liste, on itère ; pour la grille, on
                    requête les plateformes proches du PNJ.
        holes     : liste de Rect ou None. Si le PNJ est dans un trou et n'a
                    pas la permission d'y tomber, on l'expulse au sol."""
        if not self.has_gravity:
            return

        # Gravité : on accélère vers le bas.
        self.vy += settings.GRAVITY * dt
        # Cap pour éviter d'effrayer le moteur de collision (descente trop
        # rapide → on traverse les plateformes fines en une seule frame).
        if self.vy > 1200:
            self.vy = 1200

        # Application du déplacement vertical.
        self.rect.y += int(self.vy * dt)
        # Le déplacement horizontal est géré par les cinématiques via
        # rect.centerx direct (cf. cutscene.npc_walk_by_name) → on ne touche
        # pas à rect.x ici, mais on applique self.vx s'il est posé (utilisable
        # par d'éventuels scripts d'IA ultérieurs).
        if self.vx:
            self.rect.x += int(self.vx * dt)

        # ── Collisions avec les plateformes ─────────────────────────────────
        # On part du principe qu'on n'est pas au sol et on remet on_ground=True
        # uniquement si une collision avec une plateforme nous y pose.
        ancien_sol      = self.on_ground
        self.on_ground  = False

        # Récupère les plateformes pertinentes : grille spatiale (query) si
        # disponible, sinon itération brute. Cf. systems/spatial_grid.py.
        plats_test = []
        if hasattr(platforms, "query"):
            plats_test = platforms.query(self.rect)
        elif platforms is not None:
            plats_test = platforms

        for p in plats_test:
            r = getattr(p, "rect", p)   # tolère Platform OU Rect direct
            resoudre_collision(self, r)

        # ── Sol / plafond du monde ──────────────────────────────────────────
        if self.rect.bottom > settings.GROUND_Y:
            self.rect.bottom = settings.GROUND_Y
            self.vy          = 0
            self.on_ground   = True
        if self.rect.top < settings.CEILING_Y:
            self.rect.top = settings.CEILING_Y
            if self.vy < 0:
                self.vy = 0

        # ── Trous : si on est dedans et qu'on ne peut pas y tomber, on
        # remonte au sol. Pour un PNJ, on ne peut PAS tomber par défaut
        # (sinon il disparait en bas du monde sans raison).
        if holes:
            for h in holes:
                if self.rect.colliderect(h):
                    self.rect.bottom = settings.GROUND_Y
                    self.vy          = 0
                    self.on_ground   = True
                    break

        # Petit garde-fou : si on était au sol et qu'on l'est toujours
        # globalement (sol monde ou plateforme), on conserve le flag.
        if ancien_sol and not self.on_ground and self.vy == 0:
            self.on_ground = True

    def update(self):
        """Avance l'animation. Détecte le mouvement (rect a changé depuis la
        dernière frame) pour switcher idle ↔ walk et déduire le sens facing."""
        # Détection de mouvement : compare la position courante à la précédente
        cur_x, cur_y = self.rect.x, self.rect.y
        dx = cur_x - self._prev_pos[0]
        dy = cur_y - self._prev_pos[1]
        en_mouvement = (abs(dx) > 0 or abs(dy) > 0)

        # Sens (uniquement déduit du déplacement horizontal)
        if dx > 0:
            self._facing = 1
        elif dx < 0:
            self._facing = -1
        # dx == 0 → on garde le facing précédent

        self._prev_pos = (cur_x, cur_y)

        # Choix de l'animation à avancer
        if self._anims:
            etat_voulu = "walk" if en_mouvement and "walk" in self._anims else "idle"
            self._etat_anim = etat_voulu
            anim = self._anims.get(etat_voulu)
            if anim is not None:
                anim.update()
        elif self._anim:
            self._anim.update()

    # ═════════════════════════════════════════════════════════════════════════
    #  7. RENDU (sprite + nom flottant + indicateur [E])
    # ═════════════════════════════════════════════════════════════════════════

    def _init_police(self):
        """Charge la police au premier draw (pygame.font.init() doit être passé)."""
        if self._police is None:
            self._police = pygame.font.SysFont("Consolas", 12)

    def draw(self, surf, camera, joueur_rect=None):
        """Dessine le PNJ + son nom + l'indicateur [E] si le joueur est proche."""

        self._init_police()
        # camera.apply [D20] convertit le rect monde → coordonnées écran.
        rect_ecran = camera.apply(self.rect)

        # ── Sprite ou fallback ───────────────────────────────────────────────
        img = None
        if self._anims:
            anim = self._anims.get(self._etat_anim)
            if anim is not None:
                img = anim.img()
        elif self._anim and self._frames:
            img = self._anim.img()

        if img is not None:
            # Flip horizontal si le PNJ "regarde" vers la gauche.
            if self._facing == -1:
                img = pygame.transform.flip(img, True, False)
            surf.blit(img, (rect_ecran.x, rect_ecran.y))
        else:
            # Fallback : rectangle coloré + bordure blanche pour qu'on voie
            # qu'il manque un sprite (et pour pouvoir cliquer dessus en édition).
            pygame.draw.rect(surf, self.COULEUR_FALLBACK, rect_ecran)
            pygame.draw.rect(surf, (255, 255, 255), rect_ecran, 1)

        # ── Nom flottant au-dessus du personnage ─────────────────────────────
        nom_surf = self._police.render(self.nom, True, (215, 200, 255))
        surf.blit(nom_surf, (
            rect_ecran.centerx - nom_surf.get_width() // 2,
            rect_ecran.top - 16,
        ))

        # ── Indicateur [E] si le joueur est proche ───────────────────────────
        if joueur_rect and self.peut_interagir(joueur_rect):
            ind = self._police.render("[ E ]", True, (255, 215, 70))
            surf.blit(ind, (
                rect_ecran.centerx - ind.get_width() // 2,
                rect_ecran.top - 30,
            ))

    # ═════════════════════════════════════════════════════════════════════════
    #  8. SÉRIALISATION (sauvegarde JSON via l'éditeur)
    # ═════════════════════════════════════════════════════════════════════════

    def to_dict(self):
        """Convertit le PNJ en dict prêt pour le JSON [D35]."""
        return {
            "type":           "pnj",
            "x":              self.rect.x,
            "y":              self.rect.y,
            "nom":            self.nom,
            "sprite_name":    self.sprite_name,
            "dialogues":      self._dialogues,
            "dialogue_mode":  self.dialogue_mode,
            "has_gravity":    self.has_gravity,
            "is_save_point":  self.is_save_point,
            "events":         list(self.events),
            "dialogue_conditions": list(self.dialogue_conditions),
        }

    @staticmethod
    def from_dict(data):
        """Reconstruit un PNJ depuis un dict JSON.

        Méthode statique (pas de self) : on l'appelle PNJ.from_dict(data).
        Les .get() avec valeur par défaut rendent la fonction tolérante
        aux anciennes sauvegardes incomplètes (rétro-compatibilité)."""
        return PNJ(
            data["x"], data["y"],
            data.get("nom", "PNJ"),
            data.get("dialogues", []),
            sprite_name=data.get("sprite_name"),
            dialogue_mode=data.get("dialogue_mode", "boucle_dernier"),
            has_gravity=data.get("has_gravity", True),
            is_save_point=data.get("is_save_point", False),
            events=data.get("events", None),
            dialogue_conditions=data.get("dialogue_conditions", None),
        )
