import os
from datetime import datetime
from typing import Any, Dict, List

import httpx
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State, no_update

MIDDLEWARE_URL = os.getenv("MIDDLEWARE_URL", "http://localhost:8000").rstrip("/")
DASH_VIEWER_URL = os.getenv("DASH_VIEWER_URL", "http://localhost:8081").rstrip("/")


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


def fetch_telemetry(mapping: Dict[str, Any], device_id: str, key: str | None, limit: int, hours: int) -> Dict[str, Any]:
    if not mapping:
        raise RuntimeError("Mapping not loaded")
    url = f"{MIDDLEWARE_URL}/devices/{device_id}/telemetry"
    params = {"limit": limit, "hours": hours}
    if key:
        params["key"] = key
    with httpx.Client(timeout=10) as client:
        response = client.get(url, params=params)
    if response.status_code != 200:
        raise RuntimeError(f"Telemetry fetch failed: {response.status_code}")
    return response.json()


dash_app = Dash(__name__)

dash_app.layout = html.Div(
    style={
        "fontFamily": "Space Grotesk, Inter, system-ui, sans-serif",
        "background": "linear-gradient(135deg, #f8fafc, #eef2f7)",
        "minHeight": "100vh",
        "padding": "28px",
    },
    children=[
        html.H2("BIM-IOT Intelligence Hub", style={"marginBottom": "6px", "letterSpacing": "0.4px"}),
        html.P(
            "Unified operational intelligence for data-driven decisions, live telemetry, and spatial context.",
            style={"color": "#475569", "marginTop": "0"},
        ),
        html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 2fr", "gap": "18px"},
            children=[
                html.Div(
                    style={
                        "background": "white",
                        "borderRadius": "12px",
                        "padding": "18px",
                        "boxShadow": "0 12px 28px rgba(15, 23, 42, 0.08)",
                        "border": "1px solid rgba(148, 163, 184, 0.2)",
                    },
                    children=[
                        html.Div(
                            style={"display": "flex", "gap": "8px", "flexWrap": "wrap"},
                            children=[
                                html.Button("Refresh mapping", id="mapping-refresh-btn", style={"background": "#1d4ed8", "color": "white", "border": "none", "padding": "8px 12px", "borderRadius": "8px"}),
                                html.Button("Reset selection", id="reset-selection-btn", style={"background": "#e2e8f0", "color": "#0f172a", "border": "none", "padding": "8px 12px", "borderRadius": "8px"}),
                                html.Button("Focus", id="focus-device-btn", style={"background": "#0f766e", "color": "white", "border": "none", "padding": "8px 12px", "borderRadius": "8px"}),
                            ],
                        ),
                        html.Div(id="mapping-status", style={"marginTop": "8px", "color": "#4b5563"}),
                        html.H4("Device", style={"marginTop": "16px"}),
                        dcc.Dropdown(id="device-dropdown", options=[], value=None),
                        html.Div(id="device-info", style={"marginTop": "12px", "color": "#334155", "fontSize": "13px"}),
                        html.Div(id="device-details", style={"marginTop": "12px", "color": "#334155", "fontSize": "13px"}),
                    ],
                ),
                html.Div(
                    style={
                        "background": "white",
                        "borderRadius": "12px",
                        "padding": "18px",
                        "boxShadow": "0 12px 28px rgba(15, 23, 42, 0.08)",
                        "border": "1px solid rgba(148, 163, 184, 0.2)",
                    },
                    children=[
                        html.Div(
                            id="telemetry",
                            children=[
                                html.H4("Telemetry", style={"marginTop": "0", "color": "#0f172a"}),
                                html.Div(
                                    style={"display": "flex", "gap": "8px", "alignItems": "center", "flexWrap": "wrap"},
                                    children=[
                                        html.Button("Refresh telemetry", id="telemetry-load-btn", style={"background": "#1d4ed8", "color": "white", "border": "none", "padding": "8px 12px", "borderRadius": "8px"}),
                                        html.Button("Advanced options", id="telemetry-advanced-btn", style={"background": "#e2e8f0", "color": "#0f172a", "border": "none", "padding": "8px 12px", "borderRadius": "8px"}),
                                        html.Button("Auto refresh", id="telemetry-auto-btn", style={"background": "#0f766e", "color": "white", "border": "none", "padding": "8px 12px", "borderRadius": "8px"}),
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
                                        ),
                                    ],
                                ),
                                html.Div(
                                    id="telemetry-advanced",
                                    style={"marginTop": "12px", "display": "none"},
                                    children=[
                                        dcc.Input(
                                            id="telemetry-key",
                                            type="text",
                                            placeholder="Override key (optional)",
                                            style={"width": "100%"},
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
                                                    max=200,
                                                    value=24,
                                                    style={"width": "100%"},
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                html.Div(id="telemetry-status", style={"marginTop": "8px", "color": "#4b5563"}),
                            ],
                        ),
                        dcc.Graph(id="telemetry-graph", figure=go.Figure()),
                    ],
                ),
            ],
        ),
        html.H3("Viewer 3D (Vite)", style={"marginTop": "24px"}),
        html.Iframe(
            id="viewer-frame",
            src=DASH_VIEWER_URL,
            style={
                "width": "100%",
                "height": "600px",
                "border": "1px solid #e5e7eb",
                "borderRadius": "12px",
                "background": "white",
            },
        ),
        dcc.Store(id="mapping-store"),
        dcc.Store(id="viewer-command"),
        dcc.Store(id="viewer-event-store"),
        dcc.Store(id="telemetry-advanced-state", data=False),
        dcc.Store(id="telemetry-auto-state", data=False),
        dcc.Interval(id="telemetry-auto-interval", interval=10000, n_intervals=0, disabled=True),
        dcc.Interval(id="viewer-event-poll", interval=500, n_intervals=0),
        html.Script(
            """
            window.__viewerEvent = null;
            window.addEventListener("message", (event) => {
              const data = event.data;
              if (!data || typeof data !== "object") return;
              if (data.type === "viewerSelection") {
                window.__viewerEvent = data;
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
)
def on_refresh_mapping(n_clicks):
    if not n_clicks:
        return no_update, no_update, "Mapping not loaded. Click refresh.", no_update
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
    return {"type": "selectDevice", "deviceId": device_id}


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
    State("device-dropdown", "value"),
    prevent_initial_call=True,
)
def on_focus_device(n_clicks, device_id):
    if not n_clicks or not device_id:
        return no_update
    return {"type": "focusDevice", "deviceId": device_id}


@dash_app.callback(
    Output("telemetry-graph", "figure"),
    Output("telemetry-status", "children"),
    Input("telemetry-load-btn", "n_clicks"),
    Input("device-dropdown", "value"),
    Input("telemetry-auto-interval", "n_intervals"),
    State("mapping-store", "data"),
    State("device-dropdown", "value"),
    State("telemetry-key", "value"),
    State("telemetry-limit", "value"),
    State("telemetry-hours", "value"),
    State("telemetry-auto-state", "data"),
)
def on_load_telemetry(
    n_clicks,
    selected_device,
    auto_tick,
    mapping,
    device_id,
    key,
    limit,
    hours,
    auto_enabled,
):
    if auto_tick and not auto_enabled:
        return no_update, ""
    if not n_clicks and not selected_device and not auto_tick:
        return no_update, ""
    if not mapping:
        return go.Figure(), "Mapping not loaded."
    if not device_id:
        return go.Figure(), "Select a device first."
    try:
        payload = fetch_telemetry(mapping, device_id, key, int(limit or 24), int(hours or 24))
        points = payload.get("points", [])
        if not points:
            return go.Figure(), "No telemetry data."
        x_vals = [datetime.fromtimestamp(p.get("ts") / 1000) for p in points if p.get("ts") is not None]
        y_vals = [p.get("value") for p in points]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="lines+markers",
                line={"color": "#2563eb", "width": 3},
                marker={"size": 6, "color": "#1d4ed8"},
                hovertemplate="%{x|%H:%M:%S}<br>value=%{y}<extra></extra>",
            )
        )
        fig.update_layout(
            margin=dict(l=20, r=20, t=30, b=20),
            xaxis_title="Time",
            yaxis_title=payload.get("key", "value"),
            plot_bgcolor="#f8fafc",
            paper_bgcolor="white",
            font={"color": "#0f172a"},
            hovermode="x unified",
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
        return fig, f"Loaded {len(points)} points."
    except Exception as exc:
        return go.Figure(), f"Failed to load telemetry: {exc}"


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
    return device_id, detail_nodes


@dash_app.callback(
    Output("device-info", "children"),
    Input("device-dropdown", "value"),
    State("mapping-store", "data"),
)
def on_device_info(device_id, mapping):
    if not device_id or not mapping:
        return no_update
    devices = mapping.get("devices", {})
    device = devices.get(device_id) or {}
    connector = device.get("connector", {}) if isinstance(device, dict) else {}
    info = [
        html.P(f"type: {device.get('type', '')}", style={"margin": "4px 0"}),
        html.P(f"connector.type: {connector.get('type', '')}", style={"margin": "4px 0"}),
        html.P(f"connector.deviceId: {connector.get('deviceId', '')}", style={"margin": "4px 0"}),
        html.P(f"connector.telemetryKey: {connector.get('telemetryKey', '')}", style={"margin": "4px 0"}),
        html.P(f"ifcGuids: {', '.join(device.get('ifcGuids', []) or [])}", style={"margin": "4px 0"}),
    ]
    return info


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


if __name__ == "__main__":
    dash_app.run_server(host="0.0.0.0", port=8050, debug=False)
