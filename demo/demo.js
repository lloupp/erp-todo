'use strict';

const STORAGE_KEY = 'erp-medical-demo-v3';
const STATUS_COLORS = {
  'Interessado':'#3b82f6','Em andamento':'#f59e0b','Deferido':'#8b5cf6','Confirmado':'#22c55e',
  'Indeferido':'#ef4444','Cancelado':'#6b7280','Desistente':'#f97316','Trocado':'#06b6d4','Nao veio':'#9ca3af'
};
const PIPELINE_LABELS = {
  1:'Triagem do cadastro',2:'Confirmação com o aluno',3:'Acionar chefe de serviço',4:'Deferimento da vaga',
  5:'Solicitar link ao Financeiro',6:'Enviar link e documentos',7:'Comprovante e documentos',8:'Orientações para o 1º dia'
};
const SPECIALTIES = ['Cardiologia','Pediatria','Neurologia','Cirurgia Geral','Ortopedia','Dermatologia','Anestesiologia','Psiquiatria','Ginecologia e Obstetrícia','Medicina Intensiva','Radiologia','Nefrologia'];
const INSTITUTIONS = ['Universidade Alfa','Hospital Universitário Beta','Faculdade Médica Gama','Universidade Delta','Centro Acadêmico Epsilon'];
const FIRST_NAMES = ['Ana','Bruno','Carla','Daniel','Elisa','Felipe','Gabriela','Henrique','Isabela','João','Karen','Lucas','Mariana','Nicolas','Olívia','Paulo','Rafaela','Samuel','Tatiana','Vinícius','Yasmin','Arthur','Beatriz','Caio'];
const LAST_NAMES = ['Costa Demo','Silva Demo','Oliveira Demo','Martins Demo','Souza Demo','Ferreira Demo','Lima Demo','Almeida Demo','Pereira Demo','Ramos Demo','Barros Demo','Melo Demo'];
const MONTHS = ['2026-09','2026-10','2026-11','2026-12','2027-01','2027-02'];
const STATUS_SEQ = ['Interessado','Em andamento','Em andamento','Deferido','Deferido','Confirmado','Interessado','Em andamento','Confirmado','Indeferido','Desistente','Trocado'];
let state = loadState();
let currentPage = 1;
const pageSize = 10;
let charts = {};
let pipelineCollapsed = false;

function seedState() {
  const residents = Array.from({length:36}, (_,i) => {
    const status = STATUS_SEQ[i % STATUS_SEQ.length];
    const stageMap = {'Interessado':1,'Em andamento':3,'Deferido':5,'Confirmado':0,'Indeferido':0,'Desistente':0,'Trocado':3};
    const etapa = stageMap[status] ?? 1;
    const payment = status === 'Confirmado' ? (i % 3 ? 'Pago':'Isento') : (i % 5 === 0 ? 'Pago':'Pendente');
    const month = MONTHS[i % MONTHS.length];
    const day = String((i % 26)+1).padStart(2,'0');
    return {
      id:i+1,
      nome:`${FIRST_NAMES[i % FIRST_NAMES.length]} ${LAST_NAMES[(i*3)%LAST_NAMES.length]}`,
      tipo:i % 4 === 0 ? 'Doutorando':'Residente',
      modalidade:i % 3 === 0 ? 'Convenio':'Optativo',
      especialidade:SPECIALTIES[(i*5)%SPECIALTIES.length],
      subespecialidade:i%7===0?'Área demonstrativa':'',
      instituicao:INSTITUTIONS[i%INSTITUTIONS.length],
      data_inscricao:`2026-${String(((i+7)%8)+1).padStart(2,'0')}-${day}`,
      periodo_desejado:`${day}/10/2026 a ${day}/11/2026`,
      mes_ano:month,
      status,
      status_pagamento:payment,
      forma_pagamento:payment==='Pago' ? (i%2?'PIX':'Boleto') : 'PIX',
      valor:1200 + (i%5)*250,
      email:`aluno.demo${String(i+1).padStart(2,'0')}@example.com`,
      telefone:`(00) 90000-${String(i+1).padStart(4,'0')}`,
      cpf:'000.000.000-00',
      programa:`R${(i%3)+1} — Programa Demo`,
      inicio:`${month}-01`,
      termino:`${month}-28`,
      comprovante:payment==='Pago'?`DEMO-${1000+i}`:'',
      observacoes:i%6===0?'Registro fictício preparado para demonstração.':'',
      etapa,
      dias_parado:etapa ? ((i*4)%19)+1 : 0,
      updated_at:`2026-09-${String((i%13)+1).padStart(2,'0')}`
    };
  });
  return {
    residents,
    users:[
      {id:1,nome:'Administrador Demo',username:'admin.demo',role:'admin',active:true,last:'Hoje, 09:12'},
      {id:2,nome:'Atendimento Demo',username:'atendimento.demo',role:'user',active:true,last:'Hoje, 08:45'},
      {id:3,nome:'Financeiro Demo',username:'financeiro.demo',role:'user',active:false,last:'12/09/2026'}
    ],
    config:{
      specialties:[...SPECIALTIES],
      limits:Object.fromEntries(SPECIALTIES.slice(0,8).map((s,i)=>[s,4+(i%4)])),
      messages:{
        confirmacao:'Olá! Recebemos sua solicitação de estágio. Confirme, por favor, se mantém interesse no período informado.',
        orientacoes:'Olá! Seu estágio está confirmado. Apresente-se às 07h30 na recepção acadêmica com documento de identificação.'
      }
    }
  };
}
function loadState(){try{const raw=localStorage.getItem(STORAGE_KEY);return raw?JSON.parse(raw):seedState()}catch{return seedState()}}
function saveState(){localStorage.setItem(STORAGE_KEY,JSON.stringify(state))}
function resetDemo(){state=seedState();saveState();renderAll();toast('Demo restaurada com dados fictícios originais.')}
function esc(s){return String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
function fmtMoney(v){return Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'})}
function fmtDate(s){if(!s)return '—';const p=String(s).slice(0,10).split('-');return p.length===3?`${p[2]}/${p[1]}/${p[0]}`:s}
function toast(msg){const el=document.getElementById('toast');el.textContent=msg;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),2600)}
function openModal(id){document.getElementById(id)?.classList.add('active');document.body.classList.add('no-scroll')}
function closeModal(id){document.getElementById(id)?.classList.remove('active');document.body.classList.remove('no-scroll')}

