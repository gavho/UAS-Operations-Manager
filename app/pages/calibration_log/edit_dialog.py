from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, 
    QDateEdit, QTextEdit, QDialogButtonBox, QMessageBox, QHBoxLayout, QPushButton
)
from app.database import db_manager

class EditCalibrationDialog(QDialog):
    data_changed = pyqtSignal()
    def __init__(self, edit_data, parent=None):
        super().__init__(parent)
        self.edit_data = edit_data
        self.record_id = edit_data.get('id')
        self.original_calibration_id = edit_data.get('Calibration_ID')
        self.setWindowTitle(f"Edit Calibration Record (ID: {self.record_id})" if self.record_id else "Edit Calibration Record")
        self.setMinimumWidth(500)

        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        # Form fields
        self.cal_id_layout = QHBoxLayout()
        self.calibration_id_edit = QLineEdit(self.original_calibration_id)
        self.cal_id_layout.addWidget(self.calibration_id_edit)
        self.generate_id_button = QPushButton("Generate")
        self.generate_id_button.clicked.connect(self.generate_calibration_id)
        self.cal_id_layout.addWidget(self.generate_id_button)
        
        self.platform_edit = QLineEdit(edit_data.get('Platform'))
        self.sensor_combo = QComboBox()
        self.installed_id_label = QLineEdit()
        self.installed_id_label.setReadOnly(True)
        
        self.cal_date_edit = QDateEdit(QDate.fromString(edit_data.get('Calibration_Date', ''), 'yyyy-MM-dd'))
        self.cal_date_edit.setCalendarPopup(True)
        self.status_combo = QComboBox()
        self.status_combo.addItems(['APPROVED', 'REVIEW'])
        self.status_combo.setCurrentText(edit_data.get('Status'))
        self.rmse_x_edit = QLineEdit(str(edit_data.get('RMSE_X', '')))
        self.rmse_y_edit = QLineEdit(str(edit_data.get('RMSE_Y', '')))
        self.rmse_z_edit = QLineEdit(str(edit_data.get('RMSE_Z', '')))
        self.sigma0_edit = QLineEdit(str(edit_data.get('Sigma0', '')))
        self.plane_fit_edit = QLineEdit(str(edit_data.get('Plane_Fit', '')))
        self.notes_edit = QTextEdit(edit_data.get('Notes'))
        
        # Set up the form layout
        self.setup_form()
        
        # Load and set the data
        self.set_data()
        
        # Add buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.on_save)
        self.button_box.rejected.connect(self.reject)
        
        # Add form and buttons to layout
        self.layout.addLayout(self.form_layout)
        self.layout.addWidget(self.button_box)

        self.sensor_combo.currentIndexChanged.connect(self.update_installed_id)
        self.load_sensors()

    def load_sensors(self):
        """Populate sensor list for the same system (chassis) as the record's Installed_ID."""
        self.sensor_combo.clear()
        self.sensors_data = db_manager.get_simplified_sensor_list()

        current_installed_id = self.edit_data.get('Installed_ID')
        # Determine the chassis for this Installed_ID
        chassis_sn = db_manager.get_chassis_sn_by_installed_id(current_installed_id)

        sensors_for_system = self.sensors_data.get(chassis_sn, []) if chassis_sn else []

        current_sensor_name = self.edit_data.get('Sensor')
        found = False

        for sensor in sensors_for_system:
            display_name = f"{sensor['sensor_name']} ({sensor['sensor_type']})"
            self.sensor_combo.addItem(display_name, userData=sensor)
            if str(sensor['installed_id']) == str(current_installed_id):
                self.sensor_combo.setCurrentText(display_name)
                found = True

        # Fallback: ensure current sensor is selectable even if not found in list
        if not found and current_sensor_name:
            self.sensor_combo.addItem(current_sensor_name, userData={'installed_id': current_installed_id})
            self.sensor_combo.setCurrentText(current_sensor_name)

        self.update_installed_id()

    def update_installed_id(self):
        sensor_data = self.sensor_combo.currentData()
        if sensor_data:
            self.installed_id_label.setText(str(sensor_data.get('installed_id', '')))

    def setup_form(self):
        """Set up the form layout with all the widgets."""
        self.form_layout.addRow("Calibration ID:", self.cal_id_layout)
        self.form_layout.addRow("Platform:", self.platform_edit)
        self.form_layout.addRow("Sensor:", self.sensor_combo)
        self.form_layout.addRow("Installed ID:", self.installed_id_label)
        self.form_layout.addRow("Calibration Date:*", self.cal_date_edit)
        self.form_layout.addRow("Status:", self.status_combo)
        self.form_layout.addRow("RMSE X:", self.rmse_x_edit)
        self.form_layout.addRow("RMSE Y:", self.rmse_y_edit)
        self.form_layout.addRow("RMSE Z:", self.rmse_z_edit)
        self.form_layout.addRow("Sigma0:", self.sigma0_edit)
        self.form_layout.addRow("Plane Fit:", self.plane_fit_edit)
        self.form_layout.addRow("Notes:", self.notes_edit)
        
    def set_data(self):
        """Populate the form fields with data from edit_data."""
        if not self.edit_data:
            return
            
        self.calibration_id_edit.setText(self.original_calibration_id or '')
        # Platform is the UAS platform used for the calibration.
        # Do not autofill for new records; only populate when editing an existing record.
        if self.record_id:
            self.platform_edit.setText(self.edit_data.get('Platform', ''))
        
        cal_date = self.edit_data.get('Calibration_Date')
        if cal_date:
            self.cal_date_edit.setDate(QDate.fromString(cal_date, 'yyyy-MM-dd'))
            
        status = self.edit_data.get('Status')
        if status:
            self.status_combo.setCurrentText(status)
            
        self.rmse_x_edit.setText(str(self.edit_data.get('RMSE_X', '')))
        self.rmse_y_edit.setText(str(self.edit_data.get('RMSE_Y', '')))
        self.rmse_z_edit.setText(str(self.edit_data.get('RMSE_Z', '')))
        self.sigma0_edit.setText(str(self.edit_data.get('Sigma0', '')))
        self.plane_fit_edit.setText(str(self.edit_data.get('Plane_Fit', '')))
        self.notes_edit.setPlainText(self.edit_data.get('Notes', ''))

    def generate_calibration_id(self):
        """Generate a new calibration ID based on the system chassis (from Installed_ID) and date."""
        # Determine installed_id from current selection or original data
        selected_sensor_data = self.sensor_combo.currentData()
        installed_id = None
        if selected_sensor_data and 'installed_id' in selected_sensor_data:
            installed_id = selected_sensor_data['installed_id']
        else:
            installed_id = self.edit_data.get('Installed_ID')

        chassis_sn = db_manager.get_chassis_sn_by_installed_id(installed_id) if installed_id else None
        if not chassis_sn or not self.cal_date_edit.date().isValid():
            QMessageBox.warning(self, "Missing Information", "A valid sensor selection and date are required to generate an ID.")
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

    def get_data(self):
        """Get the form data as a dictionary for saving."""
        try:
            # Get installed ID from selected sensor or use original
            selected_sensor_data = self.sensor_combo.currentData()
            installed_id = None
            
            if selected_sensor_data and 'installed_id' in selected_sensor_data:
                installed_id = selected_sensor_data['installed_id']
            else:
                installed_id = self.edit_data.get('Installed_ID')
                
            if not installed_id:
                QMessageBox.critical(self, "Error", "No sensor selected or invalid sensor data.")
                return None
                
            # Get platform (optional)
            platform = (self.platform_edit.text() or '').strip() or None
                
            # Validate date
            if not self.cal_date_edit.date().isValid():
                QMessageBox.critical(self, "Error", "Please select a valid calibration date.")
                return None
                
            # Ensure we have a calibration ID
            calibration_id = self.calibration_id_edit.text().strip()
            if not calibration_id:
                if not self.generate_calibration_id():
                    return None
                calibration_id = self.calibration_id_edit.text().strip()
                
            # Prepare numeric fields
            def safe_float(value):
                try:
                    return float(value) if value else 0.0
                except (ValueError, TypeError):
                    return 0.0
                    
            # Create the data dictionary
            data = {
                'id': self.record_id,
                'Calibration_ID': calibration_id,
                'Installed_ID': installed_id,
                'Platform': platform,
                'Calibration_Date': self.cal_date_edit.date().toString('yyyy-MM-dd'),
                'Status': self.status_combo.currentText(),
                'RMSE_X': safe_float(self.rmse_x_edit.text()),
                'RMSE_Y': safe_float(self.rmse_y_edit.text()),
                'RMSE_Z': safe_float(self.rmse_z_edit.text()),
                'Sigma0': safe_float(self.sigma0_edit.text()),
                'Plane_Fit': safe_float(self.plane_fit_edit.text()),
                'Notes': self.notes_edit.toPlainText()
            }
            
            return data
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while preparing the data: {str(e)}")
            return None

    def on_save(self):
        """Handle the save button click."""
        data_to_save = self.get_data()
        if data_to_save is None:
            return  # Error message was already shown in get_data

        if db_manager.update_calibration_record(data_to_save):
            QMessageBox.information(self, "Success", "Calibration record updated successfully.")
            self.data_changed.emit()
            self.accept()
        else:
            QMessageBox.critical(self, "Database Error", "Failed to update the calibration record.")
