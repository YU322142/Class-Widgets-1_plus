from __future__ import annotations

from typing import Any

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    Flyout,
    FlyoutAnimationType,
    InfoBarIcon,
    LineEdit,
    ListWidget,
    MessageBox,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    SmoothScrollArea,
    StrongBodyLabel,
    SubtitleLabel,
    TitleLabel,
    isDarkTheme,
    qconfig,
)

from .controller import AutomationUiController
from .property_editor import AutomationPropertyEditor
from .ruleset_editor import RulesetEditor

TRIGGER_DESCRIPTIONS: dict[str, str] = {
    "classisland.lifetime.startup": (
        "在 Class Widgets 启动并加载自动化运行时后触发一次。\n\n"
        "适合：显示启动提示、初始化自动化状态、广播一个启动信号。"
    ),
    "classisland.lifetime.stopping": (
        "在 Class Widgets 准备退出时触发一次。\n\n"
        "适合：保存状态、广播退出信号、执行简单清理动作。\n\n"
        "注意：退出阶段时间有限，不建议放很长的等待动作，也不建议再触发“退出应用 / 重启应用”。"
    ),
    "classisland.lessons.currentTimeStateChanged": (
        "当当前时间状态发生变化时触发，例如从课间进入上课、从上课进入课间、进入放学状态。\n\n"
        "如果你只关心具体状态，建议使用“上课时 / 课间休息时 / 放学时”。"
    ),
    "classisland.lessons.onClass": "进入上课状态时触发。",
    "classisland.lessons.onBreakingTime": "进入课间休息状态时触发。",
    "classisland.lessons.onAfterSchool": "当天课程结束并进入放学状态时触发。",
    "classisland.lessons.preTimePoint": (
        "在指定课程状态开始前若干秒触发。\n\n"
        "例如：\n"
        "• 上课前 60 秒提醒准备上课\n"
        "• 课间前 10 秒提前显示下课提示\n"
        "• 放学前 0 秒执行放学动作\n\n"
        "支持目标：上课、课间、放学。"
    ),
    "classisland.cron": (
        "按照 Cron 表达式定时触发，适合周期性任务。\n\n"
        "当前支持 5 段 Cron：\n"
        "分钟 小时 日期 月份 星期\n\n"
        "取值范围：\n"
        "• 分钟：0-59\n"
        "• 小时：0-23\n"
        "• 日期：1-31\n"
        "• 月份：1-12\n"
        "• 星期：0-7，其中 0 和 7 都表示周日\n\n"
        "支持写法：\n"
        "• * 任意值\n"
        "• */5 每 5 个单位\n"
        "• 1,2,3 多个值\n"
        "• 1-5 范围\n"
        "• 1-10/2 范围内步进\n\n"
        "常用例子：\n"
        "• * * * * * 每分钟触发一次\n"
        "• */5 * * * * 每 5 分钟触发一次\n"
        "• 0 7 * * * 每天 07:00 触发\n"
        "• 30 21 * * 1-5 工作日 21:30 触发\n"
        "• 0 8 1 * * 每月 1 日 08:00 触发\n\n"
        "注意：Cron 触发器按分钟触发，同一分钟内只会触发一次。"
    ),
    "classisland.signal": (
        "收到应用内信号时触发。\n\n"
        "通常和“广播信号”动作配合使用。两个地方填写完全相同的信号名即可联动。"
    ),
    "classisland.uri": (
        "调用自动化 URI 路由时触发。\n\n"
        "它不是“打开网页 URL”，也不是“访问 https 链接”。\n"
        "它用于让插件、脚本或程序内部代码主动触发某个工作流。\n\n"
        "用法：\n"
        "1. 在这里填写 URI 后缀，例如：demo/test\n"
        "2. 在代码里调用：emit_automation_uri(\"demo/test\")\n"
        "3. 如果要触发恢复流程，调用：emit_automation_uri(\"demo/test\", revert=True)\n\n"
        "注意：当前实现是应用内 URI 总线；如果要从浏览器地址栏或系统快捷方式直接触发，"
        "还需要额外注册系统 URL 协议或实现单实例 IPC 转发。"
    ),
    "classisland.trayMenu": (
        "在系统托盘菜单里添加一个自定义菜单项。\n\n"
        "点击这个菜单项时触发工作流，适合手动测试、快捷执行、临时开关。"
    ),
    "classisland.ruleSet.rulesetChanged": (
        "当规则集状态更新时触发。\n\n"
        "适合对前台窗口、天气、课程状态等条件变化做联动。"
    ),
}

ACTION_DESCRIPTIONS: dict[str, str] = {
    "classisland.showNotification": "显示 CW 风格提醒。注意：主提示与详细内容会同时显示，不是先标题再正文。",
    "classisland.notification.weather": "显示天气提醒，包括三天天气、天气预警、逐小时天气。",
    "classisland.os.run": "运行程序、命令、文件、文件夹或 URL。",
    "classisland.settings": "修改自动化自身设置（如当前配置、自动化开关）。当前不是完整的全应用设置编辑器。",
    "classisland.broadcastSignal": "广播一个应用内信号，可用于联动其他 SignalTrigger。",
    "classisland.action.sleep": "等待指定时长，常用于串行动作之间的延迟。",
    "classisland.app.quit": "退出应用。",
    "classisland.app.restart": "重启应用。",
}


def get_transparent_scroll_style(content_id: str) -> str:
    return f"""
    SmoothScrollArea, QAbstractScrollArea {{
        background: transparent;
        border: none;
    }}
    QWidget#{content_id} {{
        background: transparent;
    }}
    """


