# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Animation (défilement de frames)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Une SEULE petite classe : Animation. Tu lui donnes une LISTE D'IMAGES
#  (par exemple les 6 images d'une marche), et elle te renvoie l'image à
#  afficher À CET INSTANT. À chaque appel d'update(), elle avance d'un
#  cran ; quand on arrive au bout, soit elle reboucle (loop=True), soit
#  elle se fige sur la dernière image (loop=False, ex : animation de mort).
#
#  EXEMPLE CONCRET (la marche du joueur)
#  -------------------------------------
#       images_marche = [img1, img2, img3, img4, img5, img6]   # 6 images
#       anim = Animation(images_marche, img_dur=5, loop=True)
#
#       # Chaque frame du jeu :
#       anim.update()
#       screen.blit(anim.img(), (joueur.x, joueur.y))
#
#       Avec img_dur=5 → chaque image reste affichée pendant 5 frames du
#       jeu. À 60 fps, on change d'image toutes les 5/60 ≈ 0,083 s.
#       Cycle complet : 6 × 5 = 30 frames = 0,5 s.
#
#  Petit lexique :
#     - frame (image)   = UNE des images de l'animation. anim.images[2]
#                         = la 3ᵉ image (index 0 = la 1re).
#     - frame (moteur)  = un "tour" de la boucle de jeu. À 60 fps, on a
#                         60 frames moteur par seconde.
#                         ⚠️ Le mot "frame" a 2 SENS : on essaye d'utiliser
#                         "image" pour parler des dessins de l'animation
#                         et "frame" pour parler du tic moteur.
#     - img_duration    = nombre de frames moteur passées sur chaque image.
#                         Plus c'est grand → animation plus LENTE.
#     - loop            = True → on reboucle au début à la fin.
#                         False → on s'arrête sur la dernière image.
#                         Typique : True pour la marche, False pour la
#                         mort (on ne veut pas que le mort se relève).
#     - done            = True quand l'animation non-loop est arrivée au
#                         bout. Utile pour déclencher une suite (ex : le
#                         "Game Over" apparaît quand done == True après
#                         l'anim de mort).
#     - frame interne   = self.frame est un compteur qui va de 0 à
#                         (img_duration × len(images)) - 1. On divise
#                         par img_duration pour savoir QUELLE IMAGE renvoyer.
#                         Ex : self.frame = 12, img_dur = 5 → 12 // 5 = 2 →
#                         on affiche images[2].
#
#  POURQUOI img_dur PLUTÔT QUE dt ?
#  --------------------------------
#  Parce que le jeu tourne à 60 fps stable, on raisonne en "frames".
#  Plus simple à régler à l'œil ("je veux 5 frames par image" = quasi
#  immédiat) qu'en secondes. Si on avait des framerates variables ou
#  un mode lent, on passerait à un vrai timer en secondes.
#
#  POURQUOI pause_at() vs stop() ?
#  -------------------------------
#  pause_at(i) → fige sur l'image i SANS marquer "done". Utile pour une
#                pose IDLE qui peut redémarrer (ex : on bouge à nouveau).
#  stop(i)     → fige ET marque "done" (comme si on avait atteint la fin).
#                Utile pour les animations one-shot.
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  entities/player.py : marche, attaque, dash, mort.
#  entities/enemy.py  : marche, attaque, mort.
#  entities/npc.py    : pose idle.
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D14]  Surface       — chaque image est une pygame.Surface
#     [D22]  états         — done = True/False
#
# ─────────────────────────────────────────────────────────────────────────────


class Animation:
    """Défilement de frames avec loop / non-loop, et figeage à volonté."""

    def __init__(self, images, img_dur=5, loop=True):
        self.images       = images       # liste de pygame.Surface
        self.loop         = loop         # True = boucle, False = s'arrête à la fin
        self.img_duration = img_dur      # frames moteur par image
        self.done         = False        # True quand non-loop a fini
        self.frame        = 0            # compteur interne (cf. lexique)

    # ─────────────────────────────────────────────────────────────────────────
    #  AVANCE D'UNE FRAME (à appeler chaque tour de boucle de jeu)
    # ─────────────────────────────────────────────────────────────────────────

    def update(self):
        total = self.img_duration * len(self.images)
        if self.loop:
            # Modulo total → quand on dépasse, on revient à 0.
            self.frame = (self.frame + 1) % total
        else:
            # On bloque la frame à la valeur max et on lève le flag done.
            self.frame = min(self.frame + 1, total - 1)
            if self.frame >= total - 1:
                self.done = True

    # ─────────────────────────────────────────────────────────────────────────
    #  CONTRÔLES MANUELS (figer / reprendre)
    # ─────────────────────────────────────────────────────────────────────────

    def stop(self, img_index=0):
        """Fige sur l'image `img_index` ET marque l'animation comme terminée.
        Utile pour forcer la "pose finale" d'une animation one-shot."""
        self.frame = img_index * self.img_duration
        self.done  = True

    def pause_at(self, img_index):
        """Fige sur l'image `img_index` SANS marquer "done".
        Utile pour une pose IDLE qui pourra redémarrer après."""
        # Clamp : si img_index est hors plage, on borne à 0 ou len-1.
        idx = max(0, min(img_index, len(self.images) - 1))
        self.frame = idx * self.img_duration

    def reset(self):
        """Remet l'animation au début (frame=0, done=False).
        Appelle ça quand tu (re)déclenches une anim non-loop (ex : une
        attaque qui doit toujours partir de la 1re image)."""
        self.frame = 0
        self.done  = False

    # ─────────────────────────────────────────────────────────────────────────
    #  LECTURE DE L'IMAGE COURANTE
    # ─────────────────────────────────────────────────────────────────────────

    def img(self):
        """Renvoie la pygame.Surface à afficher MAINTENANT.

        self.frame // img_duration → numéro de l'image (0, 1, 2, ...).
        Ex : frame=12, img_dur=5 → 12 // 5 = 2 → on renvoie images[2].
        """
        return self.images[int(self.frame / self.img_duration)]
    
    def index(self):
        """Renvoie l'index de l'image courante (0, 1, 2, ...)."""
        return int(self.frame / self.img_duration)
