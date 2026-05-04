from __future__ import annotations

from automation.registry import register_trigger
from automation.trigger_base import TriggerBase


@register_trigger("classisland.ruleSet.rulesetChanged", "规则集更新时")
class RulesetChangedTrigger(TriggerBase):
    def __init__(self, context=None, services=None) -> None:
        super().__init__(context=context, services=services)
        self._handler = None

    def Loaded(self) -> None:
        service = self._get_ruleset_service()

        def _on_updated():
            self.Trigger()

        self._handler = _on_updated
        service.AddStatusUpdatedHandler(_on_updated)

    def UnLoaded(self) -> None:
        if self._handler is None:
            return
        service = self._get_ruleset_service()
        service.RemoveStatusUpdatedHandler(self._handler)
        self._handler = None

    def _get_ruleset_service(self):
        if self.Context is not None and getattr(self.Context, "ruleset_service", None) is not None:
            return self.Context.ruleset_service
        if self.Services is not None:
            if isinstance(self.Services, dict) and self.Services.get("ruleset_service") is not None:
                return self.Services["ruleset_service"]
            if getattr(self.Services, "ruleset_service", None) is not None:
                return self.Services.ruleset_service
        raise RuntimeError("Ruleset service is not configured")
