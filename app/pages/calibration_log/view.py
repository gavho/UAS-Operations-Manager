from PyQt5.QtCore import Qt, pyqtSignal, QDate
from PyQt5.QtWidgets import QDialog, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QToolBar, QAction, QMessageBox, QHeaderView, QLabel, QFileDialog
import os
import re
from app.logic.cert_importer import parse_calibration_certificate, extract_merge_fields
from app.database.manager import db_manager
from app.pages.calibration_log.dialog import AddCalibrationDialog
from .edit_dialog import EditCalibrationDialog
from .import_dialog import ImportCalibrationMappingDialog

class CalibrationLogView(QWidget):
    data_changed = pyqtSignal()
    def __init__(self, chassis_sn=None):
        super().__init__()
        self.chassis_sn = chassis_sn
        self.main_layout = QVBoxLayout(self)
        self.setup_toolbar()
        self.setup_ui()
        self.load_calibration_data()

    def setup_ui(self):
        """Sets up the UI components."""
        self.table_view = QTableWidget()
        self.table_view.setSortingEnabled(True)
        self.table_view.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_view.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_view.itemSelectionChanged.connect(self.update_toolbar_state)
        self.main_layout.addWidget(self.table_view)

        self.no_data_label = QLabel("No calibration history available for this sensor.")
        self.no_data_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.no_data_label)
        self.no_data_label.hide()

    def setup_toolbar(self):
        """Creates a toolbar."""
        toolbar = QToolBar("Calibration Log Toolbar")
        self.main_layout.addWidget(toolbar)

        self.add_cal_action = QAction("Add Calibration", self)
        self.add_cal_action.triggered.connect(self.add_calibration_entry)
        toolbar.addAction(self.add_cal_action)

        self.edit_action = QAction("Edit Calibration", self)
        self.edit_action.triggered.connect(self.edit_selected_record)
        self.edit_action.setEnabled(False) # Disabled by default
        toolbar.addAction(self.edit_action)

        self.delete_action = QAction("Delete Selected", self)
        self.delete_action.triggered.connect(self.delete_selected_records)
        toolbar.addAction(self.delete_action)

        self.import_action = QAction("Import Calibration Certificate", self)
        self.import_action.triggered.connect(self.import_calibration_certificate)
        toolbar.addAction(self.import_action)

        toolbar.addSeparator()

        self.refresh_action = QAction("Refresh", self)
        self.refresh_action.triggered.connect(self.load_calibration_data)
        toolbar.addAction(self.refresh_action)

    def _generate_calibration_id_for(self, chassis_sn: str, cal_date_iso: str) -> str:
        """Generate next calibration ID like #<chassis>_G_<yyyymmdd>_<rev>."""
        existing = db_manager.get_calibration_log(chassis_sn=chassis_sn)
        existing_ids = [rec['Calibration_ID'] for rec in existing if str(rec['Calibration_Date']).startswith(cal_date_iso)]
        formatted_date = cal_date_iso.replace('-', '')
        for i in range(26):
            test = f"#{chassis_sn}_G_{formatted_date}_{chr(65+i)}"
            if test not in existing_ids:
                return test
        return f"#{chassis_sn}_G_{formatted_date}_Z"

    def import_calibration_certificate(self):
        """Import a DOCX calibration certificate and create records by mapping each metric to a sensor across all systems."""
        # Pick file (default to project root)
        start_dir = os.getcwd()
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Calibration Certificate", start_dir, "Word Documents (*.docx)")
        if not file_path:
            return

        parsed = parse_calibration_certificate(file_path)
        if parsed is None:
            QMessageBox.critical(self, "Import Error", "Unable to parse the document. Ensure python-docx is installed and the file is a valid .docx.")
            return

        cal_date_iso = parsed.date_iso or QDate.currentDate().toString('yyyy-MM-dd')

        # Determine which metric types are present in the parsed doc
        present_types = []
        if parsed.vnir_rmse_x is not None or parsed.vnir_rmse_y is not None:
            present_types.append('VNIR')
        if parsed.swir_rmse_x is not None or parsed.swir_rmse_y is not None:
            present_types.append('SWIR')
        if any(v is not None for v in [parsed.rgb_rmse_x, parsed.rgb_rmse_y, parsed.rgb_rmse_z]):
            present_types.append('RGB')
        if parsed.lidar_plane_fit is not None:
            present_types.append('LiDAR')

        if not present_types:
            # Show detected merge fields (if any) to help the user diagnose mapping names
            fields = extract_merge_fields(file_path) or {}
            if fields:
                preview = "\n".join([f"{k}: {v}" for k, v in sorted(fields.items())])
                QMessageBox.information(self, "No Data Found", f"No recognizable metrics were mapped.\n\nDetected merge fields:\n\n{preview}\n\nShare these field names to add to the mapping.")
            else:
                QMessageBox.information(self, "No Data", "No recognizable sensor metrics were found in the document.")
            return

        print(f"[CAL IMPORT] Present types: {present_types}")

        # Canonicalize type labels
        def canonical_type(t: str) -> str:
            t_norm = (t or '').strip().lower()
            if t_norm in ('vnir', 'hyperspec vnir', 'vnir camera'):
                return 'VNIR'
            if t_norm in ('swir', 'hyperspec swir', 'swir camera'):
                return 'SWIR'
            if t_norm in ('rgb', 'rgb camera', 'rgb-imager'):
                return 'RGB'
            if t_norm in ('lidar', 'li dar', 'lidar sensor', 'phoenix lidar'):
                return 'LiDAR'
            if t_norm in ('gnss', 'gps', 'rtk', 'gps/rtk'):
                return 'GNSS'
            return (t or '').strip()

        # Require chassis_sn from the document; if missing, try to infer from file path components
        target_chassis = (getattr(parsed, 'system_sn', '') or '').strip()
        if not target_chassis:
            # Infer from file name and parent directories
            try:
                parts = []
                # filename tokens split by non-alnum
                base = os.path.basename(file_path)
                parts.extend([p for p in re.split(r"[^A-Za-z0-9]+", base) if p])
                # up to 3 parent directories
                d = os.path.dirname(file_path)
                for _ in range(3):
                    if not d:
                        break
                    parts.append(os.path.basename(d))
                    d = os.path.dirname(d)
                # Deduplicate while preserving order
                seen = set()
                candidates_from_path = [p for p in parts if not (p in seen or seen.add(p))]
                print(f"[CAL IMPORT] No System_SN in doc; trying path tokens: {candidates_from_path}")
                for tok in candidates_from_path:
                    if not tok:
                        continue
                    sysinfo = db_manager.get_system_by_chassis_sn(tok)
                    if sysinfo:
                        target_chassis = tok
                        print(f"[CAL IMPORT] Inferred chassis from path token: {tok}")
                        break
            except Exception as e:
                print(f"[CAL IMPORT] Path-based chassis inference failed: {e}")
        if not target_chassis:
            QMessageBox.critical(self, "Import Error", "Certificate does not include a System/Chassis Serial Number and none could be inferred from the file path. Cannot map sensors.")
            return

        print(f"[CAL IMPORT] Parsed chassis_sn: '{target_chassis}'")

        # Try several variants to fetch the system
        candidates = [target_chassis, target_chassis.strip(), target_chassis.upper(), target_chassis.lower()]
        system_info = None
        matched_chassis = None
        for cand in candidates:
            system_info = db_manager.get_system_by_chassis_sn(cand)
            if system_info:
                matched_chassis = cand
                break
        if not system_info:
            QMessageBox.critical(self, "Import Error", f"No system found in database for chassis '{target_chassis}'.")
            return

        # Build type -> installed_id mapping from the system's active installed sensors
        type_to_iid = {}
        for s in (system_info.get('sensors') or []):
            ctype = canonical_type(s.get('type'))
            if s.get('installed_id') and ctype not in type_to_iid:
                type_to_iid[ctype] = s.get('installed_id')

        # Determine selections strictly from system configuration
        selections = {}
        missing_types = []
        for t in present_types:
            iid = type_to_iid.get(t)
            if iid:
                selections[t] = iid
            else:
                missing_types.append(t)

        if missing_types:
            QMessageBox.warning(self, "Partial Mapping",
                                "The following metric types are present in the certificate but are not installed on the target chassis: "
                                + ", ".join(missing_types) + ". These will be skipped.")

        # Build records based on parsed values
        records = []
        # Helper to create a record for a selected installed_id and metrics
        def append_record_for(installed_id: int, rmse_x=None, rmse_y=None, rmse_z=None, plane_fit=None):
            if not installed_id:
                return
            # Use the chassis SN from the certificate, not from database
            chassis = matched_chassis or 'UNKNOWN'
            cal_id = self._generate_calibration_id_for(chassis, cal_date_iso)
            records.append({
                'Calibration_ID': cal_id,
                'Installed_ID': installed_id,
                'Platform': None,
                'Calibration_Date': cal_date_iso,
                'Status': 'APPROVED',
                'RMSE_X': rmse_x,
                'RMSE_Y': rmse_y,
                'RMSE_Z': rmse_z,
                'Sigma0': None,
                'Plane_Fit': plane_fit,
                'Notes': f"Imported from {os.path.basename(file_path)}"
            })

        # VNIR
        if 'VNIR' in present_types:
            iid = selections.get('VNIR')
            append_record_for(iid, rmse_x=parsed.vnir_rmse_x, rmse_y=parsed.vnir_rmse_y)
        # SWIR
        if 'SWIR' in present_types:
            iid = selections.get('SWIR')
            append_record_for(iid, rmse_x=parsed.swir_rmse_x, rmse_y=parsed.swir_rmse_y)
        # RGB
        if 'RGB' in present_types:
            iid = selections.get('RGB')
            append_record_for(iid, rmse_x=parsed.rgb_rmse_x, rmse_y=parsed.rgb_rmse_y, rmse_z=parsed.rgb_rmse_z)
        # LiDAR
        if 'LiDAR' in present_types:
            iid = selections.get('LiDAR')
            append_record_for(iid, plane_fit=parsed.lidar_plane_fit)

        if not records:
            QMessageBox.information(self, "No Targets Selected", "No sensors were selected to receive the imported metrics.")
            return

        # Preview and confirm before saving
        # Build a neat, human-readable summary: "<Type> | <Manufacturer> <Model> | Chassis <SN>"
        preview_lines = []
        for rec in records:
            info = db_manager.get_installed_sensor_info(rec.get('Installed_ID') or 0) or {}
            sensor_type = info.get('sensor_type', 'Unknown')
            manufacturer = info.get('manufacturer', 'Unknown')
            model = info.get('sensor_model', 'Unknown')
            chassis = info.get('chassis_sn', 'UNKNOWN')
            preview_lines.append(f"• {sensor_type} | {manufacturer} {model} | Chassis {chassis}")

        # Add a small footer line with date and Calibration_ID if uniform across records
        cal_ids = {rec.get('Calibration_ID') for rec in records}
        dates = {rec.get('Calibration_Date') for rec in records}
        footer = []
        if len(cal_ids) == 1:
            footer.append(f"Calibration_ID: {next(iter(cal_ids))}")
        if len(dates) == 1:
            footer.append(f"Date: {next(iter(dates))}")
        preview_text = "\n".join(preview_lines + (["\n" + " | ".join(footer)] if footer else [])) if preview_lines else "(no records)"
        confirm = QMessageBox.question(
            self,
            "Confirm Import",
            f"You are about to import {len(records)} record(s):\n\n{preview_text}\n\nProceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if confirm != QMessageBox.Yes:
            QMessageBox.information(self, "Import Cancelled", "No changes were made.")
            return

        if db_manager.add_calibration_records(records):
            QMessageBox.information(self, "Import Complete", f"Imported {len(records)} record(s).")
            # If a specific chassis is being viewed, only refresh that filter; otherwise refresh all
            self.on_data_changed()
        else:
            QMessageBox.critical(self, "Database Error", "Failed to save imported calibration records.")

    def load_calibration_data(self):
        """Loads calibration data into the table."""
        if not db_manager.session:
            return
        
        # Assuming get_calibration_log can be filtered by chassis_sn in the future
        # For now, it fetches all. We will need to update this.
        calibration_data = db_manager.get_calibration_log(chassis_sn=self.chassis_sn)

        if not calibration_data:
            self.table_view.hide()
            self.no_data_label.show()
            return
        
        self.table_view.show()
        self.no_data_label.hide()

        # Ensure 'id' is included in headers if it exists in data
        self.headers = ['id'] + [h for h in calibration_data[0].keys() if h != 'id']
        self.table_view.setColumnCount(len(self.headers))
        self.table_view.setHorizontalHeaderLabels(self.headers)
        self.table_view.setRowCount(len(calibration_data))

        for row_idx, record in enumerate(calibration_data):
            for col_idx, header in enumerate(self.headers):
                value = record.get(header)
                display_text = '' if value is None else str(value)
                item = QTableWidgetItem(display_text)
                
                # Store the original id and Calibration_ID for saving
                if header == 'id':
                    item.setData(Qt.UserRole, record.get('id'))
                elif header == 'Calibration_ID':
                    item.setData(Qt.UserRole, record.get('Calibration_ID'))

                # Set non-editable columns
                if header in ['id', 'Calibration_ID', 'Sensor', 'Installed_ID']:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)

                self.table_view.setItem(row_idx, col_idx, item)

        self.table_view.resizeColumnsToContents()
        self.update_toolbar_state() # Set initial state

    def update_toolbar_state(self):
        """Enable/disable toolbar actions based on table selection."""
        selected_rows = len(set(item.row() for item in self.table_view.selectedItems()))
        self.edit_action.setEnabled(selected_rows == 1)
        self.delete_action.setEnabled(selected_rows > 0)

    def on_data_changed(self):
        """Slot to handle data changes from dialogs."""
        self.load_calibration_data()
        self.data_changed.emit()

    def edit_selected_record(self):
        """Opens a dialog to edit the selected calibration record."""
        selected_rows = list(set(item.row() for item in self.table_view.selectedItems()))
        if len(selected_rows) != 1:
            return

        row = selected_rows[0]
        edit_data = {}
        for col_idx, header in enumerate(self.headers):
            item = self.table_view.item(row, col_idx)
            if item is not None:
                edit_data[header] = item.text()
        
        # The primary key 'id' is crucial for editing
        id_item = self.table_view.item(row, self.headers.index('id'))
        edit_data['id'] = id_item.text()

        dialog = EditCalibrationDialog(edit_data, self)
        dialog.data_changed.connect(self.on_data_changed)
        dialog.exec_()



    def delete_selected_records(self):
        """Deletes the selected rows from the table and the database."""
        selected_items = self.table_view.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select one or more records to delete.")
            return

        # Get unique rows from selected items
        selected_rows = sorted(list(set(item.row() for item in selected_items)))

        reply = QMessageBox.question(self, 'Confirm Deletion',
                                     f"Are you sure you want to delete {len(selected_rows)} selected record(s)?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            record_ids_to_delete = []
            
            for row in selected_rows:
                # Get the record ID from the first column
                id_item = self.table_view.item(row, 0)  # First column is 'id'
                if id_item:
                    record_id = id_item.data(Qt.UserRole) or id_item.text()
                    if record_id:
                        record_ids_to_delete.append(record_id)

            if not record_ids_to_delete:
                QMessageBox.information(self, "No Records to Delete", "No valid records were selected for deletion.")
                return

            if db_manager.delete_calibration_records(record_ids_to_delete):
                QMessageBox.information(self, "Success", "Selected records have been deleted.")
                self.load_calibration_data()  # Refresh the view
            else:
                QMessageBox.critical(self, "Database Error", "Failed to delete records from the database.")

    def add_calibration_entry(self):
        """Opens a dialog to add a new calibration entry."""
        dialog = AddCalibrationDialog(self, chassis_sn=self.chassis_sn)
        dialog.data_changed.connect(self.on_data_changed)
        dialog.exec_()
