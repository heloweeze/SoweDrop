import os
import platform
import shutil
import subprocess
from pathlib import Path

# Éléments d'interface
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Logique de base et signaux
from PyQt6.QtCore import QDate, QEvent, Qt

# Pour le visuel
from PyQt6.QtGui import QAction, QIcon, QStandardItem, QStandardItemModel

from src.database import build_repository
from src.logic import (
    DocumentInput,
    LogicService,
    PreferencesDialog,
    SearchFilters,
    ValidationError,
)
from src.sftp_storage import SftpStorage, SftpStorageError, is_sftp_resource


class CheckableComboBox(QComboBox):
    """Menu déroulant permettant de cocher plusieurs catégories."""

    def __init__(self, placeholder, parent=None):
        super().__init__(parent)
        self.placeholder = placeholder
        self._items_model = QStandardItemModel(self)
        self.setModel(self._items_model)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.lineEdit().setReadOnly(True)
        self.view().viewport().installEventFilter(self)
        self._update_display_text()

    def add_checkable_items(self, values):
        for value in values:
            item = QStandardItem(value)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
            item.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
            self._items_model.appendRow(item)
        self._update_display_text()

    def checked_items(self):
        checked = []
        for row in range(self._items_model.rowCount()):
            item = self._items_model.item(row)
            if item and item.checkState() == Qt.CheckState.Checked:
                checked.append(item.text())
        return checked

    def clear_checked_items(self):
        for row in range(self._items_model.rowCount()):
            item = self._items_model.item(row)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self._update_display_text()

    def eventFilter(self, watched, event):
        if watched == self.view().viewport():
            if event.type() == QEvent.Type.MouseButtonPress:
                return True
            if event.type() == QEvent.Type.MouseButtonRelease:
                index = self.view().indexAt(event.position().toPoint())
                if index.isValid():
                    self._toggle_item(index)
                return True
        return super().eventFilter(watched, event)

    def _toggle_item(self, index):
        item = self._items_model.itemFromIndex(index)
        if not item:
            return
        new_state = (
            Qt.CheckState.Unchecked
            if item.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        item.setCheckState(new_state)
        self._update_display_text()

    def _update_display_text(self):
        checked = self.checked_items()
        self.lineEdit().setText(", ".join(checked) if checked else self.placeholder)


class AddDocumentDialog(QDialog):
    def __init__(self, parent=None, categories=None):
        super().__init__(parent)
        self.setWindowTitle("Ajouter un document")
        self.setFixedWidth(400)
        self.selected_file = None

        layout = QVBoxLayout(self)

        header = QLabel("Informations sur le nouveau document")
        header.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        layout.addWidget(header)

        form = QFormLayout()

        self.titre_input = QLineEdit()
        self.titre_input.setPlaceholderText("Saisissez le titre...")

        self.auteur_input = QLineEdit()
        self.auteur_input.setPlaceholderText("Saisissez l'auteur...")

        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")

        self.stockage_input = QComboBox()
        self.stockage_input.addItems(["local", "partage"])

        self.cat_input = CheckableComboBox("Sélectionner des catégories")
        self.cat_input.add_checkable_items(categories or ["Rapport", "Projet", "Technique"])

        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Saisissez la description...")
        self.desc_input.setMinimumHeight(150)

        self.file_label = QLabel("Aucun fichier sélectionné")
        self.file_button = QPushButton("Sélectionner un fichier")
        self.file_button.clicked.connect(self.select_file)

        form.addRow("Titre :", self.titre_input)
        form.addRow("Auteur :", self.auteur_input)
        form.addRow("Date :", self.date_input)
        form.addRow("Stockage :", self.stockage_input)
        form.addRow("Catégories :", self.cat_input)
        form.addRow("Description :", self.desc_input)
        form.addRow(self.file_button, self.file_label)
        layout.addLayout(form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Ajouter")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_data(self):
        return {
            "titre": self.titre_input.text(),
            "auteur": self.auteur_input.text(),
            "date": self.date_input.date().toString("yyyy-MM-dd"),
            "stockage": self.stockage_input.currentText(),
            "categories": self.cat_input.checked_items(),
            "description": self.desc_input.toPlainText(),
            "fichier": self.selected_file,
        }

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir un document à ajouter",
            "",
            "Documents (*.pdf *.doc *.docx *.xls *.xlsx);;Tous les fichiers (*)",
        )
        if not file_path:
            return

        self.selected_file = file_path
        self.file_label.setText(Path(file_path).name)

        if not self.titre_input.text().strip():
            self.titre_input.setText(Path(file_path).stem.replace("_", " ").strip())


class MainWindow(QMainWindow):
    def __init__(self, logic_service=None, project_root=None):
        super().__init__()

        self.project_root = Path(project_root or Path(__file__).resolve().parent.parent)
        self.logic = logic_service or LogicService(build_repository(self.project_root))

        self.setWindowTitle("SoweDrop")
        self.setWindowIcon(QIcon("pouce.png"))
        self.resize(1100, 700)

        self.createActions()
        self.createMenuBar()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)

        self.creerFiltresRecherche(left_layout)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Titre", "Auteur", "Date", "Catégorie"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)

        left_layout.addWidget(self.table)
        main_layout.addWidget(left_container, stretch=4)

        right_panel = QWidget()
        right_panel.setStyleSheet("border-left: 1px solid #ddd;")
        right_layout = QVBoxLayout(right_panel)

        self.details = QLabel("Fiche Détails")
        self.details.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 10px;")
        self.details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.details)

        self.info_titre = QLabel("Titre : -")
        self.info_auteur = QLabel("Auteur : -")
        self.info_date = QLabel("Date : -")
        self.info_cat = QLabel("Catégorie : -")
        self.info_ressource = QLabel("Ressource : -")
        self.info_mots_cles = QLabel("Mots-clés : -")
        self.info_ressource.setWordWrap(True)
        self.info_mots_cles.setWordWrap(True)

        for label in [
            self.info_titre,
            self.info_auteur,
            self.info_date,
            self.info_cat,
            self.info_ressource,
            self.info_mots_cles,
        ]:
            right_layout.addWidget(label)

        right_layout.addWidget(QLabel("<b>Description :</b>"))
        self.desc_box = QTextEdit()
        self.desc_box.setReadOnly(True)
        right_layout.addWidget(self.desc_box)
        right_layout.addStretch()

        btn_layout = QHBoxLayout()
        self.btn_ouvrir = QPushButton("Ouvrir")
        self.btn_telecharger = QPushButton("Télécharger")
        btn_layout.addWidget(self.btn_ouvrir)
        btn_layout.addWidget(self.btn_telecharger)
        right_layout.addLayout(btn_layout)

        self.table.itemClicked.connect(self.afficherDetails)
        self.table.customContextMenuRequested.connect(self.afficherMenuContextuelDocument)
        self.btn_ouvrir.clicked.connect(self.ouvrirDocumentSelectionne)
        self.btn_telecharger.clicked.connect(self.telechargerDocument)

        main_layout.addWidget(right_panel, stretch=2)
        self.afficherTableauVide()

    def afficherMenuContextuelDocument(self, position):
        menu = self.creerMenuContextuelDocument(position)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def creerMenuContextuelDocument(self, position):
        index = self.table.indexAt(position)
        menu = QMenu(self)

        if index.isValid():
            self.table.selectRow(index.row())
            self.afficherDetails(self.table.item(index.row(), 0))

            action_ouvrir = menu.addAction("Ouvrir")
            action_telecharger = menu.addAction("Télécharger")
            action_supprimer = menu.addAction("Supprimer")
            action_copier_ressource = menu.addAction("Copier le chemin de la ressource")

            action_ouvrir.triggered.connect(self.ouvrirDocumentSelectionne)
            action_telecharger.triggered.connect(self.telechargerDocument)
            action_supprimer.triggered.connect(self.deleteDocument)
            action_copier_ressource.triggered.connect(self.copierCheminRessourceSelectionne)
            menu.addSeparator()
        else:
            self.table.clearSelection()
            self.table.setCurrentCell(-1, -1)
            self.viderDetails()

        action_ajouter = menu.addAction("Ajouter un document")
        action_ajouter.triggered.connect(self.importDocument)
        return menu

    def creerFiltresRecherche(self, parent_layout):
        parent_layout.addWidget(QLabel("Recherche multicritère"))

        ligne_principale = QHBoxLayout()
        self.search_titre = QLineEdit()
        self.search_titre.setPlaceholderText("Titre")
        self.search_auteur = QLineEdit()
        self.search_auteur.setPlaceholderText("Auteur")
        self.search_mots_cles = QLineEdit()
        self.search_mots_cles.setPlaceholderText("Mots-clés, séparés par virgules")
        ligne_principale.addWidget(self.search_titre)
        ligne_principale.addWidget(self.search_auteur)
        ligne_principale.addWidget(self.search_mots_cles)
        parent_layout.addLayout(ligne_principale)

        ligne_secondaire = QHBoxLayout()
        self.search_categories = CheckableComboBox("Toutes les catégories")
        self.search_categories.add_checkable_items(self.logic.list_categories())
        ligne_secondaire.addWidget(self.search_categories)
        parent_layout.addLayout(ligne_secondaire)

        ligne_dates = QHBoxLayout()
        self.search_date_min_active = QCheckBox("Date min")
        self.search_date_min = QDateEdit(QDate.currentDate().addYears(-1))
        self.search_date_min.setCalendarPopup(True)
        self.search_date_min.setDisplayFormat("yyyy-MM-dd")
        self.search_date_min.setEnabled(False)

        self.search_date_max_active = QCheckBox("Date max")
        self.search_date_max = QDateEdit(QDate.currentDate())
        self.search_date_max.setCalendarPopup(True)
        self.search_date_max.setDisplayFormat("yyyy-MM-dd")
        self.search_date_max.setEnabled(False)

        self.btn_rechercher = QPushButton("Rechercher")
        self.btn_reset_search = QPushButton("Réinitialiser")

        ligne_dates.addWidget(self.search_date_min_active)
        ligne_dates.addWidget(self.search_date_min)
        ligne_dates.addWidget(self.search_date_max_active)
        ligne_dates.addWidget(self.search_date_max)
        ligne_dates.addStretch()
        ligne_dates.addWidget(self.btn_rechercher)
        ligne_dates.addWidget(self.btn_reset_search)
        parent_layout.addLayout(ligne_dates)

        ligne_tri = QHBoxLayout()
        ligne_tri.addWidget(QLabel("Trier par :"))
        self.search_sort_by = QComboBox()
        self.search_sort_by.addItem("Date", "date")
        self.search_sort_by.addItem("Titre", "titre")
        self.search_sort_by.addItem("Auteur", "auteur")

        self.search_sort_order = QComboBox()
        self.search_sort_order.addItem("Décroissant", "desc")
        self.search_sort_order.addItem("Croissant", "asc")

        ligne_tri.addWidget(self.search_sort_by)
        ligne_tri.addWidget(QLabel("Ordre :"))
        ligne_tri.addWidget(self.search_sort_order)
        ligne_tri.addStretch()
        parent_layout.addLayout(ligne_tri)

        self.search_date_min_active.toggled.connect(self.search_date_min.setEnabled)
        self.search_date_max_active.toggled.connect(self.search_date_max.setEnabled)
        self.btn_rechercher.clicked.connect(self.rechercherDocuments)
        self.btn_reset_search.clicked.connect(self.reinitialiserRecherche)
        self.search_sort_by.currentIndexChanged.connect(self.rechercherDocuments)
        self.search_sort_order.currentIndexChanged.connect(self.rechercherDocuments)

        for champ in (self.search_titre, self.search_auteur, self.search_mots_cles):
            champ.returnPressed.connect(self.rechercherDocuments)

    def chargerDocuments(self):
        self.chargerDocumentsAvecFiltres(SearchFilters())

    def afficherTableauVide(self):
        self.afficherDocuments([])

    def chargerDocumentsAvecFiltres(self, filters, afficher_message_aucun=False):
        try:
            documents = self.logic.search_documents(filters)
            self.afficherDocuments(documents)
            if afficher_message_aucun and not documents:
                QMessageBox.information(self, "Recherche", "Aucun document trouvé")
        except ValidationError as exc:
            QMessageBox.warning(self, "Validation", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Erreur", f"Impossible de charger les documents : {exc}")

    def afficherDocuments(self, documents):
        self.table.setRowCount(0)
        self.table.clearSelection()
        self.viderDetails()

        for document in documents:
            row = self.table.rowCount()
            self.table.insertRow(row)

            categories = ", ".join(document.get("categorie") or []) or "-"
            valeurs = [
                document.get("titre", ""),
                document.get("auteur", ""),
                document.get("date", ""),
                categories,
            ]

            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(str(valeur))
                item.setData(Qt.ItemDataRole.UserRole, document)
                self.table.setItem(row, col, item)

    def construireFiltresRecherche(self):
        return SearchFilters(
            titre=self.search_titre.text(),
            auteur=self.search_auteur.text(),
            categories=self.search_categories.checked_items(),
            mots_cles=self.search_mots_cles.text(),
            date_min=(
                self.search_date_min.date().toString("yyyy-MM-dd")
                if self.search_date_min_active.isChecked()
                else None
            ),
            date_max=(
                self.search_date_max.date().toString("yyyy-MM-dd")
                if self.search_date_max_active.isChecked()
                else None
            ),
            sort_by=self.search_sort_by.currentData(),
            sort_order=self.search_sort_order.currentData(),
        )

    def rechercherDocuments(self):
        self.chargerDocumentsAvecFiltres(
            self.construireFiltresRecherche(),
            afficher_message_aucun=True,
        )

    def reinitialiserRecherche(self):
        self.search_titre.clear()
        self.search_auteur.clear()
        self.search_mots_cles.clear()
        self.search_categories.clear_checked_items()
        self.search_date_min_active.setChecked(False)
        self.search_date_max_active.setChecked(False)
        self.search_date_min.setEnabled(False)
        self.search_date_max.setEnabled(False)

        sort_by_was_blocked = self.search_sort_by.blockSignals(True)
        sort_order_was_blocked = self.search_sort_order.blockSignals(True)
        self.search_sort_by.setCurrentIndex(0)
        self.search_sort_order.setCurrentIndex(0)
        self.search_sort_by.blockSignals(sort_by_was_blocked)
        self.search_sort_order.blockSignals(sort_order_was_blocked)

        self.afficherTableauVide()

    def viderDetails(self):
        self.info_titre.setText("Titre : -")
        self.info_auteur.setText("Auteur : -")
        self.info_date.setText("Date : -")
        self.info_cat.setText("Catégorie : -")
        self.info_ressource.setText("Ressource : -")
        self.info_mots_cles.setText("Mots-clés : -")
        self.desc_box.clear()

    def documentSelectionne(self):
        current_row = self.table.currentRow()
        if current_row == -1:
            return None

        item = self.table.item(current_row, 0)
        if not item:
            return None

        document = item.data(Qt.ItemDataRole.UserRole)
        return document if isinstance(document, dict) else None

    def cheminDocumentSelectionne(self):
        """
        Retourne un chemin local utilisable par l'application.

        Si la ressource est SFTP, le fichier est d'abord téléchargé dans
        data/documents/cache/ puis ce chemin local est retourné.
        """
        document = self.documentSelectionne()
        if not document:
            return None

        ressource = document.get("chemin_fichier") or document.get("ressource")
        if not ressource:
            return None

        if is_sftp_resource(ressource):
            remote_path = ressource.replace("sftp:", "", 1)
            filename = Path(remote_path).name
            cache_dir = self.project_root / "data" / "documents" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            local_cache_path = cache_dir / filename

            sftp_storage = SftpStorage.from_project(self.project_root)
            sftp_storage.download_file(ressource, local_cache_path)
            return local_cache_path

        chemin = Path(ressource)
        if not chemin.is_absolute():
            chemin = self.project_root / chemin

        legacy_data_path = self.project_root / "data" / ressource
        if not chemin.exists() and legacy_data_path.exists():
            chemin = legacy_data_path

        return chemin

    def copierCheminRessourceSelectionne(self):
        document = self.documentSelectionne()
        if not document:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner un document.")
            return

        ressource = document.get("ressource") or document.get("chemin_fichier")
        if not ressource:
            QMessageBox.warning(self, "Erreur", "Aucun chemin de ressource disponible.")
            return

        QApplication.clipboard().setText(str(ressource))
        self.statusBar().showMessage("Chemin de la ressource copié", 3000)

    def afficherDetails(self, item):
        row = item.row()
        titre = self.table.item(row, 0).text() if self.table.item(row, 0) else "-"
        auteur = self.table.item(row, 1).text() if self.table.item(row, 1) else "-"
        date = self.table.item(row, 2).text() if self.table.item(row, 2) else "-"
        cat = self.table.item(row, 3).text() if self.table.item(row, 3) else "-"

        self.info_titre.setText(f"Titre : {titre}")
        self.info_auteur.setText(f"Auteur : {auteur}")
        self.info_date.setText(f"Date : {date}")
        self.info_cat.setText(f"Catégorie : {cat}")

        document = self.documentSelectionne()
        ressource = document.get("ressource") if document else ""
        mots_cles = ", ".join(document.get("mots_cles") or []) if document else ""
        description = document.get("description") if document else ""

        self.info_ressource.setText(f"Ressource : {ressource or '-'}")
        self.info_mots_cles.setText(f"Mots-clés : {mots_cles or '-'}")
        self.desc_box.setText(description or f"Aucune description pour : {titre}")

    def filtrerTableau(self):
        self.rechercherDocuments()

    def importDocument(self):
        dialog = AddDocumentDialog(self, self.logic.list_categories())

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()

            try:
                if not data["fichier"]:
                    raise ValidationError("Veuillez sélectionner un fichier.")
                if not data["titre"].strip():
                    raise ValidationError("Le titre est obligatoire.")
                if not data["auteur"].strip():
                    raise ValidationError("L'auteur est obligatoire.")

                relative_resource = self.copierFichierDansStockage(
                    data["fichier"],
                    data["stockage"],
                )

                suffix = Path(data["fichier"]).suffix.upper().lstrip(".")

                document_id = self.logic.add_document(
                    DocumentInput(
                        titre=data["titre"],
                        auteur=data["auteur"],
                        date_document=data["date"],
                        ressource=relative_resource,
                        description=data["description"],
                        categories=data["categories"],
                        stockage=data["stockage"],
                        chemin_fichier=relative_resource,
                        type_fichier=suffix,
                    )
                )

                QMessageBox.information(
                    self,
                    "Ajout",
                    f"Document ajouté avec succès (id {document_id}).",
                )
                self.chargerDocuments()

            except ValidationError as exc:
                QMessageBox.warning(self, "Validation", str(exc))
            except SftpStorageError as exc:
                QMessageBox.critical(self, "Erreur SFTP", str(exc))
            except Exception as exc:
                QMessageBox.critical(self, "Erreur", f"Impossible d'ajouter le document : {exc}")

    def copierFichierDansStockage(self, source_file, stockage):
        """
        Copie le fichier choisi dans le bon espace de stockage.

        - local : copie dans data/documents/local/
        - partage : upload sur le VPS en SFTP dans /commun
        """
        source = Path(source_file)

        if stockage == "partage":
            sftp_storage = SftpStorage.from_project(self.project_root)
            return sftp_storage.upload_file(source)

        target_dir = self.project_root / "data" / "documents" / stockage
        target_dir.mkdir(parents=True, exist_ok=True)

        target = target_dir / source.name

        if target.exists():
            stem = source.stem
            suffix = source.suffix
            index = 1
            while target.exists():
                target = target_dir / f"{stem}_{index}{suffix}"
                index += 1

        shutil.copy2(source, target)
        return str(target.relative_to(self.project_root)).replace("\\", "/")

    def ouvrirDocumentSelectionne(self):
        try:
            file_path = self.cheminDocumentSelectionne()
        except SftpStorageError as exc:
            QMessageBox.critical(self, "Erreur SFTP", str(exc))
            return

        if not file_path or not file_path.exists():
            QMessageBox.warning(self, "Erreur", "Fichier introuvable sur le disque.")
            return

        try:
            systeme = platform.system()
            if systeme == "Windows":
                os.startfile(str(file_path))
            elif systeme == "Darwin":
                subprocess.call(("open", str(file_path)))
            else:
                subprocess.call(("xdg-open", str(file_path)))
        except Exception as exc:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir le document : {exc}")

    def telechargerDocument(self):
        try:
            file_path = self.cheminDocumentSelectionne()
        except SftpStorageError as exc:
            QMessageBox.critical(self, "Erreur SFTP", str(exc))
            return

        if not file_path or not file_path.exists():
            QMessageBox.warning(self, "Erreur", "Fichier introuvable sur le disque.")
            return

        dest_path, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer sous",
            file_path.name,
        )
        if dest_path:
            shutil.copy(file_path, dest_path)
            QMessageBox.information(self, "Succès", "Fichier téléchargé/copié avec succès.")

    def createActions(self):
        self.actArchive = QAction("&Corbeille", self)
        self.actArchive.setShortcut("Ctrl+A")
        self.actArchive.setStatusTip("Archive des documents récemment effacés")

        self.actPref = QAction("&Préférences", self)
        self.actPref.setShortcut("Ctrl+P")
        self.actPref.setStatusTip("Préférences de l'utilisateur")
        self.actPref.triggered.connect(self.ouvrirPreferences)

        self.actExit = QAction("Quitter", self)
        self.actExit.setShortcut("Alt+F4")
        self.actExit.setStatusTip("Quitter")
        self.actExit.triggered.connect(self.quitApp)

        self.actExport = QAction("&Exporter", self)
        self.actExport.setShortcut("Ctrl+E")
        self.actExport.setStatusTip("Exporter le document")
        self.actExport.triggered.connect(self.exportDocument)

        self.actDelete = QAction("&Supprimer un document", self)
        self.actDelete.setShortcut("Ctrl+D")
        self.actDelete.setStatusTip("Supprimer le document sélectionné")
        self.actDelete.triggered.connect(self.deleteDocument)

        self.actImport = QAction("&Sélectionner un document...", self)
        self.actImport.setShortcut("Ctrl+O")
        self.actImport.setStatusTip("Importer un document depuis votre ordinateur")
        self.actImport.triggered.connect(self.importDocument)

        self.actGuide = QAction("&Guide utilisateur", self)
        self.actGuide.setShortcut("Ctrl+G")
        self.actGuide.setStatusTip("Guide utilisateur")

        self.actContact = QAction("&Contacter", self)
        self.actContact.setShortcut("Ctrl+M")
        self.actContact.setStatusTip("Contacter les développeurs")

    def createMenuBar(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("&Fichier")
        file_menu.addAction(self.actArchive)
        file_menu.addSeparator()
        file_menu.addAction(self.actPref)
        file_menu.addSeparator()
        file_menu.addAction(self.actExit)

        edition = menu.addMenu("&Édition")
        edition.addAction(self.actExport)
        edition.addSeparator()
        edition.addAction(self.actDelete)

        import_menu = menu.addMenu("&Importer")
        import_menu.addAction(self.actImport)

        help_menu = menu.addMenu("&Aide")
        help_menu.addAction(self.actGuide)
        help_menu.addSeparator()
        help_menu.addAction(self.actContact)

    def quitApp(self):
        self.close()

    def exportDocument(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Exportation", "Le tableau est vide !")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter les données",
            "export_donnees.txt",
            "Fichier Texte (*.txt);;Tous les fichiers (*)",
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    for row in range(self.table.rowCount()):
                        row_data = []
                        for col in range(self.table.columnCount()):
                            item = self.table.item(row, col)
                            row_data.append(item.text() if item else "")
                        f.write(" | ".join(row_data) + "\n")
            except Exception as exc:
                QMessageBox.critical(self, "Erreur", f"Impossible d'exporter : {exc}")

    def editDocument(self):
        print("Action : Modifier le document")

    def deleteDocument(self):
        document = self.documentSelectionne()
        if not document:
            QMessageBox.warning(self, "Attention", "Veuillez cliquer sur une ligne du tableau d'abord.")
            return

        document_id = document.get("id")
        if not document_id:
            QMessageBox.warning(self, "Erreur", "Impossible d'identifier le document sélectionné.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirmation",
            "Voulez-vous vraiment supprimer ce document ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            self.logic.delete_document(int(document_id))
            self.chargerDocuments()
            self.viderDetails()
        except Exception as exc:
            QMessageBox.critical(self, "Erreur", f"Impossible de supprimer le document : {exc}")

    def ouvrirPreferences(self):
        dialog = PreferencesDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            reglages = dialog.get_preferences()

            font = self.font()
            font.setPointSize(reglages["taille_police"])
            QApplication.instance().setFont(font)

            if reglages["theme"] == "Sombre":
                self.appliquer_theme_sombre()
            else:
                self.appliquer_theme_clair()

    def appliquer_theme_sombre(self):
        theme_sombre = """
        QMainWindow, QDialog, .QWidget {
            background-color: #1e1e1e;
            color: #ffffff;
        }
        QLabel, QRadioButton, QCheckBox {
            color: #ffffff;
        }
        QMenuBar {
            background-color: #1e1e1e;
            color: #ffffff;
        }
        QMenuBar::item:selected {
            background-color: #3d3d3d;
            color: #ffffff;
        }
        QMenu {
            background-color: #1e1e1e;
            color: #ffffff;
            border: 1px solid #3f3f46;
        }
        QMenu::item:selected {
            background-color: #2980b9;
            color: #ffffff;
        }
        QTableWidget {
            background-color: #252526;
            gridline-color: #3f3f46;
            color: #ffffff;
        }
        QHeaderView::section {
            background-color: #2d2d30;
            color: #ffffff;
            border: 1px solid #3f3f46;
        }
        QLineEdit, QTextEdit, QSpinBox, QComboBox {
            background-color: #2d2d30;
            color: #ffffff;
            border: 1px solid #555555;
            padding: 5px;
        }
        """
        QApplication.instance().setStyleSheet(theme_sombre)
        self.statusBar().showMessage("Mode Sombre activé", 3000)

    def appliquer_theme_clair(self):
        theme_clair = """
        QMainWindow, QDialog, .QWidget {
            background-color: #f5f5f5;
            color: #000000;
        }
        QLabel, QRadioButton, QCheckBox {
            color: #000000;
        }
        QMenuBar {
            background-color: #f5f5f5;
            color: #000000;
        }
        QMenuBar::item:selected {
            background-color: #e5e5e5;
            color: #000000;
        }
        QMenu {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #ccc;
        }
        QMenu::item:selected {
            background-color: #3498db;
            color: #ffffff;
        }
        QLineEdit, QTextEdit, QSpinBox, QComboBox {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #ccc;
            padding: 5px;
        }
        QTableWidget {
            background-color: #ffffff;
            gridline-color: #dcdcdc;
            color: #000000;
        }
        QHeaderView::section {
            background-color: #e5e5e5;
            color: #000000;
            border: 1px solid #dcdcdc;
        }
        """
        QApplication.instance().setStyleSheet(theme_clair)
        self.statusBar().showMessage("Mode Clair activé", 3000)
