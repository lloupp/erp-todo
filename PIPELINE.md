# Pipeline de Atendimento — Residentes & Doutorandos

Fluxo de trabalho controlado do cadastro à conclusão do estágio, mapeando o atendimento humano feito pela equipe administrativa do Ensino e Pesquisa (Santa Casa / UFCSPA).

Princípio do sistema: **NADA é enviado automaticamente**. O ERP pergunta "fazer X agora?" e o humano confirma. Mensagens são sempre editáveis no modal antes de abrir o WhatsApp/email. Tudo é rastreável (responsável, timestamp, observação).

---

## Visão geral

```
Forms/Excel ──► [1] Le registro ──► [2] Confirma com cliente ──► [3] Aciona chefe de
                     │                                           serviço (vaga)
                     │                                                  │
                     ▼                                                  ▼
                  Interessado                                     Em andamento
                                                                         │
            ┌──────────────────────────────────────────────────────────┘
            ▼
       [4] Chefe defere vaga
            │  ├─ Defere  ─► Deferido ──► [5] Pede link ao financeiro
            │  └─ Indefere ─► Indeferido (pipeline encerra)
            │                              │
            ▼                              ▼
       Deferido                       [6] Envia link + docs ao cliente
                                           │
                                           ▼
                                      [7] Recebe comprovante + analisa
                                           │
                                           ▼
                                     Confirmado
                                           │
                                           ▼
                                  [8] Orientações 1ª semana
                                       (T = início - 7 dias)
                                           │
                                           ▼
                                     Concluído
```

---

## Tabela de etapas x status x ação no sistema

| Passo | Quando | Status residente | Ação humana | O que o sistema faz | Rastreio |
|:-----:|--------|:----------------:|-------------|---------------------|----------|
| 1 | Ao importar do Forms/Excel | Interessado | Lê registro (vaga + especialidade) | Cria ação etapa 1 pendente; lista na fila de triagem | `pipeline_acoes` |
| 2 | Após leitura | Interessado | Contata cliente (email/WhatsApp) confirmando pedido | Botão "Contatar" abre WhatsApp do aluno; botão "Confirmou" marca ação feita e cria etapa 2 pendente | `pipeline_acoes` |
| 3 | Cliente confirmou | Em andamento | Contata chefe de serviço da especialidade | Reaproveita modal Área Médica atual (msg + WhatsApp ao chefe); botão "Enviado" marca feita e cria etapa 3 pendente; alerta vermelho se >7 dias sem resposta | `pipeline_acoes` |
| 4 | Chefe responde | Em andamento → Deferido / Indeferido | Recebe deferimento do chefe | Botão "Defere" → status=Deferido, ação etapa 4 feita, cria etapa 5 pendente; botão "Indefere" → encerra pipeline | `pipeline_acoes` + `historico_residentes` |
| 5 | Após deferimento | Deferido | Pede ao financeiro para gerar link de pagamento | Botão "Solicitar link" abre WhatsApp com msg modelo ao financeiro; marca ação feita, cria etapa 6 pendente | `pipeline_acoes` |
| 6 | Link recebido do financeiro | Deferido | Envia link de pagamento + solicitação de documentos ao cliente | Botão "Enviar link + docs" abre modal com msg modelo (link + lista de docs); marca ação feita, cria etapa 7 pendente | `pipeline_acoes` |
| 7 | Cliente retorna | Deferido → Confirmado | Recebe comprovante de pagamento + documentos e faz análise manual | Botão "Comprovante + docs OK" → status=Confirmado, ação etapa 7 feita, cria etapa 8 pendente; alerta vermelho se >7 dias sem retorno | `pipeline_acoes` + `historico_residentes` |
| 8 | 7 dias antes do início | Confirmado → Concluído | Envia orientações para o primeiro dia | Sistema agenda ação etapa 8 pendente em `T = início - 7 dias`; no dia, banner "Enviar orientações hoje"; botão "Enviar orientações" abre msg modelo, marca feita e conclui | `pipeline_acoes` + `historico_residentes` |

---

## Detalhamento por passo

### Passo 1 — Leitura do registro

- **Trigger**: importação do Microsoft Forms (sync recorrente) ou importação manual de planilha Excel via `/api/residentes/importar-excel`. Também ocorre em cadastro manual pelo formulário.
- **Entrada**: a planilha do Forms é texto livre (não normalizado) nos campos `especialidade`, `instituicao_origem`, `programa_ano`, `mes_desejado`, `periodo_desejado`.
- **Humano**: abre o registro na fila de triagem, confere a especialidade digitada (o sistema sugere a-versão-canônica via `_melhor_match_especialidade` já existente), ajusta `mes_ano` a partir do `mes_desejado` se necessário, corrige campos óbvios.
- **Sistema**: ao concluir a triagem, marca a ação 1 como feita e cria a ação 2 (pende te). O residente permanece em `Interessado`.
- **Sair do passo**: botão "Revisado" na fila.

