// residentes.js — Módulo Residentes & Doutorandos

'use strict';

// ─── Estado ───────────────────────────────────────────────────
let currentPage = 1;
let idExcluir = null;
let debounceTimer = null;
let previewNovos = [];
let idAvancar = null;

const STATUS_FLOW = [
    'Interessado', 'Em andamento', 'Deferido', 'Confirmado'
];
const STATUS_TODOS = [
    'Interessado', 'Em andamento', 'Deferido', 'Confirmado',
    'Trocado', 'Indeferido', 'Desistente', 'Cancelado', 'Nao veio'
];

const STATUS_COLORS = {
    'Interessado':  '#6b7280',
    'Em andamento': '#f59e0b',
    'Deferido':     '#3b82f6',
    'Confirmado':   '#10b981',
    'Trocado':      '#06b6d4',
    'Indeferido':   '#dc2626',
    'Desistente':   '#9ca3af',
    'Cancelado':    '#ef4444',
    'Nao veio':     '#374151',
};

// ─── Init ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadTheme();
    loadUserInfo();
    loadEspecialidades();
    // Lê parâmetros da URL para pré-filtrar (vindo do banner de pendências)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('status')) {
        const el = document.getElementById('f-status');
        if (el) el.value = urlParams.get('status');
    }
    if (urlParams.get('pagamento')) {
        const el = document.getElementById('f-pagamento');
        if (el) el.value = urlParams.get('pagamento');
    }
    if (urlParams.get('tipo')) {
        const el = document.getElementById('f-tipo');
        if (el) el.value = urlParams.get('tipo');
    }
    loadResidentes();
    loadWelcomeBanner();
});

// ─── Tema / sidebar ───────────────────────────────────────────
function loadTheme() {
    const t = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', t);
}

function toggleTheme() {
    const cur = document.documentElement.getAttribute('data-theme') || 'light';
    const next = cur === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

// ─── Banner de pendências ─────────────────────────────────────
function saudacao() {
    const h = new Date().getHours();
    if (h < 12) return 'Bom dia';
    if (h < 18) return 'Boa tarde';
    return 'Boa noite';
}

async function loadWelcomeBanner() {
    try {
        const [me, p] = await Promise.all([
            apiFetch('/api/me'),
            apiFetch('/api/pendencias'),
        ]);
        renderWelcomeBanner(me.nome || 'Usuário', p);
    } catch (_) {}
}

function renderWelcomeBanner(nome, p) {
    const banner = document.getElementById('welcome-banner');
    if (!banner) return;

    const chips = [];

    if (p.res_novos > 0) {
        chips.push(`<span class="welcome-chip" style="background:#eff6ff;border:1px solid #bfdbfe;color:#1d4ed8;cursor:pointer"
            onclick="document.getElementById('f-status').value='Interessado';loadResidentes()">🆕 ${p.res_novos} nova(s) inscrição(ões)</span>`);
    }
    if (p.res_em_andamento > 0) {
        chips.push(`<span class="welcome-chip" style="background:#f0fdf4;border:1px solid #bbf7d0;color:#166534;cursor:pointer"
            onclick="document.getElementById('f-status').value='Em andamento';loadResidentes()">▶ ${p.res_em_andamento} em andamento</span>`);
    }
    if (p.res_deferidos > 0) {
        chips.push(`<span class="welcome-chip" style="background:#eff6ff;border:1px solid #93c5fd;color:#1e40af;cursor:pointer"
            onclick="document.getElementById('f-status').value='Deferido';loadResidentes()">✔ ${p.res_deferidos} deferido(s)</span>`);
    }
    if (p.res_pag_pendente > 0) {
        chips.push(`<span class="welcome-chip" style="background:#fefce8;border:1px solid #fde047;color:#854d0e;cursor:pointer"
            onclick="document.getElementById('f-pagamento').value='Pendente';loadResidentes()">💰 ${p.res_pag_pendente} pagamento(s) pendente(s)</span>`);
    }

    const semProblemas = p.res_novos === 0 && p.res_pag_pendente === 0;
    const extra = semProblemas ? ' Tudo em dia!' : '';

    banner.innerHTML = `
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:10px 16px;background:var(--color-surface);border:1px solid var(--color-border);border-radius:8px;">
            <span style="font-weight:600;color:var(--color-text);white-space:nowrap;">${saudacao()}, ${nome}!${extra}</span>
            ${chips.join('')}
        </div>`;
}

async function loadUserInfo() {
    try {
        const r = await apiFetch('/api/me');
        const el = document.getElementById('sidebar-user');
        if (el && r.nome) {
            el.innerHTML = `<strong>${r.nome}</strong><span>${r.role}</span>`;
        }
    } catch (_) {}
}

// ─── API helper ───────────────────────────────────────────────
async function apiFetch(url, opts = {}) {
    const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts });
    const ct = r.headers.get('Content-Type') || '';
    if (!r.ok) {
        const msg = ct.includes('json') ? (await r.json()).erro || r.statusText : r.statusText;
        showToast(msg, 'error');
        throw new Error(msg);
    }
    return ct.includes('json') ? r.json() : r.text();
}

