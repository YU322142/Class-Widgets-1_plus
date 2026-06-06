from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from .enums import (
    ActionSetStatus,
    RulesetLogicalMode,
    RunActionRunType,
    TimeState,
    collapse_action_set_status,
)


def _new_guid_str() -> str:
    return str(uuid.uuid4())


# =========================
# Action settings
# =========================

@dataclass
class AppRestartActionSettings:
    Value: bool = False


@dataclass
class ModifyAppSettingsActionSettings:
    Name: str = ""
    Value: Any = None
    Mode: int = 0


@dataclass
class NotificationActionSettings:
    Content: str = ""
    Mask: str = ""
    IsContentSpeechEnabled: bool = True
    IsMaskSpeechEnabled: bool = True
    IsSoundEffectEnabled: bool = True
    IsTopmostEnabled: bool = True
    CustomSoundEffectPath: str = ""
    MaskDurationSeconds: float = 5.0
    ContentDurationSeconds: float = 10.0
    IsEffectEnabled: bool = True
    IsAdvancedSettingsEnabled: bool = False
    IsWaitForCompleteEnabled: bool = False


@dataclass
class RunActionSettings:
    RunType: RunActionRunType = RunActionRunType.Application
    Value: str = ""
    Args: str = ""


@dataclass
class SleepActionSettings:
    Value: float = 5.0


@dataclass
class WeatherNotificationActionSettings:
    NotificationKind: int = 0


# =========================
# Trigger settings
# =========================

@dataclass
class CronTriggerSettings:
    CronExpression: str = "0 8 * * *"


@dataclass
class PreTimePointTriggerSettings:
    TargetState: TimeState = TimeState.OnClass
    TimeSeconds: float = 60.0


@dataclass
class SignalTriggerSettings:
    SignalName: str = ""
    IsRevert: bool = False


@dataclass
class TrayMenuTriggerSettings:
    Header: str = ""
    IsRevert: bool = False


@dataclass
class UriTriggerSettings:
    UriSuffix: str = ""


# =========================
# Rule settings
# =========================

@dataclass
class StringMatchingSettings:
    Text: str = ""
    UseRegex: bool = False

    def is_matching(self, text: str) -> bool:
        if not self.UseRegex:
            return text == self.Text
        try:
            return re.search(self.Text, text) is not None
        except re.error:
            return False


@dataclass
class CurrentSubjectRuleSettings:
    SubjectId: str = ""


@dataclass
class CurrentWeatherRuleSettings:
    WeatherId: int = 0
    IsFuzzyMatch: bool = False


@dataclass
class RainTimeRuleSettings:
    RainTimeMinutes: float = 60.0
    IsRemainingTime: bool = False


@dataclass
class SunRiseSetRuleSettings:
    TimeMinutes: float = 60.0
    IsSunset: bool = False


@dataclass
class TimeStateRuleSettings:
    State: TimeState = TimeState.OnClass


@dataclass
class WindowStatusRuleSettings:
    State: int = 1


# =========================
# Core automation models
# =========================

@dataclass
class TriggerSettings:
    Id: str = ""
    Settings: Any = None

    # runtime only
    TriggerInstance: Any = field(default=None, repr=False, compare=False, metadata={"json": False})


@dataclass
class Rule:
    Id: str = ""
    IsReversed: bool = False
    Settings: Any = None
    State: int = field(default=0, metadata={"json": False})


@dataclass
class RuleGroup:
    Rules: list[Rule] = field(default_factory=list)
    Mode: RulesetLogicalMode = RulesetLogicalMode.And
    IsReversed: bool = False
    IsEnabled: bool = True
    State: int = field(default=0, metadata={"json": False})


@dataclass
class Ruleset:
    Mode: RulesetLogicalMode = RulesetLogicalMode.Or
    IsReversed: bool = False
    Groups: list[RuleGroup] = field(
        default_factory=lambda: [RuleGroup(Rules=[Rule()])]
    )
    State: int = field(default=0, metadata={"json": False})


@dataclass
class ActionItem:
    Id: str = ""
    Settings: Any = None

    # runtime only
    Exception: str | None = field(default=None, repr=False, compare=False, metadata={"json": False})
    IsWorking: bool = field(default=False, repr=False, compare=False, metadata={"json": False})
    Progress: float | None = field(default=None, repr=False, compare=False, metadata={"json": False})
    IsCompleted: bool = field(default=False, repr=False, compare=False, metadata={"json": False})
    IsNewAdded: bool = field(default=False, repr=False, compare=False, metadata={"json": False})

    @property
    def IsRevertEnabled(self) -> bool:
        # 对齐当前 ClassIsland 分支：始终为 true
        return True

    @property
    def IsRevertActionItem(self) -> bool:
        # 对齐当前 ClassIsland 分支：始终为 false
        return False

    def set_start_running(self) -> None:
        self.Exception = None
        self.IsWorking = True
        self.IsCompleted = False
        self.Progress = None

    def set_end_running(self) -> None:
        self.IsWorking = False
        self.Progress = None
        self.IsCompleted = True


@dataclass
class ActionSet:
    Name: str = "新行动组"
    Actions: list[ActionItem] = field(default_factory=list)
    IsEnabled: bool = True
    IsRevertEnabled: bool = False
    Status: ActionSetStatus = ActionSetStatus.Normal
    Guid: str = field(default_factory=_new_guid_str)

    # runtime only
    _interrupt_requested: bool = field(default=False, repr=False, compare=False, metadata={"json": False})
    _running: bool = field(default=False, repr=False, compare=False, metadata={"json": False})

    @property
    def IsWorking(self) -> bool:
        return self.Status in (ActionSetStatus.Invoking, ActionSetStatus.Reverting)

    def set_start_running(self, is_invoke: bool) -> None:
        self._interrupt_requested = False
        self._running = True
        self.Status = ActionSetStatus.Invoking if is_invoke else ActionSetStatus.Reverting
        for item in self.Actions:
            item.IsCompleted = False

    def set_end_running(self, is_invoke: bool, was_interrupted: bool = False) -> None:
        self._running = False

        if not was_interrupted:
            self.Status = (
                ActionSetStatus.IsOn
                if is_invoke and self.IsRevertEnabled
                else ActionSetStatus.Normal
            )
            return

        # 对齐 ClassIsland 中断后的状态流转
        if self.Status == ActionSetStatus.Invoking:
            self.Status = ActionSetStatus.Normal
        elif self.Status == ActionSetStatus.Reverting:
            self.Status = ActionSetStatus.IsOn

    def mark_interrupted(self) -> None:
        self._interrupt_requested = True

    @property
    def interrupt_requested(self) -> bool:
        return self._interrupt_requested

    @property
    def collapsed_status(self) -> ActionSetStatus:
        return collapse_action_set_status(self.Status)


@dataclass
class Workflow:
    Triggers: list[TriggerSettings] = field(default_factory=list)
    IsConditionEnabled: bool = False
    Ruleset: Ruleset = field(default_factory=Ruleset)
    ActionSet: ActionSet = field(default_factory=ActionSet)

    # runtime only
    _loaded: bool = field(default=False, repr=False, compare=False, metadata={"json": False})
