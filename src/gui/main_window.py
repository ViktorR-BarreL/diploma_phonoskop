import os
import json
import shutil
import copy
import ctypes
import csv
from datetime import datetime
from collections import Counter

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QFileDialog, QLabel, QListWidget, 
                             QProgressBar, QSplitter, QMessageBox, QMenuBar,
                             QMenu, QApplication, QListWidgetItem, QInputDialog,
                             QFrame, QSlider, QDialog, QTextEdit, QGroupBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtGui import QAction, QKeySequence, QActionGroup, QIcon

# Наши модули
from src.gui.visualizer import AudioCanvas
from src.gui.keyboard import PhoneticKeyboardDialog
from src.gui.phonetic_map import IPA_TO_USER, USER_TO_IPA
from src.gui.search_panel import SearchPanel
from src.gui.search_results import SearchResultsWidget
from src.gui.export_dialog import ExportDialog
from src.engine import SpeechEngine
from src.database import Database
from src.search_engine import SearchEngine
from src.export_manager import ExportManager


class FullAnalysisWorker(QThread):
    finished = pyqtSignal(list, str)
    progress = pyqtSignal(str, int)
    error = pyqtSignal(str)
    
    def __init__(self, engine, audio_path):
        super().__init__()
        self.engine = engine
        self.audio_path = audio_path
    
    def run(self):
        try:
            self.last_p = -1
            self.progress.emit("Инициализация анализа...", 0)

            def throttled_progress(msg, p):
                if p > self.last_p:
                    self.progress.emit(msg, p)
                    self.last_p = p

            # ЭТАП 1: Фонемный анализ (0% -> 80% прогресса)
            phonemes = self.engine.run_alignment(
                self.audio_path,
                progress_callback=lambda msg, p: throttled_progress(msg, int(p * 0.8))
            )

            # ЭТАП 2: Текстовая расшифровка (80% -> 100% прогресса)
            self.progress.emit("Запуск распознавания текста (Vosk)...", 81)
            
            text = self.engine.get_text_transcription(
                self.audio_path,
                progress_callback=lambda msg, p: throttled_progress(msg, 80 + int(p * 0.2))
            )

            # ЭТАП 3: Завершение ---
            self.progress.emit("Финальная обработка данных...", 100)
            
            # Принудительная очистка мусора в памяти перед возвратом в GUI
            import gc
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            self.finished.emit(phonemes if phonemes else [], text)
            
        except Exception as e:
            error_msg = f"Ошибка в рабочем потоке: {str(e)}"
            print(f"[FullAnalysisWorker] {error_msg}")
            self.error.emit(error_msg)
            self.finished.emit([], "")


