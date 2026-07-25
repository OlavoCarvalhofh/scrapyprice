"""
Trava contra execução sobreposta -- evita que a mesma coleta (mesmo site,
mesmo lote) rode duas vezes ao mesmo tempo (ex: cron/Kestra disparando de
novo antes da execução anterior terminar).

Cada "nome" tem seu próprio arquivo de lock, então sites diferentes podem
rodar em paralelo sem problema -- só a mesma coleta não pode se sobrepor.
"""
import os
import sys

from filelock import FileLock, Timeout

_LOCKS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".locks")


def adquirir_lock(nome):
    """Retorna um FileLock já adquirido, ou encerra o processo com uma
    mensagem clara se já tiver uma coleta com esse nome em andamento."""
    os.makedirs(_LOCKS_DIR, exist_ok=True)
    lock = FileLock(os.path.join(_LOCKS_DIR, f"{nome}.lock"), timeout=0)
    try:
        lock.acquire()
    except Timeout:
        sys.exit(
            f"Já existe uma coleta '{nome}' em andamento (lock ativo). "
            f"Se tiver certeza que não há nenhuma rodando, apague "
            f"'.locks/{nome}.lock' manualmente."
        )
    return lock
