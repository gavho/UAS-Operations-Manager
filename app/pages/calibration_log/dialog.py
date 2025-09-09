from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QListWidget,
    QLineEdit, QDialogButtonBox, QLabel, QDateEdit, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QPushButton
)
from app.database import db_manager

class AddCalibrationDialog(QDialog):
    data_changed = pyqtSignal()

    def __init__(self, parent=None, chassis_sn=None, edit_data=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Sensor Calibration")
        self.setMinimumSize(700, 600)

        self.main_layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        # --- Common Details ---
        self.system_combo = QComboBox()
        self.system_combo.setEditable(True)
        self.form_layout.addRow("System:", self.system_combo)

        # Platform (UAS used for the calibration)
        self.platform_edit = QLineEdit()
        self.form_layout.addRow("Platform:", self.platform_edit)

        self.cal_date_edit = QDateEdit(QDate.currentDate())
        self.cal_date_edit.setCalendarPopup(True)
        self.form_layout.addRow("Calibration Date:", self.cal_date_edit)

        # Create a horizontal layout for Calibration ID and Generate button
        cal_id_layout = QHBoxLayout()
        self.calibration_id_edit = QLineEdit()
        generate_btn = QPushButton("Generate")
        generate_btn.clicked.connect(self.generate_calibration_id)
        cal_id_layout.addWidget(self.calibration_id_edit, 1)  # Text field takes most space
        cal_id_layout.addWidget(generate_btn)  # Button takes minimum space
        self.form_layout.addRow("Calibration ID:", cal_id_layout)

        self.notes_edit = QLineEdit()
        self.form_layout.addRow("Notes:", self.notes_edit)

        self.main_layout.addLayout(self.form_layout)

        # --- Sensor Selection and Per-Sensor Data ---
        h_layout = QHBoxLayout()
        
        # Sensor Selection List
        sensor_selection_layout = QVBoxLayout()
        sensor_selection_layout.addWidget(QLabel("Select Sensors:"))
        self.sensor_list = QListWidget()
        self.sensor_list.setSelectionMode(QListWidget.ExtendedSelection)
        sensor_selection_layout.addWidget(self.sensor_list)
        h_layout.addLayout(sensor_selection_layout, 1)

        # Per-Sensor Data Table
        sensor_data_layout = QVBoxLayout()
        sensor_data_layout.addWidget(QLabel("Enter Calibration Data:"))
        self.per_sensor_table = QTableWidget()
        self.per_sensor_table.setColumnCount(7)
        self.per_sensor_table.setHorizontalHeaderLabels(["Sensor", "Status", "RMSE X", "RMSE Y", "RMSE Z", "Sigma0", "Plane_Fit"])
        header = self.per_sensor_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 7):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        sensor_data_layout.addWidget(self.per_sensor_table)
        h_layout.addLayout(sensor_data_layout, 3)
        
        self.main_layout.addLayout(h_layout)

        # --- Historical Data Table ---
        history_layout = QVBoxLayout()
        history_layout.addWidget(QLabel("Calibration History for Selected Sensor:"))
        self.history_table = QTableWidget()
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setAlternatingRowColors(True)
        history_layout.addWidget(self.history_table)

        self.no_history_label = QLabel("No calibration history available for this sensor.")
        self.no_history_label.setAlignment(Qt.AlignCenter)
        history_layout.addWidget(self.no_history_label)
        self.no_history_label.hide()

        self.main_layout.addLayout(history_layout)

        # --- Dialog Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.save_button = self.button_box.addButton("Save", QDialogButtonBox.AcceptRole)
        self.save_button.clicked.connect(self.on_save)
        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)

        # --- Connections and Initial Load ---
        self.load_systems()
        if chassis_sn:
            self.system_combo.setCurrentText(chassis_sn)
        
        self.system_combo.currentIndexChanged.connect(self.update_sensor_list)
        self.sensor_list.itemSelectionChanged.connect(self.update_sensor_table)
        self.sensor_list.itemSelectionChanged.connect(self.update_history_table)

        # Connections for auto-generating calibration ID
        self.system_combo.currentIndexChanged.connect(self.generate_calibration_id)
        self.cal_date_edit.dateChanged.connect(self.generate_calibration_id)

        self.edit_data = edit_data
        if self.edit_data:
            self.set_edit_data(self.edit_data)
        else:
            self.update_sensor_list()
            self.generate_calibration_id()

    def load_systems(self):
        systems = db_manager.get_sensor_data()
        for chassis_sn in sorted(systems.keys()):
            self.system_combo.addItem(chassis_sn)

    def update_sensor_list(self):
        self.sensor_list.clear()
        chassis_sn = self.system_combo.currentText()
        if not chassis_sn:
            return
        
        all_systems = db_manager.get_sensor_data()
        if chassis_sn in all_systems:
            system_data = all_systems[chassis_sn]
            sensors_for_system = system_data.get('sensors', [])
            
            for sensor in sensors_for_system:
                if not isinstance(sensor, dict):
                    print(f"Warning: Unexpected sensor data type: {type(sensor)}")
                    continue
                    
                sensor_name = sensor.get('model', 'Unknown Sensor')
                sensor_sn = sensor.get('serial_number', 'N/A')
                installed_id = sensor.get('id')

                if installed_id:
                    display_text = f"{sensor_name} (SN: {sensor_sn})"
                    item = QListWidgetItem(display_text)
                    item.setData(Qt.UserRole, installed_id)
                    self.sensor_list.addItem(item)
                    
        self.update_sensor_table()

    def update_sensor_table(self):
        self.per_sensor_table.setRowCount(0)
        selected_items = self.sensor_list.selectedItems()
        
        for item in selected_items:
            row_position = self.per_sensor_table.rowCount()
            self.per_sensor_table.insertRow(row_position)
            
            sensor_name_item = QTableWidgetItem(item.text())
            sensor_name_item.setFlags(sensor_name_item.flags() & ~Qt.ItemIsEditable)
            sensor_name_item.setData(Qt.UserRole, item.data(Qt.UserRole)) # Carry over Installed_ID
            self.per_sensor_table.setItem(row_position, 0, sensor_name_item)

            # Status ComboBox
            status_combo = QComboBox()
            status_combo.addItems(["APPROVED", "REVIEW"])
            self.per_sensor_table.setCellWidget(row_position, 1, status_combo)

            for col in range(2, 7): # Columns for RMSE, Sigma0, Plane_Fit
                self.per_sensor_table.setItem(row_position, col, QTableWidgetItem(""))

    def get_data(self):
        records = []
        # Platform is optional; store as NULL when empty
        platform_text = (self.platform_edit.text() or '').strip() or None

        common_data = {
            "Platform": platform_text,
            "Calibration_Date": self.cal_date_edit.date().toString("yyyy-MM-dd"),
            "Notes": self.notes_edit.text(),
            "Calibration_ID": self.calibration_id_edit.text()
        }

        if self.per_sensor_table.rowCount() == 0:
            QMessageBox.information(self, "No Sensor Data", "No sensor data is available to save.")
            return None

        for row in range(self.per_sensor_table.rowCount()):
            try:
                installed_id = self.per_sensor_table.item(row, 0).data(Qt.UserRole)
                
                def get_cell_value(r, c):
                    item = self.per_sensor_table.item(r, c)
                    return float(item.text()) if item and item.text() else None

                status_widget = self.per_sensor_table.cellWidget(row, 1)

                record = {
                    "Installed_ID": installed_id,
                    "Status": status_widget.currentText() if status_widget else None,
                    "RMSE_X": get_cell_value(row, 2),
                    "RMSE_Y": get_cell_value(row, 3),
                    "RMSE_Z": get_cell_value(row, 4),
                    "Sigma0": get_cell_value(row, 5),
                    "Plane_Fit": get_cell_value(row, 6),
                    **common_data
                }
                records.append(record)
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", f"Invalid number format in row {row + 1}. Please enter valid numbers for RMSE, Sigma0 and Plane_Fit.")
                return None
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An unexpected error occurred while processing row {row + 1}: {e}")
                return None

        # Add the original Calibration_ID if we are in edit mode
        if self.edit_data:
            for record in records:
                record['original_Calibration_ID'] = self.edit_data.get('Calibration_ID')

        return records

    def on_save(self):
        """Handles the save button click for both add and edit modes."""
        if self.edit_data:
            records_to_update = self.get_data()
            if not records_to_update:
                return # An error message was likely shown in get_data

            if db_manager.update_calibration_records(records_to_update):
                QMessageBox.information(self, "Success", "Calibration record updated successfully.")
                self.data_changed.emit()
                self.accept()
            else:
                QMessageBox.critical(self, "Database Error", "Failed to update the calibration record.")
        else:
            self.save_and_continue() # For add mode, save and clear for next entry.

    def save_and_continue(self):
        """Saves the calibration data and clears the form for the next entry."""
        records = self.get_data()
        if not records:
            return

        if not self.calibration_id_edit.text():
            QMessageBox.warning(self, "Missing ID", "Calibration ID cannot be empty.")
            return

        if db_manager.add_calibration_records(records):
            QMessageBox.information(self, "Success", f"{len(records)} calibration record(s) saved successfully.")
            self.data_changed.emit()
            self.clear_form()
            self.update_history_table() # Refresh history for the selected sensor
        else:
            QMessageBox.critical(self, "Database Error", "Failed to save calibration records.")

    def clear_form(self):
        """Clears the form fields to prepare for a new entry."""
        self.sensor_list.clearSelection()
        self.per_sensor_table.setRowCount(0)
        self.notes_edit.clear()
        self.generate_calibration_id() # Generate a new ID for the next entry

    def generate_calibration_id(self):
        """Generate a new calibration ID based on system and date."""
        chassis_sn = self.system_combo.currentText().strip()
        if not chassis_sn or not self.cal_date_edit.date().isValid():
            QMessageBox.warning(self, "Missing Information", "System and a valid date must be set to generate an ID.")
            return False
            
        cal_date = self.cal_date_edit.date().toString('yyyy-MM-dd')
        formatted_date = self.cal_date_edit.date().toString('yyyyMMdd')
        
        # Get existing calibration IDs for this platform and date
        existing_calibrations = db_manager.get_calibration_log(chassis_sn=chassis_sn)
        existing_ids = [cal['Calibration_ID'] for cal in existing_calibrations 
                       if cal['Calibration_Date'].startswith(cal_date)]
        
        # Find the next available revision letter
        rev_letter = 'A'
        for i in range(26):  # A-Z
            test_id = f"#{chassis_sn}_G_{formatted_date}_{chr(65 + i)}"
            if test_id not in existing_ids:
                rev_letter = chr(65 + i)
                break
                
        new_id = f"#{chassis_sn}_G_{formatted_date}_{rev_letter}"
        self.calibration_id_edit.setText(new_id)
        return True

    def set_edit_data(self, data):
        """Populates the dialog with data from an existing record for editing."""
        self.setWindowTitle("Edit Calibration Entry")
        self.save_button.setText("Update Existing Calibration")

        # Populate fields
        self.calibration_id_edit.setText(data.get('Calibration_ID', ''))
        # Platform comes from record's Platform
        self.platform_edit.setText(data.get('Platform', ''))
        cal_date = QDate.fromString(data.get('Calibration_Date', ''), "yyyy-MM-dd")
        if cal_date.isValid():
            self.cal_date_edit.setDate(cal_date)
        self.notes_edit.setText(data.get('Notes', ''))

        # Disable auto-generation of ID in edit mode
        self.system_combo.currentIndexChanged.disconnect(self.generate_calibration_id)
        self.cal_date_edit.dateChanged.disconnect(self.generate_calibration_id)

        # Populate sensor list for the given system and select the correct one
        self.update_sensor_list()
        installed_id_to_select = data.get('Installed_ID')
        if installed_id_to_select:
            for i in range(self.sensor_list.count()):
                item = self.sensor_list.item(i)
                if str(item.data(Qt.UserRole)) == str(installed_id_to_select):
                    item.setSelected(True)
                    self.sensor_list.setCurrentItem(item)
                    break
        
        # The selection change should trigger update_sensor_table, but call it just in case
        self.update_sensor_table()

        # Populate the per-sensor table with the specific data
        if self.per_sensor_table.rowCount() > 0:
            status_widget = self.per_sensor_table.cellWidget(0, 1)
            if status_widget:
                for col in range(2, 6):  # Columns for RMSE, Sigma0
                    self.per_sensor_table.setItem(0, col, QTableWidgetItem(""))

    def update_history_table(self):
        """Update the history table with calibration history for the selected sensor."""
        selected_items = self.sensor_list.selectedItems()
        if len(selected_items) != 1:
            self.history_table.hide()
            self.no_history_label.setText("Select a single sensor to see its history.")
            self.no_history_label.show()
            return

        installed_id = selected_items[0].data(Qt.UserRole)
        history_data = db_manager.get_calibration_history_for_sensor(installed_id)

        if not history_data:
            self.history_table.hide()
            self.no_history_label.setText("No calibration history found for this sensor.")
            self.no_history_label.show()
            return

        self.history_table.show()
        self.no_history_label.hide()

        headers = ["Date", "Status", "RMSE X", "RMSE Y", "RMSE Z", "Sigma0", "Plane_Fit", "Notes"]
        self.history_table.setColumnCount(len(headers))
        self.history_table.setHorizontalHeaderLabels(headers)
        history_header = self.history_table.horizontalHeader()
        for i in range(len(headers)):
            if headers[i] == "Notes":
                history_header.setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                history_header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.history_table.setRowCount(len(history_data))
        for row_idx, record in enumerate(history_data):
            def get_display_text(key):
                value = record.get(key)
                return '' if value is None else str(value)

            self.history_table.setItem(row_idx, 0, QTableWidgetItem(get_display_text('Calibration_Date')))
            self.history_table.setItem(row_idx, 1, QTableWidgetItem(get_display_text('Status')))
            self.history_table.setItem(row_idx, 2, QTableWidgetItem(get_display_text('RMSE_X')))
            self.history_table.setItem(row_idx, 3, QTableWidgetItem(get_display_text('RMSE_Y')))
            self.history_table.setItem(row_idx, 4, QTableWidgetItem(get_display_text('RMSE_Z')))
            self.history_table.setItem(row_idx, 5, QTableWidgetItem(get_display_text('Sigma0')))
            self.history_table.setItem(row_idx, 6, QTableWidgetItem(get_display_text('Plane_Fit')))
            self.history_table.setItem(row_idx, 7, QTableWidgetItem(get_display_text('Notes')))
        
        self.history_table.resizeColumnsToContents()
