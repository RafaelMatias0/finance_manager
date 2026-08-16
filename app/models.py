"""
Modelos do banco de dados (SQLAlchemy ORM).

Estrutura:
- Usuario: dono das movimentações, categorias e contas.
- Categoria: classifica as movimentações (ex: Salário, Alimentação),
  vinculada a um tipo (receita/despesa) e opcionalmente a um usuário
  (categorias podem ser globais/padrão ou criadas pelo próprio usuário).
- Conta: registro "de visão" de uma conta bancária do usuário (nome do
  banco + apelido opcional + saldo inicial) — sem qualquer integração
  real com instituições financeiras.
- Movimentacao: registro de entrada (receita) ou saída (despesa) de
  dinheiro, sempre vinculado a uma Conta.
- Transferencia: movimento de dinheiro entre duas contas do próprio
  usuário. Fica fora de Movimentacao de propósito — não é receita nem
  despesa, então não deve aparecer nos relatórios (que derivam o tipo
  a partir de Categoria.tipo).
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
    contas = relationship(
        "Conta", back_populates="usuario", cascade="all, delete-orphan"
    )
    transferencias = relationship(
        "Transferencia", back_populates="usuario", cascade="all, delete-orphan"
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


class Conta(Base):
    """Registro "de visão" de uma conta bancária: só o nome do banco, um
    apelido opcional e um saldo inicial — não há integração real com
    bancos. O saldo atual é sempre calculado (saldo_inicial + receitas -
    despesas + transferências recebidas - transferências enviadas), nunca
    persistido, pelo mesmo motivo que o saldo geral do usuário não é uma
    tabela própria."""

    __tablename__ = "contas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    nome_banco = Column(String(80), nullable=False)
    apelido = Column(String(80), nullable=True)
    saldo_inicial = Column(Numeric(12, 2), nullable=False, default=0)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    usuario = relationship("Usuario", back_populates="contas")
    movimentacoes = relationship("Movimentacao", back_populates="conta")

    def __repr__(self) -> str:
        return f"<Conta id={self.id} nome_banco={self.nome_banco} apelido={self.apelido}>"


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
    # RESTRICT: apagar uma conta com histórico teria que apagar/realocar
    # movimentações primeiro — evita perder histórico silenciosamente,
    # mesma lógica já usada em categoria_id.
    conta_id = Column(
        UUID(as_uuid=True), ForeignKey("contas.id", ondelete="RESTRICT"), nullable=False
    )

    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    usuario = relationship("Usuario", back_populates="movimentacoes")
    categoria = relationship("Categoria", back_populates="movimentacoes")
    conta = relationship("Conta", back_populates="movimentacoes")

    def __repr__(self) -> str:
        return f"<Movimentacao id={self.id} valor={self.valor} categoria_id={self.categoria_id}>"


class Transferencia(Base):
    """Transferência entre duas contas do mesmo usuário. Não é receita nem
    despesa — não tem Categoria e não entra nos relatórios de
    receita/despesa. Só afeta o saldo calculado das duas contas
    envolvidas (soma zero para o usuário como um todo)."""

    __tablename__ = "transferencias"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    conta_origem_id = Column(
        UUID(as_uuid=True), ForeignKey("contas.id", ondelete="RESTRICT"), nullable=False
    )
    conta_destino_id = Column(
        UUID(as_uuid=True), ForeignKey("contas.id", ondelete="RESTRICT"), nullable=False
    )
    valor = Column(Numeric(12, 2), nullable=False)
    descricao = Column(String(255), nullable=True)
    data = Column(Date, default=date.today, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    usuario = relationship("Usuario", back_populates="transferencias")
    conta_origem = relationship("Conta", foreign_keys=[conta_origem_id])
    conta_destino = relationship("Conta", foreign_keys=[conta_destino_id])

    def __repr__(self) -> str:
        return f"<Transferencia id={self.id} origem={self.conta_origem_id} destino={self.conta_destino_id}>"


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