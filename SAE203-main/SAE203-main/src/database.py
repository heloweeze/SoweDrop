from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from src.categories import AUTHORIZED_CATEGORIES, CATEGORY_BY_LOWER_NAME


class SQLiteRepository:
    """Accès SQLite pour l'application documentaire."""

    def __init__(self, db_path: str | Path, schema_path: str | Path | None = None, project_root: str | Path | None = None):
        self.db_path = Path(db_path)
        self.schema_path = Path(schema_path) if schema_path else None
        self.project_root = Path(project_root) if project_root else self.db_path.parent.parent
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_database()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON;')
        return conn

    def _ensure_database(self) -> None:
        if not self.db_path.exists():
            self.db_path.touch()

        # Si la base est neuve, on applique le schéma SQL du projet.
        if self.schema_path and self.schema_path.exists():
            with self._connect() as conn:
                has_documents = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='Documents'"
                ).fetchone()
                if not has_documents:
                    conn.executescript(self.schema_path.read_text(encoding='utf-8'))
                    conn.commit()

        self._ensure_resource_paths_inside_data()
        self._ensure_authorized_categories()
        self.seed_from_metadata_if_empty()

    def _ensure_resource_paths_inside_data(self) -> None:
        # Migration douce : les anciens chemins "documents/..." deviennent "data/documents/...".
        with self._connect() as conn:
            has_documents = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='Documents'"
            ).fetchone()
            if not has_documents:
                return

            conn.execute(
                """
                UPDATE Documents
                SET ressource = 'data/' || ressource
                WHERE ressource LIKE 'documents/%'
                """
            )

            has_versions = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='Versions'"
            ).fetchone()
            if has_versions:
                conn.execute(
                    """
                    UPDATE Versions
                    SET ressource = 'data/' || ressource
                    WHERE ressource LIKE 'documents/%'
                    """
                )

            conn.commit()

    def _ensure_authorized_categories(self) -> None:
        with self._connect() as conn:
            conn.executemany(
                'INSERT OR IGNORE INTO Categories (nomCat) VALUES (?)',
                [(category,) for category in AUTHORIZED_CATEGORIES],
            )
            conn.commit()

    def seed_from_metadata_if_empty(self) -> None:
        # Les fichiers texte servent de jeu de métadonnées initial pour une base vide.
        metadata_dir = self.project_root / 'data' / 'metadata' / 'documents'
        if not metadata_dir.exists():
            return

        with self._connect() as conn:
            count = conn.execute('SELECT COUNT(*) FROM Documents').fetchone()[0]
            if count:
                return

            for file in sorted(metadata_dir.glob('*.txt')):
                payload = self._parse_metadata_file(file)
                user_id = self._get_or_create_user(
                    conn,
                    payload.get('auteur_nom', 'INCONNU'),
                    payload.get('auteur_prenom', 'Utilisateur'),
                    payload.get('auteur_matricule', f"AUTO_{file.stem.upper()}"),
                )

                cur = conn.execute(
                    """
                    INSERT INTO Documents (
                        titre, description, idUser, date_document, ressource,
                        type_fichier, stockage, statut, version_courante
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload.get('titre', file.stem),
                        payload.get('description', ''),
                        user_id,
                        payload.get('date_document', '2026-01-01'),
                        payload.get('ressource', ''),
                        payload.get('type_fichier', ''),
                        payload.get('stockage', 'local'),
                        payload.get('statut', 'actif'),
                        1,
                    ),
                )
                doc_id = cur.lastrowid

                for cat in self._split_values(payload.get('categories', '')):
                    cat_id = self._get_or_create_category(conn, cat)
                    conn.execute(
                        'INSERT OR IGNORE INTO Documents_Categories (idDoc, idCat) VALUES (?, ?)',
                        (doc_id, cat_id),
                    )

                for mot in self._split_values(payload.get('mots_cles', '')):
                    mot_id = self._get_or_create_keyword(conn, mot)
                    conn.execute(
                        'INSERT OR IGNORE INTO Documents_MotsCles (idDoc, idMot) VALUES (?, ?)',
                        (doc_id, mot_id),
                    )

                conn.execute(
                    'INSERT INTO Historique (idDoc, objet) VALUES (?, ?)',
                    (doc_id, 'Import initial depuis les métadonnées'),
                )
                conn.execute(
                    'INSERT INTO Versions (idDoc, numero_version, ressource, commentaire) VALUES (?, ?, ?, ?)',
                    (doc_id, 1, payload.get('ressource', ''), 'Version initiale'),
                )

            conn.commit()

    def _parse_metadata_file(self, path: Path) -> dict[str, str]:
        data: dict[str, str] = {}
        for line in path.read_text(encoding='utf-8').splitlines():
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            data[key.strip()] = value.strip()
        return data

    def insert_document(self, document_data: dict[str, Any]) -> int:
        with self._connect() as conn:
            user_id = document_data.get('user_id')
            if not user_id:
                user_id = self._get_or_create_user_from_author(conn, document_data.get('auteur', 'Inconnu'))

            cur = conn.execute(
                """
                INSERT INTO Documents (
                    titre, description, idUser, date_document, ressource,
                    type_fichier, stockage, statut, version_courante
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'actif', 1)
                """,
                (
                    document_data.get('titre', ''),
                    document_data.get('description', ''),
                    user_id,
                    document_data.get('date_document', ''),
                    document_data.get('ressource', ''),
                    document_data.get('type_fichier', ''),
                    document_data.get('stockage', 'local'),
                ),
            )
            doc_id = cur.lastrowid
            conn.execute(
                'INSERT INTO Versions (idDoc, numero_version, ressource, commentaire) VALUES (?, ?, ?, ?)',
                (doc_id, 1, document_data.get('ressource', ''), 'Création du document'),
            )
            conn.commit()
            return int(doc_id)

    def link_categories_to_document(self, document_id: int, categories: list[str]) -> None:
        with self._connect() as conn:
            for category in categories:
                cat_id = self._get_or_create_category(conn, category)
                conn.execute(
                    'INSERT OR IGNORE INTO Documents_Categories (idDoc, idCat) VALUES (?, ?)',
                    (document_id, cat_id),
                )
            conn.commit()

    def list_categories(self) -> list[str]:
        return list(AUTHORIZED_CATEGORIES)

    def link_keywords_to_document(self, document_id: int, keywords: list[str]) -> None:
        with self._connect() as conn:
            for keyword in keywords:
                mot_id = self._get_or_create_keyword(conn, keyword)
                conn.execute(
                    'INSERT OR IGNORE INTO Documents_MotsCles (idDoc, idMot) VALUES (?, ?)',
                    (document_id, mot_id),
                )
            conn.commit()

    def add_history(self, document_id: int, objet: str) -> None:
        with self._connect() as conn:
            conn.execute(
                'INSERT INTO Historique (idDoc, objet) VALUES (?, ?)',
                (document_id, objet),
            )
            conn.commit()

    def search_documents(self, prepared_filters: dict[str, Any]) -> list[dict[str, Any]]:
        # Les champs remplis ajoutent des conditions ; les champs vides sont ignorés.
        where = ["d.statut != 'supprime'"]
        params: list[Any] = []

        if prepared_filters.get('titre_like'):
            where.append('LOWER(d.titre) LIKE ?')
            params.append(f"%{prepared_filters['titre_like'].lower()}%")

        if prepared_filters.get('auteur_like'):
            where.append("LOWER(u.nom || ' ' || u.prenom) LIKE ?")
            params.append(f"%{prepared_filters['auteur_like'].lower()}%")

        if prepared_filters.get('ressource_like'):
            where.append('LOWER(d.ressource) LIKE ?')
            params.append(f"%{prepared_filters['ressource_like'].lower()}%")

        if prepared_filters.get('date_min'):
            where.append('d.date_document >= ?')
            params.append(prepared_filters['date_min'])

        if prepared_filters.get('date_max'):
            where.append('d.date_document <= ?')
            params.append(prepared_filters['date_max'])

        categories = prepared_filters.get('categories_exact_or') or []
        if categories:
            # Plusieurs catégories sont combinées en OR grâce au IN (...).
            placeholders = ','.join('?' for _ in categories)
            where.append(
                f"""EXISTS (
                    SELECT 1
                    FROM Documents_Categories dc
                    JOIN Categories c ON c.idCat = dc.idCat
                    WHERE dc.idDoc = d.idDoc AND c.nomCat IN ({placeholders})
                )"""
            )
            params.extend(categories)

        keywords = prepared_filters.get('mots_cles_like_or') or []
        if keywords:
            # Plusieurs mots-clés sont combinés en OR, avec une recherche partielle.
            like_parts = []
            for keyword in keywords:
                like_parts.append('LOWER(m.mot) LIKE ?')
                params.append(f'%{keyword.lower()}%')
            where.append(
                f"""EXISTS (
                    SELECT 1
                    FROM Documents_MotsCles dm
                    JOIN MotsCles m ON m.idMot = dm.idMot
                    WHERE dm.idDoc = d.idDoc AND ({' OR '.join(like_parts)})
                )"""
            )

        sort_order = prepared_filters.get('sort_order', 'desc').upper()
        if sort_order not in {'ASC', 'DESC'}:
            sort_order = 'DESC'

        sort_column = prepared_filters.get('sort_column', 'date_document')
        if sort_column == 'auteur':
            sql_sort = f'u.nom {sort_order}, u.prenom {sort_order}'
        else:
            sql_sort = f'd.{sort_column} {sort_order}'

        sql = f"""
            SELECT DISTINCT
                d.idDoc,
                d.titre,
                d.description,
                d.date_document,
                d.ressource,
                d.type_fichier,
                d.stockage,
                d.statut,
                d.idUser,
                u.nom AS auteur_nom,
                u.prenom AS auteur_prenom,
                u.matricule AS auteur_matricule
            FROM Documents d
            JOIN Utilisateurs u ON u.idUser = d.idUser
            WHERE {' AND '.join(where)}
            ORDER BY {sql_sort}, d.idDoc ASC
        """

        with self._connect() as conn:
            # Les paramètres sont passés séparément pour éviter l'injection SQL.
            rows = conn.execute(sql, params).fetchall()
            return [self._hydrate_document_row(conn, row) for row in rows]

    def get_document_by_id(self, document_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    d.idDoc,
                    d.titre,
                    d.description,
                    d.date_document,
                    d.ressource,
                    d.type_fichier,
                    d.stockage,
                    d.statut,
                    d.idUser,
                    u.nom AS auteur_nom,
                    u.prenom AS auteur_prenom,
                    u.matricule AS auteur_matricule
                FROM Documents d
                JOIN Utilisateurs u ON u.idUser = d.idUser
                WHERE d.idDoc = ?
                """,
                (document_id,),
            ).fetchone()
            if not row:
                return None
            return self._hydrate_document_row(conn, row)

    def _hydrate_document_row(self, conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        doc = dict(row)
        doc['categories'] = [
            r['nomCat']
            for r in conn.execute(
                """
                SELECT c.nomCat
                FROM Categories c
                JOIN Documents_Categories dc ON dc.idCat = c.idCat
                WHERE dc.idDoc = ?
                ORDER BY c.nomCat
                """,
                (row['idDoc'],),
            ).fetchall()
        ]
        doc['mots_cles'] = [
            r['mot']
            for r in conn.execute(
                """
                SELECT m.mot
                FROM MotsCles m
                JOIN Documents_MotsCles dm ON dm.idMot = m.idMot
                WHERE dm.idDoc = ?
                ORDER BY m.mot
                """,
                (row['idDoc'],),
            ).fetchall()
        ]
        return doc

    def archive_document(self, document_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE Documents SET statut = 'archive' WHERE idDoc = ?", (document_id,))
            conn.commit()

    def delete_document(self, document_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE Documents SET statut = 'supprime' WHERE idDoc = ?", (document_id,))
            conn.commit()

    def document_belongs_to_user(self, document_id: int, user_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT 1 FROM Documents WHERE idDoc = ? AND idUser = ? AND statut != ? LIMIT 1',
                (document_id, user_id, 'supprime'),
            ).fetchone()
            return row is not None

    def _get_or_create_user_from_author(self, conn: sqlite3.Connection, author: str) -> int:
        author = (author or 'Utilisateur inconnu').strip()
        parts = author.split()
        if len(parts) >= 2:
            prenom = parts[0]
            nom = ' '.join(parts[1:]).upper()
        else:
            prenom = author
            nom = 'INCONNU'
        matricule = self._build_unique_matricule(conn, prenom, nom)
        return self._get_or_create_user(conn, nom, prenom, matricule)

    def _get_or_create_user(self, conn: sqlite3.Connection, nom: str, prenom: str, matricule: str) -> int:
        row = conn.execute('SELECT idUser FROM Utilisateurs WHERE matricule = ? LIMIT 1', (matricule,)).fetchone()
        if row:
            return int(row['idUser'])

        row = conn.execute('SELECT idUser FROM Utilisateurs WHERE nom = ? AND prenom = ? LIMIT 1', (nom, prenom)).fetchone()
        if row:
            return int(row['idUser'])

        cur = conn.execute('INSERT INTO Utilisateurs (nom, prenom, matricule) VALUES (?, ?, ?)', (nom, prenom, matricule))
        return int(cur.lastrowid)

    def _build_unique_matricule(self, conn: sqlite3.Connection, prenom: str, nom: str) -> str:
        base = (prenom[:1] + nom[:7]).upper().replace(' ', '') or 'USER'
        candidate = base
        index = 1
        while conn.execute('SELECT 1 FROM Utilisateurs WHERE matricule = ?', (candidate,)).fetchone():
            index += 1
            candidate = f'{base}{index}'
        return candidate

    def _get_or_create_category(self, conn: sqlite3.Connection, category: str) -> int:
        category = category.strip()
        authorized_category = CATEGORY_BY_LOWER_NAME.get(category.lower())
        if authorized_category is None:
            raise ValueError(f"Catégorie non autorisée : {category}")

        row = conn.execute('SELECT idCat FROM Categories WHERE nomCat = ?', (authorized_category,)).fetchone()
        if row:
            return int(row['idCat'])
        cur = conn.execute('INSERT INTO Categories (nomCat) VALUES (?)', (authorized_category,))
        return int(cur.lastrowid)

    def _get_or_create_keyword(self, conn: sqlite3.Connection, keyword: str) -> int:
        keyword = keyword.strip()
        row = conn.execute('SELECT idMot FROM MotsCles WHERE mot = ?', (keyword,)).fetchone()
        if row:
            return int(row['idMot'])
        cur = conn.execute('INSERT INTO MotsCles (mot) VALUES (?)', (keyword,))
        return int(cur.lastrowid)

    @staticmethod
    def _split_values(value: str) -> list[str]:
        return [item.strip() for item in value.split(';') if item.strip()]


def build_repository(project_root: str | Path) -> SQLiteRepository:
    project_root = Path(project_root)
    return SQLiteRepository(
        db_path=project_root / 'data' / 'documents.db',
        schema_path=project_root / 'data' / 'schema_documents_sqlite.sql',
        project_root=project_root,
    )
