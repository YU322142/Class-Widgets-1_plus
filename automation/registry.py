from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .compat import (
    ACTION_SETTINGS_TYPES,
    RULE_SETTINGS_TYPES,
    TRIGGER_SETTINGS_TYPES,
    _dataclass_from_dict,
    migrate_action_item_compat,
)
from .models import ActionItem, Rule, TriggerSettings


# ============================================================
# Metadata models
# ============================================================

@dataclass
class ActionInfo:
    Id: str
    Name: str
    IconGlyph: str | None = None
    IsRevertable: bool = False
    AddDefaultToMenu: bool = True
    DefaultGroupToMenu: str = ""


@dataclass
class TriggerInfo:
    Id: str
    Name: str
    IconGlyph: str = "\uED55"
    TriggerType: type | None = None
    SettingsControlType: type | None = None


@dataclass
class RuleRegistryInfo:
    Id: str
    Name: str = ""
    IconGlyph: str = "\uef27"
    SettingsType: type | None = None
    SettingsControlType: type | None = None
    Handle: Callable[[Any], bool] | None = None


# ============================================================
# Registries
# ============================================================

ACTION_INFOS: dict[str, ActionInfo] = {}
ACTION_CLASSES: dict[str, type] = {}

TRIGGER_INFOS: dict[str, TriggerInfo] = {}
TRIGGER_CLASSES: dict[str, type] = {}

RULE_INFOS: dict[str, RuleRegistryInfo] = {}

# 轻量版“菜单树”
ACTION_MENU_TREE: list[dict[str, Any]] = []


# ============================================================
# Decorators / registration
# ============================================================

def register_action(
    action_id: str,
    name: str,
    icon_glyph: str | None = None,
    add_default_to_menu: bool = True,
    default_group_to_menu: str = "",
) -> Callable[[type], type]:
    def decorator(cls: type) -> type:
        if action_id in ACTION_INFOS:
            raise ValueError(f"Duplicate action id: {action_id}")

        from .action_base import ActionBase  # avoid circular import

        is_revertable = getattr(cls, "OnRevert", None) is not getattr(ActionBase, "OnRevert", None)

        info = ActionInfo(
            Id=action_id,
            Name=name,
            IconGlyph=icon_glyph,
            IsRevertable=is_revertable,
            AddDefaultToMenu=add_default_to_menu,
            DefaultGroupToMenu=default_group_to_menu,
        )

        ACTION_INFOS[action_id] = info
        ACTION_CLASSES[action_id] = cls
        cls.__action_info__ = info

        if add_default_to_menu:
            ACTION_MENU_TREE.append(
                {
                    "Id": action_id,
                    "Name": name,
                    "IconGlyph": icon_glyph,
                    "DefaultGroupToMenu": default_group_to_menu,
                }
            )

        return cls

    return decorator


def register_trigger(
    trigger_id: str,
    name: str,
    icon_glyph: str = "\uED55",
) -> Callable[[type], type]:
    def decorator(cls: type) -> type:
        if trigger_id in TRIGGER_INFOS:
            raise ValueError(f"Duplicate trigger id: {trigger_id}")

        info = TriggerInfo(
            Id=trigger_id,
            Name=name,
            IconGlyph=icon_glyph,
            TriggerType=cls,
        )

        TRIGGER_INFOS[trigger_id] = info
        TRIGGER_CLASSES[trigger_id] = cls
        cls.__trigger_info__ = info
        return cls

    return decorator


def register_rule(
    rule_id: str,
    name: str = "",
    icon_glyph: str = "\uef27",
    settings_type: type | None = None,
    handler: Callable[[Any], bool] | None = None,
) -> RuleRegistryInfo:
    if rule_id in RULE_INFOS:
        raise ValueError(f"Duplicate rule id: {rule_id}")

    info = RuleRegistryInfo(
        Id=rule_id,
        Name=name or rule_id,
        IconGlyph=icon_glyph,
        SettingsType=settings_type,
        Handle=handler,
    )
    RULE_INFOS[rule_id] = info
    return info


def set_rule_handler(rule_id: str, handler: Callable[[Any], bool]) -> None:
    if rule_id not in RULE_INFOS:
        raise KeyError(f"Rule not registered: {rule_id}")
    RULE_INFOS[rule_id].Handle = handler


# ============================================================
# Query helpers
# ============================================================

def get_action_info(action_id: str) -> ActionInfo | None:
    return ACTION_INFOS.get(action_id)


def get_trigger_info(trigger_id: str) -> TriggerInfo | None:
    return TRIGGER_INFOS.get(trigger_id)


def get_rule_info(rule_id: str) -> RuleRegistryInfo | None:
    return RULE_INFOS.get(rule_id)


def get_registered_action_ids() -> list[str]:
    return list(ACTION_INFOS.keys())


def get_registered_trigger_ids() -> list[str]:
    return list(TRIGGER_INFOS.keys())


def get_registered_rule_ids() -> list[str]:
    return list(RULE_INFOS.keys())


# ============================================================
# Settings coercion helpers
# ============================================================

def coerce_action_item_settings(action_item: ActionItem) -> None:
    migrate_action_item_compat(action_item)
    settings_type = ACTION_SETTINGS_TYPES.get(action_item.Id)
    if settings_type is None:
        return

    action_item.Settings = _coerce_settings_obj(settings_type, action_item.Settings)


def coerce_trigger_settings(trigger_settings: TriggerSettings) -> None:
    settings_type = TRIGGER_SETTINGS_TYPES.get(trigger_settings.Id)
    if settings_type is None:
        return

    trigger_settings.Settings = _coerce_settings_obj(settings_type, trigger_settings.Settings)


def coerce_rule_settings(rule: Rule) -> None:
    settings_type = RULE_SETTINGS_TYPES.get(rule.Id)
    if settings_type is None:
        return

    rule.Settings = _coerce_settings_obj(settings_type, rule.Settings)


def _coerce_settings_obj(settings_type: type, obj: Any) -> Any:
    if obj is None:
        return settings_type()

    if isinstance(obj, settings_type):
        return obj

    if isinstance(obj, dict):
        try:
            return _dataclass_from_dict(settings_type, obj)
        except Exception:
            pass

        try:
            inst = settings_type()
            for key, value in obj.items():
                if hasattr(inst, key):
                    setattr(inst, key, value)
                    continue

                pascal = key[:1].upper() + key[1:]
                if hasattr(inst, pascal):
                    setattr(inst, pascal, value)
            return inst
        except Exception:
            return settings_type()

    return obj


# ============================================================
# Factory helpers
# ============================================================

def create_action_instance(action_item: ActionItem, **kwargs: Any) -> Any | None:
    coerce_action_item_settings(action_item)
    cls = ACTION_CLASSES.get(action_item.Id)
    if cls is None:
        return None
    return cls(**kwargs)


def create_trigger_instance(trigger_settings: TriggerSettings, **kwargs: Any) -> Any | None:
    coerce_trigger_settings(trigger_settings)
    cls = TRIGGER_CLASSES.get(trigger_settings.Id)
    if cls is None:
        return None

    instance = cls(**kwargs)
    instance.SettingsInternal = trigger_settings.Settings
    return instance