// ─── Toast ────────────────────────────────────────────────────
function showToast(msg, type = 'info') {
    const c = document.getElementById('toast-container');
    const d = document.createElement('div');
    d.className = `toast toast-${type}`;
    d.style.cssText = `background:${type==='error'?'#dc2626':type==='success'?'#10b981':'#3b82f6'};color:#fff;padding:10px 16px;border-radius:8px;font-size:13px;box-shadow:0 4px 12px rgba(0,0,0,.2);max-width:320px;`;
    d.textContent = msg;
    c.appendChild(d);
    setTimeout(() => d.remove(), 4000);
}

// ─── Modal ────────────────────────────────────────────────────
function abrirModal(id) { document.getElementById(id).classList.add('open'); }
function fecharModal(id) { document.getElementById(id).classList.remove('open'); }

// ─── Especialidades para filtro ───────────────────────────────
async function loadEspecialidades() {
    try {
        const data = await apiFetch('/api/especialidades');
        const sel = document.getElementById('f-especialidade');
        (data.especialidades || []).forEach(e => {
            const o = document.createElement('option');
            o.value = e; o.textContent = e;
            sel.appendChild(o);
        });
    } catch (_) {}
}

// ─── Filtros ──────────────────────────────────────────────────
function getFiltros() {
    const p = {};
    const busca = document.getElementById('f-busca').value.trim();
    const tipo  = document.getElementById('f-tipo').value;
    const mod   = document.getElementById('f-modalidade').value;
    const esp   = document.getElementById('f-especialidade').value;
    const mes   = document.getElementById('f-mes').value;
    const stat  = document.getElementById('f-status').value;
    const pag   = document.getElementById('f-pagamento').value;
    if (busca) p.busca = busca;
    if (tipo)  p.tipo  = tipo;
    if (mod)   p.modalidade = mod;
    if (esp)   p.especialidade = esp;
    if (mes)   p.mes_ano = mes;
    if (stat)  p.status = stat;
    if (pag)   p.status_pagamento = pag;
    return p;
}

function limparFiltros() {
    ['f-busca','f-mes'].forEach(id => document.getElementById(id).value = '');
    ['f-tipo','f-modalidade','f-especialidade','f-status','f-pagamento'].forEach(id => document.getElementById(id).value = '');
    currentPage = 1;
    loadResidentes();
}

function debounceLoad() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => { currentPage = 1; loadResidentes(); }, 300);
}

// ─── Carregar lista ───────────────────────────────────────────
async function loadResidentes() {
    const filtros = getFiltros();
    const params = new URLSearchParams({ ...filtros, page: currentPage, per_page: 15 });
    try {
        const data = await apiFetch(`/api/residentes?${params}`);
        renderTabela(data.data || []);
        renderPaginacao(data.page, data.total_pages, data.total);
    } catch (_) {}
}

