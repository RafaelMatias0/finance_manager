"""
Bateria de testes da API do Gerenciador de Finanças.

Como usar:
1. Suba o banco (docker compose up -d) e aplique as migrações (alembic upgrade head).
2. Rode a API em um terminal: uvicorn app.main:app --reload
3. Em OUTRO terminal (com a venv ativada), rode: python test_jwt.py

Não usa nenhuma dependência externa (só urllib, que já vem com o Python),
então roda igual em Windows/Mac/Linux sem precisar instalar nada a mais.

Observação: o script cria usuários com email fixo (rafael@example.com,
bianca@example.com). Se já existirem no seu banco de um teste anterior, o
teste 1 e 2 vão "FALHAR" (409 Conflito) mas os demais continuam rodando
normalmente — ou apague os usuários do banco antes de rodar de novo.
"""
import urllib.request
import urllib.error
import json

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
        print(f"\nERRO DE CONEXÃO: não consegui falar com {BASE}.")
        print("A API está rodando? (uvicorn app.main:app --reload)")
        print(f"Detalhe: {e}")
        raise SystemExit(1)


results = []


def check(label, condition, detail=""):
    status = "OK" if condition else "FALHOU"
    results.append(f"[{status}] {label} {detail}")


# 1) criar usuarios
s, b = call("POST", "/usuarios", {"nome": "Rafael", "email": "rafael@example.com", "senha": "senha123"})
check("criar usuario 1", s == 201, f"status={s}")
usuario1_id = b["id"] if s == 201 else None

s, b = call("POST", "/usuarios", {"nome": "Bianca", "email": "bianca@example.com", "senha": "outrasenha"})
check("criar usuario 2", s == 201, f"status={s}")

# 2) rota protegida sem token
s, b = call("GET", "/categorias")
check("GET /categorias sem token -> 401", s == 401, f"status={s}")

# 3) login errado
s, b = call("POST", "/auth/login", {"username": "rafael@example.com", "password": "errada"}, form=True)
check("login senha errada -> 401", s == 401, f"status={s}")

# 4) login certo
s, b = call("POST", "/auth/login", {"username": "rafael@example.com", "password": "senha123"}, form=True)
check("login usuario1 -> 200 com token", s == 200 and "access_token" in b, f"status={s}")
token1 = b["access_token"] if s == 200 else None

s, b = call("POST", "/auth/login", {"username": "bianca@example.com", "password": "outrasenha"}, form=True)
check("login usuario2 -> 200 com token", s == 200 and "access_token" in b, f"status={s}")
token2 = b["access_token"] if s == 200 else None

# Movimentação exige conta_id desde a Fase 1 (v2.1.0) — cria uma conta pra
# cada usuário antes de qualquer POST /movimentacoes.
s, b = call("POST", "/contas", {"nome_banco": "Banco Teste"}, token=token1)
check("criar conta usuario1", s == 201, f"status={s}")
conta1_id = b["id"] if s == 201 else None

s, b = call("POST", "/contas", {"nome_banco": "Banco Teste"}, token=token2)
check("criar conta usuario2", s == 201, f"status={s}")
conta2_id = b["id"] if s == 201 else None

# 5) token invalido
s, b = call("GET", "/categorias", token="token.forjado.invalido")
check("token forjado -> 401", s == 401, f"status={s}")

# 6) /usuarios/me
s, b = call("GET", "/usuarios/me", token=token1)
check("GET /usuarios/me com token1", s == 200 and b.get("email") == "rafael@example.com", f"status={s}")

# 7) listar categorias com token1
s, b = call("GET", "/categorias", token=token1)
check("GET /categorias com token1", s == 200 and len(b) >= 8, f"status={s} len={len(b) if s==200 else '?'}")
cat_salario = next(c["id"] for c in b if c["nome"] == "Salário")
cat_alimentacao = next(c["id"] for c in b if c["nome"] == "Alimentação")

# 8) criar categoria custom para usuario1
s, b = call("POST", "/categorias", {"nome": "Investimentos", "tipo": "receita"}, token=token1)
check("criar categoria custom usuario1", s == 201, f"status={s}")
cat_custom_id = b["id"] if s == 201 else None

