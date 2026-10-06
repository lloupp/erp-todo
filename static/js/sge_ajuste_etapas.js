'use strict';

let bulkPage = 1;
let bulkTotalPages = 1;
let bulkRows = [];
const bulkSelected = new Set();
let bulkUser = null;

const bulkEsc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}[c]));

async function bulkApi(url, options={}) {
    const response = await fetch(url, {
        headers: {'Content-Type':'application/json'},
        ...options,
    });
    const contentType = response.headers.get('Content-Type') || '';
    const data = contentType.includes('json') ? await response.json() : {};
    if (!response.ok) throw new Error(data.erro || 'Falha na operação.');
    return data;
}

function bulkErro(error) {
    document.getElementById('bulk-erro').textContent = error?.message || String(error || '');
}

function bulkLimparErro() {
    document.getElementById('bulk-erro').textContent = '';
}

function bulkEtapaLabel(row) {
    if (!row.etapa) return 'Sem etapa pendente';
    return `${row.etapa} — ${row.etapa_nome || row.acao_tipo || ''}`;
}

function bulkSituacao(row) {
    if (row.status === 'Concluído') return 'Histórico concluído';
    if (row.bloqueado) return `Bloqueado: ${row.bloqueio_motivo || 'sem motivo'}`;
    return row.etapa ? 'Em pipeline' : 'Sem ação pendente';
}

function bulkRender() {
    const body = document.getElementById('bulk-alunos-body');
    if (!bulkRows.length) {
        body.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:18px;color:var(--color-text-secondary)">Nenhum aluno encontrado.</td></tr>';
    } else {
        body.innerHTML = bulkRows.map(row => {
            const checked = bulkSelected.has(row.id) ? 'checked' : '';
            const periodo = row.inicio || row.termino
                ? `${bulkEsc(row.inicio || '—')} → ${bulkEsc(row.termino || '—')}`
                : bulkEsc(row.mes_ano || '—');
            return `<tr>
                <td><input type="checkbox" data-bulk-id="${row.id}" ${checked}></td>
                <td><strong>${bulkEsc(row.nome)}</strong><br><small>${bulkEsc(row.email || '')}</small></td>
                <td>${bulkEsc(row.especialidade || '—')}<br><small>${bulkEsc(row.modalidade || '')}</small></td>
                <td>${periodo}</td>
                <td>${bulkEsc(row.status || '—')}</td>
                <td>${bulkEsc(bulkEtapaLabel(row))}</td>
                <td>${bulkEsc(bulkSituacao(row))}</td>
            </tr>`;
        }).join('');
    }
    document.getElementById('bulk-total-selecionados').textContent = bulkSelected.size;
    document.getElementById('bulk-paginacao-info').textContent =
        `Página ${bulkPage} de ${bulkTotalPages}`;
    document.getElementById('bulk-prev').disabled = bulkPage <= 1;
    document.getElementById('bulk-next').disabled = bulkPage >= bulkTotalPages;

    const allCurrentSelected = bulkRows.length > 0 && bulkRows.every(r => bulkSelected.has(r.id));
    document.getElementById('bulk-check-page').checked = allCurrentSelected;
}

async function carregarBulk() {
    bulkLimparErro();
    const params = new URLSearchParams({
        page: bulkPage,
        per_page: 50,
    });
    const busca = document.getElementById('bulk-busca').value.trim();
    const status = document.getElementById('bulk-status').value;
    const etapa = document.getElementById('bulk-etapa-filtro').value;
    if (busca) params.set('busca', busca);
    if (status) params.set('status', status);
    if (etapa) params.set('etapa', etapa);

    try {
        const data = await bulkApi('/api/sge/ajuste-etapas/alunos?' + params.toString());
        bulkRows = data.data || [];
        bulkPage = data.page || 1;
        bulkTotalPages = data.total_pages || 1;
        document.getElementById('bulk-aplicar').disabled = !data.pode_editar;
        if (!data.pode_editar) {
            document.getElementById('bulk-erro').textContent =
                'Seu perfil pode consultar esta aba, mas somente coordenação ou administrador pode aplicar ajustes.';
        }
        bulkRender();
    } catch (error) {
        bulkErro(error);
    }
}

function selecionarPagina(valor=true) {
    bulkRows.forEach(row => {
        if (valor) bulkSelected.add(row.id);
        else bulkSelected.delete(row.id);
    });
    bulkRender();
}

function atualizarOpcoesDestino() {
    const value = document.getElementById('bulk-destino').value;
    const historico = value === 'concluido';
    document.getElementById('bulk-historico-aviso').style.display = historico ? 'block' : 'none';

    const stage = value.startsWith('etapa:') ? Number(value.split(':')[1]) : null;
    const showOverride = bulkUser?.role === 'admin' && (stage === 8 || stage === 9);
    document.getElementById('bulk-override-box').style.display = showOverride ? 'block' : 'none';
    if (!showOverride) {
        document.getElementById('bulk-override').checked = false;
        document.getElementById('bulk-override-motivo').value = '';
    }
}

