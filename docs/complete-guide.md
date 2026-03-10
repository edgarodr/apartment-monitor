# Apartment Climate Monitor — Complete Technical Guide

## Table of Contents

1. Architecture Overview
2. Docker Compose — The Orchestrator
3. Mosquitto — MQTT Broker
4. The Pipeline — Consumer & Weather
5. The Simulator — Testing Without Hardware
6. Raspberry Pi — Real Sensor
7. InfluxDB — Time-Series Database
8. Grafana — Dashboards & Provisioning
9. Flux Query Language
10. Key Concepts Reference
11. Study Plan & Career Resources

---

## 1. Architecture Overview

### What We Built

A real-time apartment monitoring system that collects temperature and humidity data from sensors, enriches it with external weather data, stores it in a time-series database, and visualizes it on dashboards.

### System Diagram

```
Sensor (Pi or Simulator)
   |
   | publishes JSON messages
   |
   v
MOSQUITTO (MQTT Broker)          <-- message router
   |
   | forwards messages to subscribers
   |
   v
PIPELINE (Python consumer)       <-- your code, the brain
   |
   | enriches with weather data, then writes
   |
   v
INFLUXDB (Time-series database)  <-- storage
   |
   | queried by
   |
   v
GRAFANA (Visualization)          <-- dashboards
```

### Why These Pieces?

**Why not write directly to the database from the sensor?** Because MQTT decouples the sensor from the processing. The sensor's only job is "publish a reading." It doesn't need to know about InfluxDB, weather APIs, or data enrichment. If the pipeline crashes, the sensor keeps publishing. If you add a second sensor in the bedroom, the pipeline picks it up automatically with no code changes. This pattern is called **publish/subscribe (pub/sub)** and it's the standard for IoT systems.

### Project Structure

```
apartment-monitor/
|-- docker-compose.yaml              <-- defines all 4 services
|-- config/
|   +-- mosquitto.conf               <-- MQTT broker config
|-- pipeline/
|   |-- Dockerfile                   <-- container for the Python consumer
|   |-- requirements.txt             <-- paho-mqtt, influxdb-client, requests
|   |-- consumer.py                  <-- subscribes to MQTT, enriches, writes to InfluxDB
|   +-- weather.py                   <-- fetches Paris weather from Open-Meteo
|-- simulator/
|   |-- requirements.txt             <-- paho-mqtt
|   +-- fake_sensor.py               <-- fakes DHT22 readings for development
|-- raspberry_pi/
|   +-- sensor.py                    <-- real sensor script for the Pi
|-- grafana/
|   +-- provisioning/
|       |-- datasources/
|       |   +-- influxdb.yaml        <-- auto-connects Grafana to InfluxDB
|       +-- dashboards/
|           |-- dashboards.yaml      <-- dashboard provisioning config
|           +-- apartment.json       <-- the dashboard definition
+-- .gitignore
```

---

## 2. Docker Compose — The Orchestrator

### What It Is

Docker Compose is a tool for defining and running multi-container applications. Instead of starting each container manually with long `docker run` commands, you define everything in a YAML file and run `docker compose up`.

### The File: `docker-compose.yaml`

```yaml
services:
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: mosquitto
    ports:
      - "1883:1883"
    volumes:
      - ./config/mosquitto.conf:/mosquitto/config/mosquitto.conf
      - mosquitto_data:/mosquitto/data
    restart: unless-stopped
```

**`image: eclipse-mosquitto:2`** — tells Docker to download and run the official Mosquitto image from Docker Hub. You didn't build this — someone else packaged Mosquitto into an image and published it. `:2` means version 2.

**`ports: "1883:1883"`** — maps port 1883 inside the container to port 1883 on your Mac. Without this, the container would be isolated — nothing outside Docker could reach it. The simulator runs on your Mac (not in Docker), so it needs this port mapping. Format: `"host_port:container_port"`.

**`volumes:`** — two different kinds:

- **Bind mount** (`./config/mosquitto.conf:/mosquitto/config/mosquitto.conf`) — takes a file from your Mac and makes it appear inside the container at the specified path. This is how you inject your custom config.
- **Named volume** (`mosquitto_data:/mosquitto/data`) — Docker-managed persistent storage. Survives container deletion and recreation.

