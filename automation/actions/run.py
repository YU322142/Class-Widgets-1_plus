from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
import sys
import webbrowser

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

    async def OnInvoke(self) -> None:
        run_type = self.Settings.RunType.value if hasattr(self.Settings.RunType, "value") else str(self.Settings.RunType)

        if run_type == "Application":
            self._run_application(self.Settings.Value, self.Settings.Args)
            return

        if run_type == "File":
            self._open_file(self.Settings.Value)
            return

        if run_type == "Folder":
            self._open_folder(self.Settings.Value)
            return

        if run_type == "Url":
            self._open_url(self.Settings.Value)
            return

        if run_type == "Command":
            await self._run_command_async(self.Settings.Value)
            return

        raise NotImplementedError(f"Unsupported RunType: {run_type}")

    async def OnInterrupted(self) -> None:
        if self._running_process is not None and self._running_process.returncode is None:
            try:
                self._running_process.kill()
            except Exception:
                pass

    def _run_application(self, filename: str, args: str) -> None:
        if self.Context is not None and getattr(self.Context, "open_application", None) is not None:
            result = self.Context.open_application(filename, args)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
            return

        argv = [filename]
        if args.strip():
            argv.extend(shlex.split(args, posix=(os.name != "nt")))
        subprocess.Popen(argv)

    def _open_file(self, path: str) -> None:
        if self.Context is not None and getattr(self.Context, "open_file", None) is not None:
            result = self.Context.open_file(path)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
            return
        self._open_path_native(path)

    def _open_folder(self, path: str) -> None:
        if self.Context is not None and getattr(self.Context, "open_folder", None) is not None:
            result = self.Context.open_folder(path)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
            return
        self._open_path_native(path)

    def _open_url(self, path: str) -> None:
        normalized = path.strip()
        if normalized and (":" not in normalized) and (not normalized.startswith("\\")):
            normalized = "https://" + normalized

        if self.Context is not None and getattr(self.Context, "open_url", None) is not None:
            result = self.Context.open_url(normalized)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
            return

        webbrowser.open(normalized)

    def _open_path_native(self, path: str) -> None:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
            return
        subprocess.Popen(["xdg-open", path])

    async def _run_command_async(self, command: str) -> None:
        self._running_process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            communicate_task = asyncio.create_task(self._running_process.communicate())
            stdout, stderr = await self.WaitAsync(communicate_task)
        except ActionInterruptedError:
            raise
        finally:
            process = self._running_process
            self._running_process = None

        stdout_text = self._truncate_output((stdout or b"").decode(errors="replace"))
        stderr_text = self._truncate_output((stderr or b"").decode(errors="replace"))

        if process is not None and process.returncode != 0:
            raise RuntimeError(
                f"Command failed (exit code: {process.returncode}).\n"
                f"stdout: {stdout_text or '(empty)'}\n"
                f"stderr: {stderr_text or '(empty)'}"
            )

    def _truncate_output(self, text: str) -> str:
        if len(text) <= self.MAX_OUTPUT_LEN:
            return text
        return text[: self.MAX_OUTPUT_LEN] + "\n…(truncated)"
