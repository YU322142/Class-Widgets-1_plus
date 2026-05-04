from __future__ import annotations

from automation.action_base import ActionBaseT
from automation.context import maybe_await
from automation.models import AppRestartActionSettings
from automation.registry import register_action


@register_action("classisland.app.restart", "重启 ClassIsland", add_default_to_menu=False)
class AppRestartAction(ActionBaseT[AppRestartActionSettings]):
    async def OnInvoke(self) -> None:
        if self.Context is None or getattr(self.Context, "app_restart", None) is None:
            raise RuntimeError("AutomationContext.app_restart is not configured")
        await maybe_await(self.Context.app_restart(self.Settings.Value))
