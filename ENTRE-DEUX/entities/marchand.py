from entities.npc import PNJ
import pygame

class Marchand(PNJ):
    def __init__(self, x, y, nom, dialogues, sprite_name=None, inventaire=None, echelle=2.5, has_gravity=True, dialogue_mode="boucle_dernier"):
        super().__init__(x, y, nom, dialogues, sprite_name, has_gravity=has_gravity, dialogue_mode=dialogue_mode)
        # Liste d'items : [{"nom": "Épée", "prix": 50}, ...]
        self.inventaire = inventaire or []

        if echelle != 1:
            self._rescale_frames(echelle)

    def _rescale_frames(self, echelle):
        """met le perso à l'echelle"""
        # Si jamais il il a d'autres animations
        for etat, anim in self._anims.items():
            anim.images = [
                pygame.transform.scale(
                    f,
                    (f.get_width() * echelle, f.get_height() * echelle)
                )
                for f in anim.images
            ]

        # Mode mono (fallback)
        if self._anim:
            self._anim.images = [
                pygame.transform.scale(
                    f,
                    (f.get_width() * echelle, f.get_height() * echelle)
                )
                for f in self._anim.images
            ]

        # rect
        if self._anims:
            premiere = next(iter(self._anims.values()))
            img = premiere.images[0]
            self.rect = pygame.Rect(self.rect.x, self.rect.y,
                                    img.get_width(), img.get_height())
        elif self._anim:
            img = self._anim.images[0]
            self.rect = pygame.Rect(self.rect.x, self.rect.y,
                                    img.get_width(), img.get_height())
        
    def ouvrir_boutique(self):
        """retourne l'inventaire pour que la boutique_ui puisse l'afficher."""
        return self.inventaire

    def to_dict(self):
        """objet en json"""
        d = super().to_dict()
        d["type"]      = "marchand"
        d["inventaire"] = self.inventaire
        return d
    
    @staticmethod
    def from_dict(data):
        """json en objet"""
        return Marchand(
            data["x"], data["y"],
            data.get("nom", "Marchand"),
            data.get("dialogues", []),
            sprite_name=data.get("sprite_name"),
            inventaire=data.get("inventaire", []),
            dialogue_mode=data.get("dialogue_mode", "boucle_dernier"),
        )