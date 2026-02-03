import base64
import json
import os
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

DEVICE_MAPPING_PATH = os.getenv("DEVICE_MAPPING_PATH", "frontend/src/data/devices.ifc.json")
TB_BASE_URL = os.getenv("TB_BASE_URL", "").rstrip("/")
TB_API_KEY = os.getenv("TB_API_KEY")
TB_USERNAME = os.getenv("TB_USERNAME")
TB_PASSWORD = os.getenv("TB_PASSWORD")


app = FastAPI(title="BIM-IOT Middleware")

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_mapping() -> Dict[str, Any]:
    if not os.path.exists(DEVICE_MAPPING_PATH):
        raise HTTPException(status_code=500, detail=f"Mapping not found: {DEVICE_MAPPING_PATH}")
    with open(DEVICE_MAPPING_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def get_device(mapping: Dict[str, Any], device_id: str) -> Dict[str, Any]:
    devices = mapping.get("devices", {})
    device = devices.get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Unknown device: {device_id}")
    return device


def parse_jwt_exp(token: str) -> int:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8")
        data = json.loads(decoded)
        return int(data.get("exp", 0))
    except Exception:
        return 0


class ThingsBoardClient:
    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._token_exp: int = 0

    async def _get_auth_header(self) -> Dict[str, str]:
        if TB_API_KEY:
            return {"X-Authorization": f"ApiKey {TB_API_KEY}"}

        if not TB_USERNAME or not TB_PASSWORD:
            raise HTTPException(
                status_code=500,
                detail="Missing ThingsBoard credentials. Set TB_API_KEY or TB_USERNAME/TB_PASSWORD.",
            )

        now = int(time.time())
        if self._token and self._token_exp - now > 60:
            return {"X-Authorization": f"Bearer {self._token}"}

        login_url = f"{TB_BASE_URL}/api/auth/login"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                login_url, json={"username": TB_USERNAME, "password": TB_PASSWORD}
            )
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="ThingsBoard login failed.")
        data = response.json()
        token = data.get("token")
        if not token:
            raise HTTPException(status_code=502, detail="ThingsBoard login missing token.")
        self._token = token
        self._token_exp = parse_jwt_exp(token)
        return {"X-Authorization": f"Bearer {token}"}

    async def fetch_timeseries(
        self,
        device_id: str,
        key: str,
        limit: int,
        hours: int,
    ) -> List[Dict[str, Any]]:
        if not TB_BASE_URL:
            raise HTTPException(status_code=500, detail="Missing TB_BASE_URL.")

        end_ts = int(time.time() * 1000)
        start_ts = end_ts - (hours * 60 * 60 * 1000)
        interval_ms = max(1, int((end_ts - start_ts) / max(limit, 1)))

        params = {
            "keys": key,
            "startTs": start_ts,
            "endTs": end_ts,
            "interval": interval_ms,
            "limit": limit,
            "agg": "AVG",
        }

        url = f"{TB_BASE_URL}/api/plugins/telemetry/DEVICE/{device_id}/values/timeseries"
        headers = await self._get_auth_header()

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code == 401 and not TB_API_KEY:
                self._token = None
                headers = await self._get_auth_header()
                response = await client.get(url, params=params, headers=headers)

        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="ThingsBoard telemetry fetch failed.")

        payload = response.json()
        raw_points = payload.get(key, [])
        points = []
        for item in raw_points:
            ts = item.get("ts")
            value = item.get("value")
            try:
                value = float(value)
            except (TypeError, ValueError):
                pass
            points.append({"ts": ts, "value": value})
        points.sort(key=lambda item: item["ts"])
        return points


tb_client = ThingsBoardClient()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/devices")
def list_devices() -> Dict[str, Any]:
    mapping = load_mapping()
    devices = []
    for device_id, data in mapping.get("devices", {}).items():
        devices.append(
            {
                "id": device_id,
                "type": data.get("type"),
                "connector": data.get("connector", {}),
            }
        )
    return {"devices": devices}


@app.get("/devices/{device_id}/telemetry")
async def device_telemetry(
    device_id: str,
    key: Optional[str] = Query(default=None),
    limit: int = Query(default=24, ge=1, le=200),
    hours: int = Query(default=24, ge=1, le=168),
) -> Dict[str, Any]:
    mapping = load_mapping()
    device = get_device(mapping, device_id)

    connector = device.get("connector", {})
    connector_type = connector.get("type")

    telemetry_key = key or connector.get("telemetryKey") or device.get("type")
    if not telemetry_key:
        raise HTTPException(status_code=400, detail="Missing telemetry key.")

    if connector_type == "thingsboard":
        device_tb_id = connector.get("deviceId")
        if not device_tb_id:
            raise HTTPException(status_code=400, detail="Missing ThingsBoard deviceId in mapping.")
        points = await tb_client.fetch_timeseries(
            device_id=device_tb_id,
            key=telemetry_key,
            limit=limit,
            hours=hours,
        )
        return {"deviceId": device_id, "key": telemetry_key, "points": points}

    if connector_type == "mock":
        now = int(time.time() * 1000)
        points = []
        for i in range(limit):
            ts = now - (limit - 1 - i) * 60 * 60 * 1000
            value = i
            points.append({"ts": ts, "value": value})
        return {"deviceId": device_id, "key": telemetry_key, "points": points}

    raise HTTPException(status_code=400, detail=f"Unsupported connector type: {connector_type}")
