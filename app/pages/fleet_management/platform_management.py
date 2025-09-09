from typing import Dict, Any, Optional, List, Union
from datetime import datetime, date

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QFormLayout, QMessageBox, 
    QScrollArea, QFrame, QGridLayout, QComboBox, 
    QDateEdit, QTextEdit, QSizePolicy
)
from PyQt5.QtCore import Qt, QDate, pyqtSignal as Signal
from PyQt5.QtGui import QDoubleValidator, QIntValidator, QFont, QIcon
from sqlalchemy.orm import Session

from app.services.platform_service import PlatformService


class PlatformCard(QFrame):
    """A card widget that displays platform information and allows editing."""
    
    platform_updated = Signal(dict)  # Simplified type for PyQt5 compatibility
    edit_mode_changed = Signal(bool)  # Signal emitted when edit mode changes
    
    def __init__(self, platform_data=None, parent=None, schema_info=None):
        print("\n=== PlatformCard.__init__() called ===")
        try:
            print("Calling parent __init__...")
            super().__init__(parent)
            print("Parent __init__ complete")
            
            print("Initializing instance variables...")
            self.platform_data = platform_data or {}
            self.schema_info = schema_info or {}
            self.is_editing = False
            
            print("Setting up UI...")
            self.setup_ui()
            print("UI setup complete")
            
        except Exception as e:
            print(f"ERROR in PlatformCard.__init__: {e}")
            import traceback
            traceback.print_exc()
            raise
        
    def setup_ui(self):
        """Initialize the UI components for the platform card."""
        print("\n=== PlatformCard.setup_ui() called ===")
        try:
            # Main layout
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(15, 15, 15, 15)
            self.main_layout.setSpacing(15)
            
            # Header with name and edit button
            self.header_layout = QHBoxLayout()
            self.header_layout.setContentsMargins(0, 0, 0, 10)
            
            self.name_label = QLabel(self.platform_data.get('Name', 'New Platform'))
            name_font = QFont()
            name_font.setPointSize(14)
            name_font.setBold(True)
            self.name_label.setFont(name_font)
            
            self.edit_btn = QPushButton()
            self.edit_btn.setIcon(QIcon.fromTheme("document-edit"))
            self.edit_btn.setToolTip("Edit Platform")
            self.edit_btn.setFixedSize(30, 30)
            self.edit_btn.clicked.connect(self.toggle_edit_mode)
            
            self.header_layout.addWidget(self.name_label, 1)
            self.header_layout.addWidget(self.edit_btn)
            
            # Add header to main layout
            self.main_layout.addLayout(self.header_layout)
            
            # Create a scroll area for the form
            print("Creating scroll area...")
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            
            # Container widget for the scroll area
            print("Creating scroll content...")
            scroll_content = QWidget()
            self.form_layout = QFormLayout(scroll_content)
            self.form_layout.setContentsMargins(5, 5, 15, 5)  # Add right margin for scrollbar
            self.form_layout.setSpacing(10)
            
            # Set card style
            print("Setting card style...")
            self.setStyleSheet("""
                QFrame {
                    background-color: white;
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    padding: 10px;
                }
                QLabel {
                    font-size: 13px;
                }
                QLineEdit, QTextEdit, QComboBox, QDateEdit {
                    padding: 5px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    font-size: 13px;
                }
                QPushButton {
                    padding: 5px 10px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: #f0f0f0;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)
            
            # Add form fields based on the schema
            print("Creating form fields...")
            self.fields = {}
            field_defs = self.schema_info.get('fields', {})
            
            print(f"Found {len(field_defs)} field definitions")
            for field_name, field_def in field_defs.items():
                try:
                    print(f"Creating field: {field_name}")
                    db_column = field_def.get('db_column', field_name)
                    label = field_def.get('label', field_name.replace('_', ' ').title())
                    field_type = field_def.get('type', 'text')
                    
                    print(f"  - Label: {label}, Type: {field_type}, DB Column: {db_column}")
                    
                    # Create label
                    label_widget = QLabel(f"{label}:")
                    
                    # Create appropriate input field based on type
                    if field_type == 'textarea':
                        field = QTextEdit()
                        field.setMaximumHeight(100)
                    elif field_type == 'date':
                        field = QDateEdit()
                        field.setCalendarPopup(True)
                        field.setDisplayFormat("yyyy-MM-dd")
                    elif field_type == 'combo':
                        field = QComboBox()
                        options = field_def.get('options', [])
                        field.addItems(options)
                    else:  # text, number, etc.
                        field = QLineEdit()
                        if field_type == 'number':
                            field.setValidator(QDoubleValidator())
                    
                    # Set initial value if it exists
                    if db_column in self.platform_data:
                        print(f"  - Setting initial value: {self.platform_data[db_column]}")
                        self._set_field_value(field, self.platform_data[db_column])
                    
                    # Add to form layout
                    self.form_layout.addRow(label_widget, field)
                    self.fields[field_name] = field
                    print(f"  - Field created and added to form")
                    
                except Exception as e:
                    print(f"ERROR creating field {field_name}: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Set up the scroll area and add it to the main layout
            print("Setting up scroll area...")
            scroll.setWidget(scroll_content)
            self.main_layout.addWidget(scroll)
            
            # Add buttons at the bottom
            print("Creating buttons...")
            self.button_layout = QHBoxLayout()
            
            # Save button
            self.save_btn = QPushButton("Save")
            self.save_btn.setIcon(QIcon.fromTheme("document-save"))
            self.save_btn.clicked.connect(self.save_changes)
            self.button_layout.addWidget(self.save_btn)
            
            # Cancel button
            self.cancel_btn = QPushButton("Cancel")
            self.cancel_btn.setIcon(QIcon.fromTheme("dialog-cancel"))
            self.cancel_btn.clicked.connect(self.cancel_edit)
            self.button_layout.addWidget(self.cancel_btn)
            
            # Delete button (only for existing platforms)
            self.delete_btn = QPushButton("Delete")
            self.delete_btn.setIcon(QIcon.fromTheme("edit-delete"))
            self.delete_btn.setStyleSheet("background-color: #ffdddd;")
            self.delete_btn.clicked.connect(self.delete_platform)
            self.button_layout.addWidget(self.delete_btn)
            
            # Edit button (shown when not in edit mode)
            self.edit_btn = QPushButton()
            self.edit_btn.setIcon(QIcon.fromTheme("document-edit"))
            self.edit_btn.setToolTip("Edit Platform")
            self.edit_btn.clicked.connect(self.toggle_edit_mode)
            self.button_layout.addWidget(self.edit_btn)
            
            # Add buttons to main layout
            self.main_layout.addLayout(self.button_layout)
            
            # Set initial edit mode
            print("Setting initial edit mode...")
            self.set_editing(False)
            print("setup_ui() completed successfully")
            
        except Exception as e:
            print(f"ERROR in setup_ui: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _set_field_value(self, field, value):
        """Set the value of a field based on its type."""
        if value is None:
            return
            
        if isinstance(field, QComboBox):
            if isinstance(value, bool):
                value = 'Active' if value else 'Inactive'
            index = field.findText(str(value))
            if index >= 0:
                field.setCurrentIndex(index)
            elif field.isEditable():
                field.setCurrentText(str(value))
        elif isinstance(field, QDateEdit):
            if isinstance(value, str):
                # Try to parse the date string
                try:
                    date_obj = datetime.strptime(value, '%Y-%m-%d').date()
                    field.setDate(date_obj)
                except (ValueError, TypeError):
                    pass
            elif isinstance(value, (date, datetime)):
                field.setDate(value.date() if isinstance(value, datetime) else value)
        elif isinstance(field, QTextEdit):
            field.setText(str(value) if value else '')
        else:
            field.setText(str(value) if value else '')
    
    def toggle_edit_mode(self):
        """Toggle between view and edit modes."""
        self.set_editing(not self.is_editing)
    
    def set_editing(self, edit_mode):
        """Set the card to either view or edit mode."""
        if self.is_editing == edit_mode:
            return
            
        self.is_editing = edit_mode
        
        # Show/hide appropriate buttons
        self.save_btn.setVisible(edit_mode)
        self.cancel_btn.setVisible(edit_mode)
        self.delete_btn.setVisible(edit_mode)
        
        # Set field editability
        for field in self.fields.values():
            field.setReadOnly(not edit_mode)
        
        # Update edit button icon
        if edit_mode:
            self.edit_btn.setIcon(QIcon.fromTheme("dialog-cancel"))
            self.edit_btn.setToolTip("Cancel Editing")
        else:
            self.edit_btn.setIcon(QIcon.fromTheme("document-edit"))
            self.edit_btn.setToolTip("Edit Platform")
            
        # Emit signal that edit mode changed
        self.edit_mode_changed.emit(edit_mode)
    
    def save_changes(self):
        """Save changes made to the platform."""
        try:
            # Get field definitions from schema or use defaults
            field_defs = self.schema_info.get('fields', {
                'name': {'db_column': 'Name'},
                'model': {'db_column': 'Model'},
                'serial_number': {'db_column': 'SN'},
                'manufacturer': {'db_column': 'Manufacturer'},
                'customer': {'db_column': 'Customer'},
                'rc_model': {'db_column': 'RC_Model'},
                'rc_serial_number': {'db_column': 'RC_SN'},
                'remote_id': {'db_column': 'RemoteID'},
                'registration_number': {'db_column': 'FAA_Reg'},
                'purchase_date': {'db_column': 'Acquisition_Date'},
                'status': {'db_column': 'status'},
                'notes': {'db_column': 'Notes'}
            })
            
            # Get the updated data from the form
            updated_data = {}
            
            # Handle each field based on its type
            for field_name, field in self.fields.items():
                db_column = field_defs.get(field_name, {}).get('db_column', field_name)
                
                # Get value based on field type
                if isinstance(field, QComboBox):
                    value = field.currentText().strip() if field.currentText() else None
                elif isinstance(field, QDateEdit):
                    value = field.date().toPyDate() if field.date().isValid() else None
                elif isinstance(field, QTextEdit):
                    value = field.toPlainText().strip() or None
                else:  # QLineEdit
                    value = field.text().strip() or None
                
                # Only include non-None values
                if value is not None:
                    updated_data[db_column] = value
            
            # Add timestamps
            updated_data['updated_at'] = datetime.now()
            if not self.platform_data.get('id'):
                updated_data['created_at'] = datetime.now()
            
            # Validate required fields
            if not updated_data.get('Name'):
                QMessageBox.warning(self, "Validation Error", "Platform name is required.")
                return
                
            if not updated_data.get('Model'):
                QMessageBox.warning(self, "Validation Error", "Model is required.")
                return
            
            # Update the platform data with the new values
            if not self.platform_data:
                self.platform_data = {}
            self.platform_data.update(updated_data)
            
            # Update the view with the new data
            self.update_view()
            
            # Switch back to view mode
            self.set_editing(False)
            
            # Show success message
            QMessageBox.information(self, "Success", "Platform updated successfully!")
            
            # Emit signal that the platform was updated
            self.platform_updated.emit(self.platform_data)
            
            # Emit edit mode changed signal
            self.edit_mode_changed.emit(False)
            
        except ValueError as e:
            QMessageBox.warning(self, "Input Error", f"Invalid input: {str(e)}")
    
    def update_view(self):
        """Update the view with the current platform data."""
        self.name_label.setText(self.platform_data.get('name', 'New Platform'))
        self.model_label.setText(f"<b>Model:</b> {self.platform_data.get('model', 'N/A')}")
        self.serial_label.setText(f"<b>S/N:</b> {self.platform_data.get('serial_number', 'N/A')}")
        self.reg_label.setText(f"<b>Reg:</b> {self.platform_data.get('registration_number', 'N/A')}")
        self.manufacturer_label.setText(f"<b>Manufacturer:</b> {self.platform_data.get('manufacturer', 'N/A')}")
        self.weight_label.setText(f"<b>Weight:</b> {self.platform_data.get('weight', 'N/A')} kg")
        self.flight_time_label.setText(f"<b>Max Flight Time:</b> {self.platform_data.get('max_flight_time', 'N/A')} min")
        
        # Format dates
        self.purchase_date_label.setText(f"<b>Purchased:</b> {self._format_date(self.platform_data.get('purchase_date'))}")
        self.last_maintenance_label.setText(f"<b>Last Maint:</b> {self._format_date(self.platform_data.get('last_maintenance_date'))}")
        
        # Truncate notes if too long
        notes = self.platform_data.get('notes', '')
        if len(notes) > 50:
            notes = notes[:47] + '...'
        self.notes_label.setText(f"<b>Notes:</b> {notes or 'N/A'}")
        
        # Update status indicator
        self.update_status_indicator()
        
        # Update last updated time
        last_updated = self._format_datetime(self.platform_data.get('updated_at'))
        self.updated_label.setText(f"<small>Updated: {last_updated}</small>")
    
    def _format_date(self, date_value):
        """Format a date for display."""
        if not date_value:
            return "N/A"
        try:
            if hasattr(date_value, 'strftime'):
                return date_value.strftime('%Y-%m-%d')
            return str(date_value)
        except:
            return str(date_value)
    
    def _format_datetime(self, datetime_value):
        """Format a datetime for display."""
        if not datetime_value:
            return "N/A"
        try:
            if hasattr(datetime_value, 'strftime'):
                return datetime_value.strftime('%Y-%m-%d %H:%M')
            return str(datetime_value)
        except:
            return str(datetime_value)
    
    def cancel_edit(self):
        """Cancel editing and revert changes."""
        if self.platform_data.get('id'):  # Only if this is an existing platform
            self.update_view()  # Revert to saved data
        self.set_editing(False)
        
    def delete_platform(self):
        """Handle platform deletion."""
        print("\n=== delete_platform() called ===")
        try:
            if not self.platform_data.get('id'):
                print("No platform ID found, must be a new platform")
                if self.parent():
                    self.parent().remove_card(self)
                return
                
            # Ask for confirmation
            reply = QMessageBox.question(
                self, 'Delete Platform',
                'Are you sure you want to delete this platform? This cannot be undone.',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                print(f"Deleting platform with ID: {self.platform_data.get('id')}")
                # Emit signal to parent to handle the deletion
                if self.parent() and hasattr(self.parent(), 'remove_card'):
                    self.parent().remove_card(self)
                
        except Exception as e:
            print(f"ERROR in delete_platform: {e}")
            import traceback
            traceback.print_exc()


class PlatformManagementWidget(QWidget):
    """Main widget for managing platforms in the fleet."""
    
    # Signal emitted when platforms are updated
    platforms_updated = Signal()
    
    def __init__(self, db_session: Optional[Session] = None, parent=None):
        super().__init__(parent)
        self.db_session = db_session
        self.platform_service = PlatformService(db_session) if db_session else None
        self.current_add_card = None  # Track the current add card if any
        self.platform_cards = []  # Track all platform cards
        self.setup_ui()
        if db_session:
            self.load_platforms()
    
    def set_database_session(self, db_session: Session):
        """Update the database session for this widget."""
        self.db_session = db_session
        self.platform_service = PlatformService(db_session) if db_session else None
        
        # Clear existing cards
        if hasattr(self, 'scroll_layout'):
            self.clear_layout(self.scroll_layout)
        self.platform_cards = []
        self.current_add_card = None
        
        # Reload data if we have a valid session
        if db_session:
            self.load_platforms()
    
    def setup_ui(self):
        """Initialize the UI components."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(20)
        
        # Header with title and add button
        header_layout = QHBoxLayout()
        
        title = QLabel("Manage Fleet")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)
        
        self.add_btn = QPushButton("Add New Platform")
        self.add_btn.setIcon(QIcon.fromTheme("list-add"))
        self.add_btn.clicked.connect(self.add_new_platform)
        
        header_layout.addWidget(title, 1)
        header_layout.addWidget(self.add_btn)
        
        # Scroll area for platform cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Container widget for the scroll area
        self.scroll_content = QWidget()
        self.scroll_layout = QGridLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_layout.setSpacing(15)
        
        self.scroll_area.setWidget(self.scroll_content)
        
        # Add widgets to main layout
        self.main_layout.addLayout(header_layout)
        self.main_layout.addWidget(self.scroll_area)
    
    def load_platforms(self):
        """Load all platforms from the database, regardless of status."""
        if not self.db_session:
            print("No database session available")
            return []
            
        try:
            print("Fetching all platforms from service...")
            # Get all platforms including inactive ones
            platforms = self.platform_service.get_all_platforms(include_inactive=True)
            print(f"Found {len(platforms)} platforms in total")
            return platforms
            
        except Exception as e:
            print(f"Error loading platforms: {e}")
            import traceback
            traceback.print_exc()
            return []  
    
    def display_platforms(self, platforms):
        """Display the list of platforms as cards in a grid layout."""
        # Store the current add card if it exists
        add_card = self.current_add_card
        
        # Clear existing cards
        self.clear_layout(self.scroll_layout)
        
        # Reset the current add card
        self.current_add_card = None
        
        # Define the schema info for the cards
        print(f"Displaying {len(platforms) if platforms else 0} platforms...")
        
        # Clear existing content
        self.clear_layout(self.scroll_layout)
        self.platform_cards = []
        
        if not platforms:
            print("No platforms found in the database")
            no_platforms_label = QLabel("No platforms found in the database.\nClick 'Add Platform' to create a new one.")
            no_platforms_label.setAlignment(Qt.AlignCenter)
            no_platforms_label.setStyleSheet("color: #666; font-style: italic;")
            self.scroll_layout.addWidget(no_platforms_label)
            return
            
        try:
            # Create a widget to hold the grid layout
            grid_widget = QWidget()
            grid_layout = QGridLayout(grid_widget)
            grid_layout.setContentsMargins(10, 10, 10, 10)
            grid_layout.setSpacing(20)
            grid_layout.setColumnStretch(0, 1)
            grid_layout.setColumnStretch(1, 1)
            
            # Schema info for platform cards
            schema_info = {
                'fields': {
                    'name': {'db_column': 'Name', 'type': 'text', 'label': 'Name'},
                    'model': {'db_column': 'Model', 'type': 'text', 'label': 'Model'},
                    'serial_number': {'db_column': 'SN', 'type': 'text', 'label': 'Serial Number'},
                    'manufacturer': {'db_column': 'Manufacturer', 'type': 'text', 'label': 'Manufacturer'},
                    'customer': {'db_column': 'Customer', 'type': 'text', 'label': 'Customer'},
                    'rc_model': {'db_column': 'RC_Model', 'type': 'text', 'label': 'RC Model'},
                    'rc_serial_number': {'db_column': 'RC_SN', 'type': 'text', 'label': 'RC S/N'},
                    'remote_id': {'db_column': 'RemoteID', 'type': 'text', 'label': 'Remote ID'},
                    'registration_number': {'db_column': 'FAA_Reg', 'type': 'text', 'label': 'FAA Reg'},
                    'purchase_date': {'db_column': 'Acquisition_Date', 'type': 'date', 'label': 'Acquired'},
                    'status': {'db_column': 'status', 'type': 'text', 'label': 'Status'},
                    'notes': {'db_column': 'Notes', 'type': 'textarea', 'label': 'Notes'}
                }
            }
            
            # Add platform cards to the grid
            for i, platform in enumerate(platforms):
                row = i // 2  # 2 columns
                col = i % 2
                
                try:
                    print(f"Creating card for platform: {platform.get('Name', platform.get('name', 'Unnamed'))}")
                    # Ensure we're using the correct field names from the database
                    platform_data = {
                        'id': platform.get('id'),
                        'Name': platform.get('Name', platform.get('name', '')),
                        'Model': platform.get('Model', platform.get('model', '')),
                        'SN': platform.get('SN', platform.get('serial_number', '')),
                        'Manufacturer': platform.get('Manufacturer', platform.get('manufacturer', '')),
                        'status': platform.get('status', 'Active'),
                        'FAA_Reg': platform.get('FAA_Reg', platform.get('registration_number', '')),
                        'Acquisition_Date': platform.get('Acquisition_Date', platform.get('purchase_date', '')),
                        'Notes': platform.get('Notes', platform.get('notes', '')),
                        'Customer': platform.get('Customer', platform.get('customer', '')),
                        'RC_Model': platform.get('RC_Model', platform.get('rc_model', '')),
                        'RC_SN': platform.get('RC_SN', platform.get('rc_serial_number', '')),
                        'RemoteID': platform.get('RemoteID', platform.get('remote_id', ''))
                    }
                    
                    card = PlatformCard(platform_data, self, schema_info)
                    card.platform_updated.connect(self.save_platform)
                    card.edit_mode_changed.connect(lambda editing, c=card: self.on_edit_mode_changed(c, editing))
                    
                    grid_layout.addWidget(card, row, col, Qt.AlignTop)
                    self.platform_cards.append(card)
                    
                except Exception as e:
                    print(f"Error creating platform card: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Add the grid widget to the scroll area
            self.scroll_layout.addWidget(grid_widget)
            
        except Exception as e:
            print(f"Error in display_platforms: {e}")
            import traceback
            traceback.print_exc()
            
            # Show error message to user
            error_label = QLabel(f"Error displaying platforms: {str(e)}")
            error_label.setStyleSheet("color: red;")
            error_label.setWordWrap(True)
            self.scroll_layout.addWidget(error_label)
    
    def add_new_platform(self):
        """Add a new empty platform card in edit mode."""
        print("\n=== add_new_platform() called ===")
        
        # Only allow one add card at a time
        if self.current_add_card is not None:
            print("Add card already exists, scrolling to it")
            # Scroll to the existing add card
            self.scroll_area.ensureWidgetVisible(self.current_add_card)
            return
            
        print("Creating new platform card...")
        
        # Create a new empty platform with fields from the actual database schema
        new_platform = {
            'id': None,  # Will be set when saved to the database
            'Name': '',  # Platform name
            'Model': '',
            'SN': '',  # Serial Number
            'Manufacturer': 'DJI',  # Default to DJI as common manufacturer
            'Customer': '',
            'RC_Model': '',
            'RC_SN': '',
            'RemoteID': '',
            'FAA_Reg': '',  # Registration number
            'Acquisition_Date': '',  # Purchase date
            'status': 'Active',  # Default status
            'Notes': '',
            'created_at': None,
            'updated_at': None
        }
        
        print("Creating schema info...")
        # Create the card with schema info
        schema_info = {
            'fields': {
                'name': {'db_column': 'Name', 'type': 'text', 'label': 'Name'},
                'model': {'db_column': 'Model', 'type': 'text', 'label': 'Model'},
                'serial_number': {'db_column': 'SN', 'type': 'text', 'label': 'Serial Number'},
                'manufacturer': {'db_column': 'Manufacturer', 'type': 'combo', 'label': 'Manufacturer', 'options': ['DJI', 'Autel', 'Parrot', 'Skydio', 'Other']},
                'customer': {'db_column': 'Customer', 'type': 'text', 'label': 'Customer'},
                'rc_model': {'db_column': 'RC_Model', 'type': 'text', 'label': 'RC Model'},
                'rc_serial_number': {'db_column': 'RC_SN', 'type': 'text', 'label': 'RC Serial Number'},
                'remote_id': {'db_column': 'RemoteID', 'type': 'text', 'label': 'Remote ID'},
                'registration_number': {'db_column': 'FAA_Reg', 'type': 'text', 'label': 'FAA Registration'},
                'purchase_date': {'db_column': 'Acquisition_Date', 'type': 'date', 'label': 'Acquisition Date'},
                'status': {'db_column': 'status', 'type': 'combo', 'label': 'Status', 'options': ['Active', 'Inactive', 'Maintenance', 'Retired']},
                'notes': {'db_column': 'Notes', 'type': 'textarea', 'label': 'Notes'}
            }
        }
        print("Schema info created")
        
        print("Creating PlatformCard instance...")
        try:
            # Create the card
            card = PlatformCard(new_platform, self, schema_info)
            print("PlatformCard instance created")
            
            print("Connecting signals...")
            # Connect signals
            card.platform_updated.connect(self.save_platform)
            print("Connected platform_updated signal")
            
            # Use a lambda with a default argument to avoid late binding issues
            def on_edit_mode(editing, c=card):
                print(f"Edit mode changed: {editing}")
                self.on_edit_mode_changed(c, editing)
                
            card.edit_mode_changed.connect(on_edit_mode)
            print("Connected edit_mode_changed signal")
            
            # Track this as the current add card
            self.current_add_card = card
            print("Current add card set")
            
        except Exception as e:
            print(f"ERROR creating PlatformCard: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Add to the end of the grid
        count = self.scroll_layout.count()
        row = count // 2
        col = count % 2
        self.scroll_layout.addWidget(card, row, col)
        
        # Start in edit mode
        card.set_editing(True)
        
        # Scroll to the new card
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )
    
    def on_edit_mode_changed(self, card, is_editing):
        """Handle when a card's edit mode changes."""
        if not is_editing and card == self.current_add_card:
            # If the add card exits edit mode without saving, remove it
            self.remove_card(card)
            self.current_add_card = None
    
    def remove_card(self, card):
        """Remove a card from the layout."""
        # Find the card in the layout and remove it
        for i in range(self.scroll_layout.count()):
            item = self.scroll_layout.itemAt(i)
            if item.widget() == card:
                # Remove from layout and delete the widget
                self.scroll_layout.removeWidget(card)
                card.deleteLater()
                break
    
    def save_platform(self, platform_data: Dict[str, Any]) -> None:
        """Save platform data to the database."""
        if not self.platform_service:
            QMessageBox.warning(
                self,
                "Database Error",
                "No database connection available.",
                QMessageBox.Ok
            )
            return
        
        try:
            # Map platform_data keys to match database column names
            db_platform_data = {}
            field_mapping = {
                'name': 'Name',
                'model': 'Model',
                'serial_number': 'SN',
                'manufacturer': 'Manufacturer',
                'customer': 'Customer',
                'rc_model': 'RC_Model',
                'rc_serial_number': 'RC_SN',
                'remote_id': 'RemoteID',
                'registration_number': 'FAA_Reg',
                'purchase_date': 'Acquisition_Date',
                'status': 'status',
                'notes': 'Notes'
            }
            
            # Map the data to database column names
            for ui_field, db_column in field_mapping.items():
                if ui_field in platform_data:
                    db_platform_data[db_column] = platform_data[ui_field]
            
            # Get the platform ID (if it exists)
            platform_id = platform_data.get('id')
            
            # Validate required fields
            if not db_platform_data.get('Name'):
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    "Platform name is required.",
                    QMessageBox.Ok
                )
                return
            
            # Add timestamps
            now = datetime.now()
            db_platform_data['updated_at'] = now
            if not platform_id:
                db_platform_data['created_at'] = now
            
            # Save to database
            if platform_id:
                # Update existing platform
                success = self.platform_service.update_platform(platform_id, db_platform_data)
                action = "updated"
            else:
                # Create new platform
                new_platform = self.platform_service.create_platform(db_platform_data)
                success = new_platform is not None
                action = "created"
            
            if success:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Platform '{db_platform_data.get('Name', '')}' has been {action}.",
                    QMessageBox.Ok
                )
                
                # Reset the current add card if this was an add operation
                if not platform_id:
                    self.current_add_card = None
                
                # Reload platforms and emit signal
                self.load_platforms()
                self.platforms_updated.emit()
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Failed to save platform '{db_platform_data.get('Name', '')}'.",
                    QMessageBox.Ok
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save platform: {str(e)}",
                QMessageBox.Ok
            )
            
            # Log the full error for debugging
            import traceback
            print(f"Error saving platform: {traceback.format_exc()}")
    
    @staticmethod
    def clear_layout(layout):
        """Clear all widgets from a layout."""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
