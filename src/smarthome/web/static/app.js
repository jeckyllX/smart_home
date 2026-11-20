const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const DAY_LABELS = {
    mon: "Mo",
    tue: "Tu",
    wed: "We",
    thu: "Th",
    fri: "Fr",
    sat: "Sa",
    sun: "Su",
};
const TIMEFRAME_LABELS = {
    6: "6h",
    24: "24h",
    72: "72h",
    168: "7d",
};

let currentConfig = null;
let currentState = null;
let roomHistory = {};
let selectedHistoryHours = 24;
let isHoveringChart = false;
let isDraggingControl = false;

window.__roomCharts = window.__roomCharts || {};

function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function formatRoomName(room) {
    if (!room) return "";
    return String(room)
        .split("_")
        .filter(Boolean)
        .map(w => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");
}

function formatDuration(seconds) {
    const total = Math.max(0, Math.round(seconds));
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    if (mins === 0) return `${secs}s`;
    if (secs === 0) return `${mins}m`;
    return `${mins}m ${secs}s`;
}

function formatAxisTime(tsSeconds) {
    const d = new Date(tsSeconds * 1000);
    const timeStr = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    if (selectedHistoryHours > 24) {
        const dateStr = d.toLocaleDateString([], { month: "short", day: "numeric" });
        return `${dateStr} ${timeStr}`;
    }
    return timeStr;
}

function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container || !message) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    const dismiss = () => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
    };
    toast.addEventListener("click", dismiss);
    container.appendChild(toast);
    setTimeout(dismiss, 4500);
}

function updateConnectionBadge(connected, lastEvalTs, pollIntervalSec) {
    const badge = document.getElementById("live-badge");
    const textEl = document.getElementById("live-text");
    if (!badge || !textEl) return;

    badge.classList.remove("stale", "disconnected");
    if (!connected) {
        badge.classList.add("disconnected");
        textEl.textContent = "Disconnected";
        return;
    }

    const interval = Number(pollIntervalSec) || 60;
    const staleAfterSec = Math.max(180, interval * 3);
    const nowSec = Date.now() / 1000;
    if (lastEvalTs != null && (nowSec - lastEvalTs) > staleAfterSec) {
        badge.classList.add("stale");
        textEl.textContent = "Stale";
        return;
    }

    textEl.textContent = "Live";
}

function toggleAccordion(forceState) {
    const el = document.getElementById("config-accordion");
    const header = document.getElementById("config-accordion-header");
    const arrow = document.getElementById("accordion-arrow");
    if (!el || !arrow) return;
    const isOpen = typeof forceState === "boolean"
        ? (el.classList.toggle("open", forceState), forceState)
        : el.classList.toggle("open");
    arrow.textContent = isOpen ? "▲" : "▼";
    if (header) header.setAttribute("aria-expanded", String(isOpen));
}

async function fetchState(opts = {}) {
    const background = Boolean(opts && opts.background);
    try {
        const [stateRes, histRes] = await Promise.all([
            fetch("/api/state"),
            fetch(`/api/history?hours=${selectedHistoryHours}`),
        ]);
        if (!stateRes.ok) {
            throw new Error(`HTTP ${stateRes.status}`);
        }
        currentState = await stateRes.json();
        if (histRes.ok) {
            const histData = await histRes.json();
            roomHistory = histData.rooms || {};
        }
        const pollSec = currentState.config && currentState.config.polling_interval_seconds;
        updateConnectionBadge(true, currentState.last_evaluation_time, pollSec);
        renderAlerts(currentState.alerts || []);
        renderOutdoorStrip(currentState);
        if (!(background && (isHoveringChart || isDraggingControl))) {
            renderRooms(currentState);
        }
        renderLogs(currentState);
    } catch (err) {
        console.error("Failed to fetch state:", err);
        updateConnectionBadge(false, null, 60);
        if (!background) {
            showToast("Failed to reach server for live state.", "error");
        }
    }
}

function renderAlerts(alerts) {
    const container = document.getElementById("alerts-banner");
    if (!alerts || !alerts.length) {
        container.style.display = "none";
        container.innerHTML = "";
        return;
    }
    container.style.display = "flex";
    container.innerHTML = alerts.map(a => `
        <div class="alert-banner ${a.severity === "critical" ? "alert-critical" : "alert-warning"}">
            <span>${a.severity === "critical" ? "🚨" : "⚠️"} ${escapeHtml(a.message)}</span>
            <span class="badge ${a.severity === "critical" ? "badge-danger" : "badge-warning"}">${escapeHtml(a.severity)}</span>
        </div>
    `).join("");
}

function renderOutdoorStrip(state) {
    const strip = document.getElementById("outdoor-strip");
    if (!strip) return;
    const outdoorDevs = state && state.rooms ? (state.rooms.outdoor || []) : [];
    if (!outdoorDevs.length) {
        strip.style.display = "none";
        strip.innerHTML = "";
        return;
    }

    const dev = outdoorDevs[0];
    const sourceFlag = (dev.status_flags && dev.status_flags.length) ? dev.status_flags[0] : "";
    const tempStr = dev.temperature_celsius != null ? `${dev.temperature_celsius.toFixed(1)}°C` : "--";
    const rhStr = dev.humidity_percent != null ? `${Math.round(dev.humidity_percent)}%` : "--";
    const minStr = dev.forecast_12h_min != null ? `${dev.forecast_12h_min.toFixed(1)}°C` : "--";
    const lookahead = dev.forecast_lookahead_hours ?? 12;

    strip.style.display = "flex";
    strip.innerHTML = `
        <div class="outdoor-title">
            <span>🌤️ ${escapeHtml(dev.name || "Outdoor Weather")}</span>
            <span class="badge ${dev.is_online ? "badge-success" : "badge-danger"}">${dev.is_online ? "Online" : "Offline"}</span>
            ${sourceFlag ? `<span class="badge badge-secondary">${escapeHtml(sourceFlag)}</span>` : ""}
        </div>
        <div class="outdoor-metrics">
            <div class="outdoor-metric"><span>Temp</span><strong>🌡️ ${tempStr}</strong></div>
            <div class="outdoor-metric"><span>RH</span><strong>💧 ${rhStr}</strong></div>
            <div class="outdoor-metric"><span>${lookahead}h Min</span><strong style="color: var(--primary);">❄️ ${minStr}</strong></div>
        </div>
    `;
}

async function fetchConfig() {
    try {
        const res = await fetch("/api/config");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        currentConfig = await res.json();
        populateConfigForm(currentConfig);
    } catch (err) {
        console.error("Failed to fetch config:", err);
        showToast("Failed to load settings.", "error");
    }
}

