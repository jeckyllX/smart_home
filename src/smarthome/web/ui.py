"""
Web interface HTML/CSS/JavaScript template for Smart Home dashboard.
Single-page application with zero external dependencies.
"""

from __future__ import annotations

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Home Climate Dashboard</title>
    <style>
        :root {
            --bg: #0f172a;
            --surface: #1e293b;
            --surface-hover: #334155;
            --border: #334155;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #38bdf8;
            --primary-hover: #0ea5e9;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --accent: #818cf8;
            --radius: 12px;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            padding: 1.5rem;
            line-height: 1.5;
        }

        .container { max-width: 1280px; margin: 0 auto; }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--border);
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
            gap: 1rem;
        }

        .brand { display: flex; align-items: center; gap: 0.75rem; }
        .brand h1 { font-size: 1.5rem; font-weight: 700; color: var(--primary); }
        .live-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            font-size: 0.75rem;
            padding: 0.2rem 0.6rem;
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            border-radius: 999px;
            font-weight: 600;
        }
        .live-dot { width: 8px; height: 8px; background: var(--success); border-radius: 50%; }

        .header-actions { display: flex; align-items: center; gap: 0.75rem; }

        button {
            cursor: pointer;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            font-weight: 600;
            font-size: 0.875rem;
            transition: all 0.15s ease;
        }
        .btn-primary { background: var(--primary); color: #000; }
        .btn-primary:hover { background: var(--primary-hover); }
        .btn-secondary { background: var(--surface); color: var(--text); border: 1px solid var(--border); }
        .btn-secondary:hover { background: var(--surface-hover); }
        .btn-danger { background: rgba(239, 68, 68, 0.2); color: var(--danger); border: 1px solid var(--danger); }
        .btn-danger:hover { background: var(--danger); color: #fff; }
        .btn-sm { padding: 0.25rem 0.6rem; font-size: 0.75rem; }

        /* Grid */
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.06);
            padding-bottom: 0.75rem;
        }

        .room-title {
            font-size: 1.15rem;
            font-weight: 700;
            text-transform: capitalize;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .badge {
            font-size: 0.7rem;
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .badge-success { background: rgba(16, 185, 129, 0.2); color: var(--success); }
        .badge-warning { background: rgba(245, 158, 11, 0.2); color: var(--warning); }
        .badge-danger { background: rgba(239, 68, 68, 0.2); color: var(--danger); }
        .badge-accent { background: rgba(129, 140, 248, 0.2); color: var(--accent); }

        /* Metrics */
        .metrics-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 0.75rem;
        }
        .metric-box {
            background: rgba(15, 23, 42, 0.5);
            padding: 0.65rem 0.85rem;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.04);
        }
        .metric-label { font-size: 0.75rem; color: var(--text-muted); }
        .metric-value { font-size: 1.2rem; font-weight: 700; color: var(--text); }
        .metric-sub { font-size: 0.7rem; color: var(--text-muted); }

        /* Dehumidifier Controls */
        .control-group {
            background: rgba(15, 23, 42, 0.6);
            padding: 1rem;
            border-radius: 10px;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .control-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .mode-buttons { display: flex; gap: 0.35rem; flex-wrap: wrap; }
        .mode-btn {
            background: var(--surface);
            color: var(--text-muted);
            border: 1px solid var(--border);
            padding: 0.3rem 0.65rem;
            font-size: 0.75rem;
            border-radius: 6px;
        }
        .mode-btn.active {
            background: var(--primary);
            color: #000;
            border-color: var(--primary);
            font-weight: 700;
        }

        .range-slider {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            width: 100%;
        }
        input[type="range"] {
            flex: 1;
            accent-color: var(--primary);
        }

        /* Config Panels */
        .accordion {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            margin-bottom: 1.5rem;
            overflow: hidden;
        }
        .accordion-header {
            padding: 1rem 1.25rem;
            cursor: pointer;
            font-weight: 700;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(255,255,255,0.02);
        }
        .accordion-header:hover { background: rgba(255,255,255,0.04); }
        .accordion-content {
            padding: 1.25rem;
            border-top: 1px solid var(--border);
            display: none;
        }
        .accordion.open .accordion-content { display: block; }

        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin-bottom: 1.25rem;
        }
        .form-field { display: flex; flex-direction: column; gap: 0.35rem; }
        .form-field label { font-size: 0.8rem; font-weight: 600; color: var(--text-muted); }
        input[type="text"], input[type="number"], select {
            background: var(--bg);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 0.5rem 0.75rem;
            border-radius: 6px;
            font-size: 0.875rem;
        }
        .checkbox-label {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            cursor: pointer;
            font-size: 0.875rem;
        }

        .days-selector {
            display: flex;
            gap: 0.4rem;
            flex-wrap: wrap;
        }
        .day-check {
            display: flex;
            align-items: center;
            gap: 0.2rem;
            background: var(--bg);
            padding: 0.3rem 0.5rem;
            border-radius: 6px;
            font-size: 0.75rem;
            border: 1px solid var(--border);
        }

        /* Exclusion Windows */
        .exclusion-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            margin-bottom: 1rem;
        }
        .exclusion-table th, .exclusion-table td {
            padding: 0.5rem 0.75rem;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }

        /* Alerts Banner */
        .alerts-container {
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
            margin-bottom: 1.25rem;
        }
        .alert-banner {
            padding: 0.75rem 1rem;
            border-radius: 8px;
            font-size: 0.875rem;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .alert-critical {
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid var(--danger);
            color: #fca5a5;
        }
        .alert-warning {
            background: rgba(245, 158, 11, 0.2);
            border: 1px solid var(--warning);
            color: #fcd34d;
        }

        /* 24h SVG Trend Chart */
        .chart-box {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 10px;
            padding: 0.85rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text);
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        .chart-hint {
            font-size: 0.72rem;
            color: var(--text-muted);
            background: rgba(255, 255, 255, 0.025);
            padding: 0.4rem 0.65rem;
            border-radius: 6px;
            border-left: 3px solid var(--warning);
            line-height: 1.4;
        }
        .chart-inspect-bar {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.72rem;
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 6px;
            padding: 0.35rem 0.6rem;
            color: var(--text);
            min-height: 26px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 0.35rem;
        }
        .chart-legend {
            display: flex;
            gap: 0.65rem;
            font-size: 0.7rem;
            flex-wrap: wrap;
            align-items: center;
        }
        .chart-legend-item {
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
        }

        /* Logs Console */
        .log-console {
            background: #090d16;
            border-radius: 8px;
            padding: 0.75rem;
            font-family: monospace;
            font-size: 0.8rem;
            color: #38bdf8;
            max-height: 220px;
            overflow-y: auto;
            border: 1px solid var(--border);
        }
        .log-line { margin-bottom: 0.25rem; }

        @media (max-width: 640px) {
            body { padding: 0.75rem; }
            .grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand">
                <h1>SmartHome Climate</h1>
                <span class="live-badge"><span class="live-dot"></span> Live</span>
            </div>
            <div class="header-actions">
                <span id="last-eval-time" style="font-size: 0.75rem; color: var(--text-muted);">Syncing...</span>
                <button class="btn-secondary btn-sm" onclick="fetchState()">Refresh</button>
                <button class="btn-primary btn-sm" onclick="triggerEvaluate()">Evaluate Now</button>
            </div>
        </header>

        <!-- Active Health Alerts Banner -->
        <div id="alerts-banner" class="alerts-container" style="display: none;"></div>

        <!-- Rooms Grid -->
        <main class="grid" id="rooms-grid">
            <div style="color: var(--text-muted); font-size: 0.9rem;">Loading room data...</div>
        </main>

        <!-- Configuration Accordion -->
        <div class="accordion" id="config-accordion">
            <div class="accordion-header" onclick="toggleAccordion('config-accordion')">
                <span>⚙️ Automation, Schedule & Exclusion Settings</span>
                <span id="accordion-arrow">▼</span>
            </div>
            <div class="accordion-content">
                <form id="config-form" onsubmit="saveConfig(event)">
                    <h3 style="margin-bottom: 0.75rem; color: var(--primary); font-size: 1rem;">1. Condensation Prevention & Auto-Power</h3>
                    <div class="form-grid">
                        <div class="form-field">
                            <label class="checkbox-label">
                                <input type="checkbox" id="cfg-auto-power">
                                <strong>Sensor-Driven Auto Power</strong>
                            </label>
                            <span style="font-size: 0.7rem; color: var(--text-muted);">Turns dehumidifier ON/OFF based on room climate sensor</span>
                        </div>
                        <div class="form-field">
                            <label for="cfg-min-rh">Min Target RH (%)</label>
                            <input type="number" id="cfg-min-rh" min="35" max="70" step="5">
                        </div>
                        <div class="form-field">
                            <label for="cfg-max-rh">Max Target RH (%)</label>
                            <input type="number" id="cfg-max-rh" min="35" max="70" step="5">
                        </div>
                        <div class="form-field">
                            <label for="cfg-on-offset">Turn-ON Offset RH (%)</label>
                            <input type="number" id="cfg-on-offset" min="0" max="10" step="0.5">
                        </div>
                        <div class="form-field">
                            <label for="cfg-off-offset">Turn-OFF Offset RH (%)</label>
                            <input type="number" id="cfg-off-offset" min="0" max="10" step="0.5">
                        </div>
                        <div class="form-field">
                            <label for="cfg-min-cycle">Compressor Cooldown (sec)</label>
                            <input type="number" id="cfg-min-cycle" min="60" max="1800" step="30">
                        </div>
                        <div class="form-field">
                            <label for="cfg-lookahead">Forecast Lookahead (hours)</label>
                            <input type="number" id="cfg-lookahead" min="0" max="24" step="1">
                        </div>
                        <div class="form-field">
                            <label for="cfg-glazing">Window Glazing</label>
                            <select id="cfg-glazing">
                                <option value="single">Single</option>
                                <option value="secondary">Secondary</option>
                                <option value="double">Double</option>
                                <option value="triple">Triple</option>
                            </select>
                        </div>
                        <div class="form-field">
                            <label for="cfg-override-mins">Manual Hold Duration (min)</label>
                            <input type="number" id="cfg-override-mins" min="0" max="1440" step="15">
                        </div>
                    </div>

                    <h3 style="margin: 1.25rem 0 0.75rem 0; color: var(--warning); font-size: 1rem;">1b. Health & Alert Notifications</h3>
                    <div class="form-grid">
                        <div class="form-field">
                            <label for="cfg-low-batt">Low Battery Alert (%)</label>
                            <input type="number" id="cfg-low-batt" min="1" max="50" step="5">
                        </div>
                        <div class="form-field">
                            <label for="cfg-webhook-url">Alert Webhook URL (optional)</label>
                            <input type="text" id="cfg-webhook-url" placeholder="https://ntfy.sh/your-topic">
                        </div>
                    </div>

                    <h3 style="margin: 1.25rem 0 0.75rem 0; color: var(--accent); font-size: 1rem;">2. Quiet Hours & Mode Schedule</h3>
                    <div class="form-grid">
                        <div class="form-field">
                            <label class="checkbox-label">
                                <input type="checkbox" id="cfg-sched-enabled">
                                <strong>Enable Schedule</strong>
                            </label>
                        </div>
                        <div class="form-field">
                            <label for="cfg-start-time">Night Start Time (HH:MM)</label>
                            <input type="text" id="cfg-start-time" pattern="[0-2][0-9]:[0-5][0-9]">
                        </div>
                        <div class="form-field">
                            <label for="cfg-end-time">Night End Time (HH:MM)</label>
                            <input type="text" id="cfg-end-time" pattern="[0-2][0-9]:[0-5][0-9]">
                        </div>
                        <div class="form-field">
                            <label for="cfg-night-mode">Night Mode</label>
                            <select id="cfg-night-mode">
                                <option value="sleep">sleep</option>
                                <option value="manual">manual</option>
                            </select>
                        </div>
                        <div class="form-field">
                            <label for="cfg-day-mode">Day Mode</label>
                            <select id="cfg-day-mode">
                                <option value="manual">manual</option>
                                <option value="sleep">sleep</option>
                                <option value="purify">purify</option>
                            </select>
                        </div>
                    </div>

                    <div style="margin-bottom: 1.25rem;">
                        <label style="font-size: 0.8rem; font-weight: 600; color: var(--text-muted); display: block; margin-bottom: 0.35rem;">
                            Stay in Night Mode All Day on these days:
                        </label>
                        <div class="days-selector" id="all-day-sleep-days">
                            <!-- populated by JS -->
                        </div>
                    </div>

                    <h3 style="margin: 1.25rem 0 0.75rem 0; color: var(--danger); font-size: 1rem;">3. Exclusion Windows (Force OFF & Block Power)</h3>
                    <div style="overflow-x: auto;">
                        <table class="exclusion-table" id="exclusions-table">
                            <thead>
                                <tr>
                                    <th>Enabled</th>
                                    <th>Label</th>
                                    <th>Time</th>
                                    <th>Days</th>
                                    <th>Room</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody id="exclusions-body">
                                <!-- populated by JS -->
                            </tbody>
                        </table>
                    </div>
                    <button type="button" class="btn-secondary btn-sm" onclick="addExclusionRow()">+ Add Exclusion Window</button>

                    <div style="margin-top: 1.5rem; display: flex; gap: 0.75rem;">
                        <button type="submit" class="btn-primary">Save & Apply Changes</button>
                        <button type="button" class="btn-secondary" onclick="fetchConfig()">Reset Form</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Recent Logs Section -->
        <div class="card">
            <div class="card-header">
                <span style="font-weight: 700; font-size: 0.95rem;">📜 Automation Decision Logs</span>
            </div>
            <div class="log-console" id="log-console">
                <div class="log-line">Waiting for first evaluation cycle...</div>
            </div>
        </div>
    </div>

    <script>
        const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
        let currentConfig = null;
        let currentState = null;
        let roomHistory = {};

        function toggleAccordion(id) {
            const el = document.getElementById(id);
            el.classList.toggle('open');
            document.getElementById('accordion-arrow').innerText = el.classList.contains('open') ? '▲' : '▼';
        }

        async function fetchState() {
            try {
                const [stateRes, histRes] = await Promise.all([
                    fetch('/api/state'),
                    fetch('/api/history?hours=24')
                ]);
                currentState = await stateRes.json();
                if (histRes.ok) {
                    const histData = await histRes.json();
                    roomHistory = histData.rooms || {};
                }
                renderAlerts(currentState.alerts || []);
                renderRooms(currentState);
                renderLogs(currentState);
            } catch (err) {
                console.error("Failed to fetch state:", err);
            }
        }

        function renderAlerts(alerts) {
            const container = document.getElementById('alerts-banner');
            if (!alerts || !alerts.length) {
                container.style.display = 'none';
                container.innerHTML = '';
                return;
            }
            container.style.display = 'flex';
            container.innerHTML = alerts.map(a => `
                <div class="alert-banner ${a.severity === 'critical' ? 'alert-critical' : 'alert-warning'}">
                    <span>${a.severity === 'critical' ? '🚨' : '⚠️'} ${a.message}</span>
                    <span class="badge ${a.severity === 'critical' ? 'badge-danger' : 'badge-warning'}">${a.severity}</span>
                </div>
            `).join('');
        }

        async function fetchConfig() {
            try {
                const res = await fetch('/api/config');
                currentConfig = await res.json();
                populateConfigForm(currentConfig);
            } catch (err) {
                console.error("Failed to fetch config:", err);
            }
        }

        window.__roomPoints = window.__roomPoints || {};

        function onChartHover(e, safeId) {
            const points = window.__roomPoints[safeId];
            if (!points || points.length < 2) return;
            const svg = document.getElementById('chart-svg-' + safeId);
            if (!svg) return;
            const rect = svg.getBoundingClientRect();
            const clientX = e.clientX ?? (e.touches && e.touches[0] ? e.touches[0].clientX : null);
            if (clientX == null) return;
            const relX = clientX - rect.left;
            const W = 380, PAD_LEFT = 32, PAD_RIGHT = 12;
            const svgX = (relX / rect.width) * W;
            const clampedX = Math.max(PAD_LEFT, Math.min(W - PAD_RIGHT, svgX));
            const ratio = (clampedX - PAD_LEFT) / (W - PAD_LEFT - PAD_RIGHT);
            const idx = Math.max(0, Math.min(points.length - 1, Math.round(ratio * (points.length - 1))));

            const curLine = document.getElementById('cursor-line-' + safeId);
            if (curLine) {
                curLine.setAttribute('x1', clampedX.toFixed(1));
                curLine.setAttribute('x2', clampedX.toFixed(1));
                curLine.setAttribute('visibility', 'visible');
            }
            updateInspectBar(safeId, points[idx], false);
        }

        function onChartTouch(e, safeId) {
            if (e.touches && e.touches.length) {
                onChartHover(e.touches[0], safeId);
            }
        }

        function onChartLeave(safeId) {
            const curLine = document.getElementById('cursor-line-' + safeId);
            if (curLine) {
                curLine.setAttribute('visibility', 'hidden');
            }
            const points = window.__roomPoints[safeId];
            if (points && points.length) {
                updateInspectBar(safeId, points[points.length - 1], true);
            }
        }

        function updateInspectBar(safeId, pt, isLatest) {
            const bar = document.getElementById('chart-inspect-' + safeId);
            if (!bar || !pt) return;
            const d = new Date(pt.timestamp * 1000);
            const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const tag = isLatest ? 'Latest' : timeStr;

            const tStr = pt.indoor_temp_c != null ? `${pt.indoor_temp_c.toFixed(1)}°C` : '--';
            const rhStr = pt.indoor_rh_percent != null ? `${Math.round(pt.indoor_rh_percent)}%` : '--';
            const dpStr = pt.dew_point_c != null ? `${pt.dew_point_c.toFixed(1)}°C` : '--';
            const safeStr = pt.safe_dew_point_c != null ? `${pt.safe_dew_point_c.toFixed(1)}°C` : '--';

            let html = `<span><strong>${tag}:</strong> 🌡️ <span style="color:#f43f5e;font-weight:700;">${tStr}</span> | 💧 <span style="color:#38bdf8;font-weight:700;">${rhStr} RH</span> | 💧 DewPt: <span style="color:#818cf8;font-weight:700;">${dpStr}</span> (Window Limit: <span style="color:#f59e0b;font-weight:700;">${safeStr}</span>)</span>`;
            if (pt.is_on != null) {
                html += `<span class="badge ${pt.is_on ? 'badge-primary' : 'badge-secondary'}" style="font-size:0.65rem;">${pt.is_on ? '⚡ ON' : '⚪ OFF'}</span>`;
            }
            bar.innerHTML = html;
        }

        function renderRooms(state) {
            const grid = document.getElementById('rooms-grid');
            if (!state || !state.rooms) return;

            grid.innerHTML = '';
            for (const [room, devices] of Object.entries(state.rooms)) {
                const psycho = state.psychrometrics && state.psychrometrics[room];
                const card = document.createElement('div');
                card.className = 'card';

                const isOutdoor = room === 'outdoor';
                let headerHtml = `
                    <div class="card-header">
                        <span class="room-title">${isOutdoor ? '🌤️ Outdoor Weather' : '📍 ' + room}</span>
                        ${psycho && psycho.is_excluded ? `<span class="badge badge-danger">Excluded (${psycho.exclusion_label || 'Active'})</span>` : ''}
                    </div>
                `;

                let psychoHtml = '';
                if (psycho) {
                    psychoHtml = `
                        <div class="metrics-row">
                            <div class="metric-box">
                                <div class="metric-label">Indoor Air</div>
                                <div class="metric-value">${psycho.indoor_temp_c != null ? psycho.indoor_temp_c.toFixed(1) + '°C' : '--'}</div>
                                <div class="metric-sub">${psycho.indoor_rh_percent != null ? Math.round(psycho.indoor_rh_percent) + '% RH' : '--'}</div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-label">Dew Point</div>
                                <div class="metric-value" style="color: var(--accent);">${psycho.dew_point_c != null ? psycho.dew_point_c.toFixed(1) + '°C' : '--'}</div>
                                <div class="metric-sub">Window Limit: ${psycho.safe_dew_point_c != null ? psycho.safe_dew_point_c.toFixed(1) + '°C' : '--'}</div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-label">Condens. Limit</div>
                                <div class="metric-value" style="color: var(--warning);">${psycho.raw_safe_rh_percent != null ? psycho.raw_safe_rh_percent.toFixed(1) + '%' : '--'}</div>
                                <div class="metric-sub">${psycho.safe_target_rh ? 'Target: ' + psycho.safe_target_rh + '%' : '--'}</div>
                            </div>
                        </div>
                    `;
                }

                let devicesHtml = '<div style="display: flex; flex-direction: column; gap: 0.75rem;">';
                for (const dev of devices) {
                    devicesHtml += renderDeviceCard(dev, psycho);
                }
                devicesHtml += '</div>';

                const chartHtml = isOutdoor ? '' : renderRoomChart(room, roomHistory[room] || []);

                card.innerHTML = headerHtml + psychoHtml + chartHtml + devicesHtml;
                grid.appendChild(card);
            }
        }

        function renderRoomChart(room, points) {
            const safeId = room.replace(/[^a-zA-Z0-9_-]/g, '_');
            window.__roomPoints[safeId] = points || [];

            if (!points || points.length === 0) {
                return `
                    <div class="chart-box">
                        <div class="chart-header">
                            <span>📈 24h Climate & Condensation</span>
                        </div>
                        <div class="chart-hint" style="border-left-color: var(--primary);">
                            ℹ️ <strong>Gathering Telemetry:</strong> Periodic sensor snapshots are recorded every cycle. History trend lines will appear here shortly.
                        </div>
                    </div>
                `;
            }

            if (points.length === 1) {
                const pt = points[0];
                const tStr = pt.indoor_temp_c != null ? `${pt.indoor_temp_c.toFixed(1)}°C` : '--';
                const rhStr = pt.indoor_rh_percent != null ? `${Math.round(pt.indoor_rh_percent)}%` : '--';
                const dpStr = pt.dew_point_c != null ? `${pt.dew_point_c.toFixed(1)}°C` : '--';
                return `
                    <div class="chart-box">
                        <div class="chart-header">
                            <span>📈 24h Climate & Condensation (1 point)</span>
                        </div>
                        <div class="chart-hint">
                            💡 <strong>Initial snapshot captured.</strong> Trend lines will begin plotting after the next evaluation cycle.
                        </div>
                        <div class="chart-inspect-bar" id="chart-inspect-${safeId}">
                            <span><strong>Current:</strong> 🌡️ <span style="color:#f43f5e">${tStr}</span> | 💧 <span style="color:#38bdf8">${rhStr}</span> | 💧 DewPt: <span style="color:#818cf8">${dpStr}</span></span>
                        </div>
                    </div>
                `;
            }

            // Dimensions
            const W = 380, H = 176, PAD_LEFT = 32, PAD_RIGHT = 12;
            const PLOT_W = W - PAD_LEFT - PAD_RIGHT;

            // Track 1: Humidity (%) -> Y: 14 to 68
            const T1_TOP = 14, T1_HEIGHT = 54, T1_BOTTOM = 68;
            const rhVals = points.map(p => p.indoor_rh_percent).filter(v => v != null);
            let rhMinRaw = rhVals.length ? Math.min(...rhVals) : 40;
            let rhMaxRaw = rhVals.length ? Math.max(...rhVals) : 60;
            let rhMin = Math.max(20, Math.floor((rhMinRaw - 3) / 5) * 5);
            let rhMax = Math.min(95, Math.ceil((rhMaxRaw + 3) / 5) * 5);
            if (rhMax - rhMin < 15) { rhMax = rhMin + 15; }
            const rhMid = Math.round((rhMin + rhMax) / 2);

            const xFor = i => PAD_LEFT + (i / (points.length - 1)) * PLOT_W;
            const yRh = v => T1_BOTTOM - ((Math.min(rhMax, Math.max(rhMin, v)) - rhMin) / (rhMax - rhMin)) * T1_HEIGHT;

            // Track 2: Temperatures (°C) -> Y: 84 to 154
            const T2_TOP = 84, T2_HEIGHT = 70, T2_BOTTOM = 154;
            const tVals = [];
            points.forEach(p => {
                if (p.indoor_temp_c != null) tVals.push(p.indoor_temp_c);
                if (p.dew_point_c != null) tVals.push(p.dew_point_c);
                if (p.safe_dew_point_c != null) tVals.push(p.safe_dew_point_c);
            });
            let tMinRaw = tVals.length ? Math.min(...tVals) : 10;
            let tMaxRaw = tVals.length ? Math.max(...tVals) : 25;
            let tMin = Math.floor(tMinRaw - 1);
            let tMax = Math.ceil(tMaxRaw + 1);
            if (tMax - tMin < 4) { tMax = tMin + 4; }
            const tMid = Math.round((tMin + tMax) / 2);

            const yTemp = v => T2_BOTTOM - ((Math.min(tMax, Math.max(tMin, v)) - tMin) / (tMax - tMin)) * T2_HEIGHT;

            // Polylines
            const poly = (getter, yFn) => points
                .map((p, i) => {
                    const v = getter(p);
                    return v != null ? `${xFor(i).toFixed(1)},${yFn(v).toFixed(1)}` : null;
                })
                .filter(Boolean)
                .join(' ');

            const rhLine = poly(p => p.indoor_rh_percent, yRh);
            const tempLine = poly(p => p.indoor_temp_c, yTemp);
            const dpLine = poly(p => p.dew_point_c, yTemp);
            const safeDpLine = poly(p => p.safe_dew_point_c, yTemp);

            // Shaded area under RH
            let rhArea = '';
            if (rhLine) {
                rhArea = `<polygon points="${PAD_LEFT},${T1_BOTTOM} ${rhLine} ${W - PAD_RIGHT},${T1_BOTTOM}" fill="url(#rhGrad-${safeId})" />`;
            }

            // Power ON bars
            let onBars = '';
            let hasPowerData = false;
            const barW = Math.max(1.5, PLOT_W / points.length);
            points.forEach((p, i) => {
                if (p.is_on) {
                    hasPowerData = true;
                    onBars += `<rect x="${xFor(i).toFixed(1)}" y="${T1_TOP}" width="${barW.toFixed(1)}" height="${T1_HEIGHT}" fill="rgba(56, 189, 248, 0.18)" />`;
                }
            });

            // Target RH line
            let targetRhLine = '';
            const lastTarget = points.findLast ? points.findLast(p => p.target_rh != null)?.target_rh : (points.slice().reverse().find(p => p.target_rh != null)?.target_rh);
            if (lastTarget != null && lastTarget >= rhMin && lastTarget <= rhMax) {
                const targetY = yRh(lastTarget).toFixed(1);
                targetRhLine = `<line x1="${PAD_LEFT}" y1="${targetY}" x2="${W - PAD_RIGHT}" y2="${targetY}" stroke="#f59e0b" stroke-width="1.2" stroke-dasharray="3,3" opacity="0.8" />`;
            }

            const latest = points[points.length - 1];
            const latestD = new Date(latest.timestamp * 1000);
            const latestTime = latestD.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const latestT = latest.indoor_temp_c != null ? `${latest.indoor_temp_c.toFixed(1)}°C` : '--';
            const latestRh = latest.indoor_rh_percent != null ? `${Math.round(latest.indoor_rh_percent)}%` : '--';
            const latestDp = latest.dew_point_c != null ? `${latest.dew_point_c.toFixed(1)}°C` : '--';
            const latestSafe = latest.safe_dew_point_c != null ? `${latest.safe_dew_point_c.toFixed(1)}°C` : '--';

            return `
                <div class="chart-box">
                    <div class="chart-header">
                        <span>📈 24h Climate & Condensation (${points.length} pts)</span>
                        <div class="chart-legend">
                            <span class="chart-legend-item"><span style="color: #38bdf8;">━</span> RH%</span>
                            <span class="chart-legend-item"><span style="color: #f43f5e;">━</span> Room Temp</span>
                            <span class="chart-legend-item"><span style="color: #818cf8;">━</span> Dew Point</span>
                            <span class="chart-legend-item"><span style="color: #f59e0b;">┅</span> Window Limit</span>
                            ${hasPowerData ? `<span class="chart-legend-item"><span style="color: rgba(56, 189, 248, 0.9);">█</span> ON</span>` : ''}
                        </div>
                    </div>

                    <div class="chart-hint">
                        💡 <strong>Condensation Guide:</strong> Dew Point is when water condenses. Keeping <strong>Dew Point (indigo)</strong> below the <strong>Window Limit (amber)</strong> prevents condensation and mold on window glass.
                    </div>

                    <div class="chart-inspect-bar" id="chart-inspect-${safeId}">
                        <span><strong>Latest (${latestTime}):</strong> 🌡️ <span style="color:#f43f5e;font-weight:700;">${latestT}</span> | 💧 <span style="color:#38bdf8;font-weight:700;">${latestRh} RH</span> | 💧 DewPt: <span style="color:#818cf8;font-weight:700;">${latestDp}</span> (Window Limit: <span style="color:#f59e0b;font-weight:700;">${latestSafe}</span>)</span>
                        ${latest.is_on != null ? `<span class="badge ${latest.is_on ? 'badge-primary' : 'badge-secondary'}" style="font-size:0.65rem;">${latest.is_on ? '⚡ ON' : '⚪ OFF'}</span>` : ''}
                    </div>

                    <svg id="chart-svg-${safeId}" viewBox="0 0 ${W} ${H}" width="100%" height="176" style="display: block; cursor: crosshair; user-select: none;" onmousemove="onChartHover(event, '${safeId}')" onmouseleave="onChartLeave('${safeId}')" ontouchmove="onChartTouch(event, '${safeId}')" ontouchend="onChartLeave('${safeId}')">
                        <defs>
                            <linearGradient id="rhGrad-${safeId}" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.25"/>
                                <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.0"/>
                            </linearGradient>
                        </defs>

                        <!-- Track 1 Background & Grid (Humidity %) -->
                        <text x="${PAD_LEFT}" y="10" fill="#94a3b8" font-size="8.5" font-weight="700">HUMIDITY (%)</text>
                        <line x1="${PAD_LEFT}" y1="${T1_TOP}" x2="${W - PAD_RIGHT}" y2="${T1_TOP}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="2,2" />
                        <text x="${PAD_LEFT - 4}" y="${T1_TOP + 3}" fill="#64748b" font-size="8" text-anchor="end">${rhMax}%</text>

                        <line x1="${PAD_LEFT}" y1="${T1_TOP + T1_HEIGHT / 2}" x2="${W - PAD_RIGHT}" y2="${T1_TOP + T1_HEIGHT / 2}" stroke="rgba(255,255,255,0.04)" stroke-dasharray="2,2" />
                        <text x="${PAD_LEFT - 4}" y="${T1_TOP + T1_HEIGHT / 2 + 3}" fill="#64748b" font-size="8" text-anchor="end">${rhMid}%</text>

                        <line x1="${PAD_LEFT}" y1="${T1_BOTTOM}" x2="${W - PAD_RIGHT}" y2="${T1_BOTTOM}" stroke="rgba(255,255,255,0.08)" />
                        <text x="${PAD_LEFT - 4}" y="${T1_BOTTOM + 3}" fill="#64748b" font-size="8" text-anchor="end">${rhMin}%</text>

                        ${onBars}
                        ${rhArea}
                        ${targetRhLine}
                        ${rhLine ? `<polyline fill="none" stroke="#38bdf8" stroke-width="2" points="${rhLine}" />` : ''}

                        <!-- Track 2 Background & Grid (Temperature & Dew Point °C) -->
                        <text x="${PAD_LEFT}" y="80" fill="#94a3b8" font-size="8.5" font-weight="700">TEMPERATURE & DEW POINT (°C)</text>
                        <line x1="${PAD_LEFT}" y1="${T2_TOP}" x2="${W - PAD_RIGHT}" y2="${T2_TOP}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="2,2" />
                        <text x="${PAD_LEFT - 4}" y="${T2_TOP + 3}" fill="#64748b" font-size="8" text-anchor="end">${tMax}°C</text>

                        <line x1="${PAD_LEFT}" y1="${T2_TOP + T2_HEIGHT / 2}" x2="${W - PAD_RIGHT}" y2="${T2_TOP + T2_HEIGHT / 2}" stroke="rgba(255,255,255,0.04)" stroke-dasharray="2,2" />
                        <text x="${PAD_LEFT - 4}" y="${T2_TOP + T2_HEIGHT / 2 + 3}" fill="#64748b" font-size="8" text-anchor="end">${tMid}°C</text>

                        <line x1="${PAD_LEFT}" y1="${T2_BOTTOM}" x2="${W - PAD_RIGHT}" y2="${T2_BOTTOM}" stroke="rgba(255,255,255,0.08)" />
                        <text x="${PAD_LEFT - 4}" y="${T2_BOTTOM + 3}" fill="#64748b" font-size="8" text-anchor="end">${tMin}°C</text>

                        ${safeDpLine ? `<polyline fill="none" stroke="#f59e0b" stroke-width="1.6" stroke-dasharray="3,3" points="${safeDpLine}" />` : ''}
                        ${dpLine ? `<polyline fill="none" stroke="#818cf8" stroke-width="2" points="${dpLine}" />` : ''}
                        ${tempLine ? `<polyline fill="none" stroke="#f43f5e" stroke-width="1.8" points="${tempLine}" />` : ''}

                        <!-- Time Axis -->
                        <text x="${PAD_LEFT}" y="168" fill="#64748b" font-size="7.5" text-anchor="start">-24h</text>
                        <text x="${PAD_LEFT + PLOT_W * 0.25}" y="168" fill="#64748b" font-size="7.5" text-anchor="middle">-18h</text>
                        <text x="${PAD_LEFT + PLOT_W * 0.5}" y="168" fill="#64748b" font-size="7.5" text-anchor="middle">-12h</text>
                        <text x="${PAD_LEFT + PLOT_W * 0.75}" y="168" fill="#64748b" font-size="7.5" text-anchor="middle">-6h</text>
                        <text x="${W - PAD_RIGHT}" y="168" fill="#64748b" font-size="7.5" text-anchor="end">Now</text>

                        <!-- Interactive Cursor -->
                        <line id="cursor-line-${safeId}" x1="0" y1="${T1_TOP}" x2="0" y2="${T2_BOTTOM}" stroke="rgba(255,255,255,0.45)" stroke-width="1" stroke-dasharray="2,2" visibility="hidden" />
                    </svg>
                </div>
            `;
        }

        function renderDeviceCard(dev, psycho) {
            const isDehum = dev.category === 'dehumidifier';
            const isOnline = dev.is_online;

            let html = `
                <div style="background: rgba(15,23,42,0.4); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.85rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <strong>${dev.name}</strong>
                        <span class="badge ${isOnline ? 'badge-success' : 'badge-danger'}">${isOnline ? 'Online' : 'Offline'}</span>
                    </div>
            `;

            // Telemetry badges
            html += '<div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.5rem; font-size: 0.8rem;">';
            if (dev.temperature_celsius != null) html += `<span>🌡️ ${dev.temperature_celsius.toFixed(1)}°C</span>`;
            if (dev.humidity_percent != null) html += `<span>💧 ${Math.round(dev.humidity_percent)}%</span>`;
            if (dev.battery_percent != null) html += `<span>🔋 ${dev.battery_percent}%</span>`;
            if (dev.forecast_12h_min != null) html += `<span style="color: var(--primary);">❄️ 12h Min: ${dev.forecast_12h_min.toFixed(1)}°C</span>`;
            if (dev.is_tank_full) html += `<span class="badge badge-danger">⚠️ TANK FULL</span>`;
            if (dev.status_flags && dev.status_flags.length) html += `<span style="color: var(--text-muted); font-size: 0.7rem;">Flags: ${dev.status_flags.join(', ')}</span>`;
            html += '</div>';

            // Controls for dehumidifiers
            if (isDehum) {
                const isOn = dev.is_on;
                const isHeld = dev.is_overridden;
                const holdMins = dev.override_remaining_seconds ? Math.max(1, Math.ceil(dev.override_remaining_seconds / 60)) : 0;
                html += `
                    <div class="control-group">
                        <div class="control-row">
                            <span style="font-size: 0.85rem; font-weight: 600;">Power</span>
                            <div style="display: flex; align-items: center; gap: 0.4rem;">
                                ${isHeld ? `<span class="badge badge-warning">🔒 Hold ${holdMins}m</span>` : ''}
                                <button class="btn-sm ${isOn ? 'btn-primary' : 'btn-secondary'}" onclick="sendCommand('${dev.id}', '${isOn ? 'turn_off' : 'turn_on'}')">
                                    ${isOn ? '⚡ ON' : '⚪ OFF'}
                                </button>
                            </div>
                        </div>
                        <div class="control-row">
                            <span style="font-size: 0.85rem; font-weight: 600;">Target RH</span>
                            <div class="range-slider">
                                <input type="range" min="${dev.humidity_range ? dev.humidity_range[0] : 35}" max="${dev.humidity_range ? dev.humidity_range[1] : 70}" step="${dev.humidity_step || 5}" value="${dev.target_humidity_percent || 55}" onchange="sendCommand('${dev.id}', 'set_target', {humidity: this.value})">
                                <span style="font-weight: 700; width: 40px; text-align: right;">${dev.target_humidity_percent || 55}%</span>
                            </div>
                        </div>
                        <div class="control-row">
                            <span style="font-size: 0.85rem; font-weight: 600;">Mode</span>
                            <div class="mode-buttons">
                                ${(dev.supported_modes || ['manual', 'sleep', 'laundry', 'purify']).map(m => `
                                    <button class="mode-btn ${dev.current_mode === m ? 'active' : ''}" onclick="sendCommand('${dev.id}', 'set_mode', {mode: '${m}'})">${m}</button>
                                `).join('')}
                            </div>
                        </div>
                        <div class="control-row">
                            <span style="font-size: 0.8rem; color: var(--text-muted);">Manual Hold</span>
                            <div class="mode-buttons">
                                <button class="mode-btn" onclick="sendCommand('${dev.id}', 'set_override', {minutes: 60})">1h</button>
                                <button class="mode-btn" onclick="sendCommand('${dev.id}', 'set_override', {minutes: 120})">2h</button>
                                <button class="mode-btn" onclick="sendCommand('${dev.id}', 'set_override', {minutes: 240})">4h</button>
                                ${isHeld ? `<button class="mode-btn active" onclick="sendCommand('${dev.id}', 'clear_override')">Resume Auto</button>` : ''}
                            </div>
                        </div>
                    </div>
                `;
            }

            html += '</div>';
            return html;
        }

        function renderLogs(state) {
            const consoleEl = document.getElementById('log-console');
            if (!state.last_evaluation_logs || !state.last_evaluation_logs.length) {
                consoleEl.innerHTML = '<div class="log-line">No evaluation events logged yet.</div>';
                return;
            }
            consoleEl.innerHTML = state.last_evaluation_logs.map(l => `<div class="log-line">${l}</div>`).join('');
            if (state.last_evaluation_time) {
                const d = new Date(state.last_evaluation_time * 1000);
                document.getElementById('last-eval-time').innerText = 'Last evaluated: ' + d.toLocaleTimeString();
            }
        }

        function populateConfigForm(cfg) {
            if (!cfg) return;
            const c = cfg.condensation || {};
            document.getElementById('cfg-auto-power').checked = c.auto_power !== false;
            document.getElementById('cfg-min-rh').value = c.min_target_rh || 40;
            document.getElementById('cfg-max-rh').value = c.max_target_rh || 60;
            document.getElementById('cfg-on-offset').value = c.turn_on_offset_rh || 2.0;
            document.getElementById('cfg-off-offset').value = c.turn_off_offset_rh || 2.0;
            document.getElementById('cfg-min-cycle').value = c.min_cycle_seconds || 600;
            document.getElementById('cfg-lookahead').value = c.lookahead_hours != null ? c.lookahead_hours : 12;
            document.getElementById('cfg-glazing').value = c.glazing || 'double';
            document.getElementById('cfg-override-mins').value = c.manual_override_minutes != null ? c.manual_override_minutes : 120;

            const a = cfg.alerts || {};
            document.getElementById('cfg-low-batt').value = a.low_battery_threshold_percent != null ? a.low_battery_threshold_percent : 20;
            document.getElementById('cfg-webhook-url').value = a.webhook_url || '';

            const s = cfg.quiet_schedule || {};
            document.getElementById('cfg-sched-enabled').checked = s.enabled !== false;
            document.getElementById('cfg-start-time').value = s.start_time || '23:00';
            document.getElementById('cfg-end-time').value = s.end_time || '07:00';
            document.getElementById('cfg-night-mode').value = s.night_mode || 'sleep';
            document.getElementById('cfg-day-mode').value = s.day_mode || 'manual';

            // All-day sleep days
            const sleepDaysContainer = document.getElementById('all-day-sleep-days');
            const activeSleepDays = (s.all_day_sleep_days || []).map(d => d.toLowerCase());
            sleepDaysContainer.innerHTML = WEEKDAYS.map(day => `
                <label class="day-check">
                    <input type="checkbox" name="all-day-sleep" value="${day}" ${activeSleepDays.includes(day) ? 'checked' : ''}>
                    ${day.toUpperCase()}
                </label>
            `).join('');

            // Exclusion windows
            renderExclusionsTable(s.exclusion_windows || []);
        }

        function renderExclusionsTable(windows) {
            const tbody = document.getElementById('exclusions-body');
            tbody.innerHTML = '';
            windows.forEach((win, idx) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="checkbox" class="ex-enabled" ${win.enabled ? 'checked' : ''}></td>
                    <td><input type="text" class="ex-label" value="${win.label || ''}" style="width: 120px;"></td>
                    <td>
                        <input type="text" class="ex-start" value="${win.start_time || '00:00'}" style="width: 65px;"> - 
                        <input type="text" class="ex-end" value="${win.end_time || '07:00'}" style="width: 65px;">
                    </td>
                    <td>
                        <div class="days-selector">
                            ${WEEKDAYS.map(day => `
                                <label style="font-size: 0.7rem;">
                                    <input type="checkbox" class="ex-day-${day}" ${(win.days || []).includes(day) ? 'checked' : ''}>${day[0].toUpperCase()}
                                </label>
                            `).join('')}
                        </div>
                    </td>
                    <td><input type="text" class="ex-rooms" value="${win.rooms ? win.rooms.join(', ') : ''}" placeholder="All rooms" style="width: 100px;"></td>
                    <td><button type="button" class="btn-danger btn-sm" onclick="this.closest('tr').remove()">Remove</button></td>
                `;
                tbody.appendChild(tr);
            });
        }

        function addExclusionRow() {
            const tbody = document.getElementById('exclusions-body');
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><input type="checkbox" class="ex-enabled" checked></td>
                <td><input type="text" class="ex-label" value="Night Silence" style="width: 120px;"></td>
                <td>
                    <input type="text" class="ex-start" value="00:00" style="width: 65px;"> - 
                    <input type="text" class="ex-end" value="07:00" style="width: 65px;">
                </td>
                <td>
                    <div class="days-selector">
                        ${WEEKDAYS.map(day => `
                            <label style="font-size: 0.7rem;">
                                <input type="checkbox" class="ex-day-${day}" checked>${day[0].toUpperCase()}
                            </label>
                        `).join('')}
                    </div>
                </td>
                <td><input type="text" class="ex-rooms" value="bedroom" placeholder="All rooms" style="width: 100px;"></td>
                <td><button type="button" class="btn-danger btn-sm" onclick="this.closest('tr').remove()">Remove</button></td>
            `;
            tbody.appendChild(tr);
        }

        async function saveConfig(e) {
            e.preventDefault();

            const allDaySleepChecks = document.querySelectorAll('input[name="all-day-sleep"]:checked');
            const allDaySleepDays = Array.from(allDaySleepChecks).map(c => c.value);

            const exclusionRows = document.querySelectorAll('#exclusions-body tr');
            const exclusions = [];
            exclusionRows.forEach(tr => {
                const days = [];
                WEEKDAYS.forEach(day => {
                    if (tr.querySelector(`.ex-day-${day}`).checked) days.push(day);
                });
                const roomsRaw = tr.querySelector('.ex-rooms').value.trim();
                exclusions.push({
                    enabled: tr.querySelector('.ex-enabled').checked,
                    label: tr.querySelector('.ex-label').value.trim() || 'Exclusion',
                    start_time: tr.querySelector('.ex-start').value.trim(),
                    end_time: tr.querySelector('.ex-end').value.trim(),
                    days: days,
                    rooms: roomsRaw ? roomsRaw.split(',').map(r => r.trim()).filter(Boolean) : null
                });
            });

            const payload = {
                condensation: {
                    auto_power: document.getElementById('cfg-auto-power').checked,
                    min_target_rh: parseInt(document.getElementById('cfg-min-rh').value, 10),
                    max_target_rh: parseInt(document.getElementById('cfg-max-rh').value, 10),
                    turn_on_offset_rh: parseFloat(document.getElementById('cfg-on-offset').value),
                    turn_off_offset_rh: parseFloat(document.getElementById('cfg-off-offset').value),
                    min_cycle_seconds: parseInt(document.getElementById('cfg-min-cycle').value, 10),
                    lookahead_hours: parseInt(document.getElementById('cfg-lookahead').value, 10),
                    glazing: document.getElementById('cfg-glazing').value,
                    manual_override_minutes: parseInt(document.getElementById('cfg-override-mins').value, 10)
                },
                alerts: {
                    enabled: true,
                    low_battery_threshold_percent: parseInt(document.getElementById('cfg-low-batt').value, 10),
                    webhook_url: document.getElementById('cfg-webhook-url').value.trim() || null
                },
                quiet_schedule: {
                    enabled: document.getElementById('cfg-sched-enabled').checked,
                    start_time: document.getElementById('cfg-start-time').value,
                    end_time: document.getElementById('cfg-end-time').value,
                    night_mode: document.getElementById('cfg-night-mode').value,
                    day_mode: document.getElementById('cfg-day-mode').value,
                    all_day_sleep_days: allDaySleepDays,
                    exclusion_windows: exclusions
                }
            };

            try {
                const res = await fetch('/api/config', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    alert("Configuration saved and applied successfully!");
                    fetchState();
                    fetchConfig();
                } else {
                    const err = await res.json();
                    alert("Failed to save config: " + (err.error || res.statusText));
                }
            } catch (err) {
                alert("Error connecting to server: " + err);
            }
        }

        async function sendCommand(deviceId, action, params = {}) {
            try {
                const res = await fetch(`/api/devices/${deviceId}/command`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action, ...params })
                });
                const data = await res.json();
                if (!res.ok) alert("Command failed: " + data.message);
                fetchState();
            } catch (err) {
                console.error("Command error:", err);
            }
        }

        async function triggerEvaluate() {
            try {
                await fetch('/api/evaluate', { method: 'POST' });
                fetchState();
            } catch (err) {
                console.error("Evaluation error:", err);
            }
        }

        // Auto poll state every 10 seconds
        fetchState();
        fetchConfig();
        setInterval(fetchState, 10000);
    </script>
</body>
</html>
"""