function routeTo(name){
  const valid=['dashboard','residentes','relatorios','usuarios','configuracoes']; if(!valid.includes(name)) name='residentes';
  document.querySelectorAll('.demo-view').forEach(v=>v.classList.toggle('active',v.dataset.view===name));
  document.querySelectorAll('.nav-link').forEach(a=>a.classList.toggle('active',a.dataset.route===name));
  const titles={dashboard:'Dashboard',residentes:'Residentes & Doutorandos',relatorios:'Relatórios',usuarios:'Usuários',configuracoes:'Configurações'};
  document.getElementById('page-title').textContent=titles[name];
  renderTopbar(name);
  document.getElementById('sidebar').classList.remove('open');
  if(name==='dashboard') renderDashboard();
  if(name==='residentes') renderResidents();
  if(name==='relatorios') renderReports();
  if(name==='usuarios') renderUsers();
  if(name==='configuracoes') renderConfig();
}

function themeToggle(){const root=document.documentElement;const next=root.getAttribute('data-theme')==='dark'?'light':'dark';root.setAttribute('data-theme',next);localStorage.setItem('erp-demo-theme',next);renderDashboard();renderReports()}
function renderTopbar(view){
  const root=document.getElementById('topbar-actions');
  let html='';
  if(view==='residentes') html='<button class="btn btn-sm btn-secondary" id="import-btn">&#8679; Importar Excel</button><button class="btn btn-sm btn-secondary" id="export-residents">&#8681; Exportar CSV</button><button class="btn btn-sm btn-primary" id="new-resident">+ Novo</button>';
  if(view==='dashboard') html='<select id="dash-month" class="btn btn-sm"><option value="">Todos os períodos</option></select>';
  if(view==='relatorios') html='<button class="btn btn-sm btn-secondary" id="top-export-report">&#8681; Exportar CSV</button>';
  html+='<button class="theme-toggle" id="theme-toggle" title="Alternar tema">&#9790;</button>';
  root.innerHTML=html;
  root.querySelector('#theme-toggle')?.addEventListener('click',themeToggle);
  root.querySelector('#new-resident')?.addEventListener('click',()=>editResident());
  root.querySelector('#import-btn')?.addEventListener('click',()=>openModal('import-modal'));
  root.querySelector('#export-residents')?.addEventListener('click',exportResidents);
  root.querySelector('#top-export-report')?.addEventListener('click',exportReport);
  if(view==='dashboard'){
    fillMonthSelect(root.querySelector('#dash-month'));
    root.querySelector('#dash-month').addEventListener('change',renderDashboard);
  }
}

function getFilters(){return {
  q:document.getElementById('f-busca')?.value.trim().toLowerCase()||'',tipo:document.getElementById('f-tipo')?.value||'',modalidade:document.getElementById('f-modalidade')?.value||'',esp:document.getElementById('f-especialidade')?.value||'',mes:document.getElementById('f-mes')?.value||'',insc:document.getElementById('f-mes-inscricao')?.value||'',status:document.getElementById('f-status')?.value||'',pag:document.getElementById('f-pagamento')?.value||'',sort:document.getElementById('f-ordenar')?.value||'recentes'
}}
function filteredResidents(){const f=getFilters();let rows=state.residents.filter(r=>(!f.q||[r.nome,r.email,r.cpf,r.especialidade].some(x=>String(x).toLowerCase().includes(f.q)))&&(!f.tipo||r.tipo===f.tipo)&&(!f.modalidade||r.modalidade===f.modalidade)&&(!f.esp||r.especialidade===f.esp)&&(!f.mes||r.mes_ano===f.mes)&&(!f.insc||r.data_inscricao.slice(0,7)===f.insc)&&(!f.status||r.status===f.status)&&(!f.pag||r.status_pagamento===f.pag));
  if(f.sort==='nome') rows.sort((a,b)=>a.nome.localeCompare(b.nome)); else if(f.sort==='mes_ano') rows.sort((a,b)=>a.mes_ano.localeCompare(b.mes_ano)); else rows.sort((a,b)=>b.id-a.id); return rows}

function renderWelcome(){
  const rows=state.residents; const counts={new:rows.filter(r=>r.status==='Interessado').length,run:rows.filter(r=>r.status==='Em andamento').length,defer:rows.filter(r=>r.status==='Deferido').length,pay:rows.filter(r=>r.status_pagamento==='Pendente').length};
  document.getElementById('welcome-banner').innerHTML=`<div class="demo-chip-row"><button class="demo-chip" data-filter-status="Interessado"><strong>${counts.new}</strong><span>Novas inscrições</span></button><button class="demo-chip" data-filter-status="Em andamento"><strong>${counts.run}</strong><span>Em andamento</span></button><button class="demo-chip" data-filter-status="Deferido"><strong>${counts.defer}</strong><span>Deferidos</span></button><button class="demo-chip" data-filter-pay="Pendente"><strong>${counts.pay}</strong><span>Pagamentos pendentes</span></button></div>`;
  document.querySelectorAll('[data-filter-status]').forEach(b=>b.onclick=()=>{document.getElementById('f-status').value=b.dataset.filterStatus;currentPage=1;renderResidents()});
  document.querySelectorAll('[data-filter-pay]').forEach(b=>b.onclick=()=>{document.getElementById('f-pagamento').value=b.dataset.filterPay;currentPage=1;renderResidents()});
}

