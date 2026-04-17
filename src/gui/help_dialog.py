# src/gui/help_dialog.py

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTextBrowser, 
                             QPushButton, QHBoxLayout)
from PyQt6.QtCore import Qt


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Справка — [ф]оноскоп")
        self.setMinimumSize(700, 600)
        self.resize(750, 650)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        # Устанавливаем HTML контент
        self.text_browser.setHtml(self.get_help_content())
        layout.addWidget(self.text_browser)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
    
    def get_help_content(self):
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 11pt;
            line-height: 1.5;
            margin: 15px;
        }
        h1 {
            font-size: 20pt;
            font-weight: bold;
            text-align: center;
            margin-top: 0;
            margin-bottom: 10px;
        }
        h2 {
            font-size: 16pt;
            font-weight: bold;
            margin-top: 25px;
            margin-bottom: 10px;
            border-bottom: 1px solid rgba(128, 128, 128, 0.3);
            padding-bottom: 5px;
        }
        h3 {
            font-size: 13pt;
            font-weight: bold;
            margin-top: 15px;
            margin-bottom: 5px;
        }
        p {
            margin: 8px 0;
            text-align: justify;
        }
        ul {
            margin: 5px 0;
            padding-left: 25px;
        }
        li {
            margin: 3px 0;
        }
        code {
            font-family: monospace;
            background-color: rgba(128, 128, 128, 0.15);
            padding: 1px 4px;
            border-radius: 3px;
        }
        hr {
            margin: 25px 0 10px 0;
            border: 0;
            border-top: 1px solid rgba(128, 128, 128, 0.3);
        }
        .footer {
            text-align: center;
            font-size: 10pt;
            opacity: 0.7;
            margin-top: 20px;
        }
    </style>
</head>
<body>

<h1>[ф]оноскоп 2026</h1>
<p style="text-align: center;">Программа для фонетического анализа речи</p>
<p style="text-align: center; font-style: italic; margin-bottom: 25px;">Руководство пользователя</p>

<h2>1. Начало работы</h2>
<h3>1.1. Создание нового проекта</h3>
<p>Нажмите <b>«+ Создать новый проект»</b>. Выберите аудиофайл (WAV, MP3, FLAC, OGG и др.), укажите название. Программа автоматически скопирует аудио в папку проекта и запустит анализ.</p>

<h3>1.2. Открытие и удаление</h3>
<p>Используйте список <b>«Мои проекты»</b> для быстрого доступа. Кнопка <b>«Удалить»</b> убирает проект только из списка программы, файлы на диске сохраняются.</p>

<h2>2. Интерфейс и разметка</h2>
<h3>2.1. Графики</h3>
<p>Осциллограмма и спектрограмма синхронизированы. Масштабируйте их колесиком мыши или используйте меню <b>Вид</b> для скрытия ненужных панелей.</p>

<h3>2.2. Редактирование</h3>
<ul>
    <li><b>Тайминги:</b> Перетаскивайте границы сегментов мышью.</li>
    <li><b>Фонемы:</b> Двойной клик по блоку — выбор символа (клавиатура).</li>
    <li><b>Контекстное меню:</b> Правый клик позволяет добавить или удалить сегмент.</li>
</ul>

<h2>3. Поиск и Экспорт</h2>
<h3>3.1. Шаблоны поиска</h3>
<p>Вы можете искать как стандартные сочетания (СГС), так и вводить свои в формате <code>[ф][о][н]</code>.</p>

<h3>3.2. Экспорт данных</h3>
<ul>
    <li><b>TextGrid (Praat):</b> Поддерживает экспорт всех фонем или только результатов поиска. Можно включить создание отдельных Tier (дорожек) для каждого звука.</li>
    <li><b>PDF/TXT/CSV:</b> Формирование отчетов для печати или обработки в Excel.</li>
</ul>

<h2>4. Горячие клавиши</h2>
<ul>
    <li><code>Ctrl+S</code> — Сохранить</li>
    <li><code>Ctrl+R</code> — Полный переанализ</li>
    <li><code>Ctrl+E</code> — Экспорт</li>
    <li><code>Ctrl+Z</code> — Отмена правки</li>
    <li><code>F1</code> — Справка</li>
</ul>

<hr>
<div class="footer">
            © 2026 [ф]оноскоп | <a href="https://github.com">GitHub</a>
</div>
</body>
</html>
"""