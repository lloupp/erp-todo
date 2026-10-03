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

let sgeDocumentos=[];
async function carregarDocumentos() {
    const data=await sgeApi(`/api/residentes/${sgeRid}/academico`);
    sgeDocumentos=data.documentos;
    document.getElementById('documentos-gate').textContent=data.certificado.apto?'Apto para certificado':data.certificado.motivos.join(' ');
    document.getElementById('documentos-body').innerHTML=sgeDocumentos.map(d=>`<tr data-doc="${d.id}"><td>${se(d.nome)} ${d.obrigatorio?'(obrigatório)':'(opcional)'}</td><td><select name="status">${['Pendente','Recebido','Aprovado','Rejeitado','Expirado'].map(s=>`<option ${s===d.status?'selected':''}>${s}</option>`).join('')}</select></td><td><input name="validade" type="date" value="${se(d.validade||'')}"></td><td>${d.arquivo_url?`<a href="${se(d.arquivo_url)}">Baixar arquivo</a>`:'Sem arquivo'}<input name="arquivo" type="file" accept=".pdf,.png,.jpg,.jpeg"><button class="btn btn-sm" data-doc-action="upload">Anexar (até 8 MB)</button></td><td><input name="observacao" value="${se(d.observacao||'')}"></td><td>${se(d.aprovado_por||'—')} ${se(d.aprovado_em||'')}</td><td><button class="btn btn-sm" data-doc-action="salvar">Salvar revisão</button></td></tr>`).join('');
}
document.getElementById('documentos-novo').addEventListener('submit',async event=>{
    event.preventDefault();
    try {
        await sgeApi(`/api/residentes/${sgeRid}/documentos`,{method:'POST',body:JSON.stringify({nome:event.target.elements.nome.value,obrigatorio:event.target.elements.obrigatorio.checked})});
        event.target.reset(); await carregarDocumentos();
    } catch(error) {sgeErro(error);}
});
document.getElementById('documentos-body').addEventListener('click',async event=>{
    const button=event.target.closest('[data-doc-action]'); if(!button) return;
    const row=button.closest('[data-doc]'); const d=sgeDocumentos.find(d=>d.id===Number(row.dataset.doc));
    button.disabled=true;
    try {
        if(button.dataset.docAction==='upload') {
            const file=row.querySelector('[name=arquivo]').files[0];
            if(!file) throw new Error('Selecione o arquivo');
            const form=new FormData(); form.append('arquivo',file);
            const response=await fetch(`/api/residentes/${sgeRid}/documentos/${d.id}/arquivo`,{method:'POST',body:form});
            const data=await response.json(); if(!response.ok) throw new Error(data.erro||'Falha no upload');
        } else {
            await sgeApi(`/api/residentes/${sgeRid}/documentos`,{method:'POST',body:JSON.stringify({id:d.id,nome:d.nome,obrigatorio:!!d.obrigatorio,arquivo_id:d.arquivo_id,status:row.querySelector('[name=status]').value,validade:row.querySelector('[name=validade]').value,observacao:row.querySelector('[name=observacao]').value})});
        }
        await carregarDocumentos();
    } catch(error) {sgeErro(error);} finally {button.disabled=false;}
});
carregarDocumentos().catch(sgeErro);
