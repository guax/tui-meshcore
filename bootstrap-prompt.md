# tui-meshcore

I'd like to bootstrap a python3 project that implements a TUI client for meshcore. It should be based on the pyMC_core package for interacting with the meshcore radio.
The configuration should be stored in the users .config folder and on first initialization the configs for the radio like radio type and options should be asked/configured by the user using the interface. First boot should also create a identity key for the user if that does not exist on the .config folder

List of features:
 - Add and remove public channels (key derived from name)
 - Add and remove private channels (key and name provided by user)
 - Send and see messages on channels
 - Send private messages to users

You can check /Users/guax/src/meshcore/pyMC_core/examples for some code samples of how pyMC_core works.

Here is an example of the configs that are possible (you don't have to follow this format, use for reference on the keys since they match pymc_core). For the basic radio things like bandwith and frequency etc it would be better to have them be selected from presets like EU/UK, US, AU etc.

radio:
  bandwidth: 62500
  coding_rate: 8
  crc_enabled: true
  frequency: 869618000
  implicit_header: false
  preamble_length: 17
  spreading_factor: 8
  sync_word: 13380
  tx_power: 22
repeater:
  allow_discovery: true
  cache_ttl: 60
  identity_file: null
  latitude: 52.508685
  longitude: 4.952819
  mode: forward
  node_name: guax-dev-repeater
  score_threshold: 0.3
  send_advert_interval_hours: 10
  use_score_for_tx: false
sx1262:
  bus_id: 1
  busy_pin: 24
  cs_id: 0
  cs_pin: -1
  irq_pin: 26
  is_waveshare: false
  reset_pin: 25
  rxen_pin: -1
  rxled_pin: -1
  txen_pin: -1
  txled_pin: -1
  use_dio3_tcxo: true
  use_dio2_rf: true