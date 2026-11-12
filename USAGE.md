# HMP4040 — Usage Guide

Python command-line (CLI) and terminal (TUI) applications
for the Rohde & Schwarz HMP4040 programmable power supply.

Based on the original project:
[charkster/hmp4040](https://github.com/charkster/hmp4040)

## 1. Installation

### Clone the repository

```bash
git clone https://github.com/omerrbbulut/hmp4040.git
cd hmp4040
```

### Create a Python virtual environment

Linux / macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Install dependencies

```bash
python -m pip install -r requirements.txt
```

### Verify installation

```bash
python -c "import pyvisa, textual; print('Dependencies OK')"
python -m pip check
```

## 2. Network Connection

The CLI uses TCP SCPI communication.

| Parameter | Default | Description |
|---|---|---|
| `--host` | `10.42.0.232` | Instrument IP address |
| `--port` | `5025` | SCPI TCP port |
| `--timeout` | `3000` | Communication timeout (ms) |

Specify global connection options before the subcommand.

Example:

```bash
python hmp4040_cli.py --host 192.168.1.100 info
```

Use your instrument's actual IP address.

## 3. Device Information

Get instrument identification:

```bash
python hmp4040_cli.py info
```

Read all channel states:

```bash
python hmp4040_cli.py status
```

Reset the instrument:

```bash
python hmp4040_cli.py reset
```

**Warning:** Reset can change the instrument configuration.

## 4. Channel Control

### Read channel status

```bash
python hmp4040_cli.py ch status 1
```

### Set voltage

```bash
python hmp4040_cli.py ch set 1 --voltage 5.0
```

### Set current limit

```bash
python hmp4040_cli.py ch set 1 --current 1.0
```

### Set voltage and current limit

```bash
python hmp4040_cli.py ch set 1 --voltage 5.0 --current 1.0
```

### Enable or disable a channel

```bash
python hmp4040_cli.py ch on 1
python hmp4040_cli.py ch off 1
```

**Warning:** Enabling a channel can energize connected hardware,
depending on the global output state.

## 5. Global Output Control

Enable the global output:

```bash
python hmp4040_cli.py out on
```

Disable the global output:

```bash
python hmp4040_cli.py out off
```

**Warning:** Global output activation can energize multiple
previously enabled channels.

## 6. Electronic Fuse

### Read fuse status

```bash
python hmp4040_cli.py fuse status 1
```

### Enable or disable fuse protection

```bash
python hmp4040_cli.py fuse on 1
python hmp4040_cli.py fuse off 1
```

### Read fuse delay

```bash
python hmp4040_cli.py fuse delay 1
```

### Set fuse delay

```bash
python hmp4040_cli.py fuse delay 1 --value 100
```

The valid delay range and units depend on the instrument
implementation. Confirm them before changing the value.

### Check fuse trip state

```bash
python hmp4040_cli.py fuse trip 1
```

### Link fuse channels

```bash
python hmp4040_cli.py fuse link 1 2
```

### Remove a fuse link

```bash
python hmp4040_cli.py fuse unlink 1 2
```

### List linked channels

```bash
python hmp4040_cli.py fuse links 1
```

**Warning:** Fuse settings affect hardware protection behavior.

## 7. Raw SCPI Commands

### Send a query

```bash
python hmp4040_cli.py raw query "*IDN?"
```

### Send a write command

```bash
python hmp4040_cli.py raw write "INSTrument:NSELect 1"
```

Raw write commands can change the instrument state.

Only use SCPI commands supported by the instrument firmware.

## 8. Terminal User Interface

Launch the TUI:

```bash
python hmp4040_tui.py
```

Specify the instrument IP address:

```bash
python hmp4040_tui.py --host 192.168.1.100
```

Specify all connection options:

```bash
python hmp4040_tui.py \
    --host 192.168.1.100 \
    --port 5025 \
    --timeout 3000
```

View available startup options:

```bash
python hmp4040_tui.py --help
```

## 9. Python API

The repository also contains the original Python instrument
control library and an example application.

Review the example before running:

```bash
python example.py --help
```

## 10. Troubleshooting

### Connection refused or timeout

- Verify the instrument IP address.
- Confirm TCP port 5025.
- Check the network connection and firewall.
- Verify that the instrument supports and enables SCPI socket access.

Check connectivity on Linux:

```bash
nc -vz 192.168.1.100 5025
```

### Missing Python modules

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Reinstall project dependencies:

```bash
python -m pip install -r requirements.txt
```

## 11. Safety

The HMP4040 is a programmable power supply.

Before enabling outputs:

- Check channel voltage settings.
- Verify current limits.
- Confirm the selected channels.
- Verify the load's electrical ratings.
- Review electronic fuse configuration.

Changing output or protection settings can damage connected
hardware if incompatible values are used.

## 12. Credits and License

This repository extends the original
[charkster/hmp4040](https://github.com/charkster/hmp4040)
project with CLI and TUI functionality.

The original project history and license are preserved.

See [LICENSE](LICENSE) for licensing conditions.
