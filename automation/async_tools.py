from __future__ import annotations

import asyncio
import inspect
import threading
from concurrent.futures import Future
from typing import Any


_background_loop: asyncio.AbstractEventLoop | None = None
_background_thread: threading.Thread | None = None
_background_ready = threading.Event()
_background_lock = threading.Lock()


def _background_loop_worker() -> None:
    global _background_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _background_loop = loop
    _background_ready.set()
    loop.run_forever()

    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    finally:
        loop.close()


def ensure_background_loop() -> asyncio.AbstractEventLoop:
    global _background_thread, _background_loop

    if _background_loop is not None and _background_loop.is_running():
        return _background_loop

    with _background_lock:
        if _background_loop is not None and _background_loop.is_running():
            return _background_loop

        _background_ready.clear()
        _background_thread = threading.Thread(
            target=_background_loop_worker,
            name="AutomationAsyncLoop",
            daemon=True,
        )
        _background_thread.start()
        _background_ready.wait(timeout=5)

        if _background_loop is None:
            raise RuntimeError("Failed to start automation background asyncio loop")

        return _background_loop


def schedule_coro(coro) -> asyncio.Task | Future:
    """
    如果当前线程已有 asyncio running loop，就在当前 loop create_task；
    否则提交到后台 asyncio loop 线程。
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        return loop.create_task(coro)

    bg_loop = ensure_background_loop()
    return asyncio.run_coroutine_threadsafe(coro, bg_loop)


def schedule_awaitable(value: Any) -> asyncio.Task | Future | None:
    if inspect.isawaitable(value):
        return schedule_coro(value)
    return None


def stop_background_loop() -> None:
    global _background_loop, _background_thread

    loop = _background_loop
    thread = _background_thread

    if loop is not None and loop.is_running():
        loop.call_soon_threadsafe(loop.stop)

    if thread is not None and thread.is_alive():
        thread.join(timeout=2)

    _background_loop = None
    _background_thread = None
