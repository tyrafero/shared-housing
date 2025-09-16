import requests
import time
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class GeocodingService:
    """Free geocoding service using Nominatim (OpenStreetMap)"""

    BASE_URL = "https://nominatim.openstreetmap.org/search"

    @classmethod
    def geocode_address(cls, address, suburb, state, country="Australia"):
        """
        Geocode an address and return latitude, longitude

        Args:
            address: Street address
            suburb: Suburb/city
            state: State/province
            country: Country (default: Australia)

        Returns:
            tuple: (latitude, longitude) as Decimal objects, or (None, None) if failed
        """
        try:
            # Build full address string
            full_address = f"{address}, {suburb}, {state}, {country}"

            # Parameters for Nominatim API
            params = {
                'format': 'json',
                'q': full_address,
                'limit': 1,
                'countrycodes': 'au' if country.lower() == 'australia' else None,
            }

            # Make request with proper headers (Nominatim requires User-Agent)
            headers = {
                'User-Agent': 'SharedHousing-Platform/1.0 (property geocoding)'
            }

            logger.info(f"Geocoding address: {full_address}")
            response = requests.get(cls.BASE_URL, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data and len(data) > 0:
                result = data[0]
                lat = Decimal(str(result['lat']))
                lon = Decimal(str(result['lon']))

                logger.info(f"Successfully geocoded {full_address} -> ({lat}, {lon})")
                return lat, lon
            else:
                logger.warning(f"No results found for address: {full_address}")
                return None, None

        except requests.RequestException as e:
            logger.error(f"Network error during geocoding: {e}")
            return None, None
        except (ValueError, KeyError, TypeError) as e:
            logger.error(f"Error parsing geocoding response: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Unexpected error during geocoding: {e}")
            return None, None

    @classmethod
    def geocode_with_retry(cls, address, suburb, state, country="Australia", max_retries=2):
        """
        Geocode with retry logic and rate limiting

        Args:
            address, suburb, state, country: Address components
            max_retries: Maximum number of retry attempts

        Returns:
            tuple: (latitude, longitude) or (None, None)
        """
        for attempt in range(max_retries + 1):
            if attempt > 0:
                # Rate limiting: wait before retry
                time.sleep(1)
                logger.info(f"Retrying geocoding attempt {attempt + 1}")

            lat, lon = cls.geocode_address(address, suburb, state, country)

            if lat is not None and lon is not None:
                return lat, lon

        logger.error(f"Failed to geocode after {max_retries + 1} attempts: {address}, {suburb}, {state}")
        return None, None