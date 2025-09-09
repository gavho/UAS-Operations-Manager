from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QFrame, QScrollArea, QWidget, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt
from app.database.manager import db_manager
from app.logic.cert_importer import parse_calibration_certificate
import re

class AddSystemDialog(QDialog):
    """Dialog to add a new system with its sensors."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New System")
        self.setMinimumSize(500, 600)

        self._sensor_models = []
        self._sensor_rows = []

        self.setup_ui()
        self.load_sensor_models()

    def setup_ui(self):
        """Set up the main UI components."""
        main_layout = QVBoxLayout(self)

        # Chassis and Customer Info
        info_frame = QFrame()
        info_layout = QVBoxLayout(info_frame)
        info_layout.addWidget(QLabel("Chassis Serial Number:"))
        self.chassis_sn_input = QLineEdit()
        info_layout.addWidget(self.chassis_sn_input)

        info_layout.addWidget(QLabel("Customer:"))
        self.customer_input = QLineEdit()
        info_layout.addWidget(self.customer_input)
        main_layout.addWidget(info_frame)

        # Sensors Section
        sensors_frame = QFrame()
        sensors_layout = QVBoxLayout(sensors_frame)
        sensors_header_layout = QHBoxLayout()
        sensors_header_layout.addWidget(QLabel("<b>Installed Sensors</b>"))
        sensors_header_layout.addStretch()
        self.import_from_cert_button = QPushButton("Import System from Calibration Certificate")
        self.import_from_cert_button.clicked.connect(self.import_from_certificate)
        sensors_header_layout.addWidget(self.import_from_cert_button)
        self.add_sensor_button = QPushButton("Add Sensor")
        self.add_sensor_button.clicked.connect(self.add_sensor_row)
        sensors_header_layout.addWidget(self.add_sensor_button)
        sensors_layout.addLayout(sensors_header_layout)

        # Scroll area for sensor rows
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.sensors_container = QWidget()
        self.sensors_rows_layout = QVBoxLayout(self.sensors_container)
        self.sensors_rows_layout.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(self.sensors_container)
        sensors_layout.addWidget(scroll_area)
        main_layout.addWidget(sensors_frame)

        # Dialog Buttons
        button_box = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_box.addStretch()
        button_box.addWidget(self.cancel_button)
        button_box.addWidget(self.save_button)
        main_layout.addLayout(button_box)

    def load_sensor_models(self):
        """Load sensor models from the database to populate dropdowns."""
        self._sensor_models = db_manager.get_all_sensor_models()
        if not self._sensor_models:
            self.add_sensor_button.setEnabled(False)
            QMessageBox.warning(self, "No Sensors Found", "No sensor models were found in the database. Cannot add sensors.")

    def add_sensor_row(self):
        """Add a new row for selecting a sensor and return its widgets dict."""
        sensor_row = QWidget()
        row_layout = QHBoxLayout(sensor_row)

        type_combo = QComboBox()
        model_combo = QComboBox()
        sn_input = QLineEdit()
        sn_input.setPlaceholderText("Sensor S/N")
        remove_button = QPushButton("Remove")

        # Group models by type
        models_by_type = {}
        for sensor in self._sensor_models:
            if sensor['type'] not in models_by_type:
                models_by_type[sensor['type']] = []
            models_by_type[sensor['type']].append(sensor)

        type_combo.addItems(sorted(models_by_type.keys()))

        def update_models():
            model_combo.clear()
            selected_type = type_combo.currentText()
            for sensor in models_by_type.get(selected_type, []):
                model_combo.addItem(f"{sensor['model']} ({sensor['manufacturer']})", sensor['sensor_model_id'])

        type_combo.currentTextChanged.connect(update_models)
        update_models()  # Initial population

        row_layout.addWidget(QLabel("Type:"))
        row_layout.addWidget(type_combo, 1)
        row_layout.addWidget(QLabel("Model:"))
        row_layout.addWidget(model_combo, 2)
        row_layout.addWidget(QLabel("S/N:"))
        row_layout.addWidget(sn_input, 2)  # Add stretch factor, 2)
        row_layout.addWidget(remove_button)

        # Store references to the widgets we need to access later
        sensor_row_widgets = {'row': sensor_row, 'type_combo': type_combo, 'model_combo': model_combo, 'sn_input': sn_input}
        self._sensor_rows.append(sensor_row_widgets)
        self.sensors_rows_layout.addWidget(sensor_row)

        remove_button.clicked.connect(lambda: self.remove_sensor_row(sensor_row_widgets))

        return sensor_row_widgets

    def remove_sensor_row(self, sensor_row_widgets):
        """Remove a sensor row from the layout and list."""
        self.sensors_rows_layout.removeWidget(sensor_row_widgets['row'])
        sensor_row_widgets['row'].deleteLater()
        self._sensor_rows.remove(sensor_row_widgets)

    def get_data(self):
        """Return the data entered in the dialog."""
        sensors = []
        for row_widgets in self._sensor_rows:
            model_combo = row_widgets['model_combo']
            sn_input = row_widgets['sn_input']
            sensor_id = model_combo.currentData()
            sensor_sn = sn_input.text().strip()

            # Include sensor if it has a model selected (sensor_id is not None)
            # Serial number is optional for new sensors
            if sensor_id is not None:
                sensors.append({
                    'sensor_model_id': sensor_id,
                    'sensor_sn': sensor_sn
                })

        return {
            'chassis_sn': self.chassis_sn_input.text().strip(),
            'customer': self.customer_input.text().strip(),
            'sensors': sensors
        }

    def clear_form(self):
        """Clear all current inputs and sensor rows in the dialog."""
        # Clear sensor rows
        for row in list(self._sensor_rows):
            self.remove_sensor_row(row)
        # Clear chassis and customer
        self.chassis_sn_input.clear()
        self.customer_input.clear()

    def import_from_certificate(self):
        """Parse a calibration certificate (.docx) to prefill chassis and sensors."""
        start_dir = ''
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Calibration Certificate", start_dir, "Word Documents (*.docx)")
        if not file_path:
            return
        # If there is existing data, confirm clearing before importing
        has_existing_rows = bool(self._sensor_rows)
        has_existing_text = bool(self.chassis_sn_input.text().strip() or self.customer_input.text().strip())
        if has_existing_rows or has_existing_text:
            reply = QMessageBox.question(
                self,
                'Clear Current Entries?',
                'Importing from a certificate will replace the current chassis and sensor rows. Do you want to clear them first?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.No:
                return
            self.clear_form()

        parsed = parse_calibration_certificate(file_path)
        if not parsed:
            QMessageBox.critical(self, "Import Error", "Unable to parse the document. Ensure python-docx is installed and the file is a valid .docx.")
            return

        # Prefill chassis/system SN
        if getattr(parsed, 'system_sn', None):
            self.chassis_sn_input.setText(parsed.system_sn.strip())

        # Build helpers
        # Group existing models by type (exact DB key)
        models_by_type = {}
        for s in self._sensor_models:
            key = (s['type'] or '').strip()
            models_by_type.setdefault(key, []).append(s)

        def find_matching_type_keys(type_name: str):
            """Return a list of DB type keys that match the requested type by synonyms/contains.
            This makes 'GNSS' match 'GNSS/INS Unit', and 'VNIR' match 'Hyperspec VNIR', etc.
            """
            if not type_name:
                return []
            t = type_name.strip().lower()
            # canonical tokens
            synonyms = {
                'vnir': ['vnir', 'hyperspec', 'headwall', 'specim'],
                'swir': ['swir', 'hyperspec'],
                'rgb': ['rgb'],
                'lidar': ['lidar', 'li dar', 'phoenix'],
                # include broader aliases often used for GNSS/INS
                'gnss': ['gnss', 'ins', 'gnss/ins', 'imu', 'nav', 'inertial', 'navigation'],
            }
            # choose bucket
            bucket = None
            for k in synonyms.keys():
                if k in t:
                    bucket = k
                    break
            if bucket is None:
                # fallback: try to find keys that contain the provided text
                return [k for k in models_by_type.keys() if t in k.strip().lower()]

            tokens = synonyms[bucket]
            keys = []
            for k in models_by_type.keys():
                lk = k.strip().lower()
                if any(tok in lk for tok in tokens):
                    keys.append(k)
            if keys:
                return keys
            # fallback by contains of original
            return [k for k in models_by_type.keys() if t in k.strip().lower()]

        def add_or_fill(type_name: str, model_name: str = None, serial: str = None):
            desired_id = None
            desired_type_key = None

            if model_name:
                wanted_model_name = model_name.strip().lower()
                # Try to find an exact match for the model globally
                for s in self._sensor_models:
                    if (s['model'] or '').strip().lower() == wanted_model_name:
                        desired_id = s['sensor_model_id']
                        desired_type_key = (s['type'] or '').strip()
                        break

            # Find best matching type key(s)
            target_keys = []
            if desired_type_key:
                target_keys = [desired_type_key]
            else:
                # exact case-insensitive match first
                for k in models_by_type.keys():
                    if k.lower() == (type_name or '').lower():
                        target_keys = [k]
                        break
                if not target_keys:
                    target_keys = find_matching_type_keys(type_name)

            if not target_keys:
                # Still add a row; user can pick type manually
                row = self.add_sensor_row()
                if serial:
                    row['sn_input'].setText(serial.strip())
                return

            row = self.add_sensor_row()
            # Set type selection to the first/best match
            type_combo = row['type_combo']
            # Try to set the exact text match; fallback by case-insensitive search
            idx = type_combo.findText(target_keys[0], Qt.MatchExactly)
            if idx < 0:
                # case-insensitive
                for i in range(type_combo.count()):
                    if type_combo.itemText(i).lower() == target_keys[0].lower():
                        idx = i
                        break
            if idx >= 0:
                type_combo.setCurrentIndex(idx)

            # Models are updated by signal; now select model if provided.
            # Prefer selecting by Sensor_Model_ID resolved from DB names to avoid label mismatches.
            model_combo = row['model_combo']
            if desired_id is None and model_name:
                wanted = (model_name or '').strip().lower()
                wanted_tokens = [t for t in re.split(r"[^a-z0-9]+", wanted) if t]
                # strategies over DB models for these type keys (union)
                candidates = []
                for tk in target_keys:
                    candidates.extend(models_by_type.get(tk, []))
                # Scoring function to pick best candidate
                best_score = -1
                best_id = None
                for s in candidates:
                    manu = (s['manufacturer'] or '').strip().lower()
                    model = (s['model'] or '').strip().lower()
                    combo = f"{manu} {model}".strip()
                    score = 0
                    # exacts
                    if model == wanted:
                        score += 10
                    if combo == wanted:
                        score += 12
                    # token overlaps
                    model_tokens = [t for t in re.split(r"[^a-z0-9]+", model) if t]
                    manu_tokens = [t for t in re.split(r"[^a-z0-9]+", manu) if t]
                    # presence
                    if manu and manu in wanted:
                        score += 8  # strong boost when manufacturer explicitly present
                    if any(mt in wanted_tokens for mt in model_tokens):
                        score += 3
                    if any(mt in wanted for mt in model_tokens):
                        score += 2
                    if any(mt in wanted_tokens for mt in manu_tokens):
                        score += 4  # boost when manufacturer tokens match
                    # contains either direction
                    if model in wanted or wanted in model:
                        score += 2
                    if combo in wanted or wanted in combo:
                        score += 3
                    # token-set similarity (Jaccard-like)
                    wanted_set = set(wanted_tokens)
                    combo_tokens = [t for t in re.split(r"[^a-z0-9]+", combo) if t]
                    combo_set = set(combo_tokens)
                    overlap = len(wanted_set & combo_set)
                    if overlap:
                        score += min(overlap * 2, 6)
                    # prefer longer model names (more specific)
                    score += min(len(model_tokens), 4)
                    # update best
                    if score > best_score:
                        best_score = score
                        best_id = s['sensor_model_id']
                desired_id = best_id

            # 4) If still not found and there's only one model in this type, pick it
            if desired_id is None:
                cand = []
                for tk in target_keys:
                    cand.extend(models_by_type.get(tk, []))
                if len(cand) == 1:
                    desired_id = cand[0]['sensor_model_id']

            # Apply selection in the combo by data
            if desired_id is not None:
                for i in range(model_combo.count()):
                    if model_combo.itemData(i) == desired_id:
                        model_combo.setCurrentIndex(i)
                        break
            # Serial number (always set if we have it)
            if serial:
                row['sn_input'].setText(serial.strip())

        # Use parsed per-sensor model/SN hints
        # Always add a GNSS/INS row for systems created from certificates.
        add_or_fill('GNSS', parsed.gnss_model, parsed.gnss_sn)
        if getattr(parsed, 'vnir_model', None) or getattr(parsed, 'vnir_sn', None):
            add_or_fill('VNIR', parsed.vnir_model, parsed.vnir_sn)
        if getattr(parsed, 'swir_model', None) or getattr(parsed, 'swir_sn', None):
            add_or_fill('SWIR', parsed.swir_model, parsed.swir_sn)
        if getattr(parsed, 'rgb_model', None) or getattr(parsed, 'rgb_sn', None):
            add_or_fill('RGB', parsed.rgb_model, parsed.rgb_sn)
        if getattr(parsed, 'lidar_model', None) or getattr(parsed, 'lidar_sn', None):
            add_or_fill('LiDAR', parsed.lidar_model, parsed.lidar_sn)

        # If still empty but we have sensor_types_calibrated, add blank rows for those types
        if not self._sensor_rows and getattr(parsed, 'sensor_types_calibrated', None):
            for t in parsed.sensor_types_calibrated:
                add_or_fill(t)

        QMessageBox.information(self, "Imported", "Chassis and sensor rows were prefilled from the certificate. Please review and click Save.")
