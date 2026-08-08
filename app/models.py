"""
Modelos do banco de dados (SQLAlchemy ORM).

Estrutura:
- Usuario: dono das movimentações e categorias.
- Categoria: classifica as movimentações (ex: Salário, Alimentação),
  vinculada a um tipo (receita/despesa) e opcionalmente a um usuário
  (categorias podem ser globais/padrão ou criadas pelo próprio usuário).
- Movimentacao: registro de entrada (receita) ou saída (despesa) de dinheiro.
"""
import enum
import uuid
from datetime import datetime, date

from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    Numeric,
    Date,
    DateTime,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class TipoMovimentacao(str, enum.Enum):
    RECEITA = "receita"
    DESPESA = "despesa"


class TipoRelatorio(str, enum.Enum):
    AUTOMATICO_SEMANAL = "automatico_semanal"
    AUTOMATICO_MENSAL = "automatico_mensal"


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(120), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    senha_hash = Column(String(255), nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    categorias = relationship(
        "Categoria", back_populates="usuario", cascade="all, delete-orphan"
    )
    movimentacoes = relationship(
        "Movimentacao", back_populates="usuario", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} email={self.email}>"


class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(80), nullable=False)
    tipo = Column(
        SAEnum(
            TipoMovimentacao,
            name="tipo_movimentacao",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )

    # Nulo = categoria padrão/global (ex: "Salário", "Alimentação").
    # Preenchido = categoria criada pelo próprio usuário.
    usuario_id = Column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=True
    )

    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    usuario = relationship("Usuario", back_populates="categorias")
    movimentacoes = relationship("Movimentacao", back_populates="categoria")

    def __repr__(self) -> str:
        return f"<Categoria id={self.id} nome={self.nome} tipo={self.tipo}>"


class Movimentacao(Base):
    __tablename__ = "movimentacoes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    valor = Column(Numeric(12, 2), nullable=False)
    descricao = Column(String(255), nullable=True)
    data = Column(Date, default=date.today, nullable=False)

    usuario_id = Column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    categoria_id = Column(
        UUID(as_uuid=True), ForeignKey("categorias.id", ondelete="RESTRICT"), nullable=False
    )

    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    usuario = relationship("Usuario", back_populates="movimentacoes")
    categoria = relationship("Categoria", back_populates="movimentacoes")

    def __repr__(self) -> str:
        return f"<Movimentacao id={self.id} valor={self.valor} categoria_id={self.categoria_id}>"


class Relatorio(Base):
    """Snapshot de um relatório automático (semanal/mensal), gerado pelo
    scheduler. Guarda o resultado já calculado (campo `dados`) para não
    precisar reprocessar — e para preservar o retrato daquele período mesmo
    que o usuário edite/apague movimentações depois."""

    __tablename__ = "relatorios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    tipo = Column(SAEnum(TipoRelatorio, name="tipo_relatorio", values_callable=lambda e: [x.value for x in e]), nullable=False)
    data_inicio = Column(Date, nullable=False)
    data_fim = Column(Date, nullable=False)
    dados = Column(JSONB, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    usuario = relationship("Usuario")

    def __repr__(self) -> str:
        return f"<Relatorio id={self.id} tipo={self.tipo} periodo={self.data_inicio}..{self.data_fim}>"
