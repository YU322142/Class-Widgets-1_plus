from __future__ import annotations

from automation.lifecycle_bus import ApplicationLifetime
from automation.registry import register_trigger
from automation.trigger_base import TriggerBase


@register_trigger("classisland.lifetime.stopping", "应用退出时")
class AppStoppingTrigger(TriggerBase):
    def __init__(self, context=None, services=None) -> None:
        super().__init__(context=context, services=services)
        self._handler = None
        self._triggered = False

    def Loaded(self) -> None:
        bus = self._get_lifecycle_bus()

        def _on_stopping():
            # 防止重复退出路径导致重复触发
            if self._triggered:
                return
            self._triggered = True
            self.Trigger()

        self._handler = _on_stopping
        bus.AddStoppingHandler(_on_stopping)

        # 如果工作流加载时应用已经在停止阶段，立即补触发一次
        try:
            if getattr(bus, "Phase", None) == ApplicationLifetime.Stopping:
                _on_stopping()
        except Exception:
            pass

    def UnLoaded(self) -> None:
        if self._handler is None:
            return

        try:
            bus = self._get_lifecycle_bus()
            bus.RemoveStoppingHandler(self._handler)
        finally:
            self._handler = None

    def _get_lifecycle_bus(self):
        if self.Context is not None and getattr(self.Context, "lifecycle_bus", None) is not None:
            return self.Context.lifecycle_bus

        if self.Services is not None:
            if isinstance(self.Services, dict) and self.Services.get("lifecycle_bus") is not None:
                return self.Services["lifecycle_bus"]
            if getattr(self.Services, "lifecycle_bus", None) is not None:
                return self.Services.lifecycle_bus

        raise RuntimeError("Lifecycle bus is not configured")
