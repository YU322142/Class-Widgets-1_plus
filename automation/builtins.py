from __future__ import annotations

import datetime as dt
import logging
import sys
from typing import Any

from automation.enums import TimeState
from automation.models import (
    CurrentSubjectRuleSettings,
    CurrentWeatherRuleSettings,
    RainTimeRuleSettings,
    StringMatchingSettings,
    SunRiseSetRuleSettings,
    TimeStateRuleSettings,
    WindowStatusRuleSettings,
)
from automation.platform_window import get_foreground_window_snapshot
from automation.registry import get_registered_rule_ids, register_rule, set_rule_handler

LOGGER = logging.getLogger(__name__)

_BUILTINS_REGISTERED = False
_HANDLERS_REGISTERED = False


# ============================================================
# Builtin imports
# ============================================================

def _import_builtin_modules() -> None:
    # actions
    import automation.actions.app_quit  # noqa: F401
    import automation.actions.app_restart  # noqa: F401
    import automation.actions.broadcast_signal  # noqa: F401
    import automation.actions.modify_app_settings  # noqa: F401
    import automation.actions.run  # noqa: F401
    import automation.actions.notification  # noqa: F401
    import automation.actions.weather_notification  # noqa: F401
    import automation.actions.sleep  # noqa: F401

    # triggers
    import automation.triggers.signal  # noqa: F401
    import automation.triggers.cron  # noqa: F401
    import automation.triggers.uri  # noqa: F401
    import automation.triggers.tray_menu  # noqa: F401
    import automation.triggers.app_startup  # noqa: F401
    import automation.triggers.app_stopping  # noqa: F401
    import automation.triggers.ruleset_changed  # noqa: F401
    import automation.triggers.current_time_state_changed  # noqa: F401
    import automation.triggers.on_class  # noqa: F401
    import automation.triggers.on_breaking_time  # noqa: F401
    import automation.triggers.on_after_school  # noqa: F401
    import automation.triggers.pre_time_point  # noqa: F401


# ============================================================
# Rule registration
# ============================================================

def _safe_register_rule(
    rule_id: str,
    name: str,
    *,
    settings_type: type | None = None,
    icon_glyph: str = "\uef27",
) -> None:
    if rule_id in get_registered_rule_ids():
        return
    register_rule(
        rule_id,
        name=name,
        icon_glyph=icon_glyph,
        settings_type=settings_type,
    )


def _register_rule_metadata() -> None:
    # test
    _safe_register_rule("classisland.test.true", "总是为真")
    _safe_register_rule("classisland.test.false", "总是为假")

    # windows
    _safe_register_rule("classisland.windows.className", "前台窗口类名", settings_type=StringMatchingSettings)
    _safe_register_rule("classisland.windows.text", "前台窗口标题", settings_type=StringMatchingSettings)
    _safe_register_rule("classisland.windows.status", "前台窗口状态是", settings_type=WindowStatusRuleSettings)
    _safe_register_rule("classisland.windows.processName", "前台窗口进程", settings_type=StringMatchingSettings)

    # lessons
    _safe_register_rule("classisland.lessons.currentSubject", "当前科目是", settings_type=CurrentSubjectRuleSettings)
    _safe_register_rule("classisland.lessons.nextSubject", "下节课科目是", settings_type=CurrentSubjectRuleSettings)
    _safe_register_rule("classisland.lessons.previousSubject", "上节课科目是", settings_type=CurrentSubjectRuleSettings)
    _safe_register_rule("classisland.lessons.timeState", "当前时间状态是", settings_type=TimeStateRuleSettings)

    # weather
    _safe_register_rule("classisland.weather.currentWeather", "当前天气是", settings_type=CurrentWeatherRuleSettings)
    _safe_register_rule("classisland.weather.hasWeatherAlert", "存在天气预警", settings_type=StringMatchingSettings)
    _safe_register_rule("classisland.weather.rainTime", "距离降雨开始/结束还剩", settings_type=RainTimeRuleSettings)
    _safe_register_rule("classisland.weather.sunRiseSet", "是否日出/日落", settings_type=SunRiseSetRuleSettings)


# ============================================================
# Runtime helpers
# ============================================================

def _main_module():
    return sys.modules.get("__main__")


