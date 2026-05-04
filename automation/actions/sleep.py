from __future__ import annotations

import time

from automation.action_base import ActionBaseT, ActionInterruptedError
from automation.models import SleepActionSettings
from automation.registry import register_action


@register_action("classisland.action.sleep", "等待时长")
class SleepAction(ActionBaseT[SleepActionSettings]):
    """
    对齐 ClassIsland 的 SleepAction：
    - 按秒等待
    - 可被中断
    - 尝试更新 Progress
    """

    async def OnInvoke(self) -> None:
        seconds = float(getattr(self.Settings, "Value", 5.0) or 0.0)

        if seconds <= 0:
            self.ActionItem.Progress = 100
            return

        start = time.monotonic()
        self.ActionItem.Progress = 0.0

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= seconds:
                self.ActionItem.Progress = 100.0
                break

            # 更新进度
            self.ActionItem.Progress = max(0.0, min(100.0, elapsed * 100.0 / seconds))

            # 每 100ms 检查一次中断
            await self.SleepWithInterrupt(0.1)

    async def OnInterrupted(self) -> None:
        # 保持与其它 action 一致：中断时由基类流程收尾
        return
