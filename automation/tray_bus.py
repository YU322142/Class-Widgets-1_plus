from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable


@dataclass
class TrayMenuItem:
    Id: str
    Header: str
    Callback: Callable[[], None]


class TrayMenuBus:
    """
    一个轻量的 tray 菜单总线，后面可桥接到你真实菜单/托盘实现。
    """

    def __init__(self) -> None:
        self.Items: dict[str, TrayMenuItem] = {}

    def AddMenuItem(self, header: str, callback) -> str:
        item_id = str(uuid.uuid4())
        self.Items[item_id] = TrayMenuItem(
            Id=item_id,
            Header=header,
            Callback=callback,
        )
        return item_id

    def UpdateMenuItem(self, item_id: str, header: str) -> None:
        if item_id in self.Items:
            self.Items[item_id].Header = header

    def RemoveMenuItem(self, item_id: str) -> None:
        self.Items.pop(item_id, None)

    def Click(self, item_id: str) -> None:
        if item_id in self.Items:
            self.Items[item_id].Callback()
