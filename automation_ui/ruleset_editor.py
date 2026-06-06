from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
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
    ListWidget,
    PushButton,
    StrongBodyLabel,
    SmoothScrollArea,
    isDarkTheme,
    qconfig,
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


class RulesetEditor(QWidget):
    rule_selection_changed = pyqtSignal(str, object)
    data_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._workflow: Workflow | None = None
        self._current_group_index: int = -1
        self._current_rule_index: int = -1

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.status_label = CaptionLabel("未选择工作流。")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        self.edit_ruleset_btn = PushButton("编辑全局规则集属性")
        top_row.addWidget(self.edit_ruleset_btn)

        self.live_status_label = StrongBodyLabel("")
        top_row.addWidget(self.live_status_label)

        top_row.addStretch(1)
        root.addLayout(top_row)

        self.summary_label = CaptionLabel("")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)
        self.main_splitter.setStyleSheet("QSplitter::handle { background: transparent; }")
        root.addWidget(self.main_splitter, 1)

        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        left_layout.addWidget(StrongBodyLabel("规则组"))

        self.group_list = ListWidget()
        self.group_list.setAlternatingRowColors(True)
        left_layout.addWidget(self.group_list, 1)

        group_btns = QHBoxLayout()
        self.add_group_btn = PushButton("添加组")
        self.del_group_btn = PushButton("删除组")
        group_btns.addWidget(self.add_group_btn)
        group_btns.addWidget(self.del_group_btn)
        left_layout.addLayout(group_btns)

        group_move_btns = QHBoxLayout()
        self.group_up_btn = PushButton("上移")
        self.group_down_btn = PushButton("下移")
        group_move_btns.addWidget(self.group_up_btn)
        group_move_btns.addWidget(self.group_down_btn)
        left_layout.addLayout(group_move_btns)

        self.main_splitter.addWidget(self.left_panel)

        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        right_layout.addWidget(StrongBodyLabel("规则 (当前组)"))

        self.rule_list = ListWidget()
        self.rule_list.setAlternatingRowColors(True)
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
        rule_move_btns.addWidget(self.rule_up_btn)
        rule_move_btns.addWidget(self.rule_down_btn)
        right_layout.addLayout(rule_move_btns)

        self.rule_tip = CaptionLabel("选中规则组或规则后，其详细属性会显示在左下角“参数设置”区域。")
        self.rule_tip.setWordWrap(True)
        right_layout.addWidget(self.rule_tip)

        self.main_splitter.addWidget(self.right_panel)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 1)

        self.edit_ruleset_btn.clicked.connect(self._on_edit_ruleset)

        self.group_list.currentRowChanged.connect(self._on_group_selection_changed)
        # 增加这一行，确保鼠标重复点击同一行也能切过去
        self.group_list.itemClicked.connect(lambda item: self._on_group_selection_changed(self.group_list.row(item)))

        self.rule_list.currentRowChanged.connect(self._on_rule_selection_changed)
        # 增加这一行，确保鼠标重复点击同一行也能切过去
        self.rule_list.itemClicked.connect(lambda item: self._on_rule_selection_changed(self.rule_list.row(item)))

        self.add_group_btn.clicked.connect(self._on_add_group)
        self.del_group_btn.clicked.connect(self._on_del_group)
        self.group_up_btn.clicked.connect(self._on_group_up)
        self.group_down_btn.clicked.connect(self._on_group_down)

        self.add_rule_btn.clicked.connect(self._on_add_rule)
        self.del_rule_btn.clicked.connect(self._on_del_rule)
        self.rule_up_btn.clicked.connect(self._on_rule_up)
        self.rule_down_btn.clicked.connect(self._on_rule_down)

        self._live_timer = QTimer(self)
        self._live_timer.timeout.connect(self._update_live_status)

        self._update_ui_state()

    def showEvent(self, event):
        super().showEvent(event)
        self._live_timer.start(1000)
        self._update_live_status()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._live_timer.stop()

    def set_workflow(self, workflow: Workflow | None) -> None:
        self._workflow = workflow
        self._current_group_index = -1
        self._current_rule_index = -1
        self._update_ui_state()
        self._reload_groups()
        self._update_live_status()

    def clear_selection(self) -> None:
        self.group_list.blockSignals(True)
        self.group_list.setCurrentRow(-1)
        self.group_list.clearSelection()
        self._current_group_index = -1
        self.group_list.blockSignals(False)

        self.rule_list.blockSignals(True)
        self.rule_list.setCurrentRow(-1)
        self.rule_list.clearSelection()
        self.rule_list.clear()
        self._current_rule_index = -1
        self.rule_list.blockSignals(False)

    def _get_ruleset(self):
        if self._workflow:
            if self._workflow.Ruleset is None:
                from automation.models import Ruleset
                self._workflow.Ruleset = Ruleset()
            return self._workflow.Ruleset
        return None

    def _update_ui_state(self) -> None:
        has_wf = self._workflow is not None
        self.edit_ruleset_btn.setEnabled(has_wf)
        self.add_group_btn.setEnabled(has_wf)

        has_group = has_wf and self._current_group_index >= 0
        self.del_group_btn.setEnabled(has_group)
        self.group_up_btn.setEnabled(has_group)
        self.group_down_btn.setEnabled(has_group)
        self.add_rule_btn.setEnabled(has_group)

        has_rule = has_group and self._current_rule_index >= 0
        self.del_rule_btn.setEnabled(has_rule)
        self.rule_up_btn.setEnabled(has_rule)
        self.rule_down_btn.setEnabled(has_rule)

        if not has_wf:
            self.status_label.setText("未选择工作流。")
            self.summary_label.setText("")
        else:
            rs = self._get_ruleset()
            groups_cnt = len(rs.Groups)
            rules_cnt = sum(len(g.Rules) for g in rs.Groups)
            mode_str = "且 (AND)" if rs.Mode == RulesetLogicalMode.And else "或 (OR)"
            rev_str = " (结果反转)" if rs.IsReversed else ""
            self.status_label.setText(f"当前工作流规则集：全局逻辑 {mode_str}{rev_str}")
            self.summary_label.setText(f"共包含 {groups_cnt} 个规则组，{rules_cnt} 条规则。")

    def _reload_groups(self) -> None:
        self.group_list.clear()
        self.rule_list.clear()

        rs = self._get_ruleset()
        if not rs:
            return

        for i, g in enumerate(rs.Groups):
            mode_str = "且" if getattr(g, "Mode", 0) == 1 else "或"
            enabled = "已启用" if getattr(g, "IsEnabled", True) else "已禁用"
            rev = "反转" if getattr(g, "IsReversed", False) else "正向"
            text = f"组 {i + 1} [{mode_str} / {enabled} / {rev}] ({len(g.Rules)}条)"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole + 1, text)  # 保存纯净的文本用于追加状态
            self.group_list.addItem(item)

        if rs.Groups:
            if self._current_group_index < 0:
                self._current_group_index = 0
            self._current_group_index = min(self._current_group_index, len(rs.Groups) - 1)
            self.group_list.setCurrentRow(self._current_group_index)

    def _reload_rules(self, select_current: bool = False) -> None:
        self.rule_list.clear()
        rs = self._get_ruleset()
        if not rs or self._current_group_index < 0 or self._current_group_index >= len(rs.Groups):
            return

        group = rs.Groups[self._current_group_index]
        for r in group.Rules:
            info = get_rule_info(r.Id)
            name = info.Name if info and hasattr(info, "Name") else RULE_NAME_FALLBACKS.get(r.Id, r.Id)
            rev = "[反转] " if getattr(r, "IsReversed", False) else ""
            text = f"{rev}{name}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole + 1, text)
            self.rule_list.addItem(item)

        if select_current and group.Rules:
            self._current_rule_index = max(0, min(self._current_rule_index, len(group.Rules) - 1))
            self.rule_list.setCurrentRow(self._current_rule_index)
        else:
            self._current_rule_index = -1
            self.rule_list.setCurrentRow(-1)
            self.rule_list.clearSelection()

    def _on_edit_ruleset(self) -> None:
        rs = self._get_ruleset()
        if rs:
            # 删除了 clear_selection()，这样就不破坏左侧的列表了
            self.rule_selection_changed.emit("ruleset", rs)

    def _on_group_selection_changed(self, row: int) -> None:
        if row < 0:
            return

        self._current_group_index = row
        self._current_rule_index = -1

        self._reload_rules(select_current=False)
        self._update_ui_state()

        rs = self._get_ruleset()
        if rs and 0 <= row < len(rs.Groups):
            self.rule_selection_changed.emit("rule_group", rs.Groups[row])

    def _on_rule_selection_changed(self, row: int) -> None:
        if row < 0:
            return
        self._current_rule_index = row
        self._update_ui_state()

        rs = self._get_ruleset()
        if rs and 0 <= self._current_group_index < len(rs.Groups):
            group = rs.Groups[self._current_group_index]
            if 0 <= row < len(group.Rules):
                self.rule_selection_changed.emit("rule", group.Rules[row])

    # =========================================================
    # Real-Time Evaluation Engine
    # =========================================================

    def _get_live_runtime(self):
        try:
            return self.window().automation_runtime
        except AttributeError:
            return None

    def _eval_rule(self, rule) -> bool | None:
        if not getattr(rule, "Id", ""):
            return None

        try:
            from automation.registry import get_rule_info, coerce_rule_settings
            info = get_rule_info(rule.Id)

            if not info or not getattr(info, "Handle", None):
                return False

            # 非常关键：确保新添加的规则也有默认设置对象，否则底层校验必定报错
            coerce_rule_settings(rule)
            settings = rule.Settings
            if settings is None and getattr(info, "SettingsType", None) is not None:
                try:
                    settings = info.SettingsType()
                except Exception:
                    pass

            res = info.Handle(settings)
            match = bool(res)

            if getattr(rule, "IsReversed", False):
                match = not match

            return match
        except Exception:
            return False

    def _eval_group(self, group) -> bool | None:
        if not getattr(group, "IsEnabled", True):
            return None

        valid_rules = [r for r in getattr(group, "Rules", []) if getattr(r, "Id", "")]
        if not valid_rules:
            return None

        mode = getattr(group, "Mode", 0)
        match = (mode == 1)  # 1=And(且) 时初始为 True；0=Or(或) 时初始为 False

        for r in valid_rules:
            res = self._eval_rule(r)
            if res is None:
                continue

            if (not res) and mode == 1:
                match = False
                break

            if res and mode == 0:
                match = True
                break

        if getattr(group, "IsReversed", False):
            match = not match

        return match

    def _eval_ruleset(self, ruleset) -> bool:
        mode = getattr(ruleset, "Mode", 0)
        match = (mode == 1)

        groups = getattr(ruleset, "Groups", [])
        if not groups:
            return False

        valid_groups = [g for g in groups if getattr(g, "IsEnabled", True)]

        for g in valid_groups:
            res = self._eval_group(g)
            if res is None:
                continue

            if (not res) and mode == 1:
                match = False
                break

            if res and mode == 0:
                match = True
                break

        if getattr(ruleset, "IsReversed", False):
            match = not match

        return match

    def _update_live_status(self):
        rs = self._get_ruleset()
        if not rs:
            self.live_status_label.setText("")
            return

        runtime = self._get_live_runtime()
        if not runtime:
            self.live_status_label.setText("（状态：未连接运行时）")
            self.live_status_label.setStyleSheet("color: #888;")
            return

        is_rs_match = self._eval_ruleset(rs)
        if is_rs_match:
            self.live_status_label.setText(" 状态：✔️ 规则集满足")
            self.live_status_label.setStyleSheet("color: #0f7b0f;" if not isDarkTheme() else "color: #66cc66;")
        else:
            self.live_status_label.setText(" 状态：❌ 规则集不满足")
            self.live_status_label.setStyleSheet("color: #c42b1c;" if not isDarkTheme() else "color: #ff99a4;")

        for i in range(self.group_list.count()):
            if i >= len(rs.Groups): break
            item = self.group_list.item(i)
            g = rs.Groups[i]
            is_match = self._eval_group(g)
            base_text = item.data(Qt.UserRole + 1)
            if base_text:
                if is_match is None:
                    status_str = "⚪ 跳过/为空"
                else:
                    status_str = "✔️ 符合" if is_match else "❌ 不符"
                item.setText(f"{base_text}  [{status_str}]")

        if 0 <= self._current_group_index < len(rs.Groups):
            group = rs.Groups[self._current_group_index]
            for i in range(self.rule_list.count()):
                if i >= len(group.Rules): break
                item = self.rule_list.item(i)
                r = group.Rules[i]
                is_match = self._eval_rule(r)
                base_text = item.data(Qt.UserRole + 1)
                if base_text:
                    if is_match is None:
                        status_str = "⚪ 未配置"
                    else:
                        status_str = "✔️ 符合" if is_match else "❌ 不符"
                    item.setText(f"{base_text}  [{status_str}]")

    # =========================================================
    # Rule Picker
    # =========================================================

    def _get_rule_picker_groups(self):
        from automation.registry import get_registered_rule_ids, get_rule_info
        from automation.builtins import register_builtins
        register_builtins()

        groups = {}
        registered = set(get_registered_rule_ids())

        for g_name, ids in RULE_GROUPS.items():
            g_list = []
            for rid in ids:
                info = get_rule_info(rid)
                name = info.Name if info and getattr(info, "Name", None) else RULE_NAME_FALLBACKS.get(rid, rid)
                g_list.append((rid, name))
            if g_list:
                groups[g_name] = g_list

        known = {rid for ids in RULE_GROUPS.values() for rid in ids}
        extras = []
        for rid in sorted(registered):
            if rid not in known and rid not in HIDDEN_RULE_IDS:
                info = get_rule_info(rid)
                name = info.Name if info and getattr(info, "Name", None) else RULE_NAME_FALLBACKS.get(rid, rid)
                extras.append((rid, name))

        if extras:
            groups["其它"] = extras

        return groups

    def _on_add_group(self) -> None:
        rs = self._get_ruleset()
        if not rs:
            return
        from automation.models import RuleGroup
        rs.Groups.append(RuleGroup())
        self._current_group_index = len(rs.Groups) - 1
        self._reload_groups()
        self._update_ui_state()
        self.data_changed.emit()

    def _on_del_group(self) -> None:
        rs = self._get_ruleset()
        if not rs or self._current_group_index < 0:
            return
        rs.Groups.pop(self._current_group_index)
        self._current_group_index = -1
        self._reload_groups()
        self._update_ui_state()
        self.data_changed.emit()

    def _on_group_up(self) -> None:
        rs = self._get_ruleset()
        if not rs or self._current_group_index <= 0:
            return
        idx = self._current_group_index
        rs.Groups[idx - 1], rs.Groups[idx] = rs.Groups[idx], rs.Groups[idx - 1]
        self._current_group_index -= 1
        self._reload_groups()
        self.data_changed.emit()

    def _on_group_down(self) -> None:
        rs = self._get_ruleset()
        if not rs or self._current_group_index < 0 or self._current_group_index >= len(rs.Groups) - 1:
            return
        idx = self._current_group_index
        rs.Groups[idx + 1], rs.Groups[idx] = rs.Groups[idx], rs.Groups[idx + 1]
        self._current_group_index += 1
        self._reload_groups()
        self.data_changed.emit()

    def _on_add_rule(self) -> None:
        try:
            rs = self._get_ruleset()
            if not rs or self._current_group_index < 0:
                return

            from .automation_page import GroupedPickerDialog

            host = self.window() if self.window() is not None else self
            dlg = GroupedPickerDialog(
                "选择规则",
                self._get_rule_picker_groups(),
                RULE_DESCRIPTIONS,
                host
            )

            if dlg.exec_() == QDialog.Accepted and dlg.selected_id:
                group = rs.Groups[self._current_group_index]
                from automation.models import Rule
                rule = Rule(Id=dlg.selected_id)
                group.Rules.append(rule)
                self._current_rule_index = len(group.Rules) - 1

                self.group_list.blockSignals(True)
                self._reload_groups()
                self.group_list.setCurrentRow(self._current_group_index)
                self.group_list.blockSignals(False)

                self._reload_rules(select_current=True)
                self._update_ui_state()
                self.rule_selection_changed.emit("rule", rule)
                self.data_changed.emit()
        except Exception as e:
            import traceback
            traceback.print_exc()
            from qfluentwidgets import MessageBox
            w = MessageBox("发生错误", f"无法打开添加规则窗口：\n{e}", self.window())
            w.yesButton.setText("知道了")
            w.cancelButton.hide()
            w.exec_()

    def _on_del_rule(self) -> None:
        rs = self._get_ruleset()
        if not rs or self._current_group_index < 0 or self._current_rule_index < 0:
            return
        group = rs.Groups[self._current_group_index]
        group.Rules.pop(self._current_rule_index)
        self._current_rule_index = -1
        self._reload_groups()
        self._reload_rules()
        self._update_ui_state()
        self.data_changed.emit()

    def _on_rule_up(self) -> None:
        rs = self._get_ruleset()
        if not rs or self._current_group_index < 0 or self._current_rule_index <= 0:
            return
        group = rs.Groups[self._current_group_index]
        idx = self._current_rule_index
        group.Rules[idx - 1], group.Rules[idx] = group.Rules[idx], group.Rules[idx - 1]
        self._current_rule_index -= 1
        self._reload_rules(select_current=True)
        self.data_changed.emit()

    def _on_rule_down(self) -> None:
        rs = self._get_ruleset()
        if not rs or self._current_group_index < 0:
            return
        group = rs.Groups[self._current_group_index]
        if self._current_rule_index < 0 or self._current_rule_index >= len(group.Rules) - 1:
            return
        idx = self._current_rule_index
        group.Rules[idx + 1], group.Rules[idx] = group.Rules[idx], group.Rules[idx + 1]
        self._current_rule_index += 1
        self._reload_rules(select_current=True)
        self.data_changed.emit()

