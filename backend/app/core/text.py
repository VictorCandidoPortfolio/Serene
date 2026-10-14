"""Normalização de texto usada no reconhecimento de nomes.

Mora no `core` (e não no motor) porque é usada tanto pelo service de essências
(para gravar `nome_canonico`) quanto pelo motor (para comparar famílias e
chaves de regra). É uma função pura, sem dependências.
"""

import re
import unicodedata

_ESPACOS = re.compile(r"\s+")
_NAO_ALFANUM = re.compile(r"[^a-z0-9 ]+")


def normalizar(texto: str | None) -> str:
    """Converte um nome para a forma canônica usada em buscas.

    Minúsculas, sem acentos, pontuação vira espaço e espaços são colapsados.
    Ex.: "  Óleo de BERGAMOTA-Calabresa " -> "oleo de bergamota calabresa".

    Por que existe: a aluna digita o nome do jeito dela ("bergamota",
    "Bergamota ", "BERGAMOTA"); sem normalizar, o reconhecimento contra a base
    de conhecimento falharia por diferença de grafia, não de conteúdo.

    Args:
        texto: nome livre (aceita None, que vira string vazia).

    Returns:
        str: forma canônica; string vazia se não sobrar nada.
    """
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    limpo = _NAO_ALFANUM.sub(" ", sem_acento.lower())
    return _ESPACOS.sub(" ", limpo).strip()


def chave(texto: str | None) -> str:
    """Forma canônica no formato de chave de regra/slug (`espacos_viram_underscore`).

    Usada para casar o que a aluna responde ("Acolhimento", "mais fresco")
    com `knowledge_engine_rules.chave` e `knowledge_families.slug`.
    """
    return normalizar(texto).replace(" ", "_")
