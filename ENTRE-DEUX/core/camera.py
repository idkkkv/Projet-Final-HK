# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Caméra
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Le monde du jeu est BEAUCOUP plus grand que la fenêtre. La caméra, c'est
#  la "fenêtre" qui décide CE QU'ON VOIT à l'écran à un instant donné.
#  Concrètement, elle stocke deux nombres :
#
#       offset_x = de combien on a "scrollé" vers la droite dans le monde
#       offset_y = de combien on a "scrollé" vers le bas
#
#  Pour dessiner un objet à l'écran :
#       écran_x = monde_x - offset_x
#       écran_y = monde_y - offset_y
#
#  Si le joueur est à monde_x = 1500 et offset_x = 1200, on le dessine à
#  écran_x = 300. Tout le reste suit la même règle.
#
#  EXEMPLE CONCRET (le joueur court vers la droite)
#  ------------------------------------------------
#       Frame N    : joueur à monde_x = 800,  offset_x = 600,  → écran_x = 200
#       Frame N+1  : joueur à monde_x = 805,  offset_x = 600.5,→ écran_x ≈ 204.5
#                    (le joueur n'est PAS recentré d'un coup : la caméra le
#                    rattrape progressivement avec le facteur 0.1, cf. "lerp")
#       Plus tard  : joueur à monde_x = 1200, offset_x ≈ 1000, → écran_x ≈ 200
#                    (la caméra a lentement glissé pour le suivre)
#
#  Petit lexique :
#     - caméra      = la "fenêtre" mobile par laquelle on regarde le monde.
#                     Elle ne dessine rien elle-même : elle DIT juste où
#                     dessiner les objets sur l'écran.
#     - offset      = "décalage" — la position du coin haut-gauche de la
#                     caméra dans le monde.
#     - lerp        = "linear interpolation" — formule pour avancer
#                     PROGRESSIVEMENT vers une cible :
#                          val += (cible - val) * 0.1
#                     À chaque frame, on couvre 10 % du chemin restant.
#                     Plus le facteur est grand, plus c'est sec / nerveux.
#     - clamp       = "borner" — forcer un nombre à rester dans un intervalle
#                     [min, max]. Ici on évite que la caméra sorte du monde.
#     - shake offset= petit décalage aléatoire que la caméra ADDITIONNE pour
#                     simuler un tremblement. Cf. systems/juice.py.
#     - cache       = on garde la taille de l'écran (_sw, _sh) plutôt que de
#                     la redemander à pygame à chaque appel d'apply() ou
#                     is_visible() (60 fois par frame). Économie discrète.
#     - drag / pan  = "saisir et faire glisser". Dans l'éditeur, le clic
#                     molette + déplacement souris fait défiler la vue.
#     - culling     = ne PAS dessiner ce qui est hors écran. is_visible()
#                     répond à "ce rectangle est-il dans la fenêtre ?".
#
#  POURQUOI LE FACTEUR 0.1 (CAMERA QUI RATTRAPE PROGRESSIVEMENT) ?
#  ---------------------------------------------------------------
#  Si on faisait offset_x = target_x direct, la caméra serait COLLÉE au
#  joueur → quand il fait un pas, l'écran fait un pas. Désorientant.
#  Avec * 0.1, la caméra glisse en douceur vers sa cible : ça donne une
#  impression cinématique et ça évite le "mal des transports XD" à l'écran.
#
#  POURQUOI y_offset = 150 ?
#  -------------------------
#  On vise 150 px AU-DESSUS du joueur, pas pile sur lui. Comme ça, on voit
#  davantage ce qui est sous le joueur (sol, ennemis qui arrivent), au lieu
#  d'avoir le ciel inutile en haut de l'écran.
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  core/game.py crée la caméra, l'update chaque frame, et l'utilise pour
#  TOUT ce qui se dessine dans le monde (joueur, ennemis, particules, etc.).
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Caméra plus / moins nerveuse        → facteur 0.1 dans update()
#     - Voir plus haut / plus bas du joueur → self.y_offset
#     - Bornes du monde                     → arguments scene_width/height
#     - Vitesse du scroll molette en éditeur→ constante 60 dans pan_scroll()
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D4]   pygame.Rect    — apply() renvoie un Rect translaté
#     [D8]   dt             — pas utilisé ici (le 0.1 est par frame, pas par sec)
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame
import settings
from settings import WIDTH, HEIGHT


