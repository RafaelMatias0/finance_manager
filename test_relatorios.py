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
from datetime import date

BASE = "http://127.0.0.1:8000"


def mes_atras(n, dia=5):
    """Data no dia fixo `dia` (evita problema de mês curto), n meses antes
    do mês atual. Calculado de forma independente da implementação do
    backend, pra servir de conferência real."""
    hoje = date.today()
    total_meses = hoje.year * 12 + (hoje.month - 1) - n
    ano, mes = divmod(total_meses, 12)
    return date(ano, mes + 1, dia).isoformat()


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

# Movimentação exige conta_id desde a Fase 1 (v2.1.0) — cria uma conta pro
# usuário de teste antes de lançar qualquer movimentação.
s, b = call("POST", "/contas", {"nome_banco": "Banco Teste"}, token=token)
check("criar conta de teste", s == 201, f"status={s}")
conta_id = b["id"]

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
    s, b = call("POST", "/movimentacoes", {"valor": valor, "categoria_id": categoria_id, "conta_id": conta_id, "data": data_mov}, token=token)
    check(f"criar movimentacao {data_mov} valor={valor}", s == 201, f"status={s}")

# ---------- Por categoria (sem filtro): total/%/mín/média/máx à mão ----------
# A partir daqui, com só as 7 movimentações acima: Salário (receita)
# 1000+500=1500; despesas: Alimentação 100+50=150, Transporte 80+20=100,
# Lazer 200 — total despesas=450.
s, b = call("GET", "/relatorios/por-categoria", token=token)
check("por-categoria sem filtro: status 200", s == 200, f"status={s}")
por_nome = {c["categoria_nome"]: c for c in b} if s == 200 else {}
check("por-categoria: Salário total=1500 qtd=2 min=500 media=750 max=1000",
      por_nome.get("Salário", {}).get("total") == 1500
      and por_nome["Salário"]["quantidade"] == 2
      and aproxima(por_nome["Salário"]["minimo"], 500)
      and aproxima(por_nome["Salário"]["media"], 750)
      and aproxima(por_nome["Salário"]["maximo"], 1000),
      f"={por_nome.get('Salário')}")
check("por-categoria: Salário percentual=100 (só receita)", aproxima(por_nome.get("Salário", {}).get("percentual", -1), 100), f"={por_nome.get('Salário')}")
check("por-categoria: Alimentação total=150 percentual=33.33", aproxima(por_nome.get("Alimentação", {}).get("total", -1), 150) and aproxima(por_nome.get("Alimentação", {}).get("percentual", -1), 33.33, 0.1), f"={por_nome.get('Alimentação')}")
check("por-categoria: Transporte total=100 min=20 media=50 max=80 percentual=22.22",
      aproxima(por_nome.get("Transporte", {}).get("total", -1), 100)
      and aproxima(por_nome.get("Transporte", {}).get("minimo", -1), 20)
      and aproxima(por_nome.get("Transporte", {}).get("media", -1), 50)
      and aproxima(por_nome.get("Transporte", {}).get("maximo", -1), 80)
      and aproxima(por_nome.get("Transporte", {}).get("percentual", -1), 22.22, 0.1),
      f"={por_nome.get('Transporte')}")
check("por-categoria: Lazer total=200 percentual=44.44", aproxima(por_nome.get("Lazer", {}).get("total", -1), 200) and aproxima(por_nome.get("Lazer", {}).get("percentual", -1), 44.44, 0.1), f"={por_nome.get('Lazer')}")

# ---------- Por categoria: filtro tipo=despesa (some Salário) ----------
s, b = call("GET", "/relatorios/por-categoria?tipo=despesa", token=token)
nomes_despesa = {c["categoria_nome"] for c in b} if s == 200 else set()
check("por-categoria tipo=despesa: sem Salário, com as 3 de despesa", "Salário" not in nomes_despesa and {"Alimentação", "Transporte", "Lazer"} <= nomes_despesa, f"={nomes_despesa}")

# ---------- Por categoria: filtro de período (recorta pra 01-01 e 01-02) ----------
s, b = call("GET", "/relatorios/por-categoria?data_inicio=2026-01-01&data_fim=2026-01-02", token=token)
por_nome_periodo = {c["categoria_nome"]: c for c in b} if s == 200 else {}
check("por-categoria com período: Transporte total=80 (só a de 01-02, não a de 01-04)", aproxima(por_nome_periodo.get("Transporte", {}).get("total", -1), 80), f"={por_nome_periodo.get('Transporte')}")
check("por-categoria com período: Lazer não aparece (movimentação é de 01-05)", "Lazer" not in por_nome_periodo, f"={list(por_nome_periodo.keys())}")

# ---------- Por categoria: isolamento entre usuários ----------
s, b = call("GET", "/relatorios/por-categoria", token=token_outro)
check("por-categoria outro usuário (sem movimentações): lista vazia", s == 200 and b == [], f"status={s} body={b}")

# ---------- Por categoria: erro data_fim antes de data_inicio ----------
s, b = call("GET", "/relatorios/por-categoria?data_inicio=2026-01-05&data_fim=2026-01-01", token=token)
check("por-categoria data_fim antes de data_inicio -> 422", s == 422, f"status={s}")

# ---------- Por categoria: meses_recentes (quebra mensal, datas relativas a hoje) ----------
s, b = call("POST", "/categorias", {"nome": "Teste Mensal", "tipo": "despesa"}, token=token)
cat_mensal = b["id"]
valores_mensais = [333, 222, 111]  # [2 meses atrás, 1 mês atrás, mês atual]
for i, valor in enumerate(valores_mensais):
    s, b = call("POST", "/movimentacoes", {"valor": valor, "categoria_id": cat_mensal, "conta_id": conta_id, "data": mes_atras(2 - i)}, token=token)
    check(f"criar movimentacao mensal (mes_atras={2-i}) valor={valor}", s == 201, f"status={s}")

s, b = call("GET", "/relatorios/por-categoria?meses_recentes=3", token=token)
item_mensal = next((c for c in b if c["categoria_nome"] == "Teste Mensal"), None) if s == 200 else None
check("por-categoria meses_recentes: categoria aparece com 3 meses", item_mensal is not None and len(item_mensal.get("mensal", [])) == 3, f"={item_mensal}")
if item_mensal:
    totais_mensais = [m["total"] for m in item_mensal["mensal"]]
    check("por-categoria meses_recentes: ordem do mais antigo pro mais recente = [333, 222, 111]", totais_mensais == [333.0, 222.0, 111.0], f"={totais_mensais}")

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
