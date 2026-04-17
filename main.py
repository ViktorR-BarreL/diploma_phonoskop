import os
import sys

# Оптимизация для CUDA и отрисовки
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from src.database import Database
from src.gui.start_window import StartWindow
from src.gui.main_window import MainWindow


class Application:
    def __init__(self):
        self.start_window = None
        self.main_window = None
        self.db = Database()
        
    def run(self):
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        self.register_demo_project() # Регистрируем демо-проект при каждом запуске (для тестирования и демонстрации)
        
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        
        self.show_start_window()
        
        sys.exit(app.exec())

    def show_start_window(self):
        self.start_window = StartWindow(self.db)
        self.start_window.project_selected.connect(self.on_project_selected)
        self.start_window.project_created.connect(self.on_project_created)
        self.start_window.show()
        
    def on_project_selected(self, project_id, project_path):
        self.main_window = MainWindow(
            project_id=project_id, 
            project_path=project_path,
            auto_analyze=False
        )
        self.main_window.closed_to_menu.connect(self.show_start_window)
        
        self.main_window.show()
        self.start_window.close()
        
    def on_project_created(self, project_id, project_path):
        self.main_window = MainWindow(
            project_id=project_id, 
            project_path=project_path,
            auto_analyze=True
        )
        self.main_window.closed_to_menu.connect(self.show_start_window)
        
        self.main_window.show()
        self.start_window.close()

    def register_demo_project(self):
        demo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "demo_project"))
        
        if os.path.exists(demo_path):
            # Проверяем, нет ли уже этого проекта в базе
            projects = self.db.get_all_projects()
            if not any(p['project_path'] == demo_path for p in projects):
                print("Регистрация демо-проекта...")
                audio_file = os.path.join(demo_path, "audio.wav") # или .ogg
                self.db.add_project("ДЕМО: Пример разметки", demo_path, audio_file)


def main():
    print("Запускаем [ф]оноскоп...")
    app_container = Application()
    app_container.run()


if __name__ == "__main__":
    main()