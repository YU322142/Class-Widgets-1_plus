from __future__ import annotations

from automation.action_base import ActionBaseT
from automation.context import maybe_await
from automation.models import WeatherNotificationActionSettings
from automation.registry import register_action


@register_action("classisland.notification.weather", "显示天气提醒", add_default_to_menu=False)
class WeatherNotificationAction(ActionBaseT[WeatherNotificationActionSettings]):
    async def OnInvoke(self) -> None:
        if self.Context is None:
            raise RuntimeError("AutomationContext is not configured")

        kind = int(self.Settings.NotificationKind)

        try:
            if getattr(self.Context, "logger", None) is not None:
                self.Context.logger.info(f"[AutomationWeather] NotificationKind={kind}")
        except Exception:
            pass

        # 0 = 三天天气预报
        if kind == 0:
            if self.Context.show_weather_forecast is None:
                raise RuntimeError("AutomationContext.show_weather_forecast is not configured")
            await maybe_await(self.Context.show_weather_forecast())
            return

        # 1 = 天气预警
        if kind == 1:
            if self.Context.show_weather_alerts is None:
                raise RuntimeError("AutomationContext.show_weather_alerts is not configured")
            await maybe_await(self.Context.show_weather_alerts())
            return

        # 2 = 逐小时天气
        if kind == 2:
            if self.Context.show_weather_forecast_hourly is None:
                raise RuntimeError("AutomationContext.show_weather_forecast_hourly is not configured")
            await maybe_await(self.Context.show_weather_forecast_hourly())
            return

        raise ValueError(f"Unsupported NotificationKind: {kind}")
