# BIM-IOT

## General Intro
BIM-IOT is a BIM visualization platform connected to IoT data.  
The front-end loads an IFC model, enables picking and highlighting, and displays telemetry from Thingsboard devices.

## General Design
- Frontend (Vite + TypeScript)
  - Loads an IFC and builds a GUID -> expressID mapping.
  - Loads device mapping from the middleware (`/devices.ifc.json`).
  - Displays telemetry with a chart (Chart.js).
- Dashboard (Dash + Plotly + Bootstrap, service dédié)
  - Refreshes the device mapping on demand.
  - Displays telemetry charts and embeds the Vite 3D viewer.
  - Uses Dash Bootstrap Components for layout and styling.
- Middleware (FastAPI)
  - Exposes a simple API for the front: `/devices` and `/devices/{id}/telemetry`.
  - Queries Thingsboard via REST (JWT or ApiKey).
  - Serves the IFC model and device mapping stored in a separate volume.
- Thingsboard
  - Stores devices and telemetry.
  - Receives data from the local simulator.

## Architecture Graph
```text
                +----------------------+
                |   IFC Model (.ifc)   |
                |  (volume mounted)    |
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
         |           | /devices.ifc.json    |
         |           | /model/{file}        |
         |           +----------+-----------+
         |                      |
         |                      v
         |           +----------+-----------+
         |           | devices.ifc.json     |
         |           | + model selection    |
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
- Dash dashboard: `http://localhost:8050`
- Thingsboard: `http://localhost:7000`

If the middleware runs on a different host/port, set `VITE_MIDDLEWARE_URL` when building the frontend.

### 2. Configure the mapping and model
Place the mapping + IFC model in `data/` (mounted into the middleware as `/app/data`):
- `data/devices.ifc.json`
- `data/<your-model>.ifc`

The middleware serves (after calling `POST /refresh_mapping`):
- `http://localhost:8000/devices.ifc.json`
- `http://localhost:8000/model/<file>`

#### Structure of `devices.ifc.json`
Top-level fields:
- `model.file`: IFC filename to load (must exist in `data/`).
- `backend.middlewareUrl`: Middleware base URL used by the frontend.
- `backend.thingsboard`: `baseUrl` + credentials (`apiKey` or `username`/`password`).
- `devices`: Map of device id -> metadata.

Device fields:
- `type`: Logical type (e.g. temperature, humidity).
- `ifcGuids`: IFC element GUIDs to highlight.
- `connector.type`: `thingsboard` or `mock`.
- `connector.deviceId`: Thingsboard device UUID (required for `thingsboard`).
- `connector.entityType`: `DEVICE` or `ASSET` (default `DEVICE`).
- `connector.accessToken`: Access token (used by the simulator).
- `connector.telemetryKey`: Telemetry key to query.

Example:
```json
{
  "model": { "file": "model.ifc" },
  "backend": {
    "middlewareUrl": "http://localhost:8000",
    "thingsboard": { "baseUrl": "http://thingsboard:8080", "apiKey": "REPLACE" }
  },
  "devices": {
    "DEV_1": {
      "type": "temperature",
      "ifcGuids": ["3TazwRY9P9VBCwM4_ANS28"],
      "connector": {
        "type": "thingsboard",
        "deviceId": "f34a1140-0113-11f1-873e-85f6dc6f3a3d",
        "entityType": "DEVICE",
        "accessToken": "REPLACE_WITH_ACCESS_TOKEN",
        "telemetryKey": "temperature"
      }
    }
  }
}
```

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
- If you get 422 Unprocessable Entity on telemetry: ensure limit is within 1-1000.