def _get_main_attr(*names: str, default: Any = None) -> Any:
    mod = _main_module()
    if mod is None:
        return default

    for name in names:
        if hasattr(mod, name):
            value = getattr(mod, name)
            try:
                if callable(value):
                    return value()
            except TypeError:
                pass
            return value
    return default


def _get_runtime():
    return _get_main_attr("automation_runtime", default=None)


def _get_lessons_bridge():
    runtime = _get_runtime()
    if runtime is None:
        return None

    if hasattr(runtime, "lessons_bridge"):
        return runtime.lessons_bridge

    if hasattr(runtime, "context") and hasattr(runtime.context, "lessons_bridge"):
        return runtime.context.lessons_bridge

    return None


def _get_weather_manager():
    wm = _get_main_attr("weather_manager", default=None)
    if wm is not None:
        return wm

    db_mod = _get_main_attr("db", default=None)
    if db_mod is not None and hasattr(db_mod, "weather_manager"):
        return getattr(db_mod, "weather_manager")

    try:
        import weather as weather_module
        return getattr(weather_module, "weather_manager", None)
    except Exception:
        return None


def _deep_get(data: Any, *paths: str) -> Any:
    for path in paths:
        current = data
        ok = True
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                ok = False
                break
        if ok:
            return current
    return None


def _deep_find_first_key(data: Any, keys: set[str]) -> Any:
    if isinstance(data, dict):
        for k, v in data.items():
            if k in keys:
                return v
        for _, v in data.items():
            found = _deep_find_first_key(v, keys)
            if found is not None:
                return found

    if isinstance(data, list):
        for item in data:
            found = _deep_find_first_key(item, keys)
            if found is not None:
                return found

    return None


def _payload_preview(payload: dict, limit: int = 500) -> str:
    try:
        text = repr(payload)
    except Exception:
        text = "<unreprable payload>"
    if len(text) > limit:
        return text[:limit] + "...(truncated)"
    return text


def _get_weather_payload() -> dict:
    wm = _get_weather_manager()
    if wm is None:
        LOGGER.debug("Weather payload: weather_manager not found")
        return {}

    try:
        if hasattr(wm, "_automation_get_weather_payload"):
            payload = wm._automation_get_weather_payload()
            if isinstance(payload, dict):
                LOGGER.debug(
                    f"Weather payload source=_automation_get_weather_payload "
                    f"keys={list(payload.keys())}"
                )
                return payload
    except Exception as e:
        LOGGER.debug(f"Weather payload source=_automation_get_weather_payload failed: {e}")

    for attr in ("current_weather_data", "weather_data", "cached_weather_data", "latest_weather_data"):
        try:
            payload = getattr(wm, attr, None)
            if isinstance(payload, dict):
                LOGGER.debug(
                    f"Weather payload source=attr:{attr} "
                    f"keys={list(payload.keys())}"
                )
                return payload
        except Exception as e:
            LOGGER.debug(f"Weather payload source=attr:{attr} failed: {e}")

    LOGGER.debug("Weather payload not found in WeatherManager")
    return {}


def _get_weather_alerts() -> list[dict]:
    """
    你的 weather.py 返回结构中，预警在 payload['alert'] 下。
    """
    wm = _get_weather_manager()
    payload = _get_weather_payload()
    if not isinstance(payload, dict):
        return []

    # 1) 优先用 weather_manager 自己的统一提取方法
    if wm is not None:
        try:
            if hasattr(wm, "_automation_extract_alerts"):
                alerts = wm._automation_extract_alerts()
                if isinstance(alerts, list):
                    alerts = [x for x in alerts if isinstance(x, dict)]
                    LOGGER.debug(f"Weather alerts source=_automation_extract_alerts count={len(alerts)}")
                    return alerts
        except Exception as e:
            LOGGER.debug(f"Weather alerts extraction failed: {e}")

    # 2) 从 payload['alert'] 中提取
    alert_payload = payload.get("alert", {})
    if isinstance(alert_payload, dict):
        alerts = (
            _deep_get(alert_payload, "warning")
            or _deep_get(alert_payload, "alerts")
            or _deep_get(alert_payload, "result.alerts")
        )
        if isinstance(alerts, list):
            alerts = [x for x in alerts if isinstance(x, dict)]
            LOGGER.debug(f"Weather alerts source=payload['alert'] count={len(alerts)}")
            return alerts

    # 3) fallback
    alerts = _deep_get(payload, "alerts", "result.alerts", "warning")
    if isinstance(alerts, list):
        alerts = [x for x in alerts if isinstance(x, dict)]
        LOGGER.debug(f"Weather alerts source=fallback count={len(alerts)}")
        return alerts

    LOGGER.debug(f"Weather alerts not found, payload_preview={_payload_preview(payload)}")
    return []



