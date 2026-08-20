"""
Testes das rotas de pendências. Mesmo estilo dos outros (test_jwt.py,
test_relatorios.py): roda contra a API real via urllib.

Uma parte (recorrente com vários meses de atraso acumulado) não dá pra
simular só com chamadas HTTP dentro do mesmo minuto — precisaria esperar
meses de verdade pro `criado_em` avançar. Por isso, só nesse caso
específico, o script acessa o banco diretamente (reaproveitando
app.database/app.models, que já são do próprio projeto, não uma
dependência nova) pra "voltar no tempo" o criado_em de uma pendência
recém-criada via API. Todo o resto é HTTP puro, como os demais testes.
"""
import urllib.request
import urllib.error
import json
import time
import uuid
from datetime import date, datetime, timedelta

from app.database import SessionLocal
from app import models

BASE = "http://127.0.0.1:8000"


def call(method, path, body=None, token=None, form=False):
    url = BASE + path
    headers = {}
    data = None
    if body is not None:
        if form:
            data = "&".join(f"{k}={v}" for k, v in body.items()).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw.decode()
    except urllib.error.URLError as e:
        print(f"\nERRO DE CONEXÃO: não consegui falar com {BASE}. A API está rodando?\nDetalhe: {e}")
        raise SystemExit(1)


def mes_atras(n, dia=5):
    """Data no dia fixo `dia` (evita problema de mês curto), n meses antes
    do mês atual — calculado de forma independente da implementação do
    backend, pra servir de conferência real."""
    hoje = date.today()
    total_meses = hoje.year * 12 + (hoje.month - 1) - n
    ano, mes = divmod(total_meses, 12)
    return date(ano, mes + 1, dia)


def backdatar_criado_em(pendencia_id: str, quando: datetime):
    """Só usada no teste de atraso acumulado, pra simular que a pendência
    recorrente existe há alguns meses (ver docstring do arquivo)."""
    db = SessionLocal()
    try:
        pendencia = db.get(models.Pendencia, uuid.UUID(pendencia_id))
        pendencia.criado_em = quando
        db.commit()
    finally:
        db.close()


results = []


def check(label, condition, detail=""):
    results.append(f"[{'OK' if condition else 'FALHOU'}] {label} {detail}")


email = f"pendencia{int(time.time())}@example.com"
s, b = call("POST", "/usuarios", {"nome": "Teste Pendencia", "email": email, "senha": "senha123"})
check("criar usuario", s == 201, f"status={s}")

s, b = call("POST", "/usuarios", {"nome": "Outro", "email": f"outropend{int(time.time())}@example.com", "senha": "senha123"})
outro_email = b.get("email")

s, b = call("POST", "/auth/login", {"username": email, "password": "senha123"}, form=True)
token = b["access_token"]

s, b = call("POST", "/auth/login", {"username": outro_email, "password": "senha123"}, form=True)
token_outro = b["access_token"]

s, b = call("POST", "/contas", {"nome_banco": "Banco Teste"}, token=token)
check("criar conta de teste", s == 201, f"status={s}")
conta_id = b["id"]

s, b = call("GET", "/categorias", token=token)
cats = {c["nome"]: c["id"] for c in b}
cat_despesa = cats["Contas"]
cat_receita = cats["Bônus"]

# ---------- Avulsa a vencer ----------
data_futura = (date.today() + timedelta(days=10)).isoformat()
s, b = call("POST", "/pendencias", {
    "descricao": "Presente aniversário", "valor": 200, "categoria_id": cat_despesa,
    "recorrente": False, "data_vencimento": data_futura,
}, token=token)
check("criar pendencia avulsa a vencer", s == 201, f"status={s}")
pend_avulsa_futura_id = b["id"] if s == 201 else None
check("avulsa a vencer: 1 ciclo status a_vencer", len(b.get("ciclos", [])) == 1 and b["ciclos"][0]["status"] == "a_vencer", f"={b.get('ciclos')}")

# ---------- Avulsa atrasada ----------
data_passada = (date.today() - timedelta(days=5)).isoformat()
s, b = call("POST", "/pendencias", {
    "descricao": "Conta atrasada", "valor": 80, "categoria_id": cat_despesa,
    "recorrente": False, "data_vencimento": data_passada,
}, token=token)
check("criar pendencia avulsa atrasada", s == 201, f"status={s}")
pend_avulsa_atrasada_id = b["id"] if s == 201 else None
check("avulsa atrasada: 1 ciclo status atrasada", len(b.get("ciclos", [])) == 1 and b["ciclos"][0]["status"] == "atrasada", f"={b.get('ciclos')}")

# ---------- Pagar a atrasada ----------
s, b = call("POST", f"/pendencias/{pend_avulsa_atrasada_id}/pagar", {
    "data_vencimento": data_passada, "conta_id": conta_id, "valor": 85,
}, token=token)
check("pagar pendencia avulsa: 201", s == 201, f"status={s}")
check(
    "pagar pendencia: movimentacao com pendencia_id/valor certos",
    b.get("pendencia_id") == pend_avulsa_atrasada_id and b.get("valor") == "85.00",
    f"={b}",
)

s, b = call("GET", "/pendencias", token=token)
pend_map = {p["id"]: p for p in b}
check(
    "depois de paga, avulsa atrasada some da lista de ciclos pendentes",
    len(pend_map[pend_avulsa_atrasada_id]["ciclos"]) == 0,
    f"={pend_map.get(pend_avulsa_atrasada_id)}",
)

