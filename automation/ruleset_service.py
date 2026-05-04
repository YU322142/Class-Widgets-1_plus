from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Callable

from .models import Rule, RuleGroup, Ruleset
from .registry import RULE_INFOS, coerce_rule_settings


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

    这版增强日志，方便定位：
    - 规则是否注册
    - handler 是否被调用
    - settings 是什么
    - 规则 / 规则组 / 规则集最终结果
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
        self.Logger.debug("RulesetService.NotifyStatusChanged()")
        self._emit(self._status_updated_handlers)

    def _emit(self, handlers: list[EventHandler]) -> None:
        for handler in list(handlers):
            try:
                result = handler()
                if inspect.isawaitable(result):
                    asyncio.create_task(result)
            except Exception:
                self.Logger.exception("Ruleset event handler failed")

    # =========================================================
    # Rule registration
    # =========================================================

    def RegisterRuleHandler(self, rule_id: str, handler: RuleHandler) -> None:
        if rule_id not in RULE_INFOS:
            raise KeyError(f"Rule not registered: {rule_id}")
        RULE_INFOS[rule_id].Handle = handler
        self.Logger.debug(f"Rule handler registered: {rule_id}")

    # =========================================================
    # Evaluation
    # =========================================================

    def IsRulesetSatisfied(self, ruleset: Ruleset) -> bool:
        self.Logger.debug(
            f"Evaluating ruleset: mode={getattr(ruleset.Mode, 'name', ruleset.Mode)} "
            f"reversed={ruleset.IsReversed} groups={len(ruleset.Groups)}"
        )

        is_satisfied = ruleset.Mode.name == "And"

        if len(ruleset.Groups) <= 0:
            ruleset.State = self._bool_to_rule_object_state(False)
            self.Logger.debug("Ruleset has no groups -> False")
            return False

        # 清空状态
        for group in ruleset.Groups:
            group.State = 0
            for rule in group.Rules:
                rule.State = 0

        enabled_groups = [g for g in ruleset.Groups if g.IsEnabled]
        self.Logger.debug(f"Enabled groups count: {len(enabled_groups)}")

        for group_index, group in enumerate(enabled_groups):
            res = self._is_ruleset_group_satisfied(group_index, group)
            group.State = self._bool_to_rule_object_state(res)

            self.Logger.debug(
                f"Group[{group_index}] result={res} state={group.State} "
                f"mode={getattr(group.Mode, 'name', group.Mode)} "
                f"reversed={group.IsReversed} enabled={group.IsEnabled}"
            )

            if res is None:
                continue

            result = bool(res)

            if (not result) and ruleset.Mode.name == "And":
                is_satisfied = False
                break

            if result and ruleset.Mode.name == "Or":
                is_satisfied = True
                break

        if ruleset.IsReversed:
            is_satisfied = not is_satisfied

        ruleset.State = self._bool_to_rule_object_state(is_satisfied)

        self.Logger.debug(
            f"Ruleset final result={is_satisfied} state={ruleset.State} "
            f"(mode={getattr(ruleset.Mode, 'name', ruleset.Mode)} reversed={ruleset.IsReversed})"
        )
        return is_satisfied

    def _is_ruleset_group_satisfied(self, group_index: int, group: RuleGroup) -> bool | None:
        group_satisfied = group.Mode.name == "And"

        valid_rules = [r for r in group.Rules if r.Id != ""]
        if len(valid_rules) <= 0:
            self.Logger.debug(f"Group[{group_index}] has no valid rules -> None")
            return None

        self.Logger.debug(
            f"Evaluating Group[{group_index}]: "
            f"mode={getattr(group.Mode, 'name', group.Mode)} "
            f"reversed={group.IsReversed} enabled={group.IsEnabled} "
            f"rules={len(group.Rules)}"
        )

        for rule_index, rule in enumerate(group.Rules):
            res = self._is_rule_satisfied(group_index, rule_index, rule)

            if res is None:
                rule.State = self._bool_to_rule_object_state(res)
                self.Logger.debug(
                    f"Group[{group_index}] Rule[{rule_index}] id={rule.Id} -> None / skipped"
                )
                continue

            result = bool(res)
            if rule.IsReversed:
                result = not result

            rule.State = self._bool_to_rule_object_state(result)

            self.Logger.debug(
                f"Group[{group_index}] Rule[{rule_index}] id={rule.Id} "
                f"reversed={rule.IsReversed} raw={res} final={result} state={rule.State}"
            )

            if (not result) and group.Mode.name == "And":
                group_satisfied = False
                break

            if result and group.Mode.name == "Or":
                group_satisfied = True
                break

        if group.IsReversed:
            group_satisfied = not group_satisfied

        return group_satisfied

    def _is_rule_satisfied(self, group_index: int, rule_index: int, rule: Rule) -> bool | None:
        if rule.Id == "":
            return None

        if rule.Id not in RULE_INFOS:
            self.Logger.warning(
                f"Rule {rule.Id} is not registered, fallback to false "
                f"(group={group_index} rule={rule_index})"
            )
            return False

        info = RULE_INFOS[rule.Id]
        coerce_rule_settings(rule)

        settings = rule.Settings
        if settings is None and info.SettingsType is not None:
            try:
                settings = info.SettingsType()
            except Exception:
                settings = None

        self.Logger.debug(
            f"Invoking rule handler: group={group_index} rule={rule_index} "
            f"id={rule.Id} settings={self._safe_repr(settings)} "
            f"settings_type={getattr(info.SettingsType, '__name__', str(info.SettingsType))} "
            f"handler={'yes' if info.Handle is not None else 'no'}"
        )

        if info.Handle is not None:
            try:
                result = bool(info.Handle(settings))
                self.Logger.debug(
                    f"Rule handler returned: group={group_index} rule={rule_index} id={rule.Id} -> {result}"
                )
                return result
            except Exception:
                self.Logger.exception(
                    f"Rule handler failed: group={group_index} rule={rule_index} id={rule.Id}, fallback to false"
                )
                return False

        self.Logger.warning(
            f"Rule {rule.Id} has no handler, fallback to false "
            f"(group={group_index} rule={rule_index})"
        )
        return False

    @staticmethod
    def _bool_to_rule_object_state(v: bool | None) -> int:
        if v is True:
            return 2
        if v is False:
            return 1
        return 0

    @staticmethod
    def _safe_repr(value: Any, limit: int = 240) -> str:
        try:
            text = repr(value)
        except Exception:
            text = f"<unreprable {type(value).__name__}>"

        if len(text) > limit:
            return text[:limit] + "...(truncated)"
        return text