function onChartHover(e, safeId) {
    isHoveringChart = true;
    const meta = window.__roomCharts[safeId];
    if (!meta || !meta.points || meta.points.length < 2) return;
    const svg = document.getElementById("chart-svg-" + safeId);
    if (!svg) return;

    const rect = svg.getBoundingClientRect();
    if (!rect.width) return;
    const clientX = e.clientX ?? (e.touches && e.touches[0] ? e.touches[0].clientX : null);
    if (clientX == null) return;

    const W = 380, PAD_LEFT = 32, PAD_RIGHT = 12, PLOT_W = W - PAD_LEFT - PAD_RIGHT;
    const T1_BOTTOM = 68, T1_HEIGHT = 54, T2_BOTTOM = 154, T2_HEIGHT = 70;
    const relX = clientX - rect.left;
    const svgX = (relX / rect.width) * W;
    const clampedX = Math.max(PAD_LEFT, Math.min(W - PAD_RIGHT, svgX));
    const ratio = (clampedX - PAD_LEFT) / PLOT_W;
    const targetTs = meta.minTs + ratio * meta.spanTs;

    let idx = 0;
    let bestDiff = Infinity;
    for (let i = 0; i < meta.points.length; i++) {
        const diff = Math.abs(meta.points[i].timestamp - targetTs);
        if (diff < bestDiff) {
            bestDiff = diff;
            idx = i;
        }
    }

    const pt = meta.points[idx];
    const snapX = PAD_LEFT + ((pt.timestamp - meta.minTs) / meta.spanTs) * PLOT_W;
    const snapXStr = snapX.toFixed(1);

    const curLine = document.getElementById("cursor-line-" + safeId);
    if (curLine) {
        curLine.setAttribute("x1", snapXStr);
        curLine.setAttribute("x2", snapXStr);
        curLine.setAttribute("visibility", "visible");
    }

    const setDot = (dotId, val, minV, maxV, bottom, height) => {
        const dot = document.getElementById(dotId);
        if (!dot) return;
        if (val == null) {
            dot.setAttribute("visibility", "hidden");
            return;
        }
        const clamped = Math.min(maxV, Math.max(minV, val));
        const y = bottom - ((clamped - minV) / (maxV - minV)) * height;
        dot.setAttribute("cx", snapXStr);
        dot.setAttribute("cy", y.toFixed(1));
        dot.setAttribute("visibility", "visible");
    };

    setDot("cursor-dot-rh-" + safeId, pt.indoor_rh_percent, meta.rhMin, meta.rhMax, T1_BOTTOM, T1_HEIGHT);
    setDot("cursor-dot-temp-" + safeId, pt.indoor_temp_c, meta.tMin, meta.tMax, T2_BOTTOM, T2_HEIGHT);
    setDot("cursor-dot-dp-" + safeId, pt.dew_point_c, meta.tMin, meta.tMax, T2_BOTTOM, T2_HEIGHT);

    updateInspectBar(safeId, pt, false);
}

function onChartLeave(safeId) {
    isHoveringChart = false;
    const hideIds = [
        "cursor-line-" + safeId,
        "cursor-dot-rh-" + safeId,
        "cursor-dot-temp-" + safeId,
        "cursor-dot-dp-" + safeId,
    ];
    hideIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.setAttribute("visibility", "hidden");
    });

    const meta = window.__roomCharts[safeId];
    if (meta && meta.points && meta.points.length) {
        updateInspectBar(safeId, meta.points[meta.points.length - 1], true);
    }
}

function updateInspectBar(safeId, pt, isLatest) {
    const bar = document.getElementById("chart-inspect-" + safeId);
    if (!bar || !pt) return;
    const timeStr = formatAxisTime(pt.timestamp);
    const tag = isLatest ? `Latest (${timeStr})` : timeStr;

    const tStr = pt.indoor_temp_c != null ? `${pt.indoor_temp_c.toFixed(1)}°C` : "--";
    const rhStr = pt.indoor_rh_percent != null ? `${Math.round(pt.indoor_rh_percent)}%` : "--";
    const dpStr = pt.dew_point_c != null ? `${pt.dew_point_c.toFixed(1)}°C` : "--";
    const safeStr = pt.safe_dew_point_c != null ? `${pt.safe_dew_point_c.toFixed(1)}°C` : "--";

    let html = `<span><strong>${tag}:</strong> 🌡️ <span style="color:#f43f5e;font-weight:700;">${tStr}</span> | 💧 <span style="color:#38bdf8;font-weight:700;">${rhStr} RH</span> | 💧 DewPt: <span style="color:#818cf8;font-weight:700;">${dpStr}</span> (Limit: <span style="color:#f59e0b;font-weight:700;">${safeStr}</span>)</span>`;
    if (pt.is_defrost) {
        html += `<span class="badge badge-purple">❄️ Defrost</span>`;
    } else if (pt.is_on != null) {
        html += `<span class="badge ${pt.is_on ? "badge-primary" : "badge-secondary"}">${pt.is_on ? "⚡ ON" : "⚪ OFF"}</span>`;
    }
    bar.innerHTML = html;
}

function renderSafetyBadge(psycho) {
    if (!psycho || psycho.dew_point_c == null || psycho.safe_dew_point_c == null) {
        return "";
    }
    const margin = psycho.safe_dew_point_c - psycho.dew_point_c;
    if (margin < 0) {
        return `<span class="badge badge-danger">Condensation Risk (${margin.toFixed(1)}°C)</span>`;
    }
    if (margin < 1.0) {
        return `<span class="badge badge-warning">Tight Margin (+${margin.toFixed(1)}°C)</span>`;
    }
    return `<span class="badge badge-success">Safe (+${margin.toFixed(1)}°C)</span>`;
}

