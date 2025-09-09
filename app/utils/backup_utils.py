import os
import shutil
from datetime import datetime
from pathlib import Path

def create_backup(db_path: str, backup_dir: str = None, max_backups: int = 5) -> str:
    """
    Creates a backup of the database file and manages old backups.
    
    Args:
        db_path (str): Path to the database file to back up
        backup_dir (str, optional): Directory to store backups. Defaults to 'backups' in the same directory as db_path.
        max_backups (int, optional): Maximum number of backups to keep. Defaults to 5.
        
    Returns:
        str: Path to the created backup file, or None if backup failed.
    """
    try:
        # Set default backup directory if not provided
        if backup_dir is None:
            db_dir = os.path.dirname(os.path.abspath(db_path))
            backup_dir = os.path.join(db_dir, 'backups')
        
        # Create backup directory if it doesn't exist
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_name = os.path.basename(db_path)
        backup_name = f"{os.path.splitext(db_name)[0]}_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_name)
        
        # Create the backup
        shutil.copy2(db_path, backup_path)
        print(f"[BACKUP] Created backup: {backup_path}")
        
        # Clean up old backups
        _cleanup_old_backups(backup_dir, max_backups)
        
        return backup_path
    except Exception as e:
        print(f"[BACKUP ERROR] Failed to create backup: {e}")
        return None

def _cleanup_old_backups(backup_dir: str, max_backups: int):
    """
    Removes oldest backup files beyond the maximum allowed.
    
    Args:
        backup_dir (str): Directory containing backup files
        max_backups (int): Maximum number of backups to keep
    """
    try:
        # Get all backup files
        backups = []
        for f in os.listdir(backup_dir):
            if f.endswith('.db') and '_backup_' in f:
                file_path = os.path.join(backup_dir, f)
                if os.path.isfile(file_path):
                    backups.append((file_path, os.path.getmtime(file_path)))
        
        # Sort by modification time (oldest first)
        backups.sort(key=lambda x: x[1])
        
        # Delete oldest backups if we have more than max_backups
        if len(backups) > max_backups:
            for i in range(len(backups) - max_backups):
                try:
                    os.remove(backups[i][0])
                    print(f"[BACKUP] Removed old backup: {backups[i][0]}")
                except Exception as e:
                    print(f"[BACKUP WARNING] Could not remove old backup {backups[i][0]}: {e}")
    except Exception as e:
        print(f"[BACKUP ERROR] Error during backup cleanup: {e}")
