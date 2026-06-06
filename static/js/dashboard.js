document.addEventListener('DOMContentLoaded', async () => {
    loadTheme();
    await loadDashboard();
});

function loadTheme() {
    const t = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', t);
}

async function loadDashboard() {
    try {
        const r = await fetch('/api/dashboard');
        const d = await r.json();
        renderDashboard(d);
    } catch(e) {
        document.getElementById('dashboard-container').innerHTML = '<p class="empty-state">Erro ao carregar dashboard</p>';
    }
}

function renderDashboard(d) {
    const c = document.getElementById('dashboard-container');

    const formatBRL = (v) => 'R$ ' + Number(v).toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2});

    // Stats cards
    let html = `<div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">Total Estagios</div>
            <div class="stat-value">${d.total_estagios}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Valor Total</div>
            <div class="stat-value">${formatBRL(d.total_valor)}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Valor Pago</div>
            <div class="stat-value" style="color:var(--color-success)">${formatBRL(d.valor_pago)}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Valor Pendente</div>
            <div class="stat-value" style="color:var(--color-warning)">${formatBRL(d.valor_pendente)}</div>
        </div>
    </div>`;

    // Charts: by tipo and by especialidade
    const maxTipo = Math.max(...d.por_tipo.map(x => x.count), 1);
    const maxEsp = Math.max(...d.por_especialidade.map(x => x.count), 1);

    html += `<div class="charts-grid">
        <div class="chart-card">
            <h3>Por Tipo</h3>
            <div class="bar-list">
                ${d.por_tipo.map(t => `
                    <div class="bar-item">
                        <div class="bar-label">${t.nome}</div>
                        <div class="bar-track"><div class="bar-fill" style="width:${(t.count/maxTipo*100).toFixed(0)}%"></div></div>
                        <div class="bar-count">${t.count}</div>
                    </div>`).join('')}
            </div>
        </div>
        <div class="chart-card">
            <h3>Por Especialidade</h3>
            <div class="bar-list">
                ${d.por_especialidade.map(e => `
                    <div class="bar-item">
                        <div class="bar-label">${e.nome}</div>
                        <div class="bar-track"><div class="bar-fill" style="width:${(e.count/maxEsp*100).toFixed(0)}%;background:#8b5cf6"></div></div>
                        <div class="bar-count">${e.count}</div>
                    </div>`).join('')}
            </div>
        </div>
    </div>`;

    // By etapa
    const ETAPAS = {0:'Verif. Vaga',1:'Venda',2:'Pagamento',3:'Docs Env.',4:'Docs Val.',5:'Vaga Conf.',6:'Orient.',7:'Concluido'};
    const maxEtapa = Math.max(...d.por_etapa.map(x => x.count), 1);

    html += `<div class="charts-grid">
        <div class="chart-card">
            <h3>Por Etapa</h3>
            <div class="bar-list">
                ${d.por_etapa.map(e => `
                    <div class="bar-item">
                        <div class="bar-label">${ETAPAS[e.etapa] || 'Etapa ' + e.etapa}</div>
                        <div class="bar-track"><div class="bar-fill" style="width:${(e.count/maxEtapa*100).toFixed(0)}%;background:#10b981"></div></div>
                        <div class="bar-count">${e.count}</div>
                    </div>`).join('')}
            </div>
        </div>
        <div class="chart-card">
            <h3>Status Pagamento</h3>
            <div class="bar-list">
                ${d.por_status_pagamento.map(s => {
                    const color = s.status === 'Pago' ? '#22c55e' : s.status === 'Isento' ? '#8b5cf6' : '#f59e0b';
                    return `<div class="bar-item">
                        <div class="bar-label">${s.status || 'N/A'}</div>
                        <div class="bar-track"><div class="bar-fill" style="width:${d.total_estagios ? (s.count/d.total_estagios*100).toFixed(0) : 0}%;background:${color}"></div></div>
                        <div class="bar-count">${s.count} (${formatBRL(s.total)})</div>
                    </div>`;
                }).join('')}
            </div>
        </div>
    </div>`;

    // Recent
    html += `<div class="chart-card" style="margin-bottom:24px;">
        <h3>Atualizados Recentemente</h3>
        <table class="recent-table">
            <thead><tr><th>Nome</th><th>Tipo</th><th>Especialidade</th><th>Etapa</th><th>Atualizado</th></tr></thead>
            <tbody>
                ${d.recentes.map(r => `<tr>
                    <td><strong>${r.nome}</strong></td>
                    <td>${r.tipo_nome}</td>
                    <td>${r.especialidade}</td>
                    <td>${r.etapa}</td>
                    <td>${r.updated_at || '-'}</td>
                </tr>`).join('')}
            </tbody>
        </table>
    </div>`;

    c.innerHTML = html;
}
