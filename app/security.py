"""
Segurança: hash de senha (bcrypt) e autenticação via JWT.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app import models

# ---------- Senha ----------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha_texto_puro: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha_texto_puro, senha_hash)


# ---------- JWT ----------

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY não definida. Gere uma com: "
        "python -c \"import secrets; print(secrets.token_hex(32))\" e coloque no .env"
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def criar_access_token(usuario_id: uuid.UUID) -> str:
    expira_em = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(usuario_id), "exp": expira_em}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def obter_usuario_atual(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.Usuario:
    """Dependency do FastAPI: decodifica o token e retorna o Usuario logado.
    Lança 401 se o token for inválido/expirado ou o usuário não existir mais."""
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id_str = payload.get("sub")
        if usuario_id_str is None:
            raise credenciais_invalidas
        usuario_id = uuid.UUID(usuario_id_str)
    except (JWTError, ValueError):
        raise credenciais_invalidas

    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None:
        raise credenciais_invalidas
    return usuario
