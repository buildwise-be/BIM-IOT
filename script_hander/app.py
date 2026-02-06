import hashlib
import json
import os
import subprocess
import threading
import uuid
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

MAPPING_PATH = os.getenv("DEVICE_MAPPING_PATH", "/app/data/devices.ifc.json")
MIDDLEWARE_URL = os.getenv("MIDDLEWARE_URL", "http://middleware:8000").rstrip("/")
CACHE_DIR = Path(os.getenv("PREDICTOR_CACHE_DIR", "/app/cache"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEALTH_PORT = int(os.getenv("SCRIPT_HANDLER_PORT", "8100"))
MODE = os.getenv("SCRIPT_HANDLER_MODE", "server").strip().lower()

START_TS = int(time.time() * 1000)
STATUS: Dict[str, Any] = {
    "status": "starting",
    "enabled": None,
    "last_cycle_ts": None,
    "last_success_ts": None,
    "last_items": None,
    "last_duration_ms": None,
    "last_error": None,
    "last_error_ts": None,
    "running_job_id": None,
}
RUN_LOCK = threading.Lock()
JOBS_LOCK = threading.Lock()
JOBS: Dict[str, Dict[str, Any]] = {}
CANCEL_EVENT = threading.Event()
RUN_PROC: Optional[subprocess.Popen[bytes]] = None
CURRENT_JOB_ID: Optional[str] = None


def create_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "status": "queued",
        "created_ts": now_ms(),
        "started_ts": None,
        "finished_ts": None,
        "result": None,
        "payload": payload,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    return job


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with JOBS_LOCK:
        return JOBS.get(job_id)


def update_job(job_id: str, **kwargs: Any) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job.update(kwargs)


def request_kill(job_id: Optional[str] = None) -> Dict[str, Any]:
    CANCEL_EVENT.set()
    if job_id:
        update_job(job_id, status="canceled", finished_ts=now_ms(), result={"status": "canceled"})
    if RUN_PROC and RUN_PROC.poll() is None:
        try:
            RUN_PROC.terminate()
        except Exception:
            pass
        return {"status": "killing"}
    CANCEL_EVENT.clear()
    return {"status": "idle"}


def now_ms() -> int:
    return int(time.time() * 1000)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            payload = {"status": "ok", "uptime_ms": now_ms() - START_TS}
            self._send_json(200, payload)
            return
        if self.path == "/status":
            payload = {**STATUS, "uptime_ms": now_ms() - START_TS, "mode": MODE}
            self._send_json(200, payload)
            return
        if self.path.startswith("/jobs/"):
            job_id = self.path.split("/jobs/", 1)[-1].strip("/")
            job = get_job(job_id)
            if not job:
                self._send_json(404, {"status": "not_found"})
                return
            self._send_json(200, job)
            return
        self._send_json(404, {"status": "not_found"})

    def do_POST(self) -> None:
        if self.path == "/run":
            payload = self._read_json() or {}
            scripts = payload.get("scripts")
            device_ids = payload.get("deviceIds")
            result = execute_cycle(scripts=scripts, device_ids=device_ids)
            if result.get("status") == "busy":
                self._send_json(409, result)
                return
            self._send_json(200, result)
            return
        if self.path == "/run_async":
            payload = self._read_json() or {}
            job = create_job(payload)
            thread = threading.Thread(target=run_job, args=(job["id"],), daemon=True)
            thread.start()
            self._send_json(202, {"status": "queued", "jobId": job["id"]})
            return
        if self.path == "/kill":
            payload = self._read_json() or {}
            job_id = payload.get("jobId")
            result = request_kill(job_id if isinstance(job_id, str) else None)
            self._send_json(200, result)
            return
        if self.path == "/reload":
            try:
                _ = read_mapping()
                self._send_json(200, {"status": "ok"})
            except Exception as exc:
                self._send_json(500, {"status": "error", "detail": str(exc)})
            return
        self._send_json(404, {"status": "not_found"})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json(self) -> Optional[Dict[str, Any]]:
        length = self.headers.get("Content-Length")
        if not length:
            return None
        try:
            data = self.rfile.read(int(length))
            if not data:
                return None
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None

    def _send_json(self, code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_api_server() -> None:
    server = HTTPServer(("0.0.0.0", HEALTH_PORT), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()


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

    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    with httpx.Client(timeout=10) as client:
        response = client.get(url, headers=headers)
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
    global RUN_PROC
    if CANCEL_EVENT.is_set():
        raise RuntimeError("killed")
    try:
        RUN_PROC = subprocess.Popen(
            ["python", str(script_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if RUN_PROC.stdin:
            RUN_PROC.stdin.write(json.dumps(payload).encode("utf-8"))
            RUN_PROC.stdin.close()
        start = time.time()
        while True:
            if CANCEL_EVENT.is_set():
                try:
                    RUN_PROC.terminate()
                except Exception:
                    pass
                raise RuntimeError("killed")
            if RUN_PROC.poll() is not None:
                break
            if (time.time() - start) > timeout_sec:
                try:
                    RUN_PROC.terminate()
                except Exception:
                    pass
                raise RuntimeError("timeout")
            time.sleep(0.2)
        stdout = RUN_PROC.stdout.read() if RUN_PROC.stdout else b""
        if RUN_PROC.returncode != 0:
            return None
        return json.loads(stdout.decode("utf-8"))
    finally:
        RUN_PROC = None


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


def run_cycle(
    mapping: Dict[str, Any],
    only_scripts: Optional[List[str]] = None,
    only_devices: Optional[List[str]] = None,
) -> int:
    predictor = get_predictor_config(mapping)
    if not predictor or not predictor.get("enabled", True):
        return 0

    schedule = predictor.get("schedule", {})
    max_run_sec = int(schedule.get("maxRunSec") or 60)
    refresh_sec = int((predictor.get("github", {}) or {}).get("refreshSec") or 600)
    allowlist = (predictor.get("github", {}) or {}).get("allowlist") or []
    scripts = predictor.get("scripts") or []
    if only_scripts:
        scripts = [s for s in scripts if isinstance(s, dict) and s.get("name") in only_scripts]
    global_device = (predictor.get("globalDevice") or {}).get("deviceId")

    now = int(time.time())
    refresh = (now % refresh_sec) < 2

    devices = mapping.get("devices", {}) if isinstance(mapping, dict) else {}
    if only_devices:
        devices = {k: v for k, v in devices.items() if k in only_devices}
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
    return len(items)


def execute_cycle(
    scripts: Optional[List[str]] = None,
    device_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if not RUN_LOCK.acquire(blocking=False):
        return {"status": "busy"}
    start = now_ms()
    CANCEL_EVENT.clear()
    STATUS["running_job_id"] = CURRENT_JOB_ID
    try:
        mapping = read_mapping()
        predictor = get_predictor_config(mapping)
        STATUS["enabled"] = bool(predictor.get("enabled", True))
        STATUS["last_cycle_ts"] = now_ms()
        if not STATUS["enabled"]:
            STATUS["status"] = "disabled"
            STATUS["last_items"] = 0
            STATUS["last_duration_ms"] = now_ms() - start
            return {"status": "disabled", "items": 0}
        items = run_cycle(mapping, only_scripts=scripts, only_devices=device_ids)
        STATUS["status"] = "ok"
        STATUS["last_success_ts"] = now_ms()
        STATUS["last_items"] = items
        STATUS["last_duration_ms"] = now_ms() - start
        return {"status": "ok", "items": items, "duration_ms": now_ms() - start}
    except Exception as exc:
        if str(exc) == "killed":
            STATUS["status"] = "killed"
            STATUS["last_error"] = "killed"
            STATUS["last_error_ts"] = now_ms()
            STATUS["last_duration_ms"] = now_ms() - start
            return {"status": "killed"}
        STATUS["status"] = "error"
        STATUS["last_error"] = str(exc)
        STATUS["last_error_ts"] = now_ms()
        return {"status": "error", "detail": str(exc)}
    finally:
        STATUS["running_job_id"] = None
        CANCEL_EVENT.clear()
        RUN_LOCK.release()


def run_job(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    if job.get("status") == "canceled":
        return
    global CURRENT_JOB_ID
    CURRENT_JOB_ID = job_id
    update_job(job_id, status="running", started_ts=now_ms())
    try:
        payload = job.get("payload") or {}
        scripts = payload.get("scripts")
        device_ids = payload.get("deviceIds")
        result = execute_cycle(scripts=scripts, device_ids=device_ids)
        update_job(
            job_id,
            status="done" if result.get("status") == "ok" else result.get("status"),
            result=result,
            finished_ts=now_ms(),
        )
    except Exception as exc:
        update_job(
            job_id,
            status="error",
            result={"status": "error", "detail": str(exc)},
            finished_ts=now_ms(),
        )
    finally:
        CURRENT_JOB_ID = None


def scheduler_loop() -> None:
    while True:
        schedule = {}
        try:
            mapping = read_mapping()
            predictor = get_predictor_config(mapping)
            schedule = predictor.get("schedule", {})
        except Exception as exc:
            STATUS["status"] = "error"
            STATUS["last_error"] = str(exc)
            STATUS["last_error_ts"] = now_ms()
        execute_cycle()
        interval = int(schedule.get("intervalSec") or 60)
        interval = max(1, interval)
        time.sleep(interval)


def main() -> None:
    start_api_server()
    if MODE in {"loop", "scheduler"}:
        thread = threading.Thread(target=scheduler_loop, daemon=True)
        thread.start()
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
