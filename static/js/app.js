/* ── Config ────────────────────────────────── */
const ETAPAS_OBS = {1:'Venda realizada',2:'Pagamento confirmado',3:'Docs enviados',4:'Docs validados',5:'Vaga confirmada',6:'Orientacoes enviadas',7:'Concluido'};
const ETAPAS_OBR = {0:'Verificacao de vaga',1:'Venda realizada',2:'Pagamento confirmado',3:'Docs enviados',4:'Docs validados',5:'Vaga confirmada',6:'Orientacoes enviadas',7:'Concluido'};
const ETAPA_COLORS = {0:'#6b7280',1:'#f59e0b',2:'#3b82f6',3:'#8b5cf6',4:'#06b6d4',5:'#10b981',6:'#6366f1',7:'#22c55e'};
const PER_PAGE = 15;

let currentPage = 1;
let totalPages = 1;
let totalItems = 0;

/* ── Init ─────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async () => {
    loadTheme();
    await loadUserInfo();
    await loadTipos();
    await loadFormasPagamento();
    await loadFiltros();
    loadEstagios();
    bindFilterEvents();
    bindCPFMask();
    bindTelefoneMask();
});

/* ── Theme ────────────────────────────────── */
function loadTheme() {
    const t = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', t);
}

function fmtDate(s) {
    if (!s) return '-';
    const d = s.split(/[T ]/)[0].split('-');
    return d.length === 3 ? `${d[2]}/${d[1]}/${d[0]}` : s;
}
function toggleTheme() {
    const cur = document.documentElement.getAttribute('data-theme');
    const next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
}

/* ── Sidebar ──────────────────────────────── */
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

/* ── User Info ────────────────────────────── */
async function loadUserInfo() {
 try {
 const r = await fetch('/api/me');
 if (r.ok) {
 const u = await r.json();
 const el = document.getElementById('sidebar-user');
 el.innerHTML = `<strong>${u.nome}</strong><span>${u.role}</span>`;
 // Mostrar link Usuarios so para admin
 const navUsers = document.getElementById('nav-usuarios');
 if (navUsers && u.role === 'admin') navUsers.style.display = '';
 const navVagas = document.getElementById('nav-vagas');
 if (navVagas && u.role === 'admin') navVagas.style.display = '';
 }
 } catch(e) { /* ignore */ }
}

/* ── Dropdowns ────────────────────────────── */
async function loadTipos() {
    const r = await fetch('/api/tipos');
    const tipos = await r.json();
    const sel = document.getElementById('filtro-tipo');
    const formSel = document.getElementById('form-tipo');
    tipos.forEach(t => {
        sel.innerHTML += `<option value="${t.id}">${t.nome}</option>`;
        formSel.innerHTML += `<option value="${t.id}">${t.nome}</option>`;
    });
}

async function loadFormasPagamento() {
    const r = await fetch('/api/formas-pagamento');
    const formas = await r.json();
    const sel = document.getElementById('form-forma-pag');
    sel.innerHTML = '<option value="">Selecione</option>';
    formas.forEach(f => { sel.innerHTML += `<option value="${f}">${f}</option>`; });
}

async function loadFiltros() {
    const [espR, mesR] = await Promise.all([fetch('/api/especialidades'), fetch('/api/meses')]);
    const esp = await espR.json();
    const mes = await mesR.json();
    const selEsp = document.getElementById('filtro-especialidade');
    const selMes = document.getElementById('filtro-mes');
    esp.forEach(e => { selEsp.innerHTML += `<option value="${e}">${e}</option>`; });
    mes.forEach(m => { selMes.innerHTML += `<option value="${m}">${m}</option>`; });
}

/* ── Filters ──────────────────────────────── */
function bindFilterEvents() {
    ['filtro-busca','filtro-tipo','filtro-especialidade','filtro-mes','filtro-semana','filtro-status-pag'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => {
            currentPage = 1;
            loadEstagios();
            carregarOcupacaoSemana();
        });
    });
}

