# OLED Dashboard

A web-configurable OLED display manager for Raspberry Pi with a **Betaflight-style drag-and-drop layout editor**.

Inspired by [mklements/OLED_Stats](https://github.com/mklements/OLED_Stats) but completely redesigned with a self-hosted web UI, multi-display support, and a modular widget system.

## Features

- **Visual Layout Editor** - Betaflight OSD-style drag-and-drop interface to design your display
- **Multi-Display Support** - SSD1306, SH1106, SSD1309, SSD1322 via I2C or SPI
- **18 Built-in Widgets** - CPU, RAM, Swap, Temperature, Uptime, Load, Network Speed, Disk Space, and more
- **Live Preview** - See your layout in real-time before deploying to hardware
- **Self-Hosted Web UI** - Configure everything from any browser on your network (like Pi-hole)
- **One-Command Install** - Get up and running in minutes
- **Layout Presets** - Save and switch between different layouts
- **Systemd Service** - Runs automatically on boot

## Supported Displays

| Chip | Resolution | Size | Interface |
|------|-----------|------|-----------|
| SSD1306 | 128x64 | 0.96" | I2C / SPI |
| SSD1306 | 128x32 | 0.91" | I2C / SPI |
| SSD1306 | 64x48 | 0.66" | I2C / SPI |
| SSD1306 | 64x32 | 0.49" | I2C / SPI |
| SH1106 | 128x64 | 1.3" | I2C / SPI |
| SSD1309 | 128x64 | 2.42" | I2C / SPI |
| SSD1322 | 256x64 | 3.12" | SPI / I2C |

## Quick Install

```bash
curl -sSL https://raw.githubusercontent.com/Cr4zySh4rk/oled-dashboard/main/install.sh | sudo bash
```

Then open `http://<your-pi-ip>:8686` in your browser.

## Manual Installation

```bash
# Clone the repository
git clone https://github.com/Cr4zySh4rk/oled-dashboard.git
cd oled-dashboard

# Create virtual environment
python3 -m venv --system-site-packages venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Run
python -m oled_dashboard
```

## Usage

### Web UI

After installation, access the dashboard at `http://<your-pi-ip>:8686`.

The layout editor works like the Betaflight OSD configurator:
1. **Drag widgets** from the left sidebar onto the display canvas
2. **Move and resize** widgets directly on the canvas
3. **Configure properties** in the right sidebar (font size, display format, etc.)
4. **Click "Save Layout"** to apply changes to your OLED display
5. Use **arrow keys** to nudge selected widgets (hold Shift for 1px precision)

### Command Line

```bash
# Run with simulation mode (no hardware needed)
oled-dashboard --simulate

# Run on a custom port
oled-dashboard --port 8080

# Run web server only (no display output)
oled-dashboard --no-display

# Specify config directory
oled-dashboard --config-dir /path/to/config
```

### Service Management

```bash
sudo systemctl start oled-dashboard    # Start
sudo systemctl stop oled-dashboard     # Stop
sudo systemctl restart oled-dashboard  # Restart
sudo systemctl status oled-dashboard   # Status
sudo journalctl -u oled-dashboard -f   # View logs
```

## Available Widgets

### System
- **CPU Usage** - Real-time CPU percentage with optional bar graph
- **RAM Usage** - Memory used/total with percentage
- **Swap Usage** - Swap memory statistics
- **CPU Temperature** - Temperature in Celsius or Fahrenheit
- **Uptime** - System uptime since last boot
- **Load Average** - 1/5/15 minute load averages
- **Hostname** - System hostname

### Network
- **IP Address** - Current IP with optional label
- **Network Speed** - Real-time upload/download speeds
- **Network Usage** - Total data transferred since boot

### Storage
- **Disk Space** - Usage for any mount point with optional bar
- **Disk I/O** - Read/write activity

### General
- **Static Text** - Custom text labels
- **Date/Time** - Clock with multiple format options
- **Horizontal Line** - Separator line
- **Vertical Line** - Vertical separator
- **Box Frame** - Rectangular frame/border
- **Progress Bar** - Customizable progress indicator

## API Reference

The web server exposes a REST API for programmatic control:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/displays` | GET | List supported displays |
| `/api/display` | GET/POST | Get/set display config |
| `/api/widgets` | GET | List available widgets |
| `/api/widgets/categories` | GET | Widgets by category |
| `/api/layout` | GET/POST | Get/set current layout |
| `/api/layout/presets` | GET/POST | List/save presets |
| `/api/layout/presets/<name>` | GET/DELETE | Load/delete preset |
| `/api/preview` | GET | Live display preview |
| `/api/preview/layout` | POST | Preview a layout |
| `/api/status` | GET | System status |
| `/api/renderer/start` | POST | Start display |
| `/api/renderer/stop` | POST | Stop display |
| `/api/renderer/restart` | POST | Restart display |
| `/api/config/reset` | POST | Reset to defaults |

## Configuration

Configuration is stored in `~/.config/oled-dashboard/config.json` and can be edited via the web UI or directly.

## Hardware Wiring

### I2C Connection (most common)

| OLED Pin | Raspberry Pi Pin |
|----------|-----------------|
| VCC | 3.3V (Pin 1) |
| GND | GND (Pin 6) |
| SDA | GPIO 2 / SDA (Pin 3) |
| SCL | GPIO 3 / SCL (Pin 5) |

### Verify I2C Connection

```bash
sudo i2cdetect -y 1
```

You should see `3c` (or `3d`) in the output grid.

## Uninstall

```bash
curl -sSL https://raw.githubusercontent.com/Cr4zySh4rk/oled-dashboard/main/install.sh | sudo bash -s -- --uninstall
```

## Project Structure

```
oled-dashboard/
├── oled_dashboard/
│   ├── __init__.py           # Package init
│   ├── __main__.py           # CLI entry point
│   ├── config_manager.py     # Configuration management
│   ├── renderer.py           # Display rendering engine
│   ├── drivers/              # OLED display drivers
│   │   ├── base.py           # Abstract driver interface
│   │   ├── ssd1306.py        # SSD1306 driver
│   │   ├── sh1106.py         # SH1106 driver
│   │   ├── ssd1309.py        # SSD1309 driver
│   │   ├── ssd1322.py        # SSD1322 driver
│   │   ├── simulate.py       # Simulated driver (web preview)
│   │   └── registry.py       # Driver registry
│   ├── widgets/              # Display widgets
│   │   ├── base.py           # Abstract widget class
│   │   ├── system_widgets.py # CPU, RAM, Temp, etc.
│   │   ├── network_widgets.py# IP, Speed, Usage
│   │   ├── storage_widgets.py# Disk Space, I/O
│   │   ├── static_widgets.py # Text, Lines, DateTime
│   │   └── registry.py       # Widget registry
│   └── web/                  # Flask web application
│       ├── app.py            # Flask app factory
│       ├── templates/        # HTML templates
│       └── static/           # CSS, JS, images
├── systemd/                  # Systemd service file
├── install.sh                # One-command installer
├── requirements.txt          # Python dependencies
├── setup.py                  # Package setup
└── README.md
```

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Credits

- Inspired by [mklements/OLED_Stats](https://github.com/mklements/OLED_Stats)
- UI inspired by [Betaflight Configurator](https://github.com/betaflight/betaflight-configurator) OSD tab
- Uses [Adafruit CircuitPython SSD1306](https://github.com/adafruit/Adafruit_CircuitPython_SSD1306) and [luma.oled](https://github.com/rm-hull/luma.oled)
