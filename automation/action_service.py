from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Iterable

from .action_base import ActionInterruptedError
from .models import ActionItem, ActionSet
from .registry import ACTION_INFOS, create_action_instance, migrate_action_item_compat


class ActionService:
    """
    对齐 ClassIsland.Services.ActionService 的 Python 版。

    关键兼容点：
    - ActionSet 串行执行
    - invoke/revert/interrupt 状态流转
    - 单个 action 异常只记录，不中断整个 ActionSet
    - invoke 时若当前 Reverting，先 interrupt
    - revert 时若当前 Invoking，先 interrupt
    """

    def __init__(self, logger: logging.Logger | None = None, context: Any | None = None, services: Any | None = None) -> None:
        self.Logger = logger or logging.getLogger(__name__)
        self.Context = context
        self.Services = services

    # =========================================================
    # Public APIs
    # =========================================================

    async def InvokeActionSetAsync(self, action_set: ActionSet, is_revertable: bool = True) -> None:
        if action_set.Status.name == "Reverting":
            await self.InterruptActionSetAsync(action_set)

        if action_set.IsWorking:
            return

        self.MigrateActionSet(action_set)

        interrupt_event, done_event = self._ensure_action_set_runtime(action_set)
        interrupt_event.clear()
        done_event.clear()
        action_set.set_start_running(True)
        setattr(action_set, "_runner_task", asyncio.current_task())

        try:
            await self._changeable_list_for_each_async(
                list_provider=lambda: [x for x in action_set.Actions if not x.IsRevertActionItem],
                action=lambda item: self.InvokeActionItemAsync(
                    item,
                    action_set,
                    is_revertable=(is_revertable and action_set.IsRevertEnabled),
                ),
                interrupt_event=interrupt_event,
            )
        finally:
            setattr(action_set, "_runner_task", None)
            action_set.set_end_running(
                True,
                was_interrupted=(interrupt_event.is_set() or action_set.interrupt_requested),
            )
            done_event.set()

    async def RevertActionSetAsync(self, action_set: ActionSet) -> None:
        if action_set.Status.name == "Invoking":
            await self.InterruptActionSetAsync(action_set)

        if action_set.IsWorking:
            return

        self.MigrateActionSet(action_set)

        interrupt_event, done_event = self._ensure_action_set_runtime(action_set)
        interrupt_event.clear()
        done_event.clear()
        action_set.set_start_running(False)
        setattr(action_set, "_runner_task", asyncio.current_task())

        try:
            await self._changeable_list_for_each_async(
                list_provider=lambda: [x for x in action_set.Actions if x.IsRevertActionItem or x.IsRevertEnabled],
                action=lambda item: self._revert_dispatch(item, action_set),
                interrupt_event=interrupt_event,
            )
        finally:
            setattr(action_set, "_runner_task", None)
            action_set.set_end_running(
                False,
                was_interrupted=(interrupt_event.is_set() or action_set.interrupt_requested),
            )
            done_event.set()

    async def InterruptActionSetAsync(self, action_set: ActionSet) -> None:
        self.Logger.info("Interrupting action set: %s", action_set.Name)

        interrupt_event, done_event = self._ensure_action_set_runtime(action_set)
        action_set.mark_interrupted()
        interrupt_event.set()

        runner_task = getattr(action_set, "_runner_task", None)
        if runner_task is not None and runner_task is not asyncio.current_task():
            await done_event.wait()

    async def InvokeActionItemAsync(
        self,
        action_item: ActionItem,
        action_set: ActionSet,
        is_revertable: bool = True,
    ) -> None:
        interrupt_event, _ = self._ensure_action_set_runtime(action_set)
        if interrupt_event.is_set():
            return

        provider = create_action_instance(
            action_item,
            context=self.Context,
            services=self.Services,
        )
        if provider is None:
            self.Logger.warning("Action provider not found: %s", action_item.Id)
            return

        action_info = ACTION_INFOS.get(action_item.Id)
        if action_info is None:
            self.Logger.warning("Action info not found: %s", action_item.Id)
            return

        self.MigrateActionItem(action_item)

        action_item_text = f"ActionItem[{action_info.Name}] in ActionSet[{action_set.Name}]"
        self.Logger.debug("Invoking %s", action_item_text)

        try:
            await provider.InvokeAsync(
                action_item,
                action_set,
                is_revertable=(is_revertable and action_item.IsRevertEnabled),
            )
        except ActionInterruptedError:
            pass
        except Exception:
            self.Logger.exception("Invoke action item failed: %s", action_item_text)

    async def RevertActionItemAsync(self, action_item: ActionItem, action_set: ActionSet) -> None:
        if action_item.IsRevertActionItem or (not action_item.IsRevertEnabled):
            return

        interrupt_event, _ = self._ensure_action_set_runtime(action_set)
        if interrupt_event.is_set():
            return

        provider = create_action_instance(
            action_item,
            context=self.Context,
            services=self.Services,
        )
        if provider is None:
            self.Logger.warning("Action provider not found: %s", action_item.Id)
            return

        action_info = ACTION_INFOS.get(action_item.Id)
        if action_info is None:
            self.Logger.warning("Action info not found: %s", action_item.Id)
            return

        if not action_info.IsRevertable:
            return

        self.MigrateActionItem(action_item)

        action_item_text = f"ActionItem[{action_info.Name}] in ActionSet[{action_set.Name}]"
        self.Logger.debug("Reverting %s", action_item_text)

        try:
            await provider.RevertAsync(action_item, action_set)
        except ActionInterruptedError:
            pass
        except Exception:
            self.Logger.exception("Revert action item failed: %s", action_item_text)

    def MigrateActionSet(self, action_set: ActionSet) -> None:
        # 当前先保持 no-op
        return

    def MigrateActionItem(self, action_item: ActionItem) -> None:
        # 当前先只做兼容迁移
        migrate_action_item_compat(action_item)

    def MigrateUnknownActionItem(self, action_item: ActionItem) -> None:
        migrate_action_item_compat(action_item)

    # =========================================================
    # Internal helpers
    # =========================================================

    async def _revert_dispatch(self, action_item: ActionItem, action_set: ActionSet) -> None:
        if action_item.IsRevertActionItem:
            await self.InvokeActionItemAsync(action_item, action_set, is_revertable=False)
        elif action_item.IsRevertEnabled:
            await self.RevertActionItemAsync(action_item, action_set)

    def _ensure_action_set_runtime(self, action_set: ActionSet) -> tuple[asyncio.Event, asyncio.Event]:
        interrupt_event = getattr(action_set, "_interrupt_event", None)
        if interrupt_event is None:
            interrupt_event = asyncio.Event()
            setattr(action_set, "_interrupt_event", interrupt_event)

        done_event = getattr(action_set, "_running_done_event", None)
        if done_event is None:
            done_event = asyncio.Event()
            done_event.set()
            setattr(action_set, "_running_done_event", done_event)

        if not hasattr(action_set, "_runner_task"):
            setattr(action_set, "_runner_task", None)

        return interrupt_event, done_event

    async def _changeable_list_for_each_async(
        self,
        list_provider: Callable[[], list[Any]],
        action: Callable[[Any], Awaitable[None]],
        interrupt_event: asyncio.Event,
    ) -> None:
        if interrupt_event.is_set():
            return

        current_list = list(list_provider())
        i = 0

        while True:
            if i >= len(current_list):
                break

            item = current_list[i]
            await action(item)

            if interrupt_event.is_set():
                break

            new_list = list(list_provider())
            if len(new_list) != len(current_list) or new_list != current_list:
                current_list = new_list
                try:
                    new_index = current_list.index(item)
                except ValueError:
                    continue
                i = new_index + 1
            else:
                i += 1
