"""
Raspberry Pi DHT22 sensor reader.

This script runs on the Raspberry Pi with a DHT22/AM2302 sensor connected.
It reads temperature and humidity every 5 minutes and publishes to MQTT.

Wiring (DHT22/AM2302 to Raspberry Pi):
    - VCC (pin 1) → Pi 3.3V (pin 1)
    - DATA (pin 2) → Pi GPIO4 (pin 7)
    - GND (pin 4)  → Pi GND (pin 6)

Install dependencies on the Pi:
    pip install adafruit-circuitpython-dht paho-mqtt

Usage:
    python sensor.py --host 192.168.1.XX    # replace with your Mac's local IP
"""

import argparse
import json
import time
from datetime import datetime

import adafruit_dht
import board
import paho.mqtt.client as mqtt


def main():
    parser = argparse.ArgumentParser(description="DHT22 sensor reader for Raspberry Pi")
    parser.add_argument("--host", required=True, help="MQTT broker IP (your Mac's local IP)")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--room", default="living_room", help="Room name tag")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between readings")
    parser.add_argument("--gpio", default="D4", help="GPIO pin (default: D4)")
    args = parser.parse_args()

    # Initialize the DHT22 sensor on the specified GPIO pin
    pin = getattr(board, args.gpio)
    sensor = adafruit_dht.DHT22(pin)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(args.host, args.port)
    client.loop_start()

    print(f"Sensor running on GPIO {args.gpio}, room: {args.room}")
    print(f"Publishing to {args.host}:{args.port} every {args.interval}s")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            try:
                temperature = sensor.temperature
                humidity = sensor.humidity

                if temperature is not None and humidity is not None:
                    payload = {
                        "temperature": round(temperature, 1),
                        "humidity": round(humidity, 1),
                        "room": args.room,
                    }
                    client.publish("apartment/sensors", json.dumps(payload))
                    now = datetime.now().strftime("%H:%M:%S")
                    print(f"[{now}] Published: {temperature:.1f}C, {humidity:.1f}% humidity")
                else:
                    print("Sensor returned None, skipping...")

            except RuntimeError as e:
                # DHT22 sensors occasionally fail reads — this is normal
                print(f"Sensor read error (will retry): {e}")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nSensor stopped.")
        sensor.exit()
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
