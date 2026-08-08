"""
Scheduler in-process (roda dentro do próprio processo do uvicorn) para os
relatórios automáticos:
- Semanal: toda segunda-feira às 01:00, cobrindo a semana (seg-dom) que
  acabou de fechar.
- Mensal: todo dia 1 às 01:00, cobrindo o mês que acabou de fechar.

Gera um relatório por usuário cadastrado. Isso é adequado para um projeto
de portfólio (roda no mesmo processo, sem infra extra); em produção com
muitos usuários, isso normalmente viraria um worker/fila separado.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app import models
from app.relatorios import gerar_e_salvar_relatorio_automatico

logger = logging.getLogger("scheduler")


def _gerar_para_todos_usuarios(tipo: models.TipoRelatorio):
    db = SessionLocal()
    try:
        usuarios = db.query(models.Usuario).all()
        for usuario in usuarios:
            try:
                gerar_e_salvar_relatorio_automatico(db, usuario.id, tipo)
            except Exception:
                logger.exception("Falha ao gerar relatório %s para usuário %s", tipo, usuario.id)
    finally:
        db.close()


def job_relatorio_semanal():
    _gerar_para_todos_usuarios(models.TipoRelatorio.AUTOMATICO_SEMANAL)


def job_relatorio_mensal():
    _gerar_para_todos_usuarios(models.TipoRelatorio.AUTOMATICO_MENSAL)


_scheduler = None


def iniciar_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    _scheduler.add_job(
        job_relatorio_semanal,
        CronTrigger(day_of_week="mon", hour=1, minute=0),
        id="relatorio_semanal",
        replace_existing=True,
    )
    _scheduler.add_job(
        job_relatorio_mensal,
        CronTrigger(day="1", hour=1, minute=0),
        id="relatorio_mensal",
        replace_existing=True,
    )
    _scheduler.start()
    return _scheduler


def parar_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
