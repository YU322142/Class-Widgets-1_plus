from __future__ import annotations

from datetime import datetime, time, timedelta

from automation.enums import TimeState
from automation.models import PreTimePointTriggerSettings
from automation.registry import register_trigger
from automation.trigger_base import TriggerBaseT


def _seconds_safe(seconds: float) -> timedelta:
    if seconds != seconds:  # NaN
        return timedelta(0)
    seconds = max(0.0, min(2147483.0, float(seconds)))
    return timedelta(seconds=seconds)


def _as_timedelta(value) -> timedelta | None:
    if value is None:
        return None

    if isinstance(value, timedelta):
        return value

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


@register_trigger("classisland.lessons.preTimePoint", "特定时间点前")
class PreTimePointTrigger(TriggerBaseT[PreTimePointTriggerSettings]):
    def __init__(self, context=None, services=None) -> None:
        super().__init__(context=context, services=services)
        self.LastCheckTime: datetime | None = None
        self._handler = None

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
        bridge = self._get_lessons_bridge()
        bridge.RemovePostMainTimerTickedHandler(self._handler)
        self._handler = None

    def _handle_post_tick(self) -> None:
        bridge = self._get_lessons_bridge()
        now = self._get_now()

        try:
            if bridge.CurrentState == self.Settings.TargetState:
                self.TriggerRevert()
                return

            if self.Settings.TimeSeconds < 0:
                return

            target_start_time: timedelta | None = None

            if self.Settings.TargetState == TimeState.AfterSchool:
                class_plan = getattr(bridge, "CurrentClassPlan", None)
                items = getattr(class_plan, "ValidTimeLayoutItems", None) or []
                valid = [x for x in items if getattr(x, "TimeType", None) in (0, 1)]
                if not valid:
                    return

                target_start_time = _as_timedelta(getattr(valid[-1], "EndTime", None))
                if target_start_time is None:
                    return

            else:
                if self.Settings.TargetState == TimeState.OnClass:
                    target_item = getattr(bridge, "NextClassTimeLayoutItem", None)
                elif self.Settings.TargetState == TimeState.Breaking:
                    target_item = getattr(bridge, "NextBreakingTimeLayoutItem", None)
                else:
                    target_item = None

                if target_item is None:
                    return

                target_start_time = _as_timedelta(getattr(target_item, "StartTime", None))
                if target_start_time is None:
                    return

            target_dt = _combine_date_and_timedelta(now, target_start_time - _seconds_safe(self.Settings.TimeSeconds))

            if self.LastCheckTime is not None and self.LastCheckTime < target_dt <= now:
                self.Trigger()
        finally:
            self.LastCheckTime = now

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
