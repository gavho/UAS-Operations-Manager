from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QDateEdit,
    QTextEdit, QFormLayout, QWidget
)
from PyQt5.QtCore import Qt, QDate

from app.logic.battery_manager import (
    add_battery, get_all_batteries, increment_cycle_count, delete_battery
)


class BatteryDialog(QDialog):
    """Dialog for managing battery inventory."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Battery Inventory")
        self.setMinimumSize(900, 700)
        self.setup_ui()
        self.load_batteries()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Form to add new battery
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)

        self.name_edit = QLineEdit()
        self.serial_edit = QLineEdit()
        self.purchase_date_edit = QDateEdit(QDate.currentDate())
        self.purchase_date_edit.setCalendarPopup(True)
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)

        form_layout.addRow("Battery Name:", self.name_edit)
        form_layout.addRow("Serial Number:", self.serial_edit)
        form_layout.addRow("Purchase Date:", self.purchase_date_edit)
        form_layout.addRow("Notes:", self.notes_edit)

        add_btn = QPushButton("Add Battery")
        add_btn.clicked.connect(self.add_battery_entry)
        form_layout.addWidget(add_btn)

        # Table of batteries
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "Serial #", "Acquired", "Cycles", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        layout.addWidget(form_widget)
        layout.addWidget(QLabel("Batteries:"))
        layout.addWidget(self.table)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignRight)

        # no model filter; showing all batteries

    def add_battery_entry(self):
        try:
            name = self.name_edit.text().strip()
            serial = self.serial_edit.text().strip()
            purchase_date = self.purchase_date_edit.date().toString("yyyy-MM-dd")
            notes = self.notes_edit.toPlainText().strip() or None
            if not name or not serial:
                QMessageBox.warning(self, "Error", "Battery name and serial number are required.")
                return
            add_battery(name=name, battery_sn=serial, acquisition_date=purchase_date, notes=notes, initial_cycles=0)
            # reset relevant fields
            self.name_edit.clear()
            self.serial_edit.clear()
            self.notes_edit.clear()
            self.load_batteries()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not add battery: {e}")

    def load_batteries(self):
        self.table.setRowCount(0)
        batteries = get_all_batteries()
        for row, b in enumerate(batteries):
            self.table.insertRow(row)
            bid = b.get('battery_id') or b.get('id')
            name = b.get('name') or ''
            serial = b.get('battery_sn') or ''
            acquired = b.get('acquisition_date') or ''
            cycles = b.get('cycle_count')

            self.table.setItem(row, 0, QTableWidgetItem(str(bid)))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.setItem(row, 2, QTableWidgetItem(serial))
            self.table.setItem(row, 3, QTableWidgetItem(str(acquired)))
            self.table.setItem(row, 4, QTableWidgetItem(str(cycles)))

            # Actions: Increment + Delete
            actions = QWidget()
            hl = QHBoxLayout(actions)
            hl.setContentsMargins(0, 0, 0, 0)
            inc_btn = QPushButton("+ Cycle")
            inc_btn.clicked.connect(lambda _, x=bid: self.increment_cycle(x))
            del_btn = QPushButton("Delete")
            del_btn.clicked.connect(lambda _, x=bid: self.delete_battery_entry(x))
            hl.addWidget(inc_btn)
            hl.addWidget(del_btn)
            actions.setLayout(hl)
            self.table.setCellWidget(row, 5, actions)

    def increment_cycle(self, battery_id):
        if not battery_id:
            return
        try:
            increment_cycle_count(battery_id)
            self.load_batteries()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not increment cycle: {e}")

    def delete_battery_entry(self, battery_id):
        if not battery_id:
            return
        if QMessageBox.question(self, "Confirm Delete", "Delete this battery?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                delete_battery(battery_id)
                self.load_batteries()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete battery: {e}")
