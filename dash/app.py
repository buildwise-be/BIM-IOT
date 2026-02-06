
import os
from datetime import datetime
from typing import Any, Dict, List

import httpx
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import Dash, dcc, html, Input, Output, State, no_update
from dash import callback_context, ALL

MIDDLEWARE_URL = os.getenv("MIDDLEWARE_URL", "http://localhost:8000").rstrip("/")
DASH_VIEWER_URL = os.getenv("DASH_VIEWER_URL", "http://localhost:8081").rstrip("/")
SCRIPT_HANDLER_URL = os.getenv("SCRIPT_HANDLER_URL", "http://predictor:8100").rstrip("/")
FONT_URL = "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap"


def refresh_mapping() -> None:
    url = f"{MIDDLEWARE_URL}/refresh_mapping"
    with httpx.Client(timeout=10) as client:
        response = client.post(url)
    if response.status_code != 200:
        raise RuntimeError(f"Refresh mapping failed: {response.status_code}")


def get_mapping() -> Dict[str, Any]:
    url = f"{MIDDLEWARE_URL}/devices.ifc.json"
    with httpx.Client(timeout=10) as client:
        response = client.get(url)
    if response.status_code != 200:
        raise RuntimeError(f"Fetch mapping failed: {response.status_code}")
    return response.json()


def build_device_options(mapping: Dict[str, Any]) -> List[Dict[str, str]]:
    devices = mapping.get("devices", {}) if isinstance(mapping, dict) else {}
    options = []
    for device_id, data in devices.items():
        label = f"{device_id} ({data.get('type', 'unknown')})"
        options.append({"label": label, "value": device_id})
    return options


def fetch_telemetry(
    mapping: Dict[str, Any],
    device_id: str,
    key: str | None,
    limit: int,
    hours: int,
    agg: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    interval: str | None = None,
) -> Dict[str, Any]:
    if not mapping:
        raise RuntimeError("Mapping not loaded")
    url = f"{MIDDLEWARE_URL}/devices/{device_id}/telemetry"
    params = {"limit": limit, "hours": hours}
    if key:
        params["key"] = key
    if agg:
        params["agg"] = agg
    if start_ts:
        params["startTs"] = start_ts
    if end_ts:
        params["endTs"] = end_ts
    if interval:
        params["interval"] = interval
    with httpx.Client(timeout=10) as client:
        response = client.get(url, params=params)
    if response.status_code != 200:
        detail = f"Telemetry fetch failed: {response.status_code}"
        try:
            payload = response.json()
            message = payload.get("detail") or payload.get("message") or payload.get("error")
            if message:
                detail = f"Telemetry fetch failed: {message}"
        except Exception:
            if response.text.strip():
                detail = f"Telemetry fetch failed: {response.text.strip()}"
        raise RuntimeError(detail)
    return response.json()


def fetch_thingsboard_health() -> Dict[str, Any]:
    url = f"{MIDDLEWARE_URL}/thingsboard/health"
    with httpx.Client(timeout=5) as client:
        response = client.get(url)
    if response.status_code != 200:
        return {"status": "error", "connected": False, "detail": f"{response.status_code}"}
    return response.json()


def fetch_script_handler_health() -> Dict[str, Any]:
    url = f"{SCRIPT_HANDLER_URL}/health"
    with httpx.Client(timeout=5) as client:
        response = client.get(url)
    if response.status_code != 200:
        return {"status": "error", "detail": f"{response.status_code}"}
    return response.json()


def fetch_script_handler_status() -> Dict[str, Any]:
    url = f"{SCRIPT_HANDLER_URL}/status"
    with httpx.Client(timeout=5) as client:
        response = client.get(url)
    if response.status_code != 200:
        return {"status": "error", "detail": f"{response.status_code}"}
    return response.json()


def post_script_handler_run() -> Dict[str, Any]:
    url = f"{SCRIPT_HANDLER_URL}/run"
    with httpx.Client(timeout=10) as client:
        response = client.post(url, json={})
    if response.status_code != 200:
        return {"status": "error", "detail": f"{response.status_code}"}
    return response.json()


def post_script_handler_run_async() -> Dict[str, Any]:
    url = f"{SCRIPT_HANDLER_URL}/run_async"
    with httpx.Client(timeout=10) as client:
        response = client.post(url, json={})
    if response.status_code not in {200, 202}:
        return {"status": "error", "detail": f"{response.status_code}"}
    return response.json()


def post_script_handler_reload() -> Dict[str, Any]:
    url = f"{SCRIPT_HANDLER_URL}/reload"
    with httpx.Client(timeout=10) as client:
        response = client.post(url)
    if response.status_code != 200:
        return {"status": "error", "detail": f"{response.status_code}"}
    return response.json()


def fetch_script_handler_job(job_id: str) -> Dict[str, Any]:
    url = f"{SCRIPT_HANDLER_URL}/jobs/{job_id}"
    with httpx.Client(timeout=5) as client:
        response = client.get(url)
    if response.status_code != 200:
        return {"status": "error", "detail": f"{response.status_code}"}
    return response.json()


def post_script_handler_kill(job_id: str | None = None) -> Dict[str, Any]:
    url = f"{SCRIPT_HANDLER_URL}/kill"
    payload: Dict[str, Any] = {}
    if job_id:
        payload["jobId"] = job_id
    with httpx.Client(timeout=5) as client:
        response = client.post(url, json=payload)
    if response.status_code != 200:
        return {"status": "error", "detail": f"{response.status_code}"}
    return response.json()


def fetch_alarms_summary(status: str = "ACTIVE") -> Dict[str, Any]:
    url = f"{MIDDLEWARE_URL}/alarms/summary"
    params = {"status": status}
    with httpx.Client(timeout=10) as client:
        response = client.get(url, params=params)
    if response.status_code != 200:
        detail = f"Alarm summary fetch failed: {response.status_code}"
        try:
            payload = response.json()
            message = payload.get("detail") or payload.get("message") or payload.get("error")
            if message:
                detail = f"Alarm summary fetch failed: {message}"
        except Exception:
            if response.text.strip():
                detail = f"Alarm summary fetch failed: {response.text.strip()}"
        raise RuntimeError(detail)
    return response.json()


def fetch_alarms_recent(status: str = "ACTIVE", limit: int = 8) -> Dict[str, Any]:
    url = f"{MIDDLEWARE_URL}/alarms/recent"
    params = {"status": status, "limit": limit}
    with httpx.Client(timeout=10) as client:
        response = client.get(url, params=params)
    if response.status_code != 200:
        detail = f"Alarm list fetch failed: {response.status_code}"
        try:
            payload = response.json()
            message = payload.get("detail") or payload.get("message") or payload.get("error")
            if message:
                detail = f"Alarm list fetch failed: {message}"
        except Exception:
            if response.text.strip():
                detail = f"Alarm list fetch failed: {response.text.strip()}"
        raise RuntimeError(detail)
    return response.json()


def post_alarm_action(alarm_id: str, action: str) -> Dict[str, Any]:
    url = f"{MIDDLEWARE_URL}/alarms/{alarm_id}/{action}"
    with httpx.Client(timeout=10) as client:
        response = client.post(url)
    if response.status_code != 200:
        detail = f"Alarm action failed: {response.status_code}"
        try:
            payload = response.json()
            message = payload.get("detail") or payload.get("message") or payload.get("error")
            if message:
                detail = f"Alarm action failed: {message}"
        except Exception:
            if response.text.strip():
                detail = f"Alarm action failed: {response.text.strip()}"
        raise RuntimeError(detail)
    return response.json()


def format_alarm_time(ts: int | None) -> str:
    if not ts:
        return "Unknown time"
    dt = datetime.fromtimestamp(ts / 1000)
    return dt.strftime("%H:%M %d %b")