function renderRooms(state) {
    const grid = document.getElementById("rooms-grid");
    if (!grid || !state || !state.rooms) return;

    const indoorEntries = Object.entries(state.rooms)
        .filter(([room]) => room !== "outdoor")
        .sort(([roomA, devsA], [roomB, devsB]) => {
            const hasDehumA = devsA.some(d => d.category === "dehumidifier");
            const hasDehumB = devsB.some(d => d.category === "dehumidifier");
            if (hasDehumA !== hasDehumB) return hasDehumA ? -1 : 1;
            return roomA.localeCompare(roomB);
        });

    grid.innerHTML = "";
    if (!indoorEntries.length) {
        grid.innerHTML = `<div class="muted-placeholder">No indoor rooms configured.</div>`;
        return;
    }

    for (const [room, devices] of indoorEntries) {
        const psycho = state.psychrometrics && state.psychrometrics[room];
        const card = document.createElement("div");
        card.className = "card";

        const safetyBadge = renderSafetyBadge(psycho);
        const exclusionBadge = (psycho && psycho.is_excluded)
            ? `<span class="badge badge-danger">Excluded (${escapeHtml(psycho.exclusion_label || "Active")})</span>`
            : "";

        const headerHtml = `
            <div class="card-header">
                <span class="room-title">📍 ${escapeHtml(formatRoomName(room))}</span>
                <div class="header-badges">${safetyBadge}${exclusionBadge}</div>
            </div>
        `;

        let psychoHtml = "";
        if (psycho) {
            psychoHtml = `
                <div class="metrics-row">
                    <div class="metric-box">
                        <div class="metric-label">Indoor Air</div>
                        <div class="metric-value">${psycho.indoor_temp_c != null ? psycho.indoor_temp_c.toFixed(1) + "°C" : "--"}</div>
                        <div class="metric-sub">${psycho.indoor_rh_percent != null ? Math.round(psycho.indoor_rh_percent) + "% RH" : "--"}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Dew Point</div>
                        <div class="metric-value" style="color: var(--accent);">${psycho.dew_point_c != null ? psycho.dew_point_c.toFixed(1) + "°C" : "--"}</div>
                        <div class="metric-sub">Limit: ${psycho.safe_dew_point_c != null ? psycho.safe_dew_point_c.toFixed(1) + "°C" : "--"}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Safe RH Max</div>
                        <div class="metric-value" style="color: var(--warning);">${psycho.raw_safe_rh_percent != null ? psycho.raw_safe_rh_percent.toFixed(1) + "%" : "--"}</div>
                        <div class="metric-sub">${psycho.safe_target_rh ? "Target: " + psycho.safe_target_rh + "%" : "--"}</div>
                    </div>
                </div>
            `;
        }

        const hasDehum = devices.some(d => d.category === "dehumidifier");
        let autoPowerHtml = "";
        if (hasDehum && psycho && psycho.turn_on_threshold_rh != null && psycho.turn_off_threshold_rh != null) {
            const parts = [
                `<span>Auto: <strong>ON ≥ ${psycho.turn_on_threshold_rh.toFixed(1)}%</strong> · <strong>OFF ≤ ${psycho.turn_off_threshold_rh.toFixed(1)}%</strong></span>`,
            ];
            if (psycho.cooldown_remaining_seconds && psycho.cooldown_remaining_seconds > 1) {
                parts.push(`<span class="badge badge-warning">Cooldown ${formatDuration(psycho.cooldown_remaining_seconds)}</span>`);
            }
            autoPowerHtml = `<div class="auto-power-strip">${parts.join("")}</div>`;
        }

        let devicesHtml = `<div class="devices-list">`;
        for (const dev of devices) {
            devicesHtml += renderDeviceCard(dev);
        }
        devicesHtml += `</div>`;

        const chartHtml = renderRoomChart(room, roomHistory[room] || []);

        card.innerHTML = headerHtml + psychoHtml + autoPowerHtml + chartHtml + devicesHtml;
        grid.appendChild(card);
    }

    // Bind mouse/touch chart inspection handlers directly so mouseleave doesn't depend on bubbling
    grid.querySelectorAll("svg[data-chart-id]").forEach(svg => {
        const safeId = svg.dataset.chartId;
        svg.addEventListener("mousemove", e => onChartHover(e, safeId));
        svg.addEventListener("mouseleave", () => onChartLeave(safeId));
        svg.addEventListener("touchstart", e => {
            if (e.touches && e.touches.length) onChartHover(e.touches[0], safeId);
        }, { passive: true });
        svg.addEventListener("touchmove", e => {
            if (e.touches && e.touches.length) onChartHover(e.touches[0], safeId);
        }, { passive: true });
        svg.addEventListener("touchend", () => onChartLeave(safeId));
    });
}

