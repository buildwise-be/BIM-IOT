import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

MAPPING_PATH = os.getenv("DEVICE_MAPPING_PATH", "/app/data/devices.ifc.json")
MIDDLEWARE_URL = os.getenv("MIDDLEWARE_URL", "http://middleware:8000").rstrip("/")
CACHE_DIR = Path(os.getenv("PREDICTOR_CACHE_DIR", "/app/cache"))


def read_mapping() -> Dict[str, Any]:
    with open(MAPPING_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def get_predictor_config(mapping: Dict[str, Any]) -> Dict[str, Any]:
    return mapping.get("predictor", {}) if isinstance(mapping, dict) else {}


def allow_repo(repo: str, allowlist: List[str]) -> bool:
    repo = (repo or "").strip()
    return bool(repo) and repo in allowlist


def raw_github_url(repo: str, ref: str, path: str) -> str:
    repo = repo.rstrip("/")
    if repo.startswith("https://github.com/"):
        tail = repo.replace("https://github.com/", "", 1)
        return f"https://raw.githubusercontent.com/{tail}/{ref}/{path}"
    return ""


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def fetch_script(script: Dict[str, Any], allowlist: List[str], refresh: bool) -> Optional[Path]:
    repo = script.get("repo", "")
    ref = script.get("ref", "")
    path = script.get("path", "")
    expected_sha = str(script.get("sha256") or "").strip()

    if not allow_repo(repo, allowlist):
        return None
    if not ref or not path:
        return None

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{script.get('name','script')}_{ref}_{path.replace('/', '_')}"
    local_path = CACHE_DIR / safe_name

    if local_path.exists() and not refresh:
        return local_path

    url = raw_github_url(repo, ref, path)
    if not url:
        return None

    with httpx.Client(timeout=10) as client:
        response = client.get(url)
    if response.status_code != 200:
        return None

    content = response.content
    if expected_sha and expected_sha != "<sha256>":
        if sha256_hex(content) != expected_sha:
            return None

    local_path.write_bytes(content)
    return local_path


def fetch_device_telemetry(device_id: str, key: Optional[str], limit: int, hours: int) -> Dict[str, Any]:
    url = f"{MIDDLEWARE_URL}/devices/{device_id}/telemetry"
    params: Dict[str, Any] = {"limit": limit, "hours": hours}
    if key:
        params["key"] = key
    with httpx.Client(timeout=10) as client:
        response = client.get(url, params=params)
    if response.status_code != 200:
        return {}
    return response.json()


def post_predictions(items: List[Dict[str, Any]]) -> bool:
    if not items:
        return True
    url = f"{MIDDLEWARE_URL}/predictions/apply"
    payload = {"items": items}
    with httpx.Client(timeout=10) as client:
        response = client.post(url, json=payload)
    return response.status_code == 200


def run_script(script_path: Path, payload: Dict[str, Any], timeout_sec: int) -> Optional[Dict[str, Any]]:
    try:
        proc = subprocess.run(
            ["python", str(script_path)],
            input=json.dumps(payload).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout.decode("utf-8"))
    except Exception:
        return None


def normalize_output(
    output: Dict[str, Any],
    default_device: Optional[str],
    entity_type: str,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not output:
        return items
    if "items" in output and isinstance(output["items"], list):
        for item in output["items"]:
            if isinstance(item, dict):
                items.append(item)
        return items

    device_id = output.get("deviceId") or default_device
    if not device_id:
        return items
    item = {
        "deviceId": device_id,
        "entityType": output.get("entityType") or entity_type,
        "telemetry": output.get("telemetry") or {},
        "attributes": output.get("attributes") or {},
    }
    items.append(item)
    return items


def build_payload(
    device_id: str,
    device: Dict[str, Any],
    telemetry: Dict[str, Any],
    mapping: Dict[str, Any],
    script: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "deviceId": device_id,
        "device": device,
        "telemetry": telemetry,
        "mapping": {
            "model": mapping.get("model"),
            "backend": {"thingsboard": mapping.get("backend", {}).get("thingsboard", {})},
        },
        "context": {"script": script.get("name")},
    }


def run_cycle(mapping: Dict[str, Any]) -> None:
    predictor = get_predictor_config(mapping)
    if not predictor or not predictor.get("enabled", True):
        return

    schedule = predictor.get("schedule", {})
    max_run_sec = int(schedule.get("maxRunSec") or 60)
    refresh_sec = int((predictor.get("github", {}) or {}).get("refreshSec") or 600)
    allowlist = (predictor.get("github", {}) or {}).get("allowlist") or []
    scripts = predictor.get("scripts") or []
    global_device = (predictor.get("globalDevice") or {}).get("deviceId")

    now = int(time.time())
    refresh = (now % refresh_sec) < 2

    devices = mapping.get("devices", {}) if isinstance(mapping, dict) else {}
    items: List[Dict[str, Any]] = []

    for script in scripts:
        script_path = fetch_script(script, allowlist, refresh=refresh) if isinstance(script, dict) else None
        if not script_path:
            continue

        scope = str(script.get("scope") or "per-device")
        telemetry_cfg = script.get("telemetry") or {}
        key_override = telemetry_cfg.get("keys")
        limit = int(telemetry_cfg.get("limit") or 24)
        hours = int(telemetry_cfg.get("hours") or 24)

        if scope == "global":
            combined = {}
            for dev_id, dev in devices.items():
                t_key = key_override or (dev.get("connector", {}) or {}).get("telemetryKey") or dev.get("type")
                combined[dev_id] = fetch_device_telemetry(dev_id, t_key, limit, hours)
            payload = {
                "deviceId": global_device,
                "devices": devices,
                "telemetry": combined,
                "context": {"script": script.get("name"), "scope": "global"},
            }
            output = run_script(script_path, payload, max_run_sec)
            items.extend(normalize_output(output or {}, global_device, "DEVICE"))
            continue

        for dev_id, dev in devices.items():
            t_key = key_override or (dev.get("connector", {}) or {}).get("telemetryKey") or dev.get("type")
            telemetry = fetch_device_telemetry(dev_id, t_key, limit, hours)
            payload = build_payload(dev_id, dev, telemetry, mapping, script)
            output = run_script(script_path, payload, max_run_sec)
            items.extend(normalize_output(output or {}, dev_id, "DEVICE"))

    if items:
        post_predictions(items)


def main() -> None:
    while True:
        try:
            mapping = read_mapping()
            run_cycle(mapping)
        except Exception:
            pass

        mapping = read_mapping()
        predictor = get_predictor_config(mapping)
        schedule = predictor.get("schedule", {})
        interval = int(schedule.get("intervalSec") or 60)
        interval = max(1, interval)
        time.sleep(interval)


if __name__ == "__main__":
    main()
