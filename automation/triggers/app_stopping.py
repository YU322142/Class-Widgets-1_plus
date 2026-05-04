from __future__ import annotations

from automation.registry import register_trigger
from automation.trigger_base import TriggerBase


@register_trigger("classisland.lifetime.stopping", "应用退出时")
class AppStoppingTrigger(TriggerBase):
    def __init__(self, context=None, services=None) -> None:
        super().__init__(context=context, services=services)
        self._handler = None

    def Loaded(self) -> None:
        bus = self._get_lifecycle_bus()

        def _on_stopping():
            self.Trigger()

        self._handler = _on_stopping
        bus.AddStoppingHandler(_on_stopping)

    def UnLoaded(self) -> None:
        if self._handler is None:
            return
        bus = self._get_lifecycle_bus()
        bus.RemoveStoppingHandler(self._handler)
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