**`restart: unless-stopped`** — if the container crashes, Docker automatically restarts it.

```yaml
  influxdb:
    image: influxdb:2
    container_name: influxdb
    ports:
      - "8086:8086"
    environment:
      DOCKER_INFLUXDB_INIT_MODE: setup
      DOCKER_INFLUXDB_INIT_USERNAME: admin
      DOCKER_INFLUXDB_INIT_PASSWORD: adminpassword
      DOCKER_INFLUXDB_INIT_ORG: apartment
      DOCKER_INFLUXDB_INIT_BUCKET: sensors
      DOCKER_INFLUXDB_INIT_ADMIN_TOKEN: my-super-secret-token
    volumes:
      - influxdb_data:/var/lib/influxdb2
    restart: unless-stopped
```

**`environment:`** — sets environment variables inside the container. InfluxDB reads these on first startup to automatically create:

- An admin user (`admin`/`adminpassword`)
- An organization (`apartment`) — InfluxDB groups everything under organizations
- A bucket (`sensors`) — where data lives (like a database table)
- An API token (`my-super-secret-token`) — any application that wants to read/write data must present this token

```yaml
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
    depends_on:
      - influxdb
    restart: unless-stopped
```

**`depends_on: influxdb`** — tells Docker to start InfluxDB before Grafana. Grafana needs InfluxDB to be running so it can connect to it.

The provisioning volume maps your local `grafana/provisioning/` folder into the container. Grafana reads anything in there on startup and automatically configures datasources and dashboards.

```yaml
  pipeline:
    build: ./pipeline
    container_name: pipeline
    depends_on:
      - mosquitto
      - influxdb
    environment:
      MQTT_HOST: mosquitto
      MQTT_PORT: "1883"
      INFLUXDB_URL: http://influxdb:8086
      INFLUXDB_TOKEN: my-super-secret-token
      INFLUXDB_ORG: apartment
      INFLUXDB_BUCKET: sensors
      OPEN_METEO_LATITUDE: "48.8566"
      OPEN_METEO_LONGITUDE: "2.3522"
    restart: unless-stopped
```

**`build: ./pipeline`** — unlike the other services that use pre-built images, this one builds a custom image from the Dockerfile in `./pipeline/`. This is your own code.

**`MQTT_HOST: mosquitto`** — inside Docker Compose, containers refer to each other by service name. Docker creates an internal network where `mosquitto` resolves to the Mosquitto container's IP, `influxdb` resolves to InfluxDB's IP, etc. This is Docker's built-in DNS.

```yaml
volumes:
  mosquitto_data:
  influxdb_data:
  grafana_data:
```

**Named volumes declaration** — tells Docker to create these persistent storage volumes. Data survives container restarts and recreations.

### Key Docker Compose Commands

```bash
docker compose up -d          # start all services in background
docker compose down           # stop and remove all containers
docker compose restart grafana  # restart a specific service
docker compose logs pipeline   # view logs for a specific service
docker compose ps             # see status of all containers
docker compose up --build -d  # rebuild images and restart
```

---

## 3. Mosquitto — MQTT Broker

### What Is MQTT?

MQTT (Message Queuing Telemetry Transport) is a lightweight messaging protocol designed for IoT devices. It uses a **publish/subscribe** pattern:

- **Publishers** send messages to a **topic** (like a channel name)
- **Subscribers** listen to topics and receive messages
- The **broker** (Mosquitto) sits in the middle and routes messages

```
Publisher (sensor)           Broker (Mosquitto)          Subscriber (pipeline)
     |                            |                            |
     |--- publish to              |                            |
     |    "apartment/sensors" --->|                            |
     |                            |--- forward to          -->|
     |                            |    all subscribers         |
```

### The Config: `mosquitto.conf`

```
listener 1883
```
Listen for connections on port 1883 (the standard MQTT port).

```
allow_anonymous true
```
Let anyone connect without a username/password. Fine for local development. In production you'd require authentication.

