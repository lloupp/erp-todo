// configuracoes.js — Modelos de mensagem + Contatos da Área Médica

'use strict';

let CONTATOS = [];
let excluirContatoId = null;

// ─── Layout helpers (mesmo padrão de usuarios.html) ─────────────
function loadTheme() {
    document.documentElement.setAttribute('data-theme', localStorage.getItem('theme') || 'light');
}
function toggleTheme() {
    const t = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('theme', t);
}
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}
async function loadUserInfo() {
    try {
        const r = await fetch('/api/me');
        const d = await r.json();
        const el = document.getElementById('sidebar-user');
        if (el) el.innerHTML = `<strong>${d.nome}</strong><span>${d.role}</span>`;
    } catch (_) {}
}

function abrirModal(id) { document.getElementById(id).classList.add('open'); }
function fecharModal(id) { document.getElementById(id).classList.remove('open'); }

function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

function showToast(msg, type = 'info') {
    const c = document.getElementById('toast-container');
    const d = document.createElement('div');
    d.className = `toast toast-${type}`;
    d.style.cssText = `background:${type === 'error' ? '#dc2626' : type === 'success' ? '#10b981' : '#3b82f6'};color:#fff;padding:10px 16px;border-radius:8px;font-size:13px;box-shadow:0 4px 12px rgba(0,0,0,.2);max-width:320px;`;
    d.textContent = msg;
    c.appendChild(d);
    setTimeout(() => d.remove(), 4000);
}

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

// ─── Tabs ─────────────────────────────────────────────────────
function mudarTab(nome) {
    document.querySelectorAll('.config-tab').forEach(el => el.classList.toggle('active', el.dataset.tab === nome));
    document.querySelectorAll('.config-panel').forEach(el => el.classList.remove('active'));
    document.getElementById(`panel-${nome}`).classList.add('active');
}

// ─── Modelos de Mensagem ────────────────────────────────────────
async function carregarTemplates() {
    let templates = [];
    try {
        templates = await apiFetch('/api/mensagens-modelo');
    } catch (_) { return; }

    const container = document.getElementById('lista-templates');
    container.innerHTML = templates.map(t => `
        <div class="template-card">
            <h3>${esc(t.titulo)}</h3>
            <div class="placeholders">Campos disponíveis: ${(t.placeholders || '').split(',').map(p => `<code class="ph">${esc(p.trim())}</code>`).join(' ')}</div>
            <textarea id="tpl-${esc(t.chave)}">${esc(t.texto)}</textarea>
            <button class="btn btn-sm btn-primary" onclick="salvarTemplate('${t.chave}')">Salvar</button>
        </div>
    `).join('');
}

async function salvarTemplate(chave) {
    const texto = document.getElementById(`tpl-${chave}`).value.trim();
    if (!texto) { showToast('Texto não pode ficar vazio', 'error'); return; }
    try {
        await apiFetch(`/api/mensagens-modelo/${chave}`, { method: 'PUT', body: JSON.stringify({ texto }) });
        showToast('Modelo salvo!', 'success');
    } catch (_) {}
}

// ─── Contatos da Área Médica ────────────────────────────────────
async function carregarContatos() {
    try {
        CONTATOS = await apiFetch('/api/area-medica');
    } catch (_) {
        CONTATOS = [];
    }
    renderContatos();
}

