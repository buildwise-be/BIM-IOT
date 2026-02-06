import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

DEVICE_MAPPING_PATH = os.getenv("DEVICE_MAPPING_PATH", "data/devices.ifc.json")
MAPPING_DIR = Path(os.getenv("MAPPING_DIR") or os.path.dirname(DEVICE_MAPPING_PATH)).resolve()
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


_mapping_cache: Optional[Dict[str, Any]] = None


def read_mapping_file() -> Dict[str, Any]:
    if not os.path.exists(DEVICE_MAPPING_PATH):
        raise HTTPException(status_code=500, detail=f"Mapping not found: {DEVICE_MAPPING_PATH}")
    with open(DEVICE_MAPPING_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_mapping_cached() -> Dict[str, Any]:
    if _mapping_cache is None:
        raise HTTPException(
            status_code=503,
            detail="Mapping not loaded. Call POST /refresh_mapping to load devices.ifc.json.",
        )
    return _mapping_cache


def refresh_mapping() -> Dict[str, Any]:
    global _mapping_cache
    _mapping_cache = read_mapping_file()
    return _mapping_cache


def resolve_model_path(filename: str) -> Path:
    if not filename:
        raise HTTPException(status_code=400, detail="Missing model filename.")
    safe_name = os.path.basename(filename)
    path = (MAPPING_DIR / safe_name).resolve()
    if MAPPING_DIR not in path.parents and path != MAPPING_DIR:
        raise HTTPException(status_code=400, detail="Invalid model filename.")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Model not found: {safe_name}")
    return path


def get_device(mapping: Dict[str, Any], device_id: str) -> Dict[str, Any]:
    devices = mapping.get("devices", {})
    device = devices.get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Unknown device: {device_id}")
    return device


def get_tb_settings(mapping: Dict[str, Any]) -> Dict[str, str]:
    tb = mapping.get("backend", {}).get("thingsboard", {}) if isinstance(mapping, dict) else {}
    return {
        "baseUrl": str(tb.get("baseUrl") or "").rstrip("/"),
        "apiKey": str(tb.get("apiKey") or ""),
        "username": str(tb.get("username") or ""),
        "password": str(tb.get("password") or ""),
    }


def parse_jwt_exp(token: str) -> int:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8")
        data = json.loads(decoded)
        return int(data.get("exp", 0))
    except Exception:
        return 0


def parse_interval_ms(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.isdigit():
        return int(value)
    normalized = str(value).strip().lower()
    mapping = {
        "minute": 60_000,
        "hour": 3_600_000,
        "day": 86_400_000,
        "week": 7 * 86_400_000,
        "month": 30 * 86_400_000,
        "year": 365 * 86_400_000,
    }
    if normalized in mapping:
        return mapping[normalized]
    raise HTTPException(
        status_code=400,
        detail="Invalid interval. Use minute, hour, day, week, month, year, or a numeric value in ms.",
    )


class ThingsBoardClient:
    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._token_exp: int = 0

    async def _get_auth_header(self, mapping: Dict[str, Any]) -> Dict[str, str]:
        settings = get_tb_settings(mapping)
        api_key = TB_API_KEY or settings.get("apiKey")
        username = TB_USERNAME or settings.get("username")
        password = TB_PASSWORD or settings.get("password")

        if api_key:
            return {"X-Authorization": f"ApiKey {api_key}"}

        if not username or not password:
            raise HTTPException(
                status_code=500,
                detail="Missing ThingsBoard credentials. Set TB_API_KEY or TB_USERNAME/TB_PASSWORD.",
            )

        now = int(time.time())
        if self._token and self._token_exp - now > 60:
            return {"X-Authorization": f"Bearer {self._token}"}

        base_url = TB_BASE_URL or settings.get("baseUrl")
        if not base_url:
            raise HTTPException(status_code=500, detail="Missing TB_BASE_URL.")

        login_url = f"{base_url}/api/auth/login"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                login_url, json={"username": username, "password": password}
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
        keys: str,
        limit: int,
        hours: int,
        mapping: Dict[str, Any],
        entity_type: str = "DEVICE",
        agg: str = "NONE",
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        interval: Optional[int] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        settings = get_tb_settings(mapping)
        base_url = TB_BASE_URL or settings.get("baseUrl")
        if not base_url:
            raise HTTPException(status_code=500, detail="Missing TB_BASE_URL.")

        if end_ts is None:
            end_ts = int(time.time() * 1000)
        if start_ts is None:
            start_ts = end_ts - (hours * 60 * 60 * 1000)
        params = {
            "keys": keys,
            "startTs": start_ts,
            "endTs": end_ts,
            "limit": limit,
            "agg": agg or "NONE",
        }
        if interval:
            params["interval"] = interval

        url = f"{base_url}/api/plugins/telemetry/{entity_type}/{device_id}/values/timeseries"
        headers = await self._get_auth_header(mapping)

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code == 401 and not (TB_API_KEY or settings.get("apiKey")):
                self._token = None
                headers = await self._get_auth_header(mapping)
                response = await client.get(url, params=params, headers=headers)

        if response.status_code != 200:
            detail = "ThingsBoard telemetry fetch failed."
            try:
                payload = response.json()
                message = payload.get("message") or payload.get("error") or payload.get("detail")
                if message:
                    detail = f"ThingsBoard error: {message}"
            except Exception:
                text = response.text.strip()
                if text:
                    detail = f"ThingsBoard error: {text}"
            raise HTTPException(status_code=502, detail=detail)

        payload = response.json()
        series: Dict[str, List[Dict[str, Any]]] = {}
        for key, raw_points in payload.items():
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
            series[key] = points
        return series

    async def fetch_alarm_page(
        self,
        mapping: Dict[str, Any],
        entity_type: str,
        entity_id: str,
        search_status: Optional[str],
        page_size: int = 1,
        page: int = 0,
    ) -> Dict[str, Any]:
        settings = get_tb_settings(mapping)
        base_url = TB_BASE_URL or settings.get("baseUrl")
        if not base_url:
            raise HTTPException(status_code=500, detail="Missing TB_BASE_URL.")

        url = f"{base_url}/api/alarm/{entity_type}/{entity_id}"
        params: Dict[str, Any] = {
            "pageSize": page_size,
            "page": page,
            "sortProperty": "createdTime",
            "sortOrder": "DESC",
        }
        if search_status:
            params["searchStatus"] = str(search_status).upper()

        headers = await self._get_auth_header(mapping)
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code == 401 and not (TB_API_KEY or settings.get("apiKey")):
                self._token = None
                headers = await self._get_auth_header(mapping)
                response = await client.get(url, params=params, headers=headers)

        if response.status_code != 200:
            detail = "ThingsBoard alarm fetch failed."
            try:
                payload = response.json()
                message = payload.get("message") or payload.get("error") or payload.get("detail")
                if message:
                    detail = f"ThingsBoard error: {message}"
            except Exception:
                text = response.text.strip()
                if text:
                    detail = f"ThingsBoard error: {text}"
            raise HTTPException(status_code=502, detail=detail)

        return response.json()

    async def action_alarm(
        self,
        mapping: Dict[str, Any],
        alarm_id: str,
        action: str,
    ) -> Dict[str, Any]:
        settings = get_tb_settings(mapping)
        base_url = TB_BASE_URL or settings.get("baseUrl")
        if not base_url:
            raise HTTPException(status_code=500, detail="Missing TB_BASE_URL.")

        action = action.lower().strip()
        if action not in {"ack", "clear"}:
            raise HTTPException(status_code=400, detail="Invalid alarm action.")

        url = f"{base_url}/api/alarm/{alarm_id}/{action}"
        headers = await self._get_auth_header(mapping)
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, headers=headers)
            if response.status_code == 401 and not (TB_API_KEY or settings.get("apiKey")):
                self._token = None
                headers = await self._get_auth_header(mapping)
                response = await client.post(url, headers=headers)

            if response.status_code in {404, 405} and action == "clear":
                alt_url = f"{base_url}/api/alarm/{alarm_id}/clear"
                response = await client.post(alt_url, headers=headers)

        if response.status_code not in {200, 202, 204}:
            detail = "ThingsBoard alarm action failed."
            try:
                payload = response.json()
                message = payload.get("message") or payload.get("error") or payload.get("detail")
                if message:
                    detail = f"ThingsBoard error: {message}"
            except Exception:
                text = response.text.strip()
                if text:
                    detail = f"ThingsBoard error: {text}"
            if "already cleared" in detail.lower():
                return {"status": "ok"}
            detail = f"{detail} (status={response.status_code})"
            raise HTTPException(status_code=502, detail=detail)

        if response.status_code == 204:
            return {"status": "ok"}
        return response.json()


tb_client = ThingsBoardClient()


async def build_telemetry(
    mapping: Dict[str, Any],
    device_id: str,
    key: Optional[str],
    limit: int,
    hours: int,
    agg: Optional[str] = None,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    interval: Optional[int] = None,
) -> Dict[str, Any]:
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
        entity_type = (connector.get("entityType") or "DEVICE").upper()
        if entity_type not in {"DEVICE", "ASSET"}:
            raise HTTPException(
                status_code=400,
                detail="Invalid entityType in mapping. Use DEVICE or ASSET.",
            )
        
        series = await tb_client.fetch_timeseries(
            device_id=device_tb_id,
            keys=telemetry_key,
            limit=limit,
            hours=hours,
            mapping=mapping,
            entity_type=entity_type,
            agg=(agg or "NONE"),
            start_ts=start_ts,
            end_ts=end_ts,
            interval=interval,
        )
        if "," in telemetry_key:
            return {"deviceId": device_id, "series": series}
        only_key = telemetry_key.split(",")[0].strip()
        points = series.get(only_key, [])
        return {"deviceId": device_id, "key": only_key, "points": points}

    if connector_type == "mock":
        now = int(time.time() * 1000)
        keys = [k.strip() for k in telemetry_key.split(",") if k.strip()]
        if not keys:
            keys = ["value"]
        series: Dict[str, List[Dict[str, Any]]] = {}
        for key_name in keys:
            points = []
            for i in range(limit):
                ts = now - (limit - 1 - i) * 60 * 60 * 1000
                value = i
                points.append({"ts": ts, "value": value})
            series[key_name] = points
        if len(keys) > 1:
            return {"deviceId": device_id, "series": series}
        return {"deviceId": device_id, "key": keys[0], "points": series[keys[0]]}

    raise HTTPException(status_code=400, detail=f"Unsupported connector type: {connector_type}")


async def publish_telemetry(
    mapping: Dict[str, Any],
    device_id: str,
    entity_type: str,
    telemetry: Dict[str, Any],
) -> None:
    settings = get_tb_settings(mapping)
    base_url = TB_BASE_URL or settings.get("baseUrl")
    if not base_url:
        raise HTTPException(status_code=500, detail="Missing TB_BASE_URL.")
    url = f"{base_url}/api/plugins/telemetry/{entity_type}/{device_id}/timeseries"
    headers = await tb_client._get_auth_header(mapping)
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, json=telemetry, headers=headers)
    if response.status_code not in {200, 202, 204}:
        raise HTTPException(status_code=502, detail="ThingsBoard telemetry publish failed.")