```
persistence true
persistence_location /mosquitto/data/
```
Save messages to disk so they survive a broker restart.

```
log_dest stdout
```
Send logs to the console (visible via `docker logs mosquitto`).

### Why MQTT Instead of HTTP?

| Feature | MQTT | HTTP |
|---|---|---|
| Connection | Persistent (always connected) | One request at a time |
| Overhead | ~2 bytes header | ~700 bytes headers |
| Pattern | Pub/sub (many-to-many) | Request/response (one-to-one) |
| Best for | IoT sensors, real-time data | Web pages, REST APIs |

MQTT is ideal for sensors that send small messages frequently over potentially unreliable networks.

---

## 4. The Pipeline — Consumer & Weather

### `pipeline/Dockerfile`

```dockerfile
FROM python:3.10-slim
```
Start from the official Python 3.10 image (slim variant = smaller). This is the "base layer" — Python and pip are already installed.

```dockerfile
WORKDIR /app
```
Set the working directory inside the container. All subsequent commands run from `/app`.

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```
Copy requirements and install dependencies. Done before copying code because of **Docker layer caching**: if you change Python code but not dependencies, Docker skips `pip install` on rebuild.

```dockerfile
COPY . .
```
Copy all pipeline code into the container.

```dockerfile
CMD ["python", "-u", "consumer.py"]
```
The command that runs when the container starts. `-u` means unbuffered output — without this, logs might not appear in real time.

### `pipeline/requirements.txt`

```
paho-mqtt==2.1.0           # MQTT client library
influxdb-client==1.46.0    # InfluxDB Python client
requests==2.32.3           # HTTP requests (for Open-Meteo API)
```

### `pipeline/consumer.py` — The Brain

#### Imports and Setup (lines 1-26)

```python
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
```

Two main libraries: `paho-mqtt` to subscribe to MQTT messages, `influxdb_client` to write data to InfluxDB.

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
```

Configures Python's logging system. Every `logger.info(...)` call produces output like:
`2026-03-04 15:44:20 [consumer] INFO: Written to InfluxDB successfully`

```python
influx_client = InfluxDBClient(
    url=os.environ["INFLUXDB_URL"],
    token=os.environ["INFLUXDB_TOKEN"],
    org=os.environ["INFLUXDB_ORG"],
)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)
```

Creates the database connection. `os.environ["INFLUXDB_URL"]` reads the environment variable set in `docker-compose.yaml`. If the variable doesn't exist, this crashes immediately — that's intentional (**fail-fast**: better to crash with a clear error than run with a wrong connection).

`SYNCHRONOUS` means "wait for InfluxDB to confirm each write before continuing."

#### on_connect Callback (lines 29-32)

```python
def on_connect(client, userdata, flags, reason_code, properties):
    client.subscribe("apartment/sensors")
```

MQTT works with **callbacks** — functions that the library calls when something happens. This one is called when the client connects to the broker. It immediately subscribes to the `apartment/sensors` topic.

#### on_message Callback (lines 35-81)

This function runs every time a sensor message arrives.

```python
payload = json.loads(msg.payload.decode())
```

The MQTT message arrives as raw bytes. `.decode()` converts bytes to string, `json.loads()` parses JSON into a Python dictionary.

```python
indoor_point = (
    Point("indoor_climate")
    .tag("room", room)
    .field("temperature", float(temperature))
    .field("humidity", float(humidity))
)
write_api.write(bucket=bucket, org=org, record=indoor_point)
```

InfluxDB stores data as **points**. Each point has:

- **Measurement** (`"indoor_climate"`) — like a table name
- **Tags** (`.tag("room", room)`) — indexed metadata for filtering. Low cardinality values (few unique values like room names)
- **Fields** (`.field("temperature", ...)`) — the actual numeric values you graph and aggregate
- **Timestamp** — automatically set to "now" if not provided

```python
weather = get_external_weather()
if weather:
    outdoor_point = (
        Point("outdoor_climate")
        .tag("source", "open_meteo")
        .field("temperature", float(weather["external_temperature"]))
        ...
    )
    delta_point = (
        Point("climate_delta")
        .tag("room", room)
        .field("temperature_delta", float(temperature - weather["external_temperature"]))
        ...
    )
```

