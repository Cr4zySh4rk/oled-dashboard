#!/usr/bin/env python3
"""
OLED Dashboard - Hardware Diagnostic Script
Run this on your Pi to pinpoint exactly why the display isn't showing anything.

Usage:
    sudo /opt/oled-dashboard/venv/bin/python test_display.py

    # Custom I2C address (try if default 0x3C doesn't work):
    sudo /opt/oled-dashboard/venv/bin/python test_display.py --addr 0x3D

    # 128x32 display:
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
            info("Check wiring: SDA→GPIO2(pin3), SCL→GPIO3(pin5), VCC→3.3V, GND→GND")
    except FileNotFoundError:
        fail("i2cdetect not found — install with: sudo apt install i2c-tools")
    except Exception as e:
        fail(f"i2cdetect failed: {e}")


def gpio_reset(gpio_pin=4):
    step(f"Step 2b: GPIO hardware reset on GPIO {gpio_pin}")
    info("The original OLED_Stats project pulses GPIO 4 LOW then HIGH before init.")
    info("Without this, many modules accept I2C writes silently but show nothing.")

    tried = False
    try:
        import gpiozero
        rst = gpiozero.OutputDevice(gpio_pin, active_high=False)
        rst.on()
        time.sleep(0.1)
        rst.off()
        time.sleep(0.1)
        rst.on()
        time.sleep(0.05)
        rst.close()
        ok(f"GPIO {gpio_pin} reset pulse sent via gpiozero")
        tried = True
    except Exception as e:
        info(f"gpiozero attempt: {e}")

    if not tried:
        try:
            import RPi.GPIO as GPIO
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(gpio_pin, GPIO.OUT)
            GPIO.output(gpio_pin, GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(gpio_pin, GPIO.LOW)
            time.sleep(0.1)
            GPIO.output(gpio_pin, GPIO.HIGH)
            time.sleep(0.05)
            ok(f"GPIO {gpio_pin} reset pulse sent via RPi.GPIO")
            tried = True
        except Exception as e:
            info(f"RPi.GPIO attempt: {e}")

    if not tried:
        info(f"GPIO reset skipped — no GPIO library available. "
             f"If your module has RST wired to GPIO {gpio_pin}, this may cause a blank screen.")


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
        from luma.oled.device import ssd1306, sh1106
        ok("luma.oled imported OK (ssd1306 + sh1106 available)")
        return True
    except ImportError as e:
        fail(f"luma.oled import failed: {e}")
        info("Install with: pip install luma.oled luma.core")
        return False


def draw_test_pattern_chip(chip_name, addr, width, height, bus=1, wait=4):
    """Try to draw on a specific chip type. Returns True if it succeeded without error."""
    from luma.core.interface.serial import i2c as luma_i2c
    from PIL import Image, ImageDraw

    serial = luma_i2c(port=bus, address=addr)

    if chip_name == "ssd1306":
        from luma.oled.device import ssd1306
        device = ssd1306(serial, width=width, height=height)
    else:
        from luma.oled.device import sh1106
        device = sh1106(serial, width=width, height=height)

    img = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, width-1, height-1], outline=255)
    draw.line([0, 0, width-1, height-1], fill=255)
    draw.line([width-1, 0, 0, height-1], fill=255)
    try:
        draw.text((2, height//2 - 4), f"{chip_name.upper()} OK!", fill=255)
    except Exception:
        pass

    device.display(img)
    info(f"Pattern sent via {chip_name.upper()} driver. Waiting {wait}s ...")
    time.sleep(wait)
    device.cleanup()
    return True


def chip_detection_test(addr, width, height, bus=1):
    step("Step 6: Chip detection — try SSD1306 then SH1106")
    info("Many modules labeled 'SSD1306' are actually SH1106 inside.")
    info("Both chips respond at 0x3C and accept I2C writes — but need different init.")
    info("")

    working_chip = None

    for chip in ("ssd1306", "sh1106"):
        print(f"\n  Testing {chip.upper()} driver ...")
        try:
            draw_test_pattern_chip(chip, addr, width, height, bus, wait=4)
            print(f"\n  *** Did you see '{chip.upper()} OK!' on the display? ***")
            ans = input("  Type 'y' for yes, anything else for no: ").strip().lower()
            if ans == 'y':
                ok(f"Display responded correctly to {chip.upper()} driver!")
                working_chip = chip
                break
            else:
                fail(f"{chip.upper()} driver did not produce visible output")
        except Exception as e:
            fail(f"{chip.upper()} driver raised an exception: {e}")
            import traceback
            traceback.print_exc()

    return working_chip


def check_pil():
    step("Step 7: Check Pillow")
    try:
        from PIL import Image, ImageDraw
        ok("Pillow imported OK")
        return True
    except ImportError as e:
        fail(f"Pillow not available: {e}")
        return False


def print_summary(results, working_chip=None):
    step("SUMMARY")
    for name, passed in results.items():
        if passed:
            ok(name)
        else:
            fail(name)

    print()
    if working_chip:
        print(f"\033[32m  Display works with {working_chip.upper()} driver!\033[0m")
        if working_chip == "sh1106":
            print()
            print("  \033[33mAction required:\033[0m Your module is an SH1106, not SSD1306.")
            print("  The app auto-detects this, but you can also set it explicitly:")
            print("    sudo nano ~/.config/oled-dashboard/config.json")
            print('    Change  "chip": "SSD1306"  →  "chip": "SH1106"')
            print("    sudo systemctl restart oled-dashboard")
        else:
            print()
            print("  The display hardware is confirmed working.")
            print("  If the dashboard app still shows nothing:")
            print("   • sudo journalctl -u oled-dashboard -n 50")
            print("   • Check config: sudo cat ~/.config/oled-dashboard/config.json")
    elif all(results.values()):
        print("\033[31m  All low-level checks passed but neither chip driver produced output.\033[0m")
        print("  Possible causes:")
        print("   • Display is physically damaged or counterfeit")
        print("   • Contrast/brightness stuck at 0 (try power cycling the Pi)")
        print("   • Try a different OLED module if available")
    else:
        print("\033[31m  Some checks failed. Fix the issues above then try again.\033[0m")
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
    results["i2c-dev module & /dev/i2c-1"] = True

    run_i2cdetect(args.bus)
    gpio_reset(4)  # Always try GPIO 4 reset (matches original OLED_Stats wiring)

    results["smbus2 available"] = check_smbus2()
    results["Pillow available"] = check_pil()

    if results["smbus2 available"]:
        results["device responds on I2C"] = raw_i2c_ping(addr, args.bus)
    else:
        results["device responds on I2C"] = False

    results["luma.oled available"] = check_luma()

    working_chip = None
    if results["luma.oled available"] and results.get("device responds on I2C", False):
        working_chip = chip_detection_test(addr, args.width, args.height, args.bus)
        results["display shows test pattern"] = working_chip is not None
    else:
        info("Skipping display test — prerequisites not met")
        results["display shows test pattern"] = False

    print_summary(results, working_chip)


if __name__ == "__main__":
    main()