function paymentBadge(r){const c={'Pago':'badge-pago','Pendente':'badge-pendente','Isento':'badge-isento','Cancelado':'badge-cancelado-pag'}[r.status_pagamento]||'badge-pendente';return `<span class="${c}">${esc(r.status_pagamento)}</span>`}
function statusBadge(r){return `<span class="badge-status" style="background:${STATUS_COLORS[r.status]||'#6b7280'}">${esc(r.status)}</span>`}
function renderResidents(){
  populateResidentFilters(); renderWelcome(); renderPipelineQueue();
  const all=filteredResidents(); const pages=Math.max(1,Math.ceil(all.length/pageSize)); if(currentPage>pages) currentPage=pages; const start=(currentPage-1)*pageSize; const rows=all.slice(start,start+pageSize);
  document.getElementById('resident-count').textContent=`${all.length} registro${all.length===1?'':'s'} encontrado${all.length===1?'':'s'}`;
  const body=document.getElementById('tabela-residentes'); body.innerHTML=rows.map(r=>`<tr>
    <td data-label="Nome"><strong>${esc(r.nome)}</strong><div style="font-size:11px;color:var(--color-text-secondary)">${esc(r.email)}</div></td>
    <td data-label="Tipo"><span class="badge-tipo badge-${esc(r.tipo)}">${esc(r.tipo)}</span></td><td data-label="Especialidade">${esc(r.especialidade)}</td><td data-label="Instituição">${esc(r.instituicao)}</td><td data-label="Data inscrição">${fmtDate(r.data_inscricao)}</td><td data-label="Mês desejado">${esc(r.mes_ano)}</td><td data-label="Período">${esc(r.periodo_desejado)}</td><td data-label="Mês/Ano">${esc(r.mes_ano)}</td><td data-label="Status">${statusBadge(r)}</td><td data-label="Pagamento">${paymentBadge(r)}</td>
    <td data-label="Ações"><div class="action-row"><button class="btn btn-sm" data-edit="${r.id}">Editar</button>${r.etapa?`<button class="btn btn-sm btn-primary" data-pipeline="${r.id}">Próxima ação</button>`:''}<details class="ux-row-more"><summary>Mais</summary><div class="ux-row-more-menu"><button class="btn btn-sm" data-message="${r.id}">Mensagem</button><button class="btn btn-sm" data-clone="${r.id}">Duplicar</button><button class="btn btn-sm btn-danger" data-delete="${r.id}">Excluir demo</button></div></details></div></td></tr>`).join('');
  document.getElementById('empty-state').style.display=rows.length?'none':'block';
  body.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>editResident(Number(b.dataset.edit)));
  body.querySelectorAll('[data-pipeline]').forEach(b=>b.onclick=()=>openPipeline(Number(b.dataset.pipeline)));
  body.querySelectorAll('[data-message]').forEach(b=>b.onclick=()=>openMessage(Number(b.dataset.message)));
  body.querySelectorAll('[data-clone]').forEach(b=>b.onclick=()=>cloneResident(Number(b.dataset.clone)));
  body.querySelectorAll('[data-delete]').forEach(b=>b.onclick=()=>deleteResident(Number(b.dataset.delete)));
  renderPagination(pages);
}
function populateResidentFilters(){const sel=document.getElementById('f-especialidade');if(!sel.dataset.ready){sel.innerHTML='<option value="">Todas especialidades</option>'+state.config.specialties.map(s=>`<option>${esc(s)}</option>`).join('');sel.dataset.ready='1'}const dl=document.getElementById('specialty-list');dl.innerHTML=state.config.specialties.map(s=>`<option value="${esc(s)}"></option>`).join('')}
function renderPagination(pages){const root=document.getElementById('paginacao');root.innerHTML=`<button ${currentPage<=1?'disabled':''} id="prev-page">Anterior</button><span>Página ${currentPage} de ${pages}</span><button ${currentPage>=pages?'disabled':''} id="next-page">Próxima</button>`;root.querySelector('#prev-page').onclick=()=>{currentPage--;renderResidents()};root.querySelector('#next-page').onclick=()=>{currentPage++;renderResidents()}}

function renderPipelineQueue(){
  const pending=state.residents.filter(r=>r.etapa).sort((a,b)=>b.dias_parado-a.dias_parado); const root=document.getElementById('pipeline-fila-lista');
  if(pipelineCollapsed){root.style.display='none';return} root.style.display='block';
  root.innerHTML=`<table class="pipeline-table"><thead><tr><th>Aluno</th><th>Especialidade</th><th>Etapa</th><th>Parado</th><th>Ação</th></tr></thead><tbody>${pending.slice(0,12).map(r=>`<tr><td><strong>${esc(r.nome)}</strong></td><td>${esc(r.especialidade)}</td><td>${r.etapa} — ${esc(PIPELINE_LABELS[r.etapa])}</td><td class="${r.dias_parado>14?'days-danger':r.dias_parado>7?'days-warn':''}">${r.dias_parado} dias</td><td><button class="btn btn-sm btn-primary" data-queue="${r.id}">Atuar</button></td></tr>`).join('')}</tbody></table>`;
  root.querySelectorAll('[data-queue]').forEach(b=>b.onclick=()=>openPipeline(Number(b.dataset.queue)));
}

