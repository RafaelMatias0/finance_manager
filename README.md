# Gerenciador de Finanças — Backend

Backend em **FastAPI + SQLAlchemy + PostgreSQL + Alembic**, começando pela
modelagem do banco de dados. O front-end (HTML/CSS/JS puro) será feito por
último; até lá, as rotas serão testadas pelo Swagger (`/docs`).

## Modelo de dados

- **Usuario** — id (UUID), nome, email (único), senha_hash, criado_em, atualizado_em
- **Categoria** — id, nome, tipo (`receita`/`despesa`), usuario_id (nulo = categoria
  padrão/global; preenchido = categoria criada pelo próprio usuário), criado_em
- **Conta** — id, usuario_id, nome_banco, apelido (opcional), saldo_inicial
  (Numeric 12,2), criado_em. Registro "de visão" de uma conta bancária —
  só o nome do banco e um saldo inicial, sem qualquer integração real.
- **Movimentacao** — id, valor (Numeric 12,2), descricao, data, usuario_id,
  categoria_id, conta_id, criado_em, atualizado_em
- **Transferencia** — id, usuario_id, conta_origem_id, conta_destino_id,
  valor (Numeric 12,2), descricao (opcional), data, criado_em. Movimento
  entre duas contas do próprio usuário — não é receita nem despesa.

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
- **`Movimentacao.conta_id` é obrigatório**, mesmo padrão `RESTRICT` de
  `categoria_id` — toda movimentação pertence a uma conta bancária do
  usuário.
- **Transferência como tabela própria, separada de Movimentacao** — uma
  transferência entre contas não é receita nem despesa, então não deveria
  ter Categoria nem aparecer nos relatórios (que derivam o tipo a partir de
  `Categoria.tipo`). Colocá-la em `Movimentacao` exigiria gambiarras (uma
  categoria fake "Transferência", ou um campo de tipo redundante que o
  projeto evita desde o v1). Como tabela própria, o saldo de cada conta
  soma transferências recebidas e subtrai as enviadas, e o total do
  usuário nunca é afetado (é sempre soma zero entre contas do mesmo dono).
- **Saldo de conta nunca é persistido** — mesma lógica do saldo geral do
  usuário: é sempre `saldo_inicial + receitas - despesas + transferências
  recebidas - transferências enviadas`, calculado na hora.

## Estrutura do projeto

