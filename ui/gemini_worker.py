# ui/gemini_worker.py
from PyQt6.QtCore import QThread, pyqtSignal

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
