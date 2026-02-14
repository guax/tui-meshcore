"""MeshService — bridges pyMC_core's MeshNode to the Textual UI."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional, TYPE_CHECKING

from .config import ConfigManager
from .database import DatabaseManager
from .identity import create_local_identity, load_or_create_seed
from .mock_radio import MockRadio

if TYPE_CHECKING:
    from textual.app import App

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Simple channel DB adapter expected by MeshNode
# ---------------------------------------------------------------------------

class ChannelDBAdapter:
    """Minimal channel-database object expected by MeshNode.channel_db."""

    def __init__(self, channels: list[dict[str, str]]) -> None:
        self._channels = list(channels)

    def get_channels(self) -> list[dict[str, str]]:
        logger.info("get_channels: %s", self._channels)
        return self._channels

    def set_channels(self, channels: list[dict[str, str]]) -> None:
        self._channels = list(channels)


# ---------------------------------------------------------------------------
# Event bridge: pyMC_core events → Textual messages
# ---------------------------------------------------------------------------

# Message event types handled directly by on_packet (skip in bridge to avoid dupes)
_PACKET_HANDLED_EVENTS = {
    "mesh.message.new",
    "mesh.channel.message.new",
}


class _TuiEventBridge:
    """EventSubscriber that forwards mesh events into Textual's message bus."""

    def __init__(self, app: App) -> None:
        self._app = app

    async def handle_event(self, event_type: str, data: dict[str, Any]) -> None:
        if event_type in _PACKET_HANDLED_EVENTS:
            return  # handled by MeshService.on_packet instead
        from .app import MeshEvent
        try:
            self._app.post_message(MeshEvent(event_type, data))
        except Exception:
            logger.exception("Failed to post mesh event to TUI")


# ---------------------------------------------------------------------------
# MeshService
# ---------------------------------------------------------------------------

