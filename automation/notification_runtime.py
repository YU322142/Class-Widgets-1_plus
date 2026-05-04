from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


class AsyncSignalSource:
    """
    一个轻量替代 CancellationTokenSource / CompletedTokenSource 的对象。
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    async def wait(self) -> None:
        await self._event.wait()

    def is_set(self) -> bool:
        return self._event.is_set()


@dataclass
class NotificationSettings:
    IsNotificationEnabled: bool = True
    IsSpeechEnabled: bool = False
    IsNotificationEffectEnabled: bool = True
    IsNotificationSoundEnabled: bool = False
    NotificationSoundPath: str = ""
    IsSettingsEnabled: bool = False
    IsNotificationTopmostEnabled: bool = False


@dataclass
class NotificationContent:
    Content: Any = None
    ContentTemplate: Any = None
    ContentTemplateResourceKey: Any = None
    IsSpeechEnabled: bool = True
    SpeechContent: str = ""
    Duration: timedelta = timedelta(seconds=5)
    Color: Any = None
    EndTime: datetime | None = None

    @staticmethod
    def CreateTwoIconsMask(
        text: str,
        left_icon: str = "lucide(\ue0ff)",
        right_icon: str = "lucide(\ue224)",
        has_right_icon: bool = True,
        factory=None,
    ) -> "NotificationContent":
        content = NotificationContent(
            Content={
                "type": "two_icons_mask",
                "text": text,
                "left_icon": left_icon,
                "right_icon": right_icon,
                "has_right_icon": has_right_icon,
            },
            SpeechContent=text,
            ContentTemplateResourceKey="NotificationTwoIconsMaskTemplate",
        )
        if factory is not None:
            factory(content)
        return content

    @staticmethod
    def CreateSimpleTextContent(
        text: str,
        factory=None,
    ) -> "NotificationContent":
        content = NotificationContent(
            Content={
                "type": "simple_text",
                "text": text,
            },
            SpeechContent=text,
            ContentTemplateResourceKey="NotificationSimpleTextOverlayTemplate",
        )
        if factory is not None:
            factory(content)
        return content

    @staticmethod
    def CreateRollingTextContent(
        text: str,
        duration: timedelta | None = None,
        repeat_count: int = 2,
        factory=None,
    ) -> "NotificationContent":
        duration = duration or timedelta(seconds=20)
        content = NotificationContent(
            Content={
                "type": "rolling_text",
                "text": text,
                "duration_seconds": duration.total_seconds(),
                "repeat_count": repeat_count,
            },
            SpeechContent=text,
            Duration=duration,
        )
        if factory is not None:
            factory(content)
        return content


NotificationContent.Empty = NotificationContent()


@dataclass
class NotificationRequest:
    MaskContent: NotificationContent = field(default_factory=lambda: NotificationContent.Empty)
    OverlayContent: NotificationContent | None = None
    RequestNotificationSettings: NotificationSettings = field(default_factory=NotificationSettings)
    ChannelId: str = ""

    CancellationTokenSource: AsyncSignalSource = field(default_factory=AsyncSignalSource, repr=False)
    CompletedTokenSource: AsyncSignalSource = field(default_factory=AsyncSignalSource, repr=False)

    ChainedNextRequest: "NotificationRequest | None" = field(default=None, repr=False)
    NotificationSourceGuid: str = field(default="", repr=False)
    IsPriorityOverride: bool = field(default=False, repr=False)
    PriorityOverride: int = field(default=-1, repr=False)

    def Cancel(self) -> None:
        self.CancellationTokenSource.cancel()
