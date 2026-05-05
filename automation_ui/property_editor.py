from __future__ import annotations

import sys
from typing import Any

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,QSizePolicy,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    LineEdit,
    StrongBodyLabel,
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
        else:
            section = EditorSection("参数设置", "暂不支持此对象编辑。")
            self.content_layout.addWidget(section)
            self.content_layout.addStretch(1)

    #=========================================================
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
        )# =========================================================
    # Trigger
    # =========================================================

    def _build_trigger_editor(self, trigger: TriggerSettings) -> None:
        info = get_trigger_info(trigger.Id)
        section = EditorSection("触发器", "决定工作流在什么时候触发。")
        self.content_layout.addWidget(section)

        section.form.addRow(self._make_label("类型"), QLabel(info.Name if info else trigger.Id))
        section.form.addRow(self._make_label("ID"), QLabel(trigger.Id))

        settings = trigger.Settings
        if settings is None:
            section.form.addRow(QLabel("此触发器没有设置项"))
            return

        if isinstance(settings, SignalTriggerSettings):
            self._add_line_edit(
                section.form,
                "信号名",
                settings,
                "SignalName",
                hint="用于和广播信号动作配对。名称必须完全一致，例如 demo-signal。",
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
                hint="显示在托盘菜单中的文字，例如测试天气提醒。",
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
            self._add_time_state_combo(
                section.form,
                "目标状态",
                settings,
                "TargetState",
                hint="选择要提前监听的状态，例如 OnClass 表示上课前。",
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

        section.form.addRow(QLabel("该触发器设置编辑器尚未实现"))

    # =========================================================
    # Action
    # =========================================================

    def _build_action_editor(self, action: ActionItem) -> None:
        info = get_action_info(action.Id)
        section = EditorSection("动作", "触发后执行的动作，按顺序串行运行。")
        self.content_layout.addWidget(section)

        section.form.addRow(self._make_label("类型"), QLabel(info.Name if info else action.Id))
        section.form.addRow(self._make_label("ID"), QLabel(action.Id))

        settings = action.Settings
        if settings is None:
            section.form.addRow(QLabel("此动作没有设置项"))
            return

        if isinstance(settings, NotificationActionSettings):
            self._add_line_edit(
                section.form,
                "Mask",
                settings,
                "Mask",
                hint="短提示文字，通常显示在提醒的简要部分，例如上课提醒。",
            )
            self._add_line_edit(
                section.form,
                "Content",
                settings,
                "Content",
                hint="详细提醒内容，可留空。通常用于正文部分。",
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
                "正文语音",
                settings,
                "IsContentSpeechEnabled",
                hint="勾选后，会朗读正文内容。",
            )
            self._add_checkbox(
                section.form,
                "遮罩语音",
                settings,
                "IsMaskSpeechEnabled",
                hint="勾选后，会朗读 Mask 内容。",
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
                "Mask时长(秒)",
                settings,
                "MaskDurationSeconds",
                0,
                999,
                1,
                hint="Mask 简要提示显示多久。",
            )
            self._add_double_spin(
                section.form,
                "正文时长(秒)",
                settings,
                "ContentDurationSeconds",
                0,
                999,
                1,
                hint="正文内容显示多久。",
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
            self._add_line_edit(
                section.form,
                "设置名",
                settings,
                "Name",
                hint="填写要修改的设置字段名。当前版本先使用内部字段名，后续可接入下拉选择。",
            )
            self._add_line_edit(
                section.form,
                "值",
                settings,
                "Value",
                cast_to_str=True,
                hint="填写要写入的新值；系统会按目标设置字段的类型进行转换。",
            )
            self._add_int_spin(
                section.form,
                "模式",
                settings,
                "Mode",
                0,
                999,
                hint="当前版本保留此字段，通常不需要修改。",
            )
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
                hint="要广播的信号名称。其它SignalTrigger 只有名称完全一致才会响应。",
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
                hint="勾选后按静默重启模式执行。是否完全静默取决于主程序实现。",
            )
            return

        section.form.addRow(QLabel("该动作设置编辑器尚未实现"))

    # =========================================================
    # RunAction 专用编辑器 —— 对齐 ClassIsland RunActionSettingsControl
    # =========================================================

    def _build_run_action_editor(self, section: EditorSection, settings: RunActionSettings) -> None:
        #---- 运行类型下拉 ----
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

        # ---- 值：输入框 +浏览按钮 ----
        value_row = QWidget()
        value_row_layout = QHBoxLayout(value_row)
        value_row_layout.setContentsMargins(0, 0, 0, 0)
        value_row_layout.setSpacing(6)

        value_edit = LineEdit()
        value_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        current_val = getattr(settings, "Value", "")
        value_edit.setText("" if current_val is None else str(current_val))
        value_row_layout.addWidget(value_edit)

        browse_btn = QPushButton("浏览…")
        browse_btn.setFixedWidth(72)
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

        value_label = self._make_label("值")
        section.form.addRow(value_label, value_wrapper)

        # ---- 参数输入框 ----
        args_edit = LineEdit()
        args_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        current_args = getattr(settings, "Args", "")
        args_edit.setText("" if current_args is None else str(current_args))

        args_hint_widget = FieldWidget(args_edit, "（可选）应用程序启动参数")
        args_label = self._make_label("参数")
        section.form.addRow(args_label, args_hint_widget)

        # ---- 根据 RunType 更新 UI状态 ----
        def _update_ui():
            rt = combo_current_data(type_combo)
            rt_val = rt.value if hasattr(rt, "value") else str(rt)

            if rt_val == "Application":
                value_edit.setPlaceholderText("应用程序路径")
                value_hint_label.setText(
                    "填写可执行文件路径，或点击浏览…选择。"
                )
                browse_btn.setVisible(True)
                args_label.setVisible(True)
                args_hint_widget.setVisible(True)
            elif rt_val == "File":
                value_edit.setPlaceholderText("文件路径")
                value_hint_label.setText(
                    "填写文件路径，或点击浏览…选择。系统会用默认程序打开。"
                )
                browse_btn.setVisible(True)
                args_label.setVisible(False)
                args_hint_widget.setVisible(False)
            elif rt_val == "Folder":
                value_edit.setPlaceholderText("文件夹路径")
                value_hint_label.setText(
                    "填写文件夹路径，或点击浏览…选择。系统会用文件管理器打开。"
                )
                browse_btn.setVisible(True)
                args_label.setVisible(False)
                args_hint_widget.setVisible(False)
            elif rt_val == "Url":
                value_edit.setPlaceholderText("https://example.com")
                value_hint_label.setText(
                    "填写网页地址。如果不包含协议前缀，会自动添加 https://。"
                )
                browse_btn.setVisible(False)
                args_label.setVisible(False)
                args_hint_widget.setVisible(False)
            elif rt_val == "Command":
                if sys.platform == "win32":
                    value_edit.setPlaceholderText("cmd命令")
                else:
                    value_edit.setPlaceholderText("终端命令")
                value_hint_label.setText(
                    "填写要执行的完整命令。Windows 使用 cmd.exe，Linux/macOS 使用 bash。"
                )
                browse_btn.setVisible(False)
                args_label.setVisible(False)
                args_hint_widget.setVisible(False)
            else:
                value_edit.setPlaceholderText("")
                value_hint_label.setText("")
                browse_btn.setVisible(False)
                args_label.setVisible(False)
                args_hint_widget.setVisible(False)

        # ---- 浏览按钮点击 ----
        def _on_browse():
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
                    filter_str = "应用程序 (*.app);;可执行文件 (*);;所有文件 (*)"
                else:
                    filter_str = "所有文件 (*)"
                path, _ = QFileDialog.getOpenFileName(
                    self, "选择应用程序", value_edit.text(), filter_str
                )
                if path:
                    value_edit.setText(path)

            else:
                # File
                path, _ = QFileDialog.getOpenFileName(
                    self, "选择文件", value_edit.text(), "所有文件 (*)"
                )
                if path:
                    value_edit.setText(path)

        browse_btn.clicked.connect(_on_browse)

        # ---- 信号连接 ----
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

        type_combo.currentIndexChanged.connect(_on_type_changed)
        value_edit.textChanged.connect(_on_value_changed)
        args_edit.textChanged.connect(_on_args_changed)

        # ---- 初始化 UI状态 ----
        _update_ui()

    # =========================================================
    # Widgets
    # =========================================================

    def _make_label(self, text: str) -> BodyLabel:
        label = BodyLabel(text)
        label.setWordWrap(True)
        label.setMinimumWidth(112)
        label.setMaximumWidth(132)
        return label

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
        spin = QDoubleSpinBox()
        spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setDecimals(2if step< 1 else 0)

        try:
            spin.setValue(float(getattr(obj, attr, 0)))
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
        spin = QSpinBox()
        spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        spin.setRange(minimum, maximum)
        try:
            spin.setValue(int(getattr(obj, attr, 0)))
        except Exception:
            spin.setValue(0)

        def _on_changed(value: int):
            setattr(obj, attr, int(value))
            self.changed.emit()

        spin.valueChanged.connect(_on_changed)
        form.addRow(self._make_label(title), FieldWidget(spin, hint))

    def _add_time_state_combo(self, form: QFormLayout, title: str, obj: Any, attr: str, hint: str = "") -> None:
        combo = ComboBox()
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo_add_item(combo, "None", TimeState.None_)
        combo_add_item(combo, "OnClass", TimeState.OnClass)
        combo_add_item(combo, "PrepareOnClass", TimeState.PrepareOnClass)
        combo_add_item(combo, "Breaking", TimeState.Breaking)
        combo_add_item(combo, "AfterSchool", TimeState.AfterSchool)

        current = getattr(obj, attr, TimeState.OnClass)
        idx = combo.findData(current)
        combo.setCurrentIndex(max(0, idx))

        def _on_changed(_):
            setattr(obj, attr, combo_current_data(combo))
            self.changed.emit()

        combo.currentIndexChanged.connect(_on_changed)
        form.addRow(self._make_label(title), FieldWidget(combo, hint))
