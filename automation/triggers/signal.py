from __future__ import annotations

from automation.models import SignalTriggerSettings
from automation.registry import register_trigger
from automation.trigger_base import TriggerBaseT


@register_trigger("classisland.signal", "收到信号时")
class SignalTrigger(TriggerBaseT[SignalTriggerSettings]):
    def __init__(self, context=None, services=None) -> None:
        super().__init__(context=context, services=services)
        self._bound_handler = None

    def _get_signal_bus(self):
        if self.Context is not None and getattr(self.Context, "signal_bus", None) is not None:
            return self.Context.signal_bus
        if self.Services is not None:
            if isinstance(self.Services, dict) and self.Services.get("signal_bus") is not None:
                return self.Services["signal_bus"]
            if getattr(self.Services, "signal_bus", None) is not None:
                return self.Services.signal_bus
        raise RuntimeError("Signal bus is not configured")

    def Loaded(self) -> None:
        bus = self._get_signal_bus()

        def _handler(event) -> None:
            if event.SignalName != self.Settings.SignalName:
                return

            if event.Revert:
                self.TriggerRevert()
            else:
                self.Trigger()

        self._bound_handler = _handler
        bus.AddHandler(_handler)

    def UnLoaded(self) -> None:
        if self._bound_handler is None:
            return
        bus = self._get_signal_bus()
        bus.RemoveHandler(self._bound_handler)
        self._bound_handler = None
