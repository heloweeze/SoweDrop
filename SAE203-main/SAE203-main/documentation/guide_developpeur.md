# Guide développeur - SoweDrop

Ce document est destiné aux développeurs. Il explique l'organisation actuelle du code et le fonctionnement du moteur de recherche multicritère.

## Architecture générale

L'application est une application desktop Python avec PyQt6 et SQLite.

Les fichiers principaux sont :

- `main.py` : point d'entrée de l'application ;
- `src/interface.py` : interface graphique PyQt6 ;
- `src/logic.py` : logique métier et validation ;
- `src/database.py` : accès SQLite et requêtes SQL ;
- `src/categories.py` : liste des catégories autorisées.

Le flux général est :

```text
Interface PyQt -> SearchFilters -> LogicService -> SQLiteRepository -> SQLite -> tableau
```

L'interface ne construit pas de SQL. Elle crée un objet `SearchFilters`, puis la logique métier prépare des filtres propres pour la couche base de données.

## Stockage des données

Les documents physiques sont stockés dans :

```text
data/documents/local/
data/documents/partage/
```

Les métadonnées texte, utilisées comme données d'import et d'export, sont stockées dans :

```text
data/metadata/documents/
```

La base SQLite est créée dans :

```text
data/documents.db
```

Le schéma SQL est dans :

```text
data/schema_documents_sqlite.sql
```

Au démarrage, `SQLiteRepository` vérifie la base, applique le schéma si besoin, ajoute les catégories autorisées, puis importe les métadonnées texte si la table `Documents` est vide.

## Recherche multicritère

Les critères actuellement exposés dans l'interface sont :

- titre ;
- auteur ;
- catégorie ;
- mots-clés ;
- date minimale ;
- date maximale.

La donnée `ressource` existe toujours dans le modèle et dans la base. Elle correspond au chemin du fichier. Elle est affichée dans la fiche de détails, mais elle n'est plus proposée comme filtre utilisateur car son sens est surtout technique.

## Logique AND entre les champs

Les champs renseignés sont combinés avec une logique `AND`.

Exemple :

```text
auteur = Fabien
catégorie = Rapport
```

Le document doit respecter les deux conditions pour être affiché.

Dans `src/database.py`, cette logique est construite en ajoutant les conditions dans la liste `where`, puis en les joignant avec `AND`.

## Logique OR pour catégories et mots-clés

À l'intérieur d'un même champ multiple, la logique est différente :

- plusieurs catégories sont combinées avec `OR` ;
- plusieurs mots-clés sont combinés avec `OR`.

Exemple :

```text
catégories = Rapport, Finance
```

Un document est affiché s'il appartient à Rapport ou Finance.

Pour les catégories, la requête utilise une correspondance exacte avec `IN (...)`.

Pour les mots-clés, la requête utilise `LIKE`, ce qui permet une recherche partielle.

## Tri des résultats

Les tris disponibles sont :

- `date` ;
- `titre` ;
- `auteur`.

Les ordres disponibles sont :

- `desc` : décroissant ;
- `asc` : croissant.

Par défaut, `SearchFilters` utilise :

```text
sort_by = date
sort_order = desc
```

Le tri ne remplace pas le filtrage. Les filtres déterminent quels documents sont récupérés, puis le tri détermine seulement leur ordre d'affichage.

Exemples :

- `sort_by = date`, `sort_order = desc` : documents les plus récents en premier ;
- `sort_by = titre`, `sort_order = asc` : titres classés de A à Z ;
- `sort_by = auteur`, `sort_order = desc` : auteurs classés en ordre décroissant.

Quand l'utilisateur change le tri dans l'interface, `SearchFilters` conserve les filtres actifs. La nouvelle requête recharge donc les mêmes résultats filtrés, mais dans un ordre différent.

Si une valeur de tri invalide arrive côté logique métier, `LogicService` revient sur ces valeurs sûres. C'est le fallback de tri.

## Menu clic droit des documents

Le menu contextuel de la liste est géré dans `src/interface.py`.

Le tableau utilise la politique `CustomContextMenu`, puis appelle `afficherMenuContextuelDocument()` quand l'utilisateur fait un clic droit.

La méthode `creerMenuContextuelDocument()` prépare le menu :

- si le clic vise une ligne, la ligne est sélectionnée et la fiche de détails est mise à jour ;
- les actions `Ouvrir`, `Télécharger`, `Supprimer` et `Copier le chemin de la ressource` réutilisent les méthodes existantes ;
- l'action `Ajouter un document` reste disponible dans tous les cas ;
- si le clic vise une zone vide, la sélection est vidée et seules les actions qui ne dépendent pas d'un document sont affichées.

Cette organisation évite de dupliquer la logique des boutons. Le menu clic droit est seulement une autre façon de déclencher les mêmes comportements.

## Validation des filtres

`LogicService` valide et normalise les filtres avant de les envoyer à `SQLiteRepository`.

Les principales règles sont :

- les textes sont nettoyés avec `strip()` ;
- les catégories doivent appartenir à la liste autorisée ;
- les dates doivent respecter le format `YYYY-MM-DD` ;
- une date minimale ne peut pas être supérieure à une date maximale ;
- les champs vides sont transformés en valeurs ignorées par la base.

## Format retourné à l'interface

La base retourne les colonnes SQL et hydrate aussi :

- les catégories ;
- les mots-clés.

La logique métier reformate ensuite le résultat pour l'interface avec des clés simples :

- `id` ;
- `titre` ;
- `auteur` ;
- `description` ;
- `date` ;
- `categorie` ;
- `ressource` ;
- `mots_cles` ;
- `chemin_fichier` ;
- `stockage` ;
- `type_fichier` ;
- `statut`.

## Tests disponibles

Les tests actuels vérifient l'interface de recherche en mode headless :

```bash
.venv/bin/python -m unittest discover -s tests
```

Ils couvrent :

- le chargement initial ;
- une recherche simple ;
- une combinaison de filtres ;
- la réinitialisation.

La compilation Python peut être vérifiée avec :

```bash
.venv/bin/python -m compileall main.py src tests
```
