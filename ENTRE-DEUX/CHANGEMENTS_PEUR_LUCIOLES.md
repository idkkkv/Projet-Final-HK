# Changements — Système de peur & Système de lucioles

Ce fichier récapitule les modifications. À garder ou supprimer comme tu veux.

---

## 1. Bug "bloqué dans la zone de peur" — corrigé

### Avant
- Vitesse réduite par `0.5 ^ (stade - peur_max)` → à stade 5 / peur_max 0,
  on tombait à **3 % de la vitesse normale** (quasi figé).
- Combiné au mur invisible, le joueur se retrouvait piégé dès qu'il
  effleurait la zone.

### Après
- Réduction **linéaire** : `mult = max(MIN, 1 - REDUCTION × diff)`
  (cf. `settings.py` → `FEAR_ZONE_VITESSE_MIN = 0.35`,
                     `FEAR_ZONE_REDUCTION_PAR_STADE = 0.18`).
- **Plancher à 35 %** : on peut TOUJOURS marcher pour ressortir, même
  au pire stade. Plus de piège.
- **Mur invisible RESTAURÉ** côté `direction_mur` (par défaut "d" =
  droite). Bloque la traversée dans les deux sens à travers ce bord
  uniquement → vrai obstacle scénaristique, mais les autres bords
  restent libres → on peut toujours rebrousser chemin.
- **Dash et back-dodge** subissent maintenant le `speed_multiplier`
  → impossible de "tricher" en dashant à travers la zone.

### Fichiers touchés (peur)
- `settings.py` → 2 nouvelles constantes (`FEAR_ZONE_*`)
- `world/triggers.py` → `FearZoneTrigger.facteur_vitesse()` réécrite
- `core/game.py` → `_appliquer_fear_zones()` adaptée (mur conservé)
- `entities/player.py` → dash et back-dodge multipliés par `speed_multiplier`

### Comment AJUSTER l'équilibre
Tout dans `settings.py` :

```python
FEAR_ZONE_VITESSE_MIN          = 0.35   # plus bas = plus pénible
FEAR_ZONE_REDUCTION_PAR_STADE  = 0.18   # plus haut = ralentissement plus fort
```

---

## 2. Nouvelle fonction `gagner_luciole()`

`systems/compagnons.py` → `CompagnonGroup.gagner_luciole(joueur, source, sauvegarder)`

Ajoute UNE luciole (max 5 — `COMPAGNON_NB_MAX`). Renvoie `True` si ajoutée,
`False` si déjà au max. Apparaît à côté du joueur, déjà visible. L'argument
`source` est une étiquette ("boss", "villageois", "enigme", ...) pour les
logs. `sauvegarder=True` met aussi à jour `game_config.json`.

```python
# Boss vaincu (déjà branché dans game.py) :
self.compagnons.gagner_luciole(joueur=self.joueur, source="boss")

# Échange villageois :
ok = self.compagnons.gagner_luciole(
    joueur=self.joueur, source="villageois", sauvegarder=True,
)
if ok:
    show_message("Une luciole te rejoint...")

# Énigme, quête, etc. :
self.compagnons.gagner_luciole(joueur=self.joueur, source="enigme_foret")
```

### Branchement BOSS (déjà en place)
`core/game.py` → `_declencher_effets_ennemis()` détecte les boss qui
meurent (`isinstance(ennemi, Boss)`) et appelle automatiquement
`gagner_luciole(source="boss")` + un burst de particules dorées.

### Choix des couleurs / tailles
La nouvelle luciole hérite du slot `idx` (cf. `settings.lucioles_*_idx`).
Le joueur peut customiser chacune dans **Paramètres → Compagnons**, même
celles gagnées en cours de partie.

---

## 3. Fix saisie texte éditeur

**Avant** : impossible de taper "E", "C", "TAB", "J", "H", "F4" dans une
popup de saisie de l'éditeur (nom de map, dialogue PNJ, paramètres
fear_zone) — ces touches déclenchaient leurs raccourcis (toggle éditeur,
appel compagnons, etc.) au lieu d'être ajoutées au texte.

**Après** : `core/game.py _gerer_touche()` détecte si l'éditeur est en
mode saisie de texte (`editeur._text_mode`) et route TOUTES les touches
(sauf Échap, qui annule la saisie) directement vers
`editeur.handle_key()`. Tu peux écrire des phrases comme "Ne reste pas
là" sans souci.

---

## 4. Vérification

- `python3 -m py_compile settings.py world/triggers.py systems/compagnons.py
  entities/player.py core/game.py` → OK.
- Rien d'autre n'a été cassé.

## 5. Idées pour plus tard (non faites)

- Effet visuel marquant au gain d'une luciole (mini cinématique 2-3 s,
  slow-mo + halo qui converge sur le joueur).
- Mémoire des sources déjà utilisées (éviter le double-don si on tue 2x
  le même boss après reload).
- Lucioles à couleur imposée selon la source (boss miroir = bleue, etc.).