async def publish_attributes(
    mapping: Dict[str, Any],
    device_id: str,
    entity_type: str,
    attributes: Dict[str, Any],
    scope: str = "SERVER_SCOPE",
) -> None:
    settings = get_tb_settings(mapping)
    base_url = TB_BASE_URL or settings.get("baseUrl")
    if not base_url:
        raise HTTPException(status_code=500, detail="Missing TB_BASE_URL.")
    scope = (scope or "SERVER_SCOPE").upper()
    url = f"{base_url}/api/plugins/telemetry/{entity_type}/{device_id}/attributes/{scope}"
    headers = await tb_client._get_auth_header(mapping)
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, json=attributes, headers=headers)
    if response.status_code not in {200, 202, 204}:
        raise HTTPException(status_code=502, detail="ThingsBoard attributes publish failed.")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/thingsboard/health")
async def thingsboard_health() -> Dict[str, Any]:
    mapping = load_mapping_cached()
    settings = get_tb_settings(mapping)
    base_url = TB_BASE_URL or settings.get("baseUrl")
    if not base_url:
        return {"status": "error", "connected": False, "detail": "Missing ThingsBoard baseUrl."}
    try:
        headers = await tb_client._get_auth_header(mapping)
    except HTTPException as exc:
        return {"status": "error", "connected": False, "detail": exc.detail}
    except Exception as exc:
        return {"status": "error", "connected": False, "detail": str(exc)}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{base_url}/api/system/info", headers=headers)
        if response.status_code == 200:
            return {"status": "ok", "connected": True}
        return {
            "status": "error",
            "connected": False,
            "detail": f"ThingsBoard response: {response.status_code}",
        }
    except Exception as exc:
        return {"status": "error", "connected": False, "detail": str(exc)}


