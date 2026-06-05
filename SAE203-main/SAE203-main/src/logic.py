from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QRadioButton, QButtonGroup, QCheckBox, 
                             QSpinBox, QPushButton, QFrame)
from PyQt6.QtCore import Qt

from src.categories import AUTHORIZED_CATEGORIES, CATEGORY_BY_LOWER_NAME


class LogicError(Exception):
    """Erreur métier générique."""


class ValidationError(LogicError):
    """Erreur levée quand une donnée d'entrée est invalide."""


class NotFoundError(LogicError):
    """Erreur levée lorsqu'un document n'existe pas."""


class PermissionError(LogicError):
    """Erreur levée lorsqu'un utilisateur n'a pas les droits nécessaires."""


@dataclass
class DocumentInput:
    """Données nécessaires pour créer un document."""

    titre: str
    auteur: str
    date_document: str | date
    ressource: str
    description: str = ""
    categories: list[str] = field(default_factory=list)
    mots_cles: list[str] = field(default_factory=list)
    user_id: int | None = None
    stockage: str = "local"  # local | partage
    chemin_fichier: str | None = None
    type_fichier: str = ""


@dataclass
class SearchFilters:
    """Filtres de recherche multicritère."""

    titre: str = ""
    auteur: str = ""
    categories: list[str] = field(default_factory=list)
    mots_cles: list[str] = field(default_factory=list)
    date_min: str | date | None = None
    date_max: str | date | None = None
    ressource: str = ""
    sort_by: str = "date"     # date | titre | auteur
    sort_order: str = "desc"  # desc | asc


class DatabaseRepository(Protocol):
    """Contrat minimal attendu côté database.py."""

    def insert_document(self, document_data: dict[str, Any]) -> int:
        ...

    def link_categories_to_document(self, document_id: int, categories: list[str]) -> None:
        ...

    def list_categories(self) -> list[str]:
        ...

    def link_keywords_to_document(self, document_id: int, keywords: list[str]) -> None:
        ...

    def add_history(self, document_id: int, objet: str) -> None:
        ...

    def search_documents(self, prepared_filters: dict[str, Any]) -> list[dict[str, Any]]:
        ...

    def get_document_by_id(self, document_id: int) -> dict[str, Any] | None:
        ...

    def archive_document(self, document_id: int) -> None:
        ...

    def delete_document(self, document_id: int) -> None:
        ...

    def document_belongs_to_user(self, document_id: int, user_id: int) -> bool:
        ...


