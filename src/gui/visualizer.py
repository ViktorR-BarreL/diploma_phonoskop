import numpy as np
import librosa
import pyqtgraph as pg
from PyQt6.QtWidgets import QMenu, QApplication
from PyQt6.QtCore import pyqtSignal, Qt, QRectF, QTimer
from PyQt6.QtGui import QCursor
from src.gui.phonetic_map import IPA_TO_USER

class PhonemeRegion(pg.LinearRegionItem):
    clicked = pyqtSignal(int)
    double_clicked = pyqtSignal(int)
    right_clicked = pyqtSignal(int, object)

    def __init__(self, index, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.index = index
        self.setMovable(False) 
        self.setAcceptHoverEvents(True)

    def mouseClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)
            ev.accept()
        elif ev.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit(self.index, ev.screenPos())
            ev.accept()

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.index)
            ev.accept()


class AudioCanvas(pg.GraphicsLayoutWidget):
    boundary_changed = pyqtSignal(int, str, float)
    request_delete = pyqtSignal(int)
    request_keyboard = pyqtSignal(int)
    request_add = pyqtSignal(int, float)
    request_play_index = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackground('k')
        
        self.p_wav = self.addPlot(row=0, col=0, title="Осциллограмма")
        self.p_spec = self.addPlot(row=1, col=0, title="Спектрограмма")
        self.plots = [self.p_wav, self.p_spec]

        for p in self.plots:
            p.setXLink(self.p_wav)
            p.setMenuEnabled(False)
            p.setLimits(xMin=0)
            p.setMouseEnabled(x=True, y=False)
            p.setClipToView(True) # Не рисовать то, что за краем экрана

        self.img_spec = pg.ImageItem()
        self.p_spec.addItem(self.img_spec)

        self.playheads = [pg.InfiniteLine(pos=0, pen=pg.mkPen('y', width=1), movable=False) for _ in self.plots]
        for i, p in enumerate(self.plots):
            p.addItem(self.playheads[i])

        self.raw_phonemes = []
        self.boundaries = {}
        self.regions = {}
        self.labels = {}
        
        self.duration = 0
        self.selected_boundary = None
        self._view_mode = "RU"

        self.lod_timer = QTimer()
        self.lod_timer.setSingleShot(True)
        self.lod_timer.timeout.connect(self.update_lod)
        
        # Следим за изменением масштаба
        self.p_wav.sigXRangeChanged.connect(lambda: self.lod_timer.start(100))

    def plot_audio(self, file_path):
        y, sr = librosa.load(file_path, sr=16000)
        self.duration = len(y) / sr
        
        for p in self.plots:
            p.setLimits(xMax=self.duration)
            p.setXRange(0, min(10, self.duration))

        self.p_wav.clear()
        self.p_wav.addItem(self.playheads[0])
        
        # Отрисовка волны с ограничением точек (оптимизация графики)
        step = max(1, len(y) // 40000)
        y_sampled = y[::step]
        t_sampled = np.linspace(0, self.duration, len(y_sampled))
        self.p_wav.plot(t_sampled, y_sampled, pen=pg.mkPen('#555', width=1))
        
        S = np.abs(librosa.stft(y, n_fft=512, hop_length=256))
        S_db = librosa.amplitude_to_db(S, ref=np.max)
        self.img_spec.setImage(S_db.T)
        self.img_spec.setRect(QRectF(0, 0, self.duration, 8000))
        self.img_spec.setLevels([-70, 0])
        
        self.clear_ui()

    def draw_phonemes(self, phoneme_list, view_mode="RU"):
        self.clear_ui()
        self.raw_phonemes = phoneme_list
        self._view_mode = view_mode
        
        if not phoneme_list: 
            return

        # Рисуем все границы
        for i, phn in enumerate(phoneme_list):
            self.create_boundary_pair(i, phn['start'], phn['end'])
            
            # Инициализируем пустые списки для регионов и меток
            self.regions[i] = []
            self.labels[i] = []

        self.update_lod()

    def update_lod(self):
        if not self.raw_phonemes: 
            return
        
        view_range = self.p_wav.viewRange()[0]
        x_start, x_end = view_range
        visible_width = x_end - x_start

        # Если в окне больше 20 секунд - текст не рисуем вообще
        show_text = visible_width < 20.0
        # Если в окне больше 60 секунд - фон (регионы) не рисуем
        show_regions = visible_width < 60.0

        for i, phn in enumerate(self.raw_phonemes):
            # Проверяем, попадает ли фонема в экран (с небольшим запасом)
            is_visible = phn['end'] > x_start - 1 and phn['start'] < x_end + 1
            
            # УПРАВЛЕНИЕ РЕГИОНАМИ НА ВСЕХ ГРАФИКАХ
            if is_visible and show_regions:
                if not self.regions[i]:
                    for p in self.plots:
                        r = PhonemeRegion(i, [phn['start'], phn['end']], 
                                        brush=pg.mkBrush(100, 100, 255, 35))
                        r.clicked.connect(self.request_play_index.emit)
                        r.double_clicked.connect(self.request_keyboard.emit)
                        r.right_clicked.connect(self.show_context_menu)
                        p.addItem(r)
                        self.regions[i].append(r)
                else: 
                    for r in self.regions[i]: 
                        r.show()
            else:
                if self.regions[i]:
                    for r in self.regions[i]: 
                        r.hide()

            if is_visible and show_text:
                if not self.labels[i]:
                    label = IPA_TO_USER.get(phn['label'], phn['label']) if self._view_mode == "RU" else phn['label']
                    for p_idx, p in enumerate(self.plots):
                        # Y-позиция зависит от графика
                        y_pos = 0 if p_idx == 0 else 4000
                        txt = pg.TextItem(text=label, color='w', anchor=(0.5, 0.5))
                        txt.setPos((phn['start'] + phn['end'])/2, y_pos)
                        txt.setZValue(10)
                        p.addItem(txt)
                        self.labels[i].append(txt)
                else:
                    for lbl in self.labels[i]: 
                        lbl.show()
            else:
                if self.labels[i]:
                    for lbl in self.labels[i]: 
                        lbl.hide()

    def create_boundary_pair(self, idx, s_t, e_t):
        self.boundaries[idx] = {'start': [], 'end': []}
        if s_t >= e_t: e_t = s_t + 0.1
        
        for b_type, pos, default_color in [('start', s_t, '#9b59b6'), ('end', e_t, '#3498db')]:
            lines = []
            for p in self.plots:
                line = pg.InfiniteLine(pos=pos, movable=True, pen=pg.mkPen(default_color, width=3))
                line.index = idx
                line.b_type = b_type
                line.default_color = default_color
                line.selected_color = '#f1c40f' if b_type == 'start' else '#2ecc71'
                line.sigPositionChanged.connect(self.sync_lines_realtime)
                line.sigClicked.connect(self.handle_line_click)
                p.addItem(line)
                lines.append(line)
            self.boundaries[idx][b_type] = lines

    def handle_line_click(self, line, ev):
        if self.selected_boundary:
            old_idx, old_type = self.selected_boundary
            if old_idx in self.boundaries:
                old_color = self.boundaries[old_idx][old_type][0].default_color
                for l in self.boundaries[old_idx][old_type]: l.setPen(pg.mkPen(old_color, width=3))
        
        self.selected_boundary = (line.index, line.b_type)
        for l in self.boundaries[line.index][line.b_type]:
            l.setPen(pg.mkPen(line.selected_color, width=4))
        
        if ev.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(line.index, ev.screenPos())

    def sync_lines_realtime(self, dragged_line):
        val = max(0, min(dragged_line.value(), self.duration))
        idx, b_type = dragged_line.index, dragged_line.b_type
        
        for line in self.boundaries[idx][b_type]:
            line.blockSignals(True)
            line.setValue(val)
            line.blockSignals(False)
        
        if idx in self.regions and self.regions[idx]:
            for r in self.regions[idx]:
                reg = list(r.getRegion())
                if b_type == 'start': reg[0] = val
                else: reg[1] = val
                r.setRegion(reg)
                
        if idx in self.labels and self.labels[idx]:
            # Берем актуальные границы из региона
            start = self.boundaries[idx]['start'][0].value()
            end = self.boundaries[idx]['end'][0].value()
            for lbl in self.labels[idx]:
                lbl.setPos((start + end)/2, lbl.pos().y())
        
        self.boundary_changed.emit(idx, b_type, val)

    def show_context_menu(self, idx, pos):
        menu = QMenu()
        add_act = menu.addAction("Добавить здесь")
        del_act = menu.addAction("Удалить этот сегмент")
        action = menu.exec(pos.toPoint() if hasattr(pos, 'toPoint') else QCursor.pos())
        if action == add_act:
            t = self.boundaries[idx]['end'][0].value() if idx in self.boundaries else 0
            self.request_add.emit(idx, t)
        elif action == del_act:
            self.request_delete.emit(idx)

    def clear_ui(self):
        for b_dict in self.boundaries.values():
            for lines in b_dict.values():
                for line in lines:
                    for p in self.plots: 
                        p.removeItem(line)
        
        for r_list in self.regions.values():
            for r in r_list:
                for p in self.plots: 
                    p.removeItem(r)
        
        for t_list in self.labels.values():
            for t in t_list:
                for p in self.plots: 
                    p.removeItem(t)
        
        self.boundaries = {}
        self.regions = {}
        self.labels = {}
        self.raw_phonemes = []
        self.selected_boundary = None

    def update_playhead(self, t):
        for ph in self.playheads: ph.setValue(t)