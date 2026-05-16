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
            try:
                return cls(value)
            except ValueError:
                return cls.None_

        if isinstance(value, str):
            value = value.strip()

            if value in ("None", "None_"):
                return cls.None_

            # 兼容 JSON / UI 保存成 "1"、"3"、"4" 的情况
            if value.lstrip("+-").isdigit():
                try:
                    return cls(int(value))
                except ValueError:
                    return cls.None_

            try:
                return cls[value]
            except KeyError:
                return cls.None_

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
            try:
                return cls(value)
            except ValueError:
                return cls.Normal

        if isinstance(value, str):
            value = value.strip()

            if value.lstrip("+-").isdigit():
                try:
                    return cls(int(value))
                except ValueError:
                    return cls.Normal

            try:
                return cls[value]
            except KeyError:
                return cls.Normal

        return cls.Normal


class RulesetLogicalMode(IntEnum):
    Or = 0
    And = 1

    @classmethod
    def from_value(cls, value: object) -> "RulesetLogicalMode":
        if isinstance(value, cls):
            return value

        if isinstance(value, int):
            try:
                return cls(value)
            except ValueError:
                return cls.Or

        if isinstance(value, str):
            value = value.strip()

            if value.lstrip("+-").isdigit():
                try:
                    return cls(int(value))
                except ValueError:
                    return cls.Or

            try:
                return cls[value]
            except KeyError:
                return cls.Or

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
            value = value.strip()

            try:
                return cls(value)
            except ValueError:
                pass

            try:
                return cls[value]
            except KeyError:
                return cls.Application

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
