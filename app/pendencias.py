"""
Lógica de pendências. Separado do main.py seguindo o mesmo padrão de
contas.py/relatorios.py — a rota só orquestra, o cálculo fica aqui.

Pendência não guarda status pago/pendente: cada vencimento (ciclo) é
considerado pago quando existe uma Movimentacao com pendencia_id==esta e
pendencia_referencia==aquele vencimento. Este módulo calcula, pra cada
pendência, quais vencimentos ainda não têm pagamento.
"""
import uuid
from datetime import date, timedelta
from typing import Dict, List

from sqlalchemy.orm import Session

from app import models


def _mes_seguinte(referencia: date) -> date:
    """Primeiro dia do mês seguinte ao de `referencia`."""
    if referencia.month == 12:
        return date(referencia.year + 1, 1, 1)
    return date(referencia.year, referencia.month + 1, 1)


def _data_vencimento_do_mes(ano: int, mes: int, dia_vencimento: int) -> date:
    """Vencimento de uma pendência recorrente naquele mês — dias que não
    existem no mês (ex: 31 em fevereiro) caem pro último dia do mês."""
    ultimo_dia_do_mes = (_mes_seguinte(date(ano, mes, 1)) - timedelta(days=1)).day
    dia = min(dia_vencimento, ultimo_dia_do_mes)
    return date(ano, mes, dia)


def _vencimentos_recorrente(pendencia: models.Pendencia, hoje: date) -> List[date]:
    """Um vencimento por mês, do mês de criação da pendência até o mês
    atual (inclusive) — não gera vencimentos retroativos a antes da
    pendência existir, nem vencimentos de meses futuros."""
    inicio = pendencia.criado_em.date().replace(day=1)
    fim = hoje.replace(day=1)

    vencimentos = []
    ano, mes = inicio.year, inicio.month
    while (ano, mes) <= (fim.year, fim.month):
        vencimentos.append(_data_vencimento_do_mes(ano, mes, pendencia.dia_vencimento))
        if mes == 12:
            ano, mes = ano + 1, 1
        else:
            mes += 1
    return vencimentos


def calcular_ciclos_pendentes(
    pendencia: models.Pendencia, pagos: set, hoje: date = None
) -> List[dict]:
    """`pagos` é o conjunto de `pendencia_referencia` (date) já com
    Movimentacao vinculada, pra essa pendência. Retorna os vencimentos
    ainda sem pagamento, com status "atrasada" (vencimento < hoje) ou
    "a_vencer" (>= hoje)."""
    hoje = hoje or date.today()

    if pendencia.recorrente:
        vencimentos = _vencimentos_recorrente(pendencia, hoje)
    else:
        vencimentos = [pendencia.data_vencimento]

    ciclos = []
    for vencimento in vencimentos:
        if vencimento in pagos:
            continue
        status = "atrasada" if vencimento < hoje else "a_vencer"
        ciclos.append({"data_vencimento": vencimento, "status": status})
    return ciclos


def listar_pendencias_com_ciclos(db: Session, usuario_id: uuid.UUID) -> List[dict]:
    """Todas as pendências do usuário + os ciclos pendentes de cada uma,
    calculados em lote (uma query só pra saber o que já foi pago de
    todas, em vez de uma query por pendência)."""
    pendencias = (
        db.query(models.Pendencia)
        .filter(models.Pendencia.usuario_id == usuario_id)
        .order_by(models.Pendencia.criado_em)
        .all()
    )
    if not pendencias:
        return []

    pendencia_ids = [p.id for p in pendencias]
    linhas_pagas = (
        db.query(models.Movimentacao.pendencia_id, models.Movimentacao.pendencia_referencia)
        .filter(models.Movimentacao.pendencia_id.in_(pendencia_ids))
        .all()
    )
    pagos_por_pendencia: Dict[uuid.UUID, set] = {}
    for pendencia_id, referencia in linhas_pagas:
        pagos_por_pendencia.setdefault(pendencia_id, set()).add(referencia)

    hoje = date.today()
    resultado = []
    for pendencia in pendencias:
        ciclos = calcular_ciclos_pendentes(pendencia, pagos_por_pendencia.get(pendencia.id, set()), hoje)
        resultado.append({"pendencia": pendencia, "ciclos": ciclos})
    return resultado


def ciclos_de_uma_pendencia(db: Session, pendencia: models.Pendencia) -> List[dict]:
    """Igual a `listar_pendencias_com_ciclos`, mas pra uma única pendência
    — usado depois de criar/editar, quando não faz sentido buscar todas
    as pendências do usuário só pra montar a resposta de uma."""
    pagos = {
        referencia
        for (referencia,) in db.query(models.Movimentacao.pendencia_referencia)
        .filter(models.Movimentacao.pendencia_id == pendencia.id)
        .all()
    }
    return calcular_ciclos_pendentes(pendencia, pagos)


def ja_foi_pago(db: Session, pendencia_id: uuid.UUID, data_vencimento: date) -> bool:
    """Usado por POST /pendencias/{id}/pagar pra bloquear pagar o mesmo
    ciclo duas vezes — checagem em código, além do índice único parcial
    no banco (que é a garantia final contra corrida)."""
    existe = (
        db.query(models.Movimentacao.id)
        .filter(
            models.Movimentacao.pendencia_id == pendencia_id,
            models.Movimentacao.pendencia_referencia == data_vencimento,
        )
        .first()
    )
    return existe is not None
