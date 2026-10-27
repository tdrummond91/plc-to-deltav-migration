"""Natural name ordering for navigation; never reorder source execution evidence."""
from __future__ import annotations

import re

_NUMBERS = re.compile(r'([0-9]+)')


def natural_key(value: str | None) -> tuple[tuple[tuple[int, int, str], ...], str]:
    """Compare digit runs numerically, preserving a stable spelling tie-break.

    Length plus significant digits avoids integer conversion limits and keeps
    large addresses exact. Leading zeros affect only otherwise equal names.
    This key is for display order, never identity, signatures or source order.
    """
    folded = (value or '').casefold()
    parts = []
    for position, part in enumerate(_NUMBERS.split(folded)):
        if position % 2:
            digits = part.lstrip('0') or '0'
            parts.append((1, len(digits), digits))
        else:
            parts.append((0, 0, part))
    return tuple(parts), folded
