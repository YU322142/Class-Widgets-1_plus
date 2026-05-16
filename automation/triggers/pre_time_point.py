from __future__ import annotations

from datetime import datetime, time, timedelta

from automation.enums import TimeState
from automation.models import PreTimePointTriggerSettings
from automation.registry import register_trigger
from automation.trigger_base import TriggerBaseT


def _seconds_safe(seconds) -> timedelta:
    try:
        seconds = float(seconds)
    except Exception:
        return timedelta(0)

    if seconds != seconds:  # NaN
        return timedelta(0)

    seconds = max(0.0, min(2147483.0, seconds))
    return timedelta(seconds=seconds)


def _as_timedelta(value) -> timedelta | None:
    if value is None:
        return None

    if isinstance(value, timedelta):
        return value

    if isinstance(value, datetime):
        value = value.time()

    if isinstance(value, time):
        return timedelta(
            hours=value.hour,
            minutes=value.minute,
            seconds=value.second,
            microseconds=value.microsecond,
        )

    if isinstance(value, (int, float)):
        return timedelta(seconds=float(value))

    return None


def _combine_date_and_timedelta(dt: datetime, td: timedelta) -> datetime:
    midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight + td


def _coerce_time_state(value) -> TimeState:
    try:
        state = TimeState.from_value(value)
    except Exception:
        state = TimeState.OnClass

    # 兼容旧版本错误 UI 保存出来的 PrepareOnClass
    if state == TimeState.PrepareOnClass:
        return TimeState.OnClass

    return state


def _item_time_type(item) -> int | None:
    value = getattr(item, "TimeType", None)

    try:
        return int(value)
    except Exception:
        pass

    is_break = getattr(item, "IsBreak", None)
    if is_break is True:
        return 1
    if is_break is False:
        return 0

    return None


def _is_class_item(item) -> bool:
    return _item_time_type(item) == 0


def _is_break_item(item) -> bool:
    return _item_time_type(item) == 1


def _iter_valid_layout_items(bridge):
    class_plan = getattr(bridge, "CurrentClassPlan", None)
    items = getattr(class_plan, "ValidTimeLayoutItems", None) or []
    return list(items)


