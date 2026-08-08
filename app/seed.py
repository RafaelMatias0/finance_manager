"""
Popula o banco com categorias padrão (globais, usuario_id=None).
Rode com: python -m app.seed
"""
from app.database import SessionLocal
from app.models import Categoria, TipoMovimentacao

CATEGORIAS_PADRAO = [
    ("Salário", TipoMovimentacao.RECEITA),
    ("Bônus", TipoMovimentacao.RECEITA),
    ("Outras receitas", TipoMovimentacao.RECEITA),
    ("Alimentação", TipoMovimentacao.DESPESA),
    ("Contas", TipoMovimentacao.DESPESA),
    ("Transporte", TipoMovimentacao.DESPESA),
    ("Lazer", TipoMovimentacao.DESPESA),
    ("Outras despesas", TipoMovimentacao.DESPESA),
]


def seed():
    db = SessionLocal()
    try:
        existentes = {c.nome for c in db.query(Categoria).filter(Categoria.usuario_id.is_(None))}
        criadas = 0
        for nome, tipo in CATEGORIAS_PADRAO:
            if nome not in existentes:
                db.add(Categoria(nome=nome, tipo=tipo, usuario_id=None))
                criadas += 1
        db.commit()
        print(f"{criadas} categoria(s) padrão criada(s).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
