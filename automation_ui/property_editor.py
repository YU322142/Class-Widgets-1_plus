from __future__ import annotations

import sys
from typing import Any

import list_
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    EditableComboBox,
    LineEdit,
    PushButton,
    SpinBox,
    StrongBodyLabel,
)

from automation.compat import RULE_SETTINGS_TYPES
from automation.enums import RunActionRunType, RulesetLogicalMode, TimeState
from automation.models import (
    ActionItem,
    AppRestartActionSettings,
    CurrentSubjectRuleSettings,
    CurrentWeatherRuleSettings,
    ModifyAppSettingsActionSettings,
    NotificationActionSettings,
    PreTimePointTriggerSettings,
    RainTimeRuleSettings,
    Rule,
    RuleGroup,
    Ruleset,
    RunActionSettings,
    SignalTriggerSettings,
    SleepActionSettings,
    StringMatchingSettings,
    SunRiseSetRuleSettings,
    TimeStateRuleSettings,
    TrayMenuTriggerSettings,
    TriggerSettings,
    UriTriggerSettings,
    WeatherNotificationActionSettings,
    WindowStatusRuleSettings,
    Workflow,
)
from automation.registry import get_action_info, get_rule_info, get_trigger_info
from file import config_center


def combo_add_item(combo: ComboBox, text: str, data: Any) -> None:
    try:
        combo.addItem(text, None, data)
    except TypeError:
        combo.addItem(text)
        try:
            combo.setItemData(combo.count() - 1, data, Qt.UserRole)
        except TypeError:
            combo.setItemData(combo.count() - 1, data)


def combo_current_data(combo: ComboBox) -> Any:
    try:
        return combo.currentData()
    except Exception:
        try:
            return combo.itemData(combo.currentIndex())
        except Exception:
            return None


class FieldWidget(QWidget):
    def __init__(self, editor: QWidget, hint: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(editor)

        if hint:
            self.hint_label = CaptionLabel(hint)
            self.hint_label.setWordWrap(True)
            self.hint_label.setStyleSheet("color: #666;")
            layout.addWidget(self.hint_label)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)


