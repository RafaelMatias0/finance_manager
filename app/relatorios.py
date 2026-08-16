"""
Lógica de geração dos relatórios. Separado do main.py porque é usado tanto
pelas rotas sob demanda (personalizado/comparativo) quanto pelo scheduler
(automático semanal/mensal) — mesma lógica, dois chamadores.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


def _decimal_para_float(valor) -> float:
    """JSONB não guarda Decimal nativamente — convertemos pra float na hora
    de persistir/serializar. Perda de precisão irrelevante para exibição
    em relatório (não é usado para novos cálculos financeiros depois)."""
    return float(valor) if valor is not None else 0.0


def _query_periodo(db: Session, usuario_id: uuid.UUID, data_inicio: date, data_fim: date):
    return (
        db.query(models.Movimentacao)
        .join(models.Categoria)
        .filter(
            models.Movimentacao.usuario_id == usuario_id,
            models.Movimentacao.data >= data_inicio,
            models.Movimentacao.data <= data_fim,
        )
    )


def _serializar_movimentacao(mov: models.Movimentacao) -> dict:
    return {
        "id": str(mov.id),
        "valor": _decimal_para_float(mov.valor),
        "descricao": mov.descricao,
        "data": mov.data.isoformat(),
        "categoria_id": str(mov.categoria_id),
        "categoria_nome": mov.categoria.nome,
        "categoria_tipo": mov.categoria.tipo.value,
    }


def _grafico_diario(movimentacoes: list[models.Movimentacao], data_inicio: date, data_fim: date) -> list[dict]:
    """Um ponto por dia no intervalo (mesmo os dias sem movimentação, com 0),
    para o gráfico não ter buracos."""
    por_dia = {}
    dia = data_inicio
    while dia <= data_fim:
        por_dia[dia] = {"data": dia.isoformat(), "total_receitas": 0.0, "total_despesas": 0.0}
        dia += timedelta(days=1)

    for mov in movimentacoes:
        chave = mov.data
        if chave not in por_dia:
            continue  # segurança; não deveria acontecer, já filtramos por período
        if mov.categoria.tipo == models.TipoMovimentacao.RECEITA:
            por_dia[chave]["total_receitas"] += _decimal_para_float(mov.valor)
        else:
            por_dia[chave]["total_despesas"] += _decimal_para_float(mov.valor)

    return list(por_dia.values())


def gerar_relatorio_basico(
    db: Session,
    usuario_id: uuid.UUID,
    data_inicio: date,
    data_fim: date,
    tipo: Optional[models.TipoMovimentacao] = None,
    categoria_id: Optional[uuid.UUID] = None,
) -> dict:
    """Relatório personalizado (ou base do automático): histórico, saldo do
    período, gráfico diário, e opcionalmente a participação de uma
    categoria dentro do total do MESMO TIPO dela no período."""
    query = _query_periodo(db, usuario_id, data_inicio, data_fim)
    if tipo:
        query = query.filter(models.Categoria.tipo == tipo)
    if categoria_id:
        query = query.filter(models.Movimentacao.categoria_id == categoria_id)

    movimentacoes = query.order_by(models.Movimentacao.data).all()

    total_receitas = sum(
        (m.valor for m in movimentacoes if m.categoria.tipo == models.TipoMovimentacao.RECEITA), Decimal("0")
    )
    total_despesas = sum(
        (m.valor for m in movimentacoes if m.categoria.tipo == models.TipoMovimentacao.DESPESA), Decimal("0")
    )

    resultado = {
        "data_inicio": data_inicio.isoformat(),
        "data_fim": data_fim.isoformat(),
        "filtro_tipo": tipo.value if tipo else None,
        "filtro_categoria_id": str(categoria_id) if categoria_id else None,
        "historico": [_serializar_movimentacao(m) for m in movimentacoes],
        "saldo": {
            "total_receitas": _decimal_para_float(total_receitas),
            "total_despesas": _decimal_para_float(total_despesas),
            "saldo": _decimal_para_float(total_receitas - total_despesas),
        },
        "grafico_diario": _grafico_diario(movimentacoes, data_inicio, data_fim),
        "grafico_categoria": None,
    }

    # Participação da categoria selecionada dentro do total do MESMO TIPO
    # dela no período (ex: Alimentação vs. total de despesas do período) —
    # não depende do filtro `tipo` acima, calcula sobre o período inteiro,
    # senão selecionar uma categoria de despesa com filtro tipo=receita
    # daria sempre 0/0.
    if categoria_id:
        categoria = db.get(models.Categoria, categoria_id)
        if categoria:
            todas_do_periodo = _query_periodo(db, usuario_id, data_inicio, data_fim).filter(
                models.Categoria.tipo == categoria.tipo
            )
            total_mesmo_tipo = sum((m.valor for m in todas_do_periodo), Decimal("0"))
            total_categoria = sum(
                (m.valor for m in todas_do_periodo if m.categoria_id == categoria_id), Decimal("0")
            )
            percentual = float(total_categoria / total_mesmo_tipo * 100) if total_mesmo_tipo > 0 else 0.0
            resultado["grafico_categoria"] = {
                "categoria_id": str(categoria_id),
                "categoria_nome": categoria.nome,
                "categoria_tipo": categoria.tipo.value,
                "total_categoria": _decimal_para_float(total_categoria),
                "total_mesmo_tipo_periodo": _decimal_para_float(total_mesmo_tipo),
                "percentual": round(percentual, 2),
            }

    return resultado


def gerar_relatorio_comparativo(
    db: Session,
    usuario_id: uuid.UUID,
    data_inicio: date,
    data_fim: date,
    categoria_id_1: uuid.UUID,
    categoria_id_2: uuid.UUID,
) -> dict:
    cat1 = db.get(models.Categoria, categoria_id_1)
    cat2 = db.get(models.Categoria, categoria_id_2)
    if not cat1 or not cat2:
        raise ValueError("Categoria não encontrada")

    query = _query_periodo(db, usuario_id, data_inicio, data_fim).filter(
        models.Movimentacao.categoria_id.in_([categoria_id_1, categoria_id_2])
    )
    movimentacoes = query.order_by(models.Movimentacao.data).all()

    movs_cat1 = [m for m in movimentacoes if m.categoria_id == categoria_id_1]
    movs_cat2 = [m for m in movimentacoes if m.categoria_id == categoria_id_2]
    total_cat1 = sum((m.valor for m in movs_cat1), Decimal("0"))
    total_cat2 = sum((m.valor for m in movs_cat2), Decimal("0"))

    # Gráfico de linhas: total de cada categoria por dia (com dias vazios = 0)
    por_dia = {}
    dia = data_inicio
    while dia <= data_fim:
        por_dia[dia] = {"data": dia.isoformat(), "categoria_1_total": 0.0, "categoria_2_total": 0.0}
        dia += timedelta(days=1)
    for m in movs_cat1:
        if m.data in por_dia:
            por_dia[m.data]["categoria_1_total"] += _decimal_para_float(m.valor)
    for m in movs_cat2:
        if m.data in por_dia:
            por_dia[m.data]["categoria_2_total"] += _decimal_para_float(m.valor)

    resultado = {
        "data_inicio": data_inicio.isoformat(),
        "data_fim": data_fim.isoformat(),
        "categoria_1": {
            "id": str(cat1.id), "nome": cat1.nome, "tipo": cat1.tipo.value,
            "total": _decimal_para_float(total_cat1),
        },
        "categoria_2": {
            "id": str(cat2.id), "nome": cat2.nome, "tipo": cat2.tipo.value,
            "total": _decimal_para_float(total_cat2),
        },
        "historico": [_serializar_movimentacao(m) for m in movimentacoes],
        "grafico_diario_comparativo": list(por_dia.values()),
    }

    if cat1.tipo != cat2.tipo:
        # Tipos diferentes (uma receita, uma despesa): saldo = diferença.
        # Convenção: receita entra positiva, despesa entra negativa —
        # então "saldo_diferenca" já sai com o sinal certo (ex: sobrou
        # dinheiro dessa receita depois de cobrir essa despesa = positivo).
        valor_receita = total_cat1 if cat1.tipo == models.TipoMovimentacao.RECEITA else total_cat2
        valor_despesa = total_cat1 if cat1.tipo == models.TipoMovimentacao.DESPESA else total_cat2
        resultado["modo"] = "tipos_diferentes"
        resultado["saldo_diferenca"] = _decimal_para_float(valor_receita - valor_despesa)
    else:
        # Mesmo tipo: soma das duas + participação de cada uma (e das duas
        # somadas) dentro do total daquele tipo no período.
        soma = total_cat1 + total_cat2
        todas_do_tipo = _query_periodo(db, usuario_id, data_inicio, data_fim).filter(
            models.Categoria.tipo == cat1.tipo
        )
        total_do_tipo_periodo = sum((m.valor for m in todas_do_tipo), Decimal("0"))

        def percentual(valor):
            return round(float(valor / total_do_tipo_periodo * 100), 2) if total_do_tipo_periodo > 0 else 0.0

        resultado["modo"] = "mesmo_tipo"
        resultado["tipo_comum"] = cat1.tipo.value
        resultado["saldo_soma"] = _decimal_para_float(soma)
        resultado["total_tipo_periodo"] = _decimal_para_float(total_do_tipo_periodo)
        resultado["grafico_participacao_individual"] = [
            {"categoria": cat1.nome, "percentual": percentual(total_cat1)},
            {"categoria": cat2.nome, "percentual": percentual(total_cat2)},
            {"categoria": "Restante", "percentual": percentual(total_do_tipo_periodo - soma)},
        ]
        resultado["grafico_participacao_combinada"] = [
            {"categoria": f"{cat1.nome} + {cat2.nome}", "percentual": percentual(soma)},
            {"categoria": "Restante", "percentual": percentual(total_do_tipo_periodo - soma)},
        ]

    return resultado


def _mes_menos(referencia: date, n: int) -> date:
    """Primeiro dia do mês, n meses antes do mês de `referencia`."""
    total_meses = referencia.year * 12 + (referencia.month - 1) - n
    ano, mes = divmod(total_meses, 12)
    return date(ano, mes + 1, 1)


def resumo_por_categoria(
    db: Session,
    usuario_id: uuid.UUID,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    tipo: Optional[models.TipoMovimentacao] = None,
    meses_recentes: int = 0,
) -> list[dict]:
    """Agregado por categoria — total, quantidade, mínimo, média e máximo
    das movimentações, mais o percentual de cada categoria dentro do total
    do MESMO TIPO (só entre as categorias retornadas). Sem `data_inicio`/
    `data_fim`, considera todo o histórico do usuário. Se `meses_recentes`
    > 0, anexa a cada categoria o total em cada um dos últimos N meses
    corridos (incluindo o atual).

    Agregação feita em SQL (GROUP BY), não em Python — ao contrário de
    `gerar_relatorio_basico`, aqui o período pode ser "desde sempre", então
    carregar todas as movimentações pra memória não escala (mesmo padrão
    de `calcular_saldos_contas` em app/contas.py)."""
    query = (
        db.query(
            models.Categoria.id,
            models.Categoria.nome,
            models.Categoria.tipo,
            func.sum(models.Movimentacao.valor),
            func.count(models.Movimentacao.id),
            func.min(models.Movimentacao.valor),
            func.avg(models.Movimentacao.valor),
            func.max(models.Movimentacao.valor),
        )
        .join(models.Categoria, models.Movimentacao.categoria_id == models.Categoria.id)
        .filter(models.Movimentacao.usuario_id == usuario_id)
    )
    if data_inicio:
        query = query.filter(models.Movimentacao.data >= data_inicio)
    if data_fim:
        query = query.filter(models.Movimentacao.data <= data_fim)
    if tipo:
        query = query.filter(models.Categoria.tipo == tipo)

    linhas = query.group_by(models.Categoria.id, models.Categoria.nome, models.Categoria.tipo).all()

    totais_por_tipo: dict = {}
    for _, _, cat_tipo, total, *_resto in linhas:
        totais_por_tipo[cat_tipo] = totais_por_tipo.get(cat_tipo, Decimal("0")) + total

    resultado = []
    for cat_id, nome, cat_tipo, total, quantidade, minimo, media, maximo in linhas:
        total_tipo = totais_por_tipo.get(cat_tipo, Decimal("0"))
        percentual = float(total / total_tipo * 100) if total_tipo > 0 else 0.0
        resultado.append({
            "categoria_id": str(cat_id),
            "categoria_nome": nome,
            "categoria_tipo": cat_tipo.value,
            "total": _decimal_para_float(total),
            "percentual": round(percentual, 2),
            "quantidade": quantidade,
            "minimo": _decimal_para_float(minimo),
            "media": _decimal_para_float(media),
            "maximo": _decimal_para_float(maximo),
        })

    if meses_recentes > 0:
        _anexar_totais_mensais(db, usuario_id, resultado, meses_recentes, tipo)

    resultado.sort(key=lambda r: (r["categoria_tipo"], -r["total"]))
    return resultado


def _anexar_totais_mensais(
    db: Session,
    usuario_id: uuid.UUID,
    categorias: list[dict],
    meses_recentes: int,
    tipo: Optional[models.TipoMovimentacao],
) -> None:
    """Preenche `categorias[i]["mensal"]` com o total de cada categoria em
    cada um dos últimos `meses_recentes` meses corridos (do mais antigo pro
    mais recente, incluindo o mês atual). Meses sem movimentação entram
    com total 0 (sem buraco), mesma ideia de `_grafico_diario`."""
    if not categorias:
        return

    hoje = date.today()
    meses = [_mes_menos(hoje, i) for i in range(meses_recentes - 1, -1, -1)]

    query = (
        db.query(
            models.Movimentacao.categoria_id,
            func.date_trunc("month", models.Movimentacao.data),
            func.sum(models.Movimentacao.valor),
        )
        .filter(
            models.Movimentacao.usuario_id == usuario_id,
            models.Movimentacao.data >= meses[0],
        )
    )
    if tipo:
        query = query.join(models.Categoria).filter(models.Categoria.tipo == tipo)

    linhas = query.group_by(
        models.Movimentacao.categoria_id, func.date_trunc("month", models.Movimentacao.data)
    ).all()

    por_categoria_mes = {}
    for cat_id, mes_trunc, total in linhas:
        chave = (str(cat_id), mes_trunc.date().replace(day=1))
        por_categoria_mes[chave] = _decimal_para_float(total)

    for item in categorias:
        item["mensal"] = [
            {"mes": mes.isoformat()[:7], "total": por_categoria_mes.get((item["categoria_id"], mes), 0.0)}
            for mes in meses
        ]


def periodo_semana_anterior(referencia: date) -> tuple[date, date]:
    """Segunda a domingo da semana que terminou antes de `referencia`.
    Rodando numa segunda de manhã, `referencia`=hoje(segunda) → retorna a
    segunda a domingo da semana anterior (a que acabou de fechar)."""
    dias_desde_segunda = referencia.weekday()  # segunda=0
    ultima_segunda = referencia - timedelta(days=dias_desde_segunda)
    inicio_semana_anterior = ultima_segunda - timedelta(days=7)
    fim_semana_anterior = ultima_segunda - timedelta(days=1)
    return inicio_semana_anterior, fim_semana_anterior


def periodo_mes_anterior(referencia: date) -> tuple[date, date]:
    """Primeiro ao último dia do mês anterior a `referencia`. Rodando no
    dia 1 de manhã, retorna o mês que acabou de fechar."""
    primeiro_dia_mes_atual = referencia.replace(day=1)
    fim_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
    inicio_mes_anterior = fim_mes_anterior.replace(day=1)
    return inicio_mes_anterior, fim_mes_anterior


def gerar_e_salvar_relatorio_automatico(
    db: Session, usuario_id: uuid.UUID, tipo: models.TipoRelatorio, referencia: Optional[date] = None
) -> models.Relatorio:
    referencia = referencia or date.today()

    if tipo == models.TipoRelatorio.AUTOMATICO_SEMANAL:
        data_inicio, data_fim = periodo_semana_anterior(referencia)
    else:
        data_inicio, data_fim = periodo_mes_anterior(referencia)

    dados = gerar_relatorio_basico(db, usuario_id, data_inicio, data_fim)

    relatorio = models.Relatorio(
        usuario_id=usuario_id,
        tipo=tipo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        dados=dados,
    )
    db.add(relatorio)
    db.commit()
    db.refresh(relatorio)
    return relatorio
