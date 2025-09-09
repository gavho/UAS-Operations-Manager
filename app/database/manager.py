from typing import Dict, Any, Optional, List
import math
from PyQt5.QtCore import QObject, pyqtSignal as Signal
from sqlalchemy import text

class DatabaseManager(QObject):
    """
    Manages the database connection for the application.
    The connection is provided by an external source (e.g., a host application).
    """
    connection_set = Signal()
    platforms_updated = Signal()  # Emitted when platforms are added, updated, or deleted
    systems_updated = Signal()   # Emitted when systems are added, updated, or deleted

    def __init__(self):
        super().__init__()
        self.session = None
        self.models = None
        self.last_error = ''

    def set_connection(self, session, models):
        """
        Sets the database session and models from an external source.
        """
        print("[DATABASE] Setting external database connection.")
        self.session = session
        self.models = models
        self.connection_set.emit()
        print("[DATABASE] External database connection set successfully.")
        # Ensure DB constraints are present
        try:
            self._ensure_unique_sensor_type_per_system()
        except Exception as e:
            print(f"Warning: could not ensure constraints: {e}")

    def get_model(self, model_name: str):
        """
        Retrieves a model class from the models dictionary.
        """
        if not self.models:
            return None
        return self.models.get(model_name)

    def get_all_platforms(self):
        """Fetches all platforms from the database."""
        if not self.session:
            return []

        all_platforms = []
        Platform = self.models.get('platforms')
        if Platform:
            try:
                if self.session.is_active:
                    platforms = self.session.query(Platform).all()
                    for p in platforms:
                        all_platforms.append({
                            'id': p.platform_id, 'name': p.Name, 'manufacturer': p.Manufacturer,
                            'model': p.Model, 'serial_number': p.SN, 'faa_registration': p.FAA_Reg,
                            'status': p.status, 'Customer': p.Customer, 'RC_Model': p.RC_Model,
                            'RC_SN': p.RC_SN, 'RemoteID': p.RemoteID, 'Notes': p.Notes, 'acquisition_date': p.Acquisition_Date
                        })
                else:
                    print("Session is not active, skipping platform fetch.")
            except Exception as e:
                print(f"Error fetching platforms: {e}")
        return all_platforms

    def get_platform_names(self, active_only=True):
        """Fetches platform names for dropdown, with auto-generated names if Name is empty."""
        if not self.session:
            return []

        platform_names = []
        Platform = self.models.get('platforms')
        if Platform:
            try:
                if self.session.is_active:
                    query = self.session.query(Platform)
                    if active_only:
                        query = query.filter_by(status='Active')
                    platforms = query.all()
                    for p in platforms:
                        if p.Name and p.Name.strip():
                            platform_names.append(p.Name.strip())
                        else:
                            # Auto-generate name from Customer, Manufacturer, Model
                            customer = p.Customer or ""
                            manufacturer = p.Manufacturer or ""
                            model = p.Model or ""
                            auto_name = f"{customer} {manufacturer} {model}".strip()
                            if auto_name:
                                platform_names.append(auto_name)
                            else:
                                platform_names.append(f"Platform {p.platform_id}")
                else:
                    print("Session is not active, skipping platform names fetch.")
            except Exception as e:
                print(f"Error fetching platform names: {e}")
        return sorted(list(set(platform_names)))  # Remove duplicates and sort

    def get_chassis_list(self, active_only=True):
        """Fetches chassis serial numbers from systems table, optionally filtered by active status."""
        if not self.session:
            return []

        chassis_list = []
        try:
            if active_only:
                query = text("SELECT DISTINCT Chassis_SN FROM systems WHERE Chassis_SN IS NOT NULL AND Chassis_SN != '' AND Status = 'Active' ORDER BY Chassis_SN")
            else:
                query = text("SELECT DISTINCT Chassis_SN FROM systems WHERE Chassis_SN IS NOT NULL AND Chassis_SN != '' ORDER BY Chassis_SN")
            results = self.session.execute(query).fetchall()
            chassis_list = [row[0] for row in results]
        except Exception as e:
            print(f"Error fetching chassis list: {e}")
        return chassis_list

    def get_batteries_for_platform(self, platform_name=None):
        """Fetches batteries, optionally filtered by platform_model matching the selected platform."""
        if not self.session:
            return []

        batteries = []
        try:
            # First, find the platform_model for the selected platform
            platform_model = None
            if platform_name:
                Platform = self.models.get('platforms')
                if Platform:
                    # Try to find by Name first
                    platform = self.session.query(Platform).filter_by(Name=platform_name).first()
                    if not platform:
                        # If not found by Name, try to match auto-generated name
                        platforms = self.session.query(Platform).all()
                        for p in platforms:
                            auto_name = ""
                            if not p.Name or not p.Name.strip():
                                customer = p.Customer or ""
                                manufacturer = p.Manufacturer or ""
                                model = p.Model or ""
                                auto_name = f"{customer} {manufacturer} {model}".strip()
                            if auto_name == platform_name:
                                platform = p
                                break

                    if platform and platform.Model:
                        platform_model = platform.Model

            # Fetch batteries, filtering by platform_model if available
            if platform_model:
                query = text("SELECT name, battery_sn FROM batteries WHERE platform_model = :platform_model ORDER BY name")
                results = self.session.execute(query, {'platform_model': platform_model}).fetchall()
            else:
                query = text("SELECT name, battery_sn FROM batteries ORDER BY name")
                results = self.session.execute(query).fetchall()

            for row in results:
                name = row[0] or ""
                sn = row[1] or ""
                if sn:
                    batteries.append(f"{name} (SN: {sn})")
                else:
                    batteries.append(name)

        except Exception as e:
            print(f"Error fetching batteries: {e}")
        return batteries

    def get_sensor_data(self, model_ids: Optional[List[str]] = None):
        """Fetches sensor data from the new schema, grouped by Chassis."""
        if not self.session:
            return {}

        chassis_data = {}
        try:
            params = {}
            sql = """
                SELECT
                    s.Chassis_SN, s.Customer, s.Notes AS Chassis_Notes, s.Status AS System_Status,
                    i.Installed_ID, i.Sensor_SN, i.Notes AS Sensor_Notes,
                    se.Manufacturer, se.Sensor AS Sensor_Model, se.Type AS Sensor_Type,
                    cal.last_cal_date,
                    cal_data.RMSE_X,
                    cal_data.RMSE_Y,
                    cal_data.RMSE_Z,
                    cal_data.Sigma0,
                    cal_data.Plane_Fit
                FROM systems s
                LEFT JOIN installed_sensors i ON s.Chassis_SN = i.Chassis_SN AND i.Uninstall_Date IS NULL
                LEFT JOIN sensors se ON i.Sensor_Model_ID = se.Sensor_Model_ID
                LEFT JOIN (
                    SELECT Installed_ID, MAX(Calibration_Date) as last_cal_date
                    FROM calibration
                    GROUP BY Installed_ID
                ) cal ON i.Installed_ID = cal.Installed_ID
                LEFT JOIN calibration cal_data ON cal_data.Installed_ID = i.Installed_ID AND cal_data.Calibration_Date = cal.last_cal_date
                WHERE s.Chassis_SN IS NOT NULL AND s.Chassis_SN != ''
            """
            if model_ids:
                sql += " AND se.Type IN :model_ids"
                params['model_ids'] = tuple(model_ids)

            sql += " ORDER BY s.Chassis_SN, i.Sensor_SN"
            query = text(sql)

            results = self.session.execute(query, params).fetchall()
            print(f"Found {len(results)} sensor records from new schema.")

            for row in results:
                (chassis_sn, customer, chassis_notes, system_status, installed_id, sensor_sn,
                 sensor_notes, manufacturer, sensor_model, sensor_type, last_cal_date, 
                 rmse_x, rmse_y, rmse_z, sigma0, plane_fit) = row

                if chassis_sn not in chassis_data:
                    chassis_data[chassis_sn] = {
                        'chassis': chassis_sn,
                        'customer': customer or 'N/A',
                        'status': system_status or 'Unknown',
                        'last_calibrated': 'N/A',
                        'sensors': []
                    }

                if installed_id:
                    sensor_info = {
                        'id': installed_id,
                        'type': sensor_type or 'Unknown',
                        'status': 'Unknown',
                        'last_calibrated': last_cal_date or 'N/A',
                        'serial_number': sensor_sn or 'N/A',
                        'model': sensor_model or 'Unknown',
                        'manufacturer': manufacturer or 'Unknown',
                        'notes': sensor_notes or '',
                        'rmse': f"{math.sqrt(rmse_x**2 + rmse_y**2 + rmse_z**2):.4f}" if all(v is not None for v in [rmse_x, rmse_y, rmse_z]) else 'N/A',
                        'sigma0': sigma0,
                        'plane_fit': plane_fit,
                        'rmse_x': rmse_x,
                        'rmse_y': rmse_y,
                        'rmse_z': rmse_z
                    }
                    chassis_data[chassis_sn]['sensors'].append(sensor_info)

                    if last_cal_date and (chassis_data[chassis_sn]['last_calibrated'] == 'N/A' or last_cal_date > chassis_data[chassis_sn]['last_calibrated']):
                        chassis_data[chassis_sn]['last_calibrated'] = last_cal_date
        except Exception as e:
            print(f"Error in get_sensor_data: {e}")
            import traceback
            traceback.print_exc()

        return chassis_data

    def get_simplified_sensor_list(self):
        """Fetches a simplified list of sensors grouped by chassis for dialogs."""
        if not self.session:
            return {}

        sensor_data = {}
        try:
            sql = """
                SELECT
                    s.Chassis_SN AS chassis_sn,
                    i.Installed_ID AS installed_id,
                    i.Sensor_SN AS sensor_sn,
                    se.Sensor AS sensor_name,
                    se.Type AS sensor_type
                FROM systems s
                JOIN installed_sensors i ON s.Chassis_SN = i.Chassis_SN
                JOIN sensors se ON i.Sensor_Model_ID = se.Sensor_Model_ID
                WHERE i.Uninstall_Date IS NULL
                ORDER BY s.Chassis_SN, se.Sensor
            """
            query = text(sql)
            result = self.session.execute(query).mappings().all()

            for row in result:
                chassis_sn = row.chassis_sn
                if chassis_sn not in sensor_data:
                    sensor_data[chassis_sn] = []
                sensor_data[chassis_sn].append({
                    'installed_id': row.installed_id,
                    'sensor_sn': row.sensor_sn,
                    'sensor_name': row.sensor_name,
                    'sensor_type': row.sensor_type
                })
        except Exception as e:
            print(f"Error fetching simplified sensor data: {e}")

        return sensor_data

    def get_all_sensor_models(self) -> List[Dict[str, Any]]:
        """Fetches all sensor models from the database."""
        if not self.session:
            return []

        all_sensors = []
        try:
            query = text("SELECT Sensor_Model_ID, Type, Sensor, Manufacturer FROM sensors ORDER BY Type, Sensor")
            results = self.session.execute(query).fetchall()
            for row in results:
                all_sensors.append({
                    'sensor_model_id': row[0],
                    'type': row[1],
                    'model': row[2],
                    'manufacturer': row[3]
                })
        except Exception as e:
            print(f"Error fetching sensor models: {e}")
        return all_sensors

    def add_new_system(self, chassis_sn: str, customer: str, sensors: List[Dict[str, Any]]) -> bool:
        """Adds a new system and its installed sensors to the database."""
        if not self.session:
            return False

        try:
            self.session.execute(
                text("INSERT INTO systems (Chassis_SN, Customer, Notes) VALUES (:Chassis_SN, :Customer, :Notes)"),
                {'Chassis_SN': chassis_sn, 'Customer': customer, 'Notes': ''}
            )
            for sensor in sensors:
                self.session.execute(
                    text("INSERT INTO installed_sensors (Chassis_SN, Sensor_Model_ID, Sensor_SN, Notes) VALUES (:Chassis_SN, :Sensor_Model_ID, :Sensor_SN, :Notes)"),
                    {'Chassis_SN': chassis_sn, 'Sensor_Model_ID': sensor['sensor_model_id'], 'Sensor_SN': sensor['sensor_sn'], 'Notes': ''}
                )
            self.session.commit()
            print(f"Successfully added new system {chassis_sn}")
            return True
        except Exception as e:
            self.last_error = str(e)
            print(f"Error adding new system {chassis_sn}: {e}")
            self.session.rollback()
            return False

    def get_system_by_chassis_sn(self, chassis_sn: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single system and its sensors by Chassis SN."""
        if not self.session:
            return None

        query = text("""
            SELECT
                s.Chassis_SN AS chassis_sn, s.Customer, s.Notes, s.Status AS system_status,
                i.Sensor_SN AS sensor_serial_number, i.Installed_ID AS installed_id, sen.Sensor AS sensor_model,
                sen.Type AS sensor_type, sen.Manufacturer AS sensor_manufacturer,
                sen.Sensor_Model_ID AS sensor_model_id
            FROM systems s
            LEFT JOIN installed_sensors i ON s.Chassis_SN = i.Chassis_SN AND i.Uninstall_Date IS NULL
            LEFT JOIN sensors sen ON i.Sensor_Model_ID = sen.Sensor_Model_ID
            WHERE s.Chassis_SN = :chassis_sn
        """)
        try:
            result = self.session.execute(query, {'chassis_sn': chassis_sn}).mappings().all()
            if not result:
                return None
            first_row = result[0]
            system_data = {
                'chassis': first_row['chassis_sn'], 'customer': first_row['Customer'],
                'notes': first_row['Notes'], 'system_status': first_row['system_status'], 'sensors': []
            }
            for row in result:
                if row['sensor_model_id'] is not None:
                    system_data['sensors'].append({
                        'type': row['sensor_type'], 'model': row['sensor_model'],
                        'manufacturer': row['sensor_manufacturer'], 'serial_number': row['sensor_serial_number'],
                        'sensor_model_id': row['sensor_model_id'], 'installed_id': row['installed_id']
                    })
            return system_data
        except Exception as e:
            print(f"Error fetching system {chassis_sn}: {e}")
            return None

    def update_system(self, chassis_sn: str, customer: str, notes: str, sensors: List[Dict[str, Any]], status: Optional[str] = None) -> bool:
        """Update a system's customer, notes, status, and its list of installed sensors."""
        if not self.session:
            return False

        # Reset last error before attempting update
        self.last_error = ''

        try:
            # Update system details
            self.session.execute(
                text("UPDATE systems SET Customer = :customer, Notes = :notes, Status = :status WHERE Chassis_SN = :chassis_sn"),
                {'customer': customer, 'notes': notes, 'status': status, 'chassis_sn': chassis_sn}
            )

            # Install any new sensors provided (does not auto-uninstall missing ones).
            if sensors is not None:
                # Get current active sensors for this chassis to avoid duplicates
                existing_query = text("""
                    SELECT i.Sensor_Model_ID, i.Sensor_SN, se.Type
                    FROM installed_sensors i
                    JOIN sensors se ON i.Sensor_Model_ID = se.Sensor_Model_ID
                    WHERE i.Chassis_SN = :chassis_sn AND i.Uninstall_Date IS NULL
                """)
                existing_rows = self.session.execute(existing_query, {'chassis_sn': chassis_sn}).fetchall()
                existing_set = {(row[0], row[1]) for row in existing_rows}
                existing_types = {row[2] for row in existing_rows}

                # Build desired set from form
                desired = []  # (model_id, sn, type)
                for s in sensors:
                    model_id = s.get('sensor_model_id')
                    sn = (s.get('sensor_sn') or '').strip()
                    if model_id is None:
                        continue  # Skip if no model selected
                    # Look up the sensor Type for this model_id
                    trow = self.session.execute(text("SELECT Type FROM sensors WHERE Sensor_Model_ID = :id"), {'id': model_id}).fetchone()
                    sensor_type = trow[0] if trow else None
                    desired.append((model_id, sn, sensor_type))

                # Dedupe desired by Type: keep first occurrence only
                seen_types = set()
                filtered_desired = []
                for model_id, sn, s_type in desired:
                    if s_type in seen_types:
                        continue
                    seen_types.add(s_type)
                    filtered_desired.append((model_id, sn, s_type))

                # Exclude ones that conflict with an existing active Type
                filtered_desired = [item for item in filtered_desired if item[2] not in existing_types]

                # Exclude exact duplicates (model_id, sn)
                to_insert = [(m, s) for (m, s, _t) in filtered_desired if (m, s) not in existing_set]

                if to_insert:
                    install_query = text("""
                        INSERT INTO installed_sensors (Chassis_SN, Sensor_Model_ID, Sensor_SN, Notes)
                        VALUES (:chassis_sn, :model_id, :sn, '')
                    """)
                    for model_id, sn in to_insert:
                        self.session.execute(install_query, {'chassis_sn': chassis_sn, 'model_id': model_id, 'sn': sn})

            self.session.commit()
            print(f"Successfully updated system {chassis_sn}")
            return True
        except Exception as e:
            # Capture and translate constraint errors from triggers
            err_text = str(e)
            if 'Duplicate sensor Type for chassis' in err_text:
                self.last_error = (
                    'Constraint violation: Only one active sensor per Type is allowed per chassis. '
                    'Deprecate or delete the existing sensor of that Type before adding another.'
                )
            else:
                self.last_error = err_text
            print(f"Error updating system {chassis_sn}: {e}")
            self.session.rollback()
            return False

    def deprecate_installed_sensor(self, installed_id: int) -> bool:
        """Marks an installed sensor as deprecated by setting its Uninstall_Date to now."""
        if not self.session:
            return False
        try:
            self.session.execute(
                text("UPDATE installed_sensors SET Uninstall_Date = datetime('now') WHERE Installed_ID = :installed_id"),
                {'installed_id': installed_id}
            )
            self.session.commit()
            print(f"Deprecated installed sensor {installed_id}")
            return True
        except Exception as e:
            self.last_error = str(e)
            print(f"Error deprecating installed sensor {installed_id}: {e}")
            self.session.rollback()
            return False

    def delete_installed_sensor(self, installed_id: int) -> bool:
        """Permanently deletes an installed sensor record."""
        if not self.session:
            return False
        try:
            self.session.execute(
                text("DELETE FROM installed_sensors WHERE Installed_ID = :installed_id"),
                {'installed_id': installed_id}
            )
            self.session.commit()
            print(f"Deleted installed sensor {installed_id}")
            return True
        except Exception as e:
            self.last_error = str(e)
            print(f"Error deleting installed sensor {installed_id}: {e}")
            self.session.rollback()
            return False

    def delete_system(self, chassis_sn: str) -> bool:
        """Deletes a system and its associated sensors from the database."""
        if not self.session:
            return False

        try:
            self.session.execute(
                text("DELETE FROM installed_sensors WHERE Chassis_SN = :chassis_sn"),
                {'chassis_sn': chassis_sn}
            )
            self.session.execute(
                text("DELETE FROM systems WHERE Chassis_SN = :chassis_sn"),
                {'chassis_sn': chassis_sn}
            )
            self.session.commit()
            print(f"Successfully deleted system {chassis_sn}")
            return True
        except Exception as e:
            print(f"Error deleting system {chassis_sn}: {e}")
            self.session.rollback()
            return False

    def _ensure_unique_sensor_type_per_system(self):
        """Creates triggers to enforce one active sensor per Type per chassis (Uninstall_Date IS NULL)."""
        if not self.session:
            return
        # Check and create BEFORE INSERT trigger
        check_trigger_sql = text("SELECT name FROM sqlite_master WHERE type='trigger' AND name=:name")
        triggers = {
            'trg_installed_sensors_unique_type_ins': """
                CREATE TRIGGER trg_installed_sensors_unique_type_ins
                BEFORE INSERT ON installed_sensors
                WHEN NEW.Uninstall_Date IS NULL
                BEGIN
                    SELECT RAISE(ABORT, 'Duplicate sensor Type for chassis')
                    WHERE EXISTS (
                        SELECT 1
                        FROM installed_sensors i
                        JOIN sensors se1 ON i.Sensor_Model_ID = se1.Sensor_Model_ID
                        JOIN sensors se2 ON se2.Sensor_Model_ID = NEW.Sensor_Model_ID
                        WHERE i.Chassis_SN = NEW.Chassis_SN
                          AND i.Uninstall_Date IS NULL
                          AND se1.Type = se2.Type
                    );
                END;
            """,
            'trg_installed_sensors_unique_type_upd': """
                CREATE TRIGGER trg_installed_sensors_unique_type_upd
                BEFORE UPDATE ON installed_sensors
                WHEN NEW.Uninstall_Date IS NULL
                BEGIN
                    SELECT RAISE(ABORT, 'Duplicate sensor Type for chassis')
                    WHERE EXISTS (
                        SELECT 1
                        FROM installed_sensors i
                        JOIN sensors se1 ON i.Sensor_Model_ID = se1.Sensor_Model_ID
                        JOIN sensors se2 ON se2.Sensor_Model_ID = NEW.Sensor_Model_ID
                        WHERE i.Chassis_SN = NEW.Chassis_SN
                          AND i.Installed_ID != NEW.Installed_ID
                          AND i.Uninstall_Date IS NULL
                          AND se1.Type = se2.Type
                    );
                END;
            """
        }
        for name, create_sql in triggers.items():
            exists = self.session.execute(check_trigger_sql, {'name': name}).fetchone()
            if not exists:
                self.session.execute(text(create_sql))
        self.session.commit()

    def get_calibration_log(self, chassis_sn: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetches calibration records from the database, optionally filtered by Chassis_SN."""
        if not self.session:
            return []

        all_records = []
        try:
            params = {}
            sql = """
                SELECT 
                    c.id,
                    c.Calibration_ID, 
                    se.Sensor || ' (SN: ' || i.Sensor_SN || ')' AS Sensor,
                    c.Installed_ID, 
                    c.Platform AS Platform, 
                    c.Calibration_Date, 
                    c.Status,
                    c.RMSE_X, c.RMSE_Y, c.RMSE_Z, c.Sigma0, c.Plane_Fit, c.Notes
                FROM calibration c
                JOIN installed_sensors i ON c.Installed_ID = i.Installed_ID
                JOIN systems s ON i.Chassis_SN = s.Chassis_SN
                JOIN sensors se ON i.Sensor_Model_ID = se.Sensor_Model_ID
            """
            if chassis_sn:
                sql += " WHERE s.Chassis_SN = :chassis_sn"
                params['chassis_sn'] = chassis_sn
            
            sql += " ORDER BY c.Calibration_Date DESC"

            query = text(sql)
            results = self.session.execute(query, params).mappings().all()
            all_records.extend(results)
        except Exception as e:
            print(f"Error fetching calibration log: {e}")
        return all_records

    def add_calibration_records(self, cal_data_list: List[Dict[str, Any]]) -> bool:
        """Adds new calibration records to the database."""
        if not self.session:
            return False

        try:
            query = text("""
                INSERT INTO calibration (
                    Calibration_ID, Installed_ID, Platform, Calibration_Date, Status,
                    RMSE_X, RMSE_Y, RMSE_Z, Sigma0, Plane_Fit, Notes
                ) VALUES (
                    :Calibration_ID, :Installed_ID, :Platform, :Calibration_Date, :Status,
                    :RMSE_X, :RMSE_Y, :RMSE_Z, :Sigma0, :Plane_Fit, :Notes
                )
            """)
            for cal_data in cal_data_list:
                self.session.execute(query, cal_data)
            
            self.session.commit()
            print(f"Successfully added {len(cal_data_list)} calibration records.")
            return True
        except Exception as e:
            self.last_error = str(e)
            print(f"Error adding calibration records: {e}")
            self.session.rollback()
            return False

    def update_calibration_records(self, cal_data_list: List[Dict[str, Any]]) -> bool:
        """Updates existing calibration records in the database using the 'id' field."""
        if not self.session:
            return False

        try:
            query = text("""
                UPDATE calibration SET
                    Calibration_ID = :Calibration_ID,
                    Installed_ID = :Installed_ID,
                    Platform = :Platform,
                    Calibration_Date = :Calibration_Date,
                    Status = :Status,
                    RMSE_X = :RMSE_X,
                    RMSE_Y = :RMSE_Y,
                    RMSE_Z = :RMSE_Z,
                    Sigma0 = :Sigma0,
                    Plane_Fit = :Plane_Fit,
                    Notes = :Notes
                WHERE id = :id
            """)
            for cal_data in cal_data_list:
                if 'id' not in cal_data:
                    print("Error: Missing 'id' in calibration data for update")
                    continue
                self.session.execute(query, cal_data)
            
            self.session.commit()
            print(f"Successfully updated {len(cal_data_list)} calibration records.")
            return True
        except Exception as e:
            self.last_error = str(e)
            print(f"Error updating calibration records: {e}")
            self.session.rollback()
            return False

    def update_calibration_record(self, cal_data: Dict[str, Any]) -> bool:
        """Updates a single calibration record; convenience wrapper for update_calibration_records."""
        return self.update_calibration_records([cal_data])

    def delete_calibration_records(self, record_ids: List[str]) -> bool:
        """Deletes calibration records from the database using the 'id' field."""
        if not self.session or not record_ids:
            return False

        try:
            # SQLite requires a different syntax for IN with parameters
            placeholders = ', '.join([':id' + str(i) for i in range(len(record_ids))])
            params = {'id' + str(i): val for i, val in enumerate(record_ids)}
            query = text(f"DELETE FROM calibration WHERE id IN ({placeholders})")
            self.session.execute(query, params)
            self.session.commit()
            print(f"Successfully deleted {len(record_ids)} calibration records.")
            return True
        except Exception as e:
            self.last_error = str(e)
            print(f"Error deleting calibration records: {e}")
            import traceback
            traceback.print_exc()
            self.session.rollback()
            return False

    def get_calibration_history_for_sensor(self, installed_id: int) -> List[Dict[str, Any]]:
        """Fetches the calibration history for a specific sensor."""
        if not self.session or not installed_id:
            return []

        try:
            query = text("""
                SELECT Calibration_Date, Status, RMSE_X, RMSE_Y, RMSE_Z, Sigma0, Plane_Fit, Notes
                FROM calibration
                WHERE Installed_ID = :installed_id
                ORDER BY Calibration_Date DESC
            """)
            results = self.session.execute(query, {'installed_id': installed_id}).mappings().all()
            return results
        except Exception as e:
            print(f"Error fetching calibration history: {e}")
            return []

    def get_chassis_sn_by_installed_id(self, installed_id: int) -> Optional[str]:
        """Returns the chassis serial number for a given Installed_ID, or None if not found."""
        if not self.session or not installed_id:
            return None
        try:
            query = text("""
                SELECT Chassis_SN
                FROM installed_sensors
                WHERE Installed_ID = :installed_id
            """)
            result = self.session.execute(query, {"installed_id": installed_id}).fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Error fetching chassis by installed_id {installed_id}: {e}")
            return None

    def get_installed_sensor_info(self, installed_id: int) -> Optional[Dict[str, Any]]:
        """Returns sensor info for a given Installed_ID: chassis_sn, sensor_type, sensor_model, manufacturer."""
        if not self.session or not installed_id:
            return None
        try:
            query = text(
                """
                SELECT i.Chassis_SN AS chassis_sn,
                       se.Type AS sensor_type,
                       se.Sensor AS sensor_model,
                       se.Manufacturer AS manufacturer
                FROM installed_sensors i
                JOIN sensors se ON i.Sensor_Model_ID = se.Sensor_Model_ID
                WHERE i.Installed_ID = :installed_id
                """
            )
            row = self.session.execute(query, {"installed_id": installed_id}).mappings().first()
            if not row:
                return None
            return {
                'chassis_sn': row.chassis_sn,
                'sensor_type': row.sensor_type,
                'sensor_model': row.sensor_model,
                'manufacturer': row.manufacturer,
            }
        except Exception as e:
            print(f"Error fetching installed sensor info for {installed_id}: {e}")
            return None

    def get_calibration_count_for_date(self, chassis_sn: str, cal_date: str) -> int:
        """Counts existing calibration records for a given chassis on a specific date."""
        if not self.session:
            return 0

        try:
            query = text("""
                SELECT COUNT(c.Calibration_ID)
                FROM calibration c
                JOIN installed_sensors i ON c.Installed_ID = i.Installed_ID
                WHERE i.Chassis_SN = :chassis_sn AND c.Calibration_Date = :cal_date
            """)
            result = self.session.execute(query, {'chassis_sn': chassis_sn, 'cal_date': cal_date}).scalar()
            return result if result is not None else 0
        except Exception as e:
            print(f"Error counting calibrations for date {cal_date}: {e}")
            return 0

# Create a single, global instance for the entire app to use.
db_manager = DatabaseManager()
