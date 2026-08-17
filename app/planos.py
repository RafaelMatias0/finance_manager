"""
Lógica de planos e metas. Separado do main.py seguindo o mesmo padrão de
contas.py/pendencias.py/relatorios.py — a rota só orquestra, o cálculo
fica aqui.

Progresso nunca é guardado — é sempre calculado a partir da atividade
financeira real (saldo de conta, gasto por categoria, ou Movimentações
vinculadas), igual saldo e pendência já fazem.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app import contas as contas_service
from app import pendencias as pendencias_service


def _mes_seguinte(referencia: date) -> date:
    if referencia.month == 12:
        return date(referencia.year + 1, 1, 1)
    return date(referencia.year, referencia.month + 1, 1)


def _fim_do_mes(mes: date) -> date:
    return _mes_seguinte(mes) - timedelta(days=1)


def _meses_entre(inicio: date, fim: date) -> List[date]:
    """Primeiro dia de cada mês, de `inicio` até `fim` (inclusive)."""
    meses = []
    ano, mes = inicio.year, inicio.month
    while (ano, mes) <= (fim.year, fim.month):
        meses.append(date(ano, mes, 1))
        if mes == 12:
            ano, mes = ano + 1, 1
        else:
            mes += 1
    return meses


def _tres_meses_antes(referencia: date) -> List[date]:
    """Os 3 meses imediatamente anteriores ao mês de `referencia`."""
    meses = []
    ano, mes = referencia.year, referencia.month
    for _ in range(3):
        mes -= 1
        if mes == 0:
            mes, ano = 12, ano - 1
        meses.append(date(ano, mes, 1))
    return list(reversed(meses))


def _soma_categoria_no_periodo(
    db: Session,
    conta_id: uuid.UUID,
    categoria_id: uuid.UUID,
    tipo: models.TipoMovimentacao,
    data_inicio: date,
    data_fim: date,
) -> Decimal:
    return (
        db.query(func.coalesce(func.sum(models.Movimentacao.valor), 0))
        .join(models.Categoria)
        .filter(
            models.Movimentacao.conta_id == conta_id,
            models.Movimentacao.categoria_id == categoria_id,
            models.Categoria.tipo == tipo,
            models.Movimentacao.data >= data_inicio,
            models.Movimentacao.data <= data_fim,
        )
        .scalar()
    )


def _soma_receita_conta_no_periodo(db: Session, conta_id: uuid.UUID, data_inicio: date, data_fim: date) -> Decimal:
    return (
        db.query(func.coalesce(func.sum(models.Movimentacao.valor), 0))
        .join(models.Categoria)
        .filter(
            models.Movimentacao.conta_id == conta_id,
            models.Categoria.tipo == models.TipoMovimentacao.RECEITA,
            models.Movimentacao.data >= data_inicio,
            models.Movimentacao.data <= data_fim,
        )
        .scalar()
    )


def calcular_progresso_guardar_simples(db: Session, plano: models.Plano) -> dict:
    """Progresso = quanto o saldo da conta cresceu desde o dia anterior ao
    início do plano. Nunca negativo — se o saldo caiu, o progresso fica 0
    em vez de negativo."""
    baseline = plano.mes_inicio - timedelta(days=1)
    saldo_inicio = contas_service.calcular_saldo_conta(db, plano.conta, ate_data=baseline)
    saldo_atual = contas_service.calcular_saldo_conta(db, plano.conta)
    progresso_valor = max(Decimal("0"), saldo_atual - saldo_inicio)
    percentual = float(progresso_valor / plano.valor_alvo * 100) if plano.valor_alvo else 0.0
    return {
        "modo": "simples",
        "progresso_valor": float(progresso_valor),
        "valor_alvo": float(plano.valor_alvo),
        "percentual": round(min(100.0, percentual), 2),
    }


def calcular_progresso_reducao_categoria(db: Session, plano: models.Plano, hoje: Optional[date] = None) -> dict:
    """Progresso mensal: em cada mês desde o início, o gasto real na
    categoria (dentro da conta do plano) ficou dentro do alvo? O alvo é um
    percentual da receita do mês (mesma conta) ou um valor fixo abaixo da
    média de gasto dos 3 meses ANTERIORES ao início — baseline calculado
    uma vez só, não recalculado a cada mês."""
    hoje = hoje or date.today()

    baseline_valor = None
    if plano.criterio_reducao == models.CriterioReducao.VALOR_FIXO:
        soma_baseline = sum(
            (
                _soma_categoria_no_periodo(
                    db, plano.conta_id, plano.categoria_id, models.TipoMovimentacao.DESPESA,
                    mes, _fim_do_mes(mes),
                )
                for mes in _tres_meses_antes(plano.mes_inicio)
            ),
            Decimal("0"),
        )
        baseline_valor = soma_baseline / 3

    meses = _meses_entre(plano.mes_inicio, hoje.replace(day=1))
    detalhes = []
    for mes in meses:
        eh_mes_atual = mes.year == hoje.year and mes.month == hoje.month
        fim_mes = hoje if eh_mes_atual else _fim_do_mes(mes)
        gasto = _soma_categoria_no_periodo(
            db, plano.conta_id, plano.categoria_id, models.TipoMovimentacao.DESPESA, mes, fim_mes,
        )

        if plano.criterio_reducao == models.CriterioReducao.PERCENTUAL_RECEITA:
            receita = _soma_receita_conta_no_periodo(db, plano.conta_id, mes, fim_mes)
            percentual_gasto = float(gasto / receita * 100) if receita > 0 else (100.0 if gasto > 0 else 0.0)
            alvo_descricao = f"até {plano.alvo_percentual}% da receita do mês"
            cumpriu = percentual_gasto <= float(plano.alvo_percentual)
        else:
            alvo_mes = baseline_valor - plano.alvo_valor_reducao
            alvo_descricao = f"até {alvo_mes:.2f}"
            cumpriu = gasto <= alvo_mes

        detalhes.append({
            "mes": mes.isoformat()[:7],
            "gasto": float(gasto),
            "alvo": alvo_descricao,
            "cumpriu": cumpriu,
        })

    meses_cumpridos = sum(1 for d in detalhes if d["cumpriu"])
    return {
        "modo": "reducao_categoria",
        "meses": detalhes,
        "meses_cumpridos": meses_cumpridos,
        "meses_total": len(detalhes),
    }


def calcular_progresso_divida_prazo(db: Session, plano: models.Plano) -> dict:
    progresso_valor = (
        db.query(func.coalesce(func.sum(models.Movimentacao.valor), 0))
        .filter(models.Movimentacao.plano_id == plano.id)
        .scalar()
    )
    percentual = float(progresso_valor / plano.valor_alvo * 100) if plano.valor_alvo else 0.0
    return {
        "modo": "prazo",
        "progresso_valor": float(progresso_valor),
        "valor_alvo": float(plano.valor_alvo),
        "percentual": round(min(100.0, percentual), 2),
    }


def calcular_progresso_divida_parcelas(db: Session, plano: models.Plano) -> dict:
    pendencia = plano.pendencia
    ciclos_pendentes = pendencias_service.ciclos_de_uma_pendencia(db, pendencia)
    total_parcelas = pendencia.numero_parcelas or 0
    # Conta pagamentos de verdade (Movimentacao vinculada), não
    # "numero_parcelas − ciclos pendentes" — essa conta dava errado logo
    # no início, quando ainda nem todos os N ciclos foram gerados (só
    # existe ciclo pros meses que já chegaram, não pros futuros).
    parcelas_pagas = (
        db.query(func.count(models.Movimentacao.id))
        .filter(models.Movimentacao.pendencia_id == pendencia.id)
        .scalar()
    )
    valor_parcela = pendencia.valor
    progresso_valor = valor_parcela * parcelas_pagas
    valor_alvo = valor_parcela * total_parcelas
    percentual = float(progresso_valor / valor_alvo * 100) if valor_alvo else 0.0
    return {
        "modo": "parcelas",
        "parcelas_pagas": parcelas_pagas,
        "parcelas_total": total_parcelas,
        "progresso_valor": float(progresso_valor),
        "valor_alvo": float(valor_alvo),
        "percentual": round(min(100.0, percentual), 2),
        "ciclos": ciclos_pendentes,
    }


def progresso_do_plano(db: Session, plano: models.Plano) -> dict:
    """Despacha pro cálculo certo conforme tipo/submodo do plano."""
    if plano.tipo == models.TipoPlano.GUARDAR_DINHEIRO:
        if plano.guardar_modo == models.GuardarModo.SIMPLES:
            return calcular_progresso_guardar_simples(db, plano)
        return calcular_progresso_reducao_categoria(db, plano)
    if plano.divida_modo == models.DividaModo.PRAZO:
        return calcular_progresso_divida_prazo(db, plano)
    return calcular_progresso_divida_parcelas(db, plano)


def listar_planos_com_progresso(db: Session, usuario_id: uuid.UUID) -> List[dict]:
    planos = (
        db.query(models.Plano)
        .filter(models.Plano.usuario_id == usuario_id)
        .order_by(models.Plano.criado_em)
        .all()
    )
    return [{"plano": p, "progresso": progresso_do_plano(db, p)} for p in planos]
