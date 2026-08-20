"""
Schemas Pydantic — validam o que entra (Create) e formatam o que sai (Out) da API.
Separados dos models do SQLAlchemy de propósito: o banco pode ter campos
(como senha_hash) que nunca devem ser expostos na resposta da API.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, ConfigDict, Field, model_validator

from app.models import TipoMovimentacao, TipoRelatorio, TipoPlano, GuardarModo, CriterioReducao, DividaModo


class OrdenarPor(str, Enum):
    DATA = "data"
    VALOR = "valor"
    CRIADO_EM = "criado_em"


class OrdemDirecao(str, Enum):
    ASC = "asc"
    DESC = "desc"


# ---------- Usuario ----------

class UsuarioCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=6, max_length=128)


class UsuarioUpdate(BaseModel):
    # Só o nome é editável — email é a identidade de login (usado até pra
    # achar o usuário no /auth/login) e não faz parte deste schema de
    # propósito, então nunca pode ser alterado por aqui.
    nome: Optional[str] = Field(default=None, min_length=1, max_length=120)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    email: EmailStr
    criado_em: datetime


# ---------- Categoria ----------

class CategoriaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    tipo: TipoMovimentacao


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    tipo: TipoMovimentacao
    usuario_id: Optional[uuid.UUID]


class CategoriaUpdate(BaseModel):
    """Todos os campos opcionais — só os enviados são alterados (PATCH)."""
    nome: Optional[str] = Field(default=None, min_length=1, max_length=80)
    tipo: Optional[TipoMovimentacao] = None


# ---------- Conta ----------

class ContaCreate(BaseModel):
    nome_banco: str = Field(min_length=1, max_length=80)
    apelido: Optional[str] = Field(default=None, max_length=80)
    saldo_inicial: Decimal = Field(default=Decimal("0"), max_digits=12, decimal_places=2)


class ContaUpdate(BaseModel):
    """Todos os campos opcionais — só os enviados são alterados (PATCH)."""
    nome_banco: Optional[str] = Field(default=None, min_length=1, max_length=80)
    apelido: Optional[str] = Field(default=None, max_length=80)
    saldo_inicial: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)


class ContaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome_banco: str
    apelido: Optional[str]
    saldo_inicial: Decimal
    saldo_atual: Decimal
    criado_em: datetime


# ---------- Movimentacao ----------

class MovimentacaoCreate(BaseModel):
    valor: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    descricao: Optional[str] = Field(default=None, max_length=255)
    data: date = Field(default_factory=date.today)
    categoria_id: uuid.UUID
    conta_id: uuid.UUID


class MovimentacaoUpdate(BaseModel):
    """Todos os campos opcionais — só os enviados são alterados (PATCH)."""
    valor: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    descricao: Optional[str] = Field(default=None, max_length=255)
    data: Optional[date] = None
    categoria_id: Optional[uuid.UUID] = None
    conta_id: Optional[uuid.UUID] = None


class MovimentacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    valor: Decimal
    descricao: Optional[str]
    data: date
    usuario_id: uuid.UUID
    categoria_id: uuid.UUID
    conta_id: uuid.UUID
    # Preenchidos só quando a movimentação nasceu de "marcar uma
    # pendência como paga" (POST /pendencias/{id}/pagar) — nulos numa
    # movimentação criada normalmente.
    pendencia_id: Optional[uuid.UUID] = None
    pendencia_referencia: Optional[date] = None
    # Preenchido em pagamentos de um Plano de "quitar dívida" — direto
    # (modo prazo) ou porque a pendência paga pertence a um plano (modo
    # parcelas). Nulo em movimentações normais e em planos de "guardar
    # dinheiro" (esses não geram movimentação nenhuma).
    plano_id: Optional[uuid.UUID] = None
    criado_em: datetime


class MovimentacaoListOut(BaseModel):
    total: int
    skip: int
    limit: int
    itens: List[MovimentacaoOut]


# ---------- Transferência ----------

class TransferenciaCreate(BaseModel):
    conta_origem_id: uuid.UUID
    conta_destino_id: uuid.UUID
    valor: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    descricao: Optional[str] = Field(default=None, max_length=255)
    data: date = Field(default_factory=date.today)


class TransferenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conta_origem_id: uuid.UUID
    conta_destino_id: uuid.UUID
    valor: Decimal
    descricao: Optional[str]
    data: date
    criado_em: datetime


# ---------- Pendência ----------

class StatusCiclo(str, Enum):
    ATRASADA = "atrasada"
    A_VENCER = "a_vencer"


class CicloPendencia(BaseModel):
    """Um vencimento específico (mês, pra recorrente; a data única, pra
    avulsa) ainda sem pagamento vinculado."""
    data_vencimento: date
    status: StatusCiclo


class PendenciaCreate(BaseModel):
    descricao: str = Field(min_length=1, max_length=120)
    valor: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    categoria_id: uuid.UUID
    conta_id: Optional[uuid.UUID] = None
    recorrente: bool = False
    dia_vencimento: Optional[int] = Field(default=None, ge=1, le=31)
    data_vencimento: Optional[date] = None

    @model_validator(mode="after")
    def _validar_vencimento(self):
        if self.recorrente:
            if self.dia_vencimento is None:
                raise ValueError("dia_vencimento é obrigatório para pendência recorrente")
            if self.data_vencimento is not None:
                raise ValueError("data_vencimento não se aplica a pendência recorrente (use dia_vencimento)")
        else:
            if self.data_vencimento is None:
                raise ValueError("data_vencimento é obrigatório para pendência avulsa")
            if self.dia_vencimento is not None:
                raise ValueError("dia_vencimento não se aplica a pendência avulsa (use data_vencimento)")
        return self


class PendenciaUpdate(BaseModel):
    """Todos os campos opcionais — só os enviados são alterados (PATCH).
    Não valida a combinação recorrente/dia_vencimento/data_vencimento
    entre si (validação completa só faz sentido no Create — um PATCH
    parcial poderia mudar só a descrição, por exemplo)."""
    descricao: Optional[str] = Field(default=None, min_length=1, max_length=120)
    valor: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    categoria_id: Optional[uuid.UUID] = None
    conta_id: Optional[uuid.UUID] = None
    dia_vencimento: Optional[int] = Field(default=None, ge=1, le=31)
    data_vencimento: Optional[date] = None
    ativa: Optional[bool] = None


class PendenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    descricao: str
    valor: Decimal
    categoria_id: uuid.UUID
    conta_id: Optional[uuid.UUID]
    recorrente: bool
    dia_vencimento: Optional[int]
    data_vencimento: Optional[date]
    ativa: bool
    criado_em: datetime
    ciclos: List[CicloPendencia]


class PendenciaPagarRequest(BaseModel):
    data_vencimento: date
    conta_id: uuid.UUID
    valor: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    descricao: Optional[str] = Field(default=None, max_length=255)
    data: date = Field(default_factory=date.today)


# ---------- Plano ----------

class PlanoCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    tipo: TipoPlano
    conta_id: uuid.UUID
    mes_inicio: date

    # guardar_dinheiro
    guardar_modo: Optional[GuardarModo] = None
    criterio_reducao: Optional[CriterioReducao] = None
    alvo_percentual: Optional[Decimal] = Field(default=None, gt=0, max_digits=5, decimal_places=2)
    alvo_valor_reducao: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)

    # quitar_divida
    divida_modo: Optional[DividaModo] = None
    # Só usados na criação de quitar_divida/parcelas — viram a Pendencia
    # recorrente por trás; não são campos do Plano em si.
    numero_parcelas: Optional[int] = Field(default=None, ge=1, le=600)
    dia_vencimento: Optional[int] = Field(default=None, ge=1, le=31)

    # Compartilhados: guardar_dinheiro/simples e quitar_divida usam
    # valor_alvo; guardar_dinheiro (as duas submodalidades) e
    # quitar_divida/prazo usam data_prazo; guardar_dinheiro/
    # reducao_categoria e quitar_divida (os dois modos) usam categoria_id.
    # Em quitar_divida/parcelas, valor_alvo representa o valor DE CADA
    # PARCELA na entrada (o total = parcela × numero_parcelas é calculado
    # e guardado no Plano).
    valor_alvo: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    data_prazo: Optional[date] = None
    categoria_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def _validar_campos(self):
        if self.tipo == TipoPlano.GUARDAR_DINHEIRO:
            if self.divida_modo is not None or self.numero_parcelas is not None or self.dia_vencimento is not None:
                raise ValueError("campos de quitar_divida não se aplicam a guardar_dinheiro")
            if self.guardar_modo is None:
                raise ValueError("guardar_modo é obrigatório para tipo=guardar_dinheiro")
            if self.data_prazo is None:
                raise ValueError("data_prazo é obrigatório para guardar_dinheiro")

            if self.guardar_modo == GuardarModo.SIMPLES:
                if self.valor_alvo is None:
                    raise ValueError("valor_alvo é obrigatório para guardar_dinheiro/simples")
                if self.categoria_id is not None or self.criterio_reducao is not None:
                    raise ValueError("categoria_id/criterio_reducao não se aplicam ao modo simples")
            else:  # REDUCAO_CATEGORIA
                if self.valor_alvo is not None:
                    raise ValueError("valor_alvo não se aplica ao modo reducao_categoria")
                if self.categoria_id is None:
                    raise ValueError("categoria_id é obrigatório para guardar_dinheiro/reducao_categoria")
                if self.criterio_reducao is None:
                    raise ValueError("criterio_reducao é obrigatório para guardar_dinheiro/reducao_categoria")
                if self.criterio_reducao == CriterioReducao.PERCENTUAL_RECEITA and self.alvo_percentual is None:
                    raise ValueError("alvo_percentual é obrigatório quando criterio_reducao=percentual_receita")
                if self.criterio_reducao == CriterioReducao.VALOR_FIXO and self.alvo_valor_reducao is None:
                    raise ValueError("alvo_valor_reducao é obrigatório quando criterio_reducao=valor_fixo")
        else:  # QUITAR_DIVIDA
            if self.guardar_modo is not None or self.criterio_reducao is not None or self.alvo_percentual is not None or self.alvo_valor_reducao is not None:
                raise ValueError("campos de guardar_dinheiro não se aplicam a quitar_divida")
            if self.divida_modo is None:
                raise ValueError("divida_modo é obrigatório para tipo=quitar_divida")
            if self.categoria_id is None:
                raise ValueError("categoria_id é obrigatório para quitar_divida")
            if self.valor_alvo is None:
                raise ValueError("valor_alvo é obrigatório para quitar_divida (valor total, ou valor da parcela no modo parcelas)")

            if self.divida_modo == DividaModo.PRAZO:
                if self.data_prazo is None:
                    raise ValueError("data_prazo é obrigatório para quitar_divida/prazo")
                if self.numero_parcelas is not None or self.dia_vencimento is not None:
                    raise ValueError("numero_parcelas/dia_vencimento não se aplicam ao modo prazo")
            else:  # PARCELAS
                if self.data_prazo is not None:
                    raise ValueError("data_prazo não se aplica ao modo parcelas (use numero_parcelas)")
                if self.numero_parcelas is None:
                    raise ValueError("numero_parcelas é obrigatório para quitar_divida/parcelas")
                if self.dia_vencimento is None:
                    raise ValueError("dia_vencimento é obrigatório para quitar_divida/parcelas")
        return self


class PlanoUpdate(BaseModel):
    """Todos os campos opcionais — só os enviados são alterados (PATCH).
    Não permite mudar tipo/guardar_modo/divida_modo/pendencia_id — a
    combinação de campos obrigatórios muda demais entre eles pra um PATCH
    parcial fazer sentido; pra isso, apague e crie outro plano."""
    nome: Optional[str] = Field(default=None, min_length=1, max_length=120)
    conta_id: Optional[uuid.UUID] = None
    mes_inicio: Optional[date] = None
    ativo: Optional[bool] = None
    valor_alvo: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    data_prazo: Optional[date] = None
    categoria_id: Optional[uuid.UUID] = None
    alvo_percentual: Optional[Decimal] = Field(default=None, gt=0, max_digits=5, decimal_places=2)
    alvo_valor_reducao: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)


class PlanoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    nome: str
    tipo: TipoPlano
    conta_id: uuid.UUID
    mes_inicio: date
    ativo: bool
    guardar_modo: Optional[GuardarModo]
    criterio_reducao: Optional[CriterioReducao]
    alvo_percentual: Optional[Decimal]
    alvo_valor_reducao: Optional[Decimal]
    divida_modo: Optional[DividaModo]
    pendencia_id: Optional[uuid.UUID]
    valor_alvo: Optional[Decimal]
    data_prazo: Optional[date]
    categoria_id: Optional[uuid.UUID]
    criado_em: datetime
    # Formato varia conforme tipo/submodo (ver app/planos.py) — mesmo
    # espírito de RelatorioOut.dados, não vale a pena um schema rígido
    # por campo pra algo que já muda de forma por natureza.
    progresso: Dict[str, Any]


class PlanoAportarRequest(BaseModel):
    """Só usado por quitar_divida/prazo — pagamento de parcela usa
    POST /pendencias/{id}/pagar (a conta já é fixa no plano, não precisa
    ser informada aqui)."""
    valor: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    data: date = Field(default_factory=date.today)
    descricao: Optional[str] = Field(default=None, max_length=255)


# ---------- Saldo ----------

class SaldoOut(BaseModel):
    usuario_id: uuid.UUID
    total_receitas: Decimal
    total_despesas: Decimal
    saldo: Decimal


# ---------- Autenticação ----------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Relatórios ----------

class RelatorioOut(BaseModel):
    """Relatório automático salvo (semanal/mensal). O conteúdo em si
    (histórico, saldo, dados de gráfico) fica em `dados` — o formato varia
    pouco entre execuções, então mantemos como dict em vez de um schema
    rígido por campo."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: TipoRelatorio
    data_inicio: date
    data_fim: date
    dados: Dict[str, Any]
    criado_em: datetime