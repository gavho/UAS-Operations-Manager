import os
import sys
import traceback
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Add the project root to Python path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Enable debug mode
debug_mode = True

def handle_exception(exc_type, exc_value, exc_traceback):
    """Handle uncaught exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"\n{'*' * 80}\nCRITICAL ERROR: {exc_type.__name__}: {exc_value}\n{'*' * 80}\n{error_msg}")
    
    if debug_mode and QApplication.instance() is not None:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Critical Error")
        msg.setText(f"A critical error occurred: {exc_type.__name__}")
        msg.setDetailedText(error_msg)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

# Set the exception hook
sys.excepthook = handle_exception

try:
    from PyQt5.QtWidgets import (QApplication, QMessageBox, QInputDialog,
                            QMainWindow, QVBoxLayout, QWidget, QFrame,
                            QTabWidget, QLabel, QStackedWidget, QPushButton, QHBoxLayout, QGridLayout, QSizePolicy, QButtonGroup, QToolButton)
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QIcon

    # Initialize Qt WebEngine properly
    try:
        from PyQt5.QtWebEngineWidgets import QWebEngineView
        # Set the required attribute for Qt WebEngine before creating QApplication
        QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    except ImportError:
        # PyQtWebEngine not available, but that's okay
        pass
    from app.pages.fleet_management.view import FleetManagementPage
    from app.pages.db_editor.view import DBEditorWidget
    from app.pages.sensor_management.view import SensorManagementView
    from app.pages.mission_tracker.view import MissionTrackerPage
    from app.database.manager import db_manager
    from app.database.core import get_session_and_models
except Exception as e:
    print(f"Failed to import required modules: {e}")
    if 'PyQt5' in str(e):
        print("\nERROR: PyQt5 is not properly installed. Please install it using:")
        print("pip install PyQt5")
    raise

if __name__ == "__main__":
    try:
        print("Starting application...")
        app = QApplication(sys.argv)

        if app:
            print("Creating main window...")
            # Create main window
            window = QMainWindow()
            window.setWindowTitle("Flight Ops Manager")
            window.setMinimumSize(1024, 768)
            
            try:
                # Create central widget and stacked layout
                print("Setting up UI...")
                central_widget = QStackedWidget()
                
                # Set the central widget to the main container
                window.setCentralWidget(central_widget)

                # Create main container and layout
                main_container = QWidget()
                main_layout = QVBoxLayout(main_container)
                main_layout.setContentsMargins(0, 0, 0, 0)
                main_layout.setSpacing(0)

                # --- Toolbar ---
                toolbar = QFrame()
                toolbar.setStyleSheet("""
                    QFrame {
                        background-color: #2c3e50;
                        padding: 8px 20px;
                        border-bottom: 1px solid #1a252f;
                    }
                """)
                
                toolbar_layout = QHBoxLayout(toolbar)
                toolbar_layout.setContentsMargins(10, 5, 10, 5)
                toolbar_layout.setSpacing(10)

                def create_toolbar_button(text):
                    button = QPushButton(text)
                    button.setCursor(Qt.PointingHandCursor)
                    button.setStyleSheet("""
                        QPushButton {
                            background-color: transparent;
                            color: white;
                            border: 1px solid #3498db;
                            border-radius: 4px;
                            padding: 8px 16px;
                            font-size: 14px;
                            font-weight: 500;
                        }
                        QPushButton:hover {
                            background-color: rgba(52, 152, 219, 0.2);
                        }
                        QPushButton:pressed {
                            background-color: rgba(41, 128, 185, 0.3);
                        }
                    """)
                    return button

                # Create toolbar buttons
                fleet_btn = create_toolbar_button("Fleet Management")
                sensor_btn = create_toolbar_button("Sensor Management")
                mission_btn = create_toolbar_button("Mission Management")
                db_editor_btn = create_toolbar_button("Database Editor")

                # Add buttons to toolbar
                toolbar_layout.addWidget(fleet_btn)
                toolbar_layout.addWidget(sensor_btn)
                toolbar_layout.addWidget(mission_btn)
                toolbar_layout.addWidget(db_editor_btn)
                toolbar_layout.addStretch()

                # --- Home Page (Content Area) ---
                home_page = QWidget()
                home_layout = QVBoxLayout(home_page)
                home_layout.setContentsMargins(30, 40, 30, 40)
                home_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

                # Welcome title
                title = QLabel("Flight Operations Manager")
                title.setAlignment(Qt.AlignCenter)
                title.setStyleSheet("""
                    QLabel {
                        font-size: 36px;
                        font-weight: bold;
                        color: #2c3e50;
                        margin-bottom: 30px;
                    }
                """)

                # Welcome message
                welcome_msg = QLabel("Welcome to your Flight Operations Management System.\n"
                                   "Select an option from the toolbar above to get started.")
                welcome_msg.setAlignment(Qt.AlignCenter)
                welcome_msg.setStyleSheet("""
                    QLabel {
                        font-size: 16px;
                        color: #555;
                        line-height: 1.5;
                        margin-bottom: 30px;
                    }
                """)
                welcome_msg.setWordWrap(True)

                # Add widgets to home layout
                home_layout.addStretch()
                home_layout.addWidget(title)
                home_layout.addWidget(welcome_msg)
                home_layout.addStretch()

                # Add toolbar and home page to main layout
                main_layout.addWidget(toolbar)
                main_layout.addWidget(home_page)

                # --- Application Pages ---
                def create_page_with_back_button(widget, page_name):
                    # If the widget is a QLabel, wrap it in a QWidget with center alignment
                    if isinstance(widget, QLabel):
                        container = QWidget()
                        layout = QVBoxLayout(container)
                        layout.addStretch()
                        layout.addWidget(widget, 0, Qt.AlignCenter)
                        layout.addStretch()
                        widget = container
                    
                    page = QWidget()
                    layout = QVBoxLayout(page)
                    layout.setContentsMargins(0,0,0,0)
                    
                    header = QFrame()
                    header.setStyleSheet("background-color: #2c3e50; color: white;")
                    header_layout = QHBoxLayout(header)
                    
                    back_btn = QPushButton("Back to Home")
                    back_btn.setStyleSheet("border: none; padding: 8px; text-align: left;")
                    back_btn.clicked.connect(lambda: central_widget.setCurrentIndex(0))
                    
                    title_label = QLabel(page_name)
                    title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
                    title_label.setAlignment(Qt.AlignCenter)

                    header_layout.addWidget(back_btn)
                    header_layout.addWidget(title_label)
                    header_layout.addStretch()

                    layout.addWidget(header)
                    layout.addWidget(widget, 1)  # Use stretch factor 1 to fill available space
                    return page

                # Set up database path and create backup
                db_path = os.path.join(project_root, 'flightlog.db')
                backup_dir = os.path.join(project_root, 'backups')
                
                # Create backup before connecting
                logger.info("Creating database backup...")
                try:
                    from app.utils.backup_utils import create_backup
                    backup_file = create_backup(db_path, backup_dir, max_backups=5)
                    if backup_file:
                        logger.info(f"Backup created: {backup_file}")
                    else:
                        logger.warning("Failed to create database backup")
                except Exception as e:
                    logger.error(f"Error during backup: {e}")
                    logger.error(traceback.format_exc())
                
                # Connect to the database and set up the session
                print(f"[DEBUG] Connecting to database: {db_path}")
                try:
                    session, models = get_session_and_models(db_path)
                    db_manager.set_connection(session, models)
                    print("[DEBUG] Successfully connected to database and set connection.")
                except Exception as e:
                    print(f"[ERROR] Failed to connect to database: {e}")
                    QMessageBox.critical(None, "Database Error", f"Failed to connect to the database: {e}")

                # Create instances of the pages
                fleet_page_content = FleetManagementPage()
                db_editor_content = DBEditorWidget()
                sensor_page_content = SensorManagementView()
                mission_page_content = MissionTrackerPage()

                # Wrap pages with the back button header
                fleet_page = create_page_with_back_button(fleet_page_content, "Fleet Management")
                db_editor_page = create_page_with_back_button(db_editor_content, "Database Editor")
                sensor_page = create_page_with_back_button(sensor_page_content, "Sensor Management")
                mission_page = create_page_with_back_button(mission_page_content, "Mission Management")

                # Add pages to the stacked widget
                central_widget.addWidget(main_container)      # Index 0 (main container with toolbar and home page)
                central_widget.addWidget(fleet_page)          # Index 1
                central_widget.addWidget(sensor_page)         # Index 2
                central_widget.addWidget(mission_page)        # Index 3
                central_widget.addWidget(db_editor_page)      # Index 4

                # Connect hub buttons to switch pages
                fleet_btn.clicked.connect(lambda: central_widget.setCurrentIndex(1))
                sensor_btn.clicked.connect(lambda: central_widget.setCurrentIndex(2))
                mission_btn.clicked.connect(lambda: central_widget.setCurrentIndex(3))
                db_editor_btn.clicked.connect(lambda: central_widget.setCurrentIndex(4))
                
                
                # Show window
                print("[DEBUG] Showing main window...")
                window.resize(1200, 800)
                window.show()
                print("[DEBUG] Main window shown")
                
                print("Entering application event loop...")
                sys.exit(app.exec_())
                
            except Exception as e:
                print(f"Error in main window setup: {e}")
                raise
                
    except Exception as e:
        print(f"Fatal error: {e}")
        if 'app' in locals() and QApplication.instance() is not None:
            QMessageBox.critical(
                None,
                "Fatal Error",
                f"The application encountered a fatal error and needs to close.\n\nError: {str(e)}"
            )
        sys.exit(1)



