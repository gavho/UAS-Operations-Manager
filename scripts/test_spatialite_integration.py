#!/usr/bin/env python3
"""
Comprehensive SpatiaLite Integration Test Suite
Tests various SpatiaLite functions and spatial operations
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.database.core import get_session_and_models

def test_basic_spatialite_functions():
    """Test basic SpatiaLite functions"""
    print("=== Testing Basic SpatiaLite Functions ===")

    session, models = get_session_and_models(str(project_root / 'flightlog.db'))

    try:
        # Test spatialite_version()
        result = session.execute("SELECT spatialite_version();").scalar()
        print(f"✅ SpatiaLite version: {result}")

        # Test geometry_columns table exists
        result = session.execute("SELECT COUNT(*) FROM geometry_columns;").scalar()
        print(f"✅ geometry_columns table exists: {result} records")

        # Test spatial_ref_sys table exists
        result = session.execute("SELECT COUNT(*) FROM spatial_ref_sys;").scalar()
        print(f"✅ spatial_ref_sys table exists: {result} records")

        # Test basic geometry functions
        result = session.execute("SELECT ST_AsText(ST_GeomFromText('POINT(1 1)'));").scalar()
        print(f"✅ ST_AsText works: {result}")

        # Test spatial functions
        result = session.execute("SELECT ST_Area(ST_Buffer(ST_GeomFromText('POINT(0 0)'), 1));").scalar()
        print(f"✅ ST_Buffer + ST_Area works: {result}")

    except Exception as e:
        print(f"❌ Error in basic functions: {e}")
    finally:
        session.close()

def test_spatial_queries():
    """Test spatial queries and operations"""
    print("\n=== Testing Spatial Queries ===")

    session, models = get_session_and_models(str(project_root / 'flightlog.db'))

    try:
        # Create a test table with spatial data
        session.execute("""
            CREATE TABLE IF NOT EXISTS test_locations (
                id INTEGER PRIMARY KEY,
                name TEXT,
                location GEOMETRY
            );
        """)

        # Insert test data
        session.execute("""
            INSERT OR REPLACE INTO test_locations (id, name, location) VALUES
            (1, 'Location A', ST_GeomFromText('POINT(-122.4194 37.7749)', 4326)),
            (2, 'Location B', ST_GeomFromText('POINT(-118.2437 34.0522)', 4326)),
            (3, 'Location C', ST_GeomFromText('POINT(-87.6298 41.8781)', 4326));
        """)

        # Test spatial queries
        # Find points within a bounding box
        result = session.execute("""
            SELECT name, ST_AsText(location) as coords
            FROM test_locations
            WHERE ST_Within(location, ST_GeomFromText('POLYGON((-130 30, -110 30, -110 45, -130 45, -130 30))', 4326));
        """).fetchall()

        print(f"✅ Spatial query results: {len(result)} locations found")
        for row in result:
            print(f"   - {row[0]}: {row[1]}")

        # Test distance calculation
        result = session.execute("""
            SELECT ST_Distance(
                ST_GeomFromText('POINT(-122.4194 37.7749)', 4326),
                ST_GeomFromText('POINT(-118.2437 34.0522)', 4326)
            ) as distance;
        """).scalar()

        print(f"✅ Distance calculation: {result:.2f} degrees")

        # Test spatial indexing capability
        session.execute("SELECT CreateSpatialIndex('test_locations', 'location');")
        print("✅ Spatial index created successfully")

    except Exception as e:
        print(f"❌ Error in spatial queries: {e}")
    finally:
        session.close()

def test_spatialite_metadata():
    """Test SpatiaLite metadata tables"""
    print("\n=== Testing SpatiaLite Metadata ===")

    session, models = get_session_and_models(str(project_root / 'flightlog.db'))

    try:
        # Check spatial metadata
        result = session.execute("""
            SELECT COUNT(*) FROM geometry_columns
            WHERE f_table_name = 'test_locations' AND f_geometry_column = 'location';
        """).scalar()

        if result > 0:
            print("✅ Spatial metadata registered for test_locations table")
        else:
            print("ℹ️  No spatial metadata found (expected for new table)")

        # List all spatial tables
        result = session.execute("""
            SELECT f_table_name, f_geometry_column, type, coord_dimension, srid
            FROM geometry_columns;
        """).fetchall()

        print(f"✅ Spatial tables registered: {len(result)}")
        for row in result:
            print(f"   - {row[0]}.{row[1]}: {row[2]} (SRID: {row[4]})")

    except Exception as e:
        print(f"❌ Error in metadata test: {e}")
    finally:
        session.close()

def test_advanced_spatial_functions():
    """Test advanced spatial functions"""
    print("\n=== Testing Advanced Spatial Functions ===")

    session, models = get_session_and_models(str(project_root / 'flightlog.db'))

    try:
        # Test geometry transformations
        result = session.execute("""
            SELECT ST_AsText(ST_Transform(
                ST_GeomFromText('POINT(-122.4194 37.7749)', 4326),
                3857
            ));
        """).scalar()

        print(f"✅ Coordinate transformation (4326→3857): {result}")

        # Test geometry validation
        result = session.execute("""
            SELECT ST_IsValid(ST_GeomFromText('POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))'));
        """).scalar()

        print(f"✅ Geometry validation: {'Valid' if result else 'Invalid'}")

        # Test spatial relationships
        result = session.execute("""
            SELECT ST_Contains(
                ST_GeomFromText('POLYGON((0 0, 2 0, 2 2, 0 2, 0 0))'),
                ST_GeomFromText('POINT(1 1)')
            );
        """).scalar()

        print(f"✅ Spatial relationship (Contains): {'True' if result else 'False'}")

    except Exception as e:
        print(f"❌ Error in advanced functions: {e}")
    finally:
        session.close()

def cleanup_test_data():
    """Clean up test data"""
    print("\n=== Cleaning Up Test Data ===")

    session, models = get_session_and_models(str(project_root / 'flightlog.db'))

    try:
        # Drop test table
        session.execute("DROP TABLE IF EXISTS test_locations;")
        print("✅ Test table dropped")

        # Remove spatial index
        session.execute("SELECT DisableSpatialIndex('test_locations', 'location');")
        print("✅ Spatial index disabled")

    except Exception as e:
        print(f"❌ Error cleaning up: {e}")
    finally:
        session.close()

def main():
    """Run all tests"""
    print("🚀 Starting SpatiaLite Integration Tests")
    print(f"Database: {project_root / 'flightlog.db'}")
    print("=" * 50)

    try:
        test_basic_spatialite_functions()
        test_spatial_queries()
        test_spatialite_metadata()
        test_advanced_spatial_functions()
        cleanup_test_data()

        print("\n" + "=" * 50)
        print("🎉 All SpatiaLite tests completed!")
        print("\nNext steps:")
        print("- Your app automatically loads SpatiaLite on startup")
        print("- Use spatial functions in your database queries")
        print("- Create geometry columns with 'GEOMETRY' type")
        print("- Use ST_* functions for spatial operations")

    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
