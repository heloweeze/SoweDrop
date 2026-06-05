# Guide utilisateur - SoweDrop

Ce document est destiné aux utilisateurs finaux. Il explique comment utiliser l'application sans entrer dans les détails du code.

## Lancer l'application

Depuis le dossier du projet, lancez :

```bash
.venv/bin/python main.py
```

L'application ouvre une fenêtre avec :

- une zone de recherche en haut à gauche ;
- une liste de documents au centre, vide au démarrage ;
- une fiche de détails à droite ;
- des boutons pour ouvrir ou télécharger le document sélectionné.

## Rechercher un document

La recherche permet de filtrer les documents avec plusieurs critères :

- `Titre` : cherche une partie du titre ;
- `Auteur` : cherche une partie du nom ou prénom ;
- `Mots-clés` : cherche un ou plusieurs mots-clés, séparés par des virgules ;
- `Catégories` : permet de cocher une ou plusieurs catégories ;
- `Date min` et `Date max` : limitent la recherche à une période.

Pour lancer la recherche, remplissez les champs souhaités puis cliquez sur `Rechercher`.

Les champs vides sont ignorés. Si vous cliquez sur `Rechercher` sans remplir de champ, tous les documents sont affichés.

## Comprendre la logique des filtres

Quand plusieurs champs sont renseignés, le document doit respecter tous les champs à la fois.

Exemple :

- auteur : `Fabien`
- catégorie : `Rapport`

L'application affiche seulement les documents écrits par Fabien et classés dans la catégorie Rapport.

Pour les catégories et les mots-clés, il est possible d'en mettre plusieurs. Dans ce cas, il suffit qu'au moins une catégorie ou un mot-clé corresponde.

Exemple :

- catégories : `Rapport`, `Finance`

L'application affiche les documents classés en Rapport ou en Finance.

## Trier les résultats

La zone de recherche contient aussi deux menus de tri :

- `Trier par` : `Date`, `Titre` ou `Auteur` ;
- `Ordre` : `Décroissant` ou `Croissant`.

Par défaut, les documents sont triés par date décroissante. Le document le plus récent apparaît donc en premier.

Le tri ne remplace pas la recherche. Il change seulement l'ordre des documents déjà affichés.

Exemples :

- `Date` + `Décroissant` affiche les documents les plus récents en premier ;
- `Titre` + `Croissant` classe les documents de A à Z ;
- `Auteur` + `Croissant` regroupe les documents selon le nom de l'auteur.

Si une recherche est active, le tri s'applique uniquement aux résultats de cette recherche. Les filtres restent donc inchangés.

## Réinitialiser la recherche

Le bouton `Réinitialiser` :

- vide les champs de recherche ;
- décoche les catégories ;
- désactive les dates ;
- remet le tri par défaut ;
- vide la liste des documents.

## Lire la fiche de détails

Quand vous cliquez sur une ligne du tableau, la fiche de détails affiche :

- le titre ;
- l'auteur ;
- la date ;
- la catégorie ;
- la ressource ;
- les mots-clés ;
- la description.

La ressource correspond au chemin du fichier dans le projet. Elle permet à l'application de retrouver le document à ouvrir ou télécharger.

## Ouvrir ou télécharger un document

Après avoir sélectionné une ligne :

- `Ouvrir` lance le fichier avec l'application installée sur l'ordinateur ;
- `Télécharger` copie le fichier vers l'emplacement choisi.

Si le fichier n'existe pas sur le disque, l'application affiche un message d'erreur.

## Utiliser le menu clic droit

Un clic droit sur une ligne de la liste sélectionne automatiquement le document et ouvre un menu avec les actions principales :

- `Ouvrir` ;
- `Télécharger` ;
- `Supprimer` ;
- `Copier le chemin de la ressource` ;
- `Ajouter un document`.

L'action `Copier le chemin de la ressource` place dans le presse-papiers le chemin enregistré pour le document. Ce chemin est utile pour retrouver le fichier dans le dossier `data/documents/`.

Si le clic droit est fait dans une zone vide de la liste, aucun document n'est sélectionné. Dans ce cas, le menu affiche seulement `Ajouter un document`.

## Ajouter un document

Le menu `Importer` permet d'ajouter un document.

Le formulaire demande :

- un titre ;
- un auteur ;
- une date ;
- un stockage `local` ou `partage` ;
- des catégories ;
- une description ;
- un fichier à sélectionner.

Le fichier est copié dans le dossier de stockage choisi, puis ses informations sont enregistrées dans la base.

## Supprimer un document

Le menu `Édition > Supprimer un document` supprime le document sélectionné après confirmation.

La suppression est logique : le document est marqué comme supprimé dans la base et n'apparaît plus dans la recherche.

## Où sont rangées les données ?

Les fichiers sont rangés ici :

```text
data/documents/local/
data/documents/partage/
```

Les métadonnées exportées en texte brut sont rangées ici :

```text
data/metadata/documents/
```

La base SQLite utilisée par l'application est ici :

```text
data/documents.db
```
