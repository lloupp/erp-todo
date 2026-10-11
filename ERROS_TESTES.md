# Registro de Erros — Testes ERP Estágios Médicos (Consolidado Final)

## Resumo Executivo
- 8 arquivos de teste criados em `/home/eduardodlima/erp-todo/` (não alteraram código existente)
- 18 testes executados
- 2 falhas críticas identificadas (ambas são bugs que quebram funcionalidades)

---

## Falhas Críticas (requerem correção)

### 1. Tabela `historico_residentes` não existe
**Status**: FALHA CRÍTICA  
**Onde**: `app.py:1101` (query em subquery)  
**Impacto**: `/api/dashboard` retorna 500 Internal Server Error  
**Query problemática**:
```sql
(SELECT MAX(h.ts) FROM historico_residentes h WHERE h.residente_id = r.id)
```
**Solução**: Executar migração para criar tabela `historico_residentes`. Schema esperado baseado no código:
```sql
CREATE TABLE IF NOT EXISTS historico_residentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    residente_id INTEGER NOT NULL REFERENCES residentes(id),
    status TEXT NOT NULL,
    observacao TEXT,
    responsavel TEXT,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## Avisos / Gotchas (não quebram mas afetam UX)

### 2. `/api/ai/chat` e `/api/ai/insights` retornam 503 quando AI desativado
**Status**: AVISO  
**Where**: `ai.py:115-120` retorna 503  
**Detalhe**: Comportamento correto (modo degradado), mas não há mensagem clara ao usuário sobre "IA desativada — fale com admin".

---

## Corretos / Funcionando

- Login/logout: admin/admin funciona, user/user tem role correta
- Proteção de rotas admin: retorna 403 para role!=admin  
- Status values válidos no schema  
- `pipeline_acoes` já existe com 10 colunas e 8 registros seed  
- Parser `_parse_mes_texto`: OK  
- Parser `_melhor_match_especialidade`: OK (após passar canonicos normalizados)  
- Relatórios exportar: OK (CSV gerado)  
- Pendencias API: OK (9 chaves retornadas)  
- Mensagens modelo: 5 templates seedados  

---

## Próximos Testes (pendentes)

- Testar fluxo completo de status transition (Interessado → Em andamento → Deferido → Confirmado)  
- Testar importação real de Excel (com arquivo)  
- Testar PDF de estagiário  
- Testar atualização de residente  

Os testes estão em:
- `/home/eduardodlima/erp-todo/test_basico.py` — schema básico
- `/home/eduardodlima/erp-todo/run_tests.py` — endpoints básicos
- `/home/eduardodlima/erp-todo/run_tests_auth.py` — endpoints autenticado
- `/home/eduardodlima/erp-todo/run_tests_parser.py` — parsers
- `/home/eduardodlima/erp-todo/run_tests_parser2.py` — parser de especialidades
- `/home/eduardodlima/erp-todo/run_tests_relatorios.py` — relatórios
- `/home/eduardodlima/erp-todo/run_tests_seguranca.py` — segurança/rota
- `/home/eduardodlima/erp-todo/run_tests_residentes.py` — módulo residentes
- `/home/eduardodlima/erp-todo/run_tests_ai.py` — IA e pipeline_acoes