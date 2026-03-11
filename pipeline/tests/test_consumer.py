import json

from influxdb_client import Point


def build_indoor_point(room, temperature, humidity):
    """Reproduce the point-building logic from consumer.py."""
    return (
        Point("indoor_climate")
        .tag("room", room)
        .field("temperature", float(temperature))
        .field("humidity", float(humidity))
    )


def parse_message(payload_bytes):
    """Parse an MQTT message payload."""
    payload = json.loads(payload_bytes.decode())
    return {
        "room": payload.get("room", "unknown"),
        "temperature": payload["temperature"],
        "humidity": payload["humidity"],
    }


class TestParseMessage:
    def test_parses_valid_payload(self):
        payload = json.dumps({
            "room": "bedroom",
            "temperature": 22.5,
            "humidity": 55.0,
        }).encode()

        result = parse_message(payload)

        assert result["room"] == "bedroom"
        assert result["temperature"] == 22.5
        assert result["humidity"] == 55.0

    def test_defaults_room_to_unknown(self):
        payload = json.dumps({
            "temperature": 20.0,
            "humidity": 50.0,
        }).encode()

        result = parse_message(payload)

        assert result["room"] == "unknown"


class TestBuildIndoorPoint:
    def test_creates_point_with_correct_measurement(self):
        point = build_indoor_point("living_room", 21.0, 45.0)
        line = point.to_line_protocol()

        assert line.startswith("indoor_climate,")
        assert "room=living_room" in line
        assert "temperature=21" in line
        assert "humidity=45" in line
