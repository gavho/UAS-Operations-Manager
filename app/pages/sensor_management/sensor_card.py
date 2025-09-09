from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSizePolicy, QPushButton, QToolButton, QFormLayout
)
from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QIcon
from PyQt5.QtCore import QSize

class SensorCard(QFrame):
    """A card widget that displays information about a chassis and its sensors."""
    edit_requested = pyqtSignal(str)  # Emits chassis_sn
    delete_requested = pyqtSignal(str)  # Emits chassis_sn
    calibration_log_requested = pyqtSignal(str)  # Emits chassis_sn
    details_toggled = pyqtSignal()  # Emitted after details visibility changes

    def __init__(self, system_data, parent=None):
        """
        Initialize the sensor card.

        Args:
            system_data (dict): A dictionary containing system and sensor information.
            parent: Parent widget
        """
        super().__init__(parent)
        self.chassis = system_data.get('chassis', 'Unknown Chassis')
        self.sensors = system_data.get('sensors', [])
        # Sort sensors to prioritize 'GNSS'
        self.sensors.sort(key=lambda s: (s.get('type', '').strip().lower() != 'gnss'))
        self.customer = system_data.get('customer', 'N/A')
        self.system_status = system_data.get('status', 'Unknown')
        self.detail_widgets = []

        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface for the sensor card."""
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)
        # Let parent view determine width; height is fixed and managed internally
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setObjectName("sensorCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # --- Header --- (Chassis Name and Edit/Delete Buttons)
        header_layout = QHBoxLayout()
        self.name_label = QLabel(self.chassis)
        self.name_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")

        self.edit_button = QPushButton("Edit")
        self.delete_button = QPushButton("Delete")
        self.edit_button.setFixedWidth(60)
        self.delete_button.setFixedWidth(60)
        self.edit_button.clicked.connect(self.on_edit_clicked)
        self.delete_button.clicked.connect(self.on_delete_clicked)

        header_layout.addWidget(self.name_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # --- Customer, Status, and History Button ---
        info_layout = QHBoxLayout()

        # Left side: Customer and status
        info_left = QVBoxLayout()
        customer_label = QLabel(f"<b>Customer:</b> {self.customer}")
        customer_label.setWordWrap(True)
        info_left.addWidget(customer_label)

        # Status with colored indicator
        status_layout = QHBoxLayout()
        status_indicator = QLabel()
        status_indicator.setFixedSize(12, 12)
        status_indicator.setStyleSheet(self._get_status_style())
        status_label = QLabel(f"<b>Status:</b> {self.system_status}")
        status_layout.addWidget(status_indicator)
        status_layout.addWidget(status_label)
        status_layout.addStretch()
        info_left.addLayout(status_layout)
        info_left.addStretch()
        
        # Right side: History button
        history_btn = QPushButton("Calibration History")
        history_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #3498db;
                border-radius: 4px;
                padding: 4px 8px;
                color: #3498db;
                font-size: 11px;
                min-width: 100px;
                max-height: 30px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
        """)
        history_btn.setCursor(Qt.PointingHandCursor)
        history_btn.clicked.connect(
            lambda: self.calibration_log_requested.emit(self.chassis)
        )
        
        # Add both sides to the layout
        info_layout.addLayout(info_left, 1)  # Stretch factor 1 to take available space
        info_layout.addWidget(history_btn, 0, Qt.AlignTop | Qt.AlignRight)
        
        layout.addLayout(info_layout)

        # --- Separator ---
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # --- Sensor Details (lazy) ---
        sensors_header = QLabel("Sensors")
        sensors_header.setStyleSheet("font-weight: bold; font-size: 14px; color: #34495e; margin-top: 5px;")
        layout.addWidget(sensors_header)

        # Container stub; details rows are built on-demand
        self.sensors_container = QWidget()
        self.sensors_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.sensors_layout = QVBoxLayout(self.sensors_container)
        self.sensors_layout.setContentsMargins(0, 5, 0, 5)
        self.sensors_layout.setSpacing(10)
        layout.addWidget(self.sensors_container)

        layout.addStretch()

        # --- Button Bar ---
        button_bar = QHBoxLayout()
        button_bar.addStretch()
        button_bar.addWidget(self.edit_button)
        button_bar.addWidget(self.delete_button)
        layout.addLayout(button_bar)

        self.setLayout(layout)
        self.apply_styling()

        # Build only light-weight rows with toggle; heavy details are added on expand
        self._build_sensor_rows_light()

        # Set initial height
        self._update_card_height()

    def on_edit_clicked(self):
        """Emit a signal when the edit button is clicked."""
        self.edit_requested.emit(self.chassis)

    def on_delete_clicked(self):
        """Emit a signal when the delete button is clicked."""
        self.delete_requested.emit(self.chassis)

    def on_cal_log_clicked(self):
        """Emit a signal when the calibration log button is clicked."""
        self.calibration_log_requested.emit(self.chassis)

    def _update_card_height(self):
        """Calculate and set the card's fixed height based on its visible content."""
        self.setFixedHeight(self.layout().sizeHint().height())

    def toggle_details(self, checked, widget, button):
        # Build details content lazily on first expand
        if checked and widget.layout() is None:
            # Compact form layout: label | value per row to reduce height
            details_layout = QFormLayout(widget)
            details_layout.setContentsMargins(0, 5, 0, 0)  # Tighter top margin
            details_layout.setSpacing(4)  # Tighter spacing between rows

            # Determine which sensor row this widget belongs to via property
            sensor = widget.property("sensor_data") or {}
            cal_date = sensor.get('last_calibrated', 'N/A')
            serial_number = sensor.get('serial_number', 'N/A')
            sensor_type = (sensor.get('type') or '').strip().lower()

            # GNSS: show ONLY serial number
            if sensor_type == 'gnss':
                lbl_sn = QLabel("Serial Number:")
                val_sn = QLabel(str(serial_number))
                for w in (lbl_sn,):
                    w.setWordWrap(False)
                    w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    w.setMinimumHeight(18)
                    w.setStyleSheet("background: transparent; border: none; font-size: 11px;")
                for val_w in (val_sn,):
                    val_w.setWordWrap(True)
                    val_w.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                    val_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    val_w.setMinimumHeight(18)
                    val_w.setToolTip(val_w.text())
                    val_w.setTextInteractionFlags(Qt.TextSelectableByMouse)
                    val_w.setStyleSheet("background: transparent; border: none; font-size: 11px;")
                details_layout.addRow(lbl_sn, val_sn)
            else:
                # Non-GNSS: include Calibration Date and Serial Number
                lbl_cd = QLabel("Calibration Date:")
                val_cd = QLabel(str(cal_date))
                lbl_sn = QLabel("Serial Number:")
                val_sn = QLabel(str(serial_number))
                for w in (lbl_cd, lbl_sn):
                    w.setWordWrap(False)
                    w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    w.setMinimumHeight(18)
                    w.setStyleSheet("background: transparent; border: none; font-size: 11px;")
                for val_w in (val_cd, val_sn):
                    val_w.setWordWrap(True)
                    val_w.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                    val_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    val_w.setMinimumHeight(18)
                    val_w.setToolTip(val_w.text())
                    val_w.setTextInteractionFlags(Qt.TextSelectableByMouse)
                    val_w.setStyleSheet("background: transparent; border: none; font-size: 11px;")
                details_layout.addRow(lbl_cd, val_cd)
                details_layout.addRow(lbl_sn, val_sn)

            # No separator to save vertical space

            # Values with graceful N/A fallbacks
            rmse_x = sensor.get('rmse_x', 'N/A')
            rmse_y = sensor.get('rmse_y', 'N/A')
            rmse_z = sensor.get('rmse_z', 'N/A')
            sigma0 = sensor.get('sigma0', 'N/A')
            plane_fit = sensor.get('plane_fit', 'N/A')

            fields_to_display = {}

            if sensor_type == 'gnss':
                # GNSS has no calibration metrics; do not add RMSE/Sigma fields
                fields_to_display = {}
            elif sensor_type == 'lidar':
                fields_to_display['Plane Fitting RMS:'] = plane_fit if plane_fit is not None else 'N/A'
            else:
                # Handle RMSE for other sensor types
                rmse_parts = []
                rmse_x_val = rmse_x if rmse_x is not None else 'N/A'
                rmse_y_val = rmse_y if rmse_y is not None else 'N/A'
                rmse_parts.append(f"X: {rmse_x_val}")
                rmse_parts.append(f"Y: {rmse_y_val}")

                if sensor_type not in ('vnir', 'swir'):
                    rmse_z_val = rmse_z if rmse_z is not None else 'N/A'
                    rmse_parts.append(f"Z: {rmse_z_val}")
                
                fields_to_display['RMSE (m)'] = ", ".join(rmse_parts)

                # Handle Sigma0 for non-VNIR/SWIR/RGB sensors
                if sensor_type not in ('vnir', 'swir', 'rgb'):
                    fields_to_display['Sigma0'] = sigma0 if sigma0 is not None else 'N/A'

            # Add all defined fields to the layout
            for label, value in fields_to_display.items():
                lbl = QLabel(label)
                val = QLabel(str(value))
                lbl.setStyleSheet("background: transparent; border: none; font-size: 11px;")
                val.setWordWrap(True)
                val.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                val.setTextInteractionFlags(Qt.TextSelectableByMouse)
                val.setStyleSheet("background: transparent; border: none; font-size: 11px;")
                details_layout.addRow(lbl, val)


        widget.setVisible(checked)

        button.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

        # Update the card's fixed height to accommodate the change.
        self._update_card_height()


    def _build_sensor_rows_light(self):
        # Build minimal rows: header with type/model and a toggle; details frame hidden
        for sensor in self.sensors:
            sensor_frame = QFrame()
            sensor_frame.setObjectName("sensorGroupFrame")
            sensor_frame.setFrameShape(QFrame.StyledPanel)
            sensor_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
            sensor_layout = QVBoxLayout(sensor_frame)
            sensor_layout.setContentsMargins(10, 10, 10, 10)
            sensor_layout.setSpacing(5)

            main_info_widget = QWidget()
            main_info_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            main_info_layout = QHBoxLayout(main_info_widget)
            main_info_layout.setContentsMargins(0, 0, 0, 0)

            sensor_type = sensor.get('type', 'N/A')
            sensor_model = sensor.get('model', 'N/A')
            sensor_type_model = f"<b>{sensor_type}:</b> {sensor_model}"
            type_label = QLabel(sensor_type_model)
            type_label.setWordWrap(True)
            main_info_layout.addWidget(type_label, 1)
            main_info_layout.addStretch()

            # Decide if this sensor type should have expandable calibration details
            st_lower = (sensor_type or '').strip().lower()
            # Allow expand for GNSS so we can show its Serial Number in a compact details panel.
            # Keep IR non-expandable.
            allow_expand = st_lower != 'ir'

            if allow_expand:
                details_widget = QFrame()
                details_widget.setObjectName("detailsWidget")
                details_widget.setStyleSheet("""
                    #detailsWidget {
                        border-top: 1px solid #f0f0f0;
                        margin-top: 8px;
                        padding: 2px 0;
                    }
                    #detailsWidget QLabel { padding: 0px; background: transparent; border: none; }
                """)
                details_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
                details_widget.setProperty("sensor_data", sensor)
                details_widget.setVisible(False)
                self.detail_widgets.append(details_widget)

                toggle_button = QToolButton()
                toggle_button.setArrowType(Qt.RightArrow)
                toggle_button.setCheckable(True)
                toggle_button.setChecked(False)
                toggle_button.setStyleSheet("QToolButton { border: none; padding: 0px; }")
                # Keep the arrow compact so it doesn't impact layout width
                toggle_button.setFixedSize(QSize(16, 16))
                toggle_button.clicked.connect(
                    lambda checked, w=details_widget, b=toggle_button: self.toggle_details(checked, w, b)
                )
                main_info_layout.addWidget(toggle_button)
                sensor_layout.addWidget(main_info_widget)
                sensor_layout.addWidget(details_widget)
            else:
                # No expand; still add main info
                sensor_layout.addWidget(main_info_widget)

            self.sensors_layout.addWidget(sensor_frame)


    def _get_status_style(self):
        """Get the CSS style for the status indicator based on system status."""
        status = self.system_status.lower() if self.system_status else 'unknown'

        if status == 'active':
            return """
                QLabel {
                    background-color: #28a745;
                    border-radius: 6px;
                    border: 1px solid #1e7e34;
                }
            """
        elif status == 'inactive':
            return """
                QLabel {
                    background-color: #dc3545;
                    border-radius: 6px;
                    border: 1px solid #bd2130;
                }
            """
        elif status == 'in maintenance':
            return """
                QLabel {
                    background-color: #fd7e14;
                    border-radius: 6px;
                    border: 1px solid #e8680f;
                }
            """
        else:
            return """
                QLabel {
                    background-color: #6c757d;
                    border-radius: 6px;
                    border: 1px solid #545b62;
                }
            """

    def apply_styling(self):
        """Apply styling to the card."""
        self.setStyleSheet("""
            #sensorCard {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            #sensorCard:hover {
                border: 1px solid #c0c0c0;
            }
            #sensorGroupFrame {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                margin-top: 5px;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-color: #bbb;
            }
        """)
