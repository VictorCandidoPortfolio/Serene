# SÉRENÉ — Mapa Olfativo Inteligente

| Pasta | Conteúdo |
|---|---|
| [backend/](backend/) | API em FastAPI + MySQL + Alembic. Instruções em [backend/README.md](backend/README.md). |
| [frontend/](frontend/) | Interface em React + Vite. Instruções em [frontend/README.md](frontend/README.md). |

Deploy no Vercel (dois projetos + MySQL hospedado): veja [DEPLOY.md](DEPLOY.md).

Para rodar tudo localmente, use dois terminais:

```bash
# 1) API em http://127.0.0.1:8000
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload

# 2) Interface em http://localhost:5173
cd frontend
npm install     # só na primeira vez
npm run dev
```
