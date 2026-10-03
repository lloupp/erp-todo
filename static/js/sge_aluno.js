'use strict';
const sgeRid=Number(document.getElementById('sge-aluno').dataset.residente);
const se=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function sgeApi(url,options={}) {
    const response=await fetch(url,{headers:{'Content-Type':'application/json'},...options});
    const data=await response.json();
    if (!response.ok) throw new Error(data.erro||'Falha na operação');
    return data;
}
function sgeErro(error) { document.getElementById('sge-erro').textContent=error.message; }
let frequencias=[];
let frequenciaVersao=null;
async function carregarFrequencia() {
    const data=await sgeApi(`/api/residentes/${sgeRid}/frequencia`);
    frequencias=data.registros;
    document.getElementById('frequencia-resumo').textContent=`Realizadas: ${data.realizadas}h / previstas: ${data.previstas}h — ${data.percentual}% — faltantes: ${data.faltantes}h`;
    document.getElementById('frequencia-body').innerHTML=frequencias.map(r=>`<tr><td>${se(r.data||'Saldo legado')}</td><td>${se(r.presenca)}</td><td>${r.horas}</td><td>${se(r.observacao)}</td><td>${se(r.responsavel)}</td><td>${r.data?`<button class="btn btn-sm" data-frequencia="${r.id}">Corrigir</button>`:''}</td></tr>`).join('');
}
document.getElementById('frequencia-form').addEventListener('reset',()=>{frequenciaVersao=null; document.querySelector("#frequencia-form [name=data]").readOnly=false;});
document.getElementById('frequencia-form').addEventListener('submit',async event=>{
    event.preventDefault();
    try {
        const d=Object.fromEntries(new FormData(event.target));
        d.horas=Number(d.horas); if(frequenciaVersao!==null) d.versao=frequenciaVersao;
        await sgeApi(`/api/residentes/${sgeRid}/frequencia`,{method:'POST',body:JSON.stringify(d)});
        event.target.reset(); await carregarFrequencia();
    } catch(error) { sgeErro(error); }
});
document.getElementById('frequencia-body').addEventListener('click',event=>{
    const button=event.target.closest('[data-frequencia]'); if(!button) return;
    const r=frequencias.find(r=>r.id===Number(button.dataset.frequencia));
    const form=document.getElementById('frequencia-form');
    for(const key of ['data','horas','presenca','observacao']) form.elements[key].value=r[key]??'';
    form.elements.data.readOnly=true;
    frequenciaVersao=r.versao; form.scrollIntoView({block:'center'});
});
carregarFrequencia().catch(sgeErro);
