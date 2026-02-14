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
*   **EU/UK (Narrow)**: Freq=869.618MHz, SF=8, BW=62.5kHz, CR=4/8, Pwr=22dBm
*   **EU/UK (Long Range)**: Freq=869.525MHz, SF=11, BW=250kHz, CR=4/5
*   **US (915)**: Freq=915.0Mhz (example default, allow tuning), SF=10, BW=250kHz.
*   **Manual**: Allow overriding specific keys (freq, sf, bw) in the config file.

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

## Implementation Guide

### Phase 1: Foundation
1.  Setup project structure with `poetry` or `requirements.txt`.
2.  Implement `ConfigManager` to handle loading/saving YAML configs and presets.
3.  Implement `DatabaseManager` for SQLite interactions.
4.  Create the `MockRadio` class to allow UI development on non-radio hardware.

### Phase 2: Core Logic
1.  Integrate `pyMC_core`.
2.  Create a `MeshService` class that wraps `MeshNode`.
    *   It should run the `mesh_node` in a background task.
    *   It should expose callbacks or signals when a packet arrives (to update UI).
3.  Implement the `LocalIdentity` generation/loading logic (reference `pyMC_core` examples).

### Phase 3: TUI Implementation
1.  Build the `App` class using Textual.
2.  Create the Onboarding Wizard (Modal or separate Screen) for first-run config.
3.  Build the Main Screen with Sidebar and Message views.
4.  Connect `MeshService` events to UI updates (use `call_from_thread` or Textual's message passing if crossing thread/async boundaries safely).

### Reference Code (Hardware Config)
Use this structure for the `uconsole-aiov2` config:
```yaml
radio:
  frequency: 869618000
  bandwidth: 62500
  spreading_factor: 8
  coding_rate: 8
  tx_power: 22
sx1262:
  bus_id: 1
  cs_id: 0
  busy_pin: 24
  reset_pin: 25
  irq_pin: 26
  cs_pin: -1
  use_dio3_tcxo: true
  use_dio2_rf: true
```

## Important Notes
*   **Async is Key**: The UI cannot block. Radio TX/RX operations are async.
*   **Error Handling**: If the radio fails to initialize, show a visible error in the TUI but don't crash immediately (allow checking settings).
*   **Code Style**: Type-hinted, modular, clean Python code.