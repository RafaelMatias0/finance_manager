"""
API do Gerenciador de Finanças — MVP com autenticação JWT.

O usuario_id não é mais passado manualmente: ele vem do token (Bearer),
via a dependency `obter_usuario_atual`. Cada usuário só enxerga e
manipula os próprios dados.
"""
import uuid
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.security import hash_senha, verificar_senha, criar_access_token, obter_usuario_atual

app = FastAPI(title="Gerenciador de Finanças", version="0.3.0")

# CORS liberado para desenvolvimento local (o front roda em outra origem/porta).
# Em produção, troque allow_origins=["*"] pela URL real do front.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
def atualizar_categoria(
    categoria_id: uuid.UUID,
    dados: schemas.CategoriaUpdate,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    categoria = db.get(models.Categoria, categoria_id)
    if not categoria or categoria.usuario_id != usuario_atual.id:
        # Cobre 3 casos com a mesma resposta: não existe, é de outro usuário,
        # ou é uma categoria global (usuario_id=None — ninguém edita a padrão).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(categoria, campo, valor)

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

    categoria.nome = dados.nome
    db.commit()
    db.refresh(categoria)
    return categoria


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

    movimentacao = models.Movimentacao(**dados.model_dump(), usuario_id=usuario_atual.id)
    db.add(movimentacao)
    db.commit()
    db.refresh(movimentacao)
    return movimentacao


@app.patch("/movimentacoes/{movimentacao_id}", response_model=schemas.MovimentacaoOut, tags=["movimentacoes"])
def editar_movimentacao(
    movimentacao_id: uuid.UUID,
    dados: schemas.MovimentacaoUpdate,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
    movimentacao = db.get(models.Movimentacao, movimentacao_id)
    if not movimentacao or movimentacao.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movimentação não encontrada")

    dados_informados = dados.model_dump(exclude_unset=True)
    if "categoria_id" in dados_informados:
        _validar_categoria_do_usuario(db, dados_informados["categoria_id"], usuario_atual.id)

    for campo, valor in dados_informados.items():
        setattr(movimentacao, campo, valor)

    db.commit()
    db.refresh(movimentacao)
    return movimentacao


@app.get("/movimentacoes", response_model=schemas.MovimentacaoListOut, tags=["movimentacoes"])
def listar_historico(
    tipo: Optional[models.TipoMovimentacao] = None,
    categoria_id: Optional[uuid.UUID] = None,
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
        categoria = db.get(models.Categoria, campos["categoria_id"])
        if not categoria:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")
        if categoria.usuario_id is not None and categoria.usuario_id != usuario_atual.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Categoria não pertence a esse usuário")

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


# ---------- Saldo ----------

@app.get("/saldo", response_model=schemas.SaldoOut, tags=["saldo"])
def consultar_saldo(
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(obter_usuario_atual),
):
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

    return schemas.SaldoOut(
        usuario_id=usuario_atual.id,
        total_receitas=total_receitas,
        total_despesas=total_despesas,
        saldo=total_receitas - total_despesas,
    )
