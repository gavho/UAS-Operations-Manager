"""
METAR Configuration Module

This module provides configuration management for METAR API services.
Users can configure their preferred METAR provider and API keys.
"""

import json
import os
from typing import Dict, Optional, Any
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFormLayout, QMessageBox, QCheckBox
)

class MetarConfig:
    """Configuration manager for METAR services."""

    CONFIG_FILE = "metar_config.json"

    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading METAR config: {e}")
                return self._get_default_config()
        else:
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "provider": "iowa_mesonet",  # Default to Iowa Mesonet for comprehensive historic data
            "api_key": "",
            "cache_enabled": True,
            "cache_timeout": 3600,  # 1 hour
            "auto_fetch": False,    # Don't auto-fetch by default
            "common_stations": [
                "KJFK", "KLAX", "KORD", "KATL", "KDEN",
                "KDFW", "KSFO", "KSEA", "KBOS", "KLAS"
            ]
        }

    def save_config(self):
        """Save configuration to file."""
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except IOError as e:
            print(f"Error saving METAR config: {e}")

    def get_provider(self) -> str:
        """Get the configured METAR provider."""
        return self.config.get("provider", "aviation_weather")

    def get_api_key(self) -> str:
        """Get the API key for commercial services."""
        return self.config.get("api_key", "")

    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self.config.get("cache_enabled", True)

    def get_cache_timeout(self) -> int:
        """Get cache timeout in seconds."""
        return self.config.get("cache_timeout", 3600)

    def is_auto_fetch_enabled(self) -> bool:
        """Check if auto-fetch is enabled."""
        return self.config.get("auto_fetch", False)

    def get_common_stations(self) -> list:
        """Get list of common weather stations."""
        return self.config.get("common_stations", [])

    def set_provider(self, provider: str):
        """Set the METAR provider."""
        self.config["provider"] = provider
        self.save_config()

    def set_api_key(self, api_key: str):
        """Set the API key."""
        self.config["api_key"] = api_key
        self.save_config()

    def set_cache_enabled(self, enabled: bool):
        """Enable or disable caching."""
        self.config["cache_enabled"] = enabled
        self.save_config()

    def set_cache_timeout(self, timeout: int):
        """Set cache timeout."""
        self.config["cache_timeout"] = timeout
        self.save_config()

    def set_auto_fetch(self, enabled: bool):
        """Enable or disable auto-fetch."""
        self.config["auto_fetch"] = enabled
        self.save_config()

    def add_common_station(self, station: str):
        """Add a station to the common stations list."""
        stations = self.get_common_stations()
        if station not in stations:
            stations.append(station)
            self.config["common_stations"] = stations
            self.save_config()

    def remove_common_station(self, station: str):
        """Remove a station from the common stations list."""
        stations = self.get_common_stations()
        if station in stations:
            stations.remove(station)
            self.config["common_stations"] = stations
            self.save_config()


class MetarConfigDialog(QDialog):
    """Dialog for configuring METAR settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = MetarConfig()
        self.setWindowTitle("METAR Configuration")
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        """Set up the configuration dialog UI."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("METAR API Configuration")
        title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # Form layout
        form = QFormLayout()

        # Provider selection
        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "iowa_mesonet - Iowa State University (Free, Historic Data)",
            "aviation_weather - NOAA Aviation Weather (Free)",
            "checkwx - CheckWX API (Commercial)",
            "weatherapi - WeatherAPI (Commercial)"
        ])
        current_provider = self.config.get_provider()
        provider_map = {
            "iowa_mesonet": 0,
            "aviation_weather": 1,
            "checkwx": 2,
            "weatherapi": 3
        }
        self.provider_combo.setCurrentIndex(provider_map.get(current_provider, 0))
        form.addRow("METAR Provider:", self.provider_combo)

        # API Key
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(self.config.get_api_key())
        self.api_key_input.setEchoMode(QLineEdit.Password)  # Hide API key
        form.addRow("API Key:", self.api_key_input)

        # Cache settings
        self.cache_checkbox = QCheckBox()
        self.cache_checkbox.setChecked(self.config.is_cache_enabled())
        form.addRow("Enable Caching:", self.cache_checkbox)

        # Cache timeout
        self.cache_timeout_input = QLineEdit()
        self.cache_timeout_input.setText(str(self.config.get_cache_timeout()))
        form.addRow("Cache Timeout (seconds):", self.cache_timeout_input)

        # Auto-fetch
        self.auto_fetch_checkbox = QCheckBox()
        self.auto_fetch_checkbox.setChecked(self.config.is_auto_fetch_enabled())
        form.addRow("Auto-fetch METAR:", self.auto_fetch_checkbox)

        layout.addLayout(form)

        # Info text
        info_text = QLabel(
            "• Iowa Mesonet: Free, comprehensive historic data (years back)\n"
            "• Aviation Weather: Free, but limited to recent data (24-48 hours)\n"
            "• CheckWX: Commercial service with historic data support\n"
            "• WeatherAPI: Commercial service with historic data support\n\n"
            "Iowa Mesonet is recommended for historic METAR data. No API key required."
        )
        info_text.setStyleSheet("color: #666; font-size: 11px;")
        info_text.setWordWrap(True)
        layout.addWidget(info_text)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_config)
        save_btn.setDefault(True)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

        self.setMinimumWidth(500)

    def save_config(self):
        """Save the configuration."""
        try:
            # Get provider
            provider_index = self.provider_combo.currentIndex()
            provider_map = {
                0: "iowa_mesonet",
                1: "aviation_weather",
                2: "checkwx",
                3: "weatherapi"
            }
            provider = provider_map.get(provider_index, "iowa_mesonet")

            # Get API key
            api_key = self.api_key_input.text().strip()

            # Get cache settings
            cache_enabled = self.cache_checkbox.isChecked()
            try:
                cache_timeout = int(self.cache_timeout_input.text())
            except ValueError:
                cache_timeout = 3600

            # Get auto-fetch setting
            auto_fetch = self.auto_fetch_checkbox.isChecked()

            # Save to config
            self.config.set_provider(provider)
            self.config.set_api_key(api_key)
            self.config.set_cache_enabled(cache_enabled)
            self.config.set_cache_timeout(cache_timeout)
            self.config.set_auto_fetch(auto_fetch)

            QMessageBox.information(self, "Success", "METAR configuration saved successfully!")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")


# Global configuration instance
metar_config = MetarConfig()


def show_metar_config_dialog(parent=None):
    """Show the METAR configuration dialog."""
    dialog = MetarConfigDialog(parent)
    return dialog.exec_() == QDialog.Accepted
