import asyncio

from automation.action_base import ActionBaseT
from automation.action_service import ActionService
from automation.automation_service import AutomationService
from automation.enums import TimeState
from automation.lessons_bridge import LessonsBridge
from automation.models import (
    ActionItem,
    ActionSet,
    Rule,
    RuleGroup,
    Ruleset,
    SignalTriggerSettings,
    SleepActionSettings,
    TriggerSettings,
    Workflow,
)
from automation.registry import (
    RULE_INFOS,
    register_action,
    register_rule,
    register_trigger,
)
from automation.ruleset_service import RulesetService
from automation.trigger_base import TriggerBaseT


# =========================================================
# Shared test context
# =========================================================

class TestContext:
    def __init__(self):
        self.events = []
        self.lifecycle = 0  # mimic "before Running"


# =========================================================
# Test actions
# =========================================================

@register_action("classisland.test.stage3.record", "记录 action")
class RecordAction(ActionBaseT[SleepActionSettings]):
    async def OnInvoke(self):
        self.Context.events.append(f"invoke:{self.Settings.Value}")

    async def OnRevert(self):
        self.Context.events.append(f"revert:{self.Settings.Value}")


# =========================================================
# Test triggers
# =========================================================

@register_trigger("classisland.test.stage3.manual", "手动触发器")
class ManualTrigger(TriggerBaseT[SignalTriggerSettings]):
    def Loaded(self):
        pass

    def UnLoaded(self):
        pass


@register_trigger("classisland.test.stage3.startup_like", "启动即触发")
class StartupLikeTrigger(TriggerBaseT[SignalTriggerSettings]):
    def Loaded(self):
        # 模拟 AppStartupTrigger 的核心语义：加载时若还没 Running，就直接触发
        if getattr(self.Context, "lifecycle", 0) < 5:
            self.Trigger()

    def UnLoaded(self):
        pass


# =========================================================
# Helpers
# =========================================================

def ensure_rule_registered(rule_id, name, handler):
    if rule_id not in RULE_INFOS:
        register_rule(rule_id, name=name, handler=handler)
    else:
        RULE_INFOS[rule_id].Handle = handler


def build_record_workflow(
    trigger_id: str,
    value: float,
    *,
    revert_enabled: bool = False,
    condition_enabled: bool = False,
    ruleset: Ruleset | None = None,
) -> Workflow:
    return Workflow(
        Triggers=[
            TriggerSettings(
                Id=trigger_id,
                Settings=SignalTriggerSettings(SignalName="x", IsRevert=False),
            )
        ],
        IsConditionEnabled=condition_enabled,
        Ruleset=ruleset or Ruleset(),
        ActionSet=ActionSet(
            Name=f"wf-{trigger_id}-{value}",
            IsEnabled=True,
            IsRevertEnabled=revert_enabled,
            Actions=[
                ActionItem(
                    Id="classisland.test.stage3.record",
                    Settings=SleepActionSettings(Value=value),
                )
            ],
        ),
    )


# =========================================================
# Automation tests
# =========================================================

async def test_manual_trigger_runs_action():
    ctx = TestContext()
    action_service = ActionService(context=ctx)
    ruleset_service = RulesetService()
    automation_service = AutomationService(
        action_service=action_service,
        ruleset_service=ruleset_service,
        context=ctx,
        services=None,
    )

    wf = build_record_workflow("classisland.test.stage3.manual", 1)
    automation_service.SetWorkflows([wf])
    automation_service.Start()

    trigger = wf.Triggers[0].TriggerInstance
    trigger.Trigger()
    await automation_service.DrainTasks()

    assert ctx.events == ["invoke:1"]
    print("=== automation manual trigger OK ===")


async def test_startup_like_trigger_runs_on_load():
    ctx = TestContext()
    action_service = ActionService(context=ctx)
    ruleset_service = RulesetService()
    automation_service = AutomationService(
        action_service=action_service,
        ruleset_service=ruleset_service,
        context=ctx,
        services=None,
    )

    wf = build_record_workflow("classisland.test.stage3.startup_like", 2)
    automation_service.SetWorkflows([wf])
    automation_service.Start()
    await automation_service.DrainTasks()

    assert ctx.events == ["invoke:2"]
    print("=== automation startup-like trigger OK ===")


