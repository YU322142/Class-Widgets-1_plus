from __future__ import annotations

from automation.action_base import ActionBaseT
from automation.models import SignalTriggerSettings
from automation.registry import register_action


@register_action("classisland.broadcastSignal", "广播信号")
class BroadcastSignalAction(ActionBaseT[SignalTriggerSettings]):
    def _get_signal_bus(self):
        if self.Context is not None and getattr(self.Context, "signal_bus", None) is not None:
            return self.Context.signal_bus
        if self.Services is not None:
            if isinstance(self.Services, dict) and self.Services.get("signal_bus") is not None:
                return self.Services["signal_bus"]
            if getattr(self.Services, "signal_bus", None) is not None:
                return self.Services.signal_bus
        raise RuntimeError("Signal bus is not configured")

    async def OnInvoke(self) -> None:
        bus = self._get_signal_bus()
        bus.EmitSignal(self.Settings.SignalName, self.Settings.IsRevert)

    async def OnRevert(self) -> None:
        bus = self._get_signal_bus()
        bus.EmitSignal(self.Settings.SignalName, not self.Settings.IsRevert)
