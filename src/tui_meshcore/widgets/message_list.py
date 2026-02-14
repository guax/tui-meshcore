"""Message list widget — scrollable chat history."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static


class MessageBubble(Static):
    """A single chat message displayed in the message list."""

    DEFAULT_CSS = """
    MessageBubble {
        width: 100%;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    MessageBubble.me {
        color: $success;
    }
    MessageBubble.other {
        color: $text;
    }
    MessageBubble.system {
        color: $warning;
        text-style: italic;
    }
    """

    def __init__(
        self,
        content: str,
        *,
        sender_name: str = "",
        timestamp: float | None = None,
        kind: str = "other",
    ) -> None:
        super().__init__()
        self._content = content
        self._sender_name = sender_name
        self._timestamp = timestamp or time.time()
        self.add_class(kind)

    def render(self) -> str:
        ts = datetime.fromtimestamp(self._timestamp).strftime("%H:%M")
        if "system" in self.classes:
            return f"[dim]{ts}[/] [italic]{self._content}[/]"
        name = self._sender_name or "?"
        return f"[dim]{ts}[/] [bold]{name}[/]: {self._content}"


class MessageList(VerticalScroll):
    """Scrollable list of MessageBubble widgets."""

    DEFAULT_CSS = """
    MessageList {
        height: 1fr;
        padding: 1 1;
    }
    """

    def add_message(
        self,
        content: str,
        *,
        sender_name: str = "",
        timestamp: float | None = None,
        kind: str = "other",
    ) -> None:
        bubble = MessageBubble(
            content,
            sender_name=sender_name,
            timestamp=timestamp,
            kind=kind,
        )
        self.mount(bubble)
        self.scroll_end(animate=False)

    def add_system(self, text: str) -> None:
        self.add_message(text, kind="system")

    def clear_messages(self) -> None:
        for child in list(self.children):
            child.remove()

    def load_history(self, messages: list[dict[str, Any]], my_id: str = "") -> None:
        """Bulk-load persisted messages."""
        self.clear_messages()
        for m in messages:
            kind = "me" if m.get("sender_id") == my_id or m.get("status") == "sent" else "other"
            self.add_message(
                m["content"],
                sender_name=m.get("sender_name", ""),
                timestamp=m.get("timestamp"),
                kind=kind,
            )
