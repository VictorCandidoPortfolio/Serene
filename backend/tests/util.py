"""Helpers compartilhados pelos testes (importáveis, ao contrário do conftest)."""

import re

from app.core.email import caixa_de_saida

# Atende à regra de senha forte: maiúscula + número/caractere especial.
SENHA_PADRAO = "Senha-forte-123"


def ultimo_codigo(email: str) -> str:
    """Código de 4 dígitos do último email enviado para `email`."""
    mensagens = [m for m in caixa_de_saida() if m.para == email.lower()]
    assert mensagens, f"nenhum email enviado para {email}"
    return re.search(r"do Sérené é: (\d{4})", mensagens[-1].texto).group(1)


# Classificação que a ALUNA informa. As notas de exemplo da base só sugerem
# família/características; os números (eixos e papel) vêm sempre dela.
VALORES_DA_ALUNA = {
    "Bergamota": {"v1": 2, "v2": 1.5, "v3": 3, "v4": 6, "v6": 1,
                  "papel": {"saida": 0.9, "coracao": 0.1, "fundo": 0.0}},
    "Jasmim": {"v1": 6, "v2": 5, "v3": 6, "v4": 7, "v6": 9,
               "papel": {"saida": 0.1, "coracao": 0.8, "fundo": 0.1}},
    "Cedro": {"v1": 5, "v2": 8, "v3": 2, "v4": 5, "v6": 0,
              "papel": {"saida": 0.0, "coracao": 0.2, "fundo": 0.8}},
}
