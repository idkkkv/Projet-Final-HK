# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Système de combat
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Trois fonctions, c'est tout. Mais elles évitent que les règles de combat
#  soient écrites EN DOUBLE dans player.py (pour que le joueur encaisse) et
#  dans enemy.py (pour que l'ennemi encaisse). Une seule version ici → quand
#  on change un truc, c'est changé pour tout le monde.
#
#       infliger_degats(cible, montant, source, knockback)
#           "Enlève des PV à quelqu'un."
#           Marche pour le joueur, un ennemi, un boss... peu importe.
#
#       resoudre_attaques_joueur(joueur, ennemis)
#           "Le joueur tape ? Alors qui se prend l'épée dans la tronche ?"
#
#       resoudre_contacts_ennemis(joueur, ennemis)
#           "Un ennemi colle le joueur ? Alors le joueur perd un cœur."
#
#  EXEMPLE CONCRET (ce que ça donne à l'écran)
#  -------------------------------------------
#       1) Tu cours vers un slime et tu appuies sur X (attaquer).
#       2) joueur.attacking devient True pendant ~10 frames.
#       3) resoudre_attaques_joueur() voit ça, voit que joueur.attack_rect
#          touche slime.rect → appelle infliger_degats(slime, 1, ...).
#       4) Le slime perd 1 PV, est poussé vers la droite, devient
#          invincible 0.5s pour ne pas se faire toucher 60 fois en 1 seconde.
#
#  POURQUOI getattr(cible, "...", défaut) UN PEU PARTOUT ?
#  -------------------------------------------------------
#  Parce que le joueur dit qu'il est mort avec `joueur.dead = True`,
#  alors que l'ennemi dit `ennemi.alive = False`. Deux CONVENTIONS
#  différentes (héritage du code).
#
#  Petit lexique :
#     - flag       = un booléen (True/False) qui sert à signaler un état.
#                    Exemples : dead, alive, invincible, attacking...
#                    "Lever un flag" = mettre la variable à True.
#     - convention = un choix qu'on a fait une fois et qu'on garde par
#                    cohérence. Ici, deux conventions COEXISTENT :
#                       joueur → on stocke "est-ce qu'il est MORT ?" (dead)
#                       ennemi → on stocke "est-ce qu'il est VIVANT ?" (alive)
#                    Aucune des deux n'est "mieux", mais elles sont
#                    différentes → il faut savoir gérer les deux.
#
#  getattr(obj, "nom", défaut) = "donne-moi obj.nom, et si ça n'existe pas,
#                                 renvoie `défaut` à la place" (ne plante PAS).
#
#  → On lit les DEUX flags, on accepte les DEUX conventions, et on n'a pas à
#    réécrire player.py + enemy.py.
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  core/game.py, dans _update_jeu(), à chaque frame :
#       resoudre_attaques_joueur(self.joueur, self.ennemis)
#       resoudre_contacts_ennemis(self.joueur, self.ennemis)
#  infliger_degats() est appelée INDIRECTEMENT par les deux ci-dessus.
#  Tu peux aussi l'appeler directement (ex : un piège qui blesse).
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Combien de PV un coup enlève → DEGAT_ATTAQUE_JOUEUR / DEGAT_CONTACT_ENNEMI
#     - Force du recul (knockback)   → settings.KNOCKBACK_PLAYER / _ENEMY
#     - Durée d'invincibilité        → settings.INVINCIBLE_DURATION
#     - Ajouter un coup chargé       → une nouvelle constante DEGAT_X +
#                                      une nouvelle fonction qui appelle
#                                      infliger_degats(..., DEGAT_X, ...)
#     - Reduire dgt crit             → CRIT_CHANCE_ENNEMI
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D4]   pygame.Rect    — colliderect = "ces deux rectangles se touchent ?"
#     [D22]  états          — booléens dead / alive / invincible
#
# ─────────────────────────────────────────────────────────────────────────────

from settings import (
    KNOCKBACK_PLAYER, KNOCKBACK_ENEMY,
    INVINCIBLE_DURATION,VOLUME_KILL_ENEMY
)
from audio import sound_manager
import random


# ═════════════════════════════════════════════════════════════════════════════
#  1. RÉGLAGES (combien de PV par type de coup)
# ═════════════════════════════════════════════════════════════════════════════
#
#  Tous les nombres de dégâts du jeu ICI, à un seul endroit, pour qu'on
#  puisse équilibrer sans aller fouiller 5 fichiers.

