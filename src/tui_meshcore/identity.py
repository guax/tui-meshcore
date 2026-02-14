"""Identity generation and persistence."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def generate_seed() -> bytes:
    """Generate a cryptographically random 32-byte seed."""
    return os.urandom(32)


def save_seed(path: Path, seed: bytes) -> None:
    """Save a 32-byte seed to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(seed)
    os.chmod(path, 0o600)
    logger.info("Identity seed saved to %s", path)


def load_seed(path: Path) -> bytes:
    """Load a 32-byte seed from disk."""
    seed = path.read_bytes()
    if len(seed) != 32:
        raise ValueError(f"Identity seed must be 32 bytes, got {len(seed)}")
    return seed


def load_or_create_seed(path: Path) -> bytes:
    """Load an existing seed or generate and save a new one."""
    if path.exists():
        logger.info("Loading existing identity from %s", path)
        return load_seed(path)
    logger.info("No identity found — generating new seed")
    seed = generate_seed()
    save_seed(path, seed)
    return seed


def create_local_identity(seed: bytes):
    """Create a LocalIdentity from a 32-byte seed.

    Returns the identity object from pymc_core, or None if the library
    is unavailable.
    """
    try:
        from pymc_core import LocalIdentity
        return LocalIdentity(seed=seed)
    except ImportError:
        logger.warning("pymc_core not installed — identity creation skipped")
        return None
