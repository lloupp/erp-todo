const ETAPAS_OBS = {
    1: 'Venda realizada',
    2: 'Pagamento confirmado',
    3: 'Docs enviados',
    4: 'Docs validados',
    5: 'Vaga confirmada',
    6: 'Orientacoes enviadas',
    7: 'Concluido',
};

const ETAPAS_OBR_OPT = {
    0: 'Verificacao de vaga',
    1: 'Venda realizada',
    2: 'Pagamento confirmado',
    3: 'Docs enviados',
    4: 'Docs validados',
    5: 'Vaga confirmada',
    6: 'Orientacoes enviadas',
    7: 'Concluido',
};

const ETAPA_COLORS = {
    0: '#6b7280',
    1: '#f59e0b',
    2: '#3b82f6',
    3: '#8b5cf6',
    4: '#06b6d4',
    5: '#10b981',
    6: '#6366f1',
    7: '#22c55e',
};

const MESES = [
    'Janeiro', 'Fevereiro', 'Marco', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
];

let currentEstagioId = null;
let deleteEstagioId = null;
let tipos = [];
let debounceTimer = null;

function getEtapaNome(tipoId, etapa) {
    const map = tipoId === 1 ? ETAPAS_OBS : ETAPAS_OBR_OPT;
    return map[etapa] || 'Desconhecida';
}

function getEtapaMax(tipoId) {
    return 7;
}

function getEtapaMin(tipoId) {
    return tipoId === 1 ? 1 : 0;
}

function formatMesAno(mesAno) {
    if (!mesAno) return '';
    const [y, m] = mesAno.split('-');
    return MESES[parseInt(m, 10) - 1] + ' ' + y;
}

function formatCurrency(v) {
    if (v == null) return '-';
    return 'R$ ' + parseFloat(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(d) {
    if (!d) return '-';
    const parts = d.split('-');
    return parts[2] + '/' + parts[1] + '/' + parts[0];
}

function badgeHTML(tipoId, etapa) {
    const tipoNome = tipos.find(t => t.id === tipoId)?.nome || '';
    let tipoClass = 'badge-obs';
    if (tipoId === 2) tipoClass = 'badge-obr';
    if (tipoId === 3) tipoClass = 'badge-opt';
    const etapaNome = getEtapaNome(tipoId, etapa);
    const etapaColor = ETAPA_COLORS[etapa] || '#6b7280';
    return `<span class="badge badge-tipo ${tipoClass}">${tipoNome}</span> <span class="badge" style="background:${etapaColor}">${etapa} - ${etapaNome}</span>`;
}

async function apiFetch(url, options) {
    const resp = await fetch(url, options);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.erro || 'Erro na requisicao');
    }
    return resp;
}

