from __future__ import annotations

_registered = False


def register_builtins() -> None:
    """
    显式导入所有内置 actions / triggers，
    让 @register_action / @register_trigger 真正生效。
    """
    global _registered
    if _registered:
        return

    # actions
    import automation.actions.app_quit  # noqa: F401
    import automation.actions.app_restart  # noqa: F401
    import automation.actions.broadcast_signal  # noqa: F401
    import automation.actions.modify_app_settings  # noqa: F401
    import automation.actions.notification  # noqa: F401
    import automation.actions.run  # noqa: F401
    import automation.actions.weather_notification  # noqa: F401

    # triggers
    import automation.triggers.app_startup  # noqa: F401
    import automation.triggers.app_stopping  # noqa: F401
    import automation.triggers.cron  # noqa: F401
    import automation.triggers.current_time_state_changed  # noqa: F401
    import automation.triggers.on_after_school  # noqa: F401
    import automation.triggers.on_breaking_time  # noqa: F401
    import automation.triggers.on_class  # noqa: F401
    import automation.triggers.pre_time_point  # noqa: F401
    import automation.triggers.ruleset_changed  # noqa: F401
    import automation.triggers.signal  # noqa: F401
    import automation.triggers.tray_menu  # noqa: F401
    import automation.triggers.uri  # noqa: F401

    _registered = True
