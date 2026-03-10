"""
Fake DHT22 sensor simulator.

Generates realistic temperature and humidity readings that follow
a daily pattern (cooler at night, warmer during the day) with small
random fluctuations, simulating what a real apartment sensor would produce.

Usage:
    python fake_sensor.py                     # publishes every 30 seconds
    python fake_sensor.py --interval 300      # publishes every 5 minutes (real pace)
    python fake_sensor.py --host 192.168.1.10 # connect to a specific MQTT broker
"""

import argparse
import json
import math
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt


def simulate_reading(hour: float) -> dict:
    """Generate a realistic indoor reading based on the time of day."""
    # Base temperature follows a sine curve: ~19C at night, ~23C in afternoon
    base_temp = 21.0 + 2.0 * math.sin((hour - 6) * math.pi / 12)
    temperature = base_temp + random.gauss(0, 0.3)

    # Humidity inversely correlated with temperature
    base_humidity = 50.0 - 5.0 * math.sin((hour - 6) * math.pi / 12)
    humidity = base_humidity + random.gauss(0, 1.5)
    humidity = max(20.0, min(90.0, humidity))

    return {
        "temperature": round(temperature, 1),
        "humidity": round(humidity, 1),
        "room": "living_room",
    }


def main():
    parser = argparse.ArgumentParser(description="Fake DHT22 sensor simulator")
    parser.add_argument("--host", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--interval", type=int, default=30,
                        help="Seconds between readings (default: 30 for testing)")
    args = parser.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(args.host, args.port)
    client.loop_start()

    print(f"Simulator running. Publishing to {args.host}:{args.port} every {args.interval}s")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            now = datetime.now()
            hour = now.hour + now.minute / 60.0
            reading = simulate_reading(hour)

            client.publish("apartment/sensors", json.dumps(reading))
            print(f"[{now.strftime('%H:%M:%S')}] Published: "
                  f"{reading['temperature']}C, {reading['humidity']}% humidity")

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