@app.get("/alarms/summary")
async def alarms_summary(
    status: Optional[str] = Query(default="ACTIVE"),
    page_size: int = Query(default=1, ge=1, le=100),
) -> Dict[str, Any]:
    mapping = load_mapping_cached()
    devices = mapping.get("devices", {}) if isinstance(mapping, dict) else {}
    total = 0
    failed = 0
    originators = 0

    for _, data in devices.items():
        connector = data.get("connector", {}) if isinstance(data, dict) else {}
        if connector.get("type") != "thingsboard":
            continue
        device_tb_id = connector.get("deviceId")
        if not device_tb_id:
            continue
        entity_type = (connector.get("entityType") or "DEVICE").upper()
        if entity_type not in {"DEVICE", "ASSET"}:
            continue
        originators += 1
        try:
            page = await tb_client.fetch_alarm_page(
                mapping=mapping,
                entity_type=entity_type,
                entity_id=device_tb_id,
                search_status=status,
                page_size=page_size,
                page=0,
            )
            total += int(page.get("totalElements") or 0)
        except Exception:
            failed += 1

    return {
        "status": "ok",
        "total": total,
        "originators": originators,
        "failed": failed,
    }


@app.get("/alarms/recent")
async def alarms_recent(
    status: Optional[str] = Query(default="ACTIVE"),
    limit: int = Query(default=8, ge=1, le=50),
    per_device: int = Query(default=5, ge=1, le=50),
) -> Dict[str, Any]:
    mapping = load_mapping_cached()
    devices = mapping.get("devices", {}) if isinstance(mapping, dict) else {}
    alarms: List[Dict[str, Any]] = []
    total = 0
    failed = 0
    originators = 0

    for device_id, data in devices.items():
        connector = data.get("connector", {}) if isinstance(data, dict) else {}
        if connector.get("type") != "thingsboard":
            continue
        device_tb_id = connector.get("deviceId")
        if not device_tb_id:
            continue
        entity_type = (connector.get("entityType") or "DEVICE").upper()
        if entity_type not in {"DEVICE", "ASSET"}:
            continue
        originators += 1
        try:
            page = await tb_client.fetch_alarm_page(
                mapping=mapping,
                entity_type=entity_type,
                entity_id=device_tb_id,
                search_status=status,
                page_size=per_device,
                page=0,
            )
            total += int(page.get("totalElements") or 0)
            for alarm in page.get("data", []) or []:
                alarm_id = alarm.get("id")
                if isinstance(alarm_id, dict):
                    alarm_id = alarm_id.get("id")
                alarms.append(
                    {
                        "id": alarm_id,
                        "type": alarm.get("type"),
                        "severity": alarm.get("severity"),
                        "status": alarm.get("status"),
                        "createdTime": alarm.get("createdTime"),
                        "acknowledged": alarm.get("acknowledged"),
                        "cleared": alarm.get("cleared"),
                        "originator": {
                            "deviceId": device_id,
                            "tbId": device_tb_id,
                            "entityType": entity_type,
                        },
                    }
                )
        except Exception:
            failed += 1

    alarms.sort(key=lambda item: item.get("createdTime") or 0, reverse=True)
    alarms = alarms[:limit]

    return {
        "status": "ok",
        "alarms": alarms,
        "total": total,
        "originators": originators,
        "failed": failed,
        "timestamp": int(time.time() * 1000),
    }


