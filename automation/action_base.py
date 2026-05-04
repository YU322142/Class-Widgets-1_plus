from __future__ import annotations

import asyncio
from typing import Any, Generic, TypeVar

from .models import ActionItem, ActionSet

TSettings = TypeVar("TSettings")


class ActionInterruptedError(asyncio.CancelledError):
    pass


def _ensure_action_set_runtime(action_set: ActionSet) -> asyncio.Event:
    """
    给 ActionSet 动态挂运行时字段，避免你必须立刻改 models.py。
    """
    event = getattr(action_set, "_interrupt_event", None)
    if event is None:
        event = asyncio.Event()
        setattr(action_set, "_interrupt_event", event)

    if not hasattr(action_set, "_running_task"):
        setattr(action_set, "_running_task", None)

    if not hasattr(action_set, "_running_done"):
        setattr(action_set, "_running_done", None)

    return event


class ActionBase:
    """
    对齐 ClassIsland.Core.Abstractions.Automation.ActionBase 的 Python 版。

    映射关系：
    - OnInvoke
    - OnRevert
    - OnInterrupted
    - InvokeAsync
    - RevertAsync
    """

    def __init__(self, context: Any | None = None, services: Any | None = None) -> None:
        self.Context = context
        self.Services = services

        self._settings_internal: Any = None
        self._interrupt_event: asyncio.Event | None = None
        self._interrupt_task_watch_started: bool = False

        self._action_item: ActionItem | None = None
        self._action_set: ActionSet | None = None
        self._is_revertable: bool = False

    # ------------------------------------------------------------
    # Overridables
    # ------------------------------------------------------------

    async def OnInvoke(self) -> None:
        pass

    async def OnRevert(self) -> None:
        pass

    async def OnInterrupted(self) -> None:
        pass

    # ------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------

    @property
    def SettingsInternal(self) -> Any:
        return self._settings_internal

    @property
    def ActionItem(self) -> ActionItem:
        if self._action_item is None:
            raise RuntimeError("ActionItem is not available outside action execution lifecycle.")
        return self._action_item

    @property
    def ActionSet(self) -> ActionSet:
        if self._action_set is None:
            raise RuntimeError("ActionSet is not available outside action execution lifecycle.")
        return self._action_set

    @property
    def IsRevertable(self) -> bool:
        return self._is_revertable

    @property
    def InterruptCancellationToken(self) -> asyncio.Event:
        if self._interrupt_event is None:
            raise RuntimeError("Interrupt event is not available outside action execution lifecycle.")
        return self._interrupt_event

    @property
    def IsInterrupted(self) -> bool:
        return self._interrupt_event.is_set() if self._interrupt_event is not None else False

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def ThrowIfInterrupted(self) -> None:
        if self.IsInterrupted:
            raise ActionInterruptedError()

    async def WaitUntilInterrupted(self) -> None:
        await self.InterruptCancellationToken.wait()

    async def SleepWithInterrupt(self, seconds: float) -> None:
        if seconds <= 0:
            self.ThrowIfInterrupted()
            return

        sleep_task = asyncio.create_task(asyncio.sleep(seconds))
        interrupt_task = asyncio.create_task(self.InterruptCancellationToken.wait())
        done, pending = await asyncio.wait(
            {sleep_task, interrupt_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

        if interrupt_task in done and self.InterruptCancellationToken.is_set():
            raise ActionInterruptedError()

    async def WaitAsync(self, awaitable: Any) -> Any:
        """
        等待某个 awaitable，但如果动作被中断，则立刻抛出 ActionInterruptedError。
        """
        main_task = asyncio.create_task(awaitable)
        interrupt_task = asyncio.create_task(self.InterruptCancellationToken.wait())

        done, pending = await asyncio.wait(
            {main_task, interrupt_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

        if interrupt_task in done and self.InterruptCancellationToken.is_set():
            if not main_task.done():
                main_task.cancel()
            raise ActionInterruptedError()

        return await main_task

    # ------------------------------------------------------------
    # Lifecycle entrypoints
    # ------------------------------------------------------------

    async def InvokeAsync(
        self,
        action_item: ActionItem,
        action_set: ActionSet,
        is_revertable: bool = True,
    ) -> None:
        await self._ExecuteAsync(
            action_item=action_item,
            action_set=action_set,
            is_revertable=is_revertable,
            action=self.OnInvoke,
        )

    async def RevertAsync(
        self,
        action_item: ActionItem,
        action_set: ActionSet,
    ) -> None:
        await self._ExecuteAsync(
            action_item=action_item,
            action_set=action_set,
            is_revertable=False,
            action=self.OnRevert,
        )

    async def _ExecuteAsync(
        self,
        action_item: ActionItem,
        action_set: ActionSet,
        is_revertable: bool,
        action: Any,
    ) -> None:
        self._action_item = action_item
        self._action_set = action_set
        self._is_revertable = is_revertable
        self._settings_internal = action_item.Settings
        self._interrupt_event = _ensure_action_set_runtime(action_set)
        self._interrupt_task_watch_started = False

        watcher_task: asyncio.Task | None = None

        try:
            self.ActionItem.set_start_running()
            watcher_task = asyncio.create_task(self._WatchInterrupt())

            self.ThrowIfInterrupted()
            await action()

        except ActionInterruptedError:
            # 对齐 ClassIsland：中断不记为 action 异常
            pass

        except asyncio.CancelledError:
            if self.IsInterrupted:
                pass
            else:
                raise

        except Exception as ex:
            self.ActionItem.Exception = str(ex)
            raise

        finally:
            if watcher_task is not None:
                watcher_task.cancel()
            self.ActionItem.set_end_running()

    async def _WatchInterrupt(self) -> None:
        """
        尽量模拟 ClassIsland token.Register(async () => await OnInterrupted()) 的语义。
        """
        if self._interrupt_task_watch_started:
            return
        self._interrupt_task_watch_started = True

        await self.InterruptCancellationToken.wait()
        try:
            await self.OnInterrupted()
        except Exception:
            # 中断回调不应破坏主流程
            pass


class ActionBaseT(ActionBase, Generic[TSettings]):
    @property
    def Settings(self) -> TSettings:
        return self.SettingsInternal  # type: ignore[return-value]
