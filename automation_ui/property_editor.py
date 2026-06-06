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
    StrongBodyLabel,
    qconfig,
    isDarkTheme,
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
            layout.addWidget(self.hint_label)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)


class EditorSection(QFrame):
    def __init__(self, title: str, desc: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AutomationEditorSection")
        self._update_style()
        qconfig.themeChanged.connect(self._update_style)

        self.layout_root = QVBoxLayout(self)
        self.layout_root.setContentsMargins(12, 12, 12, 12)
        self.layout_root.setSpacing(10)

        self.title_label = StrongBodyLabel(title)
        self.title_label.setWordWrap(True)
        self.layout_root.addWidget(self.title_label)

        if desc:
            self.desc_label = CaptionLabel(desc)
            self.desc_label.setWordWrap(True)
            self.layout_root.addWidget(self.desc_label)

        self.form = QFormLayout()
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setSpacing(12)
        self.form.setHorizontalSpacing(18)
        self.form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.layout_root.addLayout(self.form)

    def _update_style(self):
        if isDarkTheme():
            self.setStyleSheet(
                """
                QFrame#AutomationEditorSection {
                    background: rgba(255, 255, 255, 0.03);
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 10px;
                }
                """
            )
        else:
            self.setStyleSheet(
                """
                QFrame#AutomationEditorSection {
                    background: rgba(255, 255, 255, 0.72);
                    border: 1px solid rgba(0, 0, 0, 0.035);
                    border-radius: 10px;
                }
                """
            )


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
                hint="例如填写 demo/test，然后通过 emit_automation_uri(\"demo/test\") 触发。",
            )
            self._add_note_row(
                section.form,
                "调用 URI 触发器的用法：\n"
                "1. 这里填写一个后缀，例如 demo/test。\n"
                "2. 普通触发：emit_automation_uri(\"demo/test\")。\n"
                "3. 触发恢复：emit_automation_uri(\"demo/test\", revert=True)。\n\n"
                "注意：这里的 URI 是自动化内部路由，不是打开 https:// 链接。\n"
                "“运行 → URL”是动作，用来打开网页；“调用 URI 时”是触发器，用来让外部逻辑触发工作流。\n"
                "当前版本如果要从浏览器或系统快捷方式直接调用，还需要额外注册系统 URL 协议或实现单实例 IPC。"
            )
            return

        if hasattr(settings, "CronExpression"):
            self._add_line_edit(
                section.form,
                "Cron 表达式",
                settings,
                "CronExpression",
                hint="格式：分钟 小时 日期 月份 星期。例如 */5 * * * * 表示每 5 分钟触发一次。",
            )
            self._add_note_row(
                section.form,
                "Cron 表达式说明：\n"
                "当前支持 5 段 Cron：分钟 小时 日期 月份 星期。\n\n"
                "取值范围：\n"
                "• 分钟：0-59\n"
                "• 小时：0-23\n"
                "• 日期：1-31\n"
                "• 月份：1-12\n"
                "• 星期：0-7，0 和 7 都表示周日\n\n"
                "常用例子：\n"
                "• * * * * *：每分钟触发一次\n"
                "• */5 * * * *：每 5 分钟触发一次\n"
                "• 0 7 * * *：每天 07:00 触发\n"
                "• 30 21 * * 1-5：周一到周五 21:30 触发\n"
                "• 0 8 1 * *：每月 1 日 08:00 触发\n\n"
                "支持：*、逗号列表、范围、步进，例如 1,2,3、1-5、*/10、1-10/2。"
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
            hint="“且”表示所有启用的规则组都满足时才算满足；“或”表示任一满足即可。",
        )
        self._add_checkbox(
            section.form,
            "反转结果",
            ruleset,
            "IsReversed",
            hint="如果勾选，满足时算不满足，不满足时算满足。",
        )

    def _build_rule_group_editor(self, group: RuleGroup) -> None:
        section = EditorSection("规则组", "一组规则的集合。")
        self.content_layout.addWidget(section)

        self._add_checkbox(
            section.form,
            "启用",
            group,
            "IsEnabled",
            hint="取消勾选后，计算条件时会忽略此规则组。",
        )
        self._add_ruleset_mode_combo(
            section.form,
            "组内逻辑",
            group,
            "Mode",
            hint="“且”表示组内所有规则都满足时该组才算满足；“或”表示任一满足即可。",
        )
        self._add_checkbox(
            section.form,
            "反转结果",
            group,
            "IsReversed",
            hint="如果勾选，该组结果会被反转。",
        )

    def _build_rule_editor(self, rule: Rule) -> None:
        info = get_rule_info(rule.Id)
        section = EditorSection("规则", "具体的条件判断逻辑。")
        self.content_layout.addWidget(section)

        section.form.addRow(self._make_label("类型"), self._make_value_label(info.Name if info else rule.Id))
        section.form.addRow(self._make_label("ID"), self._make_subtle_value_label(rule.Id))

        self._add_checkbox(
            section.form,
            "反转结果",
            rule,
            "IsReversed",
            hint="如果勾选，此条规则的结果会被反转。",
        )

        settings = rule.Settings
        if settings is None:
            default_cls = RULE_SETTINGS_TYPES.get(rule.Id)
            if default_cls is not None:
                settings = default_cls()
                rule.Settings = settings
            else:
                self._add_note_row(section.form, "此规则没有设置项。")
                return

        if isinstance(settings, StringMatchingSettings):
            self._add_line_edit(
                section.form,
                "匹配文本",
                settings,
                "Text",
            )
            self._add_checkbox(
                section.form,
                "使用正则表达式",
                settings,
                "UseRegex",
            )
            return

        if isinstance(settings, TimeStateRuleSettings):
            self._add_time_state_combo(section.form, "目标状态", settings, "State")
            return

        if isinstance(settings, WindowStatusRuleSettings):
            combo = ComboBox()
            # 严格对齐 ClassIsland 原版顺序：0=正常, 1=最大化, 2=最小化, 3=全屏
            combo_add_item(combo, "正常 / 窗口化 (Normal)", 0)
            combo_add_item(combo, "最大化 (Maximized)", 1)
            combo_add_item(combo, "最小化 (Minimized)", 2)
            combo_add_item(combo, "全屏 (FullScreen)", 3)

            current = int(getattr(settings, "State", 0))
            idx = combo.findData(current)
            combo.setCurrentIndex(max(0, idx))

            def _on_changed(_):
                settings.State = int(combo_current_data(combo))
                self.changed.emit()

            combo.currentIndexChanged.connect(_on_changed)
            section.form.addRow(
                self._make_label("窗口状态"),
                FieldWidget(combo, "选择要求前台窗口处于哪种状态")
            )
            return

        if isinstance(settings, CurrentWeatherRuleSettings):
            combo = EditableComboBox()
            WEATHER_TYPE = {
                "0": "晴", "1": "多云", "2": "阴", "3": "阵雨", "4": "雷阵雨",
                "5": "雷阵雨伴有冰雹", "6": "雨夹雪", "7": "小雨", "8": "中雨",
                "9": "大雨", "10": "暴雨", "11": "大暴雨", "12": "特大暴雨",
                "13": "阵雪", "14": "小雪", "15": "中雪", "16": "大雪", "17": "暴雪",
                "18": "雾", "19": "冻雨", "20": "沙尘暴", "21": "小到中雨",
                "22": "中到大雨", "23": "大到暴雨", "24": "暴雨到大暴雨",
                "25": "大暴雨到特大暴雨", "26": "小到中雪", "27": "中到大雪",
                "28": "大到暴雪", "29": "浮尘", "30": "扬沙", "31": "强沙尘暴",
                "53": "霾", "99": "无",
            }
            for code, name in WEATHER_TYPE.items():
                combo_add_item(combo, f"{name} ({code})", str(code))
            # 修复点 1：读取时读 WeatherId
            current = str(getattr(settings, "WeatherId", ""))
            idx = combo.findData(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setText(current)

            def _on_changed(_):
                data = combo_current_data(combo)
                val = str(data) if data is not None else combo.text().strip()
                # 修复点 2：写入时写 WeatherId
                try:
                    settings.WeatherId = int(val)
                except ValueError:
                    settings.WeatherId = val
                self.changed.emit()

            combo.currentIndexChanged.connect(_on_changed)

            def _on_text_edited(t: str):
                val = t.strip()
                # 修复点 3：写入时写 WeatherId
                try:
                    settings.WeatherId = int(val)
                except ValueError:
                    settings.WeatherId = val
                self.changed.emit()

            combo.textChanged.connect(_on_text_edited)
            section.form.addRow(self._make_label("匹配天气"), FieldWidget(combo, "可以选择预设，或直接输入天气代码。"))
            return

        if isinstance(settings, SunRiseSetRuleSettings):
            combo = ComboBox()
            combo_add_item(combo, "日出后 / 日落前（白天）", False)
            combo_add_item(combo, "日落后 / 日出前（夜间）", True)

            current = bool(getattr(settings, "IsSunset", False))
            idx = combo.findData(current)
            combo.setCurrentIndex(max(0, idx))

            def _on_changed(_):
                settings.IsSunset = bool(combo_current_data(combo))
                self.changed.emit()

            combo.currentIndexChanged.connect(_on_changed)

            section.form.addRow(
                self._make_label("目标状态"),
                FieldWidget(combo, "选择当前时间应处于白天还是夜间。")
            )

            self._add_double_spin(
                section.form,
                "偏移时长 (分钟)",
                settings,
                "TimeMinutes",
                -9999,
                9999,
                1,
                hint="例如填入 60，表示日出/日落后 60 分钟开始判定；负数表示提前。",
            )
            return

        if isinstance(settings, RainTimeRuleSettings):
            self._add_double_spin(
                section.form,
                "时长阈值 (分钟)",
                settings,
                "RainTimeMinutes",
                0,
                999999,
                1,
                hint="下雨开始或结束的时间在这个分钟数以内时视为满足条件。",
            )
            self._add_checkbox(
                section.form,
                "判断降雨结束剩余时间",
                settings,
                "IsRemainingTime",
                hint="不勾选：判断距离降雨开始；勾选：判断距离降雨结束。",
            )
            return

        if isinstance(settings, CurrentSubjectRuleSettings):
            if not getattr(settings, "CwSubjectName", "") and getattr(settings, "SubjectId", ""):
                subject_id = str(getattr(settings, "SubjectId", "") or "").strip()
                if subject_id and subject_id != "00000000-0000-0000-0000-000000000000":
                    settings.CwSubjectName = subject_id
                    settings.SubjectId = "00000000-0000-0000-0000-000000000000"
            self._add_line_edit(
                section.form,
                "科目名称",
                settings,
                "CwSubjectName",
                hint="输入要匹配的科目名称，例如填写“数学”。",
            )
            return

        self._add_note_row(section.form, "该规则设置编辑器尚未实现。")

    # =========================================================
    # Run Action & Settings Action
    # =========================================================

    def _build_run_action_editor(self, section: EditorSection, settings: RunActionSettings) -> None:
        type_combo = ComboBox()
        combo_add_item(type_combo, "应用 (Application)", RunActionRunType.Application)
        combo_add_item(type_combo, "命令 (Command)", RunActionRunType.Command)
        combo_add_item(type_combo, "文件 (File)", RunActionRunType.File)
        combo_add_item(type_combo, "文件夹 (Folder)", RunActionRunType.Folder)
        combo_add_item(type_combo, "网页 URL (Url)", RunActionRunType.Url)

        current_type = getattr(settings, "RunType", RunActionRunType.Application)
        idx = type_combo.findData(current_type)
        type_combo.setCurrentIndex(max(0, idx))

        value_wrapper = QWidget()
        value_wrapper_layout = QVBoxLayout(value_wrapper)
        value_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        value_wrapper_layout.setSpacing(4)

        value_row = QWidget()
        value_row_layout = QHBoxLayout(value_row)
        value_row_layout.setContentsMargins(0, 0, 0, 0)
        value_row_layout.setSpacing(8)

        value_edit = LineEdit()
        value_edit.setText(str(getattr(settings, "Value", "")))
        value_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        value_row_layout.addWidget(value_edit)

        browse_btn = PushButton("浏览...")
        browse_btn.hide()
        value_row_layout.addWidget(browse_btn)

        value_hint_label = CaptionLabel("")
        value_hint_label.setWordWrap(True)

        value_wrapper_layout.addWidget(value_row)
        value_wrapper_layout.addWidget(value_hint_label)

        def _update_ui(rt: RunActionRunType) -> None:
            if rt in (RunActionRunType.Application, RunActionRunType.File):
                browse_btn.show()
            else:
                browse_btn.hide()

            hints = {
                RunActionRunType.Application: "填写可执行文件的路径，例如 C:\\Windows\\notepad.exe",
                RunActionRunType.Command: "填写要执行的 CMD/Shell 命令。",
                RunActionRunType.File: "填写要打开的文件路径。",
                RunActionRunType.Folder: "填写要用资源管理器打开的文件夹路径。",
                RunActionRunType.Url: "填写网页链接，例如 https://www.baidu.com",
            }
            value_hint_label.setText(hints.get(rt, ""))

        _update_ui(current_type)

        def _on_type_changed(_):
            rt = RunActionRunType(combo_current_data(type_combo))
            settings.RunType = rt
            _update_ui(rt)
            self.changed.emit()

        type_combo.currentIndexChanged.connect(_on_type_changed)

        def _on_value_changed(txt: str):
            settings.Value = txt
            self.changed.emit()

        value_edit.textChanged.connect(_on_value_changed)

        def _on_browse():
            rt = RunActionRunType(combo_current_data(type_combo))
            if rt == RunActionRunType.Application:
                path, _ = QFileDialog.getOpenFileName(self, "选择程序", "",
                                                      "可执行文件 (*.exe *.bat *.cmd);;所有文件 (*.*)")
            else:
                path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "所有文件 (*.*)")
            if path:
                value_edit.setText(path)

        browse_btn.clicked.connect(_on_browse)

        section.form.addRow(self._make_label("运行类型"), type_combo)
        section.form.addRow(self._make_label("运行目标"), value_wrapper)

        self._add_line_edit(
            section.form,
            "命令行参数",
            settings,
            "Args",
            hint="如果不需要传参数，请留空。",
        )

    def _build_modify_app_settings_editor(self, section: EditorSection,
                                          settings: ModifyAppSettingsActionSettings) -> None:
        combo = EditableComboBox()
        combo_add_item(combo, "是否启用自动化 [IsAutomationEnabled]", "IsAutomationEnabled")
        combo_add_item(combo, "当前配置文件名 [CurrentAutomationConfig]", "CurrentAutomationConfig")

        current_name = str(getattr(settings, "Name", ""))
        idx = combo.findData(current_name)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif current_name:
            combo.setText(current_name)

        def _on_name_changed():
            data = combo_current_data(combo)
            if data is not None:
                settings.Name = str(data)
            else:
                settings.Name = combo.text().strip()
            self.changed.emit()

        combo.currentIndexChanged.connect(_on_name_changed)
        combo.textChanged.connect(lambda _: _on_name_changed())

        section.form.addRow(
            self._make_label("设置项名称"),
            FieldWidget(combo, "选择或输入要修改的设置项对应的 JSON 字段名。"),
        )

        value_layout = QVBoxLayout()
        value_layout.setContentsMargins(0, 0, 0, 0)
        value_layout.setSpacing(4)

        raw_value_edit = LineEdit()
        raw_value_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        value_hint_label = CaptionLabel("")
        value_hint_label.setWordWrap(True)

        config_value_combo = ComboBox()
        config_value_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bool_value_box = CheckBox("设置值为 True")

        value_layout.addWidget(config_value_combo)
        value_layout.addWidget(bool_value_box)
        value_layout.addWidget(raw_value_edit)
        value_layout.addWidget(value_hint_label)

        def _update_value_ui():
            name = getattr(settings, "Name", "")
            val = getattr(settings, "Value", None)

            config_value_combo.hide()
            bool_value_box.hide()
            raw_value_edit.hide()

            if name == "IsAutomationEnabled":
                bool_value_box.show()
                bool_value_box.blockSignals(True)
                bool_value_box.setChecked(str(val).lower() == "true")
                bool_value_box.blockSignals(False)
                value_hint_label.setText("勾选表示开启自动化，取消勾选表示关闭。")
            elif name == "CurrentAutomationConfig":
                config_value_combo.show()
                config_value_combo.blockSignals(True)
                config_value_combo.clear()
                try:
                    configs = self.window().automation_runtime.context.settings._conf.list_configs()
                except Exception:
                    try:
                        from file import config_center
                        cw_home = config_center.CW_HOME
                        import os
                        folder = cw_home / "config" / "Automations"
                        if folder.exists():
                            configs = [f[:-5] for f in os.listdir(folder) if f.endswith(".json")]
                        else:
                            configs = ["Default"]
                    except Exception:
                        configs = ["Default"]

                for c in configs:
                    config_value_combo.addItem(c)
                idx = config_value_combo.findText(str(val))
                if idx >= 0:
                    config_value_combo.setCurrentIndex(idx)
                config_value_combo.blockSignals(False)
                value_hint_label.setText("选择要切换到的自动化配置文件。")
            else:
                raw_value_edit.show()
                raw_value_edit.blockSignals(True)
                raw_value_edit.setText(str(val) if val is not None else "")
                raw_value_edit.blockSignals(False)
                value_hint_label.setText("输入原始字符串值（暂不支持复杂类型对象）。")

        _update_value_ui()
        combo.currentIndexChanged.connect(_update_value_ui)
        combo.lineEdit().textChanged.connect(_update_value_ui)

        def _on_bool_changed(state):
            settings.Value = (state == Qt.Checked)
            self.changed.emit()

        def _on_config_val_changed(idx):
            settings.Value = config_value_combo.itemText(idx)
            self.changed.emit()

        def _on_raw_changed(txt):
            settings.Value = txt
            self.changed.emit()

        bool_value_box.stateChanged.connect(_on_bool_changed)
        config_value_combo.currentIndexChanged.connect(_on_config_val_changed)
        raw_value_edit.textChanged.connect(_on_raw_changed)

        section.form.addRow(self._make_label("新值"), value_layout)

    # =========================================================
    # UI Helpers
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
        return label

    def _add_note_row(self, form: QFormLayout, text: str) -> None:
        note = CaptionLabel(text)
        note.setWordWrap(True)
        form.addRow(note)

    def _create_styled_double_spin(self, minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
        spin = DoubleSpinBox()
        spin.setMinimum(minimum)
        spin.setMaximum(maximum)
        spin.setSingleStep(step)
        return spin

    def _add_line_edit(
            self,
            form: QFormLayout,
            title: str,
            obj: Any,
            attr: str,
            hint: str = "",
    ) -> None:
        edit = LineEdit()
        edit.setText(str(getattr(obj, attr, "")))

        def _on_changed(text: str):
            setattr(obj, attr, text)
            self.changed.emit()

        edit.textChanged.connect(_on_changed)
        form.addRow(self._make_label(title), FieldWidget(edit, hint))

    def _add_checkbox(
            self,
            form: QFormLayout,
            title: str,
            obj: Any,
            attr: str,
            hint: str = "",
    ) -> None:
        box = CheckBox(title)
        box.setChecked(bool(getattr(obj, attr, False)))

        def _on_changed(state: int):
            setattr(obj, attr, state == Qt.Checked)
            self.changed.emit()

        box.stateChanged.connect(_on_changed)
        form.addRow(self._make_label(""), FieldWidget(box, hint))

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
        spin = DoubleSpinBox()
        spin.setMinimum(minimum)
        spin.setMaximum(maximum)
        spin.setSingleStep(step)
        spin.setValue(float(getattr(obj, attr, 0.0) or 0.0))

        def _on_changed(val: float):
            setattr(obj, attr, val)
            self.changed.emit()

        spin.valueChanged.connect(_on_changed)
        form.addRow(self._make_label(title), FieldWidget(spin, hint))

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
        combo_add_item(combo, "或 (Or)", RulesetLogicalMode.Or)
        combo_add_item(combo, "且 (And)", RulesetLogicalMode.And)

        try:
            current = RulesetLogicalMode.from_value(getattr(obj, attr, RulesetLogicalMode.Or))
        except Exception:
            current = RulesetLogicalMode.Or
        setattr(obj, attr, current)

        idx = combo.findData(current)
        combo.setCurrentIndex(max(0, idx))

        def _on_changed(_):
            try:
                selected = RulesetLogicalMode.from_value(combo_current_data(combo))
            except Exception:
                selected = RulesetLogicalMode.Or
            setattr(obj, attr, selected)
            self.changed.emit()

        combo.currentIndexChanged.connect(_on_changed)
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
        combo_add_item(combo, "无 (None)", TimeState.None_)
        combo_add_item(combo, "上课中 (OnClass)", TimeState.OnClass)
        combo_add_item(combo, "课间休息 (Breaking)", TimeState.Breaking)
        combo_add_item(combo, "已放学 (AfterSchool)", TimeState.AfterSchool)

        try:
            current = TimeState.from_value(getattr(obj, attr, TimeState.None_))
        except Exception:
            current = TimeState.None_

        if current == TimeState.PrepareOnClass:
            current = TimeState.OnClass

        setattr(obj, attr, current)

        idx = combo.findData(current)
        combo.setCurrentIndex(max(0, idx))

        def _on_changed(_):
            try:
                selected = TimeState.from_value(combo_current_data(combo))
            except Exception:
                selected = TimeState.None_
            setattr(obj, attr, selected)
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


class DoubleSpinBox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDecimals(1)

    def value(self) -> float:
        return super().value()

    def setValue(self, val: float) -> None:
        super().setValue(float(val))

