from __future__ import annotations

import asyncio
from typing import Any


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

    def ShowNotification(self, request, provider_guid: str = "", channel_guid: str = "", push_notifications: bool = True) -> None:
        consumer = self._get_consumer()
        if consumer is None:
            # 没消费者时直接视作完成，避免测试卡死
            request.CompletedTokenSource.cancel()
            return
        consumer.ReceiveNotifications([request])

    async def ShowNotificationAsync(self, request, provider_guid: str = "", channel_guid: str = "") -> None:
        self.ShowNotification(request, provider_guid=provider_guid, channel_guid=channel_guid, push_notifications=True)
        await request.CompletedTokenSource.wait()

    def ShowChainedNotifications(self, requests, provider_guid: str = "", channel_guid: str = "") -> None:
        if not requests:
            return
        for i in range(len(requests) - 1):
            requests[i].ChainedNextRequest = requests[i + 1]
        consumer = self._get_consumer()
        if consumer is None:
            for req in requests:
                req.CompletedTokenSource.cancel()
            return
        consumer.ReceiveNotifications(list(requests))

    async def ShowChainedNotificationsAsync(self, requests, provider_guid: str = "", channel_guid: str = "") -> None:
        self.ShowChainedNotifications(requests, provider_guid=provider_guid, channel_guid=channel_guid)
        await requests[-1].CompletedTokenSource.wait()
