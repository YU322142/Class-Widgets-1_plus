from __future__ import annotations

from automation.action_base import ActionBase
from automation.context import maybe_await
from automation.registry import register_action


@register_action("classisland.app.quit", "退出 ClassIsland", add_default_to_menu=False)
class AppQuitAction(ActionBase):
    async def OnInvoke(self) -> None:
        if self.Context is None or getattr(self.Context, "app_quit", None) is None:
            raise RuntimeError("AutomationContext.app_quit is not configured")
        await maybe_await(self.Context.app_quit())
