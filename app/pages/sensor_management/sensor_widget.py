# app/tabs/sensor_management_widget.py

import sqlite3
from typing import Dict, List, Optional, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QToolBar, QAction,
    QStatusBar, QMessageBox, QScrollArea, QFrame, QLabel,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QEvent
from PyQt5.QtGui import QIcon, QFont

# Import from same directory
from .sensor_card import SensorCard
from .sensor_dialog import SensorDialog

class SensorManagementWidget(QWidget):
    """
    The Sensor Management page provides a card-based overview of the sensor 
    inventory and allows for adding, editing, and deleting sensors.
    
    This widget is designed to be driven by the data and database connection
    managed by a central DB Editor component.
    """
    
    def __init__(self, db_editor=None, parent=None):
        """
        Initializes the widget.
        
        Args:
            db_editor: A reference to the main DB Editor widget.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.db_editor = db_editor
        self.conn = None
        self.cursor = None
        self.sensor_columns = []
        self.sensor_cards = {}  # Dictionary to store sensor cards, keyed by ID
        self.card_widgets: List[SensorCard] = []
        
        self.setup_ui()
    
    def set_db_connection(self, connection: Optional[sqlite3.Connection]):
        """
        Sets the database connection for the widget to use for transactions.
        This should be called by the main application when a database is opened.
        
        Args:
            connection (sqlite3.Connection, optional): The active database connection.
        """
        self.conn = connection
        self.cursor = self.conn.cursor() if self.conn else None
        if self.conn:
            self.conn.row_factory = sqlite3.Row  # Access columns by name
            # Get sensor table columns
            try:
                self.cursor.execute("PRAGMA table_info(bsc_master)")
                self.sensor_columns = [col[1] for col in self.cursor.fetchall()]
            except sqlite3.Error:
                self.sensor_columns = [] # Handle case where table doesn't exist
    
    def setup_ui(self):
        """Initializes the UI components for the Sensor Management page."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # --- Header ---
        header_layout = QHBoxLayout()
        title = QLabel("Sensor Management")
        title.setFont(QFont("CONTHRAX", 20, QFont.Bold)) # As per PRD
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # --- Toolbar ---
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(24, 24))
        
        # Add Sensor button
        self.add_btn = QAction(QIcon.fromTheme("list-add"), "Add Sensor", self)
        self.add_btn.triggered.connect(self.add_sensor)
        self.toolbar.addAction(self.add_btn)
        
        # Refresh button
        self.refresh_btn = QAction(QIcon.fromTheme("view-refresh"), "Refresh", self)
        self.refresh_btn.triggered.connect(self.refresh_data)
        self.toolbar.addAction(self.refresh_btn)
        
        header_layout.addWidget(self.toolbar)
        self.layout.addLayout(header_layout)

        # --- Scroll Area for Cards ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        # Disable horizontal scrolling; allow vertical as needed
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Container for the grid of cards
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.cards_layout.setSpacing(15)
        self.cards_layout.setContentsMargins(20, 20, 20, 20)
        
        self.scroll_area.setWidget(self.cards_container)
        self.layout.addWidget(self.scroll_area)

        # Reflow cards on viewport resize
        self._base_margins = self.cards_layout.contentsMargins()
        self.scroll_area.viewport().installEventFilter(self)
        
        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.layout.addWidget(self.status_bar)
    
    def get_sensor_data_from_editor(self) -> List[Dict[str, Any]]:
        """
        Gets sensor data directly from the DB Editor's currently displayed table.
        This ensures data consistency across the application.
        
        Returns:
            A list of dictionaries, where each dictionary represents a sensor.
        """
        if not self.db_editor or self.db_editor.current_table_name != "bsc_master":
            return []
            
        table = self.db_editor.table_view
        sensors = []
        
        headers = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]
            
        for row in range(table.rowCount()):
            sensor = {}
            for col, header in enumerate(headers):
                item = table.item(row, col)
                sensor[header] = item.text() if item else None
            if sensor.get('id'):  # Ensure row has an ID
                sensors.append(sensor)
                
        return sensors

    def get_sensor_data_from_db(self) -> List[Dict[str, Any]]:
        """Fetch sensor rows directly from the database for speed."""
        if not self.conn:
            return []
        try:
            cur = self.conn.cursor()
            # Select a practical subset of columns; adjust as needed
            cur.execute("SELECT id, Name, Model, SN, status FROM bsc_master")
            rows = cur.fetchall()
            out = []
            for r in rows:
                # sqlite Row supports both index and key; convert to dict
                if isinstance(r, sqlite3.Row):
                    out.append({k: r[k] for k in r.keys()})
                else:
                    # Fallback if row_factory not set
                    out.append({
                        'id': r[0], 'Name': r[1], 'Model': r[2], 'SN': r[3], 'status': r[4]
                    })
            return out
        except sqlite3.Error:
            return []


    def refresh_data(self):
        """
        Refreshes the sensor cards display using data from the DB Editor.
        """
        if not self.conn:
            self.status_bar.showMessage("No database connection.")
            return

        # Prefer direct DB fetch; fall back to editor scrape if needed
        sensors = self.get_sensor_data_from_db() or self.get_sensor_data_from_editor()
        
        if not sensors:
            self.status_bar.showMessage("No sensors found in 'bsc_master' table.")
            return

        # Batch UI updates during rebuild
        self.cards_container.setUpdatesEnabled(False)
        try:
            self.clear_cards()
            self.card_widgets = []
            for sensor_data in sensors:
                card = SensorCard(sensor_data)
                card.edit_requested.connect(self.on_edit_sensor)
                card.delete_requested.connect(self.on_delete_sensor)
                self.card_widgets.append(card)

                sensor_id = sensor_data.get('id')
                if sensor_id is not None:
                    self.sensor_cards[sensor_id] = card

            # Add to layout using responsive grid
            self.update_grid_layout()
            self.status_bar.showMessage(f"Loaded {len(sensors)} sensors.")
        finally:
            self.cards_container.setUpdatesEnabled(True)
            
    def clear_cards(self):
        """Removes all sensor cards from the view."""
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self.sensor_cards.clear()
        self.card_widgets = []

    def eventFilter(self, obj, event):
        if obj is self.scroll_area.viewport() and event.type() == QEvent.Resize:
            self.update_grid_layout()
        return super().eventFilter(obj, event)

    def update_grid_layout(self):
        """Lay out cards responsively based on viewport width and center them."""
        if not self.card_widgets:
            return

        spacing = self.cards_layout.horizontalSpacing() or self.cards_layout.spacing()
        margins = self._base_margins
        left, top, right, bottom = margins.left(), margins.top(), margins.right(), margins.bottom()

        viewport_width = self.scroll_area.viewport().width()
        # Measure card width from a sample
        sample = self.card_widgets[0]
        card_width = sample.width() or sample.sizeHint().width() or 280

        available = viewport_width - (left + right)
        if available <= 0:
            num_cols = 1
        else:
            num_cols = max(1, (available + spacing) // (card_width + spacing))

        leftover = available - (num_cols * card_width + (num_cols - 1) * spacing)
        new_left = left + max(0, leftover // 2)
        new_right = right + max(0, leftover - (leftover // 2))
        self.cards_layout.setContentsMargins(new_left, top, new_right, bottom)

        # Clear current positions without deleting widgets
        while self.cards_layout.count():
            self.cards_layout.takeAt(0)

        # Add cards row by row
        row = col = 0
        for w in self.card_widgets:
            self.cards_layout.addWidget(w, row, col, Qt.AlignTop)
            col += 1
            if col >= num_cols:
                col = 0
                row += 1
    
    def add_sensor(self):
        """Opens a dialog to add a new sensor to the database."""
        if not self.conn or not self.cursor:
            QMessageBox.warning(self, "No Database", "Please connect to a database first.")
            return

        dialog = SensorDialog(columns=self.sensor_columns, parent=self)
        if dialog.exec_() == SensorDialog.Accepted:
            try:
                sensor_data = dialog.get_sensor_data()
                columns = ", ".join(sensor_data.keys())
                placeholders = ", ".join(["?"] * len(sensor_data))
                
                query = f"INSERT INTO bsc_master ({columns}) VALUES ({placeholders})"
                self.cursor.execute(query, list(sensor_data.values()))
                self.conn.commit()
                
                # Tell the DB editor to refresh its view, which will then update this widget
                if self.db_editor:
                    self.db_editor.refresh_current_table()
                
                QMessageBox.information(self, "Success", "Sensor added successfully!")
            except sqlite3.Error as e:
                self.conn.rollback()
                QMessageBox.critical(self, "Database Error", f"Failed to add sensor:\n{e}")

    def on_edit_sensor(self, sensor_data: dict):
        """Handles the edit request from a sensor card."""
        if not self.conn or not self.cursor:
            return

        dialog = SensorDialog(sensor=sensor_data, columns=self.sensor_columns, parent=self)
        if dialog.exec_() == SensorDialog.Accepted:
            try:
                updated_data = dialog.get_sensor_data()
                sensor_id = sensor_data.get('id')
                if not sensor_id:
                    QMessageBox.warning(self, "Error", "Cannot update sensor: Missing ID.")
                    return

                set_clause = ", ".join([f'"{k}" = ?' for k in updated_data.keys()])
                query = f"UPDATE bsc_master SET {set_clause} WHERE id = ?"
                params = list(updated_data.values()) + [sensor_id]
                
                self.cursor.execute(query, params)
                self.conn.commit()

                if self.db_editor:
                    self.db_editor.refresh_current_table()
                    
                self.status_bar.showMessage(f"Sensor '{updated_data.get('Name')}' updated.")
            except sqlite3.Error as e:
                self.conn.rollback()
                QMessageBox.critical(self, "Database Error", f"Failed to update sensor:\n{e}")

    def on_delete_sensor(self, sensor_data: dict):
        """Handles the delete request from a sensor card."""
        if not self.conn or not self.cursor:
            return

        sensor_id = sensor_data.get('id')
        sensor_name = sensor_data.get('Name', 'this sensor')
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete '{sensor_name}'?\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.cursor.execute("DELETE FROM bsc_master WHERE id = ?", (sensor_id,))
                self.conn.commit()
                
                if self.db_editor:
                    self.db_editor.refresh_current_table()
                
                self.status_bar.showMessage(f"Deleted sensor: {sensor_name}")
            except sqlite3.Error as e:
                self.conn.rollback()
                QMessageBox.critical(self, "Database Error", f"Failed to delete sensor:\n{e}")
