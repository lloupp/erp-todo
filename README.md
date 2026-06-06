# Estagios Medicos - Santa Casa / UFCSPA

Sistema de gestão de estágios médicos com Flask + SQLite.

## Instalação

```bash
python3 -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

## Execução

```bash
# Desenvolvimento (debug ativo, reload automático)
python app.py

# Produção — Windows VPS (Waitress, sem debug)
copy .env.example .env        # preencher SECRET_KEY
python run_prod.py
```

O banco SQLite é criado automaticamente na primeira execução.

Acesse: `http://localhost:5000`  
Credenciais padrão: `admin / admin` e `user / user`.

## Funcionalidades

- CRUD completo de estágios (Observership, Obrigatório, Optativo)
- Filtros por tipo, especialidade, etapa, mês, semana e status de pagamento
- Busca por nome, CPF, crachá, e-mail, especialidade e observação
- Importação de planilha Excel (.xlsx) com preview antes de confirmar
- Alertas visuais de prazo: laranja após 7 dias na etapa, vermelho após 14
- Avanço de etapa com registro automático no histórico e marcação automática de Pago na etapa 2
- Botão rápido 💰 para marcar pagamento como Pago sem abrir modal
- Emissão de certificado PDF (etapa 7 — Comprovante recebido) no modelo da Santa Casa
- Exportação CSV compatível com Excel/Microsoft (BOM UTF-8, separador `;`, CRLF)
- Módulo de relatórios para re-contato de clientes (4 templates pré-definidos)
- Dashboard com totais, gráficos por tipo, especialidade, etapa e pagamento
- Gestão de usuários com controle de acesso por perfil (admin/user)
- Controle de vagas semanais por especialidade
- Banner de boas-vindas com pendências do dia
- Tema claro/escuro (salvo no navegador)
- Notificações por e-mail (opcional, via SMTP)
- Backup diário com retenção de 7 dias

## Etapas do fluxo

| Etapa | Observership          | Obrigatório/Optativo  |
|-------|-----------------------|-----------------------|
| 0     | —                     | Verificação de vaga   |
| 1     | Venda realizada       | Venda realizada       |
| 2     | Pagamento confirmado  | Pagamento confirmado  |
| 3     | Docs enviados         | Docs enviados         |
| 4     | Docs validados        | Docs validados        |
| 5     | Vaga confirmada       | Vaga confirmada       |
| 6     | Orientações enviadas  | Orientações enviadas  |
| 7     | Comprovante recebido  | Comprovante recebido  |
| 8     | Concluído             | Concluído             |

> Na etapa 2 o `status_pagamento` é marcado como **Pago** automaticamente.  
> O botão de emissão de certificado é liberado a partir da etapa 7.

## Módulo de Relatórios

Acesse `/relatorios` para gerar listas de contato pré-filtradas:

| Relatório | Filtro principal |
|---|---|
| Egressos por período | etapa = 8, filtro por data de término |
| Pagamentos pendentes | status Pendente/Interessado em andamento |
| Em andamento sem avanço | parados ≥ N dias na mesma etapa |
| Lista por especialidade | todos os contatos ordenados por especialidade |

Cada relatório tem preview inline e exportação CSV pronta para Excel.

## API

### Estágios
- `GET /api/estagios` — lista paginada (filtros: `tipo_id`, `especialidade`, `etapa`, `mes_ano`, `semana`, `busca`, `status_pagamento`)
- `POST /api/estagios` — cria estágio
- `PUT /api/estagios/<id>` — atualiza estágio
- `DELETE /api/estagios/<id>` — remove estágio
- `POST /api/estagios/<id>/avancar` — avança etapa
- `POST /api/estagios/<id>/pago` — marca como Pago rapidamente
- `GET /api/estagios/<id>/historico` — histórico de etapas
- `GET /api/estagios/<id>/pdf` — ficha em PDF
- `GET /api/estagios/<id>/certificado` — certificado PDF (requer etapa ≥ 7)

### Exportação e importação
- `GET /api/exportar-csv` — exportação CSV (BOM UTF-8, separador `;`)
- `GET /api/relatorios/exportar` — relatórios de contato (`relatorio=egressos|pendentes|parados|especialidade`, `preview=1` para JSON)
- `POST /api/importar-excel` — importação de planilha (`confirmar=0` preview, `confirmar=1` grava)

### Dashboard e filtros
- `GET /api/dashboard` — dados do dashboard
- `GET /api/pendencias` — resumo de pendências (para banner)
- `GET /api/tipos` — tipos de estágio
- `GET /api/especialidades` — especialidades distintas
- `GET /api/meses` — meses disponíveis

### Usuários (admin)
- `GET /api/me` — usuário logado
- `GET /api/usuarios` — lista usuários
- `POST /api/usuarios` — cria usuário
- `PUT /api/usuarios/<id>` — edita usuário
- `DELETE /api/usuarios/<id>` — remove usuário

### Vagas
- `GET /api/vagas` — limites semanais por especialidade
- `PUT /api/vagas/<id>` — atualiza limite

## Produção (Windows VPS)

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Inicializar banco (só na primeira vez)
python app.py

# 3. Configurar variáveis de ambiente
copy .env.example .env
# Editar .env e preencher SECRET_KEY

# 4. Iniciar servidor de produção
python run_prod.py
```

Para gerar uma `SECRET_KEY` segura:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Backup

```bash
# Linux — executar manualmente
./backup.sh

# Windows — executar manualmente
python backup.py

# Agendador de Tarefas do Windows (diário às 2h)
# Programa: python
# Argumentos: C:\caminho\erp-todo\backup.py
```

Backups são salvos em `backups/` e removidos automaticamente após 7 dias.

## Notificações por e-mail

Desabilitadas por padrão. Para habilitar (Microsoft/Outlook):

```bash
SMTP_ENABLED=true SMTP_HOST=smtp.office365.com SMTP_PORT=587 \
SMTP_USER=voce@hospital.com.br SMTP_PASS=senha SMTP_FROM=voce@hospital.com.br \
python app.py
```
