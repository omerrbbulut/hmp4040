# HMP4040 Usage Guide

Python CLI and TUI tools for the Rohde & Schwarz HMP4040
programmable power supply.

Based on the original project:
https://github.com/charkster/hmp4040

## Requirements

- Python 3
- Rohde & Schwarz HMP4040
- Network connectivity to the instrument
- Python dependencies in `requirements.txt`

## Installation

Clone the repository:

    git clone https://github.com/omerrbbulut/hmp4040.git
    cd hmp4040

Create and activate a virtual environment (Linux/macOS):

    python -m venv .venv
    source .venv/bin/activate

On Windows PowerShell:

    python -m venv .venv
    .venv\Scripts\Activate.ps1

Install dependencies:

    python -m pip install -r requirements.txt

Verify installation:

    python -c "import pyvisa, textual; print('Dependencies OK')"
    python -m pip check

## Connection

The CLI communicates with the device using TCP SCPI.

Default connection settings:

| Parameter | Default |
|-----------|---------|
| Host | 10.42.0.232 |
| Port | 5025 |
| Timeout | 3000 ms |

Replace the host with your instrument's IP address.

Example:

    python hmp4040_cli.py --host 192.168.1.100 info

## CLI

Show available commands:

    python hmp4040_cli.py --help

Get device information:

    python hmp4040_cli.py --host 192.168.1.100 info

Show all channel states:

    python hmp4040_cli.py --host 192.168.1.100 status

Additional command groups:

- `reset`: Reset the instrument
- `ch`: Channel operations
- `out`: Global output operations
- `fuse`: Electronic fuse operations
- `raw`: Raw SCPI commands

Display command-specific options:

    python hmp4040_cli.py ch --help
    python hmp4040_cli.py out --help
    python hmp4040_cli.py fuse --help
    python hmp4040_cli.py raw --help

CAUTION: `reset`, output, channel, fuse and raw commands
can change the physical state of the instrument.

## TUI

Launch the terminal interface:

    python hmp4040_tui.py --host 192.168.1.100

Connection options:

    --host HOST
    --port PORT
    --timeout TIMEOUT

Example with explicit port and timeout:

    python hmp4040_tui.py --host 192.168.1.100 --port 5025 --timeout 3000

## Python Example

Review `example.py` before execution:

    python example.py --help

## Troubleshooting

If the connection fails:

1. Confirm the instrument IP address.
2. Confirm that the instrument and computer can communicate.
3. Check TCP port 5025.
4. Check firewall settings.
5. Verify the instrument's SCPI socket configuration.

On Linux, you can test the TCP connection using:

    nc -vz 192.168.1.100 5025

## Safety

Verify voltage, current limits and channel selection
before enabling outputs. Never assume that connected
equipment can tolerate the configured voltage or current.

## Credits

This repository extends the original
[charkster/hmp4040](https://github.com/charkster/hmp4040)
project.

Refer to LICENSE for licensing conditions.