Every sensor reading produces **3 writes to InfluxDB**: indoor data, outdoor data, and the computed delta.

#### main() — Startup (lines 84-108)

```python
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
```

Creates the MQTT client and registers callbacks. This is the **observer pattern**: "call this function when X happens."

```python
while True:
    try:
        client.connect(mqtt_host, mqtt_port)
        break
    except ConnectionRefusedError:
        time.sleep(5)
```

**Retry loop.** When Docker starts all containers simultaneously, the pipeline might start before Mosquitto is ready. This keeps trying every 5 seconds.

```python
client.loop_forever()
```

The **event loop**. Blocks forever, listening for incoming MQTT messages. Every time a message arrives, it calls `on_message`.

### `pipeline/weather.py` — External Weather

```python
_weather_cache = {"data": None, "timestamp": 0}
CACHE_TTL_SECONDS = 1800
```

**Caching.** Paris weather doesn't change every few seconds. Calling the API on every sensor reading would be wasteful. We cache for 30 minutes.

```python
def get_external_weather() -> dict:
    now = time.time()
    if _weather_cache["data"] and (now - _weather_cache["timestamp"]) < CACHE_TTL_SECONDS:
        return _weather_cache["data"]
```

If cached data is less than 30 minutes old, return it immediately. No API call.

```python
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
    )
```

**Open-Meteo REST API.** HTTP GET request with parameters in the URL. Returns JSON. `48.8566, 2.3522` are Paris coordinates. `temperature_2m` means temperature at 2 meters above ground.

```python
    response = requests.get(url, timeout=10)
    response.raise_for_status()
```

`timeout=10` — give up if no response in 10 seconds. `raise_for_status()` — raise exception on HTTP errors.

```python
    except Exception:
        logger.exception("Failed to fetch external weather")
        return {}
```

**Graceful degradation.** If the API is down, log the error but don't crash. The pipeline keeps working with indoor data only.

---

## 5. The Simulator — Testing Without Hardware

### `simulator/fake_sensor.py`

```python
def simulate_reading(hour: float) -> dict:
    base_temp = 21.0 + 2.0 * math.sin((hour - 6) * math.pi / 12)
    temperature = base_temp + random.gauss(0, 0.3)
```

**Realistic simulation.** Uses a sine wave to mimic daily temperature variation:

- `21.0` — average temperature
- `+ 2.0 * math.sin(...)` — oscillates +/-2 degrees
- `(hour - 6)` — minimum around 6 AM, maximum around 6 PM
- `random.gauss(0, 0.3)` — small random noise (standard deviation 0.3C)

Humidity is inversely correlated with temperature (when warmer, indoor humidity tends to drop).

```python
    client.loop_start()
```

Runs the MQTT event loop in a **background thread**. Different from `loop_forever()` in the consumer. Here the main thread generates readings while the background thread handles MQTT communication.

The simulator publishes to the exact same topic (`apartment/sensors`) with the exact same JSON format as the real sensor. The consumer can't tell the difference.

### How to Run

```bash
cd ~/Desktop/apartment-monitor/simulator
python3 fake_sensor.py                     # every 30 seconds (testing)
python3 fake_sensor.py --interval 300      # every 5 minutes (realistic)
python3 fake_sensor.py --host 192.168.1.10 # specific MQTT broker
```

---

## 6. Raspberry Pi — Real Sensor

### Hardware: DHT22 / AM2302

These are the **same sensor** in different packaging. AM2302 is the wired version in a plastic case.

| Spec | Value |
|---|---|
| Temperature range | -40 to 80C |
| Temperature accuracy | +/-0.5C |
| Humidity range | 0-100% |
| Humidity accuracy | +/-2-5% |
| Sampling rate | Max once every 2 seconds |

### Wiring

```
DHT22 Pin    -->    Raspberry Pi Pin
---------          ----------------
VCC (pin 1)   -->   3.3V (pin 1)
DATA (pin 2)  -->   GPIO4 (pin 7)
GND (pin 4)   -->   GND (pin 6)
```

### `raspberry_pi/sensor.py`

