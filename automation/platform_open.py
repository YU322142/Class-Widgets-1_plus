from __future__ import annotations

import os
import shlex
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Iterable, Sequence

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices


def _debug(logger, message: str) -> None:
    if logger is not None:
        try:
            logger.debug(message)
        except Exception:
            pass


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url

    if ":" not in url and not url.startswith("\\"):
        return "https://" + url
    return url


def _try_qt_open_url(url: str, logger=None) -> bool:
    try:
        ok = QDesktopServices.openUrl(QUrl(url))
        _debug(logger, f"[platform_open] QDesktopServices.openUrl({url!r}) -> {ok}")
        return bool(ok)
    except Exception as e:
        _debug(logger, f"[platform_open] QDesktopServices.openUrl({url!r}) failed: {e}")
        return False


def _try_qt_open_local(path: str, logger=None) -> bool:
    try:
        qurl = QUrl.fromLocalFile(str(Path(path).resolve()))
        ok = QDesktopServices.openUrl(qurl)
        _debug(logger, f"[platform_open] QDesktopServices.openUrl(local={path!r}) -> {ok}")
        return bool(ok)
    except Exception as e:
        _debug(logger, f"[platform_open] QDesktopServices.openUrl(local={path!r}) failed: {e}")
        return False


def _try_run_command(args: Sequence[str], logger=None, timeout: float = 8.0) -> bool:
    try:
        _debug(logger, f"[platform_open] trying command: {args!r}")
        result = subprocess.run(
            list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        if result.returncode == 0:
            _debug(logger, f"[platform_open] command ok: {args!r}")
            return True

        _debug(
            logger,
            f"[platform_open] command failed rc={result.returncode}: {args!r}, "
            f"stdout={result.stdout!r}, stderr={result.stderr!r}",
        )
        return False
    except FileNotFoundError:
        _debug(logger, f"[platform_open] command not found: {args!r}")
        return False
    except Exception as e:
        _debug(logger, f"[platform_open] command exception: {args!r}, err={e}")
        return False


def _linux_open_candidates(target: str) -> list[list[str]]:
    return [
        ["gio", "open", target],
        ["kioclient5", "exec", target],
        ["kioclient", "exec", target],
        ["gvfs-open", target],
        ["xdg-open", target],
    ]


def _mac_open_candidates(target: str) -> list[list[str]]:
    return [
        ["open", target],
    ]


def _windows_open_file(path: str) -> bool:
    os.startfile(path)  # type: ignore[attr-defined]
    return True


def open_url(url: str, logger=None) -> None:
    url = _normalize_url(url)
    if not url:
        raise RuntimeError("URL 为空，无法打开。")

    # 1) Qt
    if _try_qt_open_url(url, logger=logger):
        return

    # 2) 平台命令
    if os.name == "nt":
        try:
            _windows_open_file(url)
            return
        except Exception as e:
            _debug(logger, f"[platform_open] os.startfile(url) failed: {e}")
    elif sys.platform == "darwin":
        for cmd in _mac_open_candidates(url):
            if _try_run_command(cmd, logger=logger):
                return
    else:
        for cmd in _linux_open_candidates(url):
            if _try_run_command(cmd, logger=logger):
                return

    # 3) Python webbrowser fallback
    try:
        ok = webbrowser.open(url)
        _debug(logger, f"[platform_open] webbrowser.open({url!r}) -> {ok}")
        if ok:
            return
    except Exception as e:
        _debug(logger, f"[platform_open] webbrowser.open({url!r}) failed: {e}")

    raise RuntimeError(f"无法打开 URL：{url}")


def open_file(path: str, logger=None) -> None:
    path = str(path or "").strip()
    if not path:
        raise RuntimeError("文件路径为空，无法打开。")

    # 1) Qt
    if _try_qt_open_local(path, logger=logger):
        return

    # 2) 平台命令
    if os.name == "nt":
        try:
            _windows_open_file(path)
            return
        except Exception as e:
            _debug(logger, f"[platform_open] os.startfile(file) failed: {e}")
    elif sys.platform == "darwin":
        for cmd in _mac_open_candidates(path):
            if _try_run_command(cmd, logger=logger):
                return
    else:
        for cmd in _linux_open_candidates(path):
            if _try_run_command(cmd, logger=logger):
                return

    raise RuntimeError(f"无法打开文件：{path}")


def open_folder(path: str, logger=None) -> None:
    path = str(path or "").strip()
    if not path:
        raise RuntimeError("文件夹路径为空，无法打开。")

    # 1) Qt
    if _try_qt_open_local(path, logger=logger):
        return

    # 2) 平台命令
    if os.name == "nt":
        try:
            _windows_open_file(path)
            return
        except Exception as e:
            _debug(logger, f"[platform_open] os.startfile(folder) failed: {e}")
    elif sys.platform == "darwin":
        for cmd in _mac_open_candidates(path):
            if _try_run_command(cmd, logger=logger):
                return
    else:
        for cmd in _linux_open_candidates(path):
            if _try_run_command(cmd, logger=logger):
                return

    raise RuntimeError(f"无法打开文件夹：{path}")


def open_application(path: str, args: str = "", logger=None) -> None:
    path = str(path or "").strip()
    if not path:
        raise RuntimeError("应用程序路径为空，无法运行。")

    argv = [path]
    if args.strip():
        if os.name == "nt":
            argv.extend([x for x in args.split(" ") if x])
        else:
            argv.extend(shlex.split(args))

    _debug(logger, f"[platform_open] launching application argv={argv!r}")
    subprocess.Popen(argv)
