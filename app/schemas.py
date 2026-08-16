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

from app.models import TipoMovimentacao, TipoRelatorio


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