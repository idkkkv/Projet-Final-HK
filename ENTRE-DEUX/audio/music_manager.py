# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Gestion de la musique de fond
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  pygame.mixer.music sait jouer UN seul morceau à la fois. Ce fichier
#  ajoute par-dessus :
#
#       - un FONDU SORTANT propre (le volume baisse petit à petit)
#       - un FONDU ENTRANT (déjà fourni par pygame, on l'utilise tel quel)
#       - un ENCHAÎNEMENT auto : "termine la musique A puis lance la B"
#       - un CACHE pour la durée des morceaux (mesurer un MP3 = lent)
#
#  Pas de classe, pas d'instance. Juste des fonctions et quelques variables
#  partagées en haut du fichier (= variables "module"). Pourquoi ? Parce
#  qu'il n'y a qu'UNE musique à la fois dans le jeu → pas besoin d'objet.
#
#  EXEMPLE CONCRET (ce que ça donne à l'écran)
#  -------------------------------------------
#       music_manager.jouer("musique/menu.mp3")
#       → la musique du menu démarre avec un petit fondu d'1.5 s.
#
#       music_manager.transition("musique/jeu.mp3", fadeout_ms=1000)
#       → la musique du menu baisse pendant 1 s puis s'éteint, ensuite
#         celle du jeu démarre avec son propre fondu entrant.
#
#       music_manager.arreter()  → fondu sortant puis silence total.
#
#  PETIT LEXIQUE
#  -------------
#     - fondu (fade)   = montée/descente progressive du volume.
#                        fade-IN  = volume 0 → max  (la musique apparaît)
#                        fade-OUT = volume max → 0  (la musique disparaît)
#
#     - callback       = "fonction à rappeler plus tard". Ici : la fonction
#                        à exécuter QUAND le fondu sortant est fini.
#                        Stockée dans _after_fade, lancée par update().
#
#     - cache          = mémoire qui retient un résultat coûteux pour ne
#                        pas le recalculer. Ici : la durée d'un mp3
#                        (mesurer = charger tout le fichier, lent).
#
#     - variable module = variable déclarée TOUT EN HAUT, hors d'une
#                        fonction. Visible par toutes les fonctions du
#                        fichier. Pour la modifier dans une fonction,
#                        il faut le mot-clé `global`.
#
#     - lambda         = mini-fonction sans nom. Ex : `lambda: f(x)` =
#                        "une fonction qui, quand on l'appelle, fait f(x)".
#                        Pratique pour stocker un appel à exécuter plus tard.
#
#  COMMENT FONCTIONNE LE FONDU SORTANT ?
#  -------------------------------------
#  pygame fournit fadein nativement, mais PAS un fadeout proprement
#  enchaînable. On fait donc le nôtre à la main :
#
#       1) On se règle un _fade_speed négatif (ex: -0.5 = perdre 0.5 de
#          volume par seconde).
#       2) Chaque frame, update(dt) ajoute _fade_speed*dt au volume.
#       3) Quand le volume atteint 0 → fondu fini → on lance _after_fade
#          (le callback enregistré, ex: "lance la musique suivante").
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  core/game.py :
#       music_manager.jouer(...)        au démarrage / changement de map
#       music_manager.transition(...)   pour passer de la musique A à B
#       music_manager.update(dt)        chaque frame (sinon pas de fadeout)
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Volume par défaut          → arg `volume=` des fonctions
#     - Durée des fondus           → args `fadein_ms=` / `fadeout_ms=`
#     - Vitesse max du fondu       → constante 0.05 dans update()
#                                    (clamp anti-saut quand la fenêtre
#                                    perd le focus)
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D10] dt                  — vitesse × dt = changement par seconde
#     [D13] interpolation       — volume qui glisse de A vers B
#     [D22] états               — _fade_speed encode 3 états (0 / + / -)
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame


# ═════════════════════════════════════════════════════════════════════════════
#  1. ÉTAT GLOBAL DU MODULE (variables partagées par toutes les fonctions)
# ═════════════════════════════════════════════════════════════════════════════
#
#  Ces variables sont déclarées ICI pour être visibles partout dans le
#  fichier. Une fonction qui veut les MODIFIER doit le déclarer avec
#  `global` (sinon Python crée une variable LOCALE du même nom et la
#  variable du module n'est pas touchée).

_current        = None    # chemin du fichier en cours de lecture (ou None)
_target_volume  = 0.5     # volume qu'on VEUT atteindre (0.0 = muet, 1.0 = max)
_fade_speed     = 0       # vitesse du fondu :  0 = aucun
                          #                     > 0 = fade-IN  (volume monte)
                          #                     < 0 = fade-OUT (volume descend)
_after_fade     = None    # callback à exécuter une fois le fondu sortant fini

# Cache des durées : mesurer un mp3 = charger tout le fichier (lent).
# On le fait UNE fois par chemin, on retient le résultat dans ce dict.
#   { "musique/menu.mp3": 124.5,  "musique/jeu.mp3": 187.2,  ... }
_duration_cache = {}


