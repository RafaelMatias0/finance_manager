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
- Plano: meta de "guardar dinheiro" (simples, ou reduzindo gasto numa
  categoria) ou "quitar dívida" (por prazo livre, ou por parcelas — que
  reaproveita Pendencia por baixo, com `numero_parcelas` limitando a
  geração de ciclos). Assim como saldo e pendência, o progresso nunca é
  guardado — é sempre calculado (ver app/planos.py).
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


class TipoPlano(str, enum.Enum):
    GUARDAR_DINHEIRO = "guardar_dinheiro"
    QUITAR_DIVIDA = "quitar_divida"


class GuardarModo(str, enum.Enum):
    SIMPLES = "simples"
    REDUCAO_CATEGORIA = "reducao_categoria"


class CriterioReducao(str, enum.Enum):
    PERCENTUAL_RECEITA = "percentual_receita"
    VALOR_FIXO = "valor_fixo"


class DividaModo(str, enum.Enum):
    PRAZO = "prazo"
    PARCELAS = "parcelas"


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
    planos = relationship(
        "Plano", back_populates="usuario", cascade="all, delete-orphan"
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

    # Preenchido quando esta movimentação é um pagamento de um Plano de
    # "quitar dívida" — direto no modo "prazo" (POST /planos/{id}/aportar);
    # indireto no modo "parcelas" (POST /pendencias/{id}/pagar também
    # grava aqui, se a pendência pertencer a um plano). Nunca preenchido
    # em planos de "guardar dinheiro" — esses não geram movimentação
    # nenhuma, o progresso é derivado da atividade financeira normal.
    plano_id = Column(
        UUID(as_uuid=True), ForeignKey("planos.id", ondelete="RESTRICT"), nullable=True
    )

    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    usuario = relationship("Usuario", back_populates="movimentacoes")
    categoria = relationship("Categoria", back_populates="movimentacoes")
    conta = relationship("Conta", back_populates="movimentacoes")
    pendencia = relationship("Pendencia", back_populates="pagamentos")
    plano = relationship("Plano", back_populates="pagamentos")

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
    # Nulo = recorrente sem fim definido (aluguel, assinatura). Preenchido
    # = número máximo de ocorrências a gerar (usado por Plano em modo
    # "quitar dívida por parcelas", que cria uma Pendencia recorrente com
    # teto em vez de indefinida — ver app/planos.py).
    numero_parcelas = Column(Integer, nullable=True)
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


class Plano(Base):
    """Meta de "guardar dinheiro" ou "quitar dívida". Progresso nunca é
    guardado — sempre calculado (ver app/planos.py). Um único conjunto de
    colunas cobre os dois tipos e suas submodalidades (campos que não se
    aplicam ficam nulos); a combinação certa é validada na camada de
    schema, não aqui:

    - guardar_dinheiro/simples: valor_alvo + data_prazo. Progresso = saldo
      da conta hoje − saldo da conta em mes_inicio. Não gera Movimentacao.
    - guardar_dinheiro/reducao_categoria: categoria_id + criterio_reducao
      (+ alvo_percentual ou alvo_valor_reducao) + data_prazo. Progresso é
      mês a mês (gasto real vs. alvo). Não gera Movimentacao.
    - quitar_divida/prazo: valor_alvo + data_prazo + categoria_id.
      Progresso = soma de Movimentacao.valor com plano_id==este.
    - quitar_divida/parcelas: valor_alvo (= parcela × numero_parcelas) +
      categoria_id + pendencia_id (a Pendencia recorrente com
      numero_parcelas que este plano criou e gerencia). Sem data_prazo —
      quem define o fim é o número de parcelas.
    """

    __tablename__ = "planos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    nome = Column(String(120), nullable=False)
    tipo = Column(
        SAEnum(TipoPlano, name="tipo_plano", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    # Conta é fixa pro plano inteiro (ao contrário de Pendencia, onde a
    # conta é escolhida a cada pagamento) — é ela quem define o progresso
    # de "guardar dinheiro" e de onde saem os pagamentos de "quitar dívida".
    conta_id = Column(
        UUID(as_uuid=True), ForeignKey("contas.id", ondelete="RESTRICT"), nullable=False
    )
    mes_inicio = Column(Date, nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)

    # ---- guardar_dinheiro ----
    guardar_modo = Column(
        SAEnum(GuardarModo, name="guardar_modo", values_callable=lambda e: [x.value for x in e]),
        nullable=True,
    )
    criterio_reducao = Column(
        SAEnum(CriterioReducao, name="criterio_reducao", values_callable=lambda e: [x.value for x in e]),
        nullable=True,
    )
    alvo_percentual = Column(Numeric(5, 2), nullable=True)
    alvo_valor_reducao = Column(Numeric(12, 2), nullable=True)

    # ---- quitar_divida ----
    divida_modo = Column(
        SAEnum(DividaModo, name="divida_modo", values_callable=lambda e: [x.value for x in e]),
        nullable=True,
    )
    pendencia_id = Column(
        UUID(as_uuid=True), ForeignKey("pendencias.id", ondelete="RESTRICT"), nullable=True
    )

    # ---- compartilhados entre guardar_dinheiro e quitar_divida/prazo ----
    valor_alvo = Column(Numeric(12, 2), nullable=True)
    data_prazo = Column(Date, nullable=True)
    categoria_id = Column(
        UUID(as_uuid=True), ForeignKey("categorias.id", ondelete="RESTRICT"), nullable=True
    )

    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    usuario = relationship("Usuario", back_populates="planos")
    conta = relationship("Conta", foreign_keys=[conta_id])
    categoria = relationship("Categoria", foreign_keys=[categoria_id])
    pendencia = relationship("Pendencia", foreign_keys=[pendencia_id])
    # passive_deletes=True: mesmo motivo de Pendencia.pagamentos — deixa o
    # RESTRICT do banco barrar apagar um plano com pagamentos já feitos.
    pagamentos = relationship("Movimentacao", back_populates="plano", passive_deletes=True)

    def __repr__(self) -> str:
        return f"<Plano id={self.id} nome={self.nome} tipo={self.tipo}>"


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