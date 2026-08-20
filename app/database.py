"""
Configuração da conexão com o banco de dados PostgreSQL.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/gerenciador_financas",
)

# client_encoding forçado pra UTF-8: sem isso, em alguns ambientes Windows
# o psycopg2/libpq negocia um encoding diferente pro texto que sai daqui,
# e nome de categoria com acento (ex: "Salário") chega corrompido no banco
# (double-encoding: "SalÃ¡rio") — foi um bug real, já aconteceu rodando
# app/seed.py contra o Neon a partir do Windows.
engine = create_engine(DATABASE_URL, connect_args={"client_encoding": "utf8"})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency do FastAPI para injetar uma sessão de banco por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
