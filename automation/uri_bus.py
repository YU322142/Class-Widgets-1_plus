from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable
from .async_tools import schedule_awaitable


@dataclass
class UriEvent:
    Name: str


UriHandler = Callable[[UriEvent], Any]


class UriBus:
    """
    对齐 UriTriggerHandlerService 的 run / revert 双事件语义。
    """

    def __init__(self) -> None:
        self._run_handlers: list[UriHandler] = []
        self._revert_handlers: list[UriHandler] = []

    def AddRunHandler(self, handler: UriHandler) -> None:
        self._run_handlers.append(handler)

    def RemoveRunHandler(self, handler: UriHandler) -> None:
        if handler in self._run_handlers:
            self._run_handlers.remove(handler)

    def AddRevertHandler(self, handler: UriHandler) -> None:
        self._revert_handlers.append(handler)

    def RemoveRevertHandler(self, handler: UriHandler) -> None:
        if handler in self._revert_handlers:
            self._revert_handlers.remove(handler)

    def EmitRun(self, name: str) -> None:
        self._emit(self._run_handlers, UriEvent(Name=name))

    def EmitRevert(self, name: str) -> None:
        self._emit(self._revert_handlers, UriEvent(Name=name))

    def _emit(self, handlers: list[UriHandler], event: UriEvent) -> None:
        for handler in list(handlers):
            try:
                result = handler(event)
                schedule_awaitable(result)
            except Exception:
                pass

