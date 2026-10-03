// residentes_academico.js — acompanhamento academico do SGE
'use strict';

let academicoResidenteId = null;
let documentosAcademicosCache = [];

async function abrirAcademico(id, nome) {
    academicoResidenteId = id;
    document.getElementById("academico-operacional").href = `/sge/residentes/${id}`;
    document.getElementById('academico-titulo').textContent = 'Acompanhamento — ' + nome;
    document.getElementById('academico-conteudo').style.opacity = '.55';
    abrirModal('modal-academico');
    await carregarAcademico();
}

async function carregarAcademico() {
    if (!academicoResidenteId) return;
    try {
        const data = await apiFetch(`/api/residentes/${academicoResidenteId}/academico`);
        const r = data.residente;
        document.getElementById('academico-prevista').value =
            r.carga_horaria_prevista != null ? r.carga_horaria_prevista : '';
        document.getElementById('academico-realizada').value =
            r.carga_horaria_realizada != null ? r.carga_horaria_realizada : '';
        document.getElementById('academico-realizada').readOnly = true;
        renderCertificadoAcademico(data.certificado);
        renderDocumentosAcademicos(data.documentos || []);
    } finally {
        document.getElementById('academico-conteudo').style.opacity = '1';
    }
}

function renderCertificadoAcademico(c) {
    const box = document.getElementById('academico-certificado');
    const motivos = (c.motivos || []).map(m => `<li>${esc(m)}</li>`).join('');
    const estado = c.apto
        ? '<strong style="color:#059669">Apto para certificado</strong>'
        : '<strong style="color:#b45309">Ainda não apto para certificado</strong>';
    const emitido = c.certificado_emitido_em
        ? `<div style="margin-top:6px;font-size:12px;">Emissão registrada: ${esc(formatarDataHora(c.certificado_emitido_em))}</div>`
        : '';
    const enviado = c.certificado_enviado_em
        ? `<div style="font-size:12px;">Envio registrado: ${esc(formatarDataHora(c.certificado_enviado_em))}</div>`
        : '';

    let botoes = '';
    if (c.apto && !c.certificado_emitido_em) {
        botoes += '<button class="btn btn-sm btn-primary" onclick="registrarCertificadoAcademico(\'emitir\')">Registrar emissão</button>';
    }
    if (c.certificado_emitido_em && !c.certificado_enviado_em) {
        botoes += '<button class="btn btn-sm btn-primary" onclick="registrarCertificadoAcademico(\'enviar\')">Registrar envio</button>';
    }

    box.innerHTML = `
        <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;">
            <div>
                ${estado}
                <div style="font-size:12px;color:var(--color-text-secondary);margin-top:4px;">
                    Horas: ${c.carga_horaria_realizada || 0}h / ${c.carga_horaria_prevista || 0}h
                    &nbsp;•&nbsp; Documentos obrigatórios aprovados:
                    ${c.documentos_obrigatorios_aprovados}/${c.documentos_obrigatorios}
                </div>
                ${motivos ? `<ul style="margin:8px 0 0 18px;font-size:12px;color:var(--color-text-secondary);">${motivos}</ul>` : ''}
                ${emitido}${enviado}
            </div>
            <div style="display:flex;gap:6px;flex-wrap:wrap;">${botoes}</div>
        </div>`;
}

function formatarDataHora(valor) {
    if (!valor) return '';
    const d = new Date(valor.replace(' ', 'T') + (valor.includes('Z') ? '' : 'Z'));
    return Number.isNaN(d.getTime()) ? valor : d.toLocaleString('pt-BR');
}