function renderRoomChart(room, points) {
    const safeId = room.replace(/[^a-zA-Z0-9_-]/g, "_");
    const tfLabel = TIMEFRAME_LABELS[selectedHistoryHours] || `${selectedHistoryHours}h`;

    if (!points || points.length === 0) {
        window.__roomCharts[safeId] = { points: [] };
        return `
            <div class="chart-box">
                <div class="chart-header">
                    <span>📈 ${tfLabel} Climate &amp; Condensation</span>
                </div>
                <div class="chart-hint">
                    ℹ️ <strong>Gathering Telemetry:</strong> Periodic sensor snapshots are recorded every cycle. Trend lines will appear here shortly.
                </div>
            </div>
        `;
    }

    if (points.length === 1) {
        const pt = points[0];
        window.__roomCharts[safeId] = { points };
        const tStr = pt.indoor_temp_c != null ? `${pt.indoor_temp_c.toFixed(1)}°C` : "--";
        const rhStr = pt.indoor_rh_percent != null ? `${Math.round(pt.indoor_rh_percent)}%` : "--";
        const dpStr = pt.dew_point_c != null ? `${pt.dew_point_c.toFixed(1)}°C` : "--";
        return `
            <div class="chart-box">
                <div class="chart-header">
                    <span>📈 ${tfLabel} Climate &amp; Condensation (1 pt)</span>
                </div>
                <div class="chart-inspect-bar" id="chart-inspect-${safeId}">
                    <span><strong>Latest (${formatAxisTime(pt.timestamp)}):</strong> 🌡️ <span style="color:#f43f5e">${tStr}</span> | 💧 <span style="color:#38bdf8">${rhStr}</span> | 💧 DewPt: <span style="color:#818cf8">${dpStr}</span></span>
                </div>
            </div>
        `;
    }

    const W = 380, H = 176, PAD_LEFT = 32, PAD_RIGHT = 12;
    const PLOT_W = W - PAD_LEFT - PAD_RIGHT;

    // Track 1: Humidity (%) -> Y: 14 to 68
    const T1_TOP = 14, T1_HEIGHT = 54, T1_BOTTOM = 68;
    const rhVals = points.map(p => p.indoor_rh_percent).filter(v => v != null);
    const rhMinRaw = rhVals.length ? Math.min(...rhVals) : 40;
    const rhMaxRaw = rhVals.length ? Math.max(...rhVals) : 60;
    const rhMin = Math.max(20, Math.floor((rhMinRaw - 3) / 5) * 5);
    let rhMax = Math.min(95, Math.ceil((rhMaxRaw + 3) / 5) * 5);
    if (rhMax - rhMin < 15) rhMax = rhMin + 15;
    const rhMid = Math.round((rhMin + rhMax) / 2);

    const minTs = points[0].timestamp;
    const maxTs = points[points.length - 1].timestamp;
    const spanTs = Math.max(1, maxTs - minTs);
    const xFor = i => PAD_LEFT + ((points[i].timestamp - minTs) / spanTs) * PLOT_W;
    const yRh = v => T1_BOTTOM - ((Math.min(rhMax, Math.max(rhMin, v)) - rhMin) / (rhMax - rhMin)) * T1_HEIGHT;

    // Track 2: Temperatures (°C) -> Y: 84 to 154
    const T2_TOP = 84, T2_HEIGHT = 70, T2_BOTTOM = 154;
    const tVals = [];
    points.forEach(p => {
        if (p.indoor_temp_c != null) tVals.push(p.indoor_temp_c);
        if (p.dew_point_c != null) tVals.push(p.dew_point_c);
        if (p.safe_dew_point_c != null) tVals.push(p.safe_dew_point_c);
    });
    const tMinRaw = tVals.length ? Math.min(...tVals) : 10;
    const tMaxRaw = tVals.length ? Math.max(...tVals) : 25;
    const tMin = Math.floor(tMinRaw - 1);
    let tMax = Math.ceil(tMaxRaw + 1);
    if (tMax - tMin < 4) tMax = tMin + 4;
    const tMid = Math.round((tMin + tMax) / 2);
    const yTemp = v => T2_BOTTOM - ((Math.min(tMax, Math.max(tMin, v)) - tMin) / (tMax - tMin)) * T2_HEIGHT;

    window.__roomCharts[safeId] = { points, minTs, spanTs, rhMin, rhMax, tMin, tMax };

    const polyCoords = (getter, yFn) => points
        .map((p, i) => {
            const v = getter(p);
            return v != null ? [xFor(i), yFn(v)] : null;
        })
        .filter(Boolean);
    const fmtCoords = coords => coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");

    const rhCoords = polyCoords(p => p.indoor_rh_percent, yRh);
    const rhLine = fmtCoords(rhCoords);
    const tempLine = fmtCoords(polyCoords(p => p.indoor_temp_c, yTemp));
    const dpLine = fmtCoords(polyCoords(p => p.dew_point_c, yTemp));
    const safeDpLine = fmtCoords(polyCoords(p => p.safe_dew_point_c, yTemp));

    let rhArea = "";
    if (rhCoords.length > 0) {
        const firstRhX = rhCoords[0][0].toFixed(1);
        const lastRhX = rhCoords[rhCoords.length - 1][0].toFixed(1);
        rhArea = `<polygon points="${firstRhX},${T1_BOTTOM} ${rhLine} ${lastRhX},${T1_BOTTOM}" fill="url(#rhGrad-${safeId})" />`;
    }

    // Power ON & Defrost background bars
    let onBars = "";
    let hasPowerData = false;
    let hasDefrostData = false;
    const maxRight = W - PAD_RIGHT;
    points.forEach((p, i) => {
        if (!p.is_defrost && !p.is_on) return;
        let x0 = Math.max(PAD_LEFT, Math.min(maxRight, xFor(i)));
        let w;
        if (i < points.length - 1) {
            const x1 = Math.max(x0, Math.min(maxRight, xFor(i + 1)));
            w = Math.min(Math.max(1.5, x1 - x0), maxRight - x0);
        } else {
            w = 1.5;
            x0 = Math.max(PAD_LEFT, maxRight - w);
        }
        if (w <= 0) return;
        if (p.is_defrost) {
            hasPowerData = true;
            hasDefrostData = true;
            onBars += `<rect x="${x0.toFixed(1)}" y="${T1_TOP}" width="${w.toFixed(1)}" height="${T1_HEIGHT}" fill="rgba(168, 85, 247, 0.28)" />`;
        } else if (p.is_on) {
            hasPowerData = true;
            onBars += `<rect x="${x0.toFixed(1)}" y="${T1_TOP}" width="${w.toFixed(1)}" height="${T1_HEIGHT}" fill="rgba(56, 189, 248, 0.18)" />`;
        }
    });

    // Shaded condensation-risk spans where Dew Point > Window Limit on Track 2
    let riskAreas = "";
    let hasRiskData = false;
    let segStart = -1;
    const flushRiskSegment = (startIdx, endIdx) => {
        if (startIdx < 0 || endIdx < startIdx) return;
        hasRiskData = true;
        if (startIdx === endIdx) {
            const x = xFor(startIdx);
            const yTop = yTemp(points[startIdx].dew_point_c);
            const yBot = yTemp(points[startIdx].safe_dew_point_c);
            const h = Math.max(2, yBot - yTop);
            riskAreas += `<rect x="${Math.max(PAD_LEFT, x - 1.5).toFixed(1)}" y="${yTop.toFixed(1)}" width="3" height="${h.toFixed(1)}" fill="rgba(239, 68, 68, 0.24)" />`;
            return;
        }
        const topPts = [];
        const botPts = [];
        for (let k = startIdx; k <= endIdx; k++) {
            const x = xFor(k).toFixed(1);
            topPts.push(`${x},${yTemp(points[k].dew_point_c).toFixed(1)}`);
            botPts.push(`${x},${yTemp(points[k].safe_dew_point_c).toFixed(1)}`);
        }
        botPts.reverse();
        riskAreas += `<polygon points="${topPts.join(" ")} ${botPts.join(" ")}" fill="rgba(239, 68, 68, 0.24)" />`;
    };
    points.forEach((p, i) => {
        const isRisk = p.dew_point_c != null && p.safe_dew_point_c != null && p.dew_point_c > p.safe_dew_point_c;
        if (isRisk && segStart < 0) {
            segStart = i;
        } else if (!isRisk && segStart >= 0) {
            flushRiskSegment(segStart, i - 1);
            segStart = -1;
        }
    });
    if (segStart >= 0) {
        flushRiskSegment(segStart, points.length - 1);
    }

    // Target RH line in distinct emerald dashed stroke on Track 1
    let targetRhLine = "";
    let hasTargetRh = false;
    const lastTarget = points.findLast
        ? points.findLast(p => p.target_rh != null)?.target_rh
        : points.slice().reverse().find(p => p.target_rh != null)?.target_rh;
    if (lastTarget != null && lastTarget >= rhMin && lastTarget <= rhMax) {
        hasTargetRh = true;
        const targetY = yRh(lastTarget).toFixed(1);
        targetRhLine = `<line x1="${PAD_LEFT}" y1="${targetY}" x2="${W - PAD_RIGHT}" y2="${targetY}" stroke="#10b981" stroke-width="1.2" stroke-dasharray="3,3" opacity="0.85" />`;
    }

    const latest = points[points.length - 1];
    const latestTime = formatAxisTime(latest.timestamp);
    const latestT = latest.indoor_temp_c != null ? `${latest.indoor_temp_c.toFixed(1)}°C` : "--";
    const latestRh = latest.indoor_rh_percent != null ? `${Math.round(latest.indoor_rh_percent)}%` : "--";
    const latestDp = latest.dew_point_c != null ? `${latest.dew_point_c.toFixed(1)}°C` : "--";
    const latestSafe = latest.safe_dew_point_c != null ? `${latest.safe_dew_point_c.toFixed(1)}°C` : "--";

    return `
        <div class="chart-box">
            <div class="chart-header">
                <span>📈 ${tfLabel} Climate &amp; Condensation (${points.length} pts)</span>
                <div class="chart-legend">
                    <span class="chart-legend-item"><span style="color: #38bdf8;">━</span> RH%</span>
                    ${hasTargetRh ? `<span class="chart-legend-item"><span style="color: #10b981;">┅</span> Target RH</span>` : ""}
                    <span class="chart-legend-item"><span style="color: #f43f5e;">━</span> Temp</span>
                    <span class="chart-legend-item"><span style="color: #818cf8;">━</span> Dew Pt</span>
                    <span class="chart-legend-item"><span style="color: #f59e0b;">┅</span> Limit</span>
                    ${hasPowerData ? `<span class="chart-legend-item"><span style="color: rgba(56, 189, 248, 0.9);">█</span> ON</span>` : ""}
                    ${hasDefrostData ? `<span class="chart-legend-item"><span style="color: rgba(168, 85, 247, 0.95);">█</span> Defrost</span>` : ""}
                    ${hasRiskData ? `<span class="chart-legend-item"><span style="color: rgba(239, 68, 68, 0.85);">█</span> Risk</span>` : ""}
                </div>
            </div>

            <div class="chart-inspect-bar" id="chart-inspect-${safeId}">
                <span><strong>Latest (${latestTime}):</strong> 🌡️ <span style="color:#f43f5e;font-weight:700;">${latestT}</span> | 💧 <span style="color:#38bdf8;font-weight:700;">${latestRh} RH</span> | 💧 DewPt: <span style="color:#818cf8;font-weight:700;">${latestDp}</span> (Limit: <span style="color:#f59e0b;font-weight:700;">${latestSafe}</span>)</span>
                ${latest.is_defrost ? `<span class="badge badge-purple">❄️ Defrost</span>` : (latest.is_on != null ? `<span class="badge ${latest.is_on ? "badge-primary" : "badge-secondary"}">${latest.is_on ? "⚡ ON" : "⚪ OFF"}</span>` : "")}
            </div>

            <svg id="chart-svg-${safeId}" class="chart-svg" data-chart-id="${safeId}" viewBox="0 0 ${W} ${H}" width="100%" height="176">
                <defs>
                    <linearGradient id="rhGrad-${safeId}" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.25"/>
                        <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.0"/>
                    </linearGradient>
                </defs>

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
                ${rhLine ? `<polyline fill="none" stroke="#38bdf8" stroke-width="2" points="${rhLine}" />` : ""}

                <text x="${PAD_LEFT}" y="80" fill="#94a3b8" font-size="8.5" font-weight="700">TEMPERATURE &amp; DEW POINT (°C)</text>
                <line x1="${PAD_LEFT}" y1="${T2_TOP}" x2="${W - PAD_RIGHT}" y2="${T2_TOP}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="2,2" />
                <text x="${PAD_LEFT - 4}" y="${T2_TOP + 3}" fill="#64748b" font-size="8" text-anchor="end">${tMax}°C</text>

                <line x1="${PAD_LEFT}" y1="${T2_TOP + T2_HEIGHT / 2}" x2="${W - PAD_RIGHT}" y2="${T2_TOP + T2_HEIGHT / 2}" stroke="rgba(255,255,255,0.04)" stroke-dasharray="2,2" />
                <text x="${PAD_LEFT - 4}" y="${T2_TOP + T2_HEIGHT / 2 + 3}" fill="#64748b" font-size="8" text-anchor="end">${tMid}°C</text>

                <line x1="${PAD_LEFT}" y1="${T2_BOTTOM}" x2="${W - PAD_RIGHT}" y2="${T2_BOTTOM}" stroke="rgba(255,255,255,0.08)" />
                <text x="${PAD_LEFT - 4}" y="${T2_BOTTOM + 3}" fill="#64748b" font-size="8" text-anchor="end">${tMin}°C</text>

                ${riskAreas}
                ${safeDpLine ? `<polyline fill="none" stroke="#f59e0b" stroke-width="1.6" stroke-dasharray="3,3" points="${safeDpLine}" />` : ""}
                ${dpLine ? `<polyline fill="none" stroke="#818cf8" stroke-width="2" points="${dpLine}" />` : ""}
                ${tempLine ? `<polyline fill="none" stroke="#f43f5e" stroke-width="1.8" points="${tempLine}" />` : ""}

                <text x="${PAD_LEFT}" y="168" fill="#64748b" font-size="7.2" text-anchor="start">${formatAxisTime(minTs)}</text>
                <text x="${PAD_LEFT + PLOT_W * 0.5}" y="168" fill="#64748b" font-size="7.2" text-anchor="middle">${formatAxisTime(minTs + spanTs * 0.5)}</text>
                <text x="${W - PAD_RIGHT}" y="168" fill="#64748b" font-size="7.2" text-anchor="end">Now</text>

                <line id="cursor-line-${safeId}" x1="0" y1="${T1_TOP}" x2="0" y2="${T2_BOTTOM}" stroke="rgba(255,255,255,0.45)" stroke-width="1" stroke-dasharray="2,2" visibility="hidden" />
                <circle id="cursor-dot-rh-${safeId}" cx="0" cy="0" r="3" fill="#38bdf8" stroke="#0f172a" stroke-width="1" visibility="hidden" />
                <circle id="cursor-dot-temp-${safeId}" cx="0" cy="0" r="3" fill="#f43f5e" stroke="#0f172a" stroke-width="1" visibility="hidden" />
                <circle id="cursor-dot-dp-${safeId}" cx="0" cy="0" r="3" fill="#818cf8" stroke="#0f172a" stroke-width="1" visibility="hidden" />
            </svg>
        </div>
    `;
}

