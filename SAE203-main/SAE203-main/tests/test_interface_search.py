import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from src.database import build_repository
from src.interface import MainWindow
from src.logic import LogicService


class InterfaceSearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        repository = build_repository(PROJECT_ROOT)
        self.window = MainWindow(LogicService(repository), PROJECT_ROOT)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def table_titles(self):
        return [
            self.window.table.item(row, 0).text()
            for row in range(self.window.table.rowCount())
        ]

    def table_authors(self):
        return [
            self.window.table.item(row, 1).text()
            for row in range(self.window.table.rowCount())
        ]

    def table_dates(self):
        return [
            self.window.table.item(row, 2).text()
            for row in range(self.window.table.rowCount())
        ]

    def check_category(self, category):
        model = self.window.search_categories._items_model
        for row in range(model.rowCount()):
            item = model.item(row)
            if item.text() == category:
                item.setCheckState(Qt.CheckState.Checked)
                self.window.search_categories._update_display_text()
                return
        self.fail(f"Catégorie introuvable dans l'interface : {category}")

    def test_chargement_initial(self):
        self.assertEqual(self.window.table.rowCount(), 0)

    def test_recherche_sans_filtre_affiche_tous_les_documents(self):
        self.window.rechercherDocuments()

        self.assertEqual(self.window.table.rowCount(), 12)
        self.assertEqual(self.window.table.item(0, 2).text(), "2026-04-18")

    def test_recherche_simple_par_titre(self):
        self.window.search_titre.setText("contrat")
        self.window.rechercherDocuments()

        self.assertEqual(self.window.table.rowCount(), 1)
        self.assertEqual(self.table_titles(), ["Contrat de stage - exemple"])

    def test_combinaison_de_filtres(self):
        self.window.search_auteur.setText("Fabien")
        self.check_category("Rapport")
        self.window.rechercherDocuments()

        self.assertEqual(self.window.table.rowCount(), 1)
        self.assertEqual(self.table_titles(), ["Rapport activite reseau"])

    def test_reinitialisation(self):
        self.window.search_titre.setText("contrat")
        self.window.rechercherDocuments()
        self.assertEqual(self.window.table.rowCount(), 1)

        self.window.reinitialiserRecherche()

        self.assertEqual(self.window.table.rowCount(), 0)
        self.assertEqual(self.window.search_titre.text(), "")
        self.assertEqual(self.window.search_auteur.text(), "")
        self.assertEqual(self.window.search_mots_cles.text(), "")
        self.assertEqual(self.window.search_categories.checked_items(), [])
        self.assertEqual(self.window.search_sort_by.currentData(), "date")
        self.assertEqual(self.window.search_sort_order.currentData(), "desc")

    def test_tri_par_date_decroissante_par_defaut(self):
        self.window.rechercherDocuments()

        self.assertEqual(self.window.search_sort_by.currentData(), "date")
        self.assertEqual(self.window.search_sort_order.currentData(), "desc")
        self.assertEqual(self.table_dates()[0], "2026-04-18")
        self.assertEqual(self.table_dates()[-1], "2026-04-01")

    def test_tri_par_date_croissante(self):
        self.window.search_sort_order.setCurrentIndex(1)
        self.window.rechercherDocuments()

        self.assertEqual(self.table_dates()[0], "2026-04-01")
        self.assertEqual(self.table_dates()[-1], "2026-04-18")

    def test_tri_par_titre_croissant_et_decroissant(self):
        self.window.search_sort_by.setCurrentIndex(1)
        self.window.search_sort_order.setCurrentIndex(1)
        self.window.rechercherDocuments()
        self.assertEqual(self.table_titles()[0], "Bilan mensuel avril")

        self.window.search_sort_order.setCurrentIndex(0)
        self.window.rechercherDocuments()
        self.assertEqual(self.table_titles()[0], "Rapport activite reseau")

    def test_tri_par_auteur_croissant_et_decroissant(self):
        self.window.search_sort_by.setCurrentIndex(2)
        self.window.search_sort_order.setCurrentIndex(1)
        self.window.rechercherDocuments()
        self.assertEqual(self.table_authors()[0], "Fabien AMOURANI")

        self.window.search_sort_order.setCurrentIndex(0)
        self.window.rechercherDocuments()
        self.assertEqual(self.table_authors()[0], "Lucas MOUNIAMA")

    def test_tri_apres_recherche_simple(self):
        self.window.search_titre.setText("de")
        self.window.search_sort_by.setCurrentIndex(1)
        self.window.search_sort_order.setCurrentIndex(1)
        self.window.rechercherDocuments()

        self.assertEqual(self.window.table.rowCount(), 4)
        self.assertEqual(self.table_titles()[0], "Contrat de stage - exemple")
        self.assertEqual(self.window.search_titre.text(), "de")

    def test_tri_apres_recherche_multicritere(self):
        self.window.search_auteur.setText("Manon")
        self.check_category("Projet")
        self.window.search_sort_by.setCurrentIndex(1)
        self.window.search_sort_order.setCurrentIndex(0)
        self.window.rechercherDocuments()

        self.assertEqual(self.window.table.rowCount(), 2)
        self.assertEqual(
            self.table_titles(),
            ["Planning de deploiement", "Bilan mensuel avril"],
        )
        self.assertEqual(self.window.search_auteur.text(), "Manon")
        self.assertEqual(self.window.search_categories.checked_items(), ["Projet"])


if __name__ == "__main__":
    unittest.main()