def build_alarm_nodes(alarms: List[Dict[str, Any]]) -> Any:
    if not alarms:
        return html.Div("No active alarms", className="text-muted small")

    nodes = []
    for alarm in alarms:
        severity = str(alarm.get("severity") or "INDETERMINATE").upper()
        severity_key = severity.lower()
        if severity_key not in {"critical", "major", "minor", "warning", "indeterminate"}:
            severity_key = "indeterminate"

        created_time = alarm.get("createdTime")
        device_id = (alarm.get("originator") or {}).get("deviceId") or "Unknown device"
        alarm_type = alarm.get("type") or "Alarm"
        status = alarm.get("status") or "ACTIVE"
        alarm_id = alarm.get("id")
        can_act = bool(alarm_id)

        acknowledged = bool(alarm.get("acknowledged"))
        cleared = bool(alarm.get("cleared"))
        ack_label = "ACK" if acknowledged else "ACK?"
        clear_label = "CLEAR" if cleared else "CLEAR?"
        sev_dot_class = f"alarm-sev-dot alarm-sev-{severity_key}"

        nodes.append(
            html.Div(
                className="alarm-item",
                children=[
                    html.Div(
                        children=[
                            html.Div(
                                className="alarm-title-row",
                                children=[
                                    html.Span(className=sev_dot_class, title="Severity"),
                                    html.Span(alarm_type, className="alarm-title"),
                                ],
                            ),
                            html.Div(
                                className="alarm-meta",
                                children=[
                                    html.Span(f"{device_id} · {status} · {format_alarm_time(created_time)}"),
                                    html.Span(
                                        className="alarm-states",
                                        children=[
                                            html.Button(
                                                f"✓ {ack_label}",
                                                id={
                                                    "type": "alarm-action",
                                                    "action": "ack",
                                                    "alarmId": alarm_id,
                                                },
                                                className=f"alarm-state-btn {'alarm-state-on' if acknowledged else 'alarm-state-off'}",
                                                disabled=not can_act or acknowledged,
                                                title="Acknowledge",
                                            ),
                                            html.Button(
                                                f"✕ {clear_label}",
                                                id={
                                                    "type": "alarm-action",
                                                    "action": "clear",
                                                    "alarmId": alarm_id,
                                                },
                                                className=f"alarm-state-btn {'alarm-state-on' if cleared else 'alarm-state-off'}",
                                                disabled=not can_act or cleared,
                                                title="Clear",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ]
                    ),
                ],
            )
        )

    return nodes


dash_app = Dash(__name__, external_stylesheets=[dbc.themes.LUX, FONT_URL])
dash_app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
          :root {
            --glass-bg: rgba(255, 255, 255, 0.85);
            --glass-border: rgba(148, 163, 184, 0.25);
            --ink: #0f172a;
            --muted: #64748b;
            --accent: #0ea5a4;
          }

          body {
            font-family: 'Space Grotesk', 'Segoe UI', sans-serif;
            background: radial-gradient(circle at top, #f8fafc 0%, #eef2ff 35%, #f8fafc 70%);
            color: var(--ink);
          }

          .app-shell {
            min-height: 100vh;
          }

          .glass-card {
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 18px;
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
            backdrop-filter: blur(8px);
          }

          .soft-panel {
            border-top: 1px solid rgba(148, 163, 184, 0.15);
          }

          .kpi-label {
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.08em;
            color: var(--muted);
          }

          .kpi-value {
            font-size: 26px;
            font-weight: 600;
            margin-top: 4px;
          }

          .kpi-devices {
            color: #0f766e;
          }

          .kpi-auto {
            color: #0ea5a4;
          }

          .kpi-sync {
            color: #1d4ed8;
          }

          .kpi-alarms {
            color: #dc2626;
          }

          .kpi-sub {
            font-size: 12px;
            color: var(--muted);
            margin-top: 4px;
          }

          .telemetry-status {
            color: var(--muted);
          }

          .telemetry-status.error {
            color: #dc2626;
            font-weight: 600;
          }

          .btn-primary {
            background-color: var(--accent);
            border-color: var(--accent);
          }

          .btn-primary:hover {
            background-color: #0d9488;
            border-color: #0d9488;
          }

          .alarm-item {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            padding: 8px 0;
            border-bottom: 1px solid rgba(148, 163, 184, 0.2);
          }

          .alarm-item:last-child {
            border-bottom: none;
          }

          .alarm-title {
            font-weight: 600;
          }

          .alarm-title-row {
            display: inline-flex;
            align-items: center;
            gap: 8px;
          }

          .alarm-sev-dot {
            width: 10px;
            height: 10px;
            border-radius: 999px;
            display: inline-block;
          }

          .alarm-meta {
            font-size: 11px;
            color: var(--muted);
            margin-top: 2px;
          }

          .alarm-states {
            display: inline-flex;
            gap: 6px;
            margin-left: 8px;
          }

          .alarm-state-btn {
            font-size: 10px;
            text-transform: uppercase;
            padding: 2px 8px;
            border-radius: 999px;
            border: 1px solid rgba(148, 163, 184, 0.3);
            background: white;
          }

          .alarm-state-on {
            background: rgba(16, 185, 129, 0.15);
            color: #059669;
            border-color: rgba(16, 185, 129, 0.4);
          }

          .alarm-state-off {
            background: rgba(148, 163, 184, 0.12);
            color: #64748b;
          }

          .alarm-actions {
            display: inline-flex;
            gap: 6px;
            margin-left: 8px;
            vertical-align: middle;
          }

          .alarm-state-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }

          .kpi-sync-online {
            color: #16a34a;
          }

          .kpi-sync-offline {
            color: #dc2626;
          }

          .alarm-sev {
            font-size: 10px;
            text-transform: uppercase;
            padding: 2px 8px;
            border-radius: 999px;
            align-self: flex-start;
          }

          .alarm-sev-critical {
            background: rgba(220, 38, 38, 0.15);
            color: #dc2626;
          }

          .alarm-sev-major {
            background: rgba(245, 158, 11, 0.2);
            color: #b45309;
          }

          .alarm-sev-minor {
            background: rgba(14, 165, 233, 0.15);
            color: #0284c7;
          }

          .alarm-sev-warning {
            background: rgba(234, 88, 12, 0.15);
            color: #c2410c;
          }

          .alarm-sev-indeterminate {
            background: rgba(100, 116, 139, 0.2);
            color: #475569;
          }

          .telemetry-body {
            min-width: 0;
          }

          .telemetry-controls {
            flex-wrap: wrap;
          }

          .telemetry-tabs {
            min-width: 0;
          }

          .telemetry-body .dash-graph,
          .telemetry-body .js-plotly-plot,
          .telemetry-body .plot-container,
          .telemetry-body .main-svg {
            max-width: 100%;
          }

          .panel-collapsed {
            writing-mode: vertical-rl;
            text-orientation: mixed;
            flex-direction: column;
            align-items: center;
            gap: 8px;
          }

          .panel-collapsed .btn {
            margin: 0;
          }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""


dash_app.layout = html.Div(
    className="app-shell",
    children=[
        dbc.Container(
            fluid=True,
            className="py-4",
            children=[
                dbc.Row(
                    className="align-items-center g-3 mb-3",
                    children=[
                        dbc.Col(
                            md=8,
                            children=[
                                html.Div("BIM-IOT Intelligence Hub", className="display-6 fw-semibold"),
                                html.Div(
                                    "Unified operational intelligence for data-driven decisions, live telemetry, and spatial context.",
                                    className="text-muted",
                                ),
                            ],
                        ),
                        dbc.Col(
                            md=4,
                            children=[
                                dbc.Card(
                                    className="shadow-sm border-0",
                                    children=[
                                        dbc.CardBody(
                                            children=[
                                                html.Div("Control Center", className="text-uppercase small text-muted"),
                                                html.Div("Operational readiness", className="fw-semibold"),
                                                html.Div(
                                                    id="mapping-status",
                                                    className="text-muted small mt-2",
                                                ),
                                            ]
                                        )
                                    ],
                                )
                            ],
                        ),
                    ],
                ),
                dbc.Row(
                    className="g-3 mb-3",
                    children=[
                        dbc.Col(
                            md=4,
                            children=[
                                dbc.Card(
                                    id="awareness-panel",
                                    className="glass-card h-100",
                                    children=[
                                        dbc.CardHeader(
                                            className="d-flex justify-content-between align-items-center",
                                            children=[
                                                html.Div("Awareness Center - At a Glance", className="fw-semibold"),
                                                dbc.Button(
                                                    "v",
                                                    id="toggle-awareness-btn",
                                                    size="sm",
                                                    color="secondary",
                                                    outline=True,
                                                ),
                                            ],
                                        ),
                                        dbc.CardBody(
                                            id="awareness-body",
                                            className="soft-panel",
                                            children=[
                                                dbc.Row(
                                                    className="g-3",
                                                      children=[
                                                          dbc.Col(
                                                              md=6,
                                                              children=[
                                                                dbc.Card(
                                                                    className="glass-card h-100",
                                                                    children=[
                                                                        dbc.CardBody(
                                                                            children=[
                                                                                html.Div("Devices", className="kpi-label"),
                                                                                html.Div(
                                                                                    "0",
                                                                                    id="kpi-devices-value",
                                                                                    className="kpi-value kpi-devices",
                                                                                ),
                                                                                html.Div("Mapping loaded", className="kpi-sub"),
                                                                            ]
                                                                        )
                                                                    ],
                                                                )
                                                            ],
                                                        ),
                                                        dbc.Col(
                                                            md=6,
                                                            children=[
                                                                dbc.Card(
                                                                    className="glass-card h-100",
                                                                    children=[
                                                                        dbc.CardBody(
                                                                            children=[
                                                                                html.Div("Active alarms", className="kpi-label"),
                                                                                html.Div(
                                                                                    "0",
                                                                                    id="kpi-alarms-value",
                                                                                    className="kpi-value kpi-alarms",
                                                                                ),
                                                                                html.Div(
                                                                                    "Mapped devices",
                                                                                    id="kpi-alarms-sub",
                                                                                    className="kpi-sub",
                                                                                ),
                                                                            ]
                                                                        )
                                                                    ],
                                                                )
                                                            ],
                                                        ),
                                                        dbc.Col(
                                                            md=6,
                                                            children=[
                                                                dbc.Card(
                                                                    className="glass-card h-100",
                                                                    children=[
                                                                        dbc.CardBody(
                                                                            children=[
                                                                                html.Div("Auto refresh", className="kpi-label"),
                                                                                html.Div(
                                                                                    "OFF",
                                                                                    id="kpi-auto-value",
                                                                                    className="kpi-value kpi-auto",
                                                                                ),
                                                                                html.Div("Telemetry", className="kpi-sub"),
                                                                            ]
                                                                        )
                                                                    ],
                                                                )
                                                            ],
                                                        ),
                                                          dbc.Col(
                                                              md=6,
                                                              children=[
                                                                  dbc.Card(
                                                                      className="glass-card h-100",
                                                                      children=[
                                                                          dbc.CardBody(
                                                                              children=[
                                                                                  html.Div("Sync status", className="kpi-label"),
                                                                                  html.Div(
                                                                                      "N/A",
                                                                                      id="kpi-sync-value",
                                                                                      className="kpi-value kpi-sync",
                                                                                  ),
                                                                                  html.Div(
                                                                                      "Thingsboard",
                                                                                      id="kpi-sync-sub",
                                                                                      className="kpi-sub",
                                                                                  ),
                                                                              ]
                                                                          )
                                                                      ],
                                                                  )
                                                              ],
                                                          ),
                                                          dbc.Col(
                                                              md=6,
                                                              children=[
                                                                  dbc.Card(
                                                                      className="glass-card h-100",
                                                                      children=[
                                                                          dbc.CardBody(
                                                                              children=[
                                                                                  html.Div("Script Pulse", className="kpi-label"),
                                                                                  html.Div(
                                                                                      "N/A",
                                                                                      id="kpi-script-value",
                                                                                      className="kpi-value kpi-sync",
                                                                                  ),
                                                                                  html.Div(
                                                                                      "Script handler",
                                                                                      id="kpi-script-sub",
                                                                                      className="kpi-sub",
                                                                                  ),
                                                                              ]
                                                                          )
                                                                      ],
                                                                  )
                                                              ],
                                                          ),
                                                      ],
                                                  ),
                                                  dbc.Card(
                                                      className="glass-card mt-3",
                                              ],
                                          ),
                                      ],
                                  )
                              ],
                        ),
                        dbc.Col(
                            md=4,
                            children=[
                                dbc.Card(
                                    id="alarms-panel",
                                    className="glass-card h-100",
                                    children=[
                                        dbc.CardHeader(
                                            className="d-flex justify-content-between align-items-center",
                                            children=[
                                                html.Div("Alarms", className="fw-semibold"),
                                                dbc.Button(
                                                    "v",
                                                    id="toggle-alarms-btn",
                                                    size="sm",
                                                    color="secondary",
                                                    outline=True,
                                                ),
                                            ],
                                        ),
                                        dbc.CardBody(
                                            id="alarms-body",
                                            className="soft-panel",
                                            children=[
                                                html.Div(
                                                    id="alarms-status",
                                                    className="text-muted small mb-2",
                                                ),
                                                html.Div(
                                                    id="alarms-list",
                                                    className="small",
                                                )
                                            ],
                                        ),
                                    ],
                                )
                            ],
                        ),
                        dbc.Col(
                            md=4,
                            children=[
                                dbc.Card(
                                    id="devices-panel",
                                    className="glass-card h-100",
                                    children=[
                                        dbc.CardHeader(
                                            className="d-flex justify-content-between align-items-center",
                                            children=[
                                                html.Div("Devices", className="fw-semibold"),
                                                dbc.Button(
                                                    "v",
                                                    id="toggle-devices-btn",
                                                    size="sm",
                                                    color="secondary",
                                                    outline=True,
                                                ),
                                            ],
                                        ),
                                        dbc.CardBody(
                                            id="devices-body",
                                            className="soft-panel",
                                            children=[
                                                dbc.ButtonGroup(
                                                    className="mb-3",
                                                    children=[
                                                        dbc.Button(
                                                            "Refresh mapping",
                                                            id="mapping-refresh-btn",
                                                            color="primary",
                                                        ),
                                                        dbc.Button(
                                                            "Reset selection",
                                                            id="reset-selection-btn",
                                                            color="light",
                                                        ),
                                                        dbc.Button(
                                                            "Focus",
                                                            id="focus-device-btn",
                                                            color="success",
                                                        ),
                                                    ],
                                                ),
                                                html.Div(
                                                    "Device selection",
                                                    className="text-uppercase small text-muted",
                                                ),
                                                dcc.Dropdown(
                                                    id="device-dropdown",
                                                    options=[],
                                                    value=[],
                                                    multi=True,
                                                    className="mb-2",
                                                ),
                                                html.Div(id="device-info", className="small text-muted"),
                                                html.Hr(className="my-3"),
                                                html.Div(id="viewer-logs", className="small"),
                                            ],
                                        ),
                                    ],
                                )
                            ],
                        ),
                    ],
                ),
                dbc.Row(
                    className="g-3",
                    children=[
                        dbc.Col(
                            id="telemetry-col",
                            md=4,
                            children=[
                                dbc.Card(
                                    id="telemetry-panel",
                                    className="glass-card h-100",
                                    children=[
                                        dbc.CardHeader(
                                            id="telemetry-header",
                                            className="d-flex justify-content-between align-items-center",
                                            children=[
                                                html.Div("Telemetry", className="fw-semibold"),
                                                dbc.Button(
                                                    "<",
                                                    id="toggle-telemetry-btn",
                                                    size="sm",
                                                    color="secondary",
                                                    outline=True,
                                                ),
                                            ],
                                        ),
                                                                dbc.CardBody(
                                                                    id="telemetry-body",
                                                                    className="soft-panel telemetry-body",
                                                                    children=[
                                                                        dbc.Row(
                                                                            className="g-2 align-items-center telemetry-controls",
                                                                            children=[
                                                                                dbc.Col(
                                                                                    width="auto",
                                                                                    children=[
                                                                                        dbc.Button(
                                                                                            "Refresh telemetry",
                                                                                            id="telemetry-load-btn",
                                                                                            color="primary",
                                                                                        )
                                                                                    ],
                                                                                ),
                                                                                dbc.Col(
                                                                                    width="auto",
                                                                                    children=[
                                                                                        dbc.Button(
                                                                                            "Advanced options",
                                                                                            id="telemetry-advanced-btn",
                                                                                            color="light",
                                                                                        )
                                                                                    ],
                                                                                ),
                                                                                dbc.Col(
                                                                                    width="auto",
                                                                                    children=[
                                                                                        dbc.Button(
                                                                                            "Auto refresh",
                                                                                            id="telemetry-auto-btn",
                                                                                            color="success",
                                                                                        )
                                                                                    ],
                                                                                ),
                                                                                dbc.Col(
                                                                                    width="auto",
                                                                                    children=[
                                                                                        html.Div(
                                                                                            id="telemetry-live-indicator",
                                                                                            children="paused",
                                                                                            style={
                                                                                                "padding": "4px 8px",
                                                                                                "borderRadius": "999px",
                                                                                                "background": "#e5e7eb",
                                                                                                "color": "#334155",
                                                                                                "fontSize": "12px",
                                                                                            },
                                                                                        )
                                                                                    ],
                                                                                ),
                                                                            ],
                                                                        ),
                                                                        html.Div(
                                                                            id="telemetry-advanced",
                                                                            style={"marginTop": "12px", "display": "none"},
                                                                            children=[
                                                                                dbc.Card(
                                                                                    className="border-0 bg-light",
                                                                                    children=[
                                                                                        dbc.CardBody(
                                                                                            children=[
                                                                                                html.Div("Period", className="small text-muted"),
                                                                                                dcc.Input(
                                                                                                    id="telemetry-key",
                                                                                                    type="text",
                                                                                                    placeholder="Override key (optional)",
                                                                                                    style={"width": "100%"},
                                                                                                ),
                                                                                                html.Div(
                                                                                                    "Period mode",
                                                                                                    className="small text-muted mt-2",
                                                                                                ),
                                                                                                html.Div(
                                                                                                    style={
                                                                                                        "display": "grid",
                                                                                                        "gridTemplateColumns": "1fr 1fr",
                                                                                                        "gap": "8px",
                                                                                                        "marginTop": "8px",
                                                                                                    },
                                                                                                    children=[
                                                                                                        dcc.Dropdown(
                                                                                                            id="telemetry-period",
                                                                                                            options=[
                                                                                                                {
                                                                                                                    "label": "Last hours",
                                                                                                                    "value": "hours",
                                                                                                                },
                                                                                                                {
                                                                                                                    "label": "Last days",
                                                                                                                    "value": "days",
                                                                                                                },
                                                                                                                {
                                                                                                                    "label": "Date range",
                                                                                                                    "value": "range",
                                                                                                                },
                                                                                                            ],
                                                                                                            value="hours",
                                                                                                        ),
                                                                                                        dcc.Input(
                                                                                                            id="telemetry-hours",
                                                                                                            type="number",
                                                                                                            min=1,
                                                                                                            max=168,
                                                                                                            value=24,
                                                                                                            style={"width": "100%"},
                                                                                                        ),
                                                                                                        dcc.Input(
                                                                                                            id="telemetry-limit",
                                                                                                            type="number",
                                                                                                            min=1,
                                                                                                            max=1000,
                                                                                                            value=24,
                                                                                                            style={"width": "100%"},
                                                                                                        ),
                                                                                                    ],
                                                                                                ),
                                                                                                html.Div(
                                                                                                    "Max points (1-1000)",
                                                                                                    className="small text-muted mt-1",
                                                                                                ),
                                                                                                html.Div(
                                                                                                    "Days (when mode = days)",
                                                                                                    className="small text-muted mt-2",
                                                                                                ),
                                                                                                dcc.Input(
                                                                                                    id="telemetry-days",
                                                                                                    type="number",
                                                                                                    min=1,
                                                                                                    max=30,
                                                                                                    value=1,
                                                                                                    style={
                                                                                                        "width": "100%",
                                                                                                        "marginTop": "8px",
                                                                                                    },
                                                                                                ),
                                                                                                html.Div(
                                                                                                    "Date range (when mode = range)",
                                                                                                    className="small text-muted mt-2",
                                                                                                ),
                                                                                                dcc.DatePickerRange(
                                                                                                    id="telemetry-range",
                                                                                                    start_date_placeholder_text="Start date",
                                                                                                    end_date_placeholder_text="End date",
                                                                                                    style={"marginTop": "8px"},
                                                                                                ),
                                                                                                html.Div(
                                                                                                    "Aggregation",
                                                                                                    className="small text-muted mt-2",
                                                                                                ),
                                                                                                dcc.Dropdown(
                                                                                                    id="telemetry-agg",
                                                                                                    options=[
                                                                                                        {
                                                                                                            "label": "Raw (NONE)",
                                                                                                            "value": "NONE",
                                                                                                        },
                                                                                                        {
                                                                                                            "label": "Average (AVG)",
                                                                                                            "value": "AVG",
                                                                                                        },
                                                                                                        {"label": "Min (MIN)", "value": "MIN"},
                                                                                                        {"label": "Max (MAX)", "value": "MAX"},
                                                                                                    ],
                                                                                                    value="NONE",
                                                                                                    style={"marginTop": "8px"},
                                                                                                ),
                                                                                                html.Div(
                                                                                                    "Aggregation interval",
                                                                                                    className="small text-muted mt-2",
                                                                                                ),
                                                                                                html.Div(
                                                                                                    style={
                                                                                                        "display": "grid",
                                                                                                        "gridTemplateColumns": "1fr 1fr",
                                                                                                        "gap": "8px",
                                                                                                        "marginTop": "8px",
                                                                                                    },
                                                                                                    children=[
                                                                                                        dcc.Input(
                                                                                                            id="telemetry-agg-interval-count",
                                                                                                            type="number",
                                                                                                            min=1,
                                                                                                            value=15,
                                                                                                            style={"width": "100%"},
                                                                                                        ),
                                                                                                        dcc.Dropdown(
                                                                                                            id="telemetry-agg-interval-unit",
                                                                                                            options=[
                                                                                                                {"label": "Minute", "value": "minute"},
                                                                                                                {"label": "Hour", "value": "hour"},
                                                                                                                {"label": "Day", "value": "day"},
                                                                                                                {"label": "Week", "value": "week"},
                                                                                                                {"label": "Month", "value": "month"},
                                                                                                                {"label": "Year", "value": "year"},
                                                                                                            ],
                                                                                                            value="minute",
                                                                                                        ),
                                                                                                    ],
                                                                                                ),
                                                                                                html.Div(
                                                                                                    "Keys (comma-separated)",
                                                                                                    className="small text-muted mt-2",
                                                                                                ),
                                                                                                dcc.Input(
                                                                                                    id="telemetry-keys",
                                                                                                    type="text",
                                                                                                    placeholder="Keys (comma-separated)",
                                                                                                    style={
                                                                                                        "width": "100%",
                                                                                                        "marginTop": "8px",
                                                                                                    },
                                                                                                ),
                                                                                                html.Div(
                                                                                                    "Auto refresh interval (seconds)",
                                                                                                    className="small text-muted mt-2",
                                                                                                ),
                                                                                                dcc.Input(
                                                                                                    id="telemetry-interval",
                                                                                                    type="number",
                                                                                                    min=2,
                                                                                                    max=120,
                                                                                                    value=10,
                                                                                                    style={
                                                                                                        "width": "100%",
                                                                                                        "marginTop": "8px",
                                                                                                    },
                                                                                                ),
                                                                                            ]
                                                                                        )
                                                                                    ],
                                                                                )
                                                                            ],
                                                                        ),
                                                html.Div(
                                                    id="telemetry-status",
                                                    className="telemetry-status small mt-2",
                                                ),
                                                                        dcc.Tabs(
                                                                            id="telemetry-tabs",
                                                                            children=[],
                                                                            className="mt-3 telemetry-tabs",
                                                                        ),
                                                                    ],
                                                                ),
                                                            ],
                                                        )
                            ],
                        ),
                        dbc.Col(
                            id="pulse-col",
                            md=3,
                            children=[
                                dbc.Card(
                                    id="pulse-panel",
                                    className="glass-card h-100",
                                    children=[
                                        dbc.CardHeader(
                                            className="d-flex justify-content-between align-items-center",
                                            children=[
                                                html.Div("Pulse", className="fw-semibold"),
                                                html.Div("Script handler", className="text-muted small"),
                                            ],
                                        ),
                                        dbc.CardBody(
                                            className="soft-panel",
                                            children=[
                                                html.Div("Diagnostics", className="kpi-label"),
                                                html.Div(
                                                    id="script-pulse-details",
                                                    className="small text-muted",
                                                ),
                                                html.Hr(className="my-2"),
                                                dbc.Row(
                                                    className="g-2 align-items-center",
                                                    children=[
                                                        dbc.Col(
                                                            width="auto",
                                                            children=[
                                                                dbc.Button(
                                                                    "Run now",
                                                                    id="script-run-btn",
                                                                    color="primary",
                                                                )
                                                            ],
                                                        ),
                                                        dbc.Col(
                                                            width="auto",
                                                            children=[
                                                                dbc.Button(
                                                                    "Run async",
                                                                    id="script-run-async-btn",
                                                                    color="secondary",
                                                                )
                                                            ],
                                                        ),
                                                        dbc.Col(
                                                            width="auto",
                                                            children=[
                                                                dbc.Button(
                                                                    "Kill",
                                                                    id="script-kill-btn",
                                                                    color="danger",
                                                                )
                                                            ],
                                                        ),
                                                    ],
                                                ),
                                                dbc.Row(
                                                    className="g-2 align-items-center mt-2",
                                                    children=[
                                                        dbc.Col(
                                                            width="auto",
                                                            children=[
                                                                dbc.Button(
                                                                    "Reload mapping",
                                                                    id="script-reload-btn",
                                                                    color="light",
                                                                )
                                                            ],
                                                        )
                                                    ],
                                                ),
                                                html.Div(
                                                    id="script-control-status",
                                                    className="telemetry-status small mt-2",
                                                ),
                                                html.Div(
                                                    id="script-job-status",
                                                    className="text-muted small mt-2",
                                                ),
                                            ],
                                        ),
                                    ],
                                )
                            ],
                        ),
                        dbc.Col(
                            id="viewer-col",
                            md=5,
                            children=[
                                dbc.Card(
                                    id="viewer-panel",
                                    className="glass-card",
                                    children=[
                                        dbc.CardHeader(
                                            id="viewer-header",
                                            className="d-flex justify-content-between align-items-center",
                                            children=[
                                                html.Div("Viewer 3D", className="fw-semibold"),
                                                dbc.Button(
                                                    "<",
                                                    id="toggle-viewer-btn",
                                                    size="sm",
                                                    color="secondary",
                                                    outline=True,
                                                ),
                                            ],
                                        ),
                                                                dbc.CardBody(
                                                                    id="viewer-body",
                                                                    className="p-0",
                                                                    children=[
                                                                        html.Iframe(
                                                                            id="viewer-frame",
                                                                            src=DASH_VIEWER_URL,
                                                                            style={
                                                                                "width": "100%",
                                                                                "height": "600px",
                                                                                "border": "0",
                                                                                "display": "block",
                                                                                "background": "#0f172a",
                                                                            },
                                                                        )
                                                                    ],
                                                                ),
                                    ],
                                )
                            ],
                        )
                    ],
                ),
            ],
        ),
        dcc.Store(id="mapping-store"),
        dcc.Store(id="viewer-command"),
        dcc.Store(id="viewer-event-store"),
        dcc.Store(id="viewer-log-store"),
        dcc.Store(id="devices-panel-state", data=True),
        dcc.Store(id="alarms-panel-state", data=True),
        dcc.Store(id="awareness-panel-state", data=True),
        dcc.Store(id="script-job-id", data=""),
        dcc.Store(id="telemetry-panel-state", data=True),
        dcc.Store(id="viewer-panel-state", data=True),
        dcc.Store(id="telemetry-advanced-state", data=False),
        dcc.Store(id="telemetry-auto-state", data=False),
        dcc.Interval(id="mapping-init", interval=500, n_intervals=0, max_intervals=1),
        dcc.Interval(id="telemetry-auto-interval", interval=10000, n_intervals=0, disabled=True),
        dcc.Interval(id="viewer-event-poll", interval=500, n_intervals=0),
        dcc.Interval(id="tb-health-interval", interval=15000, n_intervals=0),
        html.Div(id="alarms-action-status", className="text-muted small d-none"),
        html.Script(
            """
            window.__viewerEvent = null;
            window.__viewerLog = null;
            window.addEventListener("message", (event) => {
              const data = event.data;
              if (!data || typeof data !== "object") return;
              if (data.type === "viewerSelection") {
                window.__viewerEvent = data;
              }
              if (data.type === "viewerLog") {
                window.__viewerLog = data;
              }
            });
            """
        ),
        html.Div(id="viewer-command-sink", style={"display": "none"}),
    ],
)


@dash_app.callback(
    Output("mapping-store", "data"),
    Output("device-dropdown", "options"),
    Output("mapping-status", "children"),
    Output("viewer-command", "data"),
    Input("mapping-refresh-btn", "n_clicks"),
    Input("mapping-init", "n_intervals"),
)
def on_refresh_mapping(n_clicks, init_ticks):
    if not n_clicks and not init_ticks:
        return no_update, no_update, "Loading mapping...", no_update
    try:
        refresh_mapping()
        mapping = get_mapping()
        options = build_device_options(mapping)
        return mapping, options, f"Mapping loaded: {len(options)} devices.", {"type": "refreshMapping"}
    except Exception as exc:
        return no_update, [], f"Failed to load mapping: {exc}", no_update


@dash_app.callback(
    Output("kpi-devices-value", "children"),
    Output("kpi-auto-value", "children"),
    Output("kpi-sync-value", "children"),
    Output("kpi-sync-value", "className"),
    Output("kpi-sync-sub", "children"),
    Output("kpi-script-value", "children"),
    Output("kpi-script-value", "className"),
    Output("kpi-script-sub", "children"),
    Output("kpi-alarms-value", "children"),
    Output("kpi-alarms-sub", "children"),
    Input("mapping-store", "data"),
    Input("telemetry-auto-state", "data"),
    Input("tb-health-interval", "n_intervals"),
)
def update_kpis(mapping, auto_state, n_intervals):
    devices_count = len(mapping.get("devices", {})) if isinstance(mapping, dict) else 0
    auto_text = "ON" if auto_state else "OFF"
    sync_value = "N/A"
    sync_sub = "Thingsboard"
    sync_class = "kpi-value kpi-sync"
    script_value = "N/A"
    script_sub = "Script handler"
    script_class = "kpi-value kpi-sync"
    alarms_value = "0"
    alarms_sub = "Mapped devices"

    if mapping:
        try:
            health = fetch_thingsboard_health()
            if health.get("connected"):
                sync_value = "ONLINE"
                sync_sub = "Thingsboard connected"
                sync_class = "kpi-value kpi-sync kpi-sync-online"
            else:
                sync_value = "OFFLINE"
                sync_sub = health.get("detail") or "Disconnected"
                sync_class = "kpi-value kpi-sync kpi-sync-offline"
        except Exception:
            sync_value = "OFFLINE"
            sync_sub = "Unavailable"
            sync_class = "kpi-value kpi-sync kpi-sync-offline"

        try:
            health = fetch_script_handler_health()
            status = str(health.get("status") or "unknown").lower()
            enabled = bool(health.get("enabled", True))
            last_success = health.get("last_success_ts")
            last_error = health.get("last_error")
            if not enabled or status == "disabled":
                script_value = "PAUSED"
                script_sub = "Disabled in config"
                script_class = "kpi-value kpi-sync kpi-sync-offline"
            elif status in {"ok", "running"}:
                script_value = "LIVE"
                script_class = "kpi-value kpi-sync kpi-sync-online"
                if last_success:
                    script_sub = f"Last run {datetime.fromtimestamp(last_success / 1000).strftime('%H:%M')}"
                else:
                    script_sub = "Running"
            elif status == "error":
                script_value = "ERROR"
                script_class = "kpi-value kpi-sync kpi-sync-offline"
                script_sub = last_error or "Check logs"
            else:
                script_value = status.upper()
                script_sub = "Unknown state"
        except Exception:
            script_value = "OFFLINE"
            script_sub = "Unreachable"
            script_class = "kpi-value kpi-sync kpi-sync-offline"

        try:
            summary = fetch_alarms_summary("ACTIVE")
            total = int(summary.get("total") or 0)
            failed = int(summary.get("failed") or 0)
            alarms_value = str(total)
            if total == 0:
                alarms_sub = "No active alarms"
            else:
                alarms_sub = "Active on mapped devices"
            if failed:
                alarms_sub = f"{alarms_sub} · {failed} source(s) unavailable"
        except Exception:
            alarms_value = "N/A"
            alarms_sub = "Alarm service unavailable"

    return (
        str(devices_count),
        auto_text,
        sync_value,
        sync_class,
        sync_sub,
        script_value,
        script_class,
        script_sub,
        alarms_value,
        alarms_sub,
    )


@dash_app.callback(
    Output("script-pulse-details", "children"),
    Input("mapping-store", "data"),
    Input("tb-health-interval", "n_intervals"),
)
def update_script_pulse_details(mapping, n_intervals):
    if not mapping:
        return html.Div("Waiting for mapping...")
    try:
        status = fetch_script_handler_status()
    except Exception:
        return html.Div("Script handler unreachable.")

    def fmt_ts(value):
        if not value:
            return "n/a"
        try:
            return datetime.fromtimestamp(value / 1000).strftime("%H:%M:%S")
        except Exception:
            return "n/a"

    lines = [
        f"Mode: {status.get('mode', 'n/a')}",
        f"Enabled: {status.get('enabled', 'n/a')}",
        f"State: {status.get('status', 'n/a')}",
        f"Running job: {status.get('running_job_id', 'n/a')}",
        f"Last cycle: {fmt_ts(status.get('last_cycle_ts'))}",
        f"Last success: {fmt_ts(status.get('last_success_ts'))}",
        f"Last items: {status.get('last_items', 'n/a')}",
        f"Last duration: {status.get('last_duration_ms', 'n/a')} ms",
    ]
    last_error = status.get("last_error")
    if last_error:
        lines.append(f"Last error: {last_error}")

    return [html.Div(line) for line in lines]


@dash_app.callback(
    Output("script-control-status", "children"),
    Output("script-control-status", "className"),
    Output("script-job-id", "data"),
    Input("script-run-btn", "n_clicks"),
    Input("script-run-async-btn", "n_clicks"),
    Input("script-kill-btn", "n_clicks"),
    Input("script-reload-btn", "n_clicks"),
    State("script-job-id", "data"),
    prevent_initial_call=True,
)
def on_script_handler_control(run_clicks, run_async_clicks, kill_clicks, reload_clicks, job_id):
    if not callback_context.triggered:
        return no_update, no_update, no_update
    trigger = callback_context.triggered[0]
    trigger_id = callback_context.triggered_id
    if not trigger or not trigger.get("value"):
        return no_update, no_update, no_update

    base_status_class = "telemetry-status small mt-2"
    error_status_class = "telemetry-status small mt-2 error"

    if trigger_id == "script-run-btn":
        try:
            result = post_script_handler_run()
            if result.get("status") == "error":
                return f"Run failed: {result.get('detail')}", error_status_class, ""
            items = result.get("items", 0)
            duration = result.get("duration_ms", "n/a")
            return f"Run ok · {items} items · {duration} ms", base_status_class, ""
        except Exception as exc:
            return f"Run failed: {exc}", error_status_class, ""

    if trigger_id == "script-run-async-btn":
        try:
            result = post_script_handler_run_async()
            if result.get("status") == "error":
                return f"Async failed: {result.get('detail')}", error_status_class, ""
            job_id = result.get("jobId") or ""
            return f"Async queued · job {job_id}", base_status_class, job_id
        except Exception as exc:
            return f"Async failed: {exc}", error_status_class, ""

    if trigger_id == "script-kill-btn":
        try:
            result = post_script_handler_kill(job_id if job_id else None)
            if result.get("status") == "error":
                return f"Kill failed: {result.get('detail')}", error_status_class, job_id
            return "Kill requested", base_status_class, job_id
        except Exception as exc:
            return f"Kill failed: {exc}", error_status_class, job_id

    if trigger_id == "script-reload-btn":
        try:
            result = post_script_handler_reload()
            if result.get("status") == "error":
                return f"Reload failed: {result.get('detail')}", error_status_class, ""
            return "Mapping reloaded", base_status_class, ""
        except Exception as exc:
            return f"Reload failed: {exc}", error_status_class, ""

    return no_update, no_update, no_update


@dash_app.callback(
    Output("script-job-status", "children"),
    Input("script-job-id", "data"),
    Input("tb-health-interval", "n_intervals"),
)
def update_script_job_status(job_id, n_intervals):
    if not job_id:
        return ""
    try:
        job = fetch_script_handler_job(job_id)
    except Exception:
        return "Job status unavailable."

    status = str(job.get("status") or "unknown")
    result = job.get("result") or {}
    if status == "done":
        items = result.get("items", "n/a")
        duration = result.get("duration_ms", "n/a")
        return f"Job {job_id} · done · {items} items · {duration} ms"
    if status == "error":
        detail = ""
        if isinstance(result, dict):
            detail = result.get("detail") or ""
        return f"Job {job_id} · error {detail}".strip()
    return f"Job {job_id} · {status}"


@dash_app.callback(
    Output("alarms-list", "children"),
    Output("alarms-status", "children"),
    Input("mapping-store", "data"),
    Input("tb-health-interval", "n_intervals"),
)
def update_alarms_panel(mapping, n_intervals):
    if not mapping:
        return html.Div("Loading alarms...", className="text-muted small"), "Loading"
    try:
        payload = fetch_alarms_recent("ACTIVE", 8)
    except Exception:
        return html.Div("Alarm service unavailable", className="text-muted small"), "Unavailable"

    alarms = payload.get("alarms") or []
    failed = int(payload.get("failed") or 0)
    timestamp = payload.get("timestamp")
    status = "Updated"
    if timestamp:
        status = datetime.fromtimestamp(timestamp / 1000).strftime("%H:%M")
    if failed:
        status = f"{status} · {failed} source(s) down"
    return build_alarm_nodes(alarms), status


@dash_app.callback(
    Output("alarms-action-status", "children"),
    Input({"type": "alarm-action", "action": "ack", "alarmId": ALL}, "n_clicks"),
    Input({"type": "alarm-action", "action": "clear", "alarmId": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def on_alarm_action(ack_clicks, clear_clicks):
    if not callback_context.triggered:
        return no_update
    trigger = callback_context.triggered[0]
    if not trigger:
        return no_update
    if not trigger.get("value"):
        return no_update
    trigger_id = callback_context.triggered_id
    if not isinstance(trigger_id, dict):
        return no_update
    alarm_id = trigger_id.get("alarmId")
    action = trigger_id.get("action")
    if not alarm_id or not action:
        return no_update
    try:
        if int(trigger.get("value") or 0) < 1:
            return no_update
    except (TypeError, ValueError):
        return no_update
    try:
        post_alarm_action(alarm_id, action)
        return f"{action} ok"
    except Exception as exc:
        return f"{action} failed: {exc}"


@dash_app.callback(
    Output("viewer-command", "data", allow_duplicate=True),
    Input("device-dropdown", "value"),
    prevent_initial_call=True,
)
def on_select_device(device_id):
    if not device_id:
        return no_update
    if isinstance(device_id, list):
        return {"type": "selectDevices", "deviceIds": device_id}
    return {"type": "selectDevices", "deviceIds": [device_id]}


@dash_app.callback(
    Output("viewer-command", "data", allow_duplicate=True),
    Input("reset-selection-btn", "n_clicks"),
    prevent_initial_call=True,
)
def on_reset_selection(n_clicks):
    if not n_clicks:
        return no_update
    return {"type": "resetSelection"}


@dash_app.callback(
    Output("viewer-command", "data", allow_duplicate=True),
    Input("focus-device-btn", "n_clicks"),
    prevent_initial_call=True,
)
def on_focus_device(n_clicks):
    if not n_clicks:
        return no_update
    return {"type": "focusModel"}

@dash_app.callback(
    Output("telemetry-tabs", "children"),
    Output("telemetry-status", "children"),
    Output("telemetry-status", "className"),
    Input("telemetry-load-btn", "n_clicks"),
    Input("device-dropdown", "value"),
    Input("telemetry-auto-interval", "n_intervals"),
    Input("telemetry-auto-state", "data"),
    State("mapping-store", "data"),
    State("telemetry-key", "value"),
    State("telemetry-limit", "value"),
    State("telemetry-hours", "value"),
    State("telemetry-days", "value"),
    State("telemetry-period", "value"),
    State("telemetry-range", "start_date"),
    State("telemetry-range", "end_date"),
    State("telemetry-agg", "value"),
    State("telemetry-agg-interval-count", "value"),
    State("telemetry-agg-interval-unit", "value"),
    State("telemetry-keys", "value"),
)
def on_load_telemetry(
    n_clicks,
    selected_device,
    auto_tick,
    auto_enabled_input,
    mapping,
    key,
    limit,
    hours,
    days,
    period_mode,
    range_start,
    range_end,
    agg,
    agg_interval_count,
    agg_interval_unit,
    keys_input,
):
    base_status_class = "telemetry-status small mt-2"
    error_status_class = "telemetry-status small mt-2 error"
    auto_enabled = bool(auto_enabled_input)
    if auto_tick and not auto_enabled:
        return no_update, "", base_status_class
    if not n_clicks and not selected_device and not auto_tick and not auto_enabled_input:
        return no_update, "", base_status_class
    if not mapping:
        return [], "Mapping not loaded.", error_status_class
    if not selected_device:
        return [], "Select a device first.", error_status_class
    try:
        start_ts = None
        end_ts = None
        hours_value = int(hours or 24)
        if period_mode == "days":
            hours_value = int(days or 1) * 24
        if period_mode == "range" and range_start and range_end:
            start_ts = int(datetime.fromisoformat(range_start).timestamp() * 1000)
            end_ts = int(datetime.fromisoformat(range_end).timestamp() * 1000 + 86399 * 1000)

        keys_value = None
        if keys_input:
            keys_value = ",".join([item.strip() for item in keys_input.split(",") if item.strip()])

        interval_value = None
        if agg_interval_count and agg_interval_unit:
            unit_ms = {
                "minute": 60_000,
                "hour": 3_600_000,
                "day": 86_400_000,
                "week": 7 * 86_400_000,
                "month": 30 * 86_400_000,
                "year": 365 * 86_400_000,
            }.get(str(agg_interval_unit).lower())
            try:
                count = int(agg_interval_count)
            except (TypeError, ValueError):
                count = 0
            if unit_ms and count > 0:
                interval_value = str(unit_ms * count)

        device_ids = selected_device if isinstance(selected_device, list) else [selected_device]
        tabs = []
        total_points = 0

        for device_id in device_ids:
            payload = fetch_telemetry(
                mapping,
                device_id,
                keys_value or key,
                int(limit or 24),
                hours_value,
                agg,
                start_ts,
                end_ts,
                interval_value,
            )

            fig = go.Figure()
            if "series" in payload:
                series = payload.get("series") or {}
                for name, points in series.items():
                    x_vals = [datetime.fromtimestamp(p.get("ts") / 1000) for p in points if p.get("ts") is not None]
                    y_vals = [p.get("value") for p in points]
                    fig.add_trace(
                        go.Scatter(
                            x=x_vals,
                            y=y_vals,
                            mode="lines+markers",
                            line={"width": 3, "shape": "spline", "smoothing": 0.6},
                            marker={"size": 6},
                            name=name,
                            hovertemplate="%{x|%H:%M:%S}<br>value=%{y}<extra></extra>",
                        )
                    )
                total_points += sum(len(points) for points in series.values())
            else:
                points = payload.get("points", [])
                x_vals = [datetime.fromtimestamp(p.get("ts") / 1000) for p in points if p.get("ts") is not None]
                y_vals = [p.get("value") for p in points]
                fig.add_trace(
                    go.Scatter(
                        x=x_vals,
                        y=y_vals,
                        mode="lines+markers",
                        line={"color": "#2563eb", "width": 3, "shape": "spline", "smoothing": 0.6},
                        marker={"size": 6, "color": "#1d4ed8"},
                        hovertemplate="%{x|%H:%M:%S}<br>value=%{y}<extra></extra>",
                    )
                )
                total_points += len(points)

            fig.update_layout(
                margin=dict(l=20, r=20, t=30, b=20),
                xaxis_title="Time",
                yaxis_title=payload.get("key", "value"),
                plot_bgcolor="#f8fafc",
                paper_bgcolor="white",
                font={"color": "#0f172a"},
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            fig.update_xaxes(
                showgrid=True,
                gridcolor="rgba(148, 163, 184, 0.3)",
                zeroline=False,
            )
            fig.update_yaxes(
                showgrid=True,
                gridcolor="rgba(148, 163, 184, 0.3)",
                zeroline=False,
            )

            tabs.append(
                dcc.Tab(
                    label=device_id,
                    children=[dcc.Graph(figure=fig)],
                )
            )

        return tabs, f"Loaded {total_points} points.", base_status_class
    except Exception as exc:
        return [], f"Failed to load telemetry: {exc}", error_status_class

dash_app.clientside_callback(
    """
    function(command) {
        if (!command) {
            return "";
        }
        const frame = document.getElementById("viewer-frame");
        if (frame && frame.contentWindow) {
            frame.contentWindow.postMessage(command, "*");
        }
        return "";
    }
    """,
    Output("viewer-command-sink", "children"),
    Input("viewer-command", "data"),
)


dash_app.clientside_callback(
    """
    function(n) {
        const evt = window.__viewerEvent;
        if (!evt) {
            return window.dash_clientside.no_update;
        }
        window.__viewerEvent = null;
        return evt;
    }
    """,
    Output("viewer-event-store", "data"),
    Input("viewer-event-poll", "n_intervals"),
)


dash_app.clientside_callback(
    """
    function(n) {
        const evt = window.__viewerLog;
        if (!evt) {
            return window.dash_clientside.no_update;
        }
        window.__viewerLog = null;
        return evt;
    }
    """,
    Output("viewer-log-store", "data"),
    Input("viewer-event-poll", "n_intervals"),
)

@dash_app.callback(
    Output("device-dropdown", "value"),
    Output("device-details", "children"),
    Input("viewer-event-store", "data"),
    prevent_initial_call=True,
)
def on_viewer_selection(event_data):
    if not event_data:
        return no_update, no_update
    device_id = event_data.get("deviceId")
    details = event_data.get("details") or []
    detail_nodes = [html.P(item, style={"margin": "4px 0"}) for item in details]
    return [device_id], detail_nodes


@dash_app.callback(
    Output("viewer-logs", "children"),
    Input("viewer-log-store", "data"),
    prevent_initial_call=True,
)
def on_viewer_log(event_data):
    if not event_data:
        return no_update
    payload = event_data.get("payload") or {}
    lines = [
        f"expressID: {payload.get('expressID', '')}",
        f"GUID: {payload.get('guid', '')}",
        f"IFC type: {payload.get('ifcType', '')}",
        f"Name: {payload.get('name', '')}",
    ]
    return html.Div(
        [
            html.Div("Viewer pick", style={"fontWeight": "600", "marginBottom": "4px"}),
            html.Ul([html.Li(line) for line in lines], style={"margin": "0 0 0 16px"}),
        ]
    )


@dash_app.callback(
    Output("device-info", "children"),
    Input("device-dropdown", "value"),
    State("mapping-store", "data"),
)
def on_device_info(device_id, mapping):
    if not device_id or not mapping:
        return no_update
    devices = mapping.get("devices", {})
    device_ids = device_id if isinstance(device_id, list) else [device_id]
    blocks = []
    for dev_id in device_ids:
        device = devices.get(dev_id) or {}
        connector = device.get("connector", {}) if isinstance(device, dict) else {}
        blocks.append(
            html.Div(
                style={"marginBottom": "8px", "paddingBottom": "6px", "borderBottom": "1px solid #e2e8f0"},
                children=[
                    html.P(f"id: {dev_id}", style={"margin": "4px 0", "fontWeight": "600"}),
                    html.P(f"type: {device.get('type', '')}", style={"margin": "4px 0"}),
                    html.P(f"connector.type: {connector.get('type', '')}", style={"margin": "4px 0"}),
                    html.P(f"connector.deviceId: {connector.get('deviceId', '')}", style={"margin": "4px 0"}),
                    html.P(
                        f"connector.telemetryKey: {connector.get('telemetryKey', '')}",
                        style={"margin": "4px 0"},
                    ),
                    html.P(
                        f"ifcGuids: {', '.join(device.get('ifcGuids', []) or [])}",
                        style={"margin": "4px 0"},
                    ),
                ],
            )
        )
    return blocks

@dash_app.callback(
    Output("telemetry-advanced", "style"),
    Output("telemetry-advanced-state", "data"),
    Input("telemetry-advanced-btn", "n_clicks"),
    State("telemetry-advanced-state", "data"),
)
def toggle_telemetry_advanced(n_clicks, is_open):
    if not n_clicks:
        return {"marginTop": "12px", "display": "none"}, is_open
    next_state = not bool(is_open)
    style = {"marginTop": "12px", "display": "block" if next_state else "none"}
    return style, next_state


@dash_app.callback(
    Output("telemetry-auto-state", "data"),
    Output("telemetry-auto-interval", "disabled"),
    Output("telemetry-live-indicator", "children"),
    Output("telemetry-live-indicator", "style"),
    Input("telemetry-auto-btn", "n_clicks"),
    State("telemetry-auto-state", "data"),
)
def toggle_auto_refresh(n_clicks, is_enabled):
    if not n_clicks:
        status = "live" if is_enabled else "paused"
        style = {
            "padding": "4px 8px",
            "borderRadius": "999px",
            "background": "#16a34a" if is_enabled else "#e5e7eb",
            "color": "white" if is_enabled else "#374151",
            "fontSize": "12px",
        }
        return is_enabled, not bool(is_enabled), status, style
    next_state = not bool(is_enabled)
    status = "live" if next_state else "paused"
    style = {
        "padding": "4px 8px",
        "borderRadius": "999px",
        "background": "#16a34a" if next_state else "#e5e7eb",
        "color": "white" if next_state else "#374151",
        "fontSize": "12px",
    }
    return next_state, not next_state, status, style

@dash_app.callback(
    Output("telemetry-hours", "style"),
    Output("telemetry-days", "style"),
    Output("telemetry-range", "style"),
    Input("telemetry-period", "value"),
)
def toggle_period_fields(mode):
    if mode == "days":
        return {"display": "none"}, {"width": "100%", "marginTop": "8px"}, {"display": "none"}
    if mode == "range":
        return {"display": "none"}, {"display": "none"}, {"marginTop": "8px"}
    return {"width": "100%"}, {"display": "none"}, {"display": "none"}


@dash_app.callback(
    Output("telemetry-auto-interval", "interval"),
    Input("telemetry-interval", "value"),
)
def update_auto_interval(seconds):
    try:
        value = int(seconds or 10)
    except (TypeError, ValueError):
        value = 10
    value = max(2, min(120, value))
    return value * 1000


def panel_style(visible: bool, base: Dict[str, Any]) -> Dict[str, Any]:
    style = dict(base)
    style["display"] = "block" if visible else "none"
    return style


@dash_app.callback(
    Output("devices-body", "style"),
    Output("devices-panel-state", "data"),
    Input("toggle-devices-btn", "n_clicks"),
    State("devices-panel-state", "data"),
    State("devices-body", "style"),
)
def toggle_devices_panel(n_clicks, is_open, current_style):
    if not n_clicks:
        return current_style, is_open
    next_state = not bool(is_open)
    return panel_style(next_state, current_style or {}), next_state


@dash_app.callback(
    Output("alarms-body", "style"),
    Output("alarms-panel-state", "data"),
    Input("toggle-alarms-btn", "n_clicks"),
    State("alarms-panel-state", "data"),
    State("alarms-body", "style"),
)
def toggle_alarms_panel(n_clicks, is_open, current_style):
    if not n_clicks:
        return current_style, is_open
    next_state = not bool(is_open)
    return panel_style(next_state, current_style or {}), next_state


@dash_app.callback(
    Output("awareness-body", "style"),
    Output("awareness-panel-state", "data"),
    Input("toggle-awareness-btn", "n_clicks"),
    State("awareness-panel-state", "data"),
    State("awareness-body", "style"),
)
def toggle_awareness_panel(n_clicks, is_open, current_style):
    if not n_clicks:
        return current_style, is_open
    next_state = not bool(is_open)
    return panel_style(next_state, current_style or {}), next_state


@dash_app.callback(
    Output("telemetry-body", "style"),
    Output("telemetry-panel-state", "data"),
    Input("toggle-telemetry-btn", "n_clicks"),
    State("telemetry-panel-state", "data"),
    State("telemetry-body", "style"),
)
def toggle_telemetry_panel(n_clicks, is_open, current_style):
    if not n_clicks:
        return current_style, is_open
    next_state = not bool(is_open)
    return panel_style(next_state, current_style or {}), next_state


@dash_app.callback(
    Output("viewer-body", "style"),
    Output("viewer-panel-state", "data"),
    Input("toggle-viewer-btn", "n_clicks"),
    State("viewer-panel-state", "data"),
    State("viewer-body", "style"),
)
def toggle_viewer_panel(n_clicks, is_open, current_style):
    if not n_clicks:
        return current_style, is_open
    next_state = not bool(is_open)
    return panel_style(next_state, current_style or {}), next_state


@dash_app.callback(
    Output("telemetry-col", "style"),
    Output("viewer-col", "style"),
    Output("telemetry-panel", "className"),
    Output("telemetry-header", "className"),
    Output("viewer-panel", "className"),
    Output("viewer-header", "className"),
    Input("telemetry-panel-state", "data"),
    Input("viewer-panel-state", "data"),
)
def resize_main_panels(telemetry_open, viewer_open):
    telemetry_style = {"minWidth": 0}
    viewer_style = {"minWidth": 0}
    telemetry_header = "d-flex justify-content-between align-items-center"
    viewer_header = "d-flex justify-content-between align-items-center"

    if not telemetry_open and viewer_open:
        telemetry_style = {"flex": "0 0 72px", "maxWidth": "72px", "minWidth": "72px"}
        viewer_style = {"flex": "1 1 auto", "maxWidth": "none", "minWidth": 0}
        telemetry_header = f"{telemetry_header} panel-collapsed"
    elif telemetry_open and not viewer_open:
        viewer_style = {"flex": "0 0 72px", "maxWidth": "72px", "minWidth": "72px"}
        telemetry_style = {"flex": "1 1 auto", "maxWidth": "none", "minWidth": 0}
        viewer_header = f"{viewer_header} panel-collapsed"
    elif not telemetry_open and not viewer_open:
        telemetry_style = {"flex": "0 0 72px", "maxWidth": "72px", "minWidth": "72px"}
        viewer_style = {"flex": "0 0 72px", "maxWidth": "72px", "minWidth": "72px"}
        telemetry_header = f"{telemetry_header} panel-collapsed"
        viewer_header = f"{viewer_header} panel-collapsed"

    return (
        telemetry_style,
        viewer_style,
        "glass-card h-100",
        telemetry_header,
        "glass-card",
        viewer_header,
    )


if __name__ == "__main__":
    dash_app.run_server(host="0.0.0.0", port=8050, debug=False)



