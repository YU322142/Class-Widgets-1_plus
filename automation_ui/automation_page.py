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
)


from .controller import AutomationUiController
from .property_editor import AutomationPropertyEditor
from .ruleset_editor import RulesetEditor


TRIGGER_DESCRIPTIONS: dict[str, str] = {
    "classisland.lifetime.startup": "在应用启动时触发。适合显示启动提示、初始化某些动作。",
    "classisland.lifetime.stopping": "在应用退出时触发。适合保存状态、发送退出通知。",
    "classisland.lessons.currentTimeStateChanged": "当当前时间状态发生变化时触发，如上课、课间、放学。",
    "classisland.lessons.onClass": "进入上课状态时触发。",
    "classisland.lessons.onBreakingTime": "进入课间休息时触发。",
    "classisland.lessons.onAfterSchool": "当天课程结束时触发。",
    "classisland.lessons.preTimePoint": "在指定状态开始前若干秒触发，例如上课前 60 秒。",
    "classisland.cron": "按照 cron 表达式定时触发。适合周期性任务。",
    "classisland.signal": "收到应用内信号时触发。适合动作之间联动。",
    "classisland.uri": "调用指定 URI 时触发。适合外部调用或快捷链接。",
    "classisland.trayMenu": "从托盘菜单点击时触发。适合手动测试或快捷执行。",
    "classisland.ruleSet.rulesetChanged": "当规则集状态更新时触发。",
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


def _scroll_style() -> str:
    return """
    SmoothScrollArea, QAbstractScrollArea {
        background: transparent;
        border: none;
    }
    QWidget#AutomationLeftScrollContent,
    QWidget#AutomationRightScrollContent {
        background: transparent;
    }

    QScrollBar:vertical {
        background: transparent;
        width: 10px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: rgba(0, 0, 0, 0.16);
        min-height: 30px;
        border-radius: 5px;
    }
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0px;
        background: transparent;
        border: none;
    }
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {
        background: transparent;
    }

    QScrollBar:horizontal {
        background: transparent;
        height: 10px;
        margin: 0px;
    }
    QScrollBar::handle:horizontal {
        background: rgba(0, 0, 0, 0.16);
        min-width: 30px;
        border-radius: 5px;
    }
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {
        width: 0px;
        background: transparent;
        border: none;
    }
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {
        background: transparent;
    }
    """


class CardFrame(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AutomationCardFrame")
        self.setStyleSheet(
            """
            QFrame#AutomationCardFrame {
                background: rgba(255, 255, 255, 0.82);
                border: 1px solid rgba(0, 0, 0, 0.035);
                border-radius: 12px;
            }
            """
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)


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
        self.desc_label.setStyleSheet("color: #666;")
        self.desc_label.setVisible(bool(desc))
        layout.addWidget(self.desc_label)


class AutomationTextFieldDialog(MessageBoxBase):
    """
    自动化配置名输入框。

    注意：
    - 这里必须继承 MessageBoxBase，而不是 Dialog。
    - parent 需要传完整 SettingsMenu，即 AutomationSettingsPage.window()。
    - 这样遮罩、弹出动效、暗色背景才和设置页其它 MessageBox 一致。
    """

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
        self.tipLabel.setStyleSheet("color: #666;")

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.contentLabel)
        self.viewLayout.addWidget(self.textField)
        self.viewLayout.addWidget(self.tipLabel)

        # 尺寸参考 menu.py 里的 CustomMessageBox，不要做特殊居中/特殊动效。
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
        text = (text or "").strip()

        if not text:
            self.tipLabel.setStyleSheet("color: #c42b1c;")
            self.tipLabel.setText("名称不能为空。")
            self.yesButton.setEnabled(False)
            return

        if self._validator is not None:
            ok, message = self._validator(text)
            if not ok:
                self.tipLabel.setStyleSheet("color: #c42b1c;")
                self.tipLabel.setText(message)
                self.yesButton.setEnabled(False)
                return

        self.tipLabel.setStyleSheet("color: #0f7b0f;")
        self.tipLabel.setText("可以使用这个名称。")
        self.yesButton.setEnabled(True)

    def text(self) -> str:
        return self.textField.text().strip()


class AutomationTextFieldDialog(MessageBoxBase):
    """
    自动化配置名输入框。

    注意：
    - 这里必须继承 MessageBoxBase，而不是 Dialog。
    - parent 需要传完整 SettingsMenu，即 AutomationSettingsPage.window()。
    - 这样遮罩、弹出动效、暗色背景才和设置页其它 MessageBox 一致。
    """

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
        self.tipLabel.setStyleSheet("color: #666;")

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.contentLabel)
        self.viewLayout.addWidget(self.textField)
        self.viewLayout.addWidget(self.tipLabel)

        # 尺寸参考 menu.py 里的 CustomMessageBox，不要做特殊居中/特殊动效。
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
        text = (text or "").strip()

        if not text:
            self.tipLabel.setStyleSheet("color: #c42b1c;")
            self.tipLabel.setText("名称不能为空。")
            self.yesButton.setEnabled(False)
            return

        if self._validator is not None:
            ok, message = self._validator(text)
            if not ok:
                self.tipLabel.setStyleSheet("color: #c42b1c;")
                self.tipLabel.setText(message)
                self.yesButton.setEnabled(False)
                return

        self.tipLabel.setStyleSheet("color: #0f7b0f;")
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
        desc.setStyleSheet("color: #666;")
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

    def _on_group_changed(self, row: int) -> None:
        self.item_list.clear()
        self.desc_label.setText("请选择一个条目后，这里会显示它的用途。")
        self.ok_btn.setEnabled(False)

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
            self.ok_btn.setEnabled(False)
            return

        item_id = item.data(Qt.UserRole)
        desc = self._descriptions.get(item_id, f"ID: {item_id}")
        self.desc_label.setText(desc)
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

    # =========================================================
    # MessageBox / Flyout helpers
    # =========================================================

    def _dialog_host(self) -> QWidget:
        """
        自动化页是 SettingsMenu 内部的一个子页面。

        普通设置页里调用 MessageBox 时，parent 通常是 SettingsMenu 自己；
        但这里的 self 是 AutomationSettingsPage。
        如果 parent 传 self，黑色遮罩和弹出动效只会覆盖自动化子页，
        视觉上就和其它设置页不一致。

        所以这里统一返回完整设置窗口 self.window()。
        """
        host = self.window()
        return host if host is not None else self

    def _center_window_dialog(self, dialog: QWidget) -> None:
        """
        只给普通 QDialog 使用，例如添加触发器/动作的选择器。

        MessageBox / MessageBoxBase 不要手动居中。
        它们要使用 qfluentwidgets 自带的遮罩和动画。
        """
        host = self._dialog_host()

        try:
            dialog.adjustSize()
        except Exception:
            pass

        try:
            host_geo = host.frameGeometry() if host.isWindow() else host.geometry()
            geo = dialog.frameGeometry()
            geo.moveCenter(host_geo.center())
            dialog.move(geo.topLeft())
        except Exception:
            pass

    def _exec_dialog(self, dialog) -> int:
        if hasattr(dialog, "exec"):
            return dialog.exec()
        return dialog.exec_()

    def _show_info_dialog(self, title: str, content: str) -> None:
        """
        和设置页“什么是灵活隐藏？”保持同款 MessageBox 效果。
        """
        w = MessageBox(title, content, self._dialog_host())
        w.yesButton.setText("知道了")
        w.cancelButton.hide()
        self._exec_dialog(w)

    def _show_error_dialog(self, title: str, content: str) -> None:
        """
        错误提示也使用设置页统一 MessageBox。
        """
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
        """
        确认弹窗统一使用 qfluentwidgets.MessageBox。

        不使用 Dialog。
        不使用自动化页专属样式。
        parent 必须是完整 SettingsMenu。
        """
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
        """
        保存成功、测试已开始等轻量提示使用设置页常用 Flyout。
        注意 parent 同样使用完整设置窗口，保证视觉层级一致。
        """
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


    def _show_tip_flyout(
        self,
        title: str,
        content: str,
        target: QWidget | None = None,
        icon=InfoBarIcon.INFORMATION,
    ) -> None:
        """
        统一设置页 Flyout 风格。
        保存 / 应用 / 测试这类轻量反馈不再弹模态框，和其它设置页保持一致。
        """
        target = target or self.status_card
        parent = self._dialog_host()

        try:
            flyout = Flyout.create(
                icon=icon,
                title=title,
                content=content,
                target=target,
                parent=parent,
                isClosable=True,
                aniType=FlyoutAnimationType.PULL_UP,
            )
            try:
                flyout.setFocusPolicy(Qt.NoFocus)
            except Exception:
                pass
        except Exception:
            # Flyout 创建失败时至少不要丢反馈
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
        self.subtitle_label.setStyleSheet("color: #666;")
        root.addWidget(self.subtitle_label)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)
        self.main_splitter.setStyleSheet("QSplitter::handle { background: transparent; }")
        self.main_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.main_splitter, 1)

        self.left_scroll = SmoothScrollArea()
        self.left_scroll.setStyleSheet(_scroll_style())
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
        self.enable_hint.setStyleSheet("color: #666;")
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
        self.config_info_label.setStyleSheet("color: #444;")
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
        self.right_scroll.setStyleSheet(_scroll_style())
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
        self.workflow_tip.setStyleSheet("color: #666;")
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

        self.trigger_tip = CaptionLabel("常见示例：应用启动时、托盘菜单点击时、收到信号时。")
        self.trigger_tip.setWordWrap(True)
        self.trigger_tip.setStyleSheet("color: #666;")
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
        self.action_tip.setStyleSheet("color: #666;")
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
        self.action_test_tip.setStyleSheet("color: #8a5a00;")
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
                text = "已保存到文件。"
        self.status_label.setText(text)
        self._set_status_style("#8a5a00", "rgba(255, 170, 0, 0.10)")

    def _set_status_applied(self, text: str | None = None) -> None:
        if text is None:
            text = "已应用到当前运行时。"
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
        self.reload_btn.clicked.connect(self._on_reload)
        self.save_btn.clicked.connect(self._on_save)
        self.apply_btn.clicked.connect(self._on_apply)
        self.new_config_btn.clicked.connect(self._on_new_config)
        self.delete_config_btn.clicked.connect(self._on_delete_config)

        self.enable_box.toggled.connect(self._on_global_enabled_changed)

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
        self.test_action_invoke_btn.clicked.connect(self._on_test_invoke_actions)
        self.test_action_revert_btn.clicked.connect(self._on_test_revert_actions)


        self.workflow_list.currentRowChanged.connect(self._on_workflow_selected)
        self.trigger_list.currentRowChanged.connect(self._on_trigger_selected)
        self.action_list.currentRowChanged.connect(self._on_action_selected)

        self.property_editor.changed.connect(self._on_property_changed)
        self.rules_editor.changed.connect(self._on_ruleset_changed)
        self.rules_editor.targetChanged.connect(self._on_ruleset_target_changed)
        self.config_combo.currentIndexChanged.connect(self._on_config_changed)

    # =========================================================
    # Reload
    # =========================================================

    def _reload_all(self) -> None:
        self._reload_configs()
        self._reload_workflows()
        self._reload_global_state()
        self._update_config_info()

    def _reload_global_state(self) -> None:
        settings = self.controller.runtime.context.settings
        enabled = bool(getattr(settings, "IsAutomationEnabled", True))
        self.enable_box.blockSignals(True)
        self.enable_box.setChecked(enabled)
        self.enable_box.blockSignals(False)

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

        for trigger in workflow.Triggers:
            self.trigger_list.addItem(
                QListWidgetItem(self.controller.trigger_display_text(trigger))
            )

        for action in workflow.ActionSet.Actions:
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

    def _refresh_summary_texts_only(self) -> None:
        for i, workflow in enumerate(self.controller.workflows):
            item = self.workflow_list.item(i)
            if item is not None:
                item.setText(self.controller.workflow_display_text(workflow))

        workflow = self._get_current_workflow()
        if workflow is None:
            self.rules_editor.refresh_display_texts()
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

        self.rules_editor.refresh_display_texts()
        self._update_config_info()

    def _update_action_test_buttons(self) -> None:
        workflow = self._get_current_workflow()
        has_actions = (
            workflow is not None
            and workflow.ActionSet is not None
            and bool(workflow.ActionSet.Actions)
        )
        can_test = bool(has_actions and self.controller.can_test_actions())

        self.test_action_invoke_btn.setEnabled(can_test)
        self.test_action_revert_btn.setEnabled(can_test)

        if not self.controller.can_test_actions():
            tip = "当前没有连接到运行中的自动化服务，无法测试动作。"
        elif not has_actions:
            tip = "请先选择一个包含动作的工作流。"
        else:
            tip = "会立即在当前会话执行动作，请谨慎测试。"

        self.test_action_invoke_btn.setToolTip(tip)
        self.test_action_revert_btn.setToolTip(tip)

    # =========================================================
    # Current helpers
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

    def _clear_trigger_action_selection(self) -> None:
        self._current_trigger_index = -1
        self._current_action_index = -1

        self.trigger_list.blockSignals(True)
        self.trigger_list.clearSelection()
        self.trigger_list.setCurrentRow(-1)
        self.trigger_list.blockSignals(False)

        self.action_list.blockSignals(True)
        self.action_list.clearSelection()
        self.action_list.setCurrentRow(-1)
        self.action_list.blockSignals(False)

    # =========================================================
    # Picker dialogs
    # =========================================================

    def _pick_trigger_id(self) -> str | None:
        groups = self.controller.available_trigger_groups()
        dlg = GroupedPickerDialog("添加触发器", groups, TRIGGER_DESCRIPTIONS, self._dialog_host())
        self._center_window_dialog(dlg)
        if self._exec_dialog(dlg) == QDialog.Accepted:
            return dlg.selected_id
        return None

    def _pick_action_id(self) -> str | None:
        groups = self.controller.available_action_groups()
        dlg = GroupedPickerDialog("添加动作", groups, ACTION_DESCRIPTIONS, self._dialog_host())
        self._center_window_dialog(dlg)
        if self._exec_dialog(dlg) == QDialog.Accepted:
            return dlg.selected_id
        return None

    # =========================================================
    # Config actions
    # =========================================================

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
                f"确定要删除配置文件“{current}”吗？\n\n删除后无法恢复。",
                yes_text="删除",
                cancel_text="取消",
            ):
                return

            next_name = self.controller.delete_config(current)
            self._reload_all()
            idx = self.config_combo.findText(next_name)
            if idx >= 0:
                self.config_combo.setCurrentIndex(idx)

            self._set_status_saved(f"已删除配置：{current}。当前切换到：{next_name}。")
        except Exception as e:
            self._set_status_error(f"删除配置失败：{e}")
            self._show_error_dialog("自动化", f"删除配置失败：\n{e}")

    def _on_global_enabled_changed(self, state: bool) -> None:
        try:
            settings = self.controller.runtime.context.settings
            if hasattr(settings, "IsAutomationEnabled"):
                settings.IsAutomationEnabled = bool(state)
            self.controller.save_current()
            self._set_status_saved('已修改“启用自动化”状态，并保存到文件。若要影响当前会话，请点击“应用到运行时”。')
        except Exception as e:
            self._set_status_error(f"修改启用状态失败：{e}")
            self._show_error_dialog("自动化", f"修改启用状态失败：\n{e}")

    def _on_reload(self) -> None:
        try:
            self.controller.load_current()
            self._current_trigger_index = -1
            self._current_action_index = -1
            self._reload_all()
            self._set_status_info(
                f"已从文件重载配置：{self.controller.get_current_config_name()}。"
                + (" 如需影响当前会话，请点击“应用到运行时”。" if self.controller.has_live_runtime() else "")
            )
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
                        "应用到运行时",
                        f"将使用当前配置文件“{config_name}”中的 {wf_count} 个工作流替换当前运行时。\n\n"
                        "这不会合并旧工作流，而是整体重载。\n\n"
                        "是否继续？",
                        yes_text="继续",
                        cancel_text="取消",
                ):
                    return

            self.controller.save_current()
            applied = self.controller.apply_current()
            self._update_config_info()

            if applied:
                self._set_status_applied(
                    f"已应用到当前运行时：{config_name}（{wf_count} 个工作流）。"
                )
                self._show_info_dialog("自动化", "已应用到当前运行时。")
            else:
                self._set_status_saved("当前没有可应用的运行时，已仅保存到文件。")
                self._show_info_dialog("自动化", "当前没有可应用的运行时，仅保存到了文件。")

        except Exception as e:
            self._set_status_error(f"应用到运行时失败：{e}")
            self._show_error_dialog("自动化", f"应用到运行时失败：\n{e}")


        except Exception as e:
            self._set_status_error(f"应用到运行时失败：{e}")
            self._show_error_dialog("自动化", f"应用到运行时失败：\n{e}")

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
            self._reload_global_state()
            self._update_config_info()

            self._set_status_saved(
                f"当前正在编辑配置：{name}。"
                + (" 已切换文件，若要影响当前会话，请点击“应用到运行时”。" if self.controller.has_live_runtime() else " 仅文件编辑模式。")
            )
        except Exception as e:
            self._set_status_error(f"切换配置文件失败：{e}")
            self._show_error_dialog("自动化", f"切换配置文件失败：\n{e}")

    # =========================================================
    # Workflow
    # =========================================================

    def _on_new_workflow(self) -> None:
        try:
            self.controller.create_workflow()
            self._current_workflow_index = len(self.controller.workflows) - 1
            self._current_trigger_index = -1
            self._current_action_index = -1
            self._reload_workflows()
            self.rules_editor.clear_selection_focus()
            self._set_status_saved("已新建工作流，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"新建工作流失败：{e}")
            self._show_error_dialog("自动化", f"新建工作流失败：\n{e}")

    def _on_delete_workflow(self) -> None:
        try:
            if self._current_workflow_index < 0:
                return
            self.controller.delete_workflow(self._current_workflow_index)
            self._current_trigger_index = -1
            self._current_action_index = -1
            self._current_workflow_index = min(self._current_workflow_index, len(self.controller.workflows) - 1)
            self._reload_workflows()
            self.rules_editor.clear_selection_focus()
            self._set_status_saved("已删除工作流，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"删除工作流失败：{e}")
            self._show_error_dialog("自动化", f"删除工作流失败：\n{e}")

    def _on_workflow_up(self) -> None:
        try:
            self._current_workflow_index = self.controller.move_workflow_up(self._current_workflow_index)
            self._reload_workflows()
            self.rules_editor.clear_selection_focus()
            self._set_status_saved("已调整工作流顺序，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"上移工作流失败：{e}")
            self._show_error_dialog("自动化", f"上移工作流失败：\n{e}")

    def _on_workflow_down(self) -> None:
        try:
            self._current_workflow_index = self.controller.move_workflow_down(self._current_workflow_index)
            self._reload_workflows()
            self.rules_editor.clear_selection_focus()
            self._set_status_saved("已调整工作流顺序，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"下移工作流失败：{e}")
            self._show_error_dialog("自动化", f"下移工作流失败：\n{e}")

    # =========================================================
    # Trigger
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
            self._set_status_saved("已添加触发器，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"添加触发器失败：{e}")
            self._show_error_dialog("自动化", f"添加触发器失败：\n{e}")

    def _on_delete_trigger(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return
            self.controller.delete_trigger(workflow, self._current_trigger_index)
            self._current_trigger_index = -1
            self._reload_middle()
            self._set_status_saved("已删除触发器，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"删除触发器失败：{e}")
            self._show_error_dialog("自动化", f"删除触发器失败：\n{e}")

    def _on_trigger_up(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return
            self._current_trigger_index = self.controller.move_trigger_up(workflow, self._current_trigger_index)
            self._reload_middle()
            if self._current_trigger_index >= 0:
                self.trigger_list.setCurrentRow(self._current_trigger_index)
            self._set_status_saved("已调整触发器顺序，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"上移触发器失败：{e}")
            self._show_error_dialog("自动化", f"上移触发器失败：\n{e}")

    def _on_trigger_down(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return
            self._current_trigger_index = self.controller.move_trigger_down(workflow, self._current_trigger_index)
            self._reload_middle()
            if self._current_trigger_index >= 0:
                self.trigger_list.setCurrentRow(self._current_trigger_index)
            self._set_status_saved("已调整触发器顺序，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"下移触发器失败：{e}")
            self._show_error_dialog("自动化", f"下移触发器失败：\n{e}")

    # =========================================================
    # Action
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
            self._set_status_saved("已添加动作，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"添加动作失败：{e}")
            self._show_error_dialog("自动化", f"添加动作失败：\n{e}")

    def _on_delete_action(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return
            self.controller.delete_action(workflow, self._current_action_index)
            self._current_action_index = -1
            self._reload_middle()
            self._set_status_saved("已删除动作，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"删除动作失败：{e}")
            self._show_error_dialog("自动化", f"删除动作失败：\n{e}")

    def _on_action_up(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return
            self._current_action_index = self.controller.move_action_up(workflow, self._current_action_index)
            self._reload_middle()
            if self._current_action_index >= 0:
                self.action_list.setCurrentRow(self._current_action_index)
            self._set_status_saved("已调整动作顺序，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"上移动作失败：{e}")
            self._show_error_dialog("自动化", f"上移动作失败：\n{e}")

    def _on_action_down(self) -> None:
        try:
            workflow = self._get_current_workflow()
            if workflow is None:
                return
            self._current_action_index = self.controller.move_action_down(workflow, self._current_action_index)
            self._reload_middle()
            if self._current_action_index >= 0:
                self.action_list.setCurrentRow(self._current_action_index)
            self._set_status_saved("已调整动作顺序，并保存到文件。")
        except Exception as e:
            self._set_status_error(f"下移动作失败：{e}")
            self._show_error_dialog("自动化", f"下移动作失败：\n{e}")

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

            # 保存编辑态，确保外部文件和内存一致；测试实际使用的是当前编辑态对象的副本
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
    # Selection
    # =========================================================

    def _on_workflow_selected(self, row: int) -> None:
        self._current_workflow_index = row
        self._current_trigger_index = -1
        self._current_action_index = -1
        self._reload_middle()
        self.rules_editor.clear_selection_focus()

        workflow = self._get_current_workflow()
        if workflow is not None:
            self.property_editor.set_target("workflow", workflow)

    def _on_trigger_selected(self, row: int) -> None:
        self._current_trigger_index = row
        if row >= 0:
            self.action_list.blockSignals(True)
            self.action_list.clearSelection()
            self.action_list.setCurrentRow(-1)
            self.action_list.blockSignals(False)
            self._current_action_index = -1
            self.rules_editor.clear_selection_focus()

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
            self.trigger_list.setCurrentRow(-1)
            self.trigger_list.blockSignals(False)
            self._current_trigger_index = -1
            self.rules_editor.clear_selection_focus()

        action = self._get_current_action()
        if action is not None:
            self.property_editor.set_target("action", action)
        elif self._get_current_workflow() is not None:
            self.property_editor.set_target("workflow", self._get_current_workflow())

    def _on_ruleset_target_changed(self, kind: str, target: object) -> None:
        self._clear_trigger_action_selection()
        if target is not None:
            self.property_editor.set_target(kind, target)

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
            self._show_error_dialog("自动化", f"保存属性失败：\n{e}")

    def _on_ruleset_changed(self) -> None:
        try:
            self.controller.save_current()
            self._refresh_summary_texts_only()
            self._set_status_saved('已修改规则集结构，并保存到文件。若要影响当前会话，请点击“应用到运行时”。')
        except Exception as e:
            self._set_status_error(f"保存规则集失败：{e}")
            self._show_error_dialog("自动化", f"保存规则集失败：\n{e}")
