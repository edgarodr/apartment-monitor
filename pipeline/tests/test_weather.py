import time
from unittest.mock import patch, MagicMock

from weather import get_external_weather, _weather_cache, CACHE_TTL_SECONDS


class TestGetExternalWeather:
	def setup_method(self):
		"""Reset cache before each test."""
		_weather_cache["data"] = None
		_weather_cache["timestamp"] = 0

	@patch("weather.requests.get")
	def test_returns_parsed_weather_data(self, mock_get):
		mock_response = MagicMock()
		mock_response.json.return_value = {
			"current": {
				"temperature_2m": 18.5,
				"relative_humidity_2m": 65,
				"wind_speed_10m": 12.3,
				"weather_code": 1,
			}
		}
		mock_response.raise_for_status = MagicMock()
		mock_get.return_value = mock_response

		result = get_external_weather()

		assert result["external_temperature"] == 18.5
		assert result["external_humidity"] == 65
		assert result["external_wind_speed"] == 12.3
		assert result["weather_code"] == 1

	@patch("weather.requests.get")
	def test_cache_returns_same_data_without_api_call(self, mock_get):
		mock_response = MagicMock()
		mock_response.json.return_value = {
			"current": {
				"temperature_2m": 20.0,
				"relative_humidity_2m": 50,
				"wind_speed_10m": 5.0,
				"weather_code": 0,
			}
		}
		mock_response.raise_for_status = MagicMock()
		mock_get.return_value = mock_response

		first_call = get_external_weather()
		second_call = get_external_weather()

		assert first_call == second_call
		assert mock_get.call_count == 1  # only one API call

	@patch("weather.requests.get")
	def test_cache_expires_after_ttl(self, mock_get):
		mock_response = MagicMock()
		mock_response.json.return_value = {
			"current": {
				"temperature_2m": 20.0,
				"relative_humidity_2m": 50,
				"wind_speed_10m": 5.0,
				"weather_code": 0,
			}
		}
		mock_response.raise_for_status = MagicMock()
		mock_get.return_value = mock_response

		get_external_weather()
		_weather_cache["timestamp"] = time.time() - CACHE_TTL_SECONDS - 1
		get_external_weather()

		assert mock_get.call_count == 2  # two API calls

	@patch("weather.requests.get")
	def test_returns_empty_dict_on_api_error(self, mock_get):
		mock_get.side_effect = Exception("Connection error")

		result = get_external_weather()

		assert result == {}
