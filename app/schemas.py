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

from pydantic import BaseModel, EmailStr, ConfigDict, Field

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


class CategoriaUpdate(BaseModel):
    # Só o nome é editável — mudar o "tipo" de uma categoria já usada
    # reclassificaria retroativamente movimentações antigas, o que é
    # mais perigoso do que vale a pena para esse MVP.
    nome: str = Field(min_length=1, max_length=80)


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


# ---------- Movimentacao ----------

class MovimentacaoCreate(BaseModel):
    valor: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    descricao: Optional[str] = Field(default=None, max_length=255)
    data: date = Field(default_factory=date.today)
    categoria_id: uuid.UUID


class MovimentacaoUpdate(BaseModel):
    valor: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    descricao: Optional[str] = Field(default=None, max_length=255)
    data: Optional[date] = None
    categoria_id: Optional[uuid.UUID] = None


class MovimentacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    valor: Decimal
    descricao: Optional[str]
    data: date
    usuario_id: uuid.UUID
    categoria_id: uuid.UUID
    criado_em: datetime


class MovimentacaoUpdate(BaseModel):
    """Todos os campos opcionais — só os enviados são alterados (PATCH)."""
    valor: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    descricao: Optional[str] = Field(default=None, max_length=255)
    data: Optional[date] = None
    categoria_id: Optional[uuid.UUID] = None


class MovimentacaoListOut(BaseModel):
    total: int
    skip: int
    limit: int
    itens: List[MovimentacaoOut]


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