class Camera:
    def __init__(self, scene_width, scene_height):
        # Position de la caméra dans le monde (coin haut-gauche).
        self.offset_x     = 0
        self.offset_y     = 0

        # Bornes du monde : la caméra ne sortira pas au-delà.
        self.scene_width  = scene_width
        self.scene_height = scene_height

        # Décalage vertical : on regarde 150 px AU-DESSUS du joueur (cf. header).
        self.y_offset     = 150

        # Cache de la taille écran. On l'actualise dans update() une fois par
        # frame. Évite get_surface() dans apply() / is_visible() qui sont
        # appelés des centaines de fois par frame.
        self._sw = WIDTH
        self._sh = HEIGHT

        # ── Caméra libre (mode éditeur) ──────────────────────────────────────
        # En mode libre, la caméra ne suit plus le joueur : on la déplace
        # à la souris (drag avec clic molette + scroll).
        self.free_mode    = False
        self._drag_active = False
        self._drag_prev   = None
        self.zoom         = 1.0  # réservé pour plus tard, pas utilisé pour l'instant

        # Screen-shake : offset additif que la caméra applique dans apply().
        # Mis à jour de l'extérieur par game.py (qui pilote le ScreenShake
        # de systems/juice.py).
        self.shake_offset = (0, 0)

        # ── Mode cinématique ──────────────────────────────────────────────────
        # Pendant une cutscene, la caméra peut viser un POINT FIXE (centre du
        # cadre voulu, en coords monde) au lieu de suivre le joueur.
        # Activé via set_cinematic_target((x, y)), désactivé par release_cinematic().
        # Le lissage utilise le MÊME facteur 0.1 que pour le suivi joueur,
        # donc transition douce dans les 2! sens.
        self._cinematic_active = False
        self._cinematic_target = (0, 0)   # (x, y) monde — à CENTRER à l'écran
        # Facteur de lerp en cinématique (0.0 < x ≤ 1.0).
        # 0.1 = défaut, doux. 0.5 = nerveux. 1.0 = collé direct (pas de lissage).
        # Modifié par cutscene "camera_focus" via param "speed".
        self._cinematic_speed     = 0.1
        # Quand on libère la caméra (camera_release), on garde un instant la
        # vitesse cinématique pour que le RETOUR vers le joueur soit aussi
        # progressif que l'aller. Désactivé automatiquement quand la caméra
        # arrive proche du joueur.
        self._cinematic_returning = False

    # ─────────────────────────────────────────────────────────────────────────
    #  MISE À JOUR (chaque frame, en mode "suit le joueur")
    # ─────────────────────────────────────────────────────────────────────────

    def snap_to(self, target_rect):
        """Centre la caméra INSTANTANÉMENT sur target_rect (pas de lerp).

        À appeler quand on téléporte le joueur (chargement de sauvegarde,
        nouvelle partie, changement de map). Sans ça, la caméra reste à
        sa position précédente et "rattrape" le joueur en quelques frames
        avec le lerp normal — l'utilisateur voit la map défiler.
        """
        # Cache de taille écran : update() le rafraîchit, mais ici on est
        # appelé en dehors de update() (au chargement). On le pose à la
        # main pour que le calcul de cible soit cohérent.
        surf = pygame.display.get_surface()
        if surf:
            self._sw, self._sh = surf.get_size()

        # Même logique que update() mais f=1 (saut direct, pas de lerp).
        target_x = target_rect.centerx - self._sw // 2
        target_y = target_rect.centery - self._sh // 2 + self.y_offset
        self.offset_x = target_x
        self.offset_y = target_y

        # Clamp aux bornes du monde (réutilise la même logique que update).
        largeur_monde = self.scene_width - settings.SCENE_LEFT
        if largeur_monde < self._sw:
            self.offset_x = settings.SCENE_LEFT - (self._sw - largeur_monde) // 2
        else:
            self.offset_x = max(settings.SCENE_LEFT,
                                min(self.offset_x,
                                    self.scene_width - self._sw))
        max_y = settings.GROUND_Y + 40 - self._sh
        min_y = settings.CEILING_Y - self._sh // 2
        self.offset_y = max(min_y, min(self.offset_y, max(0, max_y)))

    # Vitesse du lerp caméra. Plus c'est grand, plus la caméra rattrape
    # vite le joueur. ~8 → 90 % rattrapé en ~0.3 s. Indépendant du FPS
    # grâce à la formule (1 - exp(-rate*dt)).
    _LERP_RATE = 8.0

    def _facteur_lerp(self, dt, rate=None):
        """Convertit un (rate, dt) en facteur de lerp dt-indépendant.

        AVANT (factor=0.1 fixe) : à 80 fps caméra réactive, à 30 fps elle
        traînait → mouvement irrégulier perçu comme du tremblement quand
        le FPS variait. Maintenant, peu importe le FPS, le rattrapage
        prend le même temps RÉEL.
        """
        import math
        r = self._LERP_RATE if rate is None else rate
        # dt borné pour éviter les sauts énormes (cf. cap dt = 0.05 dans game.py)
        return 1.0 - math.exp(-r * max(0.0, min(0.05, dt)))

    def update(self, target_rect, dt=1/60):
        """Recentre la caméra (en douceur) sur target_rect.
        En free_mode, ne fait que rafraîchir le cache taille écran."""

        # Cache taille écran (utilisé par apply, is_visible — gain de perf).
        surf = pygame.display.get_surface()
        if surf:
            self._sw, self._sh = surf.get_size()

        # ── Adaptation au ZOOM caméra ───────────────────────────────────────
        # Quand zoom != 1.0, le rendu du monde se fait sur un BUFFER plus
        # petit (taille = écran // zoom_entier) qui sera scalé vers l'écran
        # à la fin du frame (cf. _dessiner_monde dans game.py). Pour que le
        # joueur reste centré dans CE buffer, la caméra doit raisonner sur
        # la "vue logique" (= ce qui est réellement dessiné), pas sur la
        # résolution écran finale. Sans cette ligne, le joueur apparaît
        # décentré quand on zoome.
        #
        # PIXEL ART CRISP — On arrondit la valeur de zoom à l'ENTIER le plus
        # proche. Raison : pygame.transform.scale() fait du nearest-neighbor ;
        # avec un zoom fractionnaire (ex. 1.5×), certains pixels source
        # deviennent 1 px à l'écran et d'autres 2 px → pixel art flou /
        # irrégulier. Avec un facteur ENTIER, chaque pixel source correspond
        # à exactement N pixels d'écran → sprite parfaitement net.
        # La valeur "zoom" peut rester un float côté éditeur (UI/save) ;
        # seul le rendu utilise l'entier.
        z = self.zoom if (self.zoom and self.zoom > 0) else 1.0
        z_int = max(1, int(round(z)))
        if z_int != 1:
            self._sw = max(1, self._sw // z_int)
            self._sh = max(1, self._sh // z_int)

        if self.free_mode:
            return                           # la caméra est pilotée à la souris

        # ── Mode cinématique : la cible n'est PAS le joueur, mais un point fixe ─
        # Priorité sur le suivi joueur. On centre exactement le point demandé
        # (sans y_offset : en cinématique on veut cadrer pile sur la cible).
        if self._cinematic_active:
            cx, cy = self._cinematic_target
            target_x = cx - self._sw // 2
            target_y = cy - self._sh // 2
            # On convertit la vitesse cinématique (qui était un facteur
            # par frame) en taux par seconde pour rester dt-indépendant.
            # cinematic_speed = 0.05 → rate ~3.1 ; = 0.1 → rate ~6.3
            import math
            cs = max(0.001, min(1.0, self._cinematic_speed))
            rate_cine = -math.log(1.0 - cs) * 60.0  # éq. comportement à 60 fps
            f = self._facteur_lerp(dt, rate=rate_cine)
            self.offset_x += (target_x - self.offset_x) * f
            self.offset_y += (target_y - self.offset_y) * f
            # Clamp identique au mode joueur (cf. plus bas) : si le monde
            # tient dans l'écran, on le centre ; sinon on clamp aux bords.
            max_y = settings.GROUND_Y + 40 - self._sh
            min_y = settings.CEILING_Y - 40 - self._sh // 2
            largeur_monde = self.scene_width - settings.SCENE_LEFT
            if largeur_monde <= self._sw:
                self.offset_x = settings.SCENE_LEFT - (self._sw - largeur_monde) // 2
            else:
                self.offset_x = max(settings.SCENE_LEFT,
                                    min(self.offset_x, self.scene_width - self._sw))
            self.offset_y = max(min_y, min(self.offset_y, max(0, max_y)))
            return

        # ── Phase de retour cinématique ──────────────────────────────────────
        # Pendant cinematic_active, la caméra centrait PILE sur le PNJ (sans
        # y_offset). Si on rebascule direct au mode joueur normal (qui a un
        # y_offset de 150 px), le target saute de 150 px en Y et la trajectoire
        # de retour n'est plus le miroir de l'aller (effet "bas puis droite"
        # désagréable). Pour avoir un retour symétrique, on cible le centre
        # EXACT du joueur (sans y_offset) pendant la phase de retour. Le
        # y_offset est réintroduit ensuite, en douceur, par le lerp normal.
        if self._cinematic_returning:
            target_x = target_rect.centerx - self._sw // 2
            target_y = target_rect.centery - self._sh // 2
            import math
            cs = max(0.001, min(1.0, self._cinematic_speed))
            rate_ret = -math.log(1.0 - cs) * 60.0
            f = self._facteur_lerp(dt, rate=rate_ret)
            # Sortie de la phase quand on est très proche du centre joueur.
            if abs(target_x - self.offset_x) < 8 and abs(target_y - self.offset_y) < 8:
                self._cinematic_returning = False
        else:
            # Mode joueur normal : on regarde 150 px AU-DESSUS du joueur.
            target_x = target_rect.centerx - self._sw // 2
            target_y = target_rect.centery - self._sh // 2 + self.y_offset
            # Lerp dt-aware → vitesse de rattrapage CONSTANTE en temps réel
            # quel que soit le framerate (avant : factor=0.1 par frame,
            # donc plus le fps variait, plus la caméra paraissait trembler).
            f = self._facteur_lerp(dt)
        self.offset_x += (target_x - self.offset_x) * f
        self.offset_y += (target_y - self.offset_y) * f

        # ── Clamp : on empêche la caméra de sortir du monde ──────────────────
        max_y = settings.GROUND_Y + 40 - self._sh
        min_y = settings.CEILING_Y - self._sh // 2

        # ── Cadrage horizontal ──────────────────────────────────────────────
        # Si le monde est PLUS PETIT que l'écran, on le centre dans la fenêtre
        # (le joueur ne fait plus défiler la caméra → on a des marges noires
        # à gauche et à droite, comme une scène de théâtre). Sinon, on clamp
        # entre SCENE_LEFT et SCENE_WIDTH - sw (on ne sort pas du monde).
        largeur_monde = self.scene_width - settings.SCENE_LEFT
        if largeur_monde <= self._sw:
            # Centre le monde : offset_x tel que SCENE_LEFT s'affiche au centre
            # avec les marges symétriques de chaque côté.
            self.offset_x = settings.SCENE_LEFT - (self._sw - largeur_monde) // 2
        else:
            self.offset_x = max(settings.SCENE_LEFT,
                                min(self.offset_x, self.scene_width - self._sw))
        # ── Cadrage vertical ────────────────────────────────────────────────
        # Le y_offset réglé en éditeur (PageUp/PageDown) DOIT toujours avoir
        # un effet visible sur la caméra.
        #
        # Ancien comportement (bug) : la clamp `max(0, max_y)` saturait la
        # position quand le joueur était près du sol. Avec le zoom le buffer
        # devient plus petit, donc max_y est positif et grand. Le target_y
        # demandé (qui inclut y_offset=150) dépassait max_y → tout
        # réglage ±20 px était avalé par la clamp. D'où le constat utilisateur :
        # "avec le zoom, je ne peux plus remonter/redescendre la caméra".
        #
        # Correctif : quand le monde est PLUS GRAND que la vue (cas normal,
        # surtout en mode zoom), on laisse offset_y rejoindre target_y
        # (y_offset a toujours un effet visible). Quand le monde tient
        # dans la vue (petites maps natives), on garde l'ancienne clamp
        # pour ne pas afficher une bande noire sous le sol.
        vue_plus_grande_que_monde = (
            max_y < 0 or (settings.GROUND_Y + 40 - settings.CEILING_Y) <= self._sh
        )
        if vue_plus_grande_que_monde:
            # Monde plus petit que la vue : on garde le comportement d'origine.
            self.offset_y = max(min_y, min(self.offset_y, max(0, max_y)))
        else:
            # Monde plus grand que la vue : on élargit la clamp dans la
            # direction demandée par y_offset → target_y toujours atteignable.
            effective_max = max(max_y, target_y)
            effective_min = min(min_y, target_y)
            self.offset_y = max(effective_min, min(self.offset_y, effective_max))

    # ─────────────────────────────────────────────────────────────────────────
    #  CAMÉRA LIBRE (mode éditeur uniquement — clic molette pour pan)
    # ─────────────────────────────────────────────────────────────────────────

    def start_drag(self, pos):
        """Début du drag caméra libre (clic molette enfoncé)."""
        self._drag_active = True
        self._drag_prev   = pos

    def update_drag(self, pos):
        """Souris bouge pendant que clic molette est enfoncé → on déplace
        la caméra du même delta, mais en SENS INVERSE (drag = on tire le
        monde, donc la caméra recule)."""
        if not self._drag_active or self._drag_prev is None:
            return
        dx = pos[0] - self._drag_prev[0]
        dy = pos[1] - self._drag_prev[1]
        self.offset_x -= dx
        self.offset_y -= dy
        self._drag_prev = pos

    def stop_drag(self):
        """Fin du drag (clic molette relâché)."""
        self._drag_active = False
        self._drag_prev   = None

    def pan_scroll(self, direction):
        """Molette tournée en mode libre → on défile verticalement.
        direction = +1 (haut) ou -1 (bas), 60 px par cran."""
        self.offset_y -= direction * 60

    # ─────────────────────────────────────────────────────────────────────────
    #  APPLICATION : du repère MONDE au repère ÉCRAN
    # ─────────────────────────────────────────────────────────────────────────

    def apply(self, rect):
        """Donne le rectangle ÉCRAN correspondant au rectangle MONDE.

        EXEMPLE :
            joueur.rect   = Rect(monde_x=1500, monde_y=200, w=24, h=32)
            cam.offset    = (1200, 50)
            cam.apply(...) = Rect(écran_x=300, écran_y=150, w=24, h=32)
        """
        sx, sy = self.shake_offset
        return pygame.Rect(
            rect.x - int(self.offset_x) + int(sx),
            rect.y - int(self.offset_y) + int(sy),
            rect.width,
            rect.height,
        )

    def is_visible(self, rect):
        """True si rect (en coords MONDE) chevauche la fenêtre visible.
        Sert au CULLING : on saute le draw() des objets hors écran."""
        return (rect.right  > self.offset_x and
                rect.left   < self.offset_x + self._sw and
                rect.bottom > self.offset_y and
                rect.top    < self.offset_y + self._sh)

    # ─────────────────────────────────────────────────────────────────────────
    #  CAMÉRA CINÉMATIQUE (utilisé par systems/cutscene.py)
    # ─────────────────────────────────────────────────────────────────────────
    #
    #  En cutscene, la caméra arrête de suivre le joueur et glisse vers un
    #  point fixe du monde. On garde le même lerp 0.1 que pour le joueur,
    #  donc le "switch" se voit comme un travelling doux.

    def set_cinematic_target(self, target, speed=None):
        """Active le mode cinématique : la caméra glisse vers `target` (x, y monde)
        et reste centrée dessus jusqu'à release_cinematic().

        speed : vitesse du lissage (lerp). 0.1 = défaut doux ; 0.5 = nerveux ;
                1.0 = collage immédiat. None = ne change pas la valeur en cours."""
        self._cinematic_active = True
        self._cinematic_target = (float(target[0]), float(target[1]))
        if speed is not None:
            self._cinematic_speed = float(speed)

    def release_cinematic(self):
        """Désactive le mode cinématique : la caméra reprend le suivi du joueur
        à la prochaine update(). On marque _cinematic_returning=True pour que
        le RETOUR utilise la même vitesse que l'aller (cf. update())."""
        self._cinematic_active    = False
        self._cinematic_returning = True

    def is_cinematic(self):
        """True si la caméra est actuellement en mode cinématique."""
        return self._cinematic_active
