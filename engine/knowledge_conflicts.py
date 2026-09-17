"""
Knowledge conflict detection and resolution helpers.
"""

from typing import Any, Dict, List


def detect_conflicts(existing: Dict[str, Any], new: Dict[str, Any],
                     category: str) -> List[Dict[str, Any]]:
    conflicts: List[Dict[str, Any]] = []
    if not isinstance(existing, dict) or not isinstance(new, dict):
        return conflicts
    for key in set(list(existing.keys()) + list(new.keys())):
        old_val = existing.get(key)
        new_val = new.get(key)
        if old_val == new_val:
            continue
        severity = _severity(old_val, new_val)
        conflicts.append({
            "field": key,
            "existing": old_val,
            "incoming": new_val,
            "severity": severity,
        })
    return conflicts


def _severity(old: Any, new: Any) -> str:
    if type(old) is not type(new):
        return "high"
    if isinstance(old, dict):
        old_keys, new_keys = set(old.keys()), set(new.keys())
        if not old_keys or not new_keys:
            return "high"
        added = new_keys - old_keys
        removed = old_keys - new_keys
        if added and removed:
            return "high"
        return "medium"
    if isinstance(old, (list, tuple)):
        if len(old) == 0 and len(new) > 0:
            return "medium"
    return "low"


def summarize_conflicts(conflicts: List[Dict[str, Any]], category: str) -> str:
    if not conflicts:
        return ""
    parts = [f"{c['field']}={c['severity']}" for c in conflicts]
    return f"[{category}] {len(conflicts)} conflict(s): {', '.join(parts)}"