@app.post("/alarms/{alarm_id}/{action}")
async def alarm_action(alarm_id: str, action: str) -> Dict[str, Any]:
    mapping = load_mapping_cached()
    result = await tb_client.action_alarm(mapping, alarm_id, action)
    return {"status": "ok", "result": result}


@app.post("/predictions/apply")
async def predictions_apply(payload: Dict[str, Any]) -> Dict[str, Any]:
    mapping = load_mapping_cached()
    items = payload.get("items") or []
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="Invalid items payload.")
    published = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        device_id = item.get("deviceId")
        entity_type = (item.get("entityType") or "DEVICE").upper()
        telemetry = item.get("telemetry") or {}
        attributes = item.get("attributes") or {}
        if not device_id or entity_type not in {"DEVICE", "ASSET"}:
            continue
        if telemetry:
            await publish_telemetry(mapping, device_id, entity_type, telemetry)
        if attributes:
            await publish_attributes(mapping, device_id, entity_type, attributes)
        published += 1
    return {"status": "ok", "published": published}


@app.get("/devices")
def list_devices() -> Dict[str, Any]:
    mapping = load_mapping_cached()
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


@app.get("/devices.ifc.json")
def get_mapping() -> Dict[str, Any]:
    return load_mapping_cached()


@app.post("/refresh_mapping")
def refresh_mapping_endpoint() -> Dict[str, Any]:
    mapping = refresh_mapping()
    return {
        "status": "ok",
        "path": DEVICE_MAPPING_PATH,
        "deviceCount": len(mapping.get("devices", {})),
    }


@app.get("/model/{filename}")
def get_model(filename: str) -> FileResponse:
    path = resolve_model_path(filename)
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)


@app.get("/devices/{device_id}/telemetry")
async def device_telemetry(
    device_id: str,
    key: Optional[str] = Query(default=None, description="Single key or comma-separated keys"),
    limit: int = Query(default=24, ge=1, le=1000),
    hours: int = Query(default=24, ge=1, le=168),
    agg: Optional[str] = Query(default=None),
    start_ts: Optional[int] = Query(default=None, alias="startTs"),
    end_ts: Optional[int] = Query(default=None, alias="endTs"),
    interval: Optional[str] = Query(
        default=None, description="Aggregation interval (minute/hour/day/week/month/year or ms)"
    ),
) -> Dict[str, Any]:
    mapping = load_mapping_cached()
    interval_ms = parse_interval_ms(interval)
    return await build_telemetry(mapping, device_id, key, limit, hours, agg, start_ts, end_ts, interval_ms)


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