function renderDeviceCard(dev) {
    const isDehum = dev.category === "dehumidifier";
    const isOnline = dev.is_online;
    const safeDevId = escapeHtml(dev.id);
    const isSleep = dev.current_mode === "sleep";

    let html = `
        <div class="device-card">
            <div class="device-card-header">
                <strong>${escapeHtml(dev.name)}</strong>
                <span class="badge ${isOnline ? "badge-success" : "badge-danger"}">${isOnline ? "Online" : "Offline"}</span>
            </div>
    `;

    html += `<div class="device-telemetry">`;
    if (dev.temperature_celsius != null) html += `<span>🌡️ ${dev.temperature_celsius.toFixed(1)}°C</span>`;
    if (dev.humidity_percent != null) {
        if (isDehum) {
            html += `<span class="builtin-sensor-note">Built-in RH: ${Math.round(dev.humidity_percent)}%${isSleep ? " (frozen in sleep)" : ""}</span>`;
        } else {
            html += `<span>💧 ${Math.round(dev.humidity_percent)}%</span>`;
        }
    }
    if (dev.battery_percent != null) html += `<span>🔋 ${dev.battery_percent}%</span>`;
    if (dev.is_tank_full) html += `<span class="badge badge-danger">⚠️ TANK FULL</span>`;
    if (dev.status_flags && dev.status_flags.length) {
        const flagsText = dev.status_flags.join(", ");
        const isDefrost = dev.status_flags.includes("defrost");
        html += `<span class="badge ${isDefrost ? "badge-purple" : "badge-secondary"}">${escapeHtml(flagsText)}</span>`;
    }
    html += `</div>`;

    if (isDehum) {
        const isOn = dev.is_on;
        const isHeld = dev.is_overridden;
        const holdMins = dev.override_remaining_seconds ? Math.max(1, Math.ceil(dev.override_remaining_seconds / 60)) : 0;
        const targetRh = dev.target_humidity_percent ?? 55;
        const sliderDisabled = isSleep ? "disabled" : "";

        html += `
            <div class="control-group">
                <div class="control-row">
                    <span class="control-label">Power</span>
                    <div style="display: flex; align-items: center; gap: 0.4rem;">
                        ${isHeld ? `<span class="badge badge-warning">🔒 Hold ${holdMins}m</span>` : ""}
                        <button type="button" class="btn-sm ${isOn ? "btn-primary" : "btn-secondary"}" data-device-id="${safeDevId}" data-action="${isOn ? "turn_off" : "turn_on"}">
                            ${isOn ? "⚡ ON" : "⚪ OFF"}
                        </button>
                    </div>
                </div>
                <div class="control-row">
                    <span class="control-label">Target RH</span>
                    <div class="range-slider">
                        <input type="range" data-device-id="${safeDevId}" data-action="set_target" min="${dev.humidity_range ? dev.humidity_range[0] : 35}" max="${dev.humidity_range ? dev.humidity_range[1] : 70}" step="${dev.humidity_step ?? 5}" value="${targetRh}" ${sliderDisabled}>
                        <span class="slider-value">${targetRh}%</span>
                        ${isSleep ? `<span class="badge badge-secondary">Locked in sleep</span>` : ""}
                    </div>
                </div>
                <div class="control-row">
                    <span class="control-label">Mode</span>
                    <div class="mode-buttons">
                        ${(dev.supported_modes || ["manual", "sleep", "laundry", "purify"]).map(m => `
                            <button type="button" class="mode-btn ${dev.current_mode === m ? "active" : ""}" data-device-id="${safeDevId}" data-action="set_mode" data-mode="${escapeHtml(m)}">${escapeHtml(m)}</button>
                        `).join("")}
                    </div>
                </div>
                <div class="control-row">
                    <span style="font-size: 0.8rem; color: var(--text-muted);">Manual Hold</span>
                    <div class="mode-buttons">
                        <button type="button" class="mode-btn" data-device-id="${safeDevId}" data-action="set_override" data-minutes="60">1h</button>
                        <button type="button" class="mode-btn" data-device-id="${safeDevId}" data-action="set_override" data-minutes="120">2h</button>
                        <button type="button" class="mode-btn" data-device-id="${safeDevId}" data-action="set_override" data-minutes="240">4h</button>
                        ${isHeld ? `<button type="button" class="mode-btn active" data-device-id="${safeDevId}" data-action="clear_override">Resume Auto</button>` : ""}
                    </div>
                </div>
            </div>
        `;
    }

    html += `</div>`;
    return html;
}