function editResident(id){
  const r=id?state.residents.find(x=>x.id===id):{tipo:'Residente',modalidade:'Optativo',nome:'',cpf:'000.000.000-00',email:'',telefone:'(00) 90000-0000',instituicao:'',especialidade:'',subespecialidade:'',mes_ano:'2026-10',status:'Interessado',inicio:'2026-10-01',termino:'2026-10-28',programa:'',valor:1500,forma_pagamento:'PIX',status_pagamento:'Pendente',comprovante:'',observacoes:''};
  const map={'form-id':r.id||'','form-tipo':r.tipo,'form-modalidade':r.modalidade,'form-nome':r.nome,'form-cpf':r.cpf,'form-email':r.email,'form-telefone':r.telefone,'form-instituicao':r.instituicao,'form-especialidade':r.especialidade,'form-subesp':r.subespecialidade,'form-mes-ano':r.mes_ano,'form-status':r.status,'form-inicio':r.inicio,'form-termino':r.termino,'form-programa':r.programa,'form-valor':r.valor,'form-forma-pag':r.forma_pagamento,'form-status-pag':r.status_pagamento,'form-comprovante':r.comprovante,'form-observacoes':r.observacoes};
  Object.entries(map).forEach(([k,v])=>{const e=document.getElementById(k);if(e)e.value=v??''}); document.getElementById('resident-modal-title').textContent=id?'Editar Residente':'Novo Residente'; openModal('resident-modal');
}
function saveResidentFromForm(){
  const id=Number(document.getElementById('form-id').value||0); const existing=state.residents.find(r=>r.id===id); const status=document.getElementById('form-status').value;
  const obj={...(existing||{}),id:id||Math.max(0,...state.residents.map(r=>r.id))+1,tipo:document.getElementById('form-tipo').value,modalidade:document.getElementById('form-modalidade').value,nome:document.getElementById('form-nome').value.trim()||'Novo Aluno Demo',cpf:document.getElementById('form-cpf').value,email:document.getElementById('form-email').value||`novo.demo${Date.now()%1000}@example.com`,telefone:document.getElementById('form-telefone').value,instituicao:document.getElementById('form-instituicao').value,especialidade:document.getElementById('form-especialidade').value||'Cardiologia',subespecialidade:document.getElementById('form-subesp').value,mes_ano:document.getElementById('form-mes-ano').value||'2026-10',status,inicio:document.getElementById('form-inicio').value,termino:document.getElementById('form-termino').value,programa:document.getElementById('form-programa').value,valor:Number(document.getElementById('form-valor').value||0),forma_pagamento:document.getElementById('form-forma-pag').value,status_pagamento:document.getElementById('form-status-pag').value,comprovante:document.getElementById('form-comprovante').value,observacoes:document.getElementById('form-observacoes').value,data_inscricao:existing?.data_inscricao||'2026-09-14',periodo_desejado:existing?.periodo_desejado||'01/10/2026 a 28/10/2026',etapa:existing?.etapa ?? (status==='Interessado'?1:status==='Em andamento'?3:status==='Deferido'?5:0),dias_parado:existing?.dias_parado??1,updated_at:'2026-09-14'};
  if(existing) Object.assign(existing,obj); else state.residents.push(obj); saveState(); closeModal('resident-modal'); renderAll(); toast(existing?'Cadastro atualizado na demo.':'Novo cadastro fictício criado.')
}
function cloneResident(id){const r=state.residents.find(x=>x.id===id);if(!r)return;const c={...r,id:Math.max(...state.residents.map(x=>x.id))+1,nome:r.nome+' (cópia)',email:`copia.demo${Date.now()%1000}@example.com`,status:'Interessado',etapa:1,dias_parado:1};state.residents.push(c);saveState();renderAll();toast('Registro duplicado na demo.')}
function deleteResident(id){state.residents=state.residents.filter(r=>r.id!==id);saveState();renderAll();toast('Registro fictício removido.')}

function openPipeline(id){
  const r=state.residents.find(x=>x.id===id);if(!r)return;document.getElementById('pipeline-modal-title').textContent=`Pipeline — ${r.nome}`;
  const body=document.getElementById('pipeline-modal-body');body.innerHTML=Object.entries(PIPELINE_LABELS).map(([n,label])=>{const stage=Number(n), cls=stage<r.etapa||!r.etapa?'done':stage===r.etapa?'pending':'';return `<div class="demo-stage ${cls}"><div class="demo-stage-index">${stage<r.etapa||!r.etapa?'✓':stage}</div><div><strong>${esc(label)}</strong><small>${stage<r.etapa||!r.etapa?'Concluída':stage===r.etapa?`Pendente há ${r.dias_parado} dias`:'Aguardando etapa anterior'}</small></div></div>`}).join('');
  const foot=document.getElementById('pipeline-modal-footer');
  if(!r.etapa){foot.innerHTML='<button class="btn" data-close="pipeline-modal">Fechar</button>'}
  else {let alt=''; if(r.etapa===2)alt='<button class="btn btn-danger" id="pipeline-desist">Registrar desistência</button>';if(r.etapa===4)alt='<button class="btn btn-danger" id="pipeline-deny">Indeferir</button>';foot.innerHTML=`<button class="btn btn-ghost" data-close="pipeline-modal">Cancelar</button>${alt}<button class="btn btn-primary" id="pipeline-advance">Concluir etapa ${r.etapa}</button>`;foot.querySelector('#pipeline-advance').onclick=()=>advancePipeline(id);foot.querySelector('#pipeline-desist')?.addEventListener('click',()=>finishPipeline(id,'Desistente'));foot.querySelector('#pipeline-deny')?.addEventListener('click',()=>finishPipeline(id,'Indeferido'))}
  foot.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>closeModal('pipeline-modal'));openModal('pipeline-modal');
}
function advancePipeline(id){const r=state.residents.find(x=>x.id===id);if(!r||!r.etapa)return;const stage=r.etapa;if(stage===2)r.status='Em andamento';if(stage===4)r.status='Deferido';if(stage===7&&r.status_pagamento==='Pendente')r.status_pagamento='Pago';if(stage===8){r.status='Confirmado';r.etapa=0;r.dias_parado=0}else{r.etapa++;r.dias_parado=0}r.updated_at='2026-09-14';saveState();closeModal('pipeline-modal');renderAll();toast(`Etapa ${stage} concluída na demo.`)}
function finishPipeline(id,status){const r=state.residents.find(x=>x.id===id);if(!r)return;r.status=status;r.etapa=0;r.dias_parado=0;saveState();closeModal('pipeline-modal');renderAll();toast(`Processo marcado como ${status}.`)}

