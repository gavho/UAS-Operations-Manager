"""
Mission Grouping Service for automatic Mission_ID assignment.

This service automatically assigns Mission_IDs to missions based on grouping criteria:
- date
- chassis
- customer
- site
- altitude_m
- speed_m_s
- spacing_m

Missions with identical values for all these fields get the same Mission_ID.
"""

from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime
from sqlalchemy import text
from app.database.manager import db_manager


class MissionGroupingService:
    """Service for automatically grouping missions and assigning Mission_IDs."""

    # Fields used for grouping missions
    GROUPING_FIELDS = ['date', 'chassis', 'customer', 'site', 'altitude_m', 'speed_m_s', 'spacing_m']

    def __init__(self):
        self._group_cache = {}  # Cache for performance
        self._mission_id_cache = {}  # Cache Mission_ID -> mission IDs

    def assign_mission_ids(self, reevaluate_existing: bool = True) -> Dict[str, int]:
        """
        Assign Mission_IDs to all missions based on grouping criteria.

        Args:
            reevaluate_existing: Whether to reevaluate missions that already have Mission_IDs

        Returns:
            Dictionary mapping mission IDs to their assigned Mission_IDs
        """
        if not db_manager.session:
            raise RuntimeError("Database session not available")

        try:
            # Get all missions
            Mission = db_manager.get_model('missions')
            if not Mission:
                raise RuntimeError("Missions model not found")

            missions = db_manager.session.query(Mission).all()

            # Group missions by criteria
            groups = self._group_missions_by_criteria(missions)

            # Assign Mission_IDs to groups
            assignments = {}
            next_mission_id = self._get_next_mission_id()

            for group_key, mission_list in groups.items():
                # Check if this group already has a Mission_ID
                existing_mission_id = self._find_existing_mission_id_for_group(mission_list)

                if existing_mission_id and not reevaluate_existing:
                    # Use existing Mission_ID
                    group_mission_id = existing_mission_id
                else:
                    # Assign new Mission_ID
                    if existing_mission_id:
                        group_mission_id = existing_mission_id
                    else:
                        group_mission_id = next_mission_id
                        next_mission_id += 1

                # Update all missions in this group
                for mission in mission_list:
                    assignments[mission.id] = group_mission_id
                    mission.mission_id = group_mission_id

            # Commit changes
            db_manager.session.commit()

            # Update caches
            self._update_caches(groups)

            return assignments

        except Exception as e:
            db_manager.session.rollback()
            raise RuntimeError(f"Failed to assign Mission_IDs: {e}")

    def get_missions_in_group(self, mission_id: int) -> List[Dict]:
        """
        Get all missions that belong to the same group as the given Mission_ID.

        Args:
            mission_id: The Mission_ID to find group members for

        Returns:
            List of mission dictionaries
        """
        if not db_manager.session:
            return []

        try:
            Mission = db_manager.get_model('missions')
            if not Mission:
                return []

            # Find one mission with this Mission_ID to get the grouping criteria
            reference_mission = db_manager.session.query(Mission).filter_by(mission_id=mission_id).first()
            if not reference_mission:
                return []

            # Find all missions with the same grouping criteria
            group_missions = db_manager.session.query(Mission).filter(
                Mission.date == reference_mission.date,
                Mission.chassis == reference_mission.chassis,
                Mission.customer == reference_mission.customer,
                Mission.site == reference_mission.site,
                Mission.altitude_m == reference_mission.altitude_m,
                Mission.speed_m_s == reference_mission.speed_m_s,
                Mission.spacing_m == reference_mission.spacing_m
            ).all()

            # Convert to dictionaries
            result = []
            for mission in group_missions:
                result.append({
                    'id': mission.id,
                    'mission_id': mission.mission_id,
                    'date': mission.date.strftime('%Y-%m-%d') if mission.date else None,
                    'platform': mission.platform,
                    'chassis': mission.chassis,
                    'customer': mission.customer,
                    'site': mission.site,
                    'altitude_m': mission.altitude_m,
                    'speed_m_s': mission.speed_m_s,
                    'spacing_m': mission.spacing_m,
                    'outcome': mission.outcome
                })

            return result

        except Exception as e:
            print(f"Error getting missions in group: {e}")
            return []

    def _group_missions_by_criteria(self, missions: List) -> Dict[str, List]:
        """Group missions by the specified criteria."""
        groups = {}

        for mission in missions:
            # Create group key from the specified fields
            group_key_parts = []
            for field in self.GROUPING_FIELDS:
                value = getattr(mission, field, None)
                # Handle date objects specially
                if field == 'date' and value:
                    if hasattr(value, 'strftime'):
                        value = value.strftime('%Y-%m-%d')
                    else:
                        value = str(value)
                group_key_parts.append(str(value) if value is not None else '')

            group_key = '|'.join(group_key_parts)

            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(mission)

        return groups

    def _find_existing_mission_id_for_group(self, mission_list: List) -> Optional[int]:
        """Find if any mission in the group already has a Mission_ID assigned."""
        for mission in mission_list:
            if hasattr(mission, 'mission_id') and mission.mission_id is not None:
                return mission.mission_id
        return None

    def _get_next_mission_id(self) -> int:
        """Get the next available Mission_ID."""
        if not db_manager.session:
            return 1

        try:
            Mission = db_manager.get_model('missions')
            if not Mission:
                return 1

            # Find the maximum existing Mission_ID
            max_mission_id = db_manager.session.query(Mission.mission_id).filter(
                Mission.mission_id.isnot(None)
            ).order_by(Mission.mission_id.desc()).first()

            if max_mission_id and max_mission_id[0] is not None:
                return max_mission_id[0] + 1
            else:
                return 1

        except Exception as e:
            print(f"Error getting next Mission_ID: {e}")
            return 1

    def _update_caches(self, groups: Dict[str, List]):
        """Update internal caches after Mission_ID assignment."""
        self._group_cache = groups
        self._mission_id_cache = {}

        # Build Mission_ID to mission IDs mapping
        for group_key, mission_list in groups.items():
            if mission_list and hasattr(mission_list[0], 'mission_id'):
                mission_id = mission_list[0].mission_id
                if mission_id not in self._mission_id_cache:
                    self._mission_id_cache[mission_id] = []
                self._mission_id_cache[mission_id].extend([m.id for m in mission_list])

    def clear_cache(self):
        """Clear internal caches."""
        self._group_cache.clear()
        self._mission_id_cache.clear()


# Global instance
mission_grouping_service = MissionGroupingService()
