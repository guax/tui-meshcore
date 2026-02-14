# Project: tui-meshcore

## Overview
Create a Python 3 TUI (Text User Interface) client for **meshcore**. This application will allow users to interact with a LoRa mesh network using the `pyMC_core` library. It must be robust, asynchronous, and user-friendly, suitable for running on devices like the uConsole or Raspberry Pi with LoRa HATs.

## Tech Stack
*   **Language**: Python 3.10+
*   **TUI Framework**: **Textual** (recommended for modern CSS-based styling and async support).
*   **Core Library**: `pyMC_core` (must be installed/available in the environment).
*   **Database**: `sqlite3` (for persisting chat history and node data).
*   **Async**: `asyncio` (strictly required as `pyMC_core` is async).

## Core Requirements

### 1. Configuration & Storage
*   **Location**: Store configuration and database in `~/.config/tui-meshcore/`.
*   **First Run**:
    *   If config is missing, launch an **Onboarding Wizard**.
    *   **Identity**: Generate a new `LocalIdentity` (keypair) if one doesn't exist. Save it securely.
    *   **Radio Setup**: Ask user to select a **Hardware Preset** and a **Region Preset**.
*   **Config File**: YAML or JSON.

### 2. Hardware & Regional Presets
The application should ship with built-in presets to avoid manual entry of complex LoRa parameters.

**Hardware Presets:**
*   **uConsole AIOv2** (Default for this project context):
    *   SPI Bus: 1, CS ID: 0
    *   Pins: Busy=24, Reset=25, IRQ=26, CS=-1 (Hardware CS)
    *   Flags: `use_dio3_tcxo=True`, `use_dio2_rf=True`
*   **Waveshare HAT**:
    *   SPI Bus: 0, CS ID: 0
    *   Pins: Busy=20, Reset=18, IRQ=16, CS=21, TXEN=13, RXEN=12
*   **Mock Radio**:
    *   A dummy implementation for testing UI without hardware. Should simulate receiving messages and log sent messages.

**Regional Presets (LoRa Settings):**
All presets share common defaults: `preamble_length=17`, `sync_word=13380`, `crc_enabled=true`, `implicit_header=false`.

| Preset | Freq (MHz) | SF | BW (kHz) | CR | TX Pwr (dBm) |
|---|---|---|---|---|---|
| EU/UK (Narrow) | 869.618 | 8 | 62.5 | 8 | 22 |
| EU/UK (Medium Range) | 869.525 | 10 | 250 | 5 | 22 |
| EU/UK (Long Range) | 869.525 | 11 | 250 | 5 | 22 |
| EU 433MHz (Long Range) | 433.650 | 11 | 250 | 5 | 22 |
| Czech Republic (Narrow) | 869.525 | 7 | 62.5 | 5 | 22 |
| Portugal 433 | 433.375 | 9 | 62.5 | 6 | 22 |
| Portugal 868 | 869.618 | 7 | 62.5 | 6 | 22 |
| Switzerland | 869.618 | 8 | 62.5 | 8 | 22 |
| USA/Canada (Recommended) | 910.525 | 7 | 62.5 | 5 | 22 |
| USA/Canada (Alternate) | 910.525 | 11 | 250 | 5 | 22 |
| Australia | 915.800 | 10 | 250 | 5 | 22 |
| Australia: Victoria | 916.575 | 7 | 62.5 | 8 | 22 |
| New Zealand | 917.375 | 11 | 250 | 5 | 22 |
| New Zealand (Narrow) | 917.375 | 7 | 62.5 | 5 | 22 |
| Vietnam | 920.250 | 11 | 250 | 5 | 22 |

*   **Manual**: Allow overriding any specific key (freq, sf, bw, cr, tx_power) in the config file.

### 3. Features
*   **Channels**:
    *   **Public Channels**: Key derived from name (e.g., "General"). Users can join/leave.
    *   **Private Channels**: User provides Name + PSK (Pre-Shared Key).
*   **Messaging**:
    *   Send/Receive text messages on channels.
    *   Send/Receive **Private Direct Messages** (DM) to specific Node IDs.
*   **Persistence**:
    *   Save all received and sent messages to SQLite.
    *   Schema should support: `timestamp`, `sender_id`, `sender_name`, `channel_id` (or NULL for DM), `message_content`, `status` (sent/received/failed).

### 4. UI Layout (Textual)
*   **Sidebar (Left)**:
    *   List of **Channels** (Public/Private).
    *   List of **Direct Contacts** (Nodes seen recently or saved).
    *   Status indicator (Radio Online/Offline, Identity Hash).
*   **Main View (Center)**:
    *   **Message List**: Scrollable history of the currently selected channel/chat.
    *   Different colors for "Me", "Others", and "System Messages".
*   **Input Area (Bottom)**:
    *   Text input field.
    *   Handling of `Enter` to send.

## pyMC_core API Reference

The implementing agent **must** study the reference code at the paths listed below. This section summarises the key patterns.

### Reference Paths
*   **pyMC_core examples**: `/Users/guax/src/meshcore/pyMC_core/examples/` — especially `common.py`, `send_text_message.py`, `send_channel_message.py`.
*   **pyMC_Repeater** (real-world usage): `/Users/guax/src/meshcore/pyMC_Repeater/repeater/main.py` — shows full init, dispatcher loop, and identity setup.
*   **pyMC_core source**: `/Users/guax/src/meshcore/pyMC_core/src/pymc_core/`.

### Key Classes & Patterns

**Identity**:
```python
from pymc_core import LocalIdentity
# Create from a 32-byte seed (save this seed to recreate the same identity)
identity = LocalIdentity(seed=b"32_byte_seed_here_padded_to_32!!")
pubkey = identity.get_public_key()  # bytes
```

