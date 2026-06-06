from __future__ import annotations

import json
import uuid
from dataclasses import fields, is_dataclass
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints
import types as _types

from .enums import (
    ActionSetStatus,
    RulesetLogicalMode,
    RunActionRunType,
    TimeState,
    collapse_action_set_status,
)
from .models import (
    ActionItem,
    ActionSet,
    AppRestartActionSettings,
    CronTriggerSettings,
    CurrentSubjectRuleSettings,
    CurrentWeatherRuleSettings,
    ModifyAppSettingsActionSettings,
    NotificationActionSettings,
    PreTimePointTriggerSettings,
    RainTimeRuleSettings,
    Rule,
    RuleGroup,
    Ruleset,
    RunActionSettings,
    SignalTriggerSettings,
    SleepActionSettings,
    StringMatchingSettings,
    SunRiseSetRuleSettings,
    TimeStateRuleSettings,
    TrayMenuTriggerSettings,
    TriggerSettings,
    UriTriggerSettings,
    WeatherNotificationActionSettings,
    WindowStatusRuleSettings,
    Workflow,
)

EMPTY_GUID = "00000000-0000-0000-0000-000000000000"


# =========================================
# ClassIsland ID -> settings type mappings
# =========================================

ACTION_SETTINGS_TYPES: dict[str, type] = {
    "classisland.app.restart": AppRestartActionSettings,
    "classisland.settings": ModifyAppSettingsActionSettings,
    "classisland.showNotification": NotificationActionSettings,
    "classisland.os.run": RunActionSettings,
    "classisland.action.sleep": SleepActionSettings,
    "classisland.notification.weather": WeatherNotificationActionSettings,
    "classisland.broadcastSignal": SignalTriggerSettings,
}

TRIGGER_SETTINGS_TYPES: dict[str, type] = {
    "classisland.cron": CronTriggerSettings,
    "classisland.lessons.preTimePoint": PreTimePointTriggerSettings,
    "classisland.signal": SignalTriggerSettings,
    "classisland.trayMenu": TrayMenuTriggerSettings,
    "classisland.uri": UriTriggerSettings,
}

RULE_SETTINGS_TYPES: dict[str, type] = {
    "classisland.windows.className": StringMatchingSettings,
    "classisland.windows.text": StringMatchingSettings,
    "classisland.windows.status": WindowStatusRuleSettings,
    "classisland.windows.processName": StringMatchingSettings,
    "classisland.lessons.currentSubject": CurrentSubjectRuleSettings,
    "classisland.lessons.nextSubject": CurrentSubjectRuleSettings,
    "classisland.lessons.previousSubject": CurrentSubjectRuleSettings,
    "classisland.lessons.timeState": TimeStateRuleSettings,
    "classisland.weather.currentWeather": CurrentWeatherRuleSettings,
    "classisland.weather.tomorrowWeather": CurrentWeatherRuleSettings,
    "classisland.weather.hasWeatherAlert": StringMatchingSettings,
    "classisland.weather.rainTime": RainTimeRuleSettings,
    "classisland.weather.sunRiseSet": SunRiseSetRuleSettings,
}

# =========================================
# Public API
# =========================================

def load_workflows_from_file(path: str | Path) -> list[Workflow]:
    path = Path(path)
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8-sig")
    return load_workflows_from_json_text(text)


def save_workflows_to_file(path: str | Path, workflows: list[Workflow], indent: int = 2) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        dump_workflows_to_json_text(workflows, indent=indent),
        encoding="utf-8",
    )


def load_workflows_from_json_text(text: str) -> list[Workflow]:
    if not text.strip():
        return []

    raw = json.loads(text)

    # 容忍 object-root，但优先兼容 ClassIsland 的 array-root
    if isinstance(raw, dict):
        raw = _pick(raw, "Workflows", "workflows", default=[])

    if not isinstance(raw, list):
        raise ValueError("Automation config root must be a JSON array or an object containing Workflows.")

    workflows = [_workflow_from_dict(item) for item in raw if isinstance(item, dict)]
    return workflows