function renderLogs(state) {
    const consoleEl = document.getElementById("log-console");
    if (!consoleEl) return;
    if (!state.last_evaluation_logs || !state.last_evaluation_logs.length) {
        consoleEl.innerHTML = `<div class="log-line">No evaluation events logged yet.</div>`;
    } else {
        consoleEl.innerHTML = state.last_evaluation_logs.map(l => `<div class="log-line">${escapeHtml(l)}</div>`).join("");
    }
    if (state.last_evaluation_time) {
        const d = new Date(state.last_evaluation_time * 1000);
        document.getElementById("last-eval-time").textContent = "Last evaluated: " + d.toLocaleTimeString();
    }
}

function renderWeekdayCheckboxes(containerId, inputName, selectedDays) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const active = new Set((selectedDays || []).map(d => d.toLowerCase()));
    container.innerHTML = WEEKDAYS.map(day => `
        <label class="day-check">
            <input type="checkbox" name="${inputName}" value="${day}" ${active.has(day) ? "checked" : ""}>
            ${DAY_LABELS[day]}
        </label>
    `).join("");
}

function populateConfigForm(cfg) {
    if (!cfg) return;
    const c = cfg.condensation || {};
    document.getElementById("cfg-cond-enabled").checked = c.enabled !== false;
    document.getElementById("cfg-auto-power").checked = c.auto_power !== false;
    document.getElementById("cfg-min-rh").value = c.min_target_rh ?? 40;
    document.getElementById("cfg-max-rh").value = c.max_target_rh ?? 60;
    document.getElementById("cfg-on-offset").value = c.turn_on_offset_rh ?? 2.0;
    document.getElementById("cfg-off-offset").value = c.turn_off_offset_rh ?? 2.0;
    document.getElementById("cfg-rh-deadband").value = c.rh_deadband ?? 5;
    document.getElementById("cfg-min-cycle").value = c.min_cycle_seconds ?? 600;
    document.getElementById("cfg-lookahead").value = c.lookahead_hours ?? 12;
    document.getElementById("cfg-glazing").value = c.glazing || "double";
    document.getElementById("cfg-safety-margin").value = c.safety_margin_c ?? 1.5;
    document.getElementById("cfg-fixed-dp").value = c.target_dew_point_c != null ? c.target_dew_point_c : "";
    document.getElementById("cfg-override-mins").value = c.manual_override_minutes ?? 120;

    const a = cfg.alerts || {};
    document.getElementById("cfg-alerts-enabled").checked = a.enabled !== false;
    document.getElementById("cfg-low-batt").value = a.low_battery_threshold_percent ?? 20;
    document.getElementById("cfg-webhook-url").value = a.webhook_url || "";

    const s = cfg.quiet_schedule || {};
    document.getElementById("cfg-sched-enabled").checked = s.enabled !== false;
    document.getElementById("cfg-start-time").value = (s.start_time || "23:00").slice(0, 5);
    document.getElementById("cfg-end-time").value = (s.end_time || "07:00").slice(0, 5);
    document.getElementById("cfg-night-mode").value = s.night_mode || "sleep";
    document.getElementById("cfg-day-mode").value = s.day_mode || "manual";

    renderWeekdayCheckboxes("night-days", "night-days", s.night_days || WEEKDAYS);
    renderWeekdayCheckboxes("all-day-sleep-days", "all-day-sleep", s.all_day_sleep_days || []);
    renderExclusionsTable(s.exclusion_windows || []);

    const loc = cfg.location || {};
    document.getElementById("cfg-loc-city").value = loc.city || "";
    document.getElementById("cfg-loc-lat").value = loc.latitude ?? 0;
    document.getElementById("cfg-loc-lon").value = loc.longitude ?? 0;
    document.getElementById("cfg-poll-interval").value = cfg.polling_interval_seconds ?? 60;
}

