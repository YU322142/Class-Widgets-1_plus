from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Callable


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


@dataclass
class AutomationContext:
    """
    给 actions / triggers / services 共享的运行上下文。
    """

    logger: logging.Logger | None = None

    # settings
    settings: Any = None
    settings_overlay: Any = None

    # core services / buses
    notification_host: Any = None
    signal_bus: Any = None
    uri_bus: Any = None
    tray_bus: Any = None
    lessons_bridge: Any = None
    ruleset_service: Any = None
    lifecycle_bus: Any = None

    # lifecycle hooks
    app_quit: Callable[[], Any] | None = None
    app_restart: Callable[[bool], Any] | None = None

    # run/open hooks
    open_application: Callable[[str, str], Any] | None = None
    open_file: Callable[[str], Any] | None = None
    open_folder: Callable[[str], Any] | None = None
    open_url: Callable[[str], Any] | None = None

    # weather action hooks
    show_weather_forecast: Callable[[], Any] | None = None
    show_weather_alerts: Callable[[], Any] | None = None
    show_weather_forecast_hourly: Callable[[], Any] | None = None

    # clock
    get_now: Callable[[], Any] | None = None