async def test_ruleset_blocks_trigger():
    ctx = TestContext()
    action_service = ActionService(context=ctx)
    ruleset_service = RulesetService()

    flag = {"ok": False}
    ensure_rule_registered("classisland.test.stage3.rule", "测试规则", lambda s: flag["ok"])

    wf = build_record_workflow(
        "classisland.test.stage3.manual",
        3,
        condition_enabled=True,
        ruleset=Ruleset(
            Groups=[
                RuleGroup(
                    Rules=[Rule(Id="classisland.test.stage3.rule")]
                )
            ]
        ),
    )

    automation_service = AutomationService(
        action_service=action_service,
        ruleset_service=ruleset_service,
        context=ctx,
        services=None,
    )
    automation_service.SetWorkflows([wf])
    automation_service.Start()

    trigger = wf.Triggers[0].TriggerInstance

    # false -> 不执行
    trigger.Trigger()
    await automation_service.DrainTasks()
    assert ctx.events == []

    # true -> 执行
    flag["ok"] = True
    trigger.Trigger()
    await automation_service.DrainTasks()
    assert ctx.events == ["invoke:3"]

    print("=== automation ruleset block OK ===")


async def test_ruleset_invalidates_and_reverts():
    ctx = TestContext()
    action_service = ActionService(context=ctx)
    ruleset_service = RulesetService()

    flag = {"ok": True}
    ensure_rule_registered("classisland.test.stage3.rule2", "测试规则2", lambda s: flag["ok"])

    wf = build_record_workflow(
        "classisland.test.stage3.manual",
        4,
        revert_enabled=True,
        condition_enabled=True,
        ruleset=Ruleset(
            Groups=[
                RuleGroup(
                    Rules=[Rule(Id="classisland.test.stage3.rule2")]
                )
            ]
        ),
    )

    automation_service = AutomationService(
        action_service=action_service,
        ruleset_service=ruleset_service,
        context=ctx,
        services=None,
    )
    automation_service.SetWorkflows([wf])
    automation_service.Start()

    trigger = wf.Triggers[0].TriggerInstance

    # 先正常触发 -> ActionSet 进入 IsOn
    trigger.Trigger()
    await automation_service.DrainTasks()
    assert ctx.events == ["invoke:4"]
    assert wf.ActionSet.Status.name == "IsOn"

    # 规则变 false -> NotifyStatusChanged -> 自动 revert
    flag["ok"] = False
    ruleset_service.NotifyStatusChanged()
    await automation_service.DrainTasks()

    assert ctx.events == ["invoke:4", "revert:4"]
    assert wf.ActionSet.Status.name == "Normal"

    print("=== automation ruleset invalidates and reverts OK ===")


# =========================================================
# LessonsBridge tests
# =========================================================

async def test_lessons_bridge_event_order():
    bridge = LessonsBridge()
    events = []

    bridge.AddPreMainTimerTickedHandler(lambda: events.append("pre"))
    bridge.AddCurrentTimeStateChangedHandler(lambda: events.append("state_changed"))
    bridge.AddOnClassHandler(lambda: events.append("on_class"))
    bridge.AddPostMainTimerTickedHandler(lambda: events.append("post"))

    await bridge.Tick(lambda b: b.UpdateCurrentState(TimeState.OnClass))

    assert events == ["pre", "state_changed", "on_class", "post"]
    print("=== lessons bridge event order OK ===")


async def test_lessons_bridge_no_duplicate_same_state():
    bridge = LessonsBridge()
    events = []

    bridge.AddCurrentTimeStateChangedHandler(lambda: events.append("state_changed"))
    bridge.AddOnClassHandler(lambda: events.append("on_class"))

    bridge.UpdateCurrentState(TimeState.OnClass)
    bridge.UpdateCurrentState(TimeState.OnClass)

    assert events == ["state_changed", "on_class"]
    print("=== lessons bridge same-state dedupe OK ===")


async def test_lessons_bridge_breaking_and_after_school():
    bridge = LessonsBridge()
    events = []

    bridge.AddCurrentTimeStateChangedHandler(lambda: events.append("state_changed"))
    bridge.AddOnBreakingTimeHandler(lambda: events.append("breaking"))
    bridge.AddOnAfterSchoolHandler(lambda: events.append("after_school"))

    bridge.UpdateCurrentState(TimeState.Breaking)
    bridge.UpdateCurrentState(TimeState.AfterSchool)

    assert events == [
        "state_changed", "breaking",
        "state_changed", "after_school",
    ]
    print("=== lessons bridge breaking/after-school OK ===")


# =========================================================
# main
# =========================================================

async def main():
    await test_manual_trigger_runs_action()
    await test_startup_like_trigger_runs_on_load()
    await test_ruleset_blocks_trigger()
    await test_ruleset_invalidates_and_reverts()

    await test_lessons_bridge_event_order()
    await test_lessons_bridge_no_duplicate_same_state()
    await test_lessons_bridge_breaking_and_after_school()

    print("\nALL STAGE-3 TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
