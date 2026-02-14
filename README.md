# tui-meshcore

A terminal-based chat client for **meshcore** LoRa mesh networks, built with [Textual](https://textual.textualize.io/) and [pyMC_core](https://github.com/meshcore/pyMC_core).

## Features

- **Onboarding wizard** — first-run setup for node name, hardware, and region
- **Channel messaging** — public and private (PSK) channels
- **Direct messages** — encrypted DMs to specific nodes
- **Persistent history** — SQLite-backed message and contact storage
- **Hardware presets** — uConsole AIOv2, Waveshare HAT, Mock Radio
- **15 regional presets** — EU, US/CA, AU, NZ, and more
- **Mock radio mode** — full UI testing without LoRa hardware

## Quick Start

```bash
# Install (editable, no radio hardware needed)
pip install -e .

# Install with real radio support
pip install -e ".[radio]"

# Run
tui-meshcore
```

On first launch the onboarding wizard will guide you through setup. Configuration is stored in `~/.config/tui-meshcore/`.

## Keybindings

| Key | Action |
|---|---|
| `Ctrl+Q` | Quit |
| `Ctrl+J` | Join channel |
| `Enter` | Send message |

## Project Layout

```
src/tui_meshcore/
├── app.py            # Main Textual app + entry point
├── app.tcss          # Global CSS styles
├── config.py         # ConfigManager, hardware/region presets
├── database.py       # SQLite persistence
├── identity.py       # Keypair generation/loading
├── mesh_service.py   # MeshNode wrapper + event bridge
├── mock_radio.py     # Fake radio for testing
├── screens/
│   ├── main_screen.py    # Chat UI
│   └── onboarding.py     # First-run wizard
└── widgets/
    ├── sidebar.py         # Channels + contacts + status
    └── message_list.py    # Scrollable chat history
```

## Configuration

Stored at `~/.config/tui-meshcore/config.yaml`. Example:

```yaml
node:
  name: my-node
hardware_preset: uConsole AIOv2
region_preset: EU/UK (Narrow)
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
channels:
  - name: Public
```

## License

MIT
