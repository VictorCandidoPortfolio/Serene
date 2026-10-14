"""Reconhecimento: "a essência que a aluna cadastrou corresponde a qual nota?".

Função pura de correspondência de nomes (funcionalidade 2.3). O resultado é
SEMPRE uma sugestão: quem aplica (ou não) a classificação é a aluna, via
`knowledge_note_id` + `aplicar_referencia` no cadastro. Nada aqui grava nada.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.core.text import normalizar


@dataclass(frozen=True)
class NotaRef:
    """Visão de uma `knowledge_note` para fins de busca."""

    id: int
    nome: str
    sinonimos: tuple[str, ...]


@dataclass(frozen=True)
class Correspondencia:
    """Uma nota candidata e o quão forte foi o match.

    `tipo`: "exata" (nome/sinônimo idêntico após normalização) ou "parcial"
    (um nome contém o outro, ex.: "bergamota calabresa" × "bergamota").
    """

    nota_id: int
    tipo: str
    termo: str


def buscar_correspondencias(
    nome: str, notas: Sequence[NotaRef], limite: int = 5
) -> list[Correspondencia]:
    """Procura notas de referência cujo nome/sinônimo corresponda a `nome`.

    Exatas vêm antes das parciais. Parcial exige palavra inteira contida
    (para "rosa" não casar com "rosalina" nem "cedro" com "cedrol").

    Args:
        nome: nome digitado pela aluna (qualquer grafia).
        notas: notas da base de conhecimento.
        limite: máximo de candidatas devolvidas.

    Returns:
        Lista (possivelmente vazia) de correspondências.
    """
    alvo = normalizar(nome)
    if not alvo:
        return []
    palavras_alvo = f" {alvo} "
    exatas: list[Correspondencia] = []
    parciais: list[Correspondencia] = []
    for nota in notas:
        termos = [nota.nome, *nota.sinonimos]
        achou_exata = False
        melhor_parcial: str | None = None
        for termo in termos:
            t = normalizar(termo)
            if not t:
                continue
            if t == alvo:
                exatas.append(Correspondencia(nota.id, "exata", termo))
                achou_exata = True
                break
            if melhor_parcial is None and (f" {t} " in palavras_alvo or f" {alvo} " in f" {t} "):
                melhor_parcial = termo
        if not achou_exata and melhor_parcial is not None:
            parciais.append(Correspondencia(nota.id, "parcial", melhor_parcial))
    return (exatas + parciais)[:limite]
