from __future__ import annotations

from automation.models import UriTriggerSettings
from automation.registry import register_trigger
from automation.trigger_base import TriggerBaseT


@register_trigger("classisland.uri", "调用 Uri 时")
class UriTrigger(TriggerBaseT[UriTriggerSettings]):
    def __init__(self, context=None, services=None) -> None:
        super().__init__(context=context, services=services)
        self._run_handler = None
        self._revert_handler = None

    def _get_uri_bus(self):
        if self.Context is not None and getattr(self.Context, "uri_bus", None) is not None:
            return self.Context.uri_bus
        if self.Services is not None:
            if isinstance(self.Services, dict) and self.Services.get("uri_bus") is not None:
                return self.Services["uri_bus"]
            if getattr(self.Services, "uri_bus", None) is not None:
                return self.Services.uri_bus
        raise RuntimeError("URI bus is not configured")

    def Loaded(self) -> None:
        bus = self._get_uri_bus()

        def _run(event):
            if event.Name == self.Settings.UriSuffix:
                self.Trigger()

        def _revert(event):
            if event.Name == self.Settings.UriSuffix:
                self.TriggerRevert()

        self._run_handler = _run
        self._revert_handler = _revert
        bus.AddRunHandler(_run)
        bus.AddRevertHandler(_revert)

    def UnLoaded(self) -> None:
        bus = self._get_uri_bus()
        if self._run_handler is not None:
            bus.RemoveRunHandler(self._run_handler)
        if self._revert_handler is not None:
            bus.RemoveRevertHandler(self._revert_handler)
        self._run_handler = None
        self._revert_handler = None
