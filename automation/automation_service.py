from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable

from .action_service import ActionService
from .compat import load_workflows_from_file, save_workflows_to_file
from .enums import ActionSetStatus
from .models import ActionSet, TriggerSettings, Workflow
from .registry import create_trigger_instance
from .ruleset_service import RulesetService
from concurrent.futures import Future as ConcurrentFuture
from .async_tools import schedule_coro



class AutomationService:
    """
    对齐 ClassIsland.Services.AutomationService 的 Python 版核心调度器。

    当前目标：
    - 管理 workflows
    - load/unload triggers
    - trigger -> invoke/revert ActionSet
    - ruleset 变化时触发 revert
    """

    def __init__(
        self,
        action_service: ActionService,
        ruleset_service: RulesetService,
        logger: logging.Logger | None = None,
        context: Any | None = None,
        services: Any | None = None,
        is_enabled_getter: Callable[[], bool] | None = None,
    ) -> None:
        self.Logger = logger or logging.getLogger(__name__)
        self.ActionService = action_service
        self.RulesetService = ruleset_service
        self.Context = context
        self.Services = services
        self.IsEnabledGetter = is_enabled_getter or (lambda: True)

        self.Workflows: list[Workflow] = []
        self.Configs: list[str] = []

        self._started: bool = False
        self._config_path: Path | None = None
        self._background_tasks: set[asyncio.Task] = set()

        self.RulesetService.AddStatusUpdatedHandler(self._OnRulesetStatusUpdated)

    # =========================================================
    # Config APIs
    # =========================================================

    def LoadFromFile(self, path: str | Path) -> None:
        workflows = load_workflows_from_file(path)
        self._config_path = Path(path)
        self.SetWorkflows(workflows)

    def SaveToFile(self, path: str | Path | None = None) -> None:
        target = Path(path) if path is not None else self._config_path
        if target is None:
            raise ValueError("No config path is set for AutomationService.")
        save_workflows_to_file(target, self.Workflows)

    def SetWorkflows(self, workflows: list[Workflow]) -> None:
        if self._started:
            self._UnloadAllWorkflows()
        self.Workflows = workflows
        if self._started:
            self._LoadAllWorkflows()

    def RefreshConfigs(self, automations_dir: str | Path) -> None:
        base = Path(automations_dir)
        if not base.exists():
            self.Configs = []
            return
        self.Configs = sorted([p.stem for p in base.glob("*.json")])

    # =========================================================
    # Lifecycle
    # =========================================================

    def Start(self) -> None:
        if self._started:
            return
        self._started = True
        self._LoadAllWorkflows()

    async def Stop(self) -> None:
        if not self._started:
            return

        await self.InterruptAllWorkflows()
        self._UnloadAllWorkflows()
        self._started = False

    async def DrainTasks(self) -> None:
        """
        给测试和调试使用：等待由 trigger/ruleset 触发的后台 task 执行完。
        """
        while self._background_tasks:
            tasks = list(self._background_tasks)
            if not tasks:
                break

            awaitables = []
            for task in tasks:
                if isinstance(task, asyncio.Future):
                    awaitables.append(task)
                else:
                    awaitables.append(asyncio.wrap_future(task))

            await asyncio.gather(*awaitables, return_exceptions=True)

    # =========================================================
    # Workflow load/unload
    # =========================================================

    def _LoadAllWorkflows(self) -> None:
        for workflow in self.Workflows:
            self._LoadWorkflow(workflow)

    def _UnloadAllWorkflows(self) -> None:
        for workflow in self.Workflows:
            self._UnloadWorkflow(workflow)

    def _LoadWorkflow(self, workflow: Workflow) -> None:
        for trigger_settings in workflow.Triggers:
            self._LoadTrigger(workflow, trigger_settings)
        workflow._loaded = True
        self.Logger.debug("Loaded workflow: %s", workflow.ActionSet.Name)

    def _UnloadWorkflow(self, workflow: Workflow) -> None:
        for trigger_settings in workflow.Triggers:
            self._UnloadTrigger(workflow, trigger_settings)
        workflow._loaded = False
        self.Logger.debug("Unloaded workflow: %s", workflow.ActionSet.Name)

    def _LoadTrigger(self, workflow: Workflow, trigger_settings: TriggerSettings) -> None:
        if trigger_settings.TriggerInstance is not None:
            return

        trigger = create_trigger_instance(
            trigger_settings,
            context=self.Context,
            services=self.Services,
        )
        trigger_settings.TriggerInstance = trigger

        if trigger is None:
            self.Logger.warning(
                "Trigger provider not found: %s in workflow %s",
                trigger_settings.Id,
                workflow.ActionSet.Name,
            )
            return

        trigger.SettingsInternal = trigger_settings.Settings
        trigger.AssociatedWorkflow = workflow
        trigger.AddTriggeredHandler(self._TriggerTriggered)
        trigger.AddTriggeredRevertHandler(self._TriggerTriggeredRevert)
        trigger.Loaded()

    def _UnloadTrigger(self, workflow: Workflow, trigger_settings: TriggerSettings) -> None:
        trigger = trigger_settings.TriggerInstance
        if trigger is None:
            return

        try:
            trigger.UnLoaded()
        finally:
            trigger.RemoveTriggeredHandler(self._TriggerTriggered)
            trigger.RemoveTriggeredRevertHandler(self._TriggerTriggeredRevert)
            trigger.AssociatedWorkflow = None
            trigger_settings.TriggerInstance = None

    # =========================================================
    # Trigger event handlers
    # =========================================================

    def _TriggerTriggered(self, trigger: Any) -> None:
        if not self.IsEnabledGetter():
            return

        workflow: Workflow = trigger.AssociatedWorkflow
        action_set = workflow.ActionSet

        if not action_set.IsEnabled:
            return

        if action_set.IsRevertEnabled and action_set.Status != ActionSetStatus.Normal:
            return

        if workflow.IsConditionEnabled and not self.RulesetService.IsRulesetSatisfied(workflow.Ruleset):
            return

        self.Logger.debug(
            "Workflow triggered: %s by %s",
            action_set.Name,
            getattr(trigger, "__class__", type(trigger)).__name__,
        )
        self._schedule(self.ActionService.InvokeActionSetAsync(action_set))

    def _TriggerTriggeredRevert(self, trigger: Any) -> None:
        if not self.IsEnabledGetter():
            return

        workflow: Workflow = trigger.AssociatedWorkflow
        action_set = workflow.ActionSet

        if action_set.Status != ActionSetStatus.IsOn:
            return

        self.Logger.debug(
            "Workflow revert triggered: %s by %s",
            action_set.Name,
            getattr(trigger, "__class__", type(trigger)).__name__,
        )
        self._schedule(self.ActionService.RevertActionSetAsync(action_set))

    def _OnRulesetStatusUpdated(self) -> None:
        if not self.IsEnabledGetter():
            return

        for workflow in self.Workflows:
            action_set = workflow.ActionSet

            if not workflow.IsConditionEnabled:
                continue
            if not action_set.IsRevertEnabled:
                continue
            if action_set.Status != ActionSetStatus.IsOn:
                continue

            if self.RulesetService.IsRulesetSatisfied(workflow.Ruleset):
                continue

            self.Logger.debug("Ruleset invalidated workflow, reverting: %s", action_set.Name)
            self._schedule(self.ActionService.RevertActionSetAsync(action_set))

    # =========================================================
    # Interrupt
    # =========================================================

    async def InterruptAllWorkflows(self) -> None:
        for workflow in self.Workflows:
            await self.ActionService.InterruptActionSetAsync(workflow.ActionSet)

    # =========================================================
    # Internal task scheduling
    # =========================================================

    def _schedule(self, coro: Any):
        task = schedule_coro(coro)
        self._background_tasks.add(task)

        def _done_callback(t):
            self._background_tasks.discard(t)
            try:
                t.result()
            except Exception:
                self.Logger.exception("Background automation task failed")

        task.add_done_callback(_done_callback)
        return task

