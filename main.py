import os
import sys
import shutil
import hashlib

# Оптимизация для CUDA и отрисовки
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from src.database import Database
from src.gui.start_window import StartWindow
from src.gui.main_window import MainWindow
from src.gui.download_window import DownloadProgressWindow


class Application:
    def __init__(self):
        self.db = Database()
        self.models_config = {
            "phonoscopic": {
                "repo_id": "ViktorR-BarreL/phonoscopic",
                "local_dir": "./models/phonoscopic",
                "critical_files": ["config.json", "model.safetensors", "vocab.json"]
            },
            "vosk": {
                "url": "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip",
                "local_dir": "./models/vosk",
                "critical_files": [
                    "am/final.mdl",
                    "graph/Gr.fst",
                    "graph/HCLr.fst",
                    "conf/model.conf",
                    "ivector/final.ie"
                ]
            }
        }

    # Проверка целостности Vosk
    def check_vosk_integrity(self, model_path):
        try:
            from vosk import Model, KaldiRecognizer
            import wave
            import tempfile
            import struct

            # Пытаемся загрузить модель
            test_model = Model(model_path)

            # Создаем тестовый WAV (0.5 секунды тишины)
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                with wave.open(tmp.name, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    silence = struct.pack('h' * 8000, *[0] * 8000)
                    wf.writeframes(silence)

                # Пробуем распознать тишину (должно работать без ошибок)
                wf = wave.open(tmp.name, 'rb')
                rec = KaldiRecognizer(test_model, wf.getframerate())
                data = wf.readframes(4000)
                if data:
                    rec.AcceptWaveform(data)
                wf.close()

            os.unlink(tmp.name)
            return True

        except Exception:
            return False

    # Проверка целостности Phonoscopic
    def check_phonoscopic_integrity(self, model_path):
        try:
            from transformers import Wav2Vec2Config, Wav2Vec2ForCTC
            import torch

            # 1. Проверяем конфиг
            config = Wav2Vec2Config.from_pretrained(model_path)

            # Проверяем, что это CTC модель с нормальным словарем
            if not hasattr(config, 'vocab_size') or config.vocab_size < 30:
                return False

            # 2. Проверка весов
            model = Wav2Vec2ForCTC.from_pretrained(model_path, from_tf=False)
            if not hasattr(model, 'lm_head'):
                return False

            # Проверяем, что веса не пустые
            total_params = sum(p.numel() for p in model.parameters())
            if total_params < 1000:
                return False

            return True

        except Exception:
            return False
        
    def get_corrupted_models(self):
        to_repair = []

        for name, info in self.models_config.items():
            folder = info['local_dir']

            # Если папки нет совсем - точно качаем
            if not os.path.exists(folder):
                to_repair.append(name)
                continue

            # Быстрая проверка критических файлов
            quick_valid = True
            for f in info['critical_files']:
                p = os.path.join(folder, f)

                # Проверка для весов 
                if f == "pytorch_model.bin":
                    alt_p = os.path.join(folder, "model.safetensors")
                    if not os.path.exists(p) and not os.path.exists(alt_p):
                        quick_valid = False
                        break
                    # Если нашли хотя бы один вариант, проверяем его размер
                    existing_path = p if os.path.exists(p) else alt_p
                    if os.path.getsize(existing_path) < 1000:
                        quick_valid = False
                        break
                else:
                    # Обычная проверка для остальных файлов
                    if not os.path.exists(p) or os.path.getsize(p) == 0:
                        quick_valid = False
                        break

            if not quick_valid:
                to_repair.append(name)
                shutil.rmtree(folder, ignore_errors=True)
                continue

            # Проверка реальной работоспособности модели
            if name == "vosk":
                if not self.check_vosk_integrity(folder):
                    to_repair.append(name)
                    shutil.rmtree(folder, ignore_errors=True)

            elif name == "phonoscopic":
                if not self.check_phonoscopic_integrity(folder):
                    to_repair.append(name)
                    shutil.rmtree(folder, ignore_errors=True)

        return to_repair


    def register_demo_project(self):
        demo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "demo_project"))
        
        if os.path.exists(demo_path):
            # Проверяем, нет ли уже этого проекта в базе
            projects = self.db.get_all_projects()
            if not any(p['project_path'] == demo_path for p in projects):
                audio_file = os.path.join(demo_path, "audio.wav") # или .ogg
                self.db.add_project("ДЕМО: Пример разметки", demo_path, audio_file)


    def run(self):
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))

        to_repair = self.get_corrupted_models()

        if to_repair:
            repair_cfg = {k: self.models_config[k] for k in to_repair}
            dl_win = DownloadProgressWindow(repair_cfg)
            dl_win.show()
            dl_win.start_download()
            if not dl_win.exec():
                return

        self.register_demo_project()
        self.show_start_window()
        sys.exit(app.exec())

    def show_start_window(self):
        self.start_window = StartWindow(self.db)
        self.start_window.project_selected.connect(self.on_project_selected)
        self.start_window.project_created.connect(self.on_project_created)
        self.start_window.show()

    def on_project_selected(self, project_id, project_path):
        self.main_window = MainWindow(project_id, project_path, False)
        self.main_window.closed_to_menu.connect(self.show_start_window)
        self.main_window.show()
        self.start_window.close()

    def on_project_created(self, project_id, project_path):
        self.main_window = MainWindow(project_id, project_path, True)
        self.main_window.closed_to_menu.connect(self.show_start_window)
        self.main_window.show()
        self.start_window.close()

if __name__ == "__main__":
    Application().run()