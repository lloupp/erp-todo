// UX operacional para Residentes & Doutorandos.
// Esta camada reorganiza a interface existente sem duplicar regras de negócio.
'use strict';

(function () {
    function byId(id) { return document.getElementById(id); }

    function injectStyles() {
        if (document.querySelector('link[data-residents-ux]')) return;
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = '/static/css/residentes_ux.css';
        link.dataset.residentsUx = '1';
        document.head.appendChild(link);
    }

    function setupFilters() {
        const filters = document.querySelector('.filters');
        if (!filters || filters.dataset.uxReady) return;
        filters.dataset.uxReady = '1';
        filters.classList.add('ux-filter-shell');

        const quick = document.createElement('div');
        quick.className = 'ux-filter-quick';
        const advanced = document.createElement('div');
        advanced.className = 'ux-filter-advanced';
        advanced.hidden = true;

        const quickIds = ['f-busca', 'f-status', 'f-pagamento'];
        quickIds.forEach(id => {
            const el = byId(id);
            if (el) quick.appendChild(el);
        });

        const toggleAdvanced = document.createElement('button');
        toggleAdvanced.type = 'button';
        toggleAdvanced.className = 'btn btn-sm ux-filter-toggle';
        toggleAdvanced.innerHTML = 'Mais filtros <span class="ux-filter-count"></span>';
        toggleAdvanced.addEventListener('click', () => {
            advanced.hidden = !advanced.hidden;
            toggleAdvanced.setAttribute('aria-expanded', String(!advanced.hidden));
        });
        quick.appendChild(toggleAdvanced);

        const detailToggle = document.createElement('button');
        detailToggle.type = 'button';
        detailToggle.className = 'btn btn-sm btn-ghost';
        detailToggle.title = 'Mostrar ou ocultar colunas menos usadas';
        const saved = localStorage.getItem('residentes-table-details') === '1';
        document.body.classList.toggle('show-table-details', saved);
        const updateDetailLabel = () => {
            detailToggle.textContent = document.body.classList.contains('show-table-details')
                ? 'Ocultar detalhes' : 'Ver detalhes';
        };
        updateDetailLabel();
        detailToggle.addEventListener('click', () => {
            const show = !document.body.classList.contains('show-table-details');
            document.body.classList.toggle('show-table-details', show);
            localStorage.setItem('residentes-table-details', show ? '1' : '0');
            updateDetailLabel();
        });
        quick.appendChild(detailToggle);

        const clear = Array.from(filters.querySelectorAll('button')).find(b =>
            (b.textContent || '').trim().toLowerCase() === 'limpar'
        );
        if (clear) quick.appendChild(clear);

        ['f-tipo', 'f-modalidade', 'f-especialidade', 'f-mes', 'f-mes-inscricao', 'f-ordenar'].forEach(id => {
            const el = byId(id);
            if (!el) return;
            const group = el.closest('.filter-group');
            advanced.appendChild(group || el);
        });

        filters.replaceChildren(quick, advanced);

        function updateFilterCount() {
            const ids = ['f-tipo', 'f-modalidade', 'f-especialidade', 'f-mes', 'f-mes-inscricao'];
            const count = ids.reduce((n, id) => n + (byId(id)?.value ? 1 : 0), 0);
            const badge = toggleAdvanced.querySelector('.ux-filter-count');
            badge.textContent = count ? `(${count})` : '';
            toggleAdvanced.dataset.active = count ? 'true' : 'false';
            if (count) advanced.hidden = false;
        }
        filters.addEventListener('change', updateFilterCount);
        filters.addEventListener('input', updateFilterCount);
        updateFilterCount();
    }

    function setupWorklistHeading() {
        const table = document.querySelector('.table-container');
        if (!table || document.querySelector('.ux-worklist-heading')) return;
        const heading = document.createElement('div');
        heading.className = 'ux-worklist-heading';
        heading.innerHTML = `
            <div>
                <h3>Cadastros</h3>
                <div class="ux-worklist-meta" id="ux-worklist-meta">Carregando registros…</div>
            </div>`;
        table.before(heading);

        const pagination = byId('paginacao');
        if (!pagination) return;
        const sync = () => {
            const text = (pagination.textContent || '').replace(/\s+/g, ' ').trim();
            const meta = byId('ux-worklist-meta');
            if (meta && text) meta.textContent = text;
        };
        new MutationObserver(sync).observe(pagination, { childList: true, subtree: true, characterData: true });
    }

    function labelTableCells() {
        const labels = ['Pessoa', 'Tipo', 'Especialidade', 'Instituição', 'Inscrição', 'Mês desejado',
            'Período', 'Mês/Ano', 'Status', 'Pagamento', 'Ações'];
        document.querySelectorAll('#tabela-residentes tr').forEach(row => {
            Array.from(row.cells).forEach((cell, index) => {
                cell.dataset.label = labels[index] || '';
            });
        });
    }

    function actionLabel(el) {
        const title = (el.getAttribute('title') || '').toLowerCase();
        if (title.includes('whatsapp')) return 'WhatsApp';
        if (title.includes('área médica') || title.includes('area médica')) return 'Área médica';
        if (title.includes('hist')) return 'Histórico';
        if (title.includes('avançar')) return 'Avançar status';
        if (title.includes('editar')) return 'Editar cadastro';
        if (title.includes('pdf')) return 'Abrir ficha PDF';
        if (el.classList.contains('btn-danger')) return 'Excluir';
        return el.getAttribute('title') || 'Ação';
    }

    function compactActions() {
        document.querySelectorAll('#tabela-residentes tr').forEach(row => {
            const cell = row.cells[row.cells.length - 1];
            if (!cell || cell.dataset.uxActions) return;
            cell.dataset.uxActions = '1';

            const actions = Array.from(cell.querySelectorAll(':scope > .btn, :scope > a.btn'));
            if (!actions.length) return;
            const primary = document.createElement('span');
            primary.className = 'ux-primary-actions';
            const more = document.createElement('details');
            more.className = 'ux-row-more';
            const summary = document.createElement('summary');
            summary.textContent = 'Mais';
            summary.setAttribute('aria-label', 'Mais ações');
            const menu = document.createElement('div');
            menu.className = 'ux-row-more-menu';

            actions.forEach(action => {
                const label = actionLabel(action);
                action.setAttribute('aria-label', label);
                const isPrimary = label === 'WhatsApp' || label === 'Área médica' || label === 'Avançar status';
                if (isPrimary) {
                    if (label === 'Avançar status') action.innerHTML = '&#9654; Avançar';
                    primary.appendChild(action);
                } else {
                    action.textContent = label;
                    action.classList.remove('btn-primary', 'btn-area-medica', 'btn-whatsapp');
                    if (!action.classList.contains('btn-danger')) action.classList.add('btn-ghost');
                    menu.appendChild(action);
                }
            });
            more.append(summary, menu);
            cell.replaceChildren(primary, more);
        });
    }

    function setupFormSections() {
        const grid = document.querySelector('#modal-residente .form-grid');
        if (!grid || grid.dataset.uxReady) return;
        grid.dataset.uxReady = '1';
        const groups = Array.from(grid.children).filter(el => el.classList.contains('form-group'));
        const map = new Map();
        groups.forEach(group => {
            const control = group.querySelector('[id]');
            if (control) map.set(control.id, group);
        });

        const sections = [
            ['Dados da pessoa', true, ['form-tipo', 'form-nome', 'form-cpf', 'form-email', 'form-telefone', 'form-instituicao', 'form-programa']],
            ['Estágio', true, ['form-modalidade', 'form-especialidade', 'form-subesp', 'form-mes-ano', 'form-inicio', 'form-termino', 'form-status']],
            ['Financeiro', false, ['form-valor', 'form-forma-pag', 'form-status-pag', 'form-comprovante']],
            ['Inscrição e observações', false, ['form-data-inscricao', 'form-periodo-desejado', 'form-mes-desejado', 'form-obs']],
        ];

        sections.forEach(([title, open, ids]) => {
            const details = document.createElement('details');
            details.className = 'ux-form-section';
            details.open = open;
            const summary = document.createElement('summary');
            summary.textContent = title;
            const sectionGrid = document.createElement('div');
            sectionGrid.className = 'ux-form-section-grid';
            ids.forEach(id => {
                const group = map.get(id);
                if (group) sectionGrid.appendChild(group);
            });
            details.append(summary, sectionGrid);
            grid.appendChild(details);
        });
    }

    function setupPriorityQueue() {
        const title = document.querySelector('#pipeline-fila-panel strong');
        if (title) {
            title.className = 'ux-priority-title';
            title.innerHTML = 'Prioridades de atendimento <span class="ux-priority-count" id="ux-priority-count">0</span>';
        }

        if (typeof window.carregarPipelineFila !== 'function') return;
        const original = window.carregarPipelineFila;
        window.carregarPipelineFila = async function () {
            const result = await original.apply(this, arguments);
            const panel = byId('pipeline-fila-panel');
            const list = byId('pipeline-fila-lista');
            const toggle = byId('pipeline-fila-toggle');
            const count = list ? list.querySelectorAll('tbody tr').length : 0;
            const countEl = byId('ux-priority-count');
            if (countEl) countEl.textContent = String(count);
            if (panel && panel.style.display !== 'none' && list && count > 0) {
                list.style.display = 'block';
                if (toggle) toggle.innerHTML = '&#9650;';
            }
            return result;
        };
    }

    function setupLoadingAndRenderEnhancements() {
        if (typeof window.renderTabela === 'function') {
            const originalRender = window.renderTabela;
            window.renderTabela = function () {
                const result = originalRender.apply(this, arguments);
                labelTableCells();
                compactActions();
                return result;
            };
        }

        if (typeof window.loadResidentes === 'function') {
            const originalLoad = window.loadResidentes;
            window.loadResidentes = async function () {
                document.querySelector('.table-container')?.classList.add('ux-loading');
                try {
                    return await originalLoad.apply(this, arguments);
                } finally {
                    document.querySelector('.table-container')?.classList.remove('ux-loading');
                }
            };
        }

        if (typeof window.salvarResidente === 'function') {
            const originalSave = window.salvarResidente;
            window.salvarResidente = async function () {
                const button = document.querySelector('#modal-residente .modal-footer .btn-primary');
                if (!button || button.classList.contains('ux-save-busy')) return;
                const previous = button.textContent;
                button.classList.add('ux-save-busy');
                button.disabled = true;
                button.textContent = 'Salvando…';
                try {
                    return await originalSave.apply(this, arguments);
                } finally {
                    button.disabled = false;
                    button.classList.remove('ux-save-busy');
                    button.textContent = previous;
                }
            };
        }
    }

    function setupKeyboard() {
        document.addEventListener('keydown', event => {
            if (event.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || '')) {
                event.preventDefault();
                byId('f-busca')?.focus();
            }
            if (event.key === 'Escape') {
                const openModal = Array.from(document.querySelectorAll('.modal-overlay.open')).pop();
                if (openModal && typeof window.fecharModal === 'function') window.fecharModal(openModal.id);
            }
        });
    }

    injectStyles();
    document.addEventListener('DOMContentLoaded', () => {
        document.body.classList.add('residents-ux');
        setupFilters();
        setupWorklistHeading();
        setupFormSections();
        setupPriorityQueue();
        setupLoadingAndRenderEnhancements();
        setupKeyboard();
    });
})();
