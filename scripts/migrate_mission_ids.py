#!/usr/bin/env python3
"""
Migration script to assign Mission_IDs to existing missions and create processing entries.

This script:
1. Assigns Mission_IDs to all existing missions based on grouping criteria
2. Creates processing entries for all Mission_IDs
3. Handles edge cases and provides progress reporting
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.manager import db_manager
from app.database.core import get_session_and_models
from app.logic.mission_grouping_service import mission_grouping_service
from app.logic.processing_auto_generator import processing_auto_generator


def migrate_mission_ids():
    """Main migration function."""
    print("🚀 Starting Mission_ID migration...")

    try:
        # Initialize database connection
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'flightlog.db')
        session, models = get_session_and_models(db_path)

        if not session or not models:
            print("❌ Failed to initialize database connection")
            return False

        # Set up the database manager
        db_manager.set_connection(session, models)

        print("📊 Analyzing existing missions...")

        # Get mission count
        Mission = models.get('missions')
        if not Mission:
            print("❌ Missions table not found")
            return False

        mission_count = session.query(Mission).count()
        missions_with_ids = session.query(Mission).filter(Mission.mission_id.isnot(None)).count()

        print(f"📈 Found {mission_count} total missions")
        print(f"📈 {missions_with_ids} missions already have Mission_IDs")
        print(f"📈 {mission_count - missions_with_ids} missions need Mission_IDs")

        # Step 1: Assign Mission_IDs
        print("\n🔄 Step 1: Assigning Mission_IDs...")
        assignments = mission_grouping_service.assign_mission_ids(reevaluate_existing=True)

        assigned_count = len(assignments)
        print(f"✅ Assigned Mission_IDs to {assigned_count} missions")

        # Show some examples of the assignments
        if assignments:
            print("\n📋 Sample Mission_ID assignments:")
            sample_assignments = list(assignments.items())[:5]
            for mission_db_id, mission_id in sample_assignments:
                print(f"  Mission DB ID {mission_db_id} → Mission_ID {mission_id}")

        # Step 2: Generate processing entries
        print("\n🔄 Step 2: Generating processing entries...")
        processing_results = processing_auto_generator.generate_processing_entries(force_update=True)

        summary = processing_results.get("summary", "No summary available")
        print(f"✅ Processing entries: {summary}")

        # Step 3: Verification
        print("\n🔍 Step 3: Verification...")

        # Check that all missions have Mission_IDs
        missions_without_ids = session.query(Mission).filter(Mission.mission_id.is_(None)).count()
        if missions_without_ids > 0:
            print(f"⚠️  Warning: {missions_without_ids} missions still don't have Mission_IDs")
        else:
            print("✅ All missions now have Mission_IDs")

        # Check processing entries
        Processing = models.get('processing')
        if Processing:
            processing_count = session.query(Processing).count()
            print(f"✅ Created {processing_count} processing entries")

            # Check for orphaned processing entries
            orphaned_query = session.query(Processing).filter(
                ~Processing.Mission_ID.in_(
                    session.query(Mission.mission_id).filter(Mission.mission_id.isnot(None))
                )
            )
            orphaned_count = orphaned_query.count()
            if orphaned_count > 0:
                print(f"⚠️  Warning: {orphaned_count} processing entries reference non-existent Mission_IDs")
            else:
                print("✅ No orphaned processing entries found")

        # Step 4: Show grouping statistics
        print("\n📊 Step 4: Grouping Statistics...")

        # Get Mission_ID distribution
        from sqlalchemy import func
        mission_id_counts = session.query(
            Mission.mission_id,
            func.count(Mission.id).label('count')
        ).filter(
            Mission.mission_id.isnot(None)
        ).group_by(Mission.mission_id).all()

        single_mission_groups = sum(1 for _, count in mission_id_counts if count == 1)
        multi_mission_groups = sum(1 for _, count in mission_id_counts if count > 1)

        print(f"🎯 Total unique Mission_IDs: {len(mission_id_counts)}")
        print(f"🎯 Single-mission groups: {single_mission_groups}")
        print(f"🎯 Multi-mission groups: {multi_mission_groups}")

        if multi_mission_groups > 0:
            print("\n📋 Multi-mission groups (missions that were grouped together):")
            multi_groups = [(mid, count) for mid, count in mission_id_counts if count > 1][:5]
            for mission_id, count in multi_groups:
                print(f"  Mission_ID {mission_id}: {count} missions")

        print("\n🎉 Migration completed successfully!")
        print("\n📝 Summary:")
        print(f"  • Missions processed: {mission_count}")
        print(f"  • Mission_IDs assigned: {assigned_count}")
        print(f"  • Processing entries: {summary}")
        print(f"  • Unique Mission_IDs: {len(mission_id_counts)}")

        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Clean up
        if db_manager.session:
            db_manager.session.close()


def show_migration_preview():
    """Show a preview of what the migration will do without making changes."""
    print("🔍 Migration Preview (no changes will be made)")

    try:
        # Initialize database connection
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'flightlog.db')
        session, models = get_session_and_models(db_path)

        if not session or not models:
            print("❌ Failed to initialize database connection")
            return

        Mission = models.get('missions')
        if not Mission:
            print("❌ Missions table not found")
            return

        # Analyze current state
        missions = session.query(Mission).all()
        missions_with_ids = [m for m in missions if m.mission_id is not None]
        missions_without_ids = [m for m in missions if m.mission_id is None]

        print(f"📊 Current state:")
        print(f"  • Total missions: {len(missions)}")
        print(f"  • With Mission_IDs: {len(missions_with_ids)}")
        print(f"  • Without Mission_IDs: {len(missions_without_ids)}")

        # Show grouping preview for missions without IDs
        if missions_without_ids:
            print(f"\n📋 Preview of Mission_ID assignment for {len(missions_without_ids)} missions:")

            # Group them
            groups = {}
            for mission in missions_without_ids:
                group_key_parts = []
                for field in ['date', 'chassis', 'customer', 'site', 'altitude_m', 'speed_m_s', 'spacing_m']:
                    value = getattr(mission, field, None)
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

            print(f"  • Will create {len(groups)} new Mission_ID groups")
            print(f"  • Average missions per group: {len(missions_without_ids) / len(groups):.1f}")

        # Show sample groups
        print("\n📋 Sample groups:")
        sample_groups = list(groups.items())[:3]
        for i, (group_key, group_missions) in enumerate(sample_groups, 1):
            print(f"    Group {i}: {len(group_missions)} missions")
            if group_missions:
                mission = group_missions[0]
                criteria = []
                if mission.date:
                    criteria.append(f"Date: {mission.date.strftime('%Y-%m-%d') if hasattr(mission.date, 'strftime') else mission.date}")
                if mission.chassis:
                    criteria.append(f"Chassis: {mission.chassis}")
                if mission.customer:
                    criteria.append(f"Customer: {mission.customer}")
                if mission.site:
                    criteria.append(f"Site: {mission.site}")
                print(f"      Criteria: {', '.join(criteria)}")

        session.close()

    except Exception as e:
        print(f"❌ Preview failed: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
        show_migration_preview()
    else:
        print("⚠️  This will modify your database. Consider running with --preview first.")
        response = input("Continue with migration? (y/N): ").strip().lower()
        if response == 'y':
            success = migrate_mission_ids()
            if success:
                print("\n✅ Migration completed successfully!")
            else:
                print("\n❌ Migration failed!")
                sys.exit(1)
        else:
            print("Migration cancelled.")
