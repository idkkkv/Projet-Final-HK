from inventory import InventoryItem

class Craft:
    def __init__(self, name, ingredients, result):
        self.name = name
        self.ingredients = ingredients  # Liste d'InventoryItem objects
        self.result = result  # InventoryItem objet

    def can_craft(self, inventory, recipe):
        """Verifie si le joueur a tous les ingrédients nécessaires pour crafter l'objet"""
        for ingredient in self.ingredients:
            if not inventory.has(ingredient):
                return False
        return True

    def craft(self, inventory):
        """Craft l'objet si le joueur a tous les ingrédients nécessaires, sinon affiche un message d'erreur"""
        if not self.can_craft(inventory):
            print("Nan, tu n'as pas tous les ingrédients nécessaires pour crafter cet objet D:<")
            return False
        
        # Retire les ingrédients de l'inventaire
        for ingredient in self.ingredients:
            inventory.remove(ingredient)
        
    # Ajoute le résultat du craft à l'inventaire
        inventory.add(self.result)
        print(f"You have crafted {self.result.name}!")
        return True
    