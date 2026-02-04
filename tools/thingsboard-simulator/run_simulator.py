import argparse
import json
import random
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "data" / "devices.ifc.json"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_access_token(connector: dict) -> str | None:
    if "accessToken" in connector:
        return connector["accessToken"]
    # Tolerate accidental trailing space in key
    for key in connector.keys():
        if key.strip() == "accessToken":
            return connector[key]
    return None


def value_for_device(device: dict) -> float:
    dev_type = str(device.get("type", "")).lower()
    if "temperature" in dev_type:
        return round(random.uniform(20.0, 30.0), 2)
    if "humidity" in dev_type:
        return round(random.uniform(30.0, 70.0), 2)
    return round(random.uniform(0.0, 100.0), 2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Thingsboard telemetry simulator")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to devices.ifc.json",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override Thingsboard base URL (ex: http://localhost:7000)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds between telemetry pushes",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_config(config_path)
    base_url = (
        args.base_url
        or config.get("backend", {}).get("thingsboard", {}).get("baseUrl")
    )
    if not base_url:
        raise SystemExit("Missing backend.thingsboard.baseUrl or --base-url")

    devices = config.get("devices", {})
    if not devices:
        raise SystemExit("No devices found in config")

    print(f"Using base URL: {base_url}")
    print(f"Interval: {args.interval}s")
    print("Press Ctrl+C to stop.")

    while True:
        for name, device in devices.items():
            connector = device.get("connector", {})
            if connector.get("type") != "thingsboard":
                continue
            token = get_access_token(connector)
            if not token:
                print(f"[WARN] Missing accessToken for {name}")
                continue
            telemetry_key = connector.get("telemetryKey", "value")
            value = value_for_device(device)
            url = f"{base_url}/api/v1/{token}/telemetry"
            payload = {telemetry_key: value}
            try:
                resp = requests.post(url, json=payload, timeout=5)
                if resp.status_code >= 400:
                    print(
                        f"[ERROR] {name} {resp.status_code} {resp.text.strip()} -> {payload}"
                    )
                else:
                    print(f"[OK] {name} -> {payload}")
            except Exception as exc:
                print(f"[ERROR] {name} request failed: {exc}")
        time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