def _get_current_weather_code() -> str:
    """
    优先把 payload['now'] 作为 provider 原始天气结构解析。
    """
    wm = _get_weather_manager()
    payload = _get_weather_payload()
    now_payload = _get_weather_now_payload()

    if not now_payload:
        LOGGER.debug("CurrentWeather: now payload empty")
        return ""

    provider = None
    try:
        if wm is not None and hasattr(wm, "get_current_provider"):
            provider = wm.get_current_provider()
    except Exception as e:
        LOGGER.debug(f"CurrentWeather: get_current_provider failed: {e}")

    # 1) 优先走 provider.parse_weather_icon(now_payload)
    if provider is not None and hasattr(provider, "parse_weather_icon"):
        try:
            code = provider.parse_weather_icon(now_payload)
            LOGGER.debug(
                f"CurrentWeather: provider={provider.__class__.__name__} "
                f"parse_weather_icon(now_payload) -> {code!r}"
            )
            if code not in (None, ""):
                return str(code).strip()
        except Exception as e:
            LOGGER.debug(f"CurrentWeather: provider.parse_weather_icon failed: {e}")

    # 2) 再从 now_payload 中按常见路径找
    code = _deep_get(
        now_payload,
        "current.weather",
        "current.code",
        "current.icon",
        "now.weather",
        "now.code",
        "now.icon",
        "weather_code",
        "weather",
        "icon",
    )

    if code is None:
        code = _deep_find_first_key(now_payload, {"weather_code", "code", "icon", "weather"})

    LOGGER.debug(
        f"CurrentWeather: payload_preview={_payload_preview(payload)}"
    )
    LOGGER.debug(
        f"CurrentWeather: now_payload_preview={_payload_preview(now_payload)}"
    )

    if code is None:
        LOGGER.debug("CurrentWeather: code not found in now_payload")
        return ""

    code_str = str(code).strip()
    LOGGER.debug(f"CurrentWeather: resolved code={code_str!r}")
    return code_str

def _compute_rain_remaining_minutes(values: list[float]) -> int:
    if len(values) <= 0:
        return 0

    if values[0] > 0:
        for i, v in enumerate(values):
            if v <= 0:
                return -i

    for i, v in enumerate(values):
        if v > 0:
            return i

    return 0


def _parse_datetime(value: str) -> dt.datetime | None:
    if not value:
        return None

    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return dt.datetime.strptime(value, fmt)
        except Exception:
            pass

    return None


def _get_subject_name(kind: str) -> str:
    """
    当前版本按“名称文本”匹配课程规则。
    """
    name_candidates = {
        "current": [
            "current_lesson_name",
            "current_subject_name",
            "current_subject",
        ],
        "next": [
            "next_lesson_name",
            "next_subject_name",
            "next_subject",
        ],
        "previous": [
            "previous_lesson_name",
            "previous_subject_name",
            "previous_subject",
        ],
    }.get(kind, [])

    value = _get_main_attr(*name_candidates, default="")
    if value is None:
        return ""
    value = str(value).strip()
    LOGGER.debug(f"Subject[{kind}] resolved name={value!r}")
    return value


def _get_current_time_state() -> TimeState:
    """
    优先用 automation lessons_bridge 的标准 TimeState；
    再退回主程序旧 current_state 数值语义：
    - 1 => OnClass
    - 0 => Breaking
    - 2 => AfterSchool（近似）
    """
    bridge = _get_lessons_bridge()
    if bridge is not None and hasattr(bridge, "CurrentState"):
        try:
            state = TimeState.from_value(bridge.CurrentState)
            LOGGER.debug(f"TimeState resolved from lessons_bridge: {state}")
            return state
        except Exception as e:
            LOGGER.debug(f"TimeState resolve from lessons_bridge failed: {e}")

    raw = _get_main_attr("current_state", default=None)

    if raw == 1:
        LOGGER.debug("TimeState resolved from main.current_state=1 -> OnClass")
        return TimeState.OnClass
    if raw == 0:
        LOGGER.debug("TimeState resolved from main.current_state=0 -> Breaking")
        return TimeState.Breaking
    if raw == 2:
        LOGGER.debug("TimeState resolved from main.current_state=2 -> AfterSchool")
        return TimeState.AfterSchool

    try:
        state = TimeState.from_value(raw)
        LOGGER.debug(f"TimeState resolved by fallback enum conversion: {state}")
        return state
    except Exception:
        LOGGER.debug(f"TimeState unresolved, raw={raw!r}, fallback=None_")
        return TimeState.None_
