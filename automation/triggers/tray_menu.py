from __future__ import annotations

from automation.models import TrayMenuTriggerSettings
from automation.registry import register_trigger
from automation.trigger_base import TriggerBaseT


@register_trigger("classisland.trayMenu", "从托盘菜单运行时")
class TrayMenuTrigger(TriggerBaseT[TrayMenuTriggerSettings]):
    def __init__(self, context=None, services=None) -> None:
        super().__init__(context=context, services=services)
        self._menu_item_id = None

    def _get_tray_bus(self):
        if self.Context is not None and getattr(self.Context, "tray_bus", None) is not None:
            return self.Context.tray_bus
        if self.Services is not None:
            if isinstance(self.Services, dict) and self.Services.get("tray_bus") is not None:
                return self.Services["tray_bus"]
            if getattr(self.Services, "tray_bus", None) is not None:
                return self.Services.tray_bus
        raise RuntimeError("Tray bus is not configured")

    def Loaded(self) -> None:
        bus = self._get_tray_bus()

        def _on_click():
            if self.Settings.IsRevert:
                self.TriggerRevert()
            else:
                self.Trigger()

        self._menu_item_id = bus.AddMenuItem(self.Settings.Header, _on_click)

    def UnLoaded(self) -> None:
        if self._menu_item_id is None:
            return
        bus = self._get_tray_bus()
        bus.RemoveMenuItem(self._menu_item_id)
        self._menu_item_id = None
