#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# OLED Dashboard - One-Command Installer
# Usage: curl -sSL https://raw.githubusercontent.com/Cr4zySh4rk/oled-dashboard/main/install.sh | sudo bash
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

INSTALL_DIR="/opt/oled-dashboard"
CONFIG_DIR="/root/.config/oled-dashboard"
SERVICE_NAME="oled-dashboard"
REPO_URL="https://github.com/Cr4zySh4rk/oled-dashboard.git"
BRANCH="main"

# ── Functions ──────────────────────────────────────────────────

print_banner() {
    echo -e "${CYAN}"
    echo "  ╔═══════════════════════════════════════════╗"
    echo "  ║         OLED Dashboard Installer          ║"
    echo "  ║   Web-configurable OLED display manager   ║"
    echo "  ╚═══════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_info() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_step() {
    echo -e "\n${BOLD}${CYAN}──── $1 ────${NC}\n"
}

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        log_error "This installer must be run as root (use sudo)"
        exit 1
    fi
}

check_platform() {
    if [ ! -f /proc/device-tree/model ] 2>/dev/null; then
        log_warn "This doesn't appear to be a Raspberry Pi"
        log_warn "The OLED display drivers may not work, but the web UI will run in simulation mode"
        read -p "Continue anyway? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 0
        fi
    else
        PI_MODEL=$(cat /proc/device-tree/model 2>/dev/null || echo "Unknown")
        log_info "Detected: ${PI_MODEL}"
    fi
}

enable_i2c() {
    log_step "Enabling I2C Interface"

    # Enable I2C via raspi-config noninteractive
    if command -v raspi-config &>/dev/null; then
        raspi-config nonint do_i2c 0 2>/dev/null || true
        log_info "I2C enabled via raspi-config"
    fi

    # Also enable via config.txt as fallback
    if [ -f /boot/config.txt ]; then
        if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
            echo "dtparam=i2c_arm=on" >> /boot/config.txt
            log_info "Added I2C to /boot/config.txt"
        fi
    elif [ -f /boot/firmware/config.txt ]; then
        if ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt; then
            echo "dtparam=i2c_arm=on" >> /boot/firmware/config.txt
            log_info "Added I2C to /boot/firmware/config.txt"
        fi
    fi

    # Load I2C kernel module
    modprobe i2c-dev 2>/dev/null || true
    if ! grep -q "i2c-dev" /etc/modules 2>/dev/null; then
        echo "i2c-dev" >> /etc/modules
    fi

    log_info "I2C interface configured"
}

enable_spi() {
    log_step "Enabling SPI Interface"

    if command -v raspi-config &>/dev/null; then
        raspi-config nonint do_spi 0 2>/dev/null || true
        log_info "SPI enabled via raspi-config"
    fi

    if [ -f /boot/config.txt ]; then
        if ! grep -q "^dtparam=spi=on" /boot/config.txt; then
            echo "dtparam=spi=on" >> /boot/config.txt
        fi
    elif [ -f /boot/firmware/config.txt ]; then
        if ! grep -q "^dtparam=spi=on" /boot/firmware/config.txt; then
            echo "dtparam=spi=on" >> /boot/firmware/config.txt
        fi
    fi

    log_info "SPI interface configured"
}

install_system_deps() {
    log_step "Installing System Dependencies"

    apt-get update -qq
    apt-get install -y -qq \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        python3-pil \
        python3-smbus \
        i2c-tools \
        libfreetype6-dev \
        libjpeg-dev \
        libopenjp2-7 \
        git \
        fonts-dejavu-core \
        2>/dev/null

    log_info "System dependencies installed"
}

clone_or_update_repo() {
    log_step "Installing OLED Dashboard"

    if [ -d "$INSTALL_DIR/.git" ]; then
        log_info "Existing installation found, updating..."
        cd "$INSTALL_DIR"
        git fetch origin
        git reset --hard "origin/$BRANCH"
    else
        rm -rf "$INSTALL_DIR"
        git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
        log_info "Repository cloned to $INSTALL_DIR"
    fi

    cd "$INSTALL_DIR"
}