```
gerenciador-financas/
├── app/
│   ├── __init__.py
│   ├── database.py      # engine, SessionLocal, Base, get_db()
│   ├── models.py         # Usuario, Categoria, Conta, Movimentacao, Transferencia, Relatorio, enums
│   ├── schemas.py        # schemas Pydantic (Create/Update/Out) de cada entidade
│   ├── security.py       # hash de senha (bcrypt) + JWT (criar/validar token)
│   ├── contas.py          # cálculo de saldo por conta (individual e em lote)
│   ├── relatorios.py      # lógica de agregação dos relatórios (personalizado/comparativo/automático)
│   ├── scheduler.py       # APScheduler: jobs semanal (seg 01:00) e mensal (dia 1, 01:00)
│   ├── main.py             # app FastAPI: rotas, CORS, start/stop do scheduler
│   └── seed.py            # popula categorias padrão (Salário, Alimentação, etc.)
├── front/
│   ├── index.html         # single-page: telas de auth + dashboard
│   ├── relatorios.html    # relatórios: automáticos, personalizado, comparativo
│   ├── css/
│   │   ├── style.css       # design "livro-razão" (ver seção Front-end)
│   │   └── relatorios.css  # estilos específicos da página de relatórios
│   └── js/
│       ├── config.js       # API_BASE_URL
│       ├── utils.js        # formatação de moeda/data, toast (compartilhado)
│       ├── api.js          # wrapper de fetch: token, erros, endpoints
│       ├── sidebar.js      # sidebar recolhível compartilhada entre páginas logadas
│       ├── app.js          # lógica do dashboard: forms, tabela, paginação, modais, contas, transferência
│       └── relatorios.js   # lógica da página de relatórios (usa Chart.js via CDN)
├── alembic/
│   ├── env.py             # já configurado para ler DATABASE_URL e os models
│   └── versions/          # inclui a migração da tabela `relatorios`
├── docker-compose.yml     # sobe o PostgreSQL local (porta 5433)
├── test_jwt.py            # bateria de testes automatizados: auth, CRUD, paginação
├── test_relatorios.py     # bateria de testes automatizados: relatórios
├── alembic.ini
├── requirements.txt
├── .env.example
├── CHANGELOG.md
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
   ⚠️ A partir da v2.1.0 (`Movimentacao.conta_id` obrigatório), se você já
   tinha um banco de testes de versões anteriores, rode
   `alembic downgrade base` antes do `upgrade head` — a migração de contas
   assume banco limpo, sem dados antigos pra preservar. Também ajuste o
   `down_revision` em `alembic/versions/0004_contas_e_transferencias.py`
   para apontar pro seu head atual antes de rodar (`alembic heads`).

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
| GET | `/contas` | sim | Lista as contas do usuário logado, cada uma já com `saldo_atual` calculado |
| POST | `/contas` | sim | Cria conta bancária (nome do banco, apelido opcional, saldo inicial) |
| PATCH | `/contas/{id}` | sim | Edita conta própria (campos opcionais — só os enviados mudam) |
| DELETE | `/contas/{id}` | sim | Remove conta própria; `409` se houver movimentações/transferências vinculadas |
| POST | `/movimentacoes` | sim | Cria receita ou despesa para o usuário logado (exige `conta_id`) |
| GET | `/movimentacoes` | sim | Histórico do usuário logado, filtros: `tipo`, `categoria_id`, `conta_id`, `data_inicio`, `data_fim`; paginação: `skip`, `limit`; ordenação: `ordenar_por` (`data`\|`valor`\|`criado_em`), `ordem` (`asc`\|`desc`) |
| PATCH | `/movimentacoes/{id}` | sim | Edita movimentação própria (campos opcionais — só os enviados mudam) |
| DELETE | `/movimentacoes/{id}` | sim | Remove movimentação (só se for do usuário logado — senão `404`) |
| GET | `/transferencias` | sim | Histórico de transferências entre contas do usuário logado |
| POST | `/transferencias` | sim | Transfere valor entre duas contas próprias (não é receita nem despesa) |
| GET | `/saldo` | sim | Total de receitas, despesas e saldo geral do usuário logado (soma os saldos iniciais de todas as contas) |

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

**O que tem implementado:** cadastro/login, sidebar recolhível compartilhada
entre as páginas logadas (item ativo destacado, estado colapsado
persistido), tela com saldo (receitas, despesas, saldo), painel de
**contas bancárias** (criar/editar/apagar, saldo calculado por conta,
transferência entre contas), formulário de nova movimentação (com conta
obrigatória e criação rápida de categoria própria embutida), histórico
com filtros/paginação/ordenação (incluindo filtro por conta), edição via
modal, exclusão com confirmação, logout, e uma página de **relatórios**
(`relatorios.html`) com as três modalidades — automáticos, personalizado,
comparativo — usando [Chart.js](https://www.chartjs.org/) via CDN para os
gráficos. Sessão expirada (token vencido) redireciona automaticamente
para a tela de login em ambas as páginas. Os itens "Pendências" e "Planos
e Metas" já aparecem na sidebar, marcados como "em breve" — são as
próximas fases.

O contrato HTTP entre front e back (nomes de campo, formato das respostas,
FormData sempre enviando valores como string) foi validado com chamadas
reais contra a API neste ambiente.

## Relatórios (v2.0)

### Automáticos

Um scheduler in-process (APScheduler, roda dentro do próprio processo do
`uvicorn` — sem infra extra) gera, para cada usuário cadastrado:

- **Semanal**: toda segunda-feira às 01:00, cobrindo a semana (segunda a
  domingo) que acabou de fechar.
- **Mensal**: todo dia 1 às 01:00, cobrindo o mês inteiro anterior.

Cada execução salva um **snapshot** (tabela `relatorios`, coluna `dados`
em JSONB) — não recalcula na hora de exibir, e preserva o retrato daquele
período mesmo que o usuário edite ou apague movimentações depois. A lista
fica disponível em `GET /relatorios` e cada um em `GET /relatorios/{id}`.

Como não há sistema de e-mail/notificação no projeto, "gerar automaticamente"
aqui significa: fica salvo e aparece na aba **Automáticos** da página de
relatórios — não há envio ativo pro usuário.

Pra não precisar esperar a próxima segunda 01:00 (ou o próximo dia 1) pra
ver/testar, tem `POST /relatorios/gerar-agora?tipo=automatico_semanal` (ou
`automatico_mensal`), que gera na hora. O botão "Gerar agora" na aba
Automáticos chama essa rota — é uma facilidade de teste/demonstração, não
o fluxo principal.

### Personalizado

`GET /relatorios/personalizado?data_inicio=...&data_fim=...&tipo=...&categoria_id=...`

- `data_inicio`/`data_fim`: obrigatórios.
- `tipo` (opcional): `receita`, `despesa`, ou omitido = todos.
- `categoria_id` (opcional): além de aparecer no histórico normalmente,
  ativa o **gráfico de participação** dessa categoria.

Retorna: histórico do período (respeitando os filtros), saldo do período
(`total_receitas`, `total_despesas`, `saldo`), um gráfico diário (receitas
e despesas por dia, com todos os dias do intervalo mesmo os sem
movimentação) e, se `categoria_id` foi informado, a participação dela.

**Decisão de design**: a "participação da categoria no total" é calculada
contra o total do **mesmo tipo** dela no período (ex: "Alimentação"
representa X% do total de *despesas* do período) — não contra
receitas+despesas somadas, que não faria sentido misturar (foi confirmado
com o usuário durante o desenvolvimento).

### Comparativo

`GET /relatorios/comparativo?data_inicio=...&data_fim=...&categoria_id_1=...&categoria_id_2=...`

Sempre retorna: totais de cada categoria, histórico combinado das duas, e
um gráfico de linhas com o total diário de cada uma. O resto depende do
`modo`:

- **`tipos_diferentes`** (uma receita, uma despesa): `saldo_diferenca` =
  total da receita menos total da despesa.
- **`mesmo_tipo`** (as duas receita, ou as duas despesa): `saldo_soma` =
  soma das duas, mais dois gráficos de pizza — participação de cada
  categoria isolada no total daquele tipo no período, e participação das
  duas *somadas* no mesmo total.

### Rotas de relatório

| Método | Rota | Descrição |
|---|---|---|
| GET | `/relatorios/personalizado` | Relatório sob demanda (não fica salvo) |
| GET | `/relatorios/comparativo` | Comparação entre duas categorias (não fica salvo) |
| GET | `/relatorios` | Lista os relatórios automáticos salvos do usuário |
| GET | `/relatorios/{id}` | Um relatório automático salvo específico |
| POST | `/relatorios/gerar-agora?tipo=` | Gera um automático na hora (teste/demonstração) |

Todas exigem token, e um usuário nunca vê relatório/categoria de outro
(testado — ver abaixo).

### Testes dos relatórios

`test_relatorios.py` cria movimentações num período fixo com valores
conhecidos e confere a matemática das agregações **à mão** (não só que a
rota responde 200) — histórico, saldo, gráfico diário dia a dia, percentual
de participação, diferença/soma no comparativo, participação individual e
combinada. Também cobre os erros (`data_fim` antes de `data_inicio`,
categorias iguais no comparativo, categoria inexistente/de outro usuário) e
o ciclo gerar-agora → listar → obter → isolamento entre usuários.
**45/45 passando.**

O front-end (`relatorios.js`) foi validado com um teste de contrato HTTP
(chamadas reais contra a API, conferindo que todo campo que o JS lê
realmente existe na resposta) — **11/11 passando**. Como nas versões
anteriores, não foi possível abrir um navegador de verdade neste ambiente
(Chromium via apt e Playwright via pip, ambos bloqueados) — **os gráficos
(Chart.js) e a navegação entre abas precisam ser conferidos visualmente
por você.**

## Roadmap (fases em andamento)

Combinado com o usuário: cada fase só entra em código depois de planejada
e aprovada.

- ✅ **Fase 1 — Sidebar + Contas bancárias** (v2.1.0): concluída.
- ⏳ **Fase 2 — Divisão Início / Controle**: nova página de Início (resumo
  + atalhos do dia a dia), página atual vira "Controle" (mais analítica).
- ⏳ **Fase 3 — Pendências**: lançamentos futuros com vencimento e contas
  fixas recorrentes (status pago/pendente).
- ⏳ **Fase 4 — Planos e Metas**: metas de economia + quitação de dívidas
  no mesmo sistema.
- ⏳ **Protótipo visual**: decisão pendente entre manter o "livro-razão"
  claro ou migrar para um dashboard escuro (referências anexadas pelo
  usuário) — a decidir olhando um protótipo antes de aplicar em toda a
  base.
- Cartões de crédito: fora do escopo por enquanto (decisão do usuário).

## Próximos passos técnicos

1. Refresh token / expiração mais robusta (hoje o token expira em 60min,
   sem renovação — o usuário precisa logar de novo).
2. Deploy (ex: Render/Railway para a API + Postgres gerenciado). Atenção:
   o scheduler in-process assume um único processo/worker — em produção
   com múltiplos workers, cada um agendaria o job e duplicaria os
   relatórios; precisaria virar um worker separado (ex: Celery beat) ou
   usar um lock distribuído.