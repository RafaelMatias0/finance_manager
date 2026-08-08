"""
Testes dos endpoints de relatório. Mesmo estilo do test_jwt.py: sem
dependências externas, roda contra a API real.

Cria um usuário e movimentações num período fixo (2026-01-01 a 2026-01-05,
escolhido por não ter relação com "hoje", pra não interferir com os
cálculos de semana/mês anterior do relatório automático) com valores
conhecidos, e confere a matemática das agregações à mão.
"""
import urllib.request
import urllib.error
import json
import time

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


results = []


def check(label, condition, detail=""):
    results.append(f"[{'OK' if condition else 'FALHOU'}] {label} {detail}")


def aproxima(a, b, tolerancia=0.01):
    return abs(a - b) < tolerancia


email = f"relatorio{int(time.time())}@example.com"

s, b = call("POST", "/usuarios", {"nome": "Teste Relatorio", "email": email, "senha": "senha123"})
check("criar usuario", s == 201, f"status={s}")

s, b = call("POST", "/usuarios", {"nome": "Outro", "email": f"outro{int(time.time())}@example.com", "senha": "senha123"})
outro_email = b.get("email")

s, b = call("POST", "/auth/login", {"username": email, "password": "senha123"}, form=True)
token = b["access_token"]

s, b = call("POST", "/auth/login", {"username": outro_email, "password": "senha123"}, form=True)
token_outro = b["access_token"]

s, b = call("GET", "/categorias", token=token)
cats = {c["nome"]: c["id"] for c in b}
cat_salario = cats["Salário"]
cat_alimentacao = cats["Alimentação"]
cat_transporte = cats["Transporte"]
cat_lazer = cats["Lazer"]

# ---------- Criar movimentações no período fixo ----------
movs = [
    (cat_salario, "2026-01-01", 1000),
    (cat_salario, "2026-01-03", 500),
    (cat_alimentacao, "2026-01-01", 100),
    (cat_alimentacao, "2026-01-02", 50),
    (cat_transporte, "2026-01-02", 80),
    (cat_transporte, "2026-01-04", 20),
    (cat_lazer, "2026-01-05", 200),
]
for categoria_id, data_mov, valor in movs:
    s, b = call("POST", "/movimentacoes", {"valor": valor, "categoria_id": categoria_id, "data": data_mov}, token=token)
    check(f"criar movimentacao {data_mov} valor={valor}", s == 201, f"status={s}")

# ---------- Relatório personalizado (sem filtro) ----------
s, b = call("GET", "/relatorios/personalizado?data_inicio=2026-01-01&data_fim=2026-01-05", token=token)
check("personalizado sem filtro: status 200", s == 200, f"status={s}")
check("personalizado: historico tem 7 movimentacoes", len(b.get("historico", [])) == 7, f"len={len(b.get('historico', []))}")
check("personalizado: total_receitas=1500", aproxima(b["saldo"]["total_receitas"], 1500), f"={b['saldo']['total_receitas']}")
check("personalizado: total_despesas=450", aproxima(b["saldo"]["total_despesas"], 450), f"={b['saldo']['total_despesas']}")
check("personalizado: saldo=1050", aproxima(b["saldo"]["saldo"], 1050), f"={b['saldo']['saldo']}")
check("personalizado: grafico_diario tem 5 dias", len(b["grafico_diario"]) == 5, f"len={len(b['grafico_diario'])}")

dia_por_data = {d["data"]: d for d in b["grafico_diario"]}
check("dia 01-01: receitas=1000 despesas=100", aproxima(dia_por_data["2026-01-01"]["total_receitas"], 1000) and aproxima(dia_por_data["2026-01-01"]["total_despesas"], 100))
check("dia 01-02: despesas=130 (50+80)", aproxima(dia_por_data["2026-01-02"]["total_despesas"], 130))
check("dia 01-03: receitas=500", aproxima(dia_por_data["2026-01-03"]["total_receitas"], 500))

# ---------- Relatório personalizado com categoria (participação) ----------
s, b = call("GET", f"/relatorios/personalizado?data_inicio=2026-01-01&data_fim=2026-01-05&categoria_id={cat_alimentacao}", token=token)
gc = b.get("grafico_categoria")
check("grafico_categoria: total_categoria=150", gc and aproxima(gc["total_categoria"], 150), f"={gc}")
check("grafico_categoria: total_mesmo_tipo_periodo=450 (todas despesas)", gc and aproxima(gc["total_mesmo_tipo_periodo"], 450))
check("grafico_categoria: percentual=33.33", gc and aproxima(gc["percentual"], 33.33, 0.1), f"={gc.get('percentual') if gc else None}")

# ---------- Validações de erro ----------
s, b = call("GET", "/relatorios/personalizado?data_inicio=2026-01-05&data_fim=2026-01-01", token=token)
check("data_fim antes de data_inicio -> 422", s == 422, f"status={s}")

s, b = call("GET", "/relatorios/personalizado?data_inicio=2026-01-01&data_fim=2026-01-05", )
check("relatorio sem token -> 401", s == 401, f"status={s}")