### Passo 2 — Confirmação com o cliente

- **Status**: `Interessado`.
- **Humano**: usa o botão WhatsApp do aluno (já existe em `residentes.js`), com mensagem modelo `whatsapp_aluno`, para confirmar o pedido (vaga e especialidade).
- **Desfechos**:
  - **Confirmou**: marca ação 2 como feita, avança status para `Em andamento` (via `/api/residentes/<id>/avancar` já existente), cria ação 3 pendente.
  - **Não respondeu / cancelou**: ação 2 permanece pendente; depois de N dias sem resposta, o sistema sugere mover para `Desistente` (mas só com confirmação humana).
- **Sair do passo**: botão "Confirmou" (avança) ou "Reagendar" (permite remarcar/observar).

### Passo 3 — Acionamento do chefe de serviço

- **Status**: `Em andamento`.
- **Humano**: usa o botão Área Médica (já existe, `abrirModalAreaMedica`), que sugere automaticamente o contato do chefe da especialidade mais próxima e abre modal com mensagem `whatsapp_area_medica` editável. Envia por WhatsApp (ou email, se o chefe não tiver WhatsApp).
- **Sistema**: botão "Enviado" marca ação 3 como feita, cria ação 4 pendente. Se passaram >7 dias sem a ação 4 ser concluída (sem resposta do chefe), o registro entra em alerta vermelho na fila (mesma lógica de `dias_no_status` já usada no front).
- **Sair do passo**: botão "Enviado" (registra que o contato foi feito).

### Passo 4 — Deferimento da vaga

- **Status**: `Em andamento`.
- **Humano**: recebe a resposta do chefe de serviço (via WhatsApp/email) e registra o deferimento ou indeferimento.
- **Desfechos**:
  - **Defere**: botão "Defere" → status `Deferido`, ação 4 feita, cria ação 5 pendente.
  - **Indefere**: botão "Indefere" → status `Indeferido`, pipeline encerra (ações futuras marcadas como `pulado` com motivo).
  - **Trocado** (chefe sugere outra especialidade/período): botão "Trocado" → status `Trocado`, volta para passo 3 com novo contato.
- **Rastreio**: fica em `historico_residentes` (responsável + observação + ts) e em `pipeline_acoes`.

### Passo 5 — Solicitação de link de pagamento ao financeiro

- **Status**: `Deferido`.
- **Humano**: aciona o setor financeiro (WhatsApp) pedindo a geração do link de pagamento para o residente. O valor já está no registro (`residentes.valor`).
- **Sistema**: botão "Solicitar link" abre WhatsApp com mensagem modelo `whatsapp_financeiro_link` (nova), preenchida com nome, especialidade, valor e período. Marca ação 5 como feita, cria ação 6 pendente.
- **Configuração necessária**: adicionar um contato financeiro (celular) em `area_medica` (especialidade fictícia "Financeiro") ou via nova variável de ambiente `FINANCEIRO_WHATSAPP`.
- **Sair do passo**: botão "Solicitar link" (registra que o pedido foi enviado ao financeiro).

### Passo 6 — Envio do link + solicitação de documentos ao cliente

- **Status**: `Deferido`.
- **Humano**: assim que recebe o link de pagamento do financeiro, encaminha ao cliente via WhatsApp/email, junto com a solicitação de todos os documentos necessários (CRM, termo, vacina, RG, foto, etc. — depende da especialidade).
- **Sistema**: botão "Enviar link + docs" abre modal com mensagem modelo `whatsapp_cliente_link_docs` (nova), preenchida com nome, valor, especialidade e lista de documentos. O usuário edita se necessário antes de abrir o WhatsApp. Marca ação 6 como feita, cria ação 7 pendente.
- **Lista de documentos por especialidade**: se houver variação, pode ser parametrizada em `area_medica.obs_internato`/`obs_residencia` ou numa nova coluna `documentos_necessarios` (fase posterior).
- **Sair do passo**: botão "Enviar" (registra que o link e a solicitação de docs foram enviados ao cliente).

### Passo 7 — Recebimento e análise de comprovante + documentos

- **Status**: `Deferido → Confirmado`.
- **Humano**: recebe o comprovante de pagamento e os documentos do cliente, faz análise manual (confere nomes, prazos, assinaturas, validade do CRM, etc.). Se tudo estiver OK, marca o comprovante e avança; se faltar algo, volta ao passo 6 (reesolicita).
- **Sistema**:
  - Campo `comprovante_pagamento` (texto livre, já existe) — onde colar link/ID do comprovante.
  - Botão "Comprovante + docs OK" → status `Confirmado`, ação 7 feita, cria ação 8 pendente.
  - Botão "Falta documento" → volta ação 6 para pendente, registra motivo na observação.
  - Alerta vermelho se >7 dias sem resposta do cliente (mesma lógica de `dias_no_status`).
