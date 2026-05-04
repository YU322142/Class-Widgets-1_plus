from __future__ import annotations

from datetime import timedelta

from automation.action_base import ActionBaseT
from automation.models import NotificationActionSettings
from automation.notification_runtime import NotificationContent, NotificationRequest
from automation.registry import register_action


@register_action("classisland.showNotification", "显示提醒", add_default_to_menu=False)
class NotificationAction(ActionBaseT[NotificationActionSettings]):
    def __init__(self, context=None, services=None) -> None:
        super().__init__(context=context, services=services)
        self._request: NotificationRequest | None = None

    def _get_host(self):
        if self.Context is not None and getattr(self.Context, "notification_host", None) is not None:
            return self.Context.notification_host
        raise RuntimeError("AutomationContext.notification_host is not configured")

    async def OnInvoke(self) -> None:
        host = self._get_host()

        request = NotificationRequest(
            MaskContent=NotificationContent.CreateTwoIconsMask(
                self.Settings.Mask,
                has_right_icon=False,
                factory=lambda x: self._setup_mask_content(x),
            ),
            OverlayContent=(
                None
                if (not self.Settings.Content or self.Settings.ContentDurationSeconds <= 0)
                else NotificationContent.CreateSimpleTextContent(
                    self.Settings.Content,
                    factory=lambda x: self._setup_overlay_content(x),
                )
            ),
        )
        request.RequestNotificationSettings.IsSettingsEnabled = self.Settings.IsAdvancedSettingsEnabled
        request.RequestNotificationSettings.IsNotificationEffectEnabled = self.Settings.IsEffectEnabled
        request.RequestNotificationSettings.IsNotificationSoundEnabled = self.Settings.IsSoundEffectEnabled
        request.RequestNotificationSettings.IsNotificationTopmostEnabled = self.Settings.IsTopmostEnabled
        request.RequestNotificationSettings.NotificationSoundPath = self.Settings.CustomSoundEffectPath
        request.RequestNotificationSettings.IsSpeechEnabled = True

        self._request = request

        if self.Settings.IsWaitForCompleteEnabled:
            await host.ShowNotificationAsync(request)
        else:
            host.ShowNotification(request)

    async def OnInterrupted(self) -> None:
        if self._request is not None:
            self._request.CancellationTokenSource.cancel()

    def _setup_mask_content(self, content: NotificationContent) -> None:
        content.Duration = timedelta(seconds=max(0.0, self.Settings.MaskDurationSeconds))
        content.IsSpeechEnabled = self.Settings.IsMaskSpeechEnabled

    def _setup_overlay_content(self, content: NotificationContent) -> None:
        content.IsSpeechEnabled = self.Settings.IsContentSpeechEnabled
        content.Duration = timedelta(seconds=max(0.0, self.Settings.ContentDurationSeconds))
