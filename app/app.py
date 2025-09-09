import sys
from PyQt5.QtWidgets import QApplication
from app.main_window import MainWindow


class Application(QApplication):
    """
    The core application class that manages the main window and application-level logic.
    Inherits from QApplication.
    """

    def __init__(self, sys_argv):
        super(Application, self).__init__(sys_argv)

        # Set application details
        self.setApplicationName("Flight Operations Management Tool")
        self.setOrganizationName("University Research Group")

        # Initialize and show the main window
        self.main_window = MainWindow()
        self.main_window.show()