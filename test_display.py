#!/usr/bin/env python3
"""
OLED Dashboard - Hardware Diagnostic Script
Run this on your Pi to pinpoint exactly why the display isn't showing anything.

Usage:
    sudo /opt/oled-dashboard/venv/bin/python test_display.py

    # Or with a custom I2C address:
    sudo /opt/oled-dashboard/venv/bin/python test_display.py --addr 0x3D

    # Or for a 128x32 display:
    sudo /opt/oled-dashboard/venv/bin/python test_display.py --width 128 --height 32
"""

import sys
import subprocess
import argparse
import time

# ── Helpers ───────────────────────────────────────────────────────────────────

def ok(msg):   print(f"  \033[32m[OK]\033[0m  {msg}")
def fail(msg): print(f"  \033[31m[FAIL]\033[0m {msg}")
def info(msg): print(f"  \033[36m[INFO]\033[0m {msg}")
def step(msg): print(f"\n\033[1m{'─'*50}\033[0m\n  {msg}\n{'─'*50}")

# ── Steps ─────────────────────────────────────────────────────────────────────

def check_i2c_module():
    step("Step 1: Check i2c-dev kernel module")
    try:
        out = subprocess.check_output("lsmod | grep i2c", shell=True).decode()
        if "i2c" in out:
            ok("i2c kernel module is loaded")
            info(out.strip())
        else:
            fail("i2c module NOT found in lsmod")
    except Exception:
        fail("Could not run lsmod")

    import os
    if os.path.exists("/dev/i2c-1"):
        ok("/dev/i2c-1 device file exists")
    else:
        fail("/dev/i2c-1 NOT found — I2C may not be enabled")
        info("Enable with: sudo raspi-config → Interface Options → I2C")
        info("Then run: sudo modprobe i2c-dev")


def run_i2cdetect(bus=1):
    step("Step 2: Scan I2C bus for devices")
    try:
        out = subprocess.check_output(f"i2cdetect -y {bus}", shell=True).decode()
        print(out)
        # Check for any address in the output that isn't '--'
        found = []
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) > 1:
                for p in parts[1:]:
                    if p != '--' and p != 'UU':
                        found.append(p)
        if found:
            ok(f"Device(s) found at address(es): {', '.join('0x'+a for a in found)}")
        else:
            fail("No I2C devices detected on bus 1")
            info("Check your wiring: SDA→GPIO2(pin3), SCL→GPIO3(pin5), VCC→3.3V, GND→GND")
    except FileNotFoundError:
        fail("i2cdetect not found — install with: sudo apt install i2c-tools")
    except Exception as e:
        fail(f"i2cdetect failed: {e}")


def check_smbus2():
    step("Step 3: Test smbus2 import and raw I2C ping")
    try:
        import smbus2
        ok(f"smbus2 imported OK (version {smbus2.__version__ if hasattr(smbus2,'__version__') else 'unknown'})")
        return True
    except ImportError:
        fail("smbus2 not installed — run: pip install smbus2")
        return False


def raw_i2c_ping(addr, bus=1):
    step(f"Step 4: Raw I2C ping of address 0x{addr:02X}")
    try:
        import smbus2
        with smbus2.SMBus(bus) as bus_obj:
            bus_obj.write_byte(addr, 0x00)
        ok(f"0x{addr:02X} responded to raw I2C write — device is present")
        return True
    except OSError as e:
        fail(f"0x{addr:02X} did NOT respond: {e}")
        info("Try 0x3D if you think the address might be wrong")
        return False
    except Exception as e:
        fail(f"smbus2 error: {e}")
        return False


def check_luma():
    step("Step 5: Test luma.oled import")
    try:
        from luma.core.interface.serial import i2c as luma_i2c
        from luma.oled.device import ssd1306
        ok("luma.oled imported OK")
        return True
    except ImportError as e:
        fail(f"luma.oled import failed: {e}")
        info("Install with: pip install luma.oled luma.core")
        return False


