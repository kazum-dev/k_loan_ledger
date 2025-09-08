# modules/audit.py
import csv
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Union

# 規定は data/audit_log.csv （環境変数で上書き可）
AUDIT_FILE = os.getenv("APP_AUDIT_FILE", "data/audit_log.csv")
_HEADER = ["timestamp_utc", "action", "entity", "entity_id", "actor", "details"]

def _ensure_header(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    need_header = not os.path.exists(path) or os.path.getsize(path) == 0
    if need_header:
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(_HEADER)

def _serialize_details(details: Union[str, Dict[str, Any], None]) -> str:
    if details is None:
        return ""
    if isinstance(details, str):
        return details
    try:
        return json.dumps(details, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(details)
    
def append_audit(
    action: str,
    entity: str,
    entity_id: Union[str, int],
    details: Union[str, Dict[str, Any], None] = None,
    actor: str = "CLI",
    *,
    path: str = AUDIT_FILE,    
) -> None:
    _ensure_header(path)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    row = [ts, str(action), str(entity), str(entity_id), str(actor), _serialize_details(details)]
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)
        f.flush()