function openModal(id) {
    document.getElementById(id).classList.add('active');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

async function loadTipos() {
    const resp = await fetch('/api/tipos');
    tipos = await resp.json();
    const sel = document.getElementById('est-tipo');
    sel.innerHTML = '<option value="">Selecione...</option>';
    const filtroTipo = document.getElementById('filtro-tipo');
    tipos.forEach(t => {
        sel.innerHTML += `<option value="${t.id}">${t.nome}</option>`;
        filtroTipo.innerHTML += `<option value="${t.id}">${t.nome}</option>`;
    });
}

async function loadEspecialidades() {
    const resp = await fetch('/api/especialidades');
    const list = await resp.json();
    const sel = document.getElementById('filtro-especialidade');
    sel.innerHTML = '<option value="">Todas</option>';
    list.forEach(e => {
        sel.innerHTML += `<option value="${e}">${e}</option>`;
    });
}

async function loadMeses() {
    const resp = await fetch('/api/meses');
    const list = await resp.json();
    const sel = document.getElementById('filtro-mes');
    sel.innerHTML = '<option value="">Todos</option>';
    list.forEach(m => {
        sel.innerHTML += `<option value="${m}">${formatMesAno(m)}</option>`;
    });
}

function loadEtapaFilter() {
    const sel = document.getElementById('filtro-etapa');
    sel.innerHTML = '<option value="">Todas</option>';
    sel.innerHTML += '<option value="0">0 - Verificacao de vaga</option>';
    for (let i = 1; i <= 7; i++) {
        sel.innerHTML += `<option value="${i}">${i} - ${ETAPAS_OBS[i]}</option>`;
    }
}

function getFilters() {
    return {
        tipo_id: document.getElementById('filtro-tipo').value,
        especialidade: document.getElementById('filtro-especialidade').value,
        etapa: document.getElementById('filtro-etapa').value,
        mes_ano: document.getElementById('filtro-mes').value,
        busca: document.getElementById('filtro-busca').value,
    };
}

async function loadEstagios() {
    const f = getFilters();
    const params = new URLSearchParams();
    if (f.tipo_id) params.set('tipo_id', f.tipo_id);
    if (f.especialidade) params.set('especialidade', f.especialidade);
    if (f.etapa !== '') params.set('etapa', f.etapa);
    if (f.mes_ano) params.set('mes_ano', f.mes_ano);
    if (f.busca) params.set('busca', f.busca);

    const resp = await fetch('/api/estagios?' + params.toString());
    const estagios = await resp.json();
    renderEstagios(estagios);
}

function renderEstagios(estagios) {
    const container = document.getElementById('estagios-container');

    if (estagios.length === 0) {
        container.innerHTML = '<p class="empty-state">Nenhum estagio encontrado.</p>';
        return;
    }

    const groups = {};
    estagios.forEach(e => {
        const key = e.mes_ano + '-S' + e.semana;
        if (!groups[key]) {
            groups[key] = { mes_ano: e.mes_ano, semana: e.semana, items: [] };
        }
        groups[key].items.push(e);
    });

    const sortedKeys = Object.keys(groups).sort((a, b) => b.localeCompare(a));

    let html = '';
    sortedKeys.forEach(key => {
        const g = groups[key];
        html += `<div class="group-header">${formatMesAno(g.mes_ano)} — Semana ${g.semana}</div>`;
        html += `<div class="table-wrapper"><table>
            <thead><tr>
                <th>Tipo / Etapa</th>
                <th>Nome</th>
                <th>Especialidade</th>
                <th>Cracha</th>
                <th>Valor</th>
                <th>Termino</th>
                <th>Email</th>
                <th>Telefone</th>
                <th>Docs</th>
                <th>Certificado</th>
                <th>Acoes</th>
            </tr></thead><tbody>`;

        g.items.forEach(e => {
            html += `<tr data-id="${e.id}">
                <td>${badgeHTML(e.tipo_id, e.etapa)}</td>
                <td class="nome-cell">${escHtml(e.nome)}</td>
                <td>${escHtml(e.especialidade)}</td>
                <td>${escHtml(e.cracha || '-')}</td>
                <td class="valor-cell">${formatCurrency(e.valor)}</td>
                <td>${formatDate(e.termino)}</td>
                <td>${escHtml(e.email || '-')}</td>
                <td>${escHtml(e.telefone || '-')}</td>
                <td>${escHtml(e.documentos || '-')}</td>
                <td>${formatDate(e.envio_certificado)}</td>
                <td class="actions-cell">
                    <button class="btn btn-sm btn-ghost" onclick="openHistorico(${e.id})" title="Historico">&#9776;</button>
                    <button class="btn btn-sm btn-primary" onclick="openEditModal(${e.id})" title="Editar">&#9998;</button>
                    <button class="btn btn-sm btn-danger" onclick="confirmDelete(${e.id})" title="Excluir">&times;</button>
                </td>
            </tr>`;
        });

        html += '</tbody></table></div>';
    });

    container.innerHTML = html;
}

function escHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}

function openCreateModal() {
    document.getElementById('modal-estagio-title').textContent = 'Novo Estagio';
    document.getElementById('estagio-id').value = '';
    document.getElementById('est-tipo').value = '';
    document.getElementById('est-mes-ano').value = '';
    document.getElementById('est-semana').value = '1';
    document.getElementById('est-nome').value = '';
    document.getElementById('est-especialidade').value = '';
    document.getElementById('est-cracha').value = '';
    document.getElementById('est-valor').value = '';
    document.getElementById('est-termino').value = '';
    document.getElementById('est-email').value = '';
    document.getElementById('est-telefone').value = '';
    document.getElementById('est-documentos').value = '';
    document.getElementById('est-certificado').value = '';
    document.getElementById('est-observacao').value = '';
    openModal('modal-estagio');
}

async function openEditModal(id) {
    const resp = await fetch('/api/estagios');
    const estagios = await resp.json();
    const e = estagios.find(x => x.id === id);
    if (!e) return;

    document.getElementById('modal-estagio-title').textContent = 'Editar Estagio';
    document.getElementById('estagio-id').value = e.id;
    document.getElementById('est-tipo').value = e.tipo_id;
    document.getElementById('est-mes-ano').value = e.mes_ano;
    document.getElementById('est-semana').value = e.semana;
    document.getElementById('est-nome').value = e.nome;
    document.getElementById('est-especialidade').value = e.especialidade;
    document.getElementById('est-cracha').value = e.cracha || '';
    document.getElementById('est-valor').value = e.valor || '';
    document.getElementById('est-termino').value = e.termino || '';
    document.getElementById('est-email').value = e.email || '';
    document.getElementById('est-telefone').value = e.telefone || '';
    document.getElementById('est-documentos').value = e.documentos || '';
    document.getElementById('est-certificado').value = e.envio_certificado || '';
    document.getElementById('est-observacao').value = e.observacao || '';
    openModal('modal-estagio');
}

