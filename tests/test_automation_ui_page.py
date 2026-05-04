import os
import sys
from pathlib import Path


class AutomationSettingsAdapter:
    def __init__(self, conf_module):
        self._conf = conf_module
        state = conf_module.load_automation_state()
        self.CurrentAutomationConfig = state.get("CurrentAutomationConfig", "Default")
        self.IsAutomationEnabled = state.get("IsAutomationEnabled", True)
        self.SettingsOverlays = {}

    def sync_to_disk(self):
        self._conf.save_automation_state({
            "CurrentAutomationConfig": self.CurrentAutomationConfig,
            "IsAutomationEnabled": self.IsAutomationEnabled,
        })


class FakeAutomationService:
    def __init__(self):
        self.Workflows = []


class FakeContext:
    def __init__(self, settings):
        self.settings = settings


class FakeRuntime:
    """
    仅供自动化设置页测试使用：
    - 不启动真正 automation runtime
    - 不创建后台 loop / buses / triggers 运行时
    - 只负责读写 workflows
    """
    def __init__(self, conf_module):
        from automation.builtins import register_builtins
        from automation.compat import load_workflows_from_file, save_workflows_to_file

        register_builtins()

        self._conf = conf_module
        self._load_workflows_from_file = load_workflows_from_file
        self._save_workflows_to_file = save_workflows_to_file

        self.context = FakeContext(AutomationSettingsAdapter(conf_module))
        self.automation_service = FakeAutomationService()
        self._loaded_path = None

    def load_workflows(self, path):
        self._loaded_path = Path(path)
        self.automation_service.Workflows = self._load_workflows_from_file(path)

    def save_workflows(self, path=None):
        target = Path(path) if path is not None else self._loaded_path
        if target is None:
            raise ValueError("No workflow config path loaded.")
        self._save_workflows_to_file(target, self.automation_service.Workflows)
        self.context.settings.sync_to_disk()


def main():
    # 保证独立测试时路径指向项目根目录
    repo_root = Path(__file__).resolve().parents[1]
    os.chdir(repo_root)

    # 避免 basic_dirs / conf 等模块根据 tests/test_xxx.py 误判项目根
    sys.argv[0] = str(repo_root / "main.py")

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)

    import conf
    from automation_ui.automation_page import AutomationSettingsPage

    conf.ensure_default_automation_config()

    runtime = FakeRuntime(conf)
    runtime.load_workflows(conf.get_automation_config_path())

    page = AutomationSettingsPage(runtime, conf)
    page.resize(1400, 850)
    page.setWindowTitle("Automation Settings Test")
    page.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