```python
pin = getattr(board, args.gpio)
sensor = adafruit_dht.DHT22(pin)
```

Creates a hardware connection to the DHT22 on GPIO pin D4.

```python
temperature = sensor.temperature
humidity = sensor.humidity
```

Reads actual values from the physical sensor.

```python
except RuntimeError as e:
    print(f"Sensor read error (will retry): {e}")
```

DHT22 sensors occasionally return read errors — timing issues with the protocol. Completely normal. The loop retries on the next interval.

### How to Run on the Pi

```bash
pip install adafruit-circuitpython-dht paho-mqtt
python3 sensor.py --host YOUR_MACS_IP --room living_room
python3 sensor.py --host YOUR_MACS_IP --room bedroom --gpio D17  # second sensor
```

---

## 7. InfluxDB — Time-Series Database

### What Is a Time-Series Database?

A database optimized for data indexed by time. Unlike a regular SQL database where you query by ID or name, time-series databases are built for queries like "give me all temperature readings from the last 6 hours, averaged per 10 minutes."

### Data Model

InfluxDB organizes data as:

```
Organization  -->  apartment
  Bucket      -->  sensors
    Measurement  -->  indoor_climate, outdoor_climate, climate_delta
      Tags       -->  room="living_room", source="open_meteo"
      Fields     -->  temperature=21.3, humidity=47.4
      Timestamp  -->  2026-03-04T15:44:20Z
```

**Tags vs Fields:**

| | Tags | Fields |
|---|---|---|
| Indexed | Yes (fast filtering) | No |
| Use for | Metadata (room, source) | Values (temperature, humidity) |
| Cardinality | Low (few unique values) | High (many unique values) |
| Example | room="living_room" | temperature=21.3 |

### Accessing the UI

- URL: http://localhost:8086
- Login: `admin` / `adminpassword`
- Data Explorer: click the graph icon in the sidebar

### Useful Flux Queries

All indoor readings from the last hour:
```
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "indoor_climate")
```

Indoor vs outdoor temperature:
```
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._field == "temperature")
  |> filter(fn: (r) => r._measurement == "indoor_climate"
                     or r._measurement == "outdoor_climate")
```

Temperature delta:
```
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "climate_delta")
  |> filter(fn: (r) => r._field == "temperature_delta")
```

Average temperature per hour over the last day:
```
from(bucket: "sensors")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "indoor_climate")
  |> filter(fn: (r) => r._field == "temperature")
  |> aggregateWindow(every: 1h, fn: mean)
```

---

## 8. Grafana — Dashboards & Provisioning

### What Is Grafana?

An open-source visualization platform. It connects to data sources (InfluxDB, Prometheus, PostgreSQL, etc.) and lets you build dashboards with charts, gauges, tables, and alerts.

- URL: http://localhost:3000
- Login: `admin` / `admin`

### Auto-Provisioning

Instead of manually configuring Grafana through the UI, we use **provisioning files** that Grafana reads on startup.

#### `grafana/provisioning/datasources/influxdb.yaml`

```yaml
datasources:
  - name: InfluxDB
    type: influxdb
    access: proxy
    url: http://influxdb:8086
    jsonData:
      version: Flux
      organization: apartment
      defaultBucket: sensors
    secureJsonData:
      token: my-super-secret-token
    isDefault: true
```

- `access: proxy` — Grafana's backend makes requests to InfluxDB (server-side), not your browser
- `version: Flux` — use the Flux query language
- `secureJsonData` — Grafana encrypts this token at rest

#### `grafana/provisioning/dashboards/dashboards.yaml`

```yaml
providers:
  - name: Default
    folder: Apartment
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
```

Tells Grafana: "load JSON dashboard files from this directory."

### Dashboard Structure

The dashboard (`apartment.json`) has 10 panels in 3 rows:

**Row 1 — Stat Panels (current values):**
Six panels showing the latest value for indoor temp, indoor humidity, outdoor temp, outdoor humidity, temperature delta, and wind speed. Color-coded by thresholds:

