import os
import re
from dotenv import load_dotenv
import google.generativeai as genai
from PyQt6.QtWidgets import (
    QMainWindow, QTableWidgetItem, QHeaderView, QMessageBox, QProgressDialog, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QBrush
from PyQt6.uic import loadUi
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from docx import Document
from .gemini_worker import GeminiWorker
from .utils import detect_language, get_highlighted_html, parse_data

class ExploitSearchApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.exploits = []
        self.gemini = None
        loadUi("gui.ui", self)
        self.setup_connections()
        self.load_data()
        self.configure_ai()
        self.resultsTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.resultsTable.setSortingEnabled(True)

    def setup_connections(self):
        self.searchInput.returnPressed.connect(self.search_exploits)
        self.searchBtn.clicked.connect(self.search_exploits)
        self.exportPdfBtn.clicked.connect(self.export_analysis_to_pdf)
        self.exportDocxBtn.clicked.connect(self.export_analysis_to_docx)
        self.resultsTable.cellClicked.connect(self.handle_cell_click)

    def configure_ai(self):
        load_dotenv()
        key = os.getenv('API_KEY')
        if key:
            try:
                genai.configure(api_key=key)
                self.gemini = genai.GenerativeModel('gemini-2.0-flash-001')
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'AI configuration failed: {str(e)}')
        else:
            QMessageBox.warning(self, 'Warning', 'AI analysis disabled - no API key found in .env file')

    def load_data(self):
        try:
            self.exploits = parse_data('./data/files_exploits.csv')
        except FileNotFoundError:
            QMessageBox.critical(self, 'Error', 'File "files_exploits.csv" not found.')
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to load data: {str(e)}')

    def search_exploits(self):
        query = self.searchInput.text().lower()
        results = [e for e in self.exploits if all(
            term in ' '.join([
                e['signatures'].lower(),
                e['description'].lower(),
                e['type'].lower(),
                e['platform'].lower()
            ]) for term in query.split()
        )]
        results.sort(key=lambda x: (not bool(x['signatures'].strip()), -int(x['date'].replace('-', ''))))
        self.show_results(results)

    def show_results(self, exploits):
        self.resultsTable.setRowCount(len(exploits))
        for i, exploit in enumerate(exploits):
            self.resultsTable.setItem(i, 0, QTableWidgetItem(exploit['signatures']))
            self.resultsTable.setItem(i, 1, QTableWidgetItem(exploit['description']))
            self.resultsTable.setItem(i, 2, QTableWidgetItem(exploit['type']))
            self.resultsTable.setItem(i, 3, QTableWidgetItem(exploit['platform']))
            link_item = QTableWidgetItem(exploit['link'])
            link_item.setForeground(QBrush(QColor(Qt.GlobalColor.blue)))
            self.resultsTable.setItem(i, 4, link_item)
            self.resultsTable.setItem(i, 5, QTableWidgetItem(exploit['file_path']))

    def handle_cell_click(self, row, column):
        self.load_code_from_file(row)
        self.show_aiAnalysis(row, column)

    def load_code_from_file(self, row):
        item = self.resultsTable.item(row, 5)
        if item:
            file_path = item.text()
            if not file_path.strip():
                self.codeViewer.setPlainText("Brak ścieżki do pliku.")
                return
            if not os.path.exists(file_path):
                self.codeViewer.setPlainText(f"Plik nie istnieje: {file_path}")
                return
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                    language = detect_language(file_path)
                    highlighted = get_highlighted_html(code, language)
                    self.codeViewer.setHtml(highlighted)
                    self.tabWidget.setCurrentWidget(self.tabCode)
            except Exception as e:
                self.codeViewer.setPlainText(f"Błąd podczas czytania pliku:\n{e}")

    def show_aiAnalysis(self, row, column):
        if not self.gemini:
            return

        signatures = self.resultsTable.item(row, 0).text()
        description = self.resultsTable.item(row, 1).text()

        exploit = next((e for e in self.exploits if 
                        e['signatures'] == signatures and 
                        e['description'] == description), None)

        if not exploit:
            self.aiAnalysis.setPlainText("Error: Exploit data not found.")
            return

        prompt = f"""Stwórz szczegółową analizę bezpieczeństwa w języku polskim. 
Odpowiedz wyłącznie w formacie HTML (bez markdown), uwzględnij to że mój program 
działa w ciemnym trybie. 
Uwzględnij:

1. Potencjalne wektory ataku
2. Ocenę ryzyka dla aktualnych systemów (1-10)
3. Przykładowe użycie exploita
4. Zwalczanie exploita
5. Możliwości wykrywania
6. Zalecenia dotyczące zabezpieczeń

Dane exploita:
- ID: {exploit['link'].split('/')[-1]}
- CVEs: {exploit['signatures']}
- Platforma: {exploit['platform']}
- Typ: {exploit['type']}
- Opis: {exploit['description']}
- Data publikacji: {exploit['date']}
- Autor: {exploit['author']}"""

        QTimer.singleShot(0, lambda: self.show_analysis_progress(prompt))

    def show_analysis_progress(self, prompt):
        self.progress = QProgressDialog("Generowanie analizy...", None, 0, 0, self)
        self.progress.setWindowTitle("Proszę czekać")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setCancelButton(None)
        self.progress.show()

        self.worker = GeminiWorker(self.gemini, prompt)
        self.worker.finished.connect(self.handle_ai_response)
        self.worker.start()

    def handle_ai_response(self, response):
        self.progress.close()

        if isinstance(response, Exception):
            QMessageBox.critical(self, 'Błąd', f'Błąd AI: {str(response)}')
            return

        if response.parts:
            analysis = '\n'.join(part.text for part in response.parts)
            analysis = re.sub(r'^\s*(\*\*html\*\*|```html|```)', '', analysis, flags=re.IGNORECASE)
            analysis = re.sub(r'\s*```$', '', analysis, flags=re.IGNORECASE)
            self.aiAnalysis.setHtml(analysis.strip())
        else:
            self.aiAnalysis.setPlainText("Brak danych w odpowiedzi AI.")

    def export_analysis_to_pdf(self):
        text = self.aiAnalysis.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Brak danych", "Nie znaleziono analizy do zapisania.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Zapisz jako PDF", "", "PDF files (*.pdf)")
        if not path:
            return

        try:
            c = canvas.Canvas(path, pagesize=letter)
            width, height = letter
            max_width = width - 80  # marginesy
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            import textwrap

            # Ścieżka do czcionki Roboto w folderze fonts
            font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts", "Roboto-VariableFont_wdth,wght.ttf")
            try:
                pdfmetrics.registerFont(TTFont('Roboto', font_path))
                font_name = 'Roboto'
            except Exception as font_exc:
                QMessageBox.warning(self, "Uwaga", f"Nie znaleziono fontu Roboto-VariableFont_wdth,wght.ttf lub nie można go załadować.\nPolskie znaki mogą nie wyświetlać się poprawnie w PDF.\nSzczegóły: {font_exc}")
                font_name = 'Helvetica'

            c.setFont(font_name, 10)
            lines = []
            for paragraph in text.split('\n'):
                wrapped = textwrap.wrap(paragraph, width=110, break_long_words=False, replace_whitespace=False)
                lines.extend(wrapped if wrapped else [""])
            y = height - 40
            for line in lines:
                c.drawString(40, y, line)
                y -= 14
                if y < 40:
                    c.showPage()
                    c.setFont(font_name, 10)
                    y = height - 40
            c.save()
            QMessageBox.information(self, "Sukces", f"Analiza została zapisana do {path}")
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Nie udało się zapisać PDF: {str(e)}")

    def export_analysis_to_docx(self):
        text = self.aiAnalysis.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Brak danych", "Nie znaleziono analizy do zapisania.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Zapisz jako DOCX", "", "Word documents (*.docx)")
        if not path:
            return

        try:
            doc = Document()
            paragraphs = [p for p in text.split('\n') if p.strip()]
            for paragraph in paragraphs:
                doc.add_paragraph(paragraph)
            doc.save(path)
            QMessageBox.information(self, "Sukces", f"Analiza została zapisana do {path}")
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Nie udało się zapisać DOCX: {str(e)}")