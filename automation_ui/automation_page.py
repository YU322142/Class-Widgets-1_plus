from __future__ import annotations

from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QListWidgetItem,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    ListWidget,
    PrimaryPushButton,
    PushButton,
    SmoothScrollArea,
    StrongBodyLabel,
    TitleLabel,
)

from .controller import AutomationUiController
from .property_editor import AutomationPropertyEditor


TRIGGER_DESCRIPTIONS: dict[str, str] = {
    "classisland.lifetime.startup": "在应用启动时触发。适合显示启动提示、初始化某些动作。",
    "classisland.lifetime.stopping": "在应用退出时触发。适合保存状态、发送退出通知。",
    "classisland.lessons.currentTimeStateChanged": "当当前时间状态发生变化时触发，如上课、课间、放学。",
    "classisland.lessons.onClass": "进入上课状态时触发。",
    "classisland.lessons.onBreakingTime": "进入课间休息状态时触发。",
    "classisland.lessons.onAfterSchool": "当天课程结束，进入放学状态时触发。",
    "classisland.lessons.preTimePoint": "在指定状态开始前若干秒触发，例如上课前 60 秒。",
    "classisland.cron": "按照 cron 表达式定时触发。适合周期性任务。",
    "classisland.signal": "收到应用内信号时触发。适合动作之间联动。",
    "classisland.uri": "调用指定 URI 时触发。适合外部调用或快捷链接。",
    "classisland.trayMenu": "从托盘菜单点击时触发。适合手动测试或快捷执行。",
    "classisland.ruleSet.rulesetChanged": "当规则集状态更新时触发。",
}

ACTION_DESCRIPTIONS: dict[str, str] = {
    "classisland.showNotification": "显示提醒通知，可选等待显示完成。",
    "classisland.notification.weather": "显示天气提醒，包括三天天气、天气预警、逐小时天气。",
    "classisland.os.run": "运行程序、命令、文件、文件夹或 URL。",
    "classisland.settings": "修改应用设置；启用恢复时会使用设置叠层。",
    "classisland.broadcastSignal": "广播一个应用内信号，可用于联动其他 SignalTrigger。",
    "classisland.action.sleep": "等待指定时长，常用于串行动作之间的延迟。",
    "classisland.app.quit": "退出当前应用。",
    "classisland.app.restart": "重启当前应用。",
}


