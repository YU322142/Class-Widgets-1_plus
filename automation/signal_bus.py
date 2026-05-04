from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable
from .async_tools import schedule_awaitable

@dataclass
class SignalEvent:
    SignalName: str
    Revert: bool


SignalHandler = Callable[[SignalEvent], Any]


class SignalBus:
    """
    对齐 ClassIsland 的 SignalTriggerHandlerService + signal 事件分发语义。
    """

    def __init__(self) -> None:
        self._handlers: list[SignalHandler] = []

    def AddHandler(self, handler: SignalHandler) -> None:
        self._handlers.append(handler)

    def RemoveHandler(self, handler: SignalHandler) -> None:
        if handler in self._handlers:
            self._handlers.remove(handler)

    def EmitSignal(self, name: str, revert: bool) -> None:
        event = SignalEvent(SignalName=name, Revert=revert)
        for handler in list(self._handlers):
            try:
                result = handler(event)
                schedule_awaitable(result)
            except Exception:
                pass

