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
from entities.animation import Animation
from systems.hitbox_config import get_hitbox


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
                 dialogue_mode="boucle_dernier"):
        self.nom           = nom
        self.sprite_name   = sprite_name
        self._dialogues    = dialogues
        self._conv_idx     = 0
        # "boucle_dernier" = répète la dernière phrase ; "restart" = recommence.
        self.dialogue_mode = dialogue_mode

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

    def conversation_actuelle(self):
        """Retourne la liste de lignes de la conversation à jouer maintenant.

        N'AVANCE PAS l'index : c'est le rôle de passer_a_suivante(), appelée
        par game.py UNE FOIS que le joueur a réellement fini de lire le
        dialogue (boîte fermée).

        Pourquoi ? Bug historique : on avançait l'index dès l'OUVERTURE de
        la boîte. Si le joueur s'éloignait sans finir, ou pressait E par
        erreur, la conversation suivante prenait sa place lors du prochain
        E — il ne voyait jamais réellement les premiers dialogues. Maintenant
        c'est la fin effective du dialogue qui décide d'avancer."""

        if not self._dialogues:
            return []
        return self._dialogues[self._conv_idx]

    def passer_a_suivante(self):
        """Passe à la conversation suivante. À appeler quand le joueur a
        FINI de lire le dialogue actuel (boîte fermée).

        Comportement selon dialogue_mode :
          - boucle_dernier : la dernière conversation se répète indéfiniment.
          - restart        : après la dernière, on revient à la première."""

        if not self._dialogues:
            return
        if self.dialogue_mode == "restart":
            # Modulo → boucle propre : 0 → 1 → 2 → 0 → 1 → ...
            self._conv_idx = (self._conv_idx + 1) % len(self._dialogues)
        else:
            # boucle_dernier — on bloque sur l'index de la dernière conversation.
            self._conv_idx = min(self._conv_idx + 1, len(self._dialogues) - 1)

    def reset_dialogue(self):
        """Revient à la première conversation (utilisé au respawn / nouvelle partie)."""
        self._conv_idx = 0

    # ═════════════════════════════════════════════════════════════════════════
    #  6. UPDATE (animation seulement)
    # ═════════════════════════════════════════════════════════════════════════

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
            "type":          "pnj",
            "x":             self.rect.x,
            "y":             self.rect.y,
            "nom":           self.nom,
            "sprite_name":   self.sprite_name,
            "dialogues":     self._dialogues,
            "dialogue_mode": self.dialogue_mode,
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
        )