class EditorSection(QFrame):
    def __init__(self, title: str, desc: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AutomationEditorSection")
        self.setStyleSheet(
            """
            QFrame#AutomationEditorSection {
                background: rgba(255, 255, 255, 0.72);
                border: 1px solid rgba(0, 0, 0, 0.035);
                border-radius: 10px;
            }
            """
        )
        self.layout_root = QVBoxLayout(self)
        self.layout_root.setContentsMargins(12, 12, 12, 12)
        self.layout_root.setSpacing(10)

        self.title_label = StrongBodyLabel(title)
        self.title_label.setWordWrap(True)
        self.layout_root.addWidget(self.title_label)

        if desc:
            self.desc_label = CaptionLabel(desc)
            self.desc_label.setWordWrap(True)
            self.desc_label.setStyleSheet("color: #666;")
            self.layout_root.addWidget(self.desc_label)

        self.form = QFormLayout()
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setSpacing(12)
        self.form.setHorizontalSpacing(18)
        self.form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.layout_root.addLayout(self.form)


class AutomationPropertyEditor(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._kind: str | None = None
        self._target: Any = None

        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)

    def set_target(self, kind: str | None, target: Any) -> None:
        self._kind = kind
        self._target = target
        self._rebuild()

    def _clear_content(self) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _rebuild(self) -> None:
        self._clear_content()

        if self._kind is None or self._target is None:
            section = EditorSection("参数设置", "请选择右侧要编辑的对象。")
            self.content_layout.addWidget(section)
            self.content_layout.addStretch(1)
            return

        if self._kind == "workflow":
            self._build_workflow_editor(self._target)
        elif self._kind == "trigger":
            self._build_trigger_editor(self._target)
        elif self._kind == "action":
            self._build_action_editor(self._target)
        elif self._kind == "ruleset":
            self._build_ruleset_editor(self._target)
        elif self._kind == "rule_group":
            self._build_rule_group_editor(self._target)
        elif self._kind == "rule":
            self._build_rule_editor(self._target)
        else:
            section = EditorSection("参数设置", "暂不支持此对象编辑。")
            self.content_layout.addWidget(section)

        self.content_layout.addStretch(1)

    # =========================================================
    # Workflow
    # =========================================================

    def _build_workflow_editor(self, workflow: Workflow) -> None:
        section = EditorSection("工作流", "工作流对应一个 ActionSet，可包含多个触发器、条件和动作。")
        self.content_layout.addWidget(section)

        self._add_line_edit(
            section.form,
            "名称",
            workflow.ActionSet,
            "Name",
            hint="工作流名称仅用于区分和管理，建议起一个能描述用途的名字。",
        )
        self._add_checkbox(
            section.form,
            "启用",
            workflow.ActionSet,
            "IsEnabled",
            hint="关闭后，这个工作流会被保留，但不会执行。",
        )
        self._add_checkbox(
            section.form,
            "启用恢复",
            workflow.ActionSet,
            "IsRevertEnabled",
            hint="启用后，当规则集不再满足或触发恢复时，支持恢复的动作会自动回退。",
        )
        self._add_checkbox(
            section.form,
            "启用条件",
            workflow,
            "IsConditionEnabled",
            hint="启用后，只有规则集满足时工作流才会执行；不启用时将忽略规则集。",
        )

    # =========================================================
    # Trigger
    # =========================================================

    def _build_trigger_editor(self, trigger: TriggerSettings) -> None:
        info = get_trigger_info(trigger.Id)
        section = EditorSection("触发器", "决定工作流在什么时候触发。")
        self.content_layout.addWidget(section)

        section.form.addRow(self._make_label("类型"), self._make_value_label(info.Name if info else trigger.Id))
        section.form.addRow(self._make_label("ID"), self._make_subtle_value_label(trigger.Id))

        settings = trigger.Settings
        if settings is None:
            self._add_note_row(section.form, "此触发器没有设置项。")
            return

        if isinstance(settings, SignalTriggerSettings):
            self._add_line_edit(
                section.form,
                "信号名",
                settings,
                "SignalName",
                hint="用于和“广播信号”动作配对。名称必须完全一致，例如 demo-signal。",
            )
            self._add_checkbox(
                section.form,
                "是否为恢复触发",
                settings,
                "IsRevert",
                hint="勾选后表示：收到的是恢复信号，而不是普通触发信号。",
            )
            return

        if isinstance(settings, TrayMenuTriggerSettings):
            self._add_line_edit(
                section.form,
                "菜单标题",
                settings,
                "Header",
                hint="显示在托盘菜单中的文字，例如“测试天气提醒”。",
            )
            self._add_checkbox(
                section.form,
                "点击触发恢复",
                settings,
                "IsRevert",
                hint="勾选后，点击托盘菜单时会触发恢复流程，而不是普通触发。",
            )
            return

        if isinstance(settings, UriTriggerSettings):
            self._add_line_edit(
                section.form,
                "URI 后缀",
                settings,
                "UriSuffix",
                hint="例如填写 demo/run，则可通过自动化 URI 路由触发对应工作流。",
            )
            return

        if hasattr(settings, "CronExpression"):
            self._add_line_edit(
                section.form,
                "Cron 表达式",
                settings,
                "CronExpression",
                hint="例如 */5 * * * * 表示每 5 分钟触发一次。",
            )
            return

        if isinstance(settings, PreTimePointTriggerSettings):
            self._add_pre_time_point_state_combo(
                section.form,
                "目标状态",
                settings,
                "TargetState",
                hint="对齐 ClassIsland：这里只支持“上课 / 课间 / 放学”三个提前时间点。",
            )
            self._add_double_spin(
                section.form,
                "提前秒数",
                settings,
                "TimeSeconds",
                minimum=0,
                maximum=999999,
                step=1,
                hint="例如填写 60，表示在目标状态开始前 60 秒触发。",
            )
            return

        self._add_note_row(section.form, "该触发器设置编辑器尚未实现。")

    # =========================================================
    # Action
    # =========================================================

    def _build_action_editor(self, action: ActionItem) -> None:
        info = get_action_info(action.Id)
        section = EditorSection("动作", "触发后执行的动作，按顺序串行运行。")
        self.content_layout.addWidget(section)

        section.form.addRow(self._make_label("类型"), self._make_value_label(info.Name if info else action.Id))
        section.form.addRow(self._make_label("ID"), self._make_subtle_value_label(action.Id))

        settings = action.Settings
        if settings is None:
            self._add_note_row(section.form, "此动作没有设置项。")
            return

        if isinstance(settings, NotificationActionSettings):
            self._add_note_row(
                section.form,
                "说明：在 CW 中“主提示”和“详细内容”会同时显示，不是 ClassIsland 那种先标题再正文的串行显示。",
            )
            self._add_line_edit(
                section.form,
                "主提示文字",
                settings,
                "Mask",
                hint="主要显示在提醒的主区域，相当于更醒目的核心提示。",
            )
            self._add_line_edit(
                section.form,
                "详细内容",
                settings,
                "Content",
                hint="补充说明内容，可留空。",
            )
            self._add_checkbox(
                section.form,
                "等待完成",
                settings,
                "IsWaitForCompleteEnabled",
                hint="勾选后，后续动作会等这条提醒显示完成再继续执行。",
            )
            self._add_checkbox(
                section.form,
                "高级设置",
                settings,
                "IsAdvancedSettingsEnabled",
                hint="启用后，下方音效、置顶等参数才会真正生效。",
            )
            self._add_checkbox(
                section.form,
                "详细内容语音",
                settings,
                "IsContentSpeechEnabled",
                hint="勾选后，会朗读详细内容。",
            )
            self._add_checkbox(
                section.form,
                "主提示语音",
                settings,
                "IsMaskSpeechEnabled",
                hint="勾选后，会朗读主提示文字。",
            )
            self._add_checkbox(
                section.form,
                "音效",
                settings,
                "IsSoundEffectEnabled",
                hint="勾选后，显示通知时会播放音效。",
            )
            self._add_checkbox(
                section.form,
                "置顶",
                settings,
                "IsTopmostEnabled",
                hint="勾选后，提醒显示时会尽量置顶。",
            )
            self._add_double_spin(
                section.form,
                "主提示持续(秒)",
                settings,
                "MaskDurationSeconds",
                0,
                999,
                1,
                hint="控制主提示区域保留多久。",
            )
            self._add_double_spin(
                section.form,
                "详细内容持续(秒)",
                settings,
                "ContentDurationSeconds",
                0,
                999,
                1,
                hint="控制详细内容区域保留多久。",
            )
            return

        if isinstance(settings, WeatherNotificationActionSettings):
            combo = ComboBox()
            combo_add_item(combo, "三天天气预报", 0)
            combo_add_item(combo, "天气预警", 1)
            combo_add_item(combo, "逐小时天气", 2)

            current = int(getattr(settings, "NotificationKind", 0))
            idx = combo.findData(current)
            combo.setCurrentIndex(max(0, idx))

            def _on_changed(_):
                settings.NotificationKind = int(combo_current_data(combo))
                self.changed.emit()

            combo.currentIndexChanged.connect(_on_changed)
            section.form.addRow(
                self._make_label("天气提醒类型"),
                FieldWidget(combo, "选择要显示的天气信息类型：预报 / 预警 / 逐小时天气。"),
            )
            return

        if isinstance(settings, RunActionSettings):
            self._build_run_action_editor(section, settings)
            return

        if isinstance(settings, ModifyAppSettingsActionSettings):
            self._build_modify_app_settings_editor(section, settings)
            return

        if isinstance(settings, SleepActionSettings):
            self._add_double_spin(
                section.form,
                "等待秒数",
                settings,
                "Value",
                0,
                999999,
                1,
                hint="执行到这里后暂停这么多秒，再继续执行后续动作。",
            )
            return

        if isinstance(settings, SignalTriggerSettings):
            self._add_line_edit(
                section.form,
                "信号名",
                settings,
                "SignalName",
                hint="要广播的信号名称。其它 SignalTrigger 只有名称完全一致才会响应。",
            )
            self._add_checkbox(
                section.form,
                "是否广播恢复",
                settings,
                "IsRevert",
                hint="勾选后，广播的是恢复信号；否则广播普通触发信号。",
            )
            return

        if isinstance(settings, AppRestartActionSettings):
            self._add_checkbox(
                section.form,
                "静默重启",
                settings,
                "Value",
                hint="勾选后按“静默重启”模式执行。是否完全静默取决于主程序实现。",
            )
            return

        self._add_note_row(section.form, "该动作设置编辑器尚未实现。")

    # =========================================================
    # Ruleset / RuleGroup / Rule
    # =========================================================

    def _build_ruleset_editor(self, ruleset: Ruleset) -> None:
        section = EditorSection("规则集", "控制整个条件区域的逻辑方式。")
        self.content_layout.addWidget(section)

        self._add_ruleset_mode_combo(
            section.form,
            "规则集逻辑",
            ruleset,
            "Mode",
            hint="选择“任意组满足即可（OR）”或“所有组都要满足（AND）”。",
        )
        self._add_checkbox(
            section.form,
            "反转结果",
            ruleset,
            "IsReversed",
            hint="勾选后，整个规则集的判断结果会取反。",
        )
        self._add_note_row(section.form, "提示：规则组和单条规则的详细设置，在右侧选中对应对象后会显示在这里。")

    def _build_rule_group_editor(self, group: RuleGroup) -> None:
        section = EditorSection("规则组", "规则组用于把多条规则按 AND / OR 方式组合。")
        self.content_layout.addWidget(section)

        self._add_checkbox(
            section.form,
            "启用当前规则组",
            group,
            "IsEnabled",
            hint="关闭后，这个规则组会被保留，但不会参与判断。",
        )
        self._add_ruleset_mode_combo(
            section.form,
            "组逻辑",
            group,
            "Mode",
            hint="选择“任意规则满足即可（OR）”或“所有规则都要满足（AND）”。",
        )
        self._add_checkbox(
            section.form,
            "反转当前规则组结果",
            group,
            "IsReversed",
            hint="勾选后，这个规则组的结果会被取反。",
        )
        self._add_note_row(section.form, f"当前组内规则数：{len(getattr(group, 'Rules', []) or [])}")

    def _build_rule_editor(self, rule: Rule) -> None:
        info = get_rule_info(rule.Id) if getattr(rule, "Id", "") else None
        section = EditorSection("规则", "当前选中规则的详细属性。")
        self.content_layout.addWidget(section)

        section.form.addRow(self._make_label("类型"), self._make_value_label(info.Name if info else (rule.Id or "未选择规则")))
        section.form.addRow(self._make_label("ID"), self._make_subtle_value_label(rule.Id or "(空)"))

        self._add_checkbox(
            section.form,
            "反转当前规则结果",
            rule,
            "IsReversed",
            hint="勾选后，这条规则的判断结果会取反。",
        )

        if not rule.Id:
            self._add_note_row(section.form, "当前规则尚未指定类型。请在右侧规则列表中点击“更换规则类型”。")
            return

        if rule.Settings is None:
            settings_type = RULE_SETTINGS_TYPES.get(rule.Id)
            if settings_type is not None:
                rule.Settings = settings_type()

        settings = rule.Settings
        if settings is None:
            self._add_note_row(section.form, "此规则没有可编辑的设置项。")
            return

        if isinstance(settings, StringMatchingSettings):
            self._add_line_edit(
                section.form,
                "文本",
                settings,
                "Text",
                hint="填写要匹配的文本。",
            )
            self._add_checkbox(
                section.form,
                "使用正则",
                settings,
                "UseRegex",
                hint="勾选后，文本将按正则表达式处理。",
            )
            return

        if isinstance(settings, CurrentSubjectRuleSettings):
            self._add_subject_combo(
                section.form,
                "科目",
                settings,
                "SubjectId",
                hint="CW 当前按“科目显示名称”匹配，不是 ClassIsland 的 SubjectId / 科目对象语义。",
            )
            return

        if isinstance(settings, CurrentWeatherRuleSettings):
            self._add_current_weather_combo(
                section.form,
                "天气",
                settings,
                "WeatherId",
                hint="当前实现按精确天气代码匹配。",
            )
            return

        if isinstance(settings, RainTimeRuleSettings):
            self._add_double_spin(
                section.form,
                "分钟",
                settings,
                "RainTimeMinutes",
                0,
                9999,
                1,
                hint="用于判断距离下雨开始/结束还有多少分钟。",
            )
            self._add_checkbox(
                section.form,
                "判断剩余时间",
                settings,
                "IsRemainingTime",
                hint="勾选后，表示判断“距离结束还剩多少分钟”；否则判断“距离开始还有多少分钟”。",
            )
            return

        if isinstance(settings, SunRiseSetRuleSettings):
            self._add_double_spin(
                section.form,
                "分钟",
                settings,
                "TimeMinutes",
                0,
                9999,
                1,
                hint="相对于日出或日落的分钟偏移。",
            )
            self._add_checkbox(
                section.form,
                "是否判断日落后",
                settings,
                "IsSunset",
                hint="勾选后表示按“日落”判断；否则按“日出”判断。",
            )
            return

        if isinstance(settings, TimeStateRuleSettings):
            self._add_time_state_combo(
                section.form,
                "时间状态",
                settings,
                "State",
                hint="根据当前课程时间状态进行判断。",
            )
            return

        if isinstance(settings, WindowStatusRuleSettings):
            self._add_window_state_combo(
                section.form,
                "窗口状态",
                settings,
                "State",
                hint="匹配前台窗口当前状态。",
            )
            return

        self._add_note_row(section.form, "该规则的设置编辑器尚未实现。")

    # =========================================================
    # RunAction 专用编辑器
    # =========================================================

    def _build_run_action_editor(self, section: EditorSection, settings: RunActionSettings) -> None:
        type_combo = ComboBox()
        type_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo_add_item(type_combo, "应用程序", RunActionRunType.Application)
        combo_add_item(type_combo, "命令", RunActionRunType.Command)
        combo_add_item(type_combo, "文件", RunActionRunType.File)
        combo_add_item(type_combo, "文件夹", RunActionRunType.Folder)
        combo_add_item(type_combo, "URL", RunActionRunType.Url)

        current_type = settings.RunType
        idx = type_combo.findData(current_type)
        type_combo.setCurrentIndex(max(0, idx))

        section.form.addRow(
            self._make_label("运行类型"),
            FieldWidget(type_combo, "选择要运行的对象类型。"),
        )

        value_row = QWidget()
        value_row_layout = QHBoxLayout(value_row)
        value_row_layout.setContentsMargins(0, 0, 0, 0)
        value_row_layout.setSpacing(6)

        value_edit = LineEdit()
        value_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        value_edit.setText("" if getattr(settings, "Value", None) is None else str(settings.Value))
        value_row_layout.addWidget(value_edit)

        browse_btn = PushButton("浏览…")
        browse_btn.setFixedWidth(88)
        browse_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        value_row_layout.addWidget(browse_btn)

        value_hint_label = CaptionLabel("")
        value_hint_label.setWordWrap(True)
        value_hint_label.setStyleSheet("color: #666;")

        value_wrapper = QWidget()
        value_wrapper_layout = QVBoxLayout(value_wrapper)
        value_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        value_wrapper_layout.setSpacing(4)
        value_wrapper_layout.addWidget(value_row)
        value_wrapper_layout.addWidget(value_hint_label)
        value_wrapper.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        section.form.addRow(self._make_label("值"), value_wrapper)

        args_edit = LineEdit()
        args_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        args_edit.setText("" if getattr(settings, "Args", None) is None else str(settings.Args))
        args_widget = FieldWidget(args_edit, "（可选）应用程序启动参数")
        args_label = self._make_label("参数")
        section.form.addRow(args_label, args_widget)

        def _update_ui() -> None:
            rt = combo_current_data(type_combo)
            rt_val = rt.value if hasattr(rt, "value") else str(rt)

            if rt_val == "Application":
                value_edit.setPlaceholderText("应用程序路径")
                value_hint_label.setText("填写可执行文件路径，或点击“浏览…”选择。")
                browse_btn.setVisible(True)
                args_label.setVisible(True)
                args_widget.setVisible(True)
            elif rt_val == "File":
                value_edit.setPlaceholderText("文件路径")
                value_hint_label.setText("填写文件路径，或点击“浏览…”选择。系统会用默认程序打开。")
                browse_btn.setVisible(True)
                args_label.setVisible(False)
                args_widget.setVisible(False)
            elif rt_val == "Folder":
                value_edit.setPlaceholderText("文件夹路径")
                value_hint_label.setText("填写文件夹路径，或点击“浏览…”选择。系统会用文件管理器打开。")
                browse_btn.setVisible(True)
                args_label.setVisible(False)
                args_widget.setVisible(False)
            elif rt_val == "Url":
                value_edit.setPlaceholderText("https://example.com")
                value_hint_label.setText("填写网页地址。如果不包含协议前缀，会自动补全为 https://。")
                browse_btn.setVisible(False)
                args_label.setVisible(False)
                args_widget.setVisible(False)
            elif rt_val == "Command":
                value_edit.setPlaceholderText("Windows 下为 cmd 命令，Linux/macOS 下为 bash 命令")
                value_hint_label.setText("命令类型请直接在“值”中填写完整命令文本。")
                browse_btn.setVisible(False)
                args_label.setVisible(False)
                args_widget.setVisible(False)
            else:
                value_edit.setPlaceholderText("")
                value_hint_label.setText("")
                browse_btn.setVisible(False)
                args_label.setVisible(False)
                args_widget.setVisible(False)

        def _on_browse() -> None:
            rt = combo_current_data(type_combo)
            rt_val = rt.value if hasattr(rt, "value") else str(rt)

            if rt_val == "Folder":
                path = QFileDialog.getExistingDirectory(
                    self, "选择文件夹", value_edit.text()
                )
                if path:
                    value_edit.setText(path)

            elif rt_val == "Application":
                if sys.platform == "win32":
                    filter_str = "应用程序 (*.exe *.bat *.cmd *.com *.lnk);;所有文件 (*)"
                elif sys.platform == "darwin":
                    filter_str = "应用程序 (*.app);;所有文件 (*)"
                else:
                    filter_str = "所有文件 (*)"
                path, _ = QFileDialog.getOpenFileName(
                    self, "选择应用程序", value_edit.text(), filter_str
                )
                if path:
                    value_edit.setText(path)

            else:
                path, _ = QFileDialog.getOpenFileName(
                    self, "选择文件", value_edit.text(), "所有文件 (*)"
                )
                if path:
                    value_edit.setText(path)

        def _on_type_changed(_):
            settings.RunType = combo_current_data(type_combo)
            _update_ui()
            self.changed.emit()

        def _on_value_changed(text: str):
            settings.Value = text
            self.changed.emit()

        def _on_args_changed(text: str):
            settings.Args = text
            self.changed.emit()

        browse_btn.clicked.connect(_on_browse)
        type_combo.currentIndexChanged.connect(_on_type_changed)
        value_edit.textChanged.connect(_on_value_changed)
        args_edit.textChanged.connect(_on_args_changed)

        _update_ui()

    # =========================================================
    # ModifyAppSettingsAction 专用编辑器
    # =========================================================

    def _build_modify_app_settings_editor(
        self,
        section: EditorSection,
        settings: ModifyAppSettingsActionSettings,
    ) -> None:
        SETTING_CONFIG = "CurrentAutomationConfig"
        SETTING_ENABLED = "IsAutomationEnabled"
        SETTING_CUSTOM = "__custom__"

        name_combo = ComboBox()
        name_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo_add_item(name_combo, "当前自动化配置", SETTING_CONFIG)
        combo_add_item(name_combo, "自动化总开关", SETTING_ENABLED)
        combo_add_item(name_combo, "自定义字段（高级）", SETTING_CUSTOM)

        current_name = str(getattr(settings, "Name", "") or "").strip()
        if current_name == SETTING_CONFIG:
            current_mode = SETTING_CONFIG
        elif current_name == SETTING_ENABLED:
            current_mode = SETTING_ENABLED
        else:
            current_mode = SETTING_CUSTOM

        idx = name_combo.findData(current_mode)
        name_combo.setCurrentIndex(max(0, idx))

        section.form.addRow(
            self._make_label("设置名"),
            FieldWidget(
                name_combo,
                "当前 CW 自动化 backend 只安全保证少量 automation 自身设置可修改；这不是 CI 那种完整“全应用设置编辑器”。",
            ),
        )

        custom_name_edit = LineEdit()
        custom_name_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        custom_name_edit.setText("" if current_mode != SETTING_CUSTOM else current_name)
        custom_name_widget = FieldWidget(
            custom_name_edit,
            "高级用法：仅当运行时 settings 对象确实存在这个属性名时才会生效。",
        )
        custom_name_label = self._make_label("自定义字段")
        section.form.addRow(custom_name_label, custom_name_widget)

        value_container = QWidget()
        value_layout = QVBoxLayout(value_container)
        value_layout.setContentsMargins(0, 0, 0, 0)
        value_layout.setSpacing(4)

        config_value_combo = EditableComboBox()
        config_value_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        bool_value_box = CheckBox("启用")
        bool_value_box.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)

        raw_value_edit = LineEdit()
        raw_value_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        value_hint_label = CaptionLabel("")
        value_hint_label.setWordWrap(True)
        value_hint_label.setStyleSheet("color: #666;")

        value_layout.addWidget(config_value_combo)
        value_layout.addWidget(bool_value_box)
        value_layout.addWidget(raw_value_edit)
        value_layout.addWidget(value_hint_label)

        section.form.addRow(self._make_label("值"), value_container)

        def _as_bool(value: Any) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "y", "on"}
            return bool(value)

        def _load_automation_config_names() -> list[str]:
            try:
                import conf as conf_module
                names = list(conf_module.list_automation_configs())
            except Exception:
                names = []
            if not names:
                names = ["Default"]
            return names

        def _refresh_config_combo_items(current_value: str) -> None:
            names = _load_automation_config_names()
            if current_value and current_value not in names:
                names.append(current_value)

            try:
                config_value_combo.clear()
            except Exception:
                pass

            try:
                config_value_combo.addItems(names)
            except Exception:
                for name in names:
                    try:
                        config_value_combo.addItem(name)
                    except Exception:
                        pass

            try:
                config_value_combo.setCurrentText(current_value)
            except Exception:
                pass

        def _current_name_mode() -> str:
            mode = combo_current_data(name_combo)
            return str(mode or "")

        def _update_name_and_value_ui() -> None:
            mode = _current_name_mode()

            custom_name_label.setVisible(mode == SETTING_CUSTOM)
            custom_name_widget.setVisible(mode == SETTING_CUSTOM)

            config_value_combo.setVisible(False)
            bool_value_box.setVisible(False)
            raw_value_edit.setVisible(False)

            if mode == SETTING_CONFIG:
                settings.Name = SETTING_CONFIG
                current_value = "" if settings.Value is None else str(settings.Value)
                _refresh_config_combo_items(current_value)
                config_value_combo.setVisible(True)
                value_hint_label.setText("选择或输入要切换到的自动化配置名称。")
                if settings.Value in (None, ""):
                    try:
                        settings.Value = config_value_combo.currentText().strip() or "Default"
                    except Exception:
                        settings.Value = "Default"

            elif mode == SETTING_ENABLED:
                settings.Name = SETTING_ENABLED
                bool_value_box.blockSignals(True)
                bool_value_box.setChecked(_as_bool(settings.Value))
                bool_value_box.blockSignals(False)
                bool_value_box.setVisible(True)
                value_hint_label.setText("控制自动化总开关：勾选为启用，取消为禁用。")
                settings.Value = bool_value_box.isChecked()

            else:
                custom_name = custom_name_edit.text().strip()
                settings.Name = custom_name
                raw_value_edit.blockSignals(True)
                raw_value_edit.setText("" if settings.Value is None else str(settings.Value))
                raw_value_edit.blockSignals(False)
                raw_value_edit.setVisible(True)
                value_hint_label.setText(
                    "这里按原样填写字符串值。只有当运行时 settings 对象存在同名属性时才可能生效。"
                )

        def _on_name_mode_changed(_):
            _update_name_and_value_ui()
            self.changed.emit()

        def _on_custom_name_changed(text: str):
            if _current_name_mode() == SETTING_CUSTOM:
                settings.Name = text.strip()
                self.changed.emit()

        def _on_config_value_changed(text: str):
            if _current_name_mode() == SETTING_CONFIG:
                settings.Value = text.strip()
                self.changed.emit()

        def _on_bool_value_changed(state: bool):
            if _current_name_mode() == SETTING_ENABLED:
                settings.Value = bool(state)
                self.changed.emit()

        def _on_raw_value_changed(text: str):
            if _current_name_mode() == SETTING_CUSTOM:
                settings.Value = text
                self.changed.emit()

        name_combo.currentIndexChanged.connect(_on_name_mode_changed)
        custom_name_edit.textChanged.connect(_on_custom_name_changed)
        config_value_combo.textChanged.connect(_on_config_value_changed)
        bool_value_box.toggled.connect(_on_bool_value_changed)
        raw_value_edit.textChanged.connect(_on_raw_value_changed)

        _update_name_and_value_ui()

    # =========================================================
    # Widgets / helpers
    # =========================================================

    def _make_label(self, text: str) -> BodyLabel:
        label = BodyLabel(text)
        label.setWordWrap(True)
        label.setMinimumWidth(112)
        label.setMaximumWidth(132)
        return label

    def _make_value_label(self, text: str) -> BodyLabel:
        label = BodyLabel("" if text is None else str(text))
        label.setWordWrap(True)
        return label

    def _make_subtle_value_label(self, text: str) -> CaptionLabel:
        label = CaptionLabel("" if text is None else str(text))
        label.setWordWrap(True)
        label.setStyleSheet("color: #666;")
        return label

    def _add_note_row(self, form: QFormLayout, text: str) -> None:
        note = CaptionLabel(text)
        note.setWordWrap(True)
        note.setStyleSheet("color: #666;")
        form.addRow(note)

    def _create_styled_double_spin(self, minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setDecimals(2 if step < 1 else 0)
        spin.setMinimumHeight(33)
        spin.setStyleSheet(
            """
            QDoubleSpinBox {
                padding: 0 10px;
                border: 1px solid rgba(0, 0, 0, 0.10);
                border-radius: 6px;
                background: rgba(255, 255, 255, 0.96);
            }
            QDoubleSpinBox:focus {
                border: 1px solid #009faa;
            }
            """
        )
        return spin

    def _load_subject_options(self) -> list[str]:
        options: list[str] = []
        try:
            for name in list(getattr(list_, "class_kind", []))[1:]:
                text = str(name).strip()
                if text and text not in options:
                    options.append(text)
        except Exception:
            pass
        return options

    def _load_weather_options(self) -> list[str]:
        options: list[str] = []
        try:
            import weather as weather_module

            api_name = config_center.read_conf("Weather", "api", None)
            status_data = weather_module.weather_processor._load_weather_status(api_name)

            for item in status_data.get("weatherinfo", []):
                code = str(item.get("code", "")).strip()
                if not code:
                    continue
                name = str(item.get("wea", code)).strip()
                label = f"{name} ({code})"
                if label not in options:
                    options.append(label)
        except Exception:
            pass
        return options

    @staticmethod
    def _parse_weather_code_text(text: str) -> str:
        text = str(text or "").strip()
        if not text:
            return ""
        if text.endswith(")") and "(" in text:
            maybe = text[text.rfind("(") + 1:-1].strip()
            if maybe:
                return maybe
        return text

    def _add_ruleset_mode_combo(
        self,
        form: QFormLayout,
        title: str,
        obj: Any,
        attr: str,
        hint: str = "",
    ) -> None:
        combo = ComboBox()
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo_add_item(combo, "任意满足即可（OR）", RulesetLogicalMode.Or)
        combo_add_item(combo, "全部都要满足（AND）", RulesetLogicalMode.And)

        current = getattr(obj, attr, RulesetLogicalMode.Or)
        idx = combo.findData(current)
        combo.setCurrentIndex(max(0, idx))

        def _on_changed(_):
            setattr(obj, attr, combo_current_data(combo))
            self.changed.emit()

        combo.currentIndexChanged.connect(_on_changed)
        form.addRow(self._make_label(title), FieldWidget(combo, hint))

    def _add_line_edit(
        self,
        form: QFormLayout,
        title: str,
        obj: Any,
        attr: str,
        cast_to_str: bool = False,
        hint: str = "",
    ) -> None:
        edit = LineEdit()
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        current = getattr(obj, attr, "")
        edit.setText("" if current is None else str(current))

        def _on_changed(text: str):
            setattr(obj, attr, text if cast_to_str else text)
            self.changed.emit()

        edit.textChanged.connect(_on_changed)
        form.addRow(self._make_label(title), FieldWidget(edit, hint))

    def _add_checkbox(self, form: QFormLayout, title: str, obj: Any, attr: str, hint: str = "") -> None:
        box = CheckBox()
        box.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        box.setChecked(bool(getattr(obj, attr, False)))

        def _on_changed(state: bool):
            setattr(obj, attr, bool(state))
            self.changed.emit()

        box.toggled.connect(_on_changed)
        form.addRow(self._make_label(title), FieldWidget(box, hint))

    def _add_double_spin(
        self,
        form: QFormLayout,
        title: str,
        obj: Any,
        attr: str,
        minimum: float,
        maximum: float,
        step: float,
        hint: str = "",
    ) -> None:
        current_raw = getattr(obj, attr, 0)

        use_int_style = False
        try:
            current_float = float(current_raw)
            use_int_style = step >= 1 and float(int(current_float)) == current_float
        except Exception:
            current_float = 0.0
            use_int_style = step >= 1

        if use_int_style and float(int(minimum)) == float(minimum) and float(int(maximum)) == float(maximum):
            spin = SpinBox()
            spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            spin.setMinimum(int(minimum))
            spin.setMaximum(int(maximum))
            spin.setValue(int(current_float))

            def _on_changed(value: int):
                setattr(obj, attr, float(value))
                self.changed.emit()

            spin.valueChanged.connect(_on_changed)
            form.addRow(self._make_label(title), FieldWidget(spin, hint))
            return

        spin = self._create_styled_double_spin(minimum, maximum, step)
        try:
            spin.setValue(float(current_raw))
        except Exception:
            spin.setValue(0)

        def _on_changed(value: float):
            setattr(obj, attr, float(value))
            self.changed.emit()

        spin.valueChanged.connect(_on_changed)
        form.addRow(self._make_label(title), FieldWidget(spin, hint))

    def _add_int_spin(
        self,
        form: QFormLayout,
        title: str,
        obj: Any,
        attr: str,
        minimum: int,
        maximum: int,
        hint: str = "",
    ) -> None:
        spin = SpinBox()
        spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        spin.setMinimum(minimum)
        spin.setMaximum(maximum)
        try:
            spin.setValue(int(getattr(obj, attr, 0)))
        except Exception:
            spin.setValue(0)

        def _on_changed(value: int):
            setattr(obj, attr, int(value))
            self.changed.emit()

        spin.valueChanged.connect(_on_changed)
        form.addRow(self._make_label(title), FieldWidget(spin, hint))

    def _add_subject_combo(
        self,
        form: QFormLayout,
        title: str,
        obj: Any,
        attr: str,
        hint: str = "",
    ) -> None:
        combo = EditableComboBox()
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        options = self._load_subject_options()
        current = str(getattr(obj, attr, "") or "").strip()

        try:
            combo.addItems(options)
        except Exception:
            pass

        if current:
            try:
                combo.setCurrentText(current)
            except Exception:
                pass

        def _commit_value(_text: str = ""):
            try:
                value = str(combo.currentText()).strip()
            except Exception:
                value = ""
            setattr(obj, attr, value)
            self.changed.emit()

        combo.textChanged.connect(_commit_value)
        form.addRow(self._make_label(title), FieldWidget(combo, hint))

    def _add_current_weather_combo(
        self,
        form: QFormLayout,
        title: str,
        obj: Any,
        attr: str,
        hint: str = "",
    ) -> None:
        combo = EditableComboBox()
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        options = self._load_weather_options()
        current_raw = getattr(obj, attr, 0)
        current_code = "" if current_raw is None else str(current_raw).strip()

        try:
            combo.addItems(options)
        except Exception:
            pass

        if current_code:
            matched_label = None
            for label in options:
                if self._parse_weather_code_text(label) == current_code:
                    matched_label = label
                    break
            try:
                combo.setCurrentText(matched_label or current_code)
            except Exception:
                pass

        def _commit_value(_text: str = ""):
            try:
                text = str(combo.currentText()).strip()
            except Exception:
                text = ""
            code = self._parse_weather_code_text(text)
            if not code:
                return
            try:
                setattr(obj, attr, int(code))
            except Exception:
                return
            self.changed.emit()

        combo.textChanged.connect(_commit_value)
        form.addRow(self._make_label(title), FieldWidget(combo, hint))

    def _add_time_state_combo(
        self,
        form: QFormLayout,
        title: str,
        obj: Any,
        attr: str,
        hint: str = "",
    ) -> None:
        combo = ComboBox()
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo_add_item(combo, "无", TimeState.None_)
        combo_add_item(combo, "上课", TimeState.OnClass)
        combo_add_item(combo, "准备上课（当前不可用）", TimeState.PrepareOnClass)
        combo_add_item(combo, "课间休息", TimeState.Breaking)
        combo_add_item(combo, "放学后", TimeState.AfterSchool)

        try:
            model = combo.model()
            item = model.item(2)
            if item is not None:
                item.setEnabled(False)
        except Exception:
            pass

        current = getattr(obj, attr, TimeState.OnClass)
        idx = combo.findData(current)
        combo.setCurrentIndex(max(0, idx))

        def _on_changed(_):
            setattr(obj, attr, combo_current_data(combo))
            self.changed.emit()

        combo.currentIndexChanged.connect(_on_changed)
        form.addRow(self._make_label(title), FieldWidget(combo, hint))

    def _add_pre_time_point_state_combo(
        self,
        form: QFormLayout,
        title: str,
        obj: Any,
        attr: str,
        hint: str = "",
    ) -> None:
        combo = ComboBox()
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo_add_item(combo, "上课", TimeState.OnClass)
        combo_add_item(combo, "课间", TimeState.Breaking)
        combo_add_item(combo, "放学", TimeState.AfterSchool)

        allowed = {TimeState.OnClass, TimeState.Breaking, TimeState.AfterSchool}

        try:
            current = TimeState.from_value(getattr(obj, attr, TimeState.OnClass))
        except Exception:
            current = TimeState.OnClass

        # 兼容旧版本错误 UI 保存出来的 PrepareOnClass
        if current == TimeState.PrepareOnClass:
            current = TimeState.OnClass

        if current not in allowed:
            current = TimeState.OnClass

        setattr(obj, attr, current)

        idx = combo.findData(current)
        combo.setCurrentIndex(max(0, idx))

        def _on_changed(_):
            try:
                selected = TimeState.from_value(combo_current_data(combo))
            except Exception:
                selected = TimeState.OnClass

            if selected not in allowed:
                selected = TimeState.OnClass

            setattr(obj, attr, selected)
            self.changed.emit()

        combo.currentIndexChanged.connect(_on_changed)
        form.addRow(self._make_label(title), FieldWidget(combo, hint))


    def _add_window_state_combo(
        self,
        form: QFormLayout,
        title: str,
        obj: Any,
        attr: str,
        hint: str = "",
    ) -> None:
        combo = ComboBox()
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo_add_item(combo, "正常", 0)
        combo_add_item(combo, "最大化", 1)
        combo_add_item(combo, "最小化", 2)
        combo_add_item(combo, "全屏", 3)

        current = int(getattr(obj, attr, 1))
        idx = combo.findData(current)
        combo.setCurrentIndex(max(0, idx))

        def _on_changed(_):
            setattr(obj, attr, int(combo_current_data(combo)))
            self.changed.emit()

        combo.currentIndexChanged.connect(_on_changed)
        form.addRow(self._make_label(title), FieldWidget(combo, hint))
