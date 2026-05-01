# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Boss (hérite d'Enemy) — STUB / EMBRYON
# ─────────────────────────────────────────────────────────────────────────────
#
#  ÉTAT ACTUEL : EMBRYON (pas encore branché à l'histoire)
#  -------------------------------------------------------
#  Cette classe est une COQUILLE pour les futurs boss du jeu. Elle hérite
#  de Enemy (entities/enemy.py) → elle profite déjà de tout le système de
#  combat / déplacement / collisions. Il restera juste à overrider les
#  comportements spécifiques boss-par-boss (patterns d'attaque, phases...).
#
#  USAGE PRÉVU
#  -----------
#       class BossOmbre(Boss):
#           def __init__(self, x, y):
#               super().__init__(x, y)
#               self.hp = 12              # plus dur qu'un boss générique
#               self.phase = 1
#
#           def update(self, dt):
#               super().update(dt)
#               if self.hp < 6 and self.phase == 1:
#                   self.phase = 2        # passe en phase enragée
#                   self.speed *= 1.5
#               ...
#
#  Petit lexique :
#     - héritage     = `class Boss(Enemy)` → Boss est UNE SORTE de Enemy.
#                      Il a tout ce que Enemy a (rect, hp, update...) et
#                      peut en plus avoir ses propres méthodes / overrides.
#     - super()      = "appelle la méthode du parent". super().__init__(x, y)
#                      = "fais d'abord ce que Enemy.__init__ fait, puis
#                      j'ajoute mes ajustements".
#     - phase        = entier qui mémorise dans QUELLE PHASE est le boss.
#                      Pattern classique : phase 1 = attaque normale,
#                      phase 2 = "il devient fou et plus rapide" à 50 % PV.
#     - stub         = "embryon" — coquille vide qui réserve l'API en
#                      attendant l'implémentation réelle.
#
#  POURQUOI 120×120 PX ?
#  ---------------------
#  Pour qu'un boss soit visuellement IMPRESSIONNANT, il doit faire bien
#  plus gros qu'un ennemi standard. 120 px ≈ 4 fois la taille d'un slime.
#  À ajuster pour chaque boss spécifique en fonction de son sprite.
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  PAS ENCORE. Quand un boss sera scénarisé, on en créera une instance
#  dans la scène concernée et game.py le mettra à jour comme un ennemi.
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame
from settings import *
from entities.enemy import Enemy


class Boss(Enemy):
    """Squelette générique de boss. À overrider par boss spécifique."""

    def __init__(self, x, y):
        super().__init__(x, y)                         # tout l'init d'Enemy
        self.rect  = pygame.Rect(x, y, 120, 120)       # plus grand qu'un ennemi normal
        self.hp    = 5                                 # plus de PV qu'un mob standard
        self.phase = 1                                 # phase courante (cf. lexique)

    # À compléter selon les boss de l'histoire
    # (override de update(), patterns d'attaque, transitions de phase...)


class BossMiroir(Boss):
    """
    Boss Miroir - Copie les mouvements et les attaques du joueur.
    """

    def __init__(self, x, y):
        super().__init__(x, y)
        
        # Statistiques du Boss
        self.hp = 20
        self.phase = 1
        self.speed = 3
        
        # Listes d'historique 
        self.memoire_x = []
        self.memoire_y = []
        self.memoire_attaque = []
        self.memoire_direction_attaque = []
        self.memoire_direction_regard = []
        
        # Configuration du délai (1 seconde = 50 frames environ)
        self.frames_retard = 50 
        
        # États internes du boss
        self.est_en_attaque = False
        self.direction_actuelle = 1
        self.type_attaque_actuel = "side"
        
        # Rectangle d'attaque du boss (comme le joueur)
        self.attack_rect = pygame.Rect(0, 0, 60, 60)

    def capturer_etat_joueur(self, joueur):
        """
        Récupère toutes les variables du joueur une par une.
        """
        # On extrait les données du joueur
        jx = joueur.rect.x
        jy = joueur.rect.y
        j_atk = joueur.attacking  
        j_dir_atk = joueur.attack_dir
        j_regard = joueur.direction # 1 pour droite, -1 pour gauche

        # on les ajoute aux listes de mémoire
        self.memoire_x.append(jx)
        self.memoire_y.append(jy)
        self.memoire_attaque.append(j_atk)
        self.memoire_direction_attaque.append(j_dir_atk)
        self.memoire_direction_regard.append(j_regard)

    def appliquer_comportement_miroir(self, centre_arene_x):
        """
        Logique de combat avancée : Inversion latérale.
        Si le joueur est à 100px à droite du centre, le boss sera à 100px à gauche.
        """
        if len(self.memoire_x) > self.frames_retard:
            idx = 0
            
            # --- CALCUL DE L'INVERSION MIROIR ---
            # On prend la position passée du joueur
            ancienne_pos_joueur_x = self.memoire_x[idx]
            
            # Calcul de la distance par rapport au centre
            distance_au_centre = ancienne_pos_joueur_x - centre_arene_x
            
            # Le boss se place à l'opposé (Miroir horizontal), plus dur à anticiper pour le joueur
            position_cible_x = centre_arene_x - distance_au_centre
            
            # Application
            self.rect.x = position_cible_x
            self.rect.y = self.memoire_y[idx] # Garde la même hauteur (pour le saut)

            # --- LOGIQUE D'ATTAQUE AUTOMATIQUE (Difficulté ++) ---
            # En plus de copier l'attaque du joueur, le boss attaque de lui-même si le joueur est trop proche.
            distance_directe = abs(self.rect.x - ancienne_pos_joueur_x)
            
            if distance_directe < 50:
                self.est_en_attaque = True
                self.type_attaque_actuel = "side"
            else:
                # Sinon il copie l'attaque passée du joueur
                self.est_en_attaque = self.memoire_attaque[idx]
            
            # --- GESTION DES PHASES DE COLÈRE ---
            if self.phase >= 2:
                # En phase 2, il réduit le délai : il devient plus réactif
                if self.frames_retard > 20:
                    self.frames_retard -= 0.05 # Il accélère progressivement

            # --- NETTOYAGE DES LISTES  ---
            self.memoire_x.pop(0)
            self.memoire_y.pop(0)
            self.memoire_attaque.pop(0)
            self.memoire_direction_attaque.pop(0)
            self.memoire_direction_regard.pop(0)

    def actualiser_hitbox_attaque(self):
        """
        Repositionne la hitbox du boss en fonction de ce que faisait le joueur.
        C'est un copier-coller de ta logique de joueur, mais adapté au boss.
        """
        if self.est_en_attaque:
            if self.type_attaque_actuel == "down":
                # Attaque vers le bas
                self.attack_rect.width = 60 # Valeur exemple (ATTACK_DOWN_W)
                self.attack_rect.height = 40
                self.attack_rect.midtop = (self.rect.centerx, self.rect.bottom)
            else:
                # Attaque latérale
                self.attack_rect.width = 80 # Valeur exemple (ATTACK_RECT_W)
                self.attack_rect.height = 50
                if self.direction_actuelle == 1:
                    self.attack_rect.topleft = (self.rect.right, self.rect.y + 20)
                else:
                    self.attack_rect.topright = (self.rect.left, self.rect.y + 20)

    def update(self, dt, joueur=None):
        """
        Méthode principale appelée à chaque frame.
        """
        # on n'utilise pas le update de Enemy car on veut un mouvement spécial
        # super().update(dt) 
        
        if joueur is not None:
            # 1. on enregistre le présent
            self.capturer_etat_joueur(joueur)
            
            # 2. pn imite le passé
            self.appliquer_comportement_miroir()
            
            # 3. on gère la hitbox d'attaque du boss
            self.actualiser_hitbox_attaque()
            
            # 4. Gestion de la santé / phases (optionnel)
            if self.hp < 10:
                self.phase = 2
                # On pourrait réduire le retard en phase 2 pour être plus dur
                if self.frames_retard > 30:
                    self.frames_retard -= 1