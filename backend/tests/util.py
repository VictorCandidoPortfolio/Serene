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
    "Bergamota": {"familia": "Cítrico", "knowledge_note_id": 1, "v1": 2, "v2": 1.5, "v3": 3, "v4": 6, "v6": 1,
                  "papel": {"saida": 0.9, "coracao": 0.1, "fundo": 0.0}},
    "Jasmim": {"familia": "Floral", "subfamilia": "Floral Branco", "knowledge_note_id": 3, "v1": 6, "v2": 5, "v3": 6, "v4": 7, "v6": 9,
               "papel": {"saida": 0.1, "coracao": 0.8, "fundo": 0.1}},
    "Cedro": {"familia": "Amadeirado", "knowledge_note_id": 4, "v1": 5, "v2": 8, "v3": 2, "v4": 5, "v6": 0,
              "papel": {"saida": 0.0, "coracao": 0.2, "fundo": 0.8}},
}


# ---------------------------------------------------------------------------
# Essências com valores técnicos exatos
# ---------------------------------------------------------------------------
# O cadastro oficial tem 3 campos (nome, família, percepção) e o servidor IGNORA
# v1–v5, papel, confiança etc. Vários testes precisam de números exatos (para
# conferir o motor), então eles gravam esses campos direto no banco, DEPOIS de
# cadastrar pelo caminho oficial. Isso só existe em testes.
CAMPOS_TECNICOS = (
    "familia", "subfamilia", "tipo", "papel", "v1", "v2", "v3", "v4", "v5", "v6", "confianca", "origem",
    "fornecedor", "descritores", "observacoes", "favorito", "tags", "ficha", "percepcao",
    "knowledge_note_id", "editado_da_referencia",
)


class Resposta:
    """Imita a resposta do TestClient (status_code, json(), text) para o helper abaixo."""

    def __init__(self, status_code: int, corpo):
        self.status_code, self._corpo = status_code, corpo
        self.text = str(corpo)

    def json(self):
        return self._corpo


def definir_tecnico(essencia_id: int, **campos) -> None:
    """Grava campos técnicos direto no banco de teste (só testes)."""
    from app.models.repertorio import Essencia
    from tests.conftest import _SessionTest

    with _SessionTest() as sessao:
        e = sessao.get(Essencia, essencia_id)
        for k, v in campos.items():
            setattr(e, k, v)
        sessao.commit()


def essencia_antiga(client, headers, corpo: dict, grupo: str = "Floral", percepcao: str = "neutra"):
    """Cadastra no estilo ANTIGO: `corpo` com campos técnicos, como os testes antigos enviavam.

    Cadastra pelo caminho oficial (nome + grupo + percepção) e depois grava no
    banco os campos técnicos de `corpo`. Devolve algo parecido com a resposta do
    POST (201 + essência completa). Se o cadastro oficial falhar, devolve essa falha.
    """
    r = client.post("/essencias", headers=headers,
                    json={"nome": corpo.get("nome", ""), "familia": grupo, "percepcao": percepcao})
    if r.status_code != 201:
        return r
    tecnico = {k: v for k, v in corpo.items() if k in CAMPOS_TECNICOS}
    if tecnico:
        definir_tecnico(r.json()["id"], **tecnico)
    return Resposta(201, client.get(f"/essencias/{r.json()['id']}", headers=headers).json())
