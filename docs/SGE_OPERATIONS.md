# SGE operacional — implantação e validação

As funcionalidades deste ciclo evoluem o fluxo atual de **Residentes & Doutorandos**. O módulo histórico de `estagios` continua separado; sua capacidade participa dos mesmos períodos e a mudança de etapa não dispara mais SMTP. Frequência, documentos e financeiro estruturados deste ciclo pertencem a `residentes`. Não apresentar o módulo histórico como totalmente unificado.

## Ordem de integração

A cadeia já aberta é **#2 → #3 → #4 → #5 → #6 → #7**. As novas PRs seguem **#8 (correções) → #9 (vagas) → #10 (frequência) → #11 (arquivos) → #12 (financeiro) → #13 (Central do Dia e correções finais)**. Integre por ordem e revise o diff contra a base atual antes de cada merge. A validação deste ciclo cobre a árvore final; não habilite produção com parte da cadeia aplicada. O workflow de demonstração GitHub Pages da main foi preservado, e a demo estática não hospeda Flask ou SQLite.

## Migrações incrementais

O startup suportado (`python app.py`, `wsgi:app`, Waitress) usa `ensure_database` de `db_migrations.py`. Não execute `legacy_app.py`, não remova o banco e não copie um banco de teste sobre a instalação.

| Identificador | Alteração |
| --- | --- |
| sge_operational_guards_v1 | Auditoria e índice único de ação pendente por residente |
| sge_vagas_periodos_v1 | Capacidade por especialidade, modalidade e intervalo |
| sge_frequencia_v1 | Livro de frequência e preservação de totais antigos como Saldo legado |
| sge_documentos_arquivos_v1 | Metadados, versões e arquivos privados de documentos |
| sge_financeiro_v1 | Processo financeiro com valores em centavos e versão de edição |

A migração interrompe com uma mensagem de revisão se encontrar ações pendentes duplicadas ou horas legadas inválidas; não elimina registros para fazer o índice passar. Datas de presença e pagamento antigas não são inventadas. Cada total legado de horas é preservado uma única vez. O campo antigo permanece no banco, mas não decide o certificado.

## Preparação da instalação real

1. Faça backup consistente do SQLite (API de backup SQLite ou processo parado), incluindo os arquivos privados. Não copie apenas o `.db` enquanto WAL está em uso sem uma estratégia consistente.
2. Teste a atualização em uma **cópia** da instalação existente. Verifique `PRAGMA integrity_check`, `PRAGMA foreign_key_check`, totais preservados e ações duplicadas antes de promover.
3. Configure `ERP_DATABASE`, `SECRET_KEY` e `ERP_FILES_DIR` no ambiente. `ERP_FILES_DIR` deve ser uma pasta privada, persistente, fora de `static`, com acesso somente ao serviço. O padrão é `private_sge_files` ao lado do banco. Inclua a pasta na rotina de backup/restauração.
4. Cadastre os períodos reais em `/sge/vagas`. Não há capacidades fictícias criadas pela migração. Revise especialidades/modalidades antigas e datas antes de confirmar novas vagas. Alunos ativos sem datas ocupam conservadoramente os períodos correspondentes e aparecem identificados; registros concluídos sem datas continuam históricos.
5. Configure o checklist de cada aluno e anexe os documentos. Checklists antigos sem arquivo não atendem mais ao gate de validação. Aprovação exige coordenacao/admin e a versão conferida.
6. Atribua os perfis em Usuários. `user` permanece compatível com atendimento; somente `admin` e `financeiro` alteram financeiro; `financeiro` não executa o pipeline; `somente_leitura` não altera APIs nem envia Outlook. Emissão/registro de envio do certificado exige admin/coordenacao.
7. Homologue o fluxo com registros de teste na cópia do banco antes de expor o serviço real.

## Rotina de trabalho

- `/sge/hoje`: filas operacionais com links para a ação pendente, documentos, financeiro ou gate acadêmico. Categorias têm paginação e podem conter a mesma ação por motivos diferentes. Atualize a fila antes de agir.
- `/sge/vagas`: capacidade e ocupação compartilhadas por especialidade/modalidade/período. Confirmação e alterações de período/modalidade passam por transação de escrita. Override de lotação exige administrador, justificativa e vínculo auditado com o aluno.
- `/sge/residentes/<id>`: frequência, documentos reais e financeiro. A frequência diária calcula horas realizadas, faltantes e percentual. Datas futuras e horas em ausências são bloqueadas; correções exigem a versão atual.
- O financeiro usa centavos, desconto e total derivado. `Vencido` pode ser derivado do vencimento. Registro de pagamento não confirma o estágio: a validação pelo pipeline continua humana. Reembolso deve corresponder a pagamento anterior; valores de processos pagos/encerrados não podem ser recalculados silenciosamente.
- A etapa 8 registra orientações; a etapa 9 registra término real. O gate exige conclusão, término não futuro, pagamento Pago/Isento, frequência suficiente e documentos obrigatórios aprovados com arquivos válidos.
- Cancelamento administrativo exige justificativa e preserva cadastro, resposta Forms e histórico. DELETE de residente está bloqueado. Arquivamento de um requisito documental também preserva o registro e exige administrador e motivo.

## Microsoft 365

Consulte [MICROSOFT_INTEGRATIONS.md](MICROSOFT_INTEGRATIONS.md) para os passos e payloads exatos.

- Forms: `FORMS_WEBHOOK_ENABLED=true`, `FORMS_WEBHOOK_SECRET`, fluxo Power Automate com resposta normalizada para `POST /api/integracoes/forms/inscricao` e cabeçalho `X-Forms-Webhook-Secret`. Respostas repetidas preservam o mesmo cadastro, inclusive após cancelamento.
- Outlook: `OUTLOOK_GRAPH_ENABLED=true`, `MICROSOFT_TENANT_ID`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` e `OUTLOOK_SENDER`; aplicativo Entra ID com consentimento administrativo para Microsoft Graph `Mail.Send`, restringindo a caixa remetente conforme a política da instituição. Use HTTPS no webhook público. Não use senha pessoal.
- Os valores reais não foram configurados nem testados neste ciclo. Outlook foi testado com mocks; nenhuma mensagem real foi enviada. As mensagens continuam editáveis e envio não avança o pipeline. Falhas são registradas sem copiar detalhes arbitrários do provedor, tokens ou credenciais.

## Limites da validação e próximos passos

A suíte cobre migrações vazias/legadas/idempotentes, concorrência da última vaga, pipeline, perfis, Forms duplicado, Outlook mockado, frequência/correções, arquivos privados/versões/expiração, financeiro/reembolso, gate e listas diárias. O fluxo completo até o registro de emissão/envio foi exercitado por APIs Flask, com banco temporário e checagem de integridade referencial.

A instalação de Chromium falhou no ambiente (certificado de download e arquivo recebido inválido). **Não houve E2E em navegador real nem homologação visual desktop/mobile.** As telas foram renderizadas por Flask e o JavaScript validado sintaticamente. Essa homologação continua necessária.

O certificado atual registra emissão/envio manual, mas não gera um PDF acadêmico integrado nem envia esse PDF por Graph. Não confundir registro de envio com prova de entrega. Templates por modalidade, relatórios avançados, antifraude/antimalware de arquivos, trilha visual de auditoria e unificação do módulo histórico são trabalhos posteriores. O armazenamento suporta injeção de adapter; um provedor externo ainda não foi implementado/configurado.
