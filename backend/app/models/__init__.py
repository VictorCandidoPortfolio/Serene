"""Models SQLAlchemy das duas camadas do domínio.

Importar este pacote registra TODAS as tabelas em `Base.metadata` — é o que o
Alembic (autogenerate) e os testes (`create_all`) precisam.
"""

from app.models.conta import LimiteRequisicao, VerificacaoEmail  # noqa: F401
from app.models.knowledge import (  # noqa: F401
    KnowledgeCompositionFunction,
    KnowledgeDescriptor,
    KnowledgeEngineRule,
    KnowledgeFamily,
    KnowledgeFamilyRelation,
    KnowledgeMap,
    KnowledgeNote,
)
from app.models.repertorio import (  # noqa: F401
    Acorde,
    Colecao,
    ColecaoCriacao,
    Criacao,
    Essencia,
    PerfilOlfativo,
    Referencia,
    Teste,
    User,
)
