from __future__ import annotations

from typing import Any

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    ComboBox,
    LineEdit,
    SmoothScrollArea,
)

from automation.enums import RunActionRunType, TimeState
from automation.models import (
    ActionItem,
    AppRestartActionSettings,
    ModifyAppSettingsActionSettings,
    NotificationActionSettings,
    PreTimePointTriggerSettings,
    RunActionSettings,
    SignalTriggerSettings,
    SleepActionSettings,
    TrayMenuTriggerSettings,
    TriggerSettings,
    UriTriggerSettings,
    WeatherNotificationActionSettings,
    Workflow,
)
from automation.registry import get_action_info, get_trigger_info


class EditorSection(QFrame):
    def __init__(self, title: str, desc: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AutomationEditorSection")
        self.setStyleSheet(
            """
            QFrame#AutomationEditorSection {
                background: rgba(255, 255, 255, 0.72);
                border: 1px solid rgba(0, 0, 0, 0.05);
                border-radius: 10px;
            }
            """
        )
        self.layout_root = QVBoxLayout(self)
        self.layout_root.setContentsMargins(12, 12, 12, 12)
        self.layout_root.setSpacing(8)

        self.title_label = BodyLabel(title)
        self.title_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.layout_root.addWidget(self.title_label)

        if desc:
            self.desc_label = BodyLabel(desc)
            self.desc_label.setWordWrap(True)
            self.desc_label.setStyleSheet("color: #666; font-size: 12px;")
            self.layout_root.addWidget(self.desc_label)

        self.form = QFormLayout()
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setSpacing(10)
        self.layout_root.addLayout(self.form)


class AutomationPropertyEditor(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._kind: str | None = None
        self._target: Any = None

        self.scroll = SmoothScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)

        self.scroll.setWidget(self.content)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.scroll)

    def set_target(self, kind: str | None, target: Any) -> None:
        self._kind = kind
        self._target = target
        self._rebuild()

    # =========================================================
    # Build
    # =========================================================

    def _clear_content(self) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _rebuild(self) -> None:
        self._clear_content()

        if self._kind is None or self._target is None:
            section = EditorSection("属性", "请选择左侧要编辑的对象")
            self.content_layout.addWidget(section)
            self.content_layout.addStretch(1)
            return

        if self._kind == "workflow":
            self._build_workflow_editor(self._target)
        elif self._kind == "trigger":
            self._build_trigger_editor(self._target)
        elif self._kind == "action":
            self._build_action_editor(self._target)
        else:
            section = EditorSection("属性", "暂不支持此对象编辑")
            self.content_layout.addWidget(section)

        self.content_layout.addStretch(1)

    # =========================================================
    # Workflow
    # =========================================================

    def _build_workflow_editor(self, workflow: Workflow) -> None:
        section = EditorSection("工作流", "工作流对应一个 ActionSet，可包含多个触发器、条件和动作。")
        self.content_layout.addWidget(section)

        self._add_line_edit(section.form, "名称", workflow.ActionSet, "Name")
        self._add_checkbox(section.form, "启用", workflow.ActionSet, "IsEnabled")
        self._add_checkbox(section.form, "启用恢复", workflow.ActionSet, "IsRevertEnabled")
        self._add_checkbox(section.form, "启用条件", workflow, "IsConditionEnabled")

        hint = EditorSection("条件（规则集）", "第一阶段 UI 先保留入口。")
        hint.form.addRow(QLabel("完整规则集编辑器将在下一阶段补齐。"))
        self.content_layout.addWidget(hint)

    # =========================================================
    # Trigger
    # =========================================================

    def _build_trigger_editor(self, trigger: TriggerSettings) -> None:
        info = get_trigger_info(trigger.Id)
        section = EditorSection("触发器", "用于决定工作流在什么时候触发。")
        self.content_layout.addWidget(section)

        section.form.addRow("类型", QLabel(info.Name if info else trigger.Id))
        section.form.addRow("ID", QLabel(trigger.Id))

        settings = trigger.Settings
        if settings is None:
            section.form.addRow(QLabel("此触发器没有设置项"))
            return

        if isinstance(settings, SignalTriggerSettings):
            self._add_line_edit(section.form, "信号名", settings, "SignalName")
            self._add_checkbox(section.form, "是否为恢复触发", settings, "IsRevert")
            return

        if isinstance(settings, TrayMenuTriggerSettings):
            self._add_line_edit(section.form, "菜单标题", settings, "Header")
            self._add_checkbox(section.form, "点击触发恢复", settings, "IsRevert")
            return

        if isinstance(settings, UriTriggerSettings):
            self._add_line_edit(section.form, "URI 后缀", settings, "UriSuffix")
            return

        if hasattr(settings, "CronExpression"):
            self._add_line_edit(section.form, "Cron 表达式", settings, "CronExpression")
            return

        if isinstance(settings, PreTimePointTriggerSettings):
            self._add_time_state_combo(section.form, "目标状态", settings, "TargetState")
            self._add_double_spin(section.form, "提前秒数", settings, "TimeSeconds", minimum=0, maximum=999999, step=1)
            return

        section.form.addRow(QLabel("该触发器设置编辑器尚未实现"))

    # =========================================================
    # Action
    # =========================================================

    def _build_action_editor(self, action: ActionItem) -> None:
        info = get_action_info(action.Id)
        section = EditorSection("动作", "触发后执行的动作，按顺序串行运行。")
        self.content_layout.addWidget(section)

        section.form.addRow("类型", QLabel(info.Name if info else action.Id))
        section.form.addRow("ID", QLabel(action.Id))

        settings = action.Settings
        if settings is None:
            section.form.addRow(QLabel("此动作没有设置项"))
            return

        if isinstance(settings, NotificationActionSettings):
            self._add_line_edit(section.form, "Mask", settings, "Mask")
            self._add_line_edit(section.form, "Content", settings, "Content")
            self._add_checkbox(section.form, "等待完成", settings, "IsWaitForCompleteEnabled")
            self._add_checkbox(section.form, "高级设置", settings, "IsAdvancedSettingsEnabled")
            self._add_checkbox(section.form, "正文语音", settings, "IsContentSpeechEnabled")
            self._add_checkbox(section.form, "遮罩语音", settings, "IsMaskSpeechEnabled")
            self._add_checkbox(section.form, "音效", settings, "IsSoundEffectEnabled")
            self._add_checkbox(section.form, "置顶", settings, "IsTopmostEnabled")
            self._add_double_spin(section.form, "Mask时长(秒)", settings, "MaskDurationSeconds", 0, 999, 1)
            self._add_double_spin(section.form, "正文时长(秒)", settings, "ContentDurationSeconds", 0, 999, 1)
            return

        if isinstance(settings, WeatherNotificationActionSettings):
            combo = ComboBox()
            combo.addItem("三天天气预报", 0)
            combo.addItem("天气预警", 1)
            combo.addItem("逐小时天气", 2)
            current = int(getattr(settings, "NotificationKind", 0))
            idx = combo.findData(current)
            combo.setCurrentIndex(max(0, idx))

            def _on_changed(_):
                settings.NotificationKind = int(combo.currentData())
                self.changed.emit()

            combo.currentIndexChanged.connect(_on_changed)
            section.form.addRow("天气提醒类型", combo)
            return

        if isinstance(settings, RunActionSettings):
            combo = ComboBox()
            combo.addItem("应用程序", RunActionRunType.Application)
            combo.addItem("命令", RunActionRunType.Command)
            combo.addItem("文件", RunActionRunType.File)
            combo.addItem("文件夹", RunActionRunType.Folder)
            combo.addItem("URL", RunActionRunType.Url)

            current_value = settings.RunType
            idx = 0
            for i in range(combo.count()):
                if combo.itemData(i) == current_value:
                    idx = i
                    break
            combo.setCurrentIndex(idx)

            def _on_changed(_):
                settings.RunType = combo.currentData()
                self.changed.emit()

            combo.currentIndexChanged.connect(_on_changed)
            section.form.addRow("运行类型", combo)
            self._add_line_edit(section.form, "值", settings, "Value")
            self._add_line_edit(section.form, "参数", settings, "Args")
            return

        if isinstance(settings, ModifyAppSettingsActionSettings):
            self._add_line_edit(section.form, "设置名", settings, "Name")
            self._add_line_edit(section.form, "值", settings, "Value", cast_to_str=True)
            self._add_int_spin(section.form, "模式", settings, "Mode", 0, 999)
            return

        if isinstance(settings, SleepActionSettings):
            self._add_double_spin(section.form, "等待秒数", settings, "Value", 0, 999999, 1)
            return

        if isinstance(settings, SignalTriggerSettings):
            self._add_line_edit(section.form, "信号名", settings, "SignalName")
            self._add_checkbox(section.form, "是否广播恢复", settings, "IsRevert")
            return

        if isinstance(settings, AppRestartActionSettings):
            self._add_checkbox(section.form, "静默重启", settings, "Value")
            return

        section.form.addRow(QLabel("该动作设置编辑器尚未实现"))

    # =========================================================
    # Widgets
    # =========================================================

    def _make_label(self, text: str) -> BodyLabel:
        label = BodyLabel(text)
        label.setWordWrap(True)
        return label

    def _add_line_edit(self, form: QFormLayout, title: str, obj: Any, attr: str, cast_to_str: bool = False) -> None:
        edit = LineEdit()
        current = getattr(obj, attr, "")
        edit.setText("" if current is None else str(current))

        def _on_changed(text: str):
            setattr(obj, attr, text if cast_to_str else text)
            self.changed.emit()

        edit.textChanged.connect(_on_changed)
        form.addRow(self._make_label(title), edit)

    def _add_checkbox(self, form: QFormLayout, title: str, obj: Any, attr: str) -> None:
        box = CheckBox()
        box.setChecked(bool(getattr(obj, attr, False)))

        def _on_changed(state: bool):
            setattr(obj, attr, bool(state))
            self.changed.emit()

        box.toggled.connect(_on_changed)
        form.addRow(self._make_label(title), box)

    def _add_double_spin(
        self,
        form: QFormLayout,
        title: str,
        obj: Any,
        attr: str,
        minimum: float,
        maximum: float,
        step: float,
    ) -> None:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setDecimals(2 if step < 1 else 0)

        try:
            spin.setValue(float(getattr(obj, attr, 0)))
        except Exception:
            spin.setValue(0)

        def _on_changed(value: float):
            setattr(obj, attr, float(value))
            self.changed.emit()

        spin.valueChanged.connect(_on_changed)
        form.addRow(self._make_label(title), spin)

    def _add_int_spin(self, form: QFormLayout, title: str, obj: Any, attr: str, minimum: int, maximum: int) -> None:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        try:
            spin.setValue(int(getattr(obj, attr, 0)))
        except Exception:
            spin.setValue(0)

        def _on_changed(value: int):
            setattr(obj, attr, int(value))
            self.changed.emit()

        spin.valueChanged.connect(_on_changed)
        form.addRow(self._make_label(title), spin)

    def _add_time_state_combo(self, form: QFormLayout, title: str, obj: Any, attr: str) -> None:
        combo = ComboBox()
        combo.addItem("None", TimeState.None_)
        combo.addItem("OnClass", TimeState.OnClass)
        combo.addItem("PrepareOnClass", TimeState.PrepareOnClass)
        combo.addItem("Breaking", TimeState.Breaking)
        combo.addItem("AfterSchool", TimeState.AfterSchool)

        current = getattr(obj, attr, TimeState.OnClass)
        idx = 0
        for i in range(combo.count()):
            if combo.itemData(i) == current:
                idx = i
                break
        combo.setCurrentIndex(idx)

        def _on_changed(_):
            setattr(obj, attr, combo.currentData())
            self.changed.emit()

        combo.currentIndexChanged.connect(_on_changed)
        form.addRow(self._make_label(title), combo)
