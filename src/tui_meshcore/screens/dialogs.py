"""Modal dialog screens — Join Channel, Add Contact, Leave Channel."""

from __future__ import annotations

import hashlib

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static


# ---------------------------------------------------------------------------
# Channel key derivation
# ---------------------------------------------------------------------------

# Well-known MeshCore channel secrets (ecosystem-wide constants)
_WELL_KNOWN_SECRETS: dict[str, str] = {
    "Public": "8b3387e9c5cdea6ac9e5edbaa115cd72",
}


def derive_channel_secret(name: str) -> str:
    """Return the well-known secret for a channel, or derive one via MD5."""
    if name in _WELL_KNOWN_SECRETS:
        return _WELL_KNOWN_SECRETS[name]
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Join Channel
# ---------------------------------------------------------------------------

class JoinChannelResult(Message):
    def __init__(self, name: str, secret: str, is_private: bool) -> None:
        super().__init__()
        self.name = name
        self.secret = secret
        self.is_private = is_private


class JoinChannelDialog(ModalScreen):
    """Dialog for joining a public or private channel."""

    DEFAULT_CSS = """
    JoinChannelDialog {
        align: center middle;
    }
    #join-box {
        width: 56;
        padding: 2 3;
        border: thick $accent;
        background: $surface;
    }
    #join-box Label {
        margin: 1 0 0 0;
    }
    #join-box Input {
        margin: 0 0 1 0;
    }
    #join-box Checkbox {
        margin: 0 0 1 0;
    }
    .dialog-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin: 0 0 1 0;
    }
    .button-row {
        layout: horizontal;
        height: auto;
        margin: 1 0 0 0;
    }
    .button-row Button {
        width: 1fr;
        margin: 0 1;
    }
    #psk-input {
        display: none;
    }
    #psk-label {
        display: none;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="join-box"):
            yield Static("Join Channel", classes="dialog-title")

            yield Label("Channel name")
            yield Input(placeholder="e.g. General", id="channel-name")

            yield Checkbox("Private channel (requires PSK)", id="is-private")

            yield Label("Pre-Shared Key", id="psk-label")
            yield Input(placeholder="Hex key or passphrase", id="psk-input", password=True)

            with Vertical(classes="button-row"):
                yield Button("Join", variant="primary", id="btn-join")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id != "is-private":
            return
        psk_input = self.query_one("#psk-input", Input)
        psk_label = self.query_one("#psk-label", Label)
        if event.value:
            psk_input.styles.display = "block"
            psk_label.styles.display = "block"
        else:
            psk_input.styles.display = "none"
            psk_label.styles.display = "none"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.app.pop_screen()
            return
        if event.button.id != "btn-join":
            return

        name = self.query_one("#channel-name", Input).value.strip()
        if not name:
            self.notify("Channel name is required", severity="error")
            return

        is_private = self.query_one("#is-private", Checkbox).value
        if is_private:
            psk = self.query_one("#psk-input", Input).value.strip()
            if not psk:
                self.notify("PSK is required for private channels", severity="error")
                return
            secret = psk
        else:
            secret = derive_channel_secret(name)

        self.post_message(JoinChannelResult(name, secret, is_private))
        self.app.pop_screen()


# ---------------------------------------------------------------------------
# Leave Channel
# ---------------------------------------------------------------------------

class LeaveChannelResult(Message):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name


class LeaveChannelDialog(ModalScreen):
    """Confirmation dialog for leaving a channel."""

    DEFAULT_CSS = """
    LeaveChannelDialog {
        align: center middle;
    }
    #leave-box {
        width: 48;
        padding: 2 3;
        border: thick $error;
        background: $surface;
    }
    .dialog-title {
        text-align: center;
        text-style: bold;
        color: $error;
        margin: 0 0 1 0;
    }
    .confirm-text {
        text-align: center;
        margin: 0 0 1 0;
    }
    .button-row {
        layout: horizontal;
        height: auto;
        margin: 1 0 0 0;
    }
    .button-row Button {
        width: 1fr;
        margin: 0 1;
    }
    """

    def __init__(self, channel_name: str) -> None:
        super().__init__()
        self._channel_name = channel_name

    def compose(self) -> ComposeResult:
        with Vertical(id="leave-box"):
            yield Static("Leave Channel", classes="dialog-title")
            yield Static(
                f"Leave [bold]{self._channel_name}[/]?\nMessage history will be kept.",
                classes="confirm-text",
            )
            with Vertical(classes="button-row"):
                yield Button("Leave", variant="error", id="btn-leave")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-leave":
            self.post_message(LeaveChannelResult(self._channel_name))
        self.app.pop_screen()


# ---------------------------------------------------------------------------
# Add Contact
# ---------------------------------------------------------------------------

class AddContactResult(Message):
    def __init__(self, node_id: str, name: str) -> None:
        super().__init__()
        self.node_id = node_id
        self.name = name


class AddContactDialog(ModalScreen):
    """Dialog for manually adding a contact for DMs."""

    DEFAULT_CSS = """
    AddContactDialog {
        align: center middle;
    }
    #contact-box {
        width: 56;
        padding: 2 3;
        border: thick $accent;
        background: $surface;
    }
    #contact-box Label {
        margin: 1 0 0 0;
    }
    #contact-box Input {
        margin: 0 0 1 0;
    }
    .dialog-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin: 0 0 1 0;
    }
    .button-row {
        layout: horizontal;
        height: auto;
        margin: 1 0 0 0;
    }
    .button-row Button {
        width: 1fr;
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="contact-box"):
            yield Static("Add Contact", classes="dialog-title")

            yield Label("Node ID (public key hex)")
            yield Input(placeholder="e.g. 7358a939f578…", id="contact-node-id")

            yield Label("Display name")
            yield Input(placeholder="e.g. Alice", id="contact-name")

            with Vertical(classes="button-row"):
                yield Button("Add", variant="primary", id="btn-add")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.app.pop_screen()
            return
        if event.button.id != "btn-add":
            return

        node_id = self.query_one("#contact-node-id", Input).value.strip()
        name = self.query_one("#contact-name", Input).value.strip()

        if not node_id:
            self.notify("Node ID is required", severity="error")
            return
        if not name:
            self.notify("Display name is required", severity="error")
            return

        self.post_message(AddContactResult(node_id, name))
        self.app.pop_screen()
