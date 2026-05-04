import asyncio
from datetime import datetime

from automation.action_service import ActionService
from automation.context import AutomationContext
from automation.models import (
    ActionItem,
    ActionSet,
    CronTriggerSettings,
    NotificationActionSettings,
    TrayMenuTriggerSettings,
    TriggerSettings,
    UriTriggerSettings,
    WeatherNotificationActionSettings,
)
from automation.notification_host import NotificationHost
from automation.notification_runtime import NotificationRequest
from automation.registry import create_trigger_instance

# force registrations
from automation.actions.notification import NotificationAction  # noqa: F401
from automation.actions.weather_notification import WeatherNotificationAction  # noqa: F401
from automation.triggers.cron import CronTrigger, cron_matches  # noqa: F401
from automation.triggers.uri import UriTrigger  # noqa: F401
from automation.triggers.tray_menu import TrayMenuTrigger  # noqa: F401

from automation.tray_bus import TrayMenuBus
from automation.uri_bus import UriBus


class DummyNotificationConsumer:
    def __init__(self, complete_delay: float = 0.05):
        self.AcceptsNotificationRequests = True
        self.QueuedNotificationCount = 0
        self.requests = []
        self.complete_delay = complete_delay

    def ReceiveNotifications(self, notification_requests):
        self.requests.extend(notification_requests)
        self.QueuedNotificationCount += len(notification_requests)

        for request in notification_requests:
            asyncio.create_task(self._complete_request(request))

    async def _complete_request(self, request: NotificationRequest):
        try:
            # 如果被取消，优先结束
            wait_cancel = asyncio.create_task(request.CancellationTokenSource.wait())
            wait_done = asyncio.create_task(asyncio.sleep(self.complete_delay))
            done, pending = await asyncio.wait(
                {wait_cancel, wait_done},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
        finally:
            request.CompletedTokenSource.cancel()
            self.QueuedNotificationCount = max(0, self.QueuedNotificationCount - 1)


async def test_notification_action_wait_complete():
    host = NotificationHost()
    consumer = DummyNotificationConsumer(complete_delay=0.05)
    host.RegisterNotificationConsumer(consumer, priority=0)

    ctx = AutomationContext(notification_host=host)
    svc = ActionService(context=ctx)

    aset = ActionSet(
        Name="notification-wait",
        Actions=[
            ActionItem(
                Id="classisland.showNotification",
                Settings=NotificationActionSettings(
                    Mask="hello-mask",
                    Content="hello-content",
                    IsWaitForCompleteEnabled=True,
                ),
            )
        ],
    )

    await svc.InvokeActionSetAsync(aset)

    assert len(consumer.requests) == 1
    req = consumer.requests[0]
    assert req.MaskContent.Content["type"] == "two_icons_mask"
    assert req.OverlayContent is not None
    assert req.OverlayContent.Content["type"] == "simple_text"
    assert req.CompletedTokenSource.is_set() is True
    print("=== notification action wait complete OK ===")


async def test_notification_action_interrupt():
    host = NotificationHost()
    consumer = DummyNotificationConsumer(complete_delay=5.0)
    host.RegisterNotificationConsumer(consumer, priority=0)

    ctx = AutomationContext(notification_host=host)
    svc = ActionService(context=ctx)

    aset = ActionSet(
        Name="notification-interrupt",
        Actions=[
            ActionItem(
                Id="classisland.showNotification",
                Settings=NotificationActionSettings(
                    Mask="interrupt-mask",
                    Content="interrupt-content",
                    IsWaitForCompleteEnabled=True,
                ),
            )
        ],
    )

    task = asyncio.create_task(svc.InvokeActionSetAsync(aset))
    await asyncio.sleep(0.1)
    await svc.InterruptActionSetAsync(aset)
    await task

    assert len(consumer.requests) == 1
    req = consumer.requests[0]
    assert req.CancellationTokenSource.is_set() is True
    assert req.CompletedTokenSource.is_set() is True
    print("=== notification action interrupt OK ===")


async def test_weather_notification_action():
    events = []

    async def show_forecast():
        events.append("forecast")

    async def show_alerts():
        events.append("alerts")

    async def show_hourly():
        events.append("hourly")

    ctx = AutomationContext(
        show_weather_forecast=show_forecast,
        show_weather_alerts=show_alerts,
        show_weather_forecast_hourly=show_hourly,
    )
    svc = ActionService(context=ctx)

    aset = ActionSet(
        Name="weather-notify",
        Actions=[
            ActionItem(
                Id="classisland.notification.weather",
                Settings=WeatherNotificationActionSettings(NotificationKind=0),
            ),
            ActionItem(
                Id="classisland.notification.weather",
                Settings=WeatherNotificationActionSettings(NotificationKind=1),
            ),
            ActionItem(
                Id="classisland.notification.weather",
                Settings=WeatherNotificationActionSettings(NotificationKind=2),
            ),
        ],
    )

    await svc.InvokeActionSetAsync(aset)
    assert events == ["forecast", "alerts", "hourly"]
    print("=== weather notification action OK ===")


def test_cron_matches_basic():
    dt = datetime(2024, 1, 1, 12, 1, 0)

    assert cron_matches("* * * * *", dt) is True
    assert cron_matches("1 12 * * *", dt) is True
    assert cron_matches("2 12 * * *", dt) is False
    assert cron_matches("*/5 * * * *", datetime(2024, 1, 1, 12, 10, 0)) is True
    assert cron_matches("*/5 * * * *", datetime(2024, 1, 1, 12, 11, 0)) is False

    print("=== cron matches basic OK ===")


async def test_cron_trigger_runtime():
    current = {"now": datetime(2024, 1, 1, 12, 0, 0)}
    ctx = AutomationContext(get_now=lambda: current["now"])

    trig = TriggerSettings(
        Id="classisland.cron",
        Settings=CronTriggerSettings(CronExpression="1 12 * * *"),
    )
    trigger = create_trigger_instance(trig, context=ctx, services=None)
    assert trigger is not None

    fired = []

    async def on_triggered(sender):
        fired.append("run")

    trigger.AddTriggeredHandler(on_triggered)
    trigger.Loaded()

    await asyncio.sleep(0.2)
    assert fired == []

    current["now"] = datetime(2024, 1, 1, 12, 1, 0)
    await asyncio.sleep(0.2)
    trigger.UnLoaded()

    assert fired == ["run"]
    print("=== cron trigger runtime OK ===")


async def test_uri_trigger():
    uri_bus = UriBus()
    ctx = AutomationContext(uri_bus=uri_bus)

    trig = TriggerSettings(
        Id="classisland.uri",
        Settings=UriTriggerSettings(UriSuffix="hello/world"),
    )
    trigger = create_trigger_instance(trig, context=ctx, services=None)
    assert trigger is not None

    fired = []
    reverted = []

    async def on_triggered(sender):
        fired.append("run")

    async def on_reverted(sender):
        reverted.append("revert")

    trigger.AddTriggeredHandler(on_triggered)
    trigger.AddTriggeredRevertHandler(on_reverted)
    trigger.Loaded()

    uri_bus.EmitRun("hello/world")
    uri_bus.EmitRevert("hello/world")
    await asyncio.sleep(0.05)

    trigger.UnLoaded()

    assert fired == ["run"]
    assert reverted == ["revert"]
    print("=== uri trigger OK ===")


async def test_tray_menu_trigger():
    tray_bus = TrayMenuBus()
    ctx = AutomationContext(tray_bus=tray_bus)

    trig = TriggerSettings(
        Id="classisland.trayMenu",
        Settings=TrayMenuTriggerSettings(Header="Run me", IsRevert=False),
    )
    trigger = create_trigger_instance(trig, context=ctx, services=None)
    assert trigger is not None

    fired = []

    async def on_triggered(sender):
        fired.append("run")

    trigger.AddTriggeredHandler(on_triggered)
    trigger.Loaded()

    assert len(tray_bus.Items) == 1
    item_id = next(iter(tray_bus.Items.keys()))
    assert tray_bus.Items[item_id].Header == "Run me"

    tray_bus.Click(item_id)
    await asyncio.sleep(0.05)
    trigger.UnLoaded()

    assert fired == ["run"]
    assert len(tray_bus.Items) == 0
    print("=== tray menu trigger OK ===")


async def main():
    await test_notification_action_wait_complete()
    await test_notification_action_interrupt()
    await test_weather_notification_action()
    test_cron_matches_basic()
    await test_cron_trigger_runtime()
    await test_uri_trigger()
    await test_tray_menu_trigger()
    print("\nALL STAGE-5 TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