class CardFrame(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AutomationCardFrame")
        self.setStyleSheet(
            """
            QFrame#AutomationCardFrame {
                background: rgba(255, 255, 255, 0.72);
                border: 1px solid rgba(0, 0, 0, 0.035);
                border-radius: 12px;
            }
            """
        )


class SectionHeader(QWidget):
    def __init__(self, title: str, desc: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.title_label = StrongBodyLabel(title)
        layout.addWidget(self.title_label)

        self.desc_label = CaptionLabel(desc)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #666;")
        self.desc_label.setVisible(bool(desc))
        layout.addWidget(self.desc_label)


class GroupedPickerDialog(QDialog):
    """
    更适合初学者的分组选择弹窗：
    - 左侧分组
    - 中间条目
    - 下方说明
    """

    def __init__(
        self,
        title: str,
        groups: dict[str, list[tuple[str, str]]],
        item_descriptions: dict[str, str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(780, 500)

        self._groups = groups
        self._descriptions = item_descriptions or {}
        self.selected_id: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title_label = TitleLabel(title)
        root.addWidget(title_label)

        desc = BodyLabel("先选择左侧分组，再选择具体条目。")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666;")
        root.addWidget(desc)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left_card = CardFrame()
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)
        left_layout.addWidget(SectionHeader("分组", "按概念分类，方便快速定位。"))
        self.group_list = ListWidget()
        self.group_list.setAlternatingRowColors(True)
        left_layout.addWidget(self.group_list, 1)

        right_card = CardFrame()
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8)
        right_layout.addWidget(SectionHeader("条目", "请选择你要添加的触发器或动作。"))
        self.item_list = ListWidget()
        self.item_list.setAlternatingRowColors(True)
        right_layout.addWidget(self.item_list, 1)

        splitter.addWidget(left_card)
        splitter.addWidget(right_card)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 4)

        self.desc_card = CardFrame()
        desc_layout = QVBoxLayout(self.desc_card)
        desc_layout.setContentsMargins(12, 10, 12, 10)
        desc_layout.setSpacing(4)
        desc_layout.addWidget(SectionHeader("说明"))
        self.desc_label = BodyLabel("请选择一个条目后，这里会显示它的用途。")
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #444;")
        desc_layout.addWidget(self.desc_label)
        root.addWidget(self.desc_card)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.ok_btn = PrimaryPushButton("确定")
        self.cancel_btn = PushButton("取消")
        btn_row.addWidget(self.ok_btn)
        btn_row.addWidget(self.cancel_btn)
        root.addLayout(btn_row)

        self.group_list.currentRowChanged.connect(self._on_group_changed)
        self.item_list.currentRowChanged.connect(self._on_item_changed)
        self.item_list.itemDoubleClicked.connect(lambda _: self._on_accept())
        self.ok_btn.clicked.connect(self._on_accept)
        self.cancel_btn.clicked.connect(self.reject)

        for group_name in self._groups.keys():
            self.group_list.addItem(group_name)

        if self.group_list.count() > 0:
            self.group_list.setCurrentRow(0)

    def _on_group_changed(self, row: int) -> None:
        self.item_list.clear()
        self.desc_label.setText("请选择一个条目后，这里会显示它的用途。")

        if row < 0:
            return

        group_name = self.group_list.item(row).text()
        items = self._groups.get(group_name, [])

        for item_id, display_name in items:
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, item_id)
            item.setToolTip(item_id)
            self.item_list.addItem(item)

        if self.item_list.count() > 0:
            self.item_list.setCurrentRow(0)

    def _on_item_changed(self, row: int) -> None:
        item = self.item_list.item(row)
        if item is None:
            self.desc_label.setText("请选择一个条目后，这里会显示它的用途。")
            return

        item_id = item.data(Qt.UserRole)
        desc = self._descriptions.get(item_id, f"ID: {item_id}")
        self.desc_label.setText(desc)

    def _on_accept(self) -> None:
        item = self.item_list.currentItem()
        if item is None:
            QMessageBox.warning(self, "选择", "请先选择一个条目。")
            return

        self.selected_id = item.data(Qt.UserRole)
        self.accept()


