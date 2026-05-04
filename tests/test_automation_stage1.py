import asyncio
import json
from pathlib import Path

from automation.compat import (
    dump_workflows_to_json_text,
    load_workflows_from_json_text,
)
from automation.models import (
    ActionItem,
    ActionSet,
    RunActionSettings,
    SignalTriggerSettings,
    SleepActionSettings,
)
from automation.registry import (
    ACTION_INFOS,
    TRIGGER_INFOS,
    create_action_instance,
    register_action,
    register_trigger,
)
from automation.action_base import ActionBaseT
from automation.trigger_base import TriggerBaseT


# =========================================================
# 1. 测试 JSON 兼容读取/写回
# =========================================================

def test_json_compat():
    raw = [
        {
            "Triggers": [
                {
                    "Id": "classisland.signal",
                    "Settings": {
                        "SignalName": "hello",
                        "IsRevert": False
                    }
                }
            ],
            "IsConditionEnabled": False,
            "Ruleset": {
                "Mode": 0,
                "IsReversed": False,
                "Groups": [
                    {
                        "Rules": [
                            {
                                "Id": "classisland.test.true",
                                "IsReversed": False,
                                "Settings": None
                            }
                        ],
                        "Mode": 1,
                        "IsReversed": False,
                        "IsEnabled": True
                    }
                ]
            },
            "ActionSet": {
                "Name": "测试行动组",
                "Actions": [
                    {
                        "Id": "classisland.os.run",
                        "Settings": {
                            "RunType": "Command",
                            "Value": "echo hello",
                            "Args": ""
                        }
                    }
                ],
                "IsEnabled": True,
                "IsRevertEnabled": False,
                "Status": 0,
                "Guid": "11111111-1111-1111-1111-111111111111"
            }
        }
    ]

    text = json.dumps(raw, ensure_ascii=False, indent=2)
    workflows = load_workflows_from_json_text(text)

    assert len(workflows) == 1
    wf = workflows[0]

    assert wf.ActionSet.Name == "测试行动组"
    assert wf.Triggers[0].Id == "classisland.signal"
    assert isinstance(wf.Triggers[0].Settings, SignalTriggerSettings)
    assert wf.Triggers[0].Settings.SignalName == "hello"

    assert len(wf.ActionSet.Actions) == 1
    action = wf.ActionSet.Actions[0]
    assert action.Id == "classisland.os.run"
    assert isinstance(action.Settings, RunActionSettings)
    assert action.Settings.RunType.value == "Command"
    assert action.Settings.Value == "echo hello"

    dumped = dump_workflows_to_json_text(workflows, indent=2)
    print("=== JSON roundtrip OK ===")
    print(dumped[:500], "...\n")


# =========================================================
# 2. 测试 Action 注册与执行
# =========================================================

@register_action("classisland.test.print", "测试打印")
class PrintAction(ActionBaseT[SleepActionSettings]):
    async def OnInvoke(self):
        print(f"[PrintAction] invoked, value={self.Settings.Value}")

    async def OnRevert(self):
        print(f"[PrintAction] reverted, value={self.Settings.Value}")


def test_action_registry():
    assert "classisland.test.print" in ACTION_INFOS
    print("=== action registry OK ===")
    print(ACTION_INFOS["classisland.test.print"])


async def test_action_invoke():
    item = ActionItem(
        Id="classisland.test.print",
        Settings=SleepActionSettings(Value=3),
    )
    aset = ActionSet(Name="测试 action set")

    action = create_action_instance(item, context=None, services=None)
    assert action is not None

    await action.InvokeAsync(item, aset, is_revertable=True)
    assert item.IsCompleted is True
    assert item.IsWorking is False
    print("=== action invoke OK ===")


# =========================================================
# 3. 测试 Action 中断
# =========================================================

@register_action("classisland.test.interruptable", "测试可中断 action")
class InterruptableAction(ActionBaseT[SleepActionSettings]):
    async def OnInvoke(self):
        print("[InterruptableAction] started")
        await self.SleepWithInterrupt(10)
        print("[InterruptableAction] finished normally")

    async def OnInterrupted(self):
        print("[InterruptableAction] interrupted callback fired")


async def test_action_interrupt():
    item = ActionItem(
        Id="classisland.test.interruptable",
        Settings=SleepActionSettings(Value=10),
    )
    aset = ActionSet(Name="可中断行动组")

    action = create_action_instance(item, context=None, services=None)
    assert action is not None

    task = asyncio.create_task(action.InvokeAsync(item, aset, is_revertable=True))
    await asyncio.sleep(0.3)

    # 模拟 ActionSet 被中断
    if not hasattr(aset, "_interrupt_event"):
        raise RuntimeError("interrupt event missing")

    aset._interrupt_event.set()

    await task
    assert item.IsCompleted is True
    print("=== action interrupt OK ===")


# =========================================================
# 4. 测试 Trigger 注册与触发
# =========================================================

@register_trigger("classisland.test.trigger", "测试触发器")
class DummyTrigger(TriggerBaseT[SignalTriggerSettings]):
    def Loaded(self):
        print("[DummyTrigger] loaded")

    def UnLoaded(self):
        print("[DummyTrigger] unloaded")


def test_trigger_registry():
    assert "classisland.test.trigger" in TRIGGER_INFOS
    print("=== trigger registry OK ===")
    print(TRIGGER_INFOS["classisland.test.trigger"])


async def test_trigger_fire():
    trigger = DummyTrigger(context=None, services=None)
    triggered = []
    reverted = []

    async def on_triggered(sender):
        triggered.append(sender)

    async def on_reverted(sender):
        reverted.append(sender)

    trigger.AddTriggeredHandler(on_triggered)
    trigger.AddTriggeredRevertHandler(on_reverted)

    trigger.Loaded()
    trigger.Trigger()
    trigger.TriggerRevert()
    await asyncio.sleep(0.1)
    trigger.UnLoaded()

    assert len(triggered) == 1
    assert len(reverted) == 1
    print("=== trigger fire OK ===")


# =========================================================
# main
# =========================================================

async def main():
    test_json_compat()
    test_action_registry()
    await test_action_invoke()
    await test_action_interrupt()
    test_trigger_registry()
    await test_trigger_fire()
    print("\nALL STAGE-1 TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
