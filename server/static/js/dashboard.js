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
        lightboxTotalPages: 1,
        lightboxLoading: false,
        settings: {},
        isBackgroundRefresh: false,
        expandedKeystrokeIndex: null,
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

    function formatKeystrokesForDisplay(keys) {
        if (!keys) return "";
        return String(keys).replace(/\[Space\]/g, " ");
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

    function resetPaginationForNewDate() {
        state.pages.screenshots = 1;
        state.pages.keystrokes = 1;
        state.pages.activities = 1;
        state.pages.events = 1;
    }

    function initDateNav() {
        $("#prev-day-btn").addEventListener("click", () => {
            state.selectedDate = shiftDate(state.selectedDate, -1);
            updateDateDisplay();
            resetPaginationForNewDate();
            refreshAll({ skipDiskUsage: true });
        });
        $("#next-day-btn").addEventListener("click", () => {
            state.selectedDate = shiftDate(state.selectedDate, 1);
            updateDateDisplay();
            resetPaginationForNewDate();
            refreshAll({ skipDiskUsage: true });
        });
        $("#today-btn").addEventListener("click", () => {
            state.selectedDate = todayStr();
            updateDateDisplay();
            resetPaginationForNewDate();
            refreshAll({ skipDiskUsage: true });
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
            refreshAll({ forceDiskRefresh: true });
        });
    }

    // ── Refresh All ────────────────────────────────────────
    function _saveScrollPositions() {
        const tl = $("#timeline-container");
        return {
            window: window.scrollY || document.documentElement.scrollTop,
            timeline: tl ? tl.scrollTop : 0,
        };
    }
    function _restoreScrollPositions(pos) {
        if (!pos) return;
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                window.scrollTo(0, pos.window || 0);
                const tl = $("#timeline-container");
                if (tl && pos.timeline != null) tl.scrollTop = pos.timeline;
            });
        });
    }

    async function refreshAll(options) {
        const opts = options || {};
        const skipDiskUsage = opts.skipDiskUsage === true;
        const forceDiskRefresh = opts.forceDiskRefresh === true;
        const scrollPos = _saveScrollPositions();
        state.isBackgroundRefresh = true;

        try {
            await fetchUsers();
            const parallel = [fetchStats(), fetchAllTimelines()];
            if (!skipDiskUsage) {
                parallel.push(fetchDiskUsage({ forceRefresh: forceDiskRefresh }));
            }
            await Promise.all(parallel);
            if (state.selectedUserId) {
                await refreshDetailTab();
            }
        } finally {
            state.isBackgroundRefresh = false;
        }

        _restoreScrollPositions(scrollPos);
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

    async function fetchDiskUsage(opts) {
        const o = opts || {};
        const force = o.forceRefresh === true;
        const path = "/api/admin/disk-usage" + (force ? "?refresh=true" : "");
        try {
            const data = await api("GET", path);
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

        if (state.users.length === 0) {
            container.innerHTML = '<div class="timeline-empty">No user data available for this date.</div>';
            return;
        }

        const encDate = encodeURIComponent(state.selectedDate);
        try {
            const data = await api("GET", `/api/admin/timelines?date=${encDate}`);
            const timelines = data.timelines || {};
            state.timelines = {};
            state.users.forEach((u) => {
                const uid = u.user_id || u.id;
                state.timelines[uid] = timelines[uid] != null ? timelines[uid] : null;
            });
        } catch (_) {
            state.users.forEach((u) => {
                state.timelines[u.user_id || u.id] = null;
            });
        }

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

        renderTimelineSummary();
    }

    function renderTimelineSummary() {
        const tbody = $("#timeline-summary-body");
        const section = $("#timeline-summary-section");
        if (!tbody || !section) return;

        if (state.users.length === 0) {
            section.classList.add("hidden");
            return;
        }
        section.classList.remove("hidden");

        tbody.innerHTML = "";
        state.users.forEach((u) => {
            const uid = u.user_id || u.id;
            const tl = state.timelines[uid];
            const sum = tl && tl.summary ? tl.summary : {};
            const work = sum.work_seconds ?? 0;
            const rest = sum.rest_seconds ?? 0;
            const idle = sum.idle_seconds ?? 0;
            const offline = sum.offline_seconds ?? 0;
            const keys = sum.keystroke_count ?? 0;

            const row = document.createElement("tr");
            row.className = "timeline-summary-row" + (uid === state.selectedUserId ? " selected" : "");
            row.dataset.userId = uid;
            row.innerHTML =
                `<td class="summary-user">${escapeHtml(u.display_name || u.name || uid)}</td>` +
                `<td>${formatDuration(work)}</td>` +
                `<td>${formatDuration(rest)}</td>` +
                `<td>${formatDuration(idle)}</td>` +
                `<td>${formatDuration(offline)}</td>` +
                `<td>${keys}</td>`;
            row.style.cursor = "pointer";
            row.addEventListener("click", () => selectUser(u));
            tbody.appendChild(row);
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

        const segments = Array.isArray(tl) ? tl : (tl.segments || tl.timeline || []);
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
        if (!tl) return;
        const events = Array.isArray(tl) ? [] : (tl.events || []);
        events.forEach((ev) => {
            const rawTime = ev.timestamp || ev.time || "00:00";
            const mins = timeToMinutes(rawTime);
            const leftPct = (mins / 1440) * 100;
            const marker = document.createElement("div");
            const evType = (ev.event_type || ev.type || "").toLowerCase();
            let cls = "default";
            let label = ev.event_type || ev.type || "event";
            if (evType.includes("boot") || evType.includes("start")) {
                cls = "boot";
                label = evType.includes("app") ? "App Start" : "Start";
            } else if (evType.includes("shutdown") || evType.includes("off")) cls = "shutdown";
            else if (evType.includes("kill") || evType.includes("crash") || evType.includes("stop")) cls = "alert";
            else if (evType.includes("restart") || evType.includes("reboot")) cls = "restart";
            else if (evType.includes("heartbeat")) return;
            marker.className = "timeline-event-marker " + cls;
            marker.style.left = leftPct + "%";
            marker.title = _fmtTime(rawTime) + " – " + label;
            evRow.appendChild(marker);
        });
    }

    function timeToMinutes(timeStr) {
        if (!timeStr) return 0;
        let t = timeStr;
        if (t.includes("T")) t = t.split("T")[1];
        if (t.includes("+")) t = t.split("+")[0];
        if (t.includes("-") && t.lastIndexOf("-") > 2) t = t.substring(0, t.lastIndexOf("-"));
        const parts = t.split(":");
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
        const startT = _fmtTime(seg.start || seg.start_time || "--");
        const endT = _fmtTime(seg.end || seg.end_time || "--");
        const status = seg.status || "unknown";
        const proc = seg.process || seg.active_process || "";
        tt.innerHTML =
            `<div class="tt-time">${escapeHtml(startT)} ~ ${escapeHtml(endT)}</div>` +
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
        $$(".timeline-summary-row").forEach((r) => {
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
        state.expandedKeystrokeIndex = null;
        refreshDetailTab();
    }

    function initDetailClose() {
        $("#detail-close-btn").addEventListener("click", () => {
            $("#detail-panel").classList.add("hidden");
            state.selectedUserId = null;
            state.selectedTimeRange = null;
            state.expandedKeystrokeIndex = null;
            $$(".timeline-row").forEach(r => r.classList.remove("selected"));
            $$(".timeline-summary-row").forEach(r => r.classList.remove("selected"));
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

    async function refreshDetailTab() {
        if (!state.selectedUserId) return;
        const tab = activeTab();
        if (tab === "screenshots") await fetchScreenshots();
        else if (tab === "keystrokes") await fetchKeystrokes();
        else if (tab === "activities") await fetchActivities();
        else if (tab === "events") await fetchEvents();
    }

    // ── Screenshots ────────────────────────────────────────
    async function fetchScreenshots() {
        const grid = $("#screenshot-grid");
        const pag = $("#screenshots-pagination");
        if (!state.isBackgroundRefresh) {
            grid.innerHTML = '<p style="color:var(--text-muted);padding:20px">Loading...</p>';
            pag.innerHTML = "";
        }
        try {
            const page = state.pages.screenshots;
            const data = await api("GET",
                `/api/admin/screenshots?user_id=${state.selectedUserId}&date=${state.selectedDate}&page=${page}&limit=20`);
            const items = data.items || data.screenshots || data.data || [];
            const total = data.total || items.length;
            const totalPages = data.total_pages || Math.ceil(total / 20) || 1;

            state.lightboxImages = items;
            state.lightboxTotalPages = totalPages;
            grid.innerHTML = "";

            if (items.length === 0) {
                grid.innerHTML = '<p style="color:var(--text-muted);padding:20px">No screenshots for this date.</p>';
                return;
            }

            items.forEach((item, idx) => {
                const thumbUrl = item.thumb_url || item.image_path || item.url || "";
                const capturedAt = item.captured_at || "";
                const time = capturedAt.includes("T") ? capturedAt.split("T")[1].substring(0, 8) : (item.time || "");
                const proc = item.active_process || item.process || "";
                const trigger = item.trigger || "";
                const monitor = item.monitor_index != null ? "Monitor " + item.monitor_index : "";

                const card = document.createElement("div");
                card.className = "screenshot-card";
                card.innerHTML =
                    `<img src="${escapeHtml(thumbUrl)}" alt="Screenshot" loading="lazy" decoding="async" onerror="this.style.display='none'">` +
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
    function _fmtTime(isoStr) {
        if (!isoStr) return "";
        const t = isoStr.includes("T") ? isoStr.split("T")[1] : isoStr;
        return t.substring(0, 8);
    }

    async function fetchKeystrokes() {
        const tbody = $("#keystrokes-body");
        const pag = $("#keystrokes-pagination");
        if (!state.isBackgroundRefresh) {
            tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted)">Loading...</td></tr>';
            pag.innerHTML = "";
        }
        try {
            const page = state.pages.keystrokes;
            const data = await api("GET",
                `/api/admin/keystrokes?user_id=${state.selectedUserId}&date=${state.selectedDate}&page=${page}&limit=50&grouped=true`);
            const items = data.items || [];
            const total = data.total || items.length;
            const totalPages = data.total_pages || Math.ceil(total / 50) || 1;

            tbody.innerHTML = "";
            if (items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted)">No keystroke data.</td></tr>';
                return;
            }

            items.forEach((item, idx) => {
                const time = _fmtTime(item.start_time || item.timestamp);
                const proc = item.active_process || "";
                const win = item.active_window || "";
                const keysRaw = item.keys || item.key_data || "";
                const keys = formatKeystrokesForDisplay(keysRaw);
                const count = item.count || 1;

                const row = document.createElement("tr");
                row.className = "expandable-row";
                row.dataset.keystrokeIndex = String(idx);
                row.innerHTML =
                    `<td>${escapeHtml(time)}</td>` +
                    `<td>${escapeHtml(proc)}</td>` +
                    `<td title="${escapeHtml(win)}">${escapeHtml(truncate(win, 30))}</td>` +
                    `<td><code class="keystroke-text">${escapeHtml(truncate(keys, 80))}</code> <span style="color:var(--text-muted);font-size:0.75rem">(${count})</span></td>`;

                if (keysRaw.length > 80) {
                    row.style.cursor = "pointer";
                    row.addEventListener("click", () => {
                        const next = row.nextElementSibling;
                        if (next && next.classList.contains("expanded-content")) {
                            next.remove();
                            state.expandedKeystrokeIndex = null;
                        } else {
                            const expRow = document.createElement("tr");
                            expRow.classList.add("expanded-content");
                            const expTd = document.createElement("td");
                            expTd.colSpan = 4;
                            expTd.className = "expanded-content";
                            expTd.style.whiteSpace = "pre-wrap";
                            expTd.style.wordBreak = "break-all";
                            expTd.style.fontFamily = "monospace";
                            expTd.textContent = keys;
                            expRow.appendChild(expTd);
                            row.after(expRow);
                            state.expandedKeystrokeIndex = idx;
                        }
                    });
                }
                tbody.appendChild(row);
            });

            if (state.expandedKeystrokeIndex != null && state.expandedKeystrokeIndex < items.length && (items[state.expandedKeystrokeIndex].keys || items[state.expandedKeystrokeIndex].key_data || "").length > 80) {
                const row = tbody.querySelector(`tr[data-keystroke-index="${state.expandedKeystrokeIndex}"]`);
                if (row) {
                    const keys = formatKeystrokesForDisplay(items[state.expandedKeystrokeIndex].keys || items[state.expandedKeystrokeIndex].key_data || "");
                    const expRow = document.createElement("tr");
                    expRow.classList.add("expanded-content");
                    const expTd = document.createElement("td");
                    expTd.colSpan = 4;
                    expTd.className = "expanded-content";
                    expTd.style.whiteSpace = "pre-wrap";
                    expTd.style.wordBreak = "break-all";
                    expTd.style.fontFamily = "monospace";
                    expTd.textContent = keys;
                    expRow.appendChild(expTd);
                    row.after(expRow);
                }
            }

            renderPagination(pag, page, totalPages, (p) => {
                state.pages.keystrokes = p;
                state.expandedKeystrokeIndex = null;
                fetchKeystrokes();
            });
        } catch (_) {
            tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted)">Failed to load keystrokes.</td></tr>';
        }
    }

    // ── Activities ─────────────────────────────────────────
    function _calcDurationSec(startIso, endIso) {
        try {
            return Math.max(0, Math.round((new Date(endIso) - new Date(startIso)) / 1000));
        } catch (_) { return 0; }
    }

    async function fetchActivities() {
        const tbody = $("#activities-body");
        const pag = $("#activities-pagination");
        const barsContainer = $("#app-usage-bars");
        if (!state.isBackgroundRefresh) {
            tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text-muted)">Loading...</td></tr>';
            pag.innerHTML = "";
            barsContainer.innerHTML = "";
        }
        try {
            const page = state.pages.activities;
            const data = await api("GET",
                `/api/admin/activities?user_id=${state.selectedUserId}&date=${state.selectedDate}&page=${page}&limit=50`);
            const items = data.items || [];
            const total = data.total || items.length;
            const totalPages = data.total_pages || Math.ceil(total / 50) || 1;

            tbody.innerHTML = "";
            if (items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text-muted)">No activity data.</td></tr>';
                return;
            }

            const appTotals = {};
            let grandTotal = 0;
            items.forEach((item) => {
                const proc = item.process_name || "Unknown";
                const dur = _calcDurationSec(item.started_at, item.ended_at);
                appTotals[proc] = (appTotals[proc] || 0) + dur;
                grandTotal += dur;
            });

            barsContainer.innerHTML = "";
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
                const start = _fmtTime(item.started_at);
                const end = _fmtTime(item.ended_at);
                const dur = _calcDurationSec(item.started_at, item.ended_at);
                const proc = item.process_name || "";
                const win = item.window_title || "";
                const url = item.url || "";
                const detail = url || win;

                const row = document.createElement("tr");
                row.innerHTML =
                    `<td>${escapeHtml(start)}</td>` +
                    `<td>${escapeHtml(end)}</td>` +
                    `<td>${escapeHtml(formatDuration(dur))}</td>` +
                    `<td>${escapeHtml(proc)}</td>` +
                    `<td title="${escapeHtml(win + (url ? ' | ' + url : ''))}">${escapeHtml(truncate(detail, 50))}</td>`;
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
        if (!state.isBackgroundRefresh) {
            tbody.innerHTML = '<tr><td colspan="3" style="color:var(--text-muted)">Loading...</td></tr>';
            pag.innerHTML = "";
            alertSection.classList.add("hidden");
            alertList.innerHTML = "";
        }

        try {
            const page = state.pages.events;
            const data = await api("GET",
                `/api/admin/events?user_id=${state.selectedUserId}&date=${state.selectedDate}&page=${page}&limit=50`);
            const items = data.items || [];
            const total = data.total || items.length;
            const totalPages = data.total_pages || Math.ceil(total / 50) || 1;

            tbody.innerHTML = "";
            if (items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="3" style="color:var(--text-muted)">No events.</td></tr>';
                return;
            }

            const alerts = items.filter(ev => {
                const t = (ev.event_type || "").toLowerCase();
                return t.includes("kill") || t.includes("crash") || t.includes("app_stop");
            });
            alertList.innerHTML = "";
            if (alerts.length > 0) {
                alertSection.classList.remove("hidden");
                alerts.forEach((ev) => {
                    const div = document.createElement("div");
                    div.className = "alert-event-item";
                    div.innerHTML =
                        `<span class="alert-event-time">${escapeHtml(_fmtTime(ev.timestamp))}</span>` +
                        `<span class="alert-event-type">${escapeHtml(ev.event_type || "")}</span>` +
                        `<span class="alert-event-detail">${escapeHtml(ev.details || "")}</span>`;
                    alertList.appendChild(div);
                });
            } else {
                alertSection.classList.add("hidden");
            }

            items.forEach((item) => {
                const time = _fmtTime(item.timestamp);
                const evType = item.event_type || "";
                const details = item.details || "";
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
        const imgUrl = item.image_path || item.url || "";
        const capturedAt = item.captured_at || "";
        const time = capturedAt.includes("T") ? capturedAt.split("T")[1].substring(0, 8) : (item.time || "");
        const proc = item.active_process || item.process || "";
        const trigger = item.trigger || "";
        const monitor = item.monitor_index != null ? item.monitor_index : "--";
        const url = item.active_url || "";
        const pg = state.pages.screenshots;
        const tp = state.lightboxTotalPages;

        $("#lightbox-img").src = imgUrl;
        $("#lightbox-meta").innerHTML =
            `<span><span class="label">Page:</span> ${pg}/${tp} &middot; ${state.lightboxIndex + 1}/${state.lightboxImages.length}</span>` +
            `<span><span class="label">Time:</span> ${escapeHtml(time)}</span>` +
            `<span><span class="label">Monitor:</span> ${monitor}</span>` +
            `<span><span class="label">Process:</span> ${escapeHtml(proc)}</span>` +
            (url ? `<span><span class="label">URL:</span> ${escapeHtml(truncate(url, 40))}</span>` : "") +
            (trigger ? `<span><span class="label">Trigger:</span> ${escapeHtml(trigger)}</span>` : "");
    }

    async function _lightboxFetchPage(page) {
        if (state.lightboxLoading) return false;
        state.lightboxLoading = true;
        try {
            const data = await api("GET",
                `/api/admin/screenshots?user_id=${state.selectedUserId}&date=${state.selectedDate}&page=${page}&limit=20`);
            const items = data.items || [];
            if (items.length === 0) return false;
            state.pages.screenshots = page;
            state.lightboxImages = items;
            state.lightboxTotalPages = data.total_pages || Math.ceil((data.total || items.length) / 20) || 1;
            return true;
        } catch (_) {
            return false;
        } finally {
            state.lightboxLoading = false;
        }
    }

    async function lightboxPrev() {
        if (state.lightboxLoading) return;
        if (state.lightboxIndex > 0) {
            state.lightboxIndex--;
            renderLightbox();
        } else if (state.pages.screenshots > 1) {
            const loaded = await _lightboxFetchPage(state.pages.screenshots - 1);
            if (loaded) {
                state.lightboxIndex = state.lightboxImages.length - 1;
                renderLightbox();
            }
        }
    }

    async function lightboxNext() {
        if (state.lightboxLoading) return;
        if (state.lightboxIndex < state.lightboxImages.length - 1) {
            state.lightboxIndex++;
            renderLightbox();
        } else if (state.pages.screenshots < state.lightboxTotalPages) {
            const loaded = await _lightboxFetchPage(state.pages.screenshots + 1);
            if (loaded) {
                state.lightboxIndex = 0;
                renderLightbox();
            }
        }
    }

    function initLightbox() {
        $("#lightbox-close-btn").addEventListener("click", closeLightbox);
        $("#lightbox").addEventListener("click", (e) => {
            if (e.target === $("#lightbox")) closeLightbox();
        });
        $("#lightbox-prev-btn").addEventListener("click", lightboxPrev);
        $("#lightbox-next-btn").addEventListener("click", lightboxNext);
        document.addEventListener("keydown", (e) => {
            if ($("#lightbox").classList.contains("hidden")) return;
            if (e.key === "Escape") closeLightbox();
            if (e.key === "ArrowLeft") lightboxPrev();
            if (e.key === "ArrowRight") lightboxNext();
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
