"""Pool dedicado para chamadas de IA — isola o bloqueio de rede da OpenRouter
das threads de atendimento do Waitress.

O Waitress tem poucas threads (padrao 16). As chamadas de IA sao sincronas e
demoram 6-43s (ver erp.log). Se ficassem na thread da requisicao, 8 chamadas
simultaneas saturariam o servidor e tudo (/health, /login) daria timeout.

Com este pool, a thread do Waitress so faz submit()/result() e a espera longa
ocorre numa thread propria do pool de IA. O limite de concorrencia da IA e'
AI_POOL_THREADS (default 4) — rajadas maiores enfileiram, nao derrubam o server.
"""
from concurrent.futures import ThreadPoolExecutor
import os

_AI_THREADS = int(os.environ.get('AI_POOL_THREADS', 4))
_executor = ThreadPoolExecutor(max_workers=_AI_THREADS, thread_name_prefix='ai-pool')


def run(fn, *args, **kwargs):
    """Executa fn em thread do pool e retorna o resultado (re-lanca excecoes)."""
    return _executor.submit(fn, *args, **kwargs).result()
