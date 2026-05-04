from __future__ import annotations

from automation.action_base import ActionBaseT
from automation.models import ModifyAppSettingsActionSettings
from automation.registry import register_action
from automation.settings_overlay import SettingsOverlayManager


@register_action("classisland.settings", "应用设置", add_default_to_menu=False)
class ModifyAppSettingsAction(ActionBaseT[ModifyAppSettingsActionSettings]):
    def _get_manager(self) -> SettingsOverlayManager:
        if self.Context is None:
            raise RuntimeError("AutomationContext is not configured")

        manager = getattr(self.Context, "settings_overlay", None)
        if manager is not None:
            return manager

        settings = getattr(self.Context, "settings", None)
        if settings is None:
            raise RuntimeError("AutomationContext.settings is not configured")

        manager = SettingsOverlayManager(settings)
        self.Context.settings_overlay = manager
        return manager

    async def OnInvoke(self) -> None:
        if self.Settings.Name == "":
            return

        manager = self._get_manager()
        if manager.GetPropertyInfoByName(self.Settings.Name) is None:
            raise KeyError(f"Settings property not found: {self.Settings.Name}")

        value = manager.ConvertToAssignableToSettingsType(self.Settings.Value, self.Settings.Name)

        if self.IsRevertable:
            manager.AddSettingsOverlay(self.ActionSet.Guid, self.Settings.Name, value)
        else:
            manager.SetValue(self.Settings.Name, value)

    async def OnRevert(self) -> None:
        if self.Settings.Name == "":
            return

        manager = self._get_manager()
        manager.RemoveSettingsOverlay(self.ActionSet.Guid, self.Settings.Name)
