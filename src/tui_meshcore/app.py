"""tui-meshcore — main Textual application."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.message import Message

from .config import CONFIG_DIR, DB_FILE, ConfigManager
from .database import DatabaseManager
from .mesh_service import MeshService
from .screens.dialogs import (
    AddContactDialog,
    AddContactResult,
    JoinChannelDialog,
    JoinChannelResult,
    LeaveChannelDialog,
    LeaveChannelResult,
    derive_channel_secret,
)
from .screens.main_screen import MainScreen, ScreenReady, SendMessage
from .screens.onboarding import OnboardingComplete, OnboardingScreen

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom message types
# ---------------------------------------------------------------------------

class MeshEvent(Message):
    """Bridges a pyMC_core event into Textual's message system."""

    def __init__(self, event_type: str, data: dict[str, Any]) -> None:
        super().__init__()
        self.event_type = event_type
        self.data = data


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class MeshCoreApp(App):
    """TUI client for meshcore LoRa mesh networks."""

    TITLE = "tui-meshcore"
    SUB_TITLE = "LoRa mesh chat"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+j", "join_channel", "Join Channel"),
        ("ctrl+l", "leave_channel", "Leave Channel"),
        ("ctrl+n", "add_contact", "Add Contact"),
        ("ctrl+a", "send_advert", "Send Advert"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = ConfigManager()
        self.db = DatabaseManager(DB_FILE)
        self.mesh = MeshService(self.config, self.db)
        self._main_screen = MainScreen()

    # --- lifecycle ---------------------------------------------------------

    async def on_mount(self) -> None:
        self.db.open()

        if not self.config.exists():
            self.push_screen(OnboardingScreen())
        else:
            self.config.load()
            await self._boot_mesh()

    async def on_unmount(self) -> None:
        await self.mesh.stop()
        self.db.close()

    # --- onboarding callback -----------------------------------------------

    def on_onboarding_complete(self, event: OnboardingComplete) -> None:
        self.config.set_node_name(event.node_name)
        self.config.apply_hardware_preset(event.hw_preset)
        self.config.apply_region_preset(event.region_preset)

        # Ensure a default "Public" channel exists with derived secret
        channels = self.config.get_channels()
        if not channels:
            public_secret = derive_channel_secret("Public")
            self.config.set_channels([{"name": "Public", "secret": public_secret}])
            self.db.add_channel("Public", secret=public_secret)

        self.config.save()
        asyncio.create_task(self._boot_mesh())

    # --- boot mesh ---------------------------------------------------------

    async def _boot_mesh(self) -> None:
        """Install and push main screen — actual init happens in on_screen_ready."""
        self.install_screen(self._main_screen, name="main")
        self.push_screen("main")

    async def on_screen_ready(self, event: ScreenReady) -> None:
        """Called once MainScreen is composed and widgets are queryable."""
        self._refresh_sidebar()

        await self.mesh.start(self)

        screen = self._main_screen
        screen.sidebar.set_status(
            online=self.mesh.online,
            identity=self.mesh.identity_hex,
        )
        screen.message_list.add_system("Welcome to tui-meshcore!")
        if self.mesh.online:
            screen.message_list.add_system("Radio is online.")
        else:
            screen.message_list.add_system("Radio is offline — check configuration.")

    # --- sidebar helpers ---------------------------------------------------

    def _refresh_sidebar(self) -> None:
        screen = self._main_screen
        channels = self.db.get_channels()
        if not channels:
            # Bootstrap from config
            for ch in self.config.get_channels():
                name = ch if isinstance(ch, str) else ch.get("name", "")
                if name:
                    self.db.add_channel(name, secret=ch.get("secret") if isinstance(ch, dict) else None)
            channels = self.db.get_channels()
        screen.sidebar.set_channels(channels)
        screen.sidebar.set_contacts(self.db.get_contacts())

    # --- message sending ---------------------------------------------------

    def on_send_message(self, event: SendMessage) -> None:
        screen = self._main_screen
        target = screen.current_target
        if not target:
            screen.message_list.add_system("Select a channel or contact first.")
            return

        text = event.text
        node_name = self.config.node_name

        if screen.is_dm:
            contact_id = screen.current_contact_id
            self.db.add_message(
                text,
                sender_name=node_name,
                sender_id="me",
                channel_id=contact_id,
                status="sent",
                is_dm=True,
            )
            screen.message_list.add_message(text, sender_name=node_name, kind="me")
            asyncio.create_task(self._do_send_dm(target, text))
        else:
            self.db.add_message(
                text,
                sender_name=node_name,
                sender_id="me",
                channel_id=target,
                status="sent",
            )
            screen.message_list.add_message(text, sender_name=node_name, kind="me")
            asyncio.create_task(self._do_send_channel(target, text))

    async def _do_send_channel(self, channel: str, text: str) -> None:
        ok = await self.mesh.send_channel_message(channel, text)
        if not ok:
            self._main_screen.message_list.add_system("Failed to send message.")

    async def _do_send_dm(self, contact: str, text: str) -> None:
        ok = await self.mesh.send_direct_message(contact, text)
        if not ok:
            self._main_screen.message_list.add_system("Failed to send message.")

    # --- mesh event handling -----------------------------------------------

    def on_mesh_event(self, event: MeshEvent) -> None:
        screen = self._main_screen
        et = event.event_type
        data = event.data

        if et == "mesh.channel.message.new":
            channel = data.get("channel", data.get("group", ""))
            sender = data.get("sender_name", data.get("sender", "?"))
            content = data.get("text", data.get("message", ""))
            sender_id = data.get("sender_id", "")

            self.db.add_message(
                content,
                sender_id=sender_id,
                sender_name=sender,
                channel_id=channel,
                status="received",
            )

            if screen.current_target == channel and not screen.is_dm:
                screen.message_list.add_message(content, sender_name=sender, kind="other")

        elif et == "mesh.message.new":
            sender = data.get("sender_name", data.get("sender", "?"))
            content = data.get("text", data.get("message", ""))
            sender_id = data.get("sender_id", "")

            self.db.add_message(
                content,
                sender_id=sender_id,
                sender_name=sender,
                channel_id=sender_id,
                status="received",
                is_dm=True,
            )

            if screen.is_dm and screen.current_contact_id == sender_id:
                screen.message_list.add_message(content, sender_name=sender, kind="other")
            else:
                self.notify(f"DM from {sender}: {content[:40]}")

        elif et == "mesh.network.node_discovered":
            node_id = data.get("node_id", data.get("address", ""))
            name = data.get("name", "")
            self.db.upsert_contact(
                node_id,
                name=name,
                rssi=data.get("rssi"),
                snr=data.get("snr"),
            )
            self._refresh_sidebar()

        elif et == "mesh.contact.new" or et == "mesh.contact.updated":
            node_id = data.get("node_id", data.get("address", ""))
            if node_id:
                self.db.upsert_contact(
                    node_id,
                    name=data.get("name"),
                    public_key=data.get("public_key"),
                )
                self._refresh_sidebar()

        elif et == "system.error":
            screen.message_list.add_system(f"Error: {data.get('error', 'unknown')}")

    # --- load history for selected channel/contact -------------------------

    def action_load_history(self) -> None:
        screen = self._main_screen
        target = screen.current_target
        if not target:
            return
        if screen.is_dm:
            msgs = self.db.get_messages(is_dm=True, contact_id=screen.current_contact_id)
        else:
            msgs = self.db.get_messages(channel_id=target)
        screen.message_list.load_history(msgs, my_id="me")

    # --- join / leave channel actions --------------------------------------

    def action_join_channel(self) -> None:
        self.push_screen(JoinChannelDialog())

    def on_join_channel_result(self, event: JoinChannelResult) -> None:
        self.db.add_channel(event.name, secret=event.secret, is_private=event.is_private)
        # Sync channel into config so MeshNode's channel_db sees it
        self._sync_channels_to_config()
        self._refresh_sidebar()
        self.notify(f"Joined channel: {event.name}")

    def action_leave_channel(self) -> None:
        screen = self._main_screen
        target = screen.current_target
        if not target or screen.is_dm:
            self.notify("Select a channel first.", severity="warning")
            return
        self.push_screen(LeaveChannelDialog(target))

    def on_leave_channel_result(self, event: LeaveChannelResult) -> None:
        self.db.remove_channel(event.name)
        self._sync_channels_to_config()
        self._refresh_sidebar()
        # Clear chat view if we were viewing that channel
        screen = self._main_screen
        if screen.current_target == event.name and not screen.is_dm:
            screen._current_target = ""
            screen.query_one("#chat-header").update("Select a channel or contact")
            screen.message_list.clear_messages()
        self.notify(f"Left channel: {event.name}")

    # --- add contact action ------------------------------------------------

    def action_add_contact(self) -> None:
        self.push_screen(AddContactDialog())

    def on_add_contact_result(self, event: AddContactResult) -> None:
        self.db.upsert_contact(event.node_id, name=event.name)
        self._refresh_sidebar()
        self.notify(f"Added contact: {event.name}")

    # --- send advert -------------------------------------------------------

    def action_send_advert(self) -> None:
        asyncio.create_task(self._do_send_advert())

    async def _do_send_advert(self) -> None:
        screen = self._main_screen
        ok = await self.mesh.send_advert()
        if ok:
            screen.message_list.add_system("Advert sent.")
        else:
            screen.message_list.add_system("Failed to send advert.")

    # --- channel / config sync ---------------------------------------------

    def _sync_channels_to_config(self) -> None:
        """Keep config.yaml and MeshNode's channel_db in sync with the DB."""
        db_channels = self.db.get_channels()
        cfg_channels = [
            {"name": ch["name"], "secret": ch.get("secret") or derive_channel_secret(ch["name"])}
            for ch in db_channels
        ]
        self.config.set_channels(cfg_channels)
        self.config.save()
        # Update the live channel_db on the running node
        if self.mesh.node and hasattr(self.mesh.node, "channel_db") and self.mesh.node.channel_db:
            self.mesh.node.channel_db.set_channels(cfg_channels)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(CONFIG_DIR / "tui-meshcore.log", mode="a")],
    )
    app = MeshCoreApp()
    app.run()


if __name__ == "__main__":
    main()
