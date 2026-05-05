# automation/platform_open.py
"""
跨平台打开操作 —— 对齐 ClassIsland RunAction 的行为。

ClassIsland 的核心策略非常简洁：
  - Application / File / Folder: Process.Start + UseShellExecute = true
  - Url:  Windows用 ShellExecute，Linux 用 xdg-open，macOS 用 open
  - Command: cmd.exe /c 或 /bin/bash -c

本模块用Python 等效方式复现上述行为。
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from typing import Sequence


#============================================================
# 内部工具
# ============================================================

def _debug(logger, message: str) -> None:
    if logger is not None:
        try:
            logger.debug(message)
        except Exception:
            pass


def _normalize_url(url: str) -> str:
    """与 ClassIsland 完全一致的 URL 规范化逻辑。"""
    url = (url or "").strip()
    if not url:
        return url
    if ":" not in url and not url.startswith("\\"):
        return "https://" + url
    return url


def _shell_execute_win(file: str, args: str | None = None, logger=None) -> None:
    """
    Windows:调用 ShellExecuteW，等效于 .NET 的
    Process.Start(new ProcessStartInfo { FileName=..., Arguments=..., UseShellExecute=true })

    可以打开：- 普通 exe /带空格路径的 exe
      - .lnk 快捷方式
      - UWP / MSIX 应用
      - URL 协议 (https://, ms-settings:等)
      - 任意已注册文件类型
    """
    import ctypes
    _debug(logger, f"[platform_open] ShellExecuteW file={file!r} args={args!r}")
    ret = ctypes.windll.shell32.ShellExecuteW(None, "open", file, args, None, 1)
    # ShellExecuteW 返回值> 32 表示成功
    if ret <= 32:
        raise RuntimeError(f"ShellExecuteW 失败 (返回值={ret})，file={file!r} args={args!r}")


# ============================================================
# 公共 API
# ============================================================

def open_application(path: str, args: str = "", logger=None) -> None:
    """
    运行应用程序。对齐 ClassIsland:
      Process.Start(new ProcessStartInfo {FileName = path,
          Arguments = args,
          UseShellExecute = true
      });
    """
    path = str(path or "").strip()
    if not path:
        raise RuntimeError("应用程序路径为空，无法运行。")

    args = str(args or "").strip()

    _debug(logger, f"[platform_open] open_application path={path!r} args={args!r}")

    if sys.platform == "win32":
        # UseShellExecute = true 等效
        _shell_execute_win(path, args if args else None, logger=logger)
    else:
        # Linux / macOS: 直接 exec，参数需要自己拆分
        argv = [path]
        if args:
            argv.extend(shlex.split(args))
        _debug(logger, f"[platform_open] Popen argv={argv!r}")
        subprocess.Popen(argv)


def open_file(path: str, logger=None) -> None:
    """
    打开文件。对齐 ClassIsland:
      Process.Start(new ProcessStartInfo { FileName = path, UseShellExecute = true });
    """
    path = str(path or "").strip()
    if not path:
        raise RuntimeError("文件路径为空，无法打开。")

    _debug(logger, f"[platform_open] open_file path={path!r}")
    _shell_open(path, logger=logger)


def open_folder(path: str, logger=None) -> None:
    """
    打开文件夹。对齐 ClassIsland (与 open_file 完全相同):
      Process.Start(new ProcessStartInfo { FileName = path, UseShellExecute = true });
    """
    path = str(path or "").strip()
    if not path:
        raise RuntimeError("文件夹路径为空，无法打开。")

    _debug(logger, f"[platform_open] open_folder path={path!r}")
    _shell_open(path, logger=logger)


def open_url(url: str, logger=None) -> None:
    """
    打开 URL。对齐 ClassIsland:
      Windows: Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
      Linux:Process.Start(new ProcessStartInfo("xdg-open", path) { UseShellExecute = false });
      macOS:   Process.Start(new ProcessStartInfo("open", path) { UseShellExecute = false });
    """
    url = _normalize_url(url)
    if not url:
        raise RuntimeError("URL 为空，无法打开。")

    _debug(logger, f"[platform_open] open_url url={url!r}")

    if sys.platform == "win32":
        _shell_execute_win(url, logger=logger)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", url])
    else:
        # Linux —— 与 ClassIsland 完全一致：直接 xdg-open
        subprocess.Popen(["xdg-open", url])


# ============================================================
# 内部：统一的 shell-open（File / Folder 共用）
# ============================================================

def _shell_open(path: str, logger=None) -> None:
    """
    等效于 .NET Process.Start + UseShellExecute = true。
    """
    if sys.platform == "win32":
        _shell_execute_win(path, logger=logger)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        # Linux —— 与 ClassIsland 一致
        subprocess.Popen(["xdg-open", path])
