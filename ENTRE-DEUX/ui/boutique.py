# modif taille de la fenetre : bw, bh
# modif taille img : taille=(
# split_x : separation coté img et produits
# 


import pygame 
from utils import find_file


class Boutique:
    def __init__(self):
        self.actif     = False
        self.inventaire = []
        self._police   = pygame.font.Font(find_file("Butler_font.ttf"), 16)
        self._title_police = pygame.font.Font(find_file("Butler_font.ttf"), 22)
        self.selection  = 0
        self._img_cache = {} # pr ne pas tt rechager

    def _get_police(self):
        if self._police is None:
            self._police = pygame.font.SysFont("Consolas", 16)
        if self._title_police is None:
            self._title_police = pygame.font.SysFont("Consolas", 22)
        return self._police, self._title_police

    def ouvrir(self, inventaire):
        self.actif      = True
        self.inventaire = inventaire or []
        self.selection  = 0

    def fermer(self):
        self.actif = False

    def handle_key(self, key, player):
        """Retourne l'item acheté ou None."""
        if key == pygame.K_UP:
            self.selection = max(0, self.selection - 1)
        elif key == pygame.K_DOWN:
            self.selection = min(len(self.inventaire) - 1, self.selection + 1)
        elif key in (pygame.K_SPACE, pygame.K_RETURN):
            if self.inventaire:
                item = self.inventaire[self.selection]
                stock = item.get("stock", 0)

                if stock >= 0 and player.coins >= item.get("prix", 0):
                    player.coins -= item.get("prix", 0)
                    stock -= 1
                    item["stock"] = stock
                    return item
                
        elif key == pygame.K_ESCAPE:
            self.fermer()
        return None
    
    def trouver_img(self, nom, taille=(320, 320)):
        """chercher une image avec le nom de l'item"""
        if nom in self._img_cache:
            return self._img_cache[nom]
        try:
            from ui.inventory import ITEMS
            if nom not in ITEMS:
                return None
            
            nom_fichier = ITEMS[nom].get("image")
            if not nom_fichier:
                return None
            
            chemin = find_file(nom_fichier)
            if not chemin:
                return None
            
            img = pygame.image.load(chemin).convert_alpha()
            img = pygame.transform.scale(img, taille)
            self._img_cache[nom] = img
            return img
        
        except Exception as e:
            print(f"Image introuvable pour {nom} : {e}")
            return None
        
    def split_text(self, desc, max_w, police):
        """Découpe desc (avec \n)"""
        toutes = []
        for ligne in desc.split("\n"):
            mots = ligne.split(" ")
            courante = ""
            for mot in mots:
                essai = (courante + " " + mot).strip()
                if police.size(essai)[0] <= max_w:
                    courante = essai
                else:
                    if courante:
                        toutes.append(courante)
                    courante = mot
            if courante:
                toutes.append(courante)
        return toutes

    def draw(self, surf):
        if not self.actif:
            return

        police, title_police = self._get_police()
        
        # dimensions fenetre
        bw, bh = 600, 420
        #centrage fenetre
        w, h   = surf.get_size()
        bx     = (w - bw) // 2
        by     = (h - bh) // 2
        # ajustement taille des elements
        pad = int(20)
        line = int(30)
        split_x = bx + int(bw * 0.3)
        top = by + pad
        bottom = by + bh - pad

        max_items_visibles = (bh - 80) // line

        #couleurs
        title_color = (220, 200, 255)
        text_color_purple = (230, 210, 255)
        text_color_gold = (255, 230, 100)
        text_color_gray = (100, 100, 100)
        fond_color = (20, 15, 30, 220)
        fond_contour_color = (180, 140, 255)

        # Fond
        fond = pygame.Surface((bw, bh), pygame.SRCALPHA)
        fond.fill(fond_color)
        surf.blit(fond, (bx, by))
        pygame.draw.rect(surf, (fond_contour_color), (bx, by, bw, bh), 2)

        # Séparateur vertical
        pygame.draw.line(surf, fond_contour_color,
                        (split_x, by + 10), (split_x, by + bh - 10), 1)

        # Titre
        surf.blit(title_police.render("— SHOP —", True, title_color),
                  (bx + pad + int(10), by + int(20)))
        
        # Items
        if not self.inventaire:
            surf.blit(police.render("Rien à vendre.", True, text_color_purple),
                      (bx + pad, by + int(60)))
        else:
            scroll = max(0, self.selection - max_items_visibles + 1)
                
            for i, item in enumerate(self.inventaire):
                idx_affiche = i - scroll
                if idx_affiche < 0 or idx_affiche >= max_items_visibles:
                    continue

                nom  = item.get("nom", "?")
                prix = item.get("prix", "?")
                stock = item.get("stock", "?")
                
                if i == self.selection :
                    coul  = text_color_gold
                    prefixe = "> "
                    img = self.trouver_img(nom)
                    desc = item.get("desc", "?")

                else:
                    prefixe = "  "
                    coul = text_color_purple
                    img = None
                    desc = None
                
                if desc:
                    max_desc_w = bw - int(bw * 0.3) - pad * 3
                    sous_lignes = self.split_text(desc, max_desc_w, police)
                    for k, sl in enumerate(sous_lignes):
                        y = top + int(320) + k * 22
                        surf.blit(police.render(sl, True, text_color_purple),
                                (split_x + pad, y))
                        
                if img:
                    surf.blit(img, (split_x + pad + int(35), top + int(7)))
                    
                
                if stock != 0:
                    surf.blit(police.render(f"{prefixe}{nom}  —  {prix}$",True, coul),(bx + pad, by + int(60) + idx_affiche * line))

        surf.blit(police.render("Espace=acheter", True, text_color_gray),
                (bx + pad, by + bh - line))