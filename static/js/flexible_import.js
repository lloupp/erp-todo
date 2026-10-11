/* Flexible import UI: intentionally separate from the legacy workbook importer. */
(() => {
  'use strict';
  const file = () => document.getElementById('import-file');
  const preview = () => document.getElementById('import-preview');
  const confirmButton = () => document.getElementById('btn-import-confirm');
  let accepted = null;

  function reset() {
    accepted = null;
    confirmButton().style.display = 'none';
    confirmButton().disabled = true;
    preview().replaceChildren();
  }

  function node(tag, text, parent) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = String(text);
    if (parent) parent.appendChild(element);
    return element;
  }

  function form() {
    const data = new FormData();
    data.append('arquivo', file().files[0]);
    return data;
  }

  async function send(confirm) {
    const response = await fetch('/api/importar-flexivel?confirmar=' + (confirm ? '1' : '0'), {
      method: 'POST',
      body: form(),
      credentials: 'same-origin'
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.erro || 'Falha na análise da planilha');
    return body;
  }

  window.analisarFlexivel = async function () {
    reset();
    if (!file().files.length) {
      node('p', 'Selecione uma planilha .xlsx.', preview());
      return;
    }
    const selectedFile = file().files[0];
    if (!selectedFile.name.toLowerCase().endsWith('.xlsx')) {
      node('p', 'Converta o arquivo para .xlsx antes de importar.', preview());
      return;
    }
    node('p', 'Analisando planilha...', preview());
    try {
      const data = await send(false);
      preview().replaceChildren();
      const summary = node('p', undefined, preview());
      summary.textContent = data.total_planilha + ' encontrados • ' + data.novos +
        ' novos • ' + data.duplicados + ' duplicados • ' + data.total_erros + ' erros.';
      if (data.preview && data.preview.length) {
        const table = node('table', undefined, preview());
        const header = node('tr', undefined, node('thead', undefined, table));
        ['Nome', 'Especialidade', 'Competência', 'Semana'].forEach(label => node('th', label, header));
        const tbody = node('tbody', undefined, table);
        data.preview.forEach(item => {
          const row = node('tr', undefined, tbody);
          [item.nome, item.especialidade, item.mes_ano || '—', item.semana].forEach(value =>
            node('td', value, row));
        });
      }
      if (data.total_erros) {
        node('p', 'Corrija os erros antes de importar:', preview());
        const list = node('ul', undefined, preview());
        data.erros.forEach(error => node('li', error.aba + ', linha ' + error.linha + ': ' + error.motivo, list));
        if (data.total_erros > data.erros.length)
          node('p', 'Existem erros adicionais não mostrados.', preview());
      }
      if (data.novos > 0 && data.total_erros === 0) {
        accepted = selectedFile;
        confirmButton().style.display = '';
        confirmButton().disabled = false;
      } else {
        node('p', data.novos ? 'A importação está bloqueada até a correção.' :
          'Não há novos registros para importar.', preview());
      }
    } catch (error) {
      preview().replaceChildren();
      node('p', error.message, preview());
    }
  };

  window.confirmarFlexivel = async function () {
    if (!accepted || file().files[0] !== accepted) {
      reset();
      node('p', 'O arquivo mudou. Analise novamente antes de confirmar.', preview());
      return;
    }
    confirmButton().disabled = true;
    try {
      const data = await send(true);
      reset();
      node('p', data.importados + ' registros importados. ' + data.duplicados +
        ' registros já existentes foram ignorados.', preview());
      if (typeof loadEstagios === 'function') loadEstagios();
    } catch (error) {
      node('p', 'Não foi possível confirmar: ' + error.message, preview());
    } finally {
      confirmButton().disabled = false;
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    file().addEventListener('change', reset);
  });
})();
