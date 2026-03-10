import json
import logging
import os
import time

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from weather import get_external_weather

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("consumer")

# InfluxDB setup
influx_client = InfluxDBClient(
    url=os.environ["INFLUXDB_URL"],
    token=os.environ["INFLUXDB_TOKEN"],
    org=os.environ["INFLUXDB_ORG"],
)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)
bucket = os.environ["INFLUXDB_BUCKET"]
org = os.environ["INFLUXDB_ORG"]


def on_connect(client, userdata, flags, reason_code, properties):
    logger.info("Connected to MQTT broker (reason: %s)", reason_code)
    client.subscribe("apartment/sensors")
    logger.info("Subscribed to apartment/sensors")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        room = payload.get("room", "unknown")
        temperature = payload["temperature"]
        humidity = payload["humidity"]

        logger.info(
            "Received from %s: %.1fC, %.1f%% humidity",
            room, temperature, humidity,
        )

        # Write indoor sensor data
        indoor_point = (
            Point("indoor_climate")
            .tag("room", room)
            .field("temperature", float(temperature))
            .field("humidity", float(humidity))
        )
        write_api.write(bucket=bucket, org=org, record=indoor_point)

        # Fetch and write external weather data
        weather = get_external_weather()
        if weather:
            outdoor_point = (
                Point("outdoor_climate")
                .tag("source", "open_meteo")
                .field("temperature", float(weather["external_temperature"]))
                .field("humidity", float(weather["external_humidity"]))
                .field("wind_speed", float(weather["external_wind_speed"]))
                .field("weather_code", int(weather["weather_code"]))
            )
            write_api.write(bucket=bucket, org=org, record=outdoor_point)

            # Write the temperature delta (indoor - outdoor)
            delta_point = (
                Point("climate_delta")
                .tag("room", room)
                .field("temperature_delta", float(temperature - weather["external_temperature"]))
                .field("humidity_delta", float(humidity - weather["external_humidity"]))
            )
            write_api.write(bucket=bucket, org=org, record=delta_point)

        logger.info("Written to InfluxDB successfully")

    except Exception:
        logger.exception("Error processing message")


def main():
    mqtt_host = os.environ.get("MQTT_HOST", "localhost")
    mqtt_port = int(os.environ.get("MQTT_PORT", "1883"))

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    logger.info("Connecting to MQTT broker at %s:%d", mqtt_host, mqtt_port)

    # Retry connection in case mosquitto isn't ready yet
    while True:
        try:
            client.connect(mqtt_host, mqtt_port)
            break
        except ConnectionRefusedError:
            logger.warning("MQTT broker not ready, retrying in 5 seconds...")
            time.sleep(5)

    logger.info("Pipeline running. Waiting for sensor messages...")
    client.loop_forever()


if __name__ == "__main__":
    main()
