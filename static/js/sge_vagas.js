'use strict';
let vagasAdmin = false;
const ve = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function vagasApi(url, options = {}) {
    const response = await fetch(url, {headers:{'Content-Type':'application/json'}, ...options});
    const data = await response.json();
    if (!response.ok) throw new Error(data.erro || 'Falha na operação');
    return data;
}
function vagasErro(error) { document.getElementById('vagas-erro').textContent = error.message; }
async function carregarVagas() {
    const rows = await vagasApi('/api/sge/vagas');
    document.getElementById('vagas-body').innerHTML = rows.map(p=>`<tr><td>${ve(p.especialidade)}</td><td>${ve(p.modalidade)}</td><td>${ve(p.inicio)} a ${ve(p.termino)}</td><td>${p.capacidade}</td><td>${p.ocupadas}${p.excedentes?` (${p.excedentes} excedentes)`:''}</td><td>${p.disponiveis}</td><td>${ve(p.situacao)}</td><td>${vagasAdmin?`<button class="btn btn-sm" data-periodo="${p.id}">Alterar capacidade</button>`:''}</td></tr>`).join('');
}
document.getElementById('vagas-novo').addEventListener('submit', async event=>{
    event.preventDefault();
    try {
        const data = Object.fromEntries(new FormData(event.target));
        data.capacidade = Number(data.capacidade);
        await vagasApi('/api/sge/vagas',{method:'POST',body:JSON.stringify(data)});
        event.target.reset();
        await carregarVagas();
    } catch(error) { vagasErro(error); }
});
document.getElementById('vagas-body').addEventListener('click',async event=>{
    const button = event.target.closest('[data-periodo]');
    if (!button) return;
    const valor = prompt('Nova capacidade:');
    if (valor === null || valor.trim() === '') return;
    try {
        const data = {capacidade:Number(valor)};
        try { await vagasApi(`/api/sge/vagas/${button.dataset.periodo}`,{method:'PUT',body:JSON.stringify(data)}); }
        catch(error) {
            if (!error.message.includes('override')) throw error;
            const motivo = prompt('A capacidade ficará abaixo da ocupação. Justifique a autorização administrativa:');
            if (!motivo?.trim()) return;
            await vagasApi(`/api/sge/vagas/${button.dataset.periodo}`,{method:'PUT',body:JSON.stringify({...data,override_capacidade:true,motivo})});
        }
        await carregarVagas();
    } catch(error) { vagasErro(error); }
});
(async()=>{try { const me = await vagasApi('/api/me'); vagasAdmin=me.role==='admin'; document.getElementById('vagas-novo').hidden=!vagasAdmin; await carregarVagas(); } catch(error) { vagasErro(error); }})();
