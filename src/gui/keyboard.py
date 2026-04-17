from PyQt6.QtWidgets import (QWidget, QGridLayout, QPushButton, QVBoxLayout, 
                             QGroupBox, QDialog, QHBoxLayout, QComboBox, QLabel,
                             QScrollArea, QFrame)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
from src.gui.phonetic_map import RUSSIAN_PHONEMES, IPA_PHONEMES

class PhoneticKeyboard(QWidget):
    char_pressed = pyqtSignal(str)
    
    def __init__(self, mode="RU", show_controls=False):
        super().__init__()
        self.mode = mode  # "RU" или "IPA"
        self.show_controls = show_controls  # Показывать ли управляющие кнопки
        self.init_ui()
    
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)
        
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Режим:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Русские фонемы", "IPA"])
        self.mode_combo.setCurrentText("Русские фонемы" if self.mode == "RU" else "IPA")
        self.mode_combo.currentTextChanged.connect(self.switch_mode)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        main_layout.addLayout(mode_layout)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)  # ИСПРАВЛЕНО: QFrame.Shape.NoFrame
        
        self.keys_container = QWidget()
        self.keys_layout = QVBoxLayout(self.keys_container)
        self.keys_layout.setSpacing(10)
        self.keys_layout.setContentsMargins(5, 5, 5, 5)
        
        self.scroll_area.setWidget(self.keys_container)
        
        main_layout.addWidget(self.scroll_area)
        
        self.update_keys()
    
    def switch_mode(self, text):
        self.mode = "RU" if text == "Русские фонемы" else "IPA"
        self.update_keys()
    
    def update_keys(self):
        for i in reversed(range(self.keys_layout.count())):
            item = self.keys_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        
        btn_width = 45
        btn_height = 35
        
        if self.mode == "RU":
            self.add_button_group("Гласные ударные", RUSSIAN_PHONEMES["vowels_stressed"], 6, btn_width, btn_height)
            self.add_button_group("Гласные безударные", RUSSIAN_PHONEMES["vowels_unstressed"], 6, btn_width, btn_height)
            self.add_button_group("Твердые согласные", RUSSIAN_PHONEMES["consonants_hard"], 8, btn_width, btn_height)
            self.add_button_group("Мягкие согласные", RUSSIAN_PHONEMES["consonants_soft"], 8, btn_width, btn_height)
        else:
            self.add_button_group("Гласные (Vowels)", IPA_PHONEMES["vowels"], 8, btn_width, btn_height)
            self.add_button_group("Твердые согласные", IPA_PHONEMES["consonants_hard"], 8, btn_width, btn_height)
            self.add_button_group("Мягкие согласные", IPA_PHONEMES["consonants_soft"], 8, btn_width, btn_height)
        
        if self.show_controls:
            self.add_control_buttons()
        
        self.keys_layout.addStretch()
    
    def add_control_buttons(self):
        group = QGroupBox("Управление")
        layout = QHBoxLayout()
        
        btn_clear = QPushButton("Очистить всё")
        btn_clear.clicked.connect(lambda: self.char_pressed.emit("__CLEAR__"))
        layout.addWidget(btn_clear)
        
        btn_backspace = QPushButton("⌫ Удалить")
        btn_backspace.clicked.connect(lambda: self.char_pressed.emit("__BACKSPACE__"))
        layout.addWidget(btn_backspace)
        
        btn_enter = QPushButton("⏎ Готово")
        btn_enter.clicked.connect(lambda: self.char_pressed.emit("__ENTER__"))
        layout.addWidget(btn_enter)
        
        group.setLayout(layout)
        self.keys_layout.addWidget(group)
    
    def add_button_group(self, title, chars, cols, btn_width=45, btn_height=35):
        group = QGroupBox(title)
        grid = QGridLayout()
        grid.setSpacing(3)
        grid.setContentsMargins(5, 10, 5, 5)
        
        for i, char in enumerate(chars):
            btn = QPushButton(char)
            btn.setFixedSize(btn_width, btn_height)
            btn.setFont(QFont("Segoe UI", 10))
            btn.clicked.connect(lambda _, c=char: self.char_pressed.emit(c))
            grid.addWidget(btn, i // cols, i % cols)
        
        group.setLayout(grid)
        self.keys_layout.addWidget(group)


class PhoneticKeyboardDialog(QDialog):
    char_selected = pyqtSignal(str)
    
    def __init__(self, parent=None, mode="RU"):
        super().__init__(parent)
        self.setWindowTitle("Выбор фонемы")
        self.setMinimumSize(550, 500)
        self.resize(600, 600)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.keyboard = PhoneticKeyboard(mode, show_controls=False)
        self.keyboard.char_pressed.connect(self.on_select)
        layout.addWidget(self.keyboard)
        
        btn_cancel = QPushButton("Отмена")
        btn_cancel.setFixedHeight(35)
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_cancel)
    
    def on_select(self, char):
        self.char_selected.emit(char)
        self.accept()