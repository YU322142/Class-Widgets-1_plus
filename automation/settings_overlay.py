from __future__ import annotations

import json
from dataclasses import is_dataclass
from enum import Enum, IntEnum
from typing import Any, Union, get_args, get_origin, get_type_hints
import types as _types


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("1", "true", "yes", "y", "on"):
            return True
        if v in ("0", "false", "no", "n", "off", ""):
            return False
    return bool(value)


def _coerce_to_type(value: Any, annotation: Any) -> Any:
    if annotation is Any:
        return value

    if value is None:
        return None

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (_types.UnionType, Union):
        non_none_args = [arg for arg in args if arg is not type(None)]
        if value is None:
            return None
        for candidate in non_none_args:
            try:
                return _coerce_to_type(value, candidate)
            except Exception:
                pass
        return value

    if origin is list and args:
        item_type = args[0]
        if not isinstance(value, list):
            return []
        return [_coerce_to_type(v, item_type) for v in value]

    if origin is dict and len(args) == 2:
        key_type, value_type = args
        if not isinstance(value, dict):
            return {}
        return {
            _coerce_to_type(k, key_type): _coerce_to_type(v, value_type)
            for k, v in value.items()
        }

    if isinstance(annotation, type):
        if issubclass(annotation, IntEnum):
            if isinstance(value, annotation):
                return value
            if isinstance(value, str):
                return annotation[value]
            return annotation(value)

        if issubclass(annotation, Enum):
            if isinstance(value, annotation):
                return value
            if isinstance(value, str):
                try:
                    return annotation(value)
                except Exception:
                    return annotation[value]
            return annotation(value)

        if annotation is bool:
            return _normalize_bool(value)

        if annotation in (str, int, float):
            return annotation(value)

        if is_dataclass(annotation) and isinstance(value, dict):
            return _dataclass_like_from_dict(annotation, value)

    return value


def _dataclass_like_from_dict(cls: type, raw: dict[str, Any]) -> Any:
    type_hints = get_type_hints(cls)
    kwargs = {}

    if hasattr(cls, "__dataclass_fields__"):
        for field_name in cls.__dataclass_fields__.keys():
            if field_name in raw:
                v = raw[field_name]
            else:
                camel = field_name[0].lower() + field_name[1:]
                if camel not in raw:
                    continue
                v = raw[camel]

            kwargs[field_name] = _coerce_to_type(v, type_hints.get(field_name, Any))
        return cls(**kwargs)

    inst = cls()
    for key, value in raw.items():
        target_name = key
        if not hasattr(inst, target_name):
            pascal = key[:1].upper() + key[1:]
            if hasattr(inst, pascal):
                target_name = pascal
            else:
                continue

        annotation = type_hints.get(target_name, Any)
        setattr(inst, target_name, _coerce_to_type(value, annotation))
    return inst


class SettingsOverlayManager:
    """
    对齐 ClassIsland.SettingsService 的 overlay 语义：
    - AddSettingsOverlay
    - RemoveSettingsOverlay
    - Settings.SettingsOverlays
    """

    def __init__(self, settings_obj: Any) -> None:
        self.Settings = settings_obj
        if not hasattr(self.Settings, "SettingsOverlays") or getattr(self.Settings, "SettingsOverlays") is None:
            setattr(self.Settings, "SettingsOverlays", {})

    def GetPropertyInfoByName(self, name: str) -> str | None:
        if not name:
            return None
        return name if hasattr(self.Settings, name) else None

    def GetPropertyType(self, name: str) -> Any:
        hints = get_type_hints(type(self.Settings))
        if name in hints:
            return hints[name]

        if hasattr(self.Settings, name):
            current = getattr(self.Settings, name)
            if current is not None:
                return type(current)

        return Any

    def ConvertToAssignableToSettingsType(self, value: Any, name: str) -> Any:
        annotation = self.GetPropertyType(name)

        if isinstance(value, str):
            # 尝试兼容“JSON 字符串内容”
            stripped = value.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    parsed = json.loads(value)
                    return _coerce_to_type(parsed, annotation)
                except Exception:
                    pass

        return _coerce_to_type(value, annotation)

    def SetValue(self, name: str, value: Any) -> None:
        if not hasattr(self.Settings, name):
            raise KeyError(f"Settings property not found: {name}")
        coerced = self.ConvertToAssignableToSettingsType(value, name)
        setattr(self.Settings, name, coerced)

    def AddSettingsOverlay(self, guid: str, name: str, value: Any) -> bool:
        if not hasattr(self.Settings, name):
            raise KeyError(f"Settings property not found: {name}")

        key = str(guid)
        overlays: dict[str, dict[str, Any]] = self.Settings.SettingsOverlays
        prop_overlay = overlays.get(name)

        if prop_overlay is not None and key in prop_overlay:
            del prop_overlay[key]

        current_value = getattr(self.Settings, name)
        coerced = self.ConvertToAssignableToSettingsType(value, name)

        if prop_overlay is None or "@" not in prop_overlay:
            if coerced == current_value:
                return True
            prop_overlay = {"@": current_value}

        setattr(self.Settings, name, coerced)
        prop_overlay[key] = coerced
        overlays[name] = prop_overlay
        return True

    def RemoveSettingsOverlay(self, guid: str, name: str) -> bool:
        overlays: dict[str, dict[str, Any]] = self.Settings.SettingsOverlays
        if name not in overlays:
            return False

        prop_overlay = overlays[name]
        key = str(guid)
        if key not in prop_overlay:
            return False

        del prop_overlay[key]

        if len(prop_overlay) <= 0:
            overlays.pop(name, None)
            return True

        last_value = next(reversed(prop_overlay.values()))
        restored = self.ConvertToAssignableToSettingsType(last_value, name)
        setattr(self.Settings, name, restored)

        if len(prop_overlay) > 1:
            overlays[name] = prop_overlay
        else:
            overlays.pop(name, None)

        return True