function renderDocumentosAcademicos(documentos) {
    documentosAcademicosCache = documentos;
    const tbody = document.getElementById('academico-docs-body');
    if (!documentos.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--color-text-secondary);padding:14px;">Nenhum documento cadastrado.</td></tr>';
        return;
    }
    tbody.innerHTML = documentos.map(d => `
        <tr>
            <td><input id="doc-nome-${d.id}" value="${esc(d.nome)}" style="width:100%;min-width:150px;"></td>
            <td style="text-align:center;"><input id="doc-obrigatorio-${d.id}" type="checkbox" ${d.obrigatorio ? 'checked' : ''}></td>
            <td>
                <select id="doc-status-${d.id}">
                    ${['Pendente','Recebido','Aprovado','Rejeitado','Expirado'].map(s => `<option ${s===d.status?'selected':''}>${s}</option>`).join('')}
                </select>
            </td>
            <td><input id="doc-obs-${d.id}" value="${esc(d.observacao || '')}" placeholder="Observação" style="width:100%;min-width:130px;"></td>
            <td style="font-size:11px;color:var(--color-text-secondary);">${esc(d.atualizado_por || '—')}</td>
            <td style="white-space:nowrap;">
                <button class="btn btn-sm btn-primary" onclick="salvarDocumentoAcademico(${d.id})">Salvar</button>
                <button class="btn btn-sm btn-danger" onclick="removerDocumentoAcademico(${d.id})">Arquivar</button>
            </td>
        </tr>`).join('');
}

async function salvarHorasAcademicas() {
    if (!academicoResidenteId) return;
    const prevista = document.getElementById('academico-prevista').value;
    const realizada = document.getElementById('academico-realizada').value;
    try {
        await apiFetch(`/api/residentes/${academicoResidenteId}/academico`, {
            method: 'PUT',
            body: JSON.stringify({
                carga_horaria_prevista: prevista === '' ? null : Number(prevista),
            }),
        });
        showToast('Carga horária atualizada', 'success');
        await carregarAcademico();
    } catch (_) {}
}

async function adicionarDocumentoAcademico() {
    if (!academicoResidenteId) return;
    const nomeEl = document.getElementById('academico-doc-novo');
    const nome = nomeEl.value.trim();
    if (!nome) {
        showToast('Informe o nome do documento', 'error');
        return;
    }
    try {
        await apiFetch(`/api/residentes/${academicoResidenteId}/documentos`, {
            method: 'POST',
            body: JSON.stringify({
                nome,
                obrigatorio: document.getElementById('academico-doc-obrigatorio').checked,
                status: 'Pendente',
            }),
        });
        nomeEl.value = '';
        showToast('Documento adicionado', 'success');
        await carregarAcademico();
    } catch (_) {}
}

async function salvarDocumentoAcademico(id) {
    try {
        await apiFetch(`/api/residentes/${academicoResidenteId}/documentos`, {
            method: 'POST',
            body: JSON.stringify({
                id,
                arquivo_id: documentosAcademicosCache.find(d => d.id === id)?.arquivo_id,
                nome: document.getElementById(`doc-nome-${id}`).value.trim(),
                obrigatorio: document.getElementById(`doc-obrigatorio-${id}`).checked,
                status: document.getElementById(`doc-status-${id}`).value,
                observacao: document.getElementById(`doc-obs-${id}`).value.trim(),
            }),
        });
        showToast('Documento atualizado', 'success');
        await carregarAcademico();
    } catch (_) {}
}

async function removerDocumentoAcademico(id) {
    const motivo = prompt('Justifique o arquivamento deste requisito (exige administrador):');
    if (!motivo?.trim()) return;
    try {
        await apiFetch(`/api/residentes/${academicoResidenteId}/documentos/${id}`, {method:'DELETE',body:JSON.stringify({motivo:motivo.trim()})});
        showToast('Documento removido', 'success');
        await carregarAcademico();
    } catch (_) {}
}

async function registrarCertificadoAcademico(acao) {
    try {
        await apiFetch(`/api/residentes/${academicoResidenteId}/certificado`, {
            method: 'POST',
            body: JSON.stringify({acao}),
        });
        showToast(acao === 'emitir' ? 'Emissão do certificado registrada' : 'Envio do certificado registrado', 'success');
        await carregarAcademico();
    } catch (_) {}
}