class MeshService:
    """High-level wrapper that owns radio, identity, MeshNode, and event wiring."""

    def __init__(self, config: ConfigManager, db: DatabaseManager) -> None:
        self.config = config
        self.db = db
        self.radio: Any = None
        self.identity: Any = None
        self.node: Any = None
        self._app: Optional[App] = None
        self._node_task: Optional[asyncio.Task[None]] = None
        self._event_service: Any = None
        self._bridge: Optional[_TuiEventBridge] = None
        self.online: bool = False
        self.identity_hex: str = ""

    # --- lifecycle ---------------------------------------------------------

    async def start(self, app: App) -> None:
        """Initialise radio + node and start the RX/TX loop as a background task."""
        self._app = app
        from .config import IDENTITY_FILE

        # 1. Identity
        seed = load_or_create_seed(IDENTITY_FILE)
        self.identity = create_local_identity(seed)
        if self.identity:
            pub = self.identity.get_public_key().hex()
            self.identity_hex = f"{pub[:8]}…{pub[-8:]}"
            logger.info("Identity: %s", self.identity_hex)

        # 2. Radio
        if self.config.is_mock:
            self.radio = MockRadio(fake_traffic=True)
            self.radio.begin()
            self.radio.start_fake_traffic()
            logger.info("Using MockRadio")
        else:
            try:
                self.radio = self._create_real_radio()
                self.radio.begin()
                logger.info("Real radio initialised")
            except Exception as exc:
                logger.error("Radio init failed: %s", exc)
                self.radio = MockRadio(fake_traffic=False)
                self.radio.begin()
                from .app import MeshEvent
                app.post_message(MeshEvent("system.error", {"error": str(exc)}))

        # 3. Event service
        try:
            from pymc_core.node.events.event_service import EventService
            self._event_service = EventService()
            self._bridge = _TuiEventBridge(app)
            self._event_service.subscribe_all(self._bridge)
        except ImportError:
            logger.warning("pymc_core not available — event service disabled")

        # 4. MeshNode
        if self.identity:
            try:
                from pymc_core.node.node import MeshNode
                channels_cfg = self.config.get_channels()
                channel_db = ChannelDBAdapter(channels_cfg)
                self.node = MeshNode(
                    radio=self.radio,
                    local_identity=self.identity,
                    config=self.config.data,
                    channel_db=channel_db,
                    event_service=self._event_service,
                )
                self._node_task = asyncio.create_task(self._run_node())
                self.online = True
                logger.info("MeshNode started")
            except ImportError:
                logger.warning("pymc_core not available — running without MeshNode")
            except Exception as exc:
                logger.error("MeshNode init failed: %s", exc)
                from .app import MeshEvent
                app.post_message(MeshEvent("system.error", {"error": str(exc)}))
        else:
            logger.warning("No identity — MeshNode not created")

    async def stop(self) -> None:
        self.online = False
        if self._node_task:
            self._node_task.cancel()
            try:
                await self._node_task
            except asyncio.CancelledError:
                pass
        if isinstance(self.radio, MockRadio):
            self.radio.stop_fake_traffic()
        logger.info("MeshService stopped")

    # --- messaging ---------------------------------------------------------

    async def send_channel_message(self, channel_name: str, text: str) -> bool:
        if not self.node:
            logger.warning("Cannot send to channel %s — node not initialised", channel_name)
            return False
        try:
            result = await self.node.send_group_text(channel_name, text)
            return result.get("success", False)
        except Exception:
            logger.exception("send_channel_message failed")
            return False

    async def send_direct_message(self, contact_name: str, text: str) -> bool:
        if not self.node:
            logger.warning("Cannot send — node not initialised")
            return False
        try:
            result = await self.node.send_text(contact_name, text)
            return result.get("success", False)
        except Exception:
            logger.exception("send_direct_message failed")
            return False

    # --- internals ---------------------------------------------------------

    async def on_packet(self, pkt):
        """Called by the dispatcher after a handler has processed the packet.

        Decrypted data (if any) lives in ``pkt.decrypted``.  We inspect it and
        post the appropriate MeshEvent so the TUI can display the message.
        """
        from .app import MeshEvent

        payload_type = pkt.get_payload_type()
        logger.info(f"Packet of type {payload_type} received")

        if self._app is None:
            return

        try:
            from pymc_core.protocol.constants import (
                PAYLOAD_TYPE_GRP_TXT,
                PAYLOAD_TYPE_TXT_MSG,
            )
        except ImportError:
            return

        # -- group / channel message ----------------------------------------
        if payload_type == PAYLOAD_TYPE_GRP_TXT:
            grp = pkt.decrypted.get("group_text_data")
            if not grp:
                return
            self._app.post_message(
                MeshEvent(
                    "mesh.channel.message.new",
                    {
                        "channel": grp.get("channel_name", ""),
                        "sender_name": grp.get("sender_name", "?"),
                        "text": grp.get("text", ""),
                        "timestamp": grp.get("timestamp"),
                    },
                )
            )

        # -- direct message -------------------------------------------------
        elif payload_type == PAYLOAD_TYPE_TXT_MSG:
            txt = pkt.decrypted.get("text")
            if not txt:
                return
            # The text handler only stores {"text": msg} on the packet.
            # Resolve the sender from src_hash (payload byte 1) via the DB.
            contact_name, contact_pubkey = self._resolve_sender(pkt)
            self._app.post_message(
                MeshEvent(
                    "mesh.message.new",
                    {
                        "sender_name": contact_name,
                        "sender_id": contact_pubkey,
                        "text": txt,
                    },
                )
            )

    def _resolve_sender(self, pkt) -> tuple[str, str]:
        """Look up the sender's name and public key from the packet src_hash."""
        if len(pkt.payload) < 2:
            return ("?", "")
        src_hash = pkt.payload[1]
        for contact in self.db.get_contacts():
            pk = contact.get("public_key", "")
            if pk:
                try:
                    if bytes.fromhex(pk)[0] == src_hash:
                        return (contact.get("name") or pk[:16], pk)
                except (ValueError, IndexError):
                    continue
        return (f"unknown-{src_hash:02X}", "")

    async def _run_node(self) -> None:
        try:
            self.node.dispatcher.set_packet_received_callback(self.on_packet)
            await self.node.start()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Node loop crashed")
            self.online = False

    def _create_real_radio(self):
        from pymc_core.hardware.sx1262_wrapper import SX1262Radio

        rp = self.config.radio_params
        sp = self.config.sx1262_params

        return SX1262Radio(
            bus_id=sp.get("bus_id", 1),
            cs_id=sp.get("cs_id", 0),
            cs_pin=sp.get("cs_pin", -1),
            reset_pin=sp.get("reset_pin", 25),
            busy_pin=sp.get("busy_pin", 24),
            irq_pin=sp.get("irq_pin", 26),
            txen_pin=sp.get("txen_pin", -1),
            rxen_pin=sp.get("rxen_pin", -1),
            frequency=rp.get("frequency", 869618000),
            tx_power=rp.get("tx_power", 22),
            spreading_factor=rp.get("spreading_factor", 8),
            bandwidth=rp.get("bandwidth", 62500),
            coding_rate=rp.get("coding_rate", 8),
            preamble_length=rp.get("preamble_length", 17),
            use_dio3_tcxo=sp.get("use_dio3_tcxo", False),
            use_dio2_rf=sp.get("use_dio2_rf", False),
        )