function buildExclusionRow(win) {
    const tr = document.createElement("tr");
    const activeDays = new Set((win.days || WEEKDAYS).map(d => d.toLowerCase()));
    const startVal = (win.start_time || "00:00").slice(0, 5);
    const endVal = (win.end_time || "07:00").slice(0, 5);
    const roomsVal = Array.isArray(win.rooms) ? win.rooms.join(", ") : "";

    tr.innerHTML = `
        <td data-label="Enabled"><input type="checkbox" class="ex-enabled" ${win.enabled ? "checked" : ""}></td>
        <td data-label="Label"><input type="text" class="ex-label" value="${escapeHtml(win.label || "")}"></td>
        <td data-label="Time">
            <span class="ex-time-pair">
                <input type="time" class="ex-start" value="${escapeHtml(startVal)}" required>
                <span>–</span>
                <input type="time" class="ex-end" value="${escapeHtml(endVal)}" required>
            </span>
        </td>
        <td data-label="Days">
            <div class="days-selector">
                ${WEEKDAYS.map(day => `
                    <label class="day-check" style="padding: 0.2rem 0.38rem; font-size: 0.7rem;">
                        <input type="checkbox" class="ex-day-${day}" ${activeDays.has(day) ? "checked" : ""}>${DAY_LABELS[day]}
                    </label>
                `).join("")}
            </div>
        </td>
        <td data-label="Room"><input type="text" class="ex-rooms" value="${escapeHtml(roomsVal)}" placeholder="All rooms"></td>
        <td data-label="Action"><button type="button" class="btn-danger btn-sm btn-remove-exclusion">Remove</button></td>
    `;
    return tr;
}

function renderExclusionsTable(windows) {
    const tbody = document.getElementById("exclusions-body");
    if (!tbody) return;
    tbody.innerHTML = "";
    windows.forEach(win => tbody.appendChild(buildExclusionRow(win)));
}

function addExclusionRow() {
    const tbody = document.getElementById("exclusions-body");
    if (!tbody) return;
    tbody.appendChild(buildExclusionRow({
        enabled: true,
        label: "Night Silence",
        start_time: "00:00",
        end_time: "07:00",
        days: WEEKDAYS,
        rooms: ["bedroom"],
    }));
}

async function saveConfig(e) {
    e.preventDefault();
    const saveBtn = document.getElementById("btn-save-config");

    const nightDays = Array.from(document.querySelectorAll('input[name="night-days"]:checked')).map(c => c.value);
    const allDaySleepDays = Array.from(document.querySelectorAll('input[name="all-day-sleep"]:checked')).map(c => c.value);

    const exclusionRows = document.querySelectorAll("#exclusions-body tr");
    const exclusions = [];
    for (const tr of exclusionRows) {
        const days = WEEKDAYS.filter(day => tr.querySelector(`.ex-day-${day}`).checked);
        const startT = tr.querySelector(".ex-start").value.trim().slice(0, 5);
        const endT = tr.querySelector(".ex-end").value.trim().slice(0, 5);
        if (!startT || !endT) {
            showToast("Please set start and end times for all exclusion windows.", "error");
            return;
        }
        const roomsRaw = tr.querySelector(".ex-rooms").value.trim();
        exclusions.push({
            enabled: tr.querySelector(".ex-enabled").checked,
            label: tr.querySelector(".ex-label").value.trim() || "Exclusion",
            start_time: startT,
            end_time: endT,
            days: days,
            rooms: roomsRaw ? roomsRaw.split(",").map(r => r.trim()).filter(Boolean) : null,
        });
    }

    const minTargetRh = parseInt(document.getElementById("cfg-min-rh").value, 10);
    const maxTargetRh = parseInt(document.getElementById("cfg-max-rh").value, 10);
    const turnOnOffset = parseFloat(document.getElementById("cfg-on-offset").value);
    const turnOffOffset = parseFloat(document.getElementById("cfg-off-offset").value);
    const rhDeadband = parseInt(document.getElementById("cfg-rh-deadband").value, 10);
    const minCycleSec = parseInt(document.getElementById("cfg-min-cycle").value, 10);
    const lookaheadHrs = parseInt(document.getElementById("cfg-lookahead").value, 10);
    const safetyMarginC = parseFloat(document.getElementById("cfg-safety-margin").value);
    const overrideMins = parseInt(document.getElementById("cfg-override-mins").value, 10);
    const lowBattPct = parseInt(document.getElementById("cfg-low-batt").value, 10);
    const locLat = parseFloat(document.getElementById("cfg-loc-lat").value);
    const locLon = parseFloat(document.getElementById("cfg-loc-lon").value);
    const pollInterval = parseInt(document.getElementById("cfg-poll-interval").value, 10);

    const fixedDpRaw = document.getElementById("cfg-fixed-dp").value.trim();
    const fixedDp = fixedDpRaw === "" ? null : parseFloat(fixedDpRaw);
    if (fixedDpRaw !== "" && !Number.isFinite(fixedDp)) {
        showToast('Please enter a valid number for "Fixed Target Dew Point" or leave empty.', "error");
        return;
    }

    const startTime = document.getElementById("cfg-start-time").value.trim().slice(0, 5);
    const endTime = document.getElementById("cfg-end-time").value.trim().slice(0, 5);
    if (!startTime || !endTime) {
        showToast("Please specify valid Night Start and Night End times.", "error");
        return;
    }

    const numericFields = [
        ["Min Target RH", minTargetRh],
        ["Max Target RH", maxTargetRh],
        ["Turn-ON Offset RH", turnOnOffset],
        ["Turn-OFF Offset RH", turnOffOffset],
        ["RH Deadband", rhDeadband],
        ["Compressor Cooldown", minCycleSec],
        ["Forecast Lookahead", lookaheadHrs],
        ["Safety Margin", safetyMarginC],
        ["Manual Hold Duration", overrideMins],
        ["Low Battery Alert", lowBattPct],
        ["Latitude", locLat],
        ["Longitude", locLon],
        ["Polling Interval", pollInterval],
    ];
    for (const [label, val] of numericFields) {
        if (!Number.isFinite(val)) {
            showToast(`Please enter a valid number for "${label}".`, "error");
            return;
        }
    }

    const payload = {
        condensation: {
            enabled: document.getElementById("cfg-cond-enabled").checked,
            auto_power: document.getElementById("cfg-auto-power").checked,
            min_target_rh: minTargetRh,
            max_target_rh: maxTargetRh,
            turn_on_offset_rh: turnOnOffset,
            turn_off_offset_rh: turnOffOffset,
            rh_deadband: rhDeadband,
            min_cycle_seconds: minCycleSec,
            lookahead_hours: lookaheadHrs,
            glazing: document.getElementById("cfg-glazing").value,
            safety_margin_c: safetyMarginC,
            target_dew_point_c: fixedDp,
            manual_override_minutes: overrideMins,
        },
        alerts: {
            enabled: document.getElementById("cfg-alerts-enabled").checked,
            low_battery_threshold_percent: lowBattPct,
            webhook_url: document.getElementById("cfg-webhook-url").value.trim() || null,
        },
        quiet_schedule: {
            enabled: document.getElementById("cfg-sched-enabled").checked,
            start_time: startTime,
            end_time: endTime,
            night_mode: document.getElementById("cfg-night-mode").value,
            day_mode: document.getElementById("cfg-day-mode").value,
            night_days: nightDays,
            all_day_sleep_days: allDaySleepDays,
            exclusion_windows: exclusions,
        },
        location: {
            city: document.getElementById("cfg-loc-city").value.trim() || "Unknown",
            latitude: locLat,
            longitude: locLon,
        },
        polling_interval_seconds: pollInterval,
    };

    if (saveBtn) saveBtn.disabled = true;
    try {
        const res = await fetch("/api/config", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (res.ok) {
            showToast("Configuration saved and applied.", "success");
            await Promise.all([fetchState(), fetchConfig()]);
        } else {
            showToast("Failed to save config: " + (data.error || res.statusText), "error");
        }
    } catch (err) {
        showToast("Error connecting to server: " + err.message, "error");
    } finally {
        if (saveBtn) saveBtn.disabled = false;
    }
}

async function sendCommand(deviceId, action, params = {}, triggerEl = null) {
    const groupEl = triggerEl ? triggerEl.closest(".control-group") : null;
    const controls = groupEl ? Array.from(groupEl.querySelectorAll("button, input")) : [];
    controls.forEach(el => { el.disabled = true; });
    try {
        const res = await fetch(`/api/devices/${encodeURIComponent(deviceId)}/command`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action, ...params }),
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
            showToast(data.message || data.error || "Command failed.", "error");
        } else {
            showToast(data.message || "Command applied.", "success");
        }
        await fetchState();
    } catch (err) {
        console.error("Command error:", err);
        showToast("Command failed: " + err.message, "error");
    } finally {
        controls.forEach(el => { el.disabled = false; });
    }
}

