/* Assistente IA (OpenRouter) — botão flutuante global.
   Self-contained: injeta FAB + painel de chat em qualquer página que inclua
   a sidebar. Só aparece se /api/ai/status retornar {enabled:true}. */
(function () {
    'use strict';

    var historico = [];      // [{role, content}]
    var carregando = false;

    function el(tag, attrs, html) {
        var e = document.createElement(tag);
        if (attrs) { for (var k in attrs) e.setAttribute(k, attrs[k]); }
        if (html != null) e.innerHTML = html;
        return e;
    }

    // Markdown minimalista (negrito, itálico, código, listas, quebras). Escapa HTML antes.
    function renderMd(txt) {
        var s = (txt || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        s = s.replace(/```([\s\S]*?)```/g, function (_, c) { return '<pre>' + c + '</pre>'; });
        s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
        s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        s = s.replace(/(^|\n)\s*[-*]\s+(.+)/g, '$1• $2');
        s = s.replace(/\n/g, '<br>');
        return s;
    }

    function addMsg(role, content) {
        var box = document.getElementById('ai-msgs');
        if (!box) return;
        var cls = role === 'user' ? 'ai-msg ai-msg-user' : 'ai-msg ai-msg-bot';
        var m = el('div', { 'class': cls }, role === 'user' ? renderMd(content) : renderMd(content));
        box.appendChild(m);
        box.scrollTop = box.scrollHeight;
        return m;
    }

    function setLoading(on) {
        carregando = on;
        var t = document.getElementById('ai-typing');
        if (t) t.style.display = on ? 'block' : 'none';
        var btn = document.getElementById('ai-send');
        if (btn) btn.disabled = on;
    }

    function enviar() {
        if (carregando) return;
        var input = document.getElementById('ai-input');
        var texto = (input.value || '').trim();
        if (!texto) return;
        input.value = '';
        historico.push({ role: 'user', content: texto });
        addMsg('user', texto);
        setLoading(true);
        fetch('/api/ai/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: historico })
        })
            .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
            .then(function (res) {
                setLoading(false);
                if (res.ok && res.j.resposta) {
                    historico.push({ role: 'assistant', content: res.j.resposta });
                    addMsg('assistant', res.j.resposta);
                } else {
                    addMsg('assistant', '⚠ ' + (res.j.erro || 'Não foi possível obter resposta.'));
                }
            })
            .catch(function () {
                setLoading(false);
                addMsg('assistant', '⚠ Falha de conexão com o assistente.');
            });
    }

    function gerarResumo() {
        if (carregando) return;
        addMsg('user', '📊 Resumo da situação');
        setLoading(true);
        fetch('/api/ai/insights')
            .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
            .then(function (res) {
                setLoading(false);
                if (res.ok && res.j.resumo) {
                    historico.push({ role: 'assistant', content: res.j.resumo });
                    addMsg('assistant', res.j.resumo);
                } else {
                    addMsg('assistant', '⚠ ' + (res.j.erro || 'Não foi possível gerar o resumo.'));
                }
            })
            .catch(function () {
                setLoading(false);
                addMsg('assistant', '⚠ Falha de conexão com o assistente.');
            });
    }

    function setBadge(n) {
        var b = document.getElementById('ai-badge');
        if (!b) return;
        if (n > 0) {
            b.textContent = n > 99 ? '99+' : String(n);
            b.style.display = 'block';
        } else {
            b.style.display = 'none';
        }
    }

    function atualizarBadge() {
        fetch('/api/pendencias')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (p) {
                if (!p) return;
                var total = (p.criticos || 0) + (p.alertas || 0) + (p.pag_pendente || 0) + (p.res_pag_pendente || 0);
                setBadge(total);
            })
            .catch(function () { });
    }

    function togglePainel() {
        var p = document.getElementById('ai-panel');
        if (!p) return;
        var abrir = p.style.display === 'none' || !p.style.display;
        p.style.display = abrir ? 'flex' : 'none';
        if (abrir) {
            atualizarBadge();
            var box = document.getElementById('ai-msgs');
            if (box && !box.childElementCount) {
                addMsg('assistant',
                    'Olá! Sou o assistente do ERP. Posso responder sobre estágios e '
                    + 'residentes (contagens, pendências, pagamentos, etapas). '
                    + 'Pergunte algo ou clique em **Resumo da situação**.');
            }
            var inp = document.getElementById('ai-input');
            if (inp) inp.focus();
        }
    }

    function montarUI() {
        var fab = el('button', { id: 'ai-fab', title: 'Assistente IA' }, '🤖');
        fab.addEventListener('click', togglePainel);

        var badge = el('div', { id: 'ai-badge' });

        var panel = el('div', { id: 'ai-panel' });
        panel.style.display = 'none';
        panel.innerHTML =
            '<div id="ai-header">'
            + '<span>🤖 Assistente IA</span>'
            + '<button id="ai-close" title="Fechar">&times;</button>'
            + '</div>'
            + '<div id="ai-msgs"></div>'
            + '<div id="ai-typing">digitando…</div>'
            + '<div id="ai-actions">'
            + '<button id="ai-resumo" class="ai-chip">📊 Resumo da situação</button>'
            + '</div>'
            + '<div id="ai-inputbar">'
            + '<input id="ai-input" type="text" placeholder="Pergunte sobre os dados..." autocomplete="off">'
            + '<button id="ai-send">Enviar</button>'
            + '</div>';

        document.body.appendChild(fab);
        document.body.appendChild(badge);
        document.body.appendChild(panel);

        document.getElementById('ai-close').addEventListener('click', togglePainel);
        document.getElementById('ai-send').addEventListener('click', enviar);
        document.getElementById('ai-resumo').addEventListener('click', gerarResumo);
        document.getElementById('ai-input').addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter') { ev.preventDefault(); enviar(); }
        });

        atualizarBadge();
        setInterval(atualizarBadge, 120000);
    }

    function init() {
        fetch('/api/ai/status')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (s) { if (s && s.enabled) montarUI(); })
            .catch(function () { });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
