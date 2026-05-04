from __future__ import annotations

from automation.lifecycle_bus import ApplicationLifetime
from automation.registry import register_trigger
from automation.trigger_base import TriggerBase


@register_trigger("classisland.lifetime.startup", "应用启动时")
class AppStartupTrigger(TriggerBase):
    def Loaded(self) -> None:
        phase = self._get_phase()
        if phase < ApplicationLifetime.Running:
            self.Trigger()

    def UnLoaded(self) -> None:
        pass

    def _get_phase(self) -> ApplicationLifetime:
        if self.Context is not None and getattr(self.Context, "lifecycle_bus", None) is not None:
            return self.Context.lifecycle_bus.Phase
        if self.Services is not None:
            if isinstance(self.Services, dict) and self.Services.get("lifecycle_bus") is not None:
                return self.Services["lifecycle_bus"].Phase
            if getattr(self.Services, "lifecycle_bus", None) is not None:
                return self.Services.lifecycle_bus.Phase
        return ApplicationLifetime.None_
