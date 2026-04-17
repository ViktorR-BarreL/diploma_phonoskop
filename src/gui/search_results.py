from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QHeaderView, QPushButton, QLabel,
                             QCheckBox)
from PyQt6.QtCore import pyqtSignal, Qt

class SearchResultsWidget(QWidget):
    
    result_clicked = pyqtSignal(float, float)
    selection_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.results = []
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QHBoxLayout()
        title = QLabel("Результаты поиска:")
        title.setStyleSheet("font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        self.btn_select_all = QPushButton("Выбрать все")
        self.btn_select_all.clicked.connect(self.select_all)
        header.addWidget(self.btn_select_all)
        
        self.btn_clear_selection = QPushButton("Снять выделение")
        self.btn_clear_selection.clicked.connect(self.clear_selection)
        header.addWidget(self.btn_clear_selection)
        
        layout.addLayout(header)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["№", "Таймкод", "Сочетание", "Экспорт"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemClicked.connect(self.on_item_clicked)
        
        layout.addWidget(self.table)
        
        self.info_label = QLabel("Найдено: 0 сочетаний")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.info_label)
    
    def set_results(self, results):
        self.results = results
        self.table.setRowCount(len(results))
        
        for row, res in enumerate(results):
            num_item = QTableWidgetItem(str(row + 1))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, num_item)
            
            timecode = f"{res['start']:.3f}s - {res['end']:.3f}s"
            time_item = QTableWidgetItem(timecode)
            self.table.setItem(row, 1, time_item)
            
            combination = ' '.join(res['combination'])
            combo_item = QTableWidgetItem(combination)
            self.table.setItem(row, 2, combo_item)
            
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            
            checkbox = QCheckBox()
            checkbox.setChecked(res.get('export', False))
            checkbox.stateChanged.connect(lambda state, r=row: self.on_checkbox_changed(r, state))
            checkbox_layout.addWidget(checkbox)
            
            self.table.setCellWidget(row, 3, checkbox_widget)
        
        self.info_label.setText(f"Найдено: {len(results)} сочетаний")
    
    def on_item_clicked(self, item):
        row = item.row()
        if row < len(self.results):
            res = self.results[row]
            self.result_clicked.emit(res['start'], res['end'])
    
    def on_checkbox_changed(self, row, state):
        if row < len(self.results):
            self.results[row]['export'] = (state == Qt.CheckState.Checked.value)
            self.selection_changed.emit() 
    
    def select_all(self):
        for row in range(self.table.rowCount()):
            checkbox_widget = self.table.cellWidget(row, 3)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(True)
                    self.results[row]['export'] = True
        
        self.selection_changed.emit()
    
    def clear_selection(self):
        for row in range(self.table.rowCount()):
            checkbox_widget = self.table.cellWidget(row, 3)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(False)
                    self.results[row]['export'] = False
        
        self.selection_changed.emit()
    
    def get_selected_results(self):
        return [res for res in self.results if res.get('export', False)]
    
    def get_selected_indices(self):
        return [i for i, res in enumerate(self.results) if res.get('export', False)]
    
    def set_selected_indices(self, indices):
        if indices is None:
            return
        
        for i, res in enumerate(self.results):
            res['export'] = i in indices
        
        for row in range(self.table.rowCount()):
            checkbox_widget = self.table.cellWidget(row, 3)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(row in indices)
    
    def clear(self):
        self.results = []
        self.table.setRowCount(0)
        self.info_label.setText("Найдено: 0 сочетаний")