/* ============================================================
   TAM - Team Activity Monitor  |  Dashboard JavaScript
   ============================================================ */

(function () {
    "use strict";

    // ── State ──────────────────────────────────────────────
    const state = {
        selectedDate: todayStr(),
        users: [],
        timelines: {},          // { userId: timelineData }
        selectedUserId: null,
        selectedUserIp: null,
        selectedUserName: null,
        selectedTimeRange: null, // { start, end }
        refreshTimer: null,
        refreshCountdown: 30,
        pages: {
            screenshots: 1,
            keystrokes: 1,
            activities: 1,
            events: 1,
        },
        lightboxImages: [],
        lightboxIndex: 0,
        settings: {},
    };

    // ── Helpers ────────────────────────────────────────────
    function todayStr() {
        const d = new Date();
        return d.getFullYear() + "-" +
            String(d.getMonth() + 1).padStart(2, "0") + "-" +
            String(d.getDate()).padStart(2, "0");
    }

    function formatDate(dateStr) {
        const [y, m, d] = dateStr.split("-");
        const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
        return months[parseInt(m, 10) - 1] + " " + parseInt(d, 10) + ", " + y;
    }

    function shiftDate(dateStr, delta) {
        const d = new Date(dateStr + "T00:00:00");
        d.setDate(d.getDate() + delta);
        return d.getFullYear() + "-" +
            String(d.getMonth() + 1).padStart(2, "0") + "-" +
            String(d.getDate()).padStart(2, "0");
    }

    function minutesToTime(mins) {
        const h = String(Math.floor(mins / 60)).padStart(2, "0");
        const m = String(mins % 60).padStart(2, "0");
        return h + ":" + m;
    }

    function formatDuration(seconds) {
        if (seconds == null) return "--";
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        if (h > 0) return h + "h " + m + "m";
        if (m > 0) return m + "m " + s + "s";
        return s + "s";
    }

    function escapeHtml(str) {
        if (!str) return "";
        const d = document.createElement("div");
        d.textContent = str;
        return d.innerHTML;
    }

    function truncate(str, len) {
        if (!str) return "";
        return str.length > len ? str.substring(0, len) + "..." : str;
    }

    // ── DOM Shortcuts ──────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // ── API ────────────────────────────────────────────────
    async function api(method, path, body) {
        const opts = {
            method,
            credentials: "include",
            headers: {},
        };
        if (body) {
            opts.headers["Content-Type"] = "application/json";
            opts.body = JSON.stringify(body);
        }
        const res = await fetch(path, opts);
        if (res.status === 401) {
            showLogin();
            throw new Error("Unauthorized");
        }
        if (!res.ok) {
            const text = await res.text();
            throw new Error(text || res.statusText);
        }
        const ct = res.headers.get("content-type") || "";
        if (ct.includes("application/json")) return res.json();
        return res.text();
    }

    // ── Screen Management ──────────────────────────────────
    function showLogin() {
        stopAutoRefresh();
        $("#login-screen").classList.add("active");
        $("#dashboard-screen").classList.remove("active");
        $("#login-password").value = "";
        $("#login-password").focus();
    }

    function showDashboard() {
        $("#login-screen").classList.remove("active");
        $("#dashboard-screen").classList.add("active");
        updateDateDisplay();
        refreshAll();
        startAutoRefresh();
    }

    // ── Login ──────────────────────────────────────────────
    function initLogin() {
        $("#login-form").addEventListener("submit", async (e) => {
            e.preventDefault();
            const pw = $("#login-password").value;
            if (!pw) return;
            const btn = $("#login-btn");
            const errEl = $("#login-error");
            btn.querySelector(".btn-text").classList.add("hidden");
            btn.querySelector(".btn-loader").classList.remove("hidden");
            errEl.classList.add("hidden");
            btn.disabled = true;

            try {
                await api("POST", "/api/admin/login", { password: pw });
                showDashboard();
            } catch (err) {
                errEl.textContent = "Invalid password. Please try again.";
                errEl.classList.remove("hidden");
            } finally {
                btn.querySelector(".btn-text").classList.remove("hidden");
                btn.querySelector(".btn-loader").classList.add("hidden");
                btn.disabled = false;
            }
        });
    }

    // ── Logout ─────────────────────────────────────────────
    function initLogout() {
        $("#logout-btn").addEventListener("click", async () => {
            try { await api("POST", "/api/admin/logout"); } catch (_) {}
            showLogin();
        });
    }

    // ── Date Navigation ────────────────────────────────────
    function updateDateDisplay() {
        $("#current-date").textContent = formatDate(state.selectedDate);
    }

    function initDateNav() {
        $("#prev-day-btn").addEventListener("click", () => {
            state.selectedDate = shiftDate(state.selectedDate, -1);
            updateDateDisplay();
            refreshAll();
        });
        $("#next-day-btn").addEventListener("click", () => {
            state.selectedDate = shiftDate(state.selectedDate, 1);
            updateDateDisplay();
            refreshAll();
        });
        $("#today-btn").addEventListener("click", () => {
            state.selectedDate = todayStr();
            updateDateDisplay();
            refreshAll();
        });
    }

    // ── Auto Refresh ───────────────────────────────────────
    function startAutoRefresh() {
        stopAutoRefresh();
        state.refreshCountdown = 30;
        updateCountdown();
        state.refreshTimer = setInterval(() => {
            state.refreshCountdown--;
            if (state.refreshCountdown <= 0) {
                state.refreshCountdown = 30;
                refreshAll();
            }
            updateCountdown();
        }, 1000);
    }

    function stopAutoRefresh() {
        if (state.refreshTimer) {
            clearInterval(state.refreshTimer);
            state.refreshTimer = null;
        }
    }

    function updateCountdown() {
        const el = $("#refresh-countdown");
        if (el) el.textContent = state.refreshCountdown + "s";
    }

    function initRefreshBtn() {
        $("#refresh-btn").addEventListener("click", () => {
            state.refreshCountdown = 30;
            refreshAll();
        });
    }

    // ── Refresh All ────────────────────────────────────────
    async function refreshAll() {
        await Promise.all([
            fetchStats(),
            fetchUsers(),
            fetchDiskUsage(),
        ]);
        await fetchAllTimelines();

        if (state.selectedUserId) {
            refreshDetailTab();
        }
    }

    // ── Stats ──────────────────────────────────────────────
    async function fetchStats() {
        try {
            const data = await api("GET", "/api/admin/stats");
            $("#stat-online").textContent = data.online_count ?? data.online ?? 0;
            $("#stat-idle").textContent = data.idle_count ?? data.idle ?? 0;
            $("#stat-offline").textContent = data.offline_count ?? data.offline ?? 0;
            $("#stat-total").textContent = data.total_users ?? data.total ?? 0;
        } catch (_) {}
    }

    async function fetchDiskUsage() {
        try {
            const data = await api("GET", "/api/admin/disk-usage");
            const gb = data.total_gb ?? 0;
            $("#stat-disk").textContent = gb.toFixed(2) + " GB";
        } catch (_) {
            $("#stat-disk").textContent = "--";
        }
    }

    // ── Users ──────────────────────────────────────────────
    async function fetchUsers() {
        try {
            const data = await api("GET", "/api/admin/users");
            state.users = Array.isArray(data) ? data : (data.users || []);
        } catch (_) {
            state.users = [];
        }
    }

    // ── Timelines ──────────────────────────────────────────
    async function fetchAllTimelines() {
        const container = $("#timeline-container");
        const emptyEl = $("#timeline-empty");

        if (state.users.length === 0) {
            container.innerHTML = '<div class="timeline-empty">No user data available for this date.</div>';
            return;
        }

        const promises = state.users.map(async (u) => {
            try {
                const uid = u.user_id || u.id;
                const data = await api("GET", `/api/admin/timeline/${uid}?date=${state.selectedDate}`);
                state.timelines[uid] = data;
            } catch (_) {
                state.timelines[u.user_id || u.id] = null;
            }
        });
        await Promise.all(promises);

        renderTimelines();
    }

    function renderTimelines() {
        const container = $("#timeline-container");
        container.innerHTML = "";

        if (state.users.length === 0) {
            const emptyEl = document.createElement("div");
            emptyEl.className = "timeline-empty";
            emptyEl.innerHTML = "<p>No user data available for this date.</p>";
            container.appendChild(emptyEl);
            return;
        }

        state.users.forEach((u) => {
            const uid = u.user_id || u.id;
            const row = document.createElement("div");
            row.className = "timeline-row" + (uid === state.selectedUserId ? " selected" : "");
            row.dataset.userId = uid;

            const statusClass = (u.status || "offline").toLowerCase();

            // User label
            const label = document.createElement("div");
            label.className = "timeline-user-label";
            label.innerHTML =
                `<span class="user-status-dot ${statusClass}"></span>` +
                `<span class="user-name" title="${escapeHtml(u.display_name || u.name || uid)}">${escapeHtml(u.display_name || u.name || uid)}</span>` +
                `<span class="user-ip">${escapeHtml(u.local_ip || u.ip || "")}</span>`;
            row.appendChild(label);

            // Bar wrapper
            const wrapper = document.createElement("div");
            wrapper.className = "timeline-bar-wrapper";

            // Events row
            const evRow = document.createElement("div");
            evRow.className = "timeline-events-row";
            renderEventMarkers(evRow, uid);
            wrapper.appendChild(evRow);

            // Bar
            const bar = document.createElement("div");
            bar.className = "timeline-bar";
            renderBarSegments(bar, uid);
            wrapper.appendChild(bar);

            row.appendChild(wrapper);

            row.addEventListener("click", () => selectUser(u));
            container.appendChild(row);
        });
    }

    function renderBarSegments(bar, userId) {
        const tl = state.timelines[userId];
        if (!tl) {
            const seg = document.createElement("div");
            seg.className = "timeline-segment offline";
            seg.style.width = "100%";
            bar.appendChild(seg);
            return;
        }

        const segments = tl.segments || tl.timeline || [];
        if (segments.length === 0) {
            const seg = document.createElement("div");
            seg.className = "timeline-segment offline";
            seg.style.width = "100%";
            bar.appendChild(seg);
            return;
        }

        const totalMinutes = 1440; // 24h

        segments.forEach((s) => {
            const startMin = timeToMinutes(s.start || s.start_time || "00:00");
            const endMin = timeToMinutes(s.end || s.end_time || "23:59");
            const duration = Math.max(endMin - startMin, 1);
            const widthPct = (duration / totalMinutes) * 100;
            const leftPct = (startMin / totalMinutes) * 100;

            const seg = document.createElement("div");
            seg.className = "timeline-segment " + statusToClass(s.status);
            seg.style.width = widthPct + "%";
            seg.style.position = "absolute";
            seg.style.left = leftPct + "%";

            seg.addEventListener("mouseenter", (e) => showTooltip(e, s));
            seg.addEventListener("mousemove", (e) => moveTooltip(e));
            seg.addEventListener("mouseleave", hideTooltip);
            seg.addEventListener("click", (e) => {
                e.stopPropagation();
                state.selectedTimeRange = { start: s.start || s.start_time, end: s.end || s.end_time };
                const userObj = state.users.find(u => (u.user_id || u.id) === userId);
                if (userObj) selectUser(userObj);
            });

            bar.appendChild(seg);
        });

        bar.style.position = "relative";
    }

    function renderEventMarkers(evRow, userId) {
        const tl = state.timelines[userId];
        if (!tl || !tl.events) return;
        const events = tl.events || [];
        events.forEach((ev) => {
            const time = ev.time || ev.timestamp || "00:00";
            const mins = timeToMinutes(time);
            const leftPct = (mins / 1440) * 100;
            const marker = document.createElement("div");
            const evType = (ev.type || ev.event_type || "").toLowerCase();
            let cls = "default";
            if (evType.includes("boot") || evType.includes("startup")) cls = "boot";
            else if (evType.includes("shutdown")) cls = "shutdown";
            else if (evType.includes("kill") || evType.includes("crash") || evType.includes("stop")) cls = "alert";
            else if (evType.includes("restart")) cls = "restart";
            marker.className = "timeline-event-marker " + cls;
            marker.style.left = leftPct + "%";
            marker.title = time + " - " + (ev.type || ev.event_type || "event");
            evRow.appendChild(marker);
        });
    }

    function timeToMinutes(timeStr) {
        if (!timeStr) return 0;
        const parts = timeStr.split(":");
        const h = parseInt(parts[0], 10) || 0;
        const m = parseInt(parts[1], 10) || 0;
        return h * 60 + m;
    }

    function statusToClass(status) {
        if (!status) return "offline";
        const s = status.toLowerCase();
        if (s === "working" || s === "active" || s === "online") return "working";
        if (s === "rest") return "rest";
        if (s === "idle") return "idle";
        if (s === "offline" || s === "disconnected") return "offline";
        if (s === "alert" || s === "app_stopped" || s === "killed") return "alert";
        return "offline";
    }

    // ── Time axis ──────────────────────────────────────────
    function renderTimeAxis() {
        const container = $("#timeline-hours");
        container.innerHTML = "";
        for (let h = 0; h < 24; h++) {
            const mark = document.createElement("div");
            mark.className = "timeline-hour-mark";
            mark.textContent = String(h).padStart(2, "0");
            container.appendChild(mark);
        }
    }

    // ── Tooltip ────────────────────────────────────────────
    function showTooltip(e, seg) {
        const tt = $("#tooltip");
        const startT = seg.start || seg.start_time || "--";
        const endT = seg.end || seg.end_time || "--";
        const status = seg.status || "unknown";
        const proc = seg.process || seg.active_process || "";
        tt.innerHTML =
            `<div class="tt-time">${escapeHtml(startT)} - ${escapeHtml(endT)}</div>` +
            `<div class="tt-status">Status: ${escapeHtml(status)}</div>` +
            (proc ? `<div class="tt-process">${escapeHtml(proc)}</div>` : "");
        tt.classList.remove("hidden");
        moveTooltip(e);
    }

    function moveTooltip(e) {
        const tt = $("#tooltip");
        let x = e.clientX + 14;
        let y = e.clientY + 14;
        if (x + 260 > window.innerWidth) x = e.clientX - 270;
        if (y + 80 > window.innerHeight) y = e.clientY - 90;
        tt.style.left = x + "px";
        tt.style.top = y + "px";
    }

    function hideTooltip() {
        $("#tooltip").classList.add("hidden");
    }

    // ── User Selection ─────────────────────────────────────
    function selectUser(user) {
        const uid = user.user_id || user.id;
        state.selectedUserId = uid;
        state.selectedUserIp = user.local_ip || user.ip || "";
        state.selectedUserName = user.display_name || user.name || uid;

        $$(".timeline-row").forEach((r) => {
            r.classList.toggle("selected", r.dataset.userId === String(uid));
        });

        $("#detail-user-name").textContent = state.selectedUserName;
        $("#detail-user-ip").textContent = state.selectedUserIp;
        if (state.selectedTimeRange) {
            $("#detail-time-range").textContent = state.selectedTimeRange.start + " - " + state.selectedTimeRange.end;
        } else {
            $("#detail-time-range").textContent = "Full Day";
        }

        const panel = $("#detail-panel");
        panel.classList.remove("hidden");

        state.pages.screenshots = 1;
        state.pages.keystrokes = 1;
        state.pages.activities = 1;
        state.pages.events = 1;
        refreshDetailTab();
    }

    function initDetailClose() {
        $("#detail-close-btn").addEventListener("click", () => {
            $("#detail-panel").classList.add("hidden");
            state.selectedUserId = null;
            state.selectedTimeRange = null;
            $$(".timeline-row").forEach(r => r.classList.remove("selected"));
        });
    }

    // ── Detail Tabs ────────────────────────────────────────
    function initDetailTabs() {
        $$(".tab-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                $$(".tab-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                $$(".tab-pane").forEach(p => p.classList.remove("active"));
                const tab = btn.dataset.tab;
                $(`#tab-${tab}`).classList.add("active");
                refreshDetailTab();
            });
        });
    }

    function activeTab() {
        const btn = $(".tab-btn.active");
        return btn ? btn.dataset.tab : "screenshots";
    }

    function refreshDetailTab() {
        if (!state.selectedUserId) return;
        const tab = activeTab();
        if (tab === "screenshots") fetchScreenshots();
        else if (tab === "keystrokes") fetchKeystrokes();
        else if (tab === "activities") fetchActivities();
        else if (tab === "events") fetchEvents();
    }

    // ── Screenshots ────────────────────────────────────────
    async function fetchScreenshots() {
        const grid = $("#screenshot-grid");
        const pag = $("#screenshots-pagination");
        grid.innerHTML = '<p style="color:var(--text-muted);padding:20px">Loading...</p>';
        pag.innerHTML = "";
        try {
            const page = state.pages.screenshots;
            const data = await api("GET",
                `/api/admin/screenshots?user_id=${state.selectedUserId}&date=${state.selectedDate}&page=${page}&limit=20`);
            const items = data.items || data.screenshots || data.data || [];
            const total = data.total || items.length;
            const totalPages = data.total_pages || Math.ceil(total / 20) || 1;

            state.lightboxImages = items;
            grid.innerHTML = "";

            if (items.length === 0) {
                grid.innerHTML = '<p style="color:var(--text-muted);padding:20px">No screenshots for this date.</p>';
                return;
            }

            items.forEach((item, idx) => {
                const ip = item.local_ip || state.selectedUserIp;
                const date = item.date || state.selectedDate;
                const filename = item.filename || item.file || "";
                const imgUrl = item.url || `/images/${ip}/${date}/${filename}`;
                const time = item.time || item.timestamp || "";
                const proc = item.process || item.active_process || "";
                const trigger = item.trigger || item.trigger_type || "";
                const monitor = item.monitor_index != null ? "Monitor " + item.monitor_index : "";

                const card = document.createElement("div");
                card.className = "screenshot-card";
                card.innerHTML =
                    `<img src="${escapeHtml(imgUrl)}" alt="Screenshot" loading="lazy" onerror="this.style.display='none'">` +
                    `<div class="screenshot-meta">` +
                    `<span class="time">${escapeHtml(time)}</span>` +
                    `<span class="process">${escapeHtml(proc)}${monitor ? " &middot; " + escapeHtml(monitor) : ""}</span>` +
                    (trigger ? `<span class="trigger">${escapeHtml(trigger)}</span>` : "") +
                    `</div>`;
                card.addEventListener("click", () => openLightbox(idx));
                grid.appendChild(card);
            });

            renderPagination(pag, page, totalPages, (p) => {
                state.pages.screenshots = p;
                fetchScreenshots();
            });
        } catch (_) {
            grid.innerHTML = '<p style="color:var(--text-muted);padding:20px">Failed to load screenshots.</p>';
        }
    }

    // ── Keystrokes ─────────────────────────────────────────
    async function fetchKeystrokes() {
        const tbody = $("#keystrokes-body");
        const pag = $("#keystrokes-pagination");
        tbody.innerHTML = '<tr><td colspan="3" style="color:var(--text-muted)">Loading...</td></tr>';
        pag.innerHTML = "";
        try {
            const page = state.pages.keystrokes;
            const data = await api("GET",
                `/api/admin/keystrokes?user_id=${state.selectedUserId}&date=${state.selectedDate}&page=${page}&limit=50`);
            const items = data.items || data.keystrokes || data.data || [];
            const total = data.total || items.length;
            const totalPages = data.total_pages || Math.ceil(total / 50) || 1;

            tbody.innerHTML = "";
            if (items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="3" style="color:var(--text-muted)">No keystroke data.</td></tr>';
                return;
            }

            items.forEach((item) => {
                const time = item.time || item.timestamp || "";
                const app = item.application || item.process || "";
                const keys = item.keystrokes || item.keys || item.text || "";

                const row = document.createElement("tr");
                row.className = "expandable-row";
                row.innerHTML =
                    `<td>${escapeHtml(time)}</td>` +
                    `<td>${escapeHtml(app)}</td>` +
                    `<td>${escapeHtml(truncate(keys, 60))}</td>`;

                let expanded = false;
                row.addEventListener("click", () => {
                    const next = row.nextElementSibling;
                    if (expanded && next && next.classList.contains("expanded-content")) {
                        next.remove();
                        expanded = false;
                    } else if (!expanded) {
                        const expRow = document.createElement("tr");
                        const expTd = document.createElement("td");
                        expTd.colSpan = 3;
                        expTd.className = "expanded-content";
                        expTd.textContent = keys;
                        expRow.appendChild(expTd);
                        row.after(expRow);
                        expanded = true;
                    }
                });
                tbody.appendChild(row);
            });

            renderPagination(pag, page, totalPages, (p) => {
                state.pages.keystrokes = p;
                fetchKeystrokes();
            });
        } catch (_) {
            tbody.innerHTML = '<tr><td colspan="3" style="color:var(--text-muted)">Failed to load keystrokes.</td></tr>';
        }
    }

    // ── Activities ─────────────────────────────────────────
    async function fetchActivities() {
        const tbody = $("#activities-body");
        const pag = $("#activities-pagination");
        const barsContainer = $("#app-usage-bars");
        tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text-muted)">Loading...</td></tr>';
        pag.innerHTML = "";
        barsContainer.innerHTML = "";
        try {
            const page = state.pages.activities;
            const data = await api("GET",
                `/api/admin/activities?user_id=${state.selectedUserId}&date=${state.selectedDate}&page=${page}&limit=50`);
            const items = data.items || data.activities || data.data || [];
            const total = data.total || items.length;
            const totalPages = data.total_pages || Math.ceil(total / 50) || 1;

            tbody.innerHTML = "";
            if (items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text-muted)">No activity data.</td></tr>';
                return;
            }

            // Usage summary
            const appTotals = {};
            let grandTotal = 0;
            items.forEach((item) => {
                const proc = item.process || item.application || "Unknown";
                const dur = item.duration_seconds || item.duration || 0;
                appTotals[proc] = (appTotals[proc] || 0) + dur;
                grandTotal += dur;
            });

            if (grandTotal > 0) {
                const sorted = Object.entries(appTotals).sort((a, b) => b[1] - a[1]).slice(0, 10);
                sorted.forEach(([proc, dur]) => {
                    const pct = ((dur / grandTotal) * 100).toFixed(1);
                    const row = document.createElement("div");
                    row.className = "app-bar-row";
                    row.innerHTML =
                        `<span class="app-bar-label" title="${escapeHtml(proc)}">${escapeHtml(truncate(proc, 25))}</span>` +
                        `<div class="app-bar-track"><div class="app-bar-fill" style="width:${pct}%"></div></div>` +
                        `<span class="app-bar-pct">${pct}%</span>`;
                    barsContainer.appendChild(row);
                });
            }

            items.forEach((item) => {
                const start = item.start || item.start_time || "";
                const end = item.end || item.end_time || "";
                const dur = item.duration_seconds || item.duration || 0;
                const proc = item.process || item.application || "";
                const url = item.url || item.window_title || item.title || "";

                const row = document.createElement("tr");
                row.innerHTML =
                    `<td>${escapeHtml(start)}</td>` +
                    `<td>${escapeHtml(end)}</td>` +
                    `<td>${escapeHtml(formatDuration(dur))}</td>` +
                    `<td>${escapeHtml(proc)}</td>` +
                    `<td title="${escapeHtml(url)}">${escapeHtml(truncate(url, 50))}</td>`;
                tbody.appendChild(row);
            });

            renderPagination(pag, page, totalPages, (p) => {
                state.pages.activities = p;
                fetchActivities();
            });
        } catch (_) {
            tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text-muted)">Failed to load activities.</td></tr>';
        }
    }

    // ── Events ─────────────────────────────────────────────
    async function fetchEvents() {
        const tbody = $("#events-body");
        const pag = $("#events-pagination");
        const alertSection = $("#alert-events");
        const alertList = $("#alert-events-list");
        tbody.innerHTML = '<tr><td colspan="3" style="color:var(--text-muted)">Loading...</td></tr>';
        pag.innerHTML = "";
        alertSection.classList.add("hidden");
        alertList.innerHTML = "";

        try {
            const page = state.pages.events;
            const data = await api("GET",
                `/api/admin/events?user_id=${state.selectedUserId}&date=${state.selectedDate}&page=${page}&limit=50`);
            const items = data.items || data.events || data.data || [];
            const total = data.total || items.length;
            const totalPages = data.total_pages || Math.ceil(total / 50) || 1;

            tbody.innerHTML = "";
            if (items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="3" style="color:var(--text-muted)">No events.</td></tr>';
                return;
            }

            // Alert events
            const alerts = items.filter(ev => {
                const t = (ev.type || ev.event_type || "").toLowerCase();
                return t.includes("kill") || t.includes("crash") || t.includes("app_stop");
            });
            if (alerts.length > 0) {
                alertSection.classList.remove("hidden");
                alerts.forEach((ev) => {
                    const div = document.createElement("div");
                    div.className = "alert-event-item";
                    div.innerHTML =
                        `<span class="alert-event-time">${escapeHtml(ev.time || ev.timestamp || "")}</span>` +
                        `<span class="alert-event-type">${escapeHtml(ev.type || ev.event_type || "")}</span>` +
                        `<span class="alert-event-detail">${escapeHtml(ev.details || ev.description || "")}</span>`;
                    alertList.appendChild(div);
                });
            }

            items.forEach((item) => {
                const time = item.time || item.timestamp || "";
                const evType = item.type || item.event_type || "";
                const details = item.details || item.description || "";
                const cls = eventIconClass(evType);

                const row = document.createElement("tr");
                row.innerHTML =
                    `<td>${escapeHtml(time)}</td>` +
                    `<td><span class="event-icon ${cls}">${escapeHtml(evType)}</span></td>` +
                    `<td>${escapeHtml(details)}</td>`;
                tbody.appendChild(row);
            });

            renderPagination(pag, page, totalPages, (p) => {
                state.pages.events = p;
                fetchEvents();
            });
        } catch (_) {
            tbody.innerHTML = '<tr><td colspan="3" style="color:var(--text-muted)">Failed to load events.</td></tr>';
        }
    }

    function eventIconClass(evType) {
        if (!evType) return "default";
        const t = evType.toLowerCase();
        if (t.includes("boot") || t.includes("startup")) return "boot";
        if (t.includes("shutdown")) return "shutdown";
        if (t.includes("app_start") || t.includes("start")) return "app_start";
        if (t.includes("app_stop") || t.includes("stop")) return "app_stop";
        if (t.includes("kill")) return "app_killed";
        if (t.includes("crash")) return "app_crash";
        if (t.includes("login")) return "login";
        return "default";
    }

    // ── Pagination ─────────────────────────────────────────
    function renderPagination(container, currentPage, totalPages, onPageChange) {
        container.innerHTML = "";
        if (totalPages <= 1) return;

        const prev = document.createElement("button");
        prev.className = "page-btn";
        prev.textContent = "Prev";
        prev.disabled = currentPage <= 1;
        prev.addEventListener("click", () => onPageChange(currentPage - 1));
        container.appendChild(prev);

        const maxVisible = 7;
        let startP = Math.max(1, currentPage - Math.floor(maxVisible / 2));
        let endP = Math.min(totalPages, startP + maxVisible - 1);
        if (endP - startP < maxVisible - 1) startP = Math.max(1, endP - maxVisible + 1);

        if (startP > 1) {
            container.appendChild(makePageBtn(1, currentPage, onPageChange));
            if (startP > 2) {
                const dots = document.createElement("span");
                dots.className = "page-info";
                dots.textContent = "...";
                container.appendChild(dots);
            }
        }

        for (let p = startP; p <= endP; p++) {
            container.appendChild(makePageBtn(p, currentPage, onPageChange));
        }

        if (endP < totalPages) {
            if (endP < totalPages - 1) {
                const dots = document.createElement("span");
                dots.className = "page-info";
                dots.textContent = "...";
                container.appendChild(dots);
            }
            container.appendChild(makePageBtn(totalPages, currentPage, onPageChange));
        }

        const next = document.createElement("button");
        next.className = "page-btn";
        next.textContent = "Next";
        next.disabled = currentPage >= totalPages;
        next.addEventListener("click", () => onPageChange(currentPage + 1));
        container.appendChild(next);
    }

    function makePageBtn(page, current, onPageChange) {
        const btn = document.createElement("button");
        btn.className = "page-btn" + (page === current ? " active" : "");
        btn.textContent = page;
        btn.addEventListener("click", () => onPageChange(page));
        return btn;
    }

    // ── Lightbox ───────────────────────────────────────────
    function openLightbox(index) {
        state.lightboxIndex = index;
        renderLightbox();
        $("#lightbox").classList.remove("hidden");
    }

    function closeLightbox() {
        $("#lightbox").classList.add("hidden");
    }

    function renderLightbox() {
        const item = state.lightboxImages[state.lightboxIndex];
        if (!item) return;
        const ip = item.local_ip || state.selectedUserIp;
        const date = item.date || state.selectedDate;
        const filename = item.filename || item.file || "";
        const imgUrl = item.url || `/images/${ip}/${date}/${filename}`;
        const time = item.time || item.timestamp || "";
        const proc = item.process || item.active_process || "";
        const trigger = item.trigger || item.trigger_type || "";
        const monitor = item.monitor_index != null ? item.monitor_index : "--";
        const url = item.url_captured || item.page_url || "";

        $("#lightbox-img").src = imgUrl;
        $("#lightbox-meta").innerHTML =
            `<span><span class="label">Time:</span> ${escapeHtml(time)}</span>` +
            `<span><span class="label">Monitor:</span> ${monitor}</span>` +
            `<span><span class="label">Process:</span> ${escapeHtml(proc)}</span>` +
            (url ? `<span><span class="label">URL:</span> ${escapeHtml(truncate(url, 40))}</span>` : "") +
            (trigger ? `<span><span class="label">Trigger:</span> ${escapeHtml(trigger)}</span>` : "");
    }

    function initLightbox() {
        $("#lightbox-close-btn").addEventListener("click", closeLightbox);
        $("#lightbox").addEventListener("click", (e) => {
            if (e.target === $("#lightbox")) closeLightbox();
        });
        $("#lightbox-prev-btn").addEventListener("click", () => {
            if (state.lightboxIndex > 0) {
                state.lightboxIndex--;
                renderLightbox();
            }
        });
        $("#lightbox-next-btn").addEventListener("click", () => {
            if (state.lightboxIndex < state.lightboxImages.length - 1) {
                state.lightboxIndex++;
                renderLightbox();
            }
        });
        document.addEventListener("keydown", (e) => {
            if ($("#lightbox").classList.contains("hidden")) return;
            if (e.key === "Escape") closeLightbox();
            if (e.key === "ArrowLeft" && state.lightboxIndex > 0) {
                state.lightboxIndex--;
                renderLightbox();
            }
            if (e.key === "ArrowRight" && state.lightboxIndex < state.lightboxImages.length - 1) {
                state.lightboxIndex++;
                renderLightbox();
            }
        });
    }

    // ── Settings ───────────────────────────────────────────
    const SETTINGS_MAP = {
        "setting-timezone": "system_timezone",
        "setting-capture-interval": "capture_interval_sec",
        "setting-capture-quality": "image_quality",
        "setting-capture-maxwidth": "image_max_width",
        "setting-capture-on-process-change": "capture_on_process_change",
        "setting-capture-skip-unchanged": "skip_unchanged_screen",
        "setting-rest-threshold": "idle_threshold_rest",
        "setting-idle-threshold": "idle_threshold_idle",
        "setting-heartbeat-interval": "heartbeat_interval",
        "setting-offline-threshold": "offline_threshold",
        "setting-keystroke-batch-interval": "keylog_batch_interval",
        "setting-keystroke-log-special": "keystroke_log_special_keys",
        "setting-retention-screenshots": "retention_days",
        "setting-retention-keystrokes": "retention_days",
        "setting-retention-activities": "retention_days",
        "setting-retention-events": "retention_days",
        "setting-email-enabled": "alert_enabled",
        "setting-smtp-host": "smtp_server",
        "setting-smtp-port": "smtp_port",
        "setting-smtp-user": "smtp_email",
        "setting-smtp-password": "smtp_password",
        "setting-alert-recipients": "alert_recipients",
    };

    function openSettings() {
        $("#settings-modal").classList.remove("hidden");
        loadSettings();
        loadSettingsUsers();
    }

    function closeSettings() {
        $("#settings-modal").classList.add("hidden");
    }

    async function loadSettings() {
        try {
            const data = await api("GET", "/api/admin/settings");
            state.settings = data.settings || data || {};
            populateSettingsForm(state.settings);
        } catch (_) {}
    }

    function populateSettingsForm(s) {
        Object.entries(SETTINGS_MAP).forEach(([elemId, key]) => {
            const el = document.getElementById(elemId);
            if (!el) return;
            const val = s[key];
            if (val === undefined || val === null) return;
            if (el.type === "checkbox") {
                el.checked = val === true || val === "true" || val === "1";
            } else {
                el.value = val;
            }
        });
    }

    function collectSettings() {
        const result = {};
        Object.entries(SETTINGS_MAP).forEach(([elemId, key]) => {
            const el = document.getElementById(elemId);
            if (!el) return;
            if (el.type === "checkbox") {
                result[key] = el.checked;
            } else if (el.type === "number") {
                result[key] = parseInt(el.value, 10);
            } else {
                result[key] = el.value;
            }
        });
        return result;
    }

    async function saveSettings() {
        const msg = $("#settings-save-msg");
        msg.classList.remove("hidden", "success", "error");
        try {
            const payload = collectSettings();
            await api("PUT", "/api/admin/settings", payload);
            msg.textContent = "Settings saved successfully.";
            msg.classList.add("success");
        } catch (err) {
            msg.textContent = "Failed to save: " + err.message;
            msg.classList.add("error");
        }
        setTimeout(() => msg.classList.add("hidden"), 4000);
    }

    function resetSettings() {
        populateSettingsForm(state.settings);
    }

    async function loadSettingsUsers() {
        const tbody = $("#settings-users-body");
        tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted)">Loading...</td></tr>';
        try {
            await fetchUsers();
            tbody.innerHTML = "";
            if (state.users.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted)">No users registered.</td></tr>';
                return;
            }
            state.users.forEach((u) => {
                const status = (u.status || "offline").toLowerCase();
                const lastSeen = u.last_seen || u.last_heartbeat || "--";
                const row = document.createElement("tr");
                row.innerHTML =
                    `<td>${escapeHtml(u.display_name || u.name || u.user_id || u.id)}</td>` +
                    `<td>${escapeHtml(u.local_ip || u.ip || "")}</td>` +
                    `<td><span class="status-badge ${status}">${status}</span></td>` +
                    `<td>${escapeHtml(lastSeen)}</td>`;
                tbody.appendChild(row);
            });
        } catch (_) {
            tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted)">Failed to load users.</td></tr>';
        }
    }

    async function changePassword() {
        const msg = $("#password-change-msg");
        const curPw = $("#setting-admin-current-pw").value;
        const newPw = $("#setting-admin-new-pw").value;
        const confirmPw = $("#setting-admin-confirm-pw").value;
        msg.classList.remove("hidden", "success", "error");

        if (!curPw || !newPw) {
            msg.textContent = "Please fill in all password fields.";
            msg.classList.add("error");
            return;
        }
        if (newPw !== confirmPw) {
            msg.textContent = "New passwords do not match.";
            msg.classList.add("error");
            return;
        }
        try {
            await api("PUT", "/api/admin/settings", {
                admin_password: newPw,
                current_password: curPw,
            });
            msg.textContent = "Password changed successfully.";
            msg.classList.add("success");
            $("#setting-admin-current-pw").value = "";
            $("#setting-admin-new-pw").value = "";
            $("#setting-admin-confirm-pw").value = "";
        } catch (err) {
            msg.textContent = "Failed: " + err.message;
            msg.classList.add("error");
        }
        setTimeout(() => msg.classList.add("hidden"), 4000);
    }

    function initSettings() {
        $("#settings-btn").addEventListener("click", openSettings);
        $("#settings-close-btn").addEventListener("click", closeSettings);
        $("#settings-modal").addEventListener("click", (e) => {
            if (e.target === $("#settings-modal")) closeSettings();
        });
        $("#settings-save-btn").addEventListener("click", saveSettings);
        $("#settings-reset-btn").addEventListener("click", resetSettings);
        $("#change-password-btn").addEventListener("click", changePassword);

        // Settings sub-tabs
        $$(".stab-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                $$(".stab-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                $$(".stab-pane").forEach(p => p.classList.remove("active"));
                $(`#stab-${btn.dataset.stab}`).classList.add("active");

                const footer = $("#settings-modal-footer");
                if (btn.dataset.stab === "admin" || btn.dataset.stab === "users") {
                    footer.style.display = "none";
                } else {
                    footer.style.display = "";
                }
            });
        });
    }

    // ── Keyboard shortcuts ─────────────────────────────────
    function initKeyboard() {
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                if (!$("#settings-modal").classList.contains("hidden")) {
                    closeSettings();
                }
            }
        });
    }

    // ── Session check ──────────────────────────────────────
    async function checkSession() {
        try {
            await api("GET", "/api/admin/stats");
            showDashboard();
        } catch (_) {
            showLogin();
        }
    }

    // ── Init ───────────────────────────────────────────────
    function init() {
        renderTimeAxis();
        initLogin();
        initLogout();
        initDateNav();
        initRefreshBtn();
        initDetailTabs();
        initDetailClose();
        initLightbox();
        initSettings();
        initKeyboard();
        checkSession();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
