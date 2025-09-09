from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from app.pages.flight_tracker.view import FlightTrackerWidget
from app.pages.mission_tracker.sites_widget import SitesManagementWidget
from app.pages.mission_tracker.processing_widget import ProcessingTrackerWidget

class MissionTrackerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mission Management")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget for Mission Management
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Flight Tracker tab
        self.flight_tracker_widget = FlightTrackerWidget()
        self.tab_widget.addTab(self.flight_tracker_widget, "Flight Tracker")

        # Sites Management tab
        self.sites_widget = SitesManagementWidget()
        self.tab_widget.addTab(self.sites_widget, "Sites Management")

        # Processing Tracker tab
        self.processing_widget = ProcessingTrackerWidget()
        self.tab_widget.addTab(self.processing_widget, "Processing Tracker")