function limparFiltros() {
    document.getElementById('filtro-busca').value = '';
    document.getElementById('filtro-tipo').value = '';
    document.getElementById('filtro-especialidade').value = '';
    document.getElementById('filtro-mes').value = '';
    const filSem = document.getElementById('filtro-semana');
    if (filSem) filSem.value = '';
    document.getElementById('filtro-status-pag').value = '';
    currentPage = 1;
    loadEstagios();
    carregarOcupacaoSemana();
}

function getFilterParams() {
    const p = new URLSearchParams();
    p.set('page', currentPage);
    p.set('per_page', PER_PAGE);
    const v = (id) => document.getElementById(id).value;
    if (v('filtro-busca')) p.set('busca', v('filtro-busca'));
    if (v('filtro-tipo')) p.set('tipo_id', v('filtro-tipo'));
    if (v('filtro-especialidade')) p.set('especialidade', v('filtro-especialidade'));
    if (v('filtro-mes')) p.set('mes_ano', v('filtro-mes'));
    const semEl = document.getElementById('filtro-semana');
    if (semEl && semEl.value) p.set('semana', semEl.value);
    if (v('filtro-status-pag')) p.set('status_pagamento', v('filtro-status-pag'));
    return p;
}

/* ── Load Estagios ────────────────────────── */
async function loadEstagios() {
    const r = await fetch(`/api/estagios?${getFilterParams()}`);
    const data = await r.json();
    const tbody = document.getElementById('tbody');
    tbody.innerHTML = '';

    if (data.data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" class="empty-state">Nenhum estagio encontrado</td></tr>';
    }

    data.data.forEach(e => {
        const tipoBadge = e.tipo_id === 1 ? 'badge-obs' : e.tipo_id === 2 ? 'badge-obr' : 'badge-opt';
        const etapas = e.tipo_id === 1 ? ETAPAS_OBS : ETAPAS_OBR;
        const minE = e.tipo_id === 1 ? 1 : 0;
        const etapaNome = etapas[e.etapa] || '';
        const etapaColor = ETAPA_COLORS[e.etapa] || '#6b7280';
        const dots = Array.from({length: 8 - minE}, (_, i) => {
            const step = minE + i;
            let cls = '';
            if (step < e.etapa) cls = 'filled';
            else if (step === e.etapa) cls = 'current';
            return `<span class="progress-dot ${cls}"></span>`;
        }).join('');

        const statusBadge = e.status_pagamento === 'Pago' ? 'background:#22c55e'
            : e.status_pagamento === 'Isento' ? 'background:#8b5cf6'
            : e.status_pagamento === 'Interessado' ? 'background:#6b7280'
            : 'background:#f59e0b';

        const dias = e.dias_na_etapa || 0;
        const alertaCor = (e.etapa < 7 && dias > 14) ? '#dc2626' : (e.etapa < 7 && dias > 7) ? '#f59e0b' : null;
        const alertaHtml = alertaCor
            ? `<span title="${dias} dias nesta etapa" style="color:${alertaCor};font-size:11px;font-weight:600;margin-left:4px;">&#9888; ${dias}d</span>`
            : '';

        tbody.innerHTML += `<tr>
            <td><span class="badge ${tipoBadge}">${e.tipo_nome}</span></td>
            <td><strong>${e.nome}</strong></td>
            <td>${e.cpf || '-'}</td>
            <td>${e.especialidade}</td>
            <td>${e.cracha || '-'}</td>
            <td>${fmtDate(e.inicio)}</td>
            <td>${fmtDate(e.termino)}</td>
            <td>${e.valor ? 'R$ ' + Number(e.valor).toFixed(2) : '-'}</td>
            <td><span class="badge" style="${statusBadge}">${e.status_pagamento || 'Interessado'}</span></td>
            <td>
                <div class="progress-bar">${dots}</div>
                <div style="font-size:10px;color:var(--color-text-muted);margin-top:2px;">${e.etapa} - ${etapaNome}${alertaHtml}</div>
            </td>
            <td style="white-space:nowrap;">
                <button class="btn-icon" title="Historico" onclick="verHistorico(${e.id},'${e.nome}')">&#9776;</button>
                <button class="btn-icon" title="Editar" onclick="editarEstagio(${e.id})">&#9998;</button>
                <button class="btn-icon" title="PDF" onclick="exportarPDF(${e.id})">&#128196;</button>
                <button class="btn-icon" title="Avancar etapa" onclick="avancarEtapa(${e.id},'${e.nome}')">&#10148;</button>
                <button class="btn-icon" title="Excluir" style="color:var(--color-danger);" onclick="confirmarExclusao(${e.id},'${e.nome}')">&#128465;</button>
            </td>
        </tr>`;
    });

    // Pagination
    totalItems = data.total;
    totalPages = data.total_pages;
    renderPagination();
}

