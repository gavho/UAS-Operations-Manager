from typing import Dict, List, Any, Optional
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

class SchemaInspector:
    """Service for inspecting database schema and providing dynamic field information."""
    
    def __init__(self, session: Session):
        """Initialize with a SQLAlchemy session."""
        self.session = session
        self.engine = session.get_bind()
        self.inspector = inspect(self.engine)
    
    def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get column information for a specific table.
        
        Args:
            table_name: Name of the table to inspect
            
        Returns:
            List of column information dictionaries
        """
        columns = []
        try:
            # Get column info using SQLAlchemy inspector
            for column in self.inspector.get_columns(table_name):
                columns.append({
                    'name': column['name'],
                    'type': str(column['type']),
                    'nullable': column['nullable'],
                    'default': column.get('default'),
                    'primary_key': column.get('primary_key', False)
                })
            return columns
        except Exception as e:
            logger.error(f"Error getting columns for table {table_name}: {str(e)}")
            return []
    
    def get_foreign_keys(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get foreign key information for a specific table.
        
        Args:
            table_name: Name of the table to inspect
            
        Returns:
            List of foreign key information dictionaries
        """
        try:
            return self.inspector.get_foreign_keys(table_name)
        except Exception as e:
            logger.error(f"Error getting foreign keys for table {table_name}: {str(e)}")
            return []
    
    def get_table_names(self) -> List[str]:
        """
        Get all table names in the database.
        
        Returns:
            List of table names
        """
        try:
            return self.inspector.get_table_names()
        except Exception as e:
            logger.error(f"Error getting table names: {str(e)}")
            return []
    
    def get_platform_fields(self) -> Dict[str, Any]:
        """
        Get field information for the platforms table.
        
        Returns:
            Dictionary containing platform field information
        """
        if 'platforms' not in self.get_table_names():
            return {}
            
        columns = self.get_table_columns('platforms')
        
        # Map SQL types to field types
        type_mapping = {
            'VARCHAR': 'text',
            'TEXT': 'text',
            'INTEGER': 'number',
            'FLOAT': 'number',
            'BOOLEAN': 'boolean',
            'DATE': 'date',
            'DATETIME': 'datetime'
        }
        
        fields = {}
        for column in columns:
            col_type = str(column['type']).upper()
            field_type = 'text'  # default
            
            # Determine field type based on column type
            for sql_type, field_type_name in type_mapping.items():
                if sql_type in col_type:
                    field_type = field_type_name
                    break
            
            # Special handling for certain field names
            if column['name'].lower() in ['notes', 'description']:
                field_type = 'textarea'
            elif column['name'].lower().endswith('_date'):
                field_type = 'date'
            elif column['name'].lower().endswith('_at'):
                field_type = 'datetime'
            
            fields[column['name']] = {
                'type': field_type,
                'required': not column['nullable'],
                'primary_key': column['primary_key'],
                'default': column['default']
            }
            
            # Add display names (convert snake_case to Title Case)
            display_name = column['name'].replace('_', ' ').title()
            if column['name'].lower() == 'sn':
                display_name = 'Serial Number'
            fields[column['name']]['display_name'] = display_name
        
        return fields
