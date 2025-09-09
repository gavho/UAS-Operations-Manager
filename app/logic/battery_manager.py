import sqlite3

DB_PATH = 'flightlog.db'

def _has_column(conn, table_name: str, column_name: str) -> bool:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cur.fetchall())

def batteries_support_platform_model() -> bool:
    conn = get_db_connection()
    try:
        return _has_column(conn, 'batteries', 'platform_model')
    finally:
        conn.close()

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def add_battery(name, battery_sn, acquisition_date, notes=None, initial_cycles=0, platform_model: str = None):
    """Inserts a new battery record aligned to schema (name, battery_sn, acquisition_date, cycle_count, notes).
    If the batteries table has a 'platform_model' column, it will be set when provided.
    """
    conn = get_db_connection()
    try:
        # Allow optional serial numbers; if None, store as empty string to avoid NOT NULL constraint issues
        battery_sn_to_store = battery_sn if battery_sn is not None else ''
        if _has_column(conn, 'batteries', 'platform_model'):
            conn.execute(
                'INSERT INTO batteries (name, battery_sn, acquisition_date, cycle_count, notes, platform_model) VALUES (?, ?, ?, ?, ?, ?)',
                (name, battery_sn_to_store, acquisition_date, initial_cycles, notes, platform_model)
            )
        else:
            conn.execute(
                'INSERT INTO batteries (name, battery_sn, acquisition_date, cycle_count, notes) VALUES (?, ?, ?, ?, ?)',
                (name, battery_sn_to_store, acquisition_date, initial_cycles, notes)
            )
        conn.commit()
    finally:
        conn.close()

def get_all_batteries():
    """Retrieves all batteries."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM batteries')
        batteries = cursor.fetchall()
        return [dict(row) for row in batteries]
    finally:
        conn.close()

def increment_cycle_count(battery_id):
    """Takes a battery_id and increments its cycle_count by one."""
    conn = get_db_connection()
    try:
        conn.execute('UPDATE batteries SET cycle_count = cycle_count + 1 WHERE battery_id = ?', (battery_id,))
        conn.commit()
    finally:
        conn.close()

def delete_battery(battery_id):
    """Removes a specific battery record."""
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM batteries WHERE battery_id = ?', (battery_id,))
        conn.commit()
    finally:
        conn.close()

def update_battery(battery_id, name=None, battery_sn=None, acquisition_date=None, notes=None, platform_model=None, cycle_count=None):
    """Updates fields for a battery. Only non-None fields are updated.
    Respects presence of 'platform_model' column.
    """
    if not battery_id:
        return
    conn = get_db_connection()
    try:
        fields = []
        params = []
        if name is not None:
            fields.append('name = ?')
            params.append(name)
        if battery_sn is not None:
            # If clearing serial (None at UI), coerce to empty string to satisfy potential NOT NULL
            fields.append('battery_sn = ?')
            params.append(battery_sn if battery_sn is not None else '')
        if acquisition_date is not None:
            fields.append('acquisition_date = ?')
            params.append(acquisition_date)
        if notes is not None:
            fields.append('notes = ?')
            params.append(notes)
        if platform_model is not None and _has_column(conn, 'batteries', 'platform_model'):
            fields.append('platform_model = ?')
            params.append(platform_model)
        if cycle_count is not None:
            fields.append('cycle_count = ?')
            params.append(cycle_count)
        if not fields:
            return
        params.append(battery_id)
        sql = f"UPDATE batteries SET {', '.join(fields)} WHERE battery_id = ?"
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()
