"""Main chat screen — sidebar + message list + input."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, Static

from ..widgets.message_list import MessageList
from ..widgets.sidebar import ChannelSelected, ContactSelected, Sidebar


class ScreenReady(Message):
    """Posted when MainScreen is fully composed and widgets are queryable."""


class SendMessage(Message):
    """Emitted when the user presses Enter in the input box."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class MainScreen(Screen):
    """Primary screen: sidebar + chat area."""

    BINDINGS = [
        ("ctrl+q", "app.quit", "Quit"),
        ("ctrl+j", "app.join_channel", "Join Channel"),
        ("ctrl+l", "app.leave_channel", "Leave Channel"),
        ("ctrl+n", "app.add_contact", "Add Contact"),
    ]

    DEFAULT_CSS = """
    MainScreen {
        layout: horizontal;
    }
    #chat-area {
        width: 1fr;
    }
    #chat-header {
        height: 3;
        padding: 1 2;
        background: $primary-background;
        color: $text;
        text-style: bold;
    }
    #msg-input {
        dock: bottom;
        margin: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._current_target: str = ""
        self._current_is_dm: bool = False
        self._current_contact_id: str = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Sidebar(id="sidebar")
        with Vertical(id="chat-area"):
            yield Static("Select a channel or contact", id="chat-header")
            yield MessageList(id="message-list")
            yield Input(placeholder="Type a message…", id="msg-input")
        yield Footer()

    def on_mount(self) -> None:
        self.post_message(ScreenReady())

    # --- event handlers ----------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "msg-input":
            return
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        self.post_message(SendMessage(text))

    def on_channel_selected(self, event: ChannelSelected) -> None:
        name = event.name.lstrip("🔒 ")
        self._current_target = name
        self._current_is_dm = False
        self._current_contact_id = ""
        self.query_one("#chat-header", Static).update(f"# {name}")
        self.app.action_load_history()  # type: ignore[attr-defined]

    def on_contact_selected(self, event: ContactSelected) -> None:
        self._current_target = event.name
        self._current_is_dm = True
        self._current_contact_id = event.node_id
        self.query_one("#chat-header", Static).update(f"DM: {event.name}")
        self.app.action_load_history()  # type: ignore[attr-defined]

    # --- public accessors --------------------------------------------------

    @property
    def current_target(self) -> str:
        return self._current_target

    @property
    def is_dm(self) -> bool:
        return self._current_is_dm

    @property
    def current_contact_id(self) -> str:
        return self._current_contact_id

    @property
    def message_list(self) -> MessageList:
        return self.query_one("#message-list", MessageList)

    @property
    def sidebar(self) -> Sidebar:
        return self.query_one("#sidebar", Sidebar)
