import os
import sys
from pathlib import Path
import traceback
from sqlalchemy import create_engine, MetaData, Column, Integer, String, Text, TIMESTAMP, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.automap import automap_base

# Declarative base for our explicit models
Base = declarative_base()

# SpatiaLite integration settings
EXTENSION_NAME = "mod_spatialite"
LIB_DIR = (Path(__file__).resolve().parents[2] / "lib").resolve()

def _register_spatialite_extension(engine):
    """
    Register a per-connection hook that:
    - Adds the ./lib directory to the Windows DLL search path (Python 3.8+)
    - Enables SQLite extension loading
    - Loads the SpatiaLite extension (mod_spatialite)
    """
    def _on_connect(dbapi_connection, connection_record):
        # Ensure DLL search path includes our bundled ./lib on Windows
        try:
            if sys.platform == "win32" and sys.version_info >= (3, 8):
                os.add_dll_directory(str(LIB_DIR))
            else:
                # Fallback: prepend to PATH for non-Windows or older Python
                os.environ["PATH"] = str(LIB_DIR) + os.pathsep + os.environ.get("PATH", "")
        except Exception as e:
            print(f"Warning: Failed to adjust DLL search path: {e}")

        # Enable and load the extension
        try:
            dbapi_connection.enable_load_extension(True)
            loaded = False
            try:
                # Try by short name (relies on PATH/add_dll_directory)
                dbapi_connection.load_extension(EXTENSION_NAME)
                loaded = True
            except Exception:
                # Try explicit path to the DLL (Windows .dll, else .so)
                candidate = str(LIB_DIR / (EXTENSION_NAME + (".dll" if sys.platform == "win32" else ".so")))
                dbapi_connection.load_extension(candidate)
                loaded = True
            if not loaded:
                raise RuntimeError("SpatiaLite extension was not loaded.")
        except Exception as e:
            print(f"Warning: Failed to load SpatiaLite extension '{EXTENSION_NAME}': {e}")

    # Attach listener so every new DB-API connection loads SpatiaLite
    event.listen(engine, "connect", _on_connect)

# Explicit model for the 'platforms' table matching the user's schema.
# We are telling SQLAlchemy that 'id' is the primary key for ORM purposes,
# which allows automap to work even if it's not a PK in the DB schema.
class Platform(Base):
    __tablename__ = 'platforms'

    platform_id = Column('platform_id', Integer, primary_key=True)
    Customer = Column('Customer', Text)
    Manufacturer = Column('Manufacturer', Text)
    Model = Column('Model', Text)
    Name = Column('Name', Text)
    RC_Model = Column('RC_Model', Text)
    RC_SN = Column('RC_SN', Text)
    SN = Column('SN', Text)
    RemoteID = Column('RemoteID', Text)
    FAA_Reg = Column('FAA_Reg', Text)
    Acquisition_Date = Column('Acquisition_Date', Text)
    status = Column('status', Text)
    Notes = Column('Notes', Text)
    created_at = Column('created_at', TIMESTAMP)
    updated_at = Column('updated_at', TIMESTAMP)

    def __repr__(self):
        return f"<Platform(Name='{self.Name}', SN='{self.SN}')>"

def get_session_and_models(db_path: str) -> tuple:
    """
    Initializes a database connection using a hybrid approach:
    - An explicit model is used for the 'platforms' table to handle its lack of a primary key.
    - SQLAlchemy's automap feature discovers all other tables dynamically.

    Args:
        db_path (str): The file path to the SQLite database.

    Returns:
        tuple: A tuple containing the session object and a dictionary of all
               discovered model classes, or (None, None) if an error occurs.
    """
    try:
        if not os.path.exists(db_path):
            print(f"Error: Database file not found at {db_path}")
            return None, None

        engine = create_engine(f"sqlite:///{db_path}")
        # Ensure SpatiaLite extension loads for each connection
        _register_spatialite_extension(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Verify SpatiaLite is available and optionally initialize metadata
        try:
            with engine.connect() as conn:
                try:
                    version = conn.exec_driver_sql("SELECT spatialite_version();").scalar()
                    if version:
                        print(f"SpatiaLite loaded. Version: {version}")
                except Exception as ver_err:
                    print(f"Warning: Unable to verify SpatiaLite version: {ver_err}")

                # Initialize spatial metadata if core tables are missing
                try:
                    existing_count = conn.exec_driver_sql(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN ('geometry_columns','spatial_ref_sys');"
                    ).scalar()
                    if existing_count is not None and existing_count < 2:
                        conn.exec_driver_sql("SELECT InitSpatialMetaData(1);")
                        print("Initialized SpatiaLite metadata tables (geometry_columns, spatial_ref_sys).")
                except Exception as init_err:
                    # Non-fatal; only informational
                    print(f"Info: Skipped InitSpatialMetaData: {init_err}")
        except Exception as e:
            print(f"Warning: SpatiaLite check/initialization skipped due to connection error: {e}")

        # Reflect all tables from the database
        metadata = MetaData()
        metadata.reflect(bind=engine)

        # Remove the 'platforms' table from the reflected metadata to avoid
        # conflicts with our explicit model, which handles the missing primary key.
        if 'platforms' in metadata.tables:
            metadata.remove(metadata.tables['platforms'])

        # Automap base for dynamically loaded tables
        AutomapBase = automap_base(metadata=metadata)
        AutomapBase.prepare()

        # Collect all models for the application to use
        models = {}
        
        # Add all automapped tables to the models dictionary
        for name, cls in AutomapBase.classes.items():
            models[name] = cls
            # Add a sanitized version for names with hyphens
            if '-' in name:
                models[name.replace('-', '_')] = cls
        
        # Add our explicit Platform model to the dictionary
        models['platforms'] = Platform
        
        
        if 'platforms' in models:
            print("Successfully loaded 'platforms' table model.")
        else:
            print("Warning: Failed to load 'platforms' table model.")
            
        if 'bsc-sensor' in models or 'bsc_sensor' in models:
            print("Successfully loaded 'bsc-sensor' table model.")
        else:
            print("Warning: 'bsc-sensor' table not found in the database.")

        return session, models

    except Exception as e:
        print(f"Error loading database schema: {e}")
        traceback.print_exc()
        return None, None
