'use strict';
const ce=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function centralRows(items) {
    return items.map(i=>`<tr><td><a href="${ce(i.url)}">${ce(i.nome)}</a></td><td>${ce(i.especialidade)}</td><td>${ce(i.prazo||'Sem prazo')}</td><td>${['Normal','Alta','Urgente'][i.prioridade]||'Normal'}</td><td>${ce(i.responsavel||'Sem responsável')}</td><td>${ce(i.detalhe)}</td><td><a class="btn btn-sm" href="${ce(i.url)}">Abrir ação</a></td></tr>`).join('');
}
async function centralApi(query='') {
    const response=await fetch('/api/sge/hoje'+query); const data=await response.json();
    if(!response.ok) throw new Error(data.erro||'Falha ao carregar a central'); return data;
}
function renderCertificados(categorias) {
    const aptos=categorias.find(c=>c.id==='certificados_aptos')||{total:0,items:[]};
    const enviar=categorias.find(c=>c.id==='certificados_enviar')||{total:0,items:[]};
    const total=aptos.total+enviar.total;
    const box=document.getElementById('central-certificados');

    const bloco=(titulo,subtitulo,categoria,classe)=>`
        <div class="central-cert-card ${classe}">
            <div class="central-cert-card-head">
                <div>
                    <strong>${ce(titulo)}</strong>
                    <small>${ce(subtitulo)}</small>
                </div>
                <span class="central-cert-count">${categoria.total}</span>
            </div>
            <div class="central-cert-list">
                ${categoria.items.length?categoria.items.slice(0,5).map(i=>`
                    <a class="central-cert-item" href="${ce(i.url)}">
                        <span><strong>${ce(i.nome)}</strong><small>${ce(i.especialidade||'')}</small></span>
                        <span>Abrir</span>
                    </a>`).join(''):'<p class="central-cert-empty">Nenhum certificado pendente.</p>'}
            </div>
            ${categoria.total>5?`<button class="btn btn-sm" data-cert-categoria="${ce(categoria.id)}">Ver todos (${categoria.total})</button>`:''}
        </div>`;

    box.innerHTML=`
        <div class="central-cert-header">
            <div>
                <h3>Certificados</h3>
                <p>Emissão e envio continuam exigindo ação humana.</p>
            </div>
            <span class="central-cert-total">${total} pendente(s)</span>
        </div>
        <div class="central-cert-grid">
            ${bloco('Aptos para emissão','Todos os critérios acadêmicos atendidos.',aptos,'central-cert-ready')}
            ${bloco('Emitidos aguardando envio','Certificados já emitidos que ainda precisam ser enviados.',enviar,'central-cert-send')}
        </div>`;
}

async function carregarCentral() {
    const data=await centralApi();
    document.getElementById('central-data').textContent='Referência: '+data.data;
    renderCertificados(data.categorias);
    const demais=data.categorias.filter(c=>!['certificados_aptos','certificados_enviar'].includes(c.id));
    document.getElementById('central-categorias').innerHTML=demais.map(c=>`<details ${c.total?'open':''} data-categoria="${ce(c.id)}" style="margin-top:20px"><summary><strong>${ce(c.titulo)} (${c.total})</strong></summary><div style="overflow:auto"><table><thead><tr><th>Aluno</th><th>Especialidade</th><th>Prazo</th><th>Prioridade</th><th>Responsável</th><th>Pendência</th><th>Ação</th></tr></thead><tbody>${centralRows(c.items)}</tbody></table></div>${!c.total?'<p>Nenhuma pendência nesta categoria.</p>':''}${c.proximo_offset!==null?`<button class="btn" data-proximo="${c.proximo_offset}">Carregar mais</button>`:''}</details>`).join('');
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

document.getElementById('central-certificados').addEventListener('click',async event=>{
    const button=event.target.closest('[data-cert-categoria]');
    if(!button)return;
    const categoria=button.dataset.certCategoria;
    try{
        const data=await centralApi('?categoria='+encodeURIComponent(categoria)+'&limit=200');
        const c=data.categorias[0];
        const wrapper=document.createElement('div');
        wrapper.className='central-cert-all';
        wrapper.innerHTML=`<h4>${ce(c.titulo)} (${c.total})</h4><div style="overflow:auto"><table><thead><tr><th>Aluno</th><th>Especialidade</th><th>Pendência</th><th>Ação</th></tr></thead><tbody>${c.items.map(i=>`<tr><td>${ce(i.nome)}</td><td>${ce(i.especialidade)}</td><td>${ce(i.detalhe)}</td><td><a class="btn btn-sm" href="${ce(i.url)}">Abrir</a></td></tr>`).join('')}</tbody></table></div>`;
        const card=button.closest('.central-cert-card');
        const old=card.querySelector('.central-cert-all');
        if(old){old.remove();button.textContent=`Ver todos (${c.total})`;return;}
        card.appendChild(wrapper);
        button.textContent='Ocultar lista completa';
    }catch(error){centralErro(error);}
});