- **Sair do passo**: botão "Comprovante + docs OK" (avança) ou "Falta documento" (volta).

### Passo 8 — Orientações para o primeiro dia

- **Status**: `Confirmado → Concluído`.
- **Trigger**: automático, baseado na data de `inicio`. O sistema agenda a ação 8 para `T = inicio - 7 dias`.
- **Humano**: no dia (ou alguns dias antes), o banner da fila mostra "Enviar orientações hoje para X". O usuário clica, abre o WhatsApp/email do aluno com a mensagem modelo `whatsapp_cliente_orientacoes` (nova), preenchida com nome, especialidade, data e local do primeiro dia.
- **Sistema**: botão "Enviar orientações" marca ação 8 como feita e, opcionalmente, avança status para `Concluído` (ou mantém `Confirmado` até o fim efetivo do estágio). Se `inicio` não estiver preenchido, a ação fica pendente sem data-alvo e entra na fila manual.
- **Sair do passo**: botão "Enviar orientações" (conclui o pipeline para o residente).

---

## Conceitos de controle

### Ação pendente, feita e pulada

Cada passo do pipeline é uma linha na tabela `pipeline_acoes`, ligada a um residente:

```
pipeline_acoes (
    id, residente_id, etapa (1-8), acao_tipo, status,
    responsavel, ts, observacao, reagendado_para
)
```

- `pendente` — precisa de ação humana (aparece na fila)
- `feita` — ação concluída
- `pulado` — ação cancelada (ex: indeferimento, desistência)

A fila de atendimento (`/api/pipeline/fila`) lista apenas ações `pendente`, ordenadas por criticidade (dias parado) e por data-alvo (`reagendado_para` para o passo 8).

### Encerramento do pipeline

O pipeline de um residente encerra quando:
- Status vira `Indeferido`, `Desistente`, `Cancelado` ou `Nao veio` — todas as ações pendentes viram `pulado` com motivo.
- Ação 8 é concluída — todas as ações estão `feita`, residente pode ir para `Concluído`.

### Alertas de prazo

Reaproveita a lógica de `dias_no_status` já existente no frontend (badge laranja >7 dias, vermelho >14 dias). No pipeline, o controle é por etapa:
- Etapa 3 (chefe) sem ação 4há >7 dias → alerta laranja
- Etapa 7 (cliente) sem ação 8 há >7 dias → alerta laranja
- Qualquer etapa >14 dias parado → alerta vermelho

### Responsável

Toda ação registra `responsavel` (nome do usuário logado, igual ao `historico_residentes` atual). Isso permite auditoria: quem contatou, quem deferiu, quem enviou o link.

---

## Novas mensagens modelo (3)

Adicionar à tabela `mensagens_modelo` (mesmo padrão das existentes `whatsapp_aluno` e `whatsapp_area_medica`):

### `whatsapp_financeiro_link`
Texto: "Olá! Tudo bem? Gostaria de solicitar a geração do link de pagamento para {{tipo}} {{nome}}, especialidade {{especialidade}}, valor R$ {{valor}}, período {{periodo}}. Encaminho para o cliente assim que receber. Obrigado!"

Placeholders: nome, tipo (residente/doutorando), especialidade, valor, periodo, usuario.

### `whatsapp_cliente_link_docs`
Texto: "Olá {{nome}}, tudo bem? Segue o link de pagamento da sua inscrição: {{link}}. Valor: R$ {{valor}}. Junto com o pagamento, encaminhe os documentos: {{documentos}}. Após o pagamento, nos avise com o comprovante. Qualquer dúvida, me chame. Abraço!"

Placeholders: nome, link, valor, documentos, especialidade, usuario.

### `whatsapp_cliente_orientacoes`
Texto: "Olá {{nome}}, tudo bem? Faltam poucos dias para o início do seu estágio em {{especialidade}} ({{data_inicio}}). Seguem as orientações para o primeiro dia: {{orientacoes}}. Local: {{local}}. Confirmar recebimento, por favor. Até logo!"

Placeholders: nome, especialidade, data_inicio, orientacoes, local, usuario.

Todas as três são editáveis na tela de Configurações (`PUT /api/mensagens-modelo/<chave>`, admin-only), igual às que já existem.

---

## Novas rotas (backend)

| Método | Rota | Quem | Descrição |
|--------|------|------|-----------|
| GET | `/api/pipeline/fila` | admin | Lista ações `pendente` com dados do residente, etapa atual, dias parado, alerta |
| GET | `/api/pipeline/fila/<etapa>` | admin | Filtra fila por etapa 1-8 |
| POST | `/api/residentes/<id>/acao` | admin | Marca ação (feita/pulada); sistema cria próxima pendente automaticamente |
| GET | `/api/pipeline/dashboard` | todos | KPIs por etapa (pendentes, críticos, feitos) |
| GET | `/api/pipeline/residente/<id>` | admin | Histórico do pipeline de um residente (todas as ações) |

Segurança: repete o padrão do `ai.py` — nunca executa SQL gerado; sempre humano actionado; mensagens sempre editáveis antes do envio.

---

## Novas telas / componentes frontend

1. **Banner no `/residentes`** *(reaproveita o `welcome-banner` atual)*: chips por etapa pendente. Ex: "3 novos p/ triagem" (etapa 1), "5 aguardando chefe" (etapa 3), "2 prontos p/ enviar link" (etapa 6). Click filtra a fila.

2. **Modal de ação por passo** *(um modal genérico, adaptável)*: mostra o residente, a etapa atual, botões de ação (Confirmou/Enviado/Defere/Indefere/etc.), campo de observação, botão para abrir o WhatsApp/email com a mensagem modelo preenchida e editável antes de enviar. Fecha marcando a ação.

3. **Fila de atendimento** *(nova view `/pipeline` ou aba em `/residentes`)*: tabela kanban opcional com 8 colunas (uma por etapa), mostrando os residentes em cada pendência. Alternativamente, lista simples filtrável por etapa/ status/ criticidade.

---

## Integração com a IA (opcional)

Reaproveita `/api/ai/insights` (já existe em `ai.py`). O `montar_snapshot(db)` deve incluir dados do pipeline:

- Contagem de pendentes por etapa
- Residentes críticos (>14 dias parados)
- Próximas ações 8 agendadas (orientações a enviar na semana)

A IA continua sem gerar SQL e sem enviar mensagens — apenas produz um resumo executivo diário com o que precisa de atenção.

---

## Migração / implementação

1. Criar tabela `pipeline_acoes` (migração inline no bloco `__main__` de `app.py`, mesmo padrão das outras).
2. Seed: para residentes já existentes (status atual), criar ações pendentes compatíveis — ex: em `Em andamento` criar etapa 3 pendente; em `Deferido` criar etapa 5 pendente. Não alterar status.
3. Adicionar as 3 mensagens modelo no `MENSAGEM_MODELO_SEED` em `app.py`.
4. Implementar rotas `/api/pipeline/*` no `app.py`.
5. Adicionar lógica de criação de ação pendente nos endpoints de importação (`/api/residentes/importar-excel` e no `sync_forms.py`, se reativado) e no `POST /api/residentes` (cadastro manual).
6. Adicionar banner e modal de ação no `residentes.js` / template `residentes.html`.
7. Opcional: view `/pipeline` (kanban ou fila).

---

## Fluxo de dados (resumo)

```
IMPORTAÇÃO           PIPELINE (8 etapas)            STATUS (SQLite)
----------           --------------------           ----------------
Forms → residentes   ação etapa 1 pendente          Interessado
                     [1] Revisado
                     ação etapa 2 pendente
                     [2] Confirmou
                     ação etapa 3 pendente          Em andamento
                     [3] Enviado ao chefe
                     ação etapa 4 pendente
                     [4] Defere
                     ação etapa 5 pendente          Deferido
                     [5] Solicitar link
                     ação etapa 6 pendente
                     [6] Enviar link + docs
                     ação etapa 7 pendente
                     [7] Comprovante + docs OK      Confirmado
                     ação etapa 8 pendente
                     (T = inicio - 7 dias)
                     [8] Enviar orientações         Concluído
                     pipeline encerra
```

---

## Pontos de atenção

- **Nada é enviado automaticamente.** O sistema nunca dispara WhatsApp/email sem clique humano.
- **Mensagens sempre editáveis.** O modal abre com o template preenchido, mas o usuário pode alterar antes de abrir o `wa.me`.
- **Passo 8 depende de `inicio`.** Se a data de início não estiver preenchida no cadastro, a ação 8 fica pendente sem data-alvo e entra na fila manual.
- **Fallback de tabela livre.** Especialidade do Forms é texto livre; o `_melhor_match_especialidade` sugere a versão canônica, mas a correção é sempre humana (passo 1).
- **Encerramento manual.** Indeferido/Desistente/Cancelado/Nao veio encerram o pipeline, mas precisam de clique humano nos botões do modal.
- **Auditoria.** Cada ação tem responsável e timestamp. O histórico de status (`historico_residentes`) segue gravando alterações de status, e `pipeline_acoes` grava o detalhamento das ações por etapa.