function openMessage(id){const r=state.residents.find(x=>x.id===id);if(!r)return;document.getElementById('message-title').textContent=`Mensagem — ${r.nome}`;document.getElementById('message-text').value=`Olá, ${r.nome.split(' ')[0]}! ${state.config.messages.confirmacao}`;document.getElementById('message-modal').dataset.resident=id;openModal('message-modal')}

function importFictitious(){const base=Math.max(...state.residents.map(r=>r.id))+1;['Cardiologia','Pediatria','Neurologia'].forEach((esp,j)=>state.residents.push({id:base+j,nome:`Importado Demo 0${j+1}`,tipo:j===1?'Doutorando':'Residente',modalidade:'Optativo',especialidade:esp,subespecialidade:'',instituicao:'Instituição Importada Demo',data_inscricao:'2026-09-14',periodo_desejado:'01/11/2026 a 28/11/2026',mes_ano:'2026-11',status:'Interessado',status_pagamento:'Pendente',forma_pagamento:'PIX',valor:1500,email:`importado.demo${j+1}@example.com`,telefone:`(00) 90000-10${j+1}0`,cpf:'000.000.000-00',programa:'Programa Importado Demo',inicio:'2026-11-01',termino:'2026-11-28',comprovante:'',observacoes:'Criado pelo simulador de importação.',etapa:1,dias_parado:1,updated_at:'2026-09-14'}));saveState();closeModal('import-modal');renderAll();toast('3 registros fictícios importados.')}

function fillMonthSelect(sel){if(!sel)return;const current=sel.value;const months=[...new Set(state.residents.map(r=>r.mes_ano))].sort();sel.innerHTML='<option value="">Todos os períodos</option>'+months.map(m=>`<option value="${m}">${m}</option>`).join('');sel.value=current}
function dashboardData(month=''){const rows=state.residents.filter(r=>!month||r.mes_ano===month);const count=k=>rows.filter(k).length;const by=(key)=>Object.entries(rows.reduce((a,r)=>{const v=r[key]||'Não informado';a[v]=(a[v]||0)+1;return a},{})).map(([name,count])=>({name,count}));return{rows,total:rows.length,kpis:{criticos:count(r=>r.etapa&&r.dias_parado>14),alertas:count(r=>r.etapa&&r.dias_parado>7&&r.dias_parado<=14),novos:count(r=>r.status==='Interessado'),em_andamento:count(r=>r.status==='Em andamento'),deferidos:count(r=>r.status==='Deferido'),confirmados:count(r=>r.status==='Confirmado'),pag_pendente:count(r=>r.status_pagamento==='Pendente')},financeiro:{pago:rows.filter(r=>r.status_pagamento==='Pago').reduce((s,r)=>s+r.valor,0),pendente:rows.filter(r=>r.status_pagamento==='Pendente').reduce((s,r)=>s+r.valor,0)},status:by('status'),tipo:by('tipo'),esp:by('especialidade').sort((a,b)=>b.count-a.count),mes:by('mes_ano').sort((a,b)=>a.name.localeCompare(b.name)),recentes:[...rows].sort((a,b)=>b.id-a.id).slice(0,8)}}

