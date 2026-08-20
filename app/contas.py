"""
Lógica de contas bancárias e transferências. Separado do main.py seguindo
o mesmo padrão de relatorios.py — a rota só orquestra, a lógica de
cálculo/agregação fica aqui.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


def calcular_saldo_conta(db: Session, conta: models.Conta, ate_data: Optional[date] = None) -> Decimal:
    """saldo_inicial + receitas - despesas (das movimentações da conta)
    + transferências recebidas - transferências enviadas.

    `ate_data`: sem informar, é o saldo atual (comportamento de sempre).
    Informando, considera só movimentações/transferências com `data <=
    ate_data` — "qual era o saldo da conta naquele momento". Usado pelo
    progresso de Plano (guardar dinheiro / simples): saldo hoje menos
    saldo no mês de início do plano."""
    filtro_data_mov = [models.Movimentacao.data <= ate_data] if ate_data else []
    filtro_data_transf = [models.Transferencia.data <= ate_data] if ate_data else []

    receitas = (
        db.query(func.coalesce(func.sum(models.Movimentacao.valor), 0))
        .join(models.Categoria)
        .filter(
            models.Movimentacao.conta_id == conta.id,
            models.Categoria.tipo == models.TipoMovimentacao.RECEITA,
            *filtro_data_mov,
        )
        .scalar()
    )
    despesas = (
        db.query(func.coalesce(func.sum(models.Movimentacao.valor), 0))
        .join(models.Categoria)
        .filter(
            models.Movimentacao.conta_id == conta.id,
            models.Categoria.tipo == models.TipoMovimentacao.DESPESA,
            *filtro_data_mov,
        )
        .scalar()
    )
    recebidas = (
        db.query(func.coalesce(func.sum(models.Transferencia.valor), 0))
        .filter(models.Transferencia.conta_destino_id == conta.id, *filtro_data_transf)
        .scalar()
    )
    enviadas = (
        db.query(func.coalesce(func.sum(models.Transferencia.valor), 0))
        .filter(models.Transferencia.conta_origem_id == conta.id, *filtro_data_transf)
        .scalar()
    )
    return conta.saldo_inicial + receitas - despesas + recebidas - enviadas


def calcular_serie_saldo_diaria(
    db: Session, usuario_id: uuid.UUID, contas: list[models.Conta], dias: int = 30
) -> list[dict]:
    """Série diária de saldo de cada conta — um ponto por dia, sem buracos.
    Usada pelo gráfico de linha em destaque de Controle.

    A janela normalmente cobre os últimos `dias` dias (hoje incluso), mas
    se a primeira movimentação/transferência do usuário for mais recente
    que isso, a janela encolhe pra começar nela — em vez de esticar o
    gráfico com vários dias "achatados" (saldo parado) antes de qualquer
    coisa ter acontecido.

    Ponto de partida de cada conta: calcular_saldo_conta(..., ate_data=
    véspera da janela) — o saldo "congelado" antes do primeiro dia da
    janela — depois soma-se, dia a dia, o delta daquele dia (agregado em
    SQL por (conta, dia), igual espírito de calcular_saldos_contas: não dá
    pra carregar toda movimentação pra memória). A janela é curta (no
    máximo `dias`), então a soma cumulativa dia a dia em Python não escala
    com o histórico todo — só com o tamanho da janela."""
    if not contas:
        return []

    conta_ids = [c.id for c in contas]
    hoje = date.today()
    janela_inicio = hoje - timedelta(days=dias - 1)

    primeira_movimentacao = (
        db.query(func.min(models.Movimentacao.data))
        .filter(models.Movimentacao.usuario_id == usuario_id)
        .scalar()
    )
    primeira_transferencia = (
        db.query(func.min(models.Transferencia.data))
        .filter(models.Transferencia.usuario_id == usuario_id)
        .scalar()
    )
    primeiras_datas = [d for d in (primeira_movimentacao, primeira_transferencia) if d is not None]
    if primeiras_datas:
        janela_inicio = max(janela_inicio, min(primeiras_datas))

    vespera = janela_inicio - timedelta(days=1)

    # delta[(conta_id, dia)] = receitas - despesas (movimentações) +
    # recebidas - enviadas (transferências) naquele dia, só dentro da janela.
    delta: Dict[tuple, Decimal] = {}

    receitas_despesas = (
        db.query(
            models.Movimentacao.conta_id,
            models.Movimentacao.data,
            models.Categoria.tipo,
            func.coalesce(func.sum(models.Movimentacao.valor), 0),
        )
        .join(models.Categoria)
        .filter(
            models.Movimentacao.conta_id.in_(conta_ids),
            models.Movimentacao.data >= janela_inicio,
            models.Movimentacao.data <= hoje,
        )
        .group_by(models.Movimentacao.conta_id, models.Movimentacao.data, models.Categoria.tipo)
        .all()
    )
    for conta_id, dia, tipo, total in receitas_despesas:
        chave = (conta_id, dia)
        sinal = total if tipo == models.TipoMovimentacao.RECEITA else -total
        delta[chave] = delta.get(chave, Decimal("0")) + sinal

    recebidas = (
        db.query(
            models.Transferencia.conta_destino_id,
            models.Transferencia.data,
            func.coalesce(func.sum(models.Transferencia.valor), 0),
        )
        .filter(
            models.Transferencia.conta_destino_id.in_(conta_ids),
            models.Transferencia.data >= janela_inicio,
            models.Transferencia.data <= hoje,
        )
        .group_by(models.Transferencia.conta_destino_id, models.Transferencia.data)
        .all()
    )
    for conta_id, dia, total in recebidas:
        chave = (conta_id, dia)
        delta[chave] = delta.get(chave, Decimal("0")) + total

    enviadas = (
        db.query(
            models.Transferencia.conta_origem_id,
            models.Transferencia.data,
            func.coalesce(func.sum(models.Transferencia.valor), 0),
        )
        .filter(
            models.Transferencia.conta_origem_id.in_(conta_ids),
            models.Transferencia.data >= janela_inicio,
            models.Transferencia.data <= hoje,
        )
        .group_by(models.Transferencia.conta_origem_id, models.Transferencia.data)
        .all()
    )
    for conta_id, dia, total in enviadas:
        chave = (conta_id, dia)
        delta[chave] = delta.get(chave, Decimal("0")) - total

    resultado = []
    for conta in contas:
        saldo_acumulado = calcular_saldo_conta(db, conta, ate_data=vespera)

        serie = []
        dia = janela_inicio
        while dia <= hoje:
            saldo_acumulado += delta.get((conta.id, dia), Decimal("0"))
            serie.append({"dia": dia.isoformat(), "saldo": float(saldo_acumulado)})
            dia += timedelta(days=1)

        resultado.append({
            "conta_id": str(conta.id),
            "conta_nome": conta.apelido or conta.nome_banco,
            "serie": serie,
        })

    return resultado


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