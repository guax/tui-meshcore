"""Sidebar widget — channels, contacts, and status."""

from __future__ import annotations

import logging
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView, Static

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Messages emitted by the sidebar
# ---------------------------------------------------------------------------

class ChannelSelected(Message):
    def __init__(self, name: str) -> None:
        super().__init__()
        logger.info(f"Selected channel: {name}")
        self.name = name


class ContactSelected(Message):
    def __init__(self, node_id: str, name: str) -> None:
        super().__init__()
        self.node_id = node_id
        self.name = name


# ---------------------------------------------------------------------------
# Sub-widgets
# ---------------------------------------------------------------------------

class StatusBar(Static):
    """Displays radio online/offline and identity hash."""

    radio_online: reactive[bool] = reactive(False)
    identity_hex: reactive[str] = reactive("")

    def render(self) -> str:
        status = "[bold green]● Online[/]" if self.radio_online else "[bold red]● Offline[/]"
        ident = self.identity_hex or "—"
        return f"{status}\n[dim]{ident}[/]"


class ChannelList(ListView):
    """List of channels the user has joined."""

    DEFAULT_CSS = """
    ChannelList {
        height: auto;
        max-height: 50%;
    }
    """

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        name = event.item.name or ""
        self.post_message(ChannelSelected(name))


class ContactList(ListView):
    """List of known contacts / recently-seen nodes."""

    DEFAULT_CSS = """
    ContactList {
        height: auto;
        max-height: 50%;
    }
    """

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        node_id = item.name or ""
        label = item.query_one(Label)
        display = str(label.render())
        self.post_message(ContactSelected(node_id, display))


# ---------------------------------------------------------------------------
# Main sidebar composite
# ---------------------------------------------------------------------------

class Sidebar(Vertical):
    """Left-hand sidebar containing channels, contacts, and status."""

    DEFAULT_CSS = """
    Sidebar {
        width: 28;
        dock: left;
        background: $surface;
        border-right: solid $primary-background;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status-bar")
        yield Label("[bold]Channels[/]", classes="section-title")
        yield ChannelList(id="channel-list")
        yield Label("[bold]Contacts[/]", classes="section-title")
        yield ContactList(id="contact-list")

    # --- public helpers called by the app ----------------------------------

    def set_status(self, *, online: bool, identity: str = "") -> None:
        bar = self.query_one("#status-bar", StatusBar)
        bar.radio_online = online
        bar.identity_hex = identity

    def set_channels(self, channels: list[dict]) -> None:
        lv = self.query_one("#channel-list", ChannelList)
        lv.clear()
        for ch in channels:
            name = ch.get("name", "?")
            prefix = "🔒 " if ch.get("is_private") else "# "
            lv.append(ListItem(Label(f"{prefix}{name}"), name=name))

    def set_contacts(self, contacts: list[dict]) -> None:
        lv = self.query_one("#contact-list", ContactList)
        lv.clear()
        for c in contacts:
            display = c.get("name") or c.get("node_id", "?")
            lv.append(ListItem(Label(display), name=c.get("node_id", "")))