# 9) usuario2 nao ve categoria custom do usuario1
s, b = call("GET", "/categorias", token=token2)
nomes = [c["nome"] for c in b] if s == 200 else []
check("usuario2 nao ve categoria custom do usuario1", "Investimentos" not in nomes, f"nomes={len(nomes)}")

# 10) criar movimentacoes para usuario1 (sem passar usuario_id, vem do token)
s, b = call("POST", "/movimentacoes", {"valor": 3000.00, "descricao": "Salário Agosto", "categoria_id": cat_salario, "conta_id": conta1_id}, token=token1)
check("criar receita usuario1", s == 201, f"status={s}")

s, b = call("POST", "/movimentacoes", {"valor": 450.50, "descricao": "Mercado", "categoria_id": cat_alimentacao, "conta_id": conta1_id}, token=token1)
check("criar despesa usuario1", s == 201, f"status={s}")
despesa_id = b["id"] if s == 201 else None

# 11) usuario2 tenta criar movimentacao usando categoria custom do usuario1 -> 403
s, b = call("POST", "/movimentacoes", {"valor": 100, "categoria_id": cat_custom_id, "conta_id": conta2_id}, token=token2)
check("usuario2 usa categoria de usuario1 -> 403", s == 403, f"status={s}")

# 12) historico do usuario1
s, b = call("GET", "/movimentacoes", token=token1)
check("historico usuario1 tem 2 movimentacoes", s == 200 and b.get("total") == 2 and len(b.get("itens", [])) == 2, f"status={s} body={b}")

# 13) historico do usuario2 deve estar vazio (isolamento)
s, b = call("GET", "/movimentacoes", token=token2)
check("historico usuario2 vazio (isolamento)", s == 200 and b.get("total") == 0, f"status={s} body={b}")

# 14) saldo usuario1
s, b = call("GET", "/saldo", token=token1)
check("saldo usuario1 correto (2549.50)", s == 200 and b.get("saldo") == "2549.50", f"status={s} body={b}")

# 15) usuario2 tenta apagar movimentacao do usuario1 -> 404 (nao 403, para nao vazar existencia)
s, b = call("DELETE", f"/movimentacoes/{despesa_id}", token=token2)
check("usuario2 apaga movimentacao de usuario1 -> 404", s == 404, f"status={s}")

# 16) usuario1 apaga a propria movimentacao -> 204
s, b = call("DELETE", f"/movimentacoes/{despesa_id}", token=token1)
check("usuario1 apaga a propria movimentacao -> 204", s == 204, f"status={s}")

# 17) saldo recalculado
s, b = call("GET", "/saldo", token=token1)
check("saldo recalculado apos delete (3000.00)", s == 200 and b.get("saldo") == "3000.00", f"status={s} body={b}")

# 18) PATCH categoria custom do usuario1 -> deve funcionar
s, b = call("PATCH", f"/categorias/{cat_custom_id}", {"nome": "Investimentos Renda Fixa"}, token=token1)
check("PATCH categoria propria (usuario1)", s == 200 and b.get("nome") == "Investimentos Renda Fixa", f"status={s}")

# 19) PATCH categoria global (Salário) -> 404 (ninguem edita categoria padrao)
s, b = call("PATCH", f"/categorias/{cat_salario}", {"nome": "Salario Hackeado"}, token=token1)
check("PATCH categoria global -> 404", s == 404, f"status={s}")

# 20) PATCH categoria de outro usuario -> 404
s, b = call("PATCH", f"/categorias/{cat_custom_id}", {"nome": "Roubada"}, token=token2)
check("usuario2 edita categoria de usuario1 -> 404", s == 404, f"status={s}")

# 21) criar nova movimentacao pra testar PATCH
s, b = call("POST", "/movimentacoes", {"valor": 100.00, "descricao": "Original", "categoria_id": cat_salario, "conta_id": conta1_id}, token=token1)
mov_id = b["id"] if s == 201 else None
check("criar movimentacao para teste de patch", s == 201, f"status={s}")

