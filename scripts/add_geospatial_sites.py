#!/usr/bin/env python3
"""
Add geospatial reference to the 'sites' table using SpatiaLite
"""

import os
import sys
import sqlite3
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Setup DLL path for SpatiaLite
if sys.platform == "win32" and sys.version_info >= (3, 8):
    os.add_dll_directory(str(project_root / 'lib'))
else:
    os.environ["PATH"] = str(project_root / 'lib') + os.pathsep + os.environ.get("PATH", "")

def add_geospatial_column():
    """Add geometry column to sites table and register it with SpatiaLite"""
    print("=== Adding Geospatial Column to Sites Table ===")

    db_path = str(project_root / 'flightlog.db')

    # Connect with SpatiaLite support
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    conn.load_extension('mod_spatialite')

    try:
        # Check if geometry column already exists
        cursor = conn.execute("""
            SELECT COUNT(*) FROM geometry_columns
            WHERE f_table_name = 'sites' AND f_geometry_column = 'geom';
        """)
        result = cursor.fetchone()[0]

        if result > 0:
            print("✅ Geometry column 'geom' already exists in sites table")
            return

        # Add geometry column to sites table
        print("Adding geometry column 'geom' to sites table...")
        conn.execute("""
            ALTER TABLE sites ADD COLUMN geom GEOMETRY;
        """)

        # Register the geometry column with SpatiaLite
        print("Registering geometry column with SpatiaLite...")
        conn.execute("""
            INSERT INTO geometry_columns (f_table_name, f_geometry_column, geometry_type, coord_dimension, srid, spatial_index_enabled)
            VALUES ('sites', 'geom', 0, 2, 4326, 0);
        """)

        # Create spatial index for better performance
        print("Creating spatial index...")
        conn.execute("""
            SELECT CreateSpatialIndex('sites', 'geom');
        """)

        conn.commit()
        print("✅ Successfully added geospatial column to sites table")

        # Verify the changes
        cursor = conn.execute("""
            SELECT f_table_name, f_geometry_column, geometry_type, srid
            FROM geometry_columns
            WHERE f_table_name = 'sites';
        """)
        result = cursor.fetchall()

        print("✅ Geometry column registered:")
        for row in result:
            print(f"   - Table: {row[0]}, Column: {row[1]}, Type: {row[2]}, SRID: {row[3]}")

    except Exception as e:
        print(f"❌ Error adding geospatial column: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def test_geospatial_functionality():
    """Test the new geospatial functionality"""
    print("\n=== Testing Geospatial Functionality ===")

    db_path = str(project_root / 'flightlog.db')

    # Connect with SpatiaLite support
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    conn.load_extension('mod_spatialite')

    try:
        # Test inserting a point geometry
        print("Testing geometry insertion...")
        conn.execute("""
            UPDATE sites SET geom = ST_GeomFromText('POINT(-122.4194 37.7749)', 4326)
            WHERE site_ID = 1;
        """)

        # Test spatial query
        cursor = conn.execute("""
            SELECT name, ST_AsText(geom) as coordinates
            FROM sites
            WHERE geom IS NOT NULL
            LIMIT 5;
        """)
        result = cursor.fetchall()

        print(f"✅ Spatial query successful: {len(result)} sites with geometry")
        for row in result:
            print(f"   - {row[0]}: {row[1]}")

        # Test spatial functions
        cursor = conn.execute("""
            SELECT ST_AsText(ST_Buffer(ST_GeomFromText('POINT(-122.4194 37.7749)', 4326), 0.01));
        """)
        result = cursor.fetchone()[0]

        print(f"✅ Spatial buffer function works: {result}")

        conn.commit()

    except Exception as e:
        print(f"❌ Error testing geospatial functionality: {e}")
        conn.rollback()
    finally:
        conn.close()

def main():
    """Main function"""
    print("🚀 Adding Geospatial Reference to Sites Table")
    print(f"Database: {project_root / 'flightlog.db'}")
    print("=" * 50)

    try:
        add_geospatial_column()
        test_geospatial_functionality()

        print("\n" + "=" * 50)
        print("🎉 Geospatial column successfully added to sites table!")
        print("\nWhat was accomplished:")
        print("- Added 'geom' GEOMETRY column to sites table")
        print("- Registered column with SpatiaLite metadata")
        print("- Created spatial index for performance")
        print("- Tested basic spatial operations")
        print("\nUsage:")
        print("- Use ST_GeomFromText() to insert geometries")
        print("- Use ST_AsText() to retrieve geometries")
        print("- Use spatial functions like ST_Distance(), ST_Within(), etc.")
        print("- SRID 4326 (WGS84) is used for latitude/longitude coordinates")

    except Exception as e:
        print(f"\n❌ Failed to add geospatial column: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
