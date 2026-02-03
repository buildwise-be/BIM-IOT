# BIM-IOT

## General Intro
BIM-IOT is a BIM visualization platform connected to IoT data.  
The front-end loads an IFC model, enables picking and highlighting, and displays telemetry from Thingsboard devices.

## General Design
- Frontend (Vite + TypeScript)
  - Loads an IFC and builds a GUID -> expressID mapping.
  - Links BIM objects to IoT devices via `frontend/src/data/devices.ifc.json`.
  - Displays telemetry with a chart (Chart.js).
- Middleware (FastAPI)
  - Exposes a simple API for the front: `/devices` and `/devices/{id}/telemetry`.
  - Queries Thingsboard via REST (JWT or ApiKey).
  - Reads configuration and mappings from `frontend/src/data/devices.ifc.json`.
- Thingsboard
  - Stores devices and telemetry.
  - Receives data from the local simulator.

## Architecture Graph
```text
                +----------------------+
                |   IFC Model (.ifc)   |
                +----------+-----------+
                           |
                           v
+------------------+   +---+---------------------+
|  Thingsboard     |<--| Frontend (Vite + TS)    |
|  (Telemetry DB)  |   |  Viewer + UI + Charts   |
+--------+---------+   +---+---------------------+
         ^                 |
         |                 v
         |           +-----+----------------+
         |           | Middleware (FastAPI) |
         |           | /devices, /telemetry |
         |           +----------+-----------+
         |                      |
         |                      v
         |           +----------+-----------+
         |           | devices.ifc.json     |
         |           | mapping + TB creds   |
         |           +----------------------+
         |
         +---- Simulator (local Python) ----+
```

## Getting Started
### 1. Start the Docker stack
```bash
docker compose up -d --build
```

Exposed services:
- Frontend: `http://localhost:8081`
- Middleware: `http://localhost:8000`
- Thingsboard: `http://localhost:7000`

### 2. Configure the mapping
Edit `frontend/src/data/devices.ifc.json`:
- `backend.middlewareUrl`: Middleware URL.
- `backend.thingsboard`: `baseUrl` + credentials (apiKey or username/password).
- Each device must have `deviceId`, `accessToken`, `telemetryKey`, `entityType` (DEVICE/ASSET).

### 3. Start the Thingsboard simulator (local)
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r tools/thingsboard-simulator/requirements.txt
python tools/thingsboard-simulator/run_simulator.py --base-url http://localhost:7000 --interval 5
```

### 4. Use the application
- Open `http://localhost:8081`
- Select a device: the IFC element is highlighted and telemetry is shown.

## Quick Troubleshooting
- If the front does not load telemetry: verify `deviceId` is a valid Thingsboard UUID.
- If only one point appears: middleware must use `agg=NONE` (already applied).
- If Thingsboard is not accessible: check `docker compose ps` and `http://localhost:7000`.
