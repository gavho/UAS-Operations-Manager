from PyQt5.QtWidgets import QWidget, QVBoxLayout
from .fleet_management.fleet_widget_updated import FleetManagementWidget

class FleetManagementPage(QWidget):
    """
    Container page for the Fleet Management widget.
    """
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Instantiate the actual fleet management widget
        self.fleet_widget = FleetManagementWidget()
        
        layout.addWidget(self.fleet_widget)
        self.setLayout(layout)

    def refresh_data(self):
        """Refreshes the data in the fleet widget."""
        self.fleet_widget.refresh_data()