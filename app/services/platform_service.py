from typing import List, Dict, Optional, Any, Union, Tuple
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import text, inspect, Table, MetaData
import logging

# Set up logging
logger = logging.getLogger(__name__)

class PlatformService:
    """Service class for handling platform-related database operations."""
    
    def __init__(self, session: Session):
        """Initialize with a SQLAlchemy session."""
        self.session = session
        self._schema_columns = None
    
    def _get_platform_columns(self) -> List[str]:
        """
        Dynamically get the column names from the platforms table.
        
        Returns:
            List of column names
        """
        if self._schema_columns is None:
            try:
                # Use SQLAlchemy's inspector to get column information
                inspector = inspect(self.session.get_bind())
                columns = inspector.get_columns('platforms')
                self._schema_columns = [col['name'] for col in columns]
            except Exception as e:
                logger.error(f"Error getting platform columns: {e}")
                # Fallback to default columns if we can't inspect the schema
                self._schema_columns = [
                    'id', 'name', 'model', 'SN', 'manufacturer', 
                    'weight_kg', 'max_flight_time_min', 'status',
                    'registration_number', 'purchase_date', 'last_maintenance_date',
                    'next_maintenance_date', 'notes', 'is_active',
                    'created_at', 'updated_at'
                ]
        return self._schema_columns
    
    def _build_platform_query(self, include_inactive: bool = False) -> Tuple[str, dict]:
        """
        Build a dynamic SQL query for platforms based on the actual schema.
        
        Args:
            include_inactive: Whether to include inactive platforms
            
        Returns:
            Tuple of (query_string, params_dict)
        """
        # Define the expected columns and their mappings to the actual database
        column_mapping = {
            'id': 'id',
            'name': 'Name',
            'model': 'Model',
            'serial_number': 'SN',
            'manufacturer': 'Manufacturer',
            'status': 'status',
            'registration_number': 'FAA_Reg',
            'purchase_date': 'Acquisition_Date',
            'notes': 'Notes',
            'created_at': 'created_at',
            'updated_at': 'updated_at',
            'customer': 'Customer',
            'rc_model': 'RC_Model',
            'rc_serial_number': 'RC_SN',
            'remote_id': 'RemoteID'
        }
        
        # Get actual columns from the database
        inspector = inspect(self.session.get_bind())
        try:
            actual_columns = [col['name'] for col in inspector.get_columns('platforms')]
        except Exception as e:
            logger.error(f"Error getting platform columns: {e}")
            actual_columns = list(column_mapping.values())
        
        # Build the SELECT clause with only columns that exist in the database
        select_parts = []
        for app_col, db_col in column_mapping.items():
            if db_col in actual_columns:
                select_parts.append(f'"{db_col}" as {app_col}')
        
        # If we couldn't find any columns, use a basic query
        if not select_parts:
            select_parts = ['*']
        
        # Build the WHERE clause
        where_clause = ''
        params = {}
        if not include_inactive and 'status' in actual_columns:
            where_clause = 'WHERE LOWER(status) = \'active\''
        
        query = f"""
            SELECT {', '.join(select_parts)}
            FROM platforms
            {where_clause}
            ORDER BY Name
        """
        
        logger.debug(f"Generated platform query: {query}")
        return query, params
    
    def get_all_platforms(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieve all platforms from the database.
        
        Args:
            include_inactive: If True, include inactive platforms. Default is False.
            
        Returns:
            List of platform dictionaries
        """
        try:
            # Build the query dynamically based on the actual schema
            query, params = self._build_platform_query(include_inactive)
            result = self.session.execute(text(query), params)
            
            # Convert result to list of dictionaries with proper type conversion
            platforms = []
            for row in result.mappings():
                platform = {}
                for key, value in row.items():
                    # Convert date/datetime objects to ISO format for JSON serialization
                    if isinstance(value, (date, datetime)):
                        platform[key] = value.isoformat()
                    else:
                        platform[key] = value
                platforms.append(platform)
            
            return platforms
            
        except SQLAlchemyError as e:
            logger.error(f"Error fetching platforms: {e}", exc_info=True)
            raise
    
    def get_platform(self, platform_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a single platform by ID."""
        try:
            result = self.session.execute(
                text("""
                SELECT * FROM platforms
                WHERE id = :id
                """),
                {'id': platform_id}
            )
            
            row = result.mappings().first()
            return dict(row) if row else None
            
        except SQLAlchemyError as e:
            print(f"Error fetching platform {platform_id}: {e}")
            return None
    
    def create_platform(self, platform_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new platform in the database.
        
        Args:
            platform_data: Dictionary containing platform data
            
        Returns:
            Dictionary containing the created platform data
            
        Raises:
            ValueError: If required fields are missing
            IntegrityError: If a database integrity error occurs
            SQLAlchemyError: For other database errors
        """
        required_fields = ['name', 'model']
        missing_fields = [field for field in required_fields if not platform_data.get(field)]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
        try:
            # Set default values for required fields
            platform_data.setdefault('is_active', True)
            platform_data.setdefault('status', 'Active')
            platform_data['created_at'] = datetime.utcnow()
            platform_data['updated_at'] = datetime.utcnow()
            
            # Convert date strings to date objects if needed
            date_fields = ['purchase_date', 'last_maintenance_date', 'next_maintenance_date']
            for field in date_fields:
                if field in platform_data and isinstance(platform_data[field], str):
                    try:
                        platform_data[field] = datetime.fromisoformat(platform_data[field]).date()
                    except (ValueError, AttributeError):
                        platform_data[field] = None
            
            # Remove any None values to use database defaults
            platform_data = {k: v for k, v in platform_data.items() if v is not None}
            
            # Execute the insert
            columns = ', '.join(platform_data.keys())
            placeholders = ', '.join([f':{key}' for key in platform_data.keys()])
            
            result = self.session.execute(
                text(f"""
                INSERT INTO platforms ({columns})
                VALUES ({placeholders})
                RETURNING *
                """),
                platform_data
            )
            
            self.session.commit()
            
            row = result.mappings().first()
            if not row:
                raise SQLAlchemyError("Failed to retrieve created platform")
                
            return dict(row)
            
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"Integrity error creating platform: {e}", exc_info=True)
            raise
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error creating platform: {e}", exc_info=True)
            raise
    
    def update_platform(self, platform_id: int, platform_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing platform in the database.
        
        Args:
            platform_id: ID of the platform to update
            platform_data: Dictionary containing updated platform data
            
        Returns:
            Dictionary containing the updated platform data
            
        Raises:
            ValueError: If the platform doesn't exist or no data to update
            SQLAlchemyError: For database errors
        """
        if not platform_data:
            raise ValueError("No data provided for update")
            
        # Check if platform exists
        current = self.get_platform(platform_id)
        if not current:
            raise ValueError(f"Platform with ID {platform_id} not found")
            
        try:
            # Remove read-only fields
            for field in ['id', 'created_at']:
                platform_data.pop(field, None)
                
            # Update timestamps
            platform_data['updated_at'] = datetime.utcnow()
            
            # Convert date strings to date objects if needed
            date_fields = ['purchase_date', 'last_maintenance_date', 'next_maintenance_date']
            for field in date_fields:
                if field in platform_data and isinstance(platform_data[field], str):
                    try:
                        platform_data[field] = datetime.fromisoformat(platform_data[field]).date()
                    except (ValueError, AttributeError):
                        platform_data[field] = None
            
            # Remove None values to preserve existing data
            platform_data = {k: v for k, v in platform_data.items() if v is not None}
            
            if not platform_data:
                return current
                
            # Prepare and execute the update
            set_clause = ', '.join([f"{key} = :{key}" for key in platform_data.keys()])
            params = platform_data.copy()
            params['id'] = platform_id
            
            result = self.session.execute(
                text(f"""
                UPDATE platforms
                SET {set_clause}
                WHERE id = :id
                RETURNING *
                """),
                params
            )
            
            self.session.commit()
            
            row = result.mappings().first()
            if not row:
                raise SQLAlchemyError("Failed to retrieve updated platform")
                
            return dict(row)
            
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"Integrity error updating platform {platform_id}: {e}", exc_info=True)
            raise
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error updating platform {platform_id}: {e}", exc_info=True)
            raise
    
    def delete_platform(self, platform_id: int) -> bool:
        """
        Delete a platform from the database.
        
        Args:
            platform_id: ID of the platform to delete
            
        Returns:
            bool: True if the platform was deleted, False otherwise
            
        Raises:
            SQLAlchemyError: If a database error occurs
        """
        try:
            # First check if the platform exists
            platform = self.get_platform(platform_id)
            if not platform:
                return False
                
            # Soft delete by setting is_active to False
            result = self.session.execute(
                text("""
                UPDATE platforms
                SET is_active = FALSE, updated_at = :now
                WHERE id = :id
                RETURNING id
                """),
                {'id': platform_id, 'now': datetime.utcnow()}
            )
            
            self.session.commit()
            return result.rowcount > 0
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error deleting platform {platform_id}: {e}", exc_info=True)
            raise
