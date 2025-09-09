import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QStackedWidget,
    QAction, QToolBar, QMessageBox, QSizePolicy, QToolButton,
    QMenuBar, QMenu
)
from typing import Union
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon
from sqlalchemy import text

# Import database components
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import application components
from .pages.db_editor.editor_widget import DBEditorWidget
from .pages.fleet_management.view import FleetManagementPage
from .database.manager import db_manager
from .database.core import get_session_and_models
from .pages.sensor_management.view import SensorManagementView
from .logic.metar_config import show_metar_config_dialog



class MainWindow(QMainWindow):
    """
    The main window of the application, which serves as the central hub.
    It contains a stacked widget to switch between different pages (tools).
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flight Operations Management Tool")
        self.setGeometry(100, 100, 1400, 900)

        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background: #f8f9fa;
            }
            QLabel {
                color: #333;
            }
        """)

        self.setup_ui()
        self.connect_signals()
        self.update_ui_for_database() # Initial UI state

    def setup_ui(self):
        """Set up the main UI components, including pages and toolbar."""
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        self.setup_menubar()
        self.setup_pages()
        self.setup_toolbar()

    def connect_signals(self):
        """Connect signals from db_manager to UI update slots."""
        db_manager.connection_set.connect(self.update_ui_for_database)

        # Connect page change signal
        self.stacked_widget.currentChanged.connect(self.on_page_changed)

    def setup_pages(self):
        """
        Initializes all the pages (widgets) for the application
        and adds them to the stacked widget.
        """
        # --- Home Page ---
        self.home_page = QWidget()
        self.home_page.setWindowTitle("Home")
        home_layout = QVBoxLayout(self.home_page)
        home_layout.setAlignment(Qt.AlignCenter)
        title = QLabel("Welcome to the Flight Operations Manager")
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #333;")
        home_layout.addWidget(title)

        # --- Other Pages ---
        print("Initializing Fleet Management page...")
        self.fleet_management_page = FleetManagementPage(self)
        self.fleet_management_page.setWindowTitle("Fleet Management")
        
        print("Initializing Sensor Management page...")
        self.sensor_management_page = SensorManagementView(self)
        self.sensor_management_page.setWindowTitle("Sensor Management")
        
        print("Initializing DB Editor page...")
        self.db_editor_page = DBEditorWidget()
        self.db_editor_page.setWindowTitle("Database Editor")

        # Add pages to stacked widget
        self.stacked_widget.addWidget(self.home_page)
        self.stacked_widget.addWidget(self.fleet_management_page)
        self.stacked_widget.addWidget(self.sensor_management_page)
        self.stacked_widget.addWidget(self.db_editor_page)

        # Set home page as default
        self.stacked_widget.setCurrentWidget(self.home_page)

    def setup_toolbar(self):
        """
        Sets up the main application toolbar with navigation and settings.
        """
        # Create and configure the main toolbar
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setIconSize(QSize(22, 22))
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background: #f0f0f0;
                border: none;
                border-bottom: 1px solid #d0d0d0;
                spacing: 5px;
                padding: 5px 10px;
            }
            QToolButton {
                padding: 5px 10px;
                border: 1px solid transparent;
                border-radius: 4px;
                background: transparent;
            }
            QToolButton:hover {
                background: #e0e0e0;
                border: 1px solid #c0c0c0;
            }
            QToolButton:checked {
                background: #d0d0d0;
                border: 1px solid #b0b0b0;
            }
        """)
        self.addToolBar(toolbar)

        # --- Navigation Actions ---
        home_action = QAction(QIcon.fromTheme("go-home"), "Home", self)
        home_action.triggered.connect(lambda: self.stacked_widget.setCurrentWidget(self.home_page))
        toolbar.addAction(home_action)

        # Fleet Management Actions
        fleet_action = QAction(QIcon.fromTheme("system-users"), "Fleet Management", self)
        fleet_action.triggered.connect(lambda: self.stacked_widget.setCurrentWidget(self.fleet_management_page))
        toolbar.addAction(fleet_action)
        
        sensor_action = QAction(QIcon.fromTheme("sensor"), "Sensor Management", self)
        sensor_action.triggered.connect(lambda: self.stacked_widget.setCurrentWidget(self.sensor_management_page))
        toolbar.addAction(sensor_action)

        # Add Fleet Management specific actions
        self.maintenance_action = QAction("Maintenance", self)
        self.battery_action = QAction("Battery Management", self)

        # Add to toolbar with a separator
        toolbar.addSeparator()
        toolbar.addAction(self.maintenance_action)
        toolbar.addAction(self.battery_action)

        # Initially hide these actions
        self.maintenance_action.setVisible(False)
        self.battery_action.setVisible(False)

        db_editor_action = QAction(QIcon.fromTheme("accessories-text-editor"), "Database Editor", self)
        db_editor_action.triggered.connect(lambda: self.stacked_widget.setCurrentWidget(self.db_editor_page))
        toolbar.addAction(db_editor_action)

        # --- Spacer and Right-aligned items ---
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        toolbar.addWidget(spacer)

        # --- Database Status ---
        self.status_label = QLabel("No database connected")
        self.status_label.setStyleSheet("color: #666; padding: 0 10px;")
        toolbar.addWidget(self.status_label)

    def setup_menubar(self):
        """Set up the main menu bar with settings and tools."""
        menubar = self.menuBar()

        # Settings menu
        settings_menu = menubar.addMenu("Settings")

        # METAR configuration action
        metar_config_action = QAction("METAR Configuration", self)
        metar_config_action.triggered.connect(lambda: show_metar_config_dialog(self))
        settings_menu.addAction(metar_config_action)

        # Tools menu
        tools_menu = menubar.addMenu("Tools")

        # Add any other tool actions here as needed



    def connect_to_database(self, db_path: str):
        """Connect to a database using the db_manager."""
        try:
            session, models = get_session_and_models(db_path)
            db_manager.set_connection(session, models)
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to connect to {db_path}:\n{e}")

    def update_ui_for_database(self):
        """Update the UI based on database connection status."""
        if db_manager.session:
            self.status_label.setText("Database Connected")
            self.status_label.setStyleSheet("color: #008000; padding: 0 10px;")
            self.fleet_management_page.setEnabled(True)
            self.db_editor_page.setEnabled(True)
            self.sensor_management_page.setEnabled(True)
        else:
            self.status_label.setText("No database connected")
            self.status_label.setStyleSheet("color: #FF0000; padding: 0 10px;")
            self.fleet_management_page.setEnabled(False)
            self.db_editor_page.setEnabled(False)
            self.sensor_management_page.setEnabled(False)

    def on_page_changed(self, index):
        """Handle page changes to update toolbar button visibility."""
        current_page = self.stacked_widget.widget(index)
        is_fleet_page = current_page == self.fleet_management_page

        # Update visibility of fleet management specific actions
        self.maintenance_action.setVisible(is_fleet_page)
        self.battery_action.setVisible(is_fleet_page)
