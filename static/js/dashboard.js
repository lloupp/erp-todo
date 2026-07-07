// Dashboard — Residentes & Doutorandos (Observership removido: modulo desativado no ERP).
document.addEventListener('DOMContentLoaded', () => {
    loadTheme();
    loadDashboard();
});

// ── Tema ──────────────────────────────────────────────────────
function loadTheme() {
    document.documentElement.setAttribute('data-theme', localStorage.getItem('theme') || 'light');
}
function toggleTheme() {
    const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    loadDashboard(document.getElementById('dash-mes-filtro')?.value || '');
}
function toggleSidebar() {
    document.getElementById('sidebar')?.classList.toggle('open');
}

// ── Período ───────────────────────────────────────────────────
function trocarPeriodo(mes) { loadDashboard(mes); }

// ── Utilitários ───────────────────────────────────────────────
const fmtBRL = v => 'R$ ' + Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtDate = s => { if (!s) return '-'; const p = s.split(/[T ]/)[0].split('-'); return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : s; };

function isDark() { return document.documentElement.getAttribute('data-theme') === 'dark'; }
function chartColors() {
    return {
        text: isDark() ? '#f9fafb' : '#1f2937',
        grid: isDark() ? '#374151' : '#e5e7eb',
        surface: isDark() ? '#1f2937' : '#ffffff',
    };
}

// Destrói canvas e recria (evita "Canvas is already in use" ao re-renderizar)
function resetCanvas(id) {
    const old = document.getElementById(id);
    if (!old) return null;
    const clone = document.createElement('canvas');
    clone.id = id;
    old.parentNode.replaceChild(clone, old);
    return clone;
}

// ── Cores fixas por categoria ─────────────────────────────────
const COR_RES_STATUS = {
    'Interessado': '#3b82f6', 'Em andamento': '#f59e0b', 'Deferido': '#8b5cf6',
    'Confirmado': '#22c55e', 'Indeferido': '#ef4444', 'Cancelado': '#6b7280',
    'Desistente': '#f97316', 'Trocado': '#06b6d4', 'Nao veio': '#d1d5db',
};
const PAG_COR = { 'Pago': '#22c55e', 'Pendente': '#f59e0b', 'Isento': '#8b5cf6', 'Cancelado': '#ef4444' };
const PALETTE = ['#3b82f6','#6d28d9','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#f97316','#ec4899','#84cc16'];

// ── Carga principal ───────────────────────────────────────────
async function loadDashboard(mes = '') {
    const url = '/api/dashboard' + (mes ? `?mes_ano=${encodeURIComponent(mes)}` : '');
    try {
        const r = await fetch(url);
        if (!r.ok) throw new Error(r.status);
        const d = await r.json();
        populateMesesFiltro(d.meses_disponiveis, mes);
        renderDashboard(d);
    } catch (e) {
        document.getElementById('dashboard-container').innerHTML =
            '<p class="empty-state">Erro ao carregar dashboard.</p>';
    }
}

function populateMesesFiltro(meses, atual) {
    const sel = document.getElementById('dash-mes-filtro');
    if (!sel) return;
    const opts = ['<option value="">Todos os períodos</option>'];
    (meses || []).forEach(m => {
        const sel_ = m === atual ? ' selected' : '';
        opts.push(`<option value="${m}"${sel_}>${m}</option>`);
    });
    sel.innerHTML = opts.join('');
}

// ── Render principal ──────────────────────────────────────────
function renderDashboard(d) {
    const K = d.kpis || {};
    const periodo = d.mes_filtro ? ` — ${d.mes_filtro}` : '';

    // ── KPI CARDS ─────────────────────────────────────────────
    const kpiCards = `
    <div class="dash-section-title">RESIDENTES & DOUTORANDOS${periodo}</div>
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#eff6ff;color:#1d4ed8">👥</div>
            <div class="kpi-body"><div class="kpi-val">${d.total || 0}</div><div class="kpi-label">Total</div></div>
        </div>
        <div class="kpi-card ${K.criticos > 0 ? 'kpi-danger' : ''}">
            <div class="kpi-icon" style="background:#fef2f2;color:#dc2626">⚠</div>
            <div class="kpi-body"><div class="kpi-val">${K.criticos || 0}</div><div class="kpi-label">Críticos (+14d parado)</div></div>
        </div>
        <div class="kpi-card ${K.alertas > 0 ? 'kpi-warn' : ''}">
            <div class="kpi-icon" style="background:#fff7ed;color:#d97706">⚡</div>
            <div class="kpi-body"><div class="kpi-val">${K.alertas || 0}</div><div class="kpi-label">Alertas (7–14d parado)</div></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#eff6ff;color:#1d4ed8">🆕</div>
            <div class="kpi-body"><div class="kpi-val">${K.novos || 0}</div><div class="kpi-label">Interessados</div></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#fefce8;color:#854d0e">▶</div>
            <div class="kpi-body"><div class="kpi-val">${K.em_andamento || 0}</div><div class="kpi-label">Em andamento</div></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#eff6ff;color:#1e40af">✔</div>
            <div class="kpi-body"><div class="kpi-val">${K.deferidos || 0}</div><div class="kpi-label">Deferidos</div></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#f0fdf4;color:#166534">🎓</div>
            <div class="kpi-body"><div class="kpi-val">${K.confirmados || 0}</div><div class="kpi-label">Confirmados</div></div>
        </div>
        <div class="kpi-card ${K.pag_pendente > 0 ? 'kpi-warn' : ''}">
            <div class="kpi-icon" style="background:#fefce8;color:#854d0e">💰</div>
            <div class="kpi-body"><div class="kpi-val">${K.pag_pendente || 0}</div><div class="kpi-label">Pagto Pendente</div></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#f0fdf4;color:#166534">💵</div>
            <div class="kpi-body"><div class="kpi-val">${fmtBRL(d.financeiro?.pago)}</div><div class="kpi-label">Total Pago</div></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#fefce8;color:#854d0e">💸</div>
            <div class="kpi-body"><div class="kpi-val">${fmtBRL(d.financeiro?.pendente)}</div><div class="kpi-label">Valor Pendente</div></div>
        </div>
    </div>`;

    // ── GRAFICOS ROW 1: Donuts + Top especialidades ────────────
    const row1 = `
    <div class="charts-grid charts-grid-3">
        <div class="chart-card">
            <h3>Residentes por Status</h3>
            <div class="chart-canvas-wrap"><canvas id="chart-res-status"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>Residentes por Tipo</h3>
            <div class="chart-canvas-wrap"><canvas id="chart-res-tipo"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>Top Especialidades</h3>
            <div class="chart-canvas-wrap"><canvas id="chart-res-esp"></canvas></div>
        </div>
    </div>`;

    // ── GRAFICOS ROW 2: Tendência mensal ────────────────────────
    const row2 = `
    <div class="charts-grid">
        <div class="chart-card" style="grid-column: 1 / -1;">
            <h3>Tendência Mensal — Residentes</h3>
            <div class="chart-canvas-wrap" style="height:240px"><canvas id="chart-trend-res"></canvas></div>
        </div>
    </div>`;

    // ── RECENTES ───────────────────────────────────────────────
    const recRows = (d.recentes || []).map(r => `<tr>
        <td><strong>${r.nome}</strong></td>
        <td>${r.tipo || '—'}</td>
        <td>${r.especialidade || '—'}</td>
        <td><span style="font-weight:600;color:${COR_RES_STATUS[r.status] || 'inherit'}">${r.status || '—'}</span></td>
        <td><span style="color:${PAG_COR[r.status_pagamento] || 'inherit'};font-size:12px">${r.status_pagamento || '—'}</span></td>
        <td>${fmtDate(r.updated_at)}</td>
    </tr>`).join('');

    const rowRecentes = `
    <div class="chart-card" style="margin-bottom:32px">
        <h3>Residentes Atualizados Recentemente</h3>
        <table class="recent-table">
            <thead><tr><th>Nome</th><th>Tipo</th><th>Especialidade</th><th>Status</th><th>Pagto</th><th>Atualizado</th></tr></thead>
            <tbody>${recRows || '<tr><td colspan="6" class="empty-state">Sem registros</td></tr>'}</tbody>
        </table>
    </div>`;

    // ── Monta tudo ────────────────────────────────────────────
    document.getElementById('dashboard-container').innerHTML =
        kpiCards + row1 + row2 + rowRecentes;

    // ── Renderiza charts ──────────────────────────────────────
    renderCharts(d);
}

// ── Chart.js helpers ──────────────────────────────────────────
function baseOptions(extra = {}) {
    const cc = chartColors();
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { labels: { color: cc.text, font: { size: 12 } } },
        },
        ...extra,
    };
}

function donutChart(canvasId, labels, values, colors) {
    const cc = chartColors();
    const canvas = resetCanvas(canvasId);
    if (!canvas) return;
    new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{ data: values, backgroundColor: colors, borderWidth: 2, borderColor: cc.surface }],
        },
        options: baseOptions({
            cutout: '60%',
            plugins: {
                legend: { position: 'bottom', labels: { color: cc.text, boxWidth: 12, padding: 8, font: { size: 11 } } },
                tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed} (${((ctx.parsed / ctx.dataset.data.reduce((a, b) => a + b, 0)) * 100).toFixed(1)}%)` } },
            },
        }),
    });
}

function barChart(canvasId, labels, datasets, indexAxis = 'y') {
    const cc = chartColors();
    const canvas = resetCanvas(canvasId);
    if (!canvas) return;
    new Chart(canvas, {
        type: 'bar',
        data: { labels, datasets },
        options: baseOptions({
            indexAxis,
            scales: {
                x: { grid: { color: cc.grid }, ticks: { color: cc.text } },
                y: { grid: { color: cc.grid }, ticks: { color: cc.text, font: { size: 11 } } },
            },
            plugins: {
                legend: { display: datasets.length > 1, labels: { color: cc.text } },
            },
        }),
    });
}

function lineChart(canvasId, labels, datasets) {
    const cc = chartColors();
    const canvas = resetCanvas(canvasId);
    if (!canvas) return;
    new Chart(canvas, {
        type: 'line',
        data: { labels, datasets },
        options: baseOptions({
            scales: {
                x: { grid: { color: cc.grid }, ticks: { color: cc.text, maxTicksLimit: 12 } },
                y: { grid: { color: cc.grid }, ticks: { color: cc.text }, beginAtZero: true },
            },
            plugins: { legend: { display: datasets.length > 1, labels: { color: cc.text } } },
        }),
    });
}

function renderCharts(d) {
    // Donut: residentes por status
    if (d.por_status?.length) {
        donutChart('chart-res-status',
            d.por_status.map(x => x.status),
            d.por_status.map(x => x.count),
            d.por_status.map(x => COR_RES_STATUS[x.status] || '#9ca3af')
        );
    }

    // Donut: residentes por tipo
    if (d.por_tipo?.length) {
        donutChart('chart-res-tipo',
            d.por_tipo.map(x => x.tipo),
            d.por_tipo.map(x => x.count),
            d.por_tipo.map((_, i) => PALETTE[i % PALETTE.length])
        );
    }

    // Barra horizontal: top especialidades
    if (d.por_especialidade?.length) {
        const top = d.por_especialidade.slice(0, 10);
        barChart('chart-res-esp',
            top.map(x => x.nome),
            [{ label: 'Residentes', data: top.map(x => x.count), backgroundColor: '#3b82f6', borderRadius: 4 }],
            'y'
        );
    }

    // Linha: tendência mensal
    if (d.por_mes?.length) {
        const meses = [...d.por_mes].reverse();
        lineChart('chart-trend-res',
            meses.map(x => x.mes_ano),
            [{
                label: 'Qtd Residentes', data: meses.map(x => x.count),
                borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,.15)',
                fill: true, tension: 0.3, pointRadius: 4,
            }]
        );
    }
}
