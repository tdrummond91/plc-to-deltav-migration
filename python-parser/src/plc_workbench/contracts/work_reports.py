"""Versioned work-report size and JSON layout policy, without workflow imports.

The work-check module re-exports these caps for compatibility. Select cap names
rather than cached values so its callers can still override those aliases in
boundary tests. This policy does not validate or authorize a report for sharing.
"""
from __future__ import annotations

import json
from typing import Any

MAX_REPORT_BYTES = 32 * 1024
MAX_REPORT_V22_BYTES = 48 * 1024
MAX_REPORT_V28_BYTES = 64 * 1024
MAX_REPORT_V32_BYTES = 80 * 1024
MAX_REPORT_V39_BYTES = 88 * 1024
MAX_REPORT_V40_BYTES = 96 * 1024
MAX_REPORT_V41_BYTES = 104 * 1024
MAX_REPORT_V42_BYTES = 104 * 1024
MAX_REPORT_V43_BYTES = 104 * 1024
MAX_REPORT_V44_BYTES = 104 * 1024
MAX_REPORT_V45_BYTES = 104 * 1024
MAX_REPORT_V46_BYTES = 104 * 1024
MAX_REPORT_V47_BYTES = 104 * 1024
MAX_REPORT_V48_BYTES = 112 * 1024
MAX_REPORT_V49_BYTES = 128 * 1024
MAX_REPORT_V50_BYTES = 128 * 1024
MAX_REPORT_V51_BYTES = 144 * 1024
MAX_REPORT_V52_BYTES = 144 * 1024
MAX_REPORT_V53_BYTES = 144 * 1024

# Equal current values retain separate names where historical versions already
# exposed their own cap. Do not turn the last range into an open-ended default.
_LIMIT_ERAS = (
    (range(22, 28), "MAX_REPORT_V22_BYTES"),
    (range(28, 32), "MAX_REPORT_V28_BYTES"),
    (range(32, 39), "MAX_REPORT_V32_BYTES"),
    *((range(version, version + 1), f"MAX_REPORT_V{version}_BYTES")
      for version in range(39, 54)),
)
EXPANDED_LIMIT_NAMES = tuple(name for _, name in _LIMIT_ERAS)
MAX_WORK_REPORT_BYTES = max(globals()[name] for name in EXPANDED_LIMIT_NAMES)


def report_limit_name(version: int) -> str:
    """Select a cap alias; unknown versions retain the historical 32 KiB cap."""
    for versions, name in _LIMIT_ERAS:
        if version in versions:
            return name
    return "MAX_REPORT_BYTES"


def publication_limit_name(payload: Any) -> str | None:
    """Allow an expanded cap only for an exact known work-report discriminator.

    None means the caller's ordinary summary cap, which is independent of the
    work-check base alias. Closed validation must still follow this selection.
    """
    if (type(payload) is dict
            and payload.get("report_kind") == "l5x_work_machine_check"
            and type(payload.get("schema_version")) is int
            and payload["schema_version"] in range(22, 54)):
        return report_limit_name(payload["schema_version"])
    return None


def serialize_report(report: dict[str, Any]) -> str:
    """Preserve canonical bytes: compact work31-53, pretty JSON otherwise."""
    layout = ({"separators": (",", ":")}
              if report["schema_version"] in range(31, 54) else {"indent": 2})
    return json.dumps(report, sort_keys=True, ensure_ascii=True, **layout) + "\n"