async function triggerEvaluate(btn) {
    if (btn) btn.disabled = true;
    try {
        const res = await fetch("/api/evaluate", { method: "POST" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        showToast("Evaluation cycle completed.", "info");
        await fetchState();
    } catch (err) {
        console.error("Evaluation error:", err);
        showToast("Evaluation failed: " + err.message, "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

function initDashboard() {
    document.getElementById("btn-refresh").addEventListener("click", async e => {
        const btn = e.currentTarget;
        btn.disabled = true;
        try {
            await fetchState();
        } finally {
            btn.disabled = false;
        }
    });

    document.getElementById("btn-evaluate").addEventListener("click", e => {
        triggerEvaluate(e.currentTarget);
    });

    document.querySelectorAll(".tf-btn[data-hours]").forEach(btn => {
        btn.addEventListener("click", () => {
            const hrs = parseInt(btn.dataset.hours, 10);
            if (!Number.isFinite(hrs) || hrs === selectedHistoryHours) return;
            selectedHistoryHours = hrs;
            document.querySelectorAll(".tf-btn[data-hours]").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            fetchState();
        });
    });

    const accHeader = document.getElementById("config-accordion-header");
    accHeader.addEventListener("click", () => toggleAccordion());
    accHeader.addEventListener("keydown", e => {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggleAccordion();
        }
    });

    document.getElementById("btn-add-exclusion").addEventListener("click", addExclusionRow);
    document.getElementById("btn-reset-config").addEventListener("click", () => {
        fetchConfig();
        showToast("Settings form reset.", "info");
    });
    document.getElementById("exclusions-body").addEventListener("click", e => {
        const rmBtn = e.target.closest(".btn-remove-exclusion");
        if (rmBtn) {
            const tr = rmBtn.closest("tr");
            if (tr) tr.remove();
        }
    });
    document.getElementById("config-form").addEventListener("submit", saveConfig);

    const roomsGridEl = document.getElementById("rooms-grid");
    roomsGridEl.addEventListener("click", e => {
        const btn = e.target.closest("button[data-device-id][data-action]");
        if (!btn || btn.disabled) return;
        const devId = btn.dataset.deviceId;
        const action = btn.dataset.action;
        const params = {};
        if (btn.dataset.mode) params.mode = btn.dataset.mode;
        if (btn.dataset.minutes) params.minutes = parseInt(btn.dataset.minutes, 10);
        sendCommand(devId, action, params, btn);
    });
    roomsGridEl.addEventListener("pointerdown", e => {
        if (e.target.matches('input[type="range"]')) {
            isDraggingControl = true;
        }
    });
    roomsGridEl.addEventListener("input", e => {
        const slider = e.target.closest('input[type="range"][data-action="set_target"]');
        if (!slider) return;
        const valEl = slider.parentElement && slider.parentElement.querySelector(".slider-value");
        if (valEl) valEl.textContent = `${slider.value}%`;
    });
    roomsGridEl.addEventListener("change", e => {
        const slider = e.target.closest('input[type="range"][data-device-id][data-action="set_target"]');
        if (!slider) return;
        isDraggingControl = false;
        sendCommand(slider.dataset.deviceId, "set_target", { humidity: slider.value }, slider);
    });
    window.addEventListener("pointerup", () => { isDraggingControl = false; });
    window.addEventListener("pointercancel", () => { isDraggingControl = false; });

    fetchState();
    fetchConfig();
    setInterval(() => fetchState({ background: true }), 10000);
}

initDashboard();
