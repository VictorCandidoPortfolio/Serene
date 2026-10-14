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
