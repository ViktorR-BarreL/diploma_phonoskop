from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QComboBox, QPushButton, 
                             QLabel, QMessageBox, QLineEdit, QDialog, QVBoxLayout,
                             QFrame)
from PyQt6.QtCore import pyqtSignal, Qt

class SearchPanel(QWidget):
    
    search_requested = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel("Поиск сочетаний:")
        layout.addWidget(label)
        
        self.combo = QComboBox()
        self.combo.addItems([
        "ВСЕ (все фонемы)",
        "СЃС (согл-удар.гласн-согл)",
        "Ѓ (все ударные гласные)",
        "Г (все гласные)",
        "С (все согласные)",
        "Пользовательский..."
        ])
        self.combo.currentTextChanged.connect(self.on_preset_selected)
        layout.addWidget(self.combo)
        
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Нажмите для ввода с экранной клавиатуры")
        self.user_input.setReadOnly(True)
        self.user_input.mousePressEvent = self.open_search_keyboard
        self.user_input.setMinimumWidth(300)
        self.user_input.setEnabled(False)
        layout.addWidget(self.user_input)
        
        self.btn_search = QPushButton("Найти")
        self.btn_search.clicked.connect(self.search)
        layout.addWidget(self.btn_search)
        
        layout.addStretch()
    
    def on_preset_selected(self, text):
        if text == "Пользовательский...":
            self.user_input.setEnabled(True)
            self.user_input.setReadOnly(True)
        else:
            self.user_input.setEnabled(False)
            self.user_input.clear()
    
    def open_search_keyboard(self, event):
        from src.gui.keyboard import PhoneticKeyboard
        
        view_mode = "RU"
        if self.parent() and hasattr(self.parent(), 'phoneme_view_mode'):
            view_mode = self.parent().phoneme_view_mode
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Ввод сочетания фонем")
        dialog.setMinimumSize(600, 600)
        dialog.resize(650, 700)
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        input_field = QLineEdit()
        input_field.setPlaceholderText("Введите сочетание фонем...")
        input_field.setMinimumHeight(35)
        main_layout.addWidget(input_field)
        
        controls_layout = QHBoxLayout()
        btn_clear = QPushButton("Очистить")
        btn_backspace = QPushButton("⌫ Удалить")
        btn_clear.setFixedHeight(35)
        btn_backspace.setFixedHeight(35)
        
        controls_layout.addWidget(btn_clear)
        controls_layout.addWidget(btn_backspace)
        controls_layout.addStretch()
        main_layout.addLayout(controls_layout)
        
        keyboard = PhoneticKeyboard(mode=view_mode, show_controls=False)
        main_layout.addWidget(keyboard, 1)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)
        
        bottom_layout = QHBoxLayout()
        btn_cancel = QPushButton("Отмена")
        btn_ok = QPushButton("Найти")
        btn_cancel.setMinimumHeight(35)
        btn_ok.setMinimumHeight(35)
        
        btn_cancel.clicked.connect(dialog.reject)
        btn_ok.clicked.connect(lambda: on_enter())
        
        bottom_layout.addWidget(btn_cancel)
        bottom_layout.addWidget(btn_ok)
        main_layout.addLayout(bottom_layout)
        
        def on_key_pressed(char):
            current = input_field.text()
            input_field.setText(current + f"[{char}]")
        
        keyboard.char_pressed.connect(on_key_pressed)
        btn_clear.clicked.connect(lambda: input_field.clear())
        btn_backspace.clicked.connect(lambda: on_backspace())
        
        def on_backspace():
            current = input_field.text()
            last_open = current.rfind('[')
            if last_open != -1:
                input_field.setText(current[:last_open])
        
        def on_enter():
            pattern = input_field.text().strip()
            if pattern:
                self.user_input.setText(pattern)
                dialog.accept()
                self.search()
        
        dialog.exec()
    
    def search(self):
        preset = self.combo.currentText()
        
        if preset == "Пользовательский...":
            pattern = self.user_input.text().strip()
            if not pattern:
                QMessageBox.warning(self, "Внимание", "Введите паттерн для поиска (нажмите на поле)")
                return
            
            import re
            if not re.match(r'^(\[[^\]]+\])+$', pattern):
                msg = QMessageBox(self)
                msg.setWindowTitle("Ошибка формата")
                msg.setText("Паттерн должен быть в формате [ф][о][н][е][м][а]")
                msg.setInformativeText("Используйте экранную клавиатуру для ввода")
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.button(QMessageBox.StandardButton.Ok).setText("ОК")
                msg.exec()
                return
        else:
            pattern = self.preset_to_pattern(preset)
        
        self.search_requested.emit(pattern)
    
    def preset_to_pattern(self, preset: str) -> str:
        mapping = {
            "ВСЕ (все фонемы)": ".*",
            "СЃС (согл-удар.гласн-согл)": "СЃС",
            "Ѓ (все ударные гласные)": "Ѓ",
            "Г (все гласные)": "Г",
            "С (все согласные)": "С",
        }
        return mapping.get(preset, preset)