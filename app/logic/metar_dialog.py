"""
Enhanced METAR Selection Dialog

This dialog allows users to:
1. Enter date, time, timezone, and ICAO station
2. Fetch METAR data for a time range
3. Select from multiple METAR observations
4. Return the selected METAR to the mission editor
"""

import pytz
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QProgressBar, QMessageBox, QDateEdit, QTimeEdit, QGroupBox,
    QFormLayout, QSplitter, QTextEdit
)
from PyQt5.QtCore import Qt, QDate, QTime, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from .metar_service import metar_service


class MetarFetchWorker(QThread):
    """Worker thread for fetching METAR data around a specific time."""
    finished = pyqtSignal(list)  # Emits list of (timestamp, metar) tuples
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, station_code: str, target_time_utc: datetime, hours_window: int = 2):
        super().__init__()
        self.station_code = station_code
        self.target_time_utc = target_time_utc
        self.hours_window = hours_window

    def run(self):
        try:
            self.progress.emit("Fetching METAR data around specified time...")

            # Fetch METAR data around the target time (only hourly observations)
            metars = metar_service.get_metars_around_time(
                self.station_code,
                self.target_time_utc,
                self.hours_window
            )

            self.progress.emit(f"Found {len(metars)} hourly METAR observations")
            self.finished.emit(metars)

        except Exception as e:
            self.error.emit(str(e))


