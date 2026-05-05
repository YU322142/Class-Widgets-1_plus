from __future__ import annotations

from typing import Any

import list_
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QListWidgetItem,
    QMessageBox,
    QSpinBox,
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
    LineEdit,
    ListWidget,
    PushButton,
    StrongBodyLabel,
)

from automation.builtins import register_builtins
from automation.compat import RULE_SETTINGS_TYPES
from automation.enums import RulesetLogicalMode, TimeState
from automation.models import (
    CurrentSubjectRuleSettings,
    CurrentWeatherRuleSettings,
    RainTimeRuleSettings,
    Rule,
    RuleGroup,
    StringMatchingSettings,
    SunRiseSetRuleSettings,
    TimeStateRuleSettings,
    WindowStatusRuleSettings,
    Workflow,
)
from automation.registry import get_registered_rule_ids, get_rule_info
from file import config_center


RULE_GROUPS: dict[str, list[str]] = {
    "窗口": [
        "classisland.windows.className",
        "classisland.windows.text",
        "classisland.windows.status",
        "classisland.windows.processName",
    ],
    "课程": [
        "classisland.lessons.currentSubject",
        "classisland.lessons.nextSubject",
        "classisland.lessons.previousSubject",
        "classisland.lessons.timeState",
    ],
    "天气": [
        "classisland.weather.currentWeather",
        "classisland.weather.hasWeatherAlert",
        "classisland.weather.rainTime",
        "classisland.weather.sunRiseSet",
    ],
    "测试": [
        "classisland.test.true",
        "classisland.test.false",
    ],
}

RULE_DESCRIPTIONS: dict[str, str] = {
    "classisland.windows.className": "前台窗口类名匹配。",
    "classisland.windows.text": "前台窗口标题匹配。",
    "classisland.windows.status": "前台窗口状态是否为正常 / 最大化 / 最小化 / 全屏。",
    "classisland.windows.processName": "前台窗口进程名匹配。",
    "classisland.lessons.currentSubject": "当前课程科目匹配（CW 当前按科目显示名称比较，不是 CI 的科目对象语义）。",
    "classisland.lessons.nextSubject": "下节课科目匹配（CW 当前按科目显示名称比较）。",
    "classisland.lessons.previousSubject": "上节课科目匹配（CW 当前按科目显示名称比较）。",
    "classisland.lessons.timeState": "当前时间状态匹配。",
    "classisland.weather.currentWeather": "当前天气类型匹配（当前实现按精确天气代码比较）。",
    "classisland.weather.hasWeatherAlert": "天气预警文本匹配。",
    "classisland.weather.rainTime": "距离下雨开始/结束的时间范围判断。",
    "classisland.weather.sunRiseSet": "当前是否日出后 / 日落后。",
    "classisland.test.true": "始终为真（测试用）。",
    "classisland.test.false": "始终为假（测试用）。",
}

RULE_NAME_FALLBACKS: dict[str, str] = {
    "classisland.windows.className": "前台窗口类名",
    "classisland.windows.text": "前台窗口标题",
    "classisland.windows.status": "前台窗口状态是",
    "classisland.windows.processName": "前台窗口进程",
    "classisland.lessons.currentSubject": "当前科目是",
    "classisland.lessons.nextSubject": "下节课科目是",
    "classisland.lessons.previousSubject": "上节课科目是",
    "classisland.lessons.timeState": "当前时间状态是",
    "classisland.weather.currentWeather": "当前天气是",
    "classisland.weather.hasWeatherAlert": "存在天气预警",
    "classisland.weather.rainTime": "距离降雨开始/结束还剩",
    "classisland.weather.sunRiseSet": "是否日出/日落",
    "classisland.test.true": "总是为真",
    "classisland.test.false": "总是为假",
}


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


class RulePickerDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        register_builtins()

        self.setWindowTitle("选择规则")
        self.resize(760, 480)
        self.selected_rule_id: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = StrongBodyLabel("选择规则")
        root.addWidget(title)

        tip = CaptionLabel("先选择左侧分组，再选择右侧具体规则。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #666;")
        root.addWidget(tip)

        body = QHBoxLayout()
        root.addLayout(body, 1)

        self.group_list = ListWidget()
        self.group_list.setMinimumWidth(180)
        self.rule_list = ListWidget()

        body.addWidget(self.group_list, 2)
        body.addWidget(self.rule_list, 4)

        self.desc_label = CaptionLabel("请选择一个规则后，这里会显示它的用途。")
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #666;")
        root.addWidget(self.desc_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.ok_btn = PushButton("确定")
        self.cancel_btn = PushButton("取消")
        self.ok_btn.setEnabled(False)
        btn_row.addWidget(self.ok_btn)
        btn_row.addWidget(self.cancel_btn)
        root.addLayout(btn_row)

        self.group_list.currentRowChanged.connect(self._on_group_changed)
        self.rule_list.currentRowChanged.connect(self._on_rule_changed)
        self.rule_list.itemDoubleClicked.connect(lambda _: self._accept_current())
        self.ok_btn.clicked.connect(self._accept_current)
        self.cancel_btn.clicked.connect(self.reject)

        for group_name in self._available_groups().keys():
            self.group_list.addItem(group_name)

        if self.group_list.count() > 0:
            self.group_list.setCurrentRow(0)

    def _available_groups(self) -> dict[str, list[str]]:
        result = {k: v[:] for k, v in RULE_GROUPS.items()}

        registered = set(get_registered_rule_ids())
        known = {rid for ids in RULE_GROUPS.values() for rid in ids}
        extras = [rid for rid in sorted(registered) if rid not in known]
        if extras:
            result["其它"] = extras

        return result

    def _rule_name(self, rule_id: str) -> str:
        info = get_rule_info(rule_id)
        if info and getattr(info, "Name", None):
            return info.Name
        return RULE_NAME_FALLBACKS.get(rule_id, rule_id)

    def _on_group_changed(self, row: int) -> None:
        self.rule_list.clear()
        self.desc_label.setText("请选择一个规则后，这里会显示它的用途。")
        self.ok_btn.setEnabled(False)

        if row < 0:
            return

        groups = self._available_groups()
        group_name = self.group_list.item(row).text()
        ids = groups.get(group_name, [])

        for rule_id in ids:
            item = QListWidgetItem(self._rule_name(rule_id))
            item.setData(Qt.UserRole, rule_id)
            item.setToolTip(rule_id)
            self.rule_list.addItem(item)

        if self.rule_list.count() > 0:
            self.rule_list.setCurrentRow(0)

    def _on_rule_changed(self, row: int) -> None:
        item = self.rule_list.item(row)
        if item is None:
            self.desc_label.setText("请选择一个规则后，这里会显示它的用途。")
            self.ok_btn.setEnabled(False)
            return

        rule_id = item.data(Qt.UserRole)
        self.desc_label.setText(RULE_DESCRIPTIONS.get(rule_id, f"规则 ID：{rule_id}"))
        self.ok_btn.setEnabled(True)

    def _accept_current(self) -> None:
        item = self.rule_list.currentItem()
        if item is None:
            QMessageBox.warning(self, "选择规则", "请先选择一个规则。")
            return

        self.selected_rule_id = item.data(Qt.UserRole)
        self.accept()


class RulesetEditor(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        register_builtins()

        self._workflow: Workflow | None = None
        self._current_group_index: int = -1
        self._current_rule_index: int = -1
        self._updating = False

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.status_label = CaptionLabel("未选择工作流。")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #666;")
        root.addWidget(self.status_label)

        global_row = QHBoxLayout()
        global_row.setSpacing(10)
        self.mode_combo = ComboBox()
        combo_add_item(self.mode_combo, "任意组满足即可（OR）", RulesetLogicalMode.Or)
        combo_add_item(self.mode_combo, "所有组都要满足（AND）", RulesetLogicalMode.And)

        self.reverse_box = CheckBox("反转整个规则集结果")
        global_row.addWidget(BodyLabel("规则集逻辑"))
        global_row.addWidget(self.mode_combo, 1)
        global_row.addWidget(self.reverse_box)
        root.addLayout(global_row)

        self.enable_condition_box = CheckBox("启用当前工作流条件")
        root.addWidget(self.enable_condition_box)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)
        self.main_splitter.setStyleSheet("QSplitter::handle { background: transparent; }")
        root.addWidget(self.main_splitter)

        # 左：规则组
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        group_header = StrongBodyLabel("规则组")
        left_layout.addWidget(group_header)

        self.group_list = ListWidget()
        self.group_list.setAlternatingRowColors(True)
        self.group_list.setMinimumHeight(120)
        left_layout.addWidget(self.group_list, 1)

        group_btns = QHBoxLayout()
        self.add_group_btn = PushButton("添加规则组")
        self.del_group_btn = PushButton("删除规则组")
        group_btns.addWidget(self.add_group_btn)
        group_btns.addWidget(self.del_group_btn)
        left_layout.addLayout(group_btns)

        group_move_btns = QHBoxLayout()
        self.group_up_btn = PushButton("上移")
        self.group_down_btn = PushButton("下移")
        group_move_btns.addWidget(self.group_up_btn)
        group_move_btns.addWidget(self.group_down_btn)
        left_layout.addLayout(group_move_btns)

        self.group_enabled_box = CheckBox("启用当前规则组")
        self.group_reverse_box = CheckBox("反转当前规则组结果")
        left_layout.addWidget(self.group_enabled_box)
        left_layout.addWidget(self.group_reverse_box)

        mode_row = QHBoxLayout()
        mode_row.addWidget(BodyLabel("组逻辑"))
        self.group_mode_combo = ComboBox()
        combo_add_item(self.group_mode_combo, "任意规则满足即可（OR）", RulesetLogicalMode.Or)
        combo_add_item(self.group_mode_combo, "所有规则都要满足（AND）", RulesetLogicalMode.And)
        mode_row.addWidget(self.group_mode_combo, 1)
        left_layout.addLayout(mode_row)

        self.main_splitter.addWidget(self.left_panel)

        # 右：规则列表 + 当前规则参数
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        rule_header = StrongBodyLabel("规则")
        right_layout.addWidget(rule_header)

        self.rule_list = ListWidget()
        self.rule_list.setAlternatingRowColors(True)
        self.rule_list.setMinimumHeight(140)
        self.rule_list.setMaximumHeight(200)
        right_layout.addWidget(self.rule_list)

        rule_btns = QHBoxLayout()
        self.add_rule_btn = PushButton("添加规则")
        self.del_rule_btn = PushButton("删除规则")
        self.rule_up_btn = PushButton("上移")
        self.rule_down_btn = PushButton("下移")
        rule_btns.addWidget(self.add_rule_btn)
        rule_btns.addWidget(self.del_rule_btn)
        rule_btns.addWidget(self.rule_up_btn)
        rule_btns.addWidget(self.rule_down_btn)
        right_layout.addLayout(rule_btns)

        self.rule_name_label = StrongBodyLabel("当前规则：未选择")
        right_layout.addWidget(self.rule_name_label)

        self.rule_desc_label = CaptionLabel("请选择一个规则后，这里会显示它的用途。")
        self.rule_desc_label.setWordWrap(True)
        self.rule_desc_label.setStyleSheet("color: #666;")
        right_layout.addWidget(self.rule_desc_label)

        rule_meta_row = QHBoxLayout()
        self.change_rule_btn = PushButton("更换规则类型")
        self.rule_reverse_box = CheckBox("反转当前规则结果")
        rule_meta_row.addWidget(self.change_rule_btn)
        rule_meta_row.addWidget(self.rule_reverse_box)
        rule_meta_row.addStretch(1)
        right_layout.addLayout(rule_meta_row)

        self.settings_container = QWidget()
        self.settings_form = QFormLayout(self.settings_container)
        self.settings_form.setContentsMargins(0, 0, 0, 0)
        self.settings_form.setSpacing(10)
        self.settings_form.setHorizontalSpacing(16)
        self.settings_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.settings_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        right_layout.addWidget(self.settings_container, 1)

        self.main_splitter.addWidget(self.right_panel)
        QTimer.singleShot(0, self._apply_initial_sizes)

        self.mode_combo.currentIndexChanged.connect(self._on_ruleset_meta_changed)
        self.reverse_box.toggled.connect(self._on_ruleset_meta_changed)
        self.enable_condition_box.toggled.connect(self._on_enable_condition_changed)

        self.group_list.currentRowChanged.connect(self._on_group_selected)
        self.rule_list.currentRowChanged.connect(self._on_rule_selected)

        self.add_group_btn.clicked.connect(self._on_add_group)
        self.del_group_btn.clicked.connect(self._on_delete_group)
        self.group_up_btn.clicked.connect(self._on_group_up)
        self.group_down_btn.clicked.connect(self._on_group_down)

        self.add_rule_btn.clicked.connect(self._on_add_rule)
        self.del_rule_btn.clicked.connect(self._on_delete_rule)
        self.rule_up_btn.clicked.connect(self._on_rule_up)
        self.rule_down_btn.clicked.connect(self._on_rule_down)

        self.group_enabled_box.toggled.connect(self._on_group_meta_changed)
        self.group_reverse_box.toggled.connect(self._on_group_meta_changed)
        self.group_mode_combo.currentIndexChanged.connect(self._on_group_meta_changed)

        self.rule_reverse_box.toggled.connect(self._on_rule_meta_changed)
        self.change_rule_btn.clicked.connect(self._on_change_rule_type)

    def _apply_initial_sizes(self) -> None:
        self.main_splitter.setSizes([260, 560])

    def set_workflow(self, workflow: Workflow | None) -> None:
        self._workflow = workflow
        self._current_group_index = -1
        self._current_rule_index = -1

        self._ensure_structure()
        self._reload_all()

    def _ensure_structure(self) -> None:
        if self._workflow is None:
            return

        if self._workflow.Ruleset is None:
            from automation.models import Ruleset
            self._workflow.Ruleset = Ruleset()

        if not self._workflow.Ruleset.Groups:
            self._workflow.Ruleset.Groups = [RuleGroup(Rules=[Rule()])]

        for group in self._workflow.Ruleset.Groups:
            if not group.Rules:
                group.Rules = [Rule()]

    def _reload_all(self) -> None:
        self._updating = True
        try:
            self._reload_status()
            self._reload_ruleset_meta()
            self._reload_group_list()
            self._reload_group_meta()
            self._reload_rule_list()
            self._reload_rule_detail()
        finally:
            self._updating = False

    def _reload_status(self) -> None:
        if self._workflow is None:
            self.status_label.setText("未选择工作流。")
            self.enable_condition_box.setChecked(False)
            self.enable_condition_box.setEnabled(False)
            return

        self.enable_condition_box.setEnabled(True)
        self.enable_condition_box.blockSignals(True)
        self.enable_condition_box.setChecked(bool(self._workflow.IsConditionEnabled))
        self.enable_condition_box.blockSignals(False)

        if not self._workflow.IsConditionEnabled:
            self.status_label.setText("当前工作流未启用条件。你可以在这里直接勾选“启用当前工作流条件”。")
        else:
            self.status_label.setText("当前工作流已启用条件。只有规则集满足时，工作流才会执行。")

    def _reload_ruleset_meta(self) -> None:
        if self._workflow is None:
            self.mode_combo.setEnabled(False)
            self.reverse_box.setEnabled(False)
            return

        self.mode_combo.setEnabled(True)
        self.reverse_box.setEnabled(True)

        ruleset = self._workflow.Ruleset
        idx = 0 if ruleset.Mode == RulesetLogicalMode.Or else 1
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(idx)
        self.mode_combo.blockSignals(False)

        self.reverse_box.blockSignals(True)
        self.reverse_box.setChecked(bool(ruleset.IsReversed))
        self.reverse_box.blockSignals(False)

    def _reload_group_list(self) -> None:
        self.group_list.clear()

        if self._workflow is None:
            return

        for i, group in enumerate(self._workflow.Ruleset.Groups):
            logic = "AND" if group.Mode == RulesetLogicalMode.And else "OR"
            state = "启用" if group.IsEnabled else "禁用"
            reversed_text = " / 反转" if group.IsReversed else ""
            item = QListWidgetItem(f"规则组 {i + 1} [{state} / {logic}{reversed_text}]")
            self.group_list.addItem(item)

        if self._workflow.Ruleset.Groups:
            if self._current_group_index < 0:
                self._current_group_index = 0
            self._current_group_index = min(self._current_group_index, len(self._workflow.Ruleset.Groups) - 1)
            self.group_list.blockSignals(True)
            self.group_list.setCurrentRow(self._current_group_index)
            self.group_list.blockSignals(False)

    def _reload_group_meta(self) -> None:
        group = self._current_group()
        enabled = group is not None

        self.group_enabled_box.setEnabled(enabled)
        self.group_reverse_box.setEnabled(enabled)
        self.group_mode_combo.setEnabled(enabled)

        if group is None:
            self.group_enabled_box.setChecked(False)
            self.group_reverse_box.setChecked(False)
            return

        self.group_enabled_box.blockSignals(True)
        self.group_enabled_box.setChecked(bool(group.IsEnabled))
        self.group_enabled_box.blockSignals(False)

        self.group_reverse_box.blockSignals(True)
        self.group_reverse_box.setChecked(bool(group.IsReversed))
        self.group_reverse_box.blockSignals(False)

        idx = 0 if group.Mode == RulesetLogicalMode.Or else 1
        self.group_mode_combo.blockSignals(True)
        self.group_mode_combo.setCurrentIndex(idx)
        self.group_mode_combo.blockSignals(False)

    def _reload_rule_list(self) -> None:
        self.rule_list.clear()

        group = self._current_group()
        if group is None:
            return

        for i, rule in enumerate(group.Rules):
            name = self._rule_name(rule.Id) if rule.Id else "未选择规则"
            reversed_text = " / 反转" if rule.IsReversed else ""
            self.rule_list.addItem(QListWidgetItem(f"规则 {i + 1}: {name}{reversed_text}"))

        if group.Rules:
            if self._current_rule_index < 0:
                self._current_rule_index = 0
            self._current_rule_index = min(self._current_rule_index, len(group.Rules) - 1)
            self.rule_list.blockSignals(True)
            self.rule_list.setCurrentRow(self._current_rule_index)
            self.rule_list.blockSignals(False)

    def _clear_settings_form(self) -> None:
        while self.settings_form.rowCount() > 0:
            self.settings_form.removeRow(0)

    def _reload_rule_detail(self) -> None:
        self._clear_settings_form()

        rule = self._current_rule()
        enabled = rule is not None

        self.change_rule_btn.setEnabled(enabled)
        self.rule_reverse_box.setEnabled(enabled)

        if rule is None:
            self.rule_name_label.setText("当前规则：未选择")
            self.rule_desc_label.setText("请选择一个规则后，这里会显示它的用途。")
            self.rule_reverse_box.setChecked(False)
            return

        rule_name = self._rule_name(rule.Id) if rule.Id else "未选择规则"
        self.rule_name_label.setText(f"当前规则：{rule_name}")
        self.rule_desc_label.setText(
            RULE_DESCRIPTIONS.get(rule.Id, "该规则的说明暂未提供。")
            if rule.Id else "当前规则尚未指定类型。"
        )

        self.rule_reverse_box.blockSignals(True)
        self.rule_reverse_box.setChecked(bool(rule.IsReversed))
        self.rule_reverse_box.blockSignals(False)

        if rule.Id == "":
            self._add_note("当前规则尚未指定类型，请点击“更换规则类型”或“添加规则”。")
            return

        settings = rule.Settings
        if settings is None:
            settings_type = RULE_SETTINGS_TYPES.get(rule.Id)
            if settings_type is not None:
                settings = settings_type()
                rule.Settings = settings

        if isinstance(settings, StringMatchingSettings):
            self._add_line_edit("文本", settings, "Text")
            self._add_checkbox("使用正则", settings, "UseRegex")
            return

        if isinstance(settings, CurrentSubjectRuleSettings):
            self._add_subject_combo("科目", settings, "SubjectId")
            self._add_note("说明：CW 当前按“科目显示名称”匹配，不是 ClassIsland 的 SubjectId / 科目对象语义。")
            return

        if isinstance(settings, CurrentWeatherRuleSettings):
            self._add_current_weather_combo("天气", settings, "WeatherId")
            self._add_note("说明：当前实现按精确天气代码匹配；ClassIsland 的“包含相似天气”在 CW 当前设计下暂无等价安全实现，因此这次不改 backend 语义。")
            return

        if isinstance(settings, RainTimeRuleSettings):
            self._add_double_spin("分钟", settings, "RainTimeMinutes", 0, 9999, 1)
            self._add_checkbox("判断剩余时间（否则判断距离开始）", settings, "IsRemainingTime")
            return

        if isinstance(settings, SunRiseSetRuleSettings):
            self._add_double_spin("分钟", settings, "TimeMinutes", 0, 9999, 1)
            self._add_checkbox("是否判断日落后", settings, "IsSunset")
            return

        if isinstance(settings, TimeStateRuleSettings):
            self._add_time_state_combo("时间状态", settings, "State")
            return

        if isinstance(settings, WindowStatusRuleSettings):
            self._add_window_state_combo("窗口状态", settings, "State")
            return

        self._add_note("该规则的设置编辑器尚未实现。")

    def _current_group(self) -> RuleGroup | None:
        if self._workflow is None:
            return None
        groups = self._workflow.Ruleset.Groups
        if 0 <= self._current_group_index < len(groups):
            return groups[self._current_group_index]
        return None

    def _current_rule(self) -> Rule | None:
        group = self._current_group()
        if group is None:
            return None
        if 0 <= self._current_rule_index < len(group.Rules):
            return group.Rules[self._current_rule_index]
        return None

    def _rule_name(self, rule_id: str) -> str:
        info = get_rule_info(rule_id)
        if info and getattr(info, "Name", None):
            return info.Name
        return RULE_NAME_FALLBACKS.get(rule_id, rule_id)

    def _emit_changed(self) -> None:
        if self._updating:
            return
        self.changed.emit()

    # =========================================================
    # Events - ruleset meta
    # =========================================================

    def _on_enable_condition_changed(self, state: bool) -> None:
        if self._workflow is None or self._updating:
            return
        self._workflow.IsConditionEnabled = bool(state)
        self._reload_status()
        self._emit_changed()

    def _on_ruleset_meta_changed(self) -> None:
        if self._workflow is None or self._updating:
            return

        self._workflow.Ruleset.Mode = combo_current_data(self.mode_combo)
        self._workflow.Ruleset.IsReversed = self.reverse_box.isChecked()
        self._reload_group_list()
        self._emit_changed()

    # =========================================================
    # Events - groups
    # =========================================================

    def _on_group_selected(self, row: int) -> None:
        self._current_group_index = row
        self._current_rule_index = -1

        self._updating = True
        try:
            self._reload_group_meta()
            self._reload_rule_list()
            self._reload_rule_detail()
        finally:
            self._updating = False

    def _on_add_group(self) -> None:
        if self._workflow is None:
            return

        group = RuleGroup(Rules=[Rule()])
        self._workflow.Ruleset.Groups.append(group)
        self._current_group_index = len(self._workflow.Ruleset.Groups) - 1
        self._current_rule_index = 0
        self._reload_all()
        self._emit_changed()

    def _on_delete_group(self) -> None:
        if self._workflow is None:
            return
        groups = self._workflow.Ruleset.Groups
        if not (0 <= self._current_group_index < len(groups)):
            return

        groups.pop(self._current_group_index)
        if not groups:
            groups.append(RuleGroup(Rules=[Rule()]))

        self._current_group_index = min(self._current_group_index, len(groups) - 1)
        self._current_rule_index = 0
        self._reload_all()
        self._emit_changed()

    def _on_group_up(self) -> None:
        group = self._current_group()
        if self._workflow is None or group is None:
            return
        idx = self._current_group_index
        if idx <= 0:
            return

        groups = self._workflow.Ruleset.Groups
        groups[idx - 1], groups[idx] = groups[idx], groups[idx - 1]
        self._current_group_index = idx - 1
        self._reload_all()
        self._emit_changed()

    def _on_group_down(self) -> None:
        group = self._current_group()
        if self._workflow is None or group is None:
            return
        idx = self._current_group_index
        groups = self._workflow.Ruleset.Groups
        if idx < 0 or idx >= len(groups) - 1:
            return

        groups[idx + 1], groups[idx] = groups[idx], groups[idx + 1]
        self._current_group_index = idx + 1
        self._reload_all()
        self._emit_changed()

    def _on_group_meta_changed(self) -> None:
        group = self._current_group()
        if group is None or self._updating:
            return

        group.IsEnabled = self.group_enabled_box.isChecked()
        group.IsReversed = self.group_reverse_box.isChecked()
        group.Mode = combo_current_data(self.group_mode_combo)

        self._reload_group_list()
        if self._current_group_index >= 0:
            self.group_list.setCurrentRow(self._current_group_index)
        self._emit_changed()

    # =========================================================
    # Events - rules
    # =========================================================

    def _on_rule_selected(self, row: int) -> None:
        self._current_rule_index = row
        self._updating = True
        try:
            self._reload_rule_detail()
        finally:
            self._updating = False

    def _on_add_rule(self) -> None:
        group = self._current_group()
        if group is None:
            return

        dlg = RulePickerDialog(self)
        if dlg.exec_() != QDialog.Accepted or not dlg.selected_rule_id:
            return

        rule_id = dlg.selected_rule_id
        settings_type = RULE_SETTINGS_TYPES.get(rule_id)
        rule = Rule(
            Id=rule_id,
            IsReversed=False,
            Settings=settings_type() if settings_type else None,
        )
        group.Rules.append(rule)
        self._current_rule_index = len(group.Rules) - 1
        self._reload_all()
        self._emit_changed()

    def _on_delete_rule(self) -> None:
        group = self._current_group()
        if group is None:
            return

        if not (0 <= self._current_rule_index < len(group.Rules)):
            return

        group.Rules.pop(self._current_rule_index)
        if not group.Rules:
            group.Rules.append(Rule())

        self._current_rule_index = min(self._current_rule_index, len(group.Rules) - 1)
        self._reload_all()
        self._emit_changed()

    def _on_rule_up(self) -> None:
        group = self._current_group()
        if group is None:
            return
        idx = self._current_rule_index
        if idx <= 0:
            return

        group.Rules[idx - 1], group.Rules[idx] = group.Rules[idx], group.Rules[idx - 1]
        self._current_rule_index = idx - 1
        self._reload_all()
        self._emit_changed()

    def _on_rule_down(self) -> None:
        group = self._current_group()
        if group is None:
            return
        idx = self._current_rule_index
        if idx < 0 or idx >= len(group.Rules) - 1:
            return

        group.Rules[idx + 1], group.Rules[idx] = group.Rules[idx], group.Rules[idx + 1]
        self._current_rule_index = idx + 1
        self._reload_all()
        self._emit_changed()

    def _on_rule_meta_changed(self) -> None:
        rule = self._current_rule()
        if rule is None or self._updating:
            return

        rule.IsReversed = self.rule_reverse_box.isChecked()
        self._reload_rule_list()
        if self._current_rule_index >= 0:
            self.rule_list.setCurrentRow(self._current_rule_index)
        self._emit_changed()

    def _on_change_rule_type(self) -> None:
        rule = self._current_rule()
        if rule is None:
            return

        dlg = RulePickerDialog(self)
        if dlg.exec_() != QDialog.Accepted or not dlg.selected_rule_id:
            return

        rule_id = dlg.selected_rule_id
        settings_type = RULE_SETTINGS_TYPES.get(rule_id)

        rule.Id = rule_id
        rule.Settings = settings_type() if settings_type else None

        self._emit_changed()
        QTimer.singleShot(0, self._reload_all)

    # =========================================================
    # Setting editors
    # =========================================================

    def _label(self, text: str) -> BodyLabel:
        label = BodyLabel(text)
        label.setWordWrap(True)
        label.setMinimumWidth(112)
        label.setMaximumWidth(132)
        return label

    def _add_note(self, text: str) -> None:
        note = CaptionLabel(text)
        note.setWordWrap(True)
        note.setStyleSheet("color: #666;")
        self.settings_form.addRow(note)

    def _add_line_edit(self, title: str, obj: Any, attr: str) -> None:
        edit = LineEdit()
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        current = getattr(obj, attr, "")
        edit.setText("" if current is None else str(current))

        def _on_changed(text: str):
            setattr(obj, attr, text)
            self._emit_changed()

        edit.textChanged.connect(_on_changed)
        self.settings_form.addRow(self._label(title), edit)

    def _add_checkbox(self, title: str, obj: Any, attr: str) -> None:
        box = CheckBox()
        box.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        box.setChecked(bool(getattr(obj, attr, False)))

        def _on_changed(state: bool):
            setattr(obj, attr, bool(state))
            self._emit_changed()

        box.toggled.connect(_on_changed)
        self.settings_form.addRow(self._label(title), box)

    def _add_double_spin(self, title: str, obj: Any, attr: str, minimum: float, maximum: float, step: float) -> None:
        spin = QDoubleSpinBox()
        spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setDecimals(2 if step < 1 else 0)
        try:
            spin.setValue(float(getattr(obj, attr, 0)))
        except Exception:
            spin.setValue(0)

        def _on_changed(value: float):
            setattr(obj, attr, float(value))
            self._emit_changed()

        spin.valueChanged.connect(_on_changed)
        self.settings_form.addRow(self._label(title), spin)

    def _add_int_spin(self, title: str, obj: Any, attr: str, minimum: int, maximum: int) -> None:
        spin = QSpinBox()
        spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        spin.setRange(minimum, maximum)
        try:
            spin.setValue(int(getattr(obj, attr, 0)))
        except Exception:
            spin.setValue(0)

        def _on_changed(value: int):
            setattr(obj, attr, int(value))
            self._emit_changed()

        spin.valueChanged.connect(_on_changed)
        self.settings_form.addRow(self._label(title), spin)

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

    def _add_subject_combo(self, title: str, obj: Any, attr: str) -> None:
        combo = ComboBox()
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        try:
            combo.setEditable(True)
        except Exception:
            pass

        options = self._load_subject_options()
        current = str(getattr(obj, attr, "") or "").strip()

        if current and current not in options:
            options.append(current)

        for option in options:
            combo_add_item(combo, option, option)

        if current:
            idx = combo.findData(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                try:
                    combo.setCurrentText(current)
                except Exception:
                    pass

        def _commit_value(*_):
            value = ""
            try:
                data = combo_current_data(combo)
                if data not in (None, ""):
                    value = str(data).strip()
            except Exception:
                pass

            if not value:
                try:
                    value = str(combo.currentText()).strip()
                except Exception:
                    value = ""

            setattr(obj, attr, value)
            self._emit_changed()

        combo.currentIndexChanged.connect(_commit_value)

        try:
            line_edit = combo.lineEdit()
        except Exception:
            line_edit = None

        if line_edit is not None:
            line_edit.textChanged.connect(lambda _text: _commit_value())

        self.settings_form.addRow(self._label(title), combo)

    def _load_weather_options(self) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []

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
                if all(existing_code != code for existing_code, _ in options):
                    options.append((code, label))
        except Exception:
            pass

        return options

    def _add_current_weather_combo(self, title: str, obj: Any, attr: str) -> None:
        combo = ComboBox()
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        try:
            combo.setEditable(True)
        except Exception:
            pass

        options = self._load_weather_options()
        current_raw = getattr(obj, attr, 0)
        current_code = "" if current_raw is None else str(current_raw).strip()

        for code, label in options:
            combo_add_item(combo, label, code)

        if current_code and all(code != current_code for code, _ in options):
            combo_add_item(combo, f"当前值 ({current_code})", current_code)

        if current_code:
            idx = combo.findData(current_code)
            combo.setCurrentIndex(max(0, idx))
            try:
                combo.setCurrentText(combo.itemText(idx) if idx >= 0 else current_code)
            except Exception:
                pass

        def _commit_value(*_):
            value = ""
            try:
                data = combo_current_data(combo)
                if data not in (None, ""):
                    value = str(data).strip()
            except Exception:
                pass

            if not value:
                try:
                    value = str(combo.currentText()).strip()
                except Exception:
                    value = ""

            if not value:
                return

            try:
                setattr(obj, attr, int(value))
            except Exception:
                return

            self._emit_changed()

        combo.currentIndexChanged.connect(_commit_value)

        try:
            line_edit = combo.lineEdit()
        except Exception:
            line_edit = None

        if line_edit is not None:
            line_edit.textChanged.connect(lambda _text: _commit_value())

        self.settings_form.addRow(self._label(title), combo)

    def _add_time_state_combo(self, title: str, obj: Any, attr: str) -> None:
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
            self._emit_changed()

        combo.currentIndexChanged.connect(_on_changed)
        self.settings_form.addRow(self._label(title), combo)

    def _add_window_state_combo(self, title: str, obj: Any, attr: str) -> None:
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
            self._emit_changed()

        combo.currentIndexChanged.connect(_on_changed)
        self.settings_form.addRow(self._label(title), combo)
