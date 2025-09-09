# app/widgets/sensor_dialog.py

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QComboBox, QDialogButtonBox, QMessageBox, QDateEdit
)
from PyQt5.QtCore import Qt, QDate

class SensorDialog(QDialog):
    """
    A dialog window for creating a new sensor or editing an existing one.
    The form fields are generated based on the provided table columns.
    """
    
    def __init__(self, sensor: dict = None, columns: list = None, parent=None):
        """
        Initializes the dialog.
        
        Args:
            sensor (dict, optional): Data for an existing sensor to pre-fill the form.
            columns (list, optional): A list of column names from the database table.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.sensor = sensor or {}
        self.columns = columns or []
        self.fields = {}  # To store references to the input widgets
        
        # Set window title based on whether we are adding or editing
        self.setWindowTitle("Edit Sensor" if sensor else "Add New Sensor")
        self.setMinimumWidth(400)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Sets up the UI elements of the dialog."""
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        # Dynamically create form fields based on the table's columns
        for column in self.columns:
            # Exclude fields that are auto-managed by the database
            if column.lower() in ['id', 'created_at', 'updated_at']:
                continue
                
            field = None
            current_value = self.sensor.get(column)

            # Create specific widget types for certain columns
            if 'date' in column.lower():
                field = QDateEdit()
                field.setCalendarPopup(True)
                field.setDisplayFormat("yyyy-MM-dd")
                if current_value:
                    try:
                        # Attempt to parse date from YYYY-MM-DD string
                        date_obj = QDate.fromString(str(current_value), "yyyy-MM-dd")
                        if date_obj.isValid():
                            field.setDate(date_obj)
                    except (ValueError, TypeError):
                        field.setDate(QDate.currentDate())
                else:
                    field.setDate(QDate.currentDate())

            elif column.lower() == 'status':
                field = QComboBox()
                field.addItems(['Active', 'Inactive', 'Maintenance', 'Retired'])
                if current_value:
                    index = field.findText(str(current_value), Qt.MatchFixedString)
                    if index >= 0:
                        field.setCurrentIndex(index)
            
            else: # Default to a QLineEdit for other text-based fields
                field = QLineEdit()
                if current_value is not None:
                    field.setText(str(current_value))
            
            if field:
                # Format the label for display (e.g., 'serial_number' -> 'Serial Number')
                display_name = column.replace('_', ' ').title()
                form_layout.addRow(f"{display_name}:", field)
                self.fields[column] = field  # Store the field for later data retrieval
        
        layout.addLayout(form_layout)
        
        # Standard OK and Cancel buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
    
    def validate_and_accept(self):
        """Performs basic validation before closing the dialog."""
        # Example: Ensure 'Name' and 'Model' fields are not empty
        for field_name in ['Name', 'Model', 'SN']:
            if field_name in self.fields:
                if not self.fields[field_name].text().strip():
                    QMessageBox.warning(self, "Validation Error", f"'{field_name}' is a required field.")
                    return  # Stop the accept process
        
        self.accept()  # If validation passes, accept the dialog

    def get_sensor_data(self) -> dict:
        """
        Retrieves the data from the form fields and returns it as a dictionary.
        
        Returns:
            dict: A dictionary mapping column names to their entered values.
        """
        data = {}
        for column, field in self.fields.items():
            if isinstance(field, QComboBox):
                data[column] = field.currentText()
            elif isinstance(field, QDateEdit):
                data[column] = field.date().toString("yyyy-MM-dd")
            else: # QLineEdit
                data[column] = field.text().strip()
        return data