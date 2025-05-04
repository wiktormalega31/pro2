import sys
import csv
import re
import google.generativeai as genai
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidgetItem, QHeaderView,
    QMessageBox, QProgressDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QBrush
from PyQt6.uic import loadUi
from dotenv import load_dotenv
import os

# Import funkcji highlightującej z pygments
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter

class GeminiWorker(QThread):
    finished = pyqtSignal(object)

    def __init__(self, gemini, prompt):
        super().__init__()
        self.gemini = gemini
        self.prompt = prompt

    def run(self):
        try:
            response = self.gemini.generate_content(self.prompt)
            self.finished.emit(response)
        except Exception as e:
            self.finished.emit(e)

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
        self.resultsTable.cellClicked.connect(self.handle_cell_click)

    def configure_ai(self):
        load_dotenv()
        key = os.getenv('API_KEY')
        if key:
            try:
                genai.configure(api_key=key)
                self.gemini = genai.GenerativeModel('gemini-1.5-pro-latest')
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'AI configuration failed: {str(e)}')
        else:
            QMessageBox.warning(self, 'Warning', 'AI analysis disabled - no API key found in .env file')

    def load_data(self):
        try:
            self.parse_data('./data/files_exploits.csv')
        except FileNotFoundError:
            QMessageBox.critical(self, 'Error', 'File "files_exploits.csv" not found.')
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to load data: {str(e)}')

    def parse_data(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.exploits.append({
                        'signatures': row.get('codes', '').replace(';', ', '),
                        'description': row.get('description', ''),
                        'type': row.get('type', ''),
                        'platform': row.get('platform', ''),
                        'link': f"https://www.exploit-db.com/exploits/{row.get('id', '')}",
                        'author': row.get('author', ''),
                        'date': row.get('date_published', ''),
                        'verified': row.get('verified', ''),
                        'file_path': row.get('file', '')
                    })
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to parse data: {str(e)}')

    def detect_language(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        ext_map = {
            '.py': 'python',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.rb': 'ruby',
            '.pl': 'perl',
            '.php': 'php',
            '.js': 'javascript',
            '.html': 'html',
            '.sh': 'bash',
            '.java': 'java',
        }
        return ext_map.get(ext, 'text')

    def get_highlighted_html(self, code, language):
        try:
            lexer = get_lexer_by_name(language)
        except Exception:
            lexer = get_lexer_by_name('text')
        # transparentne tło i brak obramowania dla całego kodu i elementów
        css = (
            '. { background: transparent !important; } '

        )
        formatter = HtmlFormatter(
            style='monokai',
            full=True,
            noclasses=True,
            cssstyles=css
        )
        return highlight(code, lexer, formatter)

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
                    language = self.detect_language(file_path)
                    highlighted = self.get_highlighted_html(code, language)
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
Odpowiedz wyłącznie w formacie HTML (bez markdown). 
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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ExploitSearchApp()
    window.show()
    sys.exit(app.exec())
