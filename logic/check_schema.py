import sqlite3
import os

def check_database_schema(db_path):
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("\n=== Database Schema ===")
    print(f"Database: {db_path}")
    print(f"Tables: {[t[0] for t in tables]}")
    
    # Get schema for each table
    for table in tables:
        table_name = table[0]
        print(f"\nTable: {table_name}")
        print("-" * 50)
        
        # Get table info
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        print("Columns:")
        for col in columns:
            print(f"  {col[1]} ({col[2]}) {'PRIMARY KEY' if col[5] else ''}")
        
        # Get some sample data
        try:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
            sample = cursor.fetchone()
            if sample:
                print("\nSample row:")
                for i, col in enumerate(columns):
                    print(f"  {col[1]}: {sample[i]}")
        except Exception as e:
            print(f"  Could not fetch sample data: {e}")
    
    conn.close()

if __name__ == "__main__":
    db_path = "flightlog.db"
    check_database_schema(db_path)
