import sys
import shutil
import datetime
import os
from PyQt5.QtWidgets import (
    QMainWindow, QMessageBox, QTableWidget, QTableWidgetItem, QPushButton, QApplication, QToolBar, QAction,
    QLineEdit, QLabel, QWidget, QSizePolicy, QDockWidget, QComboBox, QPlainTextEdit, QDateEdit,
    QCheckBox
)
from PyQt5.QtGui import QIcon, QColor, QBrush, QKeySequence, QFontDatabase, QFont, QPixmap
from PyQt5.QtCore import Qt, QSize, QDate
from PyQt5.uic import loadUi
from app.database.manager import db_manager
from datetime import datetime, date

# Temporary ID prefix for new unsaved rows
TEMP_ID_PREFIX = "NEW_"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # --- NEW: Call the backup function before anything else ---
        self._create_and_manage_backup()

        # Get the directory of the current script to create absolute paths
        base_dir = os.path.dirname(__file__)
        parent_dir = os.path.join(base_dir, '..')

        # Load the UI file using a path relative to the script's location
        ui_path = os.path.join(base_dir, "flight_log.ui")
        loadUi(ui_path, self)

        # --- UPDATED: Resize the window to a larger size to make the dock widget appear on half the screen ---
        self.resize(1600, 900)

        # --- Database Session ---
        connections = db_manager.get_all_connections()
        if connections:
            # Get the session from the first available database connection
            db_path = next(iter(connections))
            self.session = connections[db_path]['session']
            # Get the Mission model from the automapped models
            self.Mission = connections[db_path]['models'].get('missions')
            if not self.Mission:
                QMessageBox.critical(self, "Database Error", "'missions' table not found in the database.")
                self.session = None # Prevent further operations
        else:
            self.session = None
            self.Mission = None
            QMessageBox.critical(self, "Database Error", "No database connection available.")

        # --- State Flags ---
        self.updating_table = False
        self.is_undoing = False
        self.is_redoing = False

        # --- Edit Tracking ---
        self.edited_cells = {}
        self.undo_stack = []
        self.redo_stack = []
        self.current_edit_original_value = None
        self.current_selected_mission_id = None
        self.original_table_data = {}  # Added to track original data for reverting colors

        # New set to track unsaved rows by their temporary ID
        self.unsaved_rows = {}

        # --- Register Custom Fonts and Get Names ---
        conthrax_font_path = os.path.join(parent_dir, "resources", "conthrax-sb.ttf")
        roboto_font_path = os.path.join(parent_dir, "resources", "Roboto-Regular.ttf")

        conthrax_id = QFontDatabase.addApplicationFont(conthrax_font_path)
        roboto_id = QFontDatabase.addApplicationFont(roboto_font_path)

        conthrax_font_family = ""
        if conthrax_id != -1:
            conthrax_font_family = QFontDatabase.applicationFontFamilies(conthrax_id)[0]
        else:
            print("Failed to load Conthrax font. Using default font.")

        roboto_font_family = ""
        if roboto_id != -1:
            roboto_font_family = QFontDatabase.applicationFontFamilies(roboto_id)[0]
        else:
            print("Failed to load Roboto font. Using default font.")

        # --- NEW: Apply Stylesheet from a file ---
        # This is the corrected section to load the stylesheet
        qss_path = os.path.join(base_dir, "styles.qss")
        if os.path.exists(qss_path):
            try:
                with open(qss_path, "r") as f:
                    self.setStyleSheet(f.read())
            except Exception as e:
                print(f"Failed to load stylesheet: {e}")
        else:
            print(f"Warning: Stylesheet file not found at {qss_path}. Using default styles.")

        # --- Call helper function to find all widgets ---
        self._find_widgets()
        try:
            # Get the standard height from a widget that looks correct
            correct_height = self.platformInput.sizeHint().height()

            # Force the problematic widgets to use this correct, fixed height
            self.issuesHwInput.setFixedHeight(correct_height)
            self.issuesOperatorInput.setFixedHeight(correct_height)
            self.issuesSwInput.setFixedHeight(correct_height)
            self.outcomeInput.setFixedHeight(correct_height)
        except Exception as e:
            print(f"Could not apply height fix: {e}")
        # --- Connect Original UI Element Signals ---
        # The saveNewMissionButton is now redundant but kept for clarity and will be hidden
        self.saveNewMissionButton.clicked.connect(self.save_new_mission)
        self.updateMissionButton.clicked.connect(self.update_mission)
        self.missionTable.cellPressed.connect(self.cell_pressed_for_edit)
        self.missionTable.cellChanged.connect(self.cell_was_edited)
        self.missionTable.cellClicked.connect(self.load_mission_to_form)

        # --- Connect new clear button ---
        # It appears there is no 'clearFormButton' in the UI file, so this check is important.
        if hasattr(self, 'clearFormButton') and self.clearFormButton:
            self.clearFormButton.clicked.connect(self.clear_form)

        # --- Setup Toolbar and Form UI ---
        self.create_toolbar()
        self.load_missions()

        # --- Mark required fields with a red asterisk ---
        self._mark_required_fields()

        # The form is initially hidden in the new UI
        self.updateMissionButton.hide()
        self.saveNewMissionButton.show()

        # --- NEW: Set size policy for cell editor to prevent squishing ---
        self.missionTable.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _find_widgets(self):
        """Initializes and retrieves all UI widgets by their object names."""
        # Main table
        self.missionTable = self.findChild(QTableWidget, "missionTable")
        # Mission details dock
        self.dockWidget = self.findChild(QDockWidget, "dockWidget")

        # All the input fields from the mission details form
        self.mission_id_input = self.findChild(QLineEdit, "mission_id_input")
        self.dateInput = self.findChild(QDateEdit, "dateInput")
        self.platformInput = self.findChild(QLineEdit, "platformInput")
        self.chassisInput = self.findChild(QLineEdit, "chassisInput")
        self.customerInput = self.findChild(QLineEdit, "customerInput")
        self.siteInput = self.findChild(QLineEdit, "siteInput")
        self.altitudeInput = self.findChild(QLineEdit, "altitudeInput")
        self.speedInput = self.findChild(QLineEdit, "speedInput")
        self.spacingInput = self.findChild(QLineEdit, "spacingInput")
        self.skyInput = self.findChild(QComboBox, "skyInput")
        self.windInput = self.findChild(QLineEdit, "windInput")
        self.batteryInput = self.findChild(QLineEdit, "batteryInput")
        self.filesizeInput = self.findChild(QLineEdit, "filesizeInput")
        self.isTestInput = self.findChild(QCheckBox, "isTestInput")
        self.issuesHwInput = self.findChild(QLineEdit, "issuesHwInput")
        self.issuesOperatorInput = self.findChild(QLineEdit, "issuesOperatorInput")
        self.issuesSwInput = self.findChild(QLineEdit, "issuesSwInput")
        self.outcomeInput = self.findChild(QLineEdit, "outcomeInput")
        self.commentsInput = self.findChild(QPlainTextEdit, "commentsInput")
        self.rawMetarInput = self.findChild(QPlainTextEdit, "rawMetarInput")

        # Labels for required fields
        self.labelMissionID = self.findChild(QLabel, "labelMissionID")
        self.labelDate = self.findChild(QLabel, "labelDate")
        self.labelPlatform = self.findChild(QLabel, "labelPlatform")
        self.labelSite = self.findChild(QLabel, "labelSite")
        self.labelBattery = self.findChild(QLabel, "labelBattery")

        # Buttons
        self.updateMissionButton = self.findChild(QPushButton, "updateMissionButton")
        self.saveNewMissionButton = self.findChild(QPushButton, "saveNewMissionButton")
        # This will be None if not in the UI file, which is handled in __init__
        self.clearFormButton = self.findChild(QPushButton, "clearFormButton")

    def _create_and_manage_backup(self):
        """
        Creates a timestamped backup of the database and manages old backups,
        keeping only the 3 most recent.
        """
        # Ensure the database path is absolute
        db_path = os.path.join(os.path.dirname(__file__), "test_flightlog.db")
        backup_dir = os.path.join(os.path.dirname(__file__), "backups")
        max_backups = 3

        # Check if the main database file exists
        if not os.path.exists(db_path):
            print(f"Error: Database file not found at {db_path}. Skipping backup.")
            return

        # Create the backups directory if it doesn't exist
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            print(f"Created backup directory: {backup_dir}")

        # Create a new backup file with a timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"test_flightlog_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)

        try:
            shutil.copy2(db_path, backup_path)
            print(f"Database backed up successfully to: {backup_path}")
        except Exception as e:
            print(f"An error occurred during backup: {e}")
            return

        # Get all backup files
        backups = [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if
                   f.startswith("test_flightlog_backup_")]

        # Sort backups by modification time (oldest first)
        backups.sort(key=os.path.getmtime)

        # Remove oldest backups if there are more than the max limit
        if len(backups) > max_backups:
            to_delete = backups[:len(backups) - max_backups]
            for file in to_delete:
                try:
                    os.remove(file)
                    print(f"Deleted old backup: {file}")
                except Exception as e:
                    print(f"Could not delete old backup file {file}: {e}")

    def create_toolbar(self):
        """Creates and configures the main toolbar with actions and shortcuts."""
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        base_dir = os.path.dirname(__file__)
        parent_dir = os.path.join(base_dir, '..')
        logo_path = os.path.join(parent_dir, "resources", "GRYFN WHITE.png")

        # --- Add the GRYFN Logo to the Toolbar ---
        logo_label = QLabel()
        if os.path.exists(logo_path):
            logo_pixmap = QPixmap(logo_path)
            scaled_pixmap = logo_pixmap.scaled(QSize(100, 32), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setToolTip("GRYFN Logo")
        else:
            print(f"Logo file not found: '{logo_path}'")
            logo_label.setText("GRYFN")
        toolbar.addWidget(logo_label)

        # --- Refresh Action ---
        icons_dir = os.path.join(base_dir, "icons")
        self.refresh_action = QAction(QIcon(os.path.join(icons_dir, "refresh-cw.svg")), "Refresh", self)
        self.refresh_action.setStatusTip("Reload all missions from the database")
        self.refresh_action.setShortcut(QKeySequence("Ctrl+R"))
        self.refresh_action.triggered.connect(self.load_missions)
        toolbar.addAction(self.refresh_action)

        # --- Save Edits Action ---
        self.save_action = QAction(QIcon(os.path.join(icons_dir, "save.svg")), "Save Edits", self)
        self.save_action.setStatusTip("Save all pending changes to the database")
        self.save_action.setShortcut(QKeySequence("Ctrl+S"))
        self.save_action.triggered.connect(self.save_edits)
        toolbar.addAction(self.save_action)

        # --- Delete Row Action ---
        self.delete_action = QAction(QIcon(os.path.join(icons_dir, "trash-2.svg")), "Delete Selected Row", self)
        self.delete_action.setStatusTip("Delete the currently selected mission")
        self.delete_action.setShortcut(QKeySequence("Del"))
        self.delete_action.triggered.connect(self.delete_selected)
        toolbar.addAction(self.delete_action)

        # --- Create New Row Action ---
        self.create_row_action = QAction(QIcon(os.path.join(icons_dir, "plus.svg")), "Create New Row", self)
        self.create_row_action.setStatusTip("Creates a new empty row in the table")
        self.create_row_action.setShortcut(QKeySequence("Ctrl+N"))
        self.create_row_action.triggered.connect(self.create_new_empty_row)
        toolbar.addAction(self.create_row_action)

        # --- Undo Action ---
        self.undo_action = QAction(QIcon(os.path.join(icons_dir, "undo.svg")), "Undo", self)
        self.undo_action.setStatusTip("Undo the last cell edit")
        self.undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        self.undo_action.triggered.connect(self.undo_last_edit)
        toolbar.addAction(self.undo_action)

        # --- Redo Action ---
        self.redo_action = QAction(QIcon(os.path.join(icons_dir, "redo.svg")), "Redo", self)
        self.redo_action.setStatusTip("Re-do the last undone cell edit")
        self.redo_action.setShortcut(QKeySequence("Ctrl+Y"))
        self.redo_action.triggered.connect(self.redo_last_edit)
        toolbar.addAction(self.redo_action)

        # --- Copy, Cut, Paste Actions ---
        self.copy_action = QAction(QIcon(os.path.join(icons_dir, "copy.svg")), "Copy", self)
        self.copy_action.setShortcut(QKeySequence.Copy)
        toolbar.addAction(self.copy_action)

        self.cut_action = QAction(QIcon(os.path.join(icons_dir, "scissors.svg")), "Cut", self)
        self.cut_action.setShortcut(QKeySequence.Cut)
        toolbar.addAction(self.cut_action)

        self.paste_action = QAction(QIcon(os.path.join(icons_dir, "clipboard.svg")), "Paste", self)
        self.paste_action.setShortcut(QKeySequence.Paste)
        toolbar.addAction(self.paste_action)

        # Use a spacer widget to push the next action to the far right.
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        # --- Toggle Mission Editor Dock Widget ---
        self.toggle_mission_editor_action = self.dockWidget.toggleViewAction()
        self.toggle_mission_editor_action.setText("MISSION EDITOR")
        self.toggle_mission_editor_action.setStatusTip("Show/Hide the Mission Editor form")
        self.toggle_mission_editor_action.setIcon(QIcon(os.path.join(icons_dir, "edit.svg")))
        toolbar.addAction(self.toggle_mission_editor_action)

    def get_text(self, widget):
        """
        Helper method to get text from different types of input widgets.
        """
        if isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, QComboBox):
            return widget.currentText()
        elif isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        elif isinstance(widget, QDateEdit):
            return widget.date().toPyDate()
        elif isinstance(widget, QCheckBox):
            return widget.isChecked()
        return ""

    def load_missions(self):
        """Loads all missions from the database and populates the table."""
        # This prevents the cellChanged signal from firing during population
        self.updating_table = True
        self.edited_cells.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.unsaved_rows.clear()
        self.updateMissionButton.hide()
        self.saveNewMissionButton.show()
        self.original_table_data.clear()

        self.missionTable.setRowCount(0)
        headers = [
            "ID", "Mission ID", "Date", "Platform", "Chassis", "Customer", "Site",
            "Altitude (m)", "Speed (m/s)", "Spacing (m)", "Sky", "Wind (kts)", "Battery", "Filesize (GB)",
            "Test?", "HW Issues", "Operator Issues", "SW Issues", "Outcome", "Comments", "Raw METAR"
        ]
        self.missionTable.setColumnCount(len(headers))
        self.missionTable.setHorizontalHeaderLabels(headers)
        if not self.session:
            return
        if not self.session or not self.Mission:
            return
        missions = self.session.query(self.Mission).all()
        for row_idx, m in enumerate(missions):
            self.missionTable.insertRow(row_idx)
            date_value = m.date.strftime('%Y-%m-%d') if m.date else ""
            values = [
                m.id, m.mission_id, date_value, m.platform, m.chassis, m.customer, m.site,
                m.altitude_m, m.speed_m_s, m.spacing_m, m.sky_conditions, m.wind_knots, m.battery,
                m.filesize_gb, "Yes" if m.is_test else "No", m.issues_hw, m.issues_operator,
                m.issues_sw, m.outcome, m.comments, m.raw_metar
            ]
            for col_idx, val in enumerate(values):
                item = QTableWidgetItem(str(val or ""))
                self.missionTable.setItem(row_idx, col_idx, item)

            # Store original values for edit tracking
            self.original_table_data[m.id] = {header: str(values[col_idx] or "") for col_idx, header in
                                              enumerate(headers)}

            self.missionTable.setVerticalHeaderItem(row_idx, QTableWidgetItem(str(row_idx + 1)))

        self.missionTable.resizeColumnsToContents()
        self.updating_table = False

    def load_mission_to_form(self, row, column):
        """Loads the selected mission's details into the form for editing."""
        id_item = self.missionTable.item(row, 0)
        if not id_item or not id_item.text():
            self.clear_form()
            return

        db_id_text = id_item.text().strip(' *')
        is_new_row = db_id_text.startswith(TEMP_ID_PREFIX)

        headers = [self.missionTable.horizontalHeaderItem(c).text() for c in range(self.missionTable.columnCount())]

        # This handles both existing missions and new rows
        if not is_new_row:
            mission_db_id = int(db_id_text)
            if not self.session:
                return
            if not self.session or not self.Mission:
                return
            mission = self.session.query(self.Mission).filter_by(id=mission_db_id).first()
            if not mission:
                QMessageBox.warning(self, "Load Error", f"Mission with ID {mission_db_id} not found in the database.")
                self.clear_form()
                return

            self.current_selected_mission_id = mission_db_id

            if mission.date:
                self.dateInput.setDate(QDate(mission.date))
            else:
                self.dateInput.setDate(QDate.currentDate())

            self.mission_id_input.setText(str(mission.mission_id or ''))
            self.platformInput.setText(str(mission.platform or ''))
            self.chassisInput.setText(str(mission.chassis or ''))
            self.customerInput.setText(str(mission.customer or ''))
            self.siteInput.setText(str(mission.site or ''))
            self.altitudeInput.setText(str(mission.altitude_m or ''))
            self.speedInput.setText(str(mission.speed_m_s or ''))
            self.spacingInput.setText(str(mission.spacing_m or ''))
            self.windInput.setText(str(mission.wind_knots or ''))
            self.batteryInput.setText(str(mission.battery or ''))
            self.filesizeInput.setText(str(mission.filesize_gb or ''))
            sky_text = mission.sky_conditions or ""
            index = self.skyInput.findText(sky_text, Qt.MatchFixedString)
            if index >= 0:
                self.skyInput.setCurrentIndex(index)
            else:
                self.skyInput.setCurrentIndex(0)
            self.isTestInput.setChecked(mission.is_test or False)
            self.issuesHwInput.setText(str(mission.issues_hw or ''))
            self.issuesOperatorInput.setText(str(mission.issues_operator or ''))
            self.issuesSwInput.setText(str(mission.issues_sw or ''))
            self.outcomeInput.setText(str(mission.outcome or ''))
            self.commentsInput.setPlainText(str(mission.comments or ''))
            self.rawMetarInput.setPlainText(str(mission.raw_metar or ''))
            self.updateMissionButton.show()
            self.saveNewMissionButton.hide()

        else:  # This block handles the new rows with temporary IDs
            self.current_selected_mission_id = db_id_text
            self.updateMissionButton.show()
            self.saveNewMissionButton.hide()

            self.mission_id_input.setText(self.missionTable.item(row, headers.index("Mission ID")).text() or '')
            date_str = self.missionTable.item(row, headers.index("Date")).text() or ''
            if date_str:
                try:
                    self.dateInput.setDate(QDate.fromString(date_str, 'yyyy-MM-dd'))
                except ValueError:
                    self.dateInput.setDate(QDate.currentDate())
            self.platformInput.setText(self.missionTable.item(row, headers.index("Platform")).text() or '')
            self.chassisInput.setText(self.missionTable.item(row, headers.index("Chassis")).text() or '')
            self.customerInput.setText(self.missionTable.item(row, headers.index("Customer")).text() or '')
            self.siteInput.setText(self.missionTable.item(row, headers.index("Site")).text() or '')
            self.altitudeInput.setText(self.missionTable.item(row, headers.index("Altitude (m)")).text() or '')
            self.speedInput.setText(self.missionTable.item(row, headers.index("Speed (m/s)")).text() or '')
            self.spacingInput.setText(self.missionTable.item(row, headers.index("Spacing (m)")).text() or '')
            sky_text = self.missionTable.item(row, headers.index("Sky")).text() or ""
            index = self.skyInput.findText(sky_text, Qt.MatchFixedString)
            if index >= 0:
                self.skyInput.setCurrentIndex(index)
            else:
                self.skyInput.setCurrentIndex(0)
            self.windInput.setText(self.missionTable.item(row, headers.index("Wind (kts)")).text() or '')
            self.batteryInput.setText(self.missionTable.item(row, headers.index("Battery")).text() or '')
            self.filesizeInput.setText(self.missionTable.item(row, headers.index("Filesize (GB)")).text() or '')
            test_val = self.missionTable.item(row, headers.index("Test?")).text() or ''
            self.isTestInput.setChecked(test_val.lower() == 'yes')
            self.issuesHwInput.setText(self.missionTable.item(row, headers.index("HW Issues")).text() or '')
            self.issuesOperatorInput.setText(
                self.missionTable.item(row, headers.index("Operator Issues")).text() or '')
            self.issuesSwInput.setText(self.missionTable.item(row, headers.index("SW Issues")).text() or '')
            self.outcomeInput.setText(self.missionTable.item(row, headers.index("Outcome")).text() or '')
            self.commentsInput.setPlainText(self.missionTable.item(row, headers.index("Comments")).text() or '')
            self.rawMetarInput.setPlainText(self.missionTable.item(row, headers.index("Raw METAR")).text() or '')

    def update_mission(self):
        """
        Updates an existing mission or saves a new one to the database from the form data.
        This function now handles both cases.
        """
        if not self.current_selected_mission_id:
            QMessageBox.warning(self, "No Mission Selected", "Please select a mission from the table to update.")
            return

        is_new_row = str(self.current_selected_mission_id).startswith(TEMP_ID_PREFIX)

        try:
            # Prepare data from form
            mission_data = {
                "mission_id": self.get_text(self.mission_id_input) or None,
                "date": self.dateInput.date().toPyDate(),
                "platform": self.get_text(self.platformInput) or None,
                "chassis": self.get_text(self.chassisInput) or None,
                "customer": self.get_text(self.customerInput) or None,
                "site": self.get_text(self.siteInput) or None,
                "altitude_m": float(self.get_text(self.altitudeInput)) if self.get_text(self.altitudeInput) else None,
                "speed_m_s": float(self.get_text(self.speedInput)) if self.get_text(self.speedInput) else None,
                "spacing_m": float(self.get_text(self.spacingInput)) if self.get_text(self.spacingInput) else None,
                "sky_conditions": self.skyInput.currentText() or None,
                "wind_knots": float(self.get_text(self.windInput)) if self.get_text(self.windInput) else None,
                "battery": self.get_text(self.batteryInput) or None,
                "filesize_gb": float(self.get_text(self.filesizeInput)) if self.get_text(self.filesizeInput) else None,
                "is_test": self.isTestInput.isChecked(),
                "issues_hw": self.get_text(self.issuesHwInput) or None,
                "issues_operator": self.get_text(self.issuesOperatorInput) or None,
                "issues_sw": self.get_text(self.issuesSwInput) or None,
                "outcome": self.get_text(self.outcomeInput) or None,
                "comments": self.get_text(self.commentsInput) or None,
                "raw_metar": self.get_text(self.rawMetarInput) or None
            }

            if not self.session:
                return

            if is_new_row:
                new_mission = self.Mission(**mission_data)
                self.session.add(new_mission)
                self.session.commit()
                QMessageBox.information(self, "Success", "New mission saved successfully!")
            else:
                mission = self.session.query(self.Mission).filter_by(id=self.current_selected_mission_id).first()
                if mission:
                    for key, value in mission_data.items():
                        setattr(mission, key, value)
                    self.session.commit()
                    QMessageBox.information(self, "Success", f"Mission ID {mission.mission_id} updated successfully!")

            self.clear_form()
            self.load_missions()

        except ValueError as e:
            if self.session:
                self.session.rollback()
            QMessageBox.critical(self, "Input Error", f"Failed to save/update mission due to invalid input data:\n{e}")
        except Exception as e:
            if self.session:
                self.session.rollback()
            QMessageBox.critical(self, "Error", f"An unexpected error occurred:\n{e}")

    def save_new_mission(self):
        """Saves a new mission to the database from the form data."""
        # This function is now redundant as 'update_mission' handles both cases,
        # but it remains connected to the button for backward compatibility.
        # It's better to hide this button in the UI for a streamlined experience.
        self.update_mission()

    def create_new_empty_row(self):
        """Creates a new editable row in the table for a new mission."""
        row_count = self.missionTable.rowCount()
        self.missionTable.insertRow(row_count)
        self.missionTable.scrollToBottom()

        # Set a temporary ID for the new row and other default values
        temp_id = f"{TEMP_ID_PREFIX}{row_count}"
        headers = [
            "ID", "Mission ID", "Date", "Platform", "Chassis", "Customer", "Site",
            "Altitude (m)", "Speed (m/s)", "Spacing (m)", "Sky", "Wind (kts)", "Battery", "Filesize (GB)",
            "Test?", "HW Issues", "Operator Issues", "SW Issues", "Outcome", "Comments", "Raw METAR"
        ]

        default_values = {
            "ID": temp_id,
            "Date": datetime.now().strftime('%Y-%m-%d'),
            "Test?": "No"
        }

        for col_num, header in enumerate(headers):
            value = default_values.get(header, "")
            item = QTableWidgetItem(str(value))
            self.missionTable.setItem(row_count, col_num, item)

        # Add to unsaved rows tracker
        self.unsaved_rows[temp_id] = True
        QMessageBox.information(self, "New Row",
                                "A new row has been added. Please fill in the details and click 'Save Edits' (or Ctrl+S) to save.")

    def delete_selected(self):
        """Deletes the selected mission from the table and database."""
        selected_rows = set(index.row() for index in self.missionTable.selectionModel().selectedRows())
        if not selected_rows:
            return

        reply = QMessageBox.question(self, "Confirm Deletion",
                                     "Are you sure you want to delete the selected mission(s)? This action cannot be undone.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                ids_to_delete = []
                for row_idx in sorted(selected_rows, reverse=True):
                    db_id_item = self.missionTable.item(row_idx, 0)
                    if db_id_item:
                        db_id_text = db_id_item.text().strip(' *')
                        if db_id_text.startswith(TEMP_ID_PREFIX):
                            # It's an unsaved row, just remove it from the table and tracking list
                            self.missionTable.removeRow(row_idx)
                            self.unsaved_rows.pop(db_id_text, None)
                        else:
                            # It's a saved mission, add to deletion list and remove from tracking lists
                            db_id = int(db_id_text)
                            ids_to_delete.append(db_id)
                            # Remove any edited cell tracking for this row
                            keys_to_delete = [key for key, val in self.edited_cells.items() if key[0] == row_idx]
                            for key in keys_to_delete:
                                self.edited_cells.pop(key, None)

                if not self.session:
                    return
                for db_id in ids_to_delete:
                    mission = self.session.query(self.Mission).filter_by(id=db_id).first()
                    if mission:
                        self.session.delete(mission)

                self.session.commit()
                QMessageBox.information(self, "Success", "Selected mission(s) deleted successfully.")
                self.load_missions()
            except Exception as e:
                if self.session:
                    self.session.rollback()
                QMessageBox.critical(self, "Error", f"An error occurred during deletion: {e}")

    def cell_pressed_for_edit(self, row, column):
        """
        Records the original value of a cell before an edit starts.
        """
        if not self.updating_table:
            item = self.missionTable.item(row, column)
            if item:
                self.current_edit_original_value = item.text()

    def cell_was_edited(self, row, column):
        """
        Records a cell edit for potential saving and undo, and adds visual indicators.
        """
        if self.updating_table or self.is_undoing or self.is_redoing:
            return

        current_item = self.missionTable.item(row, column)
        if not current_item:
            return

        db_id_item = self.missionTable.item(row, 0)
        if not db_id_item:
            print("Error: Database ID not found for the edited row.")
            return

        db_id = db_id_item.text()
        column_name = self.missionTable.horizontalHeaderItem(column).text()
        new_value = current_item.text()

        is_temp_id = db_id.startswith(TEMP_ID_PREFIX)

        # Determine the original value to check for a revert
        original_value_for_revert = ""
        if not is_temp_id:
            try:
                original_value_for_revert = self.original_table_data.get(int(db_id.strip(' *')), {}).get(column_name,
                                                                                                         "")
            except (ValueError, TypeError):
                original_value_for_revert = self.current_edit_original_value
        else:
            original_value_for_revert = self.current_edit_original_value or ""

        # If the value is the same as the original, clear the highlight and the asterisk if no other edits exist on the row.
        if new_value == original_value_for_revert:
            current_item.setData(Qt.BackgroundRole, QColor("#ebcb8b"))

            self.edited_cells.pop((row, column), None)

            # Check if this row has any other edited cells before removing the asterisk
            edited_in_row = any(key[0] == row for key in self.edited_cells)
            if not edited_in_row and not is_temp_id:
                db_id_item.setText(db_id.replace(" *", ""))
            return

        # If the value is different, apply the visual indicators and record the change.
        edit_record = {
            "db_id": db_id,
            "column_name": column_name,
            "row": row,
            "column": column,
            "old_value": self.current_edit_original_value,
            "new_value": new_value
        }
        self.undo_stack.append(edit_record)
        self.redo_stack.clear()

        self.edited_cells[(row, column)] = new_value
        current_item.setData(Qt.BackgroundRole, (QColor("#ebcb8b")))
        self.current_edit_original_value = None

        # Add asterisk to ID if it's not already there
        if not db_id.endswith(" *") and not is_temp_id:
            db_id_item.setText(db_id + " *")

        if is_temp_id:
            self.unsaved_rows[db_id] = True

    def save_edits(self):
        """Saves all edited cells and new rows to the database."""
        if not self.edited_cells and not self.unsaved_rows:
            QMessageBox.information(self, "No Changes", "No changes to save.")
            return

        reply = QMessageBox.question(self, "Confirm Save",
                                     f"Are you sure you want to save {len(self.edited_cells) + len(self.unsaved_rows)} changes?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        try:
            # Process new rows first and get the new permanent IDs
            temp_id_to_db_id = {}
            for temp_id in list(self.unsaved_rows.keys()):
                row_idx = -1
                for r in range(self.missionTable.rowCount()):
                    item = self.missionTable.item(r, 0)
                    if item and item.text() == temp_id:
                        row_idx = r
                        break

                if row_idx != -1:
                    headers = [self.missionTable.horizontalHeaderItem(c).text() for c in
                               range(self.missionTable.columnCount())]
                    mission_dict = {
                        "mission_id": self.missionTable.item(row_idx, headers.index(
                            "Mission ID")).text() if self.missionTable.item(row_idx,
                                                                            headers.index("Mission ID")) else None,
                        "date": datetime.strptime(self.missionTable.item(row_idx, headers.index("Date")).text(),
                                                  '%Y-%m-%d').date() if self.missionTable.item(row_idx, headers.index(
                            "Date")) and self.missionTable.item(row_idx, headers.index("Date")).text() else None,
                        "platform": self.missionTable.item(row_idx,
                                                           headers.index("Platform")).text() if self.missionTable.item(
                            row_idx, headers.index("Platform")) else None,
                        "chassis": self.missionTable.item(row_idx,
                                                          headers.index("Chassis")).text() if self.missionTable.item(
                            row_idx, headers.index("Chassis")) else None,
                        "customer": self.missionTable.item(row_idx,
                                                           headers.index("Customer")).text() if self.missionTable.item(
                            row_idx, headers.index("Customer")) else None,
                        "site": self.missionTable.item(row_idx, headers.index("Site")).text() if self.missionTable.item(
                            row_idx, headers.index("Site")) else None,
                        "altitude_m": float(self.missionTable.item(row_idx, headers.index(
                            "Altitude (m)")).text()) if self.missionTable.item(row_idx, headers.index(
                            "Altitude (m)")) and self.missionTable.item(row_idx,
                                                                        headers.index("Altitude (m)")).text() else None,
                        "speed_m_s": float(self.missionTable.item(row_idx, headers.index(
                            "Speed (m/s)")).text()) if self.missionTable.item(row_idx, headers.index(
                            "Speed (m/s)")) and self.missionTable.item(row_idx,
                                                                       headers.index("Speed (m/s)")).text() else None,
                        "spacing_m": float(self.missionTable.item(row_idx, headers.index(
                            "Spacing (m)")).text()) if self.missionTable.item(row_idx, headers.index(
                            "Spacing (m)")) and self.missionTable.item(row_idx,
                                                                       headers.index("Spacing (m)")).text() else None,
                        "sky_conditions": self.missionTable.item(row_idx,
                                                                 headers.index("Sky")).text() if self.missionTable.item(
                            row_idx, headers.index("Sky")) else None,
                        "wind_knots": float(self.missionTable.item(row_idx, headers.index(
                            "Wind (kts)")).text()) if self.missionTable.item(row_idx, headers.index(
                            "Wind (kts)")) and self.missionTable.item(row_idx,
                                                                      headers.index("Wind (kts)")).text() else None,
                        "battery": self.missionTable.item(row_idx,
                                                          headers.index("Battery")).text() if self.missionTable.item(
                            row_idx, headers.index("Battery")) else None,
                        "filesize_gb": float(self.missionTable.item(row_idx, headers.index(
                            "Filesize (GB)")).text()) if self.missionTable.item(row_idx, headers.index(
                            "Filesize (GB)")) and self.missionTable.item(row_idx, headers.index(
                            "Filesize (GB)")).text() else None,
                        "is_test": self.missionTable.item(row_idx, headers.index(
                            "Test?")).text().lower() == 'yes' if self.missionTable.item(row_idx, headers.index(
                            "Test?")) else False,
                        "issues_hw": self.missionTable.item(row_idx, headers.index(
                            "HW Issues")).text() if self.missionTable.item(row_idx,
                                                                           headers.index("HW Issues")) else None,
                        "issues_operator": self.missionTable.item(row_idx, headers.index(
                            "Operator Issues")).text() if self.missionTable.item(row_idx, headers.index(
                            "Operator Issues")) else None,
                        "issues_sw": self.missionTable.item(row_idx, headers.index(
                            "SW Issues")).text() if self.missionTable.item(row_idx,
                                                                           headers.index("SW Issues")) else None,
                        "outcome": self.missionTable.item(row_idx,
                                                          headers.index("Outcome")).text() if self.missionTable.item(
                            row_idx, headers.index("Outcome")) else None,
                        "comments": self.missionTable.item(row_idx,
                                                           headers.index("Comments")).text() if self.missionTable.item(
                            row_idx, headers.index("Comments")) else None,
                        "raw_metar": self.missionTable.item(row_idx, headers.index(
                            "Raw METAR")).text() if self.missionTable.item(row_idx,
                                                                           headers.index("Raw METAR")) else None
                    }
                    new_mission = Mission(**mission_dict)
                    self.session.add(new_mission)
                    self.session.flush()  # Commit the new mission to get a database ID
                    temp_id_to_db_id[temp_id] = new_mission.id

            # Now process existing edited cells
            for (row, column), new_value in self.edited_cells.items():
                db_id_item = self.missionTable.item(row, 0)
                if not db_id_item: continue

                db_id = db_id_item.text().strip(' *')

                # Check if this edit belongs to a newly created row
                if db_id.startswith(TEMP_ID_PREFIX):
                    actual_db_id = temp_id_to_db_id.get(db_id)
                    if not actual_db_id: continue
                else:
                    actual_db_id = int(db_id)

                column_name = self.missionTable.horizontalHeaderItem(column).text()
                mission = self.session.query(Mission).filter_by(id=actual_db_id).first()
                if mission:
                    col_to_attr = {
                        "Mission ID": "mission_id", "Date": "date", "Platform": "platform",
                        "Chassis": "chassis", "Customer": "customer", "Site": "site",
                        "Altitude (m)": "altitude_m", "Speed (m/s)": "speed_m_s",
                        "Spacing (m)": "spacing_m", "Sky": "sky_conditions",
                        "Wind (kts)": "wind_knots", "Battery": "battery",
                        "Filesize (GB)": "filesize_gb", "Test?": "is_test",
                        "HW Issues": "issues_hw", "Operator Issues": "issues_operator",
                        "SW Issues": "issues_sw", "Outcome": "outcome",
                        "Comments": "comments", "Raw METAR": "raw_metar"
                    }
                    attr_name = col_to_attr.get(column_name)

                    if attr_name:  # Check if the attribute name is valid
                        if attr_name in ["altitude_m", "speed_m_s", "spacing_m", "wind_knots", "filesize_gb"]:
                            setattr(mission, attr_name, float(new_value) if new_value else None)
                        elif attr_name == "is_test":
                            setattr(mission, attr_name, new_value.lower() == 'yes')
                        elif attr_name == "date":
                            try:
                                date_obj = datetime.strptime(new_value, '%Y-%m-%d').date()
                                setattr(mission, attr_name, date_obj)
                            except ValueError:
                                raise ValueError(f"Invalid date format for '{new_value}'. Use YYYY-MM-DD.")
                        else:
                            setattr(mission, attr_name, new_value)

            self.session.commit()

            # --- FIX: Clear the tracking dictionaries after a successful commit ---
            self.edited_cells.clear()
            self.unsaved_rows.clear()

            QMessageBox.information(self, "Success", "All changes have been saved.")
            # --- Now it's safe to reload the missions ---
            self.load_missions()

        except ValueError as e:
            self.session.rollback()
            QMessageBox.critical(self, "Input Error", f"Failed to save changes due to invalid input data:\n{e}")
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"An unexpected error occurred while saving: {e}")

    def undo_last_edit(self):
        """Undoes the last cell edit from the undo stack."""
        if self.undo_stack:
            self.is_undoing = True
            edit = self.undo_stack.pop()
            self.redo_stack.append(edit)

            row, col = edit['row'], edit['column']
            old_value = str(edit['old_value'] or "")

            # Temporarily disconnect the signal to prevent re-triggering cell_was_edited
            self.missionTable.cellChanged.disconnect(self.cell_was_edited)
            self.missionTable.setItem(row, col, QTableWidgetItem(old_value))
            self.missionTable.cellChanged.connect(self.cell_was_edited)

            # Manually trigger the visual changes and update the edited_cells dictionary
            current_item = self.missionTable.item(row, col)
            if current_item:
                current_item.setData(Qt.BackgroundRole, None)

            # Check if this row still has edited cells
            row_edited = any(
                (r, c) in self.edited_cells for r in range(self.missionTable.rowCount())
                for c in range(self.missionTable.columnCount())
                if r == row and c != col
            )

            db_id_item = self.missionTable.item(row, 0)
            if db_id_item and not row_edited and not db_id_item.text().startswith(TEMP_ID_PREFIX):
                db_id_text = db_id_item.text().replace(" *", "")
                db_id_item.setText(db_id_text)

            self.edited_cells.pop((row, col), None)

            self.is_undoing = False

    def redo_last_edit(self):
        """Redoes the last undone cell edit from the redo stack."""
        if self.redo_stack:
            self.is_redoing = True
            edit = self.redo_stack.pop()
            self.undo_stack.append(edit)

            row, col = edit['row'], edit['column']
            new_value = str(edit['new_value'] or "")

            self.missionTable.cellChanged.disconnect(self.cell_was_edited)
            self.missionTable.setItem(row, col, QTableWidgetItem(new_value))
            self.missionTable.cellChanged.connect(self.cell_was_edited)

            # Manually apply visual changes
            current_item = self.missionTable.item(row, col)
            if current_item:
                current_item.setData(Qt.BackgroundRole, QColor("#ebcb8b"))

            db_id_item = self.missionTable.item(row, 0)
            if db_id_item and not db_id_item.text().endswith(" *") and not db_id_item.text().startswith(TEMP_ID_PREFIX):
                db_id_item.setText(db_id_item.text() + " *")

            self.edited_cells[(row, col)] = new_value

            self.is_redoing = False

    def clear_form(self):
        """Clears all input fields in the mission editor form."""
        self.mission_id_input.clear()
        self.dateInput.setDate(QDate.currentDate())
        self.platformInput.clear()
        self.chassisInput.clear()
        self.customerInput.clear()
        self.siteInput.clear()
        self.altitudeInput.clear()
        self.speedInput.clear()
        self.spacingInput.clear()
        self.skyInput.setCurrentIndex(0)
        self.windInput.clear()
        self.batteryInput.clear()
        self.filesizeInput.clear()
        self.isTestInput.setChecked(False)
        self.issuesHwInput.clear()
        self.issuesOperatorInput.clear()
        self.issuesSwInput.clear()
        self.outcomeInput.clear()
        self.commentsInput.clear()
        self.rawMetarInput.clear()

        self.updateMissionButton.hide()
        self.saveNewMissionButton.show()
        self.current_selected_mission_id = None

    def _mark_required_fields(self):
        """Marks required fields with a red asterisk."""
        # Removed the Mission ID field from this list, as it is not required.
        self.labelDate.setText(f"{self.labelDate.text()} <span style='color:red;'>*</span>")
        self.labelPlatform.setText(f"{self.labelPlatform.text()} <span style='color:red;'>*</span>")
        self.labelSite.setText(f"{self.labelSite.text()} <span style='color:red;'>*</span>")
        self.labelBattery.setText(f"{self.labelBattery.text()} <span style='color:red;'>*</span>")

    def closeEvent(self, event):
        """Handles the close event of the window."""
        if self.edited_cells or self.unsaved_rows:
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         "You have unsaved changes. Are you sure you want to quit?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.session.close()
                event.accept()
            else:
                event.ignore()
        else:
            self.session.close()
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())