document.addEventListener("DOMContentLoaded", () => {
    // Current active filter state
    let filterState = {
        start_date: "",
        end_date: "",
        platforms: [],
        genres: [],
        providers: [],
        channels: []
    };

    // Chart instances
    let platformChart = null;
    let playbackRatioChart = null;
    let trendChart = null;

    // Cache current overview data to handle metric toggle instantly
    let currentOverviewData = null;

    // DOM Elements
    const navItems = document.querySelectorAll(".nav-item");
    const tabContents = document.querySelectorAll(".tab-content");
    const toggleFiltersBtn = document.getElementById("toggle-filters-btn");
    const filterPanel = document.getElementById("filter-panel");
    
    // Filter Inputs
    const filterStartDate = document.getElementById("filter-start-date");
    const filterEndDate = document.getElementById("filter-end-date");
    const filterPlatform = document.getElementById("filter-platform");
    const filterGenre = document.getElementById("filter-genre");
    const filterProvider = document.getElementById("filter-provider");
    const btnResetFilters = document.getElementById("btn-reset-filters");
    const btnApplyFilters = document.getElementById("btn-apply-filters");
    const dataPeriodLabel = document.getElementById("data-period-label");

    // KPI Elements
    const kpiUsersTotal = document.getElementById("kpi-users-total");
    const kpiUsersActive15s = document.getElementById("kpi-users-active-15s");
    const kpiUsersActive15sRatio = document.getElementById("kpi-users-active-15s-ratio");
    const kpiUsersActive3m = document.getElementById("kpi-users-active-3m");
    const kpiUsersActive3mRatio = document.getElementById("kpi-users-active-3m-ratio");
    const kpiUsersActive15m = document.getElementById("kpi-users-active-15m");
    const kpiUsersActive15mRatio = document.getElementById("kpi-users-active-15m-ratio");
    const kpiVtTotal = document.getElementById("kpi-vt-total");
    const kpiPlaybacksTotal = document.getElementById("kpi-playbacks-total");

    // Average metrics Elements
    const avgVt15s = document.getElementById("avg-vt-15s");
    const avgVt15sDesc = document.getElementById("avg-vt-15s-desc");
    const avgVt3m = document.getElementById("avg-vt-3m");
    const avgVt3mDesc = document.getElementById("avg-vt-3m-desc");
    const avgVt15m = document.getElementById("avg-vt-15m");
    const avgVt15mDesc = document.getElementById("avg-vt-15m-desc");
    const avgVtTotal = document.getElementById("avg-vt-total");
    const avgPbPerUser = document.getElementById("avg-pb-per-user");
    const metricToggleSwitch = document.getElementById("metric-toggle-switch");
    const lblToggleActive = document.getElementById("lbl-toggle-active");
    const lblToggleTotal = document.getElementById("lbl-toggle-total");

    // Trends Selector
    const trendMetricSelector = document.getElementById("trend-metric-selector");

    // Rankings Table
    const rankingsSortSelector = document.getElementById("rankings-sort-selector");
    const rankingsTableBody = document.querySelector("#rankings-table tbody");

    // SQL Console
    const sqlQueryInput = document.getElementById("sql-query-input");
    const btnRunSql = document.getElementById("btn-run-sql");
    const sqlResultsArea = document.getElementById("sql-results-area");
    const sqlTmplBtns = document.querySelectorAll(".sql-tmpl-btn");

    /* ----------------------------------------------------
       1. ROUTING & TAB NAVIGATION
       ---------------------------------------------------- */
    function switchTab(targetHash) {
        // Update nav active class
        navItems.forEach(item => {
            if (item.getAttribute("href") === targetHash) {
                item.classList.add("active");
            } else {
                item.classList.remove("active");
            }
        });

        // Show correct tab content
        tabContents.forEach(content => {
            const contentId = `#${content.getAttribute("id")}`;
            if (contentId === targetHash) {
                content.classList.add("active");
            } else {
                content.classList.remove("active");
            }
        });

        // Trigger chart redraws if necessary when tabs change
        if (targetHash === "#trends-section") {
            loadTrends();
        } else if (targetHash === "#channels-section") {
            loadRankings();
        }
    }

    // Nav click events
    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const targetHash = item.getAttribute("href");
            window.location.hash = targetHash;
            switchTab(targetHash);
        });
    });

    // Handle initial hash routing
    if (window.location.hash) {
        switchTab(window.location.hash);
    }

    // Toggle filter panel visibility
    toggleFiltersBtn.addEventListener("click", () => {
        filterPanel.classList.toggle("hide");
        toggleFiltersBtn.classList.toggle("active");
    });

    /* ----------------------------------------------------
       2. METRIC TOGGLE: ACTIVE VS TOTAL
       ---------------------------------------------------- */
    metricToggleSwitch.addEventListener("change", () => {
        const isTotalUserMode = metricToggleSwitch.checked;
        
        if (isTotalUserMode) {
            lblToggleTotal.classList.add("active");
            lblToggleActive.classList.remove("active");
        } else {
            lblToggleActive.classList.add("active");
            lblToggleTotal.classList.remove("active");
        }
        
        updateAverageMetricsDisplay(isTotalUserMode);
    });

    function updateAverageMetricsDisplay(isTotalUserMode) {
        if (!currentOverviewData) return;
        
        const vt = currentOverviewData.viewing_time;
        
        if (isTotalUserMode) {
            // Option 2: Efficiency (Viewing Hours per Total User)
            avgVt15s.innerText = `${vt.per_user_total_15s.toFixed(2)} h`;
            avgVt15sDesc.innerText = "전체 유입 사용자당 활성 시청시간 (>15초) (Hours)";

            avgVt3m.innerText = `${vt.per_user_total_3m.toFixed(2)} h`;
            avgVt3mDesc.innerText = "전체 유입 사용자당 활성 시청시간 (>3분) (Hours)";
            
            avgVt15m.innerText = `${vt.per_user_total_15m.toFixed(2)} h`;
            avgVt15mDesc.innerText = "전체 유입 사용자당 활성 시청시간 (>15분) (Hours)";
        } else {
            // Option 1: Engagement (Viewing Hours per Active User)
            avgVt15s.innerText = `${vt.per_user_active_15s.toFixed(2)} h`;
            avgVt15sDesc.innerText = "15초 이상 활성 시청자당 시청시간 (Hours)";

            avgVt3m.innerText = `${vt.per_user_active_3m.toFixed(2)} h`;
            avgVt3mDesc.innerText = "3분 이상 활성 시청자당 시청시간 (Hours)";
            
            avgVt15m.innerText = `${vt.per_user_active_15m.toFixed(2)} h`;
            avgVt15mDesc.innerText = "15분 이상 활성 시청자당 시청시간 (Hours)";
        }
    }

    /* ----------------------------------------------------
       3. FILTER LOADING & DATA FETCHING
       ---------------------------------------------------- */
    async function loadFilters() {
        try {
            const res = await fetch("/api/filters");
            const data = await res.json();
            
            // Set date inputs
            if (data.date_range) {
                filterStartDate.min = data.date_range.min;
                filterStartDate.max = data.date_range.max;
                filterStartDate.value = data.date_range.min;
                
                filterEndDate.min = data.date_range.min;
                filterEndDate.max = data.date_range.max;
                filterEndDate.value = data.date_range.max;
                
                filterState.start_date = data.date_range.min;
                filterState.end_date = data.date_range.max;
                
                dataPeriodLabel.innerText = `${formatDateString(data.date_range.min)} ~ ${formatDateString(data.date_range.max)}`;
            }

            // Populate multi-select options
            populateSelect(filterPlatform, data.platforms);
            populateSelect(filterGenre, data.genres);
            populateSelect(filterProvider, data.providers);
            
            // Trigger first data load
            refreshDashboardData();
        } catch (err) {
            console.error("Failed to load filters:", err);
        }
    }

    function populateSelect(selectEl, items) {
        selectEl.innerHTML = "";
        items.forEach(item => {
            const opt = document.createElement("option");
            opt.value = item;
            opt.textContent = item;
            selectEl.appendChild(opt);
        });
    }

    function getSelectedOptions(selectEl) {
        return Array.from(selectEl.selectedOptions).map(opt => opt.value);
    }

    // Format dates nicely
    function formatDateString(isoString) {
        if (!isoString) return "";
        const parts = isoString.split("-");
        return `${parts[0]}.${parts[1]}.${parts[2]}`;
    }

    // Apply Filter Click
    btnApplyFilters.addEventListener("click", () => {
        filterState.start_date = filterStartDate.value;
        filterState.end_date = filterEndDate.value;
        filterState.platforms = getSelectedOptions(filterPlatform);
        filterState.genres = getSelectedOptions(filterGenre);
        filterState.providers = getSelectedOptions(filterProvider);
        
        dataPeriodLabel.innerText = `${formatDateString(filterState.start_date)} ~ ${formatDateString(filterState.end_date)}`;
        
        refreshDashboardData();
        
        // Hide panel
        filterPanel.classList.add("hide");
        toggleFiltersBtn.classList.remove("active");
    });

    // Reset Filters
    btnResetFilters.addEventListener("click", () => {
        filterStartDate.value = filterStartDate.min;
        filterEndDate.value = filterEndDate.max;
        
        Array.from(filterPlatform.options).forEach(opt => opt.selected = false);
        Array.from(filterGenre.options).forEach(opt => opt.selected = false);
        Array.from(filterProvider.options).forEach(opt => opt.selected = false);
        
        filterState = {
            start_date: filterStartDate.min,
            end_date: filterEndDate.max,
            platforms: [],
            genres: [],
            providers: [],
            channels: []
        };
        
        dataPeriodLabel.innerText = `${formatDateString(filterState.start_date)} ~ ${formatDateString(filterState.end_date)}`;
        refreshDashboardData();
    });

    // Refresh everything
    function refreshDashboardData() {
        loadOverview();
        loadPlatformBreakdown();
        
        const currentHash = window.location.hash || "#overview-section";
        if (currentHash === "#trends-section") {
            loadTrends();
        } else if (currentHash === "#channels-section") {
            loadRankings();
        }
    }

    /* ----------------------------------------------------
       4. OVERVIEW STATS & CHARTS LOADING
       ---------------------------------------------------- */
    // Build query params string from state
    function buildQueryParams(state) {
        const params = new URLSearchParams();
        if (state.start_date) params.append("start_date", state.start_date);
        if (state.end_date) params.append("end_date", state.end_date);
        
        state.platforms.forEach(p => params.append("platform", p));
        state.genres.forEach(g => params.append("genre", g));
        state.providers.forEach(pr => params.append("provider", pr));
        state.channels.forEach(c => params.append("channel", c));
        
        return params.toString();
    }

    async function loadOverview() {
        try {
            const queryStr = buildQueryParams(filterState);
            const res = await fetch(`/api/overview?${queryStr}`);
            const data = await res.json();
            
            currentOverviewData = data;
            
            // Format numbers
            kpiUsersTotal.innerText = data.users.total.toLocaleString();
            kpiUsersActive15s.innerText = data.users.active_15s.toLocaleString();
            kpiUsersActive15sRatio.innerText = `비율: ${data.users.active_15s_ratio}%`;
            kpiUsersActive3m.innerText = data.users.active_3m.toLocaleString();
            kpiUsersActive3mRatio.innerText = `비율: ${data.users.active_3m_ratio}%`;
            kpiUsersActive15m.innerText = data.users.active_15m.toLocaleString();
            kpiUsersActive15mRatio.innerText = `비율: ${data.users.active_15m_ratio}%`;
            kpiVtTotal.innerText = data.viewing_time.total.toLocaleString();
            kpiPlaybacksTotal.innerText = data.playback.total.toLocaleString();
            
            // Standard user averages
            avgVtTotal.innerText = `${data.viewing_time.per_user_total.toFixed(2)} h`;
            avgPbPerUser.innerText = `${data.playback.playback_per_user.toFixed(1)} 회`;
            
            // Trigger display calculation
            updateAverageMetricsDisplay(metricToggleSwitch.checked);
            
            // Render Playback Ratio Chart
            renderPlaybackRatioChart(data.playback);
        } catch (err) {
            console.error("Failed to load overview data:", err);
        }
    }

    async function loadPlatformBreakdown() {
        try {
            const queryStr = buildQueryParams(filterState);
            const res = await fetch(`/api/platform-breakdown?${queryStr}`);
            const data = await res.json();
            
            renderPlatformChart(data);
        } catch (err) {
            console.error("Failed to load platform breakdown:", err);
        }
    }

    /* ----------------------------------------------------
       5. CHARTS RENDERING (Chart.js)
       ---------------------------------------------------- */
    // Helper to destroy existing chart instances
    function destroyChart(chartInstance) {
        if (chartInstance) {
            chartInstance.destroy();
        }
    }

    // Platform Doughnut Chart
    function renderPlatformChart(data) {
        destroyChart(platformChart);
        
        const labels = data.map(item => item.platform);
        const userCounts = data.map(item => item.users);
        
        const ctx = document.getElementById("platform-chart").getContext("2d");
        
        platformChart = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: labels,
                datasets: [{
                    data: userCounts,
                    backgroundColor: [
                        "#8b5cf6", // Purple
                        "#3b82f6", // Blue
                        "#10b981", // Emerald
                        "#f59e0b", // Amber
                        "#ec4899", // Pink
                        "#6366f1"  // Indigo
                    ],
                    borderWidth: 2,
                    borderColor: "#161622"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "right",
                        labels: {
                            color: "#9ca3af",
                            font: { family: "Outfit", size: 12 }
                        }
                    }
                },
                cutout: "70%"
            }
        });
    }

    // Playback breakdown Doughnut Chart
    function renderPlaybackRatioChart(playbackData) {
        destroyChart(playbackRatioChart);
        
        const total = playbackData.total;
        const active15s = playbackData.active_15s;
        const active3m = playbackData.active_3m;
        const active15m = playbackData.active_15m;
        
        const shortBounce = total - active15s;
        const active15sTo3m = active15s - active3m;
        const active3to15m = active3m - active15m;

        const ctx = document.getElementById("playback-ratio-chart").getContext("2d");
        
        playbackRatioChart = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: ["15초 미만 초단기 이탈 (Bounce)", "15초 ~ 3분 시청", "3분 ~ 15분 시청", "15분 이상 장기 시청"],
                datasets: [{
                    data: [shortBounce, active15sTo3m, active3to15m, active15m],
                    backgroundColor: [
                        "#ef4444", // Red/Bounce
                        "#ec4899", // Pink
                        "#3b82f6", // Blue
                        "#10b981"  // Emerald
                    ],
                    borderWidth: 2,
                    borderColor: "#161622"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "right",
                        labels: {
                            color: "#9ca3af",
                            font: { family: "Outfit", size: 12 }
                        }
                    }
                },
                cutout: "70%"
            }
        });
    }

    /* ----------------------------------------------------
       6. DAILY TRENDS CHART
       ---------------------------------------------------- */
    trendMetricSelector.addEventListener("change", () => {
        loadTrends();
    });

    async function loadTrends() {
        try {
            const queryStr = buildQueryParams(filterState);
            const res = await fetch(`/api/trends?${queryStr}`);
            const data = await res.json();
            
            renderTrendChart(data);
        } catch (err) {
            console.error("Failed to load trend data:", err);
        }
    }

    function renderTrendChart(data) {
        destroyChart(trendChart);
        
        const dates = data.map(item => formatDateString(item.date));
        const selectedMetric = trendMetricSelector.value;
        const datasets = [];

        if (selectedMetric === "users") {
            datasets.push({
                label: "전체 사용자 (Total Users)",
                data: data.map(item => item.users),
                borderColor: "#8b5cf6",
                backgroundColor: "rgba(139, 92, 246, 0.05)",
                fill: true,
                tension: 0.3
            }, {
                label: "15초 이상 활성 사용자",
                data: data.map(item => item.active_users_15s),
                borderColor: "#ec4899",
                backgroundColor: "rgba(236, 72, 153, 0.05)",
                fill: true,
                tension: 0.3
            }, {
                label: "3분 이상 활성 사용자",
                data: data.map(item => item.active_users_3m),
                borderColor: "#10b981",
                backgroundColor: "rgba(16, 185, 129, 0.05)",
                fill: true,
                tension: 0.3
            }, {
                label: "15분 이상 활성 사용자",
                data: data.map(item => item.active_users_15m),
                borderColor: "#3b82f6",
                backgroundColor: "rgba(59, 130, 246, 0.05)",
                fill: true,
                tension: 0.3
            });
        } else if (selectedMetric === "viewing_time") {
            datasets.push({
                label: "총 시청 시간 (Hrs)",
                data: data.map(item => item.viewing_time),
                borderColor: "#3b82f6",
                backgroundColor: "rgba(59, 130, 246, 0.05)",
                fill: true,
                tension: 0.3
            }, {
                label: "15초 이상 시청 시간 (Hrs)",
                data: data.map(item => item.viewing_time_15s),
                borderColor: "#ec4899",
                backgroundColor: "rgba(236, 72, 153, 0.05)",
                fill: true,
                tension: 0.3
            }, {
                label: "3분 이상 시청 시간 (Hrs)",
                data: data.map(item => item.viewing_time_3m),
                borderColor: "#10b981",
                backgroundColor: "rgba(16, 185, 129, 0.05)",
                fill: true,
                tension: 0.3
            }, {
                label: "15분 이상 시청 시간 (Hrs)",
                data: data.map(item => item.viewing_time_15m),
                borderColor: "#f59e0b",
                backgroundColor: "rgba(245, 158, 11, 0.05)",
                fill: true,
                tension: 0.3
            });
        } else if (selectedMetric === "playbacks") {
            datasets.push({
                label: "총 재생 횟수 (Total Playbacks)",
                data: data.map(item => item.playbacks),
                borderColor: "#8b5cf6",
                backgroundColor: "rgba(139, 92, 246, 0.05)",
                fill: true,
                tension: 0.3
            }, {
                label: "15초 이상 재생 횟수",
                data: data.map(item => item.playbacks_15s),
                borderColor: "#ec4899",
                backgroundColor: "rgba(236, 72, 153, 0.05)",
                fill: true,
                tension: 0.3
            }, {
                label: "3분 이상 재생 횟수",
                data: data.map(item => item.playbacks_3m),
                borderColor: "#10b981",
                backgroundColor: "rgba(16, 185, 129, 0.05)",
                fill: true,
                tension: 0.3
            }, {
                label: "15분 이상 재생 횟수",
                data: data.map(item => item.playbacks_15m),
                borderColor: "#3b82f6",
                backgroundColor: "rgba(59, 130, 246, 0.05)",
                fill: true,
                tension: 0.3
            });
        }

        const ctx = document.getElementById("trend-line-chart").getContext("2d");
        
        trendChart = new Chart(ctx, {
            type: "line",
            data: {
                labels: dates,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: "#9ca3af",
                            font: { family: "Outfit", size: 12 }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: "rgba(255, 255, 255, 0.03)" },
                        ticks: { color: "#9ca3af", font: { family: "Outfit" } }
                    },
                    y: {
                        grid: { color: "rgba(255, 255, 255, 0.03)" },
                        ticks: { color: "#9ca3af", font: { family: "Outfit" } }
                    }
                }
            }
        });
    }

    /* ----------------------------------------------------
       7. CHANNEL RANKINGS TABLE
       ---------------------------------------------------- */
    rankingsSortSelector.addEventListener("change", () => {
        loadRankings();
    });

    async function loadRankings() {
        try {
            const sortBy = rankingsSortSelector.value;
            const queryStr = buildQueryParams(filterState);
            const res = await fetch(`/api/channel-rankings?sort_by=${sortBy}&limit=20&${queryStr}`);
            const data = await res.json();
            
            renderRankingsTable(data);
        } catch (err) {
            console.error("Failed to load rankings:", err);
        }
    }

    function renderRankingsTable(data) {
        rankingsTableBody.innerHTML = "";
        
        if (data.length === 0) {
            rankingsTableBody.innerHTML = `<tr><td colspan="12" style="text-align: center; color: var(--text-muted);">데이터가 없습니다. 필터를 조정해 보세요.</td></tr>`;
            return;
        }

        data.forEach(row => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${row.rank}</td>
                <td style="font-family: monospace; font-size: 13px;">${row.channel_id}</td>
                <td style="font-weight: 500;">${row.channel_name}</td>
                <td>${row.users.toLocaleString()}</td>
                <td>${row.active_users_15s.toLocaleString()}</td>
                <td>${row.active_users_3m.toLocaleString()}</td>
                <td>${row.viewing_time.toLocaleString()}</td>
                <td>${row.viewing_time_15s.toLocaleString()}</td>
                <td>${row.viewing_time_3m.toLocaleString()}</td>
                <td>${row.playbacks.toLocaleString()}</td>
                <td>${row.per_user_active_15s.toFixed(2)} h</td>
                <td>${row.per_user_active_3m.toFixed(2)} h</td>
            `;
            rankingsTableBody.appendChild(tr);
        });
    }

    /* ----------------------------------------------------
       8. READ-ONLY SQL QUERY EDITOR
       ---------------------------------------------------- */
    btnRunSql.addEventListener("click", () => {
        runCustomQuery();
    });

    sqlTmplBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            sqlQueryInput.value = btn.getAttribute("data-sql");
            runCustomQuery();
        });
    });

    async function runCustomQuery() {
        const query = sqlQueryInput.value.trim();
        if (!query) return;

        sqlResultsArea.innerHTML = `<p style="color: var(--text-secondary); text-align: center;"><i class="fa-solid fa-spinner fa-spin"></i> Running query on DuckDB...</p>`;
        
        try {
            const res = await fetch("/api/query", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: query })
            });
            
            const data = await res.json();
            
            if (!res.ok) {
                sqlResultsArea.innerHTML = `<div class="sql-error">[Error] ${data.detail}</div>`;
                return;
            }
            
            renderQueryResults(data);
        } catch (err) {
            sqlResultsArea.innerHTML = `<div class="sql-error">[Error] Connection failed: ${err.message}</div>`;
        }
    }

    function renderQueryResults(data) {
        if (data.row_count === 0) {
            sqlResultsArea.innerHTML = `<p style="color: var(--text-muted); text-align: center;">Query executed successfully. 0 rows returned.</p>`;
            return;
        }

        const table = document.createElement("table");
        table.className = "data-table";
        table.style.fontSize = "13px";

        // Table Header
        let thead = "<thead><tr>";
        data.columns.forEach(col => {
            thead += `<th>${col}</th>`;
        });
        thead += "</tr></thead>";

        // Table Body
        let tbody = "<tbody>";
        data.records.forEach(row => {
            tbody += "<tr>";
            data.columns.forEach(col => {
                let val = row[col];
                if (typeof val === "number") {
                    val = val.toLocaleString();
                }
                tbody += `<td>${val}</td>`;
            });
            tbody += "</tr>";
        });
        tbody += "</tbody>";

        table.innerHTML = thead + tbody;
        
        sqlResultsArea.innerHTML = "";
        
        const summary = document.createElement("div");
        summary.style.marginBottom = "12px";
        summary.style.fontSize = "12px";
        summary.style.color = "var(--text-secondary)";
        summary.innerHTML = `<span class="badge" style="background-color: var(--accent-emerald-glow); border-color: var(--accent-emerald); color: var(--accent-emerald);">${data.row_count} rows returned</span>`;
        
        const tableContainer = document.createElement("div");
        tableContainer.style.overflowX = "auto";
        tableContainer.appendChild(table);

        sqlResultsArea.appendChild(summary);
        sqlResultsArea.appendChild(tableContainer);
    }

    // Initialize the dashboard
    loadFilters();
});