def dump_workflows_to_json_text(workflows: list[Workflow], indent: int = 2) -> str:
    payload = [_to_jsonable(wf) for wf in workflows]
    return json.dumps(payload, ensure_ascii=False, indent=indent)

# =========================================
# Migration
# =========================================

def migrate_action_item_compat(item: ActionItem) -> ActionItem:
    """
    对齐 ClassIsland ActionService.MigrateUnknownActionItem 的旧设置项迁移逻辑。
    """
    prefix = "classisland.settings."
    if item.Id.startswith(prefix):
        suffix = item.Id[len(prefix):]
        processed_name = suffix[0].upper() + suffix[1:] if suffix else ""

        old_settings = item.Settings
        old_value = None
        if isinstance(old_settings, dict):
            old_value = old_settings.get("Value")

        item.Id = "classisland.settings"
        item.Settings = ModifyAppSettingsActionSettings(
            Name=processed_name,
            Value=old_value,
        )

    return item

# =========================================
# Deserialize
# =========================================

def _workflow_from_dict(data: dict[str, Any]) -> Workflow:
    workflow = Workflow(
        Triggers=[_trigger_from_dict(x) for x in _pick(data, "Triggers", "triggers", default=[]) if isinstance(x, dict)],
        IsConditionEnabled=_parse_bool(_pick(data, "IsConditionEnabled", "isConditionEnabled", default=False)),
        Ruleset=_ruleset_from_dict(_pick(data, "Ruleset", "ruleset", default={})),
        ActionSet=_action_set_from_dict(_pick(data, "ActionSet", "actionSet", default={})),
    )
    return _attach_extra_fields(
        workflow,
        data,
        _json_key_set("Triggers", "IsConditionEnabled", "Ruleset", "ActionSet"),
    )


def _trigger_from_dict(data: dict[str, Any]) -> TriggerSettings:
    trigger_id = str(_pick(data, "Id", "id", default=""))
    raw_settings = _pick(data, "Settings", "settings", default=None)
    settings = _deserialize_settings(TRIGGER_SETTINGS_TYPES.get(trigger_id), raw_settings)
    trigger = TriggerSettings(
        Id=trigger_id,
        Settings=settings,
    )
    return _attach_extra_fields(
        trigger,
        data,
        _json_key_set("Id", "Settings", "AssociatedTriggerInfo", "TriggerInstance"),
    )


def _action_set_from_dict(data: dict[str, Any]) -> ActionSet:
    status = _parse_action_set_status(_pick(data, "Status", "status", default=0))
    raw_actions = _pick(data, "Actions", "ActionItems", "actions", "actionItems", default=[])

    action_set = ActionSet(
        Name=str(_pick(data, "Name", "name", default="新行动组")),
        Actions=[_action_item_from_dict(x) for x in raw_actions if isinstance(x, dict)],
        IsEnabled=_parse_bool(_pick(data, "IsEnabled", "isEnabled", default=True), default=True),
        IsRevertEnabled=_parse_bool(_pick(data, "IsRevertEnabled", "isRevertEnabled", default=False)),
        Status=status,
        Guid=str(_pick(data, "Guid", "guid", default="")) or _new_guid_fallback(),
    )
    return _attach_extra_fields(
        action_set,
        data,
        _json_key_set(
            "Name",
            "Actions",
            "ActionItems",
            "IsEnabled",
            "IsRevertEnabled",
            "Status",
            "Guid",
            "IsWorking",
            "InterruptCts",
            "RunningTcs",
        ),
    )


def _action_item_from_dict(data: dict[str, Any]) -> ActionItem:
    action_id = str(_pick(data, "Id", "id", default=""))
    raw_settings = _pick(data, "Settings", "settings", default=None)
    settings = _deserialize_settings(ACTION_SETTINGS_TYPES.get(action_id), raw_settings)

    item = ActionItem(
        Id=action_id,
        Settings=settings,
        IsCompleted=_parse_bool(_pick(data, "IsCompleted", "isCompleted", default=False)),
    )
    item = _attach_extra_fields(
        item,
        data,
        _json_key_set(
            "IsCompleted",
            "Id",
            "Settings",
            "IsRevertEnabled",
            "IsRevertActionItem",
            "Exception",
            "IsWorking",
            "Progress",
            "IsNewAdded",
        ),
    )
    return migrate_action_item_compat(item)


