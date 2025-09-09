from typing import Dict, List, Optional, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QToolBar, QAction, 
    QStatusBar, QMessageBox, QScrollArea, QFrame, QGridLayout, QTableWidgetItem
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QIcon

from app.database.manager import db_manager
from .platform_card import PlatformCard
from .platform_dialog import PlatformDialog

class FleetManagementWidget(QWidget):
    """
    The Fleet Management page that provides an overview of the fleet inventory
    and quick access to common fleet management tasks using a card-based UI.
    
    This widget now uses the DB Editor's connection and data instead of
    maintaining its own database connection.
    """
    
    database_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.platform_cards = {}  # Store platform cards by ID
        self.setup_ui()
        # Connect to database signals to automatically refresh data
        db_manager.database_added.connect(self.refresh_data)
        db_manager.database_removed.connect(self.refresh_data)
    
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
    
    def get_platform_data(self) -> List[Dict[str, Any]]:
        """
        Get platform data from the DatabaseManager.
        Returns a list of dictionaries, where each dictionary represents a platform.
        """
        return db_manager.get_all_platforms()
    
    def refresh_data(self):
        """Refresh the platform data from the DatabaseManager and update the cards."""
        try:
            # Clear existing cards
            self.clear_cards()
            
            # Get platform data from DatabaseManager
            platforms = self.get_platform_data()
            
            if not platforms:
                self.status_bar.showMessage("No platforms found or no database connection")
                return
            
            # Create a card for each platform
            for row, platform in enumerate(platforms):
                # Create a card for this platform
                card = PlatformCard(platform)
                
                # Connect signals
                card.edit_requested.connect(self.on_edit_platform)
                card.delete_requested.connect(self.on_delete_platform)
                
                # Add to layout (3 cards per row)
                row_pos = row // 3
                col_pos = row % 3
                self.cards_layout.addWidget(card, row_pos, col_pos)
                
                # Store reference to the card
                platform_id = platform.get('id')
                if platform_id is not None:
                    self.platform_cards[platform_id] = card
            
            self.status_bar.showMessage(f"Loaded {len(platforms)} platforms")
            
        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to load platforms:\n{str(e)}"
            )
    
    def clear_cards(self):
        """Remove all platform cards from the layout."""
        # Remove all widgets from the layout
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        # Clear the cards dictionary
        self.platform_cards.clear()
    
    def on_edit_platform(self, platform_data):
        """Handle edit request from a platform card."""
        platform_id = platform_data.get('id')
        if not platform_id:
            QMessageBox.warning(self, "Error", "Cannot edit platform: Missing platform ID")
            return

        connections = db_manager.get_all_connections()
        if not connections:
            QMessageBox.critical(self, "Database Error", "No database connection available.")
            return

        # For simplicity, use the first connection. 
        db_path = next(iter(connections))
        conn_info = connections[db_path]
        session = conn_info['session']
        Platform = conn_info['models'].get('platforms')

        if not Platform:
            QMessageBox.critical(self, "Database Error", "Platform model not found.")
            return

        platform_to_edit = session.query(Platform).get(platform_id)
        if not platform_to_edit:
            QMessageBox.critical(self, "Database Error", f"Platform with ID {platform_id} not found.")
            return

        # Get column names from the model to pass to the dialog
        platform_columns = [c.name for c in Platform.__table__.columns]

        dialog = PlatformDialog(platform=platform_data, columns=platform_columns, parent=self)
        if dialog.exec_() == PlatformDialog.Accepted:
            try:
                updated_data = dialog.get_platform_data()
                for key, value in updated_data.items():
                    setattr(platform_to_edit, key, value)
                
                session.commit()
                self.refresh_data() # Refresh all cards to show updated data
                self.status_bar.showMessage("Platform updated successfully")

            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Database Error", f"Failed to update platform:\n{str(e)}")
    
    def on_delete_platform(self, platform_data):
        """Handle delete request from a platform card."""
        platform_id = platform_data.get('id')
        platform_name = platform_data.get('name', 'this platform')

        if not platform_id:
            QMessageBox.warning(self, "Error", "Cannot delete platform: Missing platform ID")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete '{platform_name}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            connections = db_manager.get_all_connections()
            if not connections:
                QMessageBox.critical(self, "Database Error", "No database connection available.")
                return

            db_path = next(iter(connections))
            conn_info = connections[db_path]
            session = conn_info['session']
            Platform = conn_info['models'].get('platforms')

            if not Platform:
                QMessageBox.critical(self, "Database Error", "Platform model not found.")
                return

            try:
                platform_to_delete = session.query(Platform).get(platform_id)
                if platform_to_delete:
                    session.delete(platform_to_delete)
                    session.commit()
                    self.refresh_data() # Refresh UI
                    self.status_bar.showMessage(f"Deleted platform: {platform_name}")
                else:
                    QMessageBox.warning(self, "Not Found", f"Platform '{platform_name}' not found in database.")

            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Database Error", f"Failed to delete platform:\n{str(e)}")
    
    def add_platform(self):
        """Add a new platform."""
        connections = db_manager.get_all_connections()
        if not connections:
            QMessageBox.warning(self, "No Database", "Please connect to a database first.")
            return

        db_path = next(iter(connections))
        conn_info = connections[db_path]
        session = conn_info['session']
        Platform = conn_info['models'].get('platforms')

        if not Platform:
            QMessageBox.critical(self, "Database Error", "Platform model not found.")
            return

        platform_columns = [c.name for c in Platform.__table__.columns if c.name != 'id']

        dialog = PlatformDialog(columns=platform_columns, parent=self)
        if dialog.exec_() == PlatformDialog.Accepted:
            try:
                platform_data = dialog.get_platform_data()
                new_platform = Platform(**platform_data)
                session.add(new_platform)
                session.commit()
                self.refresh_data()
                QMessageBox.information(self, "Success", "Platform added successfully!")

            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Database Error", f"Failed to add platform:\n{str(e)}")
    