function renderTabela(rows) {
    const tbody = document.getElementById('tabela-residentes');
    const empty = document.getElementById('empty-state');
    if (!rows.length) {
        tbody.innerHTML = '';
        empty.style.display = 'block';
        return;
    }
    empty.style.display = 'none';
    tbody.innerHTML = rows.map(r => {
        const cor = STATUS_COLORS[r.status] || '#6b7280';
        const tipoCls = r.tipo === 'Doutorando' ? 'badge-Doutorando' : 'badge-Residente';
        const pagBadge = r.status_pagamento === 'Pago'
            ? '<span class="badge-pago">Pago</span>'
            : r.status_pagamento === 'Isento'
                ? '<span class="badge-isento">Isento</span>'
                : r.status_pagamento === 'Cancelado'
                    ? '<span class="badge-cancelado-pag">Cancelado</span>'
                    : '<span class="badge-pendente">Pendente</span>';
        const mesFormatado = r.mes_ano ? r.mes_ano.slice(0,7) : '—';
        return `<tr>
            <td><strong>${esc(r.nome)}</strong><br><small style="color:var(--color-text-secondary)">${esc(r.email||'')} ${r.telefone?'· '+esc(r.telefone):''}</small></td>
            <td><span class="badge-tipo ${tipoCls}">${esc(r.tipo)}</span><br><small>${esc(r.modalidade||'')}</small></td>
            <td>${esc(r.especialidade)}<br><small style="color:var(--color-text-secondary)">${esc(r.subespecialidade||'')}</small></td>
            <td>${esc(r.instituicao_origem||'—')}</td>
            <td style="white-space:nowrap;font-size:12px;">${esc(r.data_inscricao||'—')}</td>
            <td style="font-size:12px;">${esc(r.mes_desejado||'—')}</td>
            <td style="font-size:12px;">${esc(r.periodo_desejado||'—')}</td>
            <td>${mesFormatado}</td>
            <td><span class="badge-status" style="background:${cor}">${esc(r.status)}</span></td>
            <td>${pagBadge}${r.valor?`<br><small>R$ ${Number(r.valor).toFixed(2)}</small>`:''}</td>
            <td style="white-space:nowrap;">
                <button class="btn btn-sm btn-ghost" onclick="abrirHistorico(${r.id},'${esc(r.nome).replace(/'/g,"\\'")}')" title="Historico">&#9776;</button>
                ${proximoStatus(r.status) ? `<button class="btn btn-sm btn-primary" onclick="abrirModalAvancar(${r.id},'${esc(r.nome).replace(/'/g,"\\'")}','${esc(r.status)}')" title="Avançar status">&#9654;</button>` : ''}
                <button class="btn btn-sm btn-ghost" onclick="abrirModalEditar(${r.id})" title="Editar">&#9998;</button>
                <button class="btn btn-sm btn-danger" onclick="confirmarExclusao(${r.id}, '${esc(r.nome).replace(/'/g,"\\'")}')">&#128465;</button>
            </td>
        </tr>`;
    }).join('');
}

function renderPaginacao(page, totalPages, total) {
    const el = document.getElementById('paginacao');
    el.innerHTML = `
        <button onclick="mudarPag(${page-1})" ${page<=1?'disabled':''}>&#8249;</button>
        <span>Pagina ${page} de ${totalPages} &nbsp;|&nbsp; ${total} registro(s)</span>
        <button onclick="mudarPag(${page+1})" ${page>=totalPages?'disabled':''}>&#8250;</button>
    `;
}

function mudarPag(p) {
    currentPage = p;
    loadResidentes();
}

// ─── Criar / Editar ───────────────────────────────────────────
function abrirModalNovo() {
    document.getElementById('modal-titulo').textContent = 'Novo Residente / Doutorando';
    document.getElementById('form-id').value = '';
    ['form-nome','form-email','form-telefone','form-cpf','form-instituicao',
     'form-programa','form-especialidade','form-subesp','form-mes-ano',
     'form-inicio','form-termino','form-obs',
     'form-data-inscricao','form-periodo-desejado','form-mes-desejado'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('form-tipo').value = 'Residente';
    document.getElementById('form-modalidade').value = 'Optativo';
    document.getElementById('form-status').value = 'Interessado';
    document.getElementById('form-valor').value = '';
    document.getElementById('form-forma-pag').value = '';
    document.getElementById('form-status-pag').value = 'Pendente';
    document.getElementById('form-comprovante').value = '';
    abrirModal('modal-residente');
}

async function abrirModalEditar(id) {
    try {
        // Busca registro via lista completa (sem paginação de 1)
        const data = await apiFetch(`/api/residentes?page=1&per_page=1000`);
        const r = (data.data || []).find(x => x.id === id);
        if (!r) { showToast('Registro nao encontrado', 'error'); return; }

        document.getElementById('modal-titulo').textContent = 'Editar Residente / Doutorando';
        document.getElementById('form-id').value = r.id;
        document.getElementById('form-nome').value = r.nome || '';
        document.getElementById('form-email').value = r.email || '';
        document.getElementById('form-telefone').value = r.telefone || '';
        document.getElementById('form-cpf').value = r.cpf || '';
        document.getElementById('form-instituicao').value = r.instituicao_origem || '';
        document.getElementById('form-programa').value = r.programa_ano || '';
        document.getElementById('form-tipo').value = r.tipo || 'Residente';
        document.getElementById('form-modalidade').value = r.modalidade || 'Optativo';
        document.getElementById('form-especialidade').value = r.especialidade || '';
        document.getElementById('form-subesp').value = r.subespecialidade || '';
        document.getElementById('form-mes-ano').value = r.mes_ano ? r.mes_ano.slice(0,7) : '';
        document.getElementById('form-inicio').value = r.inicio || '';
        document.getElementById('form-termino').value = r.termino || '';
        document.getElementById('form-status').value = r.status || 'Interessado';
        document.getElementById('form-valor').value = r.valor != null ? r.valor : '';
        document.getElementById('form-forma-pag').value = r.forma_pagamento || '';
        document.getElementById('form-status-pag').value = r.status_pagamento || 'Pendente';
        document.getElementById('form-comprovante').value = r.comprovante_pagamento || '';
        document.getElementById('form-data-inscricao').value = r.data_inscricao || '';
        document.getElementById('form-periodo-desejado').value = r.periodo_desejado || '';
        document.getElementById('form-mes-desejado').value = r.mes_desejado || '';
        document.getElementById('form-obs').value = r.observacao || '';
        abrirModal('modal-residente');
    } catch (_) {}
}

async function salvarResidente() {
    const id = document.getElementById('form-id').value;
    const nome = document.getElementById('form-nome').value.trim();
    const especialidade = document.getElementById('form-especialidade').value.trim();
    const mes_ano = document.getElementById('form-mes-ano').value;

    if (!nome || !especialidade || !mes_ano) {
        showToast('Nome, especialidade e mes/ano sao obrigatorios', 'error');
        return;
    }

    const body = {
        nome,
        email: document.getElementById('form-email').value.trim(),
        telefone: document.getElementById('form-telefone').value.trim(),
        cpf: document.getElementById('form-cpf').value.trim(),
        tipo: document.getElementById('form-tipo').value,
        modalidade: document.getElementById('form-modalidade').value,
        especialidade,
        subespecialidade: document.getElementById('form-subesp').value.trim(),
        instituicao_origem: document.getElementById('form-instituicao').value.trim(),
        programa_ano: document.getElementById('form-programa').value.trim(),
        mes_ano,
        inicio: document.getElementById('form-inicio').value || null,
        termino: document.getElementById('form-termino').value || null,
        status: document.getElementById('form-status').value,
        valor: document.getElementById('form-valor').value ? Number(document.getElementById('form-valor').value) : null,
        forma_pagamento: document.getElementById('form-forma-pag').value || null,
        status_pagamento: document.getElementById('form-status-pag').value,
        comprovante_pagamento: document.getElementById('form-comprovante').value.trim() || null,
        data_inscricao: document.getElementById('form-data-inscricao').value.trim() || null,
        periodo_desejado: document.getElementById('form-periodo-desejado').value.trim() || null,
        mes_desejado: document.getElementById('form-mes-desejado').value.trim() || null,
        observacao: document.getElementById('form-obs').value.trim(),
    };

    try {
        if (id) {
            await apiFetch(`/api/residentes/${id}`, { method: 'PUT', body: JSON.stringify(body) });
            showToast('Registro atualizado com sucesso', 'success');
        } else {
            await apiFetch('/api/residentes', { method: 'POST', body: JSON.stringify(body) });
            showToast('Registro criado com sucesso', 'success');
        }
        fecharModal('modal-residente');
        loadResidentes();
    } catch (_) {}
}

// ─── Avançar Status ───────────────────────────────────────────
function proximoStatus(status) {
    const idx = STATUS_FLOW.indexOf(status);
    if (idx === -1 || idx === STATUS_FLOW.length - 1) return null;
    return STATUS_FLOW[idx + 1];
}

function abrirModalAvancar(id, nome, statusAtual) {
    idAvancar = id;
    const proximo = proximoStatus(statusAtual);

    document.getElementById('avancar-nome').textContent = nome;
    document.getElementById('avancar-status-atual').textContent = statusAtual;

    // Pré-seleciona o próximo status no flow, mas permite qualquer outro
    const sel = document.getElementById('avancar-novo-status');
    sel.value = proximo || statusAtual;

    document.getElementById('avancar-obs').value = '';
    abrirModal('modal-avancar');
}

async function confirmarAvancar() {
    if (!idAvancar) return;
    const novoStatus = document.getElementById('avancar-novo-status').value;
    const obs = document.getElementById('avancar-obs').value.trim();
    try {
        await apiFetch(`/api/residentes/${idAvancar}/avancar`, {
            method: 'POST',
            body: JSON.stringify({ status: novoStatus, observacao: obs }),
        });
        showToast(`Status atualizado para "${novoStatus}"`, 'success');
        fecharModal('modal-avancar');
        idAvancar = null;
        loadResidentes();
    } catch (_) {}
}

// ─── Histórico ────────────────────────────────────────────────
async function abrirHistorico(id, nome) {
    document.getElementById('hist-titulo').textContent = `Histórico — ${nome}`;
    document.getElementById('tbody-hist').innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--color-text-secondary)">Carregando...</td></tr>';
    abrirModal('modal-historico-res');
    try {
        const rows = await apiFetch(`/api/residentes/${id}/historico`);
        if (!rows.length) {
            document.getElementById('tbody-hist').innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--color-text-secondary)">Nenhum registro de historico.</td></tr>';
            return;
        }
        const cor = s => STATUS_COLORS[s] || '#6b7280';
        document.getElementById('tbody-hist').innerHTML = rows.map(r => {
            const dt = r.ts ? new Date(r.ts).toLocaleString('pt-BR') : '—';
            return `<tr>
                <td><span class="badge-status" style="background:${cor(r.status)};padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;color:#fff">${esc(r.status)}</span></td>
                <td>${esc(r.observacao || '—')}</td>
                <td>${esc(r.responsavel || '—')}</td>
                <td style="white-space:nowrap;font-size:12px;">${dt}</td>
            </tr>`;
        }).join('');
    } catch (_) {}
}

// ─── Excluir ──────────────────────────────────────────────────
function confirmarExclusao(id, nome) {
    idExcluir = id;
    document.getElementById('excluir-nome').textContent = nome;
    abrirModal('modal-excluir');
}

async function excluirResidente() {
    if (!idExcluir) return;
    try {
        await apiFetch(`/api/residentes/${idExcluir}`, { method: 'DELETE' });
        showToast('Registro excluido', 'success');
        fecharModal('modal-excluir');
        idExcluir = null;
        loadResidentes();
    } catch (_) {}
}

// ─── Exportar CSV ─────────────────────────────────────────────
function exportarCSV() {
    const filtros = getFiltros();
    const params = new URLSearchParams(filtros);
    window.location.href = `/api/residentes/exportar-csv?${params}`;
}

// ─── Importar Excel ───────────────────────────────────────────
function abrirModalImport() {
    document.getElementById('import-file').value = '';
    document.getElementById('import-status').textContent = '';
    document.getElementById('import-preview').innerHTML = '';
    document.getElementById('btn-confirmar-import').disabled = true;
    previewNovos = [];
    abrirModal('modal-import');
}

async function analisarArquivo() {
    const fileInput = document.getElementById('import-file');
    const tipo = document.getElementById('import-tipo').value;
    if (!fileInput.files.length) return;

    const statusEl = document.getElementById('import-status');
    const previewEl = document.getElementById('import-preview');
    const btnConfirmar = document.getElementById('btn-confirmar-import');
    statusEl.textContent = 'Analisando arquivo...';
    previewEl.innerHTML = '';
    btnConfirmar.disabled = true;
    previewNovos = [];

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        const r = await fetch(`/api/residentes/importar-excel?confirmar=0&tipo=${encodeURIComponent(tipo)}`, {
            method: 'POST',
            body: formData,
        });
        const data = await r.json();
        if (!r.ok) { showToast(data.erro || 'Erro ao analisar', 'error'); return; }

        previewNovos = data.preview || [];
        statusEl.innerHTML = `<strong>${data.total_planilha}</strong> registros na planilha &nbsp;|&nbsp; ` +
            `<strong style="color:#10b981">${data.novos}</strong> novos &nbsp;|&nbsp; ` +
            `<strong style="color:#f59e0b">${data.duplicados}</strong> ja existem (serao ignorados)`;

        if (previewNovos.length) {
            previewEl.innerHTML = `<p style="font-size:12px;margin-bottom:4px;">Preview (ate 30 registros):</p>
            <table>
                <thead><tr><th>Nome</th><th>Especialidade</th><th>Mes/Ano</th><th>Instituicao</th><th>Status</th></tr></thead>
                <tbody>${previewNovos.map(r => `<tr>
                    <td>${esc(r.nome)}</td>
                    <td>${esc(r.especialidade)}</td>
                    <td>${esc(r.mes_ano)}</td>
                    <td>${esc(r.instituicao_origem||'—')}</td>
                    <td>${esc(r.status)}</td>
                </tr>`).join('')}</tbody>
            </table>`;
            btnConfirmar.disabled = false;
        } else {
            previewEl.innerHTML = '<p style="color:#f59e0b;font-size:13px;">Nenhum registro novo para importar.</p>';
        }
    } catch (e) {
        showToast('Erro ao processar arquivo', 'error');
    }
}

async function confirmarImport() {
    const fileInput = document.getElementById('import-file');
    const tipo = document.getElementById('import-tipo').value;
    if (!fileInput.files.length) return;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        const r = await fetch(`/api/residentes/importar-excel?confirmar=1&tipo=${encodeURIComponent(tipo)}`, {
            method: 'POST',
            body: formData,
        });
        const data = await r.json();
        if (!r.ok) { showToast(data.erro || 'Erro ao importar', 'error'); return; }
        showToast(`${data.novos} registros importados com sucesso!`, 'success');
        fecharModal('modal-import');
        loadResidentes();
    } catch (e) {
        showToast('Erro ao importar', 'error');
    }
}

// ─── Utilitário ───────────────────────────────────────────────
function esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