def _ruleset_from_dict(data: dict[str, Any]) -> Ruleset:
    if not isinstance(data, dict):
        return Ruleset()

    groups = _pick(data, "Groups", "groups", default=[])
    ruleset = Ruleset(
        Mode=_parse_ruleset_mode(_pick(data, "Mode", "mode", default=0)),
        IsReversed=_parse_bool(_pick(data, "IsReversed", "isReversed", default=False)),
        Groups=[_rule_group_from_dict(x) for x in groups if isinstance(x, dict)] or [RuleGroup(Rules=[Rule()])],
    )
    return _attach_extra_fields(
        ruleset,
        data,
        _json_key_set("Mode", "IsReversed", "Groups", "State"),
    )


def _rule_group_from_dict(data: dict[str, Any]) -> RuleGroup:
    rules = _pick(data, "Rules", "rules", default=[])
    group = RuleGroup(
        Rules=[_rule_from_dict(x) for x in rules if isinstance(x, dict)],
        Mode=_parse_ruleset_mode(_pick(data, "Mode", "mode", default=1)),
        IsReversed=_parse_bool(_pick(data, "IsReversed", "isReversed", default=False)),
        IsEnabled=_parse_bool(_pick(data, "IsEnabled", "isEnabled", default=True), default=True),
    )
    return _attach_extra_fields(
        group,
        data,
        _json_key_set("Rules", "Mode", "IsReversed", "IsEnabled", "State"),
    )


def _rule_from_dict(data: dict[str, Any]) -> Rule:
    rule_id = str(_pick(data, "Id", "id", default=""))
    raw_settings = _pick(data, "Settings", "settings", default=None)
    settings = _deserialize_settings(RULE_SETTINGS_TYPES.get(rule_id), raw_settings)

    rule = Rule(
        Id=rule_id,
        IsReversed=_parse_bool(_pick(data, "IsReversed", "isReversed", default=False)),
        Settings=settings,
    )
    return _attach_extra_fields(
        rule,
        data,
        _json_key_set("Id", "IsReversed", "Settings", "State"),
    )


def _deserialize_settings(cls: type | None, raw: Any) -> Any:
    if cls is None:
        return raw
    if raw is None:
        return cls()
    if isinstance(raw, cls):
        return raw
    if isinstance(raw, dict):
        return _dataclass_from_dict(cls, raw)
    return raw


def _dataclass_from_dict(cls: type, raw: dict[str, Any]) -> Any:
    kwargs: dict[str, Any] = {}
    type_hints = get_type_hints(cls)

    for f in fields(cls):
        key_value = _pick(raw, f.name, f.name[0].lower() + f.name[1:], default=_MISSING)
        if key_value is _MISSING:
            continue

        annotation = type_hints.get(f.name, Any)
        kwargs[f.name] = _coerce_value(key_value, annotation)

    inst = cls(**kwargs)

    if isinstance(inst, CurrentSubjectRuleSettings):
        _normalize_current_subject_settings(inst)

    # 【跨应用兼容性补丁】收集未知字典键（避免擦除原版新增字段或第三方插件配置）
    known_keys = _json_key_set(
        *(f.name for f in fields(cls) if f.metadata.get("json", True) is not False)
    )
    return _attach_extra_fields(inst, raw, known_keys)



