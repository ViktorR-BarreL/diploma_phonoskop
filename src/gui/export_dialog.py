import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QCheckBox, QPushButton, QFileDialog,
                             QGroupBox, QTabWidget, QWidget)
from PyQt6.QtCore import Qt

class ExportDialog(QDialog):
 
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Экспорт - [ф]оноскоп")
        self.setMinimumWidth(550)
        self.setMinimumHeight(450)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.tab_widget = QTabWidget()
        
        # Вкладка: Текстовые форматы
        self.text_tab = self.create_text_tab()
        self.tab_widget.addTab(self.text_tab, "Текстовые форматы")
        
        # Вкладка: PDF
        self.pdf_tab = self.create_pdf_tab()
        self.tab_widget.addTab(self.pdf_tab, "PDF")
        
        # Вкладка: Спецформаты (Praat)
        self.special_tab = self.create_special_tab()
        self.tab_widget.addTab(self.special_tab, "Спецформаты")
        
        layout.addWidget(self.tab_widget)
        
        buttons_layout = QHBoxLayout()
        self.btn_export = QPushButton("Экспортировать")
        self.btn_export.clicked.connect(self.on_export)
        buttons_layout.addWidget(self.btn_export)
        
        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.reject)
        buttons_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(buttons_layout)
    
    def create_text_tab(self):
        '''Вкладка для текстовых форматов (TXT, CSV)'''
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Формат файла
        format_group = QGroupBox("Формат файла")
        format_layout = QVBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "TXT (*.txt)",
            "CSV (*.csv)"
        ])
        format_layout.addWidget(self.format_combo)
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        content_group = QGroupBox("Содержимое экспорта")
        content_layout = QVBoxLayout()
        
        self.export_phonemes = QCheckBox("Фонемная расшифровка (с таймкодами)")
        self.export_phonemes.setChecked(True)
        content_layout.addWidget(self.export_phonemes)
        
        self.export_text_transcript = QCheckBox("Текстовая расшифровка (если есть)")
        self.export_text_transcript.setChecked(True)
        content_layout.addWidget(self.export_text_transcript)
        
        self.export_search_results = QCheckBox("Результаты поиска")
        self.export_search_results.setChecked(True)
        content_layout.addWidget(self.export_search_results)
        
        content_group.setLayout(content_layout)
        layout.addWidget(content_group)
        
        options_group = QGroupBox("Дополнительные опции")
        options_layout = QVBoxLayout()
        
        self.include_timestamps = QCheckBox("Включить временные метки")
        self.include_timestamps.setChecked(True)
        options_layout.addWidget(self.include_timestamps)
        
        self.include_duration = QCheckBox("Включить длительность")
        self.include_duration.setChecked(True)
        options_layout.addWidget(self.include_duration)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        layout.addStretch()
        return tab
    
    def create_pdf_tab(self):
        """Вкладка для PDF"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Что включать в PDF
        content_group = QGroupBox("Содержимое отчета")
        content_layout = QVBoxLayout()
        
        self.pdf_include_table = QCheckBox("Таблица фонем")
        self.pdf_include_table.setChecked(True)
        content_layout.addWidget(self.pdf_include_table)
        
        self.pdf_include_text = QCheckBox("Текстовая расшифровка")
        self.pdf_include_text.setChecked(True)
        content_layout.addWidget(self.pdf_include_text)
        
        self.pdf_include_search = QCheckBox("Результаты поиска")
        self.pdf_include_search.setChecked(True)
        content_layout.addWidget(self.pdf_include_search)
        
        content_group.setLayout(content_layout)
        layout.addWidget(content_group)
        
        layout.addStretch()
        return tab
    
    def create_special_tab(self):
        """Вкладка для специальных форматов (TextGrid, PitchTier)"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        format_group = QGroupBox("Формат файла")
        format_layout = QVBoxLayout()
        self.special_format_combo = QComboBox()
        self.special_format_combo.addItems([
            "TextGrid (*.TextGrid)",
            "PitchTier (*.PitchTier)"
        ])
        format_layout.addWidget(self.special_format_combo)
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        content_group = QGroupBox("Что экспортировать")
        content_layout = QVBoxLayout()
        
        self.export_all_phonemes = QCheckBox("Все фонемы")
        self.export_all_phonemes.setChecked(True)
        content_layout.addWidget(self.export_all_phonemes)
        
        self.export_search_results = QCheckBox("Результаты поиска (отмеченные на экспорт)")
        self.export_search_results.setChecked(False)
        content_layout.addWidget(self.export_search_results)
        
        content_group.setLayout(content_layout)
        layout.addWidget(content_group)
        
        praat_group = QGroupBox("Опции Praat")
        praat_layout = QVBoxLayout()
        
        self.praat_include_tiers = QCheckBox("Создать отдельные Tier'ы для каждой фонемы")
        self.praat_include_tiers.setChecked(False)
        praat_layout.addWidget(self.praat_include_tiers)
        
        self.praat_textgrid_format = QCheckBox("Использовать формат TextGrid (совместимость с MFA)")
        self.praat_textgrid_format.setChecked(True)
        praat_layout.addWidget(self.praat_textgrid_format)
        
        praat_group.setLayout(praat_layout)
        layout.addWidget(praat_group)
        
        layout.addStretch()
        return tab
    
    def on_export(self):
        current_tab = self.tab_widget.currentIndex()
        
        if current_tab == 0:  # Текстовые форматы
            format_str = self.format_combo.currentText()
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Сохранить файл", "", format_str
            )
            
            if file_path:
                self.export_params = {
                    'file_path': file_path,
                    'type': 'text',
                    'format': format_str,
                    'export_phonemes': self.export_phonemes.isChecked(),
                    'export_text_transcript': self.export_text_transcript.isChecked(),
                    'export_search_results': self.export_search_results.isChecked(),
                    'include_timestamps': self.include_timestamps.isChecked(),
                    'include_duration': self.include_duration.isChecked()
                }
                self.accept()
                
        elif current_tab == 1:  # PDF
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Сохранить PDF", "", "PDF (*.pdf)"
            )
            
            if file_path:
                self.export_params = {
                    'file_path': file_path,
                    'type': 'pdf',
                    'format': 'PDF (*.pdf)',
                    'pdf_include_table': self.pdf_include_table.isChecked(),
                    'pdf_include_text': self.pdf_include_text.isChecked(),
                    'pdf_include_search': self.pdf_include_search.isChecked(),
                    'export_search_results': self.pdf_include_search.isChecked()
                }
                self.accept()
                
        else:  # Специальные форматы
            format_str = self.special_format_combo.currentText()
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Сохранить файл", "", format_str
            )
            
            if file_path:
                if not self.export_all_phonemes.isChecked() and not self.export_search_results.isChecked():
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.warning(self, "Внимание", "Выберите хотя бы один вариант для экспорта")
                    return
                
                self.export_params = {
                    'file_path': file_path,
                    'type': 'special',
                    'format': format_str,
                    'export_all_phonemes': self.export_all_phonemes.isChecked(),
                    'export_search_results': self.export_search_results.isChecked(),
                    'praat_include_tiers': self.praat_include_tiers.isChecked(),
                    'praat_textgrid_format': self.praat_textgrid_format.isChecked()
                }
                self.accept()
    
    def get_params(self):
        if hasattr(self, 'export_params'):
            return self.export_params
        return None
    
    def set_search_results(self, results):
        self.search_results = results
    
    def set_text_transcript(self, transcript):
        self.text_transcript = transcript