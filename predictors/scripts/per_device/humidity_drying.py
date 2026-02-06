import json
import sys
from datetime import datetime, timezone

def _get_points(telemetry):
    if isinstance(telemetry, dict):
        points = telemetry.get("points")
        if isinstance(points, list):
            return points
        series = telemetry.get("series")
        if isinstance(series, dict):
            for _, pts in series.items():
                if isinstance(pts, list):
                    return pts
    return []

def _filter_points(points):
    cleaned = []
    for item in points:
        if not isinstance(item, dict):
            continue
        ts = item.get("ts")
        val = item.get("value")
        try:
            ts = int(ts)
            val = float(val)
        except Exception:
            continue
        cleaned.append({"ts": ts, "value": val})
    cleaned.sort(key=lambda p: p["ts"])
    return cleaned

def _linear_regression(points):
    n = len(points)
    if n < 2:
        return None
    xs = [p["ts"] for p in points]
    ys = [p["value"] for p in points]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den = sum((x - x_mean) ** 2 for x in xs)
    if den == 0:
        return None
    slope = num / den
    intercept = y_mean - slope * x_mean
    return slope, intercept

def _iso(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    telemetry = payload.get("telemetry") or {}
    points = _filter_points(_get_points(telemetry))

    device = payload.get("device") or {}
    drying_cfg = device.get("drying") or {}
    threshold = float(drying_cfg.get("rhThreshold", 65.0))
    min_points = int(drying_cfg.get("minPoints", 6))
    max_points = int(drying_cfg.get("maxPoints", 48))

    if len(points) < max(2, min_points):
        output = {
            "deviceId": payload.get("deviceId"),
            "telemetry": {"rh_threshold": threshold},
            "attributes": {"drying_status": "insufficient_data"},
        }
        print(json.dumps(output))
        return

    points = points[-max_points:]
    last = points[-1]
    current_rh = last["value"]

    if current_rh <= threshold:
        output = {
            "deviceId": payload.get("deviceId"),
            "telemetry": {
                "rh_current": current_rh,
                "rh_threshold": threshold,
                "drying_eta_ts": last["ts"],
                "drying_eta_hours": 0.0,
                "drying_rh_slope_per_hour": 0.0,
            },
            "attributes": {
                "drying_status": "done",
                "drying_eta_iso": _iso(last["ts"]),
            },
        }
        print(json.dumps(output))
        return

    reg = _linear_regression(points)
    if not reg:
        output = {
            "deviceId": payload.get("deviceId"),
            "telemetry": {
                "rh_current": current_rh,
                "rh_threshold": threshold,
            },
            "attributes": {"drying_status": "insufficient_data"},
        }
        print(json.dumps(output))
        return

    slope, _ = reg  # RH per ms
    slope_per_hour = slope * 3600 * 1000

    if slope >= 0:
        output = {
            "deviceId": payload.get("deviceId"),
            "telemetry": {
                "rh_current": current_rh,
                "rh_threshold": threshold,
                "drying_rh_slope_per_hour": slope_per_hour,
            },
            "attributes": {"drying_status": "not_drying"},
        }
        print(json.dumps(output))
        return

    time_to_threshold_ms = (threshold - current_rh) / slope
    eta_ts = int(last["ts"] + time_to_threshold_ms)
    eta_hours = max(0.0, time_to_threshold_ms / 3600 / 1000)

    output = {
        "deviceId": payload.get("deviceId"),
        "telemetry": {
            "rh_current": current_rh,
            "rh_threshold": threshold,
            "drying_eta_ts": eta_ts,
            "drying_eta_hours": eta_hours,
            "drying_rh_slope_per_hour": slope_per_hour,
        },
        "attributes": {
            "drying_status": "estimating",
            "drying_eta_iso": _iso(eta_ts),
        },
    }
    print(json.dumps(output))

if __name__ == "__main__":
    main()
