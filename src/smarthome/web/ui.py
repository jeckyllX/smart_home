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
            background: rgba(15, 23, 42, 0.55);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 8px;
            padding: 0.75rem;
        }
        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-bottom: 0.4rem;
        }
        .chart-legend {
            display: flex;
            gap: 0.75rem;
            font-size: 0.7rem;
            flex-wrap: wrap;
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

        function renderRooms(state) {
            const grid = document.getElementById('rooms-grid');
            if (!state || !state.rooms) return;

            grid.innerHTML = '';
            for (const [room, devices] of Object.entries(state.rooms)) {
                const psycho = state.psychrometrics && state.psychrometrics[room];
                const card = document.createElement('div');
                card.className = 'card';

                let headerHtml = `
                    <div class="card-header">
                        <span class="room-title">📍 ${room}</span>
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
                                <div class="metric-sub">Safe: ${psycho.safe_dew_point_c != null ? psycho.safe_dew_point_c.toFixed(1) + '°C' : '--'}</div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-label">Condens. Limit</div>
                                <div class="metric-value" style="color: var(--warning);">${psycho.raw_safe_rh_percent != null ? psycho.raw_safe_rh_percent.toFixed(1) + '%' : '--'}</div>
                                <div class="metric-sub">Target: ${psycho.safe_target_rh || '--'}%</div>
                            </div>
                        </div>
                    `;
                }

                let devicesHtml = '<div style="display: flex; flex-direction: column; gap: 0.75rem;">';
                for (const dev of devices) {
                    devicesHtml += renderDeviceCard(dev, psycho);
                }
                devicesHtml += '</div>';

                const chartHtml = renderRoomChart(room, roomHistory[room] || []);

                card.innerHTML = headerHtml + psychoHtml + chartHtml + devicesHtml;
                grid.appendChild(card);
            }
        }

        function renderRoomChart(room, points) {
            if (!points || points.length < 2) {
                return '';
            }
            const W = 340, H = 95, PAD = 10;
            const tMin = Math.min(...points.map(p => Math.min(p.indoor_temp_c ?? 20, p.dew_point_c ?? 10, p.safe_dew_point_c ?? 10))) - 1;
            const tMax = Math.max(...points.map(p => Math.max(p.indoor_temp_c ?? 20, p.dew_point_c ?? 10, p.safe_dew_point_c ?? 10))) + 1;
            const tSpan = Math.max(2, tMax - tMin);

            const xFor = i => PAD + (i / (points.length - 1)) * (W - 2 * PAD);
            const yTemp = v => H - PAD - ((v - tMin) / tSpan) * (H - 2 * PAD);
            const yRh = v => H - PAD - ((Math.max(20, Math.min(90, v)) - 20) / 70) * (H - 2 * PAD);

            const poly = (getter, yFn) => points
                .map((p, i) => getter(p) != null ? `${xFor(i).toFixed(1)},${yFn(getter(p)).toFixed(1)}` : null)
                .filter(Boolean)
                .join(' ');

            const rhLine = poly(p => p.indoor_rh_percent, yRh);
            const dpLine = poly(p => p.dew_point_c, yTemp);
            const safeDpLine = poly(p => p.safe_dew_point_c, yTemp);

            let onBars = '';
            const barW = Math.max(2, (W - 2 * PAD) / points.length);
            points.forEach((p, i) => {
                if (p.is_on) {
                    onBars += `<rect x="${xFor(i).toFixed(1)}" y="${PAD}" width="${barW.toFixed(1)}" height="${H - 2 * PAD}" fill="rgba(56, 189, 248, 0.14)" />`;
                }
            });

            return `
                <div class="chart-box">
                    <div class="chart-header">
                        <span>📈 24h Climate & Runtime (${points.length} pts)</span>
                        <div class="chart-legend">
                            <span style="color: #38bdf8;">━ RH%</span>
                            <span style="color: #818cf8;">━ DewPt</span>
                            <span style="color: #f59e0b;">┅ SafeDP</span>
                            <span style="color: rgba(56, 189, 248, 0.7);">█ ON</span>
                        </div>
                    </div>
                    <svg viewBox="0 0 ${W} ${H}" width="100%" height="95" style="display: block;">
                        ${onBars}
                        ${safeDpLine ? `<polyline fill="none" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="3,3" points="${safeDpLine}" />` : ''}
                        ${dpLine ? `<polyline fill="none" stroke="#818cf8" stroke-width="1.75" points="${dpLine}" />` : ''}
                        ${rhLine ? `<polyline fill="none" stroke="#38bdf8" stroke-width="2" points="${rhLine}" />` : ''}
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