# 22) PATCH parcial (só valor) -> descricao deve continuar igual
s, b = call("PATCH", f"/movimentacoes/{mov_id}", {"valor": 250.75}, token=token1)
check("PATCH parcial so valor", s == 200 and b.get("valor") == "250.75" and b.get("descricao") == "Original", f"status={s} body={b}")

# 23) PATCH mudando categoria pra uma que pertence a outro usuario -> 403
s, b = call("PATCH", f"/movimentacoes/{mov_id}", {"categoria_id": cat_custom_id}, token=token2)
check("usuario2 edita movimentacao de usuario1 -> 404", s == 404, f"status={s}")

# 24) PATCH em movimentacao inexistente -> 404
s, b = call("PATCH", "/movimentacoes/00000000-0000-0000-0000-000000000000", {"valor": 10}, token=token1)
check("PATCH movimentacao inexistente -> 404", s == 404, f"status={s}")

# 25) preparar dados para paginacao/ordenacao: criar mais 4 movimentacoes de despesa com valores diferentes
valores = [10, 40, 20, 30]
for v in valores:
    call("POST", "/movimentacoes", {"valor": v, "descricao": f"Despesa {v}", "categoria_id": cat_alimentacao, "conta_id": conta1_id}, token=token1)

# nesse ponto usuario1 tem: 1 receita original (test 10, ainda existe) +
# 1 movimentacao do teste de patch (test 21, editada para 250.75) +
# 4 despesas novas = 6 movimentacoes (a despesa do test 10 foi deletada no test 16)
s, b = call("GET", "/movimentacoes", token=token1)
check("total de movimentacoes apos criar mais 4", s == 200 and b.get("total") == 6, f"status={s} total={b.get('total')}")

# 26) paginacao: limit=2 deve trazer so 2 itens, mas total continua 6
s, b = call("GET", "/movimentacoes?limit=2", token=token1)
check("paginacao limit=2", s == 200 and len(b.get("itens", [])) == 2 and b.get("total") == 6, f"status={s} body_len={len(b.get('itens', []))} total={b.get('total')}")

# 27) paginacao: skip=4&limit=2 deve trazer os 2 ultimos restantes
s, b = call("GET", "/movimentacoes?skip=4&limit=2", token=token1)
check("paginacao skip=4&limit=2 traz o restante (2 itens)", s == 200 and len(b.get("itens", [])) == 2, f"status={s} body_len={len(b.get('itens', []))}")

# 27b) paginacao: skip=6 (== total) deve vir vazio
s, b = call("GET", "/movimentacoes?skip=6&limit=2", token=token1)
check("paginacao skip=total traz vazio", s == 200 and len(b.get("itens", [])) == 0, f"status={s} body_len={len(b.get('itens', []))}")

# 28) ordenacao por valor ascendente
s, b = call("GET", "/movimentacoes?ordenar_por=valor&ordem=asc&tipo=despesa", token=token1)
valores_recebidos = [float(m["valor"]) for m in b.get("itens", [])] if s == 200 else []
check("ordenar por valor asc", s == 200 and valores_recebidos == sorted(valores_recebidos), f"status={s} valores={valores_recebidos}")

# 29) ordenacao por valor descendente
s, b = call("GET", "/movimentacoes?ordenar_por=valor&ordem=desc&tipo=despesa", token=token1)
valores_recebidos = [float(m["valor"]) for m in b.get("itens", [])] if s == 200 else []
check("ordenar por valor desc", s == 200 and valores_recebidos == sorted(valores_recebidos, reverse=True), f"status={s} valores={valores_recebidos}")

# 30) ordenar_por invalido -> 422 (validacao de enum)
s, b = call("GET", "/movimentacoes?ordenar_por=campo_que_nao_existe", token=token1)
check("ordenar_por invalido -> 422", s == 422, f"status={s}")

print("\n".join(results))
falhas = [r for r in results if "FALHOU" in r]
print(f"\n{len(results) - len(falhas)}/{len(results)} testes passaram")
