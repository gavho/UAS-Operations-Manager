from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMenu, QAction, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon


class PlatformCard(QFrame):
    """A card widget that displays information about a single platform."""
    
    # Signals
    edit_requested = pyqtSignal(dict)  # Emitted when edit is requested
    delete_requested = pyqtSignal(dict)  # Emitted when delete is requested
    
    def __init__(self, platform_data, parent=None):
        """
        Initialize the platform card with platform data.
        
        Args:
            platform_data: Dictionary containing platform information
            parent: Parent widget
        """
        super().__init__(parent)
        self.platform_data = platform_data
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface for the platform card."""
        # Set up the frame
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)
        self.setMinimumWidth(300)
        self.setMaximumWidth(350)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Header with name and status
        header_layout = QHBoxLayout()
        
        # Platform name
        name = self.platform_data.get('name', 'Unnamed Platform')
        self.name_label = QLabel(name)
        name_font = QFont()
        name_font.setPointSize(14)
        name_font.setBold(True)
        self.name_label.setFont(name_font)
        
        # Status indicator
        status = self.platform_data.get('status', 'unknown').lower()
        self.status_label = QLabel(status.upper())
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        status_font = QFont()
        status_font.setBold(True)
        self.status_label.setFont(status_font)
        
        # Set status color
        if status == 'active':
            self.status_label.setStyleSheet("color: #2ecc71;")  # Green
        elif status == 'inactive':
            self.status_label.setStyleSheet("color: #e74c3c;")  # Red
        elif status == 'maintenance':
            self.status_label.setStyleSheet("color: #f39c12;")  # Orange
        else:
            self.status_label.setStyleSheet("color: #7f8c8d;")  # Gray
        
        header_layout.addWidget(self.name_label)
        header_layout.addWidget(self.status_label)
        
        # Add header to main layout
        layout.addLayout(header_layout)
        
        # Add a separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: #ecf0f1;")
        layout.addWidget(line)
        
        # Platform details
        details_layout = QVBoxLayout()
        details_layout.setSpacing(5)
        
        # Add platform details (exclude some fields)
        exclude_fields = {'id', 'created_at', 'updated_at', 'last_updated'}
        
        for key, value in self.platform_data.items():
            if key.lower() in exclude_fields or value is None:
                continue
                
            # Format the key for display
            display_key = key.replace('_', ' ').title()
            if key.lower() == 'sn':
                display_key = 'Serial Number'
            
            # Create a row for this field
            row = QHBoxLayout()
            
            # Field name
            key_label = QLabel(f"{display_key}:")
            key_label.setStyleSheet("color: #7f8c8d; font-weight: bold;")
            key_label.setMinimumWidth(100)
            
            # Field value
            value_label = QLabel(str(value))
            value_label.setWordWrap(True)
            
            row.addWidget(key_label)
            row.addWidget(value_label, 1)  # Allow value to expand
            
            details_layout.addLayout(row)
        
        # Add details to main layout
        layout.addLayout(details_layout)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)
        
        # Edit button
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setIcon(QIcon.fromTheme("document-edit"))
        self.edit_btn.clicked.connect(self.on_edit_clicked)
        
        # Delete button
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setIcon(QIcon.fromTheme("edit-delete"))
        self.delete_btn.clicked.connect(self.on_delete_clicked)
        
        # Add buttons to layout
        button_layout.addWidget(self.edit_btn)
        button_layout.addWidget(self.delete_btn)
        
        # Add buttons to main layout
        layout.addLayout(button_layout)
        
        # Set the main layout
        self.setLayout(layout)
        
        # Apply styling
        self.apply_styling()
    
    def apply_styling(self):
        """Apply styling to the card."""
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #bdc3c7;
                border-radius: 8px;
                padding: 5px;
            }
            QFrame:hover {
                border: 1px solid #3498db;
                background-color: #f8f9fa;
            }
            QPushButton {
                padding: 5px 10px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """)
    
    def on_edit_clicked(self):
        """Handle edit button click."""
        self.edit_requested.emit(self.platform_data)
    
    def on_delete_clicked(self):
        """Handle delete button click."""
        self.delete_requested.emit(self.platform_data)
    
    def update_platform_data(self, platform_data):
        """Update the platform data displayed in the card."""
        self.platform_data = platform_data
        # Clear the current layout
        self.clear_layout(self.layout())
        # Rebuild the UI with new data
        self.setup_ui()
    
    def clear_layout(self, layout):
        """Recursively clear all items from a layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clear_layout(item.layout())
            # Remove the layout from its parent
            if layout.parentWidget():
                layout.parentWidget().setLayout(None)
