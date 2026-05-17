"""Small opt-in console debug logger for chat orchestration."""

from __future__ import annotations

import json
import os
from typing import Any


def chat_debug_enabled() -> bool:
    return os.getenv("CHAT_DEBUG", "").lower() in {"1", "true", "yes", "on"}


def chat_debug(event: str, **payload: Any) -> None:
    """Print one structured chat debug event when CHAT_DEBUG is enabled."""
    if not chat_debug_enabled():
        return
    print(
        "[chat-debug] "
        + json.dumps(
            {"event": event, **payload},
            default=str,
            ensure_ascii=False,
        ),
        flush=True,
    )
