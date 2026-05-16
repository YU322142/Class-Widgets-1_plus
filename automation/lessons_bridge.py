from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Callable

from .async_tools import schedule_awaitable
from .enums import TimeState


LOGGER = logging.getLogger(__name__)

EventHandler = Callable[[], Any]


class LessonsBridge:
    """
    一个贴近 ClassIsland ILessonsService 事件语义的 Python 桥接层。

    目标：
    - 提供 PreMainTimerTicked / PostMainTimerTicked
    - 提供 CurrentTimeStateChanged / OnClass / OnBreakingTime / OnAfterSchool
    - 保持事件顺序与 ClassIsland 接近
    """

    def __init__(self) -> None:
        self.CurrentState: TimeState = TimeState.None_
        self.CurrentOverlayStatus: TimeState = TimeState.None_
        self._current_overlay_event_status: TimeState = TimeState.None_

        # 这些属性供 automation lessons bridge / trigger / rule 使用
        self.CurrentClassPlan: Any = None
        self.CurrentTimeLayoutItem: Any = None
        self.NextClassTimeLayoutItem: Any = None
        self.NextBreakingTimeLayoutItem: Any = None
        self.CurrentSubject: Any = None
        self.NextClassSubject: Any = None
        self.PreviousSubject: Any = None
        self.OnClassLeftTime: Any = None
        self.OnBreakingTimeLeftTime: Any = None

        self._pre_main_timer_ticked_handlers: list[EventHandler] = []
        self._post_main_timer_ticked_handlers: list[EventHandler] = []
        self._on_class_handlers: list[EventHandler] = []
        self._on_breaking_time_handlers: list[EventHandler] = []
        self._on_after_school_handlers: list[EventHandler] = []
        self._current_time_state_changed_handlers: list[EventHandler] = []

        self._timer_running: bool = False

    # =========================================================
    # Timer-like semantics
    # =========================================================

    def StartMainTimer(self) -> None:
        self._timer_running = True

    def StopMainTimer(self) -> None:
        self._timer_running = False

    @property
    def IsTimerRunning(self) -> bool:
        return self._timer_running

    async def Tick(self, processor: Callable[["LessonsBridge"], Any] | None = None) -> None:
        """
        模拟一次主循环 tick：
        PreMainTimerTicked -> processor -> PostMainTimerTicked
        """
        self._emit(self._pre_main_timer_ticked_handlers)

        if processor is not None:
            result = processor(self)
            if inspect.isawaitable(result):
                await result

        self._emit(self._post_main_timer_ticked_handlers)

    # =========================================================
    # State update
    # =========================================================

    def UpdateCurrentState(self, new_state: TimeState) -> None:
        """
        对齐 ClassIsland LessonsService.ProcessLessons() 中
        状态变化事件发射顺序：
        1. CurrentTimeStateChanged
        2. OnClass / OnBreakingTime / OnAfterSchool
        3. 更新 overlay event status
        """
        if not isinstance(new_state, TimeState):
            new_state = TimeState.from_value(new_state)

        self.CurrentState = new_state

        if self.CurrentState != self._current_overlay_event_status:
            self._emit(self._current_time_state_changed_handlers)

            if self.CurrentState == TimeState.OnClass:
                self._emit(self._on_class_handlers)
            elif self.CurrentState == TimeState.Breaking:
                self._emit(self._on_breaking_time_handlers)
            elif self.CurrentState == TimeState.AfterSchool:
                self._emit(self._on_after_school_handlers)

            self._current_overlay_event_status = self.CurrentState

    # =========================================================
    # Event registration
    # =========================================================

    def AddPreMainTimerTickedHandler(self, handler: EventHandler) -> None:
        if handler not in self._pre_main_timer_ticked_handlers:
            self._pre_main_timer_ticked_handlers.append(handler)

    def RemovePreMainTimerTickedHandler(self, handler: EventHandler) -> None:
        if handler in self._pre_main_timer_ticked_handlers:
            self._pre_main_timer_ticked_handlers.remove(handler)

    def AddPostMainTimerTickedHandler(self, handler: EventHandler) -> None:
        if handler not in self._post_main_timer_ticked_handlers:
            self._post_main_timer_ticked_handlers.append(handler)

    def RemovePostMainTimerTickedHandler(self, handler: EventHandler) -> None:
        if handler in self._post_main_timer_ticked_handlers:
            self._post_main_timer_ticked_handlers.remove(handler)

    def AddOnClassHandler(self, handler: EventHandler) -> None:
        if handler not in self._on_class_handlers:
            self._on_class_handlers.append(handler)

    def RemoveOnClassHandler(self, handler: EventHandler) -> None:
        if handler in self._on_class_handlers:
            self._on_class_handlers.remove(handler)

    def AddOnBreakingTimeHandler(self, handler: EventHandler) -> None:
        if handler not in self._on_breaking_time_handlers:
            self._on_breaking_time_handlers.append(handler)

    def RemoveOnBreakingTimeHandler(self, handler: EventHandler) -> None:
        if handler in self._on_breaking_time_handlers:
            self._on_breaking_time_handlers.remove(handler)

    def AddOnAfterSchoolHandler(self, handler: EventHandler) -> None:
        if handler not in self._on_after_school_handlers:
            self._on_after_school_handlers.append(handler)

    def RemoveOnAfterSchoolHandler(self, handler: EventHandler) -> None:
        if handler in self._on_after_school_handlers:
            self._on_after_school_handlers.remove(handler)

    def AddCurrentTimeStateChangedHandler(self, handler: EventHandler) -> None:
        if handler not in self._current_time_state_changed_handlers:
            self._current_time_state_changed_handlers.append(handler)

    def RemoveCurrentTimeStateChangedHandler(self, handler: EventHandler) -> None:
        if handler in self._current_time_state_changed_handlers:
            self._current_time_state_changed_handlers.remove(handler)

    # =========================================================
    # Debug helpers
    # =========================================================

    def DebugTriggerOnClass(self) -> None:
        self._emit(self._on_class_handlers)

    def DebugTriggerOnBreakingTime(self) -> None:
        self._emit(self._on_breaking_time_handlers)

    def DebugTriggerOnAfterSchool(self) -> None:
        self._emit(self._on_after_school_handlers)

    def DebugTriggerOnStateChanged(self) -> None:
        self._emit(self._current_time_state_changed_handlers)

    # =========================================================
    # Internal
    # =========================================================

    def _emit(self, handlers: list[EventHandler]) -> None:
        for handler in list(handlers):
            try:
                result = handler()
                schedule_awaitable(result)
            except Exception:
                # 旧版这里是 pass，导致触发器异常完全无日志。
                # 自动化问题排查时非常痛苦，所以这里保留主流程不中断，但记录异常。
                LOGGER.exception("LessonsBridge event handler failed")