```
Temperature thresholds:
  < 18C  = blue (cold)
  18-24C = green (comfortable)
  24-28C = orange (warm)
  > 28C  = red (hot)

Humidity thresholds:
  < 30%  = orange (too dry)
  30-60% = green (comfortable)
  60-70% = orange (humid)
  > 70%  = red (too humid)
```

**Row 2 — Time Series Charts:**
- Indoor vs Outdoor Temperature (orange and blue lines)
- Indoor vs Outdoor Humidity (green and purple lines)

**Row 3 — Analysis Charts:**
- Temperature Delta over time (color gradient showing how much warmer inside is)
- Wind Speed over time

### Dashboard Auto-Refresh

```json
"refresh": "10s"
```

The dashboard queries InfluxDB every 10 seconds for new data.

---

## 9. Flux Query Language

Flux is InfluxDB's query language. It uses a pipe-forward pattern where data flows through transformations:

```
from(bucket: "sensors")                                    // 1. Start: read from bucket
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop) // 2. Filter: time range
  |> filter(fn: (r) => r._field == "temperature")          // 3. Filter: only temperature
  |> filter(fn: (r) => r._measurement == "indoor_climate") // 4. Filter: only indoor
  |> aggregateWindow(every: v.windowPeriod, fn: mean)      // 5. Aggregate: average per window
  |> yield(name: "result")                                  // 6. Output: return results
```

### Key Flux Functions

| Function | What It Does | Example |
|---|---|---|
| `from()` | Select the data bucket | `from(bucket: "sensors")` |
| `range()` | Filter by time | `range(start: -1h)` |
| `filter()` | Filter rows | `filter(fn: (r) => r._field == "temperature")` |
| `last()` | Get the most recent value | Used in stat panels |
| `mean()` | Calculate average | Used inside aggregateWindow |
| `aggregateWindow()` | Group by time intervals | `aggregateWindow(every: 1h, fn: mean)` |
| `yield()` | Name the output | `yield(name: "result")` |

### Grafana Variables in Flux

- `v.timeRangeStart` / `v.timeRangeStop` — the time range selected in the Grafana time picker
- `v.windowPeriod` — auto-calculated aggregation window (adapts to zoom level)

---

## 10. Key Concepts Reference

### Concepts Practiced in This Project

| Concept | Where Used | What It Means |
|---|---|---|
| Docker containers | All 4 services | Isolated environments with bundled dependencies |
| Docker Compose | `docker-compose.yaml` | Multi-container orchestration |
| Dockerfiles | `pipeline/Dockerfile` | Instructions to build a custom container image |
| Volumes | InfluxDB, Grafana, Mosquitto | Persistent storage that survives container restarts |
| Bind mounts | Mosquitto config, Grafana provisioning | Map host files into containers |
| Environment variables | All services | Configure apps without hardcoding values |
| MQTT pub/sub | Sensor to pipeline | Decoupled messaging pattern for IoT |
| Callbacks / Observer pattern | `on_connect`, `on_message` | "Call my function when X happens" |
| REST APIs | Open-Meteo weather | HTTP request/response for data fetching |
| Caching | `weather.py` | Avoid redundant API calls |
| Graceful degradation | Weather fetch failure | Keep working with partial data |
| Time-series databases | InfluxDB | Databases optimized for timestamped data |
| Measurements, tags, fields | InfluxDB data model | How time-series data is structured |
| Flux query language | InfluxDB and Grafana | Pipe-based data query and transformation |
| Dashboard as code | `apartment.json` | Dashboards defined in files, not manual clicks |
| Auto-provisioning | Grafana datasources and dashboards | Auto-configure on startup from files |
| Retry logic | Pipeline MQTT connection | Handle services starting at different times |
| Fail-fast | InfluxDB connection (os.environ) | Crash early with clear errors |
| Structured logging | Pipeline consumer | Timestamped, labeled log output |
| Layer caching | Dockerfile order | Speed up Docker rebuilds |
| DNS in Docker | Service names as hostnames | Containers find each other by name |

### Design Patterns Used

