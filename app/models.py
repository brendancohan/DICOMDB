import json
import re
import sqlite3
from typing import Any, Optional

MODALITY_TYPES = ["CT", "MR", "US", "DX", "CR", "MG", "XA", "NM", "PT", "RF", "OTHER"]
MODALITY_STATUSES = ["Active", "Maintenance", "Decommissioned"]
FIELD_TYPES = ["text", "number", "dropdown", "boolean", "date", "textarea", "url"]
DESTINATION_TYPES = ["PACS", "VNA", "Worklist", "AI", "3D", "Print", "Archive", "Other"]
ROUTE_DIRECTIONS = ["Send", "MWL", "Query/Retrieve", "MPPS", "Print"]


def _slugify_key(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return slug or "custom_field"


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def record_audit(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: Optional[int],
    entity_name: str,
    action: str,
    editor_label: str,
    changes: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO audit_log (entity_type, entity_id, entity_name, action, editor_label, changes_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (entity_type, entity_id, entity_name, action, editor_label, json.dumps(changes)),
    )


def _compute_diff(old: dict[str, Any], new: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    diff: dict[str, Any] = {}
    for k in keys:
        if old.get(k) != new.get(k):
            diff[k] = {"old": old.get(k), "new": new.get(k)}
    return diff


# ---------------------------------------------------------------------------
# Field Definitions
# ---------------------------------------------------------------------------

def list_field_definitions(
    conn: sqlite3.Connection, include_archived: bool = False
) -> list[dict[str, Any]]:
    where = "" if include_archived else "WHERE archived = 0"
    rows = conn.execute(
        f"SELECT * FROM field_definitions {where} ORDER BY display_order ASC, id ASC"
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["options"] = json.loads(d["options_json"] or "[]")
        except json.JSONDecodeError:
            d["options"] = []
        result.append(d)
    return result


def create_field_definition(
    conn: sqlite3.Connection,
    label: str,
    field_type: str,
    options: list[str],
    section: str,
    show_in_table: bool,
    is_required: bool,
    editor_label: str,
) -> dict[str, Any]:
    base_key = _slugify_key(label)
    key = base_key
    suffix = 2
    while conn.execute("SELECT 1 FROM field_definitions WHERE key = ?", (key,)).fetchone():
        key = f"{base_key}_{suffix}"
        suffix += 1

    max_order = conn.execute("SELECT COALESCE(MAX(display_order), 0) FROM field_definitions").fetchone()[0]
    cur = conn.execute(
        """
        INSERT INTO field_definitions
            (key, label, field_type, options_json, section, show_in_table, is_required, display_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            key,
            label.strip(),
            field_type if field_type in FIELD_TYPES else "text",
            json.dumps([o.strip() for o in options if o.strip()]),
            section.strip() or "General",
            1 if show_in_table else 0,
            1 if is_required else 0,
            max_order + 1,
        ),
    )
    field_id = cur.lastrowid
    record_audit(
        conn,
        "field_definition",
        field_id,
        label.strip(),
        "create",
        editor_label,
        {"key": key, "field_type": field_type, "section": section},
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM field_definitions WHERE id = ?", (field_id,)).fetchone())


def update_field_definition(
    conn: sqlite3.Connection,
    field_id: int,
    label: str,
    options: list[str],
    section: str,
    show_in_table: bool,
    is_required: bool,
    editor_label: str,
) -> None:
    old_row = conn.execute("SELECT * FROM field_definitions WHERE id = ?", (field_id,)).fetchone()
    if not old_row:
        return
    conn.execute(
        """
        UPDATE field_definitions
        SET label = ?, options_json = ?, section = ?, show_in_table = ?, is_required = ?
        WHERE id = ?
        """,
        (
            label.strip(),
            json.dumps([o.strip() for o in options if o.strip()]),
            section.strip() or "General",
            1 if show_in_table else 0,
            1 if is_required else 0,
            field_id,
        ),
    )
    record_audit(
        conn,
        "field_definition",
        field_id,
        label.strip(),
        "update",
        editor_label,
        {"label": label.strip(), "section": section.strip()},
    )
    conn.commit()


def toggle_archive_field(conn: sqlite3.Connection, field_id: int, editor_label: str) -> None:
    row = conn.execute("SELECT * FROM field_definitions WHERE id = ?", (field_id,)).fetchone()
    if not row:
        return
    new_val = 0 if row["archived"] else 1
    conn.execute("UPDATE field_definitions SET archived = ? WHERE id = ?", (new_val, field_id))
    record_audit(
        conn,
        "field_definition",
        field_id,
        row["label"],
        "archive" if new_val else "restore",
        editor_label,
        {"archived": {"old": bool(row["archived"]), "new": bool(new_val)}},
    )
    conn.commit()


def move_field_order(conn: sqlite3.Connection, field_id: int, direction: str) -> None:
    rows = conn.execute(
        "SELECT id, display_order FROM field_definitions ORDER BY display_order ASC, id ASC"
    ).fetchall()
    idx = next((i for i, r in enumerate(rows) if r["id"] == field_id), None)
    if idx is None:
        return
    swap_idx = idx - 1 if direction == "up" else idx + 1
    if swap_idx < 0 or swap_idx >= len(rows):
        return
    a, b = rows[idx], rows[swap_idx]
    conn.execute("UPDATE field_definitions SET display_order = ? WHERE id = ?", (b["display_order"], a["id"]))
    conn.execute("UPDATE field_definitions SET display_order = ? WHERE id = ?", (a["display_order"], b["id"]))
    conn.commit()


# ---------------------------------------------------------------------------
# Modalities, AE Titles, and Routes
# ---------------------------------------------------------------------------

def get_modality(conn: sqlite3.Connection, modality_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute("SELECT * FROM modalities WHERE id = ?", (modality_id,)).fetchone()
    if not row:
        return None
    m = dict(row)
    try:
        m["custom_fields"] = json.loads(m["custom_fields"] or "{}")
    except json.JSONDecodeError:
        m["custom_fields"] = {}

    ae_rows = conn.execute(
        "SELECT * FROM modality_ae_titles WHERE modality_id = ? ORDER BY display_order ASC, id ASC",
        (modality_id,),
    ).fetchall()
    m["ae_titles"] = [dict(r) for r in ae_rows]

    route_rows = conn.execute(
        """
        SELECT r.*, d.name AS destination_name, d.dest_type, d.ae_title AS dest_ae_title,
               d.ip_address AS dest_ip, d.port AS dest_port,
               a.ae_title AS ae_title
        FROM modality_routes r
        JOIN destinations d ON d.id = r.destination_id
        LEFT JOIN modality_ae_titles a ON a.id = r.ae_title_id
        WHERE r.modality_id = ?
        ORDER BY d.name ASC
        """,
        (modality_id,),
    ).fetchall()
    m["routes"] = [dict(r) for r in route_rows]
    return m


def list_modalities(
    conn: sqlite3.Connection,
    q: str = "",
    modality_type: str = "",
    status: str = "",
    location: str = "",
    destination_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    sql = "SELECT DISTINCT m.* FROM modalities m"
    joins: list[str] = []
    wheres: list[str] = []
    params: list[Any] = []

    if q.strip():
        joins.append("LEFT JOIN modality_ae_titles a ON a.modality_id = m.id")
        like = f"%{q.strip()}%"
        wheres.append(
            "(m.device_name LIKE ? OR m.manufacturer LIKE ? OR m.model LIKE ? "
            "OR m.location LIKE ? OR m.ip_address LIKE ? OR m.notes LIKE ? "
            "OR m.custom_fields LIKE ? OR a.ae_title LIKE ?)"
        )
        params.extend([like] * 8)

    if modality_type:
        wheres.append("m.modality_type = ?")
        params.append(modality_type)
    if status:
        wheres.append("m.status = ?")
        params.append(status)
    if location:
        wheres.append("m.location = ?")
        params.append(location)
    if destination_id:
        joins.append("JOIN modality_routes r ON r.modality_id = m.id")
        wheres.append("r.destination_id = ?")
        params.append(destination_id)

    if joins:
        sql += " " + " ".join(joins)
    if wheres:
        sql += " WHERE " + " AND ".join(wheres)
    sql += " ORDER BY m.device_name ASC"

    rows = conn.execute(sql, params).fetchall()
    result = []
    for r in rows:
        m = dict(r)
        try:
            m["custom_fields"] = json.loads(m["custom_fields"] or "{}")
        except json.JSONDecodeError:
            m["custom_fields"] = {}
        m["ae_titles"] = [
            dict(a)
            for a in conn.execute(
                "SELECT * FROM modality_ae_titles WHERE modality_id = ? ORDER BY display_order ASC, id ASC",
                (m["id"],),
            ).fetchall()
        ]
        m["routes"] = [
            dict(rt)
            for rt in conn.execute(
                """
                SELECT r.*, d.name AS destination_name, a.ae_title AS ae_title
                FROM modality_routes r
                JOIN destinations d ON d.id = r.destination_id
                LEFT JOIN modality_ae_titles a ON a.id = r.ae_title_id
                WHERE r.modality_id = ?
                """,
                (m["id"],),
            ).fetchall()
        ]
        result.append(m)
    return result


def list_locations(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT location FROM modalities WHERE location != '' ORDER BY location ASC"
    ).fetchall()
    return [r["location"] for r in rows]


def save_modality(
    conn: sqlite3.Connection,
    modality_id: Optional[int],
    data: dict[str, Any],
    ae_titles: list[dict[str, Any]],
    routes: list[dict[str, Any]],
    editor_label: str,
) -> int:
    old = get_modality(conn, modality_id) if modality_id else None
    custom_json = json.dumps(data.get("custom_fields") or {})

    if modality_id is None:
        cur = conn.execute(
            """
            INSERT INTO modalities
                (device_name, modality_type, manufacturer, model, location, ip_address, status, notes, custom_fields)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["device_name"].strip(),
                data["modality_type"],
                data.get("manufacturer", "").strip(),
                data.get("model", "").strip(),
                data.get("location", "").strip(),
                data.get("ip_address", "").strip(),
                data.get("status", "Active"),
                data.get("notes", "").strip(),
                custom_json,
            ),
        )
        modality_id = cur.lastrowid
    else:
        conn.execute(
            """
            UPDATE modalities
            SET device_name = ?, modality_type = ?, manufacturer = ?, model = ?,
                location = ?, ip_address = ?, status = ?, notes = ?, custom_fields = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE id = ?
            """,
            (
                data["device_name"].strip(),
                data["modality_type"],
                data.get("manufacturer", "").strip(),
                data.get("model", "").strip(),
                data.get("location", "").strip(),
                data.get("ip_address", "").strip(),
                data.get("status", "Active"),
                data.get("notes", "").strip(),
                custom_json,
                modality_id,
            ),
        )

    # Replace AE titles and map index -> new id for route linking
    conn.execute("DELETE FROM modality_ae_titles WHERE modality_id = ?", (modality_id,))
    ae_id_by_index: dict[int, int] = {}
    for idx, ae in enumerate(ae_titles):
        aet = (ae.get("ae_title") or "").strip()
        if not aet:
            continue
        port_val = int(ae["port"]) if str(ae.get("port") or "").strip().isdigit() else None
        cur_ae = conn.execute(
            """
            INSERT INTO modality_ae_titles
                (modality_id, ae_title, role_label, ip_address, port, notes, display_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                modality_id,
                aet,
                (ae.get("role_label") or "").strip(),
                (ae.get("ip_address") or "").strip(),
                port_val,
                (ae.get("notes") or "").strip(),
                idx,
            ),
        )
        ae_id_by_index[idx] = cur_ae.lastrowid

    # Replace routes
    conn.execute("DELETE FROM modality_routes WHERE modality_id = ?", (modality_id,))
    for rt in routes:
        dest_id = rt.get("destination_id")
        if not dest_id:
            continue
        ae_idx = rt.get("ae_index")
        ae_title_id = ae_id_by_index.get(ae_idx) if ae_idx is not None else None
        conn.execute(
            """
            INSERT INTO modality_routes (modality_id, ae_title_id, destination_id, direction, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                modality_id,
                ae_title_id,
                int(dest_id),
                rt.get("direction") or "Send",
                (rt.get("notes") or "").strip(),
            ),
        )

    new_state = get_modality(conn, modality_id) or {}
    if old is None:
        record_audit(
            conn,
            "modality",
            modality_id,
            data["device_name"].strip(),
            "create",
            editor_label,
            {"device_name": data["device_name"].strip(), "modality_type": data["modality_type"]},
        )
    else:
        diff = _compute_diff(
            old,
            new_state,
            ["device_name", "modality_type", "manufacturer", "model", "location", "ip_address", "status", "notes", "custom_fields"],
        )
        if len(old.get("ae_titles", [])) != len(new_state.get("ae_titles", [])):
            diff["ae_titles_count"] = {"old": len(old.get("ae_titles", [])), "new": len(new_state.get("ae_titles", []))}
        if len(old.get("routes", [])) != len(new_state.get("routes", [])):
            diff["routes_count"] = {"old": len(old.get("routes", [])), "new": len(new_state.get("routes", []))}
        record_audit(
            conn,
            "modality",
            modality_id,
            data["device_name"].strip(),
            "update",
            editor_label,
            diff or {"updated": True},
        )
    conn.commit()
    return modality_id


def delete_modality(conn: sqlite3.Connection, modality_id: int, editor_label: str) -> None:
    row = conn.execute("SELECT device_name FROM modalities WHERE id = ?", (modality_id,)).fetchone()
    if not row:
        return
    conn.execute("DELETE FROM modalities WHERE id = ?", (modality_id,))
    record_audit(
        conn,
        "modality",
        modality_id,
        row["device_name"],
        "delete",
        editor_label,
        {"deleted": row["device_name"]},
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Destinations
# ---------------------------------------------------------------------------

def list_destinations(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT d.*, COUNT(DISTINCT r.modality_id) AS modality_count
        FROM destinations d
        LEFT JOIN modality_routes r ON r.destination_id = d.id
        GROUP BY d.id
        ORDER BY d.name ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def get_destination(conn: sqlite3.Connection, dest_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute("SELECT * FROM destinations WHERE id = ?", (dest_id,)).fetchone()
    return dict(row) if row else None


def get_destination_modalities(conn: sqlite3.Connection, dest_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT m.id, m.device_name, m.modality_type, m.location, m.ip_address, m.status,
               r.direction, r.notes AS route_notes, a.ae_title AS source_ae_title
        FROM modality_routes r
        JOIN modalities m ON m.id = r.modality_id
        LEFT JOIN modality_ae_titles a ON a.id = r.ae_title_id
        WHERE r.destination_id = ?
        ORDER BY m.device_name ASC
        """,
        (dest_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def save_destination(
    conn: sqlite3.Connection,
    dest_id: Optional[int],
    data: dict[str, Any],
    editor_label: str,
) -> int:
    port_val = int(data["port"]) if str(data.get("port") or "").strip().isdigit() else None
    if dest_id is None:
        cur = conn.execute(
            """
            INSERT INTO destinations (name, dest_type, ae_title, ip_address, port, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"].strip(),
                data.get("dest_type", "PACS"),
                data.get("ae_title", "").strip(),
                data.get("ip_address", "").strip(),
                port_val,
                data.get("notes", "").strip(),
            ),
        )
        dest_id = cur.lastrowid
        record_audit(conn, "destination", dest_id, data["name"].strip(), "create", editor_label, {"name": data["name"].strip()})
    else:
        conn.execute(
            """
            UPDATE destinations
            SET name = ?, dest_type = ?, ae_title = ?, ip_address = ?, port = ?, notes = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE id = ?
            """,
            (
                data["name"].strip(),
                data.get("dest_type", "PACS"),
                data.get("ae_title", "").strip(),
                data.get("ip_address", "").strip(),
                port_val,
                data.get("notes", "").strip(),
                dest_id,
            ),
        )
        record_audit(conn, "destination", dest_id, data["name"].strip(), "update", editor_label, {"name": data["name"].strip()})
    conn.commit()
    return dest_id


def delete_destination(conn: sqlite3.Connection, dest_id: int, editor_label: str) -> None:
    row = conn.execute("SELECT name FROM destinations WHERE id = ?", (dest_id,)).fetchone()
    if not row:
        return
    conn.execute("DELETE FROM destinations WHERE id = ?", (dest_id,))
    record_audit(conn, "destination", dest_id, row["name"], "delete", editor_label, {"deleted": row["name"]})
    conn.commit()


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

def list_audit_logs(
    conn: sqlite3.Connection,
    entity_type: str = "",
    action: str = "",
    q: str = "",
    limit: int = 200,
) -> list[dict[str, Any]]:
    wheres: list[str] = []
    params: list[Any] = []
    if entity_type:
        wheres.append("entity_type = ?")
        params.append(entity_type)
    if action:
        wheres.append("action = ?")
        params.append(action)
    if q.strip():
        like = f"%{q.strip()}%"
        wheres.append("(entity_name LIKE ? OR editor_label LIKE ? OR changes_json LIKE ?)")
        params.extend([like, like, like])

    sql = "SELECT * FROM audit_log"
    if wheres:
        sql += " WHERE " + " AND ".join(wheres)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["changes"] = json.loads(d["changes_json"] or "{}")
        except json.JSONDecodeError:
            d["changes"] = {}
        result.append(d)
    return result
