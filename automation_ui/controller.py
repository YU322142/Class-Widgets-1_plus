from __future__ import annotations

from pathlib import Path
from typing import Any

from automation.builtins import register_builtins
from automation.compat import (
    ACTION_SETTINGS_TYPES,
    TRIGGER_SETTINGS_TYPES,
)
from automation.models import (
    ActionItem,
    ActionSet,
    Rule,
    RuleGroup,
    Ruleset,
    TriggerSettings,
    Workflow,
)
from automation.registry import (
    get_action_info,
    get_registered_action_ids,
    get_registered_trigger_ids,
    get_trigger_info,
)


class AutomationUiController:
    """
    UI 控制层：
    - 页面操作的是 editor runtime
    - 只有 apply_current() 才真正作用到 live runtime
    """

    def __init__(self, runtime: Any, conf_module: Any) -> None:
        register_builtins()
        self.runtime = runtime
        self.conf = conf_module

        # 参考 ClassIsland：触发器按“生命周期 / 课程 / 通用”组织
        self._trigger_groups: dict[str, list[tuple[str, str]]] = {
            "生命周期": [
                ("classisland.lifetime.startup", "应用启动时"),
                ("classisland.lifetime.stopping", "应用退出时"),
            ],
            "课程": [
                ("classisland.lessons.currentTimeStateChanged", "当前时间状态变化时"),
                ("classisland.lessons.onClass", "上课时"),
                ("classisland.lessons.onBreakingTime", "课间休息时"),
                ("classisland.lessons.onAfterSchool", "放学时"),
                ("classisland.lessons.preTimePoint", "特定时间点前"),
            ],
            "通用": [
                ("classisland.cron", "cron"),
                ("classisland.signal", "收到信号时"),
                ("classisland.uri", "调用 Uri 时"),
                ("classisland.trayMenu", "从托盘菜单运行时"),
                ("classisland.ruleSet.rulesetChanged", "规则集更新时"),
            ],
        }

        # 参考 ClassIsland ActionMenuTree 的思路：动作按组展示
        self._action_groups: dict[str, list[tuple[str, str]]] = {
            "提醒": [
                ("classisland.showNotification", "显示提醒"),
                ("classisland.notification.weather", "显示天气提醒"),
            ],
            "运行": [
                ("classisland.os.run", "运行"),
            ],
            "应用设置": [
                ("classisland.settings", "应用设置"),
            ],
            "自动化": [
                ("classisland.broadcastSignal", "广播信号"),
            ],
            "控制": [
                ("classisland.action.sleep", "等待时长"),
            ],
            "ClassIsland": [
                ("classisland.app.quit", "退出 ClassIsland"),
                ("classisland.app.restart", "重启 ClassIsland"),
            ],
        }

    # =========================================================
    # Config
    # =========================================================

    def get_current_config_name(self) -> str:
        settings = self.runtime.context.settings
        if settings is not None and hasattr(settings, "CurrentAutomationConfig"):
            return str(settings.CurrentAutomationConfig or "Default")
        return self.conf.get_current_automation_config_name()

    def set_current_config_name(self, name: str) -> None:
        settings = self.runtime.context.settings
        if settings is not None and hasattr(settings, "CurrentAutomationConfig"):
            settings.CurrentAutomationConfig = name
            if hasattr(settings, "sync_to_disk"):
                settings.sync_to_disk()

        self.conf.set_current_automation_config_name(name)

    def get_current_config_path(self) -> Path:
        return self.conf.get_automation_config_path(self.get_current_config_name())

    def list_configs(self) -> list[str]:
        return self.conf.list_automation_configs()

    def ensure_default_config(self) -> Path:
        return self.conf.ensure_default_automation_config()

    def create_config(self, name: str) -> str:
        name = (name or "").strip()
        if not name:
            raise ValueError("配置文件名称不能为空。")

        invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
        if any(ch in name for ch in invalid_chars):
            raise ValueError("配置文件名称包含非法字符。")

        path = self.conf.get_automation_config_path(name)
        if path.exists():
            raise FileExistsError(f"配置文件“{name}”已存在。")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]", encoding="utf-8")

        self.set_current_config_name(name)
        self.load_current()
        return name

    def delete_config(self, name: str) -> str:
        name = (name or "").strip()
        if not name:
            raise ValueError("未指定要删除的配置文件。")

        configs = self.list_configs()
        if name not in configs:
            raise FileNotFoundError(f"配置文件“{name}”不存在。")

        if len(configs) <= 1:
            raise ValueError("至少需要保留一个自动化配置文件。")

        path = self.conf.get_automation_config_path(name)
        if path.exists():
            path.unlink()

        remain = [x for x in configs if x != name]
        next_name = remain[0] if remain else "Default"

        if self.get_current_config_name() == name:
            self.set_current_config_name(next_name)
            self.load_current()

        return next_name

    def load_current(self) -> None:
        self.runtime.load_workflows(self.get_current_config_path())

    def save_current(self) -> None:
        settings = self.runtime.context.settings
        if settings is not None and hasattr(settings, "sync_to_disk"):
            settings.sync_to_disk()
        self.runtime.save_workflows(self.get_current_config_path())

    def apply_current(self) -> bool:
        if hasattr(self.runtime, "apply_to_runtime"):
            return bool(self.runtime.apply_to_runtime())
        return False

    def has_live_runtime(self) -> bool:
        return bool(getattr(self.runtime, "has_live_runtime", False))

    # =========================================================
    # Workflows
    # =========================================================

    @property
    def workflows(self) -> list[Workflow]:
        return self.runtime.automation_service.Workflows

    def create_workflow(self) -> Workflow:
        wf = Workflow(
            Triggers=[],
            IsConditionEnabled=False,
            Ruleset=Ruleset(
                Groups=[RuleGroup(Rules=[Rule()])]
            ),
            ActionSet=ActionSet(
                Name="新工作流",
                Actions=[],
                IsEnabled=True,
                IsRevertEnabled=False,
            ),
        )
        self.workflows.append(wf)
        self.save_current()
        return wf

    def delete_workflow(self, index: int) -> None:
        if 0 <= index < len(self.workflows):
            self.workflows.pop(index)
            self.save_current()

    def move_workflow_up(self, index: int) -> int:
        if 0 < index < len(self.workflows):
            self.workflows[index - 1], self.workflows[index] = self.workflows[index], self.workflows[index - 1]
            self.save_current()
            return index - 1
        return index

    def move_workflow_down(self, index: int) -> int:
        if 0 <= index < len(self.workflows) - 1:
            self.workflows[index + 1], self.workflows[index] = self.workflows[index], self.workflows[index + 1]
            self.save_current()
            return index + 1
        return index

    # =========================================================
    # Triggers
    # =========================================================

    def add_trigger(self, workflow: Workflow, trigger_id: str) -> TriggerSettings:
        settings_type = TRIGGER_SETTINGS_TYPES.get(trigger_id)
        trigger = TriggerSettings(
            Id=trigger_id,
            Settings=settings_type() if settings_type else None,
        )
        workflow.Triggers.append(trigger)
        self.save_current()
        return trigger

    def delete_trigger(self, workflow: Workflow, index: int) -> None:
        if 0 <= index < len(workflow.Triggers):
            workflow.Triggers.pop(index)
            self.save_current()

    def move_trigger_up(self, workflow: Workflow, index: int) -> int:
        if 0 < index < len(workflow.Triggers):
            workflow.Triggers[index - 1], workflow.Triggers[index] = workflow.Triggers[index], workflow.Triggers[index - 1]
            self.save_current()
            return index - 1
        return index

    def move_trigger_down(self, workflow: Workflow, index: int) -> int:
        if 0 <= index < len(workflow.Triggers) - 1:
            workflow.Triggers[index + 1], workflow.Triggers[index] = workflow.Triggers[index], workflow.Triggers[index + 1]
            self.save_current()
            return index + 1
        return index

    # =========================================================
    # Actions
    # =========================================================

    def add_action(self, workflow: Workflow, action_id: str) -> ActionItem:
        settings_type = ACTION_SETTINGS_TYPES.get(action_id)
        action_item = ActionItem(
            Id=action_id,
            Settings=settings_type() if settings_type else None,
        )
        workflow.ActionSet.Actions.append(action_item)
        self.save_current()
        return action_item

    def delete_action(self, workflow: Workflow, index: int) -> None:
        if 0 <= index < len(workflow.ActionSet.Actions):
            workflow.ActionSet.Actions.pop(index)
            self.save_current()

    def move_action_up(self, workflow: Workflow, index: int) -> int:
        actions = workflow.ActionSet.Actions
        if 0 < index < len(actions):
            actions[index - 1], actions[index] = actions[index], actions[index - 1]
            self.save_current()
            return index - 1
        return index

    def move_action_down(self, workflow: Workflow, index: int) -> int:
        actions = workflow.ActionSet.Actions
        if 0 <= index < len(actions) - 1:
            actions[index + 1], actions[index] = actions[index], actions[index + 1]
            self.save_current()
            return index + 1
        return index

    # =========================================================
    # Registry data
    # =========================================================

    def _trigger_name_fallback(self, trigger_id: str) -> str:
        for _, entries in self._trigger_groups.items():
            for tid, name in entries:
                if tid == trigger_id:
                    return name
        return trigger_id

    def _action_name_fallback(self, action_id: str) -> str:
        fallback = {
            "classisland.showNotification": "显示提醒",
            "classisland.notification.weather": "显示天气提醒",
            "classisland.os.run": "运行",
            "classisland.action.sleep": "等待时长",
            "classisland.settings": "应用设置",
            "classisland.broadcastSignal": "广播信号",
            "classisland.app.quit": "退出 ClassIsland",
            "classisland.app.restart": "重启 ClassIsland",
        }
        return fallback.get(action_id, action_id)

    def available_trigger_groups(self) -> dict[str, list[tuple[str, str]]]:
        register_builtins()
        registered_ids = set(get_registered_trigger_ids())

        grouped: dict[str, list[tuple[str, str]]] = {}

        for group_name, items in self._trigger_groups.items():
            visible_items: list[tuple[str, str]] = []

            for trigger_id, default_name in items:
                info = get_trigger_info(trigger_id)
                display_name = info.Name if info else default_name

                if trigger_id in registered_ids or trigger_id == "classisland.trayMenu":
                    visible_items.append((trigger_id, display_name))

            if visible_items:
                grouped[group_name] = visible_items

        extras: list[tuple[str, str]] = []
        known_ids = {tid for items in self._trigger_groups.values() for tid, _ in items}
        for trigger_id in sorted(registered_ids):
            if trigger_id in known_ids:
                continue
            info = get_trigger_info(trigger_id)
            extras.append((trigger_id, info.Name if info else self._trigger_name_fallback(trigger_id)))

        if extras:
            grouped["其它"] = extras

        return grouped

    def available_action_groups(self) -> dict[str, list[tuple[str, str]]]:
        register_builtins()
        registered_ids = set(get_registered_action_ids())

        grouped: dict[str, list[tuple[str, str]]] = {}

        for group_name, items in self._action_groups.items():
            visible_items: list[tuple[str, str]] = []
            for action_id, default_name in items:
                if action_id not in registered_ids:
                    continue
                info = get_action_info(action_id)
                display_name = info.Name if info else default_name
                visible_items.append((action_id, display_name))
            if visible_items:
                grouped[group_name] = visible_items

        extras: list[tuple[str, str]] = []
        known_ids = {aid for items in self._action_groups.values() for aid, _ in items}
        for action_id in sorted(registered_ids):
            if action_id in known_ids:
                continue
            info = get_action_info(action_id)
            extras.append((action_id, info.Name if info else self._action_name_fallback(action_id)))

        if extras:
            grouped["其它"] = extras

        return grouped

    def available_triggers(self) -> list[tuple[str, str]]:
        flat: list[tuple[str, str]] = []
        for _, items in self.available_trigger_groups().items():
            flat.extend(items)
        return flat

    def available_actions(self) -> list[tuple[str, str]]:
        flat: list[tuple[str, str]] = []
        for _, items in self.available_action_groups().items():
            flat.extend(items)
        return flat

    # =========================================================
    # Display helpers
    # =========================================================

    def workflow_display_text(self, workflow: Workflow) -> str:
        name = workflow.ActionSet.Name
        enabled = "启用" if workflow.ActionSet.IsEnabled else "禁用"
        revert = "可恢复" if workflow.ActionSet.IsRevertEnabled else "不恢复"
        return f"{name} [{enabled}/{revert}]"

    def trigger_display_text(self, trigger: TriggerSettings) -> str:
        info = get_trigger_info(trigger.Id)
        name = info.Name if info else self._trigger_name_fallback(trigger.Id)
        summary = self.trigger_summary(trigger)
        return f"{name}  {summary}".strip()

    def action_display_text(self, action: ActionItem) -> str:
        info = get_action_info(action.Id)
        name = info.Name if info else self._action_name_fallback(action.Id)
        summary = self.action_summary(action)
        return f"{name}  {summary}".strip()

    def trigger_summary(self, trigger: TriggerSettings) -> str:
        s = trigger.Settings
        if s is None:
            return ""

        trigger_id = trigger.Id

        if trigger_id == "classisland.signal":
            return f"({getattr(s, 'SignalName', '')})"
        if trigger_id == "classisland.trayMenu":
            return f"({getattr(s, 'Header', '')})"
        if trigger_id == "classisland.uri":
            return f"({getattr(s, 'UriSuffix', '')})"
        if trigger_id == "classisland.cron":
            return f"({getattr(s, 'CronExpression', '')})"
        if trigger_id == "classisland.lessons.preTimePoint":
            return f"({getattr(getattr(s, 'TargetState', None), 'name', '')} 前 {getattr(s, 'TimeSeconds', '')}s)"

        return ""

    def action_summary(self, action: ActionItem) -> str:
        s = action.Settings
        if s is None:
            return ""

        action_id = action.Id

        if action_id == "classisland.showNotification":
            return f"({getattr(s, 'Mask', '') or getattr(s, 'Content', '')})"

        if action_id == "classisland.notification.weather":
            kind = int(getattr(s, "NotificationKind", 0))
            kind_map = {
                0: "三天天气预报",
                1: "天气预警",
                2: "逐小时天气",
            }
            return f"({kind_map.get(kind, kind)})"

        if action_id == "classisland.os.run":
            run_type = getattr(s, "RunType", None)
            run_type_name = getattr(run_type, "name", str(run_type)) if run_type is not None else ""
            target = getattr(s, "Value", "")
            if target:
                return f"({run_type_name}: {target})"
            return f"({run_type_name})"

        if action_id == "classisland.settings":
            return f"({getattr(s, 'Name', '')})"

        if action_id == "classisland.action.sleep":
            return f"({getattr(s, 'Value', '')}s)"

        if action_id == "classisland.broadcastSignal":
            return f"({getattr(s, 'SignalName', '')})"

        if action_id == "classisland.app.restart":
            return f"(quiet={getattr(s, 'Value', False)})"

        return ""
