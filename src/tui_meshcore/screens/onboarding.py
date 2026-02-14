"""Onboarding wizard screen — first-run configuration."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Header, Input, Label, Select, Static

from ..config import HARDWARE_PRESETS, REGION_PRESETS


class OnboardingComplete(Message):
    """Posted when the user finishes the wizard."""

    def __init__(self, node_name: str, hw_preset: str, region_preset: str) -> None:
        super().__init__()
        self.node_name = node_name
        self.hw_preset = hw_preset
        self.region_preset = region_preset


class OnboardingScreen(Screen):
    """First-run setup wizard."""

    DEFAULT_CSS = """
    OnboardingScreen {
        align: center middle;
    }
    #wizard-box {
        width: 64;
        max-height: 80%;
        padding: 2 3;
        border: thick $accent;
        background: $surface;
    }
    #wizard-box Label {
        margin: 1 0 0 0;
    }
    #wizard-box Input {
        margin: 0 0 1 0;
    }
    #wizard-box Select {
        margin: 0 0 1 0;
    }
    #wizard-box Button {
        margin: 2 0 0 0;
        width: 100%;
    }
    .wizard-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin: 0 0 1 0;
    }
    .wizard-subtitle {
        text-align: center;
        color: $text-muted;
        margin: 0 0 2 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Center():
            with Vertical(id="wizard-box"):
                yield Static("Welcome to tui-meshcore", classes="wizard-title")
                yield Static("Let's set up your node.", classes="wizard-subtitle")

                yield Label("Node name")
                yield Input(
                    placeholder="my-node",
                    id="node-name",
                    value="meshcore-tui",
                )

                yield Label("Hardware preset")
                yield Select(
                    [(name, name) for name in HARDWARE_PRESETS],
                    id="hw-preset",
                    value="uConsole AIOv2",
                )

                yield Label("Region preset")
                yield Select(
                    [(name, name) for name in REGION_PRESETS],
                    id="region-preset",
                    value="EU/UK (Narrow)",
                )

                yield Button("Save & Start", variant="primary", id="btn-save")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "btn-save":
            return
        node_name = self.query_one("#node-name", Input).value.strip() or "meshcore-tui"
        hw = self.query_one("#hw-preset", Select).value
        region = self.query_one("#region-preset", Select).value

        if isinstance(hw, str) and isinstance(region, str):
            self.post_message(OnboardingComplete(node_name, hw, region))
            self.app.pop_screen()