async function saveEstagio() {
    const id = document.getElementById('estagio-id').value;
    const data = {
        tipo_id: parseInt(document.getElementById('est-tipo').value, 10),
        mes_ano: document.getElementById('est-mes-ano').value,
        semana: parseInt(document.getElementById('est-semana').value, 10),
        nome: document.getElementById('est-nome').value,
        especialidade: document.getElementById('est-especialidade').value,
        cracha: document.getElementById('est-cracha').value || null,
        valor: document.getElementById('est-valor').value || null,
        termino: document.getElementById('est-termino').value || null,
        email: document.getElementById('est-email').value || null,
        telefone: document.getElementById('est-telefone').value || null,
        documentos: document.getElementById('est-documentos').value || null,
        envio_certificado: document.getElementById('est-certificado').value || null,
        observacao: document.getElementById('est-observacao').value || null,
    };

    if (!data.tipo_id || !data.mes_ano || !data.nome || !data.especialidade) {
        alert('Preencha os campos obrigatorios: Tipo, Mes/Ano, Nome, Especialidade.');
        return;
    }

    try {
        if (id) {
            await apiFetch('/api/estagios/' + id, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
        } else {
            await apiFetch('/api/estagios', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
        }
        closeModal('modal-estagio');
        await loadEstagios();
        await loadEspecialidades();
        await loadMeses();
    } catch (err) {
        alert('Erro ao salvar: ' + err.message);
    }
}

function confirmDelete(id) {
    deleteEstagioId = id;
    openModal('modal-confirm');
    document.getElementById('btn-confirm-delete').onclick = async () => {
        try {
            await apiFetch('/api/estagios/' + deleteEstagioId, { method: 'DELETE' });
            closeModal('modal-confirm');
            await loadEstagios();
            await loadEspecialidades();
            await loadMeses();
        } catch (err) {
            alert('Erro ao excluir: ' + err.message);
        }
    };
}

async function openHistorico(id) {
    currentEstagioId = id;
    const resp = await fetch('/api/estagios');
    const estagios = await resp.json();
    const est = estagios.find(x => x.id === id);
    if (!est) return;

    document.getElementById('modal-historico-title').textContent = 'Historico — ' + est.nome;

    const histResp = await fetch('/api/estagios/' + id + '/historico');
    const historico = await histResp.json();

    const list = document.getElementById('historico-list');
    if (historico.length === 0) {
        list.innerHTML = '<p class="empty-state">Nenhum registro.</p>';
    } else {
        list.innerHTML = historico.map(h => {
            const etapaNome = getEtapaNome(est.tipo_id, h.etapa);
            const color = ETAPA_COLORS[h.etapa] || '#6b7280';
            return `<div class="historico-item">
                <div class="historico-dot" style="background:${color}"></div>
                <div class="historico-content">
                    <strong>${h.etapa} - ${etapaNome}</strong>
                    ${h.observacao ? '<p>' + escHtml(h.observacao) + '</p>' : ''}
                    <span>${h.responsavel || ''} — ${h.ts}</span>
                </div>
            </div>`;
        }).join('');
    }

    const maxEtapa = getEtapaMax(est.tipo_id);
    const btnAvancar = document.getElementById('btn-avancar');
    if (est.etapa >= maxEtapa) {
        btnAvancar.disabled = true;
        btnAvancar.textContent = 'Concluido';
    } else {
        btnAvancar.disabled = false;
        btnAvancar.textContent = 'Avancar para: ' + getEtapaNome(est.tipo_id, est.etapa + 1);
    }

    document.getElementById('avancar-responsavel').value = '';
    document.getElementById('avancar-obs').value = '';
    openModal('modal-historico');
}

async function avancarEtapa() {
    if (!currentEstagioId) return;
    const responsavel = document.getElementById('avancar-responsavel').value || 'Sistema';
    const obs = document.getElementById('avancar-obs').value || '';

    try {
        await apiFetch('/api/estagios/' + currentEstagioId + '/avancar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ responsavel, observacao: obs }),
        });
        await openHistorico(currentEstagioId);
        await loadEstagios();
    } catch (err) {
        alert('Erro ao avancar etapa: ' + err.message);
    }
}

function exportCSV() {
    const f = getFilters();
    const params = new URLSearchParams();
    if (f.tipo_id) params.set('tipo_id', f.tipo_id);
    if (f.especialidade) params.set('especialidade', f.especialidade);
    if (f.etapa !== '') params.set('etapa', f.etapa);
    if (f.mes_ano) params.set('mes_ano', f.mes_ano);
    if (f.busca) params.set('busca', f.busca);

    window.location.href = '/api/exportar-csv?' + params.toString();
}

function clearFilters() {
    document.getElementById('filtro-busca').value = '';
    document.getElementById('filtro-tipo').value = '';
    document.getElementById('filtro-especialidade').value = '';
    document.getElementById('filtro-etapa').value = '';
    document.getElementById('filtro-mes').value = '';
    loadEstagios();
}

function setupFilters() {
    const ids = ['filtro-busca', 'filtro-tipo', 'filtro-especialidade', 'filtro-etapa', 'filtro-mes'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(loadEstagios, 300);
        });
    });
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
        document.getElementById('sidebar').classList.remove('open');
    }
});

document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
        if (e.target === overlay) overlay.classList.remove('active');
    });
});

async function init() {
    await loadTipos();
    loadEtapaFilter();
    await loadEspecialidades();
    await loadMeses();
    setupFilters();
    await loadEstagios();
}

init();
