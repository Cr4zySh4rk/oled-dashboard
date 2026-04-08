/**
 * OLED Dashboard - Betaflight-style Layout Editor
 * Main application JavaScript
 */

(function () {
    'use strict';

    // ── State ──────────────────────────────────────────────────
    const state = {
        display: { chip: 'SSD1306', width: 128, height: 64, rotation: 0, interface: 'i2c', brightness: 255 },
        widgets: [],          // placed widget instances
        availableWidgets: [], // widget catalog
        selectedWidgetIdx: -1,
        scale: 4,             // canvas pixel scale
        gridSnap: 2,          // snap to 2px grid
        previewInterval: null,
        dragState: null,
    };

    // Widget icon map
    const WIDGET_ICONS = {
        cpu_usage: '⚡', ram_usage: '🧠', swap_usage: '💾', temperature: '🌡',
        uptime: '⏱', load_avg: '📊', hostname: '🏠', ip_address: '🌐',
        net_speed: '📶', net_usage: '📡', disk_space: '💿', disk_io: '📀',
        static_text: 'Aa', hline: '─', vline: '│', box: '□',
        progress_bar: '▓', datetime: '🕐',
    };

    // ── API helpers ────────────────────────────────────────────
    async function api(method, path, body = null) {
        const opts = { method, headers: { 'Content-Type': 'application/json' } };
        if (body) opts.body = JSON.stringify(body);
        const res = await fetch(path, opts);
        return res.json();
    }

    // ── Toast notifications ────────────────────────────────────
    function toast(msg, type = 'info') {
        const container = document.getElementById('toastContainer');
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.textContent = msg;
        container.appendChild(el);
        setTimeout(() => el.remove(), 3000);
    }

    // ── Initialize ─────────────────────────────────────────────
    async function init() {
        try {
            // Load available displays
            const displays = await api('GET', '/api/displays');
            populateDisplaySelector(displays);

            // Load widget catalog
            const categories = await api('GET', '/api/widgets/categories');
            populateWidgetPalette(categories);

            // Load current config
            const config = await api('GET', '/api/config');
            if (config.display) {
                state.display = { ...state.display, ...config.display };
                syncDisplayUI();
            }
            if (config.layout && config.layout.widgets) {
                state.widgets = config.layout.widgets;
            }

            // Set up canvas
            updateCanvas();
            renderPlacedWidgets();

            // Set up event listeners
            setupEventListeners();

            // Start preview
            startPreview();

            // Update status
            updateStatus('connected');
        } catch (err) {
            console.error('Init error:', err);
            updateStatus('error');
            toast('Failed to connect to server', 'error');
        }
    }

    // ── Display Selector ───────────────────────────────────────
    function populateDisplaySelector(displays) {
        const sel = document.getElementById('selDisplay');
        sel.innerHTML = '';
        displays.forEach(d => {
            const opt = document.createElement('option');
            opt.value = `${d.chip}:${d.width}x${d.height}`;
            opt.textContent = `${d.chip} ${d.description}`;
            sel.appendChild(opt);
        });
        // Set current value
        const val = `${state.display.chip}:${state.display.width}x${state.display.height}`;
        sel.value = val;
    }

    function syncDisplayUI() {
        const sel = document.getElementById('selDisplay');
        sel.value = `${state.display.chip}:${state.display.width}x${state.display.height}`;
        document.getElementById('selRotation').value = state.display.rotation;
        document.getElementById('selInterface').value = state.display.interface;
        document.getElementById('sliderBrightness').value = state.display.brightness || 255;
        document.getElementById('displayResolution').textContent = `${state.display.width} x ${state.display.height}`;
        document.getElementById('displayChip').textContent = state.display.chip;
    }

    // ── Widget Palette ─────────────────────────────────────────
    function populateWidgetPalette(categories) {
        const container = document.getElementById('widgetCategories');
        container.innerHTML = '';
        state.availableWidgets = [];

        const order = ['system', 'network', 'storage', 'general'];
        const catNames = { system: 'System', network: 'Network', storage: 'Storage', general: 'General' };

        order.forEach(cat => {
            const widgets = categories[cat];
            if (!widgets || widgets.length === 0) return;

            const catDiv = document.createElement('div');
            catDiv.className = `widget-category cat-${cat}`;

            const header = document.createElement('div');
            header.className = 'category-header';
            header.textContent = catNames[cat] || cat;
            catDiv.appendChild(header);

            widgets.forEach(w => {
                state.availableWidgets.push(w);
                const item = document.createElement('div');
                item.className = 'widget-item';
                item.dataset.widgetId = w.widget_id;
                item.draggable = true;
                item.innerHTML = `
                    <div class="widget-icon">${WIDGET_ICONS[w.widget_id] || '▪'}</div>
                    <div class="widget-info">
                        <div class="widget-name">${w.name}</div>
                        <div class="widget-desc">${w.description}</div>
                    </div>
                `;
                catDiv.appendChild(item);
            });

            container.appendChild(catDiv);
        });
    }

    // ── Canvas ─────────────────────────────────────────────────
    function updateCanvas() {
        const canvas = document.getElementById('oledCanvas');
        const frame = document.getElementById('displayFrame');
        const overlay = document.getElementById('widgetOverlay');
        const grid = document.getElementById('gridOverlay');

        const w = state.display.width;
        const h = state.display.height;
        const s = state.scale;

        canvas.width = w * s;
        canvas.height = h * s;
        canvas.style.width = `${w * s}px`;
        canvas.style.height = `${h * s}px`;

        frame.style.width = `${w * s}px`;
        frame.style.height = `${h * s}px`;

        overlay.style.width = `${w * s}px`;
        overlay.style.height = `${h * s}px`;

        grid.style.width = `${w * s}px`;
        grid.style.height = `${h * s}px`;
        grid.style.backgroundSize = `${s}px ${s}px`;

        // Clear canvas to black
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        document.getElementById('displayResolution').textContent = `${w} x ${h}`;
        document.getElementById('displayChip').textContent = state.display.chip;
    }

    // ── Placed Widgets ─────────────────────────────────────────
    function renderPlacedWidgets() {
        const overlay = document.getElementById('widgetOverlay');
        overlay.innerHTML = '';

        state.widgets.forEach((w, idx) => {
            const el = document.createElement('div');
            el.className = 'placed-widget' + (idx === state.selectedWidgetIdx ? ' selected' : '');
            el.dataset.index = idx;

            const s = state.scale;
            el.style.left = `${w.x * s}px`;
            el.style.top = `${w.y * s}px`;
            el.style.width = `${w.width * s}px`;
            el.style.height = `${w.height * s}px`;

            // Semi-transparent colored background per category
            const meta = state.availableWidgets.find(a => a.widget_id === w.widget_id);
            const cat = meta ? meta.category : 'general';
            const colors = { system: '88,166,255', network: '63,185,80', storage: '210,153,34', general: '188,140,255' };
            el.style.background = `rgba(${colors[cat] || '136,136,136'}, 0.15)`;

            // Label
            const label = document.createElement('span');
            label.className = 'widget-label';
            label.textContent = `${WIDGET_ICONS[w.widget_id] || ''} ${w.widget_id} [${w.x},${w.y}]`;
            el.appendChild(label);

            // Resize handle
            const handle = document.createElement('div');
            handle.className = 'resize-handle';
            el.appendChild(handle);

            overlay.appendChild(el);
        });

        // Render pixel preview on canvas
        renderCanvasPreview();
    }

    async function renderCanvasPreview() {
        try {
            const data = await api('POST', '/api/preview/layout', { widgets: state.widgets });
            if (data.image) {
                const img = new Image();
                img.onload = () => {
                    const canvas = document.getElementById('oledCanvas');
                    const ctx = canvas.getContext('2d');
                    ctx.imageSmoothingEnabled = false;
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                };
                img.src = 'data:image/png;base64,' + data.image;
            }
        } catch (e) {
            // Silently fail for preview
        }
    }

    // ── Properties Panel ───────────────────────────────────────
    function showProperties(idx) {
        state.selectedWidgetIdx = idx;
        const panel = document.getElementById('propertiesContent');

        if (idx < 0 || idx >= state.widgets.length) {
            panel.innerHTML = '<p class="placeholder-text">Select a widget on the canvas to edit its properties.</p>';
            renderPlacedWidgets();
            return;
        }

        const w = state.widgets[idx];
        const meta = state.availableWidgets.find(a => a.widget_id === w.widget_id);

        panel.innerHTML = `
            <div class="prop-group">
                <div class="prop-group-title">Widget</div>
                <div style="font-size:12px; color:var(--accent-cyan); margin-bottom:4px; font-weight:600;">
                    ${WIDGET_ICONS[w.widget_id] || ''} ${meta ? meta.name : w.widget_id}
                </div>
            </div>

            <div class="prop-group">
                <div class="prop-group-title">Position</div>
                <div class="prop-row">
                    <label>X</label>
                    <input type="number" id="propX" value="${w.x}" min="0" max="${state.display.width}" step="${state.gridSnap}">
                    <label>Y</label>
                    <input type="number" id="propY" value="${w.y}" min="0" max="${state.display.height}" step="${state.gridSnap}">
                </div>
            </div>

            <div class="prop-group">
                <div class="prop-group-title">Size</div>
                <div class="prop-row">
                    <label>W</label>
                    <input type="number" id="propW" value="${w.width}" min="4" max="${state.display.width}" step="${state.gridSnap}">
                    <label>H</label>
                    <input type="number" id="propH" value="${w.height}" min="4" max="${state.display.height}" step="${state.gridSnap}">
                </div>
            </div>

            <div class="prop-group">
                <div class="prop-group-title">Font</div>
                <div class="prop-row">
                    <label>Size</label>
                    <input type="number" id="propFontSize" value="${w.font_size || 12}" min="6" max="32" step="1">
                </div>
            </div>

            ${buildConfigFields(w)}

            <button class="btn btn-sm btn-danger btn-delete-widget" id="btnDeleteWidget">
                Remove Widget
            </button>
        `;

        // Bind property change listeners
        ['propX', 'propY', 'propW', 'propH', 'propFontSize'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('change', () => updateWidgetProperty(idx));
        });

        // Config fields
        panel.querySelectorAll('[data-config-key]').forEach(el => {
            el.addEventListener('change', () => updateWidgetConfig(idx));
        });

        // Delete button
        document.getElementById('btnDeleteWidget').addEventListener('click', () => {
            state.widgets.splice(idx, 1);
            state.selectedWidgetIdx = -1;
            showProperties(-1);
            renderPlacedWidgets();
        });

        renderPlacedWidgets();
    }

    function buildConfigFields(w) {
        const configs = {
            cpu_usage: [{ key: 'show_bar', label: 'Show Bar', type: 'checkbox' }],
            ram_usage: [{ key: 'format', label: 'Format', type: 'select', options: ['compact', 'bar'] }],
            temperature: [{ key: 'unit', label: 'Unit', type: 'select', options: ['C', 'F'] }],
            disk_space: [
                { key: 'mount_point', label: 'Mount', type: 'text', default: '/' },
                { key: 'show_bar', label: 'Show Bar', type: 'checkbox' },
            ],
            static_text: [{ key: 'text', label: 'Text', type: 'text', default: 'Hello' }],
            datetime: [{ key: 'format', label: 'Format', type: 'select', options: ['time', 'date', 'datetime', 'short_time'] }],
            ip_address: [{ key: 'show_label', label: 'Show Label', type: 'checkbox' }],
            net_speed: [{ key: 'interface', label: 'Interface', type: 'text', default: '' }],
            load_avg: [{ key: 'format', label: 'Format', type: 'select', options: ['all', '1min'] }],
            box: [{ key: 'filled', label: 'Filled', type: 'checkbox' }],
            progress_bar: [{ key: 'value', label: 'Value %', type: 'number', min: 0, max: 100 }],
        };

        const fields = configs[w.widget_id];
        if (!fields) return '';

        let html = '<div class="prop-group"><div class="prop-group-title">Configuration</div>';
        fields.forEach(f => {
            const val = (w.config && w.config[f.key] !== undefined) ? w.config[f.key] : (f.default || '');
            if (f.type === 'checkbox') {
                html += `<div class="prop-row">
                    <label>${f.label}</label>
                    <input type="checkbox" data-config-key="${f.key}" ${val ? 'checked' : ''}>
                </div>`;
            } else if (f.type === 'select') {
                html += `<div class="prop-row"><label>${f.label}</label><select data-config-key="${f.key}">`;
                f.options.forEach(o => {
                    html += `<option value="${o}" ${val === o ? 'selected' : ''}>${o}</option>`;
                });
                html += '</select></div>';
            } else if (f.type === 'number') {
                html += `<div class="prop-row">
                    <label>${f.label}</label>
                    <input type="number" data-config-key="${f.key}" value="${val}" min="${f.min || 0}" max="${f.max || 999}">
                </div>`;
            } else {
                html += `<div class="prop-row">
                    <label>${f.label}</label>
                    <input type="text" data-config-key="${f.key}" value="${val}">
                </div>`;
            }
        });
        html += '</div>';
        return html;
    }

    function updateWidgetProperty(idx) {
        const w = state.widgets[idx];
        w.x = parseInt(document.getElementById('propX').value) || 0;
        w.y = parseInt(document.getElementById('propY').value) || 0;
        w.width = parseInt(document.getElementById('propW').value) || 32;
        w.height = parseInt(document.getElementById('propH').value) || 12;
        w.font_size = parseInt(document.getElementById('propFontSize').value) || 12;

        // Snap to grid
        w.x = Math.round(w.x / state.gridSnap) * state.gridSnap;
        w.y = Math.round(w.y / state.gridSnap) * state.gridSnap;

        renderPlacedWidgets();
    }

    function updateWidgetConfig(idx) {
        const w = state.widgets[idx];
        if (!w.config) w.config = {};

        document.querySelectorAll('[data-config-key]').forEach(el => {
            const key = el.dataset.configKey;
            if (el.type === 'checkbox') {
                w.config[key] = el.checked;
            } else if (el.type === 'number') {
                w.config[key] = parseFloat(el.value);
            } else {
                w.config[key] = el.value;
            }
        });

        renderPlacedWidgets();
    }

    // ── Drag & Drop ────────────────────────────────────────────
    function setupEventListeners() {
        const overlay = document.getElementById('widgetOverlay');
        const frame = document.getElementById('displayFrame');

        // Widget palette drag
        document.querySelectorAll('.widget-item').forEach(item => {
            item.addEventListener('dragstart', onPaletteDragStart);
            item.addEventListener('dragend', onPaletteDragEnd);
        });

        // Drop zone
        frame.addEventListener('dragover', onCanvasDragOver);
        frame.addEventListener('drop', onCanvasDrop);

        // Placed widget interactions
        overlay.addEventListener('mousedown', onOverlayMouseDown);
        document.addEventListener('mousemove', onDocMouseMove);
        document.addEventListener('mouseup', onDocMouseUp);

        // Click outside to deselect
        frame.addEventListener('click', (e) => {
            if (e.target === frame || e.target.id === 'oledCanvas' || e.target.id === 'gridOverlay') {
                showProperties(-1);
            }
        });

        // Keyboard
        document.addEventListener('keydown', onKeyDown);

        // Display settings changes
        document.getElementById('selDisplay').addEventListener('change', onDisplayChange);
        document.getElementById('selRotation').addEventListener('change', onRotationChange);
        document.getElementById('selInterface').addEventListener('change', onInterfaceChange);
        document.getElementById('sliderBrightness').addEventListener('input', onBrightnessChange);

        // Save button
        document.getElementById('btnSaveLayout').addEventListener('click', saveLayout);

        // Clear all
        document.getElementById('btnClearAll').addEventListener('click', () => {
            if (confirm('Remove all widgets from the canvas?')) {
                state.widgets = [];
                state.selectedWidgetIdx = -1;
                showProperties(-1);
                renderPlacedWidgets();
            }
        });

        // Refresh preview
        document.getElementById('btnRefreshPreview').addEventListener('click', refreshPreview);

        // Widget search
        document.getElementById('widgetSearch').addEventListener('input', onWidgetSearch);

        // Modal
        document.getElementById('btnModalClose').addEventListener('click', closeModal);
        document.getElementById('btnModalCancel').addEventListener('click', closeModal);
    }

    // Palette drag
    let dragGhost = null;

    function onPaletteDragStart(e) {
        const widgetId = e.currentTarget.dataset.widgetId;
        e.dataTransfer.setData('text/plain', widgetId);
        e.dataTransfer.effectAllowed = 'copy';

        // Custom drag image
        dragGhost = document.createElement('div');
        dragGhost.className = 'drag-ghost';
        dragGhost.textContent = `${WIDGET_ICONS[widgetId] || '▪'} ${widgetId}`;
        document.body.appendChild(dragGhost);
        e.dataTransfer.setDragImage(dragGhost, 0, 0);
    }

    function onPaletteDragEnd() {
        if (dragGhost) { dragGhost.remove(); dragGhost = null; }
    }

    function onCanvasDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
    }

    function onCanvasDrop(e) {
        e.preventDefault();
        const widgetId = e.dataTransfer.getData('text/plain');
        if (!widgetId) return;

        const meta = state.availableWidgets.find(w => w.widget_id === widgetId);
        if (!meta) return;

        const rect = document.getElementById('displayFrame').getBoundingClientRect();
        let x = Math.floor((e.clientX - rect.left) / state.scale);
        let y = Math.floor((e.clientY - rect.top) / state.scale);

        // Snap
        x = Math.round(x / state.gridSnap) * state.gridSnap;
        y = Math.round(y / state.gridSnap) * state.gridSnap;

        // Clamp
        x = Math.max(0, Math.min(state.display.width - meta.default_size[0], x));
        y = Math.max(0, Math.min(state.display.height - meta.default_size[1], y));

        const newWidget = {
            widget_id: widgetId,
            x, y,
            width: meta.default_size[0],
            height: meta.default_size[1],
            font_size: 11,
            font_path: null,
            label: meta.name,
            config: {},
        };

        state.widgets.push(newWidget);
        const idx = state.widgets.length - 1;
        showProperties(idx);
        toast(`Added ${meta.name}`, 'success');

        if (dragGhost) { dragGhost.remove(); dragGhost = null; }
    }

    // Placed widget move/resize
    function onOverlayMouseDown(e) {
        const widget = e.target.closest('.placed-widget');
        if (!widget) return;

        const idx = parseInt(widget.dataset.index);
        showProperties(idx);

        const isResize = e.target.classList.contains('resize-handle');
        const rect = document.getElementById('displayFrame').getBoundingClientRect();

        state.dragState = {
            type: isResize ? 'resize' : 'move',
            index: idx,
            startMouseX: e.clientX,
            startMouseY: e.clientY,
            startX: state.widgets[idx].x,
            startY: state.widgets[idx].y,
            startW: state.widgets[idx].width,
            startH: state.widgets[idx].height,
            frameRect: rect,
        };

        e.preventDefault();
    }

    function onDocMouseMove(e) {
        if (!state.dragState) return;

        const d = state.dragState;
        const w = state.widgets[d.index];
        const s = state.scale;
        const dx = (e.clientX - d.startMouseX) / s;
        const dy = (e.clientY - d.startMouseY) / s;

        if (d.type === 'move') {
            let newX = Math.round((d.startX + dx) / state.gridSnap) * state.gridSnap;
            let newY = Math.round((d.startY + dy) / state.gridSnap) * state.gridSnap;
            newX = Math.max(0, Math.min(state.display.width - w.width, newX));
            newY = Math.max(0, Math.min(state.display.height - w.height, newY));
            w.x = newX;
            w.y = newY;
        } else if (d.type === 'resize') {
            let newW = Math.round((d.startW + dx) / state.gridSnap) * state.gridSnap;
            let newH = Math.round((d.startH + dy) / state.gridSnap) * state.gridSnap;
            newW = Math.max(4, Math.min(state.display.width - w.x, newW));
            newH = Math.max(4, Math.min(state.display.height - w.y, newH));
            w.width = newW;
            w.height = newH;
        }

        renderPlacedWidgets();
        // Update properties panel in real-time
        const propX = document.getElementById('propX');
        if (propX) {
            propX.value = w.x;
            document.getElementById('propY').value = w.y;
            document.getElementById('propW').value = w.width;
            document.getElementById('propH').value = w.height;
        }
    }

    function onDocMouseUp() {
        if (state.dragState) {
            state.dragState = null;
            renderPlacedWidgets();
        }
    }

    function onKeyDown(e) {
        // Delete/Backspace removes selected widget
        if ((e.key === 'Delete' || e.key === 'Backspace') && state.selectedWidgetIdx >= 0) {
            // Don't delete if an input is focused
            if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'SELECT') return;
            state.widgets.splice(state.selectedWidgetIdx, 1);
            state.selectedWidgetIdx = -1;
            showProperties(-1);
            renderPlacedWidgets();
            e.preventDefault();
        }

        // Arrow keys to nudge
        if (state.selectedWidgetIdx >= 0 && ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
            if (document.activeElement.tagName === 'INPUT') return;
            const w = state.widgets[state.selectedWidgetIdx];
            const step = e.shiftKey ? 1 : state.gridSnap;
            switch (e.key) {
                case 'ArrowLeft': w.x = Math.max(0, w.x - step); break;
                case 'ArrowRight': w.x = Math.min(state.display.width - w.width, w.x + step); break;
                case 'ArrowUp': w.y = Math.max(0, w.y - step); break;
                case 'ArrowDown': w.y = Math.min(state.display.height - w.height, w.y + step); break;
            }
            showProperties(state.selectedWidgetIdx);
            renderPlacedWidgets();
            e.preventDefault();
        }
    }

    // ── Display Settings ───────────────────────────────────────
    function onDisplayChange() {
        const val = document.getElementById('selDisplay').value;
        const [chip, res] = val.split(':');
        const [w, h] = res.split('x').map(Number);
        state.display.chip = chip;
        state.display.width = w;
        state.display.height = h;

        // Remove widgets that fall outside new bounds
        state.widgets = state.widgets.filter(widget =>
            widget.x < w && widget.y < h
        );
        state.widgets.forEach(widget => {
            if (widget.x + widget.width > w) widget.width = w - widget.x;
            if (widget.y + widget.height > h) widget.height = h - widget.y;
        });

        updateCanvas();
        renderPlacedWidgets();
        syncDisplayUI();
    }

    function onRotationChange() {
        state.display.rotation = parseInt(document.getElementById('selRotation').value);
    }

    function onInterfaceChange() {
        state.display.interface = document.getElementById('selInterface').value;
    }

    function onBrightnessChange() {
        state.display.brightness = parseInt(document.getElementById('sliderBrightness').value);
    }

    // ── Search ─────────────────────────────────────────────────
    function onWidgetSearch(e) {
        const query = e.target.value.toLowerCase();
        document.querySelectorAll('.widget-item').forEach(item => {
            const name = item.querySelector('.widget-name').textContent.toLowerCase();
            const desc = item.querySelector('.widget-desc').textContent.toLowerCase();
            item.style.display = (name.includes(query) || desc.includes(query)) ? '' : 'none';
        });
    }

    // ── Save / Load ────────────────────────────────────────────
    async function saveLayout() {
        try {
            // Save display config
            await api('POST', '/api/display', state.display);

            // Save layout
            await api('POST', '/api/layout', {
                name: 'Current',
                widgets: state.widgets,
            });

            toast('Layout saved!', 'success');
        } catch (err) {
            toast('Failed to save layout', 'error');
        }
    }

    // ── Preview ────────────────────────────────────────────────
    async function refreshPreview() {
        try {
            const data = await api('POST', '/api/preview/layout', { widgets: state.widgets });
            if (data.image) {
                document.getElementById('previewImage').src = 'data:image/png;base64,' + data.image;
            }
        } catch (e) {
            // Silently fail
        }
    }

    function startPreview() {
        refreshPreview();
        state.previewInterval = setInterval(() => {
            if (document.getElementById('chkAutoPreview').checked) {
                refreshPreview();
            }
        }, 2000);
    }

    // ── Modal ──────────────────────────────────────────────────
    function closeModal() {
        document.getElementById('modalOverlay').style.display = 'none';
    }

    // ── Status ─────────────────────────────────────────────────
    function updateStatus(status) {
        const dot = document.querySelector('.status-dot');
        const text = document.querySelector('.status-text');
        dot.className = `status-dot ${status}`;
        text.textContent = status === 'connected' ? 'Connected' : status === 'error' ? 'Disconnected' : 'Connecting...';
    }

    // ── Boot ───────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', init);

})();