class AutomationSettingsPage(QWidget):
    """
    自动化设置页（第二步 UI 优化版）

    目标：
    - 更贴近 ClassWidgets 现有设置页风格
    - 更适合初学者
    - 不改变你当前已经稳定的运行逻辑
    """

    def __init__(self, runtime: Any, conf_module: Any, parent=None) -> None:
        super().__init__(parent)
        self.controller = AutomationUiController(runtime, conf_module)

        self._current_workflow_index: int = -1
        self._current_trigger_index: int = -1
        self._current_action_index: int = -1

        self._build_ui()
        self._connect_signals()

        self.controller.ensure_default_config()
        self.controller.load_current()
        self._reload_all()
        self._set_status_info(self._build_idle_status_text())

    # =========================================================
    # UI
    # =========================================================

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 0)
        root.setSpacing(18)

        self.title_label = TitleLabel("自动化")
        root.addWidget(self.title_label)

        self.subtitle_label = BodyLabel(
            "通过“触发器 + 条件 + 动作”的方式，配置应用在不同场景下自动执行任务。"
        )
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setStyleSheet("color: #666;")
        root.addWidget(self.subtitle_label)

        self.scroll = SmoothScrollArea()
        self.scroll.setStyleSheet("background: transparent; border: none")
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll, 1)

        self.scroll_content = QWidget()
        self.scroll.setWidget(self.scroll_content)

        content_layout = QVBoxLayout(self.scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 24)
        content_layout.setSpacing(18)

        # 快速开始卡
        self.quick_start_card = CardFrame()
        quick_layout = QVBoxLayout(self.quick_start_card)
        quick_layout.setContentsMargins(16, 16, 16, 16)
        quick_layout.setSpacing(8)
        quick_layout.addWidget(SectionHeader("快速开始", "如果你是第一次使用，建议按这个顺序操作："))

        self.quick_start_label = BodyLabel(
            "1. 选择一个配置文件\n"
            "2. 新建一个工作流\n"
            "3. 给工作流添加触发器（决定什么时候触发）\n"
            "4. 给工作流添加动作（决定触发后做什么）\n"
            "5. 点击“保存”写入文件；如果希望当前会话立即生效，再点击“应用到运行时”"
        )
        self.quick_start_label.setWordWrap(True)
        self.quick_start_label.setStyleSheet("color: #444;")
        quick_layout.addWidget(self.quick_start_label)
        content_layout.addWidget(self.quick_start_card)

        # 顶部配置卡
        self.config_card = CardFrame()
        config_layout = QVBoxLayout(self.config_card)
        config_layout.setContentsMargins(16, 16, 16, 16)
        config_layout.setSpacing(10)

        config_layout.addWidget(
            SectionHeader(
                "配置文件",
                "自动化数据保存在 Automations/*.json 中。应用到运行时后，当前会话会按当前配置文件整体重载，不会和旧工作流合并。",
            )
        )

        row1 = QHBoxLayout()
        self.config_combo = ComboBox()
        row1.addWidget(self.config_combo, 1)

        self.reload_btn = PushButton("重载")
        self.save_btn = PushButton("保存到文件")
        self.apply_btn = PrimaryPushButton("应用到运行时")
        self.new_workflow_btn = PushButton("新建工作流")
        self.delete_workflow_btn = PushButton("删除工作流")

        row1.addWidget(self.reload_btn)
        row1.addWidget(self.save_btn)
        row1.addWidget(self.apply_btn)
        row1.addWidget(self.new_workflow_btn)
        row1.addWidget(self.delete_workflow_btn)
        config_layout.addLayout(row1)

        self.config_info_label = BodyLabel("")
        self.config_info_label.setWordWrap(True)
        self.config_info_label.setStyleSheet("color: #444;")
        config_layout.addWidget(self.config_info_label)
        content_layout.addWidget(self.config_card)

        # 状态卡
        self.status_card = CardFrame()
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(16, 12, 16, 12)
        status_layout.setSpacing(4)

        status_layout.addWidget(SectionHeader("当前状态"))
        self.status_label = BodyLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        status_layout.addWidget(self.status_label)

        content_layout.addWidget(self.status_card)

        # 主编辑区
        self.main_splitter = QSplitter(Qt.Horizontal)
        content_layout.addWidget(self.main_splitter, 1)

        # 左：工作流
        self.workflow_card = CardFrame()
        workflow_layout = QVBoxLayout(self.workflow_card)
        workflow_layout.setContentsMargins(12, 12, 12, 12)
        workflow_layout.setSpacing(10)

        workflow_layout.addWidget(
            SectionHeader("工作流", "工作流是自动化的基本单位。一个工作流通常包含：触发器、可选条件、动作。")
        )

        self.workflow_list = ListWidget()
        self.workflow_list.setAlternatingRowColors(True)
        workflow_layout.addWidget(self.workflow_list, 1)

        self.workflow_tip = CaptionLabel("选中左侧工作流后，可在中间查看触发器和动作，在右侧编辑属性。")
        self.workflow_tip.setWordWrap(True)
        self.workflow_tip.setStyleSheet("color: #666;")
        workflow_layout.addWidget(self.workflow_tip)

        workflow_btns = QHBoxLayout()
        self.workflow_up_btn = PushButton("上移")
        self.workflow_down_btn = PushButton("下移")
        workflow_btns.addWidget(self.workflow_up_btn)
        workflow_btns.addWidget(self.workflow_down_btn)
        workflow_layout.addLayout(workflow_btns)

        self.main_splitter.addWidget(self.workflow_card)

        # 中：触发器 / 条件 / 动作
        self.middle_container = QWidget()
        middle_layout = QVBoxLayout(self.middle_container)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(12)

        self.trigger_card = CardFrame()
        trigger_layout = QVBoxLayout(self.trigger_card)
        trigger_layout.setContentsMargins(12, 12, 12, 12)
        trigger_layout.setSpacing(10)
        trigger_layout.addWidget(
            SectionHeader("触发器", "触发器决定工作流在什么时候开始执行。")
        )

        self.trigger_list = ListWidget()
        self.trigger_list.setAlternatingRowColors(True)
        trigger_layout.addWidget(self.trigger_list)

        self.trigger_tip = CaptionLabel("常见示例：应用启动时、托盘菜单点击时、收到信号时、到达指定时间时。")
        self.trigger_tip.setWordWrap(True)
        self.trigger_tip.setStyleSheet("color: #666;")
        trigger_layout.addWidget(self.trigger_tip)

        trigger_btns = QHBoxLayout()
        self.add_trigger_btn = PushButton("添加触发器")
        self.del_trigger_btn = PushButton("删除触发器")
        self.trigger_up_btn = PushButton("上移")
        self.trigger_down_btn = PushButton("下移")
        trigger_btns.addWidget(self.add_trigger_btn)
        trigger_btns.addWidget(self.del_trigger_btn)
        trigger_btns.addWidget(self.trigger_up_btn)
        trigger_btns.addWidget(self.trigger_down_btn)
        trigger_layout.addLayout(trigger_btns)

        middle_layout.addWidget(self.trigger_card)

        self.rules_card = CardFrame()
        rules_layout = QVBoxLayout(self.rules_card)
        rules_layout.setContentsMargins(12, 12, 12, 12)
        rules_layout.setSpacing(10)
        rules_layout.addWidget(
            SectionHeader("条件 / 规则集", "条件用于进一步限制工作流是否执行。")
        )
        self.rules_hint_label = BodyLabel("当前版本暂未提供完整规则集编辑器。下一阶段将补充规则组 / 规则条目可视化编辑。")
        self.rules_hint_label.setWordWrap(True)
        self.rules_hint_label.setStyleSheet("color: #666;")
        rules_layout.addWidget(self.rules_hint_label)
        middle_layout.addWidget(self.rules_card)

        self.action_card = CardFrame()
        action_layout = QVBoxLayout(self.action_card)
        action_layout.setContentsMargins(12, 12, 12, 12)
        action_layout.setSpacing(10)
        action_layout.addWidget(
            SectionHeader("动作", "动作会在触发器满足后按顺序串行执行。")
        )

        self.action_list = ListWidget()
        self.action_list.setAlternatingRowColors(True)
        action_layout.addWidget(self.action_list, 1)

        self.action_tip = CaptionLabel("常见示例：显示提醒、运行程序、等待时长、修改设置、广播信号。")
        self.action_tip.setWordWrap(True)
        self.action_tip.setStyleSheet("color: #666;")
        action_layout.addWidget(self.action_tip)

        action_btns = QHBoxLayout()
        self.add_action_btn = PushButton("添加动作")
        self.del_action_btn = PushButton("删除动作")
        self.action_up_btn = PushButton("上移")
        self.action_down_btn = PushButton("下移")
        action_btns.addWidget(self.add_action_btn)
        action_btns.addWidget(self.del_action_btn)
        action_btns.addWidget(self.action_up_btn)
        action_btns.addWidget(self.action_down_btn)
        action_layout.addLayout(action_btns)

        middle_layout.addWidget(self.action_card, 1)

        self.main_splitter.addWidget(self.middle_container)

        # 右：属性
        self.property_card = CardFrame()
        property_layout = QVBoxLayout(self.property_card)
        property_layout.setContentsMargins(12, 12, 12, 12)
        property_layout.setSpacing(10)
        property_layout.addWidget(
            SectionHeader("属性", "这里显示当前选中对象的详细配置。")
        )

        self.property_editor = AutomationPropertyEditor()
        property_layout.addWidget(self.property_editor, 1)

        self.main_splitter.addWidget(self.property_card)

        self.main_splitter.setStretchFactor(0, 2)
        self.main_splitter.setStretchFactor(1, 3)
        self.main_splitter.setStretchFactor(2, 3)

    # =========================================================
    # Status helpers
    # =========================================================

    def _set_status_style(self, fg: str, bg: str) -> None:
        self.status_card.setObjectName("AutomationStatusCard")
        self.status_card.setStyleSheet(
            f"""
            QFrame#AutomationStatusCard {{
                background: {bg};
                border: 1px solid rgba(0, 0, 0, 0.035);
                border-radius: 12px;
            }}
            """
        )
        self.status_label.setStyleSheet(
            f"""
            QLabel {{
                color: {fg};
                background: transparent;
                border: none;
            }}
            """
        )

    def _set_status_info(self, text: str) -> None:
        self.status_label.setText(text)
        self._set_status_style("#1f4e79", "rgba(0, 120, 215, 0.08)")

    def _set_status_saved(self, text: str | None = None) -> None:
        if text is None:
            if self.controller.has_live_runtime():
                text = "已保存到文件，尚未应用到当前运行时。点击“应用到运行时”后，当前会话将被当前配置文件整体替换。"
            else:
                text = "已保存到文件。当前无 live runtime。"
        self.status_label.setText(text)
        self._set_status_style("#8a5a00", "rgba(255, 170, 0, 0.10)")

    def _set_status_applied(self, text: str | None = None) -> None:
        if text is None:
            text = "已应用到当前运行时。当前会话已按当前配置文件重新加载。"
        self.status_label.setText(text)
        self._set_status_style("#1e6b34", "rgba(46, 204, 113, 0.10)")

    def _set_status_error(self, text: str) -> None:
        self.status_label.setText(text)
        self._set_status_style("#8b1e1e", "rgba(255, 0, 0, 0.08)")

    def _build_idle_status_text(self) -> str:
        name = self.controller.get_current_config_name()
        wf_count = len(self.controller.workflows)
        if self.controller.has_live_runtime():
            return f"当前正在编辑配置：{name}（{wf_count} 个工作流）。修改后请先保存，若要影响当前会话，请点击“应用到运行时”。"
        return f"当前正在编辑配置：{name}（{wf_count} 个工作流）。当前无 live runtime，仅文件编辑模式。"

    def _update_config_info(self) -> None:
        name = self.controller.get_current_config_name()
        wf_count = len(self.controller.workflows)
        runtime_text = "已连接当前运行时" if self.controller.has_live_runtime() else "仅文件模式"
        self.config_info_label.setText(f"当前配置：{name}    ·    工作流数量：{wf_count}    ·    {runtime_text}")

    # =========================================================
    # Signals
    # =========================================================

    def _connect_signals(self) -> None:
        self.reload_btn.clicked.connect(self._on_reload)
        self.save_btn.clicked.connect(self._on_save)
        self.apply_btn.clicked.connect(self._on_apply)

        self.new_workflow_btn.clicked.connect(self._on_new_workflow)
        self.delete_workflow_btn.clicked.connect(self._on_delete_workflow)
        self.workflow_up_btn.clicked.connect(self._on_workflow_up)
        self.workflow_down_btn.clicked.connect(self._on_workflow_down)

        self.add_trigger_btn.clicked.connect(self._on_add_trigger)
        self.del_trigger_btn.clicked.connect(self._on_delete_trigger)
        self.trigger_up_btn.clicked.connect(self._on_trigger_up)
        self.trigger_down_btn.clicked.connect(self._on_trigger_down)

        self.add_action_btn.clicked.connect(self._on_add_action)
        self.del_action_btn.clicked.connect(self._on_delete_action)
        self.action_up_btn.clicked.connect(self._on_action_up)
        self.action_down_btn.clicked.connect(self._on_action_down)

        self.workflow_list.currentRowChanged.connect(self._on_workflow_selected)
        self.trigger_list.currentRowChanged.connect(self._on_trigger_selected)
        self.action_list.currentRowChanged.connect(self._on_action_selected)

        self.property_editor.changed.connect(self._on_property_changed)
        self.config_combo.currentIndexChanged.connect(self._on_config_changed)

    # =========================================================
    # Reload UI
    # =========================================================

    def _reload_all(self) -> None:
        self._reload_configs()
        self._reload_workflows()
        self._update_config_info()

    def _reload_configs(self) -> None:
        self.config_combo.blockSignals(True)
        self.config_combo.clear()

        configs = self.controller.list_configs()
        if not configs:
            self.controller.ensure_default_config()
            configs = self.controller.list_configs()

        current = self.controller.get_current_config_name()

        for name in configs:
            self.config_combo.addItem(name)

        idx = self.config_combo.findText(current)
        self.config_combo.setCurrentIndex(max(0, idx))
        self.config_combo.blockSignals(False)

    def _reload_workflows(self) -> None:
        self.workflow_list.clear()

        for workflow in self.controller.workflows:
            self.workflow_list.addItem(
                QListWidgetItem(self.controller.workflow_display_text(workflow))
            )

        if self.controller.workflows:
            if self._current_workflow_index < 0:
                self._current_workflow_index = 0
            self._current_workflow_index = min(self._current_workflow_index, len(self.controller.workflows) - 1)
            self.workflow_list.setCurrentRow(self._current_workflow_index)
        else:
            self._current_workflow_index = -1
            self.trigger_list.clear()
            self.action_list.clear()
            self.property_editor.set_target(None, None)

    def _reload_middle(self) -> None:
        self.trigger_list.clear()
        self.action_list.clear()

        workflow = self._get_current_workflow()
        if workflow is None:
            self.property_editor.set_target(None, None)
            self._update_config_info()
            return

        for trigger in workflow.Triggers:
            self.trigger_list.addItem(
                QListWidgetItem(self.controller.trigger_display_text(trigger))
            )

        for action in workflow.ActionSet.Actions:
            self.action_list.addItem(
                QListWidgetItem(self.controller.action_display_text(action))
            )

        self.property_editor.set_target("workflow", workflow)
        self._update_config_info()

    def _refresh_summary_texts_only(self) -> None:
        for i, workflow in enumerate(self.controller.workflows):
            item = self.workflow_list.item(i)
            if item is not None:
                item.setText(self.controller.workflow_display_text(workflow))

        workflow = self._get_current_workflow()
        if workflow is None:
            self._update_config_info()
            return

        for i, trigger in enumerate(workflow.Triggers):
            item = self.trigger_list.item(i)
            if item is not None:
                item.setText(self.controller.trigger_display_text(trigger))

        for i, action in enumerate(workflow.ActionSet.Actions):
            item = self.action_list.item(i)
            if item is not None:
                item.setText(self.controller.action_display_text(action))

        self._update_config_info()

    # =========================================================
    # Current object helpers
    # =========================================================

    def _get_current_workflow(self):
        if 0 <= self._current_workflow_index < len(self.controller.workflows):
            return self.controller.workflows[self._current_workflow_index]
        return None

    def _get_current_trigger(self):
        workflow = self._get_current_workflow()
        if workflow is None:
            return None
        if 0 <= self._current_trigger_index < len(workflow.Triggers):
            return workflow.Triggers[self._current_trigger_index]
        return None

    def _get_current_action(self):
        workflow = self._get_current_workflow()
        if workflow is None:
            return None
        if 0 <= self._current_action_index < len(workflow.ActionSet.Actions):
            return workflow.ActionSet.Actions[self._current_action_index]
        return None

    # =========================================================
    # Picker dialogs
    # =========================================================

    def _pick_trigger_id(self) -> str | None:
        groups = self.controller.available_trigger_groups()
        dlg = GroupedPickerDialog("添加触发器", groups, TRIGGER_DESCRIPTIONS, self)
        if dlg.exec_() == QDialog.Accepted:
            return dlg.selected_id
        return None

    def _pick_action_id(self) -> str | None:
        groups = self.controller.available_action_groups()
        dlg = GroupedPickerDialog("添加动作", groups, ACTION_DESCRIPTIONS, self)
        if dlg.exec_() == QDialog.Accepted:
            return dlg.selected_id
        return None

    # =========================================================
    # Top bar
    # =========================================================

    def _on_reload(self) -> None:
        try:
            self.controller.load_current()
            self._reload_all()
            self._set_status_info(
                f"已从文件重载配置：{self.controller.get_current_config_name()}。"
                + (" 如需影响当前会话，请点击“应用到运行时”。" if self.controller.has_live_runtime() else "")
            )
        except Exception as e:
            self._set_status_error(f"重载配置失败：{e}")
            QMessageBox.critical(self, "自动化", f"重载配置失败：\n{e}")

    def _on_save(self) -> None:
        try:
            self.controller.save_current()
            self._set_status_saved()
            self._update_config_info()
            QMessageBox.information(self, "自动化", "自动化配置已保存到文件。")
        except Exception as e:
            self._set_status_error(f"保存配置失败：{e}")
            QMessageBox.critical(self, "自动化", f"保存配置失败：\n{e}")

    def _on_apply(self) -> None:
        try:
            config_name = self.controller.get_current_config_name()
            wf_count = len(self.controller.workflows)

            if self.controller.has_live_runtime():
                ret = QMessageBox.question(
                    self,
                    "应用到运行时",
                    f"将使用当前配置文件“{config_name}”中的 {wf_count} 个工作流替换当前运行时。\n\n"
                    f"这不会合并旧工作流，而是整体重载。\n\n"
                    f"是否继续？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if ret != QMessageBox.Yes:
                    return

            self.controller.save_current()
            applied = self.controller.apply_current()
            self._update_config_info()

            if applied:
                self._set_status_applied(
                    f"已应用到当前运行时：{config_name}（{wf_count} 个工作流）。"
                )
                QMessageBox.information(self, "自动化", "已应用到当前运行时。")
            else:
                self._set_status_saved("当前没有可应用的运行时，已仅保存到文件。")
                QMessageBox.information(self, "自动化", "当前没有可应用的运行时，仅保存到了文件。")
        except Exception as e:
            self._set_status_error(f"应用到运行时失败：{e}")
            QMessageBox.critical(self, "自动化", f"应用到运行时失败：\n{e}")

    def _on_config_changed(self, index: int) -> None:
        if index < 0:
            return

        try:
            name = self.config_combo.currentText().strip()
            if not name:
                return

            self.controller.set_current_config_name(name)
            self.controller.load_current()

            self._current_workflow_index = -1
            self._current_trigger_index = -1
            self._current_action_index = -1
            self._reload_workflows()
            self._update_config_info()

            self._set_status_saved(
                f"当前正在编辑配置：{name}。"
                + (" 已切换文件，若要影响当前会话，请点击“应用到运行时”。" if self.controller.has_live_runtime() else " 当前无 live runtime，仅文件编辑模式。")
            )
        except Exception as e:
            self._set_status_error(f"切换配置文件失败：{e}")
            QMessageBox.critical(self, "自动化", f"切换配置文件失败：\n{e}")

    # =========================================================
    # Workflow actions
    # =========================================================

    def _on_new_workflow(self) -> None:
        try:
            self.controller.create_workflow()
            self._current_workflow_index = len(self.controller.workflows) - 1
            self._reload_workflows()
            self._update_config_info()
            self._set_status_saved("已新建工作流，并保存到文件。若要当前会话生效，请点击“应用到运行时”。")
        except Exception as e:
            self._set_status_error(f"新建工作流失败：{e}")
            QMessageBox.critical(self, "自动化", f"新建工作流失败：\n{e}")

    def _on_delete_workflow(self) -> None:
        try:
            if self._current_workflow_index < 0:
                return
            self.controller.delete_workflow(self._current_workflow_index)
            self._current_workflow_index = min(self._current_workflow_index, len(self.controller.workflows) - 1)
            self._reload_workflows()
            self._update_config_info()
            self._set_status_saved("已删除工作流，并保存到文件。若要当前会话生效，请点击“应用到运行时”。")
        except Exception as e:
            self._set_status_error(f"删除工作流失败：{e}")
            QMessageBox.critical(self, "自动化", f"删除工作流失败：\n{e}")

    def _on_workflow_up(self) -> None:
        try:
            self._current_workflow_index = self.controller.move_workflow_up(self._current_workflow_index)
            self._reload_workflows()
            self._update_config_info()
            self._set_status_saved("已调整工作流顺序，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"上移工作流失败：{e}")
            QMessageBox.critical(self, "自动化", f"上移工作流失败：\n{e}")

    def _on_workflow_down(self) -> None:
        try:
            self._current_workflow_index = self.controller.move_workflow_down(self._current_workflow_index)
            self._reload_workflows()
            self._update_config_info()
            self._set_status_saved("已调整工作流顺序，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"下移工作流失败：{e}")
            QMessageBox.critical(self, "自动化", f"下移工作流失败：\n{e}")

    # =========================================================
    # Trigger actions
    # =========================================================

    def _on_add_trigger(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return

            trigger_id = self._pick_trigger_id()
            if not trigger_id:
                return

            self.controller.add_trigger(workflow, trigger_id)
            self._reload_middle()
            self._update_config_info()
            self._set_status_saved("已添加触发器，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"添加触发器失败：{e}")
            QMessageBox.critical(self, "自动化", f"添加触发器失败：\n{e}")

    def _on_delete_trigger(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return
            self.controller.delete_trigger(workflow, self._current_trigger_index)
            self._current_trigger_index = -1
            self._reload_middle()
            self._update_config_info()
            self._set_status_saved("已删除触发器，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"删除触发器失败：{e}")
            QMessageBox.critical(self, "自动化", f"删除触发器失败：\n{e}")

    def _on_trigger_up(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return
            self._current_trigger_index = self.controller.move_trigger_up(workflow, self._current_trigger_index)
            self._reload_middle()
            if self._current_trigger_index >= 0:
                self.trigger_list.setCurrentRow(self._current_trigger_index)
            self._update_config_info()
            self._set_status_saved("已调整触发器顺序，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"上移触发器失败：{e}")
            QMessageBox.critical(self, "自动化", f"上移触发器失败：\n{e}")

    def _on_trigger_down(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return
            self._current_trigger_index = self.controller.move_trigger_down(workflow, self._current_trigger_index)
            self._reload_middle()
            if self._current_trigger_index >= 0:
                self.trigger_list.setCurrentRow(self._current_trigger_index)
            self._update_config_info()
            self._set_status_saved("已调整触发器顺序，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"下移触发器失败：{e}")
            QMessageBox.critical(self, "自动化", f"下移触发器失败：\n{e}")

    # =========================================================
    # Action actions
    # =========================================================

    def _on_add_action(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return

            action_id = self._pick_action_id()
            if not action_id:
                return

            self.controller.add_action(workflow, action_id)
            self._reload_middle()
            self._update_config_info()
            self._set_status_saved("已添加动作，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"添加动作失败：{e}")
            QMessageBox.critical(self, "自动化", f"添加动作失败：\n{e}")

    def _on_delete_action(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return
            self.controller.delete_action(workflow, self._current_action_index)
            self._current_action_index = -1
            self._reload_middle()
            self._update_config_info()
            self._set_status_saved("已删除动作，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"删除动作失败：{e}")
            QMessageBox.critical(self, "自动化", f"删除动作失败：\n{e}")

    def _on_action_up(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return
            self._current_action_index = self.controller.move_action_up(workflow, self._current_action_index)
            self._reload_middle()
            if self._current_action_index >= 0:
                self.action_list.setCurrentRow(self._current_action_index)
            self._update_config_info()
            self._set_status_saved("已调整动作顺序，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"上移动作失败：{e}")
            QMessageBox.critical(self, "自动化", f"上移动作失败：\n{e}")

    def _on_action_down(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return
            self._current_action_index = self.controller.move_action_down(workflow, self._current_action_index)
            self._reload_middle()
            if self._current_action_index >= 0:
                self.action_list.setCurrentRow(self._current_action_index)
            self._update_config_info()
            self._set_status_saved("已调整动作顺序，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"下移动作失败：{e}")
            QMessageBox.critical(self, "自动化", f"下移动作失败：\n{e}")

    # =========================================================
    # Selection
    # =========================================================

    def _on_workflow_selected(self, row: int) -> None:
        self._current_workflow_index = row
        self._current_trigger_index = -1
        self._current_action_index = -1
        self._reload_middle()

    def _on_trigger_selected(self, row: int) -> None:
        self._current_trigger_index = row
        if row >= 0:
            self.action_list.blockSignals(True)
            self.action_list.clearSelection()
            self.action_list.blockSignals(False)

        trigger = self._get_current_trigger()
        if trigger is not None:
            self.property_editor.set_target("trigger", trigger)
        elif self._get_current_workflow() is not None:
            self.property_editor.set_target("workflow", self._get_current_workflow())

    def _on_action_selected(self, row: int) -> None:
        self._current_action_index = row
        if row >= 0:
            self.trigger_list.blockSignals(True)
            self.trigger_list.clearSelection()
            self.trigger_list.blockSignals(False)

        action = self._get_current_action()
        if action is not None:
            self.property_editor.set_target("action", action)
        elif self._get_current_workflow() is not None:
            self.property_editor.set_target("workflow", self._get_current_workflow())

    # =========================================================
    # Property changed
    # =========================================================

    def _on_property_changed(self) -> None:
        try:
            self.controller.save_current()
            self._refresh_summary_texts_only()
            self._set_status_saved()
        except Exception as e:
            self._set_status_error(f"保存属性失败：{e}")
            QMessageBox.critical(self, "自动化", f"保存属性失败：\n{e}")
