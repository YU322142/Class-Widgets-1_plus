from __future__ import annotations

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
    # Extra info
    # =========================================================

    @property
    def has_live_runtime(self) -> bool:
        return self._real_runtime is not None


def build_editor_runtime(conf_module, runtime: Any | None):
    return EditorRuntimeAdapter(conf_module, runtime=runtime)
