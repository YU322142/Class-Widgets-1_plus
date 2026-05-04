import asyncio

from automation.action_base import ActionBaseT
from automation.action_service import ActionService
from automation.models import (
    ActionItem,
    ActionSet,
    Rule,
    RuleGroup,
    Ruleset,
    SleepActionSettings,
)
from automation.registry import (
    ACTION_INFOS,
    RULE_INFOS,
    register_action,
    register_rule,
)
from automation.ruleset_service import RulesetService


# =========================================================
# Test context
# =========================================================

class TestContext:
    def __init__(self):
        self.events = []


# =========================================================
# Rules registration
# =========================================================

def ensure_rule_registered(rule_id, name, handler):
    if rule_id not in RULE_INFOS:
        register_rule(rule_id, name=name, handler=handler)
    else:
        RULE_INFOS[rule_id].Handle = handler


# =========================================================
# Action registrations
# =========================================================

@register_action("classisland.test.stage2.append", "测试追加")
class AppendAction(ActionBaseT[SleepActionSettings]):
    async def OnInvoke(self):
        self.Context.events.append(f"append:{self.Settings.Value}")

    async def OnRevert(self):
        self.Context.events.append(f"revert-append:{self.Settings.Value}")


@register_action("classisland.test.stage2.fail", "测试失败")
class FailAction(ActionBaseT[SleepActionSettings]):
    async def OnInvoke(self):
        self.Context.events.append("fail:start")
        raise RuntimeError("intentional failure")


@register_action("classisland.test.stage2.long", "测试长任务")
class LongAction(ActionBaseT[SleepActionSettings]):
    async def OnInvoke(self):
        self.Context.events.append("long:start")
        await self.SleepWithInterrupt(5)
        self.Context.events.append("long:end")

    async def OnInterrupted(self):
        self.Context.events.append("long:interrupted")


# =========================================================
# Ruleset tests
# =========================================================

def test_ruleset_basic_true_false():
    ensure_rule_registered("classisland.test.stage2.true", "真规则", lambda s: True)
    ensure_rule_registered("classisland.test.stage2.false", "假规则", lambda s: False)

    service = RulesetService()

    rs = Ruleset(
        Groups=[
            RuleGroup(
                Rules=[Rule(Id="classisland.test.stage2.true")],
            )
        ]
    )
    assert service.IsRulesetSatisfied(rs) is True
    assert rs.State == 2
    assert rs.Groups[0].State == 2
    assert rs.Groups[0].Rules[0].State == 2

    rs2 = Ruleset(
        Groups=[
            RuleGroup(
                Rules=[Rule(Id="classisland.test.stage2.false")],
            )
        ]
    )
    assert service.IsRulesetSatisfied(rs2) is False
    assert rs2.State == 1
    assert rs2.Groups[0].State == 1
    assert rs2.Groups[0].Rules[0].State == 1

    print("=== ruleset basic true/false OK ===")


def test_ruleset_reversed():
    ensure_rule_registered("classisland.test.stage2.revtrue", "真规则", lambda s: True)
    service = RulesetService()

    rs = Ruleset(
        IsReversed=True,
        Groups=[
            RuleGroup(
                Rules=[Rule(Id="classisland.test.stage2.revtrue")],
            )
        ]
    )

    assert service.IsRulesetSatisfied(rs) is False
    assert rs.State == 1
    print("=== ruleset reversed OK ===")


def test_ruleset_group_modes():
    ensure_rule_registered("classisland.test.stage2.gtrue", "真规则", lambda s: True)
    ensure_rule_registered("classisland.test.stage2.gfalse", "假规则", lambda s: False)

    service = RulesetService()

    rs_and = Ruleset(
        Groups=[
            RuleGroup(
                Mode=type(Ruleset().Mode).And,
                Rules=[
                    Rule(Id="classisland.test.stage2.gtrue"),
                    Rule(Id="classisland.test.stage2.gfalse"),
                ],
            )
        ]
    )
    assert service.IsRulesetSatisfied(rs_and) is False

    rs_or = Ruleset(
        Groups=[
            RuleGroup(
                Mode=type(Ruleset().Mode).Or,
                Rules=[
                    Rule(Id="classisland.test.stage2.gtrue"),
                    Rule(Id="classisland.test.stage2.gfalse"),
                ],
            )
        ]
    )
    assert service.IsRulesetSatisfied(rs_or) is True

    print("=== ruleset group modes OK ===")


