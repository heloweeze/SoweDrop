-- schema_documents_sqlite.sql
-- Base de données SQLite pour l'application de gestion documentaire SAE 2.03
-- Ce script crée les tables principales, les tables d'association et une vue pratique.
-- Utilisation :
--   sqlite3 data/documents.db < schema_documents_sqlite.sql

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- Suppression de la vue si elle existe déjà.
DROP VIEW IF EXISTS Vue_Documents;

-- Suppression des tables si elles existent déjà.
-- L'ordre respecte les dépendances de clés étrangères.
DROP TABLE IF EXISTS Documents_MotsCles;
DROP TABLE IF EXISTS Documents_Categories;
DROP TABLE IF EXISTS Historique;
DROP TABLE IF EXISTS Versions;
DROP TABLE IF EXISTS Documents;
DROP TABLE IF EXISTS MotsCles;
DROP TABLE IF EXISTS Categories;
DROP TABLE IF EXISTS Utilisateurs;

-- Utilisateurs : un document est ajouté par un seul utilisateur.
CREATE TABLE Utilisateurs (
    idUser      INTEGER PRIMARY KEY AUTOINCREMENT,
    nom         VARCHAR(50) NOT NULL,
    prenom      VARCHAR(50) NOT NULL,
    matricule   VARCHAR(50) NOT NULL UNIQUE
);

-- Documents : métadonnées principales et chemin vers le fichier.
-- La base ne stocke pas le fichier lui-même, seulement son chemin d'accès.
CREATE TABLE Documents (
    idDoc              INTEGER PRIMARY KEY AUTOINCREMENT,
    titre              VARCHAR(100) NOT NULL,
    description        VARCHAR(255),
    idUser             INTEGER NOT NULL,
    date_document      DATE NOT NULL,
    ressource          VARCHAR(255) NOT NULL,
    type_fichier       VARCHAR(20),
    stockage           TEXT NOT NULL DEFAULT 'local'
                        CHECK (stockage IN ('local', 'partage')),
    statut             TEXT NOT NULL DEFAULT 'actif'
                        CHECK (statut IN ('actif', 'archive', 'supprime')),
    version_courante   INTEGER NOT NULL DEFAULT 1 CHECK (version_courante >= 1),

    CONSTRAINT fk_documents_utilisateurs
        FOREIGN KEY (idUser)
        REFERENCES Utilisateurs(idUser)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

-- Mots-clés : mots associés aux documents pour faciliter la recherche.
CREATE TABLE MotsCles (
    idMot   INTEGER PRIMARY KEY AUTOINCREMENT,
    mot     VARCHAR(50) NOT NULL UNIQUE
);

-- Catégories : catégories associées aux documents pour faciliter la recherche.
CREATE TABLE Categories (
    idCat   INTEGER PRIMARY KEY AUTOINCREMENT,
    nomCat  VARCHAR(50) NOT NULL UNIQUE
);

-- Association Documents <-> MotsCles.
-- Un document peut avoir plusieurs mots-clés.
-- Un mot-clé peut être lié à plusieurs documents.
CREATE TABLE Documents_MotsCles (
    idDoc  INTEGER NOT NULL,
    idMot  INTEGER NOT NULL,

    PRIMARY KEY (idDoc, idMot),

    CONSTRAINT fk_doc_mot_document
        FOREIGN KEY (idDoc)
        REFERENCES Documents(idDoc)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT fk_doc_mot_motcle
        FOREIGN KEY (idMot)
        REFERENCES MotsCles(idMot)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- Association Documents <-> Categories.
-- Un document peut être classé dans plusieurs catégories.
-- Une catégorie peut regrouper plusieurs documents.
CREATE TABLE Documents_Categories (
    idDoc  INTEGER NOT NULL,
    idCat  INTEGER NOT NULL,

    PRIMARY KEY (idDoc, idCat),

    CONSTRAINT fk_doc_cat_document
        FOREIGN KEY (idDoc)
        REFERENCES Documents(idDoc)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT fk_doc_cat_categorie
        FOREIGN KEY (idCat)
        REFERENCES Categories(idCat)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- Historique : traces des actions effectuées sur chaque document.
-- Au minimum, l'application doit ajouter une ligne lors de la création du document.
CREATE TABLE Historique (
    idHist  INTEGER PRIMARY KEY AUTOINCREMENT,
    idDoc   INTEGER NOT NULL,
    date    DATETIME NOT NULL DEFAULT (datetime('now')),
    objet   VARCHAR(100) NOT NULL,

    CONSTRAINT fk_historique_document
        FOREIGN KEY (idDoc)
        REFERENCES Documents(idDoc)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- Versions : table ajoutée pour soutenir la fonctionnalité "gestion des versions".
-- Elle complète l'historique sans remplacer la table Historique du document.
CREATE TABLE Versions (
    idVersion       INTEGER PRIMARY KEY AUTOINCREMENT,
    idDoc           INTEGER NOT NULL,
    numero_version  INTEGER NOT NULL CHECK (numero_version >= 1),
    ressource       VARCHAR(255) NOT NULL,
    date_version    DATETIME NOT NULL DEFAULT (datetime('now')),
    commentaire     VARCHAR(255),

    UNIQUE (idDoc, numero_version),

    CONSTRAINT fk_versions_document
        FOREIGN KEY (idDoc)
        REFERENCES Documents(idDoc)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- Vue pratique pour afficher les documents avec l'auteur.
CREATE VIEW Vue_Documents AS
SELECT
    d.idDoc,
    d.titre,
    d.description,
    u.nom AS auteur_nom,
    u.prenom AS auteur_prenom,
    u.matricule AS auteur_matricule,
    d.date_document,
    d.ressource,
    d.type_fichier,
    d.stockage,
    d.statut,
    d.version_courante
FROM Documents d
JOIN Utilisateurs u ON u.idUser = d.idUser;

COMMIT;
