import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from ui.main_window import MainWindow
from db.database import init_db

if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    app.setFont(QFont("Roboto"))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
