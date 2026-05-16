from __future__ import annotations

import logging
from enum import IntEnum
from typing import Any, Callable

from .async_tools import schedule_awaitable


LOGGER = logging.getLogger(__name__)


class ApplicationLifetime(IntEnum):
    None_ = 0
    EarlyLoading = 1
    Initializing = 2
    StartingOffline = 3
    StartingOnline = 4
    Running = 5
    Stopping = 6


EventHandler = Callable[[], Any]


class LifecycleBus:
    """
    对齐 ClassIsland AppBase.CurrentLifetime + AppStopping 事件语义。
    """

    def __init__(self, phase: ApplicationLifetime = ApplicationLifetime.StartingOnline) -> None:
        self.Phase = phase
        self._stopping_handlers: list[EventHandler] = []
        self._stopping_emitted: bool = False

    def SetPhase(self, phase: ApplicationLifetime) -> None:
        self.Phase = ApplicationLifetime(phase)

    def AddStoppingHandler(self, handler: EventHandler) -> None:
        if handler not in self._stopping_handlers:
            self._stopping_handlers.append(handler)

    def RemoveStoppingHandler(self, handler: EventHandler) -> None:
        if handler in self._stopping_handlers:
            self._stopping_handlers.remove(handler)

    def EmitStopping(self) -> None:
        self.Phase = ApplicationLifetime.Stopping

        # 防止多条退出路径重复触发。
        if self._stopping_emitted:
            return

        self._stopping_emitted = True
        self._emit(self._stopping_handlers)

    def _emit(self, handlers: list[EventHandler]) -> None:
        for handler in list(handlers):
            try:
                result = handler()
                schedule_awaitable(result)
            except Exception:
                LOGGER.exception("LifecycleBus stopping handler failed")
