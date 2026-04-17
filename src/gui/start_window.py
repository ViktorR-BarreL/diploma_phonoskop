import os
import shutil
import re
from PyQt6.QtWidgets import (QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QListWidget, QListWidgetItem, QLabel, QFileDialog,
                             QInputDialog, QApplication, QFrame, QSplitter, QLineEdit, QMenuBar)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QIcon, QAction
from PyQt6.QtCore import QSettings
from datetime import datetime

class StartWindow(QWidget):
    
    project_selected = pyqtSignal(int, str)
    project_created = pyqtSignal(int, str)
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.settings = QSettings("Phonoskop", "2026")
        default_dir = os.path.expanduser("~/Documents/Phonoskop")
        self.projects_dir = self.settings.value("projects_dir", default_dir)
        os.makedirs(self.projects_dir, exist_ok=True)
        
        self.setWindowTitle("[ф]оноскоп")
        self.setMinimumSize(1000, 600)
        self.resize(1200, 800)
        # Иконка окна
        icon_path = os.path.join(os.path.dirname(__file__), "..", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.init_ui()
        self.create_menu()
        self.load_projects()
        
    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # ЛЕВАЯ ПОЛОВИНА
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "label.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            scaled_pixmap = pixmap.scaled(
                200, 100,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            logo_label = QLabel()
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        else:
            logo_label = QLabel("[ф]оноскоп")
            logo_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        
        left_layout.addWidget(logo_label)
        left_layout.addSpacing(20)
        
        projects_title = QLabel("Мои проекты")
        projects_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        left_layout.addWidget(projects_title)
        left_layout.addSpacing(10)
        
        # ПОИСК
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Поиск...")
        self.search_bar.textChanged.connect(self.filter_projects)
        self.search_bar.setFont(QFont("Segoe UI", 12))
        left_layout.addWidget(self.search_bar)
        left_layout.addSpacing(5)
        

        self.projects_list = QListWidget()
        self.projects_list.setMinimumHeight(300)
        self.projects_list.itemDoubleClicked.connect(self.open_project)
        left_layout.addWidget(self.projects_list)

        btn_list_layout = QHBoxLayout()
        
        self.btn_delete = QPushButton("Удалить проект")
        self.btn_delete.setFont(QFont("Segoe UI", 12))
        self.btn_delete.setMinimumHeight(40)
        self.btn_delete.setStyleSheet("background-color: #610000; color: #000000;")
        self.btn_delete.clicked.connect(self.delete_selected_project)
        
        btn_list_layout.addWidget(self.btn_delete)
        btn_list_layout.addStretch()
        
        left_layout.addLayout(btn_list_layout)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(20, 0, 0, 0)
        
        right_layout.addStretch()
        
        self.btn_new = QPushButton("+ Создать новый проект")
        self.btn_new.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.btn_new.setMinimumHeight(60)
        self.btn_new.setStyleSheet("background-color: #2E8B57; color: #ffffff;")
        self.btn_new.clicked.connect(self.create_new_project)
        right_layout.addWidget(self.btn_new)
        
        right_layout.addStretch()
        
        bottom_right_layout = QHBoxLayout()
        bottom_right_layout.addStretch()

        self.btn_browse = QPushButton("Папка проектов")
        self.btn_browse.setFont(QFont("Segoe UI", 12))
        self.btn_browse.setMinimumHeight(40)
        self.btn_browse.clicked.connect(self.browse_projects_folder)
        bottom_right_layout.addWidget(self.btn_browse)

        self.btn_open_folder = QPushButton("Открыть проект из папки")
        self.btn_open_folder.setFont(QFont("Segoe UI", 12))
        self.btn_open_folder.setMinimumHeight(40)
        self.btn_open_folder.clicked.connect(self.open_project_from_folder)
        bottom_right_layout.addWidget(self.btn_open_folder)

        right_layout.addLayout(bottom_right_layout)
        
        main_layout.addWidget(left_widget, 2)
        main_layout.addWidget(right_widget, 1)

    def create_menu(self):
        menubar = QMenuBar(self)
        
        # Меню "Справка"
        help_menu = menubar.addMenu("Справка")
        
        help_action = QAction("Справка", self)
        help_action.setShortcut("F1")
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)
        
        layout = self.layout()
        if layout:
            layout.setMenuBar(menubar)

    def show_help(self):
        from src.gui.help_dialog import HelpDialog
        help_dialog = HelpDialog(self)
        help_dialog.exec()
    
    
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    
    def _check_duplicate_name(self, name_to_check, exclude_id=None):
        existing = self.db.get_all_projects()
        for p in existing:
            if p['name'].lower() == name_to_check.lower():
                if exclude_id and p['id'] == exclude_id:
                    continue
                return True
        return False

    def filter_projects(self):
        self.load_projects(self.search_bar.text())
        
    def load_projects(self, filter_text=""):
        self.projects_list.clear()
        
        try:
            projects = self.db.get_all_projects()
            
            if not projects:
                empty_item = QListWidgetItem("Нет проектов. Создайте новый!")
                empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
                empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                empty_item.setFont(QFont("Segoe UI", 12))
                self.projects_list.addItem(empty_item)
                return
            
            filtered_projects = []
            for project in projects:
                if filter_text.lower() in project['name'].lower():
                    filtered_projects.append(project)
            
            if not filtered_projects:
                empty_item = QListWidgetItem(f"По запросу '{filter_text}' ничего не найдено")
                empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
                empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                empty_item.setFont(QFont("Segoe UI", 12))
                self.projects_list.addItem(empty_item)
                return
                
            for project in filtered_projects:
                project_id = project['id']
                name = project['name']
                project_path = project['project_path']
                audio_path = project['audio_path']
                last_opened = project['last_opened']
                created_date = project['created_date']
                
                try:
                    created = datetime.strptime(created_date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
                    modified = datetime.strptime(last_opened, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
                except:
                    created = created_date[:10] if created_date else "--"
                    modified = last_opened[:16] if last_opened else "--"
                
                path_exists = os.path.exists(project_path)
                
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, project_id)
                item.setData(Qt.ItemDataRole.UserRole + 1, name)
                item.setData(Qt.ItemDataRole.UserRole + 2, project_path)
                
                widget = QWidget()
                widget_layout = QVBoxLayout(widget)
                widget_layout.setContentsMargins(5, 8, 5, 8)
                widget_layout.setSpacing(3)
                
                # Название проекта
                name_label = QLabel(name)
                name_font = QFont("Segoe UI", 14, QFont.Weight.Bold)
                name_label.setFont(name_font)
                if not path_exists:
                    name_label.setStyleSheet("color: #888;")
                widget_layout.addWidget(name_label)
                
                # Даты
                dates_label = QLabel(f"Создан: {created}    Изменён: {modified}")
                dates_font = QFont("Segoe UI", 12)
                dates_label.setFont(dates_font)
                dates_label.setStyleSheet("color: #666;")
                widget_layout.addWidget(dates_label)
                
                # Путь
                if path_exists:
                    path_text = project_path
                    path_color = "#555"
                else:
                    path_text = "ПАПКА НЕ НАЙДЕНА"
                    path_color = "#a00"
                
                path_label = QLabel(path_text)
                path_font = QFont("Segoe UI", 10)
                path_font.setItalic(True)
                path_label.setFont(path_font)
                path_label.setStyleSheet(f"color: {path_color};")
                path_label.setWordWrap(True)
                widget_layout.addWidget(path_label)
                
                item.setSizeHint(widget.sizeHint())
                
                self.projects_list.addItem(item)
                self.projects_list.setItemWidget(item, widget)
                
        except Exception as e:
            print(f"Ошибка загрузки проектов: {e}")

    def sanitize_name(self, name):
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        return name.strip()
            
    def create_new_project(self):
        formats = "Аудиофайлы (*.wav *.mp3 *.flac *.aac *.ogg *.m4a);;Все файлы (*.*)"
        audio_path, _ = QFileDialog.getOpenFileName(self, "Выберите исходный аудиофайл", "", formats)
        if not audio_path: 
            return

        suggested_name = os.path.splitext(os.path.basename(audio_path))[0]
        
        while True:
            project_name, ok = QInputDialog.getText(self, "Новый проект", "Введите название проекта:", text=suggested_name)
            if not ok: 
                return
            
            project_name = project_name.strip()
            if not project_name:
                QMessageBox.warning(self, "Ошибка", "Название не может быть пустым.")
                continue
            
            # Проверяем дубликат в БД
            if self._check_duplicate_name(project_name):
                msg = QMessageBox(self)
                msg.setWindowTitle("Имя занято")
                msg.setText(f"Проект с именем '{project_name}' уже зарегистрирован в программе.")
                msg.setInformativeText("Выберите другое название.")
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.button(QMessageBox.StandardButton.Ok).setText("ОК")
                msg.exec()
                suggested_name = project_name
                continue
            break

        last_dir = self.settings.value("last_save_dir", os.path.expanduser("~/Documents/[ф]оноскоп"))
        base_folder = QFileDialog.getExistingDirectory(self, "Где создать папку проекта?", last_dir)
        if not base_folder: 
            return
        self.settings.setValue("last_save_dir", base_folder)

        safe_folder_name = self.sanitize_name(project_name)
        project_folder = os.path.join(base_folder, safe_folder_name)

        # Проверяем дубликат папки на диске
        if os.path.exists(project_folder):
            if os.listdir(project_folder):
                msg = QMessageBox(self)
                msg.setWindowTitle("Папка уже существует")
                msg.setText(f"Директория '{project_folder}' уже существует и содержит файлы.")
                msg.setInformativeText("Использовать её? (Существующие файлы проекта могут быть перезаписаны)")
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.button(QMessageBox.StandardButton.Yes).setText("Да")
                msg.button(QMessageBox.StandardButton.No).setText("Нет")
                
                if msg.exec() == QMessageBox.StandardButton.No:
                    return
        else:
            try:
                os.makedirs(project_folder)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка ФС", f"Не удалось создать папку: {e}")
                return

        try:
            audio_ext = os.path.splitext(audio_path)[1]
            new_audio_path = os.path.join(project_folder, f"audio{audio_ext}")
            
            if os.path.exists(new_audio_path):
                msg = QMessageBox(self)
                msg.setWindowTitle("Файл существует")
                msg.setText("Аудиофайл уже есть в папке. Заменить его?")
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.button(QMessageBox.StandardButton.Yes).setText("Да")
                msg.button(QMessageBox.StandardButton.No).setText("Нет")
                
                if msg.exec() == QMessageBox.StandardButton.Yes:
                    shutil.copy2(audio_path, new_audio_path)
            else:
                shutil.copy2(audio_path, new_audio_path)
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при копировании файлов: {e}")
            return

        project_id = self.db.add_project(project_name, project_folder, new_audio_path)
        
        self._create_project_meta(project_folder, project_name, new_audio_path)
        
        self.project_created.emit(project_id, project_folder)
        self.close()

    def _create_project_meta(self, folder, name, audio):
        import json
        meta = {
            "name": name,
            "audio": os.path.basename(audio),
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "2026.1"
        }
        with open(os.path.join(folder, "project.json"), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=4)
        
    def open_project(self, item):
        project_id = item.data(Qt.ItemDataRole.UserRole)
        project_name = item.data(Qt.ItemDataRole.UserRole + 1)
        project_path = item.data(Qt.ItemDataRole.UserRole + 2)
        
        if project_id is None:
            return
        
        if not os.path.exists(project_path):
            QMessageBox.warning(
                self, 
                "Проект не найден", 
                f"Папка проекта не найдена:\n{project_path}\n\nПроект будет удален из списка."
            )
            self.db.delete_project(project_id)
            self.load_projects(self.search_bar.text())
            return
        
        self.project_selected.emit(project_id, project_path)
        self.close()
        
    def open_project_from_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Выберите папку проекта",
            self.projects_dir
        )
        
        if not folder:
            return
        
        audio_extensions = ['.wav', '.mp3', '.flac', '.aac', '.ogg', '.m4a']
        audio_file = None
        for ext in audio_extensions:
            candidate = os.path.join(folder, f"audio{ext}")
            if os.path.exists(candidate):
                audio_file = candidate
                break
        
        if not audio_file:
            QMessageBox.warning(
                self, 
                "Ошибка", 
                "В выбранной папке нет аудиофайла.\nЭто не похоже на проект [ф]оноскоп."
            )
            return
        
        project_name = os.path.basename(folder)
        
        projects = self.db.get_all_projects()
        for p in projects:
            if p['project_path'] == folder:
                self.project_selected.emit(p['id'], folder)
                self.close()
                return

        if self._check_duplicate_name(project_name):
            existing_id = None
            existing_path = None
            for p in projects:
                if p['name'].lower() == project_name.lower():
                    existing_id = p['id']
                    existing_path = p['project_path']
                    break
            
            msg = QMessageBox(self)
            msg.setWindowTitle("Проект уже существует")
            msg.setText(f"Проект с именем '{project_name}' уже существует в базе.")
            msg.setInformativeText("Заменить запись в базе на эту папку?")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            msg.button(QMessageBox.StandardButton.Yes).setText("Да")
            msg.button(QMessageBox.StandardButton.No).setText("Нет")
            msg.button(QMessageBox.StandardButton.Cancel).setText("Отмена")
            
            reply = msg.exec()
            
            if reply == QMessageBox.StandardButton.Cancel:
                return
            elif reply == QMessageBox.StandardButton.No:
                return
            else: 
                self.db.delete_project(existing_id)
        
        project_id = self.db.add_project(project_name, folder, audio_file)
        
        self.project_selected.emit(project_id, folder)
        self.close()

    def delete_selected_project(self):
        item = self.projects_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Удаление", "Выберите проект из списка")
            return
            
        project_id = item.data(Qt.ItemDataRole.UserRole)
        project_name = item.data(Qt.ItemDataRole.UserRole + 1)
        project_path = item.data(Qt.ItemDataRole.UserRole + 2)
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Подтверждение")
        msg.setText(f"Вы уверены, что хотите удалить проект '{project_name}' из базы данных?")
        msg.setInformativeText("Файлы на диске удалены не будут.")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.button(QMessageBox.StandardButton.Yes).setText("Да")
        msg.button(QMessageBox.StandardButton.No).setText("Нет")
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.db.delete_project(project_id)
            self.load_projects(self.search_bar.text())
        
    def browse_projects_folder(self):
        import subprocess
        import sys
        
        if sys.platform == 'win32':
            os.startfile(self.projects_dir)
        elif sys.platform == 'darwin':
            subprocess.run(['open', self.projects_dir])
        else:
            subprocess.run(['xdg-open', self.projects_dir])