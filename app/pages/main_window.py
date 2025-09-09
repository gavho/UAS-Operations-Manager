import sys
from PyQt5.QtWidgets import QMainWindow, QApplication, QPushButton, QVBoxLayout, QWidget
# The relative import for a file in the same directory remains the same
from .db_editor_window import DBEditorWindow

class MainWindow(QMainWindow):
    """
    The main window of the application.
    This window will serve as the main hub for accessing different
    parts of the flight operations tool.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Flight Operations Management Tool")
        self.setGeometry(100, 100, 400, 300)

        # Keep a reference to the DB editor window
        self.db_editor_window = None

        self.setup_ui()

    def setup_ui(self):
        """
        Sets up the user interface for the main window.
        """
        # Create a central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create a button to open the DB Editor
        self.db_editor_button = QPushButton("Open Database Editor")
        self.db_editor_button.setToolTip("Open the tool to view and edit the SQLite database.")
        self.db_editor_button.clicked.connect(self.open_db_editor)
        layout.addWidget(self.db_editor_button)

        # You can add more buttons here for other features in the future
        # e.g., Fleet Management, Mission Planning, etc.

    def open_db_editor(self):
        """
        Opens the DB Editor window. If the window is already open, it will be
        brought to the front.
        """
        if self.db_editor_window is None:
            # Create an instance of the DBEditorWindow
            self.db_editor_window = DBEditorWindow()
            # When the editor window is closed, set our reference back to None
            self.db_editor_window.setAttribute(0, 0)  # WA_DeleteOnClose
            self.db_editor_window.destroyed.connect(lambda: setattr(self, 'db_editor_window', None))

        # Show and activate the window
        self.db_editor_window.show()
        self.db_editor_window.activateWindow()
        self.db_editor_window.raise_()