# ---------- Pagar o mesmo ciclo de novo -> 409 ----------
s, b = call("POST", f"/pendencias/{pend_avulsa_atrasada_id}/pagar", {
    "data_vencimento": data_passada, "conta_id": conta_id,
}, token=token)
check("pagar o mesmo ciclo duas vezes -> 409", s == 409, f"status={s}")

# ---------- Pagar uma data que não é um ciclo pendente -> 422 ----------
s, b = call("POST", f"/pendencias/{pend_avulsa_futura_id}/pagar", {
    "data_vencimento": "2000-01-01", "conta_id": conta_id,
}, token=token)
check("pagar vencimento que não corresponde a ciclo real -> 422", s == 422, f"status={s}")

# ---------- Recorrente com múltiplos meses atrasados ----------
s, b = call("POST", "/pendencias", {
    "descricao": "Aluguel", "valor": 1500, "categoria_id": cat_despesa,
    "recorrente": True, "dia_vencimento": 5,
}, token=token)
check("criar pendencia recorrente", s == 201, f"status={s}")
pend_recorrente_id = b["id"]

# "Volta no tempo" o criado_em pra 2 meses atrás -> deve gerar 3 ciclos
# (mês-2, mês-1, mês atual), todos ainda sem pagamento.
backdatar_criado_em(pend_recorrente_id, datetime.combine(mes_atras(2), datetime.min.time()))

s, b = call("GET", "/pendencias", token=token)
pend_map = {p["id"]: p for p in b}
recorrente = pend_map[pend_recorrente_id]
check("recorrente com 2 meses de atraso: 3 ciclos", len(recorrente["ciclos"]) == 3, f"={recorrente['ciclos']}")

datas_esperadas = [mes_atras(2).isoformat(), mes_atras(1).isoformat(), mes_atras(0).isoformat()]
datas_recebidas = [c["data_vencimento"] for c in recorrente["ciclos"]]
check("ciclos do mais antigo pro mais recente, datas certas", datas_recebidas == datas_esperadas, f"={datas_recebidas} esperado={datas_esperadas}")

hoje = date.today()
status_esperado = ["atrasada" if m < hoje else "a_vencer" for m in (mes_atras(2), mes_atras(1), mes_atras(0))]
status_recebido = [c["status"] for c in recorrente["ciclos"]]
check("status de cada ciclo bate com atrasada/a_vencer esperado", status_recebido == status_esperado, f"={status_recebido} esperado={status_esperado}")

# Paga o ciclo mais antigo (mês-2)
s, b = call("POST", f"/pendencias/{pend_recorrente_id}/pagar", {
    "data_vencimento": mes_atras(2).isoformat(), "conta_id": conta_id, "valor": 1500,
}, token=token)
check("pagar ciclo mais antigo do aluguel: 201", s == 201, f"status={s}")

s, b = call("GET", "/pendencias", token=token)
pend_map = {p["id"]: p for p in b}
check("depois de pagar 1 ciclo, sobram 2 pendentes", len(pend_map[pend_recorrente_id]["ciclos"]) == 2, f"={pend_map[pend_recorrente_id]['ciclos']}")

# ---------- Editar / pausar ----------
s, b = call("PATCH", f"/pendencias/{pend_recorrente_id}", {"valor": 1600, "ativa": False}, token=token)
check("editar pendencia (valor + pausar)", s == 200 and b.get("valor") == "1600.00" and b.get("ativa") is False, f"={b}")

# ---------- Isolamento entre usuários ----------
s, b = call("GET", "/pendencias", token=token_outro)
check("outro usuario nao ve pendencias de usuario1", s == 200 and b == [], f"status={s} body={b}")

s, b = call("POST", f"/pendencias/{pend_recorrente_id}/pagar", {
    "data_vencimento": mes_atras(1).isoformat(), "conta_id": conta_id,
}, token=token_outro)
check("outro usuario nao paga pendencia alheia -> 404", s == 404, f"status={s}")

s, b = call("POST", "/categorias", {"nome": "Categoria Privada Pendencia", "tipo": "despesa"}, token=token)
cat_privada = b["id"]
s, b = call("POST", "/pendencias", {
    "descricao": "X", "valor": 10, "categoria_id": cat_privada,
    "recorrente": False, "data_vencimento": data_futura,
}, token=token_outro)
check("criar pendencia com categoria de outro usuario -> 403", s == 403, f"status={s}")

# ---------- Validações de erro na criação ----------
s, b = call("POST", "/pendencias", {
    "descricao": "X", "valor": 10, "categoria_id": cat_despesa, "recorrente": True,
}, token=token)
check("recorrente sem dia_vencimento -> 422", s == 422, f"status={s}")

s, b = call("POST", "/pendencias", {
    "descricao": "X", "valor": 10, "categoria_id": cat_despesa, "recorrente": False,
}, token=token)
check("avulsa sem data_vencimento -> 422", s == 422, f"status={s}")

# ---------- Apagar ----------
s, b = call("DELETE", f"/pendencias/{pend_recorrente_id}", token=token)
check("apagar pendencia com histórico (já tem pagamento) -> 409", s == 409, f"status={s}")

s, b = call("DELETE", f"/pendencias/{pend_avulsa_futura_id}", token=token)
check("apagar pendencia sem histórico -> 204", s == 204, f"status={s}")

print("\n".join(results))
falhas = [r for r in results if "FALHOU" in r]
print(f"\n{len(results) - len(falhas)}/{len(results)} testes passaram")