class LogicService:
    """
    Couche métier entre l'interface et la base de données.

    Responsabilités :
    - validation des données saisies
    - normalisation des valeurs
    - préparation des filtres de recherche
    - contrôle des droits simples
    - délégation à database.py pour l'accès SQLite
    """

    ALLOWED_SORT_FIELDS = {
        "date": "date_document",
        "titre": "titre",
        "auteur": "auteur",
    }
    ALLOWED_SORT_ORDER = {"asc", "desc"}
    ALLOWED_STORAGE = {"local", "partage"}
    STORAGE_ALIASES = {"shared": "partage"}

    def __init__(self, repository: DatabaseRepository):
        self.repository = repository

    def add_document(self, payload: DocumentInput) -> int:
        """Ajoute un document après validation métier."""
        normalized = self._validate_and_normalize_document(payload)

        document_id = self.repository.insert_document(
            {
                "titre": normalized.titre,
                "auteur": normalized.auteur,
                "date_document": self._date_to_iso(normalized.date_document),
                "ressource": normalized.ressource,
                "description": normalized.description,
                "user_id": normalized.user_id,
                "stockage": normalized.stockage,
                "chemin_fichier": normalized.chemin_fichier,
                "type_fichier": normalized.type_fichier,
            }
        )

        if normalized.categories:
            self.repository.link_categories_to_document(document_id, normalized.categories)

        if normalized.mots_cles:
            self.repository.link_keywords_to_document(document_id, normalized.mots_cles)

        self.repository.add_history(document_id, "Création du document")
        return document_id

    def list_categories(self) -> list[str]:
        """Retourne les catégories autorisées pour l'interface."""
        return list(AUTHORIZED_CATEGORIES)

    def search_documents(self, filters: SearchFilters) -> list[dict[str, Any]]:
        """Prépare les filtres, délègue la recherche SQL et reformate le résultat."""
        prepared_filters = self._prepare_search_filters(filters)
        results = self.repository.search_documents(prepared_filters)
        return [self._format_document_result(doc) for doc in results]

    def get_document_details(self, document_id: int) -> dict[str, Any]:
        """Retourne les détails d'un document par son id."""
        if not isinstance(document_id, int) or document_id <= 0:
            raise ValidationError("Identifiant de document invalide.")

        document = self.repository.get_document_by_id(document_id)
        if document is None:
            raise NotFoundError("Document introuvable.")

        return self._format_document_result(document)

    def archive_document(self, document_id: int, user_id: int) -> None:
        """Archive un document si l'utilisateur en est propriétaire."""
        self._check_document_permission(document_id, user_id)
        self.repository.archive_document(document_id)
        self.repository.add_history(document_id, "Archivage du document")

    def delete_document(self, document_id: int) -> None:
        """Supprime un document après validation de son identifiant."""
        if not isinstance(document_id, int) or document_id <= 0:
            raise ValidationError("Identifiant de document invalide.")
        self.repository.delete_document(document_id)

    def _validate_and_normalize_document(self, payload: DocumentInput) -> DocumentInput:
        """Nettoie et valide les données avant insertion."""
        titre = self._clean_text(payload.titre)
        auteur = self._clean_text(payload.auteur)
        ressource = self._clean_text(payload.ressource)
        description = self._clean_text(payload.description, allow_empty=True)
        type_fichier = self._clean_text(payload.type_fichier, allow_empty=True)

        stockage_raw = self._clean_text(payload.stockage).lower()
        stockage = self.STORAGE_ALIASES.get(stockage_raw, stockage_raw)

        if not titre:
            raise ValidationError("Le titre est obligatoire.")
        if not auteur:
            raise ValidationError("L'auteur est obligatoire.")
        if not ressource:
            raise ValidationError("La ressource est obligatoire.")
        if stockage not in self.ALLOWED_STORAGE:
            raise ValidationError("Le mode de stockage doit être 'local' ou 'partage'.")

        parsed_date = self._parse_date(payload.date_document)
        if parsed_date is None:
            raise ValidationError(
                "La date du document est obligatoire et doit être valide (YYYY-MM-DD)."
            )

        categories = self._normalize_authorized_categories(payload.categories)
        mots_cles = self._normalize_string_list(payload.mots_cles)

        return DocumentInput(
            titre=titre,
            auteur=auteur,
            date_document=parsed_date,
            ressource=ressource,
            description=description,
            categories=categories,
            mots_cles=mots_cles,
            user_id=payload.user_id,
            stockage=stockage,
            chemin_fichier=payload.chemin_fichier,
            type_fichier=type_fichier,
        )

    def _prepare_search_filters(self, filters: SearchFilters) -> dict[str, Any]:
        """Transforme les filtres de l'interface en paramètres utilisables par database.py."""
        # Chaque champ est nettoyé ici pour garder l'interface simple.
        titre = self._clean_text(filters.titre, allow_empty=True)
        auteur = self._clean_text(filters.auteur, allow_empty=True)
        ressource = self._clean_text(filters.ressource, allow_empty=True)
        # Les catégories sont validées contre la liste officielle du projet.
        categories = self._normalize_authorized_categories(filters.categories)
        mots_cles = self._normalize_string_list(filters.mots_cles)

        # Les dates vides sont ignorées, les dates mal formées sont refusées.
        date_min = self._parse_optional_search_date(filters.date_min, "La date minimale")
        date_max = self._parse_optional_search_date(filters.date_max, "La date maximale")

        if date_min and date_max and date_min > date_max:
            raise ValidationError(
                "La date minimale ne peut pas être supérieure à la date maximale."
            )

        sort_by = filters.sort_by.lower().strip() if filters.sort_by else "date"
        if sort_by not in self.ALLOWED_SORT_FIELDS:
            sort_by = "date"

        # Fallback de tri : une valeur inconnue revient sur l'ordre par défaut.
        sort_order = filters.sort_order.lower().strip() if filters.sort_order else "desc"
        if sort_order not in self.ALLOWED_SORT_ORDER:
            sort_order = "desc"

        return {
            "titre_like": titre or None,
            "auteur_like": auteur or None,
            "ressource_like": ressource or None,
            "categories_exact_or": categories or [],
            "mots_cles_like_or": mots_cles or [],
            "date_min": self._date_to_iso(date_min) if date_min else None,
            "date_max": self._date_to_iso(date_max) if date_max else None,
            "sort_column": self.ALLOWED_SORT_FIELDS[sort_by],
            "sort_order": sort_order,
        }

    def _format_document_result(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Uniformise le format retourné à l'interface."""
        auteur = doc.get("auteur")
        if not auteur:
            nom = doc.get("auteur_nom", "")
            prenom = doc.get("auteur_prenom", "")
            auteur = f"{prenom} {nom}".strip() or nom or prenom

        return {
            "id": doc.get("id") or doc.get("idDoc"),
            "user_id": doc.get("user_id") or doc.get("idUser"),
            "titre": doc.get("titre", ""),
            "auteur": auteur,
            "description": doc.get("description", ""),
            "date": doc.get("date_document") or doc.get("date", ""),
            "categorie": doc.get("categorie") or doc.get("categories") or [],
            "ressource": doc.get("ressource", ""),
            "mots_cles": doc.get("mots_cles") or [],
            "chemin_fichier": doc.get("chemin_fichier") or doc.get("ressource"),
            "stockage": doc.get("stockage"),
            "type_fichier": doc.get("type_fichier"),
            "statut": doc.get("statut"),
        }

    def _check_document_permission(self, document_id: int, user_id: int) -> None:
        """Vérifie qu'un utilisateur peut modifier/supprimer un document."""
        if not isinstance(document_id, int) or document_id <= 0:
            raise ValidationError("Identifiant de document invalide.")
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValidationError("Identifiant utilisateur invalide.")

        if not self.repository.document_belongs_to_user(document_id, user_id):
            raise PermissionError(
                "Vous ne pouvez pas modifier ou supprimer un document qui ne vous appartient pas."
            )

    @staticmethod
    def _clean_text(value: Any, allow_empty: bool = False) -> str:
        """Nettoie une valeur texte en supprimant les espaces inutiles."""
        if value is None:
            return "" if allow_empty else ""

        text = str(value).strip()
        if not text and not allow_empty:
            return ""
        return text

    @staticmethod
    def _normalize_string_list(values: list[str] | str | None) -> list[str]:
        """Normalise une liste de chaînes et supprime les doublons."""
        if values is None:
            return []

        raw_items = values.split(",") if isinstance(values, str) else values
        cleaned: list[str] = []
        seen: set[str] = set()

        for item in raw_items:
            text = str(item).strip()
            if not text:
                continue

            lowered = text.lower()
            if lowered in seen:
                continue

            seen.add(lowered)
            cleaned.append(text)

        return cleaned

    def _normalize_authorized_categories(self, values: list[str] | str | None) -> list[str]:
        categories = self._normalize_string_list(values)
        normalized: list[str] = []
        unknown: list[str] = []

        # On conserve l'écriture officielle des catégories, même si l'utilisateur change la casse.
        for category in categories:
            authorized_category = CATEGORY_BY_LOWER_NAME.get(category.lower())
            if authorized_category is None:
                unknown.append(category)
                continue
            normalized.append(authorized_category)

        if unknown:
            raise ValidationError(
                "Catégorie non autorisée : " + ", ".join(unknown)
            )

        return normalized

    @staticmethod
    def _parse_date(value: str | date | None) -> date | None:
        """Convertit une date au format YYYY-MM-DD vers un objet date."""
        if value is None:
            return None
        if isinstance(value, date):
            return value

        text = str(value).strip()
        if not text:
            return None

        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _parse_optional_search_date(self, value: str | date | None, label: str) -> date | None:
        # Pour la recherche, une date vide signifie simplement "pas de filtre".
        if value is None:
            return None

        if isinstance(value, str) and not value.strip():
            return None

        parsed_date = self._parse_date(value)
        if parsed_date is None:
            raise ValidationError(f"{label} doit être valide (YYYY-MM-DD).")

        return parsed_date

    @staticmethod
    def _date_to_iso(value: date | None) -> str | None:
        """Retourne une date au format ISO YYYY-MM-DD."""
        return value.isoformat() if value else None
    

# preferences.py
class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paramètres de l'application")
        self.setFixedWidth(450)
        
        layout = QVBoxLayout(self)
        
        # --- SECTION 1 : APPARENCE (Boutons Radio) ---
        layout.addWidget(QLabel("<b>Apparence & Thème</b>"))
        
        # Groupe pour les boutons radio (pour qu'un seul soit sélectionné à la fois)
        self.theme_group = QButtonGroup(self)
        
        theme_layout = QHBoxLayout()
        self.radio_clair = QRadioButton("Mode Clair")
        self.radio_sombre = QRadioButton("Mode Sombre")
        
        # Par défaut, on coche le mode sombre car ton appli l'est déjà (vu sur ta capture)
        self.radio_sombre.setChecked(True) 
        
        self.theme_group.addButton(self.radio_clair)
        self.theme_group.addButton(self.radio_sombre)
        
        theme_layout.addWidget(self.radio_clair)
        theme_layout.addWidget(self.radio_sombre)
        layout.addLayout(theme_layout)
        
        # Petite ligne de séparation visuelle
        layout.addWidget(self.creer_separation())
        
        # --- SECTION 2 : ACCESSIBILITÉ ---
        layout.addWidget(QLabel("<b>Accessibilité</b>"))
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Taille de la police globale :"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 15)
        self.font_size_spin.setValue(10) # Valeur par défaut
        self.font_size_spin.setSuffix(" pt")
        font_layout.addWidget(self.font_size_spin)
        layout.addLayout(font_layout)
        
        layout.addWidget(self.creer_separation())
        
        # --- SECTION 3 : COMPORTEMENT ---
        layout.addWidget(QLabel("<b>Comportement & Sécurité</b>"))
        self.check_remember = QCheckBox("Restaurer les documents ouverts au démarrage")
        self.check_confirm = QCheckBox("Demander confirmation avant de supprimer un document")
        self.check_confirm.setChecked(True)
        
        layout.addWidget(self.check_remember)
        layout.addWidget(self.check_confirm)
        
        layout.addWidget(self.creer_separation())
        
        # --- BOUTONS DE SÉLECTION FINALE ---
        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Annuler")
        self.btn_save = QPushButton("Enregistrer")
        self.btn_save.setStyleSheet("background-color: #2980b9;")
        
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

    def creer_separation(self):
        """ Crée une ligne grise discrète pour séparer les sections """
        ligne = QFrame()
        
        # CORRECTION ICI : Utilisez QFrame.Shape.HLine et QFrame.Shadow.Sunken
        ligne.setFrameShape(QFrame.Shape.HLine)
        ligne.setFrameShadow(QFrame.Shadow.Sunken)
        
        ligne.setStyleSheet("background-color: #444; ")
        return ligne

    def get_preferences(self):
        """ Récupère les choix pour les envoyer à la page principale """
        theme_choisi = "Sombre" if self.radio_sombre.isChecked() else "Clair"
        return {
            "theme": theme_choisi,
            "taille_police": self.font_size_spin.value(),
            "restaurer_session": self.check_remember.isChecked(),
            "confirmer_suppression": self.check_confirm.isChecked()
        }