DEGAT_ATTAQUE_JOUEUR = 1   # coup d'épée du joueur → 1 PV à l'ennemi
DEGAT_CONTACT_ENNEMI = 1   # contact d'un ennemi   → 1 PV (= 1 cœur) au joueur
CRIT_CHANCE_ENNEMI = 1.0   # dgt crit (temporaire pour test)
CRIT_MULTIPLIER = 2        # 2 coeurs retirés

# ═════════════════════════════════════════════════════════════════════════════
#  2. PETITES FONCTIONS UTILES (cachent la double convention dead/alive)
# ═════════════════════════════════════════════════════════════════════════════
#
#  Le joueur dit "je suis mort" avec    joueur.dead   = True.
#  L'ennemi dit "je suis mort" avec     ennemi.alive  = False.
#  Plutôt que d'écrire ce double-test partout, on le met UNE FOIS ici.

def _est_morte(cible):
    """True si la cible est déjà morte, peu importe sa convention."""
    if getattr(cible, "dead", False):              # convention "dead" (joueur)
        return True
    if getattr(cible, "alive", True) is False:     # convention "alive" (ennemi)
        return True
    return False


def _marquer_mort(cible):
    """Note la cible comme morte, dans la convention qu'elle utilise."""
    if hasattr(cible, "dead"):
        cible.dead = True
    elif hasattr(cible, "alive"):
        cible.alive = False


# ═════════════════════════════════════════════════════════════════════════════
#  3. INFLIGER DES DÉGÂTS (la fonction de base)
# ═════════════════════════════════════════════════════════════════════════════

def infliger_degats(cible, montant, source_rect=None, knockback=0):
    """Enlève `montant` PV à `cible`. Renvoie True si le coup a porté.

    PARAMÈTRES
    ----------
    cible       : le joueur, un ennemi, un boss... bref, qui encaisse.
    montant     : combien de PV on enlève (souvent 1).
    source_rect : pygame.Rect de l'attaquant. Sert UNIQUEMENT à savoir
                  dans quel sens pousser la cible. Optionnel.
    knockback   : force du recul. 0 = pas de recul.

    EXEMPLE
    -------
        slime.rect  = Rect(100, 200, 16, 16)
        joueur.rect = Rect( 80, 200, 16, 32)
        infliger_degats(slime, 1, source_rect=joueur.rect, knockback=4)
        → slime perd 1 PV
        → slime devient invincible 0.5s
        → slime.knockback_vx = +4   (poussé vers la droite, parce que le
                                     joueur est à GAUCHE de lui)

    QUAND ÇA RENVOIE False
    ----------------------
        - cible déjà morte
        - cible en invincibilité (elle vient juste d'être touchée)
    """

    # ── Déjà morte, ou invincible ? Alors on s'arrête tout de suite ──────────
    if _est_morte(cible):
        return False
    if getattr(cible, "invincible", False):
        return False

    # ── Décrément des PV ─────────────────────────────────────────────────────
    # max(0, ...) pour ne JAMAIS descendre en négatif (sinon le HUD afficherait
    # "-1 PV", ce qui n'a aucun sens).
    if hasattr(cible, "hp"):
        cible.hp = max(0, cible.hp - montant)
        if cible.hp == 0:
            _marquer_mort(cible)
    elif hasattr(cible, "alive"):
        # Pas de compteur de PV → ennemi à 1 coup, on le tue direct.
        cible.alive = False

    # ── Frames d'invincibilité après le coup encaissé ────────────────────────
    # Sans ça, un ennemi qui te touche te ferait perdre 60 cœurs PAR SECONDE
    # (à 60 fps). Avec INVINCIBLE_DURATION = 0.5s, tu ne peux être touché
    # qu'une seule fois toutes les 0.5s → tu as le temps de réagir.
    if hasattr(cible, "invincible_timer"):
        cible.invincible        = True
        cible.invincible_timer  = INVINCIBLE_DURATION

    # ── Recul horizontal (la cible est poussée loin de l'attaquant) ──────────
    # On regarde QUI est à gauche / à droite pour savoir où pousser :
    #
    #     source           cible
    #     [SLIME] ───────→ [JOUEUR]      cible à droite → poussée à droite (+)
    #
    #     cible            source
    #     [JOUEUR] ←─────── [SLIME]      cible à gauche → poussée à gauche (-)
    #
    # En clair : la cible part toujours dans le sens OPPOSÉ à l'attaquant.
    if knockback and source_rect is not None and hasattr(cible, "knockback_vx"):
        if cible.rect.centerx < source_rect.centerx:
            cible.knockback_vx = -knockback   # cible à gauche → pousse à gauche
        else:
            cible.knockback_vx = knockback    # cible à droite → pousse à droite

    return True


