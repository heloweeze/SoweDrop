# SoweDrop | SAE 2.03 - Groupe 9

SoweDrop est une application desktop de gestion documentaire développée en Python avec PyQt6. Elle permet d'ajouter des documents, de les associer à des métadonnées, de les rechercher avec plusieurs critères, puis de consulter leurs informations détaillées.

## Site du logiciel
Voici le lien du site officiel de l'application : https://heloweeze.github.io/SoweDrop/

## Fonctionnalités actuelles

- ajout de documents PDF, Word ou Excel ;
- stockage local ou partagé ;
- recherche multicritère par titre, auteur, catégories, mots-clés et dates ;
- logique `AND` entre les champs de recherche ;
- logique `OR` entre plusieurs catégories ou plusieurs mots-clés ;
- tri par date, titre ou auteur, en ordre croissant ou décroissant ;
- affichage d'une fiche de détails ;
- menu clic droit sur la liste des documents ;
- ouverture, téléchargement et suppression logique d'un document.

## Lancement

Depuis la racine du projet :

```bash
.venv/bin/python main.py
```

Si l'environnement virtuel n'existe pas encore, installez les dépendances avec :

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Organisation des données

Les fichiers physiques sont rangés dans :

```text
data/documents/local/
data/documents/partage/
```

Les métadonnées texte sont rangées dans :

```text
data/metadata/documents/
```

La base SQLite locale est générée dans :

```text
data/documents.db
```

Le fichier `data/documents.db` est ignoré par Git, car il s'agit d'une base locale générée par l'application.

## Documentation

Deux guides sont disponibles :

- [Guide utilisateur](documentation/guide_utilisateur.md) : utiliser l'application au quotidien ;
- [Guide développeur](documentation/guide_developpeur.md) : comprendre l'architecture, le code et le moteur de recherche.

Le tri des résultats est documenté dans les deux guides. Il modifie uniquement l'ordre d'affichage des documents déjà trouvés : il ne remplace pas le filtrage multicritère.

Le menu clic droit de la liste des documents est aussi décrit dans les guides. Il donne accès aux actions principales sans remplacer les boutons déjà visibles dans l'interface.

## Vérification

Compiler les fichiers Python :

```bash
.venv/bin/python -m compileall main.py src tests
```

Lancer les tests :

```bash
.venv/bin/python -m unittest discover -s tests
```

## Git

Commandes utiles pour travailler sur le projet :

```bash
git status
git add .
git commit -m "message clair"
git push
```

Avant de commencer une nouvelle tâche, récupérez le travail distant si nécessaire :

```bash
git pull
```
