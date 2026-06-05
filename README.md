# Estagios Medicos - Santa Casa / UFCSPA

Sistema de gestao de estagios medicos com Flask + SQLite.

## Instalacao

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Execucao

```bash
python app.py
```

O banco SQLite e criado automaticamente com dados de exemplo na primeira execucao.

Acesse: `http://localhost:5000`

Para acesso na rede local, use o IP da maquina: `http://<IP>:5000`

## Funcionalidades

- CRUD completo de estagios (Observership, Obrigatorio, Optativo)
- Listagem agrupada por Mes/Semana
- Filtros por tipo, especialidade, etapa, mes
- Busca por nome, email, cracha
- Avanco de etapa com registro automatico no historico
- Historico completo por aluno
- Badges coloridos por etapa
- Exportacao CSV

## Etapas do fluxo

| Etapa | Observership | Obrigatorio/Optativo |
|-------|-------------|---------------------|
| 0     | -           | Verificacao de vaga |
| 1     | Venda realizada | Venda realizada |
| 2     | Pagamento confirmado | Pagamento confirmado |
| 3     | Docs enviados | Docs enviados |
| 4     | Docs validados | Docs validados |
| 5     | Vaga confirmada | Vaga confirmada |
| 6     | Orientacoes enviadas | Orientacoes enviadas |
| 7     | Concluido | Concluido |

## API

- `GET /api/estagios` - Lista estagios (aceita filtros via query params)
- `POST /api/estagios` - Cria estagio
- `PUT /api/estagios/<id>` - Atualiza estagio
- `DELETE /api/estagios/<id>` - Remove estagio
- `POST /api/estagios/<id>/avancar` - Avanca etapa
- `GET /api/estagios/<id>/historico` - Historico de etapas
- `GET /api/tipos` - Tipos de estagio
- `GET /api/especialidades` - Especialidades distintas
- `GET /api/meses` - Meses disponiveis
- `GET /api/exportar-csv` - Exporta listagem em CSV