async function aplicarBulk() {
    bulkLimparErro();
    if (!bulkSelected.size) {
        bulkErro(new Error('Selecione pelo menos um aluno.'));
        return;
    }

    const destinoValue = document.getElementById('bulk-destino').value;
    const justificativa = document.getElementById('bulk-justificativa').value.trim();
    if (!destinoValue) {
        bulkErro(new Error('Escolha o destino da alteração.'));
        return;
    }
    if (justificativa.length < 5) {
        bulkErro(new Error('Informe uma justificativa para o ajuste em lote.'));
        return;
    }

    let payload = {
        ids: Array.from(bulkSelected),
        justificativa,
        override_capacidade: document.getElementById('bulk-override').checked,
        motivo_capacidade: document.getElementById('bulk-override-motivo').value.trim() || null,
    };
    if (destinoValue === 'proxima') {
        payload.destino = 'proxima';
    } else if (destinoValue === 'concluido') {
        payload.destino = 'concluido';
    } else if (destinoValue.startsWith('etapa:')) {
        payload.destino = 'etapa';
        payload.etapa = Number(destinoValue.split(':')[1]);
    }

    const textoDestino = document.getElementById('bulk-destino').selectedOptions[0]?.textContent || destinoValue;
    if (!window.confirm(
        `Aplicar "${textoDestino}" a ${bulkSelected.size} aluno(s)?\n\nA operação será auditada e pode ter resultados parciais se algum aluno não atender às validações.`
    )) return;

    const button = document.getElementById('bulk-aplicar');
    button.disabled = true;
    try {
        const result = await bulkApi('/api/sge/ajuste-etapas/aplicar', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
        document.getElementById('bulk-resultados').style.display = 'block';
        document.getElementById('bulk-resultados-resumo').textContent =
            `${result.selecionados} selecionado(s): ${result.sucessos} alterado(s), ${result.ignorados} ignorado(s), ${result.falhas} falha(s).`;
        document.getElementById('bulk-resultados-body').innerHTML = (result.resultados || []).map(item => {
            const ok = item.ok;
            const detail = ok
                ? (item.ignorado ? item.mensagem : item.status ? `Status: ${item.status}${item.etapa ? ` · etapa ${item.etapa}` : ''}` : 'Alterado')
                : item.erro;
            return `<tr>
                <td>${bulkEsc(item.nome || ('ID ' + item.id))}</td>
                <td class="${ok ? 'bulk-result-ok' : 'bulk-result-error'}">${ok ? (item.ignorado ? 'Ignorado' : 'OK') : 'Falhou'}</td>
                <td>${bulkEsc(detail || '')}</td>
            </tr>`;
        }).join('');
        bulkSelected.clear();
        await carregarBulk();
        document.getElementById('bulk-resultados').scrollIntoView({behavior:'smooth', block:'start'});
    } catch (error) {
        bulkErro(error);
    } finally {
        button.disabled = bulkUser && !['admin','coordenacao'].includes(bulkUser.role);
    }
}

document.getElementById('bulk-alunos-body').addEventListener('change', event => {
    const checkbox = event.target.closest('[data-bulk-id]');
    if (!checkbox) return;
    const id = Number(checkbox.dataset.bulkId);
    if (checkbox.checked) bulkSelected.add(id);
    else bulkSelected.delete(id);
    document.getElementById('bulk-total-selecionados').textContent = bulkSelected.size;
});

document.getElementById('bulk-check-page').addEventListener('change', event => selecionarPagina(event.target.checked));
document.getElementById('bulk-selecionar-pagina').addEventListener('click', () => selecionarPagina(true));
document.getElementById('bulk-limpar-selecao').addEventListener('click', () => { bulkSelected.clear(); bulkRender(); });
document.getElementById('bulk-filtrar').addEventListener('click', () => { bulkPage = 1; carregarBulk(); });
document.getElementById('bulk-limpar').addEventListener('click', () => {
    document.getElementById('bulk-busca').value = '';
    document.getElementById('bulk-status').value = '';
    document.getElementById('bulk-etapa-filtro').value = '';
    bulkPage = 1;
    carregarBulk();
});
document.getElementById('bulk-prev').addEventListener('click', () => { if (bulkPage > 1) { bulkPage--; carregarBulk(); }});
document.getElementById('bulk-next').addEventListener('click', () => { if (bulkPage < bulkTotalPages) { bulkPage++; carregarBulk(); }});
document.getElementById('bulk-destino').addEventListener('change', atualizarOpcoesDestino);
document.getElementById('bulk-aplicar').addEventListener('click', aplicarBulk);
document.getElementById('bulk-busca').addEventListener('keydown', event => {
    if (event.key === 'Enter') { bulkPage = 1; carregarBulk(); }
});

(async function initBulkStages() {
    try {
        bulkUser = await bulkApi('/api/me');
        atualizarOpcoesDestino();
        await carregarBulk();
    } catch (error) {
        bulkErro(error);
    }
})();