# ═════════════════════════════════════════════════════════════════════════════
#  2. JOUER UNE MUSIQUE (fade-in natif pygame)
# ═════════════════════════════════════════════════════════════════════════════

def jouer(chemin, boucle=-1, volume=0.5, fadein_ms=1500):
    """Lance une musique avec un fondu entrant.

    chemin     : chemin du fichier audio (.mp3, .ogg...)
    boucle     : -1 = boucle infinie (cas par défaut), 0 = joue une seule fois
    volume     : volume cible, entre 0.0 (muet) et 1.0 (max)
    fadein_ms  : durée du fondu entrant en MILLISECONDES (1500 = 1.5 s)

    Si la musique demandée joue DÉJÀ → on ne refait rien (sinon ça la
    redémarrerait au début à chaque appel, super désagréable).
    """
    global _current, _target_volume, _fade_speed, _after_fade

    # Déjà en train de jouer ce morceau-là ? On ne touche à rien.
    if chemin == _current and pygame.mixer.music.get_busy():
        return

    try:
        # load() = "prépare ce fichier audio" (ne joue pas encore)
        pygame.mixer.music.load(chemin)
        _target_volume = volume
        _fade_speed    = 0      # on annule un éventuel fondu en cours
        _after_fade    = None
        pygame.mixer.music.set_volume(volume)
        # play(loops, start, fade_ms) — "fade_ms" = fondu entrant natif pygame
        pygame.mixer.music.play(boucle, 0.0, max(0, fadein_ms))
        _current = chemin
    except Exception as e:
        # Fichier manquant, format non supporté... on log et on continue
        # silencieusement (le jeu doit pouvoir tourner sans musique).
        print(f"[music] Erreur jouer({chemin}): {e}")
        _current = None


# ═════════════════════════════════════════════════════════════════════════════
#  3. TRANSITION ENTRE DEUX MUSIQUES (fadeout puis nouvelle musique)
# ═════════════════════════════════════════════════════════════════════════════

def transition(chemin, boucle=-1, volume=0.5, fadeout_ms=1000, fadein_ms=1500):
    """Fait un fondu sortant sur la musique actuelle, puis lance la nouvelle.

    DÉROULEMENT (sur ~2.5 s avec les valeurs par défaut) :
       t = 0.0 s   on commence à baisser le volume de la musique en cours
       t = 1.0 s   musique en cours = silence → callback déclenché
       t = 1.0 s   nouvelle musique démarre avec son propre fade-in
       t = 2.5 s   nouvelle musique à plein volume

    CAS SPÉCIAL : on demande la MÊME musique que celle qui joue déjà
       → si elle est en train de fader-out, on ANNULE le fadeout et
         on remet le volume cible (sinon on aurait une musique qui
         s'éteint pour rien).
       → sinon on ne touche à rien.
    """
    global _fade_speed, _after_fade, _target_volume

    # ── Cas spécial : on redemande la musique en cours ───────────────────────
    if chemin == _current and pygame.mixer.music.get_busy():
        # Si elle est en train de fader-out, on annule.
        if _fade_speed < 0:
            _after_fade    = None
            _fade_speed    = 0
            _target_volume = volume
            pygame.mixer.music.set_volume(volume)
        return

    # ── Cas normal : il y a une musique → fadeout puis callback ──────────────
    if _current and pygame.mixer.music.get_busy():
        cur_vol = pygame.mixer.music.get_volume()
        _target_volume = 0.0
        # vitesse = -volume/durée → quand fini en `fadeout_ms` ms, vol = 0.
        # max(0.001, ...) pour éviter une division par zéro si on passe
        # fadeout_ms = 0 par erreur.
        _fade_speed    = -cur_vol / max(0.001, fadeout_ms / 1000)
        # lambda = "fonction sans nom à appeler plus tard". Quand le fondu
        # sera fini, update() exécutera ceci → la nouvelle musique démarre.
        _after_fade    = lambda: jouer(chemin, boucle, volume, fadein_ms)
    else:
        # Pas de musique en cours → on lance directement la nouvelle.
        jouer(chemin, boucle, volume, fadein_ms)


# ═════════════════════════════════════════════════════════════════════════════
#  4. ARRÊTER LA MUSIQUE (avec ou sans fondu)
# ═════════════════════════════════════════════════════════════════════════════

def arreter(fadeout_ms=800):
    """Arrête la musique, avec un fondu sortant si fadeout_ms > 0."""
    global _current, _target_volume, _fade_speed, _after_fade

    if fadeout_ms > 0 and pygame.mixer.music.get_busy():
        # Mode "doux" : on programme un fadeout, callback = arrêt sec.
        vol = pygame.mixer.music.get_volume()
        _target_volume = 0.0
        _fade_speed    = -vol / max(0.001, fadeout_ms / 1000)
        _after_fade    = lambda: _stop_immediate()
    else:
        # Mode "brutal" : silence immédiat.
        _stop_immediate()


