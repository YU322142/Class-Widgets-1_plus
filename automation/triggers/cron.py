from __future__ import annotations

import asyncio
from concurrent.futures import Future as ConcurrentFuture
from datetime import datetime

from automation.async_tools import schedule_coro
from automation.models import CronTriggerSettings
from automation.registry import register_trigger
from automation.trigger_base import TriggerBaseT


def _parse_cron_field(field: str, value: int, minimum: int, maximum: int) -> bool:
    field = field.strip()
    if field == "*":
        return True

    for part in field.split(","):
        part = part.strip()
        if not part:
            continue

        if "/" in part:
            base, step_text = part.split("/", 1)
            step = int(step_text)

            if base == "*":
                if (value - minimum) % step == 0:
                    return True
                continue

            if "-" in base:
                start_text, end_text = base.split("-", 1)
                start = int(start_text)
                end = int(end_text)
                if start <= value <= end and (value - start) % step == 0:
                    return True
                continue

            base_value = int(base)
            if value == base_value:
                return True
            continue

        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start <= value <= end:
                return True
            continue

        if int(part) == value:
            return True

    return False


def cron_matches(expression: str, dt: datetime) -> bool:
    """
    兼容 5-field cron:
    minute hour day month day_of_week

    day_of_week:
    - 0 or 7 = Sunday
    - 1 = Monday
    ...
    - 6 = Saturday
    """
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError(f"Invalid cron expression: {expression}")

    minute_f, hour_f, dom_f, month_f, dow_f = fields

    minute_match = _parse_cron_field(minute_f, dt.minute, 0, 59)
    hour_match = _parse_cron_field(hour_f, dt.hour, 0, 23)
    dom_match = _parse_cron_field(dom_f, dt.day, 1, 31)
    month_match = _parse_cron_field(month_f, dt.month, 1, 12)

    cron_dow = (dt.weekday() + 1) % 7  # Monday=1 ... Saturday=6, Sunday=0
    if "7" in dow_f:
        dow_field = dow_f.replace("7", "0")
    else:
        dow_field = dow_f
    dow_match = _parse_cron_field(dow_field, cron_dow, 0, 6)

    if not (minute_match and hour_match and month_match):
        return False

    dom_restricted = dom_f != "*"
    dow_restricted = dow_f != "*"

    if dom_restricted and dow_restricted:
        return dom_match or dow_match

    if dom_restricted:
        return dom_match

    if dow_restricted:
        return dow_match

    return True


@register_trigger("classisland.cron", "cron")
class CronTrigger(TriggerBaseT[CronTriggerSettings]):
    def __init__(self, context=None, services=None) -> None:
        super().__init__(context=context, services=services)
        self._task: asyncio.Task | ConcurrentFuture | None = None
        self._stopped = False
        self._last_minute_key = None

    def Loaded(self) -> None:
        self._stopped = False
        self._task = schedule_coro(self._worker())

    def UnLoaded(self) -> None:
        self._stopped = True
        if self._task is not None:
            try:
                self._task.cancel()
            except Exception:
                pass
            self._task = None

    def _get_now(self) -> datetime:
        if self.Context is not None and getattr(self.Context, "get_now", None) is not None:
            return self.Context.get_now()
        return datetime.now()

    async def _worker(self) -> None:
        while not self._stopped:
            now = self._get_now()
            minute_key = (now.year, now.month, now.day, now.hour, now.minute)

            try:
                if minute_key != self._last_minute_key:
                    self._last_minute_key = minute_key
                    if cron_matches(self.Settings.CronExpression, now):
                        self.Trigger()
            except Exception:
                # 非法 cron 表达式时静默，不炸主流程
                pass

            await asyncio.sleep(0.1)
