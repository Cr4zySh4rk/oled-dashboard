# OLED Dashboard — Session Notes
_Last updated: 2026-04-09_

Paste this file at the start of a new session to resume work.

---

## Project Overview

**Repo:** https://github.com/Cr4zySh4rk/oled-dashboard
**Install:** `curl -sSL https://raw.githubusercontent.com/Cr4zySh4rk/oled-dashboard/main/install.sh | sudo bash`
**Web UI:** `http://<pi-ip>:8686`
**Config:** `/root/.config/oled-dashboard/config.json`
**Install dir:** `/opt/oled-dashboard`
**Service:** `sudo systemctl status oled-dashboard`
**Logs:** `sudo journalctl -u oled-dashboard -f`

---

## Two Devices in Use

| Device | OS | Display | I2C Addr | Status |
|---|---|---|---|---|
| Raspberry Pi Zero (PiHole) | DietPi | 0.91" 128×32 SSD1306 | 0x3C | **Working** — but had 226/NAMESPACE error + rotate 180 broken |
| Raspberry Pi 5 NAS | Pi OS | 0.96" 128×64 SSD1306 | 0x3C | **Nothing showing** — i2cdetect finds it, all libs load, but nothing renders |

---

## Key Architecture

```
oled_dashboard/
  __main__.py          Flask web server entry point
  renderer.py          Renders PIL canvas, pushes to hardware + web preview buffer
  drivers/
    base.py            OLEDDriver ABC
    ssd1306.py         Main driver — tries adafruit → luma → smbus2
  widgets/
    system_widgets.py  CPU, RAM, temp, uptime, IP address, hostname
    network_widgets.py Upload/download speed
    storage_widgets.py Disk usage
  icons.py             18 pixel-art PIL drawing functions (procedural, no image files)
systemd/
  oled-dashboard.service   Systemd unit (ProtectSystem/PrivateTmp REMOVED — caused 226/NAMESPACE)
install.sh             One-command installer
requirements.txt       adafruit-blinka primary, luma.oled fallback
```

---

## Display Driver Stack (ssd1306.py)

**Priority order:**
1. `adafruit-blinka` + `adafruit-circuitpython-ssd1306` — same as proven OLED_Stats project
   Uses `board.I2C()` → `adafruit_ssd1306.SSD1306_I2C(w, h, i2c, addr=0x3C)` → `oled.image(img)` + `oled.show()`
2. `luma.oled ssd1306` — DietPi fallback (no Blinka needed)
3. `luma.oled sh1106` — for cheap modules mislabeled as SSD1306
4. Direct `smbus2` framebuffer write — last resort, converts PIL mode-"1" to SSD1306 page format

**Rotation:** ALL rotation is done via PIL (`image.rotate(-angle, expand=...)`) in `display_image()`.
Hardware rotate is NOT used — it was unreliable for 180° on some displays.

---

## Known Issues and Status

### 1. Pi Zero (PiHole) — 226/NAMESPACE error
**Cause:** `ProtectSystem=strict` and `PrivateTmp=true` in the systemd unit are unsupported on DietPi/embedded kernels.
**Fix:** Removed those lines from `systemd/oled-dashboard.service`. **FIXED and committed.**
**User action needed:** Pull latest and reinstall, or just:
```bash
sudo curl -sSL https://raw.githubusercontent.com/Cr4zySh4rk/oled-dashboard/main/systemd/oled-dashboard.service \
  -o /etc/systemd/system/oled-dashboard.service
sudo systemctl daemon-reload && sudo systemctl restart oled-dashboard
```

### 2. Pi Zero (PiHole) — Rotate 180 not working
**Cause:** `display_image()` only PIL-rotated for 90/270, relied on hardware rotate for 180 which didn't work.
**Fix:** Extended PIL rotation to cover 90/180/270 in `display_image()`. **FIXED and committed.**

### 3. Pi 5 NAS — Nothing showing on OLED
**Status:** UNRESOLVED
**Diagnostics run:**
- `i2cdetect -y 1` → finds device at 0x3C ✓
- smbus2 import ✓, raw ping ✓
- luma.oled import and init ✓, "test pattern sent" in logs ✓
- **But nothing appears on screen**

