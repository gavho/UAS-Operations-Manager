from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QDialogButtonBox, QComboBox, QScrollArea, 
    QWidget, QMessageBox
)
from PyQt5.QtCore import Qt

from app.database.manager import db_manager

class EditSystemDialog(QDialog):
    """A dialog for editing an existing system and its sensors."""

    def __init__(self, system_data, parent=None):
        super().__init__(parent)
        self.system_data = system_data
        self._sensor_models = db_manager.get_all_sensor_models()
        self._sensor_rows = []

        self.setWindowTitle("Edit System")
        self.setMinimumSize(500, 600)
        self.setup_ui()
        self.populate_data()

    def setup_ui(self):
        """Set up the user interface for the dialog."""
        main_layout = QVBoxLayout(self)
        
        # Chassis SN and Customer
        form_layout = QVBoxLayout()
        self.chassis_sn_input = QLineEdit()
        self.chassis_sn_input.setReadOnly(True) # Chassis SN is the key, should not be editable
        self.customer_input = QLineEdit()
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(60)  # Set a maximum height for the notes field

        self.status_input = QComboBox()
        self.status_input.addItems(["Active", "Inactive", "In Maintenance"])
        self.status_input.setCurrentText("Active")  # Set default

        form_layout.addWidget(QLabel("Chassis Serial Number:"))
        form_layout.addWidget(self.chassis_sn_input)
        form_layout.addWidget(QLabel("Customer:"))
        form_layout.addWidget(self.customer_input)
        form_layout.addWidget(QLabel("Status"))
        form_layout.addWidget(self.status_input)

        form_layout.addWidget(QLabel("Notes"))
        form_layout.addWidget(self.notes_input)
        
        main_layout.addLayout(form_layout)

        # --- Sensors Section ---
        main_layout.addWidget(QLabel("Sensors:"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.sensors_rows_layout = QVBoxLayout(scroll_content)
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        self.add_sensor_button = QPushButton("Add Sensor")
        self.add_sensor_button.clicked.connect(self.add_sensor_row)
        main_layout.addWidget(self.add_sensor_button)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def populate_data(self):
        """Populate the dialog with existing system data."""
        self.chassis_sn_input.setText(self.system_data.get('chassis', ''))
        self.customer_input.setText(self.system_data.get('customer', ''))
        status = self.system_data.get('system_status', 'Active')
        if status:
            index = self.status_input.findText(status, Qt.MatchFixedString)
            if index >= 0:
                self.status_input.setCurrentIndex(index)
            else:
                self.status_input.setCurrentText(status)
        self.notes_input.setPlainText(self.system_data.get('notes', ''))

        for sensor in self.system_data.get('sensors', []):
            self.add_sensor_row(sensor_data=sensor)

    def add_sensor_row(self, sensor_data=None):
        """Add a new row for selecting a sensor."""
        sensor_row = QWidget()
        row_layout = QHBoxLayout(sensor_row)

        type_combo = QComboBox()
        model_combo = QComboBox()
        sn_input = QLineEdit()
        sn_input.setPlaceholderText("Sensor S/N")
        deprecate_button = QPushButton("Deprecate")
        deprecate_button.setToolTip(
            "Mark this installed sensor as Deprecated.\n"
            "This will set an Uninstall Date and remove it from this aircraft.\n"
            "This action is permanent and cannot be undone."
        )
        remove_button = QPushButton("Remove")

        models_by_type = {}
        for sensor in self._sensor_models:
            if sensor['type'] not in models_by_type:
                models_by_type[sensor['type']] = []
            models_by_type[sensor['type']].append(sensor)

        type_combo.addItems(sorted(models_by_type.keys()))

        def update_models():
            selected_type = type_combo.currentText()
            model_combo.clear()
            for sensor in models_by_type.get(selected_type, []):
                model_combo.addItem(f"{sensor['model']} ({sensor['manufacturer']})", sensor['sensor_model_id'])

        row_layout.addWidget(QLabel("Type:"))
        row_layout.addWidget(type_combo, 1)
        row_layout.addWidget(QLabel("Model:"))
        row_layout.addWidget(model_combo, 2)
        row_layout.addWidget(QLabel("S/N:"))
        row_layout.addWidget(sn_input, 1)
        row_layout.addWidget(deprecate_button)
        row_layout.addWidget(remove_button)

        sensor_row_widgets = {
            'row': sensor_row, 
            'model_combo': model_combo, 
            'sn_input': sn_input,
            'type_combo': type_combo,
            'original_data': sensor_data,
            'deprecate_button': deprecate_button,
            'remove_button': remove_button
        }
        self._sensor_rows.append(sensor_row_widgets)
        self.sensors_rows_layout.addWidget(sensor_row)

        deprecate_button.clicked.connect(lambda: self.deprecate_sensor(sensor_row_widgets))
        remove_button.clicked.connect(lambda: self.remove_sensor_row(sensor_row_widgets))

        type_combo.currentTextChanged.connect(update_models)

        if sensor_data:
            type_combo.setCurrentText(sensor_data.get('type', ''))
            update_models() # Manually trigger model update for the pre-selected type
            model_id_to_find = sensor_data.get('sensor_model_id')
            if model_id_to_find:
                model_index = model_combo.findData(model_id_to_find)
                if model_index != -1:
                    model_combo.setCurrentIndex(model_index)
            sn_input.setText(sensor_data.get('serial_number', ''))
            # Show Deprecate only for existing sensors that have a serial and installed_id
            has_sn = bool(sensor_data.get('serial_number'))
            has_installed_id = sensor_data.get('installed_id') is not None
            deprecate_button.setVisible(has_sn and has_installed_id)
        else:
            update_models() # Initial population for a new row
            deprecate_button.setVisible(False)

    def remove_sensor_row(self, sensor_row_widgets):
        """Remove a sensor row from the layout and list.
        For existing sensors, permanently delete the installed_sensors record.
        For new (unsaved) rows, just remove the UI row.
        """
        is_existing_sensor = sensor_row_widgets.get('original_data') is not None
        if is_existing_sensor:
            installed_id = sensor_row_widgets['original_data'].get('installed_id')
            reply = QMessageBox.question(
                self,
                'Confirm Delete',
                "Delete this installed sensor record from the database?\n"
                "This will permanently remove it (cannot be undone).",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            if installed_id is not None:
                if not db_manager.delete_installed_sensor(installed_id):
                    details = db_manager.last_error or 'Unknown error.'
                    QMessageBox.warning(self, 'Delete Failed', f'Could not delete the installed sensor record.\n\nDetails: {details}')
                    return

        self.sensors_rows_layout.removeWidget(sensor_row_widgets['row'])
        sensor_row_widgets['row'].deleteLater()
        self._sensor_rows.remove(sensor_row_widgets)

    def deprecate_sensor(self, sensor_row_widgets):
        """Mark an existing installed sensor as deprecated (sets Uninstall_Date) and remove from UI."""
        original = sensor_row_widgets.get('original_data')
        if not original or original.get('installed_id') is None:
            # No-op for new rows
            return
        sn = original.get('serial_number') or ''
        installed_id = original.get('installed_id')
        reply = QMessageBox.question(
            self,
            'Confirm Deprecate',
            f"Deprecate sensor SN: {sn}?\nThis will set an Uninstall Date and remove it from this aircraft.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
        ok = db_manager.deprecate_installed_sensor(installed_id)
        if not ok:
            details = db_manager.last_error or 'Unknown error.'
            QMessageBox.warning(self, 'Deprecation Failed', f'Could not deprecate the installed sensor.\n\nDetails: {details}')
            return
        # Remove row from UI after successful deprecation
        self.sensors_rows_layout.removeWidget(sensor_row_widgets['row'])
        sensor_row_widgets['row'].deleteLater()
        self._sensor_rows.remove(sensor_row_widgets)

    def get_data(self):
        """Return the data entered in the dialog."""
        sensors = []
        for row_widgets in self._sensor_rows:
            model_combo = row_widgets['model_combo']
            sn_input = row_widgets['sn_input']
            sensor_id = model_combo.currentData()
            sensor_sn = sn_input.text().strip()

            # Include sensor if it has a model selected (sensor_id is not None)
            # Serial number is optional for new sensors
            if sensor_id is not None:
                sensors.append({
                    'sensor_model_id': sensor_id,
                    'sensor_sn': sensor_sn
                })

        return {
            'chassis_sn': self.chassis_sn_input.text().strip(),
            'customer': self.customer_input.text().strip(),
            'status': self.status_input.currentText(),
            'notes': self.notes_input.toPlainText(),
            'sensors': sensors
        }

    def accept(self):
        """Intercept Save to validate data before closing."""
        # Basic validation: ensure at least one sensor is configured
        valid_sensors = 0
        for row_widgets in self._sensor_rows:
            model_combo = row_widgets.get('model_combo')
            if model_combo and model_combo.currentData() is not None:
                valid_sensors += 1

        if valid_sensors == 0:
            QMessageBox.warning(
                self,
                'Validation Error',
                'At least one sensor must be configured for the system.'
            )
            return  # Keep dialog open

        # Note: Database constraints will handle duplicate sensor type validation
        # The database trigger prevents multiple active sensors of the same type per chassis

        # Otherwise proceed with normal accept
        super().accept()
