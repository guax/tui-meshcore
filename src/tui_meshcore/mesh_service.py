"""MeshService — bridges pyMC_core's MeshNode to the Textual UI."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
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
# Contact adapter: wraps TUI DB rows into objects pyMC_core expects
# ---------------------------------------------------------------------------

@dataclass
class Contact:
    """Lightweight contact object matching the interface pyMC_core handlers use."""
    public_key: str = ""
    name: str = ""
    out_path: list[int] = field(default_factory=list)
    type: int = 0


class ContactDBAdapter:
    """Exposes DB contacts as `.contacts` list + `.get_by_name()` for pyMC_core."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self.contacts: list[Contact] = []
        self.refresh()

    def refresh(self) -> None:
        """Re-read contacts from the database."""
        self.contacts = [
            Contact(
                public_key=row.get("public_key") or "",
                name=row.get("name") or row.get("node_id", ""),
            )
            for row in self._db.get_contacts()
            if row.get("public_key")
        ]

    def get_by_name(self, name: str) -> Optional[Contact]:
        for c in self.contacts:
            if c.name == name:
                return c
        return None

    def add_contact(self, public_key: str, name: str) -> Contact:
        """Add a contact to the DB *and* the in-memory list. Returns the new Contact."""
        self._db.upsert_contact(public_key, name=name, public_key=public_key)
        c = Contact(public_key=public_key, name=name)
        # Avoid duplicates in the in-memory list
        if not any(existing.public_key == public_key for existing in self.contacts):
            self.contacts.append(c)
        return c


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
        self._contact_db: Optional[ContactDBAdapter] = None
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
                self._contact_db = ContactDBAdapter(self.db)
                self.node = MeshNode(
                    radio=self.radio,
                    local_identity=self.identity,
                    config=self.config.data,
                    contacts=self._contact_db,
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

    # --- advertise ---------------------------------------------------------

    async def send_advert(self) -> bool:
        """Broadcast a self-advertisement packet announcing this node."""
        if not self.node:
            logger.warning("Cannot send advert — node not initialised")
            return False
        try:
            from pymc_core.protocol.packet_builder import PacketBuilder

            pkt = PacketBuilder.create_self_advert(
                local_identity=self.identity,
                name=self.config.node_name,
            )
            success = await self.node.dispatcher.send_packet(pkt, wait_for_ack=False)
            logger.info("Advert sent: %s", success)
            return success
        except Exception:
            logger.exception("send_advert failed")
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
                PAYLOAD_TYPE_ADVERT,
                PAYLOAD_TYPE_GRP_TXT,
                PAYLOAD_TYPE_TXT_MSG,
            )
        except ImportError:
            return

        # -- advertisement --------------------------------------------------
        if payload_type == PAYLOAD_TYPE_ADVERT:
            self._handle_advert(pkt)

        # -- group / channel message ----------------------------------------
        elif payload_type == PAYLOAD_TYPE_GRP_TXT:
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
            # The text handler matched the contact from _contact_db to decrypt.
            # Resolve the sender so we can attribute the message.
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

    # --- contact helpers ---------------------------------------------------

    def _handle_advert(self, pkt) -> None:
        """Process an advert packet — auto-add the sender as a contact if new."""
        from .app import MeshEvent

        try:
            from pymc_core.protocol.constants import PUB_KEY_SIZE, TIMESTAMP_SIZE, SIGNATURE_SIZE
            from pymc_core.protocol import decode_appdata
        except ImportError:
            return

        payload = pkt.get_payload()
        header_len = PUB_KEY_SIZE + TIMESTAMP_SIZE + SIGNATURE_SIZE
        if len(payload) < header_len:
            return

        pubkey_hex = payload[:PUB_KEY_SIZE].hex()
        appdata = payload[header_len:]

        try:
            decoded = decode_appdata(appdata)
        except Exception:
            logger.debug("Failed to decode advert appdata")
            return

        name = decoded.get("node_name") or decoded.get("name") or ""
        if not name:
            return

        # Ensure the contact exists in our DB and in-memory adapter
        self._ensure_contact(pubkey_hex, name)

        self._app.post_message(
            MeshEvent(
                "mesh.contact.new",
                {"node_id": pubkey_hex, "name": name, "public_key": pubkey_hex},
            )
        )

    def _ensure_contact(self, public_key: str, name: str) -> None:
        """Add the contact to the DB + adapter if not already known, and refresh sidebar."""
        if self._contact_db is None:
            return
        existing = next(
            (c for c in self._contact_db.contacts if c.public_key == public_key),
            None,
        )
        if existing is None:
            self._contact_db.add_contact(public_key, name)
            logger.info("Auto-added contact %s (%s…)", name, public_key[:16])
        else:
            # Update name if it changed
            if name and existing.name != name:
                existing.name = name
                self.db.upsert_contact(public_key, name=name, public_key=public_key)

    def _resolve_sender(self, pkt) -> tuple[str, str]:
        """Look up the sender's name and public key from the packet src_hash."""
        if not self._contact_db or len(pkt.payload) < 2:
            return ("?", "")
        src_hash = pkt.payload[1]
        for c in self._contact_db.contacts:
            if c.public_key:
                try:
                    if bytes.fromhex(c.public_key)[0] == src_hash:
                        return (c.name or c.public_key[:16], c.public_key)
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