class CardFrame(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AutomationCardFrame")
        self._update_style()
        qconfig.themeChanged.connect(self._update_style)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    def _update_style(self):
        if isDarkTheme():
            self.setStyleSheet(
                """
                QFrame#AutomationCardFrame {
                    background: rgba(255, 255, 255, 0.045);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 12px;
                }
                """
            )
        else:
            self.setStyleSheet(
                """
                QFrame#AutomationCardFrame {
                    background: rgba(255, 255, 255, 0.82);
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
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.desc_label = CaptionLabel(desc)
        self.desc_label.setWordWrap(True)
        self.desc_label.setVisible(bool(desc))
        layout.addWidget(self.desc_label)


class AutomationTextFieldDialog(MessageBoxBase):
    """自动化配置名输入框"""

    def __init__(
            self,
            parent=None,
            title: str = "标题",
            text: str = "请输入内容",
            placeholder: str = "",
            validator=None,
    ) -> None:
        super().__init__(parent)
        self._validator = validator

        self.titleLabel = SubtitleLabel(title, self)
        self.contentLabel = BodyLabel(text, self)
        self.contentLabel.setWordWrap(True)

        self.textField = LineEdit(self)
        self.textField.setPlaceholderText(placeholder)
        self.textField.setClearButtonEnabled(True)

        self.tipLabel = CaptionLabel("", self)
        self.tipLabel.setWordWrap(True)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.contentLabel)
        self.viewLayout.addWidget(self.textField)
        self.viewLayout.addWidget(self.tipLabel)

        self.widget.setMinimumWidth(350)

        self.yesButton.setText("确定")
        self.cancelButton.setText("取消")
        self.yesButton.setEnabled(False)

        self.textField.textChanged.connect(self._on_text_changed)
        self.textField.returnPressed.connect(self._on_return_pressed)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.textField.setFocus)

    def _on_return_pressed(self) -> None:
        if self.yesButton.isEnabled():
            self.yesButton.click()

    def _on_text_changed(self, text: str) -> None:
        is_dark = isDarkTheme()
        color_err = "#ff99a4" if is_dark else "#c42b1c"
        color_ok = "#66cc66" if is_dark else "#0f7b0f"

        text = (text or "").strip()

        if not text:
            self.tipLabel.setStyleSheet(f"color: {color_err};")
            self.tipLabel.setText("名称不能为空。")
            self.yesButton.setEnabled(False)
            return

        if self._validator is not None:
            ok, message = self._validator(text)
            if not ok:
                self.tipLabel.setStyleSheet(f"color: {color_err};")
                self.tipLabel.setText(message)
                self.yesButton.setEnabled(False)
                return

        self.tipLabel.setStyleSheet(f"color: {color_ok};")
        self.tipLabel.setText("可以使用这个名称。")
        self.yesButton.setEnabled(True)

    def text(self) -> str:
        return self.textField.text().strip()


class GroupedPickerDialog(QDialog):
    def __init__(
            self,
            title: str,
            groups: dict[str, list[tuple[str, str]]],
            item_descriptions: dict[str, str] | None = None,
            parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 500)

        # 增加这两行用于适配深色模式
        self._update_style()
        qconfig.themeChanged.connect(self._update_style)

        self.selected_id: str | None = None
        self._groups = groups
        self._descriptions = item_descriptions or {}

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title_label = TitleLabel(title)
        root.addWidget(title_label)

        desc = CaptionLabel("请先选择左侧分组，再选择右侧条目。")
        desc.setWordWrap(True)
        root.addWidget(desc)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; }")
        root.addWidget(splitter, 1)

        left_card = CardFrame()
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)
        left_layout.addWidget(SectionHeader("分组", "按功能分类。"))
        self.group_list = ListWidget()
        self.group_list.setAlternatingRowColors(True)
        left_layout.addWidget(self.group_list, 1)

        right_card = CardFrame()
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8)
        right_layout.addWidget(SectionHeader("条目", "请选择要添加的条目。"))
        self.item_list = ListWidget()
        self.item_list.setAlternatingRowColors(True)
        right_layout.addWidget(self.item_list, 1)

        splitter.addWidget(left_card)
        splitter.addWidget(right_card)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)

        self.desc_card = CardFrame()
        self.desc_card.setMinimumHeight(120)
        self.desc_card.setMaximumHeight(260)

        desc_layout = QVBoxLayout(self.desc_card)
        desc_layout.setContentsMargins(12, 10, 12, 10)
        desc_layout.setSpacing(6)
        desc_layout.addWidget(SectionHeader("说明"))

        self.desc_scroll = SmoothScrollArea()
        self.desc_scroll.setWidgetResizable(True)
        self.desc_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.desc_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.desc_scroll.setMinimumHeight(80)
        self.desc_scroll.setMaximumHeight(210)
        self.desc_scroll.setStyleSheet(get_transparent_scroll_style("AutomationPickerDescScrollContent"))

        self.desc_scroll_content = QWidget()
        self.desc_scroll_content.setObjectName("AutomationPickerDescScrollContent")
        self.desc_scroll.setWidget(self.desc_scroll_content)

        desc_scroll_layout = QVBoxLayout(self.desc_scroll_content)
        desc_scroll_layout.setContentsMargins(0, 0, 8, 0)
        desc_scroll_layout.setSpacing(0)

        self.desc_label = BodyLabel("请选择一个条目后，这里会显示它的用途、参数说明和示例。")
        self.desc_label.setWordWrap(True)
        self.desc_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.desc_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.desc_label.setStyleSheet("background: transparent;")

        desc_scroll_layout.addWidget(self.desc_label)
        desc_scroll_layout.addStretch(1)

        desc_layout.addWidget(self.desc_scroll, 1)
        root.addWidget(self.desc_card, 0)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.ok_btn = PrimaryPushButton("确定")
        self.cancel_btn = PushButton("取消")
        self.ok_btn.setEnabled(False)
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

    def _update_style(self):
        if isDarkTheme():
            self.setStyleSheet("QDialog { background: #202020; } QLabel { color: white; }")
        else:
            self.setStyleSheet("QDialog { background: #f3f3f3; } QLabel { color: black; }")

    def _set_description_text(self, text: str) -> None:
        self.desc_label.setText(text)
        QTimer.singleShot(0, self._scroll_description_to_top)

    def _scroll_description_to_top(self) -> None:
        try:
            self.desc_scroll.verticalScrollBar().setValue(0)
        except Exception:
            pass

    def _on_group_changed(self, row: int) -> None:
        self.item_list.clear()
        self._set_description_text("请选择一个条目后，这里会显示它的用途、参数说明和示例。")
        self.ok_btn.setEnabled(False)

        if row < 0:
            return

        group_name = self.group_list.item(row).text()
        items = self._groups.get(group_name, [])

        for item_id, display_name in items:
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, item_id)

            desc = self._descriptions.get(item_id, "")
            if desc:
                item.setToolTip(f"{display_name}\n{item_id}\n\n{desc}")
            else:
                item.setToolTip(item_id)

            self.item_list.addItem(item)

        if self.item_list.count() > 0:
            self.item_list.setCurrentRow(0)

    def _on_item_changed(self, row: int) -> None:
        item = self.item_list.item(row)
        if item is None:
            self._set_description_text("请选择一个条目后，这里会显示它的用途、参数说明和示例。")
            self.ok_btn.setEnabled(False)
            return

        item_id = item.data(Qt.UserRole)
        desc = self._descriptions.get(item_id, "")

        if desc:
            self._set_description_text(f"{desc}\n\nID：{item_id}")
        else:
            self._set_description_text(f"ID：{item_id}")

        self.ok_btn.setEnabled(True)

    def _on_accept(self) -> None:
        item = self.item_list.currentItem()
        if item is None:
            return
        self.selected_id = item.data(Qt.UserRole)
        self.accept()


class AutomationSettingsPage(QWidget):
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

        QTimer.singleShot(0, self._apply_initial_sizes)
        qconfig.themeChanged.connect(self._apply_status_style)

    # =========================================================
    # MessageBox / Flyout helpers
    # =========================================================

    def _dialog_host(self) -> QWidget:
        host = self.window()
        return host if host is not None else self

    def _exec_dialog(self, dialog) -> int:
        if hasattr(dialog, "exec"):
            return dialog.exec()
        return dialog.exec_()

    def _show_info_dialog(self, title: str, content: str) -> None:
        w = MessageBox(title, content, self._dialog_host())
        w.yesButton.setText("知道了")
        w.cancelButton.hide()
        self._exec_dialog(w)

    def _show_error_dialog(self, title: str, content: str) -> None:
        w = MessageBox(title, content, self._dialog_host())
        w.yesButton.setText("知道了")
        w.cancelButton.hide()
        self._exec_dialog(w)

    def _ask_confirm(
            self,
            title: str,
            content: str,
            yes_text: str = "确定",
            cancel_text: str = "取消",
    ) -> bool:
        w = MessageBox(title, content, self._dialog_host())
        w.yesButton.setText(yes_text)
        w.cancelButton.setText(cancel_text)
        return bool(self._exec_dialog(w))

    def _show_tip_flyout(
            self,
            title: str,
            content: str,
            target: QWidget | None = None,
            icon=InfoBarIcon.INFORMATION,
    ) -> None:
        target = target or self.status_card
        try:
            Flyout.create(
                icon=icon,
                title=title,
                content=content,
                target=target,
                parent=self._dialog_host(),
                isClosable=True,
                aniType=FlyoutAnimationType.PULL_UP,
            )
        except Exception:
            self._set_status_info(f"{title}：{content}")

    # =========================================================
    # Main UI
    # =========================================================

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 0)
        root.setSpacing(18)

        self.title_label = TitleLabel("自动化")
        root.addWidget(self.title_label)

        self.subtitle_label = CaptionLabel('通过“触发器 + 条件 + 动作”的方式，让应用在不同场景下自动执行任务。')
        self.subtitle_label.setWordWrap(True)
        root.addWidget(self.subtitle_label)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)
        self.main_splitter.setStyleSheet("QSplitter::handle { background: transparent; }")
        self.main_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.main_splitter, 1)

        self.left_scroll = SmoothScrollArea()
        self.left_scroll.setStyleSheet(get_transparent_scroll_style("AutomationLeftScrollContent"))
        self.left_scroll.setWidgetResizable(True)
        self.main_splitter.addWidget(self.left_scroll)

        self.left_content = QWidget()
        self.left_content.setObjectName("AutomationLeftScrollContent")
        self.left_scroll.setWidget(self.left_content)

        left_layout = QVBoxLayout(self.left_content)
        left_layout.setContentsMargins(0, 0, 0, 24)
        left_layout.setSpacing(12)

        self.enable_card = CardFrame()
        enable_layout = QVBoxLayout(self.enable_card)
        enable_layout.setContentsMargins(16, 16, 16, 16)
        enable_layout.setSpacing(10)
        enable_layout.addWidget(
            SectionHeader("启用自动化", "关闭后，当前配置仍会保留，但自动化不会执行。")
        )

        enable_row = QHBoxLayout()
        self.enable_box = CheckBox("启用自动化")
        enable_row.addWidget(self.enable_box)
        enable_row.addStretch(1)
        enable_layout.addLayout(enable_row)

        self.enable_hint = CaptionLabel("建议只在你已经配置好至少一个工作流后再开启。")
        self.enable_hint.setWordWrap(True)
        enable_layout.addWidget(self.enable_hint)
        left_layout.addWidget(self.enable_card)

        self.config_card = CardFrame()
        config_layout = QVBoxLayout(self.config_card)
        config_layout.setContentsMargins(16, 16, 16, 16)
        config_layout.setSpacing(10)
        config_layout.addWidget(
            SectionHeader("配置文件", "不同配置文件可以存放不同的一组自动化方案。")
        )

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self.config_combo = ComboBox()
        self.config_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row1.addWidget(self.config_combo, 1)
        self.new_config_btn = PushButton("新建配置")
        self.delete_config_btn = PushButton("删除配置")
        row1.addWidget(self.new_config_btn)
        row1.addWidget(self.delete_config_btn)
        config_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        self.reload_btn = PushButton("重载")
        self.save_btn = PushButton("保存到文件")
        self.apply_btn = PrimaryPushButton("应用到运行时")
        row2.addWidget(self.reload_btn)
        row2.addWidget(self.save_btn)
        row2.addWidget(self.apply_btn)
        config_layout.addLayout(row2)

        self._set_responsive_button_widths(
            [
                self.new_config_btn,
                self.delete_config_btn,
                self.reload_btn,
                self.save_btn,
                self.apply_btn,
            ],
            108,
        )

        self.config_info_label = BodyLabel("")
        self.config_info_label.setWordWrap(True)
        config_layout.addWidget(self.config_info_label)

        left_layout.addWidget(self.config_card)

        self.status_card = CardFrame()
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(16, 12, 16, 12)
        status_layout.setSpacing(4)
        status_layout.addWidget(SectionHeader("当前状态"))
        self.status_label = BodyLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        status_layout.addWidget(self.status_label)
        left_layout.addWidget(self.status_card)

        self.property_card = CardFrame()
        property_layout = QVBoxLayout(self.property_card)
        property_layout.setContentsMargins(16, 16, 16, 16)
        property_layout.setSpacing(10)
        property_layout.addWidget(
            SectionHeader(
                "参数设置",
                "点击右侧的工作流、触发器、规则集、规则组、规则、动作后，这里会显示对应的详细参数。"
            )
        )
        self.property_editor = AutomationPropertyEditor()
        property_layout.addWidget(self.property_editor)
        left_layout.addWidget(self.property_card)

        left_layout.addStretch(1)

        self.right_scroll = SmoothScrollArea()
        self.right_scroll.setStyleSheet(get_transparent_scroll_style("AutomationRightScrollContent"))
        self.right_scroll.setWidgetResizable(True)
        self.main_splitter.addWidget(self.right_scroll)

        self.right_content = QWidget()
        self.right_content.setObjectName("AutomationRightScrollContent")
        self.right_scroll.setWidget(self.right_content)

        right_layout = QVBoxLayout(self.right_content)
        right_layout.setContentsMargins(0, 0, 0, 24)
        right_layout.setSpacing(12)

        self.workflow_card = CardFrame()
        workflow_layout = QVBoxLayout(self.workflow_card)
        workflow_layout.setContentsMargins(16, 16, 16, 16)
        workflow_layout.setSpacing(10)

        workflow_layout.addWidget(
            SectionHeader("工作流", "每个工作流都包含：触发器、可选条件、动作。")
        )

        top_btns = QHBoxLayout()
        top_btns.setSpacing(10)
        self.new_workflow_btn = PrimaryPushButton("新建工作流")
        self.delete_workflow_btn = PushButton("删除工作流")
        self.workflow_up_btn = PushButton("上移")
        self.workflow_down_btn = PushButton("下移")
        top_btns.addWidget(self.new_workflow_btn)
        top_btns.addWidget(self.delete_workflow_btn)
        top_btns.addWidget(self.workflow_up_btn)
        top_btns.addWidget(self.workflow_down_btn)
        workflow_layout.addLayout(top_btns)

        self._set_responsive_button_widths(
            [
                self.new_workflow_btn,
                self.delete_workflow_btn,
                self.workflow_up_btn,
                self.workflow_down_btn,
            ],
            102,
        )

        self.workflow_list = ListWidget()
        self.workflow_list.setAlternatingRowColors(True)
        self.workflow_list.setMinimumHeight(180)
        workflow_layout.addWidget(self.workflow_list)

        self.workflow_tip = CaptionLabel("先选中工作流，再在下面继续配置它的触发器、条件和动作。")
        self.workflow_tip.setWordWrap(True)
        workflow_layout.addWidget(self.workflow_tip)
        right_layout.addWidget(self.workflow_card)

        self.trigger_card = CardFrame()
        trigger_layout = QVBoxLayout(self.trigger_card)
        trigger_layout.setContentsMargins(16, 16, 16, 16)
        trigger_layout.setSpacing(10)
        trigger_layout.addWidget(SectionHeader("触发器", "决定工作流在什么时候开始执行。"))

        self.trigger_list = ListWidget()
        self.trigger_list.setAlternatingRowColors(True)
        self.trigger_list.setMinimumHeight(120)
        trigger_layout.addWidget(self.trigger_list)

        self.trigger_tip = CaptionLabel("常见示例：上课前提醒、Cron 定时执行、托盘菜单手动触发、应用内 URI 调用。")
        self.trigger_tip.setWordWrap(True)
        trigger_layout.addWidget(self.trigger_tip)

        trigger_btns = QHBoxLayout()
        trigger_btns.setSpacing(10)
        self.add_trigger_btn = PushButton("添加触发器")
        self.del_trigger_btn = PushButton("删除触发器")
        self.trigger_up_btn = PushButton("上移")
        self.trigger_down_btn = PushButton("下移")
        trigger_btns.addWidget(self.add_trigger_btn)
        trigger_btns.addWidget(self.del_trigger_btn)
        trigger_btns.addWidget(self.trigger_up_btn)
        trigger_btns.addWidget(self.trigger_down_btn)
        trigger_layout.addLayout(trigger_btns)

        self._set_responsive_button_widths(
            [
                self.add_trigger_btn,
                self.del_trigger_btn,
                self.trigger_up_btn,
                self.trigger_down_btn,
            ],
            102,
        )

        right_layout.addWidget(self.trigger_card)

        self.rules_card = CardFrame()
        rules_layout = QVBoxLayout(self.rules_card)
        rules_layout.setContentsMargins(16, 16, 16, 16)
        rules_layout.setSpacing(10)
        rules_layout.addWidget(
            SectionHeader("条件 / 规则集", "用于进一步限制工作流是否执行；初学者可以先不启用。")
        )
        self.rules_editor = RulesetEditor()
        rules_layout.addWidget(self.rules_editor)
        right_layout.addWidget(self.rules_card)

        self.action_card = CardFrame()
        action_layout = QVBoxLayout(self.action_card)
        action_layout.setContentsMargins(16, 16, 16, 16)
        action_layout.setSpacing(10)
        action_layout.addWidget(SectionHeader("动作", "触发器满足后，会按顺序执行这些动作。"))

        self.action_list = ListWidget()
        self.action_list.setAlternatingRowColors(True)
        self.action_list.setMinimumHeight(120)
        action_layout.addWidget(self.action_list)

        self.action_tip = CaptionLabel("常见示例：显示提醒、运行程序、等待时长、广播信号。")
        self.action_tip.setWordWrap(True)
        action_layout.addWidget(self.action_tip)

        action_btns = QHBoxLayout()
        action_btns.setSpacing(10)
        self.add_action_btn = PushButton("添加动作")
        self.del_action_btn = PushButton("删除动作")
        self.action_up_btn = PushButton("上移")
        self.action_down_btn = PushButton("下移")
        action_btns.addWidget(self.add_action_btn)
        action_btns.addWidget(self.del_action_btn)
        action_btns.addWidget(self.action_up_btn)
        action_btns.addWidget(self.action_down_btn)
        action_layout.addLayout(action_btns)

        self._set_responsive_button_widths(
            [
                self.add_action_btn,
                self.del_action_btn,
                self.action_up_btn,
                self.action_down_btn,
            ],
            102,
        )

        action_test_btns = QHBoxLayout()
        action_test_btns.setSpacing(10)
        self.test_action_invoke_btn = PrimaryPushButton("测试触发")
        self.test_action_revert_btn = PushButton("测试恢复")

        self.test_action_invoke_btn.setToolTip("立即执行当前工作流的动作，用于测试触发效果。")
        self.test_action_revert_btn.setToolTip("立即执行当前工作流的恢复流程，用于测试恢复效果。")

        action_test_btns.addWidget(self.test_action_invoke_btn)
        action_test_btns.addWidget(self.test_action_revert_btn)
        action_test_btns.addStretch(1)
        action_layout.addLayout(action_test_btns)

        self._set_responsive_button_widths(
            [
                self.test_action_invoke_btn,
                self.test_action_revert_btn,
            ],
            112,
        )

        self.action_test_tip = CaptionLabel(
            "测试会立即在当前会话执行当前工作流的动作；会绕过触发器和条件。"
            "如果动作中包含运行程序、修改设置、退出或重启，它们都会真实执行。"
        )
        self.action_test_tip.setWordWrap(True)
        action_layout.addWidget(self.action_test_tip)

        right_layout.addWidget(self.action_card)
        right_layout.addStretch(1)

    def _set_responsive_button_widths(self, buttons: list[QWidget], min_width: int) -> None:
        for btn in buttons:
            try:
                btn.setMinimumWidth(min_width)
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            except Exception:
                pass

    def _apply_initial_sizes(self) -> None:
        total = max(self.width(), 1280)
        left = int(total * 0.40)
        left = max(380, min(left, 560))
        right = max(520, total - left - 24)
        self.main_splitter.setSizes([left, right])

    # =========================================================
    # Status
    # =========================================================

    def _set_status_style(self, type_: str) -> None:
        self._current_status_type = type_
        self._apply_status_style()

    def _apply_status_style(self) -> None:
        is_dark = isDarkTheme()
        type_ = getattr(self, "_current_status_type", "normal")

        if type_ == "saved":
            fg = "#ffcc00" if is_dark else "#8a5a00"
            bg = "rgba(255, 170, 0, 0.12)" if is_dark else "rgba(255, 170, 0, 0.10)"
        elif type_ == "applied":
            fg = "#66ff66" if is_dark else "#1e6b34"
            bg = "rgba(46, 204, 113, 0.12)" if is_dark else "rgba(46, 204, 113, 0.10)"
        elif type_ == "error":
            fg = "#ff8080" if is_dark else "#8b1e1e"
            bg = "rgba(255, 0, 0, 0.20)" if is_dark else "rgba(255, 0, 0, 0.08)"
        else:  # info
            fg = "#66ccff" if is_dark else "#1f4e79"
            bg = "rgba(0, 120, 215, 0.12)" if is_dark else "rgba(0, 120, 215, 0.08)"

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
        self._set_status_style("info")

    def _set_status_saved(self, text: str | None = None) -> None:
        if text is None:
            if self.controller.has_live_runtime():
                text = "已保存到文件，尚未应用到当前运行时。点击“应用到运行时”后，当前会话将被当前配置文件整体替换。"
            else:
                text = "已保存到文件。"
        self.status_label.setText(text)
        self._set_status_style("saved")

    def _set_status_applied(self, text: str | None = None) -> None:
        if text is None:
            text = "已应用到当前运行时。"
        self.status_label.setText(text)
        self._set_status_style("applied")

    def _set_status_error(self, text: str) -> None:
        self.status_label.setText(text)
        self._set_status_style("error")

    def _build_idle_status_text(self) -> str:
        name = self.controller.get_current_config_name()
        wf_count = len(self.controller.workflows)
        if self.controller.has_live_runtime():
            return f"当前正在编辑配置：{name}（{wf_count} 个工作流）。修改后请先保存，若要影响当前会话，请点击“应用到运行时”。"
        return f"当前正在编辑配置：{name}（{wf_count} 个工作流）。仅文件编辑模式。"

    def _update_config_info(self) -> None:
        name = self.controller.get_current_config_name()
        wf_count = len(self.controller.workflows)
        runtime_text = "已连接当前运行时" if self.controller.has_live_runtime() else "仅文件模式"
        self.config_info_label.setText(
            f"当前配置：{name}    ·    工作流数量：{wf_count}    ·    {runtime_text}"
        )

    # =========================================================
    # Signals
    # =========================================================

    def _connect_signals(self) -> None:
        self.enable_box.stateChanged.connect(self._on_enable_changed)
        self.config_combo.currentIndexChanged.connect(self._on_config_combo_changed)

        self.new_config_btn.clicked.connect(self._on_new_config)
        self.delete_config_btn.clicked.connect(self._on_delete_config)

        self.reload_btn.clicked.connect(self._on_reload)
        self.save_btn.clicked.connect(self._on_save)
        self.apply_btn.clicked.connect(self._on_apply)

        self.new_workflow_btn.clicked.connect(self._on_new_workflow)
        self.delete_workflow_btn.clicked.connect(self._on_delete_workflow)
        self.workflow_up_btn.clicked.connect(self._on_workflow_up)
        self.workflow_down_btn.clicked.connect(self._on_workflow_down)

        self.workflow_list.currentRowChanged.connect(self._on_workflow_selection_changed)

        self.add_trigger_btn.clicked.connect(self._on_add_trigger)
        self.del_trigger_btn.clicked.connect(self._on_delete_trigger)
        self.trigger_up_btn.clicked.connect(self._on_trigger_up)
        self.trigger_down_btn.clicked.connect(self._on_trigger_down)

        self.trigger_list.currentRowChanged.connect(self._on_trigger_selection_changed)

        self.add_action_btn.clicked.connect(self._on_add_action)
        self.del_action_btn.clicked.connect(self._on_delete_action)
        self.action_up_btn.clicked.connect(self._on_action_up)
        self.action_down_btn.clicked.connect(self._on_action_down)

        self.action_list.currentRowChanged.connect(self._on_action_selection_changed)

        self.test_action_invoke_btn.clicked.connect(self._on_test_invoke_actions)
        self.test_action_revert_btn.clicked.connect(self._on_test_revert_actions)

        self.property_editor.changed.connect(self._on_property_changed)

        self.rules_editor.rule_selection_changed.connect(self._on_rule_selection_changed)
        self.rules_editor.data_changed.connect(self._on_ruleset_changed)

    # =========================================================
    # Current helpers
    # =========================================================

    def _update_action_test_buttons(self) -> None:
        workflow = self._get_current_workflow()
        has_actions = (
                workflow is not None
                and workflow.ActionSet is not None
                and bool(workflow.ActionSet.Actions)
        )

        try:
            can_test_runtime = self.controller.can_test_actions()
        except Exception:
            can_test_runtime = False

        can_test = bool(has_actions and can_test_runtime)

        self.test_action_invoke_btn.setEnabled(can_test)
        self.test_action_revert_btn.setEnabled(can_test)

        if not can_test_runtime:
            tip = "当前没有连接到运行中的自动化服务，无法测试动作。"
        elif not has_actions:
            tip = "请先选择一个包含动作的工作流。"
        else:
            tip = "会立即在当前会话执行动作，请谨慎测试。"

        self.test_action_invoke_btn.setToolTip(tip)
        self.test_action_revert_btn.setToolTip(tip)

    def _get_current_workflow(self) -> Any | None:
        if 0 <= self._current_workflow_index < len(self.controller.workflows):
            return self.controller.workflows[self._current_workflow_index]
        return None

    def _get_current_trigger(self) -> Any | None:
        wf = self._get_current_workflow()
        if wf and 0 <= self._current_trigger_index < len(wf.Triggers):
            return wf.Triggers[self._current_trigger_index]
        return None

    def _get_current_action(self) -> Any | None:
        wf = self._get_current_workflow()
        if wf and 0 <= self._current_action_index < len(wf.ActionSet.Actions):
            return wf.ActionSet.Actions[self._current_action_index]
        return None

    # =========================================================
    # Global Config
    # =========================================================

    def _reload_all(self) -> None:
        self.enable_box.blockSignals(True)
        self.enable_box.setChecked(self.controller.is_automation_enabled())
        self.enable_box.blockSignals(False)

        self.config_combo.blockSignals(True)
        self.config_combo.clear()
        configs = self.controller.list_configs()
        current = self.controller.get_current_config_name()

        for c in configs:
            self.config_combo.addItem(c)

        idx = self.config_combo.findText(current)
        if idx >= 0:
            self.config_combo.setCurrentIndex(idx)
        self.config_combo.blockSignals(False)

        self._reload_workflows()

    def _on_enable_changed(self) -> None:
        is_enabled = self.enable_box.isChecked()
        self.controller.set_automation_enabled(is_enabled)
        self._set_status_saved(f"自动化已{'启用' if is_enabled else '禁用'}，记得保存并应用。")

    def _on_config_combo_changed(self, idx: int) -> None:
        if idx < 0:
            return
        name = self.config_combo.itemText(idx)
        try:
            # 修复：正确调用 controller 的切换配置接口
            self.controller.set_current_config_name(name)
            self.controller.load_current()

            self._current_workflow_index = -1
            self._current_trigger_index = -1
            self._current_action_index = -1
            self._reload_all()
            self._set_status_info(self._build_idle_status_text())
        except Exception as e:
            self._set_status_error(f"切换配置失败：{e}")
            self._show_error_dialog("自动化", f"切换配置失败：\n{e}")

    def _on_new_config(self) -> None:
        try:
            def _validator(text: str):
                invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
                if any(ch in text for ch in invalid_chars):
                    return False, "名称包含非法字符。"
                if text in self.controller.list_configs():
                    return False, "这个配置名已经存在。"
                return True, "可以使用。"

            dlg = AutomationTextFieldDialog(
                self._dialog_host(),
                title="新建配置",
                text="请输入新的自动化配置名称。",
                placeholder="例如：我的配置",
                validator=_validator,
            )

            if self._exec_dialog(dlg) != QDialog.Accepted:
                return

            created = self.controller.create_config(dlg.text())
            self._reload_all()

            idx = self.config_combo.findText(created)
            if idx >= 0:
                self.config_combo.setCurrentIndex(idx)

            self._set_status_saved(f"已新建配置：{created}。当前正在编辑新配置文件。")
            self._show_tip_flyout(
                "新建配置成功",
                f"已创建自动化配置“{created}”。",
                self.new_config_btn,
                InfoBarIcon.SUCCESS,
            )

        except Exception as e:
            self._set_status_error(f"新建配置失败：{e}")
            self._show_error_dialog("自动化", f"新建配置失败：\n{e}")

    def _on_delete_config(self) -> None:
        try:
            current = self.controller.get_current_config_name()
            if not self._ask_confirm(
                    "删除配置",
                    f"确定要删除配置文件“{current}”吗？\n删除后将不可恢复！",
            ):
                return

            if self.controller.delete_config(current):
                self._reload_all()
                self._set_status_saved(f"已删除配置：{current}。")
            else:
                self._show_error_dialog("自动化", "无法删除，这可能是最后一个配置文件。")

        except Exception as e:
            self._set_status_error(f"删除配置失败：{e}")
            self._show_error_dialog("自动化", f"删除配置失败：\n{e}")

    def _on_reload(self) -> None:
        try:
            self.controller.load_current()
            self._reload_all()
            self._set_status_info("已重新加载当前文件配置。")
        except Exception as e:
            self._set_status_error(f"重载配置失败：{e}")
            self._show_error_dialog("自动化", f"重载配置失败：\n{e}")

    def _on_save(self) -> None:
        try:
            self.controller.save_current()
            self._set_status_saved()
            self._update_config_info()
            self._show_tip_flyout(
                "保存成功",
                "自动化配置已保存到文件。",
                self.save_btn,
                InfoBarIcon.SUCCESS,
            )
        except Exception as e:
            self._set_status_error(f"保存配置失败：{e}")
            self._show_error_dialog("自动化", f"保存配置失败：\n{e}")

    def _on_apply(self) -> None:
        try:
            config_name = self.controller.get_current_config_name()
            wf_count = len(self.controller.workflows)
            if self.controller.has_live_runtime():
                if not self._ask_confirm(
                        "保存并应用到运行时",
                        f"将自动保存当前配置，并使用“{config_name}”中的 {wf_count} 个工作流替换当前运行时。\n\n"
                        "这不会合并旧工作流，而是整体重载。\n\n"
                        "是否继续？",
                        yes_text="保存并应用",
                        cancel_text="取消",
                ):
                    return
            # 先确保强行同步内存到文件
            self.controller.save_current()

            # 再调用应用方法（底层也会再保存一次以防万一）
            applied = self.controller.apply_current()
            self._update_config_info()
            # 获取真实写入的文件名和路径
            save_path = self.controller.get_current_config_path().absolute()
            if applied:
                self._set_status_applied(
                    f"已保存到文件并应用：{config_name}（{wf_count} 个工作流）。"
                )
                # 使用最稳的 InfoDialog 直接居中弹窗汇报结果！
                self._show_info_dialog(
                    "保存并应用成功",
                    f"配置已实际写入此路径：\n\n{save_path}\n\n并且当前会话已重载生效。"
                )
            else:
                self._set_status_saved("当前没有可应用的运行时，已仅保存到文件。")
                self._show_info_dialog(
                    "仅保存到文件",
                    f"当前没有可应用的运行时，配置已写入此路径：\n\n{save_path}"
                )
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._set_status_error(f"应用到运行时失败：{e}")
            self._show_error_dialog("自动化", f"应用到运行时发生异常：\n{e}")

    # =========================================================
    # Workflows List
    # =========================================================

    def _reload_workflows(self) -> None:
        self.workflow_list.clear()

        for workflow in self.controller.workflows:
            self.workflow_list.addItem(
                QListWidgetItem(self.controller.workflow_display_text(workflow))
            )

        if self.controller.workflows:
            if self._current_workflow_index < 0:
                self._current_workflow_index = 0

            self._current_workflow_index = min(
                self._current_workflow_index,
                len(self.controller.workflows) - 1,
            )
            self.workflow_list.setCurrentRow(self._current_workflow_index)
        else:
            self._current_workflow_index = -1
            self._current_trigger_index = -1
            self._current_action_index = -1

            self.trigger_list.clear()
            self.action_list.clear()
            self.rules_editor.set_workflow(None)
            self.property_editor.set_target(None, None)

        self._update_config_info()
        self._update_action_test_buttons()

    def _on_workflow_selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self.controller.workflows):
            return

        self._current_workflow_index = row
        self._current_trigger_index = -1
        self._current_action_index = -1
        self._reload_middle()

    def _reload_middle(self) -> None:
        self.trigger_list.clear()
        self.action_list.clear()

        workflow = self._get_current_workflow()
        if workflow is None:
            self.rules_editor.set_workflow(None)
            self.property_editor.set_target(None, None)
            self._update_config_info()
            self._update_action_test_buttons()
            return

        # 增加强力容错：防止外部 JSON 文件里的字段被错误写成了 null
        triggers = getattr(workflow, "Triggers", []) or []
        for trigger in triggers:
            self.trigger_list.addItem(
                QListWidgetItem(self.controller.trigger_display_text(trigger))
            )

        action_set = getattr(workflow, "ActionSet", None)
        actions = getattr(action_set, "Actions", []) if action_set else []
        for action in (actions or []):
            self.action_list.addItem(
                QListWidgetItem(self.controller.action_display_text(action))
            )

        self.rules_editor.set_workflow(workflow)

        if self._current_trigger_index >= 0:
            self.property_editor.set_target("trigger", self._get_current_trigger())
        elif self._current_action_index >= 0:
            self.property_editor.set_target("action", self._get_current_action())
        else:
            self.property_editor.set_target("workflow", workflow)

        self._update_config_info()
        self._update_action_test_buttons()

    def _on_new_workflow(self) -> None:
        self.controller.add_workflow()
        self._current_workflow_index = len(self.controller.workflows) - 1
        self._reload_workflows()
        self._set_status_saved("已添加新工作流。")

    def _on_delete_workflow(self) -> None:
        if self._current_workflow_index < 0:
            return

        if not self._ask_confirm("删除工作流", "确定要删除当前选中的工作流吗？"):
            return

        self.controller.delete_workflow(self._current_workflow_index)
        self._reload_workflows()
        self._set_status_saved("已删除工作流。")

    def _on_workflow_up(self) -> None:
        if self.controller.move_workflow_up(self._current_workflow_index):
            self._current_workflow_index -= 1
            self._reload_workflows()
            self._set_status_saved()

    def _on_workflow_down(self) -> None:
        if self.controller.move_workflow_down(self._current_workflow_index):
            self._current_workflow_index += 1
            self._reload_workflows()
            self._set_status_saved()

    # =========================================================
    # Triggers List
    # =========================================================

    def _on_trigger_selection_changed(self, row: int) -> None:
        if row < 0:
            return
        self._current_trigger_index = row

        self.action_list.blockSignals(True)
        self.action_list.clearSelection()
        self._current_action_index = -1
        self.action_list.blockSignals(False)

        self.rules_editor.clear_selection()
        self.property_editor.set_target("trigger", self._get_current_trigger())

    def _on_add_trigger(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return

            # 强力自我修复：如果底层因为坏 JSON 变成了 None，强行重置为正确列表
            if getattr(workflow, "Triggers", None) is None:
                workflow.Triggers = []

            dlg = GroupedPickerDialog(
                "选择触发器",
                self.controller.available_trigger_groups(),
                TRIGGER_DESCRIPTIONS,
                self._dialog_host(),
            )

            if self._exec_dialog(dlg) == QDialog.Accepted and dlg.selected_id:
                self.controller.add_trigger(workflow, dlg.selected_id)
                self._current_trigger_index = len(workflow.Triggers) - 1
                self._reload_middle()
                self.trigger_list.setCurrentRow(self._current_trigger_index)
                self._set_status_saved("已添加触发器。")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._show_error_dialog("添加失败", f"添加触发器异常，已记录到后台：\n{e}")

    def _on_add_action(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return

            # 强力自我修复：如果底层 ActionSet 坏了，强行重建
            if getattr(workflow, "ActionSet", None) is None:
                from automation.models import ActionSet
                import uuid
                workflow.ActionSet = ActionSet(Guid=str(uuid.uuid4()), Name="新工作流")

            if getattr(workflow.ActionSet, "Actions", None) is None:
                workflow.ActionSet.Actions = []

            dlg = GroupedPickerDialog(
                "选择动作",
                self.controller.available_action_groups(),
                ACTION_DESCRIPTIONS,
                self._dialog_host(),
            )

            if self._exec_dialog(dlg) == QDialog.Accepted and dlg.selected_id:
                self.controller.add_action(workflow, dlg.selected_id)
                self._current_action_index = len(workflow.ActionSet.Actions) - 1
                self._reload_middle()
                self.action_list.setCurrentRow(self._current_action_index)
                self._set_status_saved("已添加动作。")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._show_error_dialog("添加失败", f"添加动作异常，已记录到后台：\n{e}")

    def _on_delete_trigger(self) -> None:
        workflow = self._get_current_workflow()
        if workflow is None or self._current_trigger_index < 0:
            return

        if not self._ask_confirm("删除触发器", "确定要删除当前选中的触发器吗？"):
            return

        self.controller.delete_trigger(workflow, self._current_trigger_index)
        self._current_trigger_index = -1
        self._reload_middle()
        self._set_status_saved("已删除触发器。")

    def _on_trigger_up(self) -> None:
        workflow = self._get_current_workflow()
        if workflow and self.controller.move_trigger_up(workflow, self._current_trigger_index):
            self._current_trigger_index -= 1
            self._reload_middle()
            self.trigger_list.setCurrentRow(self._current_trigger_index)
            self._set_status_saved()

    def _on_trigger_down(self) -> None:
        workflow = self._get_current_workflow()
        if workflow and self.controller.move_trigger_down(workflow, self._current_trigger_index):
            self._current_trigger_index += 1
            self._reload_middle()
            self.trigger_list.setCurrentRow(self._current_trigger_index)
            self._set_status_saved()

    # =========================================================
    # Actions List
    # =========================================================

    def _on_action_selection_changed(self, row: int) -> None:
        if row < 0:
            return
        self._current_action_index = row

        self.trigger_list.blockSignals(True)
        self.trigger_list.clearSelection()
        self._current_trigger_index = -1
        self.trigger_list.blockSignals(False)

        self.rules_editor.clear_selection()
        self.property_editor.set_target("action", self._get_current_action())

    def _on_add_action(self) -> None:
        workflow = self._get_current_workflow()
        if workflow is None:
            return

        dlg = GroupedPickerDialog(
            "选择动作",
            self.controller.available_action_groups(),  # 这里加上了 _groups
            ACTION_DESCRIPTIONS,
            self._dialog_host(),
        )

        if self._exec_dialog(dlg) == QDialog.Accepted and dlg.selected_id:
            self.controller.add_action(workflow, dlg.selected_id)
            self._current_action_index = len(workflow.ActionSet.Actions) - 1
            self._reload_middle()
            self.action_list.setCurrentRow(self._current_action_index)
            self._set_status_saved("已添加动作。")

    def _on_delete_action(self) -> None:
        workflow = self._get_current_workflow()
        if workflow is None or self._current_action_index < 0:
            return

        if not self._ask_confirm("删除动作", "确定要删除当前选中的动作吗？"):
            return

        self.controller.delete_action(workflow, self._current_action_index)
        self._current_action_index = -1
        self._reload_middle()
        self._set_status_saved("已删除动作。")

    def _on_action_up(self) -> None:
        workflow = self._get_current_workflow()
        if workflow and self.controller.move_action_up(workflow, self._current_action_index):
            self._current_action_index -= 1
            self._reload_middle()
            self.action_list.setCurrentRow(self._current_action_index)
            self._set_status_saved()

    def _on_action_down(self) -> None:
        workflow = self._get_current_workflow()
        if workflow and self.controller.move_action_down(workflow, self._current_action_index):
            self._current_action_index += 1
            self._reload_middle()
            self.action_list.setCurrentRow(self._current_action_index)
            self._set_status_saved()

    def _on_test_invoke_actions(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                self._show_tip_flyout(
                    "无法测试",
                    "请先选择一个工作流。",
                    self.test_action_invoke_btn,
                    InfoBarIcon.WARNING,
                )
                return

            action_count = len(workflow.ActionSet.Actions)
            if action_count <= 0:
                self._show_tip_flyout(
                    "无法测试",
                    "当前工作流没有动作，请先添加至少一个动作。",
                    self.test_action_invoke_btn,
                    InfoBarIcon.WARNING,
                )
                return

            workflow_name = workflow.ActionSet.Name or "未命名工作流"

            if not self._ask_confirm(
                    "测试触发动作",
                    f"将立即在当前会话执行工作流“{workflow_name}”中的 {action_count} 个动作。\n\n"
                    "这会绕过触发器和条件，仅用于测试动作效果。\n\n"
                    "注意：如果动作中包含运行程序、修改设置、退出或重启应用，它们都会真实执行。\n\n"
                    "是否继续？",
                    yes_text="立即测试",
                    cancel_text="取消",
            ):
                return

            self.controller.save_current()
            self.controller.test_invoke_workflow(workflow)

            self._set_status_info(
                f"已开始测试触发：{workflow_name}（{action_count} 个动作）。"
            )
            self._show_tip_flyout(
                "测试已开始",
                f"正在执行“{workflow_name}”的动作。",
                self.test_action_invoke_btn,
                InfoBarIcon.INFORMATION,
            )

        except Exception as e:
            self._set_status_error(f"测试触发失败：{e}")
            self._show_error_dialog("自动化", f"测试触发失败：\n{e}")

    def _on_test_revert_actions(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                self._show_tip_flyout(
                    "无法测试恢复",
                    "请先选择一个工作流。",
                    self.test_action_revert_btn,
                    InfoBarIcon.WARNING,
                )
                return

            action_count = len(workflow.ActionSet.Actions)
            if action_count <= 0:
                self._show_tip_flyout(
                    "无法测试恢复",
                    "当前工作流没有动作，请先添加至少一个动作。",
                    self.test_action_revert_btn,
                    InfoBarIcon.WARNING,
                )
                return

            workflow_name = workflow.ActionSet.Name or "未命名工作流"

            if not self._ask_confirm(
                    "测试恢复动作",
                    f"将立即在当前会话执行工作流“{workflow_name}”的恢复流程。\n\n"
                    "这会绕过触发器和条件，仅用于测试动作恢复效果。\n\n"
                    "只有支持恢复的动作会真正执行恢复逻辑；如果之前没有执行过测试触发，部分动作可能不会产生明显效果。\n\n"
                    "是否继续？",
                    yes_text="立即恢复",
                    cancel_text="取消",
            ):
                return

            self.controller.save_current()
            self.controller.test_revert_workflow(workflow)

            self._set_status_info(
                f"已开始测试恢复：{workflow_name}。"
            )
            self._show_tip_flyout(
                "恢复测试已开始",
                f"正在执行“{workflow_name}”的恢复流程。",
                self.test_action_revert_btn,
                InfoBarIcon.INFORMATION,
            )

        except Exception as e:
            self._set_status_error(f"测试恢复失败：{e}")
            self._show_error_dialog("自动化", f"测试恢复失败：\n{e}")

    # =========================================================
    # Property / Ruleset changes
    # =========================================================

    def _on_property_changed(self) -> None:
        self._set_status_saved()
        if self._current_workflow_index >= 0:
            workflow = self.controller.workflows[self._current_workflow_index]
            self.workflow_list.item(self._current_workflow_index).setText(
                self.controller.workflow_display_text(workflow)
            )

        if self._current_trigger_index >= 0:
            trigger = self._get_current_trigger()
            if trigger:
                self.trigger_list.item(self._current_trigger_index).setText(
                    self.controller.trigger_display_text(trigger)
                )

        if self._current_action_index >= 0:
            action = self._get_current_action()
            if action:
                self.action_list.item(self._current_action_index).setText(
                    self.controller.action_display_text(action)
                )

    def _on_rule_selection_changed(self, kind: str, target: Any) -> None:
        self.trigger_list.blockSignals(True)
        self.trigger_list.clearSelection()
        self._current_trigger_index = -1
        self.trigger_list.blockSignals(False)

        self.action_list.blockSignals(True)
        self.action_list.clearSelection()
        self._current_action_index = -1
        self.action_list.blockSignals(False)

        self.property_editor.set_target(kind, target)

    def _on_ruleset_changed(self) -> None:
        self._set_status_saved()
