# automation/actions/run.py
"""
"运行"动作 —— 对齐 ClassIsland.Services.Automation.Actions.RunAction。
"""
from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
import sys

from automation.action_base import ActionBaseT, ActionInterruptedError
from automation.context import maybe_await
from automation.models import RunActionSettings
from automation.registry import register_action


@register_action("classisland.os.run", "运行", add_default_to_menu=False)
class RunAction(ActionBaseT[RunActionSettings]):
    MAX_OUTPUT_LEN = 2000

    def __init__(self, context=None, services=None) -> None:
        super().__init__(context=context, services=services)
        self._running_process: asyncio.subprocess.Process | None = None

    # =========================================================
    # 主入口
    # =========================================================

    async def OnInvoke(self) -> None:
        run_type = self.Settings.RunType.value if hasattr(self.Settings.RunType, "value") else str(self.Settings.RunType)

        if run_type == "Application":
            self._run_application(self.Settings.Value, self.Settings.Args)
            return

        if run_type == "File" or run_type == "Folder":
            # ClassIsland: File和 Folder 用完全相同的代码
            self._shell_open(self.Settings.Value)
            return

        if run_type == "Url":
            self._open_url(self.Settings.Value)
            return

        if run_type == "Command":
            await self._run_command_async(self.Settings.Value)
            return

        raise NotImplementedError(f"Unsupported RunType: {run_type}")

    # =========================================================
    # 中断 —— 对齐 ClassIsland: process.Kill(entireProcessTree: true)
    # =========================================================

    async def OnInterrupted(self) -> None:
        proc = self._running_process
        if proc is None or proc.returncode is not None:
            return
        try:
            import psutil
            parent = psutil.Process(proc.pid)
            for child in parent.children(recursive=True):
                try:
                    child.kill()
                except Exception:
                    pass
            parent.kill()
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    # =========================================================
    # Application —— 对齐 ClassIsland: UseShellExecute = true
    # =========================================================

    def _run_application(self, filename: str, args: str) -> None:
        # 优先走 Context hook（主程序可以注入自定义实现）
        if self.Context is not None and getattr(self.Context, "open_application", None) is not None:
            result = self.Context.open_application(filename, args)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
            return

        # Fallback: 直接对齐 ClassIsland
        from automation.platform_open import open_application
        open_application(filename, args)

    # =========================================================
    # File / Folder —— 对齐 ClassIsland: UseShellExecute = true
    # =========================================================

    def _shell_open(self, path: str) -> None:
        # 优先走 Context hook
        if self.Context is not None:
            # File和 Folder 在 ClassIsland 里是同一段代码，
            # 但 ClassWidgets 的 Context 分了两个hook，这里兼容一下
            run_type = self.Settings.RunType.value if hasattr(self.Settings.RunType, "value") else str(self.Settings.RunType)
            hook_name = "open_folder" if run_type == "Folder" else "open_file"
            hook = getattr(self.Context, hook_name, None)
            if hook is not None:
                result = hook(path)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
                return

        # Fallback: 直接对齐 ClassIsland
        from automation.platform_open import _shell_open
        _shell_open(path)

    # =========================================================
    # URL —— 对齐 ClassIsland 的平台分支
    # =========================================================

    def _open_url(self, url: str) -> None:
        normalized = (url or "").strip()
        if normalized and (":" not in normalized) and (not normalized.startswith("\\")):
            normalized = "https://" + normalized

        # 优先走 Context hook
        if self.Context is not None and getattr(self.Context, "open_url", None) is not None:
            result = self.Context.open_url(normalized)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
            return

        # Fallback: 直接对齐 ClassIsland
        from automation.platform_open import open_url
        open_url(normalized)

    # =========================================================
    # Command —— 对齐 ClassIsland:
    #   Windows: cmd.exe /c "command"
    #   Linux/macOS: /bin/bash -c "command"
    # =========================================================

    async def _run_command_async(self, command: str) -> None:
        if sys.platform == "win32":
            #对齐 ClassIsland: new ProcessStartInfo("cmd.exe", $"/c \"{command}\"")
            self._running_process = await asyncio.create_subprocess_exec(
                "cmd.exe", "/c", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,)
        else:
            # 对齐 ClassIsland: new ProcessStartInfo("/bin/bash", $"-c \"{command}\"")
            escaped = command.replace('"', '\\"')
            self._running_process = await asyncio.create_subprocess_exec(
                "/bin/bash", "-c", escaped,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        try:
            stdout, stderr = await self.WaitAsync(self._running_process.communicate())
        except ActionInterruptedError:
            raise
        finally:
            process = self._running_process
            self._running_process = None

        stdout_text = self._truncate_output((stdout or b"").decode(errors="replace"))
        stderr_text = self._truncate_output((stderr or b"").decode(errors="replace"))

        if process is not None and process.returncode != 0:
            raise RuntimeError(
                f"命令执行失败 (退出代码: {process.returncode})。\n"
                f"标准输出：{stdout_text or '(空)'}\n"
                f"错误输出：{stderr_text or '(空)'}"
            )

    def _truncate_output(self, text: str) -> str:
        if len(text) <= self.MAX_OUTPUT_LEN:
            return text
        return text[: self.MAX_OUTPUT_LEN] + "\n…(已截断)"
