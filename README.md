# Gerenciador de Finanças — Backend

Backend em **FastAPI + SQLAlchemy + PostgreSQL + Alembic**, começando pela
modelagem do banco de dados. O front-end (HTML/CSS/JS puro) será feito por
último; até lá, as rotas serão testadas pelo Swagger (`/docs`).

## Modelo de dados

- **Usuario** — id (UUID), nome, email (único), senha_hash, criado_em, atualizado_em
- **Categoria** — id, nome, tipo (`receita`/`despesa`), usuario_id (nulo = categoria
  padrão/global; preenchido = categoria criada pelo próprio usuário), criado_em
- **Movimentacao** — id, valor (Numeric 12,2), descricao, data, usuario_id,
  categoria_id, criado_em, atualizado_em

### Decisões de design

- **Categoria como tabela própria**, não como enum fixo na Movimentação — permite
  o usuário criar categorias próprias no futuro sem alterar o schema.
- **Sem campo `tipo` redundante em Movimentacao** — o tipo (receita/despesa) já
  vem da Categoria associada (`movimentacao.categoria.tipo`). Evita dado
  inconsistente (ex: categoria "Salário" marcada como despesa).
- **`valor` como `Numeric(12,2)`**, nunca `Float` — evita erro de arredondamento
  em dinheiro.
- **`senha_hash`**, não `senha` — a senha nunca é salva em texto puro (hash com
  passlib/bcrypt na hora de implementar o cadastro de usuário).
- **UUID como chave primária** em vez de inteiro sequencial — não expõe
  quantidade de registros/ordem de criação via API.
- **Saldo não é uma tabela** — é calculado dinamicamente (soma de receitas −
  soma de despesas), então não existe uma tabela "Saldo".
- **`ON DELETE RESTRICT` em `movimentacoes.categoria_id`** — impede apagar uma
  categoria que já tem movimentações vinculadas (evita perder o histórico
  silenciosamente). `usuario_id` usa `CASCADE`: se o usuário for apagado,
  suas categorias e movimentações vão junto.

## Estrutura do projeto

```
gerenciador-financas/
├── app/
│   ├── __init__.py
│   ├── database.py      # engine, SessionLocal, Base, get_db()
│   ├── models.py         # Usuario, Categoria, Movimentacao, TipoMovimentacao
│   ├── schemas.py        # schemas Pydantic (Create/Update/Out) de cada entidade
│   ├── security.py       # hash de senha (bcrypt) + JWT (criar/validar token)
│   ├── main.py            # app FastAPI: rotas, CORS
│   └── seed.py           # popula categorias padrão (Salário, Alimentação, etc.)
├── front/
│   ├── index.html         # single-page: telas de auth + dashboard
│   ├── css/style.css      # design "livro-razão" (ver seção Front-end)
│   └── js/
│       ├── config.js       # API_BASE_URL
│       ├── api.js          # wrapper de fetch: token, erros, endpoints
│       └── app.js          # lógica de UI: forms, tabela, paginação, modal
├── alembic/
│   ├── env.py             # já configurado para ler DATABASE_URL e os models
│   └── versions/
│       └── ..._criacao_inicial_usuarios_categorias_....py
├── docker-compose.yml     # sobe o PostgreSQL local (porta 5433)
├── test_jwt.py            # bateria de testes automatizados da API
├── alembic.ini
├── requirements.txt
├── .env.example
└── .gitignore
```

## Como rodar

1. **Criar o banco no PostgreSQL** (local ou Docker):
   ```bash
   createdb gerenciador_financas
   ```

2. **Configurar variável de ambiente**:
   ```bash
   cp .env.example .env
   # edite o .env com seu usuário/senha/host do Postgres
   ```
   Gere uma `SECRET_KEY` de verdade (não use o valor de exemplo) e cole no `.env`:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Criar venv e instalar dependências**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Aplicar as migrações**:
   ```bash
   alembic upgrade head
   ```

5. **(Opcional) Popular categorias padrão**:
   ```bash
   python -m app.seed
   ```

6. **Subir a API**:
   ```bash
   uvicorn app.main:app --reload
   ```
   Acesse o Swagger em `http://127.0.0.1:8000/docs` para testar as rotas
   sem precisar do front-end ainda.

### ⚠️ Nota sobre bcrypt

O `requirements.txt` fixa `bcrypt==4.0.1` de propósito. Versões mais novas
(4.1+) têm um bug conhecido de incompatibilidade com o `passlib` que faz
qualquer hash de senha falhar com `ValueError: password cannot be longer
than 72 bytes` — mesmo com senhas curtas. Se atualizar essa dependência no
futuro, teste o cadastro de usuário antes de confiar nela.

