"""CLI do seed: `python -m app.seed` (depois de `alembic upgrade head`)."""

from app.db.session import SessionLocal
from app.seed import popular


def main() -> None:
    """Abre uma sessão no DATABASE_URL do .env e popula o conhecimento."""
    with SessionLocal() as db:
        contagem = popular(db)
    for tabela, qtd in contagem.items():
        print(f"{tabela:36} {qtd:>3} registro(s)")
    print("Seed concluído (dados ILUSTRATIVOS — ver app/seed/data.py).")


if __name__ == "__main__":
    main()