function destroyChart(name){if(charts[name]){charts[name].destroy();delete charts[name]}}
function chartTheme(){const dark=document.documentElement.getAttribute('data-theme')==='dark';return{text:dark?'#f9fafb':'#1f2937',grid:dark?'#374151':'#e5e7eb',surface:dark?'#1f2937':'#fff'}}
function renderDashboard(){
  if(!document.getElementById('view-dashboard').classList.contains('active'))return;const sel=document.getElementById('dash-month');const month=sel?.value||'';const d=dashboardData(month);if(sel)fillMonthSelect(sel);const K=d.kpis;
  document.getElementById('dashboard-container').innerHTML=`<div class="dash-section-title">RESIDENTES & DOUTORANDOS${month?` — ${month}`:''}</div><div class="kpi-grid">
  ${kpi('👥',d.total,'Total','#eff6ff','#1d4ed8')}${kpi('⚠',K.criticos,'Críticos (+14d parado)','#fef2f2','#dc2626',K.criticos?'kpi-danger':'')}${kpi('⚡',K.alertas,'Alertas (7–14d parado)','#fff7ed','#d97706',K.alertas?'kpi-warn':'')}${kpi('🆕',K.novos,'Interessados','#eff6ff','#1d4ed8')}${kpi('▶',K.em_andamento,'Em andamento','#fefce8','#854d0e')}${kpi('✔',K.deferidos,'Deferidos','#eff6ff','#1e40af')}${kpi('🎓',K.confirmados,'Confirmados','#f0fdf4','#166534')}${kpi('💰',K.pag_pendente,'Pagto Pendente','#fefce8','#854d0e',K.pag_pendente?'kpi-warn':'')}${kpi('💵',fmtMoney(d.financeiro.pago),'Total Pago','#f0fdf4','#166534')}${kpi('💸',fmtMoney(d.financeiro.pendente),'Valor Pendente','#fefce8','#854d0e')}</div>
  <div class="charts-grid charts-grid-3"><div class="chart-card"><h3>Residentes por Status</h3><div class="chart-canvas-wrap"><canvas id="dash-status"></canvas></div></div><div class="chart-card"><h3>Residentes por Tipo</h3><div class="chart-canvas-wrap"><canvas id="dash-type"></canvas></div></div><div class="chart-card"><h3>Top Especialidades</h3><div class="chart-canvas-wrap"><canvas id="dash-esp"></canvas></div></div></div>
  <div class="charts-grid"><div class="chart-card" style="grid-column:1/-1"><h3>Tendência Mensal — Residentes</h3><div class="chart-canvas-wrap" style="height:240px"><canvas id="dash-month-chart"></canvas></div></div></div>
  <div class="chart-card" style="margin-bottom:32px"><h3>Residentes Atualizados Recentemente</h3><table class="recent-table"><thead><tr><th>Nome</th><th>Tipo</th><th>Especialidade</th><th>Status</th><th>Pagto</th><th>Atualizado</th></tr></thead><tbody>${d.recentes.map(r=>`<tr><td><strong>${esc(r.nome)}</strong></td><td>${r.tipo}</td><td>${r.especialidade}</td><td style="font-weight:600;color:${STATUS_COLORS[r.status]}">${r.status}</td><td>${r.status_pagamento}</td><td>${fmtDate(r.updated_at)}</td></tr>`).join('')}</tbody></table></div>`;
  renderDashCharts(d)
}
function kpi(icon,val,label,bg,color,extra=''){return `<div class="kpi-card ${extra}"><div class="kpi-icon" style="background:${bg};color:${color}">${icon}</div><div class="kpi-body"><div class="kpi-val">${val}</div><div class="kpi-label">${label}</div></div></div>`}
function renderDashCharts(d){const c=chartTheme();['dashStatus','dashType','dashEsp','dashMonth'].forEach(destroyChart);charts.dashStatus=new Chart(document.getElementById('dash-status'),{type:'doughnut',data:{labels:d.status.map(x=>x.name),datasets:[{data:d.status.map(x=>x.count),backgroundColor:d.status.map(x=>STATUS_COLORS[x.name]||'#9ca3af'),borderColor:c.surface}]},options:{responsive:true,maintainAspectRatio:false,cutout:'60%',plugins:{legend:{position:'bottom',labels:{color:c.text,font:{size:10}}}}}});charts.dashType=new Chart(document.getElementById('dash-type'),{type:'doughnut',data:{labels:d.tipo.map(x=>x.name),datasets:[{data:d.tipo.map(x=>x.count),backgroundColor:['#3b82f6','#8b5cf6'],borderColor:c.surface}]},options:{responsive:true,maintainAspectRatio:false,cutout:'60%',plugins:{legend:{position:'bottom',labels:{color:c.text}}}}});charts.dashEsp=new Chart(document.getElementById('dash-esp'),{type:'bar',data:{labels:d.esp.slice(0,8).map(x=>x.name),datasets:[{data:d.esp.slice(0,8).map(x=>x.count),backgroundColor:'#3b82f6',borderRadius:4}]},options:{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{ticks:{color:c.text},grid:{color:c.grid}},y:{ticks:{color:c.text,font:{size:10}},grid:{color:c.grid}}}}});charts.dashMonth=new Chart(document.getElementById('dash-month-chart'),{type:'line',data:{labels:d.mes.map(x=>x.name),datasets:[{label:'Qtd Residentes',data:d.mes.map(x=>x.count),borderColor:'#3b82f6',backgroundColor:'rgba(59,130,246,.15)',fill:true,tension:.3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:c.text}}},scales:{x:{ticks:{color:c.text},grid:{color:c.grid}},y:{ticks:{color:c.text},grid:{color:c.grid},beginAtZero:true}}}})}

