
import os
from datetime import datetime
from typing import Any, Dict, List

import httpx
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import Dash, dcc, html, Input, Output, State, no_update

MIDDLEWARE_URL = os.getenv("MIDDLEWARE_URL", "http://localhost:8000").rstrip("/")
DASH_VIEWER_URL = os.getenv("DASH_VIEWER_URL", "http://localhost:8081").rstrip("/")
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
    interval: int | None = None,
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
        raise RuntimeError(f"Telemetry fetch failed: {response.status_code}")
    return response.json()


dash_app = Dash(__name__, external_stylesheets=[dbc.themes.LUX, FONT_URL])


dash_app.layout = html.Div(
    style={
        "fontFamily": "'Space Grotesk', 'Segoe UI', sans-serif",
        "background": "radial-gradient(circle at top, #f8fafc 0%, #eef2ff 35%, #f8fafc 70%)",
        "minHeight": "100vh",
    },
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
                    className="g-3",
                    children=[
                        dbc.Col(
                            md=4,
                            children=[
                                dbc.Card(
                                    id="devices-panel",
                                    className="shadow-sm border-0 h-100",
                                    children=[
                                        dbc.CardHeader(
                                            className="d-flex justify-content-between align-items-center",
                                            children=[
                                                html.Div("Devices", className="fw-semibold"),
                                                dbc.Button(
                                                    "▾",
                                                    id="toggle-devices-btn",
                                                    size="sm",
                                                    color="secondary",
                                                    outline=True,
                                                ),
                                            ],
                                        ),
                                        dbc.CardBody(
                                            id="devices-body",
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
                        dbc.Col(
                            md=8,
                            children=[
                                dbc.Card(
                                    id="telemetry-panel",
                                    className="shadow-sm border-0 h-100",
                                    children=[
                                        dbc.CardHeader(
                                            className="d-flex justify-content-between align-items-center",
                                            children=[
                                                html.Div("Telemetry", className="fw-semibold"),
                                                dbc.Button(
                                                    "▾",
                                                    id="toggle-telemetry-btn",
                                                    size="sm",
                                                    color="secondary",
                                                    outline=True,
                                                ),
                                            ],
                                        ),
                                        dbc.CardBody(
                                            id="telemetry-body",
                                            children=[
                                                dbc.Row(
                                                    className="g-2 align-items-center",
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
                                                                            "Aggregation interval (seconds)",
                                                                            className="small text-muted mt-2",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="telemetry-agg-interval",
                                                                            type="number",
                                                                            min=1,
                                                                            max=3600,
                                                                            value=60,
                                                                            style={
                                                                                "width": "100%",
                                                                                "marginTop": "8px",
                                                                            },
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
                                                    className="text-muted small mt-2",
                                                ),
                                                dcc.Tabs(id="telemetry-tabs", children=[], className="mt-3"),
                                            ],
                                        ),
                                    ],
                                )
                            ],
                        ),
                    ],
                ),
                dbc.Row(
                    className="g-3 mt-1",
                    children=[
                        dbc.Col(
                            children=[
                                dbc.Card(
                                    id="viewer-panel",
                                    className="shadow-sm border-0",
                                    children=[
                                        dbc.CardHeader(
                                            className="d-flex justify-content-between align-items-center",
                                            children=[
                                                html.Div("Viewer 3D", className="fw-semibold"),
                                                dbc.Button(
                                                    "▾",
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
        dcc.Store(id="telemetry-panel-state", data=True),
        dcc.Store(id="viewer-panel-state", data=True),
        dcc.Store(id="telemetry-advanced-state", data=False),
        dcc.Store(id="telemetry-auto-state", data=False),
        dcc.Interval(id="mapping-init", interval=500, n_intervals=0, max_intervals=1),
        dcc.Interval(id="telemetry-auto-interval", interval=10000, n_intervals=0, disabled=True),
        dcc.Interval(id="viewer-event-poll", interval=500, n_intervals=0),
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
    State("telemetry-agg-interval", "value"),
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
    agg_interval,
    keys_input,
):
    auto_enabled = bool(auto_enabled_input)
    if auto_tick and not auto_enabled:
        return no_update, ""
    if not n_clicks and not selected_device and not auto_tick and not auto_enabled_input:
        return no_update, ""
    if not mapping:
        return [], "Mapping not loaded."
    if not selected_device:
        return [], "Select a device first."
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

        interval_ms = None
        try:
            interval_ms = int(agg_interval or 0) * 1000
        except (TypeError, ValueError):
            interval_ms = None

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
                interval_ms,
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

        return tabs, f"Loaded {total_points} points."
    except Exception as exc:
        return [], f"Failed to load telemetry: {exc}"

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


if __name__ == "__main__":
    dash_app.run_server(host="0.0.0.0", port=8050, debug=False)
