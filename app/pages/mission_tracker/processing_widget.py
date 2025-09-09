import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QSize, QDate, pyqtSignal
from PyQt5.QtGui import QIcon, QColor, QPixmap, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QToolBar, QAction,
    QLineEdit, QLabel, QSizePolicy, QComboBox, QPlainTextEdit, QDateEdit, QCheckBox, QScrollArea,
    QSplitter, QAbstractItemView, QGroupBox, QFormLayout, QTextEdit, QFrame, QMessageBox, QGridLayout,
    QDialog, QDialogButtonBox, QMenu, QStyledItemDelegate, QFileDialog
)
from PyQt5.QtCore import QEvent

from app.database.manager import db_manager
from sqlalchemy import text

TEMP_ID_PREFIX = "NEW_"

# ---- Custom QTableWidgetItem classes for proper sorting ----
class NumericTableWidgetItem(QTableWidgetItem):
    """Table item that sorts numerically based on an integer/float value."""
    def __init__(self, text_value: str):
        super().__init__(text_value)
        # Try to parse numeric sort key; fall back to string when not numeric
        try:
            if '.' in (text_value or ''):
                sort_key = float(text_value)
            else:
                sort_key = int(text_value)
        except (ValueError, TypeError):
            sort_key = None
        self.setData(Qt.UserRole, sort_key if sort_key is not None else text_value)

    def __lt__(self, other):
        if isinstance(other, QTableWidgetItem):
            a = self.data(Qt.UserRole)
            b = other.data(Qt.UserRole)
            # If both numeric, compare numerically; else compare as strings
            a_is_num = isinstance(a, (int, float))
            b_is_num = isinstance(b, (int, float))
            if a_is_num and b_is_num:
                return a < b
            return str(self.text()) < str(other.text())
        return super().__lt__(other)

class DateTableWidgetItem(QTableWidgetItem):
    """Table item that sorts by date using YYYYMMDD integer sort key."""
    def __init__(self, display_text: str):
        super().__init__(display_text or "")
        sort_key = None
        try:
            # Expect formats like YYYY-MM-DD
            if display_text:
                parts = str(display_text).split('-')
                if len(parts) == 3:
                    sort_key = int(parts[0]) * 10000 + int(parts[1]) * 100 + int(parts[2])
        except Exception:
            sort_key = None
        self.setData(Qt.UserRole, sort_key if sort_key is not None else display_text)
    def __lt__(self, other):
        if isinstance(other, QTableWidgetItem):
            a = self.data(Qt.UserRole)
            b = other.data(Qt.UserRole)
            a_is_num = isinstance(a, int)
            b_is_num = isinstance(b, int)
            if a_is_num and b_is_num:
                return a < b
            return str(self.text()) < str(other.text())
        return super().__lt__(other)

class ProcessingTrackerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.Processing = None
        self.Missions = None
        self.Sites = None

        # State flags
        self.updating_table = False
        self.is_undoing = False
        self.is_redoing = False

        # Edit tracking
        self.edited_cells = {}
        self.undo_stack = []
        self.redo_stack = []
        self.current_edit_original_value = None
        self.current_selected_processing_id = None
        self.original_table_data = {}
        self.unsaved_rows = {}

        # Data caches
        self.missions_cache = {}
        self.sites_cache = {}

        self.setup_ui()
        db_manager.connection_set.connect(self.load_data)
        self.load_data()

    def setup_ui(self):
        """Set up the user interface with table and card views."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal)

        # Left side: Controls and Table
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        self.create_toolbar()
        left_layout.addWidget(self.toolbar)

        # Filters
        self.create_filters()
        left_layout.addWidget(self.filters_group)

        # Table
        self.processing_table = QTableWidget()
        self.processing_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        self.processing_table.setAlternatingRowColors(True)
        self.processing_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.processing_table.setSortingEnabled(True)
        self.processing_table.horizontalHeader().setCascadingSectionResizes(False)
        self.processing_table.horizontalHeader().setSortIndicatorShown(True)
        self.processing_table.horizontalHeader().setStretchLastSection(True)
        self.processing_table.verticalHeader().setVisible(False)
        self.processing_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(self.processing_table)

        # Right side: Card Details View
        self.create_card_view()

        splitter.addWidget(left_widget)
        splitter.addWidget(self.card_scroll_area)
        splitter.setSizes([600, 400])

        main_layout.addWidget(splitter)

        # Connect signals
        self.processing_table.cellPressed.connect(self.cell_pressed_for_edit)
        self.processing_table.cellChanged.connect(self.cell_was_edited)
        self.processing_table.cellClicked.connect(self.load_processing_to_form)
        self.processing_table.cellDoubleClicked.connect(self.handle_cell_double_click)

    def create_toolbar(self):
        """Create the toolbar with actions."""
        self.toolbar = QToolBar("Processing Toolbar")

        # Actions
        self.refresh_action = QAction("🔄 Refresh", self)
        self.refresh_action.triggered.connect(self.load_data)

        self.save_action = QAction("💾 Save Changes", self)
        self.save_action.triggered.connect(self.save_edits)

        self.delete_action = QAction("🗑️ Delete Selected", self)
        self.delete_action.triggered.connect(self.delete_selected)

        # Manual entry creation disabled - entries are auto-generated
        # self.create_row_action = QAction("➕ New Entry", self)
        # self.create_row_action.triggered.connect(self.show_new_entry_menu)

        self.undo_action = QAction("↶ Undo", self)
        self.undo_action.triggered.connect(self.undo_last_edit)

        self.redo_action = QAction("↷ Redo", self)
        self.redo_action.triggered.connect(self.redo_last_edit)

        self.toolbar.addAction(self.refresh_action)
        self.toolbar.addAction(self.save_action)
        self.toolbar.addAction(self.delete_action)
        # Manual entry creation disabled - entries are auto-generated
        # self.toolbar.addAction(self.create_row_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.undo_action)
        self.toolbar.addAction(self.redo_action)

    def create_filters(self):
        """Create filter controls."""
        self.filters_group = QGroupBox("Filters")
        layout = QHBoxLayout(self.filters_group)

        # Status filters
        layout.addWidget(QLabel("Processed:"))
        self.processed_filter = QComboBox()
        self.processed_filter.addItem("All")
        self.processed_filter.addItem("Yes")
        self.processed_filter.addItem("No")
        self.processed_filter.addItem("Reprocess")
        self.processed_filter.currentTextChanged.connect(self.apply_filters)
        layout.addWidget(self.processed_filter)

        layout.addWidget(QLabel("QA/QC:"))
        self.qa_filter = QComboBox()
        self.qa_filter.addItem("All")
        self.qa_filter.addItem("Needs Review")
        self.qa_filter.addItem("Approved")
        self.qa_filter.addItem("Not Approved")
        self.qa_filter.currentTextChanged.connect(self.apply_filters)
        layout.addWidget(self.qa_filter)

        # Mission filter
        layout.addWidget(QLabel("Mission:"))
        self.mission_filter = QComboBox()
        self.mission_filter.addItem("All Missions")
        self.mission_filter.currentTextChanged.connect(self.apply_filters)
        layout.addWidget(self.mission_filter)

        layout.addStretch()

        # Initialize dropdown caches
        self.mission_dropdown_cache = {}
        self.site_dropdown_cache = {}
        self.populate_dropdown_caches()

    def create_card_view(self):
        """Create the card-based details view."""
        self.card_scroll_area = QScrollArea()
        self.card_scroll_area.setWidgetResizable(True)
        self.card_widget = QWidget()
        self.card_layout = QVBoxLayout(self.card_widget)

        # Header
        self.card_header = QLabel("Processing Details")
        self.card_header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        self.card_layout.addWidget(self.card_header)

        # Processing card
        self.processing_card = self.create_processing_card()
        self.card_layout.addWidget(self.processing_card)

        # Action buttons
        self.create_action_buttons()
        self.card_layout.addWidget(self.action_buttons_group)

        self.card_layout.addStretch()
        self.card_scroll_area.setWidget(self.card_widget)

    def create_processing_card(self):
        """Create the main processing information card."""
        card = QGroupBox("Processing Entry")
        card.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        layout = QVBoxLayout(card)

        # Basic info grid
        info_layout = QGridLayout()

        # Row 1
        info_layout.addWidget(QLabel("Name:"), 0, 0)
        self.card_name_label = QLabel("-")
        self.card_name_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.card_name_label, 0, 1)

        info_layout.addWidget(QLabel("Chassis SN:"), 0, 2)
        self.card_chassis_label = QLabel("-")
        info_layout.addWidget(self.card_chassis_label, 0, 3)

        # Row 2
        info_layout.addWidget(QLabel("Mission:"), 1, 0)
        self.card_mission_label = QLabel("-")
        info_layout.addWidget(self.card_mission_label, 1, 1)

        info_layout.addWidget(QLabel("Site:"), 1, 2)
        self.card_site_label = QLabel("-")
        info_layout.addWidget(self.card_site_label, 1, 3)

        # Row 3
        info_layout.addWidget(QLabel("Flight Date:"), 2, 0)
        self.card_date_label = QLabel("-")
        info_layout.addWidget(self.card_date_label, 2, 1)

        info_layout.addWidget(QLabel("Created:"), 2, 2)
        self.card_created_label = QLabel("-")
        info_layout.addWidget(self.card_created_label, 2, 3)

        layout.addLayout(info_layout)

        # Status section
        status_group = QGroupBox("Status")
        status_layout = QHBoxLayout(status_group)

        # Processed status
        processed_layout = QVBoxLayout()
        processed_layout.addWidget(QLabel("Processed:"))
        self.card_processed_label = QLabel("No")
        self.card_processed_label.setStyleSheet("""
            QLabel {
                padding: 5px;
                border-radius: 3px;
                font-weight: bold;
            }
        """)
        processed_layout.addWidget(self.card_processed_label)
        status_layout.addLayout(processed_layout)

        # QA/QC status
        qa_layout = QVBoxLayout()
        qa_layout.addWidget(QLabel("QA/QC:"))
        self.card_qa_label = QLabel("Needs Review")
        self.card_qa_label.setStyleSheet("""
            QLabel {
                padding: 5px;
                border-radius: 3px;
                font-weight: bold;
            }
        """)
        qa_layout.addWidget(self.card_qa_label)
        status_layout.addLayout(qa_layout)

        status_layout.addStretch()
        layout.addWidget(status_group)

        # Notes section
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.card_notes_text = QTextEdit()
        self.card_notes_text.setMaximumHeight(100)
        self.card_notes_text.setReadOnly(True)
        notes_layout.addWidget(self.card_notes_text)
        layout.addWidget(notes_group)

        return card

    def create_action_buttons(self):
        """Create action buttons for the card view."""
        self.action_buttons_group = QGroupBox("Actions")
        layout = QHBoxLayout(self.action_buttons_group)

        self.edit_btn = QPushButton("✏️ Edit Entry")
        self.edit_btn.clicked.connect(self.edit_processing_entry)
        layout.addWidget(self.edit_btn)

        self.open_folder_btn = QPushButton("📁 Open Data Folder")
        self.open_folder_btn.clicked.connect(self.open_data_folder)
        layout.addWidget(self.open_folder_btn)

        self.view_mission_btn = QPushButton("🚁 View Mission")
        self.view_mission_btn.clicked.connect(self.view_mission_details)
        layout.addWidget(self.view_mission_btn)

        self.group_info_btn = QPushButton("👥 Group Info")
        self.group_info_btn.clicked.connect(self.show_group_info)
        layout.addWidget(self.group_info_btn)

        layout.addStretch()

    def load_data(self):
        """Load processing data from database."""
        if not db_manager.session:
            self.setEnabled(False)
            self.processing_table.setRowCount(0)
            QMessageBox.warning(self, "Database Error", "No database connection available.")
            return

        self.Processing = db_manager.get_model('processing')
        self.Missions = db_manager.get_model('missions')
        self.Sites = db_manager.get_model('sites')

        if not self.Processing:
            self.setEnabled(False)
            self.processing_table.setRowCount(0)
            QMessageBox.critical(self, "Database Error", "'processing' table not found in the database.")
            return

        self.setEnabled(True)
        self.updating_table = True
        self.edited_cells.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.unsaved_rows.clear()
        self.original_table_data.clear()

        # Load processing data with JOINs
        query = text("""
            SELECT
                p.Process_ID,
                p.Name,
                p.Chassis_SN,
                p.Processed,
                p."QA/QC",
                p.Notes,
                p."Creation Date",
                p.Mission_ID,
                p.Site_ID,
                p.Folder_Path,
                m.date as mission_date,
                s.name as site_name,
                s.location as site_location
            FROM processing p
            LEFT JOIN missions m ON p.Mission_ID = m.id
            LEFT JOIN sites s ON p.Site_ID = s.site_ID
            ORDER BY p."Creation Date" DESC
        """)

        result = db_manager.session.execute(query).fetchall()

        # Set up table
        headers = [
            "ID", "Name", "Chassis SN", "Processed", "QA/QC", "Mission Date",
            "Site", "Created", "Mission ID", "Site ID", "Folder Path"
        ]
        self.processing_table.setColumnCount(len(headers))
        self.processing_table.setHorizontalHeaderLabels(headers)

        # Set custom delegate for Folder Path column to show button
        self.processing_table.setItemDelegateForColumn(10, FolderPathDelegate(self.processing_table))

        # Set up custom sorting for Mission ID column (column 8)
        self.processing_table.setSortingEnabled(True)
        self.processing_table.horizontalHeader().setSortIndicatorShown(True)

        # Rely on custom item types for sorting; no manual header-click rebuild needed

        # Temporarily disable sorting during population to avoid churn
        self.processing_table.setSortingEnabled(False)
        self.processing_table.setRowCount(0)
        self.missions_cache.clear()
        self.sites_cache.clear()

        for row_idx, row in enumerate(result):
            self.processing_table.insertRow(row_idx)

            # Format data
            mission_date = ""
            if row.mission_date:
                if hasattr(row.mission_date, 'strftime'):
                    mission_date = row.mission_date.strftime('%Y-%m-%d')
                else:
                    mission_date = str(row.mission_date)

            created_date = ""
            if row[6]:
                if hasattr(row[6], 'strftime'):
                    created_date = row[6].strftime('%Y-%m-%d')
                else:
                    created_date = str(row[6])
            site_display = f"{row.site_name or ''} ({row.site_location or ''})".strip()
            if site_display == "()":
                site_display = ""

            values = [
                row.Process_ID,
                row.Name or "",
                row.Chassis_SN or "",
                row.Processed or "",
                row[4] or "",  # QA/QC
                mission_date,
                site_display,
                created_date,
                row.Mission_ID or "",
                row.Site_ID or "",
                row.Folder_Path or ""  # Folder Path
            ]

            for col_idx, val in enumerate(values):
                text_val = "" if val is None else str(val)
                # Use specialized items for correct sorting
                if col_idx in (0, 8, 9):  # ID, Mission ID, Site ID
                    item = NumericTableWidgetItem(text_val)
                elif col_idx in (5, 7):  # Mission Date, Created
                    item = DateTableWidgetItem(text_val)
                else:
                    item = QTableWidgetItem(text_val)
                # While updating, do not trigger edit coloring
                self.processing_table.setItem(row_idx, col_idx, item)

                # Color coding for status columns
                if col_idx == 3:  # Processed column
                    self.set_status_color(item, val, "processed")
                elif col_idx == 4:  # QA/QC column
                    self.set_status_color(item, val, "qa")

            # Store original data
            self.original_table_data[row.Process_ID] = {header: str(values[col_idx] or "") for col_idx, header in enumerate(headers)}

            # Cache mission and site data
            if row.Mission_ID:
                self.missions_cache[row.Mission_ID] = {
                    'date': mission_date,
                    'id': row.Mission_ID
                }
            if row.Site_ID:
                self.sites_cache[row.Site_ID] = {
                    'name': row.site_name or "",
                    'location': row.site_location or ""
                }

        self.processing_table.resizeColumnsToContents()
        # Re-enable sorting now that population is complete
        self.processing_table.setSortingEnabled(True)
        self.updating_table = False

        # Update filters
        self.update_filters()

        # Clear card view
        self.clear_card_view()

    # Removed manual sorting methods; relying on QTableWidget built-in sorting with custom items

    def set_status_color(self, item, value, status_type):
        """Set color coding for status columns."""
        if status_type == "processed":
            if value == "Yes":
                item.setBackground(QColor("#d4edda"))  # Light green
                item.setForeground(QColor("#155724"))  # Dark green
            elif value == "No":
                item.setBackground(QColor("#f8d7da"))  # Light red
                item.setForeground(QColor("#721c24"))  # Dark red
            elif value == "Reprocess":
                item.setBackground(QColor("#fff3cd"))  # Light yellow
                item.setForeground(QColor("#856404"))  # Dark yellow
        elif status_type == "qa":
            if value == "Approved":
                item.setBackground(QColor("#d4edda"))  # Light green
                item.setForeground(QColor("#155724"))  # Dark green
            elif value == "Not Approved":
                item.setBackground(QColor("#f8d7da"))  # Light red
                item.setForeground(QColor("#721c24"))  # Dark red
            elif value == "Needs Review":
                item.setBackground(QColor("#cce7ff"))  # Light blue
                item.setForeground(QColor("#004085"))  # Dark blue

    def update_filters(self):
        """Update filter dropdowns with current data."""
        # Update mission filter
        current_mission_selection = self.mission_filter.currentText()
        self.mission_filter.clear()
        self.mission_filter.addItem("All Missions")

        mission_options = set()
        for mission_id, mission_data in self.missions_cache.items():
            if mission_data['date']:
                option = f"Mission {mission_id} ({mission_data['date']})"
                mission_options.add(option)

        for option in sorted(mission_options):
            self.mission_filter.addItem(option)

        # Try to restore previous selection
        if current_mission_selection and current_mission_selection != "All Missions":
            index = self.mission_filter.findText(current_mission_selection)
            if index >= 0:
                self.mission_filter.setCurrentIndex(index)

    def apply_filters(self):
        """Apply current filters to the table view."""
        processed_filter = self.processed_filter.currentText()
        qa_filter = self.qa_filter.currentText()
        mission_filter = self.mission_filter.currentText()

        for row in range(self.processing_table.rowCount()):
            show_row = True

            # Processed filter
            if processed_filter != "All":
                processed_item = self.processing_table.item(row, 3)  # Processed column
                if processed_item and processed_item.text() != processed_filter:
                    show_row = False

            # QA/QC filter
            if qa_filter != "All":
                qa_item = self.processing_table.item(row, 4)  # QA/QC column
                if qa_item and qa_item.text() != qa_filter:
                    show_row = False

            # Mission filter
            if mission_filter != "All Missions":
                mission_item = self.processing_table.item(row, 5)  # Mission Date column
                if mission_item:
                    # Extract mission ID from filter text
                    import re
                    match = re.search(r'Mission (\d+)', mission_filter)
                    if match:
                        filter_mission_id = match.group(1)
                        mission_id_item = self.processing_table.item(row, 8)  # Mission ID column
                        if mission_id_item and mission_id_item.text() != filter_mission_id:
                            show_row = False

            self.processing_table.setRowHidden(row, not show_row)

    def load_processing_to_form(self, row, column):
        """Load processing entry details to the card view."""
        id_item = self.processing_table.item(row, 0)
        if not id_item or not id_item.text():
            return

        db_id_text = id_item.text().strip(' *')
        if db_id_text.startswith(TEMP_ID_PREFIX):
            return  # Don't load details for new unsaved rows

        try:
            processing_id = int(db_id_text)

            # Get data from table
            self.card_name_label.setText(self.processing_table.item(row, 1).text() if self.processing_table.item(row, 1) else "-")
            self.card_chassis_label.setText(self.processing_table.item(row, 2).text() if self.processing_table.item(row, 2) else "-")

            # Mission info
            mission_date = self.processing_table.item(row, 5).text() if self.processing_table.item(row, 5) else ""
            mission_id = self.processing_table.item(row, 8).text() if self.processing_table.item(row, 8) else ""
            if mission_id:
                self.card_mission_label.setText(f"Mission {mission_id}")
            else:
                self.card_mission_label.setText("-")
            self.card_date_label.setText(mission_date if mission_date else "-")

            # Site info
            site_display = self.processing_table.item(row, 6).text() if self.processing_table.item(row, 6) else ""
            self.card_site_label.setText(site_display if site_display else "-")

            # Status
            processed_text = self.processing_table.item(row, 3).text() if self.processing_table.item(row, 3) else "No"
            self.card_processed_label.setText(processed_text)
            self.update_status_color(self.card_processed_label, processed_text, "processed")

            qa_text = self.processing_table.item(row, 4).text() if self.processing_table.item(row, 4) else "Needs Review"
            self.card_qa_label.setText(qa_text)
            self.update_status_color(self.card_qa_label, qa_text, "qa")

            # Created date
            created_text = self.processing_table.item(row, 7).text() if self.processing_table.item(row, 7) else ""
            self.card_created_label.setText(created_text if created_text else "-")

            # Notes (would need to be fetched from database)
            self.card_notes_text.clear()

            # Store current selection
            self.current_selected_processing_id = processing_id

        except (ValueError, Exception) as e:
            QMessageBox.warning(self, "Error", f"Failed to load processing details: {e}")

    def update_status_color(self, label, value, status_type):
        """Update the color of a status label."""
        if status_type == "processed":
            if value == "Yes":
                label.setStyleSheet("QLabel { padding: 5px; border-radius: 3px; font-weight: bold; background-color: #d4edda; color: #155724; }")
            elif value == "No":
                label.setStyleSheet("QLabel { padding: 5px; border-radius: 3px; font-weight: bold; background-color: #f8d7da; color: #721c24; }")
            elif value == "Reprocess":
                label.setStyleSheet("QLabel { padding: 5px; border-radius: 3px; font-weight: bold; background-color: #fff3cd; color: #856404; }")
            else:
                label.setStyleSheet("QLabel { padding: 5px; border-radius: 3px; font-weight: bold; }")
        elif status_type == "qa":
            if value == "Approved":
                label.setStyleSheet("QLabel { padding: 5px; border-radius: 3px; font-weight: bold; background-color: #d4edda; color: #155724; }")
            elif value == "Not Approved":
                label.setStyleSheet("QLabel { padding: 5px; border-radius: 3px; font-weight: bold; background-color: #f8d7da; color: #721c24; }")
            elif value == "Needs Review":
                label.setStyleSheet("QLabel { padding: 5px; border-radius: 3px; font-weight: bold; background-color: #cce7ff; color: #004085; }")
            else:
                label.setStyleSheet("QLabel { padding: 5px; border-radius: 3px; font-weight: bold; }")

    def clear_card_view(self):
        """Clear the card view when no item is selected."""
        self.card_name_label.setText("-")
        self.card_chassis_label.setText("-")
        self.card_mission_label.setText("-")
        self.card_site_label.setText("-")
        self.card_date_label.setText("-")
        self.card_created_label.setText("-")
        self.card_processed_label.setText("No")
        self.card_qa_label.setText("Needs Review")
        self.card_notes_text.clear()
        self.update_status_color(self.card_processed_label, "No", "processed")
        self.update_status_color(self.card_qa_label, "Needs Review", "qa")
        self.current_selected_processing_id = None

    def edit_processing_entry(self):
        """Open edit dialog for the selected processing entry."""
        if not self.current_selected_processing_id:
            QMessageBox.warning(self, "No Selection", "Please select a processing entry to edit.")
            return

        # For now, show a simple message. In a full implementation, this would open a detailed edit dialog
        QMessageBox.information(self, "Edit Entry", f"Edit dialog for processing ID {self.current_selected_processing_id} would open here.")

    def open_data_folder(self):
        """Open the data folder associated with this processing entry."""
        if not self.current_selected_processing_id:
            QMessageBox.warning(self, "No Selection", "Please select a processing entry first.")
            return

        try:
            # Get processing entry details from database
            query = text("""
                SELECT p.Name, p.Chassis_SN, m.date, s.name as site_name
                FROM processing p
                LEFT JOIN missions m ON p.Mission_ID = m.id
                LEFT JOIN sites s ON p.Site_ID = s.site_ID
                WHERE p.Process_ID = :process_id
            """)

            result = db_manager.session.execute(query, {'process_id': self.current_selected_processing_id}).fetchone()

            if result:
                processing_name = result.Name or "Unknown"
                chassis_sn = result.Chassis_SN or "Unknown"
                mission_date = ""
                if result.date:
                    if hasattr(result.date, 'strftime'):
                        mission_date = result.date.strftime('%Y%m%d')
                    else:
                        mission_date = str(result.date)
                else:
                    mission_date = "Unknown"
                site_name = result.site_name or "Unknown"

                # Construct folder path based on naming convention
                # This is a configurable approach - you can modify the path structure as needed
                base_data_path = self.get_base_data_path()

                # Example folder structure: /Data/20250909_Mission1_SiteName/ChassisSN_ProcessingName/
                folder_name = f"{mission_date}_{site_name.replace(' ', '_')}"
                subfolder_name = f"{chassis_sn}_{processing_name.replace(' ', '_')}"

                full_path = os.path.join(base_data_path, folder_name, subfolder_name)

                # Create directory if it doesn't exist
                if not os.path.exists(full_path):
                    os.makedirs(full_path, exist_ok=True)
                    QMessageBox.information(self, "Folder Created",
                                          f"Data folder was created:\n{full_path}\n\nOpening folder...")

                # Open the folder in file explorer
                self.open_folder_in_explorer(full_path)

            else:
                QMessageBox.warning(self, "Data Not Found", "Could not retrieve processing entry details.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open data folder: {str(e)}")

    def get_base_data_path(self):
        """Get the base data storage path. This can be configured as needed."""
        # You can make this configurable through settings or environment variables
        # For now, using a default relative path
        base_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'Data')

        # Ensure the path exists
        if not os.path.exists(base_path):
            os.makedirs(base_path, exist_ok=True)

        return os.path.abspath(base_path)

    def open_folder_in_explorer(self, path):
        """Open a folder in the system's file explorer."""
        try:
            if os.name == 'nt':  # Windows
                os.startfile(path)
            elif os.name == 'posix':  # macOS or Linux
                if sys.platform == 'darwin':  # macOS
                    subprocess.run(['open', path])
                else:  # Linux
                    subprocess.run(['xdg-open', path])
            else:
                QMessageBox.warning(self, "Unsupported OS", "Folder opening is not supported on this operating system.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open folder: {str(e)}")

    def view_mission_details(self):
        """View details of the associated mission."""
        if not self.current_selected_processing_id:
            QMessageBox.warning(self, "No Selection", "Please select a processing entry first.")
            return

        QMessageBox.information(self, "View Mission", f"Mission details for processing ID {self.current_selected_processing_id} would be displayed here.")

    def show_group_info(self):
        """Show information about all missions in the same group as the selected processing entry."""
        if not self.current_selected_processing_id:
            QMessageBox.warning(self, "No Selection", "Please select a processing entry first.")
            return

        try:
            # Get the Mission_ID for this processing entry
            processing = db_manager.session.query(self.Processing).filter_by(
                Process_ID=self.current_selected_processing_id
            ).first()

            if not processing or not processing.Mission_ID:
                QMessageBox.warning(self, "No Mission ID", "This processing entry is not linked to a mission.")
                return

            # Get all missions in the same group
            from app.logic.mission_grouping_service import mission_grouping_service
            group_missions = mission_grouping_service.get_missions_in_group(processing.Mission_ID)

            if not group_missions:
                QMessageBox.information(self, "Group Info", f"No missions found for Mission_ID {processing.Mission_ID}")
                return

            # Create a dialog to show the group information
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Missions in Group {processing.Mission_ID}")
            dialog.setModal(True)
            dialog.resize(800, 400)

            layout = QVBoxLayout(dialog)

            # Header
            header = QLabel(f"Missions grouped under Mission_ID {processing.Mission_ID}:")
            header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
            layout.addWidget(header)

            # Info about grouping criteria
            criteria_label = QLabel("Grouping criteria: Date, Chassis, Customer, Site, Altitude, Speed, Spacing")
            criteria_label.setStyleSheet("font-style: italic; color: #666; margin-bottom: 10px;")
            layout.addWidget(criteria_label)

            # Missions table
            table = QTableWidget()
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.setSortingEnabled(True)
            table.horizontalHeader().setStretchLastSection(True)
            table.verticalHeader().setVisible(False)

            # Set up table headers
            headers = ["Mission ID", "Date", "Platform", "Chassis", "Customer", "Site", "Outcome"]
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)

            # Populate table with group missions
            for mission in group_missions:
                row_idx = table.rowCount()
                table.insertRow(row_idx)

                values = [
                    str(mission['mission_id']),
                    mission['date'],
                    mission['platform'] or "",
                    mission['chassis'] or "",
                    mission['customer'] or "",
                    mission['site'] or "",
                    mission['outcome'] or ""
                ]

                for col_idx, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    table.setItem(row_idx, col_idx, item)

            table.resizeColumnsToContents()
            layout.addWidget(table)

            # Summary info
            summary_label = QLabel(f"Total missions in this group: {len(group_missions)}")
            summary_label.setStyleSheet("margin-top: 10px;")
            layout.addWidget(summary_label)

            # Close button
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            button_layout.addWidget(close_btn)
            layout.addLayout(button_layout)

            dialog.exec_()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to show group information: {e}")

    def create_new_empty_row(self):
        """Create a new empty row for data entry."""
        row_count = self.processing_table.rowCount()
        self.processing_table.insertRow(row_count)
        temp_id = f"{TEMP_ID_PREFIX}{row_count}"
        self.processing_table.setItem(row_count, 0, QTableWidgetItem(temp_id))
        self.processing_table.setItem(row_count, 3, QTableWidgetItem("No"))  # Default Processed status
        self.processing_table.setItem(row_count, 4, QTableWidgetItem("Needs Review"))  # Default QA/QC status
        self.processing_table.setItem(row_count, 7, QTableWidgetItem(datetime.now().strftime('%Y-%m-%d')))  # Creation date
        self.unsaved_rows[temp_id] = True
        self.processing_table.scrollToBottom()

    def show_new_entry_menu(self):
        """Show the enhanced New Entry menu with import options."""
        menu = QMenu(self)

        # Create Empty Entry action
        empty_action = QAction("📝 Create Empty Entry", self)
        empty_action.triggered.connect(self.create_new_empty_row)
        menu.addAction(empty_action)

        # Import from Flight Tracker action
        import_action = QAction("🚁 Import from Flight Tracker", self)
        import_action.triggered.connect(self.show_mission_browser_dialog)
        menu.addAction(import_action)

        # Show menu at toolbar button position
        menu.exec_(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft()))

    def show_mission_browser_dialog(self):
        """Show the Mission Browser Dialog for importing mission data."""
        dialog = MissionBrowserDialog(self.mission_dropdown_cache, self.site_dropdown_cache, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            selected_mission = dialog.get_selected_mission()
            if selected_mission:
                self.create_processing_from_mission(selected_mission)

    def create_processing_from_mission(self, mission_data):
        """Create a new processing entry from selected mission data."""
        row_count = self.processing_table.rowCount()
        self.processing_table.insertRow(row_count)
        temp_id = f"{TEMP_ID_PREFIX}{row_count}"

        # Auto-populate fields from mission data
        mission_id = mission_data.get('id', '')
        mission_date = mission_data.get('date', '')
        chassis = mission_data.get('chassis', '')
        name = f"Mission {mission_id} Processing"

        # Set values in table
        self.processing_table.setItem(row_count, 0, QTableWidgetItem(temp_id))
        self.processing_table.setItem(row_count, 1, QTableWidgetItem(name))  # Name
        self.processing_table.setItem(row_count, 2, QTableWidgetItem(chassis))  # Chassis SN
        self.processing_table.setItem(row_count, 3, QTableWidgetItem("No"))  # Processed
        self.processing_table.setItem(row_count, 4, QTableWidgetItem("Needs Review"))  # QA/QC
        self.processing_table.setItem(row_count, 5, QTableWidgetItem(mission_date))  # Mission Date
        self.processing_table.setItem(row_count, 7, QTableWidgetItem(datetime.now().strftime('%Y-%m-%d')))  # Created
        self.processing_table.setItem(row_count, 8, QTableWidgetItem(str(mission_id)))  # Mission ID

        # Mark as unsaved
        self.unsaved_rows[temp_id] = True
        self.processing_table.scrollToBottom()

        QMessageBox.information(self, "Entry Created",
                              f"New processing entry created for Mission {mission_id}.\n\n"
                              f"You can now set the data folder path and save the entry.")

    def save_edits(self):
        """Save all pending edits."""
        if not self.edited_cells and not self.unsaved_rows:
            QMessageBox.information(self, "No Changes", "There are no pending changes to save.")
            return

        try:
            saved_count = 0

            # Handle new rows first
            for temp_id in list(self.unsaved_rows.keys()):
                row_idx = -1
                for i in range(self.processing_table.rowCount()):
                    item = self.processing_table.item(i, 0)
                    if item and item.text() == temp_id:
                        row_idx = i
                        break

                if row_idx == -1:
                    continue

                # Skip empty rows
                if not self._is_row_has_data(row_idx):
                    continue

                headers = [self.processing_table.horizontalHeaderItem(c).text()
                         for c in range(self.processing_table.columnCount())]
                processing_data = {}

                for col, header in enumerate(headers):
                    if header == 'ID':
                        continue

                    item = self.processing_table.item(row_idx, col)
                    if not item:
                        continue

                    text = item.text().strip()
                    col_name = header.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')

                    # Handle different data types
                    if not text:
                        processing_data[col_name] = None
                    elif header == 'Created':
                        try:
                            processing_data[col_name] = datetime.strptime(text, '%Y-%m-%d').date()
                        except ValueError:
                            processing_data[col_name] = datetime.now().date()
                    elif header in ['Mission ID', 'Site ID']:
                        try:
                            processing_data[col_name] = int(text) if text else None
                        except ValueError:
                            processing_data[col_name] = None
                    else:
                        processing_data[col_name] = text

                try:
                    new_processing = self.Processing(**processing_data)
                    db_manager.session.add(new_processing)
                    saved_count += 1

                    # Update the temp ID to real ID
                    db_manager.session.flush()
                    self.processing_table.item(row_idx, 0).setText(str(new_processing.Process_ID))

                except Exception as e:
                    db_manager.session.rollback()
                    QMessageBox.warning(self, "Save Error",
                                     f"Failed to save row {row_idx + 1}: {str(e)}")

            # Handle cell edits for existing processing entries
            for (row, col), new_value in self.edited_cells.items():
                db_id_item = self.processing_table.item(row, 0)
                if not db_id_item or db_id_item.text().startswith(TEMP_ID_PREFIX):
                    continue

                try:
                    db_id = int(db_id_item.text().strip(' *'))
                    column_name = self.processing_table.horizontalHeaderItem(col).text().lower().replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')
                    processing = db_manager.session.query(self.Processing).filter_by(Process_ID=db_id).first()

                    if processing:
                        # Convert value to appropriate type
                        if column_name == 'created':
                            new_value = datetime.strptime(new_value, '%Y-%m-%d').date() if new_value else datetime.now().date()
                        elif column_name in ['mission_id', 'site_id']:
                            try:
                                new_value = int(new_value) if new_value else None
                            except (ValueError, TypeError):
                                new_value = None

                        setattr(processing, column_name, new_value)
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
                self.load_data()  # Refresh the table
            else:
                QMessageBox.information(self, "No Valid Changes", "No valid changes were found to save.")

        except Exception as e:
            db_manager.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save changes: {e}")

    def delete_selected(self):
        """Delete the selected processing entry."""
        selected_rows = sorted(list(set(index.row() for index in self.processing_table.selectedIndexes())), reverse=True)
        if not selected_rows:
            return

        reply = QMessageBox.question(self, "Confirm Deletion", "Delete selected processing entry(ies)?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                deleted_count = 0
                for row in selected_rows:
                    id_item = self.processing_table.item(row, 0)
                    if id_item.text().startswith(TEMP_ID_PREFIX):
                        # Just remove from table for unsaved rows
                        self.processing_table.removeRow(row)
                        if id_item.text() in self.unsaved_rows:
                            del self.unsaved_rows[id_item.text()]
                    else:
                        db_id = int(id_item.text().strip(' *'))
                        processing = db_manager.session.query(self.Processing).filter_by(Process_ID=db_id).first()
                        if processing:
                            db_manager.session.delete(processing)
                            deleted_count += 1

                if deleted_count > 0:
                    db_manager.session.commit()
                    QMessageBox.information(self, "Success", f"Successfully deleted {deleted_count} processing entry(ies).")
                    self.load_data()  # Refresh the table
                else:
                    QMessageBox.information(self, "No Changes", "No entries were deleted.")

            except Exception as e:
                db_manager.session.rollback()
                QMessageBox.critical(self, "Error", f"Failed to delete entries: {e}")

    def cell_pressed_for_edit(self, row, column):
        """Handle cell press for edit tracking."""
        if not self.updating_table:
            item = self.processing_table.item(row, column)
            self.current_edit_original_value = item.text() if item else ""

    def cell_was_edited(self, row, column):
        """Handle cell editing."""
        if self.updating_table or self.is_undoing or self.is_redoing:
            return

        current_item = self.processing_table.item(row, column)
        new_value = current_item.text() if current_item else ""

        if new_value == self.current_edit_original_value:
            return

        db_id_item = self.processing_table.item(row, 0)
        db_id = db_id_item.text()
        column_name = self.processing_table.horizontalHeaderItem(column).text()

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

    def populate_dropdown_caches(self):
        """Populate dropdown caches with mission and site data."""
        try:
            # Populate mission dropdown cache
            if self.Missions:
                missions = db_manager.session.query(self.Missions).all()
                self.mission_dropdown_cache = {}
                for mission in missions:
                    mission_date = ""
                    if mission.date:
                        if hasattr(mission.date, 'strftime'):
                            mission_date = mission.date.strftime('%Y-%m-%d')
                        else:
                            mission_date = str(mission.date)
                    display_text = f"Mission {mission.id}"
                    if mission_date:
                        display_text += f" ({mission_date})"
                    self.mission_dropdown_cache[mission.id] = display_text

            # Populate site dropdown cache
            if self.Sites:
                sites = db_manager.session.query(self.Sites).all()
                self.site_dropdown_cache = {}
                for site in sites:
                    display_text = site.name or "Unknown"
                    if site.location:
                        display_text += f" ({site.location})"
                    self.site_dropdown_cache[site.site_ID] = display_text

        except Exception as e:
            print(f"Error populating dropdown caches: {e}")

    def _is_row_has_data(self, row_idx):
        """Check if a row has any non-empty data cells (excluding ID column)."""
        for col in range(1, self.processing_table.columnCount()):
            item = self.processing_table.item(row_idx, col)
            if item and item.text().strip():
                return True
        return False

    def undo_last_edit(self):
        """Undo the last edit."""
        if not self.undo_stack:
            return

        try:
            self.is_undoing = True
            last_edit = self.undo_stack.pop()
            self.redo_stack.append(last_edit)

            row, col = last_edit['row'], last_edit['column']
            old_value = last_edit['old_value']

            # Update the cell value
            self.processing_table.item(row, col).setText(old_value)

            # Remove from edited cells if it reverts to original
            if (row, col) in self.edited_cells:
                del self.edited_cells[(row, col)]

            # Reset background color
            self.processing_table.item(row, col).setBackground(QColor())

            # Update asterisk in ID column if no more edits in this row
            id_item = self.processing_table.item(row, 0)
            if id_item:
                db_id = id_item.text().strip(' *')
                has_edits = any((row, c) in self.edited_cells for c in range(1, self.processing_table.columnCount()))
                if not has_edits:
                    id_item.setText(db_id)
                else:
                    id_item.setText(f"{db_id} *")

        except Exception as e:
            QMessageBox.warning(self, "Undo Error", f"Failed to undo edit: {e}")
        finally:
            self.is_undoing = False

    def redo_last_edit(self):
        """Redo the last undone edit."""
        if not self.redo_stack:
            return

        try:
            self.is_redoing = True
            last_undone_edit = self.redo_stack.pop()
            self.undo_stack.append(last_undone_edit)

            row, col = last_undone_edit['row'], last_undone_edit['column']
            new_value = last_undone_edit['new_value']

            # Update the cell value
            self.processing_table.item(row, col).setText(new_value)

            # Add back to edited cells
            self.edited_cells[(row, col)] = new_value

            # Set background color
            self.processing_table.item(row, col).setBackground(QColor("#d08770"))

            # Update asterisk in ID column
            id_item = self.processing_table.item(row, 0)
            if id_item and not id_item.text().endswith(' *'):
                db_id = id_item.text().strip(' *')
                id_item.setText(f"{db_id} *")

        except Exception as e:
            QMessageBox.warning(self, "Redo Error", f"Failed to redo edit: {e}")
        finally:
            self.is_redoing = False

    def handle_cell_double_click(self, row, column):
        """Handle double-click on table cells to show appropriate editors."""
        column_name = self.processing_table.horizontalHeaderItem(column).text()

        # Show dropdown for Mission ID column
        if column_name == "Mission ID":
            self.show_mission_dropdown(row, column)
        # Show dropdown for Site ID column
        elif column_name == "Site ID":
            self.show_site_dropdown(row, column)
        # Show dropdown for Processed column
        elif column_name == "Processed":
            self.show_processed_dropdown(row, column)
        # Show dropdown for QA/QC column
        elif column_name == "QA/QC":
            self.show_qa_dropdown(row, column)

    def show_mission_dropdown(self, row, column):
        """Show dropdown for mission selection."""
        if not self.mission_dropdown_cache:
            QMessageBox.warning(self, "No Data", "No mission data available.")
            return

        # Create dropdown widget
        combo = QComboBox()
        combo.addItem("")  # Empty option

        # Add mission options
        mission_options = []
        for mission_id, display_text in self.mission_dropdown_cache.items():
            mission_options.append((mission_id, display_text))

        # Sort by mission ID
        mission_options.sort(key=lambda x: x[0])

        for mission_id, display_text in mission_options:
            combo.addItem(display_text, mission_id)

        # Set current value if exists
        current_item = self.processing_table.item(row, column)
        if current_item:
            current_text = current_item.text().strip()
            if current_text:
                try:
                    current_id = int(current_text)
                    for i in range(combo.count()):
                        if combo.itemData(i) == current_id:
                            combo.setCurrentIndex(i)
                            break
                except ValueError:
                    pass

        # Position and show dropdown
        rect = self.processing_table.visualItemRect(self.processing_table.item(row, column))
        combo.setGeometry(rect)
        combo.setParent(self.processing_table)
        combo.show()
        combo.setFocus()

        # Connect to update function
        combo.currentIndexChanged.connect(lambda: self.update_cell_from_dropdown(row, column, combo))

    def show_site_dropdown(self, row, column):
        """Show dropdown for site selection."""
        if not self.site_dropdown_cache:
            QMessageBox.warning(self, "No Data", "No site data available.")
            return

        # Create dropdown widget
        combo = QComboBox()
        combo.addItem("")  # Empty option

        # Add site options
        site_options = []
        for site_id, display_text in self.site_dropdown_cache.items():
            site_options.append((site_id, display_text))

        # Sort by site name
        site_options.sort(key=lambda x: x[1])

        for site_id, display_text in site_options:
            combo.addItem(display_text, site_id)

        # Set current value if exists
        current_item = self.processing_table.item(row, column)
        if current_item:
            current_text = current_item.text().strip()
            if current_text:
                try:
                    current_id = int(current_text)
                    for i in range(combo.count()):
                        if combo.itemData(i) == current_id:
                            combo.setCurrentIndex(i)
                            break
                except ValueError:
                    pass

        # Position and show dropdown
        rect = self.processing_table.visualItemRect(self.processing_table.item(row, column))
        combo.setGeometry(rect)
        combo.setParent(self.processing_table)
        combo.show()
        combo.setFocus()

        # Connect to update function
        combo.currentIndexChanged.connect(lambda: self.update_cell_from_dropdown(row, column, combo))

    def show_processed_dropdown(self, row, column):
        """Show dropdown for processed status."""
        combo = QComboBox()
        combo.addItem("Yes")
        combo.addItem("No")
        combo.addItem("Reprocess")

        # Set current value
        current_item = self.processing_table.item(row, column)
        if current_item:
            current_text = current_item.text().strip()
            index = combo.findText(current_text)
            if index >= 0:
                combo.setCurrentIndex(index)

        # Position and show dropdown
        rect = self.processing_table.visualItemRect(self.processing_table.item(row, column))
        combo.setGeometry(rect)
        combo.setParent(self.processing_table)
        combo.show()
        combo.setFocus()

        # Connect to update function
        combo.currentIndexChanged.connect(lambda: self.update_cell_from_dropdown(row, column, combo))

    def show_qa_dropdown(self, row, column):
        """Show dropdown for QA/QC status."""
        combo = QComboBox()
        combo.addItem("Needs Review")
        combo.addItem("Approved")
        combo.addItem("Not Approved")

        # Set current value
        current_item = self.processing_table.item(row, column)
        if current_item:
            current_text = current_item.text().strip()
            index = combo.findText(current_text)
            if index >= 0:
                combo.setCurrentIndex(index)

        # Position and show dropdown
        rect = self.processing_table.visualItemRect(self.processing_table.item(row, column))
        combo.setGeometry(rect)
        combo.setParent(self.processing_table)
        combo.show()
        combo.setFocus()

        # Connect to update function
        combo.currentIndexChanged.connect(lambda: self.update_cell_from_dropdown(row, column, combo))

    def update_cell_from_dropdown(self, row, column, combo):
        """Update cell value from dropdown selection."""
        selected_text = combo.currentText()
        selected_data = combo.currentData()

        # For Mission ID and Site ID, store the ID but display the text
        column_name = self.processing_table.horizontalHeaderItem(column).text()
        if column_name in ["Mission ID", "Site ID"] and selected_data is not None:
            # Store the ID in the cell
            display_text = str(selected_data) if selected_data else ""
        else:
            # For other columns, use the display text
            display_text = selected_text

        # Update the cell
        item = self.processing_table.item(row, column)
        if item:
            item.setText(display_text)

            # Trigger the edit handler
            self.cell_was_edited(row, column)

        # Close the dropdown
        combo.hide()
        combo.setParent(None)


class MissionBrowserDialog(QDialog):
    """Dialog for browsing and selecting missions to import for processing."""

    def __init__(self, mission_cache, site_cache, parent=None):
        super().__init__(parent)
        self.mission_cache = mission_cache
        self.site_cache = site_cache
        self.selected_mission = None

        self.setWindowTitle("Select Mission for Processing")
        self.setModal(True)
        self.resize(800, 600)

        self.setup_ui()
        self.load_missions()

    def setup_ui(self):
        """Set up the dialog user interface."""
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Select a mission to create a processing entry:")
        header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)

        # Search/Filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by mission ID, date, or platform...")
        self.search_input.textChanged.connect(self.filter_missions)
        filter_layout.addWidget(self.search_input)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Missions table
        self.missions_table = QTableWidget()
        self.missions_table.setAlternatingRowColors(True)
        self.missions_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.missions_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.missions_table.setSortingEnabled(True)
        self.missions_table.horizontalHeader().setStretchLastSection(True)
        self.missions_table.verticalHeader().setVisible(False)

        # Set up table headers
        headers = ["Mission ID", "Date", "Platform", "Chassis", "Site"]
        self.missions_table.setColumnCount(len(headers))
        self.missions_table.setHorizontalHeaderLabels(headers)

        layout.addWidget(self.missions_table)

        # Mission details preview
        details_group = QGroupBox("Mission Details")
        details_layout = QVBoxLayout(details_group)

        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(100)
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)

        layout.addWidget(details_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.select_btn = QPushButton("Select Mission")
        self.select_btn.clicked.connect(self.select_mission)
        self.select_btn.setEnabled(False)
        button_layout.addWidget(self.select_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Connect signals
        self.missions_table.itemSelectionChanged.connect(self.update_details)
        self.missions_table.itemDoubleClicked.connect(self.select_mission)

    def load_missions(self):
        """Load missions into the table."""
        self.missions_table.setRowCount(0)

        # Get mission data from database with JOIN to sites
        try:
            from app.database.manager import db_manager
            from sqlalchemy import text

            if db_manager.session:
                # Query to get missions with site information
                query = text("""
                    SELECT
                        m.id,
                        m.date,
                        m.platform,
                        m.chassis,
                        m.site,
                        s.name as site_name,
                        s.location as site_location
                    FROM missions m
                    LEFT JOIN sites s ON m.site = s.site_ID
                    ORDER BY m.date DESC, m.id DESC
                """)

                result = db_manager.session.execute(query).fetchall()

                for row in result:
                    row_idx = self.missions_table.rowCount()
                    self.missions_table.insertRow(row_idx)

                    # Format mission data
                    mission_date = ""
                    if row.date:
                        if hasattr(row.date, 'strftime'):
                            mission_date = row.date.strftime('%Y-%m-%d')
                        else:
                            mission_date = str(row.date)

                    # Format site display
                    site_display = ""
                    if row.site_name:
                        site_display = row.site_name
                        if row.site_location:
                            site_display += f" ({row.site_location})"

                    # Set table values
                    values = [
                        str(row.id),
                        mission_date,
                        row.platform or "",
                        row.chassis or "",
                        site_display
                    ]

                    for col_idx, value in enumerate(values):
                        item = QTableWidgetItem(value)
                        self.missions_table.setItem(row_idx, col_idx, item)

                    # Store mission data in first column for retrieval
                    self.missions_table.item(row_idx, 0).setData(Qt.UserRole, {
                        'id': row.id,
                        'date': mission_date,
                        'platform': row.platform or "",
                        'chassis': row.chassis or "",
                        'site': site_display,
                        'site_id': row.site
                    })

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load missions: {e}")
            print(f"Mission loading error: {e}")

        self.missions_table.resizeColumnsToContents()

    def filter_missions(self):
        """Filter missions based on search text."""
        search_text = self.search_input.text().lower()

        for row in range(self.missions_table.rowCount()):
            show_row = True

            if search_text:
                # Check if any column contains the search text
                row_text = ""
                for col in range(self.missions_table.columnCount()):
                    item = self.missions_table.item(row, col)
                    if item:
                        row_text += item.text().lower() + " "

                if search_text not in row_text:
                    show_row = False

            self.missions_table.setRowHidden(row, not show_row)

    def update_details(self):
        """Update the mission details preview."""
        selected_rows = self.missions_table.selectionModel().selectedRows()
        if not selected_rows:
            self.details_text.clear()
            self.select_btn.setEnabled(False)
            return

        row = selected_rows[0].row()
        mission_data = self.missions_table.item(row, 0).data(Qt.UserRole)

        if mission_data:
            details = f"""
Mission ID: {mission_data['id']}
Date: {mission_data['date']}
Platform: {mission_data['platform']}
Chassis: {mission_data['chassis']}
Site: {mission_data['site']}
"""
            self.details_text.setPlainText(details.strip())
            self.select_btn.setEnabled(True)
        else:
            self.details_text.clear()
            self.select_btn.setEnabled(False)

    def select_mission(self):
        """Select the currently highlighted mission."""
        selected_rows = self.missions_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a mission first.")
            return

        row = selected_rows[0].row()
        mission_data = self.missions_table.item(row, 0).data(Qt.UserRole)

        if mission_data:
            self.selected_mission = mission_data
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Could not retrieve mission data.")

    def get_selected_mission(self):
        """Get the selected mission data."""
        return self.selected_mission


class FolderPathDelegate(QStyledItemDelegate):
    """Custom delegate to display a button for folder path selection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_table = parent

    def paint(self, painter, option, index):
        """Paint the button in the cell."""
        # Get the current folder path
        folder_path = index.data(Qt.DisplayRole) or ""

        # Create button appearance
        button_text = "📁 Set Folder" if not folder_path else f"📁 {os.path.basename(folder_path) if folder_path else 'Set Folder'}"

        # Draw button-like background
        painter.fillRect(option.rect, QColor("#e3f2fd"))  # Light blue background

        # Draw border
        painter.setPen(QColor("#1976d2"))
        painter.drawRect(option.rect.adjusted(0, 0, -1, -1))

        # Draw text
        painter.setPen(QColor("#0d47a1"))
        painter.drawText(option.rect, Qt.AlignCenter, button_text)

    def editorEvent(self, event, model, option, index):
        """Handle mouse events on the button."""
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self.show_folder_dialog(index)
            return True
        return super().editorEvent(event, model, option, index)

    def show_folder_dialog(self, index):
        """Show folder selection dialog and update the cell."""
        # Get current folder path if any
        current_path = index.data(Qt.DisplayRole) or ""

        # Open folder selection dialog
        folder_path = QFileDialog.getExistingDirectory(
            self.parent_table,
            "Select Data Folder",
            current_path or os.path.expanduser("~")
        )

        if folder_path:
            # Update the model data
            model = index.model()
            model.setData(index, folder_path, Qt.EditRole)

            # Trigger edit handling
            if hasattr(self.parent_table, 'parent') and hasattr(self.parent_table.parent(), 'cell_was_edited'):
                self.parent_table.parent().cell_was_edited(index.row(), index.column())
