"""Dashboard builder - custom widget-based dashboards.

Users can create dashboards with configurable widgets (stats, charts,
tables) arranged in a grid layout. Dashboards are persisted to the
database and can be shared across users.
"""

import json
import logging
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("TRACES_DB_PATH", "traces.db")


def _ensure_dashboards_table():
    """Create dashboards tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dashboards (
                dashboard_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                owner_id TEXT,
                layout TEXT NOT NULL DEFAULT '[]',
                is_public INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_widgets (
                widget_id TEXT PRIMARY KEY,
                dashboard_id TEXT NOT NULL,
                widget_type TEXT NOT NULL,
                title TEXT NOT NULL,
                config TEXT NOT NULL DEFAULT '{}',
                position_x INTEGER NOT NULL DEFAULT 0,
                position_y INTEGER NOT NULL DEFAULT 0,
                width INTEGER NOT NULL DEFAULT 4,
                height INTEGER NOT NULL DEFAULT 2,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (dashboard_id) REFERENCES dashboards(dashboard_id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_widgets_dashboard_id ON dashboard_widgets(dashboard_id)")
        conn.commit()
    finally:
        conn.close()


# ── Widget Types ─────────────────────────────────────────

class WidgetType:
    """Available widget types."""
    STAT_CARD = "stat_card"
    TIME_SERIES = "time_series"
    MODEL_TABLE = "model_table"
    ERROR_TABLE = "error_table"
    TOP_TRACES = "top_traces"
    SPAN_TYPE_PIE = "span_type_pie"
    COST_BREAKDOWN = "cost_breakdown"
    LATENCY_CHART = "latency_chart"
    CUSTOM_QUERY = "custom_query"


WIDGET_DEFAULTS = {
    WidgetType.STAT_CARD: {"metric": "trace_count", "label": "Traces"},
    WidgetType.TIME_SERIES: {"granularity": "hour", "metric": "traces", "limit": 48},
    WidgetType.MODEL_TABLE: {"sort_by": "cost"},
    WidgetType.ERROR_TABLE: {"limit": 10},
    WidgetType.TOP_TRACES: {"sort_by": "cost", "limit": 10},
    WidgetType.SPAN_TYPE_PIE: {},
    WidgetType.COST_BREAKDOWN: {"group_by": "model"},
    WidgetType.LATENCY_CHART: {"span_type": "all"},
    WidgetType.CUSTOM_QUERY: {"sql": "", "display": "table"},
}


# ── Dashboard CRUD ──────────────────────────────────────


def create_dashboard(name: str, description: str = "", owner_id: Optional[str] = None, is_public: bool = False) -> Dict[str, Any]:
    """Create a new dashboard."""
    _ensure_dashboards_table()
    import secrets
    dashboard_id = secrets.token_hex(8)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO dashboards (dashboard_id, name, description, owner_id, layout, is_public) VALUES (?, ?, ?, ?, ?, ?)",
            (dashboard_id, name, description, owner_id, "[]", 1 if is_public else 0),
        )
        conn.commit()
        return {
            "dashboard_id": dashboard_id,
            "name": name,
            "description": description,
            "owner_id": owner_id,
            "layout": [],
            "is_public": is_public,
            "widgets": [],
        }
    finally:
        conn.close()


def get_dashboard(dashboard_id: str) -> Optional[Dict[str, Any]]:
    """Get a dashboard with its widgets."""
    _ensure_dashboards_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM dashboards WHERE dashboard_id = ?",
            (dashboard_id,),
        ).fetchone()
        if not row:
            return None

        dashboard = dict(row)
        dashboard["layout"] = json.loads(dashboard["layout"]) if dashboard["layout"] else []
        dashboard["is_public"] = bool(dashboard["is_public"])

        # Get widgets
        widget_rows = conn.execute(
            "SELECT * FROM dashboard_widgets WHERE dashboard_id = ? ORDER BY position_y, position_x",
            (dashboard_id,),
        ).fetchall()
        widgets = []
        for wr in widget_rows:
            w = dict(wr)
            w["config"] = json.loads(w["config"]) if w["config"] else {}
            widgets.append(w)
        dashboard["widgets"] = widgets
        return dashboard
    finally:
        conn.close()


def list_dashboards(owner_id: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """List dashboards, optionally filtered by owner."""
    _ensure_dashboards_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if owner_id:
            rows = conn.execute(
                "SELECT * FROM dashboards WHERE owner_id = ? OR is_public = 1 ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (owner_id, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM dashboards ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()

        dashboards = []
        for row in rows:
            d = dict(row)
            d["layout"] = json.loads(d["layout"]) if d["layout"] else []
            d["is_public"] = bool(d["is_public"])
            d["widget_count"] = conn.execute(
                "SELECT COUNT(*) FROM dashboard_widgets WHERE dashboard_id = ?",
                (d["dashboard_id"],),
            ).fetchone()[0]
            dashboards.append(d)
        return dashboards
    finally:
        conn.close()


def update_dashboard(dashboard_id: str, data: Dict[str, Any]) -> bool:
    """Update dashboard metadata."""
    conn = sqlite3.connect(DB_PATH)
    try:
        sets = []
        params: list = []
        for key in ("name", "description", "layout", "is_public"):
            if key in data:
                val = data[key]
                if key == "layout":
                    val = json.dumps(val)
                elif key == "is_public":
                    val = 1 if val else 0
                sets.append(f"{key} = ?")
                params.append(val)
        if not sets:
            return True
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(dashboard_id)
        conn.execute(
            f"UPDATE dashboards SET {', '.join(sets)} WHERE dashboard_id = ?",
            params,
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update dashboard: {e}")
        return False
    finally:
        conn.close()


def delete_dashboard(dashboard_id: str) -> bool:
    """Delete a dashboard and its widgets."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM dashboards WHERE dashboard_id = ?", (dashboard_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to delete dashboard: {e}")
        return False
    finally:
        conn.close()


# ── Widget CRUD ──────────────────────────────────────────


def add_widget(dashboard_id: str, widget_type: str, title: str, config: Optional[Dict] = None,
               position_x: int = 0, position_y: int = 0, width: int = 4, height: int = 2) -> Dict[str, Any]:
    """Add a widget to a dashboard."""
    _ensure_dashboards_table()
    import secrets
    widget_id = secrets.token_hex(8)
    effective_config = {**WIDGET_DEFAULTS.get(widget_type, {}), **(config or {})}

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT INTO dashboard_widgets
            (widget_id, dashboard_id, widget_type, title, config, position_x, position_y, width, height)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (widget_id, dashboard_id, widget_type, title, json.dumps(effective_config),
             position_x, position_y, width, height),
        )
        conn.execute("UPDATE dashboards SET updated_at = CURRENT_TIMESTAMP WHERE dashboard_id = ?", (dashboard_id,))
        conn.commit()
        return {
            "widget_id": widget_id,
            "dashboard_id": dashboard_id,
            "widget_type": widget_type,
            "title": title,
            "config": effective_config,
            "position_x": position_x,
            "position_y": position_y,
            "width": width,
            "height": height,
        }
    finally:
        conn.close()


def update_widget(widget_id: str, data: Dict[str, Any]) -> bool:
    """Update a widget's configuration or position."""
    conn = sqlite3.connect(DB_PATH)
    try:
        sets = []
        params: list = []
        for key in ("widget_type", "title", "config", "position_x", "position_y", "width", "height"):
            if key in data:
                val = data[key]
                if key == "config":
                    val = json.dumps(val)
                sets.append(f"{key} = ?")
                params.append(val)
        if not sets:
            return True
        params.append(widget_id)
        conn.execute(
            f"UPDATE dashboard_widgets SET {', '.join(sets)} WHERE widget_id = ?",
            params,
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update widget: {e}")
        return False
    finally:
        conn.close()


def delete_widget(widget_id: str) -> bool:
    """Delete a widget."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM dashboard_widgets WHERE widget_id = ?", (widget_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to delete widget: {e}")
        return False
    finally:
        conn.close()
