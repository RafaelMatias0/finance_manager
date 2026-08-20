"""
API do Gerenciador de Finanças — MVP com autenticação JWT.

O usuario_id não é mais passado manualmente: ele vem do token (Bearer),
via a dependency `obter_usuario_atual`. Cada usuário só enxerga e
manipula os próprios dados.
"""
import uuid
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.security import hash_senha, verificar_senha, criar_access_token, obter_usuario_atual
from app import relatorios as relatorios_service
from app import contas as contas_service
from app import pendencias as pendencias_service
from app import planos as planos_service
from app.scheduler import iniciar_scheduler, parar_scheduler

app = FastAPI(title="Gerenciador de Finanças", version="0.4.0")

# CORS liberado para desenvolvimento local (o front roda em outra origem/porta).
# Em produção, troque allow_origins=["*"] pela URL real do front.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    iniciar_scheduler()


@app.on_event("shutdown")
def _shutdown():
    parar_scheduler()


# ---------- Autenticação ----------

@app.post("/auth/login", response_model=schemas.Token, tags=["auth"])
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login OAuth2 padrão: username = email, password = senha.
    Usado tanto por clientes normais quanto pelo botão 'Authorize' do Swagger."""
    usuario = db.query(models.Usuario).filter(models.Usuario.email == form.username).first()
    if not usuario or not verificar_senha(form.password, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = criar_access_token(usuario.id)
    return schemas.Token(access_token=token)


# ---------- Usuário ----------

@app.post("/usuarios", response_model=schemas.UsuarioOut, status_code=status.HTTP_201_CREATED, tags=["usuarios"])
def criar_usuario(dados: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    """Cadastro é público (sem autenticação) — é assim que o usuário passa a existir."""
    if db.query(models.Usuario).filter(models.Usuario.email == dados.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email já cadastrado")

    usuario = models.Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@app.get("/usuarios/me", response_model=schemas.UsuarioOut, tags=["usuarios"])
def meu_usuario(usuario_atual: models.Usuario = Depends(obter_usuario_atual)):
    return usuario_atual


@app.patch("/usuarios/me", response_model=schemas.UsuarioOut, tags=["usuarios"])
def atualizar_meu_usuario(
    dados: schemas.UsuarioUpdate,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    """Só o nome é editável (ver schemas.UsuarioUpdate) — email é a
    identidade de login e nunca muda por aqui."""
    campos = dados.model_dump(exclude_unset=True)
    for campo, valor in campos.items():
        setattr(usuario_atual, campo, valor)

    db.commit()
    db.refresh(usuario_atual)
    return usuario_atual


# ---------- Categoria ----------

@app.get("/categorias", response_model=List[schemas.CategoriaOut], tags=["categorias"])
def listar_categorias(
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    """Retorna as categorias padrão (globais) + as criadas pelo usuário logado."""
    return (
        db.query(models.Categoria)
        .filter(
            (models.Categoria.usuario_id.is_(None))
            | (models.Categoria.usuario_id == usuario_atual.id)
        )
        .order_by(models.Categoria.tipo, models.Categoria.nome)
        .all()
    )


@app.post("/categorias", response_model=schemas.CategoriaOut, status_code=status.HTTP_201_CREATED, tags=["categorias"])
def criar_categoria(
    dados: schemas.CategoriaCreate,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    categoria = models.Categoria(**dados.model_dump(), usuario_id=usuario_atual.id)
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return categoria


@app.patch("/categorias/{categoria_id}", response_model=schemas.CategoriaOut, tags=["categorias"])
def editar_categoria(
    categoria_id: uuid.UUID,
    dados: schemas.CategoriaUpdate,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    categoria = db.get(models.Categoria, categoria_id)
    # Categorias globais (usuario_id None) não podem ser editadas por ninguém
    # via API — e categoria de outro usuário nem deveria "existir" do ponto
    # de vista de quem está pedindo (por isso 404, não 403).
    if not categoria or categoria.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(categoria, campo, valor)

    db.commit()
    db.refresh(categoria)
    return categoria


# ---------- Conta ----------

def _validar_conta_do_usuario(db: Session, conta_id: uuid.UUID, usuario_id: uuid.UUID) -> models.Conta:
    """Confere que a conta existe e pertence ao usuário logado. Diferente
    de categoria, conta não tem conceito de "global" — é sempre do
    usuário, então qualquer conta de outro usuário simplesmente não
    "existe" do ponto de vista de quem está pedindo (404)."""
    conta = db.get(models.Conta, conta_id)
    if not conta or conta.usuario_id != usuario_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada")
    return conta


@app.get("/contas", response_model=List[schemas.ContaOut], tags=["contas"])
def listar_contas(
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    contas = (
        db.query(models.Conta)
        .filter(models.Conta.usuario_id == usuario_atual.id)
        .order_by(models.Conta.criado_em)
        .all()
    )
    saldos = contas_service.calcular_saldos_contas(db, contas)
    return [
        schemas.ContaOut(
            id=c.id,
            nome_banco=c.nome_banco,
            apelido=c.apelido,
            saldo_inicial=c.saldo_inicial,
            saldo_atual=saldos.get(c.id, c.saldo_inicial),
            criado_em=c.criado_em,
        )
        for c in contas
    ]


@app.post("/contas", response_model=schemas.ContaOut, status_code=status.HTTP_201_CREATED, tags=["contas"])
def criar_conta(
    dados: schemas.ContaCreate,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    conta = models.Conta(**dados.model_dump(), usuario_id=usuario_atual.id)
    db.add(conta)
    db.commit()
    db.refresh(conta)
    return schemas.ContaOut(
        id=conta.id,
        nome_banco=conta.nome_banco,
        apelido=conta.apelido,
        saldo_inicial=conta.saldo_inicial,
        saldo_atual=conta.saldo_inicial,
        criado_em=conta.criado_em,
    )


@app.patch("/contas/{conta_id}", response_model=schemas.ContaOut, tags=["contas"])
def editar_conta(
    conta_id: uuid.UUID,
    dados: schemas.ContaUpdate,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    conta = _validar_conta_do_usuario(db, conta_id, usuario_atual.id)

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(conta, campo, valor)

    db.commit()
    db.refresh(conta)
    saldo_atual = contas_service.calcular_saldo_conta(db, conta)
    return schemas.ContaOut(
        id=conta.id,
        nome_banco=conta.nome_banco,
        apelido=conta.apelido,
        saldo_inicial=conta.saldo_inicial,
        saldo_atual=saldo_atual,
        criado_em=conta.criado_em,
    )


@app.delete("/contas/{conta_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["contas"])
def apagar_conta(
    conta_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    conta = _validar_conta_do_usuario(db, conta_id, usuario_atual.id)
    db.delete(conta)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Essa conta tem movimentações ou transferências vinculadas e não pode ser apagada.",
        )


# ---------- Movimentação ----------

def _validar_categoria_do_usuario(db: Session, categoria_id: uuid.UUID, usuario_id: uuid.UUID) -> models.Categoria:
    """Confere que a categoria existe e pode ser usada por esse usuário
    (é global ou é dele mesmo). Usado tanto no create quanto no update."""
    categoria = db.get(models.Categoria, categoria_id)
    if not categoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")
    if categoria.usuario_id is not None and categoria.usuario_id != usuario_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Categoria não pertence a esse usuário")
    return categoria


@app.post("/movimentacoes", response_model=schemas.MovimentacaoOut, status_code=status.HTTP_201_CREATED, tags=["movimentacoes"])
def criar_movimentacao(
    dados: schemas.MovimentacaoCreate,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    _validar_categoria_do_usuario(db, dados.categoria_id, usuario_atual.id)
    _validar_conta_do_usuario(db, dados.conta_id, usuario_atual.id)

    movimentacao = models.Movimentacao(**dados.model_dump(), usuario_id=usuario_atual.id)
    db.add(movimentacao)
    db.commit()
    db.refresh(movimentacao)
    return movimentacao


@app.get("/movimentacoes", response_model=schemas.MovimentacaoListOut, tags=["movimentacoes"])
def listar_historico(
    tipo: Optional[models.TipoMovimentacao] = None,
    categoria_id: Optional[uuid.UUID] = None,
    conta_id: Optional[uuid.UUID] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ordenar_por: schemas.OrdenarPor = schemas.OrdenarPor.DATA,
    ordem: schemas.OrdemDirecao = schemas.OrdemDirecao.DESC,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    """Histórico de movimentações do usuário logado, com filtros, paginação e ordenação."""
    query = (
        db.query(models.Movimentacao)
        .join(models.Categoria)
        .filter(models.Movimentacao.usuario_id == usuario_atual.id)
    )
    if tipo:
        query = query.filter(models.Categoria.tipo == tipo)
    if categoria_id:
        query = query.filter(models.Movimentacao.categoria_id == categoria_id)
    if conta_id:
        query = query.filter(models.Movimentacao.conta_id == conta_id)
    if data_inicio:
        query = query.filter(models.Movimentacao.data >= data_inicio)
    if data_fim:
        query = query.filter(models.Movimentacao.data <= data_fim)

    total = query.count()

    coluna = getattr(models.Movimentacao, ordenar_por.value)
    coluna_ordenada = coluna.desc() if ordem == schemas.OrdemDirecao.DESC else coluna.asc()
    itens = query.order_by(coluna_ordenada).offset(skip).limit(limit).all()

    return schemas.MovimentacaoListOut(total=total, skip=skip, limit=limit, itens=itens)


@app.patch("/movimentacoes/{movimentacao_id}", response_model=schemas.MovimentacaoOut, tags=["movimentacoes"])
def atualizar_movimentacao(
    movimentacao_id: uuid.UUID,
    dados: schemas.MovimentacaoUpdate,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    movimentacao = db.get(models.Movimentacao, movimentacao_id)
    if not movimentacao or movimentacao.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movimentação não encontrada")

    campos = dados.model_dump(exclude_unset=True)

    if "categoria_id" in campos:
        _validar_categoria_do_usuario(db, campos["categoria_id"], usuario_atual.id)
    if "conta_id" in campos:
        _validar_conta_do_usuario(db, campos["conta_id"], usuario_atual.id)

    for campo, valor in campos.items():
        setattr(movimentacao, campo, valor)

    db.commit()
    db.refresh(movimentacao)
    return movimentacao


@app.delete("/movimentacoes/{movimentacao_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["movimentacoes"])
def apagar_movimentacao(
    movimentacao_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    movimentacao = db.get(models.Movimentacao, movimentacao_id)
    if not movimentacao or movimentacao.usuario_id != usuario_atual.id:
        # Mesmo erro (404) para os dois casos: não vazamos se o id existe
        # mas pertence a outro usuário (senão daria pra "escanear" ids alheios).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movimentação não encontrada")
    db.delete(movimentacao)
    db.commit()


# ---------- Transferência ----------

@app.get("/transferencias", response_model=List[schemas.TransferenciaOut], tags=["transferencias"])
def listar_transferencias(
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    return (
        db.query(models.Transferencia)
        .filter(models.Transferencia.usuario_id == usuario_atual.id)
        .order_by(models.Transferencia.data.desc(), models.Transferencia.criado_em.desc())
        .all()
    )


@app.post("/transferencias", response_model=schemas.TransferenciaOut, status_code=status.HTTP_201_CREATED, tags=["transferencias"])
def criar_transferencia(
    dados: schemas.TransferenciaCreate,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    if dados.conta_origem_id == dados.conta_destino_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Escolha duas contas diferentes")

    _validar_conta_do_usuario(db, dados.conta_origem_id, usuario_atual.id)
    _validar_conta_do_usuario(db, dados.conta_destino_id, usuario_atual.id)

    transferencia = models.Transferencia(**dados.model_dump(), usuario_id=usuario_atual.id)
    db.add(transferencia)
    db.commit()
    db.refresh(transferencia)
    return transferencia


# ---------- Pendência ----------

def _pendencia_out(pendencia: models.Pendencia, ciclos: list) -> schemas.PendenciaOut:
    return schemas.PendenciaOut(
        id=pendencia.id,
        usuario_id=pendencia.usuario_id,
        descricao=pendencia.descricao,
        valor=pendencia.valor,
        categoria_id=pendencia.categoria_id,
        conta_id=pendencia.conta_id,
        recorrente=pendencia.recorrente,
        dia_vencimento=pendencia.dia_vencimento,
        data_vencimento=pendencia.data_vencimento,
        ativa=pendencia.ativa,
        criado_em=pendencia.criado_em,
        ciclos=ciclos,
    )


@app.get("/pendencias", response_model=List[schemas.PendenciaOut], tags=["pendencias"])
def listar_pendencias(
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    """Pendências do usuário logado (recorrentes e avulsas), cada uma já
    com `ciclos`: os vencimentos ainda sem pagamento (status "atrasada"
    ou "a_vencer"). Pago/pendente nunca é guardado — é sempre calculado a
    partir das Movimentações vinculadas (ver app/pendencias.py)."""
    itens = pendencias_service.listar_pendencias_com_ciclos(db, usuario_atual.id)
    return [_pendencia_out(item["pendencia"], item["ciclos"]) for item in itens]


@app.post("/pendencias", response_model=schemas.PendenciaOut, status_code=status.HTTP_201_CREATED, tags=["pendencias"])
def criar_pendencia(
    dados: schemas.PendenciaCreate,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    _validar_categoria_do_usuario(db, dados.categoria_id, usuario_atual.id)
    if dados.conta_id:
        _validar_conta_do_usuario(db, dados.conta_id, usuario_atual.id)

    pendencia = models.Pendencia(**dados.model_dump(), usuario_id=usuario_atual.id)
    db.add(pendencia)
    db.commit()
    db.refresh(pendencia)
    ciclos = pendencias_service.ciclos_de_uma_pendencia(db, pendencia)
    return _pendencia_out(pendencia, ciclos)


@app.patch("/pendencias/{pendencia_id}", response_model=schemas.PendenciaOut, tags=["pendencias"])
def editar_pendencia(
    pendencia_id: uuid.UUID,
    dados: schemas.PendenciaUpdate,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    pendencia = db.get(models.Pendencia, pendencia_id)
    if not pendencia or pendencia.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pendência não encontrada")

    campos = dados.model_dump(exclude_unset=True)
    if "categoria_id" in campos:
        _validar_categoria_do_usuario(db, campos["categoria_id"], usuario_atual.id)
    if campos.get("conta_id") is not None:
        _validar_conta_do_usuario(db, campos["conta_id"], usuario_atual.id)

    for campo, valor in campos.items():
        setattr(pendencia, campo, valor)

    db.commit()
    db.refresh(pendencia)
    ciclos = pendencias_service.ciclos_de_uma_pendencia(db, pendencia)
    return _pendencia_out(pendencia, ciclos)


@app.delete("/pendencias/{pendencia_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["pendencias"])
def apagar_pendencia(
    pendencia_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    pendencia = db.get(models.Pendencia, pendencia_id)
    if not pendencia or pendencia.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pendência não encontrada")
    db.delete(pendencia)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Essa pendência já tem pagamentos vinculados e não pode ser apagada — pause em vez de apagar (PATCH ativa=false).",
        )


@app.post("/pendencias/{pendencia_id}/pagar", response_model=schemas.MovimentacaoOut, status_code=status.HTTP_201_CREATED, tags=["pendencias"])
def pagar_pendencia(
    pendencia_id: uuid.UUID,
    dados: schemas.PendenciaPagarRequest,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    """Marca um vencimento (ciclo) da pendência como pago — na prática,
    cria a Movimentação de verdade que o quita, vinculada via
    pendencia_id/pendencia_referencia. Não existe "desmarcar como pago":
    pra isso, apague a Movimentação gerada (mesma rota de sempre)."""
    pendencia = db.get(models.Pendencia, pendencia_id)
    if not pendencia or pendencia.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pendência não encontrada")

    _validar_conta_do_usuario(db, dados.conta_id, usuario_atual.id)

    if pendencias_service.ja_foi_pago(db, pendencia_id, dados.data_vencimento):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esse vencimento já foi pago")

    ciclos_pendentes = {c["data_vencimento"] for c in pendencias_service.ciclos_de_uma_pendencia(db, pendencia)}
    if dados.data_vencimento not in ciclos_pendentes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Essa data não corresponde a um vencimento pendente dessa pendência",
        )

    # Se essa pendência foi criada por um Plano de "quitar dívida por
    # parcelas" (ver POST /planos), a Movimentação também grava plano_id
    # — rastreabilidade pro lado de Planos, sem duplicar a lógica de
    # pagamento (continua sendo a mesma pendência normal).
    plano_vinculado = db.query(models.Plano).filter(models.Plano.pendencia_id == pendencia_id).first()

    movimentacao = models.Movimentacao(
        valor=dados.valor if dados.valor is not None else pendencia.valor,
        descricao=dados.descricao or pendencia.descricao,
        data=dados.data,
        categoria_id=pendencia.categoria_id,
        conta_id=dados.conta_id,
        usuario_id=usuario_atual.id,
        pendencia_id=pendencia.id,
        pendencia_referencia=dados.data_vencimento,
        plano_id=plano_vinculado.id if plano_vinculado else None,
    )
    db.add(movimentacao)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esse vencimento já foi pago")
    db.refresh(movimentacao)
    return movimentacao


# ---------- Plano ----------

def _plano_out(plano: models.Plano, progresso: dict) -> schemas.PlanoOut:
    return schemas.PlanoOut(
        id=plano.id,
        usuario_id=plano.usuario_id,
        nome=plano.nome,
        tipo=plano.tipo,
        conta_id=plano.conta_id,
        mes_inicio=plano.mes_inicio,
        ativo=plano.ativo,
        guardar_modo=plano.guardar_modo,
        criterio_reducao=plano.criterio_reducao,
        alvo_percentual=plano.alvo_percentual,
        alvo_valor_reducao=plano.alvo_valor_reducao,
        divida_modo=plano.divida_modo,
        pendencia_id=plano.pendencia_id,
        valor_alvo=plano.valor_alvo,
        data_prazo=plano.data_prazo,
        categoria_id=plano.categoria_id,
        criado_em=plano.criado_em,
        progresso=progresso,
    )


@app.get("/planos", response_model=List[schemas.PlanoOut], tags=["planos"])
def listar_planos(
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    """Planos do usuário logado (guardar dinheiro / quitar dívida), cada
    um já com `progresso` calculado — nunca guardado, sempre derivado da
    atividade financeira real (ver app/planos.py)."""
    itens = planos_service.listar_planos_com_progresso(db, usuario_atual.id)
    return [_plano_out(item["plano"], item["progresso"]) for item in itens]


@app.post("/planos", response_model=schemas.PlanoOut, status_code=status.HTTP_201_CREATED, tags=["planos"])
def criar_plano(
    dados: schemas.PlanoCreate,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    _validar_conta_do_usuario(db, dados.conta_id, usuario_atual.id)
    if dados.categoria_id:
        _validar_categoria_do_usuario(db, dados.categoria_id, usuario_atual.id)

    campos = dados.model_dump(exclude={"numero_parcelas", "dia_vencimento"})

    pendencia_id = None
    if dados.tipo == models.TipoPlano.QUITAR_DIVIDA and dados.divida_modo == models.DividaModo.PARCELAS:
        # Modo parcelas reaproveita a Pendência recorrente (Fase 3) por
        # baixo, com numero_parcelas travando o fim — sem duplicar lógica
        # de ciclos/pagamento. `valor_alvo` na requisição, nesse modo
        # específico, é o valor DE CADA parcela; o total (guardado no
        # Plano) é calculado aqui.
        pendencia = models.Pendencia(
            usuario_id=usuario_atual.id,
            descricao=dados.nome,
            valor=dados.valor_alvo,
            categoria_id=dados.categoria_id,
            conta_id=dados.conta_id,
            recorrente=True,
            dia_vencimento=dados.dia_vencimento,
            numero_parcelas=dados.numero_parcelas,
        )
        db.add(pendencia)
        db.flush()  # pega o id gerado sem fechar a transação
        pendencia_id = pendencia.id
        campos["valor_alvo"] = dados.valor_alvo * dados.numero_parcelas

    plano = models.Plano(**campos, usuario_id=usuario_atual.id, pendencia_id=pendencia_id)
    db.add(plano)
    db.commit()
    db.refresh(plano)
    progresso = planos_service.progresso_do_plano(db, plano)
    return _plano_out(plano, progresso)


@app.patch("/planos/{plano_id}", response_model=schemas.PlanoOut, tags=["planos"])
def editar_plano(
    plano_id: uuid.UUID,
    dados: schemas.PlanoUpdate,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    plano = db.get(models.Plano, plano_id)
    if not plano or plano.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano não encontrado")

    campos = dados.model_dump(exclude_unset=True)
    if "conta_id" in campos:
        _validar_conta_do_usuario(db, campos["conta_id"], usuario_atual.id)
    if campos.get("categoria_id") is not None:
        _validar_categoria_do_usuario(db, campos["categoria_id"], usuario_atual.id)

    for campo, valor in campos.items():
        setattr(plano, campo, valor)

    db.commit()
    db.refresh(plano)
    progresso = planos_service.progresso_do_plano(db, plano)
    return _plano_out(plano, progresso)


@app.delete("/planos/{plano_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["planos"])
def apagar_plano(
    plano_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    plano = db.get(models.Plano, plano_id)
    if not plano or plano.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano não encontrado")

    pendencia_vinculada_id = plano.pendencia_id
    db.delete(plano)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esse plano já tem pagamentos vinculados e não pode ser apagado — pause em vez de apagar (PATCH ativo=false).",
        )

    # Modo parcelas: se o delete acima não foi bloqueado, o plano não
    # tinha pagamento — logo a Pendencia que ele criou por baixo também
    # não tem. Some junto, em vez de ficar órfã na página de Pendências.
    if pendencia_vinculada_id:
        pendencia = db.get(models.Pendencia, pendencia_vinculada_id)
        if pendencia:
            db.delete(pendencia)
            db.commit()


@app.post("/planos/{plano_id}/aportar", response_model=schemas.MovimentacaoOut, status_code=status.HTTP_201_CREATED, tags=["planos"])
def aportar_plano(
    plano_id: uuid.UUID,
    dados: schemas.PlanoAportarRequest,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    """Registra um pagamento pra um plano de quitar dívida no modo prazo
    (pagamentos avulsos, sem ciclo fixo). Parcelas não passam por aqui —
    usam POST /pendencias/{id}/pagar, com o pendencia_id do plano. Guardar
    dinheiro não tem rota de aporte nenhuma: não gera movimentação, o
    progresso vem da atividade financeira normal."""
    plano = db.get(models.Plano, plano_id)
    if not plano or plano.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano não encontrado")
    if plano.tipo != models.TipoPlano.QUITAR_DIVIDA or plano.divida_modo != models.DividaModo.PRAZO:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Só planos de quitar dívida no modo prazo aceitam aporte por aqui (parcelas usam POST /pendencias/{id}/pagar)",
        )

    movimentacao = models.Movimentacao(
        valor=dados.valor,
        descricao=dados.descricao or plano.nome,
        data=dados.data,
        categoria_id=plano.categoria_id,
        conta_id=plano.conta_id,
        usuario_id=usuario_atual.id,
        plano_id=plano.id,
    )
    db.add(movimentacao)
    db.commit()
    db.refresh(movimentacao)
    return movimentacao


# ---------- Saldo ----------

@app.get("/saldo", response_model=schemas.SaldoOut, tags=["saldo"])
def consultar_saldo(
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    """Saldo geral do usuário: soma do saldo inicial de todas as contas +
    receitas - despesas. Transferências não entram aqui porque são soma
    zero entre as próprias contas do usuário. Para o detalhamento por
    conta, use GET /contas."""
    resultado = (
        db.query(models.Categoria.tipo, func.coalesce(func.sum(models.Movimentacao.valor), 0))
        .join(models.Movimentacao, models.Movimentacao.categoria_id == models.Categoria.id)
        .filter(models.Movimentacao.usuario_id == usuario_atual.id)
        .group_by(models.Categoria.tipo)
        .all()
    )
    totais = {tipo: total for tipo, total in resultado}
    total_receitas = totais.get(models.TipoMovimentacao.RECEITA, 0)
    total_despesas = totais.get(models.TipoMovimentacao.DESPESA, 0)

    soma_saldos_iniciais = (
        db.query(func.coalesce(func.sum(models.Conta.saldo_inicial), 0))
        .filter(models.Conta.usuario_id == usuario_atual.id)
        .scalar()
    )

    return schemas.SaldoOut(
        usuario_id=usuario_atual.id,
        total_receitas=total_receitas,
        total_despesas=total_despesas,
        saldo=soma_saldos_iniciais + total_receitas - total_despesas,
    )


# ---------- Relatórios ----------

@app.get("/relatorios/personalizado", tags=["relatorios"])
def relatorio_personalizado(
    data_inicio: date,
    data_fim: date,
    tipo: Optional[models.TipoMovimentacao] = None,
    categoria_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    if data_fim < data_inicio:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="data_fim não pode ser anterior a data_inicio")
    return relatorios_service.gerar_relatorio_basico(db, usuario_atual.id, data_inicio, data_fim, tipo, categoria_id)


@app.get("/relatorios/comparativo", tags=["relatorios"])
def relatorio_comparativo(
    data_inicio: date,
    data_fim: date,
    categoria_id_1: uuid.UUID,
    categoria_id_2: uuid.UUID,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    if data_fim < data_inicio:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="data_fim não pode ser anterior a data_inicio")
    if categoria_id_1 == categoria_id_2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Escolha duas categorias diferentes")

    for cat_id in (categoria_id_1, categoria_id_2):
        categoria = db.get(models.Categoria, cat_id)
        if not categoria:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")
        if categoria.usuario_id is not None and categoria.usuario_id != usuario_atual.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Categoria não pertence a esse usuário")

    return relatorios_service.gerar_relatorio_comparativo(
        db, usuario_atual.id, data_inicio, data_fim, categoria_id_1, categoria_id_2
    )


@app.get("/relatorios/por-categoria", tags=["relatorios"])
def relatorio_por_categoria(
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    tipo: Optional[models.TipoMovimentacao] = None,
    meses_recentes: int = Query(default=0, ge=0, le=24),
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    """Agregado por categoria (total, %, mín/média/máx e, opcionalmente,
    quebra por mês). Sem data_inicio/data_fim, considera todo o histórico
    do usuário logado. Usada tanto pelo gráfico de gastos do mês (com
    período + tipo=despesa) quanto pela tabela de categorias de Controle
    (sem período, com meses_recentes) na página Controle."""
    if data_inicio and data_fim and data_fim < data_inicio:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="data_fim não pode ser anterior a data_inicio")
    return relatorios_service.resumo_por_categoria(db, usuario_atual.id, data_inicio, data_fim, tipo, meses_recentes)


@app.get("/relatorios/saldo-diario-por-conta", tags=["relatorios"])
def relatorio_saldo_diario_por_conta(
    dias: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    """Série diária de saldo de cada conta do usuário logado, nos últimos
    `dias` dias (hoje incluso) — usada pelo gráfico de linha "balanço
    diário por conta" em destaque em Controle."""
    contas = (
        db.query(models.Conta)
        .filter(models.Conta.usuario_id == usuario_atual.id)
        .order_by(models.Conta.criado_em)
        .all()
    )
    return contas_service.calcular_serie_saldo_diaria(db, usuario_atual.id, contas, dias)


@app.get("/relatorios", response_model=List[schemas.RelatorioOut], tags=["relatorios"])
def listar_relatorios_automaticos(
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    return (
        db.query(models.Relatorio)
        .filter(models.Relatorio.usuario_id == usuario_atual.id)
        .order_by(models.Relatorio.criado_em.desc())
        .all()
    )


@app.get("/relatorios/{relatorio_id}", response_model=schemas.RelatorioOut, tags=["relatorios"])
def obter_relatorio_automatico(
    relatorio_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    relatorio = db.get(models.Relatorio, relatorio_id)
    if not relatorio or relatorio.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relatório não encontrado")
    return relatorio


@app.post("/relatorios/gerar-agora", response_model=schemas.RelatorioOut, tags=["relatorios"])
def gerar_relatorio_automatico_agora(
    tipo: models.TipoRelatorio,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    """Dispara na hora a geração de um relatório automático (semanal ou
    mensal) para o período que já teria fechado, sem esperar o
    agendamento. Útil para testar/demonstrar a funcionalidade sem esperar
    a próxima segunda-feira 01:00 ou o próximo dia 1."""
    return relatorios_service.gerar_e_salvar_relatorio_automatico(db, usuario_atual.id, tipo)