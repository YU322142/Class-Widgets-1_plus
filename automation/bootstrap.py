from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .action_service import ActionService
from .automation_service import AutomationService
from .builtins import register_builtins
from .context import AutomationContext
from .lessons_bridge import LessonsBridge
from .lifecycle_bus import ApplicationLifetime, LifecycleBus
from .notification_host import NotificationHost
from .ruleset_service import RulesetService
from .settings_overlay import SettingsOverlayManager
from .signal_bus import SignalBus
from .tray_bus import TrayMenuBus
from .uri_bus import UriBus


class AutomationRuntime:
    """
    一个项目接入用的小型 bootstrap。
    你后面可以直接在 main.py 里实例化它。
    """

    def __init__(
        self,
        *,
        settings: Any = None,
        logger: logging.Logger | None = None,
        notification_host: NotificationHost | None = None,
    ) -> None:
        # 关键：确保所有内置 actions / triggers 已注册
        register_builtins()

        self.logger = logger or logging.getLogger(__name__)

        self.lifecycle_bus = LifecycleBus()
        self.signal_bus = SignalBus()
        self.uri_bus = UriBus()
        self.tray_bus = TrayMenuBus()
        self.lessons_bridge = LessonsBridge()
        self.notification_host = notification_host or NotificationHost()

        self.ruleset_service = RulesetService(logger=self.logger)

        self.context = AutomationContext(
            logger=self.logger,
            settings=settings,
            settings_overlay=(SettingsOverlayManager(settings) if settings is not None else None),
            notification_host=self.notification_host,
            signal_bus=self.signal_bus,
            uri_bus=self.uri_bus,
            tray_bus=self.tray_bus,
            lessons_bridge=self.lessons_bridge,
            ruleset_service=self.ruleset_service,
            lifecycle_bus=self.lifecycle_bus,
            get_now=lambda: datetime.now(),
        )

        self.action_service = ActionService(
            logger=self.logger,
            context=self.context,
            services=self,
        )
        self.automation_service = AutomationService(
            action_service=self.action_service,
            ruleset_service=self.ruleset_service,
            logger=self.logger,
            context=self.context,
            services=self,
            is_enabled_getter=self._is_enabled,
        )

    def _is_enabled(self) -> bool:
        settings = self.context.settings
        if settings is None:
            return True
        return bool(getattr(settings, "IsAutomationEnabled", True))

    def load_workflows(self, path: str | Path) -> None:
        self.automation_service.LoadFromFile(path)

    def save_workflows(self, path: str | Path | None = None) -> None:
        self.automation_service.SaveToFile(path)

    def refresh_configs(self, automations_dir: str | Path) -> None:
        self.automation_service.RefreshConfigs(automations_dir)

    def start(self) -> None:
        self.automation_service.Start()

    async def stop(self) -> None:
        self.lifecycle_bus.EmitStopping()
        await self.automation_service.Stop()

    def mark_running(self) -> None:
        self.lifecycle_bus.SetPhase(ApplicationLifetime.Running)
