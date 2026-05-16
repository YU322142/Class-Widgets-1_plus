from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


class AutomationSettingsAdapter:
    def __init__(self, conf_module):
        self._conf = conf_module
        state = conf_module.load_automation_state()
        self.CurrentAutomationConfig = state.get("CurrentAutomationConfig", "Default")
        self.IsAutomationEnabled = state.get("IsAutomationEnabled", True)
        self.SettingsOverlays = {}

    def sync_to_disk(self):
        self._conf.save_automation_state(
            {
                "CurrentAutomationConfig": self.CurrentAutomationConfig,
                "IsAutomationEnabled": self.IsAutomationEnabled,
            }
        )


class _EditorAutomationService:
    def __init__(self):
        self.Workflows = []


class _EditorContext:
    def __init__(self, settings):
        self.settings = settings


class EditorRuntimeAdapter:
    """
    自动化设置页用的“编辑态 runtime”：
    - 永远不直接修改真实运行中的 automation runtime
    - 页面中所有操作只改编辑副本 + JSON 文件
    - 显式调用 apply_to_runtime() 时才作用到真实运行时
    - 测试触发 / 测试恢复会临时使用真实运行时的 ActionService 执行动作副本
    """

    def __init__(self, conf_module, runtime: Any | None = None):
        from automation.builtins import register_builtins
        from automation.compat import load_workflows_from_file, save_workflows_to_file

        register_builtins()

        self._conf = conf_module
        self._load_workflows_from_file = load_workflows_from_file
        self._save_workflows_to_file = save_workflows_to_file
        self._real_runtime = runtime
        self._loaded_path: Path | None = None

        self.context = _EditorContext(AutomationSettingsAdapter(conf_module))
        self.automation_service = _EditorAutomationService()

        # 测试动作时使用的临时 ActionSet 副本。
        # key 为 ActionSet.Guid，确保“测试触发”后再点“测试恢复”可以恢复同一组 overlay。
        self._test_action_sets: dict[str, Any] = {}

    # =========================================================
    # Editor file I/O
    # =========================================================

    def load_workflows(self, path):
        self._loaded_path = Path(path)
        self.automation_service.Workflows = self._load_workflows_from_file(path)

    def save_workflows(self, path=None):
        target = Path(path) if path is not None else self._loaded_path
        if target is None:
            raise ValueError("No workflow config path loaded.")

        self._save_workflows_to_file(target, self.automation_service.Workflows)
        self.context.settings.sync_to_disk()

    # =========================================================
    # Apply to live runtime
    # =========================================================

    def apply_to_runtime(self):
        if self._real_runtime is None:
            return False

        target = self._loaded_path
        if target is None:
            raise ValueError("No workflow config path loaded.")

        # 先保存编辑态副本
        self.save_workflows(target)

        # 同步自动化状态
        real_settings = getattr(self._real_runtime.context, "settings", None)
        editor_settings = self.context.settings

        if real_settings is not None:
            if hasattr(real_settings, "CurrentAutomationConfig"):
                real_settings.CurrentAutomationConfig = editor_settings.CurrentAutomationConfig
            if hasattr(real_settings, "IsAutomationEnabled"):
                real_settings.IsAutomationEnabled = editor_settings.IsAutomationEnabled
            if hasattr(real_settings, "sync_to_disk"):
                real_settings.sync_to_disk()

        # 真正重新加载运行时
        self._real_runtime.load_workflows(target)

        # 如果主程序挂了“重载后回调”，这里主动触发
        callback = getattr(self._real_runtime, "on_runtime_reloaded", None)
        if callable(callback):
            try:
                callback()
            except Exception:
                pass

        return True

    # =========================================================
    # Action test
    # =========================================================

    def _get_action_service(self):
        if self._real_runtime is None:
            raise RuntimeError("当前没有连接到运行中的自动化服务，无法测试动作。")

        action_service = getattr(self._real_runtime, "action_service", None)
        if action_service is None:
            raise RuntimeError("当前运行时没有可用的 ActionService，无法测试动作。")

        return action_service

    def _clone_action_set_for_test(self, workflow):
        from automation.enums import ActionSetStatus

        action_set = deepcopy(workflow.ActionSet)

        # 测试不污染编辑态 ActionSet 的运行状态
        action_set.Status = ActionSetStatus.Normal
        if hasattr(action_set, "_interrupt_requested"):
            action_set._interrupt_requested = False
        if hasattr(action_set, "_running"):
            action_set._running = False

        # 防御性清理 ActionService 动态挂上的运行时字段
        for attr in ("_interrupt_event", "_running_done_event", "_runner_task"):
            try:
                if hasattr(action_set, attr):
                    delattr(action_set, attr)
            except Exception:
                pass

        return action_set

    def _schedule_test_coro(self, coro, task_name: str):
        from automation.async_tools import schedule_coro

        task = schedule_coro(coro)

        def _done_callback(t):
            try:
                t.result()
            except Exception:
                logger = getattr(self._real_runtime, "logger", None)
                if logger is not None:
                    try:
                        logger.exception(f"自动化动作测试失败：{task_name}")
                        return
                    except Exception:
                        pass

                try:
                    import logging

                    logging.getLogger(__name__).exception(
                        "Automation action test failed: %s", task_name
                    )
                except Exception:
                    pass

        try:
            task.add_done_callback(_done_callback)
        except Exception:
            pass

        return task

    def test_invoke_workflow(self, workflow):
        """
        测试触发当前工作流的动作。
        注意：这会真实执行动作，但不会加载/触发触发器，也不会检查规则集。
        """
        if workflow is None:
            raise ValueError("未选择工作流。")

        if not getattr(workflow.ActionSet, "Actions", None):
            raise ValueError("当前工作流没有动作，无法测试。")

        action_service = self._get_action_service()
        action_set = self._clone_action_set_for_test(workflow)

        guid = str(getattr(action_set, "Guid", ""))
        if guid:
            self._test_action_sets[guid] = action_set

        return self._schedule_test_coro(
            action_service.InvokeActionSetAsync(
                action_set,
                is_revertable=bool(getattr(action_set, "IsRevertEnabled", False)),
            ),
            f"Invoke ActionSet[{getattr(action_set, 'Name', '')}]",
        )

    def test_revert_workflow(self, workflow):
        """
        测试恢复当前工作流的动作。
        优先恢复上一次测试触发时创建的 ActionSet 副本，以便恢复 SettingsOverlay 等同 Guid 状态。
        """
        if workflow is None:
            raise ValueError("未选择工作流。")

        if not getattr(workflow.ActionSet, "Actions", None):
            raise ValueError("当前工作流没有动作，无法测试恢复。")

        action_service = self._get_action_service()

        guid = str(getattr(workflow.ActionSet, "Guid", ""))
        action_set = self._test_action_sets.get(guid)

        if action_set is None:
            action_set = self._clone_action_set_for_test(workflow)
            if guid:
                self._test_action_sets[guid] = action_set

        return self._schedule_test_coro(
            action_service.RevertActionSetAsync(action_set),
            f"Revert ActionSet[{getattr(action_set, 'Name', '')}]",
        )

    # =========================================================
    # Extra info
    # =========================================================

    @property
    def has_live_runtime(self) -> bool:
        return self._real_runtime is not None


def build_editor_runtime(conf_module, runtime: Any | None):
    return EditorRuntimeAdapter(conf_module, runtime=runtime)