def _coerce_value(value: Any, annotation: Any) -> Any:
    if value is None:
        return None

    if annotation is Any:
        return value

    origin = get_origin(annotation)
    args = get_args(annotation)

    # Python 3.10 union: X | Y
    if origin in (_types.UnionType, Union):
        non_none_args = [arg for arg in args if arg is not type(None)]
        if value is None:
            return None
        for candidate in non_none_args:
            try:
                return _coerce_value(value, candidate)
            except Exception:
                pass
        return value

    if origin is list and args:
        item_type = args[0]
        if not isinstance(value, list):
            return []
        return [_coerce_value(v, item_type) for v in value]

    if origin is dict and len(args) == 2:
        key_type, value_type = args
        if not isinstance(value, dict):
            return {}
        return {
            _coerce_value(k, key_type): _coerce_value(v, value_type)
            for k, v in value.items()
        }

    if isinstance(annotation, type):
        if issubclass(annotation, IntEnum):
            if annotation is TimeState:
                return TimeState.from_value(value)
            if annotation is ActionSetStatus:
                return ActionSetStatus.from_value(value)
            if annotation is RulesetLogicalMode:
                return RulesetLogicalMode.from_value(value)
            return annotation(value)

        if issubclass(annotation, Enum):
            if annotation is RunActionRunType:
                return RunActionRunType.from_value(value)
            return annotation(value)

        if is_dataclass(annotation) and isinstance(value, dict):
            return _dataclass_from_dict(annotation, value)

        if annotation is bool:
            return _parse_bool(value)

        if annotation in (str, int, float):
            try:
                return annotation(value)
            except Exception:
                return value

    return value

# =========================================
# Serialize
# =========================================

def _to_jsonable(obj: Any) -> Any:
    if obj is None:
        return None

    if isinstance(obj, IntEnum):
        return int(obj)

    if isinstance(obj, Enum):
        return obj.value

    if is_dataclass(obj):
        if isinstance(obj, CurrentSubjectRuleSettings):
            _normalize_current_subject_settings(obj)

        result: dict[str, Any] = {}
        for f in fields(obj):
            if f.metadata.get("json", True) is False:
                continue

            value = getattr(obj, f.name)

            if isinstance(obj, ActionSet) and f.name == "Status":
                value = collapse_action_set_status(value)

            # (可选) 和原版保持一致：如果 Settings 为 None，干脆不写入
            if f.name == "Settings" and value is None:
                continue

            result[f.name] = _to_jsonable(value)

        if isinstance(obj, ActionSet):
            result["IsWorking"] = _to_jsonable(obj.IsWorking)

        # 【跨应用兼容性补丁】将未知的原生字段原样写回 JSON
        extra = getattr(obj, "_json_extra_fields", None)
        if isinstance(extra, dict):
            for k, v in extra.items():
                if k not in result:
                    result[k] = _to_jsonable(v)

        return result

    if isinstance(obj, list):
        return [_to_jsonable(x) for x in obj]

    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}

    return obj


# =========================================
# Helpers
# =========================================

class _Missing:
    pass


_MISSING = _Missing()


def _is_guid_text(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        uuid.UUID(text)
        return True
    except Exception:
        return False


def _normalize_current_subject_settings(settings: CurrentSubjectRuleSettings) -> None:
    subject_id = str(getattr(settings, "SubjectId", "") or "").strip()
    subject_name = str(getattr(settings, "CwSubjectName", "") or "").strip()

    if subject_id and not _is_guid_text(subject_id):
        if not subject_name:
            settings.CwSubjectName = subject_id
        settings.SubjectId = EMPTY_GUID
        return

    if not subject_id:
        settings.SubjectId = EMPTY_GUID


def _json_key_set(*keys: str) -> set[str]:
    result: set[str] = set()
    for key in keys:
        if not key:
            continue
        result.add(key)
        result.add(key[:1].lower() + key[1:])
    return result


def _attach_extra_fields(obj: Any, raw: dict[str, Any], known_keys: set[str]) -> Any:
    extra = {
        key: value
        for key, value in raw.items()
        if key not in known_keys and not key.startswith("_")
    }
    if extra:
        setattr(obj, "_json_extra_fields", extra)
    return obj


def _pick(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data:
            val = data[key]
            # 如果值为 None (即 JSON 里的 null)，应该继续寻找或 fallback 到默认安全值（如 []）
            if val is not None:
                return val
    return default



def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("1", "true", "yes", "y", "on"):
            return True
        if text in ("0", "false", "no", "n", "off", ""):
            return False

    return bool(value)


def _parse_action_set_status(value: Any) -> ActionSetStatus:
    status = ActionSetStatus.from_value(value)
    return collapse_action_set_status(status)


def _parse_ruleset_mode(value: Any) -> RulesetLogicalMode:
    return RulesetLogicalMode.from_value(value)


def _new_guid_fallback() -> str:
    return str(uuid.uuid4())
