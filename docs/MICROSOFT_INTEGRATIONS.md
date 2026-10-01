# Integrações Microsoft — Forms + Outlook

Este módulo conecta o fluxo de Residentes & Doutorandos ao Microsoft 365 sem retirar a confirmação humana das ações.

## Fluxo

```
Microsoft Forms
  -> Power Automate: nova resposta
  -> Get response details
  -> POST autenticado no SGE
  -> residente criado como "Interessado"
  -> etapa 1 do pipeline: Triagem

SGE / Pipeline
  -> usuário revisa mensagem
  -> "Enviar por Outlook"
  -> Microsoft Graph / sendMail
  -> evento de envio auditado
  -> usuário registra o resultado da etapa normalmente
```

## 1. Microsoft Forms

O endpoint de entrada é:

`POST /api/integracoes/forms/inscricao`

Header obrigatório:

`X-Forms-Webhook-Secret: <FORMS_WEBHOOK_SECRET>`

O header aceita a chave em texto puro (mais simples no Power Automate) ou
`sha256=<HMAC-SHA256 do corpo>`.

### Power Automate

Crie um fluxo automatizado:

1. **Microsoft Forms — When a new response is submitted**
2. **Microsoft Forms — Get response details**
3. **HTTP — POST** para `https://SEU-SGE/api/integracoes/forms/inscricao`
4. Adicione o header `X-Forms-Webhook-Secret`
5. Monte o JSON normalizado abaixo usando os campos dinâmicos do formulário.

> A disponibilidade da ação HTTP no Power Automate depende do licenciamento
> Microsoft 365/Power Automate da organização.

Exemplo de corpo:

```json
{
  "form_id": "estagio-optativo-residentes",
  "response_id": "@{triggerOutputs()?['body/resourceData/responseId']}",
  "nome": "<Nome completo>",
  "email": "<E-mail>",
  "telefone": "<Telefone>",
  "cpf": "<CPF>",
  "tipo": "Residente",
  "modalidade": "Optativo",
  "especialidade": "<Especialidade desejada>",
  "subespecialidade": "<Subespecialidade>",
  "instituicao_origem": "<Instituição>",
  "programa_ano": "<Programa/Ano>",
  "mes_ano": "2026-11",
  "inicio": null,
  "termino": null,
  "periodo_desejado": "<Período informado no Forms>",
  "mes_desejado": "<Mês informado no Forms>",
  "observacao": "<Observações>"
}
```

`nome`, `especialidade` e um mês identificável são obrigatórios. O mês pode
vir em `mes_ano` (`AAAA-MM`), em `inicio` ou em `mes_desejado`
(ex.: `novembro 2026`).

### Idempotência

O par `form_id + response_id` vira a referência externa da inscrição. Se o
Power Automate repetir a mesma entrega, o SGE responde como duplicada e não
cria um segundo residente.

## 2. Outlook / Microsoft Graph

O SGE usa o endpoint oficial:

`POST /users/{OUTLOOK_SENDER}/sendMail`

A aplicação usa OAuth 2.0 Client Credentials. No Microsoft Entra ID:

1. Registre um aplicativo.
2. Crie um Client Secret.
3. Adicione a permissão **Microsoft Graph > Application > Mail.Send**.
4. Conceda **Admin consent**.
5. Defina a caixa de correio usada em `OUTLOOK_SENDER`.
6. Quando possível, limite o acesso do aplicativo às caixas necessárias por
   política do Exchange Online.

O botão **Enviar por Outlook** aparece nas ações do pipeline que possuem uma
mensagem. O destinatário é obtido do cadastro do aluno, do chefe de serviço ou
do contato Financeiro, conforme a etapa.

O envio não avança automaticamente o pipeline. Depois do envio, o operador
continua registrando **Confirmou**, **Enviado**, **Solicitado** etc. Isso evita
que um e-mail aceito pelo Graph seja confundido com uma resposta do destinatário.

## 3. Variáveis de ambiente

```env
FORMS_WEBHOOK_ENABLED=true
FORMS_WEBHOOK_SECRET=<chave longa aleatoria>

OUTLOOK_GRAPH_ENABLED=true
MICROSOFT_TENANT_ID=<tenant>
MICROSOFT_CLIENT_ID=<app/client id>
MICROSOFT_CLIENT_SECRET=<secret>
OUTLOOK_SENDER=<caixa@dominio>
```

## 4. Auditoria

A tabela `integracao_eventos` registra:

- provedor;
- tipo do evento;
- entrada/saída;
- sucesso/erro;
- residente relacionado;
- referência externa;
- responsável;
- data/hora.

O corpo do e-mail não é duplicado no log. Para Forms, o log guarda apenas
metadados da entrega; os dados operacionais ficam no cadastro do residente.

## 5. Endpoint de diagnóstico

Usuários autenticados podem consultar:

`GET /api/integracoes/status`

A resposta informa se Forms e Outlook estão habilitados/configurados, sem
expor secrets.