# ---------- Comparativo: tipos diferentes (Salário x Alimentação) ----------
s, b = call("GET", f"/relatorios/comparativo?data_inicio=2026-01-01&data_fim=2026-01-05&categoria_id_1={cat_salario}&categoria_id_2={cat_alimentacao}", token=token)
check("comparativo tipos diferentes: status 200", s == 200, f"status={s}")
check("comparativo: modo=tipos_diferentes", b.get("modo") == "tipos_diferentes", f"modo={b.get('modo')}")
check("comparativo: saldo_diferenca=1350 (1500-150)", aproxima(b.get("saldo_diferenca", -1), 1350), f"={b.get('saldo_diferenca')}")
check("comparativo: historico tem 4 movimentacoes", len(b.get("historico", [])) == 4, f"len={len(b.get('historico', []))}")
check("comparativo: categoria_1.total=1500", aproxima(b["categoria_1"]["total"], 1500))
check("comparativo: categoria_2.total=150", aproxima(b["categoria_2"]["total"], 150))

# ---------- Comparativo: mesmo tipo (Transporte x Lazer, ambas despesa) ----------
s, b = call("GET", f"/relatorios/comparativo?data_inicio=2026-01-01&data_fim=2026-01-05&categoria_id_1={cat_transporte}&categoria_id_2={cat_lazer}", token=token)
check("comparativo mesmo tipo: status 200", s == 200, f"status={s}")
check("comparativo: modo=mesmo_tipo", b.get("modo") == "mesmo_tipo", f"modo={b.get('modo')}")
check("comparativo: saldo_soma=300 (100+200)", aproxima(b.get("saldo_soma", -1), 300), f"={b.get('saldo_soma')}")
check("comparativo: total_tipo_periodo=450", aproxima(b.get("total_tipo_periodo", -1), 450))
participacao = {p["categoria"]: p["percentual"] for p in b.get("grafico_participacao_individual", [])}
check("participacao individual: Transporte=22.22%", aproxima(participacao.get("Transporte", -1), 22.22, 0.1), f"={participacao}")
check("participacao individual: Lazer=44.44%", aproxima(participacao.get("Lazer", -1), 44.44, 0.1), f"={participacao}")
check("participacao individual: Restante=33.33%", aproxima(participacao.get("Restante", -1), 33.33, 0.1), f"={participacao}")
combinada = {p["categoria"]: p["percentual"] for p in b.get("grafico_participacao_combinada", [])}
check("participacao combinada: soma das duas=66.67%", aproxima(combinada.get("Transporte + Lazer", -1), 66.67, 0.1), f"={combinada}")

# ---------- Validações de erro do comparativo ----------
s, b = call("GET", f"/relatorios/comparativo?data_inicio=2026-01-01&data_fim=2026-01-05&categoria_id_1={cat_salario}&categoria_id_2={cat_salario}", token=token)
check("comparativo mesma categoria duas vezes -> 422", s == 422, f"status={s}")

s, b = call("GET", f"/relatorios/comparativo?data_inicio=2026-01-01&data_fim=2026-01-05&categoria_id_1={cat_salario}&categoria_id_2=00000000-0000-0000-0000-000000000000", token=token)
check("comparativo categoria inexistente -> 404", s == 404, f"status={s}")

# categoria custom do usuario1, tentar comparar com token do outro usuario -> 403
s, b = call("POST", "/categorias", {"nome": "Custom Comparativo", "tipo": "despesa"}, token=token)
cat_custom_usuario1 = b["id"]
s, b = call("GET", f"/relatorios/comparativo?data_inicio=2026-01-01&data_fim=2026-01-05&categoria_id_1={cat_custom_usuario1}&categoria_id_2={cat_lazer}", token=token_outro)
check("comparativo com categoria de outro usuario -> 403", s == 403, f"status={s}")

# ---------- Relatório automático (gerar na hora, sem esperar o cron) ----------
s, b = call("POST", "/relatorios/gerar-agora?tipo=automatico_semanal", token=token)
check("gerar relatorio semanal na hora: 200", s == 200, f"status={s}")
check("relatorio semanal tem dados.saldo", "saldo" in b.get("dados", {}), f"body={b}")
relatorio_id = b.get("id")

s, b = call("POST", "/relatorios/gerar-agora?tipo=automatico_mensal", token=token)
check("gerar relatorio mensal na hora: 200", s == 200, f"status={s}")

s, b = call("GET", "/relatorios", token=token)
check("listar relatorios: pelo menos 2", s == 200 and len(b) >= 2, f"status={s} len={len(b) if s==200 else '?'}")

s, b = call("GET", f"/relatorios/{relatorio_id}", token=token)
check("obter relatorio especifico: 200", s == 200 and b["id"] == relatorio_id, f"status={s}")

s, b = call("GET", f"/relatorios/{relatorio_id}", token=token_outro)
check("outro usuario nao acessa relatorio alheio -> 404", s == 404, f"status={s}")

print("\n".join(results))
falhas = [r for r in results if "FALHOU" in r]
print(f"\n{len(results) - len(falhas)}/{len(results)} testes passaram")