## Rotas disponíveis

Autenticação via JWT: o `usuario_id` não é mais passado manualmente — cada
rota protegida extrai o usuário logado do token (`Authorization: Bearer
<token>`). O cadastro (`POST /usuarios`) e o login continuam públicos.

| Método | Rota | Auth? | Descrição |
|---|---|---|---|
| POST | `/usuarios` | não | Cadastra usuário (senha vira hash) |
| POST | `/auth/login` | não | Login (form: `username`=email, `password`=senha) → `access_token` |
| GET | `/usuarios/me` | sim | Dados do usuário logado |
| GET | `/categorias` | sim | Lista categorias padrão + as do usuário logado |
| POST | `/categorias` | sim | Cria categoria própria do usuário logado |
| PATCH | `/categorias/{id}` | sim | Edita categoria própria (categorias globais e de outros usuários retornam `404`) |
| POST | `/movimentacoes` | sim | Cria receita ou despesa para o usuário logado |
| GET | `/movimentacoes` | sim | Histórico do usuário logado, filtros: `tipo`, `categoria_id`, `data_inicio`, `data_fim`; paginação: `skip`, `limit`; ordenação: `ordenar_por` (`data`\|`valor`\|`criado_em`), `ordem` (`asc`\|`desc`) |
| PATCH | `/movimentacoes/{id}` | sim | Edita movimentação própria (campos opcionais — só os enviados mudam) |
| DELETE | `/movimentacoes/{id}` | sim | Remove movimentação (só se for do usuário logado — senão `404`) |
| GET | `/saldo` | sim | Total de receitas, despesas e saldo do usuário logado |

No Swagger (`/docs`), use o botão **Authorize** e informe o email/senha
cadastrados — ele já fala o protocolo OAuth2 Password que a rota
`/auth/login` implementa.

Esse fluxo completo — cadastro, rota protegida sem token (401), login com
senha errada (401), token forjado (401), isolamento de categorias e
histórico entre usuários, uma tentativa de usar categoria de outro usuário
(403), a proteção do delete contra apagar movimentação alheia (404), edição
parcial via PATCH, o bloqueio de editar categoria global ou de outro
usuário (404), paginação (`skip`/`limit`) e ordenação (`ordenar_por`/`ordem`,
incluindo validação de valor inválido → 422) — foi testado de ponta a ponta
neste ambiente (34 casos, todos passando). O script fica em `test_jwt.py`
na raiz do projeto, caso queira rodar de novo depois de alguma mudança.

**Nota sobre a resposta de `GET /movimentacoes`**: agora vem paginada —
`{"total": N, "skip": ..., "limit": ..., "itens": [...]}` — em vez de uma
lista simples. Se você já tinha algum teste manual esperando uma lista
direta, ajuste para ler `itens`.

## Front-end

HTML/CSS/JS puro (sem framework, sem build step) em `front/`. Design com
conceito de "livro-razão": fundo papel, tinta verde-escura, valores em fonte
monoespaçada (como um razão de verdade), verde para receita e terracota para
despesa, e o saldo final com sublinhado duplo — a convenção contábil de
fechamento de conta.

**Como rodar:**

1. A API precisa estar rodando (`uvicorn app.main:app --reload`) — o CORS já
   está liberado (`allow_origins=["*"]`) para o front conseguir chamá-la de
   qualquer origem.
2. Abra `front/index.html` direto no navegador (duplo clique), **ou** sirva
   como estático para evitar peculiaridades de `file://`:
   ```bash
   cd front
   python -m http.server 5500
   ```
   e acesse `http://127.0.0.1:5500`.
3. Se a API não estiver em `http://127.0.0.1:8000`, ajuste em `front/js/config.js`.

**O que tem implementado:** cadastro/login, tela com saldo (receitas,
despesas, saldo), formulário de nova movimentação (com criação rápida de
categoria própria embutida), histórico com filtros/paginação/ordenação,
edição via modal, exclusão com confirmação, e logout. Sessão expirada (token
vencido) redireciona automaticamente para a tela de login.

O contrato HTTP entre front e back (nomes de campo, formato das respostas,
FormData sempre enviando valores como string) foi validado com chamadas
reais contra a API neste ambiente — 10/10 casos passando.

## Próximos passos sugeridos

1. Refresh token / expiração mais robusta (hoje o token expira em 60min,
   sem renovação — o usuário precisa logar de novo).
2. Gráficos simples no dashboard (ex: despesas por categoria).
3. Deploy (ex: Render/Railway para a API + Postgres gerenciado).