/* ── Pagination ───────────────────────────── */
function renderPagination() {
    const info = document.getElementById('pagination-info');
    const controls = document.getElementById('pagination-controls');
    const start = (currentPage - 1) * PER_PAGE + 1;
    const end = Math.min(currentPage * PER_PAGE, totalItems);
    info.textContent = totalItems > 0 ? `Mostrando ${start}-${end} de ${totalItems}` : 'Nenhum resultado';

    controls.innerHTML = '';
    if (totalPages <= 1) return;

    // Prev
    controls.innerHTML += `<button class="page-btn" ${currentPage <= 1 ? 'disabled' : ''} onclick="goToPage(${currentPage-1})">&laquo;</button>`;

    // Pages
    const maxButtons = 7;
    let startPage = Math.max(1, currentPage - 3);
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);
    if (endPage - startPage < maxButtons - 1) startPage = Math.max(1, endPage - maxButtons + 1);

    for (let i = startPage; i <= endPage; i++) {
        controls.innerHTML += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
    }

    // Next
    controls.innerHTML += `<button class="page-btn" ${currentPage >= totalPages ? 'disabled' : ''} onclick="goToPage(${currentPage+1})">&raquo;</button>`;
}

function goToPage(p) {
    currentPage = p;
    loadEstagios();
    window.scrollTo(0, 0);
}

/* ── Modals ───────────────────────────────── */
function abrirModal(id) { document.getElementById(id).classList.add('open'); }
function fecharModal(id) { document.getElementById(id).classList.remove('open'); }

function abrirModalNovo() {
    document.getElementById('modal-form-title').textContent = 'Novo Estagio';
    document.getElementById('form-id').value = '';
    ['form-tipo','form-mes-ano','form-semana','form-nome','form-cpf','form-especialidade',
     'form-cracha','form-valor','form-forma-pag','form-status-pag','form-comprovante',
     'form-inicio','form-termino','form-email','form-telefone','form-documentos',
     'form-certificado','form-observacao'].forEach(id => {
        const el = document.getElementById(id);
        if (el.tagName === 'SELECT') el.selectedIndex = 0;
        else el.value = '';
    });
    document.getElementById('form-status-pag').value = 'Interessado';
    abrirModal('modal-form');
}

