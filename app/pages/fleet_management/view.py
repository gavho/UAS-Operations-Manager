import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QGridLayout, QDialog, QFrame, QMessageBox, QLineEdit, QComboBox,
    QFormLayout, QInputDialog, QDateEdit, QDialogButtonBox, QSizePolicy,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QSpinBox, QToolButton, QMenu
)
from PyQt5.QtCore import Qt, QDate, QSize, pyqtSignal, QDateTime, QTime, QTimer, QRectF, QUrl, QEvent
from PyQt5.QtGui import (
    QFont, QPixmap, QColor, QPainter, QBrush, QPen, QFontMetrics, QDesktopServices
)
from app.database.manager import db_manager
from app.database.maintenance_manager import maintenance_manager
from app.logic.battery_manager import (
    add_battery as add_battery_record,
    get_all_batteries,
    increment_cycle_count,
    delete_battery as delete_battery_record,
    update_battery as update_battery_record,
    batteries_support_platform_model,
)

class PlatformCard(QWidget):
    """A card widget to display platform information."""
    def __init__(self, platform_data, parent=None):
        super().__init__(parent)
        self.platform_data = platform_data
        self.parent = parent
        self.image_label = None  # Initialize image_label as instance variable
        self.setup_ui()

    def setup_ui(self):
        """Set up the card UI with consistent image display and styling."""
        self.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
                margin: 0;
                padding: 0;
            }
            QLabel#title {
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
                margin: 0;
                padding: 0;
            }
            QLabel#image_container {
                background: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin: 0 0 10px 0;
                padding: 5px;
            }
        """)

        # Fix the card width so text does not expand beyond image width
        # Image container is 180px wide; allow some padding and borders
        self.setFixedWidth(200)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
        main_layout.setAlignment(Qt.AlignTop)

        # --- Image Container ---
        self.image_container = QFrame()
        self.image_container.setFixedSize(180, 144)  # 4:3 aspect ratio
        self.image_container.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f9f9f9;
            }
        """)
        image_layout = QVBoxLayout(self.image_container)
        image_layout.setContentsMargins(4, 4, 4, 4)
        
        # Image label with fixed size
        if not hasattr(self, 'image_label') or self.image_label is None:
            self.image_label = QLabel()
            self.image_label.setAlignment(Qt.AlignCenter)
            self.image_label.setFixedSize(172, 136)  # Slightly smaller than container
            self.image_label.setStyleSheet("""
                QLabel {
                    background-color: white;
                    border: 1px solid #eee;
                    border-radius: 2px;
                }
            """)
            image_layout.addWidget(self.image_label)
        
        # Set the platform image based on model name
        model_name = self.platform_data.get('model', '')
        self.update_platform_image(model_name)
        
        main_layout.addWidget(self.image_container)

        # --- Details ---
        details_layout = QVBoxLayout()
        details_layout.setSpacing(2)

        name_label = QLabel(self.platform_data.get('name') or 'Unnamed Platform')
        name_label.setFont(QFont("Arial", 11, QFont.Bold))
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setWordWrap(True)

        # Status with colored indicator
        status_layout = QHBoxLayout()
        status_layout.setAlignment(Qt.AlignCenter)
        status_indicator = QLabel()
        status_indicator.setFixedSize(10, 10)
        status_indicator.setStyleSheet(self._get_status_style())
        status_label = QLabel(self.platform_data.get('status', 'Unknown'))
        status_label.setAlignment(Qt.AlignCenter)
        status_label.setStyleSheet("font-size: 10px; color: #666;")
        status_layout.addWidget(status_indicator)
        status_layout.addWidget(status_label)

        manufacturer_label = QLabel(self.platform_data.get('manufacturer', 'N/A'))
        manufacturer_label.setAlignment(Qt.AlignCenter)
        manufacturer_label.setWordWrap(True)

        model_label = QLabel(self.platform_data.get('model', 'N/A'))
        model_label.setAlignment(Qt.AlignCenter)
        model_label.setWordWrap(True)

        details_layout.addWidget(name_label)
        details_layout.addLayout(status_layout)
        details_layout.addWidget(manufacturer_label)
        details_layout.addWidget(model_label)

        # --- Buttons --- 
        button_layout = QHBoxLayout()
        edit_btn = QPushButton("Edit")
        delete_btn = QPushButton("Delete")
        edit_btn.clicked.connect(self.edit_platform)
        delete_btn.clicked.connect(self.delete_platform)

        button_layout.addWidget(edit_btn)
        button_layout.addWidget(delete_btn)

        main_layout.addLayout(details_layout)
        main_layout.addStretch()
        main_layout.addLayout(button_layout)
    
    def edit_platform(self):
        """Open the edit dialog for this platform."""
        if self.parent:
            self.parent.show_edit_platform_dialog(self.platform_data)

    def delete_platform(self):
        """Delete this platform after confirmation."""
        if self.parent:
            self.parent.delete_platform(self.platform_data.get('id'))

    def update_platform_image(self, model_name):
        """Update the platform image based on the model name."""
        if not model_name:
            self.set_placeholder_image()
            return

        base_path = "resources/images"
        extensions = ['.png', '.jpg', '.jpeg', '.webp']
        
        # Create potential filenames (case-insensitive)
        name_variations = [
            model_name.replace(' ', '_').lower(),
            model_name.replace(' ', '').lower(),
            model_name.split(' ')[-1].lower()  # Handles cases like 'DJI M600' -> 'm600'
        ]
        
        # Check for exact matches first, then try case-insensitive
        for name in name_variations:
            # Try exact filename match
            for ext in extensions:
                path = os.path.join(base_path, f"{name}{ext}")
                if os.path.exists(path):
                    self.set_platform_image(path)
                    return
            
            # Try case-insensitive match
            if os.path.exists(base_path):
                for file in os.listdir(base_path):
                    if file.lower().startswith(name.lower()) and any(file.lower().endswith(ext) for ext in extensions):
                        path = os.path.join(base_path, file)
                        self.set_platform_image(path)
                        return
        
        # If no image found, use placeholder
        self.set_placeholder_image()
    
    def set_platform_image(self, image_path):
        """Set the platform image from the given path."""
        if not os.path.exists(image_path):
            self.set_placeholder_image()
            return
            
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.set_placeholder_image()
            return
            
        # Scale pixmap to fit the label while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)
    
    def set_placeholder_image(self):
        """Set a placeholder image with the model name initials."""
        # Create a colored placeholder with the first letter of the model name
        model_name = self.platform_data.get('model', '?')
        if model_name and model_name != '?':
            # Get first letter of each word in the model name
            initials = ''.join(word[0].upper() for word in model_name.split())
            if not initials:
                initials = '?'
        else:
            initials = '?'
            
        # Create a colored pixmap based on the model name hash for consistency
        color_hash = hash(model_name) % 0xFFFFFF
        color = QColor(color_hash & 0xFF, (color_hash >> 8) & 0xFF, (color_hash >> 16) & 0xFF)
        
        # Create a colored rectangle with the initials
        pixmap = QPixmap(self.image_label.size())
        pixmap.fill(Qt.transparent)
        
        from PyQt5.QtGui import QPainter, QBrush, QPen, QFont
        painter = QPainter(pixmap)
        
        # Draw background circle
        size = min(pixmap.width(), pixmap.height()) - 10
        x = (pixmap.width() - size) // 2
        y = (pixmap.height() - size) // 2
        
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(color.lighter(150)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(x, y, size, size)
        
        # Draw text
        font = QFont()
        font.setPointSize(min(size // 2, 32))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(Qt.black)
        
        # Center text
        text_rect = painter.boundingRect(pixmap.rect(), Qt.AlignCenter, initials)
        painter.drawText(text_rect, Qt.AlignCenter, initials)
        
        painter.end()
        self.image_label.setPixmap(pixmap)

    def _get_status_style(self):
        """Get the CSS style for the status indicator based on platform status."""
        status = self.platform_data.get('status', '').lower() if self.platform_data else 'unknown'

        if status == 'active':
            return """
                QLabel {
                    background-color: #28a745;
                    border-radius: 5px;
                    border: 1px solid #1e7e34;
                }
            """
        elif status == 'inactive':
            return """
                QLabel {
                    background-color: #dc3545;
                    border-radius: 5px;
                    border: 1px solid #bd2130;
                }
            """
        elif status == 'in maintenance':
            return """
                QLabel {
                    background-color: #fd7e14;
                    border-radius: 5px;
                    border: 1px solid #e8680f;
                }
            """
        else:
            return """
                QLabel {
                    background-color: #6c757d;
                    border-radius: 5px;
                    border: 1px solid #545b62;
                }
            """

class PlatformDialog(QDialog):
    """Dialog for adding/editing a platform."""
    def __init__(self, parent=None, platform_data=None):
        super().__init__(parent)
        self.platform_data = platform_data or {}
        self.setWindowTitle("Edit Platform" if platform_data else "Add Platform")
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the dialog UI."""
        self.setMinimumWidth(400)
        layout = QVBoxLayout()
        
        # Form layout
        form = QFormLayout()
        
        # Name
        self.name_edit = QLineEdit(self.platform_data.get('name', ''))
        form.addRow("Name:", self.name_edit)

        self.manufacturer_edit = QLineEdit(self.platform_data.get('manufacturer', ''))
        form.addRow("Manufacturer:", self.manufacturer_edit)

        self.model_edit = QLineEdit(self.platform_data.get('model', ''))
        form.addRow("Model:", self.model_edit)

        self.sn_edit = QLineEdit(self.platform_data.get('serial_number', ''))
        form.addRow("Serial # (SN):", self.sn_edit)

        self.faa_edit = QLineEdit(self.platform_data.get('faa_registration', ''))
        form.addRow("FAA Reg:", self.faa_edit)

        self.customer_edit = QLineEdit(self.platform_data.get('Customer', ''))
        form.addRow("Customer:", self.customer_edit)

        self.rc_model_edit = QLineEdit(self.platform_data.get('RC_Model', ''))
        form.addRow("RC Model:", self.rc_model_edit)

        self.rc_sn_edit = QLineEdit(self.platform_data.get('RC_SN', ''))
        form.addRow("RC S/N:", self.rc_sn_edit)

        self.remote_id_edit = QLineEdit(self.platform_data.get('RemoteID', ''))
        form.addRow("Remote ID:", self.remote_id_edit)

        self.notes_edit = QLineEdit(self.platform_data.get('Notes', ''))
        form.addRow("Notes:", self.notes_edit)
        
        # Acquisition Date
        self.acquisition_date_edit = QDateEdit()
        self.acquisition_date_edit.setCalendarPopup(True)
        self.acquisition_date_edit.setDisplayFormat("yyyy-MM-dd")
        if 'acquisition_date' in self.platform_data and self.platform_data['acquisition_date']:
            try:
                # Try to parse the date string (format: YYYY-MM-DD)
                date_parts = list(map(int, str(self.platform_data['acquisition_date']).split('-')))
                if len(date_parts) == 3:
                    self.acquisition_date_edit.setDate(QDate(*date_parts))
            except (ValueError, TypeError):
                self.acquisition_date_edit.setDate(QDate.currentDate())
        else:
            self.acquisition_date_edit.setDate(QDate.currentDate())
        form.addRow("Acquisition Date:", self.acquisition_date_edit)
        
        # Status
        self.status_combo = QComboBox()
        self.status_combo.addItems(['Active', 'Inactive', 'In Maintenance'])
        if 'status' in self.platform_data:
            index = self.status_combo.findText(self.platform_data['status'], Qt.MatchFixedString)
            if index >= 0:
                self.status_combo.setCurrentIndex(index)
        form.addRow("Status:", self.status_combo)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.accept)
        
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        
        layout.addLayout(buttons)
        self.setLayout(layout)
    
    def get_data(self):
        """Get the form data as a dictionary."""
        data = {
            'id': self.platform_data.get('id'), # Pass the ID for updates
            'name': self.name_edit.text().strip(),
            'manufacturer': self.manufacturer_edit.text().strip(),
            'model': self.model_edit.text().strip(),
            'serial_number': self.sn_edit.text().strip(),
            'faa_registration': self.faa_edit.text().strip(),
            'status': self.status_combo.currentText(),
            'Customer': self.customer_edit.text().strip(),
            'RC_Model': self.rc_model_edit.text().strip(),
            'RC_SN': self.rc_sn_edit.text().strip(),
            'RemoteID': self.remote_id_edit.text().strip(),
            'Acquisition_Date': self.acquisition_date_edit.date().toString("yyyy-MM-dd"),
            'Notes': self.notes_edit.text().strip(),
        }
        return data

class FleetManagementPage(QWidget):
    """Main fleet management page."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._platforms_data = []  # Cache for all platforms

        # Initialize status filters
        self._status_filters = {}
        self.status_filter_definitions = [
            ('Active', 'Active'),
            ('Inactive', 'Inactive'),
            ('In Maintenance', 'In Maintenance')
        ]
        for status_id, _ in self.status_filter_definitions:
            self._status_filters[status_id] = False

        self.active_filter_widgets = {}  # To keep track of active filter widgets

        self.setup_ui()

        # Connect to database changes before initial load
        db_manager.connection_set.connect(self.load_platforms)

        # Perform initial load
        self.load_platforms()

        # Initialize filter menu
        self._update_filter_menu()

    def setup_ui(self):
        """Set up the user interface with tabs."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- Header ---
        header = QHBoxLayout()
        title = QLabel("Fleet Management")
        title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 5px 0;")
        header.addWidget(title)
        header.addStretch()
        main_layout.addLayout(header)

        # --- Tabs ---
        self.tab_widget = QTabWidget()
        # Modernize tabs appearance (pill-style)
        self.tab_widget.setDocumentMode(False)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 0; }
            QTabBar { qproperty-drawBase: 0; }
            QTabBar::tab {
                background: transparent;
                color: #374151;
                padding: 6px 14px;
                border: 1px solid transparent;
                border-radius: 16px;
                margin: 6px 6px 0 0;
            }
            QTabBar::tab:hover {
                background: #eef2ff;
                color: #111827;
            }
            QTabBar::tab:selected {
                background: #2c7be5;
                color: white;
                border-color: #2c7be5;
                font-weight: 600;
            }
        """)
        main_layout.addWidget(self.tab_widget, 1)

        # Platforms tab content
        self.platforms_tab = QWidget()
        platforms_layout = QVBoxLayout(self.platforms_tab)

        # Top bar for controls (search/sort)
        top_bar_layout = QHBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search by name...")
        self.search_bar.textChanged.connect(self.filter_and_sort_platforms)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Sort by...", "Name (A-Z)", "Name (Z-A)",
            "Manufacturer (A-Z)", "Manufacturer (Z-A)",
            "Model (A-Z)", "Model (Z-A)",
            "Acquisition Date (Newest)", "Acquisition Date (Oldest)",
            "Status (A-Z)", "Status (Z-A)"
        ])
        self.sort_combo.currentTextChanged.connect(self.filter_and_sort_platforms)
        # Add Platform button inside Platforms tab
        add_btn = QPushButton("Add Platform")
        add_btn.setFixedWidth(150)
        add_btn.setStyleSheet("""
            QPushButton { padding: 8px; background: #2c7be5; color: white; border: none; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background: #1a6bd9; }
        """)
        add_btn.clicked.connect(self.show_add_platform_dialog)

        top_bar_layout.addWidget(self.search_bar, 1)
        top_bar_layout.addWidget(self.sort_combo)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(add_btn)
        platforms_layout.addLayout(top_bar_layout)

        # --- Filter Dropdown and Active Filters ---
        filter_container = QWidget()
        filter_layout = QVBoxLayout(filter_container)
        filter_layout.setContentsMargins(0, 0, 0, 10)

        # Filter dropdown button
        self.filter_dropdown = QToolButton()
        self.filter_dropdown.setText('Add Filter ▼')
        self.filter_dropdown.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.filter_dropdown.setPopupMode(QToolButton.InstantPopup)
        self.filter_dropdown.setStyleSheet("""
            QToolButton {
                padding: 5px 10px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f0f0f0;
                text-align: left;
                min-width: 120px;
            }
            QToolButton::menu-indicator { width: 0px; }
        """)

        # Create menu for filter dropdown
        self.filter_menu = QMenu()
        self.filter_dropdown.setMenu(self.filter_menu)

        # Container for active filter tags
        self.active_filters_container = QWidget()
        self.active_filters_layout = QHBoxLayout(self.active_filters_container)
        self.active_filters_layout.setContentsMargins(0, 5, 0, 0)
        self.active_filters_layout.setSpacing(5)

        # Add widgets to layout
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filters:"))
        filter_row.addWidget(self.filter_dropdown)
        filter_row.addStretch(1)

        filter_layout.addLayout(filter_row)
        filter_layout.addWidget(self.active_filters_container)

        platforms_layout.addWidget(filter_container)

        # Scroll Area for Cards
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        # Disable horizontal scrolling; allow vertical as needed
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.cards_container = QWidget()
        # Ensure container doesn't enforce a minimum width wider than the viewport
        self.cards_container.setMinimumWidth(0)
        self.cards_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setSpacing(20)
        self.cards_layout.setContentsMargins(20, 20, 20, 20)
        # Save base margins for responsive centering calculations
        self._cards_base_margins = self.cards_layout.contentsMargins()
        self.cards_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.cards_container)
        # Reflow when the scroll viewport resizes for fluid layout
        self.scroll.viewport().installEventFilter(self)
        platforms_layout.addWidget(self.scroll, 1)

        self.tab_widget.addTab(self.platforms_tab, "Platforms")

        # Maintenance tab (embedded panel)
        self.maintenance_tab = QWidget()
        maint_layout = QVBoxLayout(self.maintenance_tab)
        self.maintenance_panel = MaintenancePanel(self)
        maint_layout.addWidget(self.maintenance_panel)
        self.tab_widget.addTab(self.maintenance_tab, "Maintenance Log")

        # Battery tab (embedded panel)
        self.battery_tab = QWidget()
        batt_layout = QVBoxLayout(self.battery_tab)
        self.battery_panel = BatteryPanel(self)
        batt_layout.addWidget(self.battery_panel)
        self.tab_widget.addTab(self.battery_tab, "Battery Inventory")

        # No auto-open dialogs; tabs show embedded panels

    def _on_filter_selected(self, display_name):
        """Handle selection of a filter from the dropdown."""
        # Check if this is a status filter
        if display_name in self._status_filters:
            if not self._status_filters.get(display_name, False):
                self._status_filters[display_name] = True
        # Add a single tag for the display name
        self._add_active_filter_tag(display_name, display_name)
        self._update_filter_menu()
        self.filter_and_sort_platforms()

    def _on_remove_filter(self, display_name):
        """Handle removing a filter tag."""
        # Check if this is a status filter
        if display_name in self._status_filters:
            self._status_filters[display_name] = False

        # Remove the UI tag
        if display_name in self.active_filter_widgets:
            widget = self.active_filter_widgets.pop(display_name)
            widget.setParent(None)
            widget.deleteLater()

        self._update_filter_menu()
        self.filter_and_sort_platforms()

    def _add_active_filter_tag(self, tag_id, display_name):
        """Add a removable filter tag to the UI."""
        if tag_id in self.active_filter_widgets:
            return

        tag_widget = QWidget()
        tag_layout = QHBoxLayout(tag_widget)
        tag_layout.setContentsMargins(5, 2, 5, 2)
        tag_layout.setSpacing(5)

        label = QLabel(display_name)

        close_btn = QPushButton('×')
        close_btn.setStyleSheet("""
            QPushButton { border: none; color: #666; font-weight: bold; padding: 0 2px; margin: 0; }
            QPushButton:hover { color: #000; background: #ddd; border-radius: 2px; }
        """)
        close_btn.setFixedSize(16, 16)
        close_btn.clicked.connect(lambda _, t=tag_id: self._on_remove_filter(t))

        tag_widget.setStyleSheet("""
            QWidget { background: #e0e0e0; border-radius: 10px; padding: 2px 5px; }
        """)

        tag_layout.addWidget(label)
        tag_layout.addWidget(close_btn)

        self.active_filters_layout.addWidget(tag_widget)
        self.active_filter_widgets[tag_id] = tag_widget

    def _update_filter_menu(self):
        """Update the filter menu to show only inactive filters."""
        self.filter_menu.clear()

        # Add status filters first
        status_section_added = False
        for status_name in sorted(self._status_filters.keys()):
            if status_name not in self.active_filter_widgets:
                if not status_section_added:
                    self.filter_menu.addSection("Status")
                    status_section_added = True
                action = self.filter_menu.addAction(status_name)
                # Use functools.partial to avoid lambda closure issues
                from functools import partial
                action.triggered.connect(partial(self._on_filter_selected, status_name))

        self.filter_dropdown.setEnabled(status_section_added)

    def filter_and_sort_platforms(self):
        """Filter and sort platforms based on UI controls."""
        if not hasattr(self, '_platforms_data'):
            return

        # 1. Filter by search text
        search_text = self.search_bar.text().lower()
        if search_text:
            platforms_to_display = [p for p in self._platforms_data if search_text in p.get('name', '').lower()]
        else:
            platforms_to_display = self._platforms_data[:]

        # 2. Filter by status
        active_statuses = {status.lower() for status, active in self._status_filters.items() if active}
        if active_statuses:
            platforms_to_display = [p for p in platforms_to_display if p.get('status', '').lower() in active_statuses]

        # 2. Sort the filtered results
        sort_index = self.sort_combo.currentIndex()
        if sort_index > 0:
            sort_option = self.sort_combo.itemText(sort_index)
            sort_key = None
            reverse = False

            if "Name" in sort_option: sort_key = lambda p: (p.get('name') or '').lower()
            elif "Manufacturer" in sort_option: sort_key = lambda p: (p.get('manufacturer') or '').lower()
            elif "Model" in sort_option: sort_key = lambda p: (p.get('model') or '').lower()
            elif "Status" in sort_option: sort_key = lambda p: (p.get('status') or '').lower()
            elif "Acquisition Date" in sort_option:
                sort_key = lambda p: p.get('acquisition_date', '0000-00-00') or '0000-00-00'
                reverse = "Newest" in sort_option

            if "(Z-A)" in sort_option or "(Oldest)" in sort_option:
                 reverse = True
            if "(A-Z)" in sort_option or "(Newest)" in sort_option:
                 reverse = False

            if sort_key:
                platforms_to_display.sort(key=sort_key, reverse=reverse)

        self.populate_cards(platforms_to_display)

    # Removed dialog open handlers as panels are embedded

    def populate_cards(self, platforms):
        """Populate the grid with a list of platform cards."""
        self.clear_all(silent=True)
        if not platforms:
            self.show_no_platforms_message()
            return

        for platform_data in platforms:
            card = PlatformCard(platform_data, self)
            self.cards_layout.addWidget(card)
        self.update_grid_layout()

    def update_grid_layout(self):
        """Arrange cards responsively without causing horizontal scroll."""
        if self.cards_layout.count() == 0:
            return
        
        # Determine card width from an existing card, fallback to 200
        sample_card = None
        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget():
                sample_card = item.widget()
                break
        card_width = 200
        if sample_card:
            # width() may be 0 before shown; use sizeHint as fallback
            card_width = sample_card.width() or sample_card.sizeHint().width() or 200

        # Spacing and margins
        spacing = self.cards_layout.horizontalSpacing()
        if spacing is None or spacing < 0:
            spacing = self.cards_layout.spacing()
        # Use stored base margins to avoid compounding during reflows
        base_margins = getattr(self, '_cards_base_margins', self.cards_layout.contentsMargins())
        left, top, right, bottom = base_margins.left(), base_margins.top(), base_margins.right(), base_margins.bottom()

        # Available width is the viewport width minus left/right margins
        viewport_width = self.scroll.viewport().width() if hasattr(self, 'scroll') and self.scroll else self.width()
        available = max(0, viewport_width - (left + right))

        # Compute columns that fit: account for gaps between items
        denom = max(1, card_width + spacing)
        num_cols = max(1, (available + spacing) // denom)

        # Center the grid by adjusting left/right margins based on leftover width
        total_cards_width = int(num_cols * card_width + max(0, num_cols - 1) * spacing)
        leftover = max(0, available - total_cards_width)
        new_left = left + leftover // 2
        new_right = right + leftover - (leftover // 2)
        # Apply margins only if changed
        self.cards_layout.setContentsMargins(new_left, top, new_right, bottom)
        
        widgets = []
        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget():
                widgets.append(item.widget())

        # Clear layout before re-adding
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)

        for i, widget in enumerate(widgets):
            row, col = i // num_cols, i % num_cols
            self.cards_layout.addWidget(widget, row, col)

    def eventFilter(self, obj, event):
        # Reflow cards when the viewport resizes to keep layout fluid
        if hasattr(self, 'scroll') and obj is self.scroll.viewport() and event.type() == QEvent.Resize:
            self.update_grid_layout()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        """Recalculate grid columns on window resize."""
        super().resizeEvent(event)
        self.update_grid_layout()

    def clear_all(self, silent=False):
        """Remove all platform cards and reset view."""
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        if not silent:
            self.show_no_platforms_message("Loading platforms...")

    def load_platforms(self):
        """Load all platforms from the database and update the view."""
        self._platforms_data = db_manager.get_all_platforms()

        if not self._platforms_data:
            if not db_manager.session:
                self.show_no_platforms_message("No database opened.")
            else:
                self.show_no_platforms_message("No platforms found.")
        
        # Set default sort and trigger display update
        # This ensures the view is populated on initial load and subsequent refreshes
        self.sort_combo.setCurrentText("Name (A-Z)")
        self.filter_and_sort_platforms()

    def show_no_platforms_message(self, message="No platforms found."):
        """Display a message in the center of the card area."""
        self.clear_all(silent=True)
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 16px; color: #888;")
        self.cards_layout.addWidget(label, 0, 0, 1, 5)

    def show_error_message(self, message):
        """Display an error message in the UI."""
        self.clear_all(silent=True)
        error_label = QLabel(f"Error: {message}")
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet("font-size: 16px; color: red;")
        self.cards_layout.addWidget(error_label, 0, 0, 1, 5)

    def show_add_platform_dialog(self):
        """Show the add platform dialog."""
        dialog = PlatformDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.save_platform(dialog.get_data())

    def show_edit_platform_dialog(self, platform_data):
        """Show the edit platform dialog."""
        dialog = PlatformDialog(self, platform_data=platform_data)
        if dialog.exec_() == QDialog.Accepted:
            self.save_platform(dialog.get_data())

    def save_platform(self, platform_data):
        """Save platform data to the database using SQLAlchemy ORM."""
        if not db_manager.session:
            QMessageBox.critical(self, "Error", "No database connection available.")
            return

        session = db_manager.session
        Platform = db_manager.models.get('platforms')

        try:
            if platform_data.get('id'):  # Update
                platform_obj = session.query(Platform).get(platform_data['id'])
                if platform_obj:
                    # Explicit mapping from dialog data keys to model attribute names
                    update_mapping = {
                        'name': 'Name',
                        'manufacturer': 'Manufacturer',
                        'model': 'Model',
                        'serial_number': 'SN',
                        'faa_registration': 'FAA_Reg',
                        'status': 'status',
                        'Customer': 'Customer',
                        'RC_Model': 'RC_Model',
                        'RC_SN': 'RC_SN',
                        'RemoteID': 'RemoteID',  # Corrected model attribute name
                        'Acquisition_Date': 'Acquisition_Date',
                        'Notes': 'Notes',
                    }
                    for form_key, model_attr in update_mapping.items():
                        if form_key in platform_data:
                            setattr(platform_obj, model_attr, platform_data[form_key])
            else: # Create
                mapped_data = {
                    'Name': platform_data.get('name'), 'Manufacturer': platform_data.get('manufacturer'),
                    'Model': platform_data.get('model'), 'SN': platform_data.get('serial_number'),
                    'FAA_Reg': platform_data.get('faa_registration'), 'status': platform_data.get('status'),
                    'Customer': platform_data.get('Customer'), 'RC_Model': platform_data.get('RC_Model'),
                    'RC_SN': platform_data.get('RC_SN'), 'RemoteID': platform_data.get('RemoteID'),
                    'Acquisition_Date': platform_data.get('Acquisition_Date'), 'Notes': platform_data.get('Notes'),
                }
                new_platform = Platform(**mapped_data)
                session.add(new_platform)
            
            session.commit()
            db_manager.platforms_updated.emit()  # Notify other components of platform changes
            self.load_platforms()
            self.sort_combo.setCurrentText("Name (A-Z)")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Database Error", f"Failed to save platform: {e}")


class MaintenancePanel(QWidget):
    """Embedded panel for maintenance management (formerly a dialog)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_platforms()
        self.load_maintenance_logs()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        # Form
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        self.platform_combo = QComboBox()
        self.maintenance_type_combo = QComboBox()
        self.maintenance_type_combo.addItems(["Firmware Update", "Repair", "Cleaning/Upkeep", "Inspection", "Modification"])
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.performed_by_edit = QLineEdit()
        self.description_edit = QLineEdit()
        self.image_path_edit = QLineEdit()
        self.image_path_edit.setPlaceholderText("Folder containing maintenance images for this entry (optional)")
        browse_btn = QPushButton("Choose Folder…")
        browse_btn.clicked.connect(self.browse_image_folder)

        form_layout.addRow("Platform:", self.platform_combo)
        form_layout.addRow("Type:", self.maintenance_type_combo)
        form_layout.addRow("Date:", self.date_edit)
        form_layout.addRow("Performed By:", self.performed_by_edit)
        form_layout.addRow("Description:", self.description_edit)
        img_row = QHBoxLayout()
        img_row.addWidget(self.image_path_edit)
        img_row.addWidget(browse_btn)
        row_widget = QWidget()
        row_widget.setLayout(img_row)
        form_layout.addRow("Images Folder:", row_widget)

        # Save/Update + Delete buttons (Delete only visible in edit mode)
        self.maint_editing_id = None
        self.maint_save_btn = QPushButton("Add Maintenance Log")
        self.maint_save_btn.clicked.connect(self.save_maintenance_log)
        self.maint_delete_btn = QPushButton("Delete")
        self.maint_delete_btn.setVisible(False)
        self.maint_delete_btn.clicked.connect(self.delete_selected_maintenance)
        self.maint_clear_btn = QPushButton("Clear Selection")
        self.maint_clear_btn.clicked.connect(self.clear_maintenance_selection)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.maint_save_btn)
        btn_row.addWidget(self.maint_delete_btn)
        btn_row.addWidget(self.maint_clear_btn)
        form_layout.addRow(btn_row)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Platform", "Type", "Date", "Performed By", "Description", "Images"]) 
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self.on_maintenance_row_selected)

        layout.addWidget(form_widget)
        # Non-blocking status label for confirmations
        self.maint_status = QLabel("")
        self.maint_status.setStyleSheet("color: #2e7d32; font-weight: bold;")
        layout.addWidget(self.maint_status)
        layout.addWidget(QLabel("Maintenance History:"))
        layout.addWidget(self.table)

    def load_platforms(self):
        self.platform_combo.clear()
        self.platform_lookup = {}
        platforms = db_manager.get_all_platforms()
        for p in platforms:
            pid = p.get('id')
            name = p.get('name') or 'Unnamed'
            sn = p.get('serial_number') or 'N/A'
            self.platform_combo.addItem(f"{name} - SN:{sn}", pid)
            self.platform_lookup[pid] = name
        self.platform_combo.currentIndexChanged.connect(self.load_maintenance_logs)

    def browse_image_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Images Folder", "")
        if path:
            self.image_path_edit.setText(path)

    def add_maintenance_log_entry(self):
        try:
            platform_id = self.platform_combo.currentData()
            maintenance_type = self.maintenance_type_combo.currentText()
            date_str = self.date_edit.date().toString("yyyy-MM-dd")
            technician = self.performed_by_edit.text().strip()
            description = self.description_edit.text().strip()
            image_path = self.image_path_edit.text().strip() or None

            if not all([platform_id, maintenance_type, technician, description]):
                QMessageBox.warning(self, "Error", "Platform, type, performed by, and description are required.")
                return

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
            self.performed_by_edit.clear()
            self.description_edit.clear()
            self.image_path_edit.clear()
            self.date_edit.setDate(QDate.currentDate())
            self.load_maintenance_logs()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not add maintenance log: {e}")

    def load_maintenance_logs(self):
        self.table.setRowCount(0)
        platform_id = self.platform_combo.currentData()
        if not platform_id:
            return
        logs = maintenance_manager.get_logs_for_platform(platform_id=platform_id)
        for row, log in enumerate(logs):
            self.table.insertRow(row)
            log_id = getattr(log, 'id', None)
            if log_id is None:
                log_id = getattr(log, 'maintenance_id', None)
            p_name = self.platform_lookup.get(platform_id, "")
            m_type = getattr(log, 'maintenance_type', '')
            date_val = getattr(log, 'maintenance_date', None) or getattr(log, 'date', None)
            date_str = ''
            if isinstance(date_val, str):
                date_str = date_val
            elif date_val is not None:
                try:
                    date_str = date_val.strftime("%Y-%m-%d")
                except Exception:
                    date_str = str(date_val)
            tech = getattr(log, 'technician', '') or getattr(log, 'performed_by', '')
            desc = getattr(log, 'description', '')

            self.table.setItem(row, 0, QTableWidgetItem(str(log_id)))
            self.table.setItem(row, 1, QTableWidgetItem(p_name))
            self.table.setItem(row, 2, QTableWidgetItem(m_type))
            self.table.setItem(row, 3, QTableWidgetItem(date_str))
            self.table.setItem(row, 4, QTableWidgetItem(tech))
            self.table.setItem(row, 5, QTableWidgetItem(desc))

            images_path = getattr(log, 'image_path', '') or ''
            btn = QPushButton("Open")
            btn.setEnabled(bool(images_path))
            btn.setProperty('image_path', images_path)
            btn.clicked.connect(lambda _, p=images_path: self.open_images_folder(p))
            self.table.setCellWidget(row, 6, btn)

    def on_maintenance_row_selected(self):
        items = self.table.selectedItems()
        if not items:
            # Exit edit mode
            self.maint_editing_id = None
            self.maint_save_btn.setText("Add Maintenance Log")
            self.maint_delete_btn.setVisible(False)
            return
        row = items[0].row()
        log_id_item = self.table.item(row, 0)
        if not log_id_item:
            return
        try:
            self.maint_editing_id = int(log_id_item.text())
        except Exception:
            self.maint_editing_id = None
            return
        # Populate form
        self.maintenance_type_combo.setCurrentText(self.table.item(row, 2).text() if self.table.item(row, 2) else "")
        date_txt = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
        if date_txt:
            try:
                self.date_edit.setDate(QDate.fromString(date_txt, "yyyy-MM-dd"))
            except Exception:
                pass
        self.performed_by_edit.setText(self.table.item(row, 4).text() if self.table.item(row, 4) else "")
        self.description_edit.setText(self.table.item(row, 5).text() if self.table.item(row, 5) else "")
        # Image path via button property
        btn = self.table.cellWidget(row, 6)
        if isinstance(btn, QPushButton):
            path = btn.property('image_path') or ''
            self.image_path_edit.setText(path)
        # Switch to update mode
        self.maint_save_btn.setText("Update Maintenance Log")
        self.maint_delete_btn.setVisible(True)

    def show_maint_status(self, text: str):
        self.maint_status.setText(text)
        QTimer.singleShot(2500, self.maint_status.clear)

    def save_maintenance_log(self):
        was_update = bool(self.maint_editing_id)
        platform_id = self.platform_combo.currentData()
        maintenance_type = self.maintenance_type_combo.currentText()
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        technician = self.performed_by_edit.text().strip()
        description = self.description_edit.text().strip()
        image_path = self.image_path_edit.text().strip() or None
        if not all([platform_id, maintenance_type, technician, description]):
            QMessageBox.warning(self, "Error", "Platform, type, performed by, and description are required.")
            return
        # Update vs Add
        if self.maint_editing_id:
            ok = maintenance_manager.update_maintenance_log(
                self.maint_editing_id,
                maintenance_type=maintenance_type,
                description=description,
                date=date_str,
                technician=technician,
                image_path=image_path,
            )
            if not ok:
                QMessageBox.critical(self, "Error", "Failed to update maintenance log.")
                return
        else:
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
        # Reset form
        self.maint_editing_id = None
        self.maint_save_btn.setText("Add Maintenance Log")
        self.maint_delete_btn.setVisible(False)
        self.performed_by_edit.clear()
        self.description_edit.clear()
        self.image_path_edit.clear()
        self.date_edit.setDate(QDate.currentDate())
        self.load_maintenance_logs()
        self.show_maint_status("Maintenance log updated." if was_update else "Maintenance log added.")

    def delete_selected_maintenance(self):
        if not self.maint_editing_id:
            return
        if QMessageBox.question(self, "Confirm Delete", "Delete this maintenance log?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            ok = maintenance_manager.delete_maintenance_log(self.maint_editing_id)
            if not ok:
                QMessageBox.critical(self, "Error", "Could not delete maintenance log.")
                return
            self.maint_editing_id = None
            self.maint_save_btn.setText("Add Maintenance Log")
            self.maint_delete_btn.setVisible(False)
            self.load_maintenance_logs()

    def clear_maintenance_selection(self):
        try:
            self.table.clearSelection()
        except Exception:
            pass
        # Reset state and clear form for add mode
        self.maint_editing_id = None
        self.maint_save_btn.setText("Add Maintenance Log")
        self.maint_delete_btn.setVisible(False)
        self.performed_by_edit.clear()
        self.description_edit.clear()
        self.image_path_edit.clear()
        self.date_edit.setDate(QDate.currentDate())

    def open_images_folder(self, path: str):
        if not path:
            QMessageBox.information(self, "No Folder", "No images folder saved for this log.")
            return
        try:
            if not os.path.isdir(path):
                QMessageBox.warning(self, "Not Found", f"Folder does not exist:\n{path}")
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open folder: {e}")


class BatteryPanel(QWidget):
    """Embedded panel for battery inventory (formerly a dialog)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_models()
        self.load_batteries()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        self.name_edit = QLineEdit()
        self.serial_edit = QLineEdit()
        self.purchase_date_edit = QDateEdit(QDate.currentDate())
        self.purchase_date_edit.setCalendarPopup(True)
        self.platform_model_combo = QComboBox()
        self.notes_edit = QLineEdit()
        # Cycle count (shown in edit mode)
        self.cycle_spin = QSpinBox()
        self.cycle_spin.setRange(0, 100000)
        self.cycle_spin.setValue(0)

        form_layout.addRow("Battery Name:", self.name_edit)
        form_layout.addRow("Serial Number:", self.serial_edit)
        form_layout.addRow("Acquisition Date:", self.purchase_date_edit)
        form_layout.addRow("Platform Model:", self.platform_model_combo)
        form_layout.addRow("Notes:", self.notes_edit)
        # Add cycle count row but hide initially (only for edit)
        self.cycle_row_label = QLabel("Cycle Count:")
        form_layout.addRow(self.cycle_row_label, self.cycle_spin)
        self.cycle_row_label.setVisible(False)
        self.cycle_spin.setVisible(False)

        # Save/Update + Delete controls
        self.batt_editing_id = None
        self.batt_save_btn = QPushButton("Add Battery")
        self.batt_save_btn.clicked.connect(self.save_battery_entry)
        self.batt_delete_btn = QPushButton("Delete")
        self.batt_delete_btn.setVisible(False)
        self.batt_delete_btn.clicked.connect(self.delete_selected_battery)
        self.batt_clear_btn = QPushButton("Clear Selection")
        self.batt_clear_btn.clicked.connect(self.clear_battery_selection)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.batt_save_btn)
        btn_row.addWidget(self.batt_delete_btn)
        btn_row.addWidget(self.batt_clear_btn)
        form_layout.addRow(btn_row)

        self.table = QTableWidget()
        # Include Platform Model column in the table view (no Actions column)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Serial #", "Acquisition Date", "Platform Model", "Cycles"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self.on_battery_row_selected)

        layout.addWidget(form_widget)
        # Non-blocking status label for confirmations
        self.batt_status = QLabel("")
        self.batt_status.setStyleSheet("color: #2e7d32; font-weight: bold;")
        layout.addWidget(self.batt_status)
        layout.addWidget(QLabel("Batteries:"))
        layout.addWidget(self.table)

    def add_battery_entry(self):
        try:
            name = self.name_edit.text().strip()
            serial = self.serial_edit.text().strip()
            purchase_date = self.purchase_date_edit.date().toString("yyyy-MM-dd")
            platform_model = self.platform_model_combo.currentText().strip() or None
            notes = self.notes_edit.text().strip() or None
            if not name:
                QMessageBox.warning(self, "Error", "Battery name is required.")
                return
            add_battery_record(name=name, battery_sn=serial, acquisition_date=purchase_date, notes=notes, initial_cycles=0, platform_model=platform_model)
            self.name_edit.clear()
            self.serial_edit.clear()
            self.notes_edit.clear()
            self.load_batteries()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not add battery: {e}")

    def load_batteries(self):
        self.table.setRowCount(0)
        batteries = get_all_batteries()
        for row, b in enumerate(batteries):
            self.table.insertRow(row)
            bid = b.get('battery_id') or b.get('id')
            name = b.get('name') or ''
            serial = b.get('battery_sn') or ''
            acquired = b.get('acquisition_date') or ''
            platform_model = b.get('platform_model') or ''
            cycles = b.get('cycle_count')

            self.table.setItem(row, 0, QTableWidgetItem(str(bid)))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.setItem(row, 2, QTableWidgetItem(serial))
            self.table.setItem(row, 3, QTableWidgetItem(acquired))
            self.table.setItem(row, 4, QTableWidgetItem(platform_model))
            self.table.setItem(row, 5, QTableWidgetItem(str(cycles)))

    def load_models(self):
        # Populate platform_model dropdown with unique Model values from platforms table
        self.platform_model_combo.clear()
        models = []
        platforms = db_manager.get_all_platforms()
        for p in platforms:
            model = p.get('model')
            if model and model not in models:
                models.append(model)
        models.sort()
        # Allow empty selection as optional
        self.platform_model_combo.addItem("")
        for m in models:
            self.platform_model_combo.addItem(m)

    

    def on_battery_row_selected(self):
        items = self.table.selectedItems()
        if not items:
            self.batt_editing_id = None
            self.batt_save_btn.setText("Add Battery")
            self.batt_delete_btn.setVisible(False)
            # Hide cycle count in add mode
            self.cycle_row_label.setVisible(False)
            self.cycle_spin.setVisible(False)
            return
        row = items[0].row()
        bid_item = self.table.item(row, 0)
        if not bid_item:
            return
        try:
            self.batt_editing_id = int(bid_item.text())
        except Exception:
            self.batt_editing_id = None
            return
        # Populate form
        self.name_edit.setText(self.table.item(row, 1).text() if self.table.item(row, 1) else "")
        self.serial_edit.setText(self.table.item(row, 2).text() if self.table.item(row, 2) else "")
        date_txt = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
        if date_txt:
            self.purchase_date_edit.setDate(QDate.fromString(date_txt, "yyyy-MM-dd"))
        # Platform model
        pm = self.table.item(row, 4).text() if self.table.item(row, 4) else ""
        idx = self.platform_model_combo.findText(pm)
        self.platform_model_combo.setCurrentIndex(idx if idx >= 0 else 0)
        # Notes not in table; clear to avoid stale text
        self.notes_edit.clear()
        # Show and set cycle count for edit mode
        try:
            cycles_txt = self.table.item(row, 5).text() if self.table.item(row, 5) else "0"
            self.cycle_spin.setValue(int(cycles_txt) if cycles_txt.isdigit() else 0)
        except Exception:
            self.cycle_spin.setValue(0)
        self.cycle_row_label.setVisible(True)
        self.cycle_spin.setVisible(True)
        # Switch to update mode
        self.batt_save_btn.setText("Update Battery")
        self.batt_delete_btn.setVisible(True)

    def show_batt_status(self, text: str):
        self.batt_status.setText(text)
        QTimer.singleShot(2500, self.batt_status.clear)

    def save_battery_entry(self):
        was_update = bool(self.batt_editing_id)
        try:
            name = self.name_edit.text().strip()
            serial = self.serial_edit.text().strip()
            purchase_date = self.purchase_date_edit.date().toString("yyyy-MM-dd")
            platform_model = self.platform_model_combo.currentText().strip() or None
            notes = self.notes_edit.text().strip() or None
            if not name:
                QMessageBox.warning(self, "Error", "Battery name is required.")
                return
            if self.batt_editing_id:
                update_battery_record(
                    self.batt_editing_id,
                    name=name,
                    battery_sn=serial,
                    acquisition_date=purchase_date,
                    notes=notes,
                    platform_model=platform_model,
                    cycle_count=self.cycle_spin.value(),
                )
            else:
                add_battery_record(name=name, battery_sn=serial, acquisition_date=purchase_date, notes=notes, initial_cycles=0, platform_model=platform_model)
            # Reset form
            self.batt_editing_id = None
            self.batt_save_btn.setText("Add Battery")
            self.batt_delete_btn.setVisible(False)
            self.name_edit.clear()
            self.serial_edit.clear()
            self.notes_edit.clear()
            # Hide cycle count when returning to add mode
            self.cycle_row_label.setVisible(False)
            self.cycle_spin.setVisible(False)
            self.load_batteries()
            self.show_batt_status("Battery updated." if was_update else "Battery added.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save battery: {e}")

    def delete_selected_battery(self):
        if not self.batt_editing_id:
            return
        if QMessageBox.question(self, "Confirm Delete", "Delete this battery?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                delete_battery_record(self.batt_editing_id)
                self.batt_editing_id = None
                self.batt_save_btn.setText("Add Battery")
                self.batt_delete_btn.setVisible(False)
                self.load_batteries()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete battery: {e}")

    def clear_battery_selection(self):
        try:
            self.table.clearSelection()
        except Exception:
            pass
        self.batt_editing_id = None
        self.batt_save_btn.setText("Add Battery")
        self.batt_delete_btn.setVisible(False)
        # Clear form
        self.name_edit.clear()
        self.serial_edit.clear()
        self.notes_edit.clear()
        self.purchase_date_edit.setDate(QDate.currentDate())
        if self.platform_model_combo.count() > 0:
            self.platform_model_combo.setCurrentIndex(0)
        # Hide cycle count in add mode
        self.cycle_row_label.setVisible(False)
        self.cycle_spin.setVisible(False)

    def delete_platform(self, platform_id):
        """Delete a platform from the database."""
        if platform_id is None: return

        reply = QMessageBox.question(self, 'Confirm Delete', 
                                     'Are you sure you want to delete this platform?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            if not db_manager.session:
                QMessageBox.critical(self, "Error", "No database connection available.")
                return
            
            session = db_manager.session
            Platform = db_manager.models.get('platforms')
            if Platform:
                try:
                    platform_obj = session.query(Platform).get(platform_id)
                    if platform_obj:
                        session.delete(platform_obj)
                        session.commit()
                        self.load_platforms()
                        return
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self, "Database Error", f"Failed to delete platform: {e}")

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    window = FleetManagementPage()
    window.setWindowTitle("Fleet Management")
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec_())
