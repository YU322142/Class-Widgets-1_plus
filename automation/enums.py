from __future__ import annotations

from enum import Enum, IntEnum


class TimeState(IntEnum):
    None_ = 0
    OnClass = 1
    PrepareOnClass = 2
    Breaking = 3
    AfterSchool = 4

    @classmethod
    def from_value(cls, value: object) -> "TimeState":
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            return cls(value)
        if isinstance(value, str):
            if value == "None":
                return cls.None_
            if value == "None_":
                return cls.None_
            return cls[value]
        return cls.None_


class ActionSetStatus(IntEnum):
    Normal = 0
    Invoking = 1
    IsOn = 2
    Reverting = 3

    @classmethod
    def from_value(cls, value: object) -> "ActionSetStatus":
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            return cls(value)
        if isinstance(value, str):
            return cls[value]
        return cls.Normal


class RulesetLogicalMode(IntEnum):
    Or = 0
    And = 1

    @classmethod
    def from_value(cls, value: object) -> "RulesetLogicalMode":
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            return cls(value)
        if isinstance(value, str):
            return cls[value]
        return cls.Or


class RunActionRunType(str, Enum):
    Application = "Application"
    Command = "Command"
    File = "File"
    Folder = "Folder"
    Url = "Url"

    @classmethod
    def from_value(cls, value: object) -> "RunActionRunType":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls(value)
            except ValueError:
                return cls[value]
        if isinstance(value, int):
            values = [
                cls.Application,
                cls.Command,
                cls.File,
                cls.Folder,
                cls.Url,
            ]
            if 0 <= value < len(values):
                return values[value]
        return cls.Application


def collapse_action_set_status(status: ActionSetStatus) -> ActionSetStatus:
    """
    对齐 ClassIsland 的 ActionSetStatusJsonConverter：
    - Invoking -> Normal
    - Reverting -> IsOn
    """
    if status == ActionSetStatus.Invoking:
        return ActionSetStatus.Normal
    if status == ActionSetStatus.Reverting:
        return ActionSetStatus.IsOn
    return status