@register_trigger("classisland.lessons.preTimePoint", "特定时间点前")
class PreTimePointTrigger(TriggerBaseT[PreTimePointTriggerSettings]):
    def __init__(self, context=None, services=None) -> None:
        super().__init__(context=context, services=services)
        self.LastCheckTime: datetime | None = None
        self._handler = None

        # 防止同一个时间点因为 schedule 轻微抖动 / 重载 / current+next 双候选而重复触发
        self._last_trigger_key: tuple[int, datetime] | None = None

    def Loaded(self) -> None:
        self.LastCheckTime = self._get_now()
        bridge = self._get_lessons_bridge()

        def _on_post_tick():
            self._handle_post_tick()

        self._handler = _on_post_tick
        bridge.AddPostMainTimerTickedHandler(_on_post_tick)

    def UnLoaded(self) -> None:
        if self._handler is None:
            return

        try:
            bridge = self._get_lessons_bridge()
            bridge.RemovePostMainTimerTickedHandler(self._handler)
        finally:
            self._handler = None

    def _handle_post_tick(self) -> None:
        bridge = self._get_lessons_bridge()
        now = self._get_now()

        try:
            if self.Settings is None:
                return

            target_state = _coerce_time_state(
                getattr(self.Settings, "TargetState", TimeState.OnClass)
            )

            raw_seconds = getattr(self.Settings, "TimeSeconds", 0)
            try:
                if float(raw_seconds) < 0:
                    return
            except Exception:
                raw_seconds = 0

            ahead = _seconds_safe(raw_seconds)

            target_dts = self._get_target_datetimes(bridge, now, target_state, ahead)

            for target_dt in target_dts:
                if self.LastCheckTime is None:
                    continue

                if self.LastCheckTime < target_dt <= now:
                    key = (int(target_state), target_dt.replace(microsecond=0))
                    if self._last_trigger_key != key:
                        self._last_trigger_key = key
                        self.Trigger()
                    break

            # 注意：
            # 这里必须放在 Trigger 检测之后。
            # 原逻辑是：
            #
            #   if bridge.CurrentState == target_state:
            #       self.TriggerRevert()
            #       return
            #
            # 当 timer 卡顿，从“提前触发点”直接跨过“目标状态开始点”时，
            # PostMainTimerTicked 里 CurrentState 已经是 target_state，
            # 旧逻辑会直接 return，导致 Trigger 永远不执行。
            if _coerce_time_state(getattr(bridge, "CurrentState", TimeState.None_)) == target_state:
                self.TriggerRevert()

        finally:
            self.LastCheckTime = now

    def _get_target_datetimes(
        self,
        bridge,
        now: datetime,
        target_state: TimeState,
        ahead: timedelta,
    ) -> list[datetime]:
        result: list[datetime] = []

        if target_state == TimeState.AfterSchool:
            result.extend(self._get_after_school_target_datetimes(bridge, now, ahead))
        elif target_state == TimeState.OnClass:
            result.extend(
                self._get_item_start_target_datetimes(
                    bridge,
                    now,
                    ahead,
                    preferred_current=True,
                    item_predicate=_is_class_item,
                    next_attr="NextClassTimeLayoutItem",
                )
            )
        elif target_state == TimeState.Breaking:
            result.extend(
                self._get_item_start_target_datetimes(
                    bridge,
                    now,
                    ahead,
                    preferred_current=True,
                    item_predicate=_is_break_item,
                    next_attr="NextBreakingTimeLayoutItem",
                )
            )

        # 去重并排序，避免 CurrentTimeLayoutItem 和 Next... 指向同一个时间点时重复触发
        unique = sorted(set(result))
        return unique

    def _get_after_school_target_datetimes(
        self,
        bridge,
        now: datetime,
        ahead: timedelta,
    ) -> list[datetime]:
        items = _iter_valid_layout_items(bridge)
        valid = [x for x in items if _item_time_type(x) in (0, 1)]

        if not valid:
            return []

        end_td = _as_timedelta(getattr(valid[-1], "EndTime", None))
        if end_td is None:
            return []

        return [_combine_date_and_timedelta(now, end_td - ahead)]

    def _get_item_start_target_datetimes(
        self,
        bridge,
        now: datetime,
        ahead: timedelta,
        *,
        preferred_current: bool,
        item_predicate,
        next_attr: str,
    ) -> list[datetime]:
        candidates = []

        # 关键修复：
        # 如果当前已经进入目标状态，NextClassTimeLayoutItem / NextBreakingTimeLayoutItem
        # 通常已经跳到下一个同类时间段。
        # 但 timer 卡了一下时，真正需要补判的是“当前刚开始的这个时间段”。
        if preferred_current:
            current_item = getattr(bridge, "CurrentTimeLayoutItem", None)
            if current_item is not None and item_predicate(current_item):
                candidates.append(current_item)

        next_item = getattr(bridge, next_attr, None)
        if next_item is not None and item_predicate(next_item):
            candidates.append(next_item)

        # 再从 CurrentClassPlan 兜底找一次。
        # 这样即使 bridge.Next... 因为边界条件没填，也能从完整时间线里算出来。
        for item in _iter_valid_layout_items(bridge):
            if item_predicate(item):
                candidates.append(item)

        result: list[datetime] = []
        for item in candidates:
            start_td = _as_timedelta(getattr(item, "StartTime", None))
            if start_td is None:
                continue

            target_dt = _combine_date_and_timedelta(now, start_td - ahead)
            result.append(target_dt)

        return result

    def _get_now(self) -> datetime:
        if self.Context is not None and getattr(self.Context, "get_now", None) is not None:
            return self.Context.get_now()
        return datetime.now()

    def _get_lessons_bridge(self):
        if self.Context is not None and getattr(self.Context, "lessons_bridge", None) is not None:
            return self.Context.lessons_bridge
        if self.Services is not None:
            if isinstance(self.Services, dict) and self.Services.get("lessons_bridge") is not None:
                return self.Services["lessons_bridge"]
            if getattr(self.Services, "lessons_bridge", None) is not None:
                return self.Services.lessons_bridge
        raise RuntimeError("Lessons bridge is not configured")
