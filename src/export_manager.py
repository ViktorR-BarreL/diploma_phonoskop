import os
import csv
import re
from datetime import datetime
from collections import Counter
from PyQt6.QtGui import QTextDocument
from PyQt6.QtPrintSupport import QPrinter

class ExportManager:
    
    def __init__(self, main_window):
        self.main = main_window
    
    def export_to_txt(self, params):
        '''Экспорт в текстовый файл с расширенной информацией и статистикой'''
        file_path = params['file_path']
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("[ф]оноскоп - Export Data\n")
            f.write("="*70 + "\n")
            f.write(f"Export date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Audio file: {os.path.basename(self.main.current_audio_path) if self.main.current_audio_path else 'Unknown'}\n")
            f.write(f"Duration: {self.main.canvas.duration:.2f} sec\n")
            f.write("="*70 + "\n\n")
            
            if params['export_phonemes']:
                f.write("PHONEME TRANSCRIPTION\n")
                f.write("-"*70 + "\n")
                
                if params['include_timestamps']:
                    if params['include_duration']:
                        f.write(f"{'N':<4} {'Start,s':<10} {'End,s':<10} {'Dur.,s':<10} {'Phoneme':<15}\n")
                    else:
                        f.write(f"{'N':<4} {'Start,s':<10} {'End,s':<10} {'Phoneme':<15}\n")
                    f.write("-"*70 + "\n")
                    
                    for i, ph in enumerate(self.main.phonemes_data):
                        if params['include_duration']:
                            duration = ph['end'] - ph['start']
                            f.write(f"{i+1:<4} {ph['start']:<10.3f} {ph['end']:<10.3f} {duration:<10.3f} {ph['label']:<15}\n")
                        else:
                            f.write(f"{i+1:<4} {ph['start']:<10.3f} {ph['end']:<10.3f} {ph['label']:<15}\n")
                else:
                    for i, ph in enumerate(self.main.phonemes_data):
                        f.write(f"{i+1}. {ph['label']}\n")
                
                f.write("\n")
                
                phoneme_counts = Counter([ph['label'] for ph in self.main.phonemes_data])
                f.write("PHONEME STATISTICS\n")
                f.write("-"*70 + "\n")
                for phoneme, count in sorted(phoneme_counts.items()):
                    f.write(f"{phoneme}: {count}\n")
                f.write("\n")
            
            if params.get('export_text_transcript', False) and self.main.text_transcript:
                f.write("TEXT TRANSCRIPT\n")
                f.write("-"*70 + "\n")
                f.write(self.main.text_transcript + "\n\n")
            
            if params['export_search_results'] and hasattr(self.main.search_results, 'results') and self.main.search_results.results:
                selected_results = [res for res in self.main.search_results.results if res.get('export', False)]
                f.write("SEARCH RESULTS (selected for export)\n")
                f.write("-"*70 + "\n")
                
                if not selected_results:
                    f.write("(No results selected for export)\n")
                else:
                    for i, res in enumerate(selected_results):
                        combination = ' '.join(res['combination'])
                        if params['include_timestamps']:
                            f.write(f"{i+1}. [{res['start']:.3f}s - {res['end']:.3f}s] {combination}\n")
                        else:
                            f.write(f"{i+1}. {combination}\n")
                f.write("\n")
            
            f.write("="*70 + "\n")
            f.write("End of file\n")
    
    def export_to_csv(self, params):
        '''Экспорт в CSV с расширенной информацией и статистикой'''
        file_path = params['file_path']
        
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            
            writer.writerow(["[ф]оноскоп Export"])
            writer.writerow([f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
            writer.writerow([f"Audio: {os.path.basename(self.main.current_audio_path) if self.main.current_audio_path else 'Unknown'}"])
            writer.writerow([])
            
            if params['export_phonemes']:
                writer.writerow(["PHONEME TRANSCRIPTION"])
                if params['include_timestamps']:
                    if params['include_duration']:
                        writer.writerow(["N", "Start,s", "End,s", "Duration,s", "Phoneme"])
                    else:
                        writer.writerow(["N", "Start,s", "End,s", "Phoneme"])
                else:
                    writer.writerow(["N", "Phoneme"])
                
                for i, ph in enumerate(self.main.phonemes_data):
                    if params['include_timestamps']:
                        if params['include_duration']:
                            duration = ph['end'] - ph['start']
                            writer.writerow([i+1, f"{ph['start']:.3f}", f"{ph['end']:.3f}", f"{duration:.3f}", ph['label']])
                        else:
                            writer.writerow([i+1, f"{ph['start']:.3f}", f"{ph['end']:.3f}", ph['label']])
                    else:
                        writer.writerow([i+1, ph['label']])
                
                writer.writerow([])
                
                phoneme_counts = Counter([ph['label'] for ph in self.main.phonemes_data])
                writer.writerow(["PHONEME STATISTICS"])
                writer.writerow(["Phoneme", "Count"])
                for phoneme, count in sorted(phoneme_counts.items()):
                    writer.writerow([phoneme, count])
                writer.writerow([])
            
            if params['export_search_results'] and hasattr(self.main.search_results, 'results') and self.main.search_results.results:
                selected_results = [res for res in self.main.search_results.results if res.get('export', False)]
                writer.writerow(["SEARCH RESULTS (selected)"])
                writer.writerow(["N", "Start,s", "End,s", "Duration,s", "Combination"])
                for i, res in enumerate(selected_results):
                    duration = res['end'] - res['start']
                    combination = ' '.join(res['combination'])
                    writer.writerow([i+1, f"{res['start']:.3f}", f"{res['end']:.3f}", f"{duration:.3f}", combination])
    
    def export_to_pdf(self, params):
        '''Экспорт в PDF с расширенной информацией и статистикой'''        
        file_path = params['file_path']
        
        html_content = self.generate_pdf_html(params, saved_graphs=[])
        
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(file_path)
            
            doc = QTextDocument()
            doc.setHtml(html_content)
            
            if hasattr(doc, 'print'):
                doc.print(printer)
            else:
                doc.print_(printer)
                
        except Exception as e:
            html_path = file_path.replace('.pdf', '.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            raise Exception(f"PDF export failed, saved as HTML instead: {html_path}")

    def generate_pdf_html(self, params, saved_graphs):
        '''Генерация HTML для PDF с учётом режима отображения фонем'''
        
        view_mode = self.main.phoneme_view_mode  # "RU" или "IPA"
        
        display_phonemes = []
        for ph in self.main.phonemes_data:
            if view_mode == "RU":
                from src.gui.phonetic_map import IPA_TO_USER
                label = IPA_TO_USER.get(ph['label'], ph['label'])
            else:
                label = ph['label']
            display_phonemes.append({
                'start': ph['start'],
                'end': ph['end'],
                'label': label
            })
        
        total_phonemes = len(display_phonemes)
        use_compact_table = total_phonemes > 500
        
        html = f"""
        <html>
        <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4;
                margin: 1.5cm;
            }}
            
            body {{
                font-family: 'Times New Roman', Times, serif;
                font-size: {'10pt' if use_compact_table else '14pt'};
                line-height: 1.3;
                color: #000000;
            }}
            
            h1 {{
                font-size: 16pt;
                font-weight: bold;
                text-align: center;
                margin-top: 20px;
                margin-bottom: 20px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            
            h2 {{
                font-size: 14pt;
                font-weight: bold;
                font-style: italic;
                margin-top: 25px;
                margin-bottom: 15px;
                border-bottom: 1px solid #000000;
                padding-bottom: 5px;
            }}
            
            p {{
                font-size: {'10pt' if use_compact_table else '14pt'};
                line-height: 1.5;
                margin-bottom: 10px;
                text-align: justify;
            }}
            
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 15px 0;
                font-size: {'8pt' if use_compact_table else '12pt'};
                border: 1px solid #000000;
            }}
            
            th {{
                background-color: #f5f5f5;
                font-weight: bold;
                border: 1px solid #000000;
                padding: {'3px 3px' if use_compact_table else '6px 5px'};
                text-align: center;
            }}
            
            td {{
                border: 1px solid #000000;
                padding: {'2px 3px' if use_compact_table else '5px 5px'};
            }}
            
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            
            .header p {{
                text-align: center;
                margin: 5px 0;
            }}
            
            .footer {{
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #000000;
                font-size: 11pt;
                color: #000000;
                font-style: italic;
            }}
            
            .info-text {{
                font-size: {'10pt' if use_compact_table else '14pt'};
            }}
            
            .note {{
                font-style: italic;
                color: #666;
                margin-top: 20px;
            }}
        </style>
        </head>
        <body>
        """
        
        # Заголовок отчета
        html += f"""
        <div class="header">
            <h1>[ф]оноскоп — Отчет о фонетическом анализе</h1>
            <p class="info-text"><strong>Дата создания отчета:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
            <p class="info-text"><strong>Аудиофайл:</strong> {os.path.basename(self.main.current_audio_path) if self.main.current_audio_path else 'Неизвестно'}</p>
            <p class="info-text"><strong>Общая длительность:</strong> {self.main.canvas.duration:.2f} сек ({self.main.canvas.duration/60:.2f} мин)</p>
            <p class="info-text"><strong>Режим отображения:</strong> {'Русские фонемы' if view_mode == 'RU' else 'IPA'}</p>
        </div>
        """
        
        # Таблица фонем
        if params.get('pdf_include_table', True) and display_phonemes:
            html += "<h2>1. Фонемная расшифровка</h2>"
            
            total_phonemes = len(display_phonemes)
            unique_phonemes = len(set(ph['label'] for ph in display_phonemes))
            
            html += f"""
            <p class="info-text"><strong>Всего фонем:</strong> {total_phonemes}</p>
            <p class="info-text"><strong>Уникальных фонем:</strong> {unique_phonemes}</p>
            """
            
            if total_phonemes > 1000:
                html += '<p class="note">Примечание: показаны первые 1000 фонем (полный список в TXT/CSV экспорте)</p>'
                display_phonemes = display_phonemes[:1000]
            
            html += "<table>"
            html += "<tr><th>№</th><th>Начало, с</th><th>Конец, с</th><th>Длит., с</th><th>Фонема</th></tr>"
            
            for i, ph in enumerate(display_phonemes):
                duration = ph['end'] - ph['start']
                html += f"""
                <tr>
                    <td style="text-align: center;">{i+1}</td>
                    <td style="text-align: right;">{ph['start']:.3f}</td>
                    <td style="text-align: right;">{ph['end']:.3f}</td>
                    <td style="text-align: right;">{duration:.3f}</td>
                    <td style="text-align: center; font-weight: bold;">{ph['label']}</td>
                </tr>
                """
            
            html += "</table>"
        
        # Текстовая расшифровка
        if params.get('pdf_include_text', True) and self.main.text_transcript:
            section_num = 2 if params.get('pdf_include_table', True) else 1
            html += f"<h2>{section_num}. Текстовая расшифровка</h2>"
            html += f'<p class="info-text" style="background-color: #f9f9f9; padding: 15px; border: 1px solid #ddd;">{self.main.text_transcript}</p>'
        
        # Результаты поиска
        if params.get('export_search_results', False) and hasattr(self.main.search_results, 'results') and self.main.search_results.results:
            selected_results = [res for res in self.main.search_results.results if res.get('export', False)]
            if selected_results:
                section_num = 2
                if params.get('pdf_include_table', True):
                    section_num += 1
                if params.get('pdf_include_text', True) and self.main.text_transcript:
                    section_num += 1
                    
                html += f"<h2>{section_num}. Результаты поиска (отмеченные для экспорта)</h2>"
                html += f'<p class="info-text"><strong>Найдено сочетаний:</strong> {len(selected_results)}</p>'
                
                html += "<table>"
                html += "<tr><th>№</th><th>Начало, с</th><th>Конец, с</th><th>Длит., с</th><th>Сочетание фонем</th></tr>"
                
                for i, res in enumerate(selected_results):
                    duration = res['end'] - res['start']
                    if view_mode == "RU":
                        from src.gui.phonetic_map import IPA_TO_USER
                        combination = ' '.join(IPA_TO_USER.get(p, p) for p in res['combination'])
                    else:
                        combination = ' '.join(res['combination'])
                        
                    html += f"""
                    <tr>
                        <td style="text-align: center;">{i+1}</td>
                        <td style="text-align: right;">{res['start']:.3f}</td>
                        <td style="text-align: right;">{res['end']:.3f}</td>
                        <td style="text-align: right;">{duration:.3f}</td>
                        <td style="text-align: center;">{combination}</td>
                    </tr>
                    """
                
                html += "</table>"
        
        
        # Футер
        html += """
        <div class="footer">
            <p>Отчет сгенерирован автоматически программой [ф]оноскоп 2026</p>
        </div>
        </body>
        </html>
        """
        
        return html
    
    def export_to_textgrid(self, params):
        """Экспорт в TextGrid (формат Praat)"""
        file_path = params['file_path']
        base_name = os.path.splitext(file_path)[0]
        ext = os.path.splitext(file_path)[1]
        
        export_all = params.get('export_all_phonemes', True)
        export_search = params.get('export_search_results', False)
        # Настройка разделения по слоям
        separate_tiers = params.get('praat_include_tiers', False)
        
        exported_files = []
        
        if export_all:
            all_file = f"{base_name}_all{ext}"
            self._export_textgrid_file(all_file, self.main.phonemes_data, separate_tiers)
            exported_files.append(all_file)

        if export_search and hasattr(self.main.search_results, 'results') and self.main.search_results.results:
            selected_results = [res for res in self.main.search_results.results if res.get('export', False)]
            
            if selected_results:
                selected_phonemes = []
                for res in selected_results:
                    start_idx, end_idx = res['indices']
                    for i in range(start_idx, end_idx + 1):
                        if i < len(self.main.phonemes_data):
                            selected_phonemes.append(self.main.phonemes_data[i])
                
                unique_phonemes = []
                seen = set()
                for ph in selected_phonemes:
                    key = (ph['start'], ph['end'], ph['label'])
                    if key not in seen:
                        seen.add(key)
                        unique_phonemes.append(ph)
                
                search_file = f"{base_name}_search_results{ext}"
                self._export_textgrid_file(search_file, unique_phonemes, separate_tiers)
                exported_files.append(search_file)
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self.main, "Внимание", "Нет выбранных результатов поиска для экспорта")

        if exported_files:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self.main,
                "Экспорт в TextGrid",
                f"Экспортировано файлов: {len(exported_files)}\n\n" + 
                "\n".join([os.path.basename(f) for f in exported_files])
            )

    def _export_textgrid_file(self, file_path, phonemes_data, separate_tiers=False):
        """Внутренний метод для формирования структуры TextGrid (совместим с Praat)"""
        duration = self.main.canvas.duration
        
        if separate_tiers:
            tier_names = sorted(list(set(ph['label'] for ph in phonemes_data)))
        else:
            tier_names = ["phonemes"]

        with open(file_path, 'w', encoding='utf-8') as f:
            # Заголовок формата
            f.write('File type = "ooTextFile"\n')
            f.write('Object class = "TextGrid"\n\n')
            f.write(f'xmin = 0\n')
            f.write(f'xmax = {duration}\n')
            f.write('tiers? <exists>\n')
            f.write(f'size = {len(tier_names)}\n')
            
            for i, name in enumerate(tier_names, 1):
                f.write(f'item [{i}]:\n')
                f.write('    class = "IntervalTier"\n')
                f.write(f'    name = "{name}"\n')
                f.write(f'    xmin = 0\n')
                f.write(f'    xmax = {duration}\n')
                
                if separate_tiers:
                    current_set = [ph for ph in phonemes_data if ph['label'] == name]
                else:
                    current_set = phonemes_data
                
                current_set = sorted(current_set, key=lambda x: x['start'])

                intervals = []
                last_time = 0.0
                
                for ph in current_set:
                    if ph['start'] > last_time:
                        intervals.append((last_time, ph['start'], ""))
                    
                    intervals.append((ph['start'], ph['end'], ph['label']))
                    last_time = ph['end']
                
                if last_time < duration:
                    intervals.append((last_time, duration, ""))
                
                f.write(f'    intervals: size = {len(intervals)}\n')
                for j, (start, end, label) in enumerate(intervals, 1):
                    f.write(f'    intervals [{j}]:\n')
                    f.write(f'        xmin = {start}\n')
                    f.write(f'        xmax = {end}\n')
                    safe_label = label.replace('"', '""')
                    f.write(f'        text = "{safe_label}"\n')

    def export_to_pitchtier(self, params):
        """Экспорт в PitchTier (формат Praat)"""
        file_path = params['file_path']
        base_name = os.path.splitext(file_path)[0]
        ext = os.path.splitext(file_path)[1]
        
        export_all = params.get('export_all_phonemes', True)
        export_search = params.get('export_search_results', False)
        
        selected_results = []
        if export_search and hasattr(self.main.search_results, 'results') and self.main.search_results.results:
            selected_results = [res for res in self.main.search_results.results if res.get('export', False)]
            if not selected_results:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self.main, "Внимание", "Нет выбранных результатов поиска для экспорта")
                export_search = False
        
        exported_files = []
        
        if export_all:
            all_file = f"{base_name}_all{ext}"
            self._export_pitchtier_file(all_file, self.main.phonemes_data)
            exported_files.append(all_file)
        
        if export_search:
            selected_phonemes = []
            for res in selected_results:
                start_idx, end_idx = res['indices']
                for i in range(start_idx, end_idx + 1):
                    if i < len(self.main.phonemes_data):
                        selected_phonemes.append(self.main.phonemes_data[i])
            
            unique_phonemes = []
            seen = set()
            for ph in selected_phonemes:
                key = (ph['start'], ph['end'], ph['label'])
                if key not in seen:
                    seen.add(key)
                    unique_phonemes.append(ph)
            
            search_file = f"{base_name}_search_results{ext}"
            self._export_pitchtier_file(search_file, unique_phonemes)
            exported_files.append(search_file)
        
        if exported_files:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self.main,
                "Экспорт в PitchTier",
                f"Экспортировано {len(exported_files)} файлов:\n" + "\n".join(os.path.basename(f) for f in exported_files)
            )

    def _export_pitchtier_file(self, file_path, phonemes_data):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('File type = "ooTextFile"\n')
            f.write('Object class = "PitchTier"\n\n')
            f.write(f'xmin = 0\n')
            f.write(f'xmax = {self.main.canvas.duration}\n')
            f.write(f'points: size = {len(phonemes_data)}\n')
            
            for i, ph in enumerate(phonemes_data, 1):
                mid_time = (ph['start'] + ph['end']) / 2
                frequency = 100 + (hash(ph['label']) % 200)
                
                f.write(f'points [{i}]:\n')
                f.write(f'    number = {mid_time}\n')
                f.write(f'    value = {frequency}\n')