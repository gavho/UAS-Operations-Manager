from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QDateEdit, 
    QTextEdit, QFormLayout, QComboBox, QFileDialog, QWidget
)
from PyQt5.QtCore import Qt, QDate
from app.database.manager import db_manager
from app.database.maintenance_manager import maintenance_manager

class MaintenanceDialog(QDialog):
    """Dialog for managing maintenance logs."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Maintenance Management")
        self.setMinimumSize(1000, 800)
        self.setup_ui()
        self.load_platforms()
        self.load_maintenance_logs()

    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Form to add new maintenance log
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        
        self.platform_combo = QComboBox()
        self.maintenance_type_combo = QComboBox()
        self.maintenance_type_combo.addItems(["Firmware Update", "Repair", "Cleaning/Upkeep", "Inspection", "Modification"])
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.performed_by_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.image_path_edit = QLineEdit()
        self.image_path_edit.setReadOnly(True)
        image_button = QPushButton("Browse...")
        image_button.clicked.connect(self.browse_image)

        form_layout.addRow("Select Platform:", self.platform_combo)
        form_layout.addRow("Maintenance Type:", self.maintenance_type_combo)
        form_layout.addRow("Date:", self.date_edit)
        form_layout.addRow("Performed By:", self.performed_by_edit)
        form_layout.addRow("Description:", self.description_edit)
        
        image_layout = QHBoxLayout()
        image_layout.addWidget(self.image_path_edit)
        image_layout.addWidget(image_button)
        form_layout.addRow("Image:", image_layout)
        
        add_button = QPushButton("Add Maintenance Entry")
        add_button.clicked.connect(self.add_maintenance_log_entry)
        form_layout.addWidget(add_button)
        
        # Table to display maintenance logs
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Platform", "Type", "Date", "Performed By", "Description", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Add widgets to layout
        layout.addWidget(form_widget)
        layout.addWidget(QLabel("Maintenance History:"))
        layout.addWidget(self.table)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignRight)

    def browse_image(self):
        """Open a file dialog to select an image."""
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.image_path_edit.setText(path)

    def load_platforms(self):
        """Load platforms into the combo box and keep a lookup for display."""
        self.platform_combo.clear()
        self.platform_lookup = {}
        platforms = db_manager.get_all_platforms()
        for p in platforms:
            pid = p.get('id')
            name = p.get('name') or 'Unnamed'
            sn = p.get('serial_number') or 'N/A'
            self.platform_combo.addItem(f"{name} - SN:{sn}", pid)
            self.platform_lookup[pid] = name
        # when platform selection changes, reload logs
        self.platform_combo.currentIndexChanged.connect(self.load_maintenance_logs)

    def add_maintenance_log_entry(self):
        """Add a new maintenance log to the database (ORM)."""
        try:
            platform_id = self.platform_combo.currentData()
            maintenance_type = self.maintenance_type_combo.currentText()
            date_str = self.date_edit.date().toString("yyyy-MM-dd")
            technician = self.performed_by_edit.text().strip()
            description = self.description_edit.toPlainText().strip()
            image_path = self.image_path_edit.text().strip() or None

            if not all([platform_id, maintenance_type, technician, description]):
                QMessageBox.warning(self, "Error", "Please fill in all required fields.")
                return

            # Use ORM manager; pass extra fields if the model supports them
            created = maintenance_manager.add_maintenance_log(
                platform_id=platform_id,
                maintenance_type=maintenance_type,
                description=description,
                date=date_str,
                technician=technician,
                image_path=image_path
            )
            if not created:
                QMessageBox.critical(self, "Error", "Failed to add maintenance log.")
                return
            # Reset inputs
            self.performed_by_edit.clear()
            self.description_edit.clear()
            self.image_path_edit.clear()
            self.date_edit.setDate(QDate.currentDate())
            self.load_maintenance_logs()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not add maintenance log: {e}")

    def load_maintenance_logs(self):
        """Load maintenance logs for the selected platform into the table."""
        self.table.setRowCount(0)
        platform_id = self.platform_combo.currentData()
        if not platform_id:
            return
        logs = maintenance_manager.get_logs_for_platform(platform_id=platform_id)
        for row, log in enumerate(logs):
            self.table.insertRow(row)
            # Extract fields safely (attribute access for ORM objects)
            log_id = getattr(log, 'id', None)
            if log_id is None:
                log_id = getattr(log, 'maintenance_id', None)
            p_name = self.platform_lookup.get(platform_id, "")
            m_type = getattr(log, 'maintenance_type', '')
            date_val = getattr(log, 'date', '')
            if not date_val:
                date_val = getattr(log, 'maintenance_date', '')
            date_str = str(date_val) if date_val else ''
            tech = getattr(log, 'technician', '')
            if not tech:
                tech = getattr(log, 'performed_by', '')
            desc = getattr(log, 'description', '')

            self.table.setItem(row, 0, QTableWidgetItem(str(log_id)))
            self.table.setItem(row, 1, QTableWidgetItem(p_name))
            self.table.setItem(row, 2, QTableWidgetItem(m_type))
            self.table.setItem(row, 3, QTableWidgetItem(date_str))
            self.table.setItem(row, 4, QTableWidgetItem(tech))
            self.table.setItem(row, 5, QTableWidgetItem(desc))

            # Actions: Delete button
            action_btn = QPushButton("Delete")
            action_btn.clicked.connect(lambda _, lid=log_id: self.delete_log_entry(lid))
            self.table.setCellWidget(row, 6, action_btn)

    def delete_log_entry(self, log_id):
        """Delete a maintenance log."""
        if not log_id:
            return
        if QMessageBox.question(self, "Confirm Delete", "Are you sure?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            ok = maintenance_manager.delete_maintenance_log(log_id)
            if not ok:
                QMessageBox.critical(self, "Error", "Failed to delete maintenance log.")
            self.load_maintenance_logs()
