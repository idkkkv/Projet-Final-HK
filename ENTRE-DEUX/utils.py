# utils.py — Fonctions utilitaires
import os

def find_file(filename, search_dir="assets"):
    """
    Cherche un fichier par son nom dans tout le dossier assets.
    Retourne le chemin complet absolu.
    
    Exemple : find_file("player_idle.png") 
    → "/Users/juliou/ENTRE-DEUX/assets/images/player_idle.png"
    """
    base = os.path.dirname(os.path.abspath(__file__))  # Dossier racine du projet
    search_path = os.path.join(base, search_dir)

    for root, dirs, files in os.walk(search_path):
        if filename in files:
            return os.path.join(root, filename)

    raise FileNotFoundError(f"Fichier '{filename}' introuvable dans '{search_dir}'")