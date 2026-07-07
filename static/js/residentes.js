// residentes.js — Módulo Residentes & Doutorandos

'use strict';

// ─── Estado ───────────────────────────────────────────────────
let currentPage = 1;
let idExcluir = null;
let debounceTimer = null;
let previewNovos = [];
let idAvancar = null;
let residentesCache = {};   // id -> registro (ultima pagina carregada), usado pelo modal Area Medica
let AREA_MEDICA = null;     // cache dos contatos de chefes de servico
let MENSAGENS_MODELO = {};  // chave -> texto do modelo (editavel em /configuracoes)
let USUARIO_LOGADO_NOME = '';

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

// Status ainda "em aberto" — só esses geram alerta de dias parado
// (Confirmado e demais são desfechos finais, não faz sentido alertar)
const STATUS_PENDENTES = ['Interessado', 'Em andamento', 'Deferido'];

// ─── Init ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    loadTheme();
    loadEspecialidades();
    // Nome do usuario logado e modelos de mensagem precisam estar prontos
    // antes do primeiro render da tabela (usados nos botoes de WhatsApp).
    await Promise.all([loadUserInfo(), carregarMensagensModelo()]);
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

async function carregarMensagensModelo() {
    try {
        const lista = await apiFetch('/api/mensagens-modelo');
        lista.forEach(t => { MENSAGENS_MODELO[t.chave] = t.texto; });
    } catch (_) {}
}

// Substitui {{chave}} pelos valores informados. Chaves nao encontradas ficam
// como estao (evita quebrar a mensagem se o admin remover um placeholder).
function preencherTemplate(texto, valores) {
    return (texto || '').replace(/\{\{\s*(\w+)\s*\}\}/g, (m, chave) =>
        Object.prototype.hasOwnProperty.call(valores, chave) ? valores[chave] : m
    );
}

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
        USUARIO_LOGADO_NOME = (r.nome || '').trim().split(' ')[0];
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
        // Backend agrupa os textos livres da planilha do Forms sob a
        // especialidade "oficial" mais parecida (mesma logica de
        // melhorMatchAreaMedica), entao aqui recebemos poucas dezenas de
        // grupos com contagem — não as ~290 variantes de texto livre.
        const data = await apiFetch('/api/residentes/especialidades');
        const sel = document.getElementById('f-especialidade');
        (data || []).forEach(g => {
            const o = document.createElement('option');
            o.value = g.grupo; o.textContent = `${g.grupo} (${g.total})`;
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
    const ord   = document.getElementById('f-ordenar').value;
    if (busca) p.busca = busca;
    if (tipo)  p.tipo  = tipo;
    if (mod)   p.modalidade = mod;
    if (esp)   p.especialidade = esp;
    if (mes)   p.mes_ano = mes;
    if (stat)  p.status = stat;
    if (pag)   p.status_pagamento = pag;
    p.ordenar = ord || 'recentes';
    return p;
}

function limparFiltros() {
    ['f-busca','f-mes'].forEach(id => document.getElementById(id).value = '');
    ['f-tipo','f-modalidade','f-especialidade','f-status','f-pagamento'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('f-ordenar').value = 'recentes';
    currentPage = 1;
    loadResidentes();
}

// ─── WhatsApp ─────────────────────────────────────────────────
const TEMPLATE_ALUNO_FALLBACK = 'Olá {{nome}}, tudo bem?\n{{usuario}} aqui do Ensino e Pesquisa.';

function whatsappLink(telefone, nome) {
    if (!telefone) return null;
    let digits = telefone.replace(/\D/g, '');
    if (!digits) return null;
    // Sem DDI (Brasil = 55): assume numero nacional (DDD + numero)
    if (digits.length <= 11) digits = '55' + digits;
    const primeiroNome = (nome || '').trim().split(' ')[0];
    const template = MENSAGENS_MODELO.whatsapp_aluno || TEMPLATE_ALUNO_FALLBACK;
    const texto = preencherTemplate(template, { nome: primeiroNome, usuario: USUARIO_LOGADO_NOME });
    return `https://wa.me/${digits}?text=${encodeURIComponent(texto)}`;
}

// ─── Área Médica (falar com chefe de serviço da especialidade) ─
async function carregarAreaMedica() {
    if (AREA_MEDICA) return AREA_MEDICA;
    try {
        AREA_MEDICA = await apiFetch('/api/area-medica');
    } catch (_) {
        AREA_MEDICA = [];
    }
    return AREA_MEDICA;
}

function normalizarTexto(s) {
    return (s || '').toString()
        .normalize('NFD').replace(/[̀-ͯ]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9 ]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

const STOPWORDS_ESP = new Set(['e', 'de', 'do', 'da', 'dos', 'das', 'em', 'ou', 'a', 'o', 'para', 'geral']);

// Termos equivalentes na nomenclatura medica brasileira sem sobreposicao de
// palavras com o nome oficial (ex: "Clínica Médica" = "Medicina Interna").
// Mesma lista usada no backend (_SINONIMOS_ESPECIALIDADE em app.py) — manter
// as duas em sincronia.
const SINONIMOS_ESPECIALIDADE = { 'clinica medica': 'Medicina Interna', 'clin medica': 'Medicina Interna' };

// Pontuacao minima pra aceitar uma sugestao automatica. Um unico substantivo
// em comum (ex: "Medicina Intensiva" vs "Medicina Interna") gera score baixo
// e ja causou sugestoes erradas — exige match exato, substring, sinonimo, ou
// 2+ palavras em comum. Mesmo valor usado no backend (_SCORE_MINIMO_MATCH).
const SCORE_MINIMO_MATCH_ESPECIALIDADE = 6;

// Sugere o contato mais provável comparando a especialidade (texto livre,
// digitado pelo proprio candidato no formulario) com a lista oficial da
// area medica. Nao e garantido — o usuario sempre confere/troca no modal.
function melhorMatchAreaMedica(especialidadeResidente) {
    if (!AREA_MEDICA || !AREA_MEDICA.length) return null;
    const alvo = normalizarTexto(especialidadeResidente);
    if (!alvo) return null;
    const palavrasAlvo = alvo.split(' ').filter(w => w && !STOPWORDS_ESP.has(w));
    let melhorIdx = null, melhorScore = 0;

    Object.entries(SINONIMOS_ESPECIALIDADE).forEach(([chave, nomeOficial]) => {
        if (!alvo.includes(chave)) return;
        const nomeOficialNorm = normalizarTexto(nomeOficial);
        const idx = AREA_MEDICA.findIndex(c => normalizarTexto(c.especialidade) === nomeOficialNorm);
        if (idx !== -1 && 20 > melhorScore) { melhorScore = 20; melhorIdx = idx; }
    });

    AREA_MEDICA.forEach((c, idx) => {
        const cand = normalizarTexto(c.especialidade);
        let score = 0;
        if (cand === alvo) score += 100;
        else if (alvo.includes(cand) || cand.includes(alvo)) score += 20;
        cand.split(' ').filter(w => w && !STOPWORDS_ESP.has(w)).forEach(p => {
            if (palavrasAlvo.includes(p)) score += 3;
        });
        if (score > melhorScore) { melhorScore = score; melhorIdx = idx; }
    });
    return melhorScore >= SCORE_MINIMO_MATCH_ESPECIALIDADE ? melhorIdx : null;
}

function formatarDataBR(iso) {
    if (!iso) return '';
    const p = String(iso).split('T')[0].split('-');
    return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : iso;
}

const TEMPLATE_AREA_MEDICA_FALLBACK = 'Olá! Tudo bem?\nGostaria de verificar a disponibilidade de vaga para Estágio {{modalidade}} em {{especialidade}} para o {{tipo}} {{nome}}, {{periodo}}.\nFico no aguardo do retorno. Muito obrigado!';

function montarMensagemAreaMedica(r, contato) {
    const tipoLower = r.tipo === 'Doutorando' ? 'doutorando' : 'residente';
    const modalidade = r.modalidade || 'Optativo';
    let periodo;
    if (r.inicio && r.termino) {
        periodo = `no período de ${formatarDataBR(r.inicio)} a ${formatarDataBR(r.termino)}`;
    } else if (r.periodo_desejado) {
        periodo = `no período de ${r.periodo_desejado}`;
    } else if (r.mes_desejado) {
        periodo = `em ${r.mes_desejado}`;
    } else {
        periodo = `no mês ${(r.mes_ano || '').slice(0, 7)}`;
    }
    const template = MENSAGENS_MODELO.whatsapp_area_medica || TEMPLATE_AREA_MEDICA_FALLBACK;
    return preencherTemplate(template, {
        nome: r.nome,
        tipo: tipoLower,
        modalidade,
        especialidade: contato.especialidade,
        periodo,
        usuario: USUARIO_LOGADO_NOME,
    });
}

async function abrirModalAreaMedica(id) {
    const r = residentesCache[id];
    if (!r) return;
    await carregarAreaMedica();
    if (!AREA_MEDICA.length) {
        showToast('Lista de contatos da área médica não carregada.', 'error');
        return;
    }

    document.getElementById('am-aluno-nome').textContent = `${r.nome} (${r.tipo})`;
    document.getElementById('am-esp-original').textContent = r.especialidade || '—';

    const select = document.getElementById('am-select');
    select.innerHTML = AREA_MEDICA.map((c, idx) =>
        `<option value="${idx}">${esc(c.especialidade)} — ${esc(c.nome)}</option>`
    ).join('');
    select.dataset.residenteId = id;

    const melhorIdx = melhorMatchAreaMedica(r.especialidade);
    if (melhorIdx !== null) select.value = melhorIdx;

    selecionarContatoAreaMedica();
    abrirModal('modal-area-medica');
}

function selecionarContatoAreaMedica() {
    const select = document.getElementById('am-select');
    const id = parseInt(select.dataset.residenteId, 10);
    const r = residentesCache[id];
    const contato = AREA_MEDICA[parseInt(select.value, 10)];
    if (!r || !contato) return;

    const partes = [];
    if (contato.celular) partes.push(`&#128241; ${esc(contato.celular)}`);
    if (contato.email) partes.push(`&#9993; ${esc(contato.email)}`);
    if (contato.obs_internato) partes.push(`Internato: ${esc(contato.obs_internato)}`);
    if (contato.obs_residencia) partes.push(`Residência: ${esc(contato.obs_residencia)}`);
    document.getElementById('am-contato-info').innerHTML =
        partes.join('<br>') || 'Sem informações de contato cadastradas para esta especialidade.';

    document.getElementById('am-mensagem').value = montarMensagemAreaMedica(r, contato);
    atualizarLinkAreaMedica();
}

function atualizarLinkAreaMedica() {
    const select = document.getElementById('am-select');
    const contato = AREA_MEDICA[parseInt(select.value, 10)];
    const mensagem = document.getElementById('am-mensagem').value;
    const btn = document.getElementById('am-btn-whatsapp');
    const link = contato ? whatsappLinkDireto(contato.celular, mensagem) : null;
    if (link) {
        btn.href = link;
        btn.classList.remove('btn-disabled');
    } else {
        btn.href = 'javascript:void(0)';
        btn.classList.add('btn-disabled');
    }
}

function whatsappLinkDireto(celular, mensagem) {
    if (!celular) return null;
    let digits = celular.replace(/\D/g, '');
    if (!digits) return null;
    if (digits.length <= 11) digits = '55' + digits;
    return `https://wa.me/${digits}?text=${encodeURIComponent(mensagem)}`;
}

function debounceLoad() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => { currentPage = 1; loadResidentes(); }, 300);
}

// Usado pelos <select> de filtro: sempre volta pra página 1, senão o filtro
// pode "não parecer funcionar" (continua pedindo a página em que o usuário
// estava, que pode não existir mais no resultado filtrado).
function aplicarFiltro() {
    currentPage = 1;
    loadResidentes();
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
    rows.forEach(r => { residentesCache[r.id] = r; });
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

        const dias = r.dias_no_status || 0;
        const emAberto = STATUS_PENDENTES.includes(r.status);
        const alertaCor = (emAberto && dias > 14) ? '#dc2626' : (emAberto && dias > 7) ? '#f59e0b' : null;
        const alertaHtml = alertaCor
            ? `<span title="${dias} dias sem mudar de status" style="color:${alertaCor};font-size:11px;font-weight:600;margin-left:4px;">&#9888; ${dias}d</span>`
            : '';

        return `<tr>
            <td><strong>${esc(r.nome)}</strong><br><small style="color:var(--color-text-secondary)">${esc(r.email||'')} ${r.telefone?'· '+esc(r.telefone):''}</small></td>
            <td><span class="badge-tipo ${tipoCls}">${esc(r.tipo)}</span><br><small>${esc(r.modalidade||'')}</small></td>
            <td>${esc(r.especialidade)}<br><small style="color:var(--color-text-secondary)">${esc(r.subespecialidade||'')}</small></td>
            <td>${esc(r.instituicao_origem||'—')}</td>
            <td style="white-space:nowrap;font-size:12px;">${esc(r.data_inscricao||'—')}</td>
            <td style="font-size:12px;">${esc(r.mes_desejado||'—')}</td>
            <td style="font-size:12px;">${esc(r.periodo_desejado||'—')}</td>
            <td>${mesFormatado}</td>
            <td><span class="badge-status" style="background:${cor}">${esc(r.status)}</span>${alertaHtml}</td>
            <td>${pagBadge}${r.valor?`<br><small>R$ ${Number(r.valor).toFixed(2)}</small>`:''}</td>
            <td style="white-space:nowrap;">
                ${r.telefone ? `<a class="btn btn-sm btn-whatsapp" href="${whatsappLink(r.telefone, r.nome)}" target="_blank" rel="noopener" title="Contatar ${esc(r.nome)} via WhatsApp">&#128241;</a>` : ''}
                <button class="btn btn-sm btn-area-medica" onclick="abrirModalAreaMedica(${r.id})" title="Falar com a Área Médica (chefe de serviço)">&#127973;</button>
                <button class="btn btn-sm btn-ghost" onclick="abrirHistorico(${r.id},'${esc(r.nome).replace(/'/g,"\\'")}')" title="Historico">&#9776;</button>
                ${proximoStatus(r.status) ? `<button class="btn btn-sm btn-primary" onclick="abrirModalAvancar(${r.id},'${esc(r.nome).replace(/'/g,"\\'")}','${esc(r.status)}')" title="Avançar status">&#9654;</button>` : ''}
                <button class="btn btn-sm btn-ghost" onclick="abrirModalEditar(${r.id})" title="Editar">&#9998;</button>
                <a class="btn btn-sm btn-ghost" href="/api/residentes/${r.id}/pdf" target="_blank" title="Gerar PDF da ficha">&#128196;</a>
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
