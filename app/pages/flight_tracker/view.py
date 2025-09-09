import os
from datetime import datetime

from PyQt5.QtCore import Qt, QSize, QDate
from PyQt5.QtGui import QIcon, QColor, QPixmap, QKeySequence
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QToolBar, QAction,
    QLineEdit, QLabel, QSizePolicy, QComboBox, QPlainTextEdit, QDateEdit, QCheckBox, QScrollArea, QGridLayout,
    QMessageBox, QSplitter, QAbstractItemView
)

from app.database.manager import db_manager
from app.logic.metar_service import metar_service, MetarWorker, get_metar_for_mission
from app.logic.metar_dialog import show_metar_selection_dialog
from app.logic.mission_grouping_service import mission_grouping_service

TEMP_ID_PREFIX = "NEW_"

class FlightTrackerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.Mission = None

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
        self.unsaved_rows = {} # New set to track unsaved rows by their temporary ID

        self.setup_ui()
        db_manager.connection_set.connect(self.load_missions)
        self.load_missions() # Initial load

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal)

        # --- Left Side: Toolbar and Table ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.create_toolbar()
        left_layout.addWidget(self.toolbar)

        self.missionTable = QTableWidget()
        self.missionTable.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        self.missionTable.setAlternatingRowColors(True)
        self.missionTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.missionTable.setSortingEnabled(True)
        self.missionTable.horizontalHeader().setCascadingSectionResizes(False)
        self.missionTable.horizontalHeader().setSortIndicatorShown(True)
        self.missionTable.horizontalHeader().setStretchLastSection(True)
        self.missionTable.verticalHeader().setVisible(False)
        self.missionTable.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Set custom sort function for Mission ID column to sort numerically
        self.missionTable.setSortingEnabled(False)  # Disable default sorting
        self.missionTable.horizontalHeader().sectionClicked.connect(self.custom_sort)
        self.current_sort_column = -1
        self.current_sort_order = Qt.AscendingOrder

        left_layout.addWidget(self.missionTable)

        # --- Right Side: Mission Editor Form ---
        self.create_editor_form()

        splitter.addWidget(left_widget)
        splitter.addWidget(self.editor_scroll_area)
        splitter.setSizes([750, 250]) # Adjust initial sizes as needed

        main_layout.addWidget(splitter)

        # --- Connect Signals ---
        self.missionTable.cellPressed.connect(self.cell_pressed_for_edit)
        self.missionTable.cellChanged.connect(self.cell_was_edited)
        self.missionTable.cellClicked.connect(self.load_mission_to_form)

    def create_toolbar(self):
        self.toolbar = QToolBar("Main Toolbar")
        # Correct path assuming 'resources' is at the project root, sibling to 'app'
        base_dir = os.path.dirname(__file__)
        icon_path = os.path.abspath(os.path.join(base_dir, '..', '..', 'resources', 'icons'))

        def create_action(text, icon_name, shortcut=None, connect_to=None):
            icon = QIcon()
            full_icon_path = os.path.join(icon_path, icon_name)
            if os.path.exists(full_icon_path):
                icon = QIcon(full_icon_path)
            action = QAction(icon, text, self)
            if shortcut:
                action.setShortcut(shortcut)
            if connect_to:
                action.triggered.connect(connect_to)
            return action

        # --- Actions ---
        self.refresh_action = create_action("Refresh", "refresh-cw.svg", connect_to=self.load_missions)
        self.save_action = create_action("Save Edits", "save.svg", shortcut=QKeySequence("Ctrl+S"), connect_to=self.save_edits)
        self.delete_action = create_action("Delete Selected Row", "trash-2.svg", shortcut=QKeySequence.Delete, connect_to=self.delete_selected)
        self.create_row_action = create_action("Create New Row", "plus.svg", shortcut=QKeySequence("Ctrl+N"), connect_to=self.create_new_empty_row)
        self.undo_action = create_action("Undo", "undo.svg", shortcut=QKeySequence.Undo, connect_to=self.undo_last_edit)
        self.redo_action = create_action("Redo", "redo.svg", shortcut=QKeySequence.Redo, connect_to=self.redo_last_edit)

        self.toolbar.addAction(self.refresh_action)
        self.toolbar.addAction(self.save_action)
        self.toolbar.addAction(self.delete_action)
        self.toolbar.addAction(self.create_row_action)
        self.toolbar.addAction(self.undo_action)
        self.toolbar.addAction(self.redo_action)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)

        self.toggle_editor_action = create_action("Toggle Editor", "sidebar.svg", connect_to=self.toggle_editor_visibility)
        self.toolbar.addAction(self.toggle_editor_action)

    def create_editor_form(self):
        self.editor_scroll_area = QScrollArea()
        self.editor_scroll_area.setWidgetResizable(True)
        self.editor_widget = QWidget()
        editor_layout = QVBoxLayout(self.editor_widget)

        title = QLabel("MISSION EDITOR")
        title.setAlignment(Qt.AlignCenter)
        # Optionally set font if available
        editor_layout.addWidget(title)

        form_layout = QGridLayout()
        form_layout.setSpacing(5)

        # Create and add all form widgets
        self.mission_id_input = QLineEdit()
        self.mission_id_input.setReadOnly(True)  # Mission_ID is auto-assigned
        self.mission_id_input.setStyleSheet("QLineEdit { background-color: #f0f0f0; }")  # Gray background to indicate read-only
        self.dateInput = QDateEdit(calendarPopup=True)
        self.platformInput = QComboBox()
        self.platformInput.setEditable(True)  # Allow custom entry
        self.chassisInput = QComboBox()
        self.chassisInput.setEditable(True)  # Allow custom entry
        self.customerInput = QLineEdit()
        self.siteInput = QLineEdit()
        self.altitudeInput = QLineEdit()
        self.speedInput = QLineEdit()
        self.spacingInput = QLineEdit()
        self.skyInput = QComboBox()
        self.skyInput.addItems(["CLR", "FEW", "SCT", "BKN", "OVC"])
        self.windInput = QLineEdit()
        self.batteryInput = QComboBox()
        self.batteryInput.setEditable(True)  # Allow custom entry
        self.filesizeInput = QLineEdit()
        self.isTestInput = QCheckBox()
        self.issuesHwInput = QComboBox()
        self.issuesHwInput.addItems(["None", "UAV", "Wiring", "GNSS", "LiDAR", "RGB", "VNIR", "SWIR", "Battery", "Other"])
        self.issuesHwInput.setCurrentText("None")  # Set default
        self.issuesOperatorInput = QComboBox()
        self.issuesOperatorInput.addItems(["None", "Pilot Error", "Flight Plan", "Lens Cap", "Polygon", "Other"])
        self.issuesOperatorInput.setCurrentText("None")  # Set default
        self.issuesEnvironmentInput = QComboBox()
        self.issuesEnvironmentInput.addItems(["None", "Clouds", "Wind", "Dust", "Solar Activity", "Outside of Solar", "Noon", "Other"])
        self.issuesEnvironmentInput.setCurrentText("None")  # Set default
        self.issuesSwInput = QLineEdit()
        self.outcomeInput = QComboBox()
        self.outcomeInput.addItems(["Failed", "Minor Loss", "Objective Complete", "Partial Success", "Full Success"])
        self.commentsInput = QPlainTextEdit()
        self.rawMetarInput = QPlainTextEdit()

        # Add widgets to form layout with labels
        form_widgets = {
            "Mission ID:": self.mission_id_input,
            "Date:*": self.dateInput,
            "Platform:*": self.platformInput,
            "Chassis:": self.chassisInput,
            "Customer:": self.customerInput,
            "Site:": self.siteInput,
            "Altitude (m):": self.altitudeInput,
            "Speed (m/s):": self.speedInput,
            "Spacing (m):": self.spacingInput,
            "Sky:": self.skyInput,
            "Wind (kts):": self.windInput,
            "Battery:*": self.batteryInput,
            "Filesize (GB):": self.filesizeInput,
            "Test?": self.isTestInput,
            "HW Issues:": self.issuesHwInput,
            "Operator Issues:": self.issuesOperatorInput,
            "Environment Issues:": self.issuesEnvironmentInput,
            "SW Issues:": self.issuesSwInput,
            "Outcome:": self.outcomeInput,
        }

        row = 0
        for label_text, widget in form_widgets.items():
            form_layout.addWidget(QLabel(label_text), row, 0)
            form_layout.addWidget(widget, row, 1)
            row += 1

        form_layout.addWidget(QLabel("Comments:"), row, 0, 1, 2)
        form_layout.addWidget(self.commentsInput, row + 1, 0, 1, 2)

        # Raw METAR section with button next to label
        metar_layout = QHBoxLayout()
        metar_label = QLabel("Raw METAR:")
        self.fetchMetarButton = QPushButton("Fetch METAR")
        self.fetchMetarButton.setStyleSheet("QPushButton { background-color: #17a2b8; color: white; padding: 2px 8px; font-size: 11px; } QPushButton:hover { background-color: #138496; }")
        self.fetchMetarButton.setMaximumWidth(80)
        metar_layout.addWidget(metar_label)
        metar_layout.addStretch()
        metar_layout.addWidget(self.fetchMetarButton)
        form_layout.addLayout(metar_layout, row + 2, 0, 1, 2)
        form_layout.addWidget(self.rawMetarInput, row + 3, 0, 1, 2)

        editor_layout.addLayout(form_layout)
        editor_layout.addStretch()

        button_layout = QHBoxLayout()
        self.updateMissionButton = QPushButton("Update Mission")
        self.saveNewMissionButton = QPushButton("Save New Mission")
        self.clearFormButton = QPushButton("Clear")
        button_layout.addStretch()
        button_layout.addWidget(self.clearFormButton)
        button_layout.addWidget(self.updateMissionButton)
        button_layout.addWidget(self.saveNewMissionButton)
        button_layout.addStretch()
        editor_layout.addLayout(button_layout)

        self.editor_scroll_area.setWidget(self.editor_widget)

        # Connect form buttons
        self.updateMissionButton.clicked.connect(self.update_mission)
        self.saveNewMissionButton.clicked.connect(self.save_new_mission)
        self.clearFormButton.clicked.connect(self.clear_form)
        self.fetchMetarButton.clicked.connect(self.fetch_metar)

        # Connect platform change to update battery dropdown
        self.platformInput.currentTextChanged.connect(self.update_battery_dropdown)

        # Connect to database manager signals for real-time updates
        db_manager.platforms_updated.connect(self.populate_dropdowns)
        db_manager.systems_updated.connect(self.populate_dropdowns)
        db_manager.systems_updated.connect(self.load_missions)

        # Populate dropdowns
        self.populate_dropdowns()

    def load_missions(self):
        if not db_manager.session:
            self.setEnabled(False)
            self.missionTable.setRowCount(0)
            QMessageBox.warning(self, "Database Error", "No database connection available.")
            return

        self.Mission = db_manager.get_model('missions')
        if not self.Mission:
            self.setEnabled(False)
            self.missionTable.setRowCount(0)
            QMessageBox.critical(self, "Database Error", "'missions' table not found in the database.")
            return

        self.setEnabled(True)
        self.updating_table = True
        self.edited_cells.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.unsaved_rows.clear()
        self.original_table_data.clear()
        self.clear_form()

        self.missionTable.setRowCount(0)
        headers = [
            "ID", "Mission ID", "Date", "Platform", "Chassis", "Customer", "Site",
            "Altitude (m)", "Speed (m/s)", "Spacing (m)", "Sky", "Wind (kts)", "Battery", "Filesize (GB)",
            "Test?", "HW Issues", "Operator Issues", "SW Issues", "Outcome", "Comments", "Raw METAR"
        ]
        self.missionTable.setColumnCount(len(headers))
        self.missionTable.setHorizontalHeaderLabels(headers)

        missions = db_manager.session.query(self.Mission).all()
        for row_idx, m in enumerate(missions):
            self.missionTable.insertRow(row_idx)
            date_value = ""
            if m.date:
                if hasattr(m.date, 'strftime'):
                    date_value = m.date.strftime('%Y-%m-%d')
                else:
                    date_value = str(m.date)
            values = [
                m.id, m.mission_id, date_value, m.platform, m.chassis, m.customer, m.site,
                m.altitude_m, m.speed_m_s, m.spacing_m, m.sky_conditions, m.wind_knots, m.battery,
                m.filesize_gb, "Yes" if m.is_test else "No", m.issues_hw, m.issues_operator,
                m.issues_sw, m.outcome, m.comments, m.raw_metar
            ]
            for col_idx, val in enumerate(values):
                item = QTableWidgetItem(str(val or ""))
                self.missionTable.setItem(row_idx, col_idx, item)

            self.original_table_data[m.id] = {header: str(values[col_idx] or "") for col_idx, header in enumerate(headers)}

        self.missionTable.resizeColumnsToContents()
        self.updating_table = False

    def get_text(self, widget):
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

    def load_mission_to_form(self, row, column):
        # Clear the form first to prevent data carryover
        self.clear_form()
        
        id_item = self.missionTable.item(row, 0)
        if not id_item or not id_item.text():
            return

        db_id_text = id_item.text().strip(' *')
        is_new_row = db_id_text.startswith(TEMP_ID_PREFIX)
        headers = [self.missionTable.horizontalHeaderItem(c).text() for c in range(self.missionTable.columnCount())]

        # For new rows, only populate the form if there's actual data in the row
        if is_new_row:
            self.current_selected_mission_id = db_id_text
            self.saveNewMissionButton.show()
            self.updateMissionButton.hide()
            
            # Only populate if there's data in the row
            has_data = any(self.missionTable.item(row, c) is not None and self.missionTable.item(row, c).text() 
                          for c in range(1, self.missionTable.columnCount()))
            
            if has_data:
                for col, header in enumerate(headers):
                    item = self.missionTable.item(row, col)
                    text = item.text() if item else ""
                    if header == "Mission ID": self.mission_id_input.setText(text)
                    elif header == "Date": 
                        self.dateInput.setDate(QDate.fromString(text, 'yyyy-MM-dd') if text else QDate.currentDate())
                    elif header == "Platform": self.platformInput.setCurrentText(text)
                    elif header == "Chassis": self.chassisInput.setCurrentText(text)
                    elif header == "Customer": self.customerInput.setText(text)
                    elif header == "Site": self.siteInput.setText(text)
                    elif header == "Altitude (m)": self.altitudeInput.setText(text)
                    elif header == "Speed (m/s)": self.speedInput.setText(text)
                    elif header == "Spacing (m)": self.spacingInput.setText(text)
                    elif header == "Sky": 
                        index = self.skyInput.findText(text, Qt.MatchFixedString)
                        self.skyInput.setCurrentIndex(index if index >= 0 else 0)
                    elif header == "Wind (kts)": self.windInput.setText(text)
                    elif header == "Battery": self.batteryInput.setCurrentText(text)
                    elif header == "Filesize (GB)": self.filesizeInput.setText(text)
                    elif header == "Test?": self.isTestInput.setChecked(text.lower() == 'yes')
                    elif header == "HW Issues":
                        index = self.issuesHwInput.findText(text, Qt.MatchFixedString)
                        if index >= 0:
                            self.issuesHwInput.setCurrentIndex(index)
                        else:
                            self.issuesHwInput.setCurrentText(text)
                    elif header == "Operator Issues":
                        index = self.issuesOperatorInput.findText(text, Qt.MatchFixedString)
                        if index >= 0:
                            self.issuesOperatorInput.setCurrentIndex(index)
                        else:
                            self.issuesOperatorInput.setCurrentText(text)
                    elif header == "SW Issues": self.issuesSwInput.setText(text)
                    elif header == "Outcome":
                        index = self.outcomeInput.findText(text, Qt.MatchFixedString)
                        if index >= 0:
                            self.outcomeInput.setCurrentIndex(index)
                        else:
                            self.outcomeInput.setCurrentText(text)
                    elif header == "Comments": self.commentsInput.setPlainText(text)
                    elif header == "Raw METAR": self.rawMetarInput.setPlainText(text)
        else:
            # Handle existing mission
            try:
                mission_db_id = int(db_id_text)
                mission = db_manager.session.query(self.Mission).filter_by(id=mission_db_id).first()
                if not mission:
                    QMessageBox.warning(self, "Load Error", f"Mission with ID {mission_db_id} not found.")
                    return

                self.current_selected_mission_id = mission_db_id
                self.dateInput.setDate(QDate(mission.date) if mission.date else QDate.currentDate())
                self.mission_id_input.setText(str(mission.mission_id or ''))
                # Set platform and chassis with proper QComboBox handling
                platform = str(mission.platform or '')
                if platform:
                    index = self.platformInput.findText(platform, Qt.MatchFixedString)
                    if index >= 0:
                        self.platformInput.setCurrentIndex(index)
                    else:
                        self.platformInput.setCurrentText(platform)

                chassis = str(mission.chassis or '')
                if chassis:
                    index = self.chassisInput.findText(chassis, Qt.MatchFixedString)
                    if index >= 0:
                        self.chassisInput.setCurrentIndex(index)
                    else:
                        self.chassisInput.setCurrentText(chassis)
                self.customerInput.setText(str(mission.customer or ''))
                self.siteInput.setText(str(mission.site or ''))
                self.altitudeInput.setText(str(mission.altitude_m) if mission.altitude_m is not None else '')
                self.speedInput.setText(str(mission.speed_m_s) if mission.speed_m_s is not None else '')
                self.spacingInput.setText(str(mission.spacing_m) if mission.spacing_m is not None else '')
                self.windInput.setText(str(mission.wind_knots) if mission.wind_knots is not None else '')
                # Set battery with proper QComboBox handling
                battery = str(mission.battery or '')
                if battery:
                    index = self.batteryInput.findText(battery, Qt.MatchFixedString)
                    if index >= 0:
                        self.batteryInput.setCurrentIndex(index)
                    else:
                        self.batteryInput.setCurrentText(battery)
                self.filesizeInput.setText(str(mission.filesize_gb) if mission.filesize_gb is not None else '')
                index = self.skyInput.findText(mission.sky_conditions or "", Qt.MatchFixedString)
                self.skyInput.setCurrentIndex(index if index >= 0 else 0)
                self.isTestInput.setChecked(mission.is_test or False)
                # Set dropdown values with fallbacks to text input if not in list
                hw_issues = str(mission.issues_hw or '')
                if hw_issues:
                    index = self.issuesHwInput.findText(hw_issues, Qt.MatchFixedString)
                    if index >= 0:
                        self.issuesHwInput.setCurrentIndex(index)
                    else:
                        self.issuesHwInput.setCurrentText(hw_issues)

                operator_issues = str(mission.issues_operator or '')
                if operator_issues:
                    index = self.issuesOperatorInput.findText(operator_issues, Qt.MatchFixedString)
                    if index >= 0:
                        self.issuesOperatorInput.setCurrentIndex(index)
                    else:
                        self.issuesOperatorInput.setCurrentText(operator_issues)

                outcome = str(mission.outcome or '')
                if outcome:
                    index = self.outcomeInput.findText(outcome, Qt.MatchFixedString)
                    if index >= 0:
                        self.outcomeInput.setCurrentIndex(index)
                    else:
                        self.outcomeInput.setCurrentText(outcome)

                self.issuesSwInput.setText(str(mission.issues_sw or ''))
                self.commentsInput.setPlainText(str(mission.comments or ''))
                self.rawMetarInput.setPlainText(str(mission.raw_metar or ''))
                self.updateMissionButton.show()
                self.saveNewMissionButton.hide()
            except (ValueError, Exception) as e:
                QMessageBox.warning(self, "Error", f"Failed to load mission: {e}")
                self.clear_form()

    def update_mission(self):
        if not self.current_selected_mission_id:
            QMessageBox.warning(self, "No Mission Selected", "Please select a mission to update.")
            return

        is_new_row = str(self.current_selected_mission_id).startswith(TEMP_ID_PREFIX)

        try:
            mission_data = {
                "mission_id": self.get_text(self.mission_id_input) or None,
                "date": self.dateInput.date().toPyDate(),
                "platform": self.get_text(self.platformInput) or None,
                "chassis": self.get_text(self.chassisInput) or None,
                "customer": self.get_text(self.customerInput) or None,
                "site": self.get_text(self.siteInput) or None,
                "altitude_m": self.get_text(self.altitudeInput) or None,
                "speed_m_s": self.get_text(self.speedInput) or None,
                "spacing_m": self.get_text(self.spacingInput) or None,
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

            if is_new_row:
                new_mission = self.Mission(**mission_data)
                db_manager.session.add(new_mission)
                db_manager.session.commit()
                QMessageBox.information(self, "Success", "New mission saved successfully!")
            else:
                mission = db_manager.session.query(self.Mission).filter_by(id=self.current_selected_mission_id).first()
                if mission:
                    for key, value in mission_data.items():
                        setattr(mission, key, value)
                    db_manager.session.commit()
                    QMessageBox.information(self, "Success", f"Mission ID {mission.mission_id} updated successfully!")

            self.clear_form()
            self.load_missions()

        except ValueError as e:
            db_manager.session.rollback()
            QMessageBox.critical(self, "Input Error", f"Invalid input data: {e}")
        except Exception as e:
            db_manager.session.rollback()
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")

    def save_new_mission(self):
        try:
            # Don't include mission_id in the data - it will be auto-assigned
            mission_data = {
                "date": self.dateInput.date().toPyDate(),
                "platform": self.get_text(self.platformInput) or None,
                "chassis": self.get_text(self.chassisInput) or None,
                "customer": self.get_text(self.customerInput) or None,
                "site": self.get_text(self.siteInput) or None,
                "altitude_m": self.get_text(self.altitudeInput) or None,
                "speed_m_s": self.get_text(self.speedInput) or None,
                "spacing_m": self.get_text(self.spacingInput) or None,
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

            # Create the mission without Mission_ID first
            new_mission = self.Mission(**mission_data)
            db_manager.session.add(new_mission)
            db_manager.session.flush()  # Get the ID but don't commit yet

            # Now assign Mission_ID using the grouping service
            try:
                assignments = mission_grouping_service.assign_mission_ids(reevaluate_existing=False)
                assigned_mission_id = assignments.get(new_mission.id)

                if assigned_mission_id:
                    new_mission.mission_id = assigned_mission_id
                    # Update the form to show the assigned Mission_ID
                    self.mission_id_input.setText(str(assigned_mission_id))

                db_manager.session.commit()

                # Auto-generate processing entry
                from app.logic.processing_auto_generator import processing_auto_generator
                if assigned_mission_id:
                    processing_results = processing_auto_generator.generate_processing_entries(force_update=False)
                    print(f"Processing entry generation: {processing_results.get('summary', 'No summary')}")

                QMessageBox.information(self, "Success",
                    f"New mission saved successfully!\nAssigned Mission_ID: {assigned_mission_id}")

            except Exception as grouping_error:
                print(f"Mission_ID assignment failed: {grouping_error}")
                # Still commit the mission even if grouping fails
                db_manager.session.commit()
                QMessageBox.information(self, "Success",
                    "New mission saved successfully!\n(Note: Mission_ID assignment failed - will be assigned later)")

            self.clear_form()
            self.load_missions()

        except ValueError as e:
            db_manager.session.rollback()
            QMessageBox.critical(self, "Input Error", f"Invalid input data: {e}")
        except Exception as e:
            db_manager.session.rollback()
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")

    def _is_row_has_data(self, row_idx):
        """Check if a row has any non-empty data cells (excluding ID column)."""
        for col in range(1, self.missionTable.columnCount()):
            item = self.missionTable.item(row_idx, col)
            if item and item.text().strip():
                return True
        return False

    def save_edits(self):
        if not self.edited_cells and not self.unsaved_rows:
            QMessageBox.information(self, "No Changes", "There are no pending changes to save.")
            return

        try:
            saved_count = 0
            
            # Handle new rows first
            for temp_id in list(self.unsaved_rows.keys()):
                row_idx = -1
                for i in range(self.missionTable.rowCount()):
                    item = self.missionTable.item(i, 0)
                    if item and item.text() == temp_id:
                        row_idx = i
                        break
                
                if row_idx == -1:
                    continue

                # Skip empty rows
                if not self._is_row_has_data(row_idx):
                    continue

                headers = [self.missionTable.horizontalHeaderItem(c).text() 
                         for c in range(self.missionTable.columnCount())]
                mission_data = {}
                
                for col, header in enumerate(headers):
                    if header == 'ID':
                        continue
                        
                    item = self.missionTable.item(row_idx, col)
                    if not item:
                        continue
                        
                    text = item.text().strip()
                    col_name = header.lower().replace(' ', '_').replace('(', '').replace(')', '')
                    
                    # Handle different data types
                    if not text:
                        mission_data[col_name] = None
                    elif header == 'Date':
                        try:
                            mission_data[col_name] = datetime.strptime(text, '%Y-%m-%d').date()
                        except ValueError:
                            mission_data[col_name] = None
                    elif header in ['Altitude (m)', 'Speed (m/s)', 'Spacing (m)', 'Wind (kts)', 'Filesize (GB)']:
                        try:
                            mission_data[col_name] = float(text) if text else None
                        except ValueError:
                            mission_data[col_name] = None
                    elif header == 'Test?':
                        mission_data['is_test'] = text.lower() == 'yes'
                    else:
                        mission_data[col_name] = text

                try:
                    new_mission = self.Mission(**mission_data)
                    db_manager.session.add(new_mission)
                    db_manager.session.flush()  # Get the ID but don't commit yet

                    # Assign Mission_ID using the grouping service
                    try:
                        assignments = mission_grouping_service.assign_mission_ids(reevaluate_existing=False)
                        assigned_mission_id = assignments.get(new_mission.id)

                        if assigned_mission_id:
                            new_mission.mission_id = assigned_mission_id
                            # Update the table to show the assigned Mission_ID
                            self.missionTable.item(row_idx, 1).setText(str(assigned_mission_id))

                        saved_count += 1

                        # Update the temp ID to real ID
                        self.missionTable.item(row_idx, 0).setText(str(new_mission.id))

                    except Exception as grouping_error:
                        print(f"Mission_ID assignment failed for new mission: {grouping_error}")
                        # Still count as saved but without Mission_ID
                        saved_count += 1
                        self.missionTable.item(row_idx, 0).setText(str(new_mission.id))

                except Exception as e:
                    db_manager.session.rollback()
                    QMessageBox.warning(self, "Save Error",
                                     f"Failed to save row {row_idx + 1}: {str(e)}")

            # Handle cell edits for existing missions
            for (row, col), new_value in self.edited_cells.items():
                db_id_item = self.missionTable.item(row, 0)
                if not db_id_item or db_id_item.text().startswith(TEMP_ID_PREFIX):
                    continue
                
                try:
                    db_id = int(db_id_item.text().strip(' *'))
                    column_name = self.missionTable.horizontalHeaderItem(col).text().lower().replace(' ', '_').replace('(', '').replace(')', '')
                    mission = db_manager.session.query(self.Mission).filter_by(id=db_id).first()
                    
                    if mission:
                        # Convert value to appropriate type
                        if column_name == 'date':
                            new_value = datetime.strptime(new_value, '%Y-%m-%d').date() if new_value else None
                        elif column_name in ['altitude_m', 'speed_m_s', 'spacing_m', 'wind_knots', 'filesize_gb']:
                            try:
                                new_value = float(new_value) if new_value else None
                            except (ValueError, TypeError):
                                new_value = None
                        elif column_name == 'is_test':
                            new_value = str(new_value).lower() == 'yes'
                                
                        setattr(mission, column_name, new_value)
                        saved_count += 1
                        
                except Exception as e:
                    db_manager.session.rollback()
                    QMessageBox.warning(self, "Update Error", 
                                     f"Failed to update cell at row {row + 1}, column {col + 1}: {str(e)}")
            
            if saved_count > 0:
                db_manager.session.commit()
                QMessageBox.information(self, "Success", f"Successfully saved {saved_count} changes.")
                self.edited_cells.clear()
                self.unsaved_rows.clear()
                self.load_missions()  # Refresh the table
            else:
                QMessageBox.information(self, "No Valid Changes", "No valid changes were found to save.")
                
        except Exception as e:
            db_manager.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save changes: {e}")

    def delete_selected(self):
        selected_rows = sorted(list(set(index.row() for index in self.missionTable.selectedIndexes())), reverse=True)
        if not selected_rows:
            return

        reply = QMessageBox.question(self, "Confirm Deletion", "Delete selected mission(s)?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                for row in selected_rows:
                    id_item = self.missionTable.item(row, 0)
                    if id_item.text().startswith(TEMP_ID_PREFIX):
                        self.missionTable.removeRow(row)
                    else:
                        db_id = int(id_item.text().strip(' *'))
                        mission = db_manager.session.query(self.Mission).filter_by(id=db_id).first()
                        if mission:
                            db_manager.session.delete(mission)
                db_manager.session.commit()
                self.load_missions()
            except Exception as e:
                db_manager.session.rollback()
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def create_new_empty_row(self):
        row_count = self.missionTable.rowCount()
        self.missionTable.insertRow(row_count)
        temp_id = f"{TEMP_ID_PREFIX}{row_count}"
        self.missionTable.setItem(row_count, 0, QTableWidgetItem(temp_id))
        self.missionTable.setItem(row_count, 2, QTableWidgetItem(datetime.now().strftime('%Y-%m-%d')))
        self.unsaved_rows[temp_id] = True
        self.missionTable.scrollToBottom()

    def cell_pressed_for_edit(self, row, column):
        if not self.updating_table:
            item = self.missionTable.item(row, column)
            self.current_edit_original_value = item.text() if item else ""

    def cell_was_edited(self, row, column):
        if self.updating_table or self.is_undoing or self.is_redoing: return

        current_item = self.missionTable.item(row, column)
        new_value = current_item.text() if current_item else ""

        if new_value == self.current_edit_original_value: return

        db_id_item = self.missionTable.item(row, 0)
        db_id = db_id_item.text()
        column_name = self.missionTable.horizontalHeaderItem(column).text()

        edit_record = {
            "db_id": db_id, "row": row, "column": column,
            "old_value": self.current_edit_original_value, "new_value": new_value
        }
        self.undo_stack.append(edit_record)
        self.redo_stack.clear()

        self.edited_cells[(row, column)] = new_value
        current_item.setBackground(QColor("#d08770"))
        if not db_id.endswith(' *'):
            db_id_item.setText(f"{db_id} *")

    def undo_last_edit(self):
        if not self.undo_stack: return
        self.is_undoing = True
        last_edit = self.undo_stack.pop()
        self.redo_stack.append(last_edit)

        row, col = last_edit['row'], last_edit['column']
        self.missionTable.item(row, col).setText(last_edit['old_value'])
        self.edited_cells.pop((row, col), None)
        # Add logic to check if row has other edits before removing color/asterisk
        self.is_undoing = False

    def redo_last_edit(self):
        if not self.redo_stack: return
        self.is_redoing = True
        last_undone_edit = self.redo_stack.pop()
        self.undo_stack.append(last_undone_edit)

        row, col = last_undone_edit['row'], last_undone_edit['column']
        self.missionTable.item(row, col).setText(last_undone_edit['new_value'])
        self.edited_cells[(row, col)] = last_undone_edit['new_value']
        self.is_redoing = False

    def toggle_editor_visibility(self):
        """Toggles the visibility of the mission editor form."""
        is_visible = self.editor_scroll_area.isVisible()
        self.editor_scroll_area.setVisible(not is_visible)

    def clear_form(self):
        for widget in self.editor_widget.findChildren(QLineEdit):
            widget.clear()
        for widget in self.editor_widget.findChildren(QPlainTextEdit):
            widget.clear()
        for widget in self.editor_widget.findChildren(QComboBox):
            widget.setCurrentIndex(0)
        for widget in self.editor_widget.findChildren(QCheckBox):
            widget.setChecked(False)
        self.dateInput.setDate(QDate.currentDate())
        self.current_selected_mission_id = None
        self.updateMissionButton.hide()
        self.saveNewMissionButton.show()

    def populate_dropdowns(self):
        """Populate all dropdowns with data from the database."""
        try:
            # Populate platforms
            platforms = db_manager.get_platform_names()
            self.platformInput.clear()
            self.platformInput.addItem("")  # Add blank option first
            self.platformInput.addItems(platforms)
            self.platformInput.setCurrentIndex(0)  # Set to blank

            # Populate chassis
            chassis_list = db_manager.get_chassis_list()
            self.chassisInput.clear()
            self.chassisInput.addItem("")  # Add blank option first
            self.chassisInput.addItems(chassis_list)
            self.chassisInput.setCurrentIndex(0)  # Set to blank

            # Populate batteries (initially all)
            batteries = db_manager.get_batteries_for_platform()
            self.batteryInput.clear()
            self.batteryInput.addItem("")  # Add blank option first
            self.batteryInput.addItems(batteries)
            self.batteryInput.setCurrentIndex(0)  # Set to blank

        except Exception as e:
            print(f"Error populating dropdowns: {e}")

    def update_battery_dropdown(self, platform_name=None):
        """Update battery dropdown based on selected platform."""
        if not platform_name or platform_name.strip() == "":
            # If no platform selected, show all batteries
            batteries = db_manager.get_batteries_for_platform()
        else:
            # Filter batteries by selected platform
            batteries = db_manager.get_batteries_for_platform(platform_name.strip())

        # Preserve current selection if it exists in the new list
        current_selection = self.batteryInput.currentText()
        self.batteryInput.clear()
        self.batteryInput.addItem("")  # Add blank option first
        self.batteryInput.addItems(batteries)
        self.batteryInput.setCurrentIndex(0)  # Set to blank initially

        # Try to restore the previous selection
        if current_selection and current_selection != "":
            index = self.batteryInput.findText(current_selection, Qt.MatchFixedString)
            if index >= 0:
                self.batteryInput.setCurrentIndex(index)

    def fetch_metar(self):
        """Fetch METAR data using the enhanced selection dialog."""
        # Get current values for pre-filling the dialog
        site = self.siteInput.text().strip()
        mission_date = self.dateInput.date().toPyDate()

        # Extract station code for pre-filling
        station_code = self._extract_airport_code(site) if site else ""

        # Convert date to datetime for the dialog (use current time if date only)
        from datetime import datetime
        if isinstance(mission_date, datetime):
            prefill_datetime = mission_date
        else:
            # If it's just a date, combine with current time
            current_time = datetime.now().time()
            prefill_datetime = datetime.combine(mission_date, current_time)

        # Show the METAR selection dialog
        selected_metar = show_metar_selection_dialog(
            parent=self,
            station=station_code,
            date=prefill_datetime
        )

        # If user selected METAR data, populate the field
        if selected_metar:
            self.rawMetarInput.setPlainText(selected_metar)

    def _extract_airport_code(self, site_text):
        """Extract ICAO airport code from site text."""
        if not site_text:
            return None

        # Look for 4-letter uppercase codes (typical ICAO format)
        words = site_text.upper().split()
        for word in words:
            if len(word) == 4 and word.isalpha():
                return word

        return None

    def _on_metar_fetched(self, metar_data):
        """Handle successful METAR data fetch."""
        self.rawMetarInput.setPlainText(metar_data)
        self.fetchMetarButton.setText("Fetch METAR")
        self.fetchMetarButton.setEnabled(True)
        QMessageBox.information(self, "METAR Fetched",
                              f"METAR data retrieved successfully for {self._extract_airport_code(self.siteInput.text())}")

    def custom_sort(self, column):
        """Custom sort function that handles numerical sorting for Mission ID column."""
        # Toggle sort order if clicking the same column
        if column == self.current_sort_column:
            self.current_sort_order = Qt.DescendingOrder if self.current_sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            self.current_sort_column = column
            self.current_sort_order = Qt.AscendingOrder

        # Get all rows data
        rows_data = []
        for row in range(self.missionTable.rowCount()):
            row_data = []
            for col in range(self.missionTable.columnCount()):
                item = self.missionTable.item(row, col)
                row_data.append(item.text() if item else "")
            rows_data.append(row_data)

        # Sort the data
        if column in [0, 1]:  # ID column (index 0) and Mission ID column (index 1)
            # Custom sort for ID/Mission ID - numerical sort
            def numerical_key(row):
                value = row[column]
                try:
                    # For ID column, handle temporary IDs like "NEW_123"
                    if column == 0 and value.startswith(TEMP_ID_PREFIX):
                        # Extract number from temp ID
                        import re
                        numbers = re.findall(r'\d+', value)
                        if numbers:
                            return int(numbers[0])
                        else:
                            return 0
                    else:
                        # Try to extract number from value (handles cases like "Mission 123" or just "123")
                        import re
                        numbers = re.findall(r'\d+', value)
                        if numbers:
                            return int(numbers[0])  # Use first number found
                        else:
                            return 0  # Default for non-numeric
                except (ValueError, TypeError):
                    return 0

            rows_data.sort(key=numerical_key, reverse=(self.current_sort_order == Qt.DescendingOrder))
        else:
            # Default string sort for other columns
            rows_data.sort(key=lambda row: row[column], reverse=(self.current_sort_order == Qt.DescendingOrder))

        # Update the table with sorted data
        self.updating_table = True
        for row_idx, row_data in enumerate(rows_data):
            for col_idx, cell_data in enumerate(row_data):
                item = self.missionTable.item(row_idx, col_idx)
                if item:
                    item.setText(cell_data)
        self.updating_table = False

        # Update sort indicator
        self.missionTable.horizontalHeader().setSortIndicator(column, self.current_sort_order)
        self.missionTable.horizontalHeader().setSortIndicatorShown(True)

    def _on_metar_error(self, error_message):
        """Handle METAR fetch error."""
        self.fetchMetarButton.setText("Fetch METAR")
        self.fetchMetarButton.setEnabled(True)
        QMessageBox.warning(self, "METAR Error", f"Failed to fetch METAR data:\n\n{error_message}")