async function editarEstagio(id) {
    const r = await fetch(`/api/estagios?per_page=1`);
    // We need a single-item endpoint; fetch all and find
    const r2 = await fetch(`/api/estagios?per_page=1000`);
    const data = await r2.json();
    const e = data.data.find(x => x.id === id);
    if (!e) return;

    document.getElementById('modal-form-title').textContent = 'Editar Estagio';
    document.getElementById('form-id').value = e.id;
    document.getElementById('form-tipo').value = e.tipo_id;
    document.getElementById('form-mes-ano').value = e.mes_ano;
    document.getElementById('form-semana').value = e.semana;
    document.getElementById('form-nome').value = e.nome;
    document.getElementById('form-cpf').value = e.cpf || '';
    document.getElementById('form-especialidade').value = e.especialidade;
    document.getElementById('form-cracha').value = e.cracha || '';
    document.getElementById('form-valor').value = e.valor || '';
    document.getElementById('form-forma-pag').value = e.forma_pagamento || '';
    document.getElementById('form-status-pag').value = e.status_pagamento || 'Interessado';
    document.getElementById('form-comprovante').value = e.comprovante_pagamento || '';
    document.getElementById('form-inicio').value = e.inicio || '';
    document.getElementById('form-termino').value = e.termino || '';
    document.getElementById('form-email').value = e.email || '';
    document.getElementById('form-telefone').value = e.telefone || '';
    document.getElementById('form-documentos').value = e.documentos || '';
    document.getElementById('form-certificado').value = e.envio_certificado || '';
    document.getElementById('form-observacao').value = e.observacao || '';
    abrirModal('modal-form');
}

async function salvarEstagio() {
    const id = document.getElementById('form-id').value;
    const body = {
        tipo_id: parseInt(document.getElementById('form-tipo').value),
        mes_ano: document.getElementById('form-mes-ano').value,
        semana: parseInt(document.getElementById('form-semana').value),
        nome: document.getElementById('form-nome').value,
        cpf: document.getElementById('form-cpf').value,
        especialidade: document.getElementById('form-especialidade').value,
        cracha: document.getElementById('form-cracha').value,
        valor: parseFloat(document.getElementById('form-valor').value) || 0,
        forma_pagamento: document.getElementById('form-forma-pag').value,
        status_pagamento: document.getElementById('form-status-pag').value,
        comprovante_pagamento: document.getElementById('form-comprovante').value,
        inicio: document.getElementById('form-inicio').value,
        termino: document.getElementById('form-termino').value,
        email: document.getElementById('form-email').value,
        telefone: document.getElementById('form-telefone').value,
        documentos: document.getElementById('form-documentos').value,
        envio_certificado: document.getElementById('form-certificado').value,
        observacao: document.getElementById('form-observacao').value,
    };

    if (!body.nome || !body.especialidade || !body.mes_ano || !body.semana) {
        alert('Preencha os campos obrigatorios: Nome, Especialidade, Mes/Ano, Semana');
        return;
    }

    // Verificar limite de vagas (apenas para novos registros)
    if (!id && body.mes_ano && body.semana) {
        try {
            const rv = await fetch(`/api/vagas-semana?mes_ano=${encodeURIComponent(body.mes_ano)}&semana=${encodeURIComponent(body.semana)}`);
            if (rv.ok) {
                const vagas = await rv.json();
                const vaga = vagas.find(v => v.especialidade.toLowerCase() === body.especialidade.toLowerCase());
                if (vaga && vaga.usadas >= vaga.limite) {
                    const continuar = confirm(
                        `⚠ Limite atingido: ${vaga.especialidade} ja tem ${vaga.usadas}/${vaga.limite} vagas nesta semana.\n\nDeseja incluir mesmo assim?`
                    );
                    if (!continuar) return;
                }
            }
        } catch(e) { /* ignora erro de rede */ }
    }

    let r;
    if (id) {
        r = await fetch(`/api/estagios/${id}`, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
    } else {
        r = await fetch('/api/estagios', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
    }

    if (!r.ok) {
        const err = await r.json();
        alert(err.erro || 'Erro ao salvar');
        return;
    }

    fecharModal('modal-form');
    loadEstagios();
}

async function avancarEtapa(id, nome) {
    if (!confirm(`Avancar etapa de ${nome}?`)) return;
    const r = await fetch(`/api/estagios/${id}/avancar`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({}) });
    if (!r.ok) {
        const err = await r.json();
        alert(err.erro || 'Erro ao avancar');
        return;
    }
    loadEstagios();
}

async function verHistorico(id, nome) {
    document.getElementById('modal-historico-title').textContent = `Historico - ${nome}`;
    const r = await fetch(`/api/estagios/${id}/historico`);
    const hist = await r.json();
    const tbody = document.getElementById('tbody-historico');
    tbody.innerHTML = '';
    if (hist.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--color-text-muted);">Sem historico</td></tr>';
    }
    hist.forEach(h => {
        tbody.innerHTML += `<tr>
            <td><span class="badge" style="background:${ETAPA_COLORS[h.etapa] || '#6b7280'}">${h.etapa}</span></td>
            <td>${h.observacao || '-'}</td>
            <td>${h.responsavel || '-'}</td>
            <td>${h.ts || '-'}</td>
        </tr>`;
    });
    abrirModal('modal-historico');
}

