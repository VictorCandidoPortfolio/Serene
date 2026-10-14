"""Relógio único da aplicação para datas gravadas e comparadas no banco."""

from datetime import datetime, timezone


def agora() -> datetime:
    """Agora em UTC, sem fuso e sem fração de segundo.

    É o formato exato das colunas DATETIME do MySQL. Truncar aqui é
    obrigatório: o MySQL ARREDONDA a fração ao gravar (12:00:00.6 vira
    12:00:01), e o horário salvo ficaria "no futuro" em relação ao calculado,
    fazendo prazos e intervalos falharem por 1 segundo.

    Datas são calculadas no Python, e não com `NOW()` do banco, porque o
    `NOW()` depende do fuso configurado no servidor MySQL.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
