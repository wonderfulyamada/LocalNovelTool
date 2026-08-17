from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Callable[..., None]) -> None:
        self._handlers[event_name].append(handler)

    def emit(self, event_name: str, **payload: Any) -> None:
        for handler in list(self._handlers.get(event_name, [])):
            handler(**payload)
