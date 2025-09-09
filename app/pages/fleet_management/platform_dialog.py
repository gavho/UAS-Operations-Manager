from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QComboBox, QDialogButtonBox, QMessageBox, QDateEdit
)
from PyQt5.QtCore import Qt, QDate

class PlatformDialog(QDialog):
    """Dialog for adding/editing platform information."""
    
    def __init__(self, platform=None, columns=None, parent=None):
        """
        Initialize the dialog.
        
        Args:
            platform: Dictionary of platform data (for editing) or None (for new)
            columns: List of column names in the platforms table
            parent: Parent widget
        """
        super().__init__(parent)
        self.platform = platform or {}
        self.columns = columns or []
        self.fields = {}
        
        self.setWindowTitle("Edit Platform" if platform else "Add New Platform")
        self.setMinimumWidth(400)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        # Create form fields based on platform columns
        for column in self.columns:
            if column.lower() == 'id':
                continue
                
            # Skip columns that shouldn't be edited directly
            if column.lower() in ['created_at', 'updated_at', 'last_updated']:
                continue
                
            # Create appropriate input field based on column name
            if column.lower() == 'status':
                field = QComboBox()
                field.addItems(['Active', 'Inactive', 'In Maintenance'])
                if self.platform and column in self.platform:
                    index = field.findText(str(self.platform[column]))
                    if index >= 0:
                        field.setCurrentIndex(index)
            elif column.lower() == 'acquisition_date':
                field = QDateEdit()
                field.setCalendarPopup(True)
                field.setDisplayFormat("yyyy-MM-dd")
                if self.platform and column in self.platform and self.platform[column]:
                    try:
                        # Try to parse the date string (format: YYYY-MM-DD)
                        date_parts = list(map(int, str(self.platform[column]).split('-')))
                        if len(date_parts) == 3:
                            field.setDate(QDate(*date_parts))
                    except (ValueError, TypeError):
                        pass
                else:
                    field.setDate(QDate.currentDate())
            else:
                field = QLineEdit()
                if self.platform and column in self.platform and self.platform[column] is not None:
                    field.setText(str(self.platform[column]))
            
            # Set placeholder text
            display_name = column.replace('_', ' ').title()
            if column.lower() == 'sn':
                display_name = 'Serial Number'
            
            form_layout.addRow(f"{display_name}:", field)
            self.fields[column] = field
        
        layout.addLayout(form_layout)
        
        # Add buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        
        layout.addWidget(buttons)
    
    def validate(self):
        """Validate the form data before accepting."""
        # Check required fields
        required_fields = ['name', 'sn']
        for field in required_fields:
            if field in self.fields and not self.fields[field].text().strip():
                display_name = field.replace('_', ' ').title()
                if field == 'sn':
                    display_name = 'Serial Number'
                QMessageBox.warning(
                    self, "Validation Error",
                    f"{display_name} is required!"
                )
                return
        
        self.accept()
    
    def get_platform_data(self):
        """
        Get the platform data from the form.
        
        Returns:
            dict: Dictionary of field names to values
        """
        data = {}
        for column, field in self.fields.items():
            if isinstance(field, QComboBox):
                data[column] = field.currentText()
            elif isinstance(field, QDateEdit):
                # Format date as YYYY-MM-DD string
                data[column] = field.date().toString("yyyy-MM-dd")
            else:
                data[column] = field.text().strip()
        return data
