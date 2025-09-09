"""
Processing Auto Generator for automatic processing entry creation.

This service automatically creates processing entries for every Mission_ID
and ensures they stay synchronized with mission changes.
"""

from typing import Dict, List, Optional, Set
from datetime import datetime
from sqlalchemy import text
from app.database.manager import db_manager


class ProcessingAutoGenerator:
    """Service for automatically creating and managing processing entries."""

    def __init__(self):
        self._processed_mission_ids = set()  # Cache of Mission_IDs that have processing entries

    def generate_processing_entries(self, force_update: bool = False) -> Dict[str, str]:
        """
        Generate processing entries for all Mission_IDs that don't have them.

        Args:
            force_update: Whether to update existing processing entries

        Returns:
            Dictionary mapping Mission_IDs to processing entry status
        """
        if not db_manager.session:
            raise RuntimeError("Database session not available")

        try:
            # Get all unique Mission_IDs from missions table
            mission_ids = self._get_all_mission_ids()
            if not mission_ids:
                return {"status": "No Mission_IDs found"}

            # Get existing processing entries
            existing_processing = self._get_existing_processing_entries()

            results = {}
            created_count = 0
            updated_count = 0

            for mission_id in mission_ids:
                if mission_id in existing_processing:
                    if force_update:
                        # Update existing entry
                        self._update_processing_entry(mission_id, existing_processing[mission_id])
                        results[str(mission_id)] = "updated"
                        updated_count += 1
                    else:
                        results[str(mission_id)] = "exists"
                else:
                    # Create new entry
                    self._create_processing_entry(mission_id)
                    results[str(mission_id)] = "created"
                    created_count += 1

            # Commit all changes
            db_manager.session.commit()

            # Update cache
            self._processed_mission_ids.update(mission_ids)

            results["summary"] = f"Created: {created_count}, Updated: {updated_count}, Total: {len(mission_ids)}"
            return results

        except Exception as e:
            db_manager.session.rollback()
            raise RuntimeError(f"Failed to generate processing entries: {e}")

    def sync_processing_entries(self) -> Dict[str, str]:
        """
        Synchronize processing entries with current Mission_IDs.
        Removes processing entries for Mission_IDs that no longer exist.

        Returns:
            Dictionary with sync results
        """
        if not db_manager.session:
            raise RuntimeError("Database session not available")

        try:
            # Get current Mission_IDs
            current_mission_ids = set(self._get_all_mission_ids())

            # Get existing processing entries
            existing_processing_ids = set(self._get_existing_processing_mission_ids())

            # Find processing entries to remove
            to_remove = existing_processing_ids - current_mission_ids

            # Find missing processing entries
            to_create = current_mission_ids - existing_processing_ids

            results = {}
            removed_count = 0
            created_count = 0

            # Remove obsolete processing entries
            for mission_id in to_remove:
                self._remove_processing_entry(mission_id)
                results[f"removed_{mission_id}"] = "removed"
                removed_count += 1

            # Create missing processing entries
            for mission_id in to_create:
                self._create_processing_entry(mission_id)
                results[f"created_{mission_id}"] = "created"
                created_count += 1

            if removed_count > 0 or created_count > 0:
                db_manager.session.commit()

            results["summary"] = f"Removed: {removed_count}, Created: {created_count}"
            return results

        except Exception as e:
            db_manager.session.rollback()
            raise RuntimeError(f"Failed to sync processing entries: {e}")

    def _get_all_mission_ids(self) -> List[int]:
        """Get all unique Mission_IDs from the missions table."""
        try:
            Mission = db_manager.get_model('missions')
            if not Mission:
                return []

            # Get distinct Mission_IDs that are not null
            mission_ids = db_manager.session.query(Mission.mission_id).filter(
                Mission.mission_id.isnot(None)
            ).distinct().all()

            return [mid[0] for mid in mission_ids if mid[0] is not None]

        except Exception as e:
            print(f"Error getting Mission_IDs: {e}")
            return []

    def _get_existing_processing_entries(self) -> Dict[int, Dict]:
        """Get existing processing entries keyed by Mission_ID."""
        try:
            Processing = db_manager.get_model('processing')
            if not Processing:
                return {}

            processing_entries = db_manager.session.query(Processing).all()

            result = {}
            for entry in processing_entries:
                if hasattr(entry, 'Mission_ID') and entry.Mission_ID is not None:
                    result[entry.Mission_ID] = {
                        'id': entry.Process_ID,
                        'name': entry.Name,
                        'chassis_sn': entry.Chassis_SN,
                        'processed': entry.Processed,
                        'qa_qc': entry.__dict__.get('QA/QC'),  # Handle column name with slash
                        'notes': entry.Notes,
                        'creation_date': entry.__dict__.get('Creation Date'),  # Handle column name with space
                        'site_id': entry.Site_ID,
                        'folder_path': entry.Folder_Path
                    }

            return result

        except Exception as e:
            print(f"Error getting existing processing entries: {e}")
            return {}

    def _get_existing_processing_mission_ids(self) -> List[int]:
        """Get list of Mission_IDs that have processing entries."""
        try:
            Processing = db_manager.get_model('processing')
            if not Processing:
                return []

            mission_ids = db_manager.session.query(Processing.Mission_ID).filter(
                Processing.Mission_ID.isnot(None)
            ).distinct().all()

            return [mid[0] for mid in mission_ids if mid[0] is not None]

        except Exception as e:
            print(f"Error getting existing processing Mission_IDs: {e}")
            return []

    def _create_processing_entry(self, mission_id: int):
        """Create a new processing entry for the given Mission_ID."""
        try:
            Processing = db_manager.get_model('processing')
            if not Processing:
                raise RuntimeError("Processing model not found")

            # Get mission details for auto-population
            mission_details = self._get_mission_details(mission_id)
            if not mission_details:
                print(f"Warning: No mission details found for Mission_ID {mission_id}")
                return

            # Create processing entry
            processing_data = {
                'Name': f"Mission {mission_id} Processing",
                'Chassis_SN': mission_details.get('chassis'),
                'Processed': 'No',
                'QA/QC': 'Needs Review',
                'Notes': '',
                'Creation Date': datetime.now().date(),
                'Mission_ID': mission_id,
                'Site_ID': mission_details.get('site_id'),
                'Folder_Path': None
            }

            # Handle column names with special characters
            processing_entry = Processing(**processing_data)
            db_manager.session.add(processing_entry)

        except Exception as e:
            print(f"Error creating processing entry for Mission_ID {mission_id}: {e}")
            raise

    def _update_processing_entry(self, mission_id: int, existing_entry: Dict):
        """Update an existing processing entry with current mission data."""
        try:
            Processing = db_manager.get_model('processing')
            if not Processing:
                return

            # Get current mission details
            mission_details = self._get_mission_details(mission_id)
            if not mission_details:
                return

            # Update the processing entry
            processing_entry = db_manager.session.query(Processing).filter_by(
                Process_ID=existing_entry['id']
            ).first()

            if processing_entry:
                # Update fields that might have changed
                processing_entry.Chassis_SN = mission_details.get('chassis')
                processing_entry.Site_ID = mission_details.get('site_id')
                # Keep other fields as they might have been manually edited

        except Exception as e:
            print(f"Error updating processing entry for Mission_ID {mission_id}: {e}")

    def _remove_processing_entry(self, mission_id: int):
        """Remove processing entry for a Mission_ID that no longer exists."""
        try:
            Processing = db_manager.get_model('processing')
            if not Processing:
                return

            # Find and remove processing entries for this Mission_ID
            processing_entries = db_manager.session.query(Processing).filter_by(
                Mission_ID=mission_id
            ).all()

            for entry in processing_entries:
                db_manager.session.delete(entry)

        except Exception as e:
            print(f"Error removing processing entry for Mission_ID {mission_id}: {e}")

    def _get_mission_details(self, mission_id: int) -> Optional[Dict]:
        """Get mission details for a given Mission_ID."""
        try:
            Mission = db_manager.get_model('missions')
            Sites = db_manager.get_model('sites')

            if not Mission:
                return None

            # Get one mission with this Mission_ID
            mission = db_manager.session.query(Mission).filter_by(mission_id=mission_id).first()
            if not mission:
                return None

            # Get site information if available
            site_id = None
            if Sites and mission.site:
                # Try to find site by name or location
                site = db_manager.session.query(Sites).filter(
                    (Sites.name == mission.site) | (Sites.location == mission.site)
                ).first()
                if site:
                    site_id = site.site_ID

            return {
                'chassis': mission.chassis,
                'site': mission.site,
                'site_id': site_id,
                'customer': mission.customer,
                'date': mission.date
            }

        except Exception as e:
            print(f"Error getting mission details for Mission_ID {mission_id}: {e}")
            return None

    def clear_cache(self):
        """Clear internal caches."""
        self._processed_mission_ids.clear()


# Global instance
processing_auto_generator = ProcessingAutoGenerator()
