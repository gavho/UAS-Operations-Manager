import os
import sqlite3
from typing import Dict, List, Optional, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QToolBar, QAction, 
    QStatusBar, QMessageBox, QFileDialog, QScrollArea, QFrame, QGridLayout
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QFont

from .platform_card import PlatformCard
from .platform_dialog import PlatformDialog

class FleetManagementWidget(QWidget):
    """
    The Fleet Management page that provides an overview of the fleet inventory
    and quick access to common fleet management tasks.
    """
    
    database_changed = pyqtSignal()
    
    def __init__(self, db_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.platform_columns = []
        self.setup_ui()
        if db_path:
            self.connect_to_database(db_path)
    
    def setup_ui(self):
        """Initialize the UI components for the Fleet Management page."""
        # Main layout
        self.layout = QVBoxLayout(self)
        
        # Create toolbar
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(24, 24))
        
        # Add buttons
        self.add_btn = QAction(QIcon(":/icons/add.png"), "Add Platform", self)
        self.add_btn.triggered.connect(self.add_platform)
        self.toolbar.addAction(self.add_btn)
        
        self.edit_btn = QAction(QIcon(":/icons/edit.png"), "Edit", self)
        self.edit_btn.triggered.connect(self.edit_platform)
        self.toolbar.addAction(self.edit_btn)
        
        self.delete_btn = QAction(QIcon(":/icons/delete.png"), "Delete", self)
        self.delete_btn.triggered.connect(self.delete_platform)
        self.toolbar.addAction(self.delete_btn)
        
        self.refresh_btn = QAction(QIcon(":/icons/refresh.png"), "Refresh", self)
        self.refresh_btn.triggered.connect(self.refresh_data)
        self.toolbar.addAction(self.refresh_btn)
        
        self.layout.addWidget(self.toolbar)
        
        # Create scroll area for the cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Container widget for the cards
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.cards_layout.setSpacing(20)
        self.cards_layout.setContentsMargins(20, 20, 20, 20)
        
        # Set the container as the scroll area's widget
        self.scroll_area.setWidget(self.cards_container)
        
        # Add scroll area to main layout
        self.layout.addWidget(self.scroll_area)
        
        # Dictionary to store platform cards by ID
        self.platform_cards = {}
        
        # Set up styles
        self.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f5f7fa;
            }
            QWidget#cards_container {
                background-color: #f5f7fa;
            }
        """)
        
        # Set the cards container object name for styling
        self.cards_container.setObjectName("cards_container")
        
        # Status bar
        self.status_bar = QStatusBar()
        self.layout.addWidget(self.status_bar)
        
        # Set layout
        self.setLayout(self.layout)
        
    def connect_to_database(self, db_path: str) -> bool:
        """Connect to the SQLite database."""
        try:
            if self.conn:
                self.conn.close()
                
            self.conn = sqlite3.connect(db_path)
            self.conn.row_factory = sqlite3.Row  # Access columns by name
            self.cursor = self.conn.cursor()
            self.db_path = db_path
            
            # Get platform table columns
            self.cursor.execute("PRAGMA table_info(platforms)")
            self.platform_columns = [col[1] for col in self.cursor.fetchall()]
            
            self.refresh_data()
            self.database_changed.emit()
            return True
            
        except sqlite3.Error as e:
            QMessageBox.critical(
                self, "Database Error",
                f"Failed to connect to database:\n{str(e)}"
            )
            return False
    
    def refresh_data(self):
        """Refresh the platform data from the database."""
        if not self.conn:
            return
            
        try:
            # Get all platforms
            self.cursor.execute("SELECT * FROM platforms")
            platforms = self.cursor.fetchall()
            
            # Set up table
            self.table.setRowCount(len(platforms))
            
            if not platforms:
                self.table.setColumnCount(0)
                return
                
            # Set column count and headers
            columns = platforms[0].keys()
            self.table.setColumnCount(len(columns))
            self.table.setHorizontalHeaderLabels(columns)
            
            # Populate table
            for row_idx, platform in enumerate(platforms):
                for col_idx, column in enumerate(columns):
                    value = platform[column]
                    if value is None:
                        value = ""
                    item = QTableWidgetItem(str(value))
                    self.table.setItem(row_idx, col_idx, item)
            
            self.status_bar.showMessage(f"Loaded {len(platforms)} platforms")
            
        except sqlite3.Error as e:
            QMessageBox.critical(
                self, "Database Error",
                f"Failed to load platforms:\n{str(e)}"
            )
    
    def add_platform(self):
        """Add a new platform."""
        if not self.conn:
            return
            
        # Create a dialog to input platform data
        from .platform_dialog import PlatformDialog
        dialog = PlatformDialog(columns=self.platform_columns, parent=self)
        if dialog.exec_() == PlatformDialog.Accepted:
            try:
                platform_data = dialog.get_platform_data()
                columns = ", ".join(platform_data.keys())
                placeholders = ", ".join(["?"] * len(platform_data))
                
                query = f"INSERT INTO platforms ({columns}) VALUES ({placeholders})"
                self.cursor.execute(query, list(platform_data.values()))
                self.conn.commit()
                
                self.refresh_data()
                QMessageBox.information(
                    self, "Success",
                    "Platform added successfully!"
                )
                
            except sqlite3.Error as e:
                self.conn.rollback()
                QMessageBox.critical(
                    self, "Database Error",
                    f"Failed to add platform:\n{str(e)}"
                )
    
    def edit_platform(self):
        """Edit the selected platform."""
        if not self.conn:
            return
            
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a platform to edit.")
            return
            
        # Get the selected row data
        row = selected[0].row()
        platform_id = self.table.item(row, 0).text()
        
        # Get platform data
        self.cursor.execute("SELECT * FROM platforms WHERE id = ?", (platform_id,))
        platform = self.cursor.fetchone()
        
        if not platform:
            QMessageBox.warning(self, "Not Found", "Selected platform not found.")
            return
        
        # Create and show edit dialog
        from .platform_dialog import PlatformDialog
        dialog = PlatformDialog(platform=dict(platform), columns=self.platform_columns, parent=self)
        if dialog.exec_() == PlatformDialog.Accepted:
            try:
                platform_data = dialog.get_platform_data()
                set_clause = ", ".join([f"{k} = ?" for k in platform_data.keys()])
                query = f"UPDATE platforms SET {set_clause} WHERE id = ?"
                
                params = list(platform_data.values())
                params.append(platform_id)
                
                self.cursor.execute(query, params)
                self.conn.commit()
                
                self.refresh_data()
                QMessageBox.information(
                    self, "Success",
                    "Platform updated successfully!"
                )
                
            except sqlite3.Error as e:
                self.conn.rollback()
                QMessageBox.critical(
                    self, "Database Error",
                    f"Failed to update platform:\n{str(e)}"
                )
    
    def delete_platform(self):
        """Delete the selected platform."""
        if not self.conn:
            return
            
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a platform to delete.")
            return
            
        row = selected[0].row()
        platform_id = self.table.item(row, 0).text()
        platform_name = self.table.item(row, 1).text()
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete platform '{platform_name}'?\n\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.cursor.execute("DELETE FROM platforms WHERE id = ?", (platform_id,))
                self.conn.commit()
                
                self.refresh_data()
                QMessageBox.information(
                    self, "Success",
                    "Platform deleted successfully!"
                )
                
            except sqlite3.Error as e:
                self.conn.rollback()
                QMessageBox.critical(
                    self, "Database Error",
                    f"Failed to delete platform:\n{str(e)}"
                )
    
    def closeEvent(self, event):
        """Clean up database connection when closing."""
        if self.conn:
            self.conn.close()
        event.accept()
        
        # Status bar
        self.status_bar = QStatusBar()
        self.layout.addWidget(self.status_bar)
        
        # Set layout
        self.setLayout(self.layout)
    
    def connect_to_database(self, db_path: str) -> bool:
        """Connect to the SQLite database."""
        try:
            if self.conn:
                self.conn.close()
                
            self.conn = sqlite3.connect(db_path)
            self.conn.row_factory = sqlite3.Row  # Access columns by name
            self.cursor = self.conn.cursor()
            self.db_path = db_path
            
            # Get platform table columns
            self.cursor.execute("PRAGMA table_info(platforms)")
            self.platform_columns = [col[1] for col in self.cursor.fetchall()]
            
            self.refresh_data()
            self.database_changed.emit()
            return True
            
        except sqlite3.Error as e:
            QMessageBox.critical(
                self, "Database Error",
                f"Failed to connect to database:\n{str(e)}"
            )
            return False
    
    def refresh_data(self):
        """Refresh the platform data from the database."""
        if not self.conn:
            return
            
        try:
            # Get all platforms
            self.cursor.execute("SELECT * FROM platforms")
            platforms = self.cursor.fetchall()
            
            # Set up table
            self.table.setRowCount(len(platforms))
            
            if not platforms:
                self.table.setColumnCount(0)
                return
                
            # Set column count and headers
            columns = platforms[0].keys()
            self.table.setColumnCount(len(columns))
            self.table.setHorizontalHeaderLabels(columns)
            
            # Populate table
            for row_idx, platform in enumerate(platforms):
                for col_idx, column in enumerate(columns):
                    value = platform[column]
                    if value is None:
                        value = ""
                    item = QTableWidgetItem(str(value))
                    self.table.setItem(row_idx, col_idx, item)
            
            self.status_bar.showMessage(f"Loaded {len(platforms)} platforms")
            
        except sqlite3.Error as e:
            QMessageBox.critical(
                self, "Database Error",
                f"Failed to load platforms:\n{str(e)}"
            )
    
    def add_platform(self):
        """Add a new platform."""
        if not self.conn:
            return
            
        # Create a dialog to input platform data
        from .platform_dialog import PlatformDialog
        dialog = PlatformDialog(columns=self.platform_columns, parent=self)
        if dialog.exec_() == PlatformDialog.Accepted:
            try:
                platform_data = dialog.get_platform_data()
                columns = ", ".join(platform_data.keys())
                placeholders = ", ".join(["?"] * len(platform_data))
                
                query = f"INSERT INTO platforms ({columns}) VALUES ({placeholders})"
                self.cursor.execute(query, list(platform_data.values()))
                self.conn.commit()
                
                self.refresh_data()
                QMessageBox.information(
                    self, "Success",
                    "Platform added successfully!"
                )
                
            except sqlite3.Error as e:
                self.conn.rollback()
                QMessageBox.critical(
                    self, "Database Error",
                    f"Failed to add platform:\n{str(e)}"
                )
    
    def edit_platform(self):
        """Edit the selected platform."""
        if not self.conn:
            return
            
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a platform to edit.")
            return
            
        # Get the selected row data
        row = selected[0].row()
        platform_id = self.table.item(row, 0).text()
        
        # Get platform data
        self.cursor.execute("SELECT * FROM platforms WHERE id = ?", (platform_id,))
        platform = self.cursor.fetchone()
        
        if not platform:
            QMessageBox.warning(self, "Not Found", "Selected platform not found.")
            return
        
        # Create and show edit dialog
        from .platform_dialog import PlatformDialog
        dialog = PlatformDialog(platform=dict(platform), columns=self.platform_columns, parent=self)
        if dialog.exec_() == PlatformDialog.Accepted:
            try:
                platform_data = dialog.get_platform_data()
                set_clause = ", ".join([f"{k} = ?" for k in platform_data.keys()])
                query = f"UPDATE platforms SET {set_clause} WHERE id = ?"
                
                params = list(platform_data.values())
                params.append(platform_id)
                
                self.cursor.execute(query, params)
                self.conn.commit()
                
                self.refresh_data()
                QMessageBox.information(
                    self, "Success",
                    "Platform updated successfully!"
                )
                
            except sqlite3.Error as e:
                self.conn.rollback()
                QMessageBox.critical(
                    self, "Database Error",
                    f"Failed to update platform:\n{str(e)}"
                )
    
    def delete_platform(self):
        """Delete the selected platform."""
        if not self.conn:
            return
            
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a platform to delete.")
            return
            
        row = selected[0].row()
        platform_id = self.table.item(row, 0).text()
        platform_name = self.table.item(row, 1).text()
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete platform '{platform_name}'?\n\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.cursor.execute("DELETE FROM platforms WHERE id = ?", (platform_id,))
                self.conn.commit()
                
                self.refresh_data()
                QMessageBox.information(
                    self, "Success",
                    "Platform deleted successfully!"
                )
                
            except sqlite3.Error as e:
                self.conn.rollback()
                QMessageBox.critical(
                    self, "Database Error",
                    f"Failed to delete platform:\n{str(e)}"
                )
                name_item.setData(Qt.UserRole, platform['id'])
