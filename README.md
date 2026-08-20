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
- **Pendencia** — id, usuario_id, descricao, valor, categoria_id, conta_id
  (opcional), recorrente (bool), dia_vencimento (1-31, se recorrente),
  data_vencimento (se avulsa), ativa (bool), criado_em, atualizado_em.
  "Definição" de uma conta a pagar/receber — recorrente (aluguel,
  assinaturas: um vencimento por mês) ou avulsa (um vencimento único).
  Não guarda status pago/pendente — isso é sempre calculado (ver decisão
  abaixo).
- **Movimentacao** ganhou três campos opcionais: `pendencia_id` e
  `pendencia_referencia` (marcar pendência como paga — ver abaixo), e
  `plano_id` (pagamento de um Plano de "quitar dívida").
- **Plano** — id, usuario_id, nome, tipo (`guardar_dinheiro`/
  `quitar_divida`), conta_id (obrigatório), mes_inicio, ativo, e um grupo
  de campos que variam conforme tipo/submodo: `guardar_modo` (`simples`/
  `reducao_categoria`), `criterio_reducao` (`percentual_receita`/
  `valor_fixo`), `alvo_percentual`, `alvo_valor_reducao`, `divida_modo`
  (`prazo`/`parcelas`), `pendencia_id` (parcelas — a Pendencia recorrente
  criada por trás), `valor_alvo`, `data_prazo`, `categoria_id`. Meta de
  "guardar dinheiro" (simples, ou reduzindo gasto numa categoria) ou de
  "quitar dívida" (prazo livre, ou parcelas). Progresso nunca é guardado
  — sempre calculado (ver decisão abaixo e `app/planos.py`).
- **Pendencia** ganhou `numero_parcelas` (opcional) — quando preenchido,
  a geração de vencimentos para depois desse tanto de meses, em vez de
  continuar indefinidamente. Usado por Plano de "quitar dívida por
  parcelas", que cria/gerencia uma Pendencia recorrente com esse teto.

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
- **Pendência não guarda status pago/pendente** — mesmo princípio do
  saldo: cada vencimento (mês, pra recorrente; a data única, pra avulsa)
  é considerado pago quando existe uma `Movimentacao` com
  `pendencia_id`==aquela pendência e `pendencia_referencia`==aquele
  vencimento específico. **Marcar como paga cria a Movimentação de
  verdade** (rota `POST /pendencias/{id}/pagar`) — não existe um "toggle"
  de status desacoplado do histórico real. `pendencia_referencia` é
  separado da `data` real do pagamento de propósito: permite pagar
  atrasado sem perder a informação de qual vencimento está sendo quitado.
  Um índice único parcial em `(pendencia_id, pendencia_referencia)`
  trava, no banco, contra pagar o mesmo vencimento duas vezes.
- **`Pendencia` sem campo `tipo` redundante** — mesmo princípio de
  `Movimentacao`: o tipo vem de `pendencia.categoria.tipo`.
- **`Pendencia.conta_id` é opcional** (ao contrário de
  `Movimentacao.conta_id`, que é obrigatório) — é só uma sugestão de
  conta padrão pro momento de pagar; a mesma pendência pode acabar sendo
  paga de contas diferentes em momentos diferentes, e a conta de fato
  usada é escolhida (obrigatoriamente) na hora de marcar como paga.
- **Relações protegidas por `RESTRICT` usam `passive_deletes=True`** —
  sem isso, o SQLAlchemy tenta "desvincular" as linhas filhas (setar a FK
  para `NULL`) *antes* de apagar o pai, em vez de deixar o `ON DELETE
  RESTRICT` do banco barrar a operação. Passava despercebido em
  `Categoria`/`Conta` porque `movimentacoes.categoria_id`/`conta_id` são
  `NOT NULL` (a tentativa de "desvincular" falhava por outro motivo, e o
  resultado observável — `409` — coincidia); ficou visível de verdade em
  `Pendencia`, onde `movimentacoes.pendencia_id` é opcional: sem
  `passive_deletes=True`, apagar uma pendência com pagamentos já feitos
  simplesmente funcionava, "descolando" o histórico sem avisar ninguém.
  Corrigido nas três relações.
- **Progresso de Plano nunca é guardado** — mesmo princípio de saldo e
  pendência: sempre calculado a partir da atividade financeira real (ver
  `app/planos.py`). "Guardar dinheiro" **não gera nenhuma Movimentação**
  — meta simples usa a diferença de saldo da conta antes/depois do início
  do plano; redução de categoria compara o gasto real mês a mês contra um
  alvo. "Quitar dívida" **gera despesa** a cada pagamento — modo prazo
  cria a Movimentação direto (`plano_id`); modo parcelas reaproveita a
  Pendencia recorrente (Fase 3) com `numero_parcelas`, sem duplicar a
  lógica de ciclos/pagamento já existente.