**Root cause hypothesis:** luma.oled's `device.display()` doesn't work on Pi 5's RP1 I2C controller for this module. The adafruit-blinka stack (now primary in the driver) may fix this — hasn't been tested yet since installer wasn't updated until now.

**Next step for user:** After pushing to GitHub and running the installer:
```bash
curl -sSL https://raw.githubusercontent.com/Cr4zySh4rk/oled-dashboard/main/install.sh | sudo bash
sudo journalctl -u oled-dashboard -f
```
Look for line: `[OLED] Ready: SSD1306 adafruit I2C (addr=0x3C)` — if that appears and display still shows nothing, it's a hardware/chip issue.

If adafruit fails too, look for: `[OLED] *** HARDWARE INIT FAILED ***` with error details.

**Backup diagnostic:** Run test script manually:
```bash
sudo /opt/oled-dashboard/venv/bin/python /opt/oled-dashboard/test_display.py
```

---

## Icons

`oled_dashboard/icons.py` — 18 procedural PIL pixel-art icons, no image files needed.

| Widget ID | Icon |
|---|---|
| `cpu_usage` | Lightning bolt |
| `ram_usage` | RAM chip |
| `temperature` | Thermometer |
| `uptime` | Clock |
| `cpu_freq` | Bar chart |
| `hostname` | House |
| `ip_address` | Globe |
| `download_speed` | WiFi waves + down arrow |
| `upload_speed` | WiFi waves + up arrow |
| `network_rx` | Down arrow |
| `network_tx` | Up arrow |
| `disk_space` | Disk platter |

**Usage:**
```python
from oled_dashboard.icons import draw_icon, icon_width
draw_icon(draw, "cpu_usage", x=0, y=0, size=10)
text_x = x + icon_width(10)
```

Icons are controlled per-widget via `"show_icon": true/false` in config.

---

## Config Format

`/root/.config/oled-dashboard/config.json`:
```json
{
  "display": {
    "chip": "SSD1306",
    "width": 128,
    "height": 64,
    "interface": "i2c",
    "i2c_address": "0x3C",
    "i2c_bus": 1,
    "rotation": 0,
    "brightness": 255
  },
  "layout": {
    "name": "Default",
    "widgets": [
      {"widget_id": "ip_address", "x": 0, "y": 0, "width": 128, "height": 14, "font_size": 12, "config": {"show_label": true}},
      {"widget_id": "cpu_usage",  "x": 0, "y": 16, "width": 60, "height": 14, "font_size": 11},
      {"widget_id": "temperature","x": 68, "y": 16, "width": 60, "height": 14, "font_size": 11},
      {"widget_id": "ram_usage",  "x": 0, "y": 32, "width": 128, "height": 14, "font_size": 11},
      {"widget_id": "disk_space", "x": 0, "y": 48, "width": 128, "height": 14, "font_size": 11}
    ]
  },
  "server": {"host": "0.0.0.0", "port": 8686, "debug": false},
  "refresh_rate": 1.0
}
```

For **128×32 display** (Pi Zero), set `"height": 32` and remove the last two rows of widgets.
For **rotation 180**, set `"rotation": 180`.

---

## Git State

Latest commit: `ca20d6f` — "fix: use adafruit-blinka stack (same as OLED_Stats), fix rotate 180, harden installer"

**IMPORTANT:** This commit exists locally but may not be pushed to GitHub yet (sandbox can't push).
To push from your Mac:
```bash
cd ~/path/to/oled-dashboard
git pull /sessions/gallant-amazing-dijkstra/mnt/oled-dashboard main
git push origin main
```

---

## Reference: OLED_Stats (the working project we're matching)

`github.com/mklements/OLED_Stats`
Local clone at: `~/Desktop/OLED_Stats` (mounted at `/sessions/.../mnt/OLED_Stats`)

Their install order (what we now match):
```bash
python3 -m venv stats_env --system-site-packages
sudo apt-get install -y python3-pil
pip3 install --upgrade adafruit-blinka
pip3 install adafruit-circuitpython-ssd1306
pip3 install psutil
```

Their render code:
```python
import board, adafruit_ssd1306
oled = adafruit_ssd1306.SSD1306_I2C(128, 32, board.I2C())
oled.image(image)
oled.show()
```
