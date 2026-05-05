import os
import requests
import zipfile
import shutil
from huggingface_hub import snapshot_download
from PyQt6.QtCore import QThread, pyqtSignal

class DownloadWorker(QThread):
    progress_signal = pyqtSignal(str, int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, models_to_download):
        super().__init__()
        self.models = models_to_download

    def run(self):
        try:
            total_tasks = len(self.models)
            for i, (model_type, info) in enumerate(self.models.items()):
                # Рассчитываем диапазон процентов для текущей модели
                start_p = int((i / total_tasks) * 100)
                end_p = int(((i + 1) / total_tasks) * 100)

                if model_type == "phonoscopic":
                    self.progress_signal.emit(f"Проверка/Загрузка фонемной модели...", -1)
                    snapshot_download(
                        repo_id=info['repo_id'],
                        local_dir=info['local_dir']
                    )
                    self.progress_signal.emit("Фонемная модель готова!", end_p)
                
                elif model_type == "vosk":
                    self.download_and_extract_vosk(info['url'], info['local_dir'], start_p, end_p)
            
            self.progress_signal.emit("Все ресурсы подготовлены!", 100)
            self.finished_signal.emit(True, "")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

    def download_and_extract_vosk(self, url, target_dir, p_offset, p_max):
        zip_path = target_dir + ".zip"
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        
        # Скачивание
        with open(zip_path, "wb") as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        # Считаем процент внутри выделенного диапазона
                        local_p = int((downloaded / total_size) * (p_max - p_offset - 10))
                        self.progress_signal.emit(
                            f"Загрузка Vosk ({downloaded//1024//1024}MB / {total_size//1024//1024}MB)...", 
                            p_offset + local_p
                        )
        
        # Распаковка
        self.progress_signal.emit("Распаковка модели Vosk...", -1)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(os.path.dirname(target_dir))
            extracted_name = zip_ref.namelist()[0].split('/')[0]
            old_path = os.path.join(os.path.dirname(target_dir), extracted_name)
            if old_path != target_dir:
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                os.rename(old_path, target_dir)
        
        if os.path.exists(zip_path):
            os.remove(zip_path)