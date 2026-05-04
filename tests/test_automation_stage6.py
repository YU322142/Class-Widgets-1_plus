import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

from automation.context import AutomationContext
from automation.lessons_bridge import LessonsBridge
from automation.lifecycle_bus import ApplicationLifetime, LifecycleBus
from automation.models import (
    PreTimePointTriggerSettings,
    TriggerSettings,
)
from automation.registry import create_trigger_instance
from automation.ruleset_service import RulesetService

# force registrations
from automation.triggers.app_startup import AppStartupTrigger  # noqa: F401
from automation.triggers.app_stopping import AppStoppingTrigger  # noqa: F401
from automation.triggers.current_time_state_changed import CurrentTimeStateChangedTrigger  # noqa: F401
from automation.triggers.on_class import OnClassTrigger  # noqa: F401
from automation.triggers.on_breaking_time import OnBreakingTimeTrigger  # noqa: F401
from automation.triggers.on_after_school import OnAfterSchoolTrigger  # noqa: F401
from automation.triggers.pre_time_point import PreTimePointTrigger  # noqa: F401
from automation.triggers.ruleset_changed import RulesetChangedTrigger  # noqa: F401

from automation.enums import TimeState
from automation.bootstrap import AutomationRuntime


@dataclass
class FakeTimeLayoutItem:
    TimeType: int = 0
    StartTime: timedelta = timedelta(0)
    EndTime: timedelta = timedelta(0)


@dataclass
class FakeClassPlan:
    ValidTimeLayoutItems: list = None


async def test_app_startup_trigger():
    lifecycle = LifecycleBus(phase=ApplicationLifetime.StartingOnline)
    ctx = AutomationContext(lifecycle_bus=lifecycle)

    trig = TriggerSettings(Id="classisland.lifetime.startup", Settings=None)
    trigger = create_trigger_instance(trig, context=ctx, services=None)
    assert trigger is not None

    fired = []

    async def on_triggered(sender):
        fired.append("run")

    trigger.AddTriggeredHandler(on_triggered)
    trigger.Loaded()
    await asyncio.sleep(0.05)

    assert fired == ["run"]
    print("=== app startup trigger OK ===")


async def test_app_stopping_trigger():
    lifecycle = LifecycleBus(phase=ApplicationLifetime.Running)
    ctx = AutomationContext(lifecycle_bus=lifecycle)

    trig = TriggerSettings(Id="classisland.lifetime.stopping", Settings=None)
    trigger = create_trigger_instance(trig, context=ctx, services=None)
    assert trigger is not None

    fired = []

    async def on_triggered(sender):
        fired.append("run")

    trigger.AddTriggeredHandler(on_triggered)
    trigger.Loaded()

    lifecycle.EmitStopping()
    await asyncio.sleep(0.05)
    trigger.UnLoaded()

    assert fired == ["run"]
    print("=== app stopping trigger OK ===")


async def test_ruleset_changed_trigger():
    ruleset_service = RulesetService()
    ctx = AutomationContext(ruleset_service=ruleset_service)

    trig = TriggerSettings(Id="classisland.ruleSet.rulesetChanged", Settings=None)
    trigger = create_trigger_instance(trig, context=ctx, services=None)
    assert trigger is not None

    fired = []

    async def on_triggered(sender):
        fired.append("run")

    trigger.AddTriggeredHandler(on_triggered)
    trigger.Loaded()

    ruleset_service.NotifyStatusChanged()
    await asyncio.sleep(0.05)
    trigger.UnLoaded()

    # 构造时一次 NotifyStatusChanged，不算 trigger，因为 Loaded 之后才订阅
    assert fired == ["run"]
    print("=== ruleset changed trigger OK ===")