setup_python_env() {
    log_step "Setting Up Python Environment"

    cd "$INSTALL_DIR"

    # Create venv with --system-site-packages so apt-installed python3-pil is available
    # (same approach as the original OLED_Stats project)
    python3 -m venv --system-site-packages venv
    source venv/bin/activate

    # Upgrade pip
    pip install --upgrade pip setuptools wheel 2>/dev/null

    # ── Install OLED display stack in the same order as OLED_Stats ──────────
    # adafruit-blinka MUST be installed first and upgraded, it wraps Pi I2C/GPIO
    # into the CircuitPython-compatible API used by adafruit-circuitpython-ssd1306
    log_info "Installing adafruit-blinka (CircuitPython Pi bridge)..."
    pip install --upgrade adafruit-blinka 2>/dev/null \
        && log_info "adafruit-blinka installed" \
        || log_warn "adafruit-blinka install failed (will try fallback libraries)"

    log_info "Installing adafruit-circuitpython-ssd1306..."
    pip install adafruit-circuitpython-ssd1306 2>/dev/null \
        && log_info "adafruit-circuitpython-ssd1306 installed" \
        || log_warn "adafruit-circuitpython-ssd1306 install failed (will try fallback libraries)"

    # ── Core dependencies ────────────────────────────────────────────────────
    log_info "Installing core dependencies..."
    pip install psutil flask 2>/dev/null

    # Pillow: prefer apt-installed python3-pil (already via system-site-packages),
    # but install via pip as well for the venv in case apt version is old
    pip install "Pillow>=9.0" 2>/dev/null \
        || log_warn "Pillow pip install failed, using system python3-pil"

    # ── Fallback OLED libraries (luma.oled + smbus2) ─────────────────────────
    # Used if adafruit-blinka is unavailable (e.g. DietPi kernel differences)
    log_info "Installing fallback OLED libraries (luma.oled, smbus2)..."
    pip install luma.oled luma.core smbus2 2>/dev/null \
        || log_warn "luma.oled install failed (adafruit stack will be used instead)"

    # ── Install the dashboard package itself ─────────────────────────────────
    pip install -e . 2>/dev/null

    deactivate
    log_info "Python environment configured"
}

create_config() {
    log_step "Creating Default Configuration"

    mkdir -p "$CONFIG_DIR"

    if [ ! -f "$CONFIG_DIR/config.json" ]; then
        cat > "$CONFIG_DIR/config.json" << 'CONFIGEOF'
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
      {"widget_id": "cpu_usage", "x": 0, "y": 16, "width": 60, "height": 14, "font_size": 11, "config": {"show_bar": false}},
      {"widget_id": "temperature", "x": 68, "y": 16, "width": 60, "height": 14, "font_size": 11, "config": {"unit": "C"}},
      {"widget_id": "ram_usage", "x": 0, "y": 32, "width": 128, "height": 14, "font_size": 11, "config": {"format": "compact"}},
      {"widget_id": "disk_space", "x": 0, "y": 48, "width": 128, "height": 14, "font_size": 11, "config": {"mount_point": "/", "show_bar": false}}
    ]
  },
  "server": {
    "host": "0.0.0.0",
    "port": 8686,
    "debug": false
  },
  "refresh_rate": 1.0
}
CONFIGEOF
        log_info "Default configuration created"
    else
        log_info "Existing configuration preserved"
    fi
}

install_service() {
    log_step "Installing Systemd Service"

    cp "$INSTALL_DIR/systemd/oled-dashboard.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    systemctl start "$SERVICE_NAME"

    log_info "Service installed and started"
}

detect_displays() {
    log_step "Detecting I2C Displays"

    if command -v i2cdetect &>/dev/null; then
        echo "Scanning I2C bus 1..."
        i2cdetect -y 1 2>/dev/null || log_warn "No I2C bus found (this is normal if I2C was just enabled)"
    else
        log_warn "i2cdetect not available, skipping detection"
    fi
}

print_summary() {
    # Get the Pi's IP address
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    if [ -z "$LOCAL_IP" ]; then
        LOCAL_IP="<your-pi-ip>"
    fi

    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  OLED Dashboard installed successfully!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}Web UI:${NC}  http://${LOCAL_IP}:8686"
    echo ""
    echo -e "  ${BOLD}Commands:${NC}"
    echo -e "    Start:   ${CYAN}sudo systemctl start oled-dashboard${NC}"
    echo -e "    Stop:    ${CYAN}sudo systemctl stop oled-dashboard${NC}"
    echo -e "    Restart: ${CYAN}sudo systemctl restart oled-dashboard${NC}"
    echo -e "    Status:  ${CYAN}sudo systemctl status oled-dashboard${NC}"
    echo -e "    Logs:    ${CYAN}sudo journalctl -u oled-dashboard -f${NC}"
    echo ""
    echo -e "  ${BOLD}Config:${NC}  $CONFIG_DIR/config.json"
    echo -e "  ${BOLD}Install:${NC} $INSTALL_DIR"
    echo ""
    echo -e "  ${YELLOW}Note:${NC} If I2C/SPI was just enabled, a reboot may be required."
    echo -e "  Run: ${CYAN}sudo reboot${NC}"
    echo ""
}

# ── Main ───────────────────────────────────────────────────────

main() {
    print_banner
    check_root
    check_platform
    install_system_deps
    enable_i2c
    enable_spi
    clone_or_update_repo
    setup_python_env
    create_config
    install_service
    detect_displays
    print_summary
}

# Handle uninstall flag
if [ "${1:-}" = "--uninstall" ]; then
    echo -e "${YELLOW}Uninstalling OLED Dashboard...${NC}"
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f /etc/systemd/system/oled-dashboard.service
    systemctl daemon-reload
    rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}OLED Dashboard uninstalled.${NC}"
    echo -e "Config preserved at: $CONFIG_DIR"
    exit 0
fi

main "$@"
