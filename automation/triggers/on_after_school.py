from __future__ import annotations

from automation.registry import register_trigger
from automation.trigger_base import TriggerBase


@register_trigger("classisland.lessons.onAfterSchool", "放学时")
class OnAfterSchoolTrigger(TriggerBase):
    def __init__(self, context=None, services=None) -> None:
        super().__init__(context=context, services=services)
        self._handler = None

    def Loaded(self) -> None:
        bridge = self._get_lessons_bridge()

        def _on_after_school():
            self.Trigger()

        self._handler = _on_after_school
        bridge.AddOnAfterSchoolHandler(_on_after_school)

    def UnLoaded(self) -> None:
        if self._handler is None:
            return
        bridge = self._get_lessons_bridge()
        bridge.RemoveOnAfterSchoolHandler(self._handler)
        self._handler = None

    def _get_lessons_bridge(self):
        if self.Context is not None and getattr(self.Context, "lessons_bridge", None) is not None:
            return self.Context.lessons_bridge
        if self.Services is not None:
            if isinstance(self.Services, dict) and self.Services.get("lessons_bridge") is not None:
                return self.Services["lessons_bridge"]
            if getattr(self.Services, "lessons_bridge", None) is not None:
                return self.Services.lessons_bridge
        raise RuntimeError("Lessons bridge is not configured")