async def test_current_time_state_changed_trigger():
    bridge = LessonsBridge()
    ctx = AutomationContext(lessons_bridge=bridge)

    trig = TriggerSettings(Id="classisland.lessons.currentTimeStateChanged", Settings=None)
    trigger = create_trigger_instance(trig, context=ctx, services=None)
    assert trigger is not None

    fired = []

    async def on_triggered(sender):
        fired.append("run")

    trigger.AddTriggeredHandler(on_triggered)
    trigger.Loaded()

    bridge.UpdateCurrentState(TimeState.OnClass)
    bridge.UpdateCurrentState(TimeState.OnClass)
    bridge.UpdateCurrentState(TimeState.Breaking)
    await asyncio.sleep(0.05)
    trigger.UnLoaded()

    assert fired == ["run", "run"]
    print("=== current time state changed trigger OK ===")


async def test_on_class_on_breaking_on_after_school_triggers():
    bridge = LessonsBridge()
    ctx = AutomationContext(lessons_bridge=bridge)

    trigger_ids = [
        "classisland.lessons.onClass",
        "classisland.lessons.onBreakingTime",
        "classisland.lessons.onAfterSchool",
    ]
    results = {tid: [] for tid in trigger_ids}
    triggers = []

    for tid in trigger_ids:
        trig = TriggerSettings(Id=tid, Settings=None)
        trigger = create_trigger_instance(trig, context=ctx, services=None)
        assert trigger is not None

        async def make_handler(sender, tid=tid):
            results[tid].append("run")

        trigger.AddTriggeredHandler(make_handler)
        trigger.Loaded()
        triggers.append(trigger)

    bridge.UpdateCurrentState(TimeState.OnClass)
    bridge.UpdateCurrentState(TimeState.Breaking)
    bridge.UpdateCurrentState(TimeState.AfterSchool)
    await asyncio.sleep(0.05)

    for trigger in triggers:
        trigger.UnLoaded()

    assert results["classisland.lessons.onClass"] == ["run"]
    assert results["classisland.lessons.onBreakingTime"] == ["run"]
    assert results["classisland.lessons.onAfterSchool"] == ["run"]
    print("=== on_class / on_breaking / on_after_school triggers OK ===")


async def test_pre_time_point_trigger_on_class_and_revert():
    bridge = LessonsBridge()
    current = {"now": datetime(2024, 1, 1, 8, 0, 0)}

    bridge.CurrentState = TimeState.Breaking
    bridge.NextClassTimeLayoutItem = FakeTimeLayoutItem(
        TimeType=0,
        StartTime=timedelta(hours=8, minutes=5),
        EndTime=timedelta(hours=8, minutes=50),
    )

    ctx = AutomationContext(
        lessons_bridge=bridge,
        get_now=lambda: current["now"],
    )

    trig = TriggerSettings(
        Id="classisland.lessons.preTimePoint",
        Settings=PreTimePointTriggerSettings(
            TargetState=TimeState.OnClass,
            TimeSeconds=60,
        ),
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

    # Loaded 时 LastCheckTime = 08:00:00
    # 目标时间 = 08:05:00 - 60s = 08:04:00
    current["now"] = datetime(2024, 1, 1, 8, 4, 0)
    await bridge.Tick()

    bridge.CurrentState = TimeState.OnClass
    current["now"] = datetime(2024, 1, 1, 8, 5, 1)
    await bridge.Tick()

    await asyncio.sleep(0.05)
    trigger.UnLoaded()

    assert fired == ["run"]
    assert reverted == ["revert"]
    print("=== pre time point trigger OK ===")


async def test_automation_runtime_basic():
    runtime = AutomationRuntime()
    runtime.start()
    runtime.mark_running()
    await runtime.stop()
    print("=== automation runtime basic OK ===")


async def main():
    await test_app_startup_trigger()
    await test_app_stopping_trigger()
    await test_ruleset_changed_trigger()
    await test_current_time_state_changed_trigger()
    await test_on_class_on_breaking_on_after_school_triggers()
    await test_pre_time_point_trigger_on_class_and_revert()
    await test_automation_runtime_basic()
    print("\nALL STAGE-6 TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
