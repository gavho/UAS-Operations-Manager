import os
import json
import tempfile
import requests
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QMessageBox, QInputDialog, QTextEdit, QSplitter,
    QComboBox, QListWidget, QListWidgetItem, QFrame, QScrollArea,
    QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QCheckBox,
    QProgressBar, QTabWidget, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QTimer, QThread, pyqtSignal as Signal
from PyQt5.QtGui import QMovie
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QTimer, QThread, pyqtSignal as Signal
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QMovie
from sqlalchemy import text
from app.database.manager import db_manager

# Import folium for map functionality
import folium
from folium.plugins import Draw
import io
import base64
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl

class SitesManagementWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sites Management")
        self.current_site = None
        self.sites_data = []
        self.drawing_enabled = False
        self.drawn_geometry = None
        self.setup_ui()
        self.load_sites()

    def setup_ui(self):
        """Set up the user interface with map and controls."""
        layout = QHBoxLayout(self)

        # Left panel: Controls and site list
        self.setup_left_panel()
        layout.addWidget(self.left_panel, 1)

        # Right panel: Map
        self.setup_map_panel()
        layout.addWidget(self.map_panel, 3)

    def setup_left_panel(self):
        """Set up the left control panel."""
        self.left_panel = QWidget()
        layout = QVBoxLayout(self.left_panel)

        # Top controls
        controls_group = QGroupBox("Controls")
        controls_layout = QVBoxLayout(controls_group)

        # Filter controls
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter by Location:"))
        self.location_filter = QComboBox()
        self.location_filter.addItem("All Locations")
        self.location_filter.currentTextChanged.connect(self.filter_sites)
        filter_layout.addWidget(self.location_filter)
        controls_layout.addLayout(filter_layout)

        # Action buttons
        buttons_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Site")
        self.edit_btn = QPushButton("Edit Selected")
        self.delete_btn = QPushButton("Delete Site")
        self.refresh_btn = QPushButton("Refresh")

        self.add_btn.clicked.connect(self.add_site)
        self.edit_btn.clicked.connect(self.edit_site)
        self.delete_btn.clicked.connect(self.delete_site)
        self.refresh_btn.clicked.connect(self.load_sites)

        buttons_layout.addWidget(self.add_btn)
        buttons_layout.addWidget(self.edit_btn)
        buttons_layout.addWidget(self.delete_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.refresh_btn)

        controls_layout.addLayout(buttons_layout)
        layout.addWidget(controls_group)

        # Sites list
        sites_group = QGroupBox("Sites")
        sites_layout = QVBoxLayout(sites_group)

        self.sites_list = QListWidget()
        self.sites_list.itemSelectionChanged.connect(self.on_site_selected)
        self.sites_list.setMaximumHeight(300)
        sites_layout.addWidget(self.sites_list)

        layout.addWidget(sites_group)

        # Site details
        details_group = QGroupBox("Site Details")
        details_layout = QVBoxLayout(details_group)

        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.details_layout = QVBoxLayout(scroll_widget)

        self.site_name_label = QLabel("No site selected")
        self.site_name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.details_layout.addWidget(self.site_name_label)

        self.owner_label = QLabel("Owner: -")
        self.details_layout.addWidget(self.owner_label)

        self.location_label = QLabel("Location: -")
        self.details_layout.addWidget(self.location_label)

        self.notes_label = QLabel("Notes:")
        self.details_layout.addWidget(self.notes_label)

        self.notes_text = QTextEdit()
        self.notes_text.setMaximumHeight(80)
        self.notes_text.setReadOnly(True)
        self.details_layout.addWidget(self.notes_text)

        self.coords_label = QLabel("Coordinates: -")
        self.details_layout.addWidget(self.coords_label)

        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        details_layout.addWidget(scroll_area)

        layout.addWidget(details_group)

    def setup_map_panel(self):
        """Set up the map panel with folium for display."""
        self.map_panel = QGroupBox("Site Map")
        layout = QVBoxLayout(self.map_panel)

        # Create folium map widget
        self.map_view = QWebEngineView()
        layout.addWidget(self.map_view)

        # Map view toggle
        view_group = QGroupBox("Map View")
        view_layout = QHBoxLayout(view_group)

        self.main_map_view_group = QButtonGroup(self)
        self.main_street_view_radio = QRadioButton("Street View")
        self.main_satellite_view_radio = QRadioButton("Satellite View")
        self.main_street_view_radio.setChecked(True)

        self.main_map_view_group.addButton(self.main_street_view_radio)
        self.main_map_view_group.addButton(self.main_satellite_view_radio)

        self.main_street_view_radio.toggled.connect(lambda: self.toggle_main_map_view())
        self.main_satellite_view_radio.toggled.connect(lambda: self.toggle_main_map_view())

        view_layout.addWidget(self.main_street_view_radio)
        view_layout.addWidget(self.main_satellite_view_radio)
        view_layout.addStretch()

        layout.addWidget(view_group)

        # Map info label
        info_label = QLabel("ℹ️ Map uses folium with Leaflet.js. Sites are stored locally in the database.")
        info_label.setStyleSheet("color: #666; font-size: 10px; padding: 5px;")
        layout.addWidget(info_label)

        # Map controls
        map_controls = QHBoxLayout()

        self.refresh_map_btn = QPushButton("🔄 Refresh Map")
        self.refresh_map_btn.clicked.connect(self.update_map)

        map_controls.addWidget(self.refresh_map_btn)
        map_controls.addStretch()

        layout.addLayout(map_controls)

        # Instructions for map usage
        instructions = QLabel("💡 Select a site from the list to zoom to its location.\n"
                             "Use the Edit button to modify site boundaries and coordinates.")
        instructions.setStyleSheet("color: #666; font-size: 10px; padding: 5px;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)



    def update_map(self):
        """Update the map with current sites using folium."""
        try:
            # Calculate center location
            latitudes = [s['latitude'] for s in self.sites_data if s['latitude'] is not None]
            longitudes = [s['longitude'] for s in self.sites_data if s['longitude'] is not None]

            if latitudes and longitudes:
                center_lat = sum(latitudes) / len(latitudes)
                center_lon = sum(longitudes) / len(longitudes)
                zoom_level = 5  # Default zoom for multiple sites
            else:
                center_lat, center_lon = 39.8283, -98.5795  # Center of USA
                zoom_level = 4

            # Create folium map
            m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level)

            # Add markers for all sites
            for site in self.sites_data:
                if site['latitude'] is not None and site['longitude'] is not None:
                    popup_text = f"{site['name']} - {site['location']}"
                    folium.Marker(
                        [site['latitude'], site['longitude']],
                        popup=popup_text
                    ).add_to(m)

            # Load existing geometry for sites that have it
            for site in self.sites_data:
                if site.get('coordinates') and site['coordinates'].startswith('POLYGON'):
                    # Parse WKT polygon and add to map
                    coords_str = site['coordinates'].replace('POLYGON((', '').replace('))', '')
                    coord_pairs = coords_str.split(', ')

                    coordinates = []
                    for pair in coord_pairs:
                        if pair.strip():
                            lon, lat = map(float, pair.strip().split())
                            coordinates.append([lat, lon])  # folium uses [lat, lon]

                    if coordinates:
                        folium.Polygon(
                            locations=coordinates,
                            color='blue',
                            weight=2,
                            fill=True,
                            fill_color='blue',
                            fill_opacity=0.3,
                            popup=f"{site['name']} boundary"
                        ).add_to(m)

            # Save map to HTML and load in web view
            map_html = m.get_root().render()
            self.map_view.setHtml(map_html)

        except Exception as e:
            print(f"Error updating map: {e}")
            # Create a basic map on error
            try:
                m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)
                map_html = m.get_root().render()
                self.map_view.setHtml(map_html)
            except:
                pass

        

    def load_sites(self):
        """Load sites from the database."""
        if not db_manager.session:
            QMessageBox.warning(self, "Database Error", "No database connection available.")
            return

        try:
        # Query sites with geometry
            query = text("""
                SELECT site_ID, name, owner, CAST(location AS TEXT) as location, notes,
                       CASE WHEN geom IS NOT NULL THEN ST_AsText(geom) ELSE NULL END as coordinates,
                       CASE WHEN geom IS NOT NULL THEN ST_X(ST_Centroid(geom)) ELSE NULL END as longitude,
                       CASE WHEN geom IS NOT NULL THEN ST_Y(ST_Centroid(geom)) ELSE NULL END as latitude
                FROM sites
                ORDER BY name
            """)
            result = db_manager.session.execute(query).fetchall()

            self.sites_data = []
            locations = set()

            for row in result:
                site_data = {
                    'id': row.site_ID,
                    'name': row.name or '',
                    'owner': row.owner or '',
                    'location': row.location or '',
                    'notes': row.notes or '',
                    'coordinates': row.coordinates,
                    'longitude': row.longitude,
                    'latitude': row.latitude
                }

                # For polygons, calculate center point if not already available
                if row.coordinates and row.coordinates.startswith('POLYGON') and (row.longitude is None or row.latitude is None):
                    center_point = self.calculate_polygon_center(row.coordinates)
                    if center_point:
                        # Extract coordinates from POINT(lon lat)
                        coords_match = center_point.replace('POINT(', '').replace(')', '').split()
                        if len(coords_match) == 2:
                            site_data['longitude'] = float(coords_match[0])
                            site_data['latitude'] = float(coords_match[1])

                self.sites_data.append(site_data)

                if row.location:
                    locations.add(row.location)

            # Update location filter
            self.location_filter.clear()
            self.location_filter.addItem("All Locations")
            for location in sorted(locations):
                self.location_filter.addItem(location)

            # Update sites list
            self.update_sites_list()

            # Update map
            self.update_map()

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load sites: {str(e)}")

    def update_sites_list(self, filter_location=None):
        """Update the sites list with optional filtering."""
        self.sites_list.clear()

        for site in self.sites_data:
            if filter_location and filter_location != "All Locations":
                if site['location'] != filter_location:
                    continue

            item_text = f"{site['name']}"
            if site['location']:
                item_text += f" ({site['location']})"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, site['id'])
            self.sites_list.addItem(item)

    def filter_sites(self, location):
        """Filter sites by location."""
        self.update_sites_list(location)

    def on_site_selected(self):
        """Handle site selection with auto-zoom."""
        selected_items = self.sites_list.selectedItems()
        if selected_items:
            site_id = selected_items[0].data(Qt.UserRole)
            self.current_site = next((s for s in self.sites_data if s['id'] == site_id), None)
            if self.current_site:
                self.update_site_details()
                self.zoom_to_site(self.current_site)
        else:
            self.current_site = None
            self.clear_site_details()
            self.zoom_to_all_sites()

    def update_site_details(self):
        """Update the site details panel."""
        if not self.current_site:
            return

        self.site_name_label.setText(self.current_site['name'])
        self.owner_label.setText(f"Owner: {self.current_site['owner']}")
        self.location_label.setText(f"Location: {self.current_site['location']}")
        self.notes_text.setText(self.current_site['notes'])

        if self.current_site['coordinates']:
            self.coords_label.setText(f"Coordinates: {self.current_site['coordinates']}")
        else:
            self.coords_label.setText("Coordinates: Not set")

    def clear_site_details(self):
        """Clear the site details panel."""
        self.site_name_label.setText("No site selected")
        self.owner_label.setText("Owner: -")
        self.location_label.setText("Location: -")
        self.notes_text.clear()
        self.coords_label.setText("Coordinates: -")

    def add_site(self):
        """Add a new site using the comprehensive dialog."""
        dialog = SiteCreationDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            site_data = dialog.get_site_data()
            if site_data:
                try:
                    # Prepare the insert query
                    if site_data.get('geometry'):
                        query = text("""
                            INSERT INTO sites (name, owner, location, notes, geom, created_at, updated_at)
                            VALUES (:name, :owner, :location, :notes, ST_GeomFromText(:geom, 4326), datetime('now'), datetime('now'))
                        """)
                    else:
                        query = text("""
                            INSERT INTO sites (name, owner, location, notes, created_at, updated_at)
                            VALUES (:name, :owner, :location, :notes, datetime('now'), datetime('now'))
                        """)

                    db_manager.session.execute(query, site_data)
                    db_manager.session.commit()

                    self.load_sites()
                    QMessageBox.information(self, "Success", "Site added successfully.")
                except Exception as e:
                    QMessageBox.critical(self, "Database Error", f"Failed to add site: {str(e)}")
                    db_manager.session.rollback()

    def edit_site(self):
        """Edit the selected site with full functionality."""
        if not self.current_site:
            QMessageBox.warning(self, "No Selection", "Please select a site to edit.")
            return

        dialog = SiteEditDialog(self.current_site, self)
        if dialog.exec_() == QDialog.Accepted:
            updated_data = dialog.get_site_data()
            if updated_data:
                try:
                    # Debug: Print what we're trying to update
                    print(f"Updating site {self.current_site['id']} with data: {updated_data}")

                    # Prepare the update query - always include geom field to handle NULL properly
                    query = text("""
                        UPDATE sites
                        SET name = :name, owner = :owner, location = :location,
                            notes = :notes,
                            geom = CASE WHEN :geom IS NOT NULL THEN ST_GeomFromText(:geom, 4326) ELSE NULL END,
                            updated_at = datetime('now')
                        WHERE site_ID = :site_id
                    """)

                    updated_data['site_id'] = self.current_site['id']

                    # Handle geometry properly - check if geometry was explicitly cleared
                    if 'geometry' in updated_data:
                        if updated_data['geometry'] is None or updated_data['geometry'] == '' or str(updated_data['geometry']).strip() == '':
                            # Geometry was explicitly cleared - set to NULL
                            updated_data['geom'] = None
                        else:
                            # Validate geometry format
                            geom_str = str(updated_data['geometry']).strip()
                            if geom_str and geom_str != 'None' and geom_str != '':
                                updated_data['geom'] = geom_str
                            else:
                                updated_data['geom'] = None
                    elif self.current_site.get('coordinates'):
                        # Keep existing geometry if no new geometry provided
                        updated_data['geom'] = self.current_site['coordinates']
                    else:
                        updated_data['geom'] = None

                    print(f"Final update data: {updated_data}")
                    db_manager.session.execute(query, updated_data)
                    db_manager.session.commit()

                    self.load_sites()
                    QMessageBox.information(self, "Success", "Site updated successfully.")
                except Exception as e:
                    print(f"Database error details: {str(e)}")
                    QMessageBox.critical(self, "Database Error", f"Failed to update site: {str(e)}")
                    db_manager.session.rollback()

    def delete_site(self):
        """Delete the selected site."""
        if not self.current_site:
            QMessageBox.warning(self, "No Selection", "Please select a site to delete.")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete site '{self.current_site['name']}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                query = text("DELETE FROM sites WHERE site_ID = :site_id")
                db_manager.session.execute(query, {'site_id': self.current_site['id']})
                db_manager.session.commit()

                self.load_sites()
                self.clear_site_details()
                QMessageBox.information(self, "Success", "Site deleted successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Failed to delete site: {str(e)}")
                db_manager.session.rollback()

    def toggle_main_map_view(self):
        """Toggle between street and satellite map views for the main map."""
        if hasattr(self, 'map_view'):
            # Force map recreation with new tile layer
            self.update_map()

    def zoom_to_site(self, site):
        """Zoom the main map to a specific site using folium."""
        if not hasattr(self, 'map_view'):
            return

        try:
            # Check if site has valid geometry or coordinates
            has_geometry = site.get('coordinates') and site['coordinates'] and site['coordinates'].startswith('POLYGON')
            has_coordinates = site['latitude'] is not None and site['longitude'] is not None

            if has_geometry or has_coordinates:
                # Use coordinates if available, otherwise calculate from geometry
                if has_coordinates:
                    center_lat = site['latitude']
                    center_lon = site['longitude']
                    zoom_level = 15  # Close zoom for individual sites
                elif has_geometry:
                    # Calculate center from polygon geometry
                    center_point = self.calculate_polygon_center(site['coordinates'])
                    if center_point:
                        # Extract coordinates from POINT(lon lat)
                        coords_match = center_point.replace('POINT(', '').replace(')', '').split()
                        if len(coords_match) == 2:
                            center_lon = float(coords_match[0])
                            center_lat = float(coords_match[1])
                            zoom_level = 15
                        else:
                            # Fallback to all sites view
                            self.zoom_to_all_sites()
                            return
                    else:
                        # Fallback to all sites view
                        self.zoom_to_all_sites()
                        return
                else:
                    # Fallback to all sites view
                    self.zoom_to_all_sites()
                    return
            else:
                # No geometry or coordinates - zoom to world view
                center_lat, center_lon = 20, 0  # Roughly center of world
                zoom_level = 2

            # Create folium map with selected site highlighted
            m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level)

            # Add markers for all sites with highlighting
            for s in self.sites_data:
                if s['latitude'] is not None and s['longitude'] is not None:
                    # Highlight the selected site
                    is_selected = s['id'] == site['id']
                    popup_text = f"{'⭐ ' if is_selected else ''}{s['name']} - {s['location']}"

                    # Use different colors for selected vs other sites
                    if is_selected:
                        folium.Marker(
                            [s['latitude'], s['longitude']],
                            popup=popup_text,
                            icon=folium.Icon(color='red', icon='star')
                        ).add_to(m)
                    else:
                        folium.Marker(
                            [s['latitude'], s['longitude']],
                            popup=popup_text
                        ).add_to(m)

            # Load existing geometry for sites that have it
            for s in self.sites_data:
                if s.get('coordinates') and s['coordinates'].startswith('POLYGON'):
                    # Parse WKT polygon and add to map
                    coords_str = s['coordinates'].replace('POLYGON((', '').replace('))', '')
                    coord_pairs = coords_str.split(', ')

                    coordinates = []
                    for pair in coord_pairs:
                        if pair.strip():
                            lon, lat = map(float, pair.strip().split())
                            coordinates.append([lat, lon])  # folium uses [lat, lon]

                    if coordinates:
                        # Highlight selected site's polygon
                        if s['id'] == site['id']:
                            folium.Polygon(
                                locations=coordinates,
                                color='red',
                                weight=3,
                                fill=True,
                                fill_color='red',
                                fill_opacity=0.4,
                                popup=f"{s['name']} boundary (SELECTED)"
                            ).add_to(m)
                        else:
                            folium.Polygon(
                                locations=coordinates,
                                color='blue',
                                weight=2,
                                fill=True,
                                fill_color='blue',
                                fill_opacity=0.3,
                                popup=f"{s['name']} boundary"
                            ).add_to(m)

            # Save map to HTML and load in web view
            map_html = m.get_root().render()
            self.map_view.setHtml(map_html)

        except Exception as e:
            print(f"Error zooming to site: {e}")
            # Fallback to world view on error
            try:
                m = folium.Map(location=[20, 0], zoom_start=2)
                map_html = m.get_root().render()
                self.map_view.setHtml(map_html)
            except:
                pass

    def zoom_to_all_sites(self):
        """Zoom the main map to show all sites globally using folium."""
        if not hasattr(self, 'map_view'):
            return

        try:
            # Get all sites with coordinates
            sites_with_coords = [s for s in self.sites_data if s['latitude'] is not None and s['longitude'] is not None]

            if sites_with_coords:
                # Calculate bounds to fit all sites
                latitudes = [s['latitude'] for s in sites_with_coords]
                longitudes = [s['longitude'] for s in sites_with_coords]

                min_lat, max_lat = min(latitudes), max(latitudes)
                min_lon, max_lon = min(longitudes), max(longitudes)

                # Add some padding
                lat_padding = (max_lat - min_lat) * 0.1
                lon_padding = (max_lon - min_lon) * 0.1

                center_lat = (min_lat + max_lat) / 2
                center_lon = (min_lon + max_lon) / 2

                # Calculate appropriate zoom level based on spread
                lat_range = max_lat - min_lat + 2 * lat_padding
                lon_range = max_lon - min_lon + 2 * lon_padding

                # Rough zoom calculation (higher zoom = closer)
                if lat_range > 50 or lon_range > 50:
                    zoom_level = 2
                elif lat_range > 10 or lon_range > 10:
                    zoom_level = 4
                elif lat_range > 1 or lon_range > 1:
                    zoom_level = 6
                else:
                    zoom_level = 8
            else:
                # No sites with coordinates - show world view
                center_lat, center_lon = 20, 0  # Roughly center of world
                zoom_level = 2

            # Create folium map with all sites
            m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level)

            # Add markers for all sites
            for s in self.sites_data:
                if s['latitude'] is not None and s['longitude'] is not None:
                    popup_text = f"{s['name']} - {s['location']}"
                    folium.Marker(
                        [s['latitude'], s['longitude']],
                        popup=popup_text
                    ).add_to(m)

            # Load existing geometry for sites that have it
            for s in self.sites_data:
                if s.get('coordinates') and s['coordinates'].startswith('POLYGON'):
                    # Parse WKT polygon and add to map
                    coords_str = s['coordinates'].replace('POLYGON((', '').replace('))', '')
                    coord_pairs = coords_str.split(', ')

                    coordinates = []
                    for pair in coord_pairs:
                        if pair.strip():
                            lon, lat = map(float, pair.strip().split())
                            coordinates.append([lat, lon])  # folium uses [lat, lon]

                    if coordinates:
                        folium.Polygon(
                            locations=coordinates,
                            color='blue',
                            weight=2,
                            fill=True,
                            fill_color='blue',
                            fill_opacity=0.3,
                            popup=f"{s['name']} boundary"
                        ).add_to(m)

            # Save map to HTML and load in web view
            map_html = m.get_root().render()
            self.map_view.setHtml(map_html)

        except Exception as e:
            print(f"Error zooming to all sites: {e}")
            # Fallback to world view on error
            try:
                m = folium.Map(location=[20, 0], zoom_start=2)
                map_html = m.get_root().render()
                self.map_view.setHtml(map_html)
            except:
                pass



    def on_polygon_created(self, geometry_type, geometry_data):
        """Handle polygon creation from Leaflet map."""
        if geometry_type == 'polygon' and geometry_data.get('wkt'):
            self.selected_geometry = geometry_data['wkt']
            print(f"Polygon created: {self.selected_geometry}")

            # Update button states
            self.start_drawing_btn.setEnabled(True)
            self.finish_drawing_btn.setEnabled(False)
            self.cancel_drawing_btn.setEnabled(False)

            QMessageBox.information(self, "Polygon Created",
                                  "✅ Polygon successfully created!\n\n"
                                  "The boundary will be saved when you click OK.")

    def on_polygon_edited(self, geometry_type, geometry_data):
        """Handle polygon editing from Leaflet map."""
        if geometry_type == 'polygon' and geometry_data.get('wkt'):
            self.selected_geometry = geometry_data['wkt']
            print(f"Polygon edited: {self.selected_geometry}")

    def on_polygon_deleted(self, geometry_id):
        """Handle polygon deletion from Leaflet map."""
        self.selected_geometry = None
        print("Polygon deleted")

    def enable_polygon_drawing(self):
        """Enable polygon drawing mode on the map."""
        try:
            # Enable drawing mode by running JavaScript
            self.polygon_map_view.page().runJavaScript("""
                // Enable polygon drawing
                if (typeof map !== 'undefined' && map.pm) {
                    map.pm.enableDraw('Polygon', {
                        allowIntersection: false,
                        drawError: {
                            color: '#e1e100',
                            message: '<strong>Error:</strong> Shape edges cannot cross!'
                        },
                        shapeOptions: {
                            color: '#007bff',
                            weight: 2,
                            fillColor: '#007bff',
                            fillOpacity: 0.3
                        }
                    });
                }
            """)
            QMessageBox.information(self, "Drawing Mode",
                                  "🎯 Polygon drawing enabled!\n\n"
                                  "Click on the map to place polygon points.\n"
                                  "Double-click or click the first point to finish.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not enable drawing mode: {str(e)}")

    def save_geometry_changes(self):
        """Save the current geometry changes to the database."""
        try:
            # Get current geometry from the map
            self.polygon_map_view.page().runJavaScript(
                "window.drawnGeometry",
                self.on_save_geometry
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save geometry: {str(e)}")

    def on_save_geometry(self, geometry):
        """Handle geometry saving callback."""
        try:
            if geometry and geometry != 'null' and geometry != '':
                # Update the database with the new geometry
                if db_manager.session:
                    query = text("""
                        UPDATE sites
                        SET geom = ST_GeomFromText(:geom, 4326), updated_at = datetime('now')
                        WHERE site_ID = :site_id
                    """)
                    db_manager.session.execute(query, {
                        'site_id': self.site_data['id'],
                        'geom': geometry
                    })
                    db_manager.session.commit()

                    # Update local data
                    self.site_data['coordinates'] = geometry
                    self.selected_geometry = geometry

                    QMessageBox.information(self, "Success",
                                          "✅ Geometry saved successfully to database!")
                else:
                    QMessageBox.critical(self, "Database Error", "No database connection available.")
            else:
                QMessageBox.information(self, "No Changes",
                                      "No geometry changes to save.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save geometry: {str(e)}")
            if db_manager.session:
                db_manager.session.rollback()

    def delete_selected_geometry(self):
        """Delete the currently selected geometry."""
        try:
            # Get current geometry to confirm deletion
            self.polygon_map_view.page().runJavaScript(
                "window.drawnGeometry",
                self.on_delete_geometry
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not delete geometry: {str(e)}")

    def on_delete_geometry(self, geometry):
        """Handle geometry deletion callback."""
        try:
            reply = QMessageBox.question(
                self, "Delete Geometry",
                "Are you sure you want to delete the selected geometry?\n\n"
                "This will remove the polygon from both the map and database.",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # Clear geometry from database
                if db_manager.session:
                    query = text("""
                        UPDATE sites
                        SET geom = NULL, updated_at = datetime('now')
                        WHERE site_ID = :site_id
                    """)
                    db_manager.session.execute(query, {'site_id': self.site_data['id']})
                    db_manager.session.commit()

                    # Clear local data
                    self.site_data['coordinates'] = None
                    self.selected_geometry = None

                    # Clear map geometry
                    self.polygon_map_view.page().runJavaScript("""
                        window.drawnGeometry = null;
                        // Clear all drawn items
                        if (typeof map !== 'undefined') {
                            map.eachLayer(function(layer) {
                                if (layer instanceof L.Polygon || layer instanceof L.Marker) {
                                    map.removeLayer(layer);
                                }
                            });
                        }
                    """)

                    QMessageBox.information(self, "Success",
                                          "✅ Geometry deleted successfully!")
                else:
                    QMessageBox.critical(self, "Database Error", "No database connection available.")
        except Exception as e:
            QMessageBox.critical(self, "Delete Error", f"Failed to delete geometry: {str(e)}")
            if db_manager.session:
                db_manager.session.rollback()

    def create_polygon_map(self):
        """Create a folium map with Draw plugin for polygon creation."""
        try:
            # Create folium map centered on default location
            center_lat, center_lon = 39.8283, -98.5795  # Center of USA
            zoom_level = 4

            # Create map with Draw plugin
            m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level)

            # Add Draw plugin with polygon drawing capabilities
            draw = Draw(
                draw_options={
                    'polyline': False,
                    'rectangle': False,
                    'circle': False,
                    'marker': True,
                    'circlemarker': False,
                    'polygon': {
                        'allowIntersection': False,
                        'drawError': {
                            'color': '#e1e100',
                            'message': '<strong>Error:</strong> Shape edges cannot cross!'
                        },
                        'shapeOptions': {
                            'color': '#007bff',
                            'weight': 2,
                            'fillColor': '#007bff',
                            'fillOpacity': 0.3
                        }
                    }
                },
                edit_options={
                    'featureGroup': None,
                    'edit': True,
                    'remove': True
                }
            )
            m.add_child(draw)

            # Add JavaScript to capture drawn geometries
            js_code = """
            <script>
            // Initialize window.drawnGeometry
            window.drawnGeometry = null;
            window.drawnItems = new L.FeatureGroup();
            map.addLayer(window.drawnItems);
            console.log('Map initialized for site creation');

            map.on('draw:created', function (e) {
                var type = e.layerType,
                    layer = e.layer;

                window.drawnItems.addLayer(layer);

                // Convert to WKT
                var wkt = '';
                if (type === 'polygon') {
                    var coords = layer.getLatLngs()[0];
                    wkt = 'POLYGON((';
                    for (var i = 0; i < coords.length; i++) {
                        wkt += coords[i].lng + ' ' + coords[i].lat;
                        if (i < coords.length - 1) wkt += ', ';
                    }
                    wkt += '))';
                } else if (type === 'marker') {
                    var coord = layer.getLatLng();
                    wkt = 'POINT(' + coord.lng + ' ' + coord.lat + ')';
                }

                // Store in window variable for Python access
                window.drawnGeometry = wkt;
                console.log('Geometry created:', wkt);
            });

            map.on('draw:edited', function (e) {
                var layers = e.layers;
                layers.eachLayer(function (layer) {
                    // Update geometry
                    if (layer instanceof L.Polygon) {
                        var coords = layer.getLatLngs()[0];
                        var wkt = 'POLYGON((';
                        for (var i = 0; i < coords.length; i++) {
                            wkt += coords[i].lng + ' ' + coords[i].lat;
                            if (i < coords.length - 1) wkt += ', ';
                        }
                        wkt += '))';
                        window.drawnGeometry = wkt;
                        console.log('Geometry edited:', wkt);
                    }
                });
            });

            map.on('draw:deleted', function (e) {
                window.drawnGeometry = null;
                console.log('Geometry deleted');
            });
            </script>
            """

            # Add JavaScript to the map
            m.get_root().html.add_child(folium.Element(js_code))

            # Save map to HTML and load in web view
            map_html = m.get_root().render()
            self.polygon_map_view.setHtml(map_html)

        except Exception as e:
            print(f"Error creating polygon map: {e}")
            # Create basic map on error
            try:
                m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)
                map_html = m.get_root().render()
                self.polygon_map_view.setHtml(map_html)
            except:
                pass

    def save_geometry_to_database(self):
        """Save the current geometry to the database from the edit dialog."""
        try:
            if hasattr(self, 'polygon_map_view') and self.polygon_map_view:
                self.polygon_map_view.page().runJavaScript(
                    """
                    (function(){
                        function ensureMapVar(){
                            if (typeof map !== 'undefined' && map && map.setView) return map;
                            var _mk = Object.keys(window).find(function(k){ return k.indexOf('map_')===0 && window[k] && window[k].setView; });
                            if (_mk) { window.map = window[_mk]; return window.map; }
                            return null;
                        }
                        function layerToWKT(layer){
                            if (!layer) return null;
                            if (layer instanceof L.Polygon){
                                var coords = layer.getLatLngs()[0] || [];
                                if (!coords.length) return null;
                                return 'POLYGON((' + coords.map(function(c){ return c.lng + ' ' + c.lat; }).join(', ') + '))';
                            }
                            if (layer instanceof L.Marker){
                                var c = layer.getLatLng();
                                return 'POINT(' + c.lng + ' ' + c.lat + ')';
                            }
                            return null;
                        }
                        ensureMapVar();
                        if (window.drawnGeometry && window.drawnGeometry !== 'null' && window.drawnGeometry !== ''){
                            return window.drawnGeometry;
                        }
                        if (window.drawnItems){
                            var layers = window.drawnItems.getLayers();
                            for (var i=0;i<layers.length;i++){
                                var w = layerToWKT(layers[i]);
                                if (w) return w;
                            }
                        }
                        if (typeof map !== 'undefined'){
                            var found = null;
                            map.eachLayer(function(layer){ if (!found) found = layerToWKT(layer); });
                            if (found) return found;
                        }
                        return null;
                    })();
                    """,
                    self.on_save_geometry_callback
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save geometry: {str(e)}")

    def force_read_and_save_geometry(self):
        """Force-read geometry from map layers (robust) and save to DB."""
        try:
            if hasattr(self, 'polygon_map_view') and self.polygon_map_view:
                self.polygon_map_view.page().runJavaScript(
                    """
                    (function(){
                        function ensureMapVar(){
                            if (typeof map !== 'undefined' && map && map.setView) return map;
                            var _mk = Object.keys(window).find(function(k){ return k.indexOf('map_')===0 && window[k] && window[k].setView; });
                            if (_mk) { window.map = window[_mk]; return window.map; }
                            return null;
                        }
                        function layerToWKT(layer){
                            if (!layer) return null;
                            if (layer instanceof L.Polygon){
                                var coords = layer.getLatLngs()[0] || [];
                                if (!coords.length) return null;
                                return 'POLYGON((' + coords.map(function(c){ return c.lng + ' ' + c.lat; }).join(', ') + '))';
                            }
                            if (layer instanceof L.Marker){
                                var c = layer.getLatLng();
                                return 'POINT(' + c.lng + ' ' + c.lat + ')';
                            }
                            return null;
                        }
                        ensureMapVar();
                        if (window.drawnGeometry && window.drawnGeometry !== 'null' && window.drawnGeometry !== ''){
                            return window.drawnGeometry;
                        }
                        if (window.drawnItems){
                            var layers = window.drawnItems.getLayers();
                            for (var i=0;i<layers.length;i++){
                                var w = layerToWKT(layers[i]);
                                if (w) return w;
                            }
                        }
                        if (typeof map !== 'undefined'){
                            var found = null;
                            map.eachLayer(function(layer){ if (!found) found = layerToWKT(layer); });
                            if (found) return found;
                        }
                        return null;
                    })();
                    """,
                    self.on_save_geometry_callback
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not read geometry: {str(e)}")

    def on_save_geometry_callback(self, geometry):
        """Handle geometry saving callback for edit dialog."""
        try:
            if geometry and geometry != 'null' and geometry != '':
                if db_manager.session:
                    query = text(
                        """
                        UPDATE sites
                        SET geom = ST_GeomFromText(:geom, 4326), updated_at = datetime('now')
                        WHERE site_ID = :site_id
                        """
                    )
                    db_manager.session.execute(query, {
                        'site_id': self.site_data['id'],
                        'geom': geometry
                    })
                    db_manager.session.commit()
                    self.site_data['coordinates'] = geometry
                    self.selected_geometry = geometry
                    QMessageBox.information(self, "Success", "✅ Geometry saved successfully to database!")
                else:
                    QMessageBox.critical(self, "Database Error", "No database connection available.")
            else:
                QMessageBox.information(self, "No Changes", "No geometry changes to save.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save geometry: {str(e)}")
            if db_manager.session:
                db_manager.session.rollback()

    def save_geometry_to_database(self):
        """Save the current geometry to the database from the edit dialog."""
        try:
            if hasattr(self, 'polygon_map_view') and self.polygon_map_view:
                self.polygon_map_view.page().runJavaScript(
                    "window.drawnGeometry",
                    self.on_save_geometry_callback
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save geometry: {str(e)}")

    def on_save_geometry_callback(self, geometry):
        """Handle geometry saving callback for edit dialog."""
        try:
            if geometry and geometry != 'null' and geometry != '':
                if db_manager.session:
                    query = text(
                        """
                        UPDATE sites
                        SET geom = ST_GeomFromText(:geom, 4326), updated_at = datetime('now')
                        WHERE site_ID = :site_id
                        """
                    )
                    db_manager.session.execute(query, {
                        'site_id': self.site_data['id'],
                        'geom': geometry
                    })
                    db_manager.session.commit()
                    self.site_data['coordinates'] = geometry
                    self.selected_geometry = geometry
                    QMessageBox.information(self, "Success", "✅ Geometry saved successfully to database!")
                else:
                    QMessageBox.critical(self, "Database Error", "No database connection available.")
            else:
                QMessageBox.information(self, "No Changes", "No geometry changes to save.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save geometry: {str(e)}")
            if db_manager.session:
                db_manager.session.rollback()

    def save_geometry_to_database(self):
        """Save the current geometry from the edit dialog map to the database."""
        try:
            if hasattr(self, 'polygon_map_view') and self.polygon_map_view:
                self.polygon_map_view.page().runJavaScript(
                    "window.drawnGeometry",
                    self.on_save_geometry_callback
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save geometry: {str(e)}")

    def on_save_geometry_callback(self, geometry):
        """Handle geometry saving callback for edit dialog."""
        try:
            if geometry and geometry != 'null' and geometry != '':
                if db_manager.session:
                    query = text(
                        """
                        UPDATE sites
                        SET geom = ST_GeomFromText(:geom, 4326), updated_at = datetime('now')
                        WHERE site_ID = :site_id
                        """
                    )
                    db_manager.session.execute(query, {
                        'site_id': self.site_data['id'],
                        'geom': geometry
                    })
                    db_manager.session.commit()
                    self.site_data['coordinates'] = geometry
                    self.selected_geometry = geometry
                    QMessageBox.information(self, "Success", "✅ Geometry saved successfully to database!")
                else:
                    QMessageBox.critical(self, "Database Error", "No database connection available.")
            else:
                QMessageBox.information(self, "No Changes", "No geometry changes to save.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save geometry: {str(e)}")
            if db_manager.session:
                db_manager.session.rollback()

    def save_geometry_to_database(self):
        """Save the current geometry to the database (edit dialog)."""
        try:
            if hasattr(self, 'polygon_map_view') and self.polygon_map_view:
                self.polygon_map_view.page().runJavaScript(
                    "window.drawnGeometry",
                    self.on_save_geometry_callback
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save geometry: {str(e)}")

    def on_save_geometry_callback(self, geometry):
        """Handle geometry saving callback for edit dialog."""
        try:
            if geometry and geometry != 'null' and geometry != '':
                if db_manager.session:
                    query = text(
                        """
                        UPDATE sites
                        SET geom = ST_GeomFromText(:geom, 4326), updated_at = datetime('now')
                        WHERE site_ID = :site_id
                        """
                    )
                    db_manager.session.execute(query, {
                        'site_id': self.site_data['id'],
                        'geom': geometry
                    })
                    db_manager.session.commit()
                    self.site_data['coordinates'] = geometry
                    self.selected_geometry = geometry
                    QMessageBox.information(self, "Success", "✅ Geometry saved successfully to database!")
                else:
                    QMessageBox.critical(self, "Database Error", "No database connection available.")
            else:
                QMessageBox.information(self, "No Changes", "No geometry changes to save.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save geometry: {str(e)}")
            if db_manager.session:
                db_manager.session.rollback()

    def load_existing_polygon(self):
        """Load existing polygon geometry if available."""
        # For creation dialog, we don't load existing polygons
        pass

    def update_map_location(self, lat, lon, display_name):
        """Update the map to show a specific location."""
        try:
            # Create folium map centered on the found location
            m = folium.Map(location=[lat, lon], zoom_start=15)

            # Add marker for the found location
            folium.Marker(
                [lat, lon],
                popup=display_name,
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(m)

            # Add Draw plugin for polygon drawing
            draw = Draw(
                draw_options={
                    'polyline': False,
                    'rectangle': False,
                    'circle': False,
                    'marker': True,
                    'circlemarker': False,
                    'polygon': {
                        'allowIntersection': False,
                        'drawError': {
                            'color': '#e1e100',
                            'message': '<strong>Error:</strong> Shape edges cannot cross!'
                        },
                        'shapeOptions': {
                            'color': '#007bff',
                            'weight': 2,
                            'fillColor': '#007bff',
                            'fillOpacity': 0.3
                        }
                    }
                },
                edit_options={
                    'featureGroup': None,
                    'edit': True,
                    'remove': True
                }
            )
            m.add_child(draw)

            # Add JavaScript to capture drawn geometries
            js_code = """
            <script>
            // Initialize window.drawnGeometry
            window.drawnGeometry = null;
            var drawnItems = new L.FeatureGroup();
            map.addLayer(drawnItems);
            console.log('Map updated with location');

            map.on('draw:created', function (e) {
                var type = e.layerType,
                    layer = e.layer;

                drawnItems.addLayer(layer);

                // Convert to WKT
                var wkt = '';
                if (type === 'polygon') {
                    var coords = layer.getLatLngs()[0];
                    wkt = 'POLYGON((';
                    for (var i = 0; i < coords.length; i++) {
                        wkt += coords[i].lng + ' ' + coords[i].lat;
                        if (i < coords.length - 1) wkt += ', ';
                    }
                    wkt += '))';
                } else if (type === 'marker') {
                    var coord = layer.getLatLng();
                    wkt = 'POINT(' + coord.lng + ' ' + coord.lat + ')';
                }

                // Store in window variable for Python access
                window.drawnGeometry = wkt;
                console.log('Geometry created:', wkt);
            });

            map.on('draw:edited', function (e) {
                var layers = e.layers;
                layers.eachLayer(function (layer) {
                    // Update geometry
                    if (layer instanceof L.Polygon) {
                        var coords = layer.getLatLngs()[0];
                        var wkt = 'POLYGON((';
                        for (var i = 0; i < coords.length; i++) {
                            wkt += coords[i].lng + ' ' + coords[i].lat;
                            if (i < coords.length - 1) wkt += ', ';
                        }
                        wkt += '))';
                        window.drawnGeometry = wkt;
                        console.log('Geometry edited:', wkt);
                    }
                });
            });

            map.on('draw:deleted', function (e) {
                window.drawnGeometry = null;
                console.log('Geometry deleted');
            });
            </script>
            """

            # Add JavaScript to the map
            m.get_root().html.add_child(folium.Element(js_code))

            # Save map to HTML and load in web view
            map_html = m.get_root().render()
            self.location_map_view.setHtml(map_html)

        except Exception as e:
            print(f"Error updating map location: {e}")

    def create_location_map(self):
        """Create a basic location map."""
        try:
            # Base map
            m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)

            # Add Draw plugin to allow drawing polygons/markers
            draw = Draw(
                draw_options={
                    'polyline': False,
                    'rectangle': False,
                    'circle': False,
                    'marker': True,
                    'circlemarker': False,
                    'polygon': {
                        'allowIntersection': False,
                        'drawError': {
                            'color': '#e1e100',
                            'message': '<strong>Error:</strong> Shape edges cannot cross!'
                        },
                        'shapeOptions': {
                            'color': '#007bff',
                            'weight': 2,
                            'fillColor': '#007bff',
                            'fillOpacity': 0.3
                        }
                    }
                },
                edit_options={
                    'featureGroup': None,
                    'edit': True,
                    'remove': True
                }
            )
            m.add_child(draw)

            # Inject JS: maintain window.drawnGeometry and a global drawnItems group
            js_code = """
            <script>
            // Ensure we have a reference to the Leaflet map instance
            if (typeof map === 'undefined' || !(map && map.setView)) {
                var _mk = Object.keys(window).find(function(k){ return k.indexOf('map_') === 0 && window[k] && window[k].setView; });
                if (_mk) { window.map = window[_mk]; }
            }

            // Initialize geometry storage and editable layer group
            window.drawnGeometry = null;
            window.drawnItems = new L.FeatureGroup();
            map.addLayer(window.drawnItems);

            // Keep a global reference to the draw control if present
            setTimeout(function(){
                try {
                    if (map && map._controls) {
                        // Find an instance of L.Control.Draw that folium added
                        for (var i = 0; i < map._controls.length; i++) {
                            var ctl = map._controls[i];
                            if (ctl && ctl.options && ctl.options.edit && ctl.options.draw) {
                                window.drawControl = ctl;
                                break;
                            }
                        }
                    }
                } catch(e) { console.warn('Unable to capture draw control:', e); }
            }, 0);

            // Handle creation of shapes
            map.on('draw:created', function (e) {
                var type = e.layerType, layer = e.layer;
                window.drawnItems.addLayer(layer);
                var wkt = '';
                if (type === 'polygon') {
                    var coords = layer.getLatLngs()[0];
                    wkt = 'POLYGON((' + coords.map(function(c){ return c.lng + ' ' + c.lat; }).join(', ') + '))';
                } else if (type === 'marker') {
                    var c = layer.getLatLng();
                    wkt = 'POINT(' + c.lng + ' ' + c.lat + ')';
                }
                window.drawnGeometry = wkt;
                console.log('Geometry created:', wkt);
            });

            // Handle edits
            map.on('draw:edited', function (e) {
                e.layers.eachLayer(function (layer) {
                    if (layer instanceof L.Polygon) {
                        var coords = layer.getLatLngs()[0];
                        var wkt = 'POLYGON((' + coords.map(function(c){ return c.lng + ' ' + c.lat; }).join(', ') + '))';
                        window.drawnGeometry = wkt;
                        console.log('Geometry edited:', wkt);
                    }
                });
            });

            // Handle deletes
            map.on('draw:deleted', function () {
                window.drawnGeometry = null;
                console.log('Geometry deleted');
            });
            </script>
            """
            m.get_root().html.add_child(folium.Element(js_code))

            map_html = m.get_root().render()
            self.location_map_view.setHtml(map_html)
        except Exception as e:
            print(f"Error creating location map: {e}")



    def save_geometry_to_database(self):
        """Save the current geometry to the database."""
        try:
            # Get current geometry from the map with robust fallback
            if hasattr(self, 'location_map_view') and self.location_map_view:
                self.location_map_view.page().runJavaScript(
                    """
                    (function(){
                        function ensureMapVar(){
                            if (typeof map !== 'undefined' && map && map.setView) return map;
                            var _mk = Object.keys(window).find(function(k){ return k.indexOf('map_')===0 && window[k] && window[k].setView; });
                            if (_mk) { window.map = window[_mk]; return window.map; }
                            return null;
                        }
                        function layerToWKT(layer){
                            if (!layer) return null;
                            if (layer instanceof L.Polygon){
                                var coords = layer.getLatLngs()[0] || [];
                                if (!coords.length) return null;
                                return 'POLYGON((' + coords.map(function(c){ return c.lng + ' ' + c.lat; }).join(', ') + '))';
                            }
                            if (layer instanceof L.Marker){
                                var c = layer.getLatLng();
                                return 'POINT(' + c.lng + ' ' + c.lat + ')';
                            }
                            return null;
                        }
                        ensureMapVar();
                        if (window.drawnGeometry && window.drawnGeometry !== 'null' && window.drawnGeometry !== ''){
                            return window.drawnGeometry;
                        }
                        if (window.drawnItems){
                            var layers = window.drawnItems.getLayers();
                            for (var i=0;i<layers.length;i++){
                                var w = layerToWKT(layers[i]);
                                if (w) return w;
                            }
                        }
                        if (typeof map !== 'undefined'){
                            var found = null;
                            map.eachLayer(function(layer){ if (!found) found = layerToWKT(layer); });
                            if (found) return found;
                        }
                        return null;
                    })();
                    """,
                    self.on_save_geometry_callback
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save geometry: {str(e)}")

    def force_read_and_save_geometry(self):
        """Force-read geometry from map layers (robust) and save to memory for creation dialog."""
        try:
            if hasattr(self, 'location_map_view') and self.location_map_view:
                self.location_map_view.page().runJavaScript(
                    """
                    (function(){
                        function ensureMapVar(){
                            if (typeof map !== 'undefined' && map && map.setView) return map;
                            var _mk = Object.keys(window).find(function(k){ return k.indexOf('map_')===0 && window[k] && window[k].setView; });
                            if (_mk) { window.map = window[_mk]; return window.map; }
                            return null;
                        }
                        function layerToWKT(layer){
                            if (!layer) return null;
                            if (layer instanceof L.Polygon){
                                var coords = layer.getLatLngs()[0] || [];
                                if (!coords.length) return null;
                                return 'POLYGON((' + coords.map(function(c){ return c.lng + ' ' + c.lat; }).join(', ') + '))';
                            }
                            if (layer instanceof L.Marker){
                                var c = layer.getLatLng();
                                return 'POINT(' + c.lng + ' ' + c.lat + ')';
                            }
                            return null;
                        }
                        ensureMapVar();
                        if (window.drawnGeometry && window.drawnGeometry !== 'null' && window.drawnGeometry !== ''){
                            return window.drawnGeometry;
                        }
                        if (window.drawnItems){
                            var layers = window.drawnItems.getLayers();
                            for (var i=0;i<layers.length;i++){
                                var w = layerToWKT(layers[i]);
                                if (w) return w;
                            }
                        }
                        if (typeof map !== 'undefined'){
                            var found = null;
                            map.eachLayer(function(layer){ if (!found) found = layerToWKT(layer); });
                            if (found) return found;
                        }
                        return null;
                    })();
                    """,
                    self.on_save_geometry_callback
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not read geometry: {str(e)}")

    def on_save_geometry_callback(self, geometry):
        """Handle geometry capture for creation dialog (store locally)."""
        try:
            if geometry and geometry != 'null' and geometry != '':
                self.selected_geometry = geometry
                QMessageBox.information(self, "Success", "✅ Geometry captured! It will be saved when you click OK.")
            else:
                QMessageBox.warning(self, "No Geometry", "No geometry was found on the map.")
        except Exception as e:
            QMessageBox.critical(self, "Capture Error", f"Failed to capture geometry: {str(e)}")

    def on_save_geometry_callback(self, geometry):
        """Handle geometry saving callback."""
        try:
            if geometry and geometry != 'null' and geometry != '':
                # Update the database with the new geometry
                if db_manager.session:
                    query = text("""
                        UPDATE sites
                        SET geom = ST_GeomFromText(:geom, 4326), updated_at = datetime('now')
                        WHERE site_ID = :site_id
                    """)
                    db_manager.session.execute(query, {
                        'site_id': self.site_data['id'],
                        'geom': geometry
                    })
                    db_manager.session.commit()

                    # Update local data
                    self.site_data['coordinates'] = geometry
                    self.selected_geometry = geometry

                    QMessageBox.information(self, "Success",
                                          "✅ Geometry saved successfully to database!")
                else:
                    QMessageBox.critical(self, "Database Error", "No database connection available.")
            else:
                QMessageBox.information(self, "No Changes",
                                      "No geometry changes to save.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save geometry: {str(e)}")
            if db_manager.session:
                db_manager.session.rollback()

    def calculate_polygon_center(self, wkt_polygon):
        """Calculate the center point of a polygon from WKT format."""
        try:
            # Parse WKT polygon format: POLYGON((x1 y1, x2 y2, ..., xn yn))
            coords_str = wkt_polygon.replace('POLYGON((', '').replace('))', '')
            coord_pairs = coords_str.split(', ')

            latitudes = []
            longitudes = []

            for pair in coord_pairs:
                if pair.strip():
                    lon, lat = map(float, pair.strip().split())
                    latitudes.append(lat)
                    longitudes.append(lon)

            if latitudes and longitudes:
                # Calculate centroid (average of all points)
                center_lat = sum(latitudes) / len(latitudes)
                center_lon = sum(longitudes) / len(longitudes)
                return f'POINT({center_lon} {center_lat})'

        except Exception as e:
            print(f"Error calculating polygon center: {e}")

        return None

    def force_read_and_save_geometry(self):
        """Force-read geometry from map layers (robust) and save to memory."""
        try:
            if hasattr(self, 'location_map_view') and self.location_map_view:
                self.location_map_view.page().runJavaScript(
                    """
                    (function(){
                        function ensureMapVar(){
                            if (typeof map !== 'undefined' && map && map.setView) return map;
                            var _mk = Object.keys(window).find(function(k){ return k.indexOf('map_')===0 && window[k] && window[k].setView; });
                            if (_mk) { window.map = window[_mk]; return window.map; }
                            return null;
                        }
                        function layerToWKT(layer){
                            if (!layer) return null;
                            if (layer instanceof L.Polygon){
                                var coords = layer.getLatLngs()[0] || [];
                                if (!coords.length) return null;
                                return 'POLYGON((' + coords.map(function(c){ return c.lng + ' ' + c.lat; }).join(', ') + '))';
                            }
                            if (layer instanceof L.Marker){
                                var c = layer.getLatLng();
                                return 'POINT(' + c.lng + ' ' + c.lat + ')';
                            }
                            return null;
                        }
                        ensureMapVar();
                        if (window.drawnGeometry && window.drawnGeometry !== 'null' && window.drawnGeometry !== ''){
                            return window.drawnGeometry;
                        }
                        if (window.drawnItems){
                            var layers = window.drawnItems.getLayers();
                            for (var i=0;i<layers.length;i++){
                                var w = layerToWKT(layers[i]);
                                if (w) return w;
                            }
                        }
                        if (typeof map !== 'undefined'){
                            var found = null;
                            map.eachLayer(function(layer){ if (!found) found = layerToWKT(layer); });
                            if (found) return found;
                        }
                        return null;
                    })();
                    """,
                    self.on_save_geometry_callback
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not read geometry: {str(e)}")


class SiteCreationDialog(QDialog):
    """Dialog for creating new sites with optional map integration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Site")
        self.setModal(True)
        self.resize(800, 600)

        # Store geometry data
        self.selected_geometry = None
        self.map_file = None

        self.setup_ui()

    def setup_javascript_bridge(self):
        """Set up JavaScript bridge for auto-save functionality."""
        if hasattr(self, 'polygon_map_view') and self.polygon_map_view:
            # Create a channel for JavaScript to Python communication
            self.polygon_map_view.page().setWebChannel(self.create_web_channel())

    def create_web_channel(self):
        """Create web channel for JavaScript communication."""
        from PyQt5.QtWebChannel import QWebChannel
        from PyQt5.QtCore import QObject, pyqtSlot

        class Bridge(QObject):
            def __init__(self, parent):
                super().__init__()
                self.parent = parent

            @pyqtSlot(str)
            def autoSaveGeometry(self, wkt):
                """Handle auto-save from JavaScript."""
                self.parent.handle_auto_save(wkt)

        channel = QWebChannel()
        bridge = Bridge(self)
        channel.registerObject('qt', bridge)
        return channel

    def handle_auto_save(self, wkt):
        """Handle automatic saving of geometry changes."""
        try:
            # For creation dialog, we don't have a site_id yet, so just store geometry
            if not hasattr(self, 'site_data') or not self.site_data.get('id'):
                print(f"Storing geometry for new site creation: {wkt}")
                self.selected_geometry = wkt if wkt and wkt != 'null' and wkt != '' else None
                return

            print(f"Auto-saving geometry for site {self.site_data['id']}: {wkt}")

            if db_manager.session:
                if wkt and wkt != 'null' and wkt != '':
                    # Save geometry
                    query = text("""
                        UPDATE sites
                        SET geom = ST_GeomFromText(:geom, 4326), updated_at = datetime('now')
                        WHERE site_ID = :site_id
                    """)
                    db_manager.session.execute(query, {
                        'site_id': self.site_data['id'],
                        'geom': wkt
                    })
                else:
                    # Clear geometry
                    query = text("""
                        UPDATE sites
                        SET geom = NULL, updated_at = datetime('now')
                        WHERE site_ID = :site_id
                    """)
                    db_manager.session.execute(query, {'site_id': self.site_data['id']})

                db_manager.session.commit()

                # Update local data
                if wkt and wkt != 'null' and wkt != '':
                    self.site_data['coordinates'] = wkt
                    self.selected_geometry = wkt

                    # Update coordinate display if it's a point
                    if wkt.startswith('POINT'):
                        coords_match = wkt.replace('POINT(', '').replace(')', '').split()
                        if len(coords_match) == 2:
                            try:
                                lon = float(coords_match[0])
                                lat = float(coords_match[1])
                                if hasattr(self, 'current_lat_label'):
                                    self.current_lat_label.setText(f"{lat:.6f}")
                                    self.current_lon_label.setText(f"{lon:.6f}")
                            except ValueError:
                                pass
                else:
                    self.site_data['coordinates'] = None
                    self.selected_geometry = None
                    if hasattr(self, 'current_lat_label'):
                        self.current_lat_label.setText("Not set")
                        self.current_lon_label.setText("Not set")

                print("✅ Auto-save completed successfully")

            else:
                print("❌ Database connection not available for auto-save")

        except Exception as e:
            print(f"❌ Auto-save error: {str(e)}")
            if db_manager.session:
                db_manager.session.rollback()

    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Create tab widget for different sections
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Basic Information Tab
        self.setup_basic_info_tab()

        # Location/Map Tab
        self.setup_location_tab()

        # Save button and dialog buttons
        buttons_layout = QHBoxLayout()

        self.save_geometry_btn = QPushButton("💾 Save Geometry")
        self.save_geometry_btn.clicked.connect(self.save_geometry_to_database)
        self.save_geometry_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; font-weight: bold; padding: 8px 16px; }")
        buttons_layout.addWidget(self.save_geometry_btn)

        # Force-read geometry (reads from Leaflet layers even if events didn't set drawnGeometry)
        self.read_geometry_btn = QPushButton("🧭 Read Geometry")
        self.read_geometry_btn.setToolTip("Force-read geometry from the map layers and save")
        self.read_geometry_btn.clicked.connect(self.force_read_and_save_geometry)
        buttons_layout.addWidget(self.read_geometry_btn)

        buttons_layout.addStretch()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        buttons_layout.addWidget(self.button_box)

        layout.addLayout(buttons_layout)

    def save_geometry_to_database(self):
        """Save the current geometry to the database."""
        try:
            # Get current geometry from the map
            if hasattr(self, 'location_map_view') and self.location_map_view:
                # Robust getter: tries drawnGeometry, then window.drawnItems, then all map layers
                self.location_map_view.page().runJavaScript(
                    """
                    (function(){
                        function ensureMapVar(){
                            if (typeof map !== 'undefined' && map && map.setView) return map;
                            var _mk = Object.keys(window).find(function(k){ return k.indexOf('map_')===0 && window[k] && window[k].setView; });
                            if (_mk) { window.map = window[_mk]; return window.map; }
                            return null;
                        }
                        function layerToWKT(layer){
                            if (!layer) return null;
                            if (layer instanceof L.Polygon){
                                var coords = layer.getLatLngs()[0] || [];
                                if (!coords.length) return null;
                                return 'POLYGON((' + coords.map(function(c){ return c.lng + ' ' + c.lat; }).join(', ') + '))';
                            }
                            if (layer instanceof L.Marker){
                                var c = layer.getLatLng();
                                return 'POINT(' + c.lng + ' ' + c.lat + ')';
                            }
                            return null;
                        }
                        ensureMapVar();
                        if (window.drawnGeometry && window.drawnGeometry !== 'null' && window.drawnGeometry !== ''){
                            return window.drawnGeometry;
                        }
                        if (window.drawnItems){
                            var layers = window.drawnItems.getLayers();
                            for (var i=0;i<layers.length;i++){
                                var w = layerToWKT(layers[i]);
                                if (w) return w;
                            }
                        }
                        if (typeof map !== 'undefined'){
                            var found = null;
                            map.eachLayer(function(layer){ if (!found) found = layerToWKT(layer); });
                            if (found) return found;
                        }
                        return null;
                    })();
                    """,
                    self.on_save_geometry_callback
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save geometry: {str(e)}")

    def on_save_geometry_callback(self, geometry):
        """Handle geometry saving callback."""
        try:
            if geometry and geometry != 'null' and geometry != '':
                # Update the database with the new geometry
                if db_manager.session:
                    query = text("""
                        UPDATE sites
                        SET geom = ST_GeomFromText(:geom, 4326), updated_at = datetime('now')
                        WHERE site_ID = :site_id
                    """)
                    db_manager.session.execute(query, {
                        'site_id': self.site_data['id'],
                        'geom': geometry
                    })
                    db_manager.session.commit()

                    # Update local data
                    self.site_data['coordinates'] = geometry
                    self.selected_geometry = geometry

                    QMessageBox.information(self, "Success",
                                          "✅ Geometry saved successfully to database!")
                else:
                    QMessageBox.critical(self, "Database Error", "No database connection available.")
            else:
                QMessageBox.information(self, "No Changes",
                                      "No geometry changes to save.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save geometry: {str(e)}")
            if db_manager.session:
                db_manager.session.rollback()

        # Set up JavaScript bridge for auto-save
        self.setup_javascript_bridge()

    def setup_javascript_bridge(self):
        """Set up JavaScript bridge for auto-save functionality."""
        if hasattr(self, 'polygon_map_view') and self.polygon_map_view:
            # Create a channel for JavaScript to Python communication
            self.polygon_map_view.page().setWebChannel(self.create_web_channel())

    def create_web_channel(self):
        """Create web channel for JavaScript communication."""
        from PyQt5.QtWebChannel import QWebChannel
        from PyQt5.QtCore import QObject, pyqtSlot

        class Bridge(QObject):
            def __init__(self, parent):
                super().__init__()
                self.parent = parent

            @pyqtSlot(str)
            def autoSaveGeometry(self, wkt):
                """Handle auto-save from JavaScript."""
                self.parent.handle_auto_save(wkt)

        channel = QWebChannel()
        bridge = Bridge(self)
        channel.registerObject('qt', bridge)
        return channel

    def handle_auto_save(self, wkt):
        """Handle automatic saving of geometry changes."""
        try:
            print(f"Auto-saving geometry for site {self.site_data['id']}: {wkt}")

            if db_manager.session:
                if wkt and wkt != 'null' and wkt != '':
                    # Save geometry
                    query = text("""
                        UPDATE sites
                        SET geom = ST_GeomFromText(:geom, 4326), updated_at = datetime('now')
                        WHERE site_ID = :site_id
                    """)
                    db_manager.session.execute(query, {
                        'site_id': self.site_data['id'],
                        'geom': wkt
                    })
                else:
                    # Clear geometry
                    query = text("""
                        UPDATE sites
                        SET geom = NULL, updated_at = datetime('now')
                        WHERE site_ID = :site_id
                    """)
                    db_manager.session.execute(query, {'site_id': self.site_data['id']})

                db_manager.session.commit()

                # Update local data
                if wkt and wkt != 'null' and wkt != '':
                    self.site_data['coordinates'] = wkt
                    self.selected_geometry = wkt

                    # Update coordinate display if it's a point
                    if wkt.startswith('POINT'):
                        coords_match = wkt.replace('POINT(', '').replace(')', '').split()
                        if len(coords_match) == 2:
                            try:
                                lon = float(coords_match[0])
                                lat = float(coords_match[1])
                                self.current_lat_label.setText(f"{lat:.6f}")
                                self.current_lon_label.setText(f"{lon:.6f}")
                            except ValueError:
                                pass
                else:
                    self.site_data['coordinates'] = None
                    self.selected_geometry = None
                    self.current_lat_label.setText("Not set")
                    self.current_lon_label.setText("Not set")

                print("✅ Auto-save completed successfully")

            else:
                print("❌ Database connection not available for auto-save")

        except Exception as e:
            print(f"❌ Auto-save error: {str(e)}")
            if db_manager.session:
                db_manager.session.rollback()

    def setup_map_widget(self):
        """Set up the map widget with the 3 required buttons."""
        self.map_widget = QWidget()
        layout = QVBoxLayout(self.map_widget)

        # Map controls - the 3 buttons as requested
        controls_layout = QHBoxLayout()

        self.draw_polygon_btn = QPushButton("🎯 Draw Polygon")
        self.draw_polygon_btn.clicked.connect(self.enable_polygon_drawing)
        self.draw_polygon_btn.setStyleSheet("QPushButton { background-color: #007bff; color: white; font-weight: bold; }")
        controls_layout.addWidget(self.draw_polygon_btn)

        self.save_btn = QPushButton("💾 Save Changes")
        self.save_btn.clicked.connect(self.save_geometry_changes)
        self.save_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; font-weight: bold; }")
        controls_layout.addWidget(self.save_btn)

        self.delete_btn = QPushButton("🗑️ Delete Selected")
        self.delete_btn.clicked.connect(self.delete_selected_geometry)
        self.delete_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; font-weight: bold; }")
        controls_layout.addWidget(self.delete_btn)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Map view
        self.polygon_map_view = QWebEngineView()
        self.polygon_map_view.setMinimumHeight(400)
        self.polygon_map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.polygon_map_view)

        # Instructions
        instructions = QLabel("🎯 How to use:\n"
                            "1. Click 'Draw Polygon' to start drawing\n"
                            "2. Click on map to place points, double-click to finish\n"
                            "3. Click 'Save Changes' to save to database\n"
                            "4. Select polygon then 'Delete Selected' to remove")
        instructions.setStyleSheet("color: #666; font-size: 10px; padding: 5px;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Create initial map
        self.create_polygon_map()

        # Set up JavaScript bridge AFTER creating the map
        self.setup_javascript_bridge()

        # Load existing polygon if available
        if self.site_data.get('coordinates') and self.site_data['coordinates'].startswith('POLYGON'):
            self.load_existing_polygon()

    def setup_basic_info_tab(self):
        """Set up the basic information tab."""
        basic_tab = QWidget()
        layout = QVBoxLayout(basic_tab)

        # Form layout for site information
        form_group = QGroupBox("Site Information")
        form_layout = QFormLayout(form_group)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter site name")
        form_layout.addRow("Site Name*:", self.name_edit)

        self.owner_edit = QLineEdit()
        self.owner_edit.setPlaceholderText("Enter owner/organization")
        form_layout.addRow("Owner:", self.owner_edit)

        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("Enter location/area")
        form_layout.addRow("Location:", self.location_edit)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Enter any additional notes...")
        self.notes_edit.setMaximumHeight(100)
        form_layout.addRow("Notes:", self.notes_edit)

        layout.addWidget(form_group)

        # Instructions
        instructions = QLabel("* Required field\n\nNext: Go to the Location tab to set the site's geographical boundaries, or click OK to create the site without location data.")
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(instructions)

        layout.addStretch()
        self.tab_widget.addTab(basic_tab, "Basic Information")

    def setup_location_tab(self):
        """Set up the location/map tab."""
        location_tab = QWidget()
        layout = QVBoxLayout(location_tab)

        # Location options
        options_group = QGroupBox("Location Options")
        options_layout = QVBoxLayout(options_group)

        self.skip_location_checkbox = QCheckBox("Skip location selection (create site without geographical data)")
        self.skip_location_checkbox.setChecked(True)  # Default to skipping
        self.skip_location_checkbox.stateChanged.connect(self.on_skip_location_changed)
        options_layout.addWidget(self.skip_location_checkbox)

        layout.addWidget(options_group)

        # Address search
        search_group = QGroupBox("Address Search")
        search_layout = QHBoxLayout(search_group)

        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("Enter address to search...")
        self.address_edit.setEnabled(False)
        search_layout.addWidget(self.address_edit)

        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.search_address)
        self.search_btn.setEnabled(False)
        search_layout.addWidget(self.search_btn)

        layout.addWidget(search_group)

        # Map area
        map_group = QGroupBox("Site Location Map")
        map_layout = QVBoxLayout(map_group)

        # Create folium map for location selection
        self.location_map_view = QWebEngineView()
        self.location_map_view.setMinimumHeight(400)
        self.location_map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        map_layout.addWidget(self.location_map_view)

        # Create initial map
        self.create_location_map()

        # Map controls
        controls_layout = QHBoxLayout()

        self.draw_polygon_btn = QPushButton("Draw Site Boundary")
        self.draw_polygon_btn.clicked.connect(self.enable_polygon_drawing)
        self.draw_polygon_btn.setEnabled(False)
        controls_layout.addWidget(self.draw_polygon_btn)

        self.clear_selection_btn = QPushButton("Clear Selection")
        self.clear_selection_btn.clicked.connect(self.clear_location_selection)
        self.clear_selection_btn.setEnabled(False)
        controls_layout.addWidget(self.clear_selection_btn)

        controls_layout.addStretch()

        map_layout.addLayout(controls_layout)

        layout.addWidget(map_group)

        self.tab_widget.addTab(location_tab, "Location")

    def on_skip_location_changed(self, state):
        """Handle skip location checkbox state change."""
        skip_location = state == Qt.Checked
        self.address_edit.setEnabled(not skip_location)
        self.search_btn.setEnabled(not skip_location)
        self.draw_polygon_btn.setEnabled(not skip_location)
        self.clear_selection_btn.setEnabled(not skip_location)



    def search_address(self):
        """Search for an address on the map using Nominatim geocoding service."""
        address = self.address_edit.text().strip()
        if not address:
            QMessageBox.warning(self, "No Address", "Please enter an address to search.")
            return

        # Show loading indicator (non-blocking)
        self.search_btn.setText("Searching...")
        self.search_btn.setEnabled(False)
        self.address_edit.setEnabled(False)

        try:
            # Use Nominatim geocoding service (OpenStreetMap) - FREE, no API key needed
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': address,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            }
            headers = {
                'User-Agent': 'Flight-Ops-Manager/1.0'
            }

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data:
                result = data[0]
                lat = float(result['lat'])
                lon = float(result['lon'])
                display_name = result['display_name']

                # Update map to show the found location
                self.update_map_location(lat, lon, display_name)

                # Show success message (brief, non-blocking)
                QMessageBox.information(self, "Location Found",
                                      f"Found: {display_name[:50]}...\n\n"
                                      f"Coordinates: {lat:.4f}, {lon:.4f}")
            else:
                QMessageBox.warning(self, "No Results",
                                  f"No location found for: {address}\n\n"
                                  f"Try a different address format or check spelling.")

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Network Error",
                               f"Unable to search address:\n{str(e)}\n\n"
                               f"Check your internet connection.")
        except Exception as e:
            QMessageBox.critical(self, "Search Error",
                               f"Error searching address:\n{str(e)}")
        finally:
            # Reset UI
            self.search_btn.setText("Search")
            self.search_btn.setEnabled(True)
            self.address_edit.setEnabled(True)

    def create_location_map(self):
        """Create the folium map on the Location tab with Leaflet.Draw and geometry capture."""
        try:
            # Base map
            m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)

            # Add Draw plugin for polygon/marker
            draw = Draw(
                draw_options={
                    'polyline': False,
                    'rectangle': False,
                    'circle': False,
                    'marker': True,
                    'circlemarker': False,
                    'polygon': {
                        'allowIntersection': False,
                        'drawError': {
                            'color': '#e1e100',
                            'message': '<strong>Error:</strong> Shape edges cannot cross!'
                        },
                        'shapeOptions': {
                            'color': '#007bff',
                            'weight': 2,
                            'fillColor': '#007bff',
                            'fillOpacity': 0.3
                        }
                    }
                },
                edit_options={
                    'featureGroup': None,
                    'edit': True,
                    'remove': True
                }
            )
            m.add_child(draw)

            # Inject JavaScript to manage geometry
            js_code = """
            <script>
            (function(){
                function ensureMapVar() {
                    if (typeof map !== 'undefined' && map && map.setView) return map;
                    var _mk = Object.keys(window).find(function(k){ return k.indexOf('map_') === 0 && window[k] && window[k].setView; });
                    if (_mk) { window.map = window[_mk]; return window.map; }
                    return null;
                }

                function attachHandlers() {
                    window.drawnGeometry = null;
                    window.drawnItems = new L.FeatureGroup();
                    map.addLayer(window.drawnItems);

                    // Auto-save to localStorage for persistence
                    function saveToStorage(wkt) {
                        try {
                            localStorage.setItem('temp_site_geometry', wkt || '');
                            console.log('Saved geometry to localStorage:', wkt);
                        } catch(e) { console.warn('Failed to save to localStorage:', e); }
                    }

                    // Load from localStorage on init
                    function loadFromStorage() {
                        try {
                            var stored = localStorage.getItem('temp_site_geometry');
                            if (stored && stored !== 'null' && stored !== '') {
                                window.drawnGeometry = stored;
                                console.log('Loaded geometry from localStorage:', stored);
                                // Try to recreate polygon from WKT
                                if (stored.indexOf('POLYGON') === 0) {
                                    var coordsStr = stored.replace('POLYGON((', '').replace('))', '');
                                    var coordPairs = coordsStr.split(', ');
                                    var latlngs = coordPairs.map(function(pair) {
                                        var ll = pair.trim().split(' ');
                                        return [parseFloat(ll[1]), parseFloat(ll[0])];
                                    });
                                    if (latlngs.length > 0) {
                                        var polygon = L.polygon(latlngs, {
                                            color: '#007bff', weight: 3, opacity: 0.8, fillColor: '#007bff', fillOpacity: 0.3
                                        });
                                        window.drawnItems.addLayer(polygon);
                                        map.fitBounds(polygon.getBounds());
                                    }
                                }
                            }
                        } catch(e) { console.warn('Failed to load from localStorage:', e); }
                    }

                    setTimeout(function(){
                        try {
                            if (map && map._controls) {
                                for (var i = 0; i < map._controls.length; i++) {
                                    var ctl = map._controls[i];
                                    if (ctl && ctl.options && ctl.options.edit && ctl.options.draw) {
                                        window.drawControl = ctl;
                                        break;
                                    }
                                }
                            }
                        } catch(e) { console.warn('Unable to capture draw control:', e); }
                        loadFromStorage();
                    }, 100);

                    map.on('draw:created', function (e) {
                        var type = e.layerType, layer = e.layer;
                        window.drawnItems.clearLayers(); // Clear previous
                        window.drawnItems.addLayer(layer);
                        var wkt = '';
                        if (type === 'polygon') {
                            var coords = layer.getLatLngs()[0];
                            wkt = 'POLYGON((' + coords.map(function(c){ return c.lng + ' ' + c.lat; }).join(', ') + '))';
                        } else if (type === 'marker') {
                            var c = layer.getLatLng();
                            wkt = 'POINT(' + c.lng + ' ' + c.lat + ')';
                        }
                        window.drawnGeometry = wkt;
                        saveToStorage(wkt);
                        console.log('Geometry created:', wkt);
                    });

                    map.on('draw:edited', function (e) {
                        e.layers.eachLayer(function (layer) {
                            if (layer instanceof L.Polygon) {
                                var coords = layer.getLatLngs()[0];
                                var wkt = 'POLYGON((' + coords.map(function(c){ return c.lng + ' ' + c.lat; }).join(', ') + '))';
                                window.drawnGeometry = wkt;
                                saveToStorage(wkt);
                                console.log('Geometry edited:', wkt);
                            }
                        });
                    });

                    map.on('draw:deleted', function () {
                        window.drawnGeometry = null;
                        saveToStorage('');
                        console.log('Geometry deleted');
                    });
                }

                function initWhenReady(tries) {
                    var m = ensureMapVar();
                    if (m) { attachHandlers(); }
                    else if (tries < 50) { setTimeout(function(){ initWhenReady(tries+1); }, 50); }
                    else { console.warn('Leaflet map variable not found'); }
                }
                initWhenReady(0);
            })();
            </script>
            """
            m.get_root().html.add_child(folium.Element(js_code))

            map_html = m.get_root().render()
            self.location_map_view.setHtml(map_html)
        except Exception as e:
            print(f"Error creating location map (creation dialog): {e}")

    def enable_polygon_drawing(self):
        """Enable polygon drawing on the map."""
        try:
            # Attempt to programmatically start Leaflet.Draw polygon tool
            # Assumes the location map was created with Leaflet.Draw and a draw control
            if hasattr(self, 'location_map_view') and self.location_map_view:
                self.location_map_view.page().runJavaScript(
                    """
                    (function(){
                        try {
                            // Ensure we have a reference to the Leaflet map instance
                            if (typeof map === 'undefined' || !(map && map.setView)) {
                                var mk = Object.keys(window).find(function(k){ return k.indexOf('map_') === 0 && window[k] && window[k].setView; });
                                if (mk) { window.map = window[mk]; }
                            }
                            if (typeof L !== 'undefined' && typeof L.Draw !== 'undefined' && typeof map !== 'undefined') {
                                // Use options from an existing control if present
                                var polyOpts = (window.drawControl && window.drawControl.options && window.drawControl.options.draw && window.drawControl.options.draw.polygon) || {};
                                // Create and enable a polygon drawer
                                window._activeDrawer = new L.Draw.Polygon(map, polyOpts);
                                window._activeDrawer.enable();
                                return 'enabled';
                            }
                            return 'not_ready';
                        } catch (e) {
                            console.error('Error enabling polygon draw:', e);
                            return 'error';
                        }
                    })();
                    """
                )
                QMessageBox.information(self, "Draw Polygon",
                                        "Click on the map to start drawing the site boundary.\n"
                                        "Complete the polygon by clicking back on the starting point.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not enable polygon drawing: {str(e)}")

    def clear_location_selection(self):
        """Clear the current location selection."""
        self.selected_geometry = None
        if hasattr(self, 'location_map_view'):
            self.create_location_map()  # Recreate the map



    def get_site_data(self):
        """Get the site data from the form."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Site name is required.")
            return None

        site_data = {
            'name': name,
            'owner': self.owner_edit.text().strip(),
            'location': self.location_edit.text().strip(),
            'notes': self.notes_edit.toPlainText().strip()
        }

        # Add geometry if available
        if self.selected_geometry:
            site_data['geometry'] = self.selected_geometry

        return site_data

    def accept(self):
        """Handle dialog acceptance with geometry capture."""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "Site name is required.")
            return

        # Try to capture any drawn geometry from the map
        if hasattr(self, 'location_map_view') and self.location_map_view:
            try:
                # Check if geometry was captured by checking the JavaScript variable
                self.location_map_view.page().runJavaScript(
                    """
                    (function(){
                        function ensureMapVar(){
                            if (typeof map !== 'undefined' && map && map.setView) return map;
                            var _mk = Object.keys(window).find(function(k){ return k.indexOf('map_')===0 && window[k] && window[k].setView; });
                            if (_mk) { window.map = window[_mk]; return window.map; }
                            return null;
                        }
                        function layerToWKT(layer){
                            if (!layer) return null;
                            if (layer instanceof L.Polygon){
                                var coords = layer.getLatLngs()[0] || [];
                                if (!coords.length) return null;
                                return 'POLYGON((' + coords.map(function(c){ return c.lng + ' ' + c.lat; }).join(', ') + '))';
                            }
                            if (layer instanceof L.Marker){
                                var c = layer.getLatLng();
                                return 'POINT(' + c.lng + ' ' + c.lat + ')';
                            }
                            return null;
                        }
                        ensureMapVar();
                        if (window.drawnGeometry && window.drawnGeometry !== 'null' && window.drawnGeometry !== ''){
                            return window.drawnGeometry;
                        }
                        if (window.drawnItems){
                            var layers = window.drawnItems.getLayers();
                            for (var i=0;i<layers.length;i++){
                                var w = layerToWKT(layers[i]);
                                if (w) return w;
                            }
                        }
                        if (typeof map !== 'undefined'){
                            var found = null;
                            map.eachLayer(function(layer){ if (!found) found = layerToWKT(layer); });
                            if (found) return found;
                        }
                        return null;
                    })();
                    """,
                    self.on_geometry_check
                )
                # Don't call super().accept() yet - wait for JavaScript callback
                return
            except Exception as e:
                print(f"Error capturing geometry: {e}")
                # If JavaScript fails, proceed without geometry
                super().accept()
        else:
            # No map available - proceed normally
            super().accept()

    def on_geometry_check(self, geometry):
        """Handle geometry check from JavaScript variable."""
        if geometry and geometry != 'null' and geometry != '':
            self.selected_geometry = geometry
            print(f"Geometry checked from map: {geometry}")

            # Calculate center point for polygons
            if geometry.startswith('POLYGON'):
                center_point = self.calculate_polygon_center(geometry)
                if center_point:
                    print(f"Calculated center point: {center_point}")
                    # Store center point as additional geometry data
                    self.center_geometry = center_point
        else:
            print("No geometry found in map")

        # Now proceed with dialog acceptance
        super().accept()

    def calculate_polygon_center(self, wkt_polygon):
        """Calculate the center point of a polygon from WKT format."""
        try:
            # Parse WKT polygon format: POLYGON((x1 y1, x2 y2, ..., xn yn))
            coords_str = wkt_polygon.replace('POLYGON((', '').replace('))', '')
            coord_pairs = coords_str.split(', ')

            latitudes = []
            longitudes = []

            for pair in coord_pairs:
                if pair.strip():
                    lon, lat = map(float, pair.strip().split())
                    latitudes.append(lat)
                    longitudes.append(lon)

            if latitudes and longitudes:
                # Calculate centroid (average of all points)
                center_lat = sum(latitudes) / len(latitudes)
                center_lon = sum(longitudes) / len(longitudes)
                return f'POINT({center_lon} {center_lat})'

        except Exception as e:
            print(f"Error calculating polygon center: {e}")

        return None

    def reject(self):
        """Handle dialog rejection."""
        super().reject()


class SiteEditDialog(QDialog):
    """Simplified dialog for editing existing sites with map controls."""

    def __init__(self, site_data, parent=None):
        super().__init__(parent)
        self.site_data = site_data
        self.setWindowTitle(f"Edit Site: {site_data['name']}")
        self.setModal(True)
        self.resize(500, 300)  # Compact window size - shorter height

        # Store geometry data
        self.selected_geometry = site_data.get('coordinates')
        self.map_file = None

        self.setup_ui()

    def setup_javascript_bridge(self):
        """Set up JavaScript bridge for auto-save functionality."""
        if hasattr(self, 'polygon_map_view') and self.polygon_map_view:
            # Create a channel for JavaScript to Python communication
            self.polygon_map_view.page().setWebChannel(self.create_web_channel())

    def create_web_channel(self):
        """Create web channel for JavaScript communication."""
        from PyQt5.QtWebChannel import QWebChannel
        from PyQt5.QtCore import QObject, pyqtSlot

        class Bridge(QObject):
            def __init__(self, parent):
                super().__init__()
                self.parent = parent

            @pyqtSlot(str)
            def autoSaveGeometry(self, wkt):
                """Handle auto-save from JavaScript."""
                self.parent.handle_auto_save(wkt)

        channel = QWebChannel()
        bridge = Bridge(self)
        channel.registerObject('qt', bridge)
        return channel

    def handle_auto_save(self, wkt):
        """Handle automatic saving of geometry changes."""
        try:
            print(f"Auto-saving geometry for site {self.site_data['id']}: {wkt}")

            if db_manager.session:
                if wkt and wkt != 'null' and wkt != '':
                    # Save geometry
                    query = text("""
                        UPDATE sites
                        SET geom = ST_GeomFromText(:geom, 4326), updated_at = datetime('now')
                        WHERE site_ID = :site_id
                    """)
                    db_manager.session.execute(query, {
                        'site_id': self.site_data['id'],
                        'geom': wkt
                    })
                else:
                    # Clear geometry
                    query = text("""
                        UPDATE sites
                        SET geom = NULL, updated_at = datetime('now')
                        WHERE site_ID = :site_id
                    """)
                    db_manager.session.execute(query, {'site_id': self.site_data['id']})

                db_manager.session.commit()

                # Update local data
                if wkt and wkt != 'null' and wkt != '':
                    self.site_data['coordinates'] = wkt
                    self.selected_geometry = wkt

                    # Update coordinate display if it's a point
                    if wkt.startswith('POINT'):
                        coords_match = wkt.replace('POINT(', '').replace(')', '').split()
                        if len(coords_match) == 2:
                            try:
                                lon = float(coords_match[0])
                                lat = float(coords_match[1])
                                self.current_lat_label.setText(f"{lat:.6f}")
                                self.current_lon_label.setText(f"{lon:.6f}")
                            except ValueError:
                                pass
                else:
                    self.site_data['coordinates'] = None
                    self.selected_geometry = None
                    self.current_lat_label.setText("Not set")
                    self.current_lon_label.setText("Not set")

                print("✅ Auto-save completed successfully")

            else:
                print("❌ Database connection not available for auto-save")

        except Exception as e:
            print(f"❌ Auto-save error: {str(e)}")
            if db_manager.session:
                db_manager.session.rollback()

    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Create tab widget for different sections
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Basic Information Tab
        self.setup_basic_info_tab()

        # Location/Map Tab
        self.setup_location_tab()

        # Save button and dialog buttons
        buttons_layout = QHBoxLayout()

        self.save_geometry_btn = QPushButton("💾 Save Geometry")
        self.save_geometry_btn.clicked.connect(self.save_geometry_to_database)
        self.save_geometry_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; font-weight: bold; padding: 8px 16px; }")
        buttons_layout.addWidget(self.save_geometry_btn)

        buttons_layout.addStretch()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        buttons_layout.addWidget(self.button_box)

        layout.addLayout(buttons_layout)

    def setup_basic_info_tab(self):
        """Set up the basic information tab with existing data."""
        basic_tab = QWidget()
        layout = QVBoxLayout(basic_tab)

        # Form layout for site information
        form_group = QGroupBox("Site Information")
        form_layout = QFormLayout(form_group)

        self.name_edit = QLineEdit(self.site_data['name'])
        self.name_edit.setPlaceholderText("Enter site name")
        form_layout.addRow("Site Name*:", self.name_edit)

        self.owner_edit = QLineEdit(self.site_data['owner'])
        self.owner_edit.setPlaceholderText("Enter owner/organization")
        form_layout.addRow("Owner:", self.owner_edit)

        self.location_edit = QLineEdit(self.site_data['location'])
        self.location_edit.setPlaceholderText("Enter location/area")
        form_layout.addRow("Location:", self.location_edit)

        self.notes_edit = QTextEdit(self.site_data['notes'])
        self.notes_edit.setPlaceholderText("Enter any additional notes...")
        self.notes_edit.setMaximumHeight(100)
        form_layout.addRow("Notes:", self.notes_edit)

        layout.addWidget(form_group)

        # Instructions
        instructions = QLabel("* Required field\n\nGo to the Location tab to update the site's geographical boundaries.")
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(instructions)

        layout.addStretch()
        self.tab_widget.addTab(basic_tab, "Basic Information")

    def setup_location_tab(self):
        """Set up the location/map tab with simplified interface."""
        location_tab = QWidget()
        layout = QVBoxLayout(location_tab)

        # Current location display
        current_location_group = QGroupBox("Current Location")
        current_layout = QVBoxLayout(current_location_group)

        # Display current coordinates
        coords_layout = QHBoxLayout()
        coords_layout.addWidget(QLabel("Latitude:"))
        self.current_lat_label = QLabel(str(self.site_data.get('latitude', 'Not set')))
        coords_layout.addWidget(self.current_lat_label)
        coords_layout.addWidget(QLabel("Longitude:"))
        self.current_lon_label = QLabel(str(self.site_data.get('longitude', 'Not set')))
        coords_layout.addWidget(self.current_lon_label)
        coords_layout.addStretch()
        current_layout.addLayout(coords_layout)

        layout.addWidget(current_location_group)

        # Location input options
        input_group = QGroupBox("Set Location")
        input_layout = QVBoxLayout(input_group)

        # Address search
        search_group = QGroupBox("Address Search")
        search_layout = QHBoxLayout(search_group)

        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("Enter address...")
        search_layout.addWidget(self.address_edit)

        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.clicked.connect(self.search_address)
        search_layout.addWidget(self.search_btn)

        input_layout.addWidget(search_group)

        # Option 3: Polygon drawing with folium
        polygon_group = QGroupBox("Draw Site Polygon")
        polygon_layout = QVBoxLayout(polygon_group)

        # Create folium map widget for polygon drawing
        self.polygon_map_view = QWebEngineView()
        self.polygon_map_view.setMinimumHeight(400)  # Ensure minimum height
        self.polygon_map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        polygon_layout.addWidget(self.polygon_map_view)

        # Create initial map with Draw plugin
        self.create_polygon_map()

        # Set up JavaScript bridge AFTER creating the map
        self.setup_javascript_bridge()

        # Load existing polygon if available
        if self.site_data.get('coordinates') and self.site_data['coordinates'].startswith('POLYGON'):
            self.load_existing_polygon()

        # Removed verbose instructions to keep window compact

        input_layout.addWidget(polygon_group)

        layout.addWidget(input_group)

        # Clear location option
        clear_layout = QHBoxLayout()
        self.clear_location_btn = QPushButton("🗑️ Clear Location")
        self.clear_location_btn.clicked.connect(self.clear_location)
        self.clear_location_btn.setStyleSheet("QPushButton { color: #d9534f; }")
        clear_layout.addWidget(self.clear_location_btn)
        clear_layout.addStretch()
        layout.addLayout(clear_layout)

        self.tab_widget.addTab(location_tab, "Location")



    def search_address(self):
        """Search for an address and set coordinates."""
        address = self.address_edit.text().strip()
        if not address:
            QMessageBox.warning(self, "No Address", "Please enter an address to search.")
            return

        try:
            # Use Nominatim geocoding service
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': address,
                'format': 'json',
                'limit': 1
            }
            headers = {
                'User-Agent': 'Flight-Ops-Manager/1.0'
            }

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data:
                result = data[0]
                lat = float(result['lat'])
                lon = float(result['lon'])
                display_name = result['display_name']

                # Set the coordinates
                self.selected_geometry = f'POINT({lon} {lat})'

                # Update display
                self.current_lat_label.setText(f"{lat:.6f}")
                self.current_lon_label.setText(f"{lon:.6f}")

                QMessageBox.information(self, "Location Found",
                                      f"📍 Found: {display_name[:50]}...\n\n"
                                      f"Coordinates: {lat:.6f}, {lon:.6f}")
            else:
                QMessageBox.warning(self, "No Results",
                                  f"No location found for: {address}")

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Network Error",
                               f"Unable to search address:\n{str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Search Error",
                               f"Error searching address:\n{str(e)}")



    def create_polygon_map(self):
        """Create a folium map with Draw plugin for polygon editing."""
        try:
            # Create folium map centered on the site's location or default
            if self.site_data.get('latitude') and self.site_data.get('longitude'):
                center_lat = self.site_data['latitude']
                center_lon = self.site_data['longitude']
                zoom_level = 15
            else:
                center_lat, center_lon = 39.8283, -98.5795  # Center of USA
                zoom_level = 4

            # Create map with Draw plugin
            m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level)

            # Add Draw plugin with polygon drawing capabilities
            draw = Draw(
                draw_options={
                    'polyline': False,
                    'rectangle': False,
                    'circle': False,
                    'marker': True,
                    'circlemarker': False,
                    'polygon': {
                        'allowIntersection': False,
                        'drawError': {
                            'color': '#e1e100',
                            'message': '<strong>Error:</strong> Shape edges cannot cross!'
                        },
                        'shapeOptions': {
                            'color': '#007bff',
                            'weight': 2,
                            'fillColor': '#007bff',
                            'fillOpacity': 0.3
                        }
                    }
                },
                edit_options={
                    'featureGroup': None,
                    'edit': True,
                    'remove': True
                }
            )
            m.add_child(draw)

            # Add JavaScript to capture drawn geometries with auto-save
            site_id = self.site_data['id']
            initial_wkt = {json.dumps(self.site_data.get('coordinates') if self.site_data.get('coordinates') else '')}
            js_code = f"""
            <script>
            // Ensure we have a reference to the Leaflet map instance
            if (typeof map === 'undefined' || !(map && map.setView)) {{
                var _mk = Object.keys(window).find(function(k){{ return k.indexOf('map_') === 0 && window[k] && window[k].setView; }});
                if (_mk) {{ window.map = window[_mk]; }}
            }}

            // Initialize window.drawnGeometry
            window.drawnGeometry = null;
            var drawnItems = new L.FeatureGroup();
            map.addLayer(drawnItems);
            var siteId = {site_id};
            console.log('Map initialized with site ID:', siteId);

            // Auto-save function - check if Qt bridge is available
            function autoSaveGeometry(wkt) {{
                console.log('Attempting auto-save with geometry:', wkt);
                console.log('Qt bridge available:', typeof window.qt !== 'undefined');
                if (window.qt && window.qt.autoSaveGeometry) {{
                    try {{
                        window.qt.autoSaveGeometry(wkt);
                        console.log('✅ Auto-save sent to Python successfully');
                    }} catch (error) {{
                        console.error('❌ Error sending auto-save to Python:', error);
                    }}
                }} else {{
                    console.warn('⚠️ Qt bridge not available for auto-save');
                }}
            }}

            // Test Qt bridge connectivity on map load
            setTimeout(function() {{
                console.log('Testing Qt bridge connectivity...');
                if (window.qt && window.qt.autoSaveGeometry) {{
                    console.log('✅ Qt bridge is connected and ready');
                }} else {{
                    console.warn('⚠️ Qt bridge not connected - auto-save will not work');
                }}
            }}, 1000);

            map.on('draw:created', function (e) {{
                var type = e.layerType,
                    layer = e.layer;

                drawnItems.addLayer(layer);

                // Convert to WKT
                var wkt = '';
                if (type === 'polygon') {{
                    var coords = layer.getLatLngs()[0];
                    wkt = 'POLYGON((';
                    for (var i = 0; i < coords.length; i++) {{
                        wkt += coords[i].lng + ' ' + coords[i].lat;
                        if (i < coords.length - 1) wkt += ', ';
                    }}
                    wkt += '))';
                }} else if (type === 'marker') {{
                    var coord = layer.getLatLng();
                    wkt = 'POINT(' + coord.lng + ' ' + coord.lat + ')';
                }}

                // Store in window variable for Python access
                window.drawnGeometry = wkt;
                console.log('Geometry created:', wkt);

                // Auto-save immediately
                autoSaveGeometry(wkt);
            }});

            map.on('draw:edited', function (e) {{
                var layers = e.layers;
                layers.eachLayer(function (layer) {{
                    // Update geometry
                    if (layer instanceof L.Polygon) {{
                        var coords = layer.getLatLngs()[0];
                        var wkt = 'POLYGON((';
                        for (var i = 0; i < coords.length; i++) {{
                            wkt += coords[i].lng + ' ' + coords[i].lat;
                            if (i < coords.length - 1) wkt += ', ';
                        }}
                        wkt += '))';
                        window.drawnGeometry = wkt;
                        console.log('Geometry edited:', wkt);

                        // Auto-save immediately
                        autoSaveGeometry(wkt);
                    }}
                }});
            }});

            map.on('draw:deleted', function (e) {{
                window.drawnGeometry = null;
                console.log('Geometry deleted - auto-saving NULL');

                // Auto-save immediately (clear geometry)
                autoSaveGeometry(null);
            }});

            // Preload existing polygon if available
            (function(){{
                try {{
                    var wkt = {json.dumps(self.site_data.get('coordinates') if self.site_data.get('coordinates') else '')};
                    if (wkt && wkt.indexOf('POLYGON') === 0) {{
                        var coordsStr = wkt.replace('POLYGON((', '').replace('))', '');
                        var coordPairs = coordsStr.split(', ');
                        var latlngs = coordPairs.map(function(pair) {{
                            var ll = pair.trim().split(' ');
                            return [parseFloat(ll[1]), parseFloat(ll[0])];
                        }});
                        var polygon = L.polygon(latlngs, {{
                            color: '#007bff', weight: 3, opacity: 0.8, fillColor: '#007bff', fillOpacity: 0.3
                        }});
                        window.drawnItems.addLayer(polygon);
                        window.drawnGeometry = wkt;
                        map.fitBounds(polygon.getBounds());
                    }}
                }} catch (e) {{ console.warn('Failed to preload WKT polygon:', e); }}
            }})();
            </script>
            """

            # Add JavaScript to the map
            m.get_root().html.add_child(folium.Element(js_code))

            # Save map to HTML and load in web view
            map_html = m.get_root().render()
            self.polygon_map_view.setHtml(map_html)

        except Exception as e:
            print(f"Error creating polygon map: {e}")
            # Create basic map on error
            try:
                m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)
                map_html = m.get_root().render()
                self.polygon_map_view.setHtml(map_html)
            except:
                pass

    def save_geometry_to_database(self):
        """Save the current geometry from the edit dialog map to the database."""
        try:
            if hasattr(self, 'polygon_map_view') and self.polygon_map_view:
                self.polygon_map_view.page().runJavaScript(
                    "window.drawnGeometry",
                    self.on_save_geometry_callback
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save geometry: {str(e)}")

    def on_save_geometry_callback(self, geometry):
        """Handle geometry saving callback for edit dialog."""
        try:
            if geometry and geometry != 'null' and geometry != '':
                if db_manager.session:
                    query = text(
                        """
                        UPDATE sites
                        SET geom = ST_GeomFromText(:geom, 4326), updated_at = datetime('now')
                        WHERE site_ID = :site_id
                        """
                    )
                    db_manager.session.execute(query, {
                        'site_id': self.site_data['id'],
                        'geom': geometry
                    })
                    db_manager.session.commit()
                    self.site_data['coordinates'] = geometry
                    self.selected_geometry = geometry
                    QMessageBox.information(self, "Success", "✅ Geometry saved successfully to database!")
                else:
                    QMessageBox.critical(self, "Database Error", "No database connection available.")
            else:
                QMessageBox.information(self, "No Changes", "No geometry changes to save.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save geometry: {str(e)}")
            if db_manager.session:
                db_manager.session.rollback()

    def clear_location(self):
        """Clear the current location and remove all polygons from the map and database."""
        reply = QMessageBox.question(
            self, "Clear Location",
            "Are you sure you want to remove all location data and polygons for this site?\n\n"
            "This will permanently delete the geographical boundaries from the database.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # Immediately update the database to clear geometry
                if db_manager.session:
                    query = text("""
                        UPDATE sites
                        SET geom = NULL, updated_at = datetime('now')
                        WHERE site_ID = :site_id
                    """)
                    db_manager.session.execute(query, {'site_id': self.site_data['id']})
                    db_manager.session.commit()

                    # Update the site data to reflect the change
                    self.site_data['coordinates'] = None
                    self.site_data['longitude'] = None
                    self.site_data['latitude'] = None

                    # Clear the UI
                    self.selected_geometry = None
                    self.current_lat_label.setText("Not set")
                    self.current_lon_label.setText("Not set")
                    self.address_edit.clear()

                    # Recreate the map without geometry
                    self.create_polygon_map()

                    QMessageBox.information(self, "Location Cleared",
                                          "✅ All location data and polygons have been permanently removed from the database.")
                else:
                    QMessageBox.critical(self, "Database Error", "No database connection available.")

            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Failed to clear location: {str(e)}")
                db_manager.session.rollback()

    def on_polygon_created(self, geometry_type, geometry_data):
        """Handle polygon creation from the map."""
        if geometry_type == 'polygon' and geometry_data.get('wkt'):
            self.selected_geometry = geometry_data['wkt']
            print(f"Polygon created in edit dialog: {self.selected_geometry}")

            QMessageBox.information(self, "Polygon Created",
                                  "✅ Polygon successfully created!\n\n"
                                  "The boundary will be saved when you click OK.")

    def on_polygon_edited(self, geometry_type, geometry_data):
        """Handle polygon editing from the map."""
        if geometry_type == 'polygon' and geometry_data.get('wkt'):
            self.selected_geometry = geometry_data['wkt']
            print(f"Polygon edited in edit dialog: {self.selected_geometry}")

    def on_polygon_deleted(self, geometry_id):
        """Handle polygon deletion from the map."""
        self.selected_geometry = None
        print("Polygon deleted in edit dialog")



    def load_existing_polygon(self):
        """Load the existing polygon geometry for the site."""
        if self.site_data.get('coordinates') and self.site_data['coordinates'].startswith('POLYGON'):
            try:
                # Parse WKT polygon and create folium map with existing geometry
                coords_str = self.site_data['coordinates'].replace('POLYGON((', '').replace('))', '')
                coord_pairs = coords_str.split(', ')

                coordinates = []
                for pair in coord_pairs:
                    if pair.strip():
                        lon, lat = map(float, pair.strip().split())
                        coordinates.append([lat, lon])  # folium uses [lat, lon]

                if coordinates:
                    # Create folium map centered on the polygon
                    center_lat = sum(coord[0] for coord in coordinates) / len(coordinates)
                    center_lon = sum(coord[1] for coord in coordinates) / len(coordinates)

                    m = folium.Map(location=[center_lat, center_lon], zoom_start=15)

                    # Add the existing polygon
                    folium.Polygon(
                        locations=coordinates,
                        color='red',
                        weight=3,
                        fill=True,
                        fill_color='red',
                        fill_opacity=0.4,
                        popup="Existing site boundary"
                    ).add_to(m)

                    # Add Draw plugin for editing
                    draw = Draw(
                        draw_options={
                            'polyline': False,
                            'rectangle': False,
                            'circle': False,
                            'marker': True,
                            'circlemarker': False,
                            'polygon': {
                                'allowIntersection': False,
                                'drawError': {
                                    'color': '#e1e100',
                                    'message': '<strong>Error:</strong> Shape edges cannot cross!'
                                },
                                'shapeOptions': {
                                    'color': '#007bff',
                                    'weight': 2,
                                    'fillColor': '#007bff',
                                    'fillOpacity': 0.3
                                }
                            }
                        },
                        edit_options={
                            'featureGroup': None,
                            'edit': True,
                            'remove': True
                        }
                    )
                    m.add_child(draw)

                    # Add JavaScript to capture drawn geometries
                    site_id = self.site_data['id']
                    js_code = f"""
                    <script>
                    // Ensure Leaflet map reference exists
                    if (typeof map === 'undefined' || !(map && map.setView)) {{
                        var _mk = Object.keys(window).find(function(k){{ return k.indexOf('map_') === 0 && window[k] && window[k].setView; }});
                        if (_mk) {{ window.map = window[_mk]; }}
                    }}
                    // Initialize window.drawnGeometry
                    window.drawnGeometry = null;
                    var drawnItems = new L.FeatureGroup();
                    map.addLayer(drawnItems);
                    var siteId = {site_id};
                    console.log('Map initialized with site ID:', siteId);

                    map.on('draw:created', function (e) {{
                        var type = e.layerType,
                            layer = e.layer;

                        drawnItems.addLayer(layer);

                        // Convert to WKT
                        var wkt = '';
                        if (type === 'polygon') {{
                            var coords = layer.getLatLngs()[0];
                            wkt = 'POLYGON((';
                            for (var i = 0; i < coords.length; i++) {{
                                wkt += coords[i].lng + ' ' + coords[i].lat;
                                if (i < coords.length - 1) wkt += ', ';
                            }}
                            wkt += '))';
                        }} else if (type === 'marker') {{
                            var coord = layer.getLatLng();
                            wkt = 'POINT(' + coord.lng + ' ' + coord.lat + ')';
                        }}

                        // Store in window variable for Python access
                        window.drawnGeometry = wkt;
                        console.log('Geometry created:', wkt);
                    }});

                    map.on('draw:edited', function (e) {{
                        var layers = e.layers;
                        layers.eachLayer(function (layer) {{
                            // Update geometry
                            if (layer instanceof L.Polygon) {{
                                var coords = layer.getLatLngs()[0];
                                var wkt = 'POLYGON((';
                                for (var i = 0; i < coords.length; i++) {{
                                    wkt += coords[i].lng + ' ' + coords[i].lat;
                                    if (i < coords.length - 1) wkt += ', ';
                                }}
                                wkt += '))';
                                window.drawnGeometry = wkt;
                                console.log('Geometry edited:', wkt);
                            }}
                        }});
                    }});

                    map.on('draw:deleted', function (e) {{
                        window.drawnGeometry = null;
                        console.log('Geometry deleted');
                    }});
                    </script>
                    """

                    # Add JavaScript to the map
                    m.get_root().html.add_child(folium.Element(js_code))

                    # Save map to HTML and load in web view
                    map_html = m.get_root().render()
                    self.polygon_map_view.setHtml(map_html)

                    print(f"Loaded existing polygon: {self.site_data['coordinates']}")

            except Exception as e:
                print(f"Error loading existing polygon: {e}")
                # Fall back to creating empty map
                self.create_polygon_map()









    def get_site_data(self):
        """Get the updated site data from the form."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Site name is required.")
            return None

        site_data = {
            'name': name,
            'owner': self.owner_edit.text().strip(),
            'location': self.location_edit.text().strip(),
            'notes': self.notes_edit.toPlainText().strip()
        }

        # Add geometry if available
        if self.selected_geometry:
            site_data['geometry'] = self.selected_geometry

        return site_data

    def accept(self):
        """Handle dialog acceptance with geometry capture from folium map."""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "Site name is required.")
            return

        # Try to capture geometry from the folium map using JavaScript
        if hasattr(self, 'polygon_map_view') and self.polygon_map_view:
            try:
                # First, ensure window.drawnGeometry is initialized if not set
                self.polygon_map_view.page().runJavaScript(
                    """
                    if (typeof window.drawnGeometry === 'undefined') {
                        window.drawnGeometry = null;
                    }
                    window.drawnGeometry;
                    """,
                    self.on_geometry_capture
                )
                # Don't call super().accept() yet - wait for JavaScript callback
                return
            except Exception as e:
                print(f"Error capturing geometry: {e}")
                # If JavaScript fails, proceed without geometry
                super().accept()
        else:
            # No map available - proceed normally
            super().accept()

    def on_geometry_capture(self, geometry):
        """Handle geometry capture from JavaScript callback."""
        if geometry and geometry != 'null' and geometry != '':
            self.selected_geometry = geometry
            print(f"Geometry captured from folium map: {self.selected_geometry}")

            # Calculate center point for polygons
            if geometry.startswith('POLYGON'):
                center_point = self.calculate_polygon_center(geometry)
                if center_point:
                    print(f"Calculated center point: {center_point}")
                    # Store center point as additional geometry data
                    self.center_geometry = center_point
        else:
            print("No geometry found in folium map - keeping existing geometry")

        # Now proceed with dialog acceptance
        super().accept()

    def on_geometry_check(self, geometry):
        """Handle geometry check from JavaScript variable."""
        if geometry and geometry != 'null' and geometry != '':
            self.selected_geometry = geometry
            print(f"Geometry captured from polygon map: {geometry}")

            # Calculate center point for polygons
            if geometry.startswith('POLYGON'):
                center_point = self.calculate_polygon_center(geometry)
                if center_point:
                    print(f"Calculated center point: {center_point}")
                    # Store center point as additional geometry data
                    self.center_geometry = center_point
        else:
            print("No geometry found in polygon map")

        # Now proceed with dialog acceptance
        super().accept()

    def calculate_polygon_center(self, wkt_polygon):
        """Calculate the center point of a polygon from WKT format."""
        try:
            # Parse WKT polygon format: POLYGON((x1 y1, x2 y2, ..., xn yn))
            coords_str = wkt_polygon.replace('POLYGON((', '').replace('))', '')
            coord_pairs = coords_str.split(', ')

            latitudes = []
            longitudes = []

            for pair in coord_pairs:
                if pair.strip():
                    lon, lat = map(float, pair.strip().split())
                    latitudes.append(lat)
                    longitudes.append(lon)

            if latitudes and longitudes:
                # Calculate centroid (average of all points)
                center_lat = sum(latitudes) / len(latitudes)
                center_lon = sum(longitudes) / len(longitudes)
                return f'POINT({center_lon} {center_lat})'

        except Exception as e:
            print(f"Error calculating polygon center: {e}")

        return None