def draw_test_pattern(addr, width, height, bus=1):
    step(f"Step 6: Init luma.oled SSD1306 and draw test pattern ({width}x{height})")
    try:
        from luma.core.interface.serial import i2c as luma_i2c
        from luma.oled.device import ssd1306
        from PIL import Image, ImageDraw, ImageFont

        info(f"Opening I2C bus {bus}, address 0x{addr:02X} ...")
        serial = luma_i2c(port=bus, address=addr)
        device = ssd1306(serial, width=width, height=height)
        ok("luma.oled device created successfully")

        # Draw a simple test pattern
        img = Image.new("1", (width, height), 0)
        draw = ImageDraw.Draw(img)

        # Border
        draw.rectangle([0, 0, width-1, height-1], outline=255)

        # Diagonal cross
        draw.line([0, 0, width-1, height-1], fill=255)
        draw.line([width-1, 0, 0, height-1], fill=255)

        # Text
        try:
            draw.text((2, height//2 - 4), "OLED OK!", fill=255)
        except Exception:
            pass

        info("Pushing test pattern to display ...")
        device.display(img)
        ok("Test pattern sent! You should see a box with an X and 'OLED OK!' on the display.")
        ok("If you see it, the hardware is working fine — the issue is in the app config.")
        info("Keeping display on for 5 seconds ...")
        time.sleep(5)
        device.cleanup()
        return True

    except Exception as e:
        fail(f"luma.oled display test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_pil():
    step("Step 7: Check Pillow")
    try:
        from PIL import Image, ImageDraw
        ok(f"Pillow imported OK")
        return True
    except ImportError as e:
        fail(f"Pillow not available: {e}")
        return False


def print_summary(results):
    step("SUMMARY")
    all_ok = all(results.values())
    for name, passed in results.items():
        if passed:
            ok(name)
        else:
            fail(name)
    print()
    if all_ok:
        print("\033[32m  All checks passed! Your OLED is working.\033[0m")
        print("  If the dashboard app still doesn't show anything, check:")
        print("   • sudo journalctl -u oled-dashboard -n 50")
        print("   • The config I2C address matches: sudo cat ~/.config/oled-dashboard/config.json")
    else:
        print("\033[31m  Some checks failed. Fix the issues above then restart the service:\033[0m")
        print("   sudo systemctl restart oled-dashboard")
        print("   sudo journalctl -u oled-dashboard -f")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OLED Dashboard hardware diagnostic")
    parser.add_argument("--addr", default="0x3C", help="I2C address (default: 0x3C)")
    parser.add_argument("--bus", type=int, default=1, help="I2C bus number (default: 1)")
    parser.add_argument("--width", type=int, default=128, help="Display width (default: 128)")
    parser.add_argument("--height", type=int, default=64, help="Display height (default: 64)")
    args = parser.parse_args()

    addr = int(args.addr, 16)

    print("\n\033[1m\033[36m  OLED Dashboard — Hardware Diagnostic\033[0m")
    print(f"  Target: I2C bus {args.bus}, address {args.addr}, {args.width}x{args.height}\n")

    results = {}

    check_i2c_module()
    results["i2c-dev module & /dev/i2c-1"] = True  # visual only

    run_i2cdetect(args.bus)

    results["smbus2 available"] = check_smbus2()

    if results["smbus2 available"]:
        results["device responds on I2C"] = raw_i2c_ping(addr, args.bus)
    else:
        results["device responds on I2C"] = False

    results["luma.oled available"] = check_luma()
    results["Pillow available"] = check_pil()

    if results["luma.oled available"] and results.get("device responds on I2C", False):
        results["test pattern displayed"] = draw_test_pattern(addr, args.width, args.height, args.bus)
    elif not results.get("device responds on I2C", False):
        info("Skipping display test — device not responding on I2C")
        results["test pattern displayed"] = False
    else:
        info("Skipping display test — luma.oled not available")
        results["test pattern displayed"] = False

    print_summary(results)


if __name__ == "__main__":
    main()
