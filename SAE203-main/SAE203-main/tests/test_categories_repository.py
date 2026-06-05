import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database import SQLiteRepository


class CategoriesRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "documents.db"
        self.repository = SQLiteRepository(
            self.db_path,
            PROJECT_ROOT / "data" / "schema_documents_sqlite.sql",
            PROJECT_ROOT,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_categorie_inconnue_refusee_par_le_repository(self):
        document = self.repository.search_documents(
            {"titre_like": "contrat", "sort_column": "date_document", "sort_order": "desc"}
        )[0]

        with self.assertRaises(ValueError):
            self.repository.link_categories_to_document(
                document["idDoc"],
                ["Categorie inconnue"],
            )


if __name__ == "__main__":
    unittest.main()
