"""Configuração de logs.

Tudo vai para a saída de erro padrão (stderr), que é o que o Vercel (e o
uvicorn local) coletam e mostram no painel de logs. Nenhum log deve conter
senha, código de verificação, token ou email completo — use
`auth_service.mascarar_email` para emails.
"""

import logging
import sys

_FORMATO = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configurar_logs(nivel: str) -> None:
    """Liga o logger "serene" no nível pedido (idempotente).

    Configura só a hierarquia "serene.*", sem mexer no logger raiz: assim
    não duplica as linhas do uvicorn nem muda o log de outras bibliotecas.
    """
    logger = logging.getLogger("serene")
    logger.setLevel(nivel)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMATO))
        logger.addHandler(handler)
    logger.propagate = False
