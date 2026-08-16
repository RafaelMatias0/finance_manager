"""
Lógica de contas bancárias e transferências. Separado do main.py seguindo
o mesmo padrão de relatorios.py — a rota só orquestra, a lógica de
cálculo/agregação fica aqui.
"""
import uuid
from decimal import Decimal
from typing import Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


def calcular_saldo_conta(db: Session, conta: models.Conta) -> Decimal:
    """saldo_inicial + receitas - despesas (das movimentações da conta)
    + transferências recebidas - transferências enviadas."""
    receitas = (
        db.query(func.coalesce(func.sum(models.Movimentacao.valor), 0))
        .join(models.Categoria)
        .filter(
            models.Movimentacao.conta_id == conta.id,
            models.Categoria.tipo == models.TipoMovimentacao.RECEITA,
        )
        .scalar()
    )
    despesas = (
        db.query(func.coalesce(func.sum(models.Movimentacao.valor), 0))
        .join(models.Categoria)
        .filter(
            models.Movimentacao.conta_id == conta.id,
            models.Categoria.tipo == models.TipoMovimentacao.DESPESA,
        )
        .scalar()
    )
    recebidas = (
        db.query(func.coalesce(func.sum(models.Transferencia.valor), 0))
        .filter(models.Transferencia.conta_destino_id == conta.id)
        .scalar()
    )
    enviadas = (
        db.query(func.coalesce(func.sum(models.Transferencia.valor), 0))
        .filter(models.Transferencia.conta_origem_id == conta.id)
        .scalar()
    )
    return conta.saldo_inicial + receitas - despesas + recebidas - enviadas


def calcular_saldos_contas(db: Session, contas: list[models.Conta]) -> Dict[uuid.UUID, Decimal]:
    """Versão em lote de calcular_saldo_conta, para não fazer N queries
    isoladas ao listar todas as contas do usuário."""
    if not contas:
        return {}

    conta_ids = [c.id for c in contas]

    por_conta = {c.id: c.saldo_inicial for c in contas}

    receitas_despesas = (
        db.query(
            models.Movimentacao.conta_id,
            models.Categoria.tipo,
            func.coalesce(func.sum(models.Movimentacao.valor), 0),
        )
        .join(models.Categoria)
        .filter(models.Movimentacao.conta_id.in_(conta_ids))
        .group_by(models.Movimentacao.conta_id, models.Categoria.tipo)
        .all()
    )
    for conta_id, tipo, total in receitas_despesas:
        if tipo == models.TipoMovimentacao.RECEITA:
            por_conta[conta_id] += total
        else:
            por_conta[conta_id] -= total

    recebidas = (
        db.query(models.Transferencia.conta_destino_id, func.coalesce(func.sum(models.Transferencia.valor), 0))
        .filter(models.Transferencia.conta_destino_id.in_(conta_ids))
        .group_by(models.Transferencia.conta_destino_id)
        .all()
    )
    for conta_id, total in recebidas:
        por_conta[conta_id] += total

    enviadas = (
        db.query(models.Transferencia.conta_origem_id, func.coalesce(func.sum(models.Transferencia.valor), 0))
        .filter(models.Transferencia.conta_origem_id.in_(conta_ids))
        .group_by(models.Transferencia.conta_origem_id)
        .all()
    )
    for conta_id, total in enviadas:
        por_conta[conta_id] -= total

    return por_conta