| Pattern | Where | Why |
|---|---|---|
| Publish/Subscribe | MQTT sensor to pipeline | Decouple data producers from consumers |
| Observer | MQTT callbacks | React to events without polling |
| Cache-Aside | Weather API caching | Reduce external API load |
| Graceful Degradation | Weather fetch failure handling | Keep core functionality working |
| Fail-Fast | Missing env vars crash immediately | Clear errors over silent failures |
| Infrastructure as Code | Docker Compose, Grafana provisioning | Reproducible setup from files |

---

## 11. Study Plan & Career Resources

### Learning Path (6 Phases)

| Phase | Topic | Weeks | Key Outcome |
|---|---|---|---|
| 1 | Docker | 1-3 | Build and run containers |
| 2 | Kubernetes | 4-8 | Understand production scheduling |
| 3 | Helm + GitLab CI/CD | 9-12 | Full deployment pipelines |
| 4 | AWS (+ Cloud Practitioner cert) | 13-17 | First certification |
| 5 | CKA certification | 18-28 | Deep K8s expertise |
| 6 | Specialization | Ongoing | MLOps, monitoring, ArgoCD |

### Free Resources

| Resource | URL |
|---|---|
| Docker Getting Started | https://docs.docker.com/get-started/ |
| Kubernetes Basics | https://kubernetes.io/docs/tutorials/kubernetes-basics/ |
| Helm Chart Templates | https://helm.sh/docs/chart_template_guide/ |
| GitLab CI/CD Quick Start | https://docs.gitlab.com/ci/quick_start/ |
| Pro Git Book | https://git-scm.com/book/en/v2 |
| Prometheus First Steps | https://prometheus.io/docs/introduction/first_steps/ |
| Grafana Tutorials | https://grafana.com/tutorials/ |
| ArgoCD Getting Started | https://argo-cd.readthedocs.io/en/stable/getting_started/ |
| MLOps Zoomcamp | https://github.com/DataTalksClub/mlops-zoomcamp |
| Data Engineering Zoomcamp | https://courses.datatalks.club/de-zoomcamp-2026/ |
| TechWorld with Nana (YouTube) | https://www.youtube.com/@TechWorldwithNana |
| freeCodeCamp Docker+K8s | https://www.freecodecamp.org/news/course-on-docker-and-kubernetes/ |

### Certifications

| Certification | Cost | Priority |
|---|---|---|
| AWS Cloud Practitioner | $100 | High |
| CKA (Kubernetes Administrator) | $445 | High |
| AWS Solutions Architect Associate | $150 | Medium |
| GitLab CI/CD Associate | $150 | Low |

### Salary Ranges in Paris (Gross Annual)

| Role | Junior (0-2 yrs) | Mid (2-5 yrs) | Senior (5-8+ yrs) |
|---|---|---|---|
| Data Scientist | 41-48K | 48-68K | 68-80K+ |
| Data Engineer | 42-48K | 48-62K | 62-72K+ |
| MLOps Engineer | 45-52K | 52-65K | 65-80K+ |
| ML Engineer | 45-55K | 55-70K | 70-85K+ |

---

## Quick Reference: Common Commands

### Docker

```bash
docker compose up -d               # start all services
docker compose down                # stop all services
docker compose restart <service>   # restart one service
docker compose logs <service>      # view service logs
docker compose ps                  # check service status
docker compose up --build -d       # rebuild and restart
```

### Simulator

```bash
cd ~/Desktop/apartment-monitor/simulator
python3 fake_sensor.py               # test mode (every 30s)
python3 fake_sensor.py --interval 300 # realistic mode (every 5min)
```

### Raspberry Pi Sensor

```bash
python3 sensor.py --host YOUR_MACS_IP --room living_room
python3 sensor.py --host YOUR_MACS_IP --room bedroom --gpio D17
```

### InfluxDB CLI (from inside container)

```bash
docker exec influxdb influx query '
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "indoor_climate")
  |> last()
' --org apartment --token my-super-secret-token
```

### Web UIs

| Service | URL | Login |
|---|---|---|
| Grafana | http://localhost:3000 | admin / admin |
| InfluxDB | http://localhost:8086 | admin / adminpassword |
| Grafana Dashboard | http://localhost:3000/d/apartment-climate | (same as Grafana) |