def _get_weather_now_payload() -> dict:
    """
    你的 weather.py 返回结构是：
    {
        "now": <provider raw weather data>,
        "alert": <provider raw alert data>
    }

    所以天气类规则（currentWeather / rainTime / sunRiseSet）应该优先读取 payload["now"]。
    如果没有 now，则回退使用根 payload。
    """
    payload = _get_weather_payload()
    if not isinstance(payload, dict):
        return {}

    now_payload = payload.get("now")
    if isinstance(now_payload, dict):
        LOGGER.debug(
            f"Weather now-payload resolved from wrapped payload, keys={list(now_payload.keys())}"
        )
        return now_payload

    LOGGER.debug("Weather now-payload missing, fallback to root payload")
    return payload


# ============================================================
# Rule handlers
# ============================================================

def _rule_true(_settings: Any) -> bool:
    return True


def _rule_false(_settings: Any) -> bool:
    return False


def _rule_window_class_name(settings: Any) -> bool:
    if not isinstance(settings, StringMatchingSettings):
        return False
    snap = get_foreground_window_snapshot()
    LOGGER.debug(f"WindowClassName current={snap.class_name!r} expected={settings.Text!r}")
    return settings.is_matching(snap.class_name)


def _rule_window_title(settings: Any) -> bool:
    if not isinstance(settings, StringMatchingSettings):
        return False
    snap = get_foreground_window_snapshot()
    LOGGER.debug(f"WindowTitle current={snap.title!r} expected={settings.Text!r}")
    return settings.is_matching(snap.title)


def _rule_window_process_name(settings: Any) -> bool:
    if not isinstance(settings, StringMatchingSettings):
        return False
    snap = get_foreground_window_snapshot()
    LOGGER.debug(f"WindowProcess current={snap.process_name!r} expected={settings.Text!r}")
    return settings.is_matching(snap.process_name)


def _rule_window_status(settings: Any) -> bool:
    if not isinstance(settings, WindowStatusRuleSettings):
        return False
    snap = get_foreground_window_snapshot()
    LOGGER.debug(
        f"WindowStatus current={snap.status} expected={settings.State} "
        f"title={snap.title!r} class={snap.class_name!r} process={snap.process_name!r}"
    )
    return int(snap.status) == int(settings.State)


def _rule_time_state(settings: Any) -> bool:
    if not isinstance(settings, TimeStateRuleSettings):
        return False
    current = _get_current_time_state()
    LOGGER.debug(f"TimeState current={current} expected={settings.State}")
    return current == settings.State


def _rule_subject(kind: str, settings: Any) -> bool:
    if not isinstance(settings, CurrentSubjectRuleSettings):
        return False

    target = str(settings.SubjectId or "").strip()
    if not target:
        LOGGER.debug(f"Subject[{kind}] target empty")
        return False

    current = _get_subject_name(kind)
    LOGGER.debug(f"Subject[{kind}] current={current!r} expected={target!r}")
    if not current:
        return False

    return current == target


def _rule_current_weather(settings: Any) -> bool:
    if not isinstance(settings, CurrentWeatherRuleSettings):
        return False

    code = _get_current_weather_code()
    LOGGER.debug(f"CurrentWeather current={code!r} expected={settings.WeatherId!r}")
    if code == "":
        return False

    return str(code) == str(settings.WeatherId)


def _rule_has_weather_alert(settings: Any) -> bool:
    if not isinstance(settings, StringMatchingSettings):
        return False

    alerts = _get_weather_alerts()
    LOGGER.debug(f"WeatherAlert current_count={len(alerts)} match_text={settings.Text!r}")
    for alert in alerts:
        title = str(alert.get("title", "") or "")
        LOGGER.debug(f"WeatherAlert checking title={title!r}")
        if settings.is_matching(title):
            LOGGER.debug(f"WeatherAlert matched title={title!r}")
            return True
    return False


