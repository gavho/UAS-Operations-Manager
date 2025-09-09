import sys
from PyQt5.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QScrollArea, QFrame, QGridLayout,
                             QLineEdit, QComboBox, QSizePolicy, QButtonGroup,
                             QMenu, QToolButton, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QFont, QCursor, QIcon, QPixmap

from app.database.manager import db_manager
from ..sensor_management.sensor_card import SensorCard
from ..calibration_log.view import CalibrationLogView
from .add_system_dialog import AddSystemDialog
from .edit_system_dialog import EditSystemDialog


class SensorManagementView(QWidget):
    """Main sensor management page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._sensors_data = []  # Cache for all sensors as list of dicts
        self._status_label = None
        # Initialize all filters as inactive by default
        self._model_filters = {}
        self.model_filter_definitions = [
            ('GOBI', 'Gobi'),
            ('GMOJ', 'Mojave'),
            ('GSON', 'Sonoran'),
            ('GSAH', 'Sahara'),
            ('cAHP', 'Co-Aligned'),
            ('cAVS', 'Legacy Co-Aligned'),
            ('cVS', 'Legacy Co-Aligned')
        ]
        for model_id, _ in self.model_filter_definitions:
            self._model_filters[model_id] = False

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
        self._last_edited_chassis = None

        # Timer for debouncing search input
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)  # 300ms delay
        self.search_timer.timeout.connect(self.filter_and_sort_sensors)

        self.setup_ui()
        self.update_model_filters()

        # Connect to the new database signal
        db_manager.connection_set.connect(self.initialize_data)

        # If the connection is already set, initialize data immediately
        if db_manager.session:
            self.initialize_data()

    def initialize_data(self):
        """Initialize sensor data when the database is ready."""
        print("Initializing sensor data...")
        self.load_sensors_from_db()

    def load_sensors_from_db(self):
        """Load all sensor data from the database into the cache."""
        print("\n=== load_sensors_from_db() called ===")
        print("Calling db_manager.get_sensor_data()...")
        
        # Check if we have pending scroll restoration data
        pending_restore = getattr(self, '_pending_scroll_restore', None)
        
        # The data is now a dictionary of systems, where each system has a list of sensors.
        self._systems_data = list(db_manager.get_sensor_data().values())
        print(f"Found {len(self._systems_data)} systems with sensor data")

        if self._systems_data:
            print("Systems data cached successfully.")
            self.update_customer_filter()
            
            # If we have pending scroll restoration, handle it after filtering/sorting
            if pending_restore:
                # Clear the pending restore to prevent it from being used again
                delattr(self, '_pending_scroll_restore')
                
                # Set the last edited chassis for the filter/sort to handle
                self._last_edited_chassis = pending_restore['last_edited']
                
                # Filter and sort the sensors
                self.filter_and_sort_sensors()
                
                # After a short delay, restore the scroll position or scroll to the chassis
                QTimer.singleShot(100, lambda: self._restore_scroll_after_edit(pending_restore))
            else:
                # No pending restore, just do a normal filter/sort
                self.filter_and_sort_sensors()
        else:
            print("No systems data found.")
            self.show_no_sensors_message("No systems data available")

        print("\n=== load_sensors_from_db() completed ===\n")
        
    def _restore_scroll_after_edit(self, restore_data):
        """Restore scroll position after an edit operation.
        
        Args:
            restore_data (dict): Dictionary containing scroll position and chassis info
        """
        # If we have a specific chassis to scroll to, do that first
        if restore_data.get('chassis'):
            self.scroll_to_chassis(restore_data['chassis'])
        # Otherwise, restore the previous scroll position
        elif 'position' in restore_data:
            scroll_bar = self.scroll_area.verticalScrollBar()
            if scroll_bar.maximum() >= restore_data['position']:
                scroll_bar.setValue(restore_data['position'])
            else:
                scroll_bar.setValue(scroll_bar.maximum())

    def update_customer_filter(self):
        """Populate the customer filter with unique customer names."""
        customers = sorted(list(set(sys.get('customer', 'N/A') for sys in self._systems_data if sys.get('customer'))))
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        self.customer_combo.addItems(["All Customers"] + customers)
        self.customer_combo.blockSignals(False)

    def update_model_filters(self):
        """Update the model filters based on the available sensor data."""
        self._model_display_names = {
            'GOBI': 'Gobi',
            'GMOJ': 'Mojave',
            'GSON': 'Sonoran',
            'GSAH': 'Sahara',
            'cAHP': 'Co-Aligned',
            'cAVS': 'Legacy Co-Aligned',
            'cVS': 'Legacy Co-Aligned'
        }
        self._update_filter_menu()

    def show_no_sensors_message(self, message):
        """Display a message when no sensors are available."""
        print(f"Showing message: {message}")
        
        # Clear any existing widgets
        self.clear_all(silent=True)
        
        # Create a container for the message
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignCenter)
        
        # Create and style the message label
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #666;
                padding: 20px;
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        
        # Add the label to the container
        layout.addWidget(label)
        
        # Add the container to the main layout
        self.cards_layout.addWidget(container, 0, 0, 1, 1, Qt.AlignCenter)
        
        # Ensure the layout is updated
        self.update_grid_layout()

    def setup_ui(self):
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- Top bar for controls ---
        top_bar_layout = QHBoxLayout()
        
        # Left side: Search bar
        search_container = QWidget()
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_label = QLabel("Search")
        search_label.setStyleSheet("font-weight: bold;")
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search by chassis or customer...")
        self.search_bar.textChanged.connect(self.search_timer.start)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_bar)
        
        # Customer filter combo
        customer_container = QWidget()
        customer_layout = QVBoxLayout(customer_container)
        customer_layout.setContentsMargins(0, 0, 0, 0)
        customer_label = QLabel("Filter by Customer")
        customer_label.setStyleSheet("font-weight: bold;")
        self.customer_combo = QComboBox()
        self.customer_combo.currentTextChanged.connect(self.filter_and_sort_sensors)
        customer_layout.addWidget(customer_label)
        customer_layout.addWidget(self.customer_combo)

        # Right side: Sort combo
        sort_container = QWidget()
        sort_layout = QVBoxLayout(sort_container)
        sort_layout.setContentsMargins(0, 0, 0, 0)
        sort_label = QLabel("Sort By")
        sort_label.setStyleSheet("font-weight: bold;")
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Chassis (A-Z)", "Chassis (Z-A)",
            "Last Calibrated (Newest)", "Last Calibrated (Oldest)"
        ])
        self.sort_combo.currentTextChanged.connect(self.filter_and_sort_sensors)
        sort_layout.addWidget(sort_label)
        sort_layout.addWidget(self.sort_combo)
        
        # Calibration Log button
        self.cal_log_button = QPushButton("Calibration Log")
        self.cal_log_button.setIcon(QIcon(QPixmap(":/icons/log")))
        self.cal_log_button.clicked.connect(self.open_calibration_log)

        top_bar_layout.addWidget(search_container, 1)
        top_bar_layout.addWidget(customer_container)
        top_bar_layout.addWidget(sort_container)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.cal_log_button)
        main_layout.addLayout(top_bar_layout)
        
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
        
        main_layout.addWidget(filter_container)

        # --- Header ---
        header = QHBoxLayout()
        title = QLabel("Sensor Management")
        title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 5px 0;")
        header.addWidget(title)
        header.addStretch()

        self.add_system_button = QPushButton("Add System")
        self.add_system_button.clicked.connect(self.open_add_system_dialog)
        header.addWidget(self.add_system_button)
        main_layout.addLayout(header)

        # --- Scroll Area for Cards ---
        scroll = QScrollArea()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # Disable horizontal scrollbar
        
        # Create container widget with vertical layout
        self.cards_container = QWidget()
        self.cards_container_layout = QVBoxLayout(self.cards_container)
        self.cards_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create grid layout for cards
        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(20)
        self.cards_layout.setContentsMargins(20, 20, 20, 20)
        self.cards_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        # Add grid layout to container
        self.cards_container_layout.addLayout(self.cards_layout)
        self.cards_container_layout.addStretch(1)  # Push cards to top
        
        # Set up scroll area
        self.scroll_area.setWidget(self.cards_container)
        
        # Add scroll area to main layout with stretch factor 1 to take available space
        main_layout.addWidget(self.scroll_area, 1)


    def _on_filter_selected(self, display_name):
        """Handle selection of a filter from the dropdown."""
        # Check if this is a status filter
        if display_name in self._status_filters:
            if not self._status_filters.get(display_name, False):
                self._status_filters[display_name] = True
        else:
            # Activate all model_ids that match the selected display_name
            models_to_activate = [model_id for model_id, d_name in self._model_display_names.items() if d_name == display_name]

            for model_id in models_to_activate:
                if not self._model_filters.get(model_id, False):
                    self._model_filters[model_id] = True

        # Add a single tag for the display name
        self._add_active_filter_tag(display_name, display_name)
        self._update_filter_menu()
        self.filter_and_sort_sensors()
            
    def _on_remove_filter(self, display_name):
        """Handle removing a filter tag."""
        # Check if this is a status filter
        if display_name in self._status_filters:
            if display_name in self._status_filters:
                self._status_filters[display_name] = False
        else:
            # Deactivate all model_ids associated with this display name
            models_to_deactivate = [model_id for model_id, d_name in self._model_display_names.items() if d_name == display_name]
            for model_id in models_to_deactivate:
                if model_id in self._model_filters:
                    self._model_filters[model_id] = False

        # Remove the UI tag
        if display_name in self.active_filter_widgets:
            widget = self.active_filter_widgets.pop(display_name)
            widget.setParent(None)
            widget.deleteLater()

        self._update_filter_menu()
        self.filter_and_sort_sensors()

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
                action.triggered.connect(
                    lambda checked, sn=status_name: self._on_filter_selected(sn)
                )

        # Add model filters
        model_section_added = False
        for display_name in sorted(self._model_display_names.values()):
            # If a tag for this display name is not already active, add it to the menu
            if display_name not in self.active_filter_widgets:
                if not model_section_added:
                    self.filter_menu.addSection("Models")
                    model_section_added = True
                action = self.filter_menu.addAction(display_name)
                action.triggered.connect(
                    lambda checked, dn=display_name: self._on_filter_selected(dn)
                )

        self.filter_dropdown.setEnabled(status_section_added or model_section_added)

    def filter_and_sort_sensors(self):
        """Filters and sorts the systems data based on current criteria."""
        print("\n=== filter_and_sort_sensors() called ===")
        if not hasattr(self, '_systems_data') or not self._systems_data:
            print("No systems data to filter.")
            self.populate_cards([])
            return

        # Only store scroll position if we don't have a pending restore
        if not hasattr(self, '_pending_scroll_restore'):
            # Store the current scroll position
            scroll_position = self.scroll_area.verticalScrollBar().value()
            # Store the currently visible chassis (if any)
            visible_chassis = None
            for i in range(self.cards_layout.count()):
                item = self.cards_layout.itemAt(i)
                if item and item.widget() and hasattr(item.widget(), 'chassis'):
                    widget_rect = item.widget().geometry()
                    viewport_rect = self.scroll_area.viewport().rect()
                    if viewport_rect.intersects(widget_rect):
                        visible_chassis = item.widget().chassis
                        break
            
            # Store the current view state for later restoration if needed
            self._current_view_state = {
                'position': scroll_position,
                'visible_chassis': visible_chassis
            }

        search_text = self.search_bar.text().strip().lower()
        active_model_ids = {model_id for model_id, active in self._model_filters.items() if active}
        active_statuses = {status for status, active in self._status_filters.items() if active}
        selected_customer = self.customer_combo.currentText()

        print(f"Filtering with search: '{search_text}', active models: {active_model_ids}, active statuses: {active_statuses}, customer: {selected_customer}")

        filtered_systems = self._systems_data

        # Filter by customer
        if selected_customer != "All Customers":
            filtered_systems = [s for s in filtered_systems if s.get('customer') == selected_customer]

        # Filter by search text
        if search_text:
            filtered_systems = [
                s for s in filtered_systems if search_text in s.get('chassis', '').lower() or \
                search_text in s.get('customer', '').lower()
            ]

        # Filter by status
        if active_statuses:
            filtered_systems = [s for s in filtered_systems if s.get('status') in active_statuses]

        # Filter by model type
        if active_model_ids:
            systems_to_display = []
            for system in filtered_systems:
                chassis_sn = system.get('chassis', '').lower()
                for model_id in active_model_ids:
                    if model_id.lower() in chassis_sn:
                        systems_to_display.append(system)
                        break
        else:
            systems_to_display = filtered_systems

        print(f"Filtered to {len(systems_to_display)} systems")

        # Sort the filtered systems
        sort_option = self.sort_combo.currentText()
        reverse_order = "(Z-A)" in sort_option or "Oldest" in sort_option

        if "Chassis" in sort_option:
            systems_to_display.sort(key=lambda x: x.get('chassis', '').lower(), reverse=reverse_order)
        elif "Calibrated" in sort_option:
            systems_to_display.sort(
                key=lambda x: (x.get('last_calibrated') is None, x.get('last_calibrated') == 'N/A', x.get('last_calibrated')),
                reverse=reverse_order
            )

        # Store the last edited chassis before populating cards
        last_edited = getattr(self, '_last_edited_chassis', None)
        
        # Populate the cards with the filtered and sorted systems
        self.populate_cards(systems_to_display)
        
        # If we have a pending scroll restore, let _restore_scroll_after_edit handle it
        if hasattr(self, '_pending_scroll_restore'):
            return
            
        # Otherwise, handle normal scroll restoration
        scroll_bar = self.scroll_area.verticalScrollBar()
        
        # If we have a last edited chassis, scroll to it
        if last_edited:
            QTimer.singleShot(150, lambda: self.scroll_to_chassis(last_edited))
            self._last_edited_chassis = None
        # Otherwise, restore the previous scroll position if we have one
        elif hasattr(self, '_current_view_state'):
            view_state = self._current_view_state
            if view_state.get('visible_chassis'):
                QTimer.singleShot(150, lambda: self.scroll_to_chassis(view_state['visible_chassis']))
            elif 'position' in view_state and view_state['position'] <= scroll_bar.maximum():
                scroll_bar.setValue(view_state['position'])
            
            # Clean up the view state
            delattr(self, '_current_view_state')

    def populate_cards(self, systems_to_display):
        """Populate the grid with a list of system cards.

        Args:
            systems_to_display (list): List of system data dictionaries.
        """
        print("\n=== populate_cards() called ===")
        print(f"Number of systems to display: {len(systems_to_display)}")
        
        # Store the current scroll position and visible chassis before clearing
        scroll_position = self.scroll_area.verticalScrollBar().value()
        visible_chassis = None
        
        # Find the first visible chassis before clearing
        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget() and hasattr(item.widget(), 'chassis'):
                widget_rect = item.widget().geometry()
                viewport_rect = self.scroll_area.viewport().rect()
                if viewport_rect.intersects(widget_rect):
                    visible_chassis = item.widget().chassis
                    break
        
        # Clear existing cards
        self.clear_all(silent=True)

        if not systems_to_display:
            self.show_no_sensors_message("No matching systems found")
            return

        # Create a list to store the cards we create
        cards = []
        
        for system_data in systems_to_display:
            try:
                card = SensorCard(system_data)
                card.edit_requested.connect(self.handle_edit_system)
                card.delete_requested.connect(self.handle_delete_system)
                card.calibration_log_requested.connect(self.open_calibration_log)
                self.cards_layout.addWidget(card)
                cards.append(card)
            except Exception as e:
                print(f"Error creating card for {system_data.get('chassis', 'Unknown')}: {e}")
        
        # Update the layout to ensure all widgets are properly positioned
        self.cards_layout.update()
        
        # Restore scroll position after a short delay
        QTimer.singleShot(50, lambda: self._restore_scroll_position(scroll_position, visible_chassis, cards))

        self.update_grid_layout()
        print("=== populate_cards() completed ===\n")



    def _restore_scroll_position(self, scroll_position, visible_chassis, cards):
        """Helper method to restore scroll position after updating cards.
        
        Args:
            scroll_position (int): The previous scroll position
            visible_chassis (str): The chassis that was previously visible
            cards (list): List of SensorCard widgets that were just created
        """
        if not cards:
            return
            
        # If we have a previously visible chassis, try to scroll to it
        if visible_chassis:
            for card in cards:
                if hasattr(card, 'chassis') and card.chassis == visible_chassis:
                    self.scroll_to_chassis(visible_chassis)
                    return
        
        # If no specific chassis to scroll to, restore the scroll position
        scroll_bar = self.scroll_area.verticalScrollBar()
        if scroll_position <= scroll_bar.maximum():
            scroll_bar.setValue(scroll_position)
        else:
            scroll_bar.setValue(scroll_bar.maximum())
    
    def update_grid_layout(self):
        """Arrange cards in the grid dynamically."""
        print("\n=== update_grid_layout() called ===")
        print(f"Current card count: {self.cards_layout.count()}")
        
        if self.cards_layout.count() == 0:
            print("No cards in layout, nothing to update")
            return

        # Calculate number of columns based on container width
        card_width = 250  # Fixed width for cards
        container_width = self.width() - 40  # Account for margins
        num_cols = max(1, container_width // (card_width + self.cards_layout.spacing()))
        
        print(f"Container width: {container_width}, Card width: {card_width}")
        print(f"Calculated columns: {num_cols}")

        # Collect all widgets
        widgets = []
        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                # Set fixed width for consistent sizing
                widget.setFixedWidth(card_width)
                widgets.append(widget)
                # Only try to access chassis attribute if it exists
                chassis_info = f"{widget.chassis}" if hasattr(widget, 'chassis') else "(no chassis attribute)"
                print(f"Found widget {i}: {chassis_info}")
            else:
                print(f"Item {i} is not a widget or has no widget")

        # Clear layout before re-adding
        print("Clearing layout...")
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item and item.widget():
                widget = item.widget()
                # Only try to access chassis attribute if it exists
                chassis_info = f"{widget.chassis}" if hasattr(widget, 'chassis') else "(no chassis attribute)"
                print(f"Removing widget: {chassis_info}")
                widget.setParent(None)
            else:
                print("Removed item with no widget")

        # Add widgets back in grid
        print("Adding widgets to grid...")
        for i, widget in enumerate(widgets):
            row = i // num_cols
            col = i % num_cols
            # Only try to access chassis attribute if it exists
            chassis_info = f"{widget.chassis}" if hasattr(widget, 'chassis') else "(no chassis attribute)"
            print(f"Adding widget {i} at row {row}, col {col} - {chassis_info}")
            self.cards_layout.addWidget(widget, row, col, Qt.AlignTop | Qt.AlignLeft)
            
        
        print(f"Final layout: {self.cards_layout.rowCount()} rows x {num_cols} cols")
        
        print("=== update_grid_layout() completed ===\n")

    def resizeEvent(self, event):
        """Recalculate grid columns on window resize."""
        super().resizeEvent(event)
        self.update_grid_layout()

    def clear_all(self, db_path=None, silent=False):
        """
        Remove all sensor cards and reset the view.
        
        Args:
            db_path (str, optional): Database path (unused, kept for compatibility)
            silent (bool): If True, don't show any status messages
        """
        print("\n=== clear_all() called ===")
        
        # Remove all widgets from the layout
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item and item.widget():
                widget = item.widget()
                widget.setParent(None)
                widget.deleteLater()
        
        # Clear any existing status messages
        if hasattr(self, '_status_label') and self._status_label:
            self._status_label.setParent(None)
            self._status_label.deleteLater()
            self._status_label = None
        
        if not silent:
            print("Cleared all cards and status messages")

    def scroll_to_chassis(self, chassis_sn):
        """Scroll the view to the card of the specified chassis.
        
        Args:
            chassis_sn (str): The chassis serial number to scroll to
        """
        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget() and hasattr(item.widget(), 'chassis') and item.widget().chassis == chassis_sn:
                # Ensure the widget is visible
                self.scroll_area.ensureWidgetVisible(item.widget())
                
                # Get the widget's position in the scroll area
                widget_pos = item.widget().pos()
                viewport = self.scroll_area.viewport()
                
                # Calculate the position to scroll to (centered in the viewport)
                scroll_value = widget_pos.y() - (viewport.height() // 2) + (item.widget().height() // 2)
                
                # Apply the scroll with animation
                scroll_bar = self.scroll_area.verticalScrollBar()
                current_value = scroll_bar.value()
                
                # Use a QPropertyAnimation for smooth scrolling
                from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
                self.scroll_animation = QPropertyAnimation(scroll_bar, b"value")
                self.scroll_animation.setDuration(300)  # 300ms animation
                self.scroll_animation.setStartValue(current_value)
                self.scroll_animation.setEndValue(max(0, scroll_value))
                self.scroll_animation.setEasingCurve(QEasingCurve.OutCubic)
                self.scroll_animation.start()
                break

    def handle_edit_system(self, chassis_sn):
        """Handle the editing of a system."""
        # Store the current scroll position and visible chassis before opening the dialog
        scroll_position = self.scroll_area.verticalScrollBar().value()
        visible_chassis = None
        
        # Find the currently visible chassis in the viewport
        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget() and hasattr(item.widget(), 'chassis'):
                widget_rect = item.widget().geometry()
                viewport_rect = self.scroll_area.viewport().rect()
                if viewport_rect.intersects(widget_rect):
                    visible_chassis = item.widget().chassis
                    break
        
        system_data = db_manager.get_system_by_chassis_sn(chassis_sn)
        if not system_data:
            QMessageBox.critical(self, "Error", f"Could not find system '{chassis_sn}' in the database.")
            return

        dialog = EditSystemDialog(system_data, self)
        if dialog.exec_() == QDialog.Accepted:
            save_confirmation = QMessageBox.question(self, "Confirm Save", 
                                                     "Are you sure you want to save these changes?",
                                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if save_confirmation == QMessageBox.Yes:
                data = dialog.get_data()
                success = db_manager.update_system(
                    data['chassis_sn'],
                    data['customer'],
                    data['notes'],
                    data['sensors'],
                    status=data['status']
                )

                if success:
                    QMessageBox.information(self, "Success", f"System '{chassis_sn}' updated successfully.")
                    db_manager.systems_updated.emit()  # Notify other components of system changes
                    self._last_edited_chassis = chassis_sn

                    self._pending_scroll_restore = {
                        'position': scroll_position,
                        'chassis': visible_chassis if visible_chassis != chassis_sn else None,
                        'last_edited': chassis_sn
                    }

                    self.load_sensors_from_db()
                else:
                    # Show specific database error if available
                    details = db_manager.last_error or 'Unknown error.'
                    QMessageBox.critical(
                        self,
                        "Database Error",
                        f"Failed to update system '{chassis_sn}'.\n\nDetails: {details}"
                    )

    def handle_delete_system(self, chassis_sn):
        """Handle the deletion of a system after confirmation."""
        reply = QMessageBox.question(
            self,
            'Confirm Deletion',
            f"Are you sure you want to delete the system '{chassis_sn}' and all its sensors? This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if db_manager.delete_system(chassis_sn):
                QMessageBox.information(self, "Success", f"System '{chassis_sn}' deleted successfully.")
                db_manager.systems_updated.emit()  # Notify other components of system changes
                self.load_sensors_from_db()
            else:
                QMessageBox.critical(self, "Database Error", f"Failed to delete system '{chassis_sn}'.")

    def open_calibration_log(self, chassis_sn=None):
        """Opens the calibration log view in a dialog."""
        dialog = QDialog(self)
        layout = QVBoxLayout(dialog)

        # If chassis_sn is not a string, it means the signal came from a source
        # without a specific chassis_sn (like the main toolbar button), so show all.
        if not isinstance(chassis_sn, str):
            chassis_sn = None
            dialog.setWindowTitle("Calibration Log - All Systems")
        else:
            dialog.setWindowTitle(f"Calibration Log - {chassis_sn}")

        calibration_view = CalibrationLogView(chassis_sn=chassis_sn)
        calibration_view.data_changed.connect(self.load_sensors_from_db)
        layout.addWidget(calibration_view)
        dialog.setLayout(layout)
        dialog.resize(900, 600)
        dialog.exec_()

    def open_add_system_dialog(self):
        """Open the dialog to add a new system."""
        dialog = AddSystemDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data['chassis_sn']:
                QMessageBox.warning(self, "Input Error", "Chassis Serial Number cannot be empty.")
                return

            success = db_manager.add_new_system(
                data['chassis_sn'],
                data['customer'],
                data['sensors']
            )

            if success:
                QMessageBox.information(self, "Success", "New system added successfully.")
                db_manager.systems_updated.emit()  # Notify other components of system changes
                self.load_sensors_from_db()
            else:
                QMessageBox.critical(self, "Database Error", "Failed to add the new system to the database.")

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    # You need to connect to a database for this to work
    # Example of connecting to a database:
    # db_manager.add_database("path/to/your/database.db")
    window = SensorManagementView()
    window.setWindowTitle("Sensor Management")
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec_())
