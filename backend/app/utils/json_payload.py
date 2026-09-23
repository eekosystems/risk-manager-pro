"""Lenient parsing of a JSON object out of a model response."""

import json
from typing import Any


def parse_json_payload(raw: str) -> dict[str, Any] | None:
    """Return the JSON object in `raw`, tolerating code fences and stray prose."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
        s = s.strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        start = s.find("{")
        end = s.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            obj = json.loads(s[start : end + 1])
        except json.JSONDecodeError:
            return None
    return obj if isinstance(obj, dict) else None
