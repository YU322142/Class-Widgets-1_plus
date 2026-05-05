from __future__ import annotations

import ctypes
import os
import shlex
import subprocess
import sys
from typing import Sequence


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


def _build_external_env() -> dict[str, str]:
    """
    为外部系统程序构造“干净”的环境。
    重点解决 Linux 便携/单文件包把自己的运行时环境污染给 xdg-open / 浏览器 / 文件管理器的问题。
    """
    env = os.environ.copy()

    if sys.platform.startswith("linux"):
        for key in (
            "LD_LIBRARY_PATH",
            "PYTHONHOME",
            "PYTHONPATH",
            "QT_PLUGIN_PATH",
            "QML2_IMPORT_PATH",
            "GI_TYPELIB_PATH",
            "GTK_PATH",
            "GIO_EXTRA_MODULES",
            "APPDIR",
            "APPIMAGE",
            "ARGV0",
        ):
            env.pop(key, None)

        # 对 PyInstaller onefile / 类似环境更友好；即使不是 PyInstaller，一般也无害
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"

    return env


def _shell_execute_win(file: str, parameters: str | None = None, logger=None) -> None:
    _debug(logger, f"[platform_open] ShellExecuteW file={file!r} args={parameters!r}")
    ret = ctypes.windll.shell32.ShellExecuteW(None, "open", file, parameters, None, 1)
    if ret <= 32:
        raise RuntimeError(
            f"ShellExecuteW failed: code={ret}, file={file!r}, args={parameters!r}"
        )


def _try_spawn_command(
    args: Sequence[str],
    *,
    logger=None,
    env: dict[str, str] | None = None,
    settle_seconds: float = 0.8,
) -> bool:
    try:
        _debug(logger, f"[platform_open] trying command: {list(args)!r}")
        proc = subprocess.Popen(
            list(args),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=(os.name != "nt"),
        )
    except FileNotFoundError:
        _debug(logger, f"[platform_open] command not found: {list(args)!r}")
        return False
    except Exception as e:
        _debug(logger, f"[platform_open] command exception: {list(args)!r}, err={e}")
        return False

    try:
        rc = proc.wait(timeout=settle_seconds)
    except subprocess.TimeoutExpired:
        _debug(logger, f"[platform_open] command assumed success (still running): {list(args)!r}")
        return True

    if rc == 0:
        _debug(logger, f"[platform_open] command success: {list(args)!r}")
        return True

    _debug(logger, f"[platform_open] command failed rc={rc}: {list(args)!r}")
    return False


def _linux_shell_open_candidates(target: str) -> list[list[str]]:
    return [
        ["xdg-open", target],
        ["gio", "open", target],
        ["kioclient5", "exec", target],
        ["kioclient", "exec", target],
        ["gvfs-open", target],
    ]


def _linux_url_candidates(url: str) -> list[list[str]]:
    return [
        ["xdg-open", url],
        ["gio", "open", url],
        ["sensible-browser", url],
        ["x-www-browser", url],
        ["firefox", url],
        ["chromium", url],
        ["chromium-browser", url],
        ["google-chrome", url],
        ["microsoft-edge", url],
        ["opera", url],
    ]


def _open_with_system_default(target: str, logger=None) -> None:
    if sys.platform == "win32":
        _shell_execute_win(target, logger=logger)
        return

    env = _build_external_env()

    if sys.platform == "darwin":
        if _try_spawn_command(["open", target], logger=logger, env=env):
            return
        raise RuntimeError(f"无法通过 open 打开目标：{target}")

    for cmd in _linux_shell_open_candidates(target):
        if _try_spawn_command(cmd, logger=logger, env=env):
            return

    raise RuntimeError(f"无法通过系统默认程序打开目标：{target}")


def open_url(url: str, logger=None) -> None:
    url = _normalize_url(url)
    if not url:
        raise RuntimeError("URL 为空，无法打开。")

    _debug(logger, f"[platform_open] open_url url={url!r}")

    if sys.platform == "win32":
        _shell_execute_win(url, logger=logger)
        return

    env = _build_external_env()

    if sys.platform == "darwin":
        if _try_spawn_command(["open", url], logger=logger, env=env):
            return
        raise RuntimeError(f"无法打开 URL：{url}")

    for cmd in _linux_url_candidates(url):
        if _try_spawn_command(cmd, logger=logger, env=env):
            return

    raise RuntimeError(f"无法打开 URL：{url}")


def open_file(path: str, logger=None) -> None:
    path = str(path or "").strip()
    if not path:
        raise RuntimeError("文件路径为空，无法打开。")

    _debug(logger, f"[platform_open] open_file path={path!r}")
    _open_with_system_default(path, logger=logger)


def open_folder(path: str, logger=None) -> None:
    path = str(path or "").strip()
    if not path:
        raise RuntimeError("文件夹路径为空，无法打开。")

    _debug(logger, f"[platform_open] open_folder path={path!r}")
    _open_with_system_default(path, logger=logger)


def open_application(path: str, args: str = "", logger=None) -> None:
    path = str(path or "").strip()
    if not path:
        raise RuntimeError("应用程序路径为空，无法运行。")

    args = str(args or "").strip()
    _debug(logger, f"[platform_open] open_application path={path!r} args={args!r}")

    if sys.platform == "win32":
        _shell_execute_win(path, args or None, logger=logger)
        return

    env = _build_external_env()

    if sys.platform == "darwin" and (path.lower().endswith(".app") or os.path.isdir(path)):
        cmd = ["open", path]
        if args:
            try:
                cmd.append("--args")
                cmd.extend(shlex.split(args))
            except Exception as e:
                raise RuntimeError(f"无法解析应用程序参数：{args!r}，错误：{e}") from e

        if _try_spawn_command(cmd, logger=logger, env=env):
            return

        raise RuntimeError(f"无法启动应用程序：{path}")

    argv = [path]
    if args:
        try:
            argv.extend(shlex.split(args))
        except Exception as e:
            raise RuntimeError(f"无法解析应用程序参数：{args!r}，错误：{e}") from e

    try:
        _debug(logger, f"[platform_open] Popen argv={argv!r}")
        subprocess.Popen(
            argv,
            env=env,
            start_new_session=(os.name != "nt"),
        )
        return
    except FileNotFoundError as e:
        _debug(logger, f"[platform_open] direct exec not found: {argv!r}, err={e}")
        if not args:
            _open_with_system_default(path, logger=logger)
            return
        raise RuntimeError(f"找不到应用程序：{path}") from e
    except OSError as e:
        _debug(logger, f"[platform_open] direct exec failed: {argv!r}, err={e}")
        if not args:
            _open_with_system_default(path, logger=logger)
            return
        raise RuntimeError(f"启动应用程序失败：{path}，错误：{e}") from e
