# Estagios Medicos - Santa Casa / UFCSPA

Sistema de gestão de estágios médicos com Flask + SQLite.

## Instalação

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Execução

```bash
# Desenvolvimento
python app.py

# Produção (Gunicorn)
gunicorn -c gunicorn.conf.py app:app
```

O banco SQLite é criado automaticamente com dados de exemplo na primeira execução.

Acesse: `http://localhost:5000`

Para acesso na rede local, use o IP da máquina: `http://<IP>:5000`

Credenciais padrão: `admin / admin` e `user / user`.

## Funcionalidades

- CRUD completo de estágios (Observership, Obrigatório, Optativo)
- Filtros por tipo, especialidade, etapa, mês e status de pagamento
- Busca por nome, CPF, crachá, e-mail, especialidade e observação
- Importação de planilha Excel (.xlsx) com preview antes de confirmar
- Alertas visuais de prazo: laranja após 7 dias na etapa, vermelho após 14
- Avanço de etapa com registro automático no histórico
- Histórico completo por aluno
- Exportação CSV/TSV com os mesmos filtros ativos
- Geração de ficha em PDF (WeasyPrint)
- Dashboard com totais, gráficos por tipo, especialidade, etapa e pagamento
- Gestão de usuários com controle de acesso por perfil (admin/user)
- Tema claro/escuro (salvo no navegador)
- Notificações por e-mail (opcional, via SMTP)
- Script de backup diário com retenção de 7 dias (`backup.sh`)

## Etapas do fluxo

| Etapa | Observership        | Obrigatório/Optativo  |
|-------|---------------------|-----------------------|
| 0     | —                   | Verificação de vaga   |
| 1     | Venda realizada     | Venda realizada       |
| 2     | Pagamento confirmado| Pagamento confirmado  |
| 3     | Docs enviados       | Docs enviados         |
| 4     | Docs validados      | Docs validados        |
| 5     | Vaga confirmada     | Vaga confirmada       |
| 6     | Orientações enviadas| Orientações enviadas  |
| 7     | Concluído           | Concluído             |

## API

- `GET /api/me` — usuário logado
- `GET /api/estagios` — lista paginada (filtros: `tipo_id`, `especialidade`, `etapa`, `mes_ano`, `busca`, `status_pagamento`)
- `POST /api/estagios` — cria estágio
- `PUT /api/estagios/<id>` — atualiza estágio
- `DELETE /api/estagios/<id>` — remove estágio
- `POST /api/estagios/<id>/avancar` — avança etapa
- `GET /api/estagios/<id>/historico` — histórico de etapas
- `GET /api/estagios/<id>/pdf` — ficha em PDF
- `GET /api/exportar-csv` — exportação CSV/TSV
- `GET /api/dashboard` — dados do dashboard
- `POST /api/importar-excel` — importação de planilha (`confirmar=0` preview, `confirmar=1` grava)
- `GET /api/tipos` — tipos de estágio
- `GET /api/especialidades` — especialidades distintas
- `GET /api/meses` — meses disponíveis
- `GET /api/usuarios` — lista usuários (admin)
- `POST /api/usuarios` — cria usuário (admin)
- `PUT /api/usuarios/<id>` — edita usuário (admin)
- `DELETE /api/usuarios/<id>` — remove usuário (admin)

## Notificações por e-mail

Desabilitadas por padrão. Para habilitar:

```bash
SMTP_ENABLED=true SMTP_HOST=smtp.gmail.com SMTP_PORT=587 \
SMTP_USER=you@gmail.com SMTP_PASS=app-password SMTP_FROM=you@gmail.com \
python app.py
```

## Backup

```bash
# Executar manualmente
./backup.sh

# Crontab sugerido (todo dia às 2h)
0 2 * * * /caminho/para/erp-todo/backup.sh
```

Backups são salvos em `backups/` e removidos automaticamente após 7 dias.