# ═════════════════════════════════════════════════════════════════════════════
#  4. ATTAQUES DU JOUEUR (appelée chaque frame)
# ═════════════════════════════════════════════════════════════════════════════
def on_side_hit(ennemi):
        """Petit recul horizontal quand on touche un ennemi de côté."""
        recul_force = 300  # ajuste cette valeur selon tes préférences
        if ennemi.direction == 1: # si on regarde à droite, on recule à gauche
            ennemi.vx = -recul_force
        else: # Si on regarde à gauche, on recule à droite
            ennemi.vx = recul_force
def resoudre_attaques_joueur(joueur, ennemis):
    """Si le joueur tape, qui se prend le coup ?

    Le joueur a 2 attributs clé pendant son attaque :
        joueur.attacking     = True pendant la fenêtre active (~10 frames)
        joueur.attack_rect   = la zone touchée (un Rect devant lui)

    On parcourt tous les ennemis vivants, et on tape ceux dont le rect
    chevauche cette zone.
    """

    # Pas en train d'attaquer ? Rien à faire.
    if not joueur.attacking:
        return

    for ennemi in ennemis:
        if _est_morte(ennemi):
            continue
        # colliderect = "ces deux rectangles se chevauchent ?" (True/False)
        if ennemi.rect.colliderect(joueur.attack_rect):
            
            #si c'est le premier ennemi
            if not joueur.attack_has_hit:
                #arreter bruit pas toucher
                sound_manager.arreter("attaque")

                #bruit toucher
                sound_manager.jouer("attaque_contact", volume=VOLUME_KILL_ENEMY)

            joueur.attack_has_hit = True #pour activer le visuel et bloquer les attaques suivantes de la même animation 

            #POGO
            if joueur.attack_dir == "down":
                joueur.on_pogo_hit()
            else:
                joueur.on_side_hit() #recul pour coups normaux
                
            infliger_degats(ennemi,
                            DEGAT_ATTAQUE_JOUEUR,
                            source_rect=joueur.rect,
                            knockback=KNOCKBACK_ENEMY)
            on_side_hit(ennemi)


# ═════════════════════════════════════════════════════════════════════════════
#  5. CONTACT JOUEUR ↔ ENNEMI (appelée chaque frame)
# ═════════════════════════════════════════════════════════════════════════════

def resoudre_contacts_ennemis(joueur, ennemis, hud=None):
    """Un ennemi colle le joueur ? Alors paf, le joueur perd un cœur.

    POURQUOI UN SEUL ENNEMI PAR FRAME ?
    -----------------------------------
    Imagine 3 slimes qui te collent dessus en même temps. Si on les laissait
    TOUS frapper la même frame, tu perdrais 3 PV en 1/60ᵉ de seconde →
    quasi-mort instantanée. Pas drôle. Donc on s'arrête au PREMIER ennemi
    qui touche → tu ne perds qu'1 cœur, tu deviens invincible 0.5s, et tu
    as le temps de t'écarter.
    """

    # Joueur déjà invincible (vient d'être touché) ou mort → on ne fait rien.
    if joueur.invincible or joueur.dead:
        return

    for ennemi in ennemis:
        # Ennemi mort, ou en cooldown (vient juste de frapper) → suivant.
        if not ennemi.alive :
            if not ennemi.pieces_donnees:
                ennemi.pieces_donnees = True
                joueur.coins += ennemi.pieces_recup
                if hud:
                    hud.add_coin(ennemi.pieces_recup)
            continue
        if ennemi.attack_cooldown > 0:
            continue
        # Pas de contact physique → suivant.
        if not joueur.rect.colliderect(ennemi.rect):
            continue

        # ── Contact ! L'ennemi déclenche son coup et son cooldown ────────────
        # ennemi.hit_player() peut renvoyer False (ex : il est en train de
        # se faire toucher lui-même → il refuse de frapper).
        if ennemi.hit_player(joueur.rect):
            # joueur.hit_by_enemy() s'occupe de tout côté joueur :
            # son d'impact, animation rouge, mise à jour du HUD, son
            # propre knockback amorti.
            degats = DEGAT_CONTACT_ENNEMI
            degats_base = DEGAT_CONTACT_ENNEMI

            # chance crit + dgt crit 
            is_crit = random.random() < CRIT_CHANCE_ENNEMI

            if is_crit: 
                degats *= CRIT_MULTIPLIER
                joueur.hitted_hard = True
            else :
                joueur.hitted_normal = True
"""
            infliger_degats(
                joueur,
                degats,
                source_rect=ennemi.rect,
                knockback=KNOCKBACK_PLAYER
            )
                
            joueur.idle_anim_hurt_normal.reset()
            joueur.idle_anim_hurt_hard.reset()

        # On sort APRÈS le premier ennemi (cf. règle plus haut).
        return
"""