# Pipeline de Atendimento — Residentes & Doutorandos

Fluxo operacional do cadastro à conclusão real do estágio. O pipeline é a fonte de verdade para a próxima ação da equipe.

Princípio central: **nada é enviado ou concluído automaticamente**. Microsoft Forms pode criar a inscrição; Outlook/WhatsApp podem preparar ou enviar a comunicação após ação explícita do usuário; a mudança de etapa continua sendo confirmada no SGE.

## Fluxo

```
Forms / Excel / cadastro manual
        |
        v
[1] Triagem
        |
        v
[2] Confirmar com aluno
        |
        v
[3] Acionar chefe de serviço
        |
        v
[4] Registrar deferimento
   | deferido        | indeferido
   v                 v
[5] Solicitar        encerra
    link financeiro
        |
        v
[6] Enviar link + documentos
        |
        v
[7] Validar pagamento + documentos
        |
        v
     Confirmado
        |
        v
[8] Orientações do 1º dia
    prazo = início - 7 dias
        |
        v
[9] Concluir estágio
    prazo = data de término
        |
        v
     Concluído
```

A etapa 8 **não** conclui o estágio. Ela somente registra que as orientações foram enviadas. A conclusão ocorre na etapa 9 e somente a partir da data de término cadastrada.

## Etapas e prazos

| Etapa | Próxima ação | Status principal | Prazo padrão |
|---|---|---|---|
| 1 | Triar cadastro | Interessado | 1 dia |
| 2 | Confirmar pedido com aluno | Interessado | 3 dias |
| 3 | Acionar chefe de serviço | Em andamento | 7 dias |
| 4 | Registrar resposta/deferimento | Em andamento | 7 dias |
| 5 | Solicitar link ao financeiro | Deferido | 2 dias |
| 6 | Enviar link + documentos | Deferido | 2 dias |
| 7 | Validar comprovante + documentos | Deferido | 7 dias |
| 8 | Enviar orientações | Confirmado | início - 7 dias |
| 9 | Registrar conclusão real | Confirmado | data de término |

Os prazos podem ser ajustados manualmente por ação sem alterar as datas acadêmicas do estágio.

## Regras de avanço

### Etapa 7 — confirmação

O resultado **Comprovante + docs OK** somente é aceito quando `status_pagamento` estiver em:

- `Pago`; ou
- `Isento`.

Caso contrário, o backend bloqueia o avanço.

### Etapa 8 — orientações

Antes de marcar **Orientações enviadas**, o cadastro precisa ter:

- data de início;
- data de término.

Ao concluir a etapa 8, o residente permanece `Confirmado` e é criada a etapa 9.

### Etapa 9 — conclusão

**Estágio concluído** somente é aceito quando a data de término for igual ou anterior à data atual.

Também existem os encerramentos:

- `Nao veio`;
- `Cancelado`.

Esses encerram o pipeline sem marcar o estágio como concluído.

## Gestão da próxima ação

Cada ação pendente pode registrar:

- **prioridade**: Normal, Alta ou Urgente;
- **prazo**;
- **responsável atual**;
- **bloqueio**;
- **motivo do bloqueio**.

Uma ação bloqueada permanece visível na fila, mas não pode ser concluída até ser desbloqueada.

O botão **Assumir para mim** atribui a ação ao usuário logado.

## Ordenação da fila

`GET /api/pipeline/fila` ordena a fila considerando:

1. prioridade manual;
2. ações atrasadas;
3. ações que vencem hoje;
4. bloqueios que exigem atenção;
5. prazo mais próximo;
6. antiguidade.

A fila mostra, para cada item:

- residente;
- especialidade;
- próxima ação;
- prazo;
- atraso;
- prioridade;
- responsável;
- bloqueio.

## Dashboard do pipeline

`GET /api/pipeline/dashboard` retorna:

- `pendentes_total`;
- `pendentes_por_etapa`;
- `atrasados`;
- `vencem_hoje`;
- `bloqueados`;
- `sem_responsavel`;
- `criticos`;
- `feitos`.

`criticos` inclui ações marcadas como Urgentes ou atrasadas há pelo menos 3 dias.

## Comunicações

### Microsoft Forms

Novas respostas podem entrar automaticamente via:

`POST /api/integracoes/forms/inscricao`

Uma inscrição nova entra como `Interessado` e recebe a etapa 1 — Triagem.

### Outlook / Microsoft Graph

Nas etapas com comunicação, o modal permite revisar assunto e mensagem e clicar em **Enviar por Outlook**.

O envio do e-mail **não muda a etapa automaticamente**. Depois do envio, o usuário registra o resultado correspondente no pipeline.

### WhatsApp

O comportamento continua o mesmo: mensagem pré-preenchida e editável antes de abrir o WhatsApp.

## Auditoria

`pipeline_acoes` registra a execução operacional:

```
id
residente_id
etapa
acao_tipo
situacao
prioridade
prazo_em
bloqueado
bloqueio_motivo
atribuido_a
responsavel
observacao
criado_em
atualizado_em
concluido_em
```

`historico_residentes` registra mudanças de status.

`integracao_eventos` registra eventos Microsoft Forms/Outlook.

## Proteção contra bypass

Enquanto existe uma ação pendente:

- a interface não exibe mais o botão antigo **Avançar status**;
- alteração direta de status no cadastro é recusada;
- `POST /api/residentes/<id>/avancar` é bloqueado.

Uma correção excepcional ainda pode ser feita por administrador usando `forcar=true` no endpoint legado, deixando trilha explícita no histórico.

## Encerramento do pipeline

O pipeline termina quando:

- etapa 4 resulta em `Indeferido`;
- etapa 2 resulta em `Desistente`;
- etapa 9 resulta em `Concluído`, `Nao veio` ou `Cancelado`;
- um administrador faz uma correção excepcional explícita.

## Relação com o acompanhamento acadêmico

Pipeline operacional e acompanhamento acadêmico são separados:

- **pipeline**: quem precisa fazer o quê e até quando;
- **acadêmico**: documentos, carga horária e elegibilidade para certificado.

O certificado continua condicionado a:

- status `Concluído`;
- pagamento `Pago` ou `Isento`;
- carga horária cumprida;
- todos os documentos obrigatórios aprovados.
