"""
OLED Dashboard - Main entry point.
Run with: python -m oled_dashboard
"""

import argparse
import signal
import sys
import threading

from oled_dashboard.config_manager import ConfigManager
from oled_dashboard.renderer import DisplayRenderer
from oled_dashboard.web.app import create_app


def main():
    parser = argparse.ArgumentParser(
        description="OLED Dashboard - Web-configurable OLED display manager"
    )
    parser.add_argument(
        "--config-dir",
        default=None,
        help="Configuration directory (default: ~/.config/oled-dashboard)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Web server host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Web server port (default: 8686)",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run in simulation mode (no hardware required)",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Start web server only, don't drive the OLED display",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode",
    )

    args = parser.parse_args()

    # Initialize configuration
    config_manager = ConfigManager(config_dir=args.config_dir)
    config = config_manager.load()

    # Determine settings (CLI overrides config)
    host = args.host or config.get("server", {}).get("host", "0.0.0.0")
    port = args.port or config.get("server", {}).get("port", 8686)
    debug = args.debug or config.get("server", {}).get("debug", False)
    simulate = args.simulate

    # Initialize renderer
    renderer = DisplayRenderer(config_manager, simulate=simulate)
    renderer.initialize()

    # Start display rendering unless --no-display
    if not args.no_display:
        renderer.start()
        print(f"[OLED Dashboard] Display renderer started"
              f" ({'simulated' if renderer.is_simulated else 'hardware'})")

    # Create Flask app
    app = create_app(config_manager=config_manager, renderer=renderer)

    # Graceful shutdown
    def shutdown(signum, frame):
        print("\n[OLED Dashboard] Shutting down...")
        renderer.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Start web server
    print(f"[OLED Dashboard] Web UI: http://{host}:{port}")
    print(f"[OLED Dashboard] Press Ctrl+C to stop")

    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    main()