class MainWindow(QMainWindow):

    closed_to_menu = pyqtSignal()

    def __init__(self, project_id=None, project_path=None, auto_analyze=False):
        super().__init__()
        
        myappid = 'mycompany.phonoskop'
        try: 
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except: 
            pass
        
        self.phoneme_view_mode = "RU"
        self.setWindowTitle("[ф]оноскоп")
        self.setMinimumSize(1300, 900)
        self.showMaximized()
        
        # Иконка окна
        icon_path = os.path.join(os.path.dirname(__file__), "..", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Инициализация движков
        self.engine = SpeechEngine(
            phoneme_model_path="./models/phonoscopic",
            use_stt=True,
            vosk_model_path="./models/vosk"
        )
        self.db = Database()
        self.search_engine = SearchEngine(USER_TO_IPA)

        self.export_manager = ExportManager(self)
        
        self.project_id = project_id
        self.project_path = project_path
        self.auto_analyze = auto_analyze
        self.coming_from_start = True
        self.current_audio_path = None
        self.phonemes_data = []
        self.text_transcript = ""
        self.undo_stack = []
        self.is_seeking = False
        self.active_segment_end = 0 
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        
        self.stop_timer = QTimer()
        self.stop_timer.setSingleShot(True)
        self.stop_timer.timeout.connect(lambda: self.player.stop())

        self.init_ui()
        self.create_menus()
        
        if project_path: 
            self.load_project(project_path)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(5, 5, 5, 5)

        top = QHBoxLayout()
        self.status_lbl = QLabel("Готов")
        top.addStretch()
        top.addWidget(self.status_lbl)
        main_layout.addLayout(top)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        
        graph_container = QWidget()
        graph_layout = QVBoxLayout(graph_container)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_layout.setSpacing(5)

        self.canvas = AudioCanvas()
        self.canvas.boundary_changed.connect(self.on_boundary_moved)
        self.canvas.request_delete.connect(self.delete_phoneme_manual)
        self.canvas.request_keyboard.connect(self.open_floating_keyboard)
        self.canvas.request_play_index.connect(self.play_phoneme_by_index)
        self.canvas.request_add.connect(self.add_phoneme_at_time)
        graph_layout.addWidget(self.canvas, 1)

        slider_row = QWidget()
        slider_layout = QHBoxLayout(slider_row)
        slider_layout.setContentsMargins(40, 0, 5, 0)
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(0, 1000)
        self.time_slider.sliderPressed.connect(self.on_seek_start)
        self.time_slider.sliderMoved.connect(self.on_seek)
        self.time_slider.sliderReleased.connect(self.on_seek_end)
        self.time_slider.setEnabled(False)
        slider_layout.addWidget(self.time_slider)
        graph_layout.addWidget(slider_row)

        controls_bar = QHBoxLayout()
        controls_bar.setContentsMargins(10, 0, 10, 5)
        
        self.btn_play = QPushButton("Play")
        self.btn_play.setFixedWidth(80)
        self.btn_play.clicked.connect(self.toggle_playback)
        self.btn_play.setEnabled(False)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setFixedWidth(100)
        self.vol_slider.setValue(70)
        self.vol_slider.valueChanged.connect(self.set_volume)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("font-family: monospace; font-size: 12px; color: #666;")

        controls_bar.addWidget(self.btn_play)
        controls_bar.addSpacing(20)
        controls_bar.addWidget(QLabel("Громкость:"))
        controls_bar.addWidget(self.vol_slider)
        controls_bar.addStretch()
        controls_bar.addWidget(self.time_label)
        
        graph_layout.addLayout(controls_bar)
        self.splitter.addWidget(graph_container)

        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget)
        
        self.search_panel = SearchPanel()
        self.search_panel.search_requested.connect(self.on_search)
        
        self.search_results = SearchResultsWidget()
        self.search_results.result_clicked.connect(self.on_search_click)
        self.search_results.selection_changed.connect(self.save_selected_exports)
        
        transcript_group = QGroupBox("Текстовая расшифровка")
        transcript_layout = QVBoxLayout()
        self.transcript_text = QTextEdit()
        self.transcript_text.setMaximumHeight(80)
        self.transcript_text.setPlaceholderText("Нажмите 'Повторно выровнять' для получения расшифровки")
        self.transcript_text.textChanged.connect(self.on_transcript_edited)
        transcript_layout.addWidget(self.transcript_text)
        transcript_group.setLayout(transcript_layout)
        
        tools_layout.addWidget(self.search_panel)
        tools_layout.addWidget(self.search_results)
        tools_layout.addWidget(transcript_group)
        
        self.splitter.addWidget(tools_widget)
        main_layout.addWidget(self.splitter, 1)

        self.progress = QProgressBar()
        self.progress.hide()
        main_layout.addWidget(self.progress)

        footer = QLabel("[ф]оноскоп работает на базе нейросетей. Результаты могут содержать ошибки. Обязательно проверяйте результаты вручную.")
        footer.setStyleSheet("color: #888; font-size: 11px; padding: 5px; border-top: 1px solid #333;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(footer)

    # Меню
    def create_menus(self):
        bar = self.menuBar()
        
        # Меню Проект
        project_menu = bar.addMenu("Проект")
        
        save_action = QAction("Сохранить проект", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_project)
        project_menu.addAction(save_action)

        save_as_action = QAction("Сохранить как...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self.save_project_as)
        project_menu.addAction(save_as_action)
        
        project_menu.addSeparator()
        
        realign_action = QAction("Повторно выровнять", self)
        realign_action.setShortcut(QKeySequence("Ctrl+R"))
        realign_action.triggered.connect(self.start_reanalysis)
        project_menu.addAction(realign_action)
        
        project_menu.addSeparator()
        
        export_action = QAction("Экспорт...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self.export_project)
        project_menu.addAction(export_action)
        
        project_menu.addSeparator()
        
        exit_action = QAction("Выход", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        project_menu.addAction(exit_action)
        
        # Меню Правка
        edit_menu = bar.addMenu("Правка")
        
        undo_action = QAction("Отменить", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self.undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("Повторить", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self.redo)
        edit_menu.addAction(redo_action)
        
        # Меню Вид
        view = bar.addMenu("Вид")

        self.act_wav = QAction("Осциллограмма", self, checkable=True, checked=True)
        self.act_spec = QAction("Спектрограмма", self, checkable=True, checked=True)

        self.act_wav.triggered.connect(self.on_view_toggled)
        self.act_spec.triggered.connect(self.on_view_toggled)

        view.addAction(self.act_wav)
        view.addAction(self.act_spec)
        
        view.addSeparator()
        
        mode_menu = view.addMenu("Вид фонем")
        group = QActionGroup(self)
        self.act_ipa = QAction("IPA", self, checkable=True)
        self.act_ru = QAction("Русский", self, checkable=True, checked=True)
        for a in [self.act_ipa, self.act_ru]: 
            group.addAction(a)
            mode_menu.addAction(a)
        self.act_ipa.triggered.connect(lambda: self.set_phoneme_view("IPA"))
        self.act_ru.triggered.connect(lambda: self.set_phoneme_view("RU"))
        
        # Меню Справка
        help_menu = bar.addMenu("Справка")
        help_action = QAction("Справка", self)
        help_action.setShortcut(QKeySequence.StandardKey.HelpContents)
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)

    def on_view_toggled(self):
        if not self.act_wav.isChecked() and not self.act_spec.isChecked():
            sender = self.sender()
            sender.setChecked(True)
            return
        
        self.canvas.p_wav.setVisible(self.act_wav.isChecked())
        self.canvas.p_spec.setVisible(self.act_spec.isChecked())
        
        self.canvas.ci.layout.activate()

    # Работа с проектами
    def new_project(self):
        from src.gui.start_window import StartWindow
        start_window = StartWindow(self.db)
        start_window.project_created.connect(self.load_project)
        start_window.show()

    def open_project_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку проекта")
        if folder:
            self.load_project(folder)

    def load_project(self, path):
        '''Загрузка существующего проекта из папки'''
        print(f"[MainWindow] Загрузка проекта из: {path}")
        self.project_path = path
        
        self.phonemes_data = []
        self.text_transcript = ""
        self.canvas.clear_ui() 
        self.status_lbl.setText("Загрузка аудио...")
        QApplication.processEvents()

        audio_extensions = ['.wav', '.mp3', '.flac', '.aac', '.ogg', '.m4a']
        audio_file = None
        for ext in audio_extensions:
            candidate = os.path.join(path, f"audio{ext}")
            if os.path.exists(candidate):
                audio_file = candidate
                break
        
        if audio_file:
            self.current_audio_path = audio_file
            self.canvas.plot_audio(audio_file) 
            self.player.setSource(QUrl.fromLocalFile(audio_file))
            self.btn_play.setEnabled(True)
            self.time_slider.setEnabled(True)
        else:
            print(f"[Warning] Аудиофайл в папке {path} не найден!")
            self.status_lbl.setText("Ошибка: аудио не найдено")

        loaded_from_db = False
        if self.project_id:
            analysis = self.db.get_analysis(self.project_id)
            if analysis:
                self.phonemes_data = analysis.get('phonemes', [])
                self.text_transcript = analysis.get('text_transcript', "")
                loaded_from_db = True
                print(f"[DB] Загружено {len(self.phonemes_data)} фонем из базы")

        if not loaded_from_db:
            json_path = os.path.join(path, "phonemes.json")
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r", encoding='utf-8') as f:
                        self.phonemes_data = json.load(f)
                    print(f"[File] Загружено {len(self.phonemes_data)} фонем из JSON")
                except Exception as e:
                    print(f"[Error] Не удалось прочитать phonemes.json: {e}")

            txt_path = os.path.join(path, "transcript.txt")
            if os.path.exists(txt_path):
                with open(txt_path, "r", encoding='utf-8') as f:
                    self.text_transcript = f.read()

        if self.phonemes_data:
            self.display_phonemes(self.phonemes_data)
            self.transcript_text.setText(self.text_transcript)
            self.status_lbl.setText(f"Проект загружен: {len(self.phonemes_data)} фонем")
            
            if self.project_id:
                search_state = self.db.get_search_state(self.project_id)
                if search_state:
                    pattern = search_state['pattern']
                    if search_state['pattern_type'] == 'preset':
                        self.search_panel.combo.setCurrentText(self.get_preset_name_by_pattern(pattern))
                    else:
                        self.search_panel.combo.setCurrentText("Пользовательский...")
                        self.search_panel.user_input.setText(pattern)
                    
                    self.on_search(pattern)
                    
                    if 'selected_exports' in search_state and search_state['selected_exports']:
                        self.search_results.set_selected_indices(search_state['selected_exports'])
        else:
            self.status_lbl.setText("Проект открыт (без разметки)")
            
            # АВТОМАТИЧЕСКИЙ ЗАПУСК АНАЛИЗА ТОЛЬКО ДЛЯ НОВЫХ ПРОЕКТОВ
            if self.auto_analyze and self.current_audio_path:
                QTimer.singleShot(500, self.start_reanalysis)

    def get_preset_name_by_pattern(self, pattern):
        presets = {
            "СГ+С": "СГ+С (согл-удар.гласн-согл)", 
            "Г+": "Г+ (все ударные гласные)", 
            "Г": "Г (все гласные)", 
            "С": "С (все согласные)", 
            ".*": "ВСЕ (все фонемы)"
        }
        return presets.get(pattern, "Пользовательский...")

    def save_selected_exports(self):
        '''Сохраняет выбранные для экспорта сочетания в БД'''
        if self.project_id and self.search_results.results:
            selected_indices = self.search_results.get_selected_indices()
            current_pattern = self.search_panel.user_input.text() if self.search_panel.combo.currentText() == "Пользовательский..." else self.search_panel.preset_to_pattern(self.search_panel.combo.currentText())
            pattern_type = 'custom' if self.search_panel.combo.currentText() == "Пользовательский..." else 'preset'
            
            self.db.save_search_state(self.project_id, current_pattern, pattern_type, selected_indices)

    def save_project(self):
        '''Сохранение проекта'''
        if not self.project_path:
            default_dir = os.path.join(os.path.expanduser("~"), "Documents", "[ф]оноскоп")
            os.makedirs(default_dir, exist_ok=True)
            
            project_folder = QFileDialog.getExistingDirectory(
                self, 
                "Выберите папку для сохранения проекта",
                default_dir
            )
            
            if not project_folder:
                return
            
            name, ok = QInputDialog.getText(self, "Название проекта", "Название проекта:")
            if not ok or not name:
                return
            
            import re
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', name.strip())
            self.project_path = os.path.join(project_folder, safe_name)
            os.makedirs(self.project_path, exist_ok=True)
            
            self.project_id = self.db.add_project(name, self.project_path, self.current_audio_path)
        
        if self.project_path:
            # Сохраняем фонемы в JSON файл
            with open(os.path.join(self.project_path, "phonemes.json"), "w", encoding='utf-8') as f:
                json.dump(self.phonemes_data, f, indent=2, ensure_ascii=False)
            
            if self.text_transcript:
                with open(os.path.join(self.project_path, "transcript.txt"), "w", encoding='utf-8') as f:
                    f.write(self.text_transcript)
            
            # Сохраняем в БД
            self.db.save_analysis(self.project_id, self.phonemes_data, self.text_transcript, self.canvas.duration)
            self.db.update_project(self.project_id, self.current_audio_path)
            
            self.status_lbl.setText("Проект сохранен")
            
            msg = QMessageBox(self)
            msg.setWindowTitle("Сохранение")
            msg.setText(f"Проект сохранен в:\n{self.project_path}")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.button(QMessageBox.StandardButton.Ok).setText("ОК")
            msg.exec()

    def save_project_as(self):
        '''Сохранить проект в новое место с новым именем'''
        if not self.phonemes_data:
            QMessageBox.warning(self, "Сохранение", "Нет данных для сохранения")
            return
        
        old_path = self.project_path
        old_name = os.path.basename(old_path) if old_path else "project"
        
        name, ok = QInputDialog.getText(
            self, 
            "Сохранить как", 
            "Введите новое название проекта:",
            text=old_name
        )
        
        if not ok or not name.strip():
            return
        
        import re
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', name.strip())
        
        default_dir = os.path.dirname(old_path) if old_path else os.path.expanduser("~/Documents/[ф]оноскоп")
        
        folder = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку для сохранения копии проекта",
            default_dir
        )
        
        if not folder:
            return
        
        new_path = os.path.join(folder, safe_name)
        
        if os.path.exists(new_path):
            msg = QMessageBox(self)
            msg.setWindowTitle("Папка существует")
            msg.setText(f"Папка '{new_path}' уже существует.")
            msg.setInformativeText("Перезаписать содержимое?")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.button(QMessageBox.StandardButton.Yes).setText("Да")
            msg.button(QMessageBox.StandardButton.No).setText("Нет")
            
            if msg.exec() == QMessageBox.StandardButton.No:
                return
        else:
            os.makedirs(new_path, exist_ok=True)
        
        try:
            if old_path and os.path.exists(old_path):
                # Копируем все файлы из старой папки
                import shutil
                for item in os.listdir(old_path):
                    src = os.path.join(old_path, item)
                    dst = os.path.join(new_path, item)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)
            
            with open(os.path.join(new_path, "phonemes.json"), "w", encoding='utf-8') as f:
                json.dump(self.phonemes_data, f, indent=2, ensure_ascii=False)
            
            if self.text_transcript:
                with open(os.path.join(new_path, "transcript.txt"), "w", encoding='utf-8') as f:
                    f.write(self.text_transcript)
            
            new_audio_path = None
            audio_extensions = ['.wav', '.mp3', '.flac', '.aac', '.ogg', '.m4a']
            for ext in audio_extensions:
                candidate = os.path.join(new_path, f"audio{ext}")
                if os.path.exists(candidate):
                    new_audio_path = candidate
                    break
            
            new_project_id = self.db.add_project(safe_name, new_path, new_audio_path)
            
            self.db.save_analysis(new_project_id, self.phonemes_data, self.text_transcript, self.canvas.duration)
            
            self.project_id = new_project_id
            self.project_path = new_path
            if new_audio_path:
                self.current_audio_path = new_audio_path
            
            self.status_lbl.setText(f"Проект сохранен как: {new_path}")
            
            msg = QMessageBox(self)
            msg.setWindowTitle("Сохранение")
            msg.setText(f"Копия проекта сохранена в:\n{new_path}")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.button(QMessageBox.StandardButton.Ok).setText("ОК")
            msg.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить копию проекта:\n{str(e)}")


    
    def closeEvent(self, event):
        '''Сохранить, выйти без сохранения или остаться'''
        
        # Если в проекте вообще нет данных, просто выходим
        if not self.phonemes_data:
            self.closed_to_menu.emit()
            event.accept()
            return

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Завершение работы")
        msg_box.setText(f"Проект '{os.path.basename(self.project_path)}' был изменен.")
        msg_box.setInformativeText("Сохранить изменения перед выходом?")
        
        btn_save = msg_box.addButton("Сохранить", QMessageBox.ButtonRole.AcceptRole)
        btn_discard = msg_box.addButton("Не сохранять", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.setDefaultButton(btn_save)
        msg_box.exec()
        
        clicked_button = msg_box.clickedButton()
        
        if clicked_button == btn_save:
            self.save_project()
            self.closed_to_menu.emit()
            event.accept()
        elif clicked_button == btn_discard:
            self.closed_to_menu.emit()
            event.accept()
        else:
            event.ignore()


    def auto_save_and_exit(self):
        if self.project_id and self.phonemes_data:
            print("[AutoSave] Сохранение проекта...")
            with open(os.path.join(self.project_path, "phonemes.json"), "w", encoding='utf-8') as f:
                json.dump(self.phonemes_data, f, indent=2, ensure_ascii=False)
            
            self.db.save_analysis(self.project_id, self.phonemes_data, self.text_transcript, self.canvas.duration)
            self.status_lbl.setText("Проект автоматически сохранен")

    
    # Анализ аудио

    def start_reanalysis(self):
        if not self.current_audio_path:
            QMessageBox.warning(self, "Ошибка", "Нет аудиофайла для анализа")
            return

        quality = self.engine.check_audio_quality(self.current_audio_path)
        
        if quality == "quiet":
            QMessageBox.critical(
                self, 
                "Ошибка качества", 
                "Возможно, аудио слишком тихое для анализа. Пожалуйста, усильте сигнал или выберите другую запись."
            )
            return
            
        if quality == "noisy":
            msg_noise = QMessageBox(self)
            msg_noise.setIcon(QMessageBox.Icon.Warning)
            msg_noise.setWindowTitle("Внимание: Шум")
            msg_noise.setText("Возможно, аудио содержит много шума или посторонних звуков.")
            msg_noise.setInformativeText("Это может значительно снизить точность распознавания фонем. Продолжить анализ?")
            btn_yes_noise = msg_noise.addButton("Продолжить", QMessageBox.ButtonRole.YesRole)
            btn_no_noise = msg_noise.addButton("Отмена", QMessageBox.ButtonRole.NoRole)
            msg_noise.exec()
            if msg_noise.clickedButton() == btn_no_noise:
                return

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Подтверждение")
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setText("Запустить полный анализ аудио?")
        msg_box.setInformativeText("Текущая разметка (фонемы и текст) будет полностью перезаписана новыми данными.")
        
        btn_yes = msg_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
        btn_no = msg_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
        msg_box.setDefaultButton(btn_no)
        
        msg_box.exec()
        
        if msg_box.clickedButton() != btn_yes:
            return
        
        self.setEnabled(False)  # Блокируем окно, чтобы пользователь ничего не сломал
        self.progress.show()
        self.progress.setValue(0)
        self.status_lbl.setText("Инициализация нейросетей...")
        
        self.worker = FullAnalysisWorker(self.engine, self.current_audio_path)
        
        self.worker.progress.connect(self.on_analysis_progress)
        self.worker.finished.connect(self.on_analysis_done)
        self.worker.error.connect(self.on_analysis_error)
        
        self.worker.start()

    def on_analysis_progress(self, message, percentage):
        self.status_lbl.setText(message)
        self.progress.setValue(percentage)

    def on_analysis_done(self, phonemes, text):
        self.progress.hide()
        self.setEnabled(True)
        
        if phonemes:
            self.save_state()
            self.phonemes_data = phonemes
            self.display_phonemes(phonemes)
        
        # Обновляем текст в поле
        self.text_transcript = text if text else ""
        
        self.transcript_text.blockSignals(True) # Блокируем, чтобы не сработал on_transcript_edited
        self.transcript_text.setText(self.text_transcript)
        self.transcript_text.blockSignals(False) # Разблокируем обратно
        
        self.status_lbl.setText("Анализ завершен")
        self.save_project()

    def on_analysis_error(self, error_msg):
        self.progress.hide()
        self.setEnabled(True)
        QMessageBox.critical(self, "Ошибка анализа", f"Произошла ошибка:\n{error_msg}")
        self.status_lbl.setText("Ошибка анализа")

   
    # Отображение фонем
    def set_phoneme_view(self, mode):
        self.phoneme_view_mode = mode
        if self.phonemes_data:
            self.display_phonemes(self.phonemes_data)

    def display_phonemes(self, data):
        self.canvas.draw_phonemes(data, self.phoneme_view_mode)

    
    # Редактирование 
    def save_state(self):
        self.undo_stack.append(copy.deepcopy(self.phonemes_data))
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def undo(self):
        if len(self.undo_stack) > 1:
            self.undo_stack.pop()
            self.phonemes_data = copy.deepcopy(self.undo_stack[-1])
            self.display_phonemes(self.phonemes_data)
            self.status_lbl.setText("Отменено")

    def redo(self):
        self.status_lbl.setText("Redo: сохраните состояние перед изменениями")

    def on_boundary_moved(self, idx, b_type, time):
        self.save_state()
        
        if b_type == 'start':
            self.phonemes_data[idx]['start'] = time
        else:
            self.phonemes_data[idx]['end'] = time

    def open_floating_keyboard(self, idx):
        dialog = PhoneticKeyboardDialog(self, mode=self.phoneme_view_mode)
        dialog.char_selected.connect(lambda char: self.on_kb_input(idx, char))
        dialog.exec()

    def on_kb_input(self, idx, char):
        if 0 <= idx < len(self.phonemes_data):
            self.save_state()
            
            if self.phoneme_view_mode == "RU":
                self.phonemes_data[idx]['label'] = USER_TO_IPA.get(char, char)
            else:
                self.phonemes_data[idx]['label'] = char
            
            self.display_phonemes(self.phonemes_data)

    def add_phoneme_at_time(self, index, time):
        self.save_state()
        
        insert_pos = index + 1
        duration = 0.1
        
        new_phoneme = {
            "label": "a", 
            "start": round(time, 3), 
            "end": round(time + duration, 3)
        }
        
        self.phonemes_data.insert(insert_pos, new_phoneme)
        
        shift = duration
        for i in range(insert_pos + 1, len(self.phonemes_data)):
            self.phonemes_data[i]['start'] += shift
            self.phonemes_data[i]['end'] += shift
        
        self.display_phonemes(self.phonemes_data)
        self.open_floating_keyboard(insert_pos)

    def delete_phoneme_manual(self, idx):
        if 0 <= idx < len(self.phonemes_data):
            self.save_state()
            
            deleted_duration = self.phonemes_data[idx]['end'] - self.phonemes_data[idx]['start']
            self.phonemes_data.pop(idx)
            
            for i in range(idx, len(self.phonemes_data)):
                self.phonemes_data[i]['start'] -= deleted_duration
                self.phonemes_data[i]['end'] -= deleted_duration
            
            self.display_phonemes(self.phonemes_data)

    def on_transcript_edited(self):
        self.text_transcript = self.transcript_text.toPlainText()

    
    # Аудио 
    def set_volume(self, value):
        self.audio_output.setVolume(value / 100)

    def update_play_button_ui(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setText("Pause")
        else:
            self.btn_play.setText("Play")

    def toggle_playback(self):
        state = self.player.playbackState()
        
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            if self.player.position() >= self.player.duration():
                self.player.setPosition(0)
            
            self.active_segment_end = 0 
            self.player.play()

    def on_position_changed(self, pos):
        curr_sec = pos / 1000.0
        
        if self.active_segment_end > 0:
            if curr_sec >= self.active_segment_end:
                self.player.pause()
                self.active_segment_end = 0  
        
        if not self.is_seeking:
            dur = self.player.duration()
            if dur > 0:
                self.time_slider.blockSignals(True)
                self.time_slider.setValue(int(pos / dur * 1000))
                self.time_slider.blockSignals(False)
                
                self.time_label.setText(f"{self.format_time(pos)} / {self.format_time(dur)}")
                self.canvas.update_playhead(curr_sec)

    def on_duration_changed(self, dur):
        self.time_slider.setEnabled(dur > 0)
        self.time_label.setText(f"00:00 / {self.format_time(dur)}")

    def on_seek_start(self):
        self.is_seeking = True
    
    def on_seek(self, val):
        dur = self.player.duration()
        if dur > 0:
            new_pos_ms = int(dur * val / 1000)
            self.canvas.update_playhead(new_pos_ms / 1000.0)
            self.time_label.setText(f"{self.format_time(new_pos_ms)} / {self.format_time(dur)}")

    def on_seek_end(self):
        dur = self.player.duration()
        if dur > 0:
            new_pos_ms = int(dur * self.time_slider.value() / 1000)
            self.player.setPosition(new_pos_ms)
        self.is_seeking = False

    def format_time(self, ms):
        s = ms // 1000
        m = s // 60
        s %= 60
        return f"{m:02d}:{s:02d}"

    def play_phoneme_by_index(self, idx):
        if 0 <= idx < len(self.phonemes_data):
            d = self.phonemes_data[idx]
            self.player.setPosition(int(d['start'] * 1000))
            self.player.play()
            self.stop_timer.start(int((d['end'] - d['start']) * 1000))

    
    # Поиск
    def on_search(self, pattern):
        if not pattern:
            self.search_results.clear()
            return
        
        if pattern.startswith('['):
            pattern_type = 'custom'
        else:
            pattern_type = 'preset'
        
        results = self.search_engine.find_pattern(
            self.phonemes_data, 
            pattern, 
            view_mode=self.phoneme_view_mode
        )
        self.search_results.set_results(results)
        self.status_lbl.setText(f"Найдено {len(results)} сочетаний")
        
        if self.project_id:
            self.db.save_search_state(self.project_id, pattern, pattern_type)

    def on_search_click(self, s, e):
        self.player.setPosition(int(s * 1000))
        self.player.play()
        duration = (e - s) * 1000
        self.stop_timer.start(int(duration))
        self.canvas.p_wav.setXRange(s - 0.05, e + 0.05)

   
    # Экспорт
    def export_project(self):
        if not self.phonemes_data:
            QMessageBox.warning(self, "Экспорт", "Нет данных для экспорта")
            return
        
        dialog = ExportDialog(self)
        if hasattr(self.search_results, 'results') and self.search_results.results:
            dialog.set_search_results(self.search_results.results)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            params = dialog.get_params()
            if params:
                self.do_export(params)
    
    def do_export(self, params):
        export_type = params['type']
        
        try:
            if export_type == 'text':
                self.export_to_text(params)
            elif export_type == 'pdf':
                self.export_to_pdf(params)
            elif export_type == 'special':
                self.export_to_special(params)
            
            msg = QMessageBox(self)
            msg.setWindowTitle("Экспорт")
            msg.setText(f"Экспорт завершен:\n{params['file_path']}")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.button(QMessageBox.StandardButton.Ok).setText("ОК")
            msg.exec()
            
            self.status_lbl.setText(f"Экспортировано: {os.path.basename(params['file_path'])}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def export_to_text(self, params):
        if params['format'].startswith("TXT"):
            self.export_manager.export_to_txt(params)
        elif params['format'].startswith("CSV"):
            self.export_manager.export_to_csv(params)

    def export_to_pdf(self, params):
        self.export_manager.export_to_pdf(params)

    def export_to_special(self, params):
        if params['format'].startswith("TextGrid"):
            self.export_manager.export_to_textgrid(params)
        elif params['format'].startswith("PitchTier"):
            self.export_manager.export_to_pitchtier(params)
    
    
    # Справка
    def show_help(self):
        from src.gui.help_dialog import HelpDialog
        help_dialog = HelpDialog(self)
        help_dialog.exec()