- **`Plano.conta_id` é obrigatório e fixo** (ao contrário de
  `Pendencia.conta_id`, que é opcional e só uma sugestão) — a conta
  define o próprio progresso (saldo ou gasto), então não faz sentido
  escolher outra a cada pagamento.
- **Baseline de "valor fixo vs. média"** (guardar dinheiro / redução por
  categoria) é calculado uma vez só, com os 3 meses *antes* do início do
  plano — fixo, não uma média móvel que mudaria junto com o próprio
  progresso.

## Estrutura do projeto

```
gerenciador-financas/
├── app/
│   ├── __init__.py
│   ├── database.py      # engine, SessionLocal, Base, get_db()
│   ├── models.py         # Usuario, Categoria, Conta, Movimentacao, Transferencia, Pendencia, Plano, Relatorio, enums
│   ├── schemas.py        # schemas Pydantic (Create/Update/Out) de cada entidade
│   ├── security.py       # hash de senha (bcrypt) + JWT (criar/validar token)
│   ├── contas.py          # cálculo de saldo por conta (individual, em lote, e "até uma data")
│   ├── pendencias.py      # cálculo de ciclos pendentes/atrasados de cada pendência
│   ├── planos.py          # cálculo de progresso de cada plano (guardar dinheiro / quitar dívida)
│   ├── relatorios.py      # lógica de agregação dos relatórios (personalizado/comparativo/automático/por-categoria)
│   ├── scheduler.py       # APScheduler: jobs semanal (seg 01:00) e mensal (dia 1, 01:00)
│   ├── main.py             # app FastAPI: rotas, CORS, start/stop do scheduler
│   └── seed.py            # popula categorias padrão (Salário, Alimentação, etc.)
├── front/
│   ├── index.html         # single-page: tela de auth + Início (grid: pendências, contas, nova movimentação)
│   ├── controle.html      # histórico completo + análise por categoria (gráfico e tabela)
│   ├── contas.html        # gestão de contas bancárias e transferências
│   ├── pendencias.html    # contas recorrentes/avulsas: criar, editar, marcar como paga
│   ├── planos.html        # metas de guardar dinheiro / quitar dívida: criar, editar, progresso
│   ├── relatorios.html    # relatórios: automáticos, personalizado, comparativo
│   ├── css/
│   │   ├── style.css       # design "livro-razão" (ver seção Front-end)
│   │   └── relatorios.css  # estilos específicos da página de relatórios
│   └── js/
│       ├── config.js       # API_BASE_URL
│       ├── utils.js        # formatação de moeda/data, toast (compartilhado)
│       ├── api.js          # wrapper de fetch: token, erros, endpoints
│       ├── sidebar.js      # sidebar recolhível compartilhada entre páginas logadas
│       ├── app.js          # lógica do Início: nova movimentação, resumo de contas e pendências
│       ├── controle.js     # histórico (filtros/paginação/edição) + análise por categoria
│       ├── contas.js       # criar/editar/apagar conta, transferências e o histórico delas
│       ├── pendencias.js   # criar/editar/apagar/pausar pendência, marcar ciclo como pago
│       ├── planos.js       # criar/editar/apagar/pausar plano, registrar pagamento
│       └── relatorios.js   # lógica da página de relatórios (usa Chart.js via CDN)
├── alembic/
│   ├── env.py             # já configurado para ler DATABASE_URL e os models
│   └── versions/          # inclui a migração da tabela `relatorios`, `pendencias` e `planos`
├── docker-compose.yml     # sobe o PostgreSQL local (porta 5433)
├── test_jwt.py            # bateria de testes automatizados: auth, CRUD, paginação
├── test_relatorios.py     # bateria de testes automatizados: relatórios
├── test_pendencias.py     # bateria de testes automatizados: pendências
├── test_planos.py         # bateria de testes automatizados: planos e metas
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
| GET | `/pendencias` | sim | Lista as pendências do usuário logado, cada uma com `ciclos` (vencimentos ainda sem pagamento, status `atrasada`/`a_vencer`) já calculado |
| POST | `/pendencias` | sim | Cria pendência (recorrente: `dia_vencimento`; avulsa: `data_vencimento`) |
| PATCH | `/pendencias/{id}` | sim | Edita pendência própria (campos opcionais — inclui pausar/reativar via `ativa`) |
| DELETE | `/pendencias/{id}` | sim | Remove pendência própria; `409` se houver pagamentos (Movimentações) vinculados |
| POST | `/pendencias/{id}/pagar` | sim | Marca um vencimento como pago — cria a Movimentação de verdade, vinculada; `409` se esse vencimento já foi pago, `422` se a data não corresponde a um ciclo pendente real |
| GET | `/planos` | sim | Lista os planos do usuário logado, cada um já com `progresso` calculado (formato varia conforme tipo/submodo) |
| POST | `/planos` | sim | Cria plano; `quitar_divida` no modo `parcelas` cria também a Pendencia recorrente por trás |
| PATCH | `/planos/{id}` | sim | Edita plano próprio (campos opcionais — não permite mudar tipo/submodo, só dados como valor/prazo/categoria/conta e pausar via `ativo`) |
| DELETE | `/planos/{id}` | sim | Remove plano próprio; `409` se houver pagamentos vinculados. No modo parcelas sem nenhum pagamento, também remove a Pendencia criada por trás |
| POST | `/planos/{id}/aportar` | sim | Registra um pagamento pra plano de `quitar_divida` no modo `prazo` (parcelas usam `POST /pendencias/{id}/pagar`); `422` se o plano não for desse tipo/modo |
| GET | `/saldo` | sim | Total de receitas, despesas e saldo geral do usuário logado (soma os saldos iniciais de todas as contas). Não é mais consumida pelo front-end no momento — o Início mostra saldo por conta em vez do total geral (ver Roadmap) |

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
neste ambiente (36 casos, todos passando). O script fica em `test_jwt.py`
na raiz do projeto, caso queira rodar de novo depois de alguma mudança.

**Nota sobre a resposta de `GET /movimentacoes`**: agora vem paginada —
`{"total": N, "skip": ..., "limit": ..., "itens": [...]}` — em vez de uma
lista simples. Se você já tinha algum teste manual esperando uma lista
direta, ajuste para ler `itens`.

## Pendências

Contas a pagar/receber — recorrentes (aluguel, assinaturas: um
vencimento por mês) ou avulsas (um vencimento único). `GET /pendencias`
calcula, pra cada uma, os **ciclos** ainda sem pagamento:

- **Recorrente**: um vencimento por mês, do mês em que a pendência foi
  criada até o mês atual (inclusive) — não retroage a antes da criação,
  nem antecipa meses futuros. Dias que não existem no mês (ex: 31 em
  fevereiro) caem pro último dia do mês.
- **Avulsa**: um único vencimento, a `data_vencimento`.
- Cada vencimento é `"atrasada"` (já passou) ou `"a_vencer"` (ainda não).
  Se o usuário ficar meses sem marcar uma recorrente como paga, cada mês
  aparece como um ciclo atrasado **separado** — a dívida acumulada fica
  visível, não é substituída pelo vencimento mais recente.

**"Marcar como paga" cria uma Movimentação de verdade** (`POST
/pendencias/{id}/pagar`, exige `data_vencimento` — qual ciclo — e
`conta_id`; `valor`/`descricao`/`data` são opcionais, com default o
valor/descrição da pendência e a data de hoje). Não existe "desmarcar
como paga": pra isso, apague a Movimentação gerada pela rota de sempre
(`DELETE /movimentacoes/{id}`) — como o vínculo é só uma referência
(`pendencia_id`/`pendencia_referencia`), apagar a Movimentação faz o
ciclo voltar a aparecer como pendente.

### Testes das pendências

`test_pendencias.py` cobre: avulsa a vencer/atrasada/paga, recorrente com
múltiplos meses de atraso acumulado (aparecendo como ciclos separados),
pagar cria a Movimentação certa (valor, conta, vínculo), bloqueio de
pagar o mesmo ciclo duas vezes (`409`) e de pagar uma data que não é um
ciclo real (`422`), `DELETE` bloqueado com histórico (`409`) e liberado
sem histórico (`204`), e isolamento entre usuários. Uma parte (o atraso
acumulado) não dá pra simular só com chamadas HTTP dentro do mesmo
minuto — o script acessa o banco diretamente (reaproveitando
`app.database`/`app.models`, que já são do próprio projeto) só pra
"voltar no tempo" o `criado_em` de uma pendência recém-criada; todo o
resto é HTTP puro, como os demais testes. **25/25 passando.**

## Planos e Metas

Dois tipos de plano, cada um com duas submodalidades — `GET /planos`
calcula o progresso de cada um (nunca guardado):

- **Guardar dinheiro** — nunca gera Movimentação; o progresso vem da
  atividade financeira que já existe.
  - *Simples*: `valor_alvo` + `data_prazo`. Progresso = saldo da conta
    hoje menos o saldo dela no dia anterior ao `mes_inicio` do plano
    (`calcular_saldo_conta(..., ate_data=...)` em `app/contas.py`).
  - *Redução de categoria*: `categoria_id` + `criterio_reducao` (
    `percentual_receita` ou `valor_fixo`) + `data_prazo`. Progresso é
    avaliado **mês a mês**: o gasto real na categoria (dentro da conta do
    plano) ficou dentro do alvo? Com `percentual_receita`, o alvo é um
    percentual da receita do mês (mesma conta). Com `valor_fixo`, o alvo
    é a média de gasto dos 3 meses *antes* do início (baseline fixo,
    calculado uma vez só) menos `alvo_valor_reducao`. Resposta inclui a
    lista mensal (`gasto`, `alvo`, `cumpriu`) e o resumo "X de Y meses".
- **Quitar dívida** — todo pagamento gera despesa de verdade.
  - *Prazo*: `valor_alvo` (total) + `data_prazo`, pagamentos avulsos
    (`POST /planos/{id}/aportar`) vinculados via `plano_id`. Progresso =
    soma paga / total.
  - *Parcelas*: `valor_alvo` na criação é o valor **de cada parcela**;
    junto com `numero_parcelas` e `dia_vencimento`, o plano cria uma
    `Pendencia` recorrente por trás (com `numero_parcelas` travando o
    fim) e guarda `pendencia_id` — o total (`parcela × numero_parcelas`)
    fica salvo em `Plano.valor_alvo`. Pagar uma parcela **é** `POST
    /pendencias/{id}/pagar` (não existe rota própria) — a conta usada é
    sempre a do plano; a Movimentação resultante grava `pendencia_id` **e**
    `plano_id`, então a mesma pendência continua aparecendo normalmente
    em `GET /pendencias`.

`Plano.conta_id` é **obrigatório e fixo** (ao contrário de
`Pendencia.conta_id`, que é opcional): a conta define o progresso, então
não há escolha de conta por pagamento. `PATCH /planos/{id}` não aceita
mudar tipo/submodo — só dados como valor, prazo, categoria, conta e
pausar/reativar (`ativo`); pra mudar de modalidade, apague e crie outro.

### Testes dos planos

`test_planos.py` cobre as 4 combinações tipo/submodo com números
conferidos à mão: saldo antes/depois da conta (simples), meses
cumpridos/não cumpridos nos dois critérios de redução (percentual e valor
fixo, com baseline fixo), aportes avulsos e progresso (dívida por prazo),
criação da Pendencia por trás + pagamento de parcela gravando
`pendencia_id` e `plano_id` + `numero_parcelas` travando os ciclos mesmo
com vários meses de atraso acumulado (dívida por parcelas), `DELETE`
bloqueado com pagamento e liberado sem (inclusive removendo a Pendencia
órfã no modo parcelas), validações de erro de criação por combinação
tipo/modo, e isolamento entre usuários. **44/44 passando.**

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
persistido, um único botão de recolher/expandir — vive na própria
sidebar). A página **Início** (`index.html`) é o resumo/atalhos do dia a
dia: grid com card de pendências (as mais urgentes, só leitura), card de
saldo por conta (só leitura), o formulário de nova movimentação (com
conta obrigatória e criação rápida de categoria própria embutida) e um
placeholder "em breve" (envio de arquivo, ainda sem funcionalidade). A
página **Controle** (`controle.html`) é a mais analítica: o histórico
completo (filtros/paginação/ordenação, edição via modal, exclusão com
confirmação), um gráfico de gastos por categoria do mês atual, e uma
tabela-resumo por categoria (total, % do tipo, mínimo/média/máximo e a
evolução dos últimos 3 meses). A página **Contas** (`contas.html`)
concentra a gestão de **contas bancárias** (criar/editar/apagar, saldo
calculado por conta) e **transferências** entre contas, incluindo o
histórico das transferências já feitas. A página **Pendências**
(`pendencias.html`) lista contas recorrentes e avulsas com seus
vencimentos pendentes/atrasados, permite criar/editar/pausar/apagar, e
marcar cada vencimento como pago (confirmando conta/valor/data). E uma
página **Planos e Metas** (`planos.html`) traz um formulário em cascata
(tipo → submodo → campos daquele submodo) e cards de progresso — barra
pra meta simples/dívida, checklist mensal pra redução de categoria, lista
de parcelas (reaproveitando o mesmo componente visual de Pendências) pra
dívida por parcelas. E uma página de **relatórios** (`relatorios.html`)
com as três modalidades — automáticos, personalizado, comparativo —
usando [Chart.js](https://www.chartjs.org/) via CDN para os gráficos
(usado também em Controle, pro gráfico de categoria). Sessão expirada
(token vencido) redireciona automaticamente para a tela de login em
todas as páginas. Com Planos e Metas, todos os itens da sidebar estão
ativos — não sobrou nenhum "em breve".

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

### Por categoria

`GET /relatorios/por-categoria?data_inicio=...&data_fim=...&tipo=...&meses_recentes=...`

Agregado por categoria — todos os parâmetros são opcionais. Sem
`data_inicio`/`data_fim`, considera todo o histórico do usuário logado.
Pra cada categoria com movimentação no período: `total`, `percentual`
(dentro do total do MESMO TIPO, só entre as categorias retornadas),
`quantidade`, `minimo`, `media`, `maximo`. Com `meses_recentes=N`, cada
categoria ganha também `mensal`: o total dela em cada um dos últimos N
meses corridos (incluindo o atual), do mais antigo pro mais recente.

Usada de duas formas na página **Controle**: o gráfico de pizza chama com
`data_inicio`/`data_fim` do mês corrente e `tipo=despesa`; a tabela-resumo
chama sem período (histórico completo) e com `meses_recentes=3`.

**Decisão de design**: a agregação é feita em SQL (`GROUP BY`), não
carregando as movimentações pra memória como `/relatorios/personalizado`
faz — aqui o período pode ser "desde sempre", então precisa escalar
(mesmo padrão de `calcular_saldos_contas` em `app/contas.py`).

### Rotas de relatório

| Método | Rota | Descrição |
|---|---|---|
| GET | `/relatorios/personalizado` | Relatório sob demanda (não fica salvo) |
| GET | `/relatorios/comparativo` | Comparação entre duas categorias (não fica salvo) |
| GET | `/relatorios/por-categoria` | Agregado por categoria: total, %, mín/média/máx e, opcionalmente (`meses_recentes`), quebra mensal — usada pelo gráfico e pela tabela de Controle |
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
combinada, e (novo) total/%/mín/média/máx e quebra mensal de
`/relatorios/por-categoria` — essa última com datas relativas a "hoje"
(calculadas no próprio teste, independente da implementação), já que a
quebra mensal depende da data de execução. Também cobre os erros
(`data_fim` antes de `data_inicio`, categorias iguais no comparativo,
categoria inexistente/de outro usuário) e o ciclo gerar-agora → listar →
obter → isolamento entre usuários. **62/62 passando.**

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

- ✅ **Fase 1 — Sidebar + Contas bancárias** (v2.1.0): concluída. Refinada
  depois: contas/transferências ganharam página própria (`contas.html`),
  o Início passou a mostrar só um resumo de saldo por conta, e sobrou
  apenas um botão de recolher/expandir a sidebar (o duplicado no topo do
  conteúdo foi removido).
- ✅ **Fase 2 — Divisão Início / Controle** (v2.2.0): concluída. Início
  ficou só com resumo/atalhos (saldo por conta, nova movimentação);
  Controle (`controle.html`, nova) ganhou o histórico completo + análise
  por categoria (gráfico do mês, tabela com total/%/mín/média/máx/últimos
  3 meses) — rota nova `GET /relatorios/por-categoria` no backend.
- ✅ **Fase 3 — Pendências** (v2.3.0): concluída. Nova tabela `Pendencia`
  (recorrente ou avulsa) — status pago/pendente nunca é guardado, sempre
  calculado a partir das Movimentações vinculadas; marcar como paga cria
  a Movimentação de verdade. Página nova `pendencias.html`, card ativado
  no grid do Início, rotas `GET/POST/PATCH/DELETE /pendencias` + `POST
  /pendencias/{id}/pagar`. Sem subcategorias ainda (fora de escopo desde
  a Fase 2, adiado pra mini-fase própria).
- ✅ **Fase 4 — Planos e Metas** (v2.4.0): concluída. Nova tabela `Plano`
  — "guardar dinheiro" (meta simples via saldo da conta, ou redução de
  gasto numa categoria) e "quitar dívida" (prazo livre, ou parcelas —
  reaproveitando a Pendencia recorrente da Fase 3 com `numero_parcelas`
  novo). Progresso nunca é guardado, sempre calculado. Página nova
  `planos.html`, rotas `GET/POST/PATCH/DELETE /planos` + `POST
  /planos/{id}/aportar`. Com essa fase, todos os itens da sidebar
  planejados desde o início do projeto estão implementados.
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