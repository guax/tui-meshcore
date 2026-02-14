"""Configuration management with hardware and regional presets."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".config" / "tui-meshcore"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
IDENTITY_FILE = CONFIG_DIR / "identity.key"
DB_FILE = CONFIG_DIR / "messages.db"

# ---------------------------------------------------------------------------
# Hardware presets
# ---------------------------------------------------------------------------

HARDWARE_PRESETS: dict[str, dict[str, Any]] = {
    "uConsole AIOv2": {
        "bus_id": 1,
        "cs_id": 0,
        "cs_pin": -1,
        "reset_pin": 25,
        "busy_pin": 24,
        "irq_pin": 26,
        "txen_pin": -1,
        "rxen_pin": -1,
        "use_dio3_tcxo": True,
        "use_dio2_rf": True,
    },
    "Waveshare HAT": {
        "bus_id": 0,
        "cs_id": 0,
        "cs_pin": 21,
        "reset_pin": 18,
        "busy_pin": 20,
        "irq_pin": 16,
        "txen_pin": 13,
        "rxen_pin": 12,
        "use_dio3_tcxo": False,
        "use_dio2_rf": False,
    },
    "Mock Radio": {},
}

# ---------------------------------------------------------------------------
# Regional presets
# ---------------------------------------------------------------------------

_COMMON_RADIO = {
    "preamble_length": 17,
    "sync_word": 13380,
    "crc_enabled": True,
    "implicit_header": False,
}


def _rp(freq_mhz: float, sf: int, bw_khz: float, cr: int, tx: int = 22) -> dict[str, Any]:
    return {
        **_COMMON_RADIO,
        "frequency": int(freq_mhz * 1_000_000),
        "spreading_factor": sf,
        "bandwidth": int(bw_khz * 1000),
        "coding_rate": cr,
        "tx_power": tx,
    }


REGION_PRESETS: dict[str, dict[str, Any]] = {
    "EU/UK (Narrow)": _rp(869.618, 8, 62.5, 8),
    "EU/UK (Medium Range)": _rp(869.525, 10, 250, 5),
    "EU/UK (Long Range)": _rp(869.525, 11, 250, 5),
    "EU 433MHz (Long Range)": _rp(433.650, 11, 250, 5),
    "Czech Republic (Narrow)": _rp(869.525, 7, 62.5, 5),
    "Portugal 433": _rp(433.375, 9, 62.5, 6),
    "Portugal 868": _rp(869.618, 7, 62.5, 6),
    "Switzerland": _rp(869.618, 8, 62.5, 8),
    "USA/Canada (Recommended)": _rp(910.525, 7, 62.5, 5),
    "USA/Canada (Alternate)": _rp(910.525, 11, 250, 5),
    "Australia": _rp(915.800, 10, 250, 5),
    "Australia: Victoria": _rp(916.575, 7, 62.5, 8),
    "New Zealand": _rp(917.375, 11, 250, 5),
    "New Zealand (Narrow)": _rp(917.375, 7, 62.5, 5),
    "Vietnam": _rp(920.250, 11, 250, 5),
}

# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------


class ConfigManager:
    """Load / save YAML configuration and apply presets."""

    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self.config_dir = config_dir
        self.config_file = config_dir / "config.yaml"
        self._data: dict[str, Any] = {}

    # --- persistence -------------------------------------------------------

    def exists(self) -> bool:
        return self.config_file.exists()

    def load(self) -> dict[str, Any]:
        if not self.config_file.exists():
            self._data = {}
            return self._data
        with open(self.config_file, "r") as fh:
            self._data = yaml.safe_load(fh) or {}
        return self._data

    def save(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as fh:
            yaml.dump(self._data, fh, default_flow_style=False, sort_keys=False)
        logger.info("Config saved to %s", self.config_file)

    # --- accessors ---------------------------------------------------------

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    @data.setter
    def data(self, value: dict[str, Any]) -> None:
        self._data = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    # --- preset helpers ----------------------------------------------------

    def apply_hardware_preset(self, name: str) -> None:
        if name not in HARDWARE_PRESETS:
            raise ValueError(f"Unknown hardware preset: {name}")
        self._data["hardware_preset"] = name
        self._data["sx1262"] = dict(HARDWARE_PRESETS[name])

    def apply_region_preset(self, name: str) -> None:
        if name not in REGION_PRESETS:
            raise ValueError(f"Unknown region preset: {name}")
        self._data["region_preset"] = name
        self._data["radio"] = dict(REGION_PRESETS[name])

    def set_node_name(self, name: str) -> None:
        self._data.setdefault("node", {})["name"] = name

    @property
    def node_name(self) -> str:
        return self._data.get("node", {}).get("name", "meshcore-tui")

    @property
    def hardware_preset(self) -> str:
        return self._data.get("hardware_preset", "")

    @property
    def region_preset(self) -> str:
        return self._data.get("region_preset", "")

    @property
    def is_mock(self) -> bool:
        return self.hardware_preset == "Mock Radio"

    @property
    def radio_params(self) -> dict[str, Any]:
        return dict(self._data.get("radio", {}))

    @property
    def sx1262_params(self) -> dict[str, Any]:
        return dict(self._data.get("sx1262", {}))

    def get_channels(self) -> list[dict[str, str]]:
        return list(self._data.get("channels", []))

    def set_channels(self, channels: list[dict[str, str]]) -> None:
        self._data["channels"] = channels