# =========================================================
# ActionService tests
# =========================================================

async def test_action_service_invoke_serial():
    ctx = TestContext()
    svc = ActionService(context=ctx)

    aset = ActionSet(
        Name="串行测试",
        IsRevertEnabled=True,
        Actions=[
            ActionItem(Id="classisland.test.stage2.append", Settings=SleepActionSettings(Value=1)),
            ActionItem(Id="classisland.test.stage2.append", Settings=SleepActionSettings(Value=2)),
        ],
    )

    await svc.InvokeActionSetAsync(aset)

    assert ctx.events == ["append:1", "append:2"]
    assert aset.Status.name == "IsOn"
    assert all(x.IsCompleted for x in aset.Actions)

    print("=== action service invoke serial OK ===")


async def test_action_service_revert():
    ctx = TestContext()
    svc = ActionService(context=ctx)

    aset = ActionSet(
        Name="恢复测试",
        IsRevertEnabled=True,
        Actions=[
            ActionItem(Id="classisland.test.stage2.append", Settings=SleepActionSettings(Value=10)),
            ActionItem(Id="classisland.test.stage2.append", Settings=SleepActionSettings(Value=20)),
        ],
    )

    await svc.InvokeActionSetAsync(aset)
    await svc.RevertActionSetAsync(aset)

    assert ctx.events == [
        "append:10",
        "append:20",
        "revert-append:10",
        "revert-append:20",
    ]
    assert aset.Status.name == "Normal"

    print("=== action service revert OK ===")


async def test_action_service_exception_continue():
    ctx = TestContext()
    svc = ActionService(context=ctx)

    aset = ActionSet(
        Name="异常不中断测试",
        IsRevertEnabled=False,
        Actions=[
            ActionItem(Id="classisland.test.stage2.append", Settings=SleepActionSettings(Value=100)),
            ActionItem(Id="classisland.test.stage2.fail", Settings=SleepActionSettings(Value=0)),
            ActionItem(Id="classisland.test.stage2.append", Settings=SleepActionSettings(Value=200)),
        ],
    )

    await svc.InvokeActionSetAsync(aset)

    assert ctx.events == [
        "append:100",
        "fail:start",
        "append:200",
    ]
    assert aset.Actions[1].Exception is not None
    assert aset.Status.name == "Normal"

    print("=== action service exception continue OK ===")


async def test_action_service_interrupt():
    ctx = TestContext()
    svc = ActionService(context=ctx)

    aset = ActionSet(
        Name="中断测试",
        IsRevertEnabled=True,
        Actions=[
            ActionItem(Id="classisland.test.stage2.long", Settings=SleepActionSettings(Value=0)),
            ActionItem(Id="classisland.test.stage2.append", Settings=SleepActionSettings(Value=999)),
        ],
    )

    task = asyncio.create_task(svc.InvokeActionSetAsync(aset))
    await asyncio.sleep(0.3)
    await svc.InterruptActionSetAsync(aset)
    await task

    assert "long:start" in ctx.events
    assert "long:interrupted" in ctx.events
    assert "append:999" not in ctx.events
    assert aset.Status.name == "Normal"

    print("=== action service interrupt OK ===")


# =========================================================
# main
# =========================================================

async def main():
    test_ruleset_basic_true_false()
    test_ruleset_reversed()
    test_ruleset_group_modes()

    await test_action_service_invoke_serial()
    await test_action_service_revert()
    await test_action_service_exception_continue()
    await test_action_service_interrupt()

    print("\nALL STAGE-2 TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
