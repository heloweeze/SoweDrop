import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from src.database import build_repository
from src.interface import MainWindow
from src.logic import LogicService


def main():
    # Prépare l'application, les services, la fenêtre principale, puis lance la boucle Qt.
    project_root = Path(__file__).resolve().parent
    app = QApplication(sys.argv)

    repository = build_repository(project_root)
    logic_service = LogicService(repository)

    window = MainWindow(logic_service, project_root)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
