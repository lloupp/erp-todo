'use strict';

(function () {
    const $ = id => document.getElementById(id);

    async function getJson(url) {
        const response = await fetch(url, { headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    }

    function fmtNumber(value) {
        return Number(value || 0).toLocaleString('pt-BR');
    }

    function fmtMoney(value) {
        return Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    function setText(id, value) {
        const el = $(id);
        if (el) el.textContent = value;
    }

    function renderBars(id, items, labelKey, valueKey, limit = 10) {
        const root = $(id);
        if (!root) return;
        root.replaceChildren();
        const rows = [...(items || [])].sort((a, b) => Number(b[valueKey] || 0) - Number(a[valueKey] || 0)).slice(0, limit);
        if (!rows.length) {
            const empty = document.createElement('div');
            empty.className = 'report-empty-inline';
            empty.textContent = 'Sem dados para exibir.';
            root.appendChild(empty);
            return;
        }
        const max = Math.max(1, ...rows.map(row => Number(row[valueKey] || 0)));
        rows.forEach(row => {
            const wrap = document.createElement('div');
            wrap.className = 'report-bar-row';
            const head = document.createElement('div');
            head.className = 'report-bar-head';
            const label = document.createElement('span');
            label.textContent = row[labelKey] || 'Não informado';
            const value = document.createElement('strong');
            value.textContent = fmtNumber(row[valueKey]);
            head.append(label, value);
            const track = document.createElement('div');
            track.className = 'report-bar-track';
            const fill = document.createElement('div');
            fill.className = 'report-bar-fill';
            fill.style.width = `${Math.max(4, Number(row[valueKey] || 0) / max * 100)}%`;
            track.appendChild(fill);
            wrap.append(head, track);
            root.appendChild(wrap);
        });
    }

    function renderPipeline(data) {
        const root = $('pipeline-etapas');
        if (!root) return;
        root.replaceChildren();
        const labels = {
            1: 'Triagem do cadastro',
            2: 'Confirmação com o aluno',
            3: 'Acionar chefe de serviço',
            4: 'Deferimento da vaga',
            5: 'Solicitar link ao Financeiro',
            6: 'Enviar link e documentos',
            7: 'Comprovante e documentos',
            8: 'Orientações para o 1º dia',
        };
        const stages = data?.pendentes_por_etapa || {};
        const entries = Object.entries(stages).sort((a, b) => Number(a[0]) - Number(b[0]));
        if (!entries.length) {
            const empty = document.createElement('div');
            empty.className = 'report-empty-inline';
            empty.textContent = 'Nenhuma ação pendente no pipeline.';
            root.appendChild(empty);
            return;
        }
        entries.forEach(([stage, total]) => {
            const row = document.createElement('div');
            row.className = 'report-pipeline-row';
            const name = document.createElement('div');
            name.className = 'report-pipeline-name';
            name.textContent = `${stage} — ${labels[stage] || 'Etapa'}`;
            const count = document.createElement('span');
            count.className = 'report-badge';
            count.textContent = fmtNumber(total);
            const link = document.createElement('a');
            link.className = 'btn btn-sm btn-ghost report-pipeline-late';
            link.href = '/residentes';
            link.textContent = 'Abrir fila';
            row.append(name, count, link);
            root.appendChild(row);
        });
    }

    function fillMonthFilter(months, current) {
        const select = $('report-month');
        if (!select) return;
        const previous = current ?? select.value;
        select.replaceChildren();
        const all = document.createElement('option');
        all.value = '';
        all.textContent = 'Todos os meses';
        select.appendChild(all);
        (months || []).forEach(month => {
            const option = document.createElement('option');
            option.value = month;
            option.textContent = month;
            select.appendChild(option);
        });
        select.value = previous || '';
    }

    async function refresh() {
        const button = $('refresh-reports');
        if (button) {
            button.disabled = true;
            button.textContent = 'Atualizando…';
        }
        document.body.classList.add('reports-loading');
        setText('reports-status', 'Atualizando indicadores…');
        try {
            const month = $('report-month')?.value || '';
            const dashboardUrl = month ? `/api/dashboard?mes_ano=${encodeURIComponent(month)}` : '/api/dashboard';
            const [dashboard, pipeline, pending] = await Promise.all([
                getJson(dashboardUrl),
                getJson('/api/pipeline/dashboard'),
                getJson('/api/pendencias'),
            ]);

            fillMonthFilter(dashboard.meses_disponiveis, dashboard.mes_filtro);
            setText('kpi-total', fmtNumber(dashboard.total));
            setText('kpi-novos', fmtNumber(dashboard.kpis?.novos));
            setText('kpi-andamento', fmtNumber(dashboard.kpis?.em_andamento));
            setText('kpi-deferidos', fmtNumber(dashboard.kpis?.deferidos));
            setText('kpi-confirmados', fmtNumber(dashboard.kpis?.confirmados));
            setText('kpi-pagamentos', fmtNumber(dashboard.kpis?.pag_pendente));
            setText('kpi-criticos', fmtNumber(dashboard.kpis?.criticos));
            setText('kpi-alertas', fmtNumber(dashboard.kpis?.alertas));
            setText('kpi-financeiro', fmtMoney(dashboard.financeiro?.pendente));
            setText('kpi-fila', fmtNumber(Object.values(pipeline.pendentes_por_etapa || {}).reduce((a, b) => a + Number(b || 0), 0)));
            setText('kpi-pipeline-criticos', fmtNumber(pipeline.criticos));
            setText('pending-confirmed', fmtNumber(pending.res_confirmados));

            renderBars('chart-status', dashboard.por_status, 'status', 'count', 9);
            renderBars('chart-especialidades', dashboard.por_especialidade, 'nome', 'count', 10);
            renderBars('chart-meses', dashboard.por_mes, 'mes_ano', 'count', 12);
            renderBars('chart-tipos', dashboard.por_tipo, 'tipo', 'count', 5);
            renderPipeline(pipeline);

            const time = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
            setText('reports-status', `Atualizado às ${time}${month ? ` · filtro ${month}` : ''}`);
        } catch (error) {
            console.error('Falha ao carregar relatórios agregados', error);
            setText('reports-status', 'Falha ao carregar indicadores. Tente novamente.');
        } finally {
            document.body.classList.remove('reports-loading');
            if (button) {
                button.disabled = false;
                button.textContent = 'Atualizar dados';
            }
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        $('refresh-reports')?.addEventListener('click', refresh);
        $('report-month')?.addEventListener('change', refresh);
        refresh();
    });
})();
