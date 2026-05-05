from __future__ import annotations

from typing import Any

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidgetItem,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)
from qfluentwidgets import (
    CaptionLabel,
    ComboBox,
    ListWidget,
    PushButton,
    StrongBodyLabel,
)

from automation.builtins import register_builtins
from automation.compat import RULE_SETTINGS_TYPES
from automation.enums import RulesetLogicalMode
from automation.models import Rule, RuleGroup, Workflow
from automation.registry import get_registered_rule_ids, get_rule_info


HIDDEN_RULE_IDS = {
    "classisland.test.true",
    "classisland.test.false",
}

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
    "classisland.test.true": "历史测试规则，不建议继续使用。",
    "classisland.test.false": "历史测试规则，不建议继续使用。",
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
    "classisland.test.true": "测试规则（真）",
    "classisland.test.false": "测试规则（假）",
}


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
        extras = [
            rid for rid in sorted(registered)
            if rid not in known and rid not in HIDDEN_RULE_IDS
        ]
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
    targetChanged = pyqtSignal(str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        register_builtins()

        self._workflow: Workflow | None = None
        self._current_group_index: int = -1
        self._current_rule_index: int = -1
        self._updating = False
        self._suspend_target_emit = False

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.status_label = CaptionLabel("未选择工作流。")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #666;")
        root.addWidget(self.status_label)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        self.edit_ruleset_btn = PushButton("规则集属性")
        top_row.addWidget(self.edit_ruleset_btn)
        top_row.addStretch(1)
        root.addLayout(top_row)

        self.summary_label = CaptionLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color: #666;")
        root.addWidget(self.summary_label)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)
        self.main_splitter.setStyleSheet("QSplitter::handle { background: transparent; }")
        root.addWidget(self.main_splitter, 1)

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
        self.edit_group_btn = PushButton("当前组属性")
        group_move_btns.addWidget(self.group_up_btn)
        group_move_btns.addWidget(self.group_down_btn)
        group_move_btns.addWidget(self.edit_group_btn)
        left_layout.addLayout(group_move_btns)

        self.main_splitter.addWidget(self.left_panel)

        # 右：规则
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        rule_header = StrongBodyLabel("规则")
        right_layout.addWidget(rule_header)

        self.rule_list = ListWidget()
        self.rule_list.setAlternatingRowColors(True)
        self.rule_list.setMinimumHeight(140)
        right_layout.addWidget(self.rule_list, 1)

        rule_btns = QHBoxLayout()
        self.add_rule_btn = PushButton("添加规则")
        self.del_rule_btn = PushButton("删除规则")
        rule_btns.addWidget(self.add_rule_btn)
        rule_btns.addWidget(self.del_rule_btn)
        right_layout.addLayout(rule_btns)

        rule_move_btns = QHBoxLayout()
        self.rule_up_btn = PushButton("上移")
        self.rule_down_btn = PushButton("下移")
        self.change_rule_btn = PushButton("更换规则类型")
        self.edit_rule_btn = PushButton("当前规则属性")
        rule_move_btns.addWidget(self.rule_up_btn)
        rule_move_btns.addWidget(self.rule_down_btn)
        rule_move_btns.addWidget(self.change_rule_btn)
        rule_move_btns.addWidget(self.edit_rule_btn)
        right_layout.addLayout(rule_move_btns)

        self.rule_tip = CaptionLabel("选中规则组或规则后，其详细属性会显示在左下角“参数设置”区域。")
        self.rule_tip.setWordWrap(True)
        self.rule_tip.setStyleSheet("color: #666;")
        right_layout.addWidget(self.rule_tip)

        self.main_splitter.addWidget(self.right_panel)

        QTimer.singleShot(0, self._apply_initial_sizes)

        self.edit_ruleset_btn.clicked.connect(self._on_edit_ruleset)
        self.edit_group_btn.clicked.connect(self._on_edit_group)
        self.edit_rule_btn.clicked.connect(self._on_edit_rule)

        self.group_list.currentRowChanged.connect(self._on_group_selected)
        self.rule_list.currentRowChanged.connect(self._on_rule_selected)

        # 关键修复：允许“点击已选中的组/规则”也切换属性面板
        self.group_list.itemClicked.connect(self._on_group_item_clicked)
        self.rule_list.itemClicked.connect(self._on_rule_item_clicked)

        self.add_group_btn.clicked.connect(self._on_add_group)
        self.del_group_btn.clicked.connect(self._on_delete_group)
        self.group_up_btn.clicked.connect(self._on_group_up)
        self.group_down_btn.clicked.connect(self._on_group_down)

        self.add_rule_btn.clicked.connect(self._on_add_rule)
        self.del_rule_btn.clicked.connect(self._on_delete_rule)
        self.rule_up_btn.clicked.connect(self._on_rule_up)
        self.rule_down_btn.clicked.connect(self._on_rule_down)
        self.change_rule_btn.clicked.connect(self._on_change_rule_type)

    def _apply_initial_sizes(self) -> None:
        self.main_splitter.setSizes([260, 520])

    def set_workflow(self, workflow: Workflow | None) -> None:
        self._workflow = workflow
        self._current_group_index = -1
        self._current_rule_index = -1

        self._ensure_structure()

        self._suspend_target_emit = True
        try:
            self._reload_all()
        finally:
            self._suspend_target_emit = False

    def clear_selection_focus(self) -> None:
        self._suspend_target_emit = True
        try:
            self._current_group_index = -1
            self._current_rule_index = -1

            self.group_list.blockSignals(True)
            self.group_list.clearSelection()
            self.group_list.setCurrentRow(-1)
            self.group_list.blockSignals(False)

            self.rule_list.blockSignals(True)
            self.rule_list.clearSelection()
            self.rule_list.setCurrentRow(-1)
            self.rule_list.blockSignals(False)
        finally:
            self._suspend_target_emit = False

    def refresh_display_texts(self) -> None:
        self._suspend_target_emit = True
        try:
            self._reload_group_list()
            self._reload_rule_list()
            self._reload_status()
        finally:
            self._suspend_target_emit = False

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
            self._reload_group_list()
            self._reload_rule_list()
            self._update_buttons_state()
        finally:
            self._updating = False

    def _reload_status(self) -> None:
        if self._workflow is None:
            self.status_label.setText("未选择工作流。")
            self.summary_label.setText("")
            return

        ruleset = self._workflow.Ruleset
        group_count = len(ruleset.Groups)
        rule_count = sum(len(g.Rules) for g in ruleset.Groups)
        mode_text = "AND" if ruleset.Mode == RulesetLogicalMode.And else "OR"
        reversed_text = "已反转" if ruleset.IsReversed else "未反转"

        self.status_label.setText("提示：规则组与规则的详细属性已统一移动到左下角“参数设置”区域。")
        self.summary_label.setText(
            f"规则集状态：{group_count} 个规则组 / {rule_count} 条规则    ·    逻辑：{mode_text}    ·    {reversed_text}"
        )

    def _reload_group_list(self) -> None:
        self.group_list.clear()

        if self._workflow is None:
            return

        groups = self._workflow.Ruleset.Groups
        for i, group in enumerate(groups):
            logic = "AND" if group.Mode == RulesetLogicalMode.And else "OR"
            state = "启用" if group.IsEnabled else "禁用"
            reversed_text = " / 反转" if group.IsReversed else ""
            item = QListWidgetItem(f"规则组 {i + 1} [{state} / {logic}{reversed_text}]")
            self.group_list.addItem(item)

        if groups:
            if self._current_group_index < 0:
                self._current_group_index = 0
            self._current_group_index = min(self._current_group_index, len(groups) - 1)

            self.group_list.blockSignals(True)
            self.group_list.setCurrentRow(self._current_group_index)
            self.group_list.blockSignals(False)
        else:
            self._current_group_index = -1

    def _reload_rule_list(self) -> None:
        self.rule_list.clear()

        group = self._current_group()
        if group is None:
            self._current_rule_index = -1
            return

        for i, rule in enumerate(group.Rules):
            name = self._rule_name(rule.Id) if rule.Id else "未选择规则"
            reversed_text = " / 反转" if rule.IsReversed else ""
            self.rule_list.addItem(QListWidgetItem(f"规则 {i + 1}: {name}{reversed_text}"))

        if group.Rules and self._current_rule_index >= 0:
            self._current_rule_index = min(self._current_rule_index, len(group.Rules) - 1)
            self.rule_list.blockSignals(True)
            self.rule_list.setCurrentRow(self._current_rule_index)
            self.rule_list.blockSignals(False)
        else:
            self._current_rule_index = -1
            self.rule_list.blockSignals(True)
            self.rule_list.setCurrentRow(-1)
            self.rule_list.blockSignals(False)

    def _update_buttons_state(self) -> None:
        workflow_exists = self._workflow is not None
        group_exists = self._current_group() is not None
        rule_exists = self._current_rule() is not None

        self.edit_ruleset_btn.setEnabled(workflow_exists)

        self.del_group_btn.setEnabled(group_exists)
        self.group_up_btn.setEnabled(group_exists)
        self.group_down_btn.setEnabled(group_exists)
        self.edit_group_btn.setEnabled(group_exists)

        self.add_rule_btn.setEnabled(group_exists)
        self.del_rule_btn.setEnabled(rule_exists)
        self.rule_up_btn.setEnabled(rule_exists)
        self.rule_down_btn.setEnabled(rule_exists)
        self.change_rule_btn.setEnabled(rule_exists)
        self.edit_rule_btn.setEnabled(rule_exists)

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

    def _emit_target(self, kind: str, target: object | None) -> None:
        if self._suspend_target_emit or target is None:
            return
        self.targetChanged.emit(kind, target)

    # =========================================================
    # Target selection
    # =========================================================

    def _on_edit_ruleset(self) -> None:
        if self._workflow is None:
            return
        self._emit_target("ruleset", self._workflow.Ruleset)

    def _on_edit_group(self) -> None:
        group = self._current_group()
        if group is None:
            return
        self._emit_target("rule_group", group)

    def _on_edit_rule(self) -> None:
        rule = self._current_rule()
        if rule is None:
            return
        self._emit_target("rule", rule)

    # 关键修复：点击已选中的规则组，也强制切换到规则组属性
    def _on_group_item_clicked(self, item) -> None:
        row = self.group_list.row(item)
        if row < 0:
            return

        self._current_group_index = row
        self._current_rule_index = -1

        self.rule_list.blockSignals(True)
        self.rule_list.clearSelection()
        self.rule_list.setCurrentRow(-1)
        self.rule_list.blockSignals(False)

        group = self._current_group()
        if group is not None:
            self._emit_target("rule_group", group)

    # 对称处理：点击已选中的规则，也强制切换到规则属性
    def _on_rule_item_clicked(self, item) -> None:
        row = self.rule_list.row(item)
        if row < 0:
            return

        self._current_rule_index = row
        rule = self._current_rule()
        if rule is not None:
            self._emit_target("rule", rule)

    # =========================================================
    # Group events
    # =========================================================

    def _on_group_selected(self, row: int) -> None:
        self._current_group_index = row
        self._current_rule_index = -1

        self._updating = True
        try:
            self._reload_rule_list()
            self._update_buttons_state()
        finally:
            self._updating = False

        group = self._current_group()
        if group is not None:
            self._emit_target("rule_group", group)

    def _on_add_group(self) -> None:
        if self._workflow is None:
            return

        group = RuleGroup(Rules=[Rule()])
        self._workflow.Ruleset.Groups.append(group)
        self._current_group_index = len(self._workflow.Ruleset.Groups) - 1
        self._current_rule_index = -1

        self._reload_all()
        self._emit_changed()
        self._emit_target("rule_group", group)

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
        self._current_rule_index = -1

        self._reload_all()
        self._emit_changed()

        group = self._current_group()
        if group is not None:
            self._emit_target("rule_group", group)
        elif self._workflow is not None:
            self._emit_target("ruleset", self._workflow.Ruleset)

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
        self._emit_target("rule_group", self._current_group())

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
        self._emit_target("rule_group", self._current_group())

    # =========================================================
    # Rule events
    # =========================================================

    def _on_rule_selected(self, row: int) -> None:
        self._current_rule_index = row
        self._update_buttons_state()

        rule = self._current_rule()
        if rule is not None:
            self._emit_target("rule", rule)

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
        self._emit_target("rule", rule)

    def _on_delete_rule(self) -> None:
        group = self._current_group()
        if group is None:
            return

        if not (0 <= self._current_rule_index < len(group.Rules)):
            return

        group.Rules.pop(self._current_rule_index)
        if not group.Rules:
            group.Rules.append(Rule())

        if self._current_rule_index >= len(group.Rules):
            self._current_rule_index = len(group.Rules) - 1

        self._reload_all()
        self._emit_changed()

        rule = self._current_rule()
        if rule is not None and rule.Id:
            self._emit_target("rule", rule)
        else:
            self._emit_target("rule_group", group)

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
        self._emit_target("rule", self._current_rule())

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
        self._emit_target("rule", self._current_rule())

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

        self._reload_all()
        self._emit_changed()
        self._emit_target("rule", rule)
