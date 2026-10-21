"""Interpretação da descrição em linguagem natural (função PURA, sem IA).

A aluna escreve "quero algo doce, floral e bem suave, que passe calma". Este
módulo procura, no texto, palavras que o BANCO conhece (campo `sinonimos` das
regras de emoção/preferência e o vocabulário de intensidade) e devolve as
chaves reconhecidas. Não há modelo de linguagem, nem adivinhação:

- só se reconhece o que está cadastrado (palavra desconhecida é ignorada e o
  motor diz o que entendeu, para a aluna corrigir);
- a comparação ignora acentos e maiúsculas e exige a palavra inteira;
- negação simples ("sem doce", "não quero floral", "nem cítrico") anula o termo
  e o devolve em `negados`, em vez de transformá-lo no seu oposto.

Determinístico: mesma frase, mesmo resultado, na ordem em que as palavras
aparecem no texto.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.text import normalizar

# Quantas palavras antes do termo ainda contam para uma negação ("não quero doce").
JANELA_NEGACAO = 3


@dataclass(frozen=True)
class Interpretacao:
    """O que foi entendido da descrição.

    Attributes:
        emocoes / preferencias: chaves de regra reconhecidas (ordem do texto, sem repetir).
        intensidade: 0–10 se uma palavra de intensidade apareceu, senão None.
        negados: termos citados com negação (não foram usados).
    """

    emocoes: list[str] = field(default_factory=list)
    preferencias: list[str] = field(default_factory=list)
    intensidade: float | None = None
    negados: list[str] = field(default_factory=list)

    @property
    def entendeu_algo(self) -> bool:
        return bool(self.emocoes or self.preferencias or self.intensidade is not None)


def _termos(chave: str, regra: Mapping[str, Any]) -> list[str]:
    """Termos que identificam uma regra: a chave, o rótulo e os sinônimos."""
    brutos = [chave, regra.get("rotulo", ""), *regra.get("sinonimos", [])]
    return [t for t in dict.fromkeys(normalizar(str(b)) for b in brutos) if t]


def interpretar(
    texto: str | None,
    regras_emocao: Mapping[str, Mapping[str, Any]],
    regras_preferencia: Mapping[str, Mapping[str, Any]],
    vocabulario: Mapping[str, Any],
) -> Interpretacao:
    """Extrai emoções, preferências e intensidade de um texto livre.

    Args:
        texto: descrição da aluna (None/vazio -> nada entendido).
        regras_emocao / regras_preferencia: regras do banco (com `sinonimos`).
        vocabulario: regra `criacao_vocabulario/linguagem`:
            {"intensidade": {palavra: 0..10}, "negacao": [palavras]}.
    """
    palavras = normalizar(texto).split()
    if not palavras:
        return Interpretacao()
    negacao = {normalizar(n) for n in vocabulario.get("negacao", [])}
    intensidades = {normalizar(k): float(v) for k, v in (vocabulario.get("intensidade") or {}).items()}

    # termo (lista de palavras) -> ("emocao"|"preferencia", chave)
    indice: list[tuple[list[str], str, str]] = []
    for tipo, regras in (("emocao", regras_emocao), ("preferencia", regras_preferencia)):
        for chave, regra in regras.items():
            for termo in _termos(chave, regra):
                indice.append((termo.split(), tipo, chave))
    # Termos mais longos primeiro: "roupa limpa" vence "limpa".
    indice.sort(key=lambda t: (-len(t[0]), t[1], t[2]))

    achados: list[tuple[int, str, str]] = []   # (posição, tipo, chave)
    negados: list[str] = []
    intensidade: float | None = None
    usadas: set[int] = set()

    for ini, _ in enumerate(palavras):
        if ini in usadas:
            continue
        for termo, tipo, chave in indice:
            fim = ini + len(termo)
            if palavras[ini:fim] == termo and not usadas.intersection(range(ini, fim)):
                usadas.update(range(ini, fim))
                antes = palavras[max(0, ini - JANELA_NEGACAO):ini]
                if negacao.intersection(antes):
                    negados.append(" ".join(termo))
                else:
                    achados.append((ini, tipo, chave))
                break
    # Intensidade: passada própria (uma palavra como "marcante" é preferência E intensidade).
    for ini, palavra in enumerate(palavras):
        antes = palavras[max(0, ini - JANELA_NEGACAO):ini]
        if palavra in intensidades and not negacao.intersection(antes):
            intensidade = intensidades[palavra]   # a primeira palavra de intensidade vale
            break

    emocoes = list(dict.fromkeys(c for _, t, c in sorted(achados) if t == "emocao"))
    prefs = list(dict.fromkeys(c for _, t, c in sorted(achados) if t == "preferencia"))
    return Interpretacao(emocoes, prefs, intensidade, list(dict.fromkeys(negados)))


def rotulos(chaves: Sequence[str], regras: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Chaves -> rótulos de exibição."""
    return [str(regras[c].get("rotulo", c)) for c in chaves if c in regras]