def _stop_immediate():
    """Arrêt sec sans fondu. Préfixé par _ = "privé, ne pas appeler de l'extérieur"."""
    global _current, _fade_speed, _after_fade
    pygame.mixer.music.stop()
    _current     = None
    _fade_speed  = 0
    _after_fade  = None


# ═════════════════════════════════════════════════════════════════════════════
#  5. INFOS SUR LA MUSIQUE EN COURS
# ═════════════════════════════════════════════════════════════════════════════

def get_duree():
    """Renvoie la durée TOTALE du morceau chargé, en secondes (ou 0).

    POURQUOI UN CACHE ?
    -------------------
    pygame ne sait pas mesurer la durée de pygame.mixer.music. Il faut
    re-créer un pygame.mixer.Sound (ce qui charge tout le fichier en
    mémoire), lire sa longueur, puis le jeter. Pour un mp3 de 3 minutes,
    ça prend plusieurs centaines de millisecondes — donc on retient le
    résultat dans `_duration_cache` pour ne le faire qu'une seule fois
    par fichier.
    """
    if not _current:
        return 0

    # Déjà calculé pour ce chemin → on relit la valeur en cache.
    if _current in _duration_cache:
        return _duration_cache[_current]

    # Pas en cache → on charge, on mesure, on retient.
    try:
        s = pygame.mixer.Sound(_current)
        dur = s.get_length()
        del s   # libère la mémoire du fichier (on n'a besoin que de la durée)
        _duration_cache[_current] = dur
        return dur
    except Exception:
        return 0


def get_pos_s():
    """Position actuelle dans le morceau, en secondes (0 si rien ne joue)."""
    if pygame.mixer.music.get_busy():
        # get_pos() renvoie des MILLISECONDES → /1000 pour avoir des secondes.
        return pygame.mixer.music.get_pos() / 1000
    return 0


def volume(v):
    """Règle le volume directement, sans fondu. v entre 0.0 et 1.0."""
    global _target_volume
    # max/min = clamp pour rester dans [0.0, 1.0] même si on passe -5 ou 99.
    _target_volume = max(0.0, min(1.0, v))
    pygame.mixer.music.set_volume(_target_volume)


# ═════════════════════════════════════════════════════════════════════════════
#  6. UPDATE — fait avancer le fondu sortant (à appeler chaque frame)
# ═════════════════════════════════════════════════════════════════════════════

def update(dt):
    """Avance le fondu sortant manuel. À appeler chaque frame depuis game.py.

    dt = temps écoulé depuis la frame précédente, en secondes [D10].
         Multiplier la vitesse par dt → on bouge "X par seconde" peu
         importe le framerate (60 fps ou 144 fps, même résultat).

    POURQUOI le clamp dt = min(dt, 0.05) ?
    --------------------------------------
    Si la fenêtre perd le focus / un breakpoint stoppe le jeu pendant 5 s,
    le dt suivant fait 5.0 → vol += -0.5 * 5.0 = -2.5 → SAUT brutal de
    -2.5 unités d'un coup. Avec le clamp à 0.05 s, le pire qui peut
    arriver = un tout petit saut, imperceptible.
    """
    global _fade_speed, _after_fade, _target_volume

    # Pas de fondu en cours ? Rien à faire.
    if _fade_speed == 0:
        return

    # Anti-saut quand la fenêtre perd le focus (cf. docstring).
    dt = min(dt, 0.05)

    # On lit le volume actuel et on le décale d'un cran.
    vol = pygame.mixer.music.get_volume()
    vol += _fade_speed * dt

    # ── A-t-on atteint le volume cible ? ─────────────────────────────────────
    # Cas fade-IN (_fade_speed > 0) : on monte → terminé quand vol >= cible.
    if _fade_speed > 0 and vol >= _target_volume:
        vol = _target_volume
        _fade_speed = 0

    # Cas fade-OUT (_fade_speed < 0) : on descend → terminé quand vol <= cible.
    elif _fade_speed < 0 and vol <= _target_volume:
        vol = max(0.0, _target_volume)
        _fade_speed = 0
        # ── Fondu sortant FINI → on déclenche le callback ────────────────────
        # Ex: dans transition() on a stocké lambda: jouer(nouvelle_musique).
        # Maintenant qu'on est silencieux, on appelle ce lambda → la
        # nouvelle musique démarre.
        if _after_fade:
            cb = _after_fade
            _after_fade = None     # on efface AVANT d'appeler (évite récursion
                                   # infinie si le callback re-déclenche un
                                   # fondu).
            cb()
            return

    # On applique le nouveau volume (clampé entre 0 et 1 par sécurité).
    pygame.mixer.music.set_volume(max(0.0, min(1.0, vol)))