let deleteId = null;
function confirmarExclusao(id, nome) {
    deleteId = id;
    document.getElementById('delete-msg').textContent = `Excluir estagio de "${nome}"? Esta acao nao pode ser desfeita.`;
    document.getElementById('btn-confirm-delete').onclick = async () => {
        await fetch(`/api/estagios/${deleteId}`, { method: 'DELETE' });
        fecharModal('modal-delete');
        loadEstagios();
    };
    abrirModal('modal-delete');
}

/* ── Export CSV ────────────────────────────── */
function exportarCSV() {
    const sep = document.getElementById('csv-separator').value;
    const params = getFilterParams();
    params.set('separador', sep);
    window.open(`/api/exportar-csv?${params}`, '_blank');
}

/* ── Export PDF ────────────────────────────── */
function exportarPDF(id) {
    window.open(`/api/estagios/${id}/pdf`, '_blank');
}

/* ── CPF Mask ─────────────────────────────── */
function bindCPFMask() {
    const el = document.getElementById('form-cpf');
    el.addEventListener('input', () => {
        let v = el.value.replace(/\D/g, '').slice(0, 11);
        if (v.length > 9) v = v.replace(/(\d{3})(\d{3})(\d{3})(\d{1,2})/, '$1.$2.$3-$4');
        else if (v.length > 6) v = v.replace(/(\d{3})(\d{3})(\d{1,3})/, '$1.$2.$3');
        else if (v.length > 3) v = v.replace(/(\d{3})(\d{1,3})/, '$1.$2');
        el.value = v;
    });
}

/* ── Telefone Mask ────────────────────────── */
function bindTelefoneMask() {
    const el = document.getElementById('form-telefone');
    el.addEventListener('input', () => {
        let v = el.value.replace(/\D/g, '').slice(0, 11);
        if (v.length > 6) v = v.replace(/(\d{2})(\d{5})(\d{1,4})/, '($1) $2-$3');
        else if (v.length > 2) v = v.replace(/(\d{2})(\d{1,5})/, '($1) $2');
        el.value = v;
    });
}

/* ── Importar Excel ───────────────────────── */
async function analisarXlsx() {
    const file = document.getElementById('import-file').files[0];
    if (!file) { alert('Selecione um arquivo .xlsx'); return; }

    const form = new FormData();
    form.append('arquivo', file);

    const preview = document.getElementById('import-preview');
    const btnConfirm = document.getElementById('btn-import-confirm');
    preview.innerHTML = '<p style="color:var(--color-text-muted);padding:8px 0;">Analisando...</p>';
    btnConfirm.style.display = 'none';

    const r = await fetch('/api/importar-excel?confirmar=0', { method: 'POST', body: form });
    const data = await r.json();
    if (data.erro) { preview.innerHTML = `<p style="color:#dc2626">${data.erro}</p>`; return; }

    // Seletor de abas
    let abaHtml = '';
    if (data.abas_disponiveis && data.abas_disponiveis.length > 1) {
        abaHtml = `<div style="margin-bottom:12px;padding:12px;background:var(--color-surface-hover);border-radius:6px;font-size:13px;">
            <div style="font-weight:600;margin-bottom:8px;">Abas a importar:</div>
            <div id="abas-check" style="display:flex;flex-wrap:wrap;gap:6px;">
            ${data.abas_disponiveis.map(a => `
                <label style="display:flex;align-items:center;gap:4px;cursor:pointer;padding:3px 8px;border:1px solid var(--color-border);border-radius:4px;font-size:12px;background:var(--color-bg);">
                    <input type="checkbox" name="aba" value="${a}" checked style="cursor:pointer;"> ${a}
                </label>`).join('')}
            </div>
            <button class="btn btn-sm" onclick="reaplicarFiltroAbas()" style="margin-top:8px;">Reanalisar seleção</button>
        </div>`;
    } else if (data.abas_disponiveis && data.abas_disponiveis.length === 1) {
        abaHtml = `<input type="hidden" name="aba" value="${data.abas_disponiveis[0]}" id="aba-unica">`;
    }

    let html = `${abaHtml}<div style="margin-bottom:12px;padding:12px;background:var(--color-surface-hover);border-radius:6px;font-size:13px;">
        <strong>${data.novos}</strong> novos &bull;
        <strong style="color:var(--color-text-muted)">${data.duplicados}</strong> ja existentes &bull;
        <strong>${data.total_planilha}</strong> total na planilha
    </div>`;

    if (data.preview && data.preview.length > 0) {
        html += `<div style="overflow-x:auto;max-height:280px;overflow-y:auto;border:1px solid var(--color-border);border-radius:6px;">
        <table style="width:100%;font-size:12px;border-collapse:collapse;">
        <thead style="background:var(--color-surface-hover);">
            <tr>
                <th style="padding:6px 10px;text-align:left;border-bottom:1px solid var(--color-border);">Nome</th>
                <th style="padding:6px 10px;text-align:left;border-bottom:1px solid var(--color-border);">Especialidade</th>
                <th style="padding:6px 10px;text-align:left;border-bottom:1px solid var(--color-border);">Mes/Ano</th>
                <th style="padding:6px 10px;text-align:left;border-bottom:1px solid var(--color-border);">Sem.</th>
                <th style="padding:6px 10px;text-align:left;border-bottom:1px solid var(--color-border);">Valor</th>
            </tr>
        </thead><tbody>`;
        data.preview.forEach(rec => {
            html += `<tr>
                <td style="padding:5px 10px;border-bottom:1px solid var(--color-border-light);">${rec.nome || '-'}</td>
                <td style="padding:5px 10px;border-bottom:1px solid var(--color-border-light);">${rec.especialidade || '-'}</td>
                <td style="padding:5px 10px;border-bottom:1px solid var(--color-border-light);">${rec.mes_ano || '-'}</td>
                <td style="padding:5px 10px;border-bottom:1px solid var(--color-border-light);">${rec.semana || '-'}</td>
                <td style="padding:5px 10px;border-bottom:1px solid var(--color-border-light);">${rec.valor ? 'R$ ' + Number(rec.valor).toFixed(2) : '-'}</td>
            </tr>`;
        });
        if (data.novos > 30) {
            html += `<tr><td colspan="5" style="text-align:center;padding:8px;color:var(--color-text-muted);">... e mais ${data.novos - 30} registros</td></tr>`;
        }
        html += '</tbody></table></div>';
    } else if (data.novos === 0) {
        html += '<p style="color:var(--color-text-muted);font-size:13px;">Nenhum registro novo encontrado — todos ja existem no sistema.</p>';
    }

    preview.innerHTML = html;
    if (data.novos > 0) btnConfirm.style.display = '';
}

/* ── Ocupacao semanal ─────────────────────── */
async function carregarOcupacaoSemana() {
    const mesAno = document.getElementById('filtro-mes').value;
    const semana = document.getElementById('filtro-semana') ? document.getElementById('filtro-semana').value : '';
    const painel = document.getElementById('painel-ocupacao');
    if (!painel) return;

    if (!mesAno || !semana) {
        painel.innerHTML = '';
        painel.style.display = 'none';
        return;
    }

    const r = await fetch(`/api/vagas-semana?mes_ano=${encodeURIComponent(mesAno)}&semana=${encodeURIComponent(semana)}`);
    if (!r.ok) return;
    const dados = await r.json();
    if (!dados.length) { painel.style.display = 'none'; return; }

    const linhas = dados.map(d => {
        const pct = Math.min(100, Math.round(d.usadas / d.limite * 100));
        const cor = d.usadas >= d.limite ? '#dc2626' : d.usadas >= d.limite * 0.75 ? '#f59e0b' : '#10b981';
        return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
            <span style="width:200px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${d.especialidade}">${d.especialidade}</span>
            <div style="flex:1;background:var(--color-border);border-radius:4px;height:8px;overflow:hidden;">
                <div style="width:${pct}%;background:${cor};height:100%;border-radius:4px;transition:width .3s;"></div>
            </div>
            <span style="font-size:12px;font-weight:600;color:${cor};white-space:nowrap;">${d.usadas}/${d.limite}</span>
        </div>`;
    }).join('');

    painel.style.display = 'block';
    painel.innerHTML = `<div style="font-size:12px;font-weight:600;color:var(--color-text-secondary);margin-bottom:8px;">Ocupacao — Semana ${semana} de ${mesAno}</div>${linhas}`;
}

function _abasSelecionadas() {
    const checks = document.querySelectorAll('#abas-check input[type=checkbox]:checked');
    return checks.length > 0 ? [...checks].map(c => c.value) : [];
}

async function reaplicarFiltroAbas() {
    const file = document.getElementById('import-file').files[0];
    if (!file) return;
    const form = new FormData();
    form.append('arquivo', file);
    _abasSelecionadas().forEach(a => form.append('abas', a));
    const preview = document.getElementById('import-preview');
    const btnConfirm = document.getElementById('btn-import-confirm');
    const stats = preview.querySelector('div:last-child');
    // Reanalisar apenas as estatísticas sem mudar o seletor de abas
    const r = await fetch('/api/importar-excel?confirmar=0', { method: 'POST', body: form });
    const data = await r.json();
    if (data.erro) { return; }
    if (stats) stats.innerHTML = `<strong>${data.novos}</strong> novos &bull; <strong style="color:var(--color-text-muted)">${data.duplicados}</strong> ja existentes &bull; <strong>${data.total_planilha}</strong> total nas abas selecionadas`;
    btnConfirm.style.display = data.novos > 0 ? '' : 'none';
}

async function confirmarImport() {
    const file = document.getElementById('import-file').files[0];
    if (!file) return;

    const form = new FormData();
    form.append('arquivo', file);
    _abasSelecionadas().forEach(a => form.append('abas', a));

    const btn = document.getElementById('btn-import-confirm');
    btn.disabled = true;
    btn.textContent = 'Importando...';

    const r = await fetch('/api/importar-excel?confirmar=1', { method: 'POST', body: form });
    const data = await r.json();

    btn.disabled = false;
    btn.textContent = 'Confirmar Importacao';

    if (data.erro) { alert(data.erro); return; }

    fecharModal('modal-import');
    document.getElementById('import-file').value = '';
    document.getElementById('import-preview').innerHTML = '';
    btn.style.display = 'none';

    alert(`Importacao concluida:\n${data.importados} registros importados\n${data.duplicados} ja existentes (ignorados)`);

    loadEstagios();
    // Recarregar filtros de especialidade e mes
    const [espR, mesR] = await Promise.all([fetch('/api/especialidades'), fetch('/api/meses')]);
    const esp = await espR.json();
    const mes = await mesR.json();
    const selEsp = document.getElementById('filtro-especialidade');
    const selMes = document.getElementById('filtro-mes');
    selEsp.innerHTML = '<option value="">Todas</option>';
    selMes.innerHTML = '<option value="">Todos</option>';
    esp.forEach(e => { selEsp.innerHTML += `<option value="${e}">${e}</option>`; });
    mes.forEach(m => { selMes.innerHTML += `<option value="${m}">${m}</option>`; });
}
