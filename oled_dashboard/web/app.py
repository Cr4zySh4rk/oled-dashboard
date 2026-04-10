"""
Flask web application for OLED Dashboard configuration.
Serves the Betaflight-style layout editor and API endpoints.
"""

import os
import json
from flask import Flask, render_template, request, jsonify, send_from_directory, Response

from oled_dashboard.config_manager import ConfigManager
from oled_dashboard.renderer import DisplayRenderer
from oled_dashboard.widgets.registry import WidgetRegistry
from oled_dashboard.drivers.registry import DriverRegistry


def create_app(config_manager: ConfigManager = None, renderer: DisplayRenderer = None):
    """Create and configure the Flask application."""

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    if config_manager is None:
        config_manager = ConfigManager()
    if renderer is None:
        renderer = DisplayRenderer(config_manager, simulate=True)
        renderer.initialize()

    # Store references
    app.config_manager = config_manager
    app.renderer = renderer

    # ── Pages ──────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        """Main dashboard / layout editor page."""
        config = config_manager.load()
        return render_template(
            "index.html",
            config=config,
            version="1.0.0",
        )

    # ── API: Display Settings ─────────────────────────────────────────

    @app.route("/api/displays", methods=["GET"])
    def api_list_displays():
        """List all supported display configurations."""
        return jsonify(DriverRegistry.list_all_displays())

    @app.route("/api/display", methods=["GET"])
    def api_get_display():
        """Get current display configuration."""
        return jsonify(config_manager.get_display_config())

    @app.route("/api/display", methods=["POST"])
    def api_set_display():
        """Update display configuration."""
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        config_manager.set_display_config(data)

        # Reinitialize renderer with new settings
        renderer.stop()
        renderer.initialize()
        renderer.start()

        return jsonify({"status": "ok", "display": data})

    # ── API: Widgets ──────────────────────────────────────────────────

    @app.route("/api/widgets", methods=["GET"])
    def api_list_widgets():
        """List all available widgets."""
        return jsonify(WidgetRegistry.list_widgets())

    @app.route("/api/widgets/categories", methods=["GET"])
    def api_list_widget_categories():
        """List widgets grouped by category."""
        return jsonify(WidgetRegistry.list_by_category())

    # ── API: Layout ───────────────────────────────────────────────────

    @app.route("/api/layout", methods=["GET"])
    def api_get_layout():
        """Get the current pages and page interval."""
        return jsonify({
            "pages": config_manager.get_pages(),
            "page_interval": config_manager.get_page_interval(),
            # Legacy field for backward compat
            "layout": config_manager.get_layout(),
        })

    @app.route("/api/layout", methods=["POST"])
    def api_set_layout():
        """Update pages (and optionally page_interval). Accepts multi-page or legacy format."""
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        if "pages" in data:
            config_manager.set_pages(data["pages"])
        elif "widgets" in data:
            # Legacy single-layout format
            config_manager.set_pages([{"name": "Page 1", "widgets": data["widgets"]}])

        if "page_interval" in data:
            config_manager.set_page_interval(data["page_interval"])

        renderer.reload_layout()
        return jsonify({"status": "ok"})

    @app.route("/api/layout/presets", methods=["GET"])
    def api_list_presets():
        """List saved layout presets."""
        return jsonify(config_manager.list_layout_presets())

    @app.route("/api/layout/presets", methods=["POST"])
    def api_save_preset():
        """Save a layout preset."""
        data = request.get_json()
        name = data.get("name")
        layout = data.get("layout") or config_manager.get_layout()
        if not name:
            return jsonify({"error": "Name required"}), 400
        config_manager.save_layout_preset(name, layout)
        return jsonify({"status": "ok"})

    @app.route("/api/layout/presets/<name>", methods=["GET"])
    def api_load_preset(name):
        """Load a saved layout preset."""
        preset = config_manager.load_layout_preset(name)
        if preset is None:
            return jsonify({"error": "Preset not found"}), 404
        return jsonify(preset)

    @app.route("/api/layout/presets/<name>", methods=["DELETE"])
    def api_delete_preset(name):
        """Delete a saved layout preset."""
        if config_manager.delete_layout_preset(name):
            return jsonify({"status": "ok"})
        return jsonify({"error": "Preset not found"}), 404

    # ── API: Preview ──────────────────────────────────────────────────

    @app.route("/api/preview", methods=["GET"])
    def api_preview():
        """Get a live preview of the current display."""
        scale = request.args.get("scale", 4, type=int)
        b64 = renderer.get_preview_base64(scale=scale)
        return jsonify({"image": b64})

    @app.route("/api/preview/layout", methods=["POST"])
    def api_preview_layout():
        """Preview a specific layout without saving it."""
        data = request.get_json()
        if not data:
            return jsonify({"error": "No layout data"}), 400

        # Temporarily apply the layout for preview
        from oled_dashboard.widgets.registry import WidgetRegistry
        from PIL import Image, ImageDraw
        from oled_dashboard.drivers.simulate import SimulatedDriver

        display_cfg = config_manager.get_display_config()
        width = display_cfg.get("width", 128)
        height = display_cfg.get("height", 64)

        image = Image.new("1", (width, height), 0)
        draw = ImageDraw.Draw(image)

        for wc in data.get("widgets", []):
            widget = WidgetRegistry.create_from_dict(wc)
            if widget:
                try:
                    widget.draw(draw)
                except Exception:
                    pass

        sim = SimulatedDriver(width=width, height=height)
        sim.initialize()
        sim.display_image(image)

        scale = request.args.get("scale", 4, type=int)
        b64 = sim.get_framebuffer_base64(scale=scale)
        return jsonify({"image": b64})

    # ── API: System ───────────────────────────────────────────────────

    @app.route("/api/config", methods=["GET"])
    def api_get_config():
        """Get the full configuration (includes pages + page_interval)."""
        cfg = config_manager.load()
        # Inject pages/page_interval so the JS can use them directly
        cfg["pages"] = config_manager.get_pages()
        cfg["page_interval"] = config_manager.get_page_interval()
        return jsonify(cfg)

    @app.route("/api/config/reset", methods=["POST"])
    def api_reset_config():
        """Reset configuration to defaults."""
        config_manager.reset_to_defaults()
        renderer.reload_layout()
        return jsonify({"status": "ok"})

    @app.route("/api/config/export", methods=["GET"])
    def api_export_config():
        """Download the full config as a JSON backup file."""
        cfg = config_manager.load()
        cfg["pages"] = config_manager.get_pages()
        cfg["page_interval"] = config_manager.get_page_interval()
        payload = json.dumps(cfg, indent=2)
        return Response(
            payload,
            mimetype="application/json",
            headers={"Content-Disposition": 'attachment; filename="oled-dashboard-config.json"'},
        )

    @app.route("/api/config/import", methods=["POST"])
    def api_import_config():
        """Apply a previously exported config (restore from backup)."""
        # Accept either a multipart file upload or a raw JSON body
        if request.files and "file" in request.files:
            try:
                data = json.loads(request.files["file"].read())
            except Exception:
                return jsonify({"error": "Could not parse uploaded file as JSON"}), 400
        else:
            data = request.get_json()

        if not data:
            return jsonify({"error": "No config data provided"}), 400

        try:
            config_manager.import_config(data)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        renderer.stop()
        renderer.initialize()
        renderer.start()
        return jsonify({"status": "ok", "message": "Config restored successfully"})

    @app.route("/api/status", methods=["GET"])
    def api_status():
        """Get system status."""
        return jsonify({
            "renderer_running": renderer.is_running,
            "simulated": renderer.is_simulated,
            "display": config_manager.get_display_config(),
            "widget_count": len(renderer.widgets),
        })

    @app.route("/api/renderer/start", methods=["POST"])
    def api_start_renderer():
        """Start the display renderer."""
        renderer.start()
        return jsonify({"status": "ok", "running": True})

    @app.route("/api/renderer/stop", methods=["POST"])
    def api_stop_renderer():
        """Stop the display renderer."""
        renderer.stop()
        return jsonify({"status": "ok", "running": False})

    @app.route("/api/renderer/restart", methods=["POST"])
    def api_restart_renderer():
        """Restart the display renderer."""
        renderer.stop()
        renderer.initialize()
        renderer.start()
        return jsonify({"status": "ok", "running": True})

    # ── Pi-hole integration status ─────────────────────────────────────

    @app.route("/api/pihole/status", methods=["GET"])
    def api_pihole_status():
        """Return whether Pi-hole is detected on this host."""
        try:
            from oled_dashboard.widgets.pihole_widgets import is_pihole_available
            available = is_pihole_available()
        except Exception:
            available = False
        return jsonify({"available": available})

    return app
