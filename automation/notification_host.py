from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

from automation.async_tools import schedule_coro


class NotificationHost:
    """
    一个轻量版 NotificationHost，先满足 NotificationAction 的兼容需求：
    - show notification
    - wait for complete
    - chained notifications
    - register consumer
    """

    def __init__(self) -> None:
        self._consumers: list[tuple[int, Any]] = []
        self._queue: deque[Any] = deque()
        self._worker = None
        self._worker_running = False

    def RegisterNotificationConsumer(self, consumer: Any, priority: int) -> None:
        self._consumers.append((priority, consumer))
        self._consumers.sort(key=lambda x: x[0])

    def UnregisterNotificationConsumer(self, consumer: Any) -> None:
        self._consumers = [(p, c) for p, c in self._consumers if c is not consumer]

    def _get_consumer(self) -> Any | None:
        for _, consumer in self._consumers:
            if getattr(consumer, "AcceptsNotificationRequests", True) and getattr(consumer, "QueuedNotificationCount", 0) <= 0:
                return consumer
        return None

    def _has_accepting_consumer(self) -> bool:
        return any(getattr(consumer, "AcceptsNotificationRequests", True) for _, consumer in self._consumers)

    def _ensure_worker(self) -> None:
        if self._worker_running:
            return
        self._worker_running = True
        self._worker = schedule_coro(self._drain_queue())

    def _enqueue(self, request) -> None:
        self._queue.append(request)
        self._ensure_worker()

    async def _wait_for_consumer(self) -> Any | None:
        while True:
            consumer = self._get_consumer()
            if consumer is not None:
                return consumer
            if not self._has_accepting_consumer():
                return None
            await asyncio.sleep(0.05)

    async def _drain_queue(self) -> None:
        try:
            while self._queue:
                request = self._queue.popleft()

                if request.CancellationTokenSource.is_set():
                    request.CompletedTokenSource.cancel()
                    continue

                consumer = await self._wait_for_consumer()
                if consumer is None:
                    # 没消费者时直接视作完成，避免自动化动作永久等待。
                    request.CompletedTokenSource.cancel()
                    continue

                consumer.ReceiveNotifications([request])
                await request.CompletedTokenSource.wait()
        finally:
            self._worker_running = False
            if self._queue:
                self._ensure_worker()

    def ShowNotification(self, request, provider_guid: str = "", channel_guid: str = "", push_notifications: bool = True) -> None:
        self._enqueue(request)

    async def ShowNotificationAsync(self, request, provider_guid: str = "", channel_guid: str = "") -> None:
        self.ShowNotification(request, provider_guid=provider_guid, channel_guid=channel_guid, push_notifications=True)
        await request.CompletedTokenSource.wait()

    def ShowChainedNotifications(self, requests, provider_guid: str = "", channel_guid: str = "") -> None:
        if not requests:
            return
        for i in range(len(requests) - 1):
            requests[i].ChainedNextRequest = requests[i + 1]
        for request in requests:
            self._enqueue(request)

    async def ShowChainedNotificationsAsync(self, requests, provider_guid: str = "", channel_guid: str = "") -> None:
        self.ShowChainedNotifications(requests, provider_guid=provider_guid, channel_guid=channel_guid)
        await requests[-1].CompletedTokenSource.wait()
