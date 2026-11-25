import ipaddress
import re
import socket
import sqlite3
import time
from collections import defaultdict
from typing import Any

from pynetdicom import AE
from pynetdicom.sop_class import Verification

_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9\-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)*$")


def validate_ae_title(ae_title: str) -> list[str]:
    """Validate a DICOM AE Title and return a list of warning/error messages."""
    issues: list[str] = []
    if not ae_title or not ae_title.strip():
        issues.append("AE Title cannot be empty.")
        return issues
    if ae_title != ae_title.strip():
        issues.append("AE Title has leading or trailing spaces.")
    if len(ae_title) > 16:
        issues.append(f"AE Title exceeds 16 characters ({len(ae_title)} chars).")
    if "\\" in ae_title:
        issues.append("AE Title cannot contain backslash (\\).")
    for ch in ae_title:
        code = ord(ch)
        if code < 0x20 or code > 0x7E:
            issues.append("AE Title must contain only printable ASCII characters.")
            break
    return issues


def validate_ip_or_host(value: str) -> bool:
    """Return True if value is a valid IPv4/IPv6 address or hostname (or empty)."""
    v = value.strip()
    if not v:
        return True
    try:
        ipaddress.ip_address(v)
        return True
    except ValueError:
        return bool(_HOSTNAME_RE.match(v))


def validate_port(port: Any) -> bool:
    """Return True if port is None/empty or an integer between 1 and 65535."""
    if port is None or port == "":
        return True
    try:
        p = int(port)
        return 1 <= p <= 65535
    except (TypeError, ValueError):
        return False


def find_conflicts(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Detect duplicate AE Titles, IP:Port collisions, and invalid AE Title formats."""
    rows = conn.execute(
        """
        SELECT
            a.id AS ae_id,
            a.modality_id,
            a.ae_title,
            a.role_label,
            a.ip_address AS ae_ip,
            a.port,
            m.device_name,
            m.ip_address AS device_ip,
            m.status
        FROM modality_ae_titles a
        JOIN modalities m ON m.id = a.modality_id
        WHERE m.status != 'Decommissioned'
        ORDER BY a.ae_title, m.device_name
        """
    ).fetchall()

    by_aet: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_ip_port: dict[str, list[dict[str, Any]]] = defaultdict(list)
    invalid_aets: list[dict[str, Any]] = []

    for r in rows:
        item = dict(r)
        aet_norm = (item["ae_title"] or "").strip().upper()
        if aet_norm:
            by_aet[aet_norm].append(item)

        issues = validate_ae_title(item["ae_title"] or "")
        if issues:
            invalid_aets.append({**item, "issues": issues})

        effective_ip = (item["ae_ip"] or item["device_ip"] or "").strip()
        port = item["port"]
        if effective_ip and port:
            key = f"{effective_ip.lower()}:{port}"
            by_ip_port[key].append({**item, "effective_ip": effective_ip})

    duplicate_aets = [
        {"ae_title": k, "entries": v}
        for k, v in sorted(by_aet.items())
        if len(v) > 1
    ]
    duplicate_ip_ports = [
        {"endpoint": k, "entries": v}
        for k, v in sorted(by_ip_port.items())
        if len(v) > 1
    ]

    return {
        "duplicate_aets": duplicate_aets,
        "duplicate_ip_ports": duplicate_ip_ports,
        "invalid_aets": invalid_aets,
        "total_count": len(duplicate_aets) + len(duplicate_ip_ports) + len(invalid_aets),
    }


def test_tcp_connection(host: str, port: int, timeout: float = 3.0) -> dict[str, Any]:
    """Attempt a TCP socket connection to host:port and measure latency."""
    host = (host or "").strip()
    if not host or not validate_port(port):
        return {"ok": False, "latency_ms": None, "message": "Invalid host or port."}
    start = time.perf_counter()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            elapsed = round((time.perf_counter() - start) * 1000, 1)
            return {"ok": True, "latency_ms": elapsed, "message": f"TCP connected in {elapsed} ms"}
    except OSError as exc:
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        return {"ok": False, "latency_ms": elapsed, "message": f"TCP failed: {exc}"}


def test_dicom_echo(
    host: str,
    port: int,
    called_aet: str,
    calling_aet: str = "DICOMDB",
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Send a DICOM C-ECHO (Verification) request using pynetdicom."""
    host = (host or "").strip()
    called_aet = (called_aet or "").strip()
    if not host or not validate_port(port) or not called_aet:
        return {
            "ok": False,
            "status": None,
            "latency_ms": None,
            "message": "Host, port, and Called AE Title are required.",
        }

    ae = AE(ae_title=calling_aet[:16] or "DICOMDB")
    ae.add_requested_context(Verification)
    ae.acse_timeout = timeout
    ae.dimse_timeout = timeout
    ae.network_timeout = timeout

    start = time.perf_counter()
    try:
        assoc = ae.associate(host, int(port), ae_title=called_aet[:16])
    except Exception as exc:
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        return {
            "ok": False,
            "status": None,
            "latency_ms": elapsed,
            "message": f"Association error: {exc}",
        }

    if not assoc.is_established:
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        return {
            "ok": False,
            "status": None,
            "latency_ms": elapsed,
            "message": "Association rejected or timed out.",
        }

    try:
        status = assoc.send_c_echo()
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        if status and status.Status == 0x0000:
            return {
                "ok": True,
                "status": "0x0000",
                "latency_ms": elapsed,
                "message": f"C-ECHO succeeded (0x0000) in {elapsed} ms",
            }
        code = f"0x{status.Status:04X}" if status else "None"
        return {
            "ok": False,
            "status": code,
            "latency_ms": elapsed,
            "message": f"C-ECHO returned status {code}",
        }
    finally:
        assoc.release()
