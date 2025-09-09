import sqlite3

DB_PATH = 'flightlog.db'

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def add_maintenance_log(platform_id, date, description, parts_used, cost):
    """Inserts a new maintenance record linked to a platform_id."""
    conn = get_db_connection()
    try:
        conn.execute(
            'INSERT INTO maintenance (platform_id, date, description, parts_used, cost) VALUES (?, ?, ?, ?, ?)',
            (platform_id, date, description, parts_used, cost)
        )
        conn.commit()
    finally:
        conn.close()

def get_logs_for_platform(platform_id):
    """Retrieves all maintenance records for a specific platform_id."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM maintenance WHERE platform_id = ?', (platform_id,))
        logs = cursor.fetchall()
        return [dict(log) for log in logs]
    finally:
        conn.close()

def delete_maintenance_log(log_id):
    """Removes a specific maintenance record."""
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM maintenance WHERE id = ?', (log_id,))
        conn.commit()
    finally:
        conn.close()