**Radio Init (SX1262)**:
```python
from pymc_core.hardware.sx1262_wrapper import SX1262Radio
radio = SX1262Radio(
    bus_id=1, cs_id=0, cs_pin=-1, reset_pin=25, busy_pin=24, irq_pin=26,
    txen_pin=-1, rxen_pin=-1,
    frequency=869618000, tx_power=22, spreading_factor=8,
    bandwidth=62500, coding_rate=8, preamble_length=17,
    use_dio3_tcxo=True, use_dio2_rf=True,
)
radio.begin()
```

**MeshNode (high-level API)**:
```python
from pymc_core.node.node import MeshNode
node = MeshNode(
    radio=radio,
    local_identity=identity,
    config={"node": {"name": "my-node"}},
    contacts=contact_storage,    # optional, app-injected
    channel_db=channel_db,       # optional, app-injected
    event_service=event_service, # optional, app-injected
)
# Start the RX/TX loop (blocks forever)
await node.start()  # internally calls dispatcher.run_forever()
```

**Sending Messages**:
```python
# Direct text message (needs contact in contact book)
result = await node.send_text("alice", "Hello!")  # returns dict with success, snr, rssi

# Channel/group message
result = await node.send_group_text("Public", "Hello channel!")
```

**Event System** — Subscribe to incoming messages:
```python
from pymc_core.node.events.event_service import EventService, EventSubscriber
from pymc_core.node.events.events import MeshEvents

class MyHandler(EventSubscriber):
    async def handle_event(self, event_type: str, data: dict) -> None:
        if event_type == MeshEvents.NEW_CHANNEL_MESSAGE:
            print(f"Channel msg: {data}")
        elif event_type == MeshEvents.NEW_MESSAGE:
            print(f"DM: {data}")
        elif event_type == MeshEvents.NODE_DISCOVERED:
            print(f"New node: {data}")

event_service = EventService()
event_service.subscribe_all(MyHandler())  # or subscribe to specific events
node.set_event_service(event_service)
```

Available `MeshEvents`:
*   `NEW_MESSAGE`, `MESSAGE_READ`, `UNREAD_COUNT_CHANGED`
*   `NEW_CHANNEL_MESSAGE`, `CHANNEL_UPDATED`
*   `NEW_CONTACT`, `CONTACT_UPDATED`
*   `NODE_DISCOVERED`, `SIGNAL_STRENGTH_UPDATED`
*   `NODE_STARTED`, `NODE_STOPPED`, `TELEMETRY_UPDATED`

**Dispatcher (lower-level)**:
The `Dispatcher` manages the radio RX/TX loop. For most TUI work, use `MeshNode` which wraps the dispatcher. The repeater project uses the dispatcher directly with a fallback handler:
```python
from pymc_core.node.dispatcher import Dispatcher
dispatcher = Dispatcher(radio)
dispatcher.register_fallback_handler(my_callback)  # async fn(packet)
await dispatcher.run_forever()
```

## Implementation Guide

### Phase 1: Foundation
1.  Setup project structure with `pyproject.toml` (or `requirements.txt`).
2.  Implement `ConfigManager` to handle loading/saving YAML configs and presets.
3.  Implement `DatabaseManager` for SQLite interactions (messages, contacts, channels).
4.  Create the `MockRadio` class implementing the same interface as `SX1262Radio` (inheriting from `pymc_core.hardware.base.LoRaRadio`). It should:
    *   Log all sent packets.
    *   Optionally generate fake incoming messages on a timer for UI testing.
    *   Return success from `begin()` and `send_packet()` without real hardware.

### Phase 2: Core Logic
1.  Integrate `pyMC_core`.
2.  Create a `MeshService` class that wraps `MeshNode`.
    *   It should start `node.start()` as an `asyncio.Task`.
    *   It should create an `EventService` and register an `EventSubscriber` that bridges events to the Textual UI (e.g., posting Textual `Message` objects).
3.  Implement `LocalIdentity` generation/loading:
    *   On first run, generate a random 32-byte seed, save it to `~/.config/tui-meshcore/identity.key`.
    *   On subsequent runs, load the seed and recreate `LocalIdentity`.

### Phase 3: TUI Implementation
1.  Build the `App` class using Textual.
2.  Create the Onboarding Wizard (Modal or separate Screen) for first-run config.
3.  Build the Main Screen with Sidebar and Message views.
4.  Connect `MeshService` events to UI updates using Textual's `post_message` / `call_from_thread` to safely cross async boundaries.

### Reference Config (uconsole-aiov2 + EU/UK Narrow)
```yaml
node:
  name: "my-node"
radio:
  frequency: 869618000
  bandwidth: 62500
  spreading_factor: 8
  coding_rate: 8
  tx_power: 22
  preamble_length: 17
  sync_word: 13380
  crc_enabled: true
  implicit_header: false
sx1262:
  bus_id: 1
  cs_id: 0
  busy_pin: 24
  reset_pin: 25
  irq_pin: 26
  cs_pin: -1
  txen_pin: -1
  rxen_pin: -1
  use_dio3_tcxo: true
  use_dio2_rf: true
```

## Important Notes
*   **Async is Key**: The UI must never block. `node.start()` runs the radio loop and must be a background task.
*   **Error Handling**: If the radio fails to initialize, show a visible error in the TUI but don't crash. Allow the user to reconfigure settings.
*   **Mock Mode**: When hardware preset is "Mock Radio", skip all real radio init and use the `MockRadio` class.
*   **Code Style**: Type-hinted, modular, clean Python code.