function renderContatos() {
    const busca = (document.getElementById('am-busca').value || '').toLowerCase();
    const filtrados = CONTATOS.filter(c =>
        !busca || (c.especialidade || '').toLowerCase().includes(busca) || (c.nome || '').toLowerCase().includes(busca)
    );

    const tbody = document.getElementById('tabela-contatos');
    const empty = document.getElementById('am-empty');
    if (!filtrados.length) {
        tbody.innerHTML = '';
        empty.style.display = 'block';
        return;
    }
    empty.style.display = 'none';
    tbody.innerHTML = filtrados.map(c => `
        <tr>
            <td><strong>${esc(c.especialidade)}</strong>
                ${c.obs_internato ? `<br><small style="color:var(--color-text-secondary)">Internato: ${esc(c.obs_internato)}</small>` : ''}
                ${c.obs_residencia ? `<br><small style="color:var(--color-text-secondary)">Residência: ${esc(c.obs_residencia)}</small>` : ''}
            </td>
            <td>${esc(c.nome || '—')}</td>
            <td>${esc(c.celular || '—')}</td>
            <td style="font-size:12px;">${esc(c.email || '—')}</td>
            <td style="white-space:nowrap;">
                <button class="btn btn-sm btn-ghost" onclick="editarContato(${c.id})" title="Editar">&#9998;</button>
                <button class="btn btn-sm btn-danger" onclick="confirmarExcluirContato(${c.id}, '${esc(c.especialidade).replace(/'/g, "\\'")}')" title="Excluir">&#128465;</button>
            </td>
        </tr>
    `).join('');
}

function abrirModalContato() {
    document.getElementById('contato-modal-titulo').textContent = 'Novo Contato';
    ['contato-id', 'contato-especialidade', 'contato-nome', 'contato-celular', 'contato-email',
     'contato-obs-internato', 'contato-obs-residencia'].forEach(id => { document.getElementById(id).value = ''; });
    abrirModal('modal-contato');
}

function editarContato(id) {
    const c = CONTATOS.find(x => x.id === id);
    if (!c) return;
    document.getElementById('contato-modal-titulo').textContent = 'Editar Contato';
    document.getElementById('contato-id').value = c.id;
    document.getElementById('contato-especialidade').value = c.especialidade || '';
    document.getElementById('contato-nome').value = c.nome || '';
    document.getElementById('contato-celular').value = c.celular || '';
    document.getElementById('contato-email').value = c.email || '';
    document.getElementById('contato-obs-internato').value = c.obs_internato || '';
    document.getElementById('contato-obs-residencia').value = c.obs_residencia || '';
    abrirModal('modal-contato');
}

async function salvarContato() {
    const id = document.getElementById('contato-id').value;
    const body = {
        especialidade: document.getElementById('contato-especialidade').value.trim(),
        nome: document.getElementById('contato-nome').value.trim(),
        celular: document.getElementById('contato-celular').value.trim(),
        email: document.getElementById('contato-email').value.trim(),
        obs_internato: document.getElementById('contato-obs-internato').value.trim(),
        obs_residencia: document.getElementById('contato-obs-residencia').value.trim(),
    };
    if (!body.especialidade) { showToast('Especialidade é obrigatória', 'error'); return; }

    try {
        await apiFetch(id ? `/api/area-medica/${id}` : '/api/area-medica', {
            method: id ? 'PUT' : 'POST',
            body: JSON.stringify(body),
        });
        showToast(id ? 'Contato atualizado!' : 'Contato criado!', 'success');
        fecharModal('modal-contato');
        carregarContatos();
    } catch (_) {}
}

function confirmarExcluirContato(id, especialidade) {
    excluirContatoId = id;
    document.getElementById('msg-confirmar-contato').textContent = `Excluir o contato de "${especialidade}"?`;
    abrirModal('modal-confirmar-contato');
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('btn-confirmar-excluir-contato').onclick = async () => {
        if (!excluirContatoId) return;
        try {
            await apiFetch(`/api/area-medica/${excluirContatoId}`, { method: 'DELETE' });
            showToast('Contato excluído!', 'success');
            carregarContatos();
        } catch (_) {}
        fecharModal('modal-confirmar-contato');
        excluirContatoId = null;
    };

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            fecharModal('modal-contato');
            fecharModal('modal-confirmar-contato');
        }
    });

    loadTheme();
    loadUserInfo();
    carregarTemplates();
    carregarContatos();
});