def _rule_rain_time(settings: Any) -> bool:
    if not isinstance(settings, RainTimeRuleSettings):
        return False

    now_payload = _get_weather_now_payload()
    values = _deep_get(now_payload, "minutely.precipitation.value")

    if not isinstance(values, list):
        LOGGER.debug(
            f"RainTime: values not found in now_payload, preview={_payload_preview(now_payload)}"
        )
        return False

    try:
        values = [float(x) for x in values]
    except Exception:
        LOGGER.debug(f"RainTime: values invalid={values!r}")
        return False

    remain = _compute_rain_remaining_minutes(values)
    base_time = ((-1.0) if settings.IsRemainingTime else 1.0) * remain
    LOGGER.debug(
        f"RainTime remain={remain} compare={settings.RainTimeMinutes} "
        f"is_remaining={settings.IsRemainingTime} values_head={values[:8]}"
    )
    return base_time > 0 and base_time <= float(settings.RainTimeMinutes)



def _rule_sunrise_sunset(settings: Any) -> bool:
    if not isinstance(settings, SunRiseSetRuleSettings):
        return False

    now_payload = _get_weather_now_payload()
    sun_items = _deep_get(now_payload, "forecastDaily.sunRiseSet.value")
    if not isinstance(sun_items, list):
        LOGGER.debug(
            f"SunRiseSet: sunRiseSet not found in now_payload, preview={_payload_preview(now_payload)}"
        )
        return False

    sunrise = None
    sunset = None
    now_naive = dt.datetime.now()

    for item in sun_items:
        if not isinstance(item, dict):
            continue

        frm = _parse_datetime(str(item.get("from", "") or ""))
        to = _parse_datetime(str(item.get("to", "") or ""))
        if frm is None or to is None:
            continue

        # 统一转为“本地时区下的 naive datetime”，避免 aware / naive 混用报错
        if frm.tzinfo is not None:
            frm = frm.astimezone().replace(tzinfo=None)
        if to.tzinfo is not None:
            to = to.astimezone().replace(tzinfo=None)

        if frm.date() == now_naive.date() or to.date() == now_naive.date():
            sunrise = frm
            sunset = to
            break

    LOGGER.debug(
        f"SunRiseSet sunrise={sunrise} sunset={sunset} now={now_naive} is_sunset={settings.IsSunset}"
    )

    if sunrise is None or sunset is None:
        return False

    # IsSunset=True：判断当前是否处于“日落后到次日日出前”
    if settings.IsSunset:
        return now_naive >= sunset or now_naive < sunrise

    # IsSunset=False：判断当前是否处于“日出后到日落前”
    return sunrise <= now_naive < sunset




def _register_rule_handlers() -> None:
    set_rule_handler("classisland.test.true", _rule_true)
    set_rule_handler("classisland.test.false", _rule_false)

    set_rule_handler("classisland.windows.className", _rule_window_class_name)
    set_rule_handler("classisland.windows.text", _rule_window_title)
    set_rule_handler("classisland.windows.status", _rule_window_status)
    set_rule_handler("classisland.windows.processName", _rule_window_process_name)

    set_rule_handler("classisland.lessons.currentSubject", lambda s: _rule_subject("current", s))
    set_rule_handler("classisland.lessons.nextSubject", lambda s: _rule_subject("next", s))
    set_rule_handler("classisland.lessons.previousSubject", lambda s: _rule_subject("previous", s))
    set_rule_handler("classisland.lessons.timeState", _rule_time_state)

    set_rule_handler("classisland.weather.currentWeather", _rule_current_weather)
    set_rule_handler("classisland.weather.hasWeatherAlert", _rule_has_weather_alert)
    set_rule_handler("classisland.weather.rainTime", _rule_rain_time)
    set_rule_handler("classisland.weather.sunRiseSet", _rule_sunrise_sunset)


# ============================================================
# Public entry
# ============================================================

def register_builtins() -> None:
    global _BUILTINS_REGISTERED, _HANDLERS_REGISTERED

    if not _BUILTINS_REGISTERED:
        _import_builtin_modules()
        _register_rule_metadata()
        _BUILTINS_REGISTERED = True

    if not _HANDLERS_REGISTERED:
        _register_rule_handlers()
        _HANDLERS_REGISTERED = True
