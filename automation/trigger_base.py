from __future__ import annotations

import asyncio
import inspect

from typing import Any, Awaitable, Callable, Generic, TypeVar
from .async_tools import schedule_awaitable


TSettings = TypeVar("TSettings")

TriggerCallback = Callable[["TriggerBase"], Any]


class TriggerBase:
    """
    对齐 ClassIsland.Core.Abstractions.Automation.TriggerBase 的 Python 版。

    映射关系：
    - Trigger()
    - TriggerRevert()
    - Loaded()
    - UnLoaded()
    - AssociatedWorkflow
    """

    def __init__(self, context: Any | None = None, services: Any | None = None) -> None:
        self.Context = context
        self.Services = services

        self._settings_internal: Any = None
        self._associated_workflow: Any = None

        self._triggered_callbacks: list[TriggerCallback] = []
        self._triggered_revert_callbacks: list[TriggerCallback] = []

    # ------------------------------------------------------------
    # Overridables
    # ------------------------------------------------------------

    def Loaded(self) -> None:
        pass

    def UnLoaded(self) -> None:
        pass

    # ------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------

    @property
    def SettingsInternal(self) -> Any:
        return self._settings_internal

    @SettingsInternal.setter
    def SettingsInternal(self, value: Any) -> None:
        self._settings_internal = value

    @property
    def AssociatedWorkflow(self) -> Any:
        return self._associated_workflow

    @AssociatedWorkflow.setter
    def AssociatedWorkflow(self, value: Any) -> None:
        self._associated_workflow = value

    # ------------------------------------------------------------
    # Event subscribe
    # ------------------------------------------------------------

    def AddTriggeredHandler(self, callback: TriggerCallback) -> None:
        self._triggered_callbacks.append(callback)

    def RemoveTriggeredHandler(self, callback: TriggerCallback) -> None:
        if callback in self._triggered_callbacks:
            self._triggered_callbacks.remove(callback)

    def AddTriggeredRevertHandler(self, callback: TriggerCallback) -> None:
        self._triggered_revert_callbacks.append(callback)

    def RemoveTriggeredRevertHandler(self, callback: TriggerCallback) -> None:
        if callback in self._triggered_revert_callbacks:
            self._triggered_revert_callbacks.remove(callback)

    # ------------------------------------------------------------
    # Emit
    # ------------------------------------------------------------

    def Trigger(self) -> None:
        self._emit(self._triggered_callbacks)

    def TriggerRevert(self) -> None:
        self._emit(self._triggered_revert_callbacks)

    def _emit(self, callbacks: list[TriggerCallback]) -> None:
        for callback in list(callbacks):
            try:
                result = callback(self)
                schedule_awaitable(result)
            except Exception:
                # 对齐原版思路：trigger 发射本身不应让调用侧崩掉
                pass


class TriggerBaseT(TriggerBase, Generic[TSettings]):
    @property
    def Settings(self) -> TSettings:
        return self.SettingsInternal  # type: ignore[return-value]
