# main.py
import sys
# import qdarkstyle
from PyQt6.QtWidgets import QApplication
from ui.main_window import ExploitSearchApp

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("Exploit Search")
    app.setApplicationVersion("0.8")
    
    # app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))

    window = ExploitSearchApp()
    window.show()

    sys.exit(app.exec())
