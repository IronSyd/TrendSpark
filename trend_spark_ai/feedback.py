from __future__ import annotations
from typing import Sequence


def adaptive_reply_tones(default_tones: Sequence[str]) -> list[str]:
    """Return tones in their provided order, filtering blanks."""
    return [tone for tone in default_tones if tone]
