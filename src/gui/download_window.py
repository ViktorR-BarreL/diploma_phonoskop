from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QMessageBox
from PyQt6.QtCore import Qt
from src.model_downloader import DownloadWorker

class DownloadProgressWindow(QDialog):
    def __init__(self, models_to_download):
        super().__init__()
        self.setWindowTitle("Подготовка ресурсов")
        self.setFixedSize(400, 150)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        
        layout = QVBoxLayout(self)
        self.label = QLabel("Проверка наличия моделей...")
        layout.addWidget(self.label)
        
        self.pbar = QProgressBar()
        layout.addWidget(self.pbar)
        
        self.worker = DownloadWorker(models_to_download)
        self.worker.progress_signal.connect(self.update_status)
        self.worker.finished_signal.connect(self.on_finished)
        
    def start_download(self):
        self.worker.start()

    def update_status(self, msg, val):
        self.label.setText(msg)
        if val == -1:
            # Режим "бегающей" полоски (анимация без конкретного % )
            self.pbar.setRange(0, 0)
        else:
            # Обычный режим с процентами
            self.pbar.setRange(0, 100)
            self.pbar.setValue(val)

    def on_finished(self, success, error_msg):
        if success:
            self.accept() # Закрываем окно с успехом
        else:
            QMessageBox.critical(
                self, 
                "Ошибка загрузки", 
                "Не удалось загрузить модели. Проверьте подключение к интернету и перезапустите программу."
            )
            self.reject()