"""Mock radio implementation for UI testing without hardware."""

from __future__ import annotations

import asyncio
import logging
import random
import struct
import time
from typing import Optional

logger = logging.getLogger(__name__)


class MockRadio:
    """Dummy LoRa radio that simulates send/receive for UI testing.

    Implements the same interface as pymc_core.hardware.base.LoRaRadio
    so it can be used as a drop-in replacement.
    """

    def __init__(self, fake_traffic: bool = True, traffic_interval: float = 15.0) -> None:
        self._fake_traffic = fake_traffic
        self._traffic_interval = traffic_interval
        self._last_rssi: int = -80
        self._last_snr: float = 8.5
        self._tx_log: list[bytes] = []
        self._rx_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._running = False
        self._traffic_task: Optional[asyncio.Task[None]] = None

    # --- LoRaRadio interface -----------------------------------------------

    def begin(self) -> None:
        logger.info("[MockRadio] Radio initialised (mock mode)")
        self._running = True

    async def send(self, data: bytes) -> dict | None:
        logger.info("[MockRadio] TX %d bytes: %s", len(data), data.hex()[:40])
        self._tx_log.append(data)
        await asyncio.sleep(0.05)
        return {"status": "ok"}

    async def wait_for_rx(self) -> bytes:
        if not self._running:
            await asyncio.sleep(1)
            return b""
        data = await self._rx_queue.get()
        self._last_rssi = random.randint(-120, -40)
        self._last_snr = round(random.uniform(-5, 15), 1)
        return data

    def sleep(self) -> None:
        logger.info("[MockRadio] Sleeping")
        self._running = False

    def get_last_rssi(self) -> int:
        return self._last_rssi

    def get_last_snr(self) -> float:
        return self._last_snr

    # --- fake traffic generator --------------------------------------------

    def start_fake_traffic(self) -> None:
        if self._fake_traffic and self._traffic_task is None:
            self._traffic_task = asyncio.create_task(self._generate_traffic())

    def stop_fake_traffic(self) -> None:
        if self._traffic_task:
            self._traffic_task.cancel()
            self._traffic_task = None

    async def _generate_traffic(self) -> None:
        """Push synthetic packets into the RX queue periodically."""
        try:
            while self._running:
                await asyncio.sleep(self._traffic_interval)
                fake = self._build_fake_packet()
                if fake:
                    await self._rx_queue.put(fake)
        except asyncio.CancelledError:
            pass

    @staticmethod
    def _build_fake_packet() -> bytes:
        """Build a minimal fake raw packet (just random bytes for now)."""
        return bytes(random.getrandbits(8) for _ in range(32))

    # --- helpers -----------------------------------------------------------

    def inject_rx(self, data: bytes) -> None:
        """Manually inject a packet into the receive queue (for testing)."""
        self._rx_queue.put_nowait(data)
