# src/exporters/exporter.py

import os
import csv
import json
from datetime import datetime
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtCore import QRect, QSize

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class Exporter:
    """Экспорт данных в различные форматы"""
    
    def __init__(self):
        self.temp_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "SpeechAnalyzer")
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def export(self, phonemes, audio_path, params):
        """Основной метод экспорта"""
        file_path = params['file_path']
        format_type = params['format']
        content_type = params['content_type']
        include_timestamps = params.get('include_timestamps', True)
        include_search = params.get('include_search_results', False)
        search_results = params.get('search_results', [])
        
        ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if ext == '.txt':
                self._export_txt(file_path, phonemes, include_timestamps, include_search, search_results)
            elif ext == '.csv':
                self._export_csv(file_path, phonemes, include_timestamps, include_search, search_results)
            elif ext == '.pdf':
                self._export_pdf(file_path, phonemes, content_type, include_timestamps, include_search, search_results)
            elif ext == '.png':
                self._export_png(file_path, phonemes, content_type, include_timestamps)
            elif ext == '.TextGrid':
                self._export_textgrid(file_path, phonemes)
            elif ext == '.PitchTier':
                self._export_pitchtier(file_path, phonemes)
            else:
                QMessageBox.warning(None, "Ошибка", f"Неподдерживаемый формат: {ext}")
                
        except Exception as e:
            QMessageBox.critical(None, "Ошибка экспорта", f"Не удалось экспортировать: {str(e)}")
    
    def _export_txt(self, file_path, phonemes, include_timestamps, include_search, search_results):
        """Экспорт в TXT"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("SPEECHANALYZER PRO EXPORT\n")
            f.write(f"Дата экспорта: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Количество фонем: {len(phonemes)}\n")
            f.write("=" * 50 + "\n\n")
            
            if include_timestamps:
                f.write("ФОНЕМЫ С ТАЙМКОДАМИ:\n")
                f.write("-" * 40 + "\n")
                for i, ph in enumerate(phonemes):
                    f.write(f"{i+1:3d}. [{ph['start']:6.3f}s - {ph['end']:6.3f}s] {ph['label']}\n")
            else:
                f.write("ФОНЕМЫ:\n")
                f.write("-" * 40 + "\n")
                for i, ph in enumerate(phonemes):
                    f.write(f"{i+1:3d}. {ph['label']}\n")
            
            if include_search and search_results:
                f.write("\n" + "=" * 50 + "\n")
                f.write("РЕЗУЛЬТАТЫ ПОИСКА:\n")
                f.write("-" * 40 + "\n")
                for res in search_results:
                    f.write(f"[{res['start']:.3f}s - {res['end']:.3f}s] {''.join(res['combination'])}\n")
    
    def _export_csv(self, file_path, phonemes, include_timestamps, include_search, search_results):
        """Экспорт в CSV"""
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(["Экспорт SpeechAnalyzer Pro", datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow([])
            
            if include_timestamps:
                writer.writerow(["Номер", "Начало (с)", "Конец (с)", "Длительность (с)", "Фонема"])
                for i, ph in enumerate(phonemes):
                    writer.writerow([i+1, ph['start'], ph['end'], ph['end']-ph['start'], ph['label']])
            else:
                writer.writerow(["Номер", "Фонема"])
                for i, ph in enumerate(phonemes):
                    writer.writerow([i+1, ph['label']])
            
            if include_search and search_results:
                writer.writerow([])
                writer.writerow(["РЕЗУЛЬТАТЫ ПОИСКА"])
                writer.writerow(["Начало (с)", "Конец (с)", "Сочетание"])
                for res in search_results:
                    writer.writerow([res['start'], res['end'], ''.join(res['combination'])])
    
    def _export_pdf(self, file_path, phonemes, content_type, include_timestamps, include_search, search_results):
        """Экспорт в PDF"""
        if not REPORTLAB_AVAILABLE:
            QMessageBox.warning(None, "Ошибка", "Для экспорта в PDF установите reportlab: pip install reportlab")
            return
        
        doc = SimpleDocTemplate(file_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Заголовок
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, alignment=1)
        story.append(Paragraph("SpeechAnalyzer Pro - Отчёт", title_style))
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}", styles['Normal']))
        story.append(Spacer(1, 0.3 * inch))
        
        # Таблица фонем
        if content_type in ['phonemes_only', 'both']:
            story.append(Paragraph("Фонемы", styles['Heading2']))
            story.append(Spacer(1, 0.1 * inch))
            
            if include_timestamps:
                data = [["№", "Начало", "Конец", "Длит.", "Фонема"]]
                for i, ph in enumerate(phonemes):
                    data.append([str(i+1), f"{ph['start']:.3f}", f"{ph['end']:.3f}", f"{ph['end']-ph['start']:.3f}", ph['label']])
            else:
                data = [["№", "Фонема"]]
                for i, ph in enumerate(phonemes):
                    data.append([str(i+1), ph['label']])
            
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(table)
            story.append(Spacer(1, 0.3 * inch))
        
        # Результаты поиска
        if include_search and search_results:
            story.append(Paragraph("Результаты поиска", styles['Heading2']))
            story.append(Spacer(1, 0.1 * inch))
            
            data = [["Начало", "Конец", "Сочетание"]]
            for res in search_results:
                data.append([f"{res['start']:.3f}", f"{res['end']:.3f}", ''.join(res['combination'])])
            
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(table)
        
        doc.build(story)
    
    def _export_png(self, file_path, phonemes, content_type, include_timestamps):
        """Экспорт в PNG (только график)"""
        if not MATPLOTLIB_AVAILABLE:
            QMessageBox.warning(None, "Ошибка", "Для экспорта в PNG установите matplotlib: pip install matplotlib")
            return
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Создаём визуализацию фонем
        y_positions = []
        labels = []
        for i, ph in enumerate(phonemes):
            mid = (ph['start'] + ph['end']) / 2
            y_positions.append(mid)
            labels.append(ph['label'])
            # Рисуем блоки
            ax.axvspan(ph['start'], ph['end'], alpha=0.3, color='blue')
        
        ax.set_xlim(0, phonemes[-1]['end'] if phonemes else 1)
        ax.set_ylim(-1, 1)
        ax.set_xlabel("Время (с)")
        ax.set_ylabel("Амплитуда")
        ax.set_title("Фонемная разметка")
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(file_path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def _export_textgrid(self, file_path, phonemes):
        """Экспорт в TextGrid (формат Praat)"""
        if not phonemes:
            # Создаём пустой TextGrid
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('File type = "ooTextFile"\n')
                f.write('Object class = "TextGrid"\n\n')
                f.write('xmin = 0\n')
                f.write('xmax = 1\n')
                f.write('tiers? <exists>\n')
                f.write('size = 1\n')
                f.write('item []:\n')
                f.write('    item [1]:\n')
                f.write('        class = "IntervalTier"\n')
                f.write('        name = "phonemes"\n')
                f.write('        xmin = 0\n')
                f.write('        xmax = 1\n')
                f.write('        intervals: size = 0\n')
            return
    
    def _export_pitchtier(self, file_path, phonemes):
        """Экспорт в PitchTier (формат Praat)"""
        if not phonemes:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('File type = "ooTextFile"\n')
                f.write('Object class = "PitchTier"\n\n')
                f.write('xmin = 0\n')
                f.write('xmax = 1\n')
                f.write('points: size = 0\n')
            return