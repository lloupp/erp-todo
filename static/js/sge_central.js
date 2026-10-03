'use strict';
const ce=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function centralRows(items) {
    return items.map(i=>`<tr><td><a href="${ce(i.url)}">${ce(i.nome)}</a></td><td>${ce(i.especialidade)}</td><td>${ce(i.prazo||'Sem prazo')}</td><td>${['Normal','Alta','Urgente'][i.prioridade]||'Normal'}</td><td>${ce(i.responsavel||'Sem responsável')}</td><td>${ce(i.detalhe)}</td><td><a class="btn btn-sm" href="${ce(i.url)}">Abrir ação</a></td></tr>`).join('');
}
async function centralApi(query='') {
    const response=await fetch('/api/sge/hoje'+query); const data=await response.json();
    if(!response.ok) throw new Error(data.erro||'Falha ao carregar a central'); return data;
}
async function carregarCentral() {
    const data=await centralApi();
    document.getElementById('central-data').textContent='Referência: '+data.data;
    document.getElementById('central-categorias').innerHTML=data.categorias.map(c=>`<details ${c.total?'open':''} data-categoria="${ce(c.id)}" style="margin-top:20px"><summary><strong>${ce(c.titulo)} (${c.total})</strong></summary><div style="overflow:auto"><table><thead><tr><th>Aluno</th><th>Especialidade</th><th>Prazo</th><th>Prioridade</th><th>Responsável</th><th>Pendência</th><th>Ação</th></tr></thead><tbody>${centralRows(c.items)}</tbody></table></div>${!c.total?'<p>Nenhuma pendência nesta categoria.</p>':''}${c.proximo_offset!==null?`<button class="btn" data-proximo="${c.proximo_offset}">Carregar mais</button>`:''}</details>`).join('');
}
document.getElementById('central-atualizar').addEventListener('click',()=>carregarCentral().catch(centralErro));
function centralErro(error) {document.getElementById('central-erro').textContent=error.message;}
document.getElementById('central-categorias').addEventListener('click',async event=>{
    const button=event.target.closest('[data-proximo]'); if(!button)return;
    const section=button.closest('[data-categoria]'); button.disabled=true;
    try {
        const data=await centralApi(`?categoria=${encodeURIComponent(section.dataset.categoria)}&offset=${button.dataset.proximo}`);
        const c=data.categorias[0]; section.querySelector('tbody').insertAdjacentHTML('beforeend',centralRows(c.items));
        if(c.proximo_offset===null) button.remove(); else button.dataset.proximo=c.proximo_offset;
    } catch(error) {centralErro(error);} finally {button.disabled=false;}
});
carregarCentral().catch(centralErro);
