import asyncio

from automation.action_service import ActionService
from automation.context import AutomationContext
from automation.models import (
    ActionItem,
    ActionSet,
    AppRestartActionSettings,
    ModifyAppSettingsActionSettings,
    RunActionSettings,
    SignalTriggerSettings,
    TriggerSettings,
)
from automation.registry import create_trigger_instance
from automation.settings_overlay import SettingsOverlayManager
from automation.signal_bus import SignalBus

# force registration by import
from automation.actions.app_quit import AppQuitAction  # noqa: F401
from automation.actions.app_restart import AppRestartAction  # noqa: F401
from automation.actions.broadcast_signal import BroadcastSignalAction  # noqa: F401
from automation.actions.modify_app_settings import ModifyAppSettingsAction  # noqa: F401
from automation.actions.run import RunAction  # noqa: F401
from automation.triggers.signal import SignalTrigger  # noqa: F401


class FakeSettings:
    Count: int
    Theme: str
    Flag: bool

    def __init__(self):
        self.Count = 1
        self.Theme = "light"
        self.Flag = True
        self.SettingsOverlays = {}


async def test_modify_settings_direct():
    settings = FakeSettings()
    ctx = AutomationContext(settings=settings, settings_overlay=SettingsOverlayManager(settings))
    svc = ActionService(context=ctx)

    aset = ActionSet(
        Name="direct-settings",
        IsRevertEnabled=False,
        Actions=[
            ActionItem(
                Id="classisland.settings",
                Settings=ModifyAppSettingsActionSettings(Name="Count", Value="123"),
            )
        ],
    )

    await svc.InvokeActionSetAsync(aset)

    assert settings.Count == 123
    assert settings.SettingsOverlays == {}
    print("=== modify settings direct OK ===")


async def test_modify_settings_overlay_and_revert():
    settings = FakeSettings()
    ctx = AutomationContext(settings=settings, settings_overlay=SettingsOverlayManager(settings))
    svc = ActionService(context=ctx)

    aset = ActionSet(
        Name="overlay-settings",
        IsRevertEnabled=True,
        Actions=[
            ActionItem(
                Id="classisland.settings",
                Settings=ModifyAppSettingsActionSettings(Name="Theme", Value="dark"),
            )
        ],
    )

    await svc.InvokeActionSetAsync(aset)
    assert settings.Theme == "dark"
    assert "Theme" in settings.SettingsOverlays

    await svc.RevertActionSetAsync(aset)
    assert settings.Theme == "light"
    assert "Theme" not in settings.SettingsOverlays

    print("=== modify settings overlay/revert OK ===")


async def test_signal_action_and_trigger():
    bus = SignalBus()
    ctx = AutomationContext(signal_bus=bus)
    svc = ActionService(context=ctx)

    trig = TriggerSettings(
        Id="classisland.signal",
        Settings=SignalTriggerSettings(SignalName="hello", IsRevert=False),
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

    aset = ActionSet(
        Name="signal-action",
        IsRevertEnabled=True,
        Actions=[
            ActionItem(
                Id="classisland.broadcastSignal",
                Settings=SignalTriggerSettings(SignalName="hello", IsRevert=False),
            )
        ],
    )

    await svc.InvokeActionSetAsync(aset)
    await asyncio.sleep(0.05)
    assert fired == ["run"]

    await svc.RevertActionSetAsync(aset)
    await asyncio.sleep(0.05)
    assert reverted == ["revert"]

    trigger.UnLoaded()
    print("=== signal action + trigger OK ===")


async def test_app_quit_and_restart_hooks():
    events = []

    async def app_quit():
        events.append("quit")

    async def app_restart(quiet: bool):
        events.append(("restart", quiet))

    ctx = AutomationContext(
        app_quit=app_quit,
        app_restart=app_restart,
    )
    svc = ActionService(context=ctx)

    quit_set = ActionSet(
        Name="quit",
        Actions=[ActionItem(Id="classisland.app.quit", Settings=None)],
    )
    restart_set = ActionSet(
        Name="restart",
        Actions=[ActionItem(Id="classisland.app.restart", Settings=AppRestartActionSettings(Value=True))],
    )

    await svc.InvokeActionSetAsync(quit_set)
    await svc.InvokeActionSetAsync(restart_set)

    assert events == ["quit", ("restart", True)]
    print("=== app quit/restart hooks OK ===")


async def test_run_action_uses_context_hooks():
    events = []

    def open_application(path: str, args: str):
        events.append(("app", path, args))

    def open_file(path: str):
        events.append(("file", path))

    def open_folder(path: str):
        events.append(("folder", path))

    def open_url(url: str):
        events.append(("url", url))

    ctx = AutomationContext(
        open_application=open_application,
        open_file=open_file,
        open_folder=open_folder,
        open_url=open_url,
    )
    svc = ActionService(context=ctx)

    aset = ActionSet(
        Name="run-hooks",
        Actions=[
            ActionItem(
                Id="classisland.os.run",
                Settings=RunActionSettings(RunType="Application", Value="myapp.exe", Args="--x 1"),
            ),
            ActionItem(
                Id="classisland.os.run",
                Settings=RunActionSettings(RunType="File", Value="a.txt", Args=""),
            ),
            ActionItem(
                Id="classisland.os.run",
                Settings=RunActionSettings(RunType="Folder", Value="C:/Temp", Args=""),
            ),
            ActionItem(
                Id="classisland.os.run",
                Settings=RunActionSettings(RunType="Url", Value="example.com", Args=""),
            ),
        ],
    )

    await svc.InvokeActionSetAsync(aset)

    assert events == [
        ("app", "myapp.exe", "--x 1"),
        ("file", "a.txt"),
        ("folder", "C:/Temp"),
        ("url", "https://example.com"),
    ]
    print("=== run action hooks OK ===")


async def main():
    await test_modify_settings_direct()
    await test_modify_settings_overlay_and_revert()
    await test_signal_action_and_trigger()
    await test_app_quit_and_restart_hooks()
    await test_run_action_uses_context_hooks()
    print("\nALL STAGE-4 TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