function renderReports(){
  const sel=document.getElementById('report-month');fillMonthSelect(sel);const d=dashboardData(sel.value);const pending=state.residents.filter(r=>r.etapa);const totalQueue=pending.length;document.getElementById('reports-status').textContent=`Atualizado agora · ${sel.value||'todos os meses'}`;
  const items=[['Cadastros',d.total,'Total no período'],['Novas inscrições',d.kpis.novos,'Status Interessado'],['Em andamento',d.kpis.em_andamento,'Atendimento iniciado'],['Deferidos',d.kpis.deferidos,'Vaga deferida'],['Confirmados',d.kpis.confirmados,'Etapa final'],['Pagamentos pendentes',d.kpis.pag_pendente,'Cobrança em aberto','attention'],['Valor pendente',fmtMoney(d.financeiro.pendente),'Saldo demonstrativo','attention'],['Críticos',d.kpis.criticos,'Mais de 14 dias sem avanço','critical'],['Alertas',d.kpis.alertas,'Entre 8 e 14 dias','attention'],['Fila atual',totalQueue,'Ações pendentes']];
  document.getElementById('reports-kpis').innerHTML=items.map(([l,v,n,c=''])=>`<article class="report-kpi ${c}"><span class="report-kpi-label">${l}</span><strong class="report-kpi-value">${v}</strong><span class="report-kpi-note">${n}</span></article>`).join('');
  document.getElementById('report-pipeline').innerHTML=Object.entries(PIPELINE_LABELS).map(([stage,label])=>{const count=pending.filter(r=>r.etapa===Number(stage)).length;return `<div class="report-pipeline-row"><div class="report-pipeline-name">${stage} — ${label}</div><span class="report-badge">${count}</span><a href="#residentes" class="btn btn-sm btn-ghost">Abrir fila</a></div>`}).join('');
  const shortcuts=[['Novas inscrições','Interessado'],['Em andamento','Em andamento'],['Deferidos','Deferido'],['Confirmados','Confirmado'],['Pagamentos pendentes','Pendente']];document.getElementById('report-shortcuts').innerHTML=shortcuts.map(([label,val])=>`<a class="report-action" href="#residentes" data-report-filter="${val}"><strong>${label}</strong><span>Abrir lista operacional correspondente.</span></a>`).join('');document.querySelectorAll('[data-report-filter]').forEach(a=>a.onclick=()=>{setTimeout(()=>{if(a.dataset.reportFilter==='Pendente')document.getElementById('f-pagamento').value='Pendente';else document.getElementById('f-status').value=a.dataset.reportFilter;renderResidents()},10)});
  renderReportCharts(d)
}
function renderReportCharts(d){const c=chartTheme();['reportStatus','reportEsp','reportMonth'].forEach(destroyChart);charts.reportStatus=new Chart(document.getElementById('report-status-chart'),{type:'doughnut',data:{labels:d.status.map(x=>x.name),datasets:[{data:d.status.map(x=>x.count),backgroundColor:d.status.map(x=>STATUS_COLORS[x.name]||'#9ca3af'),borderColor:c.surface}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'bottom',labels:{color:c.text,font:{size:10}}}}}});charts.reportEsp=new Chart(document.getElementById('report-specialty-chart'),{type:'bar',data:{labels:d.esp.slice(0,8).map(x=>x.name),datasets:[{data:d.esp.slice(0,8).map(x=>x.count),backgroundColor:'#3b82f6'}]},options:{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{ticks:{color:c.text},grid:{color:c.grid}},y:{ticks:{color:c.text,font:{size:10}},grid:{display:false}}}}});charts.reportMonth=new Chart(document.getElementById('report-month-chart'),{type:'bar',data:{labels:d.mes.map(x=>x.name),datasets:[{data:d.mes.map(x=>x.count),backgroundColor:'#8b5cf6'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:c.text},grid:{display:false}},y:{ticks:{color:c.text},grid:{color:c.grid},beginAtZero:true}}}})}

function csvCell(v){let s=String(v??'');if(/^[=+\-@]/.test(s))s=`'${s}`;return `"${s.replace(/"/g,'""')}"`}
function downloadCsv(filename,rows){const csv='\ufeff'+rows.map(r=>r.map(csvCell).join(';')).join('\r\n');const blob=new Blob([csv],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);toast('CSV gerado pela demonstração.')}
function exportResidents(){const rows=filteredResidents();downloadCsv('residentes_demo.csv',[['Nome','Tipo','Especialidade','Instituição','Mês/Ano','Status','Pagamento','E-mail'],...rows.map(r=>[r.nome,r.tipo,r.especialidade,r.instituicao,r.mes_ano,r.status,r.status_pagamento,r.email])])}
function exportReport(){const month=document.getElementById('report-month')?.value||'';const d=dashboardData(month);downloadCsv('relatorio_gerencial_demo.csv',[['Relatório gerencial DEMO'],['Filtro',month||'Todos'],[],['Indicador','Valor'],['Cadastros',d.total],['Interessados',d.kpis.novos],['Em andamento',d.kpis.em_andamento],['Deferidos',d.kpis.deferidos],['Confirmados',d.kpis.confirmados],['Pagamento pendente',d.kpis.pag_pendente],['Valor pendente',d.financeiro.pendente],[],['Status','Quantidade'],...d.status.map(x=>[x.name,x.count]),[],['Especialidade','Quantidade'],...d.esp.map(x=>[x.name,x.count])])}

function renderUsers(){const body=document.getElementById('users-table');body.innerHTML=state.users.map(u=>`<tr><td><strong>${esc(u.nome)}</strong></td><td>${esc(u.username)}</td><td>${u.role==='admin'?'Administrador':'Usuário'}</td><td><span class="user-status ${u.active?'on':'off'}">${u.active?'Ativo':'Inativo'}</span></td><td>${esc(u.last)}</td><td><button class="btn btn-sm" data-user-toggle="${u.id}">${u.active?'Desativar':'Ativar'}</button></td></tr>`).join('');body.querySelectorAll('[data-user-toggle]').forEach(b=>b.onclick=()=>{const u=state.users.find(x=>x.id===Number(b.dataset.userToggle));u.active=!u.active;saveState();renderUsers();toast('Status do usuário alterado na demo.')})}
function addUser(){const name=document.getElementById('user-name').value.trim()||'Novo Usuário Demo';const username=document.getElementById('user-login').value.trim()||`usuario.demo${state.users.length+1}`;state.users.push({id:Math.max(...state.users.map(u=>u.id))+1,nome:name,username,role:document.getElementById('user-role').value,active:true,last:'Nunca'});saveState();closeModal('user-modal');renderUsers();toast('Usuário fictício adicionado.')}

