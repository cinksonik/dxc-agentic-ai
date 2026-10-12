from __future__ import annotations

import re
from typing import Any


_WORD_RE = re.compile(r"\b\w+\b")


def _words(text: str) -> set[str]:
    return {match.group(0).lower() for match in _WORD_RE.finditer(text)}


def _priority_from_base(base_priority: str) -> str:
    order = {"P4": "P3", "P3": "P2", "P2": "P1", "P1": "P1"}
    return order[base_priority]


def triage(ticket: dict) -> dict:
    title = ticket.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title is required")

    description = ticket.get("description")
    if description is None:
        description = ""
    if not isinstance(description, str):
        description = str(description)

    affected_users = ticket.get("affected_users", 1)
    if not isinstance(affected_users, int) or affected_users < 1:
        raise ValueError("affected_users must be a positive int")

    customer_tier = ticket.get("customer_tier", "standard")
    if customer_tier not in {"standard", "vip"}:
        raise ValueError("invalid customer_tier")

    text = f"{title} {description}"
    words = _words(text)

    if affected_users >= 50 or {"outage", "down"} & words:
        priority = "P1"
    elif affected_users >= 10 or {"urgent", "blocked"} & words:
        priority = "P2"
    elif affected_users >= 2:
        priority = "P3"
    else:
        priority = "P4"

    if customer_tier == "vip":
        priority = _priority_from_base(priority)

    if {"phishing", "breach", "malware"} & words:
        queue = "Security"
    elif {"vpn", "wifi", "network"} & words:
        queue = "Network"
    elif {"password", "login", "locked"} & words:
        queue = "Access"
    elif {"laptop", "keyboard", "screen"} & words:
        queue = "Hardware"
    else:
        queue = "General"

    sla_hours = {"P1": 2, "P2": 8, "P3": 24, "P4": 72}[priority]
    return {"priority": priority, "queue": queue, "sla_hours": sla_hours}
