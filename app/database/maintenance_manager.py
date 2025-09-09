from datetime import datetime
from sqlalchemy import and_
from sqlalchemy.exc import SQLAlchemyError
from .manager import db_manager

class MaintenanceManager:
    """
    Handles all database operations related to maintenance logs.
    """
    
    @staticmethod
    def add_maintenance_log(platform_id, maintenance_type, description, date=None, technician=None, **kwargs):
        """
        Adds a new maintenance record for a specific platform.
        
        Args:
            platform_id (int): The ID of the platform this maintenance is for
            maintenance_type (str): Type of maintenance (e.g., 'Routine', 'Repair', 'Inspection')
            description (str): Detailed description of the maintenance performed
            date (datetime, optional): When the maintenance was performed. Defaults to current time.
            technician (str, optional): Name of the technician who performed the maintenance
            **kwargs: Additional maintenance details to store
            
        Returns:
            dict: The created maintenance record, or None if failed
        """
        if not db_manager.session:
            print("Error: No database connection available.")
            return None
            
        try:
            Maintenance = db_manager.get_model('maintenance')
            if not Maintenance:
                print("Error: 'maintenance' table not found in the database.")
                return None

            # Build a safe insert payload using only existing columns and omitting the PK
            payload = {}
            # Required/common fields
            if hasattr(Maintenance, 'platform_id'):
                payload['platform_id'] = platform_id
            if hasattr(Maintenance, 'maintenance_type'):
                payload['maintenance_type'] = maintenance_type
            if hasattr(Maintenance, 'description'):
                payload['description'] = description

            # Flexible fields
            # Map any additional kwargs that match columns
            for k, v in kwargs.items():
                if hasattr(Maintenance, k):
                    payload[k] = v

            # Support both 'date' and 'maintenance_date'
            if date is not None:
                if hasattr(Maintenance, 'maintenance_date'):
                    payload['maintenance_date'] = date
                elif hasattr(Maintenance, 'date'):
                    payload['date'] = date

            # Support both 'technician' and 'performed_by'
            if technician is not None:
                if hasattr(Maintenance, 'performed_by'):
                    payload['performed_by'] = technician
                elif hasattr(Maintenance, 'technician'):
                    payload['technician'] = technician

            # If schema uses a NOT NULL maintenance_id without autoincrement, generate the next ID
            try:
                if hasattr(Maintenance, 'maintenance_id') and 'maintenance_id' not in payload:
                    from sqlalchemy import text as sa_text
                    table_name = Maintenance.__table__.name
                    next_id_sql = sa_text(f"SELECT COALESCE(MAX(maintenance_id), 0) + 1 FROM {table_name}")
                    next_id = db_manager.session.execute(next_id_sql).scalar()
                    if next_id is None:
                        next_id = 1
                    payload['maintenance_id'] = int(next_id)
            except Exception:
                # Fallback: do not set if query fails; insert may still succeed if PK autogenerates
                pass

            # Compose column list and params
            cols = list(payload.keys())
            if not cols:
                print("Error: No valid columns to insert for maintenance record.")
                return None

            table_name = Maintenance.__table__.name
            placeholders = ', '.join([f":{c}" for c in cols])
            columns_sql = ', '.join(cols)

            from sqlalchemy import text as sa_text
            insert_sql = sa_text(f"INSERT INTO {table_name} ({columns_sql}) VALUES ({placeholders})")
            db_manager.session.execute(insert_sql, payload)
            db_manager.session.commit()

            # Try to fetch the created row (order by PK desc if available)
            pk_attr = None
            if hasattr(Maintenance, 'id'):
                pk_attr = getattr(Maintenance, 'id')
            elif hasattr(Maintenance, 'maintenance_id'):
                pk_attr = getattr(Maintenance, 'maintenance_id')

            query = db_manager.session.query(Maintenance)
            # Narrow down to this platform and description to avoid wrong pick
            if hasattr(Maintenance, 'platform_id'):
                query = query.filter(Maintenance.platform_id == platform_id)
            if hasattr(Maintenance, 'description') and description:
                query = query.filter(Maintenance.description == description)
            if pk_attr is not None:
                query = query.order_by(pk_attr.desc())
            created = query.first()
            return created
            
        except SQLAlchemyError as e:
            db_manager.session.rollback()
            print(f"Error adding maintenance log: {e}")
            return None
    
    @staticmethod
    def get_logs_for_platform(platform_id, limit=100, offset=0):
        """
        Retrieves maintenance logs for a specific platform.
        
        Args:
            platform_id (int): The ID of the platform
            limit (int): Maximum number of records to return
            offset (int): Number of records to skip (for pagination)
            
        Returns:
            list: List of maintenance records, or empty list if none found
        """
        if not db_manager.session:
            print("Error: No database connection available.")
            return []
            
        try:
            Maintenance = db_manager.get_model('maintenance')
            if not Maintenance:
                print("Error: 'maintenance' table not found in the database.")
                return []
                
            # Determine the correct date column for ordering
            order_col = None
            if hasattr(Maintenance, 'maintenance_date'):
                order_col = getattr(Maintenance, 'maintenance_date')
            elif hasattr(Maintenance, 'date'):
                order_col = getattr(Maintenance, 'date')

            query = db_manager.session.query(Maintenance).filter(Maintenance.platform_id == platform_id)
            if order_col is not None:
                query = query.order_by(order_col.desc())
            logs = query.offset(offset).limit(limit).all()
            
            return [log for log in logs]
            
        except SQLAlchemyError as e:
            print(f"Error retrieving maintenance logs: {e}")
            return []
    
    @staticmethod
    def delete_maintenance_log(log_id):
        """
        Deletes a specific maintenance log.
        
        Args:
            log_id (int): The ID of the maintenance log to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        if not db_manager.session:
            print("Error: No database connection available.")
            return False
            
        try:
            Maintenance = db_manager.get_model('maintenance')
            if not Maintenance:
                print("Error: 'maintenance' table not found in the database.")
                return False
                
            # Determine primary key column name
            pk_col = None
            if hasattr(Maintenance, 'id'):
                pk_col = getattr(Maintenance, 'id')
            elif hasattr(Maintenance, 'maintenance_id'):
                pk_col = getattr(Maintenance, 'maintenance_id')

            if pk_col is None:
                print("Error: Could not determine maintenance primary key column.")
                return False

            result = (db_manager.session.query(Maintenance)
                     .filter(pk_col == log_id)
                     .delete())
                     
            if result > 0:
                db_manager.session.commit()
                return True
            return False
            
        except SQLAlchemyError as e:
            db_manager.session.rollback()
            print(f"Error deleting maintenance log: {e}")
            return False

    @staticmethod
    def update_maintenance_log(log_id, **fields):
        """
        Updates a maintenance log by primary key. Only provided fields that match columns will be updated.
        """
        if not db_manager.session:
            print("Error: No database connection available.")
            return False

        try:
            Maintenance = db_manager.get_model('maintenance')
            if not Maintenance:
                print("Error: 'maintenance' table not found in the database.")
                return False

            # Determine primary key column name
            pk_col = None
            if hasattr(Maintenance, 'id'):
                pk_col = getattr(Maintenance, 'id')
            elif hasattr(Maintenance, 'maintenance_id'):
                pk_col = getattr(Maintenance, 'maintenance_id')
            if pk_col is None:
                print("Error: Could not determine maintenance primary key column.")
                return False

            # Build updates only for valid attributes
            updates = {}
            for k, v in fields.items():
                if hasattr(Maintenance, k):
                    updates[k] = v
                elif k == 'date':
                    if hasattr(Maintenance, 'maintenance_date'):
                        updates['maintenance_date'] = v
                elif k == 'technician':
                    if hasattr(Maintenance, 'performed_by'):
                        updates['performed_by'] = v

            if not updates:
                return False

            (db_manager.session.query(Maintenance)
                .filter(pk_col == log_id)
                .update(updates))
            db_manager.session.commit()
            return True
        except SQLAlchemyError as e:
            db_manager.session.rollback()
            print(f"Error updating maintenance log: {e}")
            return False

# Create a singleton instance for easy importing
maintenance_manager = MaintenanceManager()