class MetarSelectionDialog(QDialog):
    """Dialog for selecting METAR data from a range of observations."""

    def __init__(self, parent=None, prefill_station: str = "", prefill_date: datetime = None):
        super().__init__(parent)
        self.selected_metar = None
        self.prefill_station = prefill_station
        self.prefill_date = prefill_date or datetime.now()
        self.timezone_str = 'UTC'  # Default timezone

        self.setWindowTitle("Select METAR Data")
        self.setModal(True)
        self.setMinimumSize(800, 600)

        self.setup_ui()
        self.connect_signals()

        # Prefill values if provided
        if self.prefill_station:
            self.station_input.setText(self.prefill_station)
        if self.prefill_date:
            self.date_input.setDate(QDate(self.prefill_date.year, self.prefill_date.month, self.prefill_date.day))
            self.time_input.setTime(QTime(self.prefill_date.hour, self.prefill_date.minute))

    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("METAR Data Selection")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # Input section
        input_group = QGroupBox("Search Parameters")
        input_layout = QFormLayout(input_group)

        # Date and time inputs
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        input_layout.addRow("Date:", self.date_input)

        self.time_input = QTimeEdit()
        self.time_input.setTime(QTime.currentTime())
        input_layout.addRow("Time:", self.time_input)

        # Timezone selection
        self.timezone_combo = QComboBox()
        timezones = [
            'UTC', 'US/Eastern', 'US/Central', 'US/Mountain', 'US/Pacific',
            'US/Alaska', 'US/Hawaii', 'Europe/London', 'Europe/Paris',
            'Asia/Tokyo', 'Australia/Sydney'
        ]
        self.timezone_combo.addItems(timezones)
        self.timezone_combo.setCurrentText('UTC')
        input_layout.addRow("Timezone:", self.timezone_combo)

        # Station input
        self.station_input = QLineEdit()
        self.station_input.setPlaceholderText("e.g., KJFK, KLAX, KORD")
        input_layout.addRow("ICAO Station:", self.station_input)

        layout.addWidget(input_group)

        # Fetch button
        self.fetch_button = QPushButton("Fetch METAR Data")
        self.fetch_button.setStyleSheet("QPushButton { background-color: #17a2b8; color: white; padding: 8px; } QPushButton:hover { background-color: #138496; }")
        layout.addWidget(self.fetch_button)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Results section
        results_group = QGroupBox("METAR Observations")
        results_layout = QVBoxLayout(results_group)

        # METAR table
        self.metar_table = QTableWidget()
        self.metar_table.setColumnCount(3)
        # Set initial header - will be updated when timezone is selected
        self.metar_table.setHorizontalHeaderLabels(["Time (UTC)", "METAR", "Select"])
        self.metar_table.setAlternatingRowColors(True)
        self.metar_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.metar_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.metar_table.horizontalHeader().setStretchLastSection(True)
        results_layout.addWidget(self.metar_table)

        # Selected METAR preview
        preview_group = QGroupBox("Selected METAR")
        preview_layout = QVBoxLayout(preview_group)

        self.selected_metar_display = QTextEdit()
        self.selected_metar_display.setMaximumHeight(60)
        self.selected_metar_display.setReadOnly(True)
        self.selected_metar_display.setPlaceholderText("Click 'Select' on a METAR observation above to preview it here")
        preview_layout.addWidget(self.selected_metar_display)

        results_layout.addWidget(preview_group)

        layout.addWidget(results_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.select_button = QPushButton("Use Selected METAR")
        self.select_button.setEnabled(False)
        self.select_button.setStyleSheet("QPushButton { background-color: #28a745; color: white; } QPushButton:hover { background-color: #218838; }")

        cancel_button = QPushButton("Cancel")

        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(self.select_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # Connect buttons
        self.select_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

    def connect_signals(self):
        """Connect widget signals."""
        self.fetch_button.clicked.connect(self.fetch_metar_data)
        self.metar_table.itemSelectionChanged.connect(self.on_metar_selected)

    def fetch_metar_data(self):
        """Fetch METAR data for the specified parameters."""
        station = self.station_input.text().strip().upper()
        if not station:
            QMessageBox.warning(self, "Missing Station", "Please enter an ICAO station code.")
            return

        # Get date and time
        date = self.date_input.date().toPyDate()
        time = self.time_input.time()
        timezone_str = self.timezone_combo.currentText()

        # Store timezone for use in other methods
        self.timezone_str = timezone_str

        # Convert to UTC
        try:
            local_tz = pytz.timezone(timezone_str)
            local_dt = local_tz.localize(datetime.combine(date, time.toPyTime()))
            utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
        except Exception as e:
            QMessageBox.warning(self, "Timezone Error", f"Error converting timezone: {e}")
            return

        # Show progress
        self.progress_bar.setVisible(True)
        self.fetch_button.setEnabled(False)
        self.fetch_button.setText("Fetching...")

        # Start worker thread
        self.worker = MetarFetchWorker(station, utc_dt)
        self.worker.finished.connect(self.on_metar_data_received)
        self.worker.error.connect(self.on_metar_error)
        self.worker.progress.connect(self.on_progress_update)
        self.worker.start()

    def on_metar_data_received(self, metars):
        """Handle received METAR data."""
        self.progress_bar.setVisible(False)
        self.fetch_button.setEnabled(True)
        self.fetch_button.setText("Fetch METAR Data")

        # Update table header to show selected timezone
        timezone_display = self.timezone_str.replace('/', '/').replace('_', ' ')
        if self.timezone_str == 'UTC':
            header_label = "Time (UTC)"
        else:
            header_label = f"Time ({timezone_display})"
        self.metar_table.setHorizontalHeaderLabels([header_label, "METAR", "Select"])

        # Clear existing data
        self.metar_table.setRowCount(0)

        if not metars:
            QMessageBox.information(self, "No Data", "No METAR data found for the specified time range.")
            return

        # Populate table
        self.metar_table.setRowCount(len(metars))

        for row, (timestamp, metar) in enumerate(metars):
            # Parse timestamp - Iowa Mesonet format is typically 'YYYY-MM-DD HH:MM'
            try:
                if 'T' in timestamp:
                    dt_utc = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                else:
                    dt_utc = datetime.strptime(timestamp, '%Y-%m-%d %H:%M')

                # Ensure the UTC datetime is properly timezone-aware
                if dt_utc.tzinfo is None:
                    dt_utc = pytz.UTC.localize(dt_utc)

                # Convert UTC to user's selected timezone for display
                user_tz = pytz.timezone(self.timezone_str)
                dt_user = dt_utc.astimezone(user_tz)

                # Calculate the timezone offset
                offset = dt_user.utcoffset()
                offset_hours = offset.total_seconds() / 3600
                offset_str = f"{'+' if offset_hours >= 0 else ''}{offset_hours:+.0f}"

                # Show time in user's timezone with offset
                time_str = dt_user.strftime('%Y-%m-%d %I:%M %p')
                timezone_name = dt_user.strftime('%Z')
                utc_str = dt_utc.strftime('%H:%MZ')

                # Combine both for clarity with timezone info
                display_time = f"{time_str} {timezone_name}\n(UTC: {utc_str})"

            except Exception as e:
                # Fallback if timezone conversion fails
                display_time = timestamp

            # Time column - show in user's timezone
            time_item = QTableWidgetItem(display_time)
            time_item.setToolTip(f"UTC Time: {timestamp}")
            self.metar_table.setItem(row, 0, time_item)

            # METAR column - show actual METAR data (contains UTC time)
            metar_item = QTableWidgetItem(metar)
            metar_item.setToolTip(f"Full METAR: {metar}")  # Show full METAR on hover
            self.metar_table.setItem(row, 1, metar_item)

            # Select button column
            select_button = QPushButton("Select")
            select_button.clicked.connect(lambda checked, r=row, m=metar: self.select_metar(r, m))
            self.metar_table.setCellWidget(row, 2, select_button)

        # Resize columns
        self.metar_table.resizeColumnsToContents()
        self.metar_table.horizontalHeader().setStretchLastSection(True)

        # Select first row by default
        if metars:
            self.metar_table.selectRow(0)
            self.select_metar(0, metars[0][1])

    def on_metar_error(self, error_msg):
        """Handle METAR fetch error."""
        self.progress_bar.setVisible(False)
        self.fetch_button.setEnabled(True)
        self.fetch_button.setText("Fetch METAR Data")

        QMessageBox.critical(self, "Fetch Error", f"Failed to fetch METAR data:\n\n{error_msg}")

    def on_progress_update(self, message):
        """Update progress message."""
        self.progress_bar.setFormat(message)

    def on_metar_selected(self):
        """Handle METAR selection in table."""
        current_row = self.metar_table.currentRow()
        if current_row >= 0:
            metar_item = self.metar_table.item(current_row, 1)
            if metar_item:
                self.selected_metar_display.setPlainText(metar_item.text())

    def select_metar(self, row, metar):
        """Select a specific METAR observation."""
        self.selected_metar = metar
        self.selected_metar_display.setPlainText(metar)
        self.select_button.setEnabled(True)

        # Highlight selected row
        self.metar_table.selectRow(row)

    def get_selected_metar(self):
        """Get the selected METAR string."""
        return self.selected_metar


def show_metar_selection_dialog(parent=None, station: str = "", date: datetime = None) -> str:
    """
    Show the METAR selection dialog and return the selected METAR.

    Args:
        parent: Parent widget
        station: Prefill station code
        date: Prefill date/time

    Returns:
        Selected METAR string or empty string if cancelled
    """
    dialog = MetarSelectionDialog(parent, station, date)
    result = dialog.exec_()

    if result == QDialog.Accepted:
        return dialog.get_selected_metar() or ""
    else:
        return ""
