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
- Pendencia: "definição" de uma conta a pagar/receber — recorrente
  (aluguel, assinaturas, vencimento mensal) ou avulsa (um vencimento
  único). Não guarda status pago/pendente: isso é sempre calculado a
  partir de existir ou não uma Movimentacao vinculada (campo
  Movimentacao.pendencia_id) a um vencimento (Movimentacao.
  pendencia_referencia) específico — mesmo princípio de "nada calculável
  vira tabela própria" já usado pro saldo.
"""
import enum
import uuid
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Column,
    String,
    ForeignKey,
    Integer,
    Numeric,
    Date,
    DateTime,
    Enum as SAEnum,
    Index,
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
    pendencias = relationship(
        "Pendencia", back_populates="usuario", cascade="all, delete-orphan"
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
    # passive_deletes=True: deixa o RESTRICT do banco decidir (409 na
    # exclusão se houver movimentações vinculadas). Sem isso, o
    # SQLAlchemy tenta "desvincular" as movimentações (settar
    # categoria_id = NULL) antes do delete — e só não quebra hoje porque
    # a coluna é NOT NULL (faz a mesma coisa dar errado por outro
    # motivo). Ver Pendencia.pagamentos, onde isso quebrava de verdade.
    movimentacoes = relationship("Movimentacao", back_populates="categoria", passive_deletes=True)

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
    movimentacoes = relationship("Movimentacao", back_populates="conta", passive_deletes=True)

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

    # Preenchidos só quando esta movimentação nasceu de "marcar uma
    # pendência como paga" (POST /pendencias/{id}/pagar). pendencia_id
    # identifica QUAL pendência; pendencia_referencia identifica QUAL
    # vencimento/ciclo dela foi quitado — não é o mesmo que `data` (que é
    # quando o pagamento de fato aconteceu, podendo ser depois do
    # vencimento). RESTRICT: apagar uma pendência com pagamentos já feitos
    # perderia esse histórico silenciosamente.
    pendencia_id = Column(
        UUID(as_uuid=True), ForeignKey("pendencias.id", ondelete="RESTRICT"), nullable=True
    )
    pendencia_referencia = Column(Date, nullable=True)

    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    usuario = relationship("Usuario", back_populates="movimentacoes")
    categoria = relationship("Categoria", back_populates="movimentacoes")
    conta = relationship("Conta", back_populates="movimentacoes")
    pendencia = relationship("Pendencia", back_populates="pagamentos")

    __table_args__ = (
        # Trava contra pagar o mesmo vencimento duas vezes — só se aplica
        # às linhas que de fato vieram de uma pendência (pendencia_id não
        # nulo); movimentações normais não entram nessa restrição.
        Index(
            "ix_movimentacoes_pendencia_ciclo_unico",
            "pendencia_id",
            "pendencia_referencia",
            unique=True,
            postgresql_where=pendencia_id.isnot(None),
        ),
    )

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


class Pendencia(Base):
    """"Definição" de uma conta a pagar/receber — recorrente (aluguel,
    assinaturas: um vencimento por mês, no dia `dia_vencimento`) ou avulsa
    (um vencimento único, em `data_vencimento`). Não guarda status
    pago/pendente: cada vencimento é considerado pago quando existe uma
    Movimentacao com `pendencia_id`==esta e `pendencia_referencia`==aquele
    vencimento (ver Movimentacao). Sem campo `tipo` redundante — igual
    Movimentacao, o tipo vem de `pendencia.categoria.tipo`."""

    __tablename__ = "pendencias"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    descricao = Column(String(120), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    categoria_id = Column(
        UUID(as_uuid=True), ForeignKey("categorias.id", ondelete="RESTRICT"), nullable=False
    )
    # Conta sugerida por padrão ao marcar como paga — não obrigatória,
    # já que a mesma pendência pode ser paga de contas diferentes em
    # momentos diferentes.
    conta_id = Column(
        UUID(as_uuid=True), ForeignKey("contas.id", ondelete="RESTRICT"), nullable=True
    )
    recorrente = Column(Boolean, nullable=False, default=False)
    # Exatamente um dos dois preenchido, validado na camada de schema/rota
    # (mesmo estilo do resto do projeto — sem CHECK no banco):
    # dia_vencimento (1-31) se recorrente, data_vencimento se avulsa.
    dia_vencimento = Column(Integer, nullable=True)
    data_vencimento = Column(Date, nullable=True)
    # Permite "pausar" uma recorrente (ex: assinatura cancelada) sem
    # apagar — apagar exigiria não ter nenhum pagamento no histórico.
    ativa = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    usuario = relationship("Usuario", back_populates="pendencias")
    categoria = relationship("Categoria")
    conta = relationship("Conta")
    # passive_deletes=True: deixa o RESTRICT do banco barrar o delete
    # (409) quando há Movimentacao vinculada, em vez do SQLAlchemy tentar
    # settar pendencia_id = NULL nelas antes de apagar a pendência (o que
    # funcionaria silenciosamente aqui, já que pendencia_id é nullable —
    # apagaria a pendência e "descolaria" o histórico de pagamentos sem
    # avisar ninguém).
    pagamentos = relationship("Movimentacao", back_populates="pendencia", passive_deletes=True)

    def __repr__(self) -> str:
        return f"<Pendencia id={self.id} descricao={self.descricao} recorrente={self.recorrente}>"


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