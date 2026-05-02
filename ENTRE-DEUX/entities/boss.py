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
import random
import time
import math

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

    def draw(self, surface):  #cette fonction faudra l'adapter selon le tile
        # On appelle le draw du parent pour afficher le sprite du tileset
        super().draw(surface) 
        
        # On ajoute juste un petit effet visuel "miroir" par dessus (code bonus)
        # Un contour bleu pour dire que c'est une copie magique
        pygame.draw.rect(surface, (0, 191, 255), self.rect, 2, border_radius=5)
        # petit contour blanc pour l'effet "miroir"
        pygame.draw.rect(surface, (255, 255, 255), self.rect, 2)

    def update(self, dt, joueur=None):
        """
        Méthode principale appelée à chaque frame.
        """
        # on n'utilise pas le update de Enemy car on veut un mouvement spécial
        # super().update(dt) 

        # Le *args et **kwargs permettent d'ignorer les arguments
        # supplémentaires envoyés par game.py (murs, plateformes, etc.)
        if joueur is not None:
            self.capturer_etat_joueur(joueur)
            self.appliquer_comportement_miroir(WIDTH // 2)
            self.actualiser_hitbox_attaque()

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

class LaTempête(Boss):
    """
    Boss Tempête : Une tempête de souvenirs. 
    Le but n'est pas de battre le boss mais de survivre à la scène pour ça :
    Le boss ne sera pas qu'une entité physique, mais un gestionnaire d'objets tombants. Ce gestionnaire fait tomber 2 types d'objets :
    Souvenirs Sombres (Dégâts) : Si tu les touches, tu perds 1 PV
    Souvenirs Lumineux (Score/Survie) : Tu dois en ramasser x pour gagner le combat et "calmer la tempête".
    """
    def __init__(self, x, y):
        # On appelle le constructeur (Enemy/Boss)
        super().__init__(x, y)
        
        # --- CONFIGURATION PHYSIQUE ---
        self.rect = pygame.Rect(x, y, 120, 120)
        self.hp = 9999  # Il ne meurt pas par les dégâts classiques
        self.invincible = True 
        
        # --- SYSTÈME DE PHASES (15s / 15s) ---
        self.timer_cycle = 0.0
        self.phase_tempete = False  # False = Calme, True = Pluie intense
        self.seuil_cycle = 15.0     # Durée de chaque phase en secondes
        
        # --- GESTION DES OBJETS TOMBANTS ---
        # On crée une liste vide pour stocker les dictionnaires d'objets
        self.liste_souvenirs = []
        self.dernier_spawn_temps = time.time()
        
        # --- PROGRESSION ---
        self.souvenirs_clairs_collectes = 0
        self.objectif_victoire = 15
        self.combat_termine = False

        # --- ANIMATION ET MOUVEMENT ---
        self.base_y = y # On mémorise la hauteur de départ
        self.compteur_animation = 0.0

    def creer_et_ajouter_souvenir(self):
        """
        FONCTION DE CRÉATION : Génère un objet (dictionnaire) 
        et l'ajoute à la liste principale.
        """
        taille = random.randint(30, 50)
        position_x = random.randint(50, WIDTH - 50)
        
        # Choix du type (Sombre = Dégâts, Lumineux = Point)
        chance = random.random()
        est_lumineux = chance < 0.20 # 20% de chance d'avoir un souvenir clair
        
        # On crée le dictionnaire de l'objet
        nouvel_objet = {
            "rect": pygame.Rect(position_x, -60, taille, taille),
            "vitesse": random.uniform(3.0, 5.0) if not self.phase_tempete else random.uniform(6.0, 10.0),
            "est_bon": est_lumineux,
            "couleur": (255, 255, 200) if est_lumineux else (40, 10, 60),
            "rotation": 0,
            "vitesse_rotation": random.randint(1, 5),
            "actif": True
        }
        
        # On l'ajoute à la liste 
        self.liste_souvenirs.append(nouvel_objet)

    def gerer_spawn_objets(self):
        """
        Gère le timing d'apparition selon la phase de 15 secondes.
        """
        maintenant = time.time()
        
        # Ratio de spawn : 1s en calme, ~0.15s en tempête
        delai = 1.0 if not self.phase_tempete else 0.15
        
        if maintenant - self.dernier_spawn_temps > delai:
            self.creer_et_ajouter_souvenir()
            self.dernier_spawn_temps = maintenant

    def update(self, dt, joueur):
        """
        Mise à jour globale du boss et de ses projectiles.
        """
        if self.combat_termine:
            return

        # 1. Gestion du chrono des 15 secondes
        self.timer_cycle += dt
        if self.timer_cycle >= self.seuil_cycle:
            self.phase_tempete = not self.phase_tempete
            self.timer_cycle = 0.0 # Reset du timer
            print(f"Changement de phase ! Tempête : {self.phase_tempete}")

        # 2. Mouvement flottant (accessible au corps à corps)
        self.compteur_animation += 0.05
        # Le boss se deplace horizontalement et verticalement
        self.rect.x = (WIDTH // 2 - 60) + math.sin(self.compteur_animation) * 100
        self.rect.y = self.base_y + math.cos(self.compteur_animation) * 30

        # 3. Spawn et Mise à jour des souvenirs
        self.gerer_spawn_objets()
        
        # On parcourt la liste des objets tombants
        for s in self.liste_souvenirs:
            if s["actif"]:
                # Chute
                s["rect"].y += s["vitesse"]
                s["rotation"] += s["vitesse_rotation"]
                
                # Collision avec le joueur
                if joueur.rect.colliderect(s["rect"]):
                    if s["est_bon"]:
                        self.souvenirs_clairs_collectes += 1
                        if self.souvenirs_clairs_collectes >= self.objectif_victoire:
                            self.combat_termine = True
                    else:
                        # On utilise ta fonction de dégâts
                        joueur.hit_by_enemy(s["rect"])
                    s["actif"] = False
                
                # suppression si hors écran
                if s["rect"].y > SCREEN_HEIGHT + 100:
                    s["actif"] = False

        # 4. Collision avec le corps du Boss - UNIQUEMENT si le boss est vivant
        if self.alive and joueur.rect.colliderect(self.rect):
            # Le contact avec le noyau blesse le joueur
            joueur.hit_by_enemy(self.rect)

        # 5. Nettoyage de la liste 
        nouvelle_liste = []
        for s in self.liste_souvenirs:
            if s["actif"] == True:
                nouvelle_liste.append(s)
        self.liste_souvenirs = nouvelle_liste

    def draw(self, surface): #pareil à adapter selon le tile
        """Affiche le boss et la pluie de souvenirs."""
        # On appelle le draw du parent pour afficher le sprite du tileset
        super().draw(surface) 
        
        # On ajoute juste un petit effet visuel "miroir" par dessus (conteur bleu)
        pygame.draw.rect(surface, (0, 191, 255), self.rect, 2, border_radius=5)