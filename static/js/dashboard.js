// Dashboard robusto — Estágios + Residentes, Chart.js, filtro de período.
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
const COR_TIPO = { 'Observership': '#6d28d9', 'Obrigatório': '#3b82f6', 'Optativo': '#10b981' };
const COR_RES_STATUS = {
    'Interessado': '#3b82f6', 'Em andamento': '#f59e0b', 'Deferido': '#8b5cf6',
    'Confirmado': '#22c55e', 'Indeferido': '#ef4444', 'Cancelado': '#6b7280',
    'Desistente': '#f97316', 'Trocado': '#06b6d4', 'Nao veio': '#d1d5db',
};
const COR_PAG = { 'Pago': '#22c55e', 'Pendente': '#f59e0b', 'Isento': '#8b5cf6', 'Interessado': '#3b82f6' };
const PALETTE = ['#6d28d9','#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#f97316','#ec4899','#84cc16'];

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
    const R = d.residentes || {};
    const KE = d.kpis_estagio || {};
    const KR = R.kpis || {};
    const periodo = d.mes_filtro ? ` — ${d.mes_filtro}` : '';

    // ── KPI CARDS ─────────────────────────────────────────────
    const kpiCards = `
    <div class="dash-section-title">OBSERVERSHIP${periodo}</div>
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#ede9fe;color:#6d28d9">📋</div>
            <div class="kpi-body"><div class="kpi-val">${d.total_estagios}</div><div class="kpi-label">Total Estágios</div></div>
        </div>
        <div class="kpi-card ${KE.criticos > 0 ? 'kpi-danger' : ''}">
            <div class="kpi-icon" style="background:#fef2f2;color:#dc2626">⚠</div>
            <div class="kpi-body"><div class="kpi-val">${KE.criticos}</div><div class="kpi-label">Críticos (+14d)</div></div>
        </div>
        <div class="kpi-card ${KE.alertas > 0 ? 'kpi-warn' : ''}">
            <div class="kpi-icon" style="background:#fff7ed;color:#d97706">⚡</div>
            <div class="kpi-body"><div class="kpi-val">${KE.alertas}</div><div class="kpi-label">Alertas (7–14d)</div></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#f0fdf4;color:#166534">✔</div>
            <div class="kpi-body"><div class="kpi-val">${KE.ativos}</div><div class="kpi-label">Em andamento</div></div>
        </div>
        <div class="kpi-card ${KE.pag_pendente > 0 ? 'kpi-warn' : ''}">
            <div class="kpi-icon" style="background:#fefce8;color:#854d0e">💰</div>
            <div class="kpi-body"><div class="kpi-val">${fmtBRL(d.valor_pendente)}</div><div class="kpi-label">Pagto Pendente</div></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#f0fdf4;color:#166534">💵</div>
            <div class="kpi-body"><div class="kpi-val">${fmtBRL(d.valor_pago)}</div><div class="kpi-label">Pago</div></div>
        </div>
    </div>
    <div class="dash-section-title" style="margin-top:8px">RESIDENTES & DOUTORANDOS${periodo}</div>
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#eff6ff;color:#1d4ed8">👥</div>
            <div class="kpi-body"><div class="kpi-val">${R.total || 0}</div><div class="kpi-label">Total Residentes</div></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#eff6ff;color:#1d4ed8">🆕</div>
            <div class="kpi-body"><div class="kpi-val">${KR.novos || 0}</div><div class="kpi-label">Interessados</div></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#fefce8;color:#854d0e">▶</div>
            <div class="kpi-body"><div class="kpi-val">${KR.em_andamento || 0}</div><div class="kpi-label">Em andamento</div></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#eff6ff;color:#1e40af">✔</div>
            <div class="kpi-body"><div class="kpi-val">${KR.deferidos || 0}</div><div class="kpi-label">Deferidos</div></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="background:#f0fdf4;color:#166534">🎓</div>
            <div class="kpi-body"><div class="kpi-val">${KR.confirmados || 0}</div><div class="kpi-label">Confirmados</div></div>
        </div>
        <div class="kpi-card ${KR.pag_pendente > 0 ? 'kpi-warn' : ''}">
            <div class="kpi-icon" style="background:#fefce8;color:#854d0e">💰</div>
            <div class="kpi-body"><div class="kpi-val">${KR.pag_pendente || 0}</div><div class="kpi-label">Pagto Pendente</div></div>
        </div>
    </div>`;

    // ── GRAFICOS ROW 1: Donuts ─────────────────────────────────
    const row1 = `
    <div class="charts-grid charts-grid-3">
        <div class="chart-card">
            <h3>Estágios por Tipo</h3>
            <div class="chart-canvas-wrap"><canvas id="chart-tipo"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>Status Pagamento (Estágios)</h3>
            <div class="chart-canvas-wrap"><canvas id="chart-pag"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>Residentes por Status</h3>
            <div class="chart-canvas-wrap"><canvas id="chart-res-status"></canvas></div>
        </div>
    </div>`;

    // ── GRAFICOS ROW 2: Barras ─────────────────────────────────
    const row2 = `
    <div class="charts-grid">
        <div class="chart-card">
            <h3>Estágios por Etapa (Observership em andamento)</h3>
            <div class="chart-canvas-wrap"><canvas id="chart-etapa"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>Top Especialidades — Residentes</h3>
            <div class="chart-canvas-wrap"><canvas id="chart-res-esp"></canvas></div>
        </div>
    </div>`;

    // ── GRAFICOS ROW 3: Tendências ─────────────────────────────
    const row3 = `
    <div class="charts-grid">
        <div class="chart-card">
            <h3>Tendência Mensal — Estágios</h3>
            <div class="chart-canvas-wrap" style="height:220px"><canvas id="chart-trend-est"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>Tendência Mensal — Residentes</h3>
            <div class="chart-canvas-wrap" style="height:220px"><canvas id="chart-trend-res"></canvas></div>
        </div>
    </div>`;

    // ── TOP ESPECIALIDADES ESTÁGIOS ────────────────────────────
    const maxEsp = Math.max(...(d.por_especialidade || []).map(x => x.count), 1);
    const espBars = (d.por_especialidade || []).slice(0, 10).map(e => `
        <div class="bar-item">
            <div class="bar-label">${e.nome || '—'}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${(e.count / maxEsp * 100).toFixed(0)}%;background:#6d28d9"></div></div>
            <div class="bar-count">${e.count}</div>
        </div>`).join('');

    const row4 = `
    <div class="charts-grid">
        <div class="chart-card">
            <h3>Top Especialidades — Estágios</h3>
            <div class="bar-list">${espBars || '<p class="empty-state">Sem dados</p>'}</div>
        </div>
        <div class="chart-card">
            <h3>Residentes por Tipo</h3>
            <div class="chart-canvas-wrap"><canvas id="chart-res-tipo"></canvas></div>
        </div>
    </div>`;

    // ── RECENTES ───────────────────────────────────────────────
    const PAG_COR = { 'Pago': '#22c55e', 'Pendente': '#f59e0b', 'Isento': '#8b5cf6', 'Interessado': '#3b82f6' };
    const recRows = (d.recentes || []).map(r => `<tr>
        <td><strong>${r.nome}</strong></td>
        <td>${r.tipo_nome}</td>
        <td>${r.especialidade || '—'}</td>
        <td><span style="font-weight:600">${r.etapa}</span></td>
        <td><span style="color:${PAG_COR[r.status_pagamento] || 'inherit'};font-size:12px">${r.status_pagamento || '—'}</span></td>
        <td>${fmtDate(r.updated_at)}</td>
    </tr>`).join('');

    const rowRecentes = `
    <div class="chart-card" style="margin-bottom:32px">
        <h3>Estágios Atualizados Recentemente</h3>
        <table class="recent-table">
            <thead><tr><th>Nome</th><th>Tipo</th><th>Especialidade</th><th>Etapa</th><th>Pagto</th><th>Atualizado</th></tr></thead>
            <tbody>${recRows || '<tr><td colspan="6" class="empty-state">Sem registros</td></tr>'}</tbody>
        </table>
    </div>`;

    // ── Monta tudo ────────────────────────────────────────────
    document.getElementById('dashboard-container').innerHTML =
        kpiCards + row1 + row2 + row3 + row4 + rowRecentes;

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
    const R = d.residentes || {};
    const cc = chartColors();

    // Donut: estágios por tipo
    if (d.por_tipo?.length) {
        donutChart('chart-tipo',
            d.por_tipo.map(x => x.nome),
            d.por_tipo.map(x => x.count),
            d.por_tipo.map(x => COR_TIPO[x.nome] || PALETTE[0])
        );
    }

    // Donut: pagamento estágios
    if (d.por_status_pagamento?.length) {
        donutChart('chart-pag',
            d.por_status_pagamento.map(x => x.status || 'N/A'),
            d.por_status_pagamento.map(x => x.count),
            d.por_status_pagamento.map(x => COR_PAG[x.status] || '#9ca3af')
        );
    }

    // Donut: residentes por status
    if (R.por_status?.length) {
        donutChart('chart-res-status',
            R.por_status.map(x => x.status),
            R.por_status.map(x => x.count),
            R.por_status.map(x => COR_RES_STATUS[x.status] || '#9ca3af')
        );
    }

    // Barra horizontal: etapas
    if (d.por_etapa?.length) {
        const ETAPAS = { 0: 'Verif. Vaga', 1: 'Venda', 2: 'Pagamento', 3: 'Docs Env.', 4: 'Docs Val.', 5: 'Vaga Conf.', 6: 'Orientação', 7: 'Concluído' };
        barChart('chart-etapa',
            d.por_etapa.map(x => ETAPAS[x.etapa] || `Etapa ${x.etapa}`),
            [{ label: 'Estágios', data: d.por_etapa.map(x => x.count), backgroundColor: d.por_etapa.map(x => x.etapa === 7 ? '#22c55e' : '#6d28d9'), borderRadius: 4 }],
            'y'
        );
    }

    // Barra horizontal: top especialidades residentes
    if (R.por_especialidade?.length) {
        const top = R.por_especialidade.slice(0, 10);
        barChart('chart-res-esp',
            top.map(x => x.nome),
            [{ label: 'Residentes', data: top.map(x => x.count), backgroundColor: '#3b82f6', borderRadius: 4 }],
            'y'
        );
    }

    // Linha: tendência mensal estágios
    if (d.por_mes?.length) {
        const meses = [...d.por_mes].reverse();
        lineChart('chart-trend-est',
            meses.map(x => x.mes_ano),
            [{
                label: 'Qtd Estágios', data: meses.map(x => x.count),
                borderColor: '#6d28d9', backgroundColor: 'rgba(109,40,217,.15)',
                fill: true, tension: 0.3, pointRadius: 4,
            }]
        );
    }

    // Linha: tendência mensal residentes
    if (R.por_mes?.length) {
        const meses = [...R.por_mes].reverse();
        lineChart('chart-trend-res',
            meses.map(x => x.mes_ano),
            [{
                label: 'Qtd Residentes', data: meses.map(x => x.count),
                borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,.15)',
                fill: true, tension: 0.3, pointRadius: 4,
            }]
        );
    }

    // Donut: residentes por tipo
    if (R.por_tipo?.length) {
        donutChart('chart-res-tipo',
            R.por_tipo.map(x => x.tipo),
            R.por_tipo.map(x => x.count),
            R.por_tipo.map((_, i) => PALETTE[i % PALETTE.length])
        );
    }
}
