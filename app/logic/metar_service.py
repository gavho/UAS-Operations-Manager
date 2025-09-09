import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from PyQt5.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

class MetarService:
    """
    Service for fetching METAR data from various aviation weather APIs.
    Supports multiple providers for redundancy and flexibility.
    """

    def __init__(self, api_key: str = None, provider: str = "iowa_mesonet"):
        """
        Initialize METAR service.

        Args:
            api_key: API key for commercial services (optional)
            provider: Weather data provider ('iowa_mesonet', 'aviation_weather', 'checkwx', 'weatherapi')
        """
        self.api_key = api_key
        self.provider = provider
        self.session = requests.Session()
        self.session.timeout = 30  # 30 second timeout for larger data requests

        # Cache for API responses to avoid repeated calls
        self.cache = {}
        self.cache_timeout = 3600  # 1 hour cache

    def get_metar(self, station_code: str, date: datetime = None) -> Optional[str]:
        """
        Get METAR data for a specific station and date.

        Args:
            station_code: ICAO airport code (e.g., 'KJFK', 'KLAX')
            date: Date for historic data (defaults to current if None)

        Returns:
            METAR string or None if not found
        """
        cache_key = f"{station_code}_{date.strftime('%Y%m%d') if date else 'current'}"

        # Check cache first
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if datetime.now() - cached_time < timedelta(seconds=self.cache_timeout):
                return cached_data

        try:
            if self.provider == "iowa_mesonet":
                metar_data = self._get_from_iowa_mesonet(station_code, date)
            elif self.provider == "aviation_weather":
                metar_data = self._get_from_aviation_weather(station_code, date)
            elif self.provider == "checkwx":
                metar_data = self._get_from_checkwx(station_code, date)
            elif self.provider == "weatherapi":
                metar_data = self._get_from_weatherapi(station_code, date)
            else:
                logger.error(f"Unknown provider: {self.provider}")
                return None

            # Cache the result
            self.cache[cache_key] = (datetime.now(), metar_data)
            return metar_data

        except Exception as e:
            logger.error(f"Error fetching METAR data: {e}")
            return None

    def _get_from_iowa_mesonet(self, station_code: str, date: datetime = None) -> Optional[str]:
        """
        Get METAR from Iowa State University Mesonet (free, comprehensive historic data).
        Supports historic data going back many years.
        """
        if not date:
            date = datetime.now()

        # Format date for the API
        date_str = date.strftime('%Y-%m-%d')

        url = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

        # Iowa Mesonet API parameters (reverted to working parameters)
        params = {
            'station': station_code.upper(),
            'data': 'metar',
            'year1': date.year,
            'month1': date.month,
            'day1': date.day,
            'year2': date.year,
            'month2': date.month,
            'day2': date.day,
            'tz': 'UTC',
            'format': 'onlycomma',
            'latlon': 'no',
            'missing': 'null',
            'trace': 'null'
        }



        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()

            # Parse the CSV response
            lines = response.text.strip().split('\n')
            if len(lines) < 2:  # No data
                return None

            # Find the most recent METAR for the requested date
            metars = []
            for line in lines[1:]:  # Skip header
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 3:  # station, valid, metar, ...
                        station = parts[0]
                        timestamp = parts[1]
                        metar_text = parts[2] if len(parts) > 2 else ''
                        if metar_text and metar_text != 'null' and metar_text.strip():
                            metars.append((timestamp, metar_text))

            if metars:
                # Return the most recent METAR
                return metars[-1][1]

        except requests.RequestException as e:
            logger.error(f"Iowa Mesonet API error: {e}")

        return None

    def get_metar_range(self, station_code: str, start_date: datetime, end_date: datetime) -> list:
        """
        Get METAR data for a date range from Iowa Mesonet.
        Returns list of (timestamp, metar) tuples.
        Filters to return only actual METAR reports, not all ASOS observations.

        Args:
            station_code: ICAO station code
            start_date: Start date/time (UTC)
            end_date: End date/time (UTC)
        """
        params = {
            'station': station_code.upper(),
            'data': 'metar',
            'year1': start_date.year,
            'month1': start_date.month,
            'day1': start_date.day,
            'year2': end_date.year,
            'month2': end_date.month,
            'day2': end_date.day,
            'tz': 'UTC',
            'format': 'onlycomma',
            'latlon': 'no',
            'missing': 'null',
            'trace': 'null'
        }

        url = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()

            lines = response.text.strip().split('\n')
            all_observations = []

            for line in lines[1:]:  # Skip header
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 3:  # station, valid, metar, ...
                        station = parts[0]
                        timestamp = parts[1]
                        metar_text = parts[2] if len(parts) > 2 else ''
                        if metar_text and metar_text != 'null' and metar_text.strip():
                            all_observations.append((timestamp, metar_text))

            # Filter to return only actual METAR reports (typically hourly)
            metar_reports = self._filter_to_metar_reports_only(all_observations)
            return metar_reports

        except requests.RequestException as e:
            logger.error(f"Iowa Mesonet API error: {e}")
            return []

    def _filter_to_metar_reports_only(self, observations: list) -> list:
        """
        Filter observations to return only actual METAR reports, not all ASOS observations.
        METAR reports contain 'RMK AO2' and are issued hourly.

        Args:
            observations: List of (timestamp, observation_text) tuples

        Returns:
            List of (timestamp, metar_text) tuples containing only actual METAR reports
        """
        metar_reports = []

        for timestamp, observation in observations:
            # Check if this is an actual METAR report by looking for 'RMK AO2'
            if 'RMK AO2' in observation.upper():
                # Clean the METAR format
                cleaned_metar = self._clean_metar_format(observation)
                metar_reports.append((timestamp, cleaned_metar))

        # Return only the METAR reports with RMK AO2
        return metar_reports

    def _filter_hourly_metars(self, metars: list) -> list:
        """
        Filter to show only actual METAR reports (not all ASOS observations).
        METAR reports are typically hourly and have specific formatting.
        We want to show ~5 observations around the target time.
        """
        metar_reports = []

        for timestamp, metar in metars:
            # Check if this is a METAR report by looking for standard METAR formatting
            is_metar = False

            # Check for standard METAR indicators
            if ('RMK AO2' in metar or 'RMK SLP' in metar or
                ('AUTO' in metar and 'RMK' in metar) or
                metar.count('KT') >= 1):  # Wind information indicates METAR format
                is_metar = True

            # Also check for specific minute patterns that indicate METAR reports
            try:
                if 'T' in timestamp:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                else:
                    dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M')

                # METAR stations often report at consistent minutes (like :54, :55, etc.)
                if dt.minute >= 50:  # Last 10 minutes of hour often contain METAR reports
                    is_metar = True
            except (ValueError, TypeError):
                pass

            if is_metar:
                # Clean the METAR format
                cleaned_metar = self._clean_metar_format(metar)
                metar_reports.append((timestamp, cleaned_metar))

        # If we have too many, limit to ~5 most relevant observations
        if len(metar_reports) > 5:
            # Sort by timestamp and take the middle 5 to show observations around target time
            metar_reports.sort(key=lambda x: x[0])
            start_idx = max(0, len(metar_reports) // 2 - 2)
            metar_reports = metar_reports[start_idx:start_idx + 5]

        # If we don't have enough METAR reports, return what we have (at least some data)
        if len(metar_reports) == 0 and len(metars) > 0:
            # Fallback: return first 5 observations if no clear METAR reports found
            metar_reports = [(ts, self._clean_metar_format(m)) for ts, m in metars[:5]]

        return metar_reports

    def _clean_metar_format(self, metar: str) -> str:
        """
        Clean METAR format by removing non-standard station-specific remarks.
        """
        # Remove common non-standard endings that appear in Iowa Mesonet data
        metar = metar.replace(' MADISHF', '')
        metar = metar.replace(' MADIS', '')

        # If the METAR ends with a space, clean it up
        metar = metar.strip()

        return metar

    def get_metars_around_time(self, station_code: str, target_time: datetime, hours_window: int = 2) -> list:
        """
        Get METAR data around a specific time, with proper timezone handling.
        METAR data is naturally hourly, so we get +/- hours_window from target time.

        Args:
            station_code: ICAO station code
            target_time: Target time (in UTC)
            hours_window: Number of hours before/after to include (default: 2)

        Returns:
            List of (timestamp, metar) tuples for observations around the target time
        """
        start_time = target_time - timedelta(hours=hours_window)
        end_time = target_time + timedelta(hours=hours_window)

        all_metars = self.get_metar_range(station_code, start_time, end_time)

        # Sort by time difference from target
        metars_with_diff = []
        for timestamp, metar in all_metars:
            try:
                if 'T' in timestamp:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                else:
                    dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M')

                time_diff = abs((dt - target_time).total_seconds() / 3600)  # hours
                metars_with_diff.append((time_diff, timestamp, metar))
            except (ValueError, TypeError):
                # If parsing fails, put at end
                metars_with_diff.append((999, timestamp, metar))

        # Sort by time difference (closest first)
        metars_with_diff.sort(key=lambda x: x[0])

        # Return in chronological order
        return [(timestamp, metar) for _, timestamp, metar in sorted(metars_with_diff, key=lambda x: x[1])]

    def _get_from_aviation_weather(self, station_code: str, date: datetime = None) -> Optional[str]:
        """
        Get METAR from NOAA Aviation Weather Center (free, no API key required).
        Limited to recent data (last 24-48 hours).
        """
        if date and (datetime.now() - date) > timedelta(hours=24):
            # Aviation Weather only provides recent data
            return None

        url = f"https://aviationweather.gov/api/data/metar?ids={station_code}&format=json&taf=false&hours=24"

        try:
            response = self.session.get(url)
            response.raise_for_status()

            data = response.json()
            if data and len(data) > 0:
                # Return the most recent METAR
                return data[0].get('rawOb', '')

        except requests.RequestException as e:
            logger.error(f"Aviation Weather API error: {e}")

        return None

    def _get_from_checkwx(self, station_code: str, date: datetime = None) -> Optional[str]:
        """
        Get METAR from CheckWX API (commercial service).
        Requires API key and supports historic data.
        """
        if not self.api_key:
            logger.error("CheckWX API key required")
            return None

        if date:
            # Historic data
            date_str = date.strftime('%Y/%m/%d')
            url = f"https://api.checkwx.com/metar/{station_code}/decoded?date={date_str}"
        else:
            # Current data
            url = f"https://api.checkwx.com/metar/{station_code}/decoded"

        headers = {'X-API-Key': self.api_key}

        try:
            response = self.session.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            if data and 'data' in data and len(data['data']) > 0:
                return data['data'][0].get('raw_text', '')

        except requests.RequestException as e:
            logger.error(f"CheckWX API error: {e}")

        return None

    def _get_from_weatherapi(self, station_code: str, date: datetime = None) -> Optional[str]:
        """
        Get METAR from WeatherAPI (commercial service).
        Requires API key and supports historic data.
        """
        if not self.api_key:
            logger.error("WeatherAPI key required")
            return None

        # WeatherAPI uses IATA codes, need to convert ICAO to IATA
        iata_code = self._icao_to_iata(station_code)
        if not iata_code:
            return None

        if date:
            # Historic data
            date_str = date.strftime('%Y-%m-%d')
            url = f"http://api.weatherapi.com/v1/history.json?key={self.api_key}&q={iata_code}&dt={date_str}"
        else:
            # Current data
            url = f"http://api.weatherapi.com/v1/current.json?key={self.api_key}&q={iata_code}"

        try:
            response = self.session.get(url)
            response.raise_for_status()

            data = response.json()
            if data and 'current' in data:
                # WeatherAPI doesn't provide raw METAR, but we can construct a simplified version
                current = data['current']
                temp_c = current.get('temp_c', 0)
                wind_kph = current.get('wind_kph', 0)
                wind_dir = current.get('wind_dir', 'VRB')
                pressure_mb = current.get('pressure_mb', 1013)

                # Construct a simplified METAR-like string
                metar = f"METAR {station_code} {datetime.now().strftime('%d%H%M')}Z {wind_dir}{int(wind_kph * 0.539957):03d}KT {int(temp_c):02d}/{int(temp_c - 5):02d} Q{int(pressure_mb):04d}"
                return metar

        except requests.RequestException as e:
            logger.error(f"WeatherAPI error: {e}")

        return None

    def _icao_to_iata(self, icao_code: str) -> Optional[str]:
        """
        Convert ICAO airport code to IATA code.
        This is a simplified mapping - in production, you'd want a proper database.
        """
        # Common mappings (you'd want to expand this or use a proper API)
        mapping = {
            'KJFK': 'JFK',
            'KLAX': 'LAX',
            'KORD': 'ORD',
            'KATL': 'ATL',
            'KDEN': 'DEN',
            'KDFW': 'DFW',
            'KSFO': 'SFO',
            'KSEA': 'SEA',
            'KBOS': 'BOS',
            'KLAS': 'LAS',
        }
        return mapping.get(icao_code.upper())

    def find_nearest_station(self, lat: float, lon: float) -> Optional[str]:
        """
        Find the nearest weather station to given coordinates.
        This is a simplified implementation.
        """
        # In a real implementation, you'd use a proper geolocation service
        # For now, return a default or implement basic logic
        return None

    def clear_cache(self):
        """Clear the API response cache."""
        self.cache.clear()


class MetarWorker(QThread):
    """
    Worker thread for fetching METAR data asynchronously.
    """
    finished = pyqtSignal(str)  # Emits METAR string
    error = pyqtSignal(str)     # Emits error message

    def __init__(self, metar_service: MetarService, station_code: str, date: datetime = None):
        super().__init__()
        self.metar_service = metar_service
        self.station_code = station_code
        self.date = date

    def run(self):
        try:
            metar_data = self.metar_service.get_metar(self.station_code, self.date)
            if metar_data:
                self.finished.emit(metar_data)
            else:
                self.error.emit("No METAR data found")
        except Exception as e:
            self.error.emit(str(e))


# Import configuration
from app.logic.metar_config import metar_config

# Global instance for easy access (configured)
metar_service = MetarService(
    api_key=metar_config.get_api_key(),
    provider=metar_config.get_provider()
)


def get_metar_for_mission(site: str, date: datetime) -> Optional[str]:
    """
    Convenience function to get METAR data for a mission.
    Attempts to extract station code from site field.

    Args:
        site: Site/location string that may contain airport code
        date: Mission date

    Returns:
        METAR string or None
    """
    if not site:
        return None

    # Try to extract ICAO code from site string
    # Look for 4-letter uppercase codes (typical ICAO format)
    words = site.upper().split()
    for word in words:
        if len(word) == 4 and word.isalpha():
            return metar_service.get_metar(word, date)

    # If no ICAO code found, try common airport identifiers
    common_stations = ['KJFK', 'KLAX', 'KORD', 'KATL', 'KDEN']
    for station in common_stations:
        metar = metar_service.get_metar(station, date)
        if metar:
            return metar

    return None
