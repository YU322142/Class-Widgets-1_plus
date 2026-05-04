from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Callable

from .models import Rule, RuleGroup, Ruleset
from .registry import RULE_INFOS, coerce_rule_settings
from .async_tools import schedule_awaitable

RuleHandler = Callable[[Any], bool]
EventHandler = Callable[[], Any]


class RulesetService:
    """
    对齐 ClassIsland.Services.RulesetService 的 Python 版。

    关键兼容点：
    - Rule.State / RuleGroup.State / Ruleset.State 三态
      0 = unknown / empty
      1 = false
      2 = true
    - RuleGroup.Mode / Ruleset.Mode 支持 And / Or
    - Rule / Group / Ruleset 支持 IsReversed
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.Logger = logger or logging.getLogger(__name__)

        self._foreground_window_changed_handlers: list[EventHandler] = []
        self._status_updated_handlers: list[EventHandler] = []

        # 对齐原版构造后立即 NotifyStatusChanged
        self.NotifyStatusChanged()

    # =========================================================
    # Event management
    # =========================================================

    def AddForegroundWindowChangedHandler(self, handler: EventHandler) -> None:
        self._foreground_window_changed_handlers.append(handler)

    def RemoveForegroundWindowChangedHandler(self, handler: EventHandler) -> None:
        if handler in self._foreground_window_changed_handlers:
            self._foreground_window_changed_handlers.remove(handler)

    def AddStatusUpdatedHandler(self, handler: EventHandler) -> None:
        self._status_updated_handlers.append(handler)

    def RemoveStatusUpdatedHandler(self, handler: EventHandler) -> None:
        if handler in self._status_updated_handlers:
            self._status_updated_handlers.remove(handler)

    def EmitForegroundWindowChanged(self) -> None:
        self._emit(self._foreground_window_changed_handlers)

    def NotifyStatusChanged(self) -> None:
        self._emit(self._status_updated_handlers)

    def _emit(self, handlers: list[EventHandler]) -> None:
        for handler in list(handlers):
            try:
                result = handler()
                schedule_awaitable(result)
            except Exception:
                self.Logger.exception("Ruleset event handler failed")

    # =========================================================
    # Rule registration
    # =========================================================

    def RegisterRuleHandler(self, rule_id: str, handler: RuleHandler) -> None:
        if rule_id not in RULE_INFOS:
            raise KeyError(f"Rule not registered: {rule_id}")
        RULE_INFOS[rule_id].Handle = handler

    # =========================================================
    # Evaluation
    # =========================================================

    def IsRulesetSatisfied(self, ruleset: Ruleset) -> bool:
        """
        对齐 C# RulesetService.IsRulesetSatisfied。
        """
        is_satisfied = ruleset.Mode.name == "And"

        if len(ruleset.Groups) <= 0:
            ruleset.State = self._bool_to_rule_object_state(False)
            return False

        # 清空可视状态
        for group in ruleset.Groups:
            group.State = 0
            for rule in group.Rules:
                rule.State = 0

        for group in [g for g in ruleset.Groups if g.IsEnabled]:
            res = self._is_ruleset_group_satisfied(group)
            group.State = self._bool_to_rule_object_state(res)

            if res is None:
                continue

            result = bool(res)

            if (not result) and group.Mode.name == "And":
                # 注意：这里只是 group 自己的 mode，不影响 ruleset 汇总逻辑
                pass

            if (not result) and ruleset.Mode.name == "And":
                is_satisfied = False
                break

            if result and ruleset.Mode.name == "Or":
                is_satisfied = True
                break

        if ruleset.IsReversed:
            is_satisfied = not is_satisfied

        ruleset.State = self._bool_to_rule_object_state(is_satisfied)
        return is_satisfied

    def _is_ruleset_group_satisfied(self, group: RuleGroup) -> bool | None:
        group_satisfied = group.Mode.name == "And"

        valid_rules = [r for r in group.Rules if r.Id != ""]
        if len(valid_rules) <= 0:
            return None

        for rule in group.Rules:
            res = self._is_rule_satisfied(rule)

            if res is None:
                rule.State = self._bool_to_rule_object_state(res)
                continue

            result = bool(res)
            if rule.IsReversed:
                result = not result

            rule.State = self._bool_to_rule_object_state(result)

            if (not result) and group.Mode.name == "And":
                group_satisfied = False
                break

            if result and group.Mode.name == "Or":
                group_satisfied = True
                break

        if group.IsReversed:
            group_satisfied = not group_satisfied

        return group_satisfied

    def _is_rule_satisfied(self, rule: Rule) -> bool | None:
        if rule.Id == "":
            return None

        if rule.Id not in RULE_INFOS:
            self.Logger.warning("Rule %s is not registered, fallback to false", rule.Id)
            return False

        info = RULE_INFOS[rule.Id]
        coerce_rule_settings(rule)

        settings = rule.Settings
        if settings is None and info.SettingsType is not None:
            try:
                settings = info.SettingsType()
            except Exception:
                settings = None

        if info.Handle is not None:
            try:
                return bool(info.Handle(settings))
            except Exception:
                self.Logger.exception("Rule handler failed: %s", rule.Id)
                return False

        self.Logger.warning("Rule %s has no handler, fallback to false", rule.Id)
        return False

    @staticmethod
    def _bool_to_rule_object_state(v: bool | None) -> int:
        if v is True:
            return 2
        if v is False:
            return 1
        return 0