function renderConfig(){const cfg=state.config;document.getElementById('limits-list').innerHTML=Object.entries(cfg.limits).map(([s,v])=>`<div class="limit-row"><span>${esc(s)}</span><input type="number" min="1" value="${v}" data-limit="${esc(s)}"></div>`).join('');document.getElementById('msg-confirmacao').value=cfg.messages.confirmacao;document.getElementById('msg-orientacoes').value=cfg.messages.orientacoes;document.getElementById('specialty-tags').innerHTML=cfg.specialties.map(s=>`<span class="demo-tag">${esc(s)}</span>`).join('')}
function saveConfig(){document.querySelectorAll('[data-limit]').forEach(i=>state.config.limits[i.dataset.limit]=Number(i.value||1));state.config.messages.confirmacao=document.getElementById('msg-confirmacao').value;state.config.messages.orientacoes=document.getElementById('msg-orientacoes').value;saveState();toast('Configurações salvas localmente na demo.')}
function addSpecialty(){const input=document.getElementById('new-specialty');const v=input.value.trim();if(v&&!state.config.specialties.includes(v)){state.config.specialties.push(v);state.config.limits[v]=4;input.value='';saveState();document.getElementById('f-especialidade').dataset.ready='';renderConfig();populateResidentFilters();toast('Especialidade fictícia adicionada.')}}

function renderAI(kind){const pending=state.residents.filter(r=>r.etapa);let text='';if(kind==='fila'){const crit=pending.filter(r=>r.dias_parado>14).length;text=`A fila demonstrativa possui ${pending.length} ações pendentes. ${crit} estão críticas (>14 dias). A etapa com mais volume é ${mostCommon(pending.map(r=>r.etapa),n=>PIPELINE_LABELS[n])}.`}if(kind==='financeiro'){const rows=state.residents.filter(r=>r.status_pagamento==='Pendente');text=`Há ${rows.length} pagamentos pendentes, somando ${fmtMoney(rows.reduce((s,r)=>s+r.valor,0))}. Especialidade mais frequente: ${mostCommon(rows.map(r=>r.especialidade))}.`}if(kind==='criticos'){const rows=pending.filter(r=>r.dias_parado>14).sort((a,b)=>b.dias_parado-a.dias_parado);text=rows.length?`Prioridade máxima: ${rows.slice(0,3).map(r=>`${r.nome} (${r.dias_parado}d, etapa ${r.etapa})`).join('; ')}.`:'Não há casos críticos na base demonstrativa.'}document.getElementById('ai-answer').textContent=text}
function mostCommon(arr,format=x=>x){if(!arr.length)return 'nenhuma';const c={};arr.forEach(x=>c[x]=(c[x]||0)+1);const key=Object.entries(c).sort((a,b)=>b[1]-a[1])[0][0];return format(key)}

function renderAll(){if(document.getElementById('view-residentes').classList.contains('active'))renderResidents();if(document.getElementById('view-dashboard').classList.contains('active'))renderDashboard();if(document.getElementById('view-relatorios').classList.contains('active'))renderReports();if(document.getElementById('view-usuarios').classList.contains('active'))renderUsers();if(document.getElementById('view-configuracoes').classList.contains('active'))renderConfig()}

function bind(){
  document.documentElement.setAttribute('data-theme',localStorage.getItem('erp-demo-theme')||'light');
  document.getElementById('menu-toggle').onclick=()=>document.getElementById('sidebar').classList.toggle('open');
  window.addEventListener('hashchange',()=>routeTo(location.hash.slice(1)||'residentes'));
  document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>closeModal(b.dataset.close));
  document.querySelectorAll('.modal-overlay').forEach(m=>m.addEventListener('click',e=>{if(e.target===m)closeModal(m.id)}));
  ['f-busca','f-tipo','f-modalidade','f-especialidade','f-mes','f-mes-inscricao','f-status','f-pagamento','f-ordenar'].forEach(id=>document.getElementById(id)?.addEventListener(id==='f-busca'?'input':'change',()=>{currentPage=1;renderResidents()}));
  document.getElementById('clear-filters').onclick=()=>{['f-busca','f-tipo','f-modalidade','f-especialidade','f-mes','f-mes-inscricao','f-status','f-pagamento'].forEach(id=>document.getElementById(id).value='');document.getElementById('f-ordenar').value='recentes';currentPage=1;renderResidents()};
  document.getElementById('toggle-details').onclick=e=>{document.body.classList.toggle('show-table-details');e.target.textContent=document.body.classList.contains('show-table-details')?'Ocultar colunas extras':'Mostrar mais colunas'};
  document.getElementById('pipeline-toggle').onclick=()=>{pipelineCollapsed=!pipelineCollapsed;document.getElementById('pipeline-fila-toggle').textContent=pipelineCollapsed?'▼':'▲';renderPipelineQueue()};
  document.getElementById('save-resident').onclick=saveResidentFromForm;document.getElementById('confirm-import').onclick=importFictitious;document.getElementById('send-message').onclick=()=>{closeModal('message-modal');toast('Envio simulado. Nenhuma mensagem real foi enviada.')};
  document.getElementById('report-month').addEventListener('change',renderReports);document.getElementById('export-report').onclick=exportReport;
  document.getElementById('new-user').onclick=()=>openModal('user-modal');document.getElementById('save-user').onclick=addUser;
  document.getElementById('save-config').onclick=saveConfig;document.getElementById('add-specialty').onclick=addSpecialty;document.getElementById('reset-demo-settings').onclick=resetDemo;document.getElementById('reset-demo-sidebar').onclick=resetDemo;
  document.getElementById('ai-button').onclick=()=>document.getElementById('ai-panel').classList.toggle('open');document.getElementById('ai-close').onclick=()=>document.getElementById('ai-panel').classList.remove('open');document.querySelectorAll('.ai-quick').forEach(b=>b.onclick=()=>renderAI(b.dataset.ai));
  document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('.modal-overlay.active').forEach(m=>closeModal(m.id));if(e.key==='/'&&document.getElementById('view-residentes').classList.contains('active')&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();document.getElementById('f-busca').focus()}});
  routeTo(location.hash.slice(1)||'residentes');
}
document.addEventListener('DOMContentLoaded',